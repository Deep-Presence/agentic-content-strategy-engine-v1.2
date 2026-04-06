"""Step 1 — Crawl company website, extract text, chunk, embed, store in pgvector.

Async-first comprehensive site-tree discovery + embedding pipeline.
Discovers ALL pages via:
  Phase 1: robots.txt -> Sitemap directives
  Phase 2: Sitemap XML parsing (recursive, handles sitemap indexes)
  Phase 3: RSS / Atom feed discovery
  Phase 4: Enhanced BFS crawling (canonical, hreflang, link extraction)

Outputs:
  - Site discovery artifacts (discovered_pages.json, site_tree.json, discovery_summary.json)
  - Lightweight company_embeddings.json (with embedding_ids, NO raw vectors)
  - Embeddings persisted to pgvector
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

import defusedxml.ElementTree as SafeET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from core.config.settings import settings
from core.gap_analysis.steps.s4_enrich_citations import compute_structural_signals
from core.storage.backends.base import StorageBackend
from core.models.gap_analysis import (
    CompanyPageAnalysis,
    DiscoveredPage,
    DiscoverySource,
    GapAnalysisInput,
    SemanticUnit,
    SiteDiscoveryResult,
    SiteTreeNode,
)
from core.shared_tools.vector_store import (
    async_delete_company_collection,
    async_upsert_embeddings,
)
from core.shared_tools.async_embedding_client import async_embed_texts
from core.shared_tools.knowledge_doc_metadata import doc_storage_key, mark_documents_embedded
from core.shared_tools.text_extraction import extract_text as _extract_text_from_file
from core.shared_tools.text_extraction import extract_text_from_bytes

logger = logging.getLogger(__name__)

_CONTENT_ENGINE_ROOT = Path(__file__).resolve().parents[3]  # content-strategy-engine/


def _ga_dbg(msg: str, **kw: Any) -> None:
    """Emit a microscopic debug log when GA_DEBUG=true."""
    if settings.gap_analysis_debug:
        logger.info("[ga-debug] %s", msg, extra=kw)

# XML namespace map for sitemap parsing
_SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

# Common sitemap paths to probe if robots.txt has none
_COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
    "/sitemap-index.xml",
    "/post-sitemap.xml",
    "/page-sitemap.xml",
]

# Common RSS/Atom feed paths
_COMMON_FEED_PATHS = [
    "/feed/",
    "/rss/",
    "/feed.xml",
    "/rss.xml",
    "/atom.xml",
    "/blog/feed/",
    "/blog/rss/",
    "/blog/feed.xml",
]

# File extensions to skip during crawl
_SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".rar",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".ico", ".xml",
}


# ===========================================================================
# Utility Functions
# ===========================================================================


def _normalize_url(url: str) -> str:
    """Normalize URL: strip fragment, trailing slash, lowercase scheme+host."""
    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
    )
    cleaned = urlunparse(normalized).rstrip("/")
    return cleaned


def _same_host(url: str, domain: str) -> bool:
    """Check if URL belongs to the same domain (supports subdomains)."""
    netloc = urlparse(url).netloc.lower()
    return netloc == domain.lower() or netloc.endswith(f".{domain.lower()}")


def _should_skip_url(url: str) -> bool:
    """Skip non-HTML resources based on extension."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    return any(path_lower.endswith(ext) for ext in _SKIP_EXTENSIONS)


async def _build_robot_parser(
    base_url: str, client: httpx.AsyncClient
) -> Tuple[RobotFileParser, Optional[str]]:
    """Build robot parser AND return the raw robots.txt content."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    raw_robots: Optional[str] = None
    try:
        resp = await client.get(robots_url, timeout=15)
        if resp.status_code < 400:
            raw_robots = resp.text
            rp.parse(raw_robots.splitlines())
        else:
            rp.parse("")
    except Exception as e:
        logger.warning("Failed to fetch robots.txt: %s", e)
        rp.parse("")
    return rp, raw_robots


# ===========================================================================
# Phase 1: robots.txt -> Sitemap Discovery
# ===========================================================================


def _extract_sitemaps_from_robots(raw_robots: Optional[str]) -> List[str]:
    """Extract all Sitemap: directives from robots.txt content."""
    if not raw_robots:
        return []
    sitemaps: List[str] = []
    for line in raw_robots.splitlines():
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            url = line.split(":", 1)[1].strip()
            if url:
                sitemaps.append(url)
    return sitemaps


# ===========================================================================
# Phase 2: Sitemap XML Parsing (recursive)
# ===========================================================================


_MAX_XML_BYTES: int = 10 * 1024 * 1024  # 10 MB


async def _fetch_xml(url: str, client: httpx.AsyncClient) -> Optional[ET.Element]:
    """Fetch and parse an XML URL, return root element or None.

    Uses ``defusedxml`` to block entity expansion and XXE attacks.
    Rejects responses larger than :data:`_MAX_XML_BYTES`.
    """
    try:
        resp = await client.get(url, timeout=20)
        if resp.status_code >= 400:
            return None
        content = resp.text
        if not content.strip():
            return None
        if len(content.encode("utf-8", errors="replace")) > _MAX_XML_BYTES:
            logger.warning("XML body too large for %s — skipping", url)
            return None
        return SafeET.fromstring(content)
    except (SafeET.DTDForbidden, SafeET.EntitiesForbidden):
        logger.warning("XML entity/DTD attack blocked for %s", url)
        return None
    except Exception as e:
        logger.warning("Failed to parse XML at %s: %s", url, e)
        return None


async def _parse_sitemaps_recursive(
    sitemap_urls: List[str],
    client: httpx.AsyncClient,
    domain: str,
    max_urls: int = 10_000,
) -> Tuple[List[DiscoveredPage], List[str]]:
    """Recursively parse sitemap XMLs (handles sitemap indexes)."""
    discovered: List[DiscoveredPage] = []
    all_sitemaps: List[str] = list(sitemap_urls)
    visited_sitemaps: Set[str] = set()
    queue = list(sitemap_urls)

    while queue and len(discovered) < max_urls:
        sitemap_url = queue.pop(0)
        if sitemap_url in visited_sitemaps:
            continue
        visited_sitemaps.add(sitemap_url)

        root = await _fetch_xml(sitemap_url, client)
        if root is None:
            continue

        root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if root_tag == "sitemapindex":
            for sitemap_el in root.findall("sm:sitemap", _SITEMAP_NS):
                loc_el = sitemap_el.find("sm:loc", _SITEMAP_NS)
                if loc_el is not None and loc_el.text:
                    child_url = loc_el.text.strip()
                    if child_url not in visited_sitemaps:
                        queue.append(child_url)
                        all_sitemaps.append(child_url)
            # Also try without namespace
            for sitemap_el in root.findall("sitemap"):
                loc_el = sitemap_el.find("loc")
                if loc_el is not None and loc_el.text:
                    child_url = loc_el.text.strip()
                    if child_url not in visited_sitemaps:
                        queue.append(child_url)
                        all_sitemaps.append(child_url)

        elif root_tag == "urlset":
            for url_el in root.findall("sm:url", _SITEMAP_NS):
                _extract_sitemap_url(url_el, discovered, domain, _SITEMAP_NS)
            for url_el in root.findall("url"):
                _extract_sitemap_url(url_el, discovered, domain, ns=None)

        await asyncio.sleep(0.1)

    return discovered, all_sitemaps


def _extract_sitemap_url(
    url_el: ET.Element,
    discovered: List[DiscoveredPage],
    domain: str,
    ns: Optional[Dict[str, str]],
) -> None:
    """Extract a single URL entry from sitemap XML."""
    def _find(tag: str) -> Optional[str]:
        if ns:
            el = url_el.find(f"sm:{tag}", ns)
        else:
            el = url_el.find(tag)
        return el.text.strip() if el is not None and el.text else None

    loc = _find("loc")
    if not loc:
        return
    normalized = _normalize_url(loc)
    if not _same_host(normalized, domain):
        return

    hreflang: Dict[str, str] = {}
    xhtml_links = url_el.findall("xhtml:link", _SITEMAP_NS) if ns else []
    for link in xhtml_links:
        lang = link.get("hreflang", "")
        href = link.get("href", "")
        if lang and href:
            hreflang[lang] = href

    priority_str = _find("priority")
    discovered.append(DiscoveredPage(
        url=loc,
        normalized_url=normalized,
        discovery_source=DiscoverySource.SITEMAP,
        last_modified=_find("lastmod"),
        change_frequency=_find("changefreq"),
        priority=float(priority_str) if priority_str else None,
        hreflang_alternates=hreflang,
    ))


# ===========================================================================
# Phase 3: RSS / Atom Feed Discovery
# ===========================================================================


def _discover_feeds_from_html(html: str, base_url: str) -> List[str]:
    """Extract RSS/Atom feed URLs from HTML <link> tags."""
    feeds: List[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link", type=True):
        link_type = (link.get("type") or "").lower()
        if "rss" in link_type or "atom" in link_type:
            href = link.get("href", "").strip()
            if href:
                feeds.append(urljoin(base_url, href))
    return feeds


async def _parse_rss_feed(
    feed_url: str,
    client: httpx.AsyncClient,
    domain: str,
) -> List[DiscoveredPage]:
    """Parse RSS/Atom feed and extract article URLs."""
    discovered: List[DiscoveredPage] = []
    root = await _fetch_xml(feed_url, client)
    if root is None:
        return discovered

    # RSS 2.0: <channel><item><link>
    for item in root.iter("item"):
        link_el = item.find("link")
        if link_el is not None and link_el.text:
            url = link_el.text.strip()
            normalized = _normalize_url(url)
            if _same_host(normalized, domain):
                title_el = item.find("title")
                discovered.append(DiscoveredPage(
                    url=url,
                    normalized_url=normalized,
                    title=title_el.text.strip() if title_el is not None and title_el.text else None,
                    discovery_source=DiscoverySource.RSS_FEED,
                ))

    # Atom: <entry><link href="...">
    for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
        for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = link.get("href", "").strip()
            if href:
                normalized = _normalize_url(href)
                if _same_host(normalized, domain):
                    title_el = entry.find("{http://www.w3.org/2005/Atom}title")
                    discovered.append(DiscoveredPage(
                        url=href,
                        normalized_url=normalized,
                        title=title_el.text.strip() if title_el is not None and title_el.text else None,
                        discovery_source=DiscoverySource.RSS_FEED,
                    ))

    return discovered


# ===========================================================================
# Phase 4: Enhanced BFS Crawl
# ===========================================================================


def _extract_links_enhanced(html: str, base_url: str, domain: str) -> List[str]:
    """Extract all internal links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links: Set[str] = set()
    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        normalized = _normalize_url(absolute)
        if _same_host(normalized, domain) and not _should_skip_url(normalized):
            links.add(normalized)
    return list(links)


def _extract_canonical(html: str, base_url: str) -> Optional[str]:
    """Extract canonical URL from <link rel='canonical'>."""
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        return _normalize_url(urljoin(base_url, link["href"]))
    return None


def _extract_hreflang(html: str, base_url: str) -> Dict[str, str]:
    """Extract hreflang alternate URLs."""
    soup = BeautifulSoup(html, "html.parser")
    alternates: Dict[str, str] = {}
    for link in soup.find_all("link", rel="alternate"):
        lang = link.get("hreflang", "")
        href = link.get("href", "")
        if lang and href:
            alternates[lang] = urljoin(base_url, href)
    return alternates


def _extract_page_metadata(html: str) -> Dict[str, Optional[str | int]]:
    """Extract title, h1, meta description, word count from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(" ", strip=True) if h1_tag else None
    meta_desc = None
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        meta_desc = meta_tag.get("content", "").strip() or None

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    wc = len(text.split())

    return {
        "title": title,
        "h1": h1,
        "meta_description": meta_desc,
        "word_count": wc,
    }


# ===========================================================================
# Cloudflare / Playwright / Wayback fallback helpers
# ===========================================================================

_WAYBACK_PREFIX_RE = re.compile(r"https?://web\.archive\.org/web/\d+id_/")


def _is_cloudflare_challenge(html: str, status_code: int) -> bool:
    """Detect Cloudflare JS challenge pages."""
    if status_code == 403:
        return True
    if not html:
        return False
    lower = html[:5000].lower()
    return any(m in lower for m in (
        "just a moment",
        "cf-browser-verification",
        "challenge-platform",
        "cf_chl_opt",
    ))


async def _init_playwright_browser() -> Optional[Tuple[Any, Any]]:
    """Lazily launch headless Chromium. Returns (browser, pw_instance) or None."""
    try:
        from playwright.async_api import async_playwright
        _ga_dbg("Launching Playwright browser...")
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        _ga_dbg("Playwright browser launched successfully")
        logger.info("[SiteDiscovery] Playwright browser launched for Cloudflare bypass.")
        return browser, pw
    except ImportError:
        _ga_dbg("Playwright NOT installed!")
        logger.warning(
            "[SiteDiscovery] playwright not installed. "
            "Run: pip install playwright && playwright install chromium"
        )
        return None
    except Exception as e:
        _ga_dbg(f"Playwright launch FAILED: {e}")
        logger.warning("[SiteDiscovery] Playwright launch failed: %s", e)
        return None


async def _fetch_with_playwright(
    url: str, browser: Any, semaphore: asyncio.Semaphore,
) -> Optional[Tuple[str, str, int]]:
    """Fetch a page with headless Chromium. Returns (url, html, status) or None."""
    async with semaphore:
        page = None
        try:
            page = await browser.new_page()
            resp = await page.goto(url, wait_until="networkidle", timeout=30000)
            if resp is None:
                return None
            status = resp.status
            html = await page.content()
            if _is_cloudflare_challenge(html, status):
                # Wait for challenge to resolve, then re-check
                await page.wait_for_timeout(6000)
                html = await page.content()
                if _is_cloudflare_challenge(html, status):
                    return None
            return (url, html, status)
        except Exception as e:
            _ga_dbg(f"Playwright EXCEPTION for {url}: {type(e).__name__}: {e}")
            logger.debug("[Playwright] %s: %s", url, e)
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass


async def _fetch_from_wayback(
    url: str, client: httpx.AsyncClient,
) -> Optional[Tuple[str, str, int]]:
    """Fetch latest Wayback Machine snapshot. Returns (url, html, 200) or None."""
    try:
        wb_url = f"https://web.archive.org/web/2id_/{url}"
        resp = await client.get(wb_url, timeout=25)
        if resp.status_code >= 400:
            return None
        ct = resp.headers.get("content-type", "")
        if "text/html" not in ct.lower():
            return None
        html = resp.text or ""
        if not html.strip():
            return None
        # Strip residual Wayback URL rewriting from links
        html = _WAYBACK_PREFIX_RE.sub("", html)
        return (url, html, 200)
    except Exception as e:
        logger.debug("[Wayback] %s: %s", url, e)
        return None


# ===========================================================================
# Text Extraction + Chunking (preserved from original)
# ===========================================================================


def _extract_paragraphs(html: str) -> Tuple[str, List[str]]:
    """Extract title and text paragraphs from HTML (for semantic units)."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    elements = soup.find_all(["p", "li", "h2", "h3"])
    paragraphs: List[str] = []
    for el in elements:
        text = " ".join(el.get_text(" ", strip=True).split())
        if text and len(text) >= 50:
            paragraphs.append(text)
    return title, paragraphs


def _chunk_paragraphs(
    paragraphs: Iterable[str], min_words: int = 80, max_words: int = 220
) -> List[str]:
    chunks: List[str] = []
    buffer: List[str] = []
    word_count = 0
    for para in paragraphs:
        words = para.split()
        if not words:
            continue
        if word_count + len(words) > max_words and buffer:
            chunks.append(" ".join(buffer))
            buffer = []
            word_count = 0
        buffer.append(para)
        word_count += len(words)
        if word_count >= min_words:
            chunks.append(" ".join(buffer))
            buffer = []
            word_count = 0
    if buffer:
        chunks.append(" ".join(buffer))
    return chunks


# ===========================================================================
# Site-Tree Builder (flat list -> hierarchical tree)
# ===========================================================================


def _build_site_tree(pages: List[DiscoveredPage], base_url: str) -> SiteTreeNode:
    """Build a hierarchical site-tree from a flat list of discovered pages."""
    parsed_base = urlparse(base_url)
    root = SiteTreeNode(
        url=base_url,
        title="Root",
        path_segment="/",
        depth=0,
    )

    nodes_by_path: Dict[str, SiteTreeNode] = {"/": root}

    for page in sorted(pages, key=lambda p: p.normalized_url):
        parsed = urlparse(page.normalized_url)
        if parsed.netloc.lower() != parsed_base.netloc.lower():
            continue

        path = parsed.path.strip("/")
        if not path:
            root.title = page.title or root.title
            root.discovery_source = page.discovery_source
            root.status_code = page.status_code
            continue

        segments = path.split("/")
        current_path = "/"

        for i, segment in enumerate(segments):
            parent_path = current_path
            current_path = f"{current_path.rstrip('/')}/{segment}"

            if current_path not in nodes_by_path:
                node = SiteTreeNode(
                    url=f"{parsed_base.scheme}://{parsed_base.netloc}{current_path}",
                    path_segment=segment,
                    depth=i + 1,
                )
                nodes_by_path[current_path] = node
                parent_node = nodes_by_path.get(parent_path, root)
                parent_node.children.append(node)

            if i == len(segments) - 1:
                node = nodes_by_path[current_path]
                node.title = page.title or node.title
                node.discovery_source = page.discovery_source
                node.status_code = page.status_code

    def _count_below(node: SiteTreeNode) -> int:
        count = len(node.children)
        for child in node.children:
            count += _count_below(child)
        node.page_count_below = count
        return count

    _count_below(root)
    return root


# ===========================================================================
# Main Discovery Orchestrator
# ===========================================================================


async def discover_site_tree(
    domain: str,
    seed_urls: List[str],
    max_pages: int = 500,
    max_depth: int = 5,
    respect_robots: bool = True,
) -> Tuple[SiteDiscoveryResult, List[Tuple[str, str]]]:
    """Async comprehensive site-tree discovery.

    Returns:
        SiteDiscoveryResult with full discovery metadata (flat + tree).
        List[Tuple[url, html]] with crawled pages for embedding.
    """
    if not domain:
        raise ValueError("domain is required for site discovery")

    base_url = seed_urls[0] if seed_urls else f"https://{domain}"
    start_time = time.time()
    errors: List[str] = []

    # URL registry: normalized_url -> DiscoveredPage
    registry: Dict[str, DiscoveredPage] = {}
    pages_with_html: List[Tuple[str, str]] = []

    def _register(page: DiscoveredPage) -> bool:
        if page.normalized_url not in registry:
            registry[page.normalized_url] = page
            return True
        return False

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "ContentStrategyBot/1.0 (gap-analysis)"},
        limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
    ) as client:

        # -------------------------------------------------------------------
        # Phase 1: robots.txt
        # -------------------------------------------------------------------
        logger.info("[SiteDiscovery] Phase 1: Fetching robots.txt for %s", domain)
        rp, raw_robots = await _build_robot_parser(base_url, client)
        robots_sitemaps = _extract_sitemaps_from_robots(raw_robots)
        logger.info(
            "[SiteDiscovery] Found %d sitemap(s) in robots.txt", len(robots_sitemaps)
        )

        # -------------------------------------------------------------------
        # Phase 2: Sitemap discovery + parsing
        # -------------------------------------------------------------------
        logger.info("[SiteDiscovery] Phase 2: Parsing sitemaps")

        sitemap_candidates: List[str] = list(robots_sitemaps)
        parsed_base = urlparse(base_url)
        for path in _COMMON_SITEMAP_PATHS:
            candidate = f"{parsed_base.scheme}://{parsed_base.netloc}{path}"
            if candidate not in sitemap_candidates:
                sitemap_candidates.append(candidate)

        sitemap_pages, all_sitemaps = await _parse_sitemaps_recursive(
            sitemap_candidates, client, domain, max_urls=max_pages * 2
        )
        for page in sitemap_pages:
            _register(page)
        logger.info(
            "[SiteDiscovery] Sitemaps yielded %d URLs from %d sitemap file(s)",
            len(sitemap_pages),
            len(all_sitemaps),
        )

        # -------------------------------------------------------------------
        # Phase 3: RSS / Atom feed discovery
        # -------------------------------------------------------------------
        logger.info("[SiteDiscovery] Phase 3: Probing RSS/Atom feeds")
        rss_feeds_found: List[str] = []

        for feed_path in _COMMON_FEED_PATHS:
            feed_url = f"{parsed_base.scheme}://{parsed_base.netloc}{feed_path}"
            feed_pages = await _parse_rss_feed(feed_url, client, domain)
            if feed_pages:
                rss_feeds_found.append(feed_url)
                for page in feed_pages:
                    _register(page)
            await asyncio.sleep(0.1)

        logger.info(
            "[SiteDiscovery] RSS feeds found: %d, total URLs so far: %d",
            len(rss_feeds_found),
            len(registry),
        )

        # -------------------------------------------------------------------
        # Phase 4: Enhanced BFS crawl (seed-URL-path-prioritized)
        # -------------------------------------------------------------------
        logger.info("[SiteDiscovery] Phase 4: BFS crawling")

        seed_prefixes: List[str] = []
        for surl in seed_urls:
            path = urlparse(_normalize_url(surl)).path.rstrip("/")
            if path:
                seed_prefixes.append(path)
        logger.info(
            "[SiteDiscovery] Seed path prefixes for priority: %s",
            seed_prefixes,
        )

        def _matches_seed_prefix(url: str) -> bool:
            path = urlparse(url).path.rstrip("/")
            return any(path.startswith(pfx) for pfx in seed_prefixes) if seed_prefixes else False

        priority_queue: List[Tuple[str, int, Optional[str]]] = []
        rest_queue: List[Tuple[str, int, Optional[str]]] = []

        # Always start BFS from base_url (fallback when sitemaps/RSS find nothing)
        priority_queue.append((_normalize_url(base_url), 0, None))
        for url in seed_urls:
            normalized = _normalize_url(url)
            if normalized != _normalize_url(base_url):
                priority_queue.append((normalized, 0, None))

        for norm_url in list(registry.keys()):
            if not _should_skip_url(norm_url):
                if _matches_seed_prefix(norm_url):
                    priority_queue.append((norm_url, 0, None))
                else:
                    rest_queue.append((norm_url, 0, None))

        bfs_queue: List[Tuple[str, int, Optional[str]]] = priority_queue + rest_queue
        logger.info(
            "[SiteDiscovery] BFS queue: %d priority + %d rest = %d total",
            len(priority_queue),
            len(rest_queue),
            len(bfs_queue),
        )

        visited_crawl: Set[str] = set()
        crawl_count = 0
        semaphore = asyncio.Semaphore(10)

        # Fallback state for Cloudflare-protected sites
        pw_semaphore = asyncio.Semaphore(3)
        _pw: Dict[str, Any] = {
            "browser": None, "mgr": None,
            "site_blocked": False, "available": True,
        }

        # Early-stopping counters
        _consecutive_pw_fails = 0
        _consecutive_wb_fails = 0
        _consecutive_total_fails = 0
        _pw_fail_threshold = settings.gap_analysis_pw_fail_threshold
        _wb_fail_threshold = settings.gap_analysis_wb_fail_threshold
        _total_fail_threshold = settings.gap_analysis_total_fail_threshold
        _wb_available = True

        async def _crawl_one(
            url: str, depth: int, parent_url: Optional[str],
        ) -> Optional[Tuple[str, str, int, dict, Optional[str], Dict[str, str]]]:
            """Fetch a single page. Fallback chain: httpx -> Playwright -> Wayback."""
            nonlocal _consecutive_pw_fails, _consecutive_wb_fails, _wb_available
            html: Optional[str] = None
            status_code: int = 0

            # --- Tier 1: httpx (skip if site is known Cloudflare-blocked) ---
            if not _pw["site_blocked"]:
                async with semaphore:
                    try:
                        resp = await client.get(url)
                        status_code = resp.status_code
                        content_type = resp.headers.get("content-type", "")

                        if status_code < 400 and "text/html" in content_type.lower():
                            html = resp.text or ""
                            if not _is_cloudflare_challenge(html, status_code):
                                metadata = _extract_page_metadata(html)
                                canonical = _extract_canonical(html, url)
                                hreflang = _extract_hreflang(html, url)
                                return (url, html, status_code, metadata, canonical, hreflang)
                            else:
                                _ga_dbg(f"httpx got Cloudflare challenge for {url}")
                        else:
                            _ga_dbg(f"httpx non-HTML or error: {url} status={status_code} ct={content_type[:50]}")
                    except Exception as e:
                        _ga_dbg(f"httpx exception for {url}: {type(e).__name__}: {e}")
                        errors.append(f"Crawl error for {url}: {e}")

                logger.info("[BFS] httpx blocked for %s (status=%d), trying fallbacks", url, status_code)

            # --- Tier 2: Playwright ---
            if _pw["available"]:
                if _pw["browser"] is None:
                    result = await _init_playwright_browser()
                    if result is not None:
                        _pw["browser"], _pw["mgr"] = result
                    else:
                        _ga_dbg(f"Playwright unavailable, skipping tier-2 for {url}")
                        _pw["available"] = False

                if _pw["browser"] is not None:
                    pw_result = await _fetch_with_playwright(url, _pw["browser"], pw_semaphore)
                    if pw_result is not None:
                        _consecutive_pw_fails = 0
                        _, html, status_code = pw_result
                        if not _pw["site_blocked"]:
                            _pw["site_blocked"] = True
                            _ga_dbg("Cloudflare confirmed — ALL pages now via Playwright")
                            logger.info(
                                "[SiteDiscovery] Cloudflare detected — switching to Playwright for all pages."
                            )
                        return (url, html, status_code,
                                _extract_page_metadata(html),
                                _extract_canonical(html, url),
                                _extract_hreflang(html, url))
                    else:
                        _consecutive_pw_fails += 1
                        _ga_dbg(f"Playwright returned None for {url} (consecutive_fails={_consecutive_pw_fails})")
                        if _consecutive_pw_fails >= _pw_fail_threshold:
                            _pw["available"] = False
                            logger.info(
                                "[SiteDiscovery] Playwright disabled — %d consecutive failures, "
                                "falling through to Wayback only",
                                _consecutive_pw_fails,
                            )
                            _ga_dbg(f"Playwright DISABLED after {_consecutive_pw_fails} consecutive failures")
            else:
                _ga_dbg(f"Playwright not available, falling through to Wayback for {url}")

            # --- Tier 3: Wayback Machine ---
            if _wb_available:
                wb_result = await _fetch_from_wayback(url, client)
                if wb_result is not None:
                    _consecutive_wb_fails = 0
                    _ga_dbg(f"Wayback hit for {url}")
                    _, html, status_code = wb_result
                    metadata = _extract_page_metadata(html)
                    canonical = _extract_canonical(html, url)
                    hreflang = _extract_hreflang(html, url)
                    return (url, html, status_code, metadata, canonical, hreflang)
                else:
                    _consecutive_wb_fails += 1
                    _ga_dbg(f"Wayback returned None for {url} (consecutive_fails={_consecutive_wb_fails})")
                    if _consecutive_wb_fails >= _wb_fail_threshold:
                        _wb_available = False
                        logger.info(
                            "[SiteDiscovery] Wayback Machine disabled — %d consecutive failures",
                            _consecutive_wb_fails,
                        )
                        _ga_dbg(f"Wayback DISABLED after {_consecutive_wb_fails} consecutive failures")
            else:
                _ga_dbg(f"Wayback not available, skipping tier-3 for {url}")

            _ga_dbg(f"ALL 3 TIERS FAILED for {url}")
            return None

        _bfs_start = time.monotonic()
        try:
            while bfs_queue and crawl_count < max_pages:
                # Pop a batch for concurrent fetching
                batch: List[Tuple[str, int, Optional[str]]] = []
                while bfs_queue and len(batch) < 10:
                    url, depth, parent_url = bfs_queue.pop(0)
                    url = _normalize_url(url)

                    if url in visited_crawl or depth > max_depth:
                        continue
                    if _should_skip_url(url):
                        continue
                    if respect_robots and not rp.can_fetch("*", url):
                        visited_crawl.add(url)
                        continue

                    visited_crawl.add(url)
                    batch.append((url, depth, parent_url))

                if not batch:
                    continue

                # --- Microscopic progress every 10 pages ---
                if crawl_count % 10 == 0:
                    _elapsed = time.monotonic() - _bfs_start
                    _ga_dbg(
                        f"BFS progress: {crawl_count}/{max_pages} crawled, "
                        f"{len(bfs_queue)} queued, {len(pages_with_html)} with HTML, "
                        f"playwright={'ON' if _pw['site_blocked'] else 'OFF'}, "
                        f"elapsed={_elapsed:.1f}s"
                    )

                # Fetch batch concurrently
                tasks = [_crawl_one(url, depth, parent_url) for url, depth, parent_url in batch]
                results = await asyncio.gather(*tasks)

                for (url, depth, parent_url), result in zip(batch, results):
                    if result is None:
                        _consecutive_total_fails += 1
                        _register(DiscoveredPage(
                            url=url,
                            normalized_url=url,
                            status_code=0,
                            discovery_source=DiscoverySource.BFS_CRAWL,
                            depth=depth,
                            parent_url=parent_url,
                            has_content=False,
                        ))
                        continue

                    _consecutive_total_fails = 0
                    fetched_url, html, status_code, metadata, canonical, hreflang = result
                    crawl_count += 1

                    page = DiscoveredPage(
                        url=url,
                        normalized_url=url,
                        title=metadata["title"],
                        h1=metadata["h1"],
                        meta_description=metadata["meta_description"],
                        word_count=metadata["word_count"],
                        status_code=status_code,
                        content_type="text/html",
                        discovery_source=DiscoverySource.BFS_CRAWL,
                        depth=depth,
                        parent_url=parent_url,
                        canonical_url=canonical,
                        hreflang_alternates=hreflang,
                        has_content=True,
                    )

                    if url in registry:
                        existing = registry[url]
                        existing.title = metadata["title"] or existing.title
                        existing.h1 = metadata["h1"]
                        existing.meta_description = metadata["meta_description"]
                        existing.word_count = metadata["word_count"]
                        existing.status_code = status_code
                        existing.content_type = "text/html"
                        existing.canonical_url = canonical
                        existing.hreflang_alternates = hreflang or existing.hreflang_alternates
                        existing.has_content = True
                    else:
                        _register(page)

                    pages_with_html.append((url, html))

                    if canonical and canonical != url and _same_host(canonical, domain):
                        _register(DiscoveredPage(
                            url=canonical,
                            normalized_url=canonical,
                            discovery_source=DiscoverySource.CANONICAL,
                            depth=depth,
                            parent_url=url,
                        ))

                    for lang, alt_url in hreflang.items():
                        alt_normalized = _normalize_url(alt_url)
                        if _same_host(alt_normalized, domain):
                            _register(DiscoveredPage(
                                url=alt_url,
                                normalized_url=alt_normalized,
                                discovery_source=DiscoverySource.HREFLANG,
                                depth=depth,
                                parent_url=url,
                            ))

                    page_feeds = _discover_feeds_from_html(html, url)
                    for page_feed_url in page_feeds:
                        if page_feed_url not in rss_feeds_found:
                            feed_pages = await _parse_rss_feed(page_feed_url, client, domain)
                            if feed_pages:
                                rss_feeds_found.append(page_feed_url)
                                for fp in feed_pages:
                                    _register(fp)

                    if depth < max_depth:
                        for link in _extract_links_enhanced(html, url, domain):
                            if link not in visited_crawl:
                                entry = (link, depth + 1, url)
                                if _matches_seed_prefix(link):
                                    bfs_queue.insert(0, entry)
                                else:
                                    bfs_queue.append(entry)

                # Early-stop: all 3 tiers failing consecutively
                if _consecutive_total_fails >= _total_fail_threshold:
                    logger.info(
                        "[SiteDiscovery] BFS early-stop — %d consecutive pages returned no content. "
                        "Stopping crawl with %d pages collected.",
                        _consecutive_total_fails,
                        len(pages_with_html),
                    )
                    _ga_dbg(
                        f"BFS EARLY-STOP: {_consecutive_total_fails} consecutive total failures, "
                        f"{len(pages_with_html)} pages collected so far"
                    )
                    break

                await asyncio.sleep(0.1)
        finally:
            # Clean up Playwright browser if it was initialized
            if _pw["browser"] is not None:
                try:
                    await _pw["browser"].close()
                except Exception:
                    pass
            if _pw["mgr"] is not None:
                try:
                    await _pw["mgr"].stop()
                except Exception:
                    pass

        _bfs_total = time.monotonic() - _bfs_start
        _ga_dbg(
            f"BFS DONE: {crawl_count} crawled, {len(pages_with_html)} with HTML, "
            f"{len(registry)} discovered, playwright={'USED' if _pw['site_blocked'] else 'NOT USED'}, "
            f"elapsed={_bfs_total:.1f}s"
        )
        logger.info(
            "[SiteDiscovery] BFS crawled %d pages. Total discovered: %d%s",
            crawl_count,
            len(registry),
            " (Playwright bypass used)" if _pw["site_blocked"] else "",
        )

    # -------------------------------------------------------------------
    # Build outputs
    # -------------------------------------------------------------------
    all_pages = list(registry.values())

    stats: Dict[str, int] = defaultdict(int)
    for p in all_pages:
        stats[p.discovery_source.value] += 1

    site_tree = _build_site_tree(all_pages, base_url)
    duration = time.time() - start_time

    result = SiteDiscoveryResult(
        domain=domain,
        base_url=base_url,
        total_pages_discovered=len(all_pages),
        discovery_stats=dict(stats),
        pages=all_pages,
        site_tree=site_tree,
        sitemaps_found=all_sitemaps,
        rss_feeds_found=rss_feeds_found,
        robots_txt_raw=raw_robots,
        crawl_duration_seconds=round(duration, 2),
        errors=errors,
    )

    return result, pages_with_html


# ===========================================================================
# Semantic Unit Builder
# ===========================================================================


def build_semantic_units(
    pages: List[Tuple[str, str]],
    discovery_lookup: Optional[Dict[str, DiscoveredPage]] = None,
) -> List[SemanticUnit]:
    """Build SemanticUnit objects from crawled pages."""
    units: List[SemanticUnit] = []
    counter = 0
    for url, html in pages:
        title, paragraphs = _extract_paragraphs(html)
        chunks = _chunk_paragraphs(paragraphs)
        source = None
        if discovery_lookup:
            normalized = _normalize_url(url)
            dp = discovery_lookup.get(normalized)
            if dp:
                source = dp.discovery_source.value
        for chunk in chunks:
            counter += 1
            text = chunk.strip()
            units.append(
                SemanticUnit(
                    unit_id=f"unit_{counter}",
                    url=url,
                    title=title or None,
                    text=text,
                    char_count=len(text),
                    word_count=len(text.split()),
                    discovery_source=source,
                )
            )
    return units


# ===========================================================================
# Legacy wrapper (backward compat)
# ===========================================================================


async def crawl_company_assets(
    domain: str,
    seed_urls: List[str],
    max_pages: int,
    max_depth: int,
) -> List[Tuple[str, str]]:
    """Legacy entry point — returns just the (url, html) pairs."""
    _, pages_with_html = await discover_site_tree(
        domain=domain,
        seed_urls=seed_urls,
        max_pages=max_pages,
        max_depth=max_depth,
    )
    return pages_with_html


# ===========================================================================
# Knowledge Document Loading
# ===========================================================================


def _load_knowledge_doc_units(
    effective_slug: str,
    storage: StorageBackend,
    start_counter: int = 0,
) -> List[SemanticUnit]:
    """Load knowledge documents via StorageBackend, extract text, chunk into SemanticUnits.

    Reads _metadata.json from StorageBackend to discover docs, fetches each
    document's bytes via ``storage.read_bytes()``, and uses
    ``extract_text_from_bytes()`` for PDF/DOCX/MD/TXT extraction.
    """
    from core.shared_tools.knowledge_doc_metadata import _metadata_key

    metadata_content = storage.read(_metadata_key(effective_slug))
    if metadata_content is None:
        logger.info("[knowledge_docs] No metadata for slug=%s", effective_slug)
        return []

    try:
        raw = json.loads(metadata_content)
    except Exception:
        logger.warning("[knowledge_docs] Failed to parse _metadata.json for slug=%s", effective_slug)
        return []

    units: List[SemanticUnit] = []
    counter = start_counter

    for entry in raw:
        stored_filename = entry.get("stored_filename", "")
        original_filename = entry.get("filename", stored_filename)
        key = doc_storage_key(effective_slug, stored_filename)

        file_bytes = storage.read_bytes(key)
        if file_bytes is None:
            logger.warning("[knowledge_docs] File missing: %s", key)
            continue

        # Extract text using shared utility (from bytes, no filesystem needed)
        suffix = Path(stored_filename).suffix.lower()
        text = extract_text_from_bytes(file_bytes, suffix)
        if not text and suffix not in (".md", ".txt", ".pdf", ".docx"):
            continue

        if not text.strip():
            if suffix in (".md", ".txt", ".pdf", ".docx"):
                logger.warning(
                    "[knowledge_docs] Empty text after extraction: filename=%s suffix=%s — skipping",
                    original_filename,
                    suffix,
                )
            continue

        # Split into paragraphs and chunk using the same strategy as site content
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = _chunk_paragraphs(paragraphs)

        for chunk in chunks:
            counter += 1
            chunk_text = chunk.strip()
            if not chunk_text:
                continue
            units.append(
                SemanticUnit(
                    unit_id=f"kdoc_{counter}",
                    url=None,
                    title=original_filename,
                    text=chunk_text,
                    char_count=len(chunk_text),
                    word_count=len(chunk_text.split()),
                    discovery_source=DiscoverySource.KNOWLEDGE_DOC.value,
                )
            )

    logger.info(
        "[knowledge_docs] Loaded %d semantic units for slug=%s",
        len(units),
        effective_slug,
    )
    return units


# _mark_knowledge_docs_embedded moved to core.shared_tools.knowledge_doc_metadata
# as mark_documents_embedded (uses shared lock to coordinate with uploads).


# ===========================================================================
# Main Entry Point: embed_company_assets
# ===========================================================================


async def embed_company_assets(
    input_data: GapAnalysisInput,
    storage: Optional[StorageBackend] = None,
    prefix: str = "",
) -> List[SemanticUnit]:
    """Crawl, chunk, embed, and store company assets (async).

    Uses multi-phase discovery (sitemap + RSS + BFS) and stores
    embeddings in pgvector. JSON artifacts are lightweight (IDs only).
    """
    if storage is None:
        from core.storage import get_storage_backend
        storage = get_storage_backend()

    company_slug = input_data.company_slug or re.sub(
        r"[^a-z0-9]+", "-", input_data.company_name.lower()
    ).strip("-")
    if not prefix:
        prefix = f"gap_analysis/{company_slug}"
    max_pages = input_data.max_crawl_pages or settings.gap_analysis_max_crawl_pages
    max_depth = input_data.max_crawl_depth or settings.gap_analysis_max_crawl_depth

    seed_urls = [str(u) for u in input_data.seed_urls]

    # --- Full site-tree discovery ---
    _ga_dbg(f"Starting discover_site_tree: domain={input_data.domain}, max_pages={max_pages}, max_depth={max_depth}")
    discovery_result, pages_with_html = await discover_site_tree(
        domain=input_data.domain or "",
        seed_urls=seed_urls,
        max_pages=max_pages,
        max_depth=max_depth,
    )
    _ga_dbg(f"discover_site_tree complete: {discovery_result.total_pages_discovered} discovered, {len(pages_with_html)} with HTML")

    # Save site-tree discovery artifacts
    storage.mkdir(f"{prefix}/site_discovery")

    storage.write(
        f"{prefix}/site_discovery/discovered_pages.json",
        json.dumps(
            [p.model_dump(mode="json") for p in discovery_result.pages],
            indent=2,
            default=str,
        ),
    )

    if discovery_result.site_tree:
        storage.write(
            f"{prefix}/site_discovery/site_tree.json",
            json.dumps(
                discovery_result.site_tree.model_dump(mode="json"),
                indent=2,
                default=str,
            ),
        )

    summary = {
        "domain": discovery_result.domain,
        "base_url": discovery_result.base_url,
        "total_pages_discovered": discovery_result.total_pages_discovered,
        "pages_with_html_crawled": len(pages_with_html),
        "discovery_stats": discovery_result.discovery_stats,
        "sitemaps_found": discovery_result.sitemaps_found,
        "rss_feeds_found": discovery_result.rss_feeds_found,
        "crawl_duration_seconds": discovery_result.crawl_duration_seconds,
        "errors": discovery_result.errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    storage.write(
        f"{prefix}/site_discovery/discovery_summary.json",
        json.dumps(summary, indent=2, default=str),
    )

    logger.info(
        "[embed_company_assets] Site discovery complete: "
        "%d URLs discovered, %d pages crawled.",
        discovery_result.total_pages_discovered,
        len(pages_with_html),
    )

    # --- Build semantic units ---
    _ga_dbg(f"Building semantic units from {len(pages_with_html)} pages...")
    discovery_lookup = {_normalize_url(p.url): p for p in discovery_result.pages}
    units = build_semantic_units(pages_with_html, discovery_lookup=discovery_lookup)
    _ga_dbg(f"Built {len(units)} semantic units")

    # --- Structural analysis of company pages (per-page, not per-chunk) ---
    page_analyses: List[CompanyPageAnalysis] = []
    for url, html in pages_with_html:
        try:
            _paragraphs, signals = compute_structural_signals(html)
            page_title = None
            dp = discovery_lookup.get(_normalize_url(url))
            if dp:
                page_title = dp.title
            page_analyses.append(
                CompanyPageAnalysis(
                    url=url,
                    title=page_title,
                    structural_signals=signals,
                    word_count=signals.word_count,
                    paragraph_count=signals.paragraph_count,
                )
            )
        except Exception:
            logger.debug(
                "[embed_company_assets] Structural analysis failed for %s", url
            )

    # Save company page analysis artifact
    storage.write(
        f"{prefix}/company_page_analysis.json",
        json.dumps(
            [pa.model_dump(mode="json") for pa in page_analyses],
            indent=2,
            default=str,
        ),
    )
    logger.info(
        "[embed_company_assets] Structural analysis complete: %d/%d pages analyzed",
        len(page_analyses),
        len(pages_with_html),
    )

    # --- Load knowledge documents (if any) ---
    kdoc_slug = getattr(input_data, "knowledge_doc_slug", None)
    if kdoc_slug:
        kdoc_units = _load_knowledge_doc_units(
            kdoc_slug,
            storage,
            start_counter=len(units),
        )
        if kdoc_units:
            logger.info(
                "[embed_company_assets] Adding %d knowledge doc units to %d site units",
                len(kdoc_units),
                len(units),
            )
            units.extend(kdoc_units)

    # --- Embed (async) ---
    texts = [u.text for u in units]
    _ga_dbg(f"Embedding {len(texts)} text chunks via OpenAI...")
    _embed_start = time.monotonic()
    embeddings = await async_embed_texts(texts)
    _ga_dbg(f"Embedding complete: {len(embeddings)} vectors in {time.monotonic() - _embed_start:.1f}s")
    for unit, embedding in zip(units, embeddings):
        unit.embedding = embedding
        unit.embedding_id = f"{company_slug}__{unit.unit_id}"

    # --- Store in pgvector (delete + insert is atomic inside upsert_embeddings) ---
    await async_upsert_embeddings(
        company_slug=company_slug,
        unit_ids=[u.unit_id for u in units],
        texts=texts,
        embeddings=embeddings,
        metadatas=[
            {
                "url": str(u.url) if u.url else "",
                "title": u.title or "",
                "unit_id": u.unit_id,
            }
            for u in units
        ],
    )

    # --- Save lightweight JSON (embedding_id only, no raw vectors) ---
    payload = [u.model_dump(mode="json", exclude={"embedding"}) for u in units]
    storage.write(
        f"{prefix}/company_embeddings.json",
        json.dumps(payload, indent=2, default=str),
    )

    # --- Mark knowledge docs as embedded ---
    # H6-fix: run blocking lock + I/O off the event loop
    if kdoc_slug:
        await asyncio.to_thread(mark_documents_embedded, kdoc_slug, storage=storage)

    logger.info(
        "[embed_company_assets] S1 complete: %d pages crawled, %d semantic units, "
        "embeddings stored in pgvector.",
        len(pages_with_html),
        len(units),
    )

    return units
