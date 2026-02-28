"""Step 2 — Parallel per-page HTML analysis for the site audit pipeline.

Extracts structural and content signals from each crawled page HTML string
and produces a ``PageAuditResult`` with check findings attached.

``analyze_all_pages()`` is async and fans out via asyncio.gather with a
Semaphore.  ``analyze_single_page()`` itself is synchronous (pure CPU/parsing,
no I/O).

Usage::

    results = await analyze_all_pages(
        pages=output.pages_with_html,
        depth_map=output.crawl_depth_map,
        status_code_map=output.status_code_map,
        redirect_map=output.redirect_map,
        config=DEFAULT_AUDIT_CONFIG,
    )
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urlparse, urljoin

import trafilatura
import textstat
from bs4 import BeautifulSoup, Tag

from core.models.site_audit import (
    AuditFinding,
    PageAuditResult,
)
from core.site_audit.checks.crawlability import (
    check_canonical,
    check_crawl_depth,
    check_noindex,
    check_status_code,
)
from core.site_audit.checks.eeat_signals import check_author, check_freshness
from core.site_audit.checks.on_page_seo import (
    check_h1,
    check_heading_hierarchy,
    check_images,
    check_internal_links,
    check_meta_description,
    check_title,
)
from core.site_audit.checks.security import check_https, check_mixed_content
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML extraction helpers (pure, no I/O)
# ---------------------------------------------------------------------------

#: Common CSS class patterns for author attribution.
_AUTHOR_CLASS_PATTERNS: tuple[str, ...] = (
    "author",
    "byline",
    "post-author",
    "entry-author",
    "article-author",
    "writer",
)


def _extract_title(soup: BeautifulSoup) -> tuple[str, int]:
    """Extract ``<title>`` tag text and its length.

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (title_text, length).  Both are empty/0 if absent.
    """
    title_tag = soup.title
    if title_tag is None:
        return "", 0
    text = (title_tag.string or "").strip()
    return text, len(text)


def _extract_meta_description(soup: BeautifulSoup) -> tuple[str, int]:
    """Extract meta description content and its length.

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (content, length).  Both are empty/0 if absent.
    """
    tag = soup.find("meta", attrs={"name": "description"})
    if tag is None:
        return "", 0
    content = (tag.get("content") or "").strip()  # type: ignore[union-attr]
    return content, len(content)


def _extract_headings(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Extract all heading tags (H1–H6) in document order.

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Ordered list of dicts with keys ``"level"`` (e.g. ``"h2"``) and
        ``"text"``.
    """
    headings: list[dict[str, str]] = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        headings.append({
            "level": tag.name.lower(),
            "text": tag.get_text(" ", strip=True),
        })
    return headings


def _extract_image_stats(soup: BeautifulSoup) -> tuple[int, int, int]:
    """Count images and classify by alt-text presence.

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (total, with_alt, without_alt).
    """
    images = soup.find_all("img")
    total = len(images)
    with_alt = 0
    without_alt = 0
    for img in images:
        alt = img.get("alt")
        if alt is not None and str(alt).strip():
            with_alt += 1
        else:
            without_alt += 1
    return total, with_alt, without_alt


def _extract_link_counts(soup: BeautifulSoup, base_url: str) -> tuple[int, int]:
    """Count internal vs external links.

    Args:
        soup: Parsed BeautifulSoup object.
        base_url: Page URL for same-domain comparison.

    Returns:
        Tuple of (internal_count, external_count).
    """
    base_netloc = urlparse(base_url).netloc.lower().split(":")[0]
    internal = 0
    external = 0
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        netloc = urlparse(absolute).netloc.lower().split(":")[0]
        if netloc == base_netloc:
            internal += 1
        elif netloc:
            external += 1
    return internal, external


def _extract_content_metrics(soup: BeautifulSoup, html: str) -> tuple[int, float]:
    """Extract word count and Flesch-Kincaid reading level.

    Uses trafilatura for main-content extraction (strips nav/footer noise).
    Falls back to full-page text on extraction failure.

    Args:
        soup: Parsed BeautifulSoup object (used for fallback).
        html: Raw HTML string (passed to trafilatura).

    Returns:
        Tuple of (word_count, reading_level).
    """
    main_text: str = ""
    try:
        extracted = trafilatura.extract(html, include_tables=False)
        if extracted and len(extracted) > 50:
            main_text = extracted
    except Exception:
        pass

    if not main_text:
        # Fallback: strip scripts/styles and get visible text
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        main_text = soup.get_text(" ", strip=True)

    word_count = len(main_text.split()) if main_text else 0

    reading_level: float = 0.0
    if main_text and word_count >= 10:
        try:
            reading_level = textstat.flesch_kincaid_grade(main_text)
        except Exception:
            reading_level = 0.0

    return word_count, reading_level


def _is_ssr(soup: BeautifulSoup) -> bool:
    """Detect whether the page is server-side rendered.

    A page is considered SSR when its ``<body>`` contains >100 words of
    visible text (excluding script content).

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        True when the page appears to be SSR.
    """
    body = soup.body
    if body is None:
        return False
    # Remove script/style tags temporarily for word counting
    for tag in body(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = body.get_text(" ", strip=True)
    return len(visible_text.split()) > 100


def _extract_canonical(
    soup: BeautifulSoup, base_url: str
) -> tuple[bool, Optional[str]]:
    """Extract canonical URL information.

    Args:
        soup: Parsed BeautifulSoup object.
        base_url: Page URL for resolving relative canonical hrefs.

    Returns:
        Tuple of (has_canonical, canonical_url_or_None).
    """
    tag = soup.find("link", rel="canonical")
    if tag is None:
        return False, None
    href = (tag.get("href") or "").strip()  # type: ignore[union-attr]
    if not href:
        return False, None
    absolute = urljoin(base_url, href)
    return True, absolute


def _extract_robots_meta(soup: BeautifulSoup) -> tuple[bool, bool]:
    """Check for noindex and nofollow in meta robots tags.

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (is_noindex, is_nofollow).
    """
    tag = soup.find("meta", attrs={"name": "robots"})
    if tag is None:
        return False, False
    content = (tag.get("content") or "").lower()  # type: ignore[union-attr]
    return "noindex" in content, "nofollow" in content


def _extract_freshness(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    """Extract publish and modified dates from meta tags and ``<time>`` elements.

    Checks in order:
    1. ``<meta property="article:published_time">``
    2. ``<meta property="article:modified_time">``
    3. First ``<time datetime="...">`` element

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (publish_date_str_or_None, modified_date_str_or_None).
    """
    publish_date: Optional[str] = None
    modified_date: Optional[str] = None

    pub_meta = soup.find("meta", attrs={"property": "article:published_time"})
    if pub_meta is not None:
        val = pub_meta.get("content")  # type: ignore[union-attr]
        if val:
            publish_date = str(val).strip()

    mod_meta = soup.find("meta", attrs={"property": "article:modified_time"})
    if mod_meta is not None:
        val = mod_meta.get("content")  # type: ignore[union-attr]
        if val:
            modified_date = str(val).strip()

    # Fallback: first <time> element with a datetime attribute
    if not publish_date:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag is not None:
            val = time_tag.get("datetime")  # type: ignore[union-attr]
            if val:
                publish_date = str(val).strip()

    return publish_date, modified_date


def _extract_author(soup: BeautifulSoup) -> tuple[bool, Optional[str]]:
    """Detect author attribution on the page.

    Checks (in order):
    1. ``<meta name="author">``
    2. ``<a rel="author">``
    3. Common author CSS class patterns

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (has_author, author_name_or_None).
    """
    # meta name="author"
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author is not None:
        val = meta_author.get("content")  # type: ignore[union-attr]
        if val and str(val).strip():
            return True, str(val).strip()

    # <a rel="author">
    rel_author = soup.find("a", rel="author")
    if rel_author is not None:
        text = rel_author.get_text(strip=True)
        if text:
            return True, text

    # Common author class patterns
    for pattern in _AUTHOR_CLASS_PATTERNS:
        for tag in soup.find_all(class_=re.compile(pattern, re.IGNORECASE)):
            text = tag.get_text(strip=True) if isinstance(tag, Tag) else ""
            if text and len(text) < 100:  # Sanity check — not a paragraph
                return True, text

    return False, None


def _has_mixed_content(soup: BeautifulSoup, page_url: str) -> bool:
    """Detect mixed content on HTTPS pages.

    Checks ``src`` and ``href`` attributes on ``<script>``, ``<link>``,
    ``<img>``, ``<iframe>``, and ``<source>`` tags for HTTP-schemed URLs.

    Args:
        soup: Parsed BeautifulSoup object.
        page_url: Page URL — only checked on HTTPS pages.

    Returns:
        True when an HTTP resource is loaded on an HTTPS page.
    """
    if not page_url.startswith("https://"):
        return False

    check_attrs = [
        ("script", "src"),
        ("link", "href"),
        ("img", "src"),
        ("iframe", "src"),
        ("source", "src"),
    ]
    for tag_name, attr in check_attrs:
        for tag in soup.find_all(tag_name, **{attr: True}):
            val = (tag.get(attr) or "").strip()
            if val.startswith("http://"):
                return True
    return False


# ---------------------------------------------------------------------------
# Single-page analysis (synchronous, pure CPU)
# ---------------------------------------------------------------------------


def analyze_single_page(
    url: str,
    html: str,
    depth: int,
    status_code: int,
    redirect_url: Optional[str],
    config: AuditConfig,
) -> PageAuditResult:
    """Analyse a single crawled page and return a structured result.

    This function is synchronous and has no I/O.  It can be called directly
    or via ``asyncio.to_thread()`` if needed.

    Args:
        url: Page URL (normalized).
        html: Raw HTML string of the page.
        depth: BFS crawl depth at which this page was found.
        status_code: HTTP status code returned for this URL.
        redirect_url: Final URL if a redirect occurred, else ``None``.
        config: Audit configuration for thresholds.

    Returns:
        :class:`~core.models.site_audit.PageAuditResult` with all extracted
        signals and a ``findings`` list populated by the check functions.
    """
    result = PageAuditResult(
        url=url,
        status_code=status_code,
        crawl_depth=depth,
        redirect_url=redirect_url,
    )

    # Collect all findings
    all_findings: list[AuditFinding] = []

    # Status code findings
    all_findings.extend(check_status_code(url, status_code))

    # Depth findings
    all_findings.extend(check_crawl_depth(url, depth))

    # Security: HTTPS
    all_findings.extend(check_https(url))

    # No HTML content — can't do further checks
    if not html:
        result.findings = all_findings
        return result

    # Parse HTML — use html.parser (stdlib, no extra deps)
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning("Failed to parse HTML for %s: %s", url, exc)
        result.findings = all_findings
        return result

    # Title
    title, title_length = _extract_title(soup)
    result.title = title
    result.title_length = title_length
    all_findings.extend(check_title(url, title, title_length, config))

    # Meta description
    meta_desc, meta_length = _extract_meta_description(soup)
    result.meta_description = meta_desc
    result.meta_description_length = meta_length
    all_findings.extend(check_meta_description(url, meta_desc, meta_length, config))

    # Headings
    headings = _extract_headings(soup)
    result.headings = headings
    h1_tags = [h for h in headings if h.get("level") == "h1"]
    h1_count = len(h1_tags)
    h1_text = h1_tags[0].get("text", "") if h1_tags else ""
    result.h1_count = h1_count
    result.h1_text = h1_text
    all_findings.extend(check_h1(url, h1_count, h1_text))
    all_findings.extend(check_heading_hierarchy(url, headings))
    result.heading_hierarchy_valid = not any(
        f.finding_type == "heading_hierarchy_skip" for f in all_findings
    )

    # Images
    total_imgs, with_alt, without_alt = _extract_image_stats(soup)
    result.image_count = total_imgs
    result.images_with_alt = with_alt
    result.images_without_alt = without_alt
    all_findings.extend(check_images(url, total_imgs, without_alt))

    # Links
    internal_count, external_count = _extract_link_counts(soup, url)
    result.internal_link_count = internal_count
    result.external_link_count = external_count
    all_findings.extend(check_internal_links(url, internal_count))

    # Content metrics
    word_count, reading_level = _extract_content_metrics(soup, html)
    result.word_count = word_count
    result.reading_level = reading_level

    # SSR detection — re-parse since we decomposed tags above during content extraction
    try:
        fresh_soup = BeautifulSoup(html, "html.parser")
        result.is_ssr = _is_ssr(fresh_soup)
    except Exception:
        result.is_ssr = True

    # Canonical
    has_canonical, canonical_url = _extract_canonical(soup, url)
    result.has_canonical = has_canonical
    result.canonical_url = canonical_url
    all_findings.extend(check_canonical(url, has_canonical, canonical_url))

    # Robots meta
    is_noindex, is_nofollow = _extract_robots_meta(soup)
    result.is_noindex = is_noindex
    result.is_nofollow = is_nofollow
    all_findings.extend(check_noindex(url, is_noindex))

    # Mixed content
    mixed = _has_mixed_content(soup, url)
    result.has_mixed_content = mixed
    result.has_https = url.startswith("https://")
    all_findings.extend(check_mixed_content(url, mixed))

    # Freshness
    publish_date, modified_date = _extract_freshness(soup)
    result.publish_date = publish_date
    result.modified_date = modified_date
    all_findings.extend(check_freshness(url, publish_date, modified_date))

    # Author
    has_author, author_name = _extract_author(soup)
    result.has_author = has_author
    result.author_name = author_name
    all_findings.extend(check_author(url, has_author))

    result.findings = all_findings
    return result


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def analyze_all_pages(
    pages: list[tuple[str, str]],
    depth_map: dict[str, int],
    status_code_map: dict[str, int],
    redirect_map: dict[str, str],
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> list[PageAuditResult]:
    """Analyse all crawled pages concurrently.

    Wraps :func:`analyze_single_page` calls with an ``asyncio.Semaphore``
    and gathers results.  ``analyze_single_page`` itself is synchronous —
    no ``asyncio.to_thread()`` needed for typical page volumes.

    Args:
        pages: List of ``(url, html)`` pairs from s1_discover.
        depth_map: ``{url: depth}`` from s1_discover.
        status_code_map: ``{url: status_code}`` from s1_discover.
        redirect_map: ``{url: final_url}`` from s1_discover.
        config: Audit configuration.

    Returns:
        List of :class:`~core.models.site_audit.PageAuditResult` objects,
        one per input page.  Errors in individual page analysis are caught
        and logged without crashing the full run.
    """
    semaphore = asyncio.Semaphore(config.page_analysis_concurrency)

    async def _analyse_one(url: str, html: str) -> PageAuditResult:
        async with semaphore:
            depth = depth_map.get(url, 0)
            status = status_code_map.get(url, 200)
            redirect = redirect_map.get(url)
            try:
                return analyze_single_page(
                    url=url,
                    html=html,
                    depth=depth,
                    status_code=status,
                    redirect_url=redirect,
                    config=config,
                )
            except Exception as exc:
                logger.error("Page analysis failed for %s: %s", url, exc, exc_info=True)
                return PageAuditResult(
                    url=url,
                    status_code=status,
                    crawl_depth=depth,
                    redirect_url=redirect,
                )

    tasks = [_analyse_one(url, html) for url, html in pages]
    results = await asyncio.gather(*tasks)
    return list(results)
