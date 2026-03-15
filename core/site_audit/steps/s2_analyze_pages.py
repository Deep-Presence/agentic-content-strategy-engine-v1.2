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
from core.site_audit.checks.performance import check_ssr_content
from core.site_audit.checks.performance_structural import (
    check_image_optimization,
    check_inline_code_weight,
    check_page_size,
    check_render_blocking,
    check_resource_counts,
)
from core.site_audit.checks.schema_checks import infer_page_type
from core.site_audit.checks.security import (
    check_https,
    check_mixed_content,
    check_security_headers,
)
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
    text = title_tag.get_text(" ", strip=True)
    return text, len(text)


def _extract_meta_description(soup: BeautifulSoup) -> tuple[str, int]:
    """Extract meta description content and its length.

    Fallback chain:
    1. ``<meta name="description">``
    2. ``<meta property="og:description">``
    3. ``<meta name="twitter:description">``

    Args:
        soup: Parsed BeautifulSoup object.

    Returns:
        Tuple of (content, length).  Both are empty/0 if absent.
    """
    # Primary: standard meta description
    tag = soup.find("meta", attrs={"name": "description"})
    if tag is not None:
        content = (tag.get("content") or "").strip()  # type: ignore[union-attr]
        if content:
            return content, len(content)

    # Fallback 1: Open Graph description
    tag = soup.find("meta", attrs={"property": "og:description"})
    if tag is not None:
        content = (tag.get("content") or "").strip()  # type: ignore[union-attr]
        if content:
            return content, len(content)

    # Fallback 2: Twitter card description
    tag = soup.find("meta", attrs={"name": "twitter:description"})
    if tag is not None:
        content = (tag.get("content") or "").strip()  # type: ignore[union-attr]
        if content:
            return content, len(content)

    return "", 0


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
        # Fallback: re-parse from raw HTML to avoid mutating the shared soup
        fallback_soup = BeautifulSoup(html, "html.parser")
        for tag in fallback_soup(["script", "style", "noscript"]):
            tag.decompose()
        main_text = fallback_soup.get_text(" ", strip=True)

    word_count = len(main_text.split()) if main_text else 0

    reading_level: float = 0.0
    if main_text and word_count >= 10:
        try:
            reading_level = textstat.flesch_kincaid_grade(main_text)
        except Exception:
            reading_level = 0.0

    return word_count, reading_level


def _is_ssr(html: str) -> bool:
    """Detect whether the page is server-side rendered.

    A page is considered SSR when its ``<body>`` contains >100 words of
    visible text (excluding script content).

    Re-parses from raw HTML internally to avoid mutating any shared soup.

    Args:
        html: Raw HTML string.

    Returns:
        True when the page appears to be SSR.
    """
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if body is None:
        return False
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

    # Additional fallbacks for modified_date
    if not modified_date:
        for prop in ("og:updated_time", "DC.date.modified"):
            tag = soup.find("meta", attrs={"property": prop}) or soup.find(
                "meta", attrs={"name": prop}
            )
            if tag is not None:
                val = tag.get("content")  # type: ignore[union-attr]
                if val:
                    modified_date = str(val).strip()
                    break
        if not modified_date:
            tag = soup.find("meta", attrs={"itemprop": "dateModified"})
            if tag is not None:
                val = tag.get("content")  # type: ignore[union-attr]
                if val:
                    modified_date = str(val).strip()

    # Additional fallbacks for publish_date
    if not publish_date:
        tag = soup.find("meta", attrs={"itemprop": "datePublished"})
        if tag is not None:
            val = tag.get("content")  # type: ignore[union-attr]
            if val:
                publish_date = str(val).strip()
        if not publish_date:
            tag = soup.find("meta", attrs={"name": "DC.date.created"})
            if tag is not None:
                val = tag.get("content")  # type: ignore[union-attr]
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


_HTTP_URL_IN_CSS_RE = re.compile(
    r"""url\(\s*['"]?(http://[^'")]+)['"]?\s*\)""", re.IGNORECASE,
)


def _has_mixed_content(soup: BeautifulSoup, page_url: str) -> bool:
    """Detect mixed content on HTTPS pages.

    Checks:
    1. ``src`` / ``href`` attributes on resource tags.
    2. ``srcset`` on ``<img>`` and ``<source>`` (comma-separated URL list).
    3. ``poster`` on ``<video>``, ``data`` on ``<object>``, ``src`` on ``<embed>``.
    4. Inline ``style`` attributes and ``<style>`` blocks for ``url(http://...)``.

    Args:
        soup: Parsed BeautifulSoup object.
        page_url: Page URL — only checked on HTTPS pages.

    Returns:
        True when an HTTP resource is loaded on an HTTPS page.
    """
    if not page_url.startswith("https://"):
        return False

    # Phase 1: Standard tag/attribute pairs
    check_attrs = [
        ("script", "src"),
        ("link", "href"),
        ("img", "src"),
        ("iframe", "src"),
        ("source", "src"),
        ("video", "poster"),
        ("object", "data"),
        ("embed", "src"),
    ]
    for tag_name, attr in check_attrs:
        for tag in soup.find_all(tag_name, **{attr: True}):
            val = (tag.get(attr) or "").strip()
            if val.startswith("http://"):
                return True

    # Phase 2: srcset attributes (img, source) — comma-separated URL+descriptor
    for tag_name in ("img", "source"):
        for tag in soup.find_all(tag_name, srcset=True):
            for entry in (tag.get("srcset") or "").split(","):
                url_part = entry.strip().split()[0] if entry.strip() else ""
                if url_part.startswith("http://"):
                    return True

    # Phase 3: Inline style attributes with url(http://...)
    for tag in soup.find_all(style=True):
        if _HTTP_URL_IN_CSS_RE.search(tag.get("style") or ""):
            return True

    # Phase 4: <style> blocks
    for style_tag in soup.find_all("style"):
        text = style_tag.string or style_tag.get_text()
        if text and _HTTP_URL_IN_CSS_RE.search(text):
            return True

    return False


# ---------------------------------------------------------------------------
# Performance structural extraction helpers (pure, no I/O)
# ---------------------------------------------------------------------------


def _extract_page_size(html: str) -> int:
    """Return HTML size in bytes."""
    return len(html.encode("utf-8"))


def _extract_resource_counts(soup: BeautifulSoup) -> tuple[int, int]:
    """Count external scripts and external stylesheets.

    Returns:
        Tuple of (external_script_count, external_css_count).
    """
    external_scripts = len(soup.find_all("script", src=True))
    external_css = len(soup.find_all("link", rel="stylesheet"))
    return external_scripts, external_css


def _extract_render_blocking(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
    """Identify render-blocking scripts and stylesheets in ``<head>``.

    Returns:
        Tuple of (blocking_script_urls, blocking_css_urls).
    """
    head = soup.find("head")
    if not head:
        return [], []

    blocking_scripts: list[str] = []
    for script in head.find_all("script", src=True):
        if not (
            script.has_attr("async")
            or script.has_attr("defer")
            or script.get("type") == "module"
        ):
            blocking_scripts.append(script.get("src", ""))

    blocking_css: list[str] = []
    for link in head.find_all("link", rel="stylesheet"):
        media = (link.get("media") or "").lower()
        if not link.has_attr("disabled") and media not in ("print", "not all"):
            blocking_css.append(link.get("href", ""))

    return blocking_scripts, blocking_css


def _extract_image_optimization_signals(soup: BeautifulSoup) -> dict:
    """Extract image optimization signals.

    Returns:
        Dict with keys: total, without_lazy, without_dimensions,
        without_srcset, uses_modern_formats.
    """
    images = soup.find_all("img")
    total = len(images)
    without_lazy = 0
    without_dimensions = 0
    without_srcset = 0
    modern_format_count = 0

    for img in images:
        if img.get("loading", "").lower() != "lazy":
            without_lazy += 1
        if not (img.get("width") and img.get("height")):
            without_dimensions += 1
        if not img.has_attr("srcset"):
            without_srcset += 1
        src = (img.get("src") or "").lower()
        if src.endswith((".webp", ".avif")):
            modern_format_count += 1

    return {
        "total": total,
        "without_lazy": without_lazy,
        "without_dimensions": without_dimensions,
        "without_srcset": without_srcset,
        "uses_modern_formats": modern_format_count > 0,
    }


def _extract_inline_code_weight(soup: BeautifulSoup) -> tuple[int, int]:
    """Return (inline_js_bytes, inline_css_bytes)."""
    js_bytes = sum(
        len((s.string or "").encode("utf-8"))
        for s in soup.find_all("script")
        if not s.get("src") and s.string
    )
    css_bytes = sum(
        len((s.string or "").encode("utf-8"))
        for s in soup.find_all("style")
        if s.string
    )
    return js_bytes, css_bytes


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
    check_core_web_vitals: bool = True,
    headers: dict[str, str] | None = None,
    sitemap_lastmod: str | None = None,
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

    # SSR detection — _is_ssr re-parses internally (no shared state)
    try:
        result.is_ssr = _is_ssr(html)
    except Exception:
        result.is_ssr = True

    # Performance: SSR content check (pure, no I/O)
    if check_core_web_vitals:
        all_findings.extend(check_ssr_content(html, url))

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

    # Security headers (HTTPS pages only, when headers available)
    if headers is not None and url.startswith("https://"):
        all_findings.extend(check_security_headers(url, headers))

    # Performance — structural checks
    html_bytes = _extract_page_size(html)
    result.html_bytes = html_bytes
    all_findings.extend(check_page_size(url, html_bytes, config))

    ext_scripts, ext_css = _extract_resource_counts(soup)
    result.external_script_count = ext_scripts
    result.external_css_count = ext_css
    all_findings.extend(check_resource_counts(url, ext_scripts, ext_css, config))

    blocking_scripts, blocking_css = _extract_render_blocking(soup)
    result.blocking_script_count = len(blocking_scripts)
    result.blocking_css_count = len(blocking_css)
    all_findings.extend(check_render_blocking(url, blocking_scripts, blocking_css, config))

    img_signals = _extract_image_optimization_signals(soup)
    result.images_without_lazy = img_signals["without_lazy"]
    result.images_without_dimensions = img_signals["without_dimensions"]
    all_findings.extend(
        check_image_optimization(
            url,
            images_without_lazy=img_signals["without_lazy"],
            images_without_dimensions=img_signals["without_dimensions"],
            images_without_srcset=img_signals["without_srcset"],
            total_images=img_signals["total"],
            uses_modern_formats=img_signals["uses_modern_formats"],
            config=config,
        )
    )

    inline_js, inline_css = _extract_inline_code_weight(soup)
    result.inline_js_bytes = inline_js
    result.inline_css_bytes = inline_css
    all_findings.extend(check_inline_code_weight(url, inline_js, inline_css, config))

    # Freshness (enhanced: pass HTTP Last-Modified + sitemap lastmod)
    publish_date, modified_date = _extract_freshness(soup)
    result.publish_date = publish_date
    result.modified_date = modified_date
    page_type = infer_page_type(url, html)
    http_last_modified = (
        {k.lower(): v for k, v in headers.items()}.get("last-modified")
        if headers
        else None
    )
    all_findings.extend(
        check_freshness(
            url,
            publish_date,
            modified_date,
            page_type=page_type,
            http_last_modified=http_last_modified,
            sitemap_lastmod=sitemap_lastmod,
        )
    )

    # Author — only penalise missing author on article-type pages (blog, posts,
    # articles).  Homepages, product pages, etc. do not need author attribution.
    has_author, author_name = _extract_author(soup)
    result.has_author = has_author
    result.author_name = author_name
    if page_type == "article":
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
    check_core_web_vitals: bool = True,
    headers_map: dict[str, dict[str, str]] | None = None,
    sitemap_lastmod_map: dict[str, str] | None = None,
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
        headers_map: ``{url: {header: value}}`` HTTP response headers per page.
        sitemap_lastmod_map: ``{url: lastmod_str}`` from sitemap.

    Returns:
        List of :class:`~core.models.site_audit.PageAuditResult` objects,
        one per input page.  Errors in individual page analysis are caught
        and logged without crashing the full run.
    """
    _headers = headers_map or {}
    _lastmod = sitemap_lastmod_map or {}
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
                    check_core_web_vitals=check_core_web_vitals,
                    headers=_headers.get(url),
                    sitemap_lastmod=_lastmod.get(url),
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
