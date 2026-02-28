"""Step 1 — Async BFS site discovery for the site audit pipeline.

Builds a purpose-built async BFS crawler from scratch using httpx.AsyncClient.
Performs 4-phase discovery:
  Phase 1: robots.txt fetch + AI-bot access detection + llms.txt check
  Phase 2: Sitemap XML parsing (recursive, handles sitemap index files)
  Phase 3: RSS/Atom feed discovery
  Phase 4: BFS crawl with asyncio.Semaphore concurrency control

CRITICAL: This module does NOT import from core/gap_analysis/steps/s1_embed_assets.py.

Usage::

    output = await discover_site(domain="example.com", max_pages=200, max_depth=4)
    # output.pages_with_html  -> list[tuple[str, str]]  (url, html) pairs
    # output.ai_bot_access    -> AIBotAccessResult
    # output.sitemap_health   -> SitemapHealthResult
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from core.models.site_audit import AIBotAccessResult, SitemapHealthResult
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Extensions that are never HTML content — skip without fetching.
_SKIP_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".rar",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".ico", ".xml", ".json", ".csv",
})

#: Common sitemap paths probed when robots.txt lists none.
_COMMON_SITEMAP_PATHS: tuple[str, ...] = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
    "/sitemap-index.xml",
)

#: AI crawler ``User-agent`` names to check in robots.txt.
_AI_BOTS: tuple[str, ...] = (
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "CCBot",
)

#: Sitemap XML namespace.
_SITEMAP_NS: dict[str, str] = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

#: Default user-agent sent by the site audit crawler.
_DEFAULT_UA: str = "DeepPresence-SiteAudit/1.0"

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class S1DiscoveryOutput:
    """All outputs produced by the discovery step.

    Attributes:
        pages_with_html: Pairs of (url, html_string) for each successfully
            fetched HTML page.  Used by s2_analyze_pages.
        ai_bot_access: Summary of which AI crawlers are allowed.
        sitemap_health: Summary of sitemap coverage and health.
        crawl_depth_map: ``{normalized_url: depth}`` for every discovered URL.
        redirect_map: ``{original_url: final_url}`` for redirected requests.
        status_code_map: ``{url: http_status_code}`` for every fetched URL.
        robots_txt_raw: Raw text of /robots.txt (empty string if unavailable).
        discovered_urls: All normalized URLs found during discovery (superset
            of pages_with_html — includes non-HTML, disallowed, skipped pages).
    """

    pages_with_html: list[tuple[str, str]] = field(default_factory=list)
    ai_bot_access: AIBotAccessResult = field(default_factory=AIBotAccessResult)
    sitemap_health: SitemapHealthResult = field(default_factory=SitemapHealthResult)
    crawl_depth_map: dict[str, int] = field(default_factory=dict)
    redirect_map: dict[str, str] = field(default_factory=dict)
    status_code_map: dict[str, int] = field(default_factory=dict)
    robots_txt_raw: str = ""
    discovered_urls: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# URL utilities (pure, no I/O)
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    Strips the fragment, lowercases scheme and host, and removes a trailing
    slash from the path (unless the path is just ``"/"``).

    Args:
        url: Absolute or relative URL string.

    Returns:
        Normalized URL string.
    """
    try:
        parsed = urlparse(url)
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            fragment="",
        )
        result = urlunparse(normalized)
        # Remove trailing slash only if path has content beyond "/"
        if result.endswith("/") and urlparse(result).path not in ("", "/"):
            result = result.rstrip("/")
        return result
    except Exception:
        return url


def is_same_domain(url: str, domain: str) -> bool:
    """Return True only when *url* belongs to exactly *domain*.

    Subdomains are treated as different domains.  e.g.
    ``blog.example.com`` is NOT the same domain as ``example.com``.

    Args:
        url: Absolute URL string.
        domain: Domain string, e.g. ``"example.com"``.

    Returns:
        True if the netloc of *url* equals *domain* (case-insensitive).
    """
    netloc = urlparse(url).netloc.lower()
    # Strip port if present
    netloc = netloc.split(":")[0]
    return netloc == domain.lower()


def should_skip_url(url: str) -> bool:
    """Return True when *url* should never be fetched (non-HTML resource).

    Checks based on path extension only — no network I/O.

    Args:
        url: Absolute URL string.

    Returns:
        True if the URL path ends with a known non-HTML extension.
    """
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _SKIP_EXTENSIONS)


def _extract_links(html: str, base_url: str, domain: str) -> list[str]:
    """Extract and normalize internal <a href> links from HTML.

    Filters out: fragments, mailto:, tel:, javascript: links; non-same-domain
    URLs; and known non-HTML extensions.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative hrefs.
        domain: Allowed domain string for same-domain filtering.

    Returns:
        List of deduplicated normalized absolute URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if not href:
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        normalized = normalize_url(absolute)
        if is_same_domain(normalized, domain) and not should_skip_url(normalized):
            links.add(normalized)
    return list(links)


# ---------------------------------------------------------------------------
# robots.txt helpers
# ---------------------------------------------------------------------------


async def _fetch_robots_txt(
    domain: str, client: httpx.AsyncClient, timeout: float
) -> tuple[str, RobotFileParser]:
    """Fetch /robots.txt and build a RobotFileParser.

    Args:
        domain: Domain to fetch robots.txt from (scheme inferred as https).
        client: httpx async client.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (raw_text, robot_parser).  On any error the raw_text is ""
        and the parser is initialised with an empty string (allows everything).
    """
    robots_url = f"https://{domain}/robots.txt"
    rp = RobotFileParser()
    raw = ""
    try:
        resp = await client.get(robots_url, timeout=timeout)
        if resp.status_code < 400:
            raw = resp.text
            rp.parse(raw.splitlines())
        else:
            rp.parse([])
    except Exception as exc:
        logger.warning("robots.txt fetch failed for %s: %s", domain, exc)
        rp.parse([])
    return raw, rp


def _parse_ai_bot_access(
    raw_robots: str,
    rp: RobotFileParser,
    homepage: str,
) -> AIBotAccessResult:
    """Determine which AI crawlers are blocked by robots.txt.

    A bot is considered blocked only when ``Disallow: /`` (root disallow)
    appears under its ``User-agent`` directive.  Partial blocks are not
    flagged here — they are tracked via the crawler's robots respect logic.

    Args:
        raw_robots: Raw robots.txt content.
        rp: Parsed RobotFileParser instance.
        homepage: Homepage URL used to test ``can_fetch``.

    Returns:
        :class:`~core.models.site_audit.AIBotAccessResult` instance.
    """
    result = AIBotAccessResult(robots_txt_exists=bool(raw_robots.strip()))

    bot_fields = {
        "GPTBot": "gptbot_allowed",
        "ClaudeBot": "claudebot_allowed",
        "PerplexityBot": "perplexitybot_allowed",
        "Google-Extended": "google_extended_allowed",
        "CCBot": "ccbot_allowed",
    }

    for bot_name, field_name in bot_fields.items():
        allowed = rp.can_fetch(bot_name, homepage)
        object.__setattr__(result, field_name, allowed)  # AIBotAccessResult is not frozen

    return result


def _parse_sitemap_urls_from_robots(raw_robots: str) -> list[str]:
    """Extract ``Sitemap:`` directive URLs from robots.txt text.

    Args:
        raw_robots: Raw robots.txt content.

    Returns:
        List of sitemap URL strings found in ``Sitemap:`` directives.
    """
    if not raw_robots:
        return []
    urls: list[str] = []
    for line in raw_robots.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            url = stripped.split(":", 1)[1].strip()
            if url:
                urls.append(url)
    return urls


# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------


async def _fetch_xml(
    url: str, client: httpx.AsyncClient, timeout: float
) -> Optional[ET.Element]:
    """Fetch *url* and parse it as XML, returning the root element.

    Args:
        url: XML URL to fetch.
        client: httpx async client.
        timeout: Request timeout in seconds.

    Returns:
        Parsed root ``ET.Element``, or ``None`` on any error.
    """
    try:
        resp = await client.get(url, timeout=timeout)
        if resp.status_code >= 400:
            return None
        text = resp.text
        if not text.strip():
            return None
        return ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("XML parse error for %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to fetch XML at %s: %s", url, exc)
        return None


async def _parse_sitemap(
    sitemap_url: str,
    client: httpx.AsyncClient,
    timeout: float,
    domain: str,
    visited: set[str],
    max_urls: int = 10_000,
) -> tuple[list[str], bool]:
    """Recursively fetch and parse a sitemap or sitemap index.

    Args:
        sitemap_url: URL of the sitemap to fetch.
        client: httpx async client.
        timeout: Request timeout in seconds.
        domain: Allowed domain for URL filtering.
        visited: Set of already-visited sitemap URLs (mutated in place).
        max_urls: Maximum number of page URLs to collect.

    Returns:
        Tuple of (page_urls, has_index) where page_urls is a list of
        normalized page URLs and has_index indicates a sitemap index was found.
    """
    if sitemap_url in visited:
        return [], False
    visited.add(sitemap_url)

    root = await _fetch_xml(sitemap_url, client, timeout)
    if root is None:
        return [], False

    # Strip namespace to get local tag name
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    urls: list[str] = []
    has_index = False

    if tag == "sitemapindex":
        has_index = True
        child_sitemap_urls: list[str] = []
        # With namespace
        for sm_el in root.findall("sm:sitemap", _SITEMAP_NS):
            loc_el = sm_el.find("sm:loc", _SITEMAP_NS)
            if loc_el is not None and loc_el.text:
                child_sitemap_urls.append(loc_el.text.strip())
        # Without namespace (fallback)
        for sm_el in root.findall("sitemap"):
            loc_el = sm_el.find("loc")
            if loc_el is not None and loc_el.text:
                child_sitemap_urls.append(loc_el.text.strip())

        for child_url in child_sitemap_urls:
            if len(urls) >= max_urls:
                break
            child_urls, _ = await _parse_sitemap(
                child_url, client, timeout, domain, visited, max_urls
            )
            urls.extend(child_urls)

    elif tag == "urlset":
        # With namespace
        for url_el in root.findall("sm:url", _SITEMAP_NS):
            loc_el = url_el.find("sm:loc", _SITEMAP_NS)
            if loc_el is not None and loc_el.text:
                normalized = normalize_url(loc_el.text.strip())
                if is_same_domain(normalized, domain):
                    urls.append(normalized)
        # Without namespace (fallback)
        for url_el in root.findall("url"):
            loc_el = url_el.find("loc")
            if loc_el is not None and loc_el.text:
                normalized = normalize_url(loc_el.text.strip())
                if is_same_domain(normalized, domain):
                    urls.append(normalized)

    return urls, has_index


async def _discover_from_sitemaps(
    domain: str,
    raw_robots: str,
    client: httpx.AsyncClient,
    timeout: float,
) -> SitemapHealthResult:
    """Parse all sitemaps for *domain* and return a health summary.

    Args:
        domain: Domain being audited.
        raw_robots: Raw robots.txt content for sitemap directive extraction.
        client: httpx async client.
        timeout: Request timeout in seconds.

    Returns:
        :class:`~core.models.site_audit.SitemapHealthResult` with discovered
        URLs and health information.
    """
    sitemap_urls_from_robots = _parse_sitemap_urls_from_robots(raw_robots)
    all_sitemap_urls: list[str] = list(sitemap_urls_from_robots)

    # Fall back to common paths if robots.txt listed none
    if not all_sitemap_urls:
        for path in _COMMON_SITEMAP_PATHS:
            all_sitemap_urls.append(f"https://{domain}{path}")

    visited_sitemaps: set[str] = set()
    page_urls: list[str] = []
    errors: list[str] = []
    has_index = False

    for sitemap_url in all_sitemap_urls:
        try:
            found_urls, is_index = await _parse_sitemap(
                sitemap_url, client, timeout, domain, visited_sitemaps
            )
            if found_urls:
                page_urls.extend(found_urls)
                if is_index:
                    has_index = True
        except Exception as exc:
            errors.append(f"{sitemap_url}: {exc}")

    return SitemapHealthResult(
        has_sitemap=len(page_urls) > 0,
        sitemap_url_count=len(page_urls),
        sitemap_urls=list(set(page_urls)),
        sitemap_errors=errors,
        has_sitemap_index=has_index,
    )


# ---------------------------------------------------------------------------
# RSS / Atom discovery
# ---------------------------------------------------------------------------


def _discover_feeds_from_html(html: str, base_url: str) -> list[str]:
    """Extract RSS/Atom feed URLs from HTML ``<link>`` tags.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative feed hrefs.

    Returns:
        List of absolute feed URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    feeds: list[str] = []
    for link in soup.find_all("link", type=True):
        link_type = (link.get("type") or "").lower()
        if "rss" in link_type or "atom" in link_type:
            href = (link.get("href") or "").strip()
            if href:
                feeds.append(urljoin(base_url, href))
    return feeds


async def _extract_rss_urls(
    feed_url: str, client: httpx.AsyncClient, timeout: float, domain: str
) -> list[str]:
    """Fetch an RSS/Atom feed and extract article page URLs.

    Args:
        feed_url: URL of the RSS or Atom feed.
        client: httpx async client.
        timeout: Request timeout in seconds.
        domain: Allowed domain for URL filtering.

    Returns:
        List of normalized page URLs from feed entries.
    """
    root = await _fetch_xml(feed_url, client, timeout)
    if root is None:
        return []

    urls: list[str] = []

    # RSS 2.0: <channel><item><link>
    for item in root.iter("item"):
        link_el = item.find("link")
        if link_el is not None and link_el.text:
            normalized = normalize_url(link_el.text.strip())
            if is_same_domain(normalized, domain):
                urls.append(normalized)

    # Atom: <entry><link href="...">
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = (link.get("href") or "").strip()
            if href:
                normalized = normalize_url(href)
                if is_same_domain(normalized, domain):
                    urls.append(normalized)

    return urls


# ---------------------------------------------------------------------------
# Main crawler class
# ---------------------------------------------------------------------------


class AsyncSiteCrawler:
    """Async BFS crawler that discovers pages on a single domain.

    Phase 1: Fetch robots.txt, detect AI bot access, check llms.txt.
    Phase 2: Parse sitemaps (recursive, handles sitemap index).
    Phase 3: Discover RSS/Atom feeds from homepage HTML.
    Phase 4: BFS crawl with asyncio.Semaphore concurrency control.

    Args:
        domain: Domain to crawl (e.g. ``"example.com"``).
        max_pages: Stop crawling after this many HTML pages are fetched.
        max_depth: Maximum BFS depth (seed URLs are depth 0).
        concurrency: Maximum concurrent HTTP requests.
        respect_robots: If True, skip URLs disallowed by robots.txt.
        timeout: Per-request timeout in seconds.
        user_agent: User-agent header sent with every request.
    """

    def __init__(
        self,
        domain: str,
        max_pages: int = 200,
        max_depth: int = 4,
        concurrency: int = 30,
        respect_robots: bool = True,
        timeout: float = 15.0,
        user_agent: str = _DEFAULT_UA,
        _transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        """Initialise the crawler with configuration.

        Args:
            domain: Domain to crawl.
            max_pages: Maximum pages to fetch HTML for.
            max_depth: BFS depth limit.
            concurrency: Semaphore limit for parallel requests.
            respect_robots: Whether to honour robots.txt disallow rules.
            timeout: Per-request HTTP timeout in seconds.
            user_agent: User-agent string sent with each request.
            _transport: Optional httpx transport override (for testing).
                Pass an ``httpx.MockTransport`` to avoid real network calls.
        """
        self.domain = domain.lower()
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.respect_robots = respect_robots
        self.timeout = timeout
        self.user_agent = user_agent
        self._transport = _transport

        # BFS state
        self._visited: set[str] = set()
        self._queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self._results: list[tuple[str, str]] = []  # (url, html)
        self._depth_map: dict[str, int] = {}
        self._status_map: dict[str, int] = {}
        self._redirect_map: dict[str, str] = {}
        self._robots_disallowed: set[str] = set()
        self._discovered: set[str] = set()

        self._robot_parser: RobotFileParser = RobotFileParser()
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(concurrency)
        self._stop_crawling: bool = False

    async def crawl(self) -> S1DiscoveryOutput:
        """Run the full 4-phase discovery and return results.

        Returns:
            :class:`S1DiscoveryOutput` with all discovery results.
        """
        homepage = f"https://{self.domain}/"

        client_kwargs: dict[str, object] = {
            "follow_redirects": True,
            "max_redirects": 5,
            "headers": {"User-Agent": self.user_agent},
            "timeout": self.timeout,
        }
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            # Phase 1: robots.txt + AI bot access
            robots_raw, self._robot_parser = await _fetch_robots_txt(
                self.domain, client, self.timeout
            )
            ai_bot_access = _parse_ai_bot_access(robots_raw, self._robot_parser, homepage)

            # Check llms.txt
            has_llms_txt = await self._check_llms_txt(client)
            # AIBotAccessResult uses regular dataclass assignment
            ai_bot_access = AIBotAccessResult(
                gptbot_allowed=ai_bot_access.gptbot_allowed,
                claudebot_allowed=ai_bot_access.claudebot_allowed,
                perplexitybot_allowed=ai_bot_access.perplexitybot_allowed,
                google_extended_allowed=ai_bot_access.google_extended_allowed,
                ccbot_allowed=ai_bot_access.ccbot_allowed,
                has_llms_txt=has_llms_txt,
                robots_txt_exists=ai_bot_access.robots_txt_exists,
            )

            # Phase 2: Sitemap discovery
            sitemap_health = await _discover_from_sitemaps(
                self.domain, robots_raw, client, self.timeout
            )

            # Seed BFS queue with sitemap URLs at depth 0
            for url in sitemap_health.sitemap_urls:
                await self._enqueue(url, 0)

            # Phase 3: RSS/Atom feed discovery (from homepage)
            await self._phase3_rss(client, homepage)

            # Always seed the homepage
            await self._enqueue(homepage, 0)

            # Phase 4: BFS crawl
            await self._phase4_bfs(client)

        return S1DiscoveryOutput(
            pages_with_html=self._results,
            ai_bot_access=ai_bot_access,
            sitemap_health=sitemap_health,
            crawl_depth_map=dict(self._depth_map),
            redirect_map=dict(self._redirect_map),
            status_code_map=dict(self._status_map),
            robots_txt_raw=robots_raw,
            discovered_urls=set(self._discovered),
        )

    async def _check_llms_txt(self, client: httpx.AsyncClient) -> bool:
        """Return True if /llms.txt exists and is reachable.

        Args:
            client: httpx async client.

        Returns:
            True when GET /llms.txt returns HTTP 2xx.
        """
        try:
            resp = await client.get(
                f"https://{self.domain}/llms.txt", timeout=self.timeout
            )
            return resp.status_code < 400
        except Exception:
            return False

    async def _enqueue(self, url: str, depth: int) -> None:
        """Add *url* to the BFS queue if not already visited or queued.

        Uses the minimum depth if the URL is discovered at multiple depths.

        Args:
            url: Normalized URL to enqueue.
            depth: BFS depth of this URL.
        """
        normalized = normalize_url(url)
        if not normalized:
            return
        if normalized in self._visited:
            return
        if normalized in self._depth_map:
            # Keep minimum depth
            if depth < self._depth_map[normalized]:
                self._depth_map[normalized] = depth
            return
        self._discovered.add(normalized)
        self._depth_map[normalized] = depth
        await self._queue.put((normalized, depth))

    def _is_allowed(self, url: str) -> bool:
        """Return True if the URL is allowed by robots.txt (or respect_robots is off).

        Args:
            url: URL to check.

        Returns:
            True if crawling is allowed.
        """
        if not self.respect_robots:
            return True
        allowed = self._robot_parser.can_fetch(self.user_agent, url)
        if not allowed:
            self._robots_disallowed.add(url)
        return allowed

    async def _phase3_rss(self, client: httpx.AsyncClient, homepage: str) -> None:
        """Fetch homepage HTML and extract RSS/Atom feed URLs.

        Feeds are parsed and their article URLs seeded into the BFS queue.

        Args:
            client: httpx async client.
            homepage: Homepage URL to fetch.
        """
        try:
            resp = await client.get(homepage, timeout=self.timeout)
            if resp.status_code < 400:
                html = resp.text
                feed_urls = _discover_feeds_from_html(html, homepage)
                for feed_url in feed_urls:
                    try:
                        article_urls = await _extract_rss_urls(
                            feed_url, client, self.timeout, self.domain
                        )
                        for url in article_urls:
                            await self._enqueue(url, 0)
                    except Exception as exc:
                        logger.warning("RSS feed parse error for %s: %s", feed_url, exc)
        except Exception as exc:
            logger.warning("Homepage fetch for RSS discovery failed: %s", exc)

    async def _phase4_bfs(self, client: httpx.AsyncClient) -> None:
        """Run BFS crawl using multiple async workers.

        Spawns ``self.concurrency`` worker coroutines that all pull from
        ``self._queue`` concurrently, bounded by ``self._semaphore``.

        Args:
            client: httpx async client (shared across workers).
        """
        workers = [
            asyncio.create_task(self._bfs_worker(client))
            for _ in range(self.concurrency)
        ]
        await self._queue.join()
        self._stop_crawling = True
        for w in workers:
            w.cancel()
        # Suppress CancelledError from worker cancellation
        await asyncio.gather(*workers, return_exceptions=True)

    async def _bfs_worker(self, client: httpx.AsyncClient) -> None:
        """Single BFS worker: dequeue, fetch, extract links, enqueue.

        Runs until the queue is drained or _stop_crawling is set.

        Args:
            client: httpx async client shared with all workers.
        """
        while not self._stop_crawling:
            try:
                url, depth = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process_url(client, url, depth)
            finally:
                self._queue.task_done()

    async def _process_url(
        self, client: httpx.AsyncClient, url: str, depth: int
    ) -> None:
        """Fetch and process a single URL within the BFS crawl.

        Skips URLs that: are already visited, exceed max_depth, are not
        same-domain, have a non-HTML extension, or are disallowed by robots.

        Args:
            client: httpx async client.
            url: Normalized URL to fetch.
            depth: BFS depth of this URL.
        """
        if url in self._visited:
            return

        self._visited.add(url)

        if depth > self.max_depth:
            return

        if should_skip_url(url):
            return

        if not is_same_domain(url, self.domain):
            return

        if not self._is_allowed(url):
            self._status_map[url] = 0
            return

        async with self._semaphore:
            try:
                resp = await client.get(url, timeout=self.timeout)
            except httpx.TimeoutException:
                logger.warning("Timeout fetching %s", url)
                self._status_map[url] = 0
                return
            except Exception as exc:
                logger.warning("Error fetching %s: %s", url, exc)
                self._status_map[url] = 0
                return

        final_url = str(resp.url)
        normalized_final = normalize_url(final_url)
        if normalized_final != url:
            self._redirect_map[url] = normalized_final

        status = resp.status_code
        self._status_map[url] = status

        content_type = (resp.headers.get("content-type") or "").lower()
        is_html = "text/html" in content_type

        if status < 400 and is_html:
            if len(self._results) < self.max_pages:
                html = resp.text
                self._results.append((url, html))

                if not self._stop_crawling and depth < self.max_depth:
                    links = _extract_links(html, url, self.domain)
                    for link in links:
                        await self._enqueue(link, depth + 1)
            else:
                # max_pages reached — stop enqueuing new URLs
                self._stop_crawling = True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def discover_site(
    domain: str,
    max_pages: int = 200,
    max_depth: int = 4,
    concurrency: int = 30,
    respect_robots: bool = True,
    timeout: float = 15.0,
    user_agent: str = _DEFAULT_UA,
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> S1DiscoveryOutput:
    """Run async BFS discovery for *domain* and return all outputs.

    This is the main entry point for the site audit s1 step.

    Args:
        domain: Domain to audit (e.g. ``"example.com"``).  No scheme needed.
        max_pages: Maximum number of HTML pages to collect.
        max_depth: Maximum BFS crawl depth.
        concurrency: Max parallel HTTP requests.
        respect_robots: Whether to honour robots.txt Disallow rules.
        timeout: Per-request HTTP timeout in seconds.
        user_agent: User-agent header sent with each request.
        config: Audit configuration (used for timeout/concurrency overrides
            when called from the pipeline orchestrator).

    Returns:
        :class:`S1DiscoveryOutput` with all discovery data.
    """
    crawler = AsyncSiteCrawler(
        domain=domain,
        max_pages=max_pages,
        max_depth=max_depth,
        concurrency=concurrency,
        respect_robots=respect_robots,
        timeout=timeout,
        user_agent=user_agent,
    )
    return await crawler.crawl()
