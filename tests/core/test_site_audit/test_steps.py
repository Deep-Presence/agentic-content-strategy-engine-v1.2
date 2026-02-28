"""Tests for core/site_audit/steps/s2_analyze_pages.py.

Covers:
  - analyze_single_page with well-formed HTML (correct extraction)
  - minimal HTML (<html></html>) → no crash
  - HTML with 0 headings
  - HTML with 50 H1s
  - HTML with no title tag
  - HTML with unicode
  - HTML with deeply nested structure
  - Empty HTML string
  - SSR detection
  - Mixed content detection
  - Canonical extraction
  - Author extraction variants
  - Freshness date extraction
  - analyze_all_pages async orchestration
"""
from __future__ import annotations

import asyncio
import textwrap
from unittest.mock import patch

import pytest

from core.models.site_audit import AuditCheckSeverity, PageAuditResult
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG
from core.site_audit.steps.s2_analyze_pages import (
    _extract_author,
    _extract_canonical,
    _extract_content_metrics,
    _extract_freshness,
    _extract_headings,
    _extract_image_stats,
    _extract_link_counts,
    _extract_meta_description,
    _extract_robots_meta,
    _extract_title,
    _has_mixed_content,
    _is_ssr,
    analyze_all_pages,
    analyze_single_page,
)
from bs4 import BeautifulSoup

_URL = "https://example.com/page"


def _soup(html: str) -> BeautifulSoup:
    """Helper to build a BeautifulSoup from html string."""
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# Fixture HTML strings
# ---------------------------------------------------------------------------

_WELL_FORMED = textwrap.dedent("""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <title>How B2B Companies Win AI Search Citations | DeepPresence</title>
      <meta name="description" content="This comprehensive guide explains the
      strategies B2B SaaS companies use to appear in AI-generated search results
      like Perplexity and ChatGPT. Covers technical, content, and E-E-A-T signals."/>
      <link rel="canonical" href="https://example.com/page"/>
      <meta name="author" content="Jane Smith"/>
      <meta property="article:published_time" content="2025-06-01T10:00:00Z"/>
    </head>
    <body>
      <h1>How B2B Companies Win AI Search Citations</h1>
      <h2>Introduction</h2>
      <p>In 2025, AI search engines like Perplexity and ChatGPT have fundamentally
         changed how B2B buyers discover software vendors. This guide explains...</p>
      <p>Companies that invest in structured content and E-E-A-T signals are seeing
         dramatically higher citation rates across all major AI platforms.</p>
      <h2>The Technical Foundation</h2>
      <p>Before any content strategy can work, your site needs to be technically
         accessible to AI crawlers. That means robots.txt, llms.txt, clean HTML,
         and fast page load times.</p>
      <h3>Robots.txt Configuration</h3>
      <p>AI search bots like GPTBot and ClaudeBot respect robots.txt directives.
         Blocking them means your content will never be cited.</p>
      <img src="/diagram1.png" alt="AI citation diagram showing source ranking"/>
      <img src="/photo.jpg" alt="Team working on content strategy"/>
      <a href="/about">About Us</a>
      <a href="/pricing">Pricing</a>
      <a href="https://external.com/source">External Source</a>
    </body>
    </html>
""")

_MINIMAL_HTML = "<html></html>"
_EMPTY_HTML = ""
_NO_HEADINGS = "<html><head><title>Page</title></head><body><p>Content only</p></body></html>"
_MANY_H1 = "<html><body>" + "".join(f"<h1>H1 Number {i}</h1>" for i in range(50)) + "</body></html>"
_NO_TITLE = "<html><body><h1>Heading</h1><p>Content</p></body></html>"
_UNICODE = (
    "<html><head><title>Ünïcödé pägé ñ</title></head>"
    "<body><h1>Héading with ünïcödé</h1><p>テスト テスト</p></body></html>"
)
_DEEPLY_NESTED = "<html><body>" + "<div>" * 100 + "<p>Deep content</p>" + "</div>" * 100 + "</body></html>"
_HTTP_PAGE = textwrap.dedent("""\
    <html><head><title>HTTP Page</title></head>
    <body>
      <h1>Insecure Page</h1>
      <p>Content here.</p>
    </body></html>
""")
_MIXED_CONTENT = textwrap.dedent("""\
    <html><head><title>Mixed Content</title></head>
    <body>
      <h1>HTTPS page with HTTP resource</h1>
      <script src="http://cdn.example.com/analytics.js"></script>
      <img src="http://images.example.com/logo.png" alt="Logo"/>
    </body></html>
""")
_META_NOINDEX = textwrap.dedent("""\
    <html><head>
      <meta name="robots" content="noindex, nofollow"/>
      <title>Private Page</title>
    </head><body><h1>Private</h1></body></html>
""")
_RSS_LINK_HTML = textwrap.dedent("""\
    <html><head>
      <title>Blog</title>
      <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="RSS"/>
    </head><body><h1>Blog</h1></body></html>
""")


# ---------------------------------------------------------------------------
# _extract_title tests
# ---------------------------------------------------------------------------


class TestExtractTitle:
    def test_normal_title(self) -> None:
        soup = _soup("<html><head><title>Hello World</title></head></html>")
        title, length = _extract_title(soup)
        assert title == "Hello World"
        assert length == 11

    def test_no_title_returns_empty(self) -> None:
        soup = _soup("<html><head></head></html>")
        title, length = _extract_title(soup)
        assert title == ""
        assert length == 0

    def test_empty_title_tag(self) -> None:
        soup = _soup("<html><head><title></title></head></html>")
        title, length = _extract_title(soup)
        assert title == ""
        assert length == 0

    def test_whitespace_stripped(self) -> None:
        soup = _soup("<html><head><title>  Hello  </title></head></html>")
        title, _ = _extract_title(soup)
        assert title == "Hello"


# ---------------------------------------------------------------------------
# _extract_meta_description tests
# ---------------------------------------------------------------------------


class TestExtractMetaDescription:
    def test_normal_meta(self) -> None:
        soup = _soup('<html><head><meta name="description" content="A great page"/></head></html>')
        desc, length = _extract_meta_description(soup)
        assert desc == "A great page"
        assert length == 12

    def test_no_meta_returns_empty(self) -> None:
        soup = _soup("<html><head></head></html>")
        desc, length = _extract_meta_description(soup)
        assert desc == ""
        assert length == 0

    def test_empty_content_attribute(self) -> None:
        soup = _soup('<html><head><meta name="description" content=""/></head></html>')
        desc, length = _extract_meta_description(soup)
        assert desc == ""
        assert length == 0


# ---------------------------------------------------------------------------
# _extract_image_stats tests
# ---------------------------------------------------------------------------


class TestExtractImageStats:
    def test_all_with_alt(self) -> None:
        html = '<html><body><img src="a.jpg" alt="A"/><img src="b.jpg" alt="B"/></body></html>'
        soup = _soup(html)
        total, with_alt, without_alt = _extract_image_stats(soup)
        assert total == 2
        assert with_alt == 2
        assert without_alt == 0

    def test_none_with_alt(self) -> None:
        html = '<html><body><img src="a.jpg"/><img src="b.jpg"/></body></html>'
        soup = _soup(html)
        total, with_alt, without_alt = _extract_image_stats(soup)
        assert total == 2
        assert with_alt == 0
        assert without_alt == 2

    def test_empty_alt_counts_as_without(self) -> None:
        html = '<html><body><img src="a.jpg" alt=""/></body></html>'
        soup = _soup(html)
        total, with_alt, without_alt = _extract_image_stats(soup)
        assert total == 1
        assert without_alt == 1

    def test_no_images(self) -> None:
        soup = _soup("<html><body><p>No images here</p></body></html>")
        total, with_alt, without_alt = _extract_image_stats(soup)
        assert total == 0
        assert with_alt == 0
        assert without_alt == 0


# ---------------------------------------------------------------------------
# _extract_canonical tests
# ---------------------------------------------------------------------------


class TestExtractCanonical:
    def test_has_canonical(self) -> None:
        html = '<html><head><link rel="canonical" href="https://example.com/page"/></head></html>'
        soup = _soup(html)
        has_can, url = _extract_canonical(soup, "https://example.com/page")
        assert has_can is True
        assert url == "https://example.com/page"

    def test_no_canonical(self) -> None:
        soup = _soup("<html><head></head></html>")
        has_can, url = _extract_canonical(soup, "https://example.com/page")
        assert has_can is False
        assert url is None

    def test_relative_canonical_resolved(self) -> None:
        html = '<html><head><link rel="canonical" href="/page"/></head></html>'
        soup = _soup(html)
        has_can, url = _extract_canonical(soup, "https://example.com/other")
        assert has_can is True
        assert url == "https://example.com/page"


# ---------------------------------------------------------------------------
# _extract_robots_meta tests
# ---------------------------------------------------------------------------


class TestExtractRobotsMeta:
    def test_noindex_detected(self) -> None:
        html = '<html><head><meta name="robots" content="noindex"/></head></html>'
        soup = _soup(html)
        noindex, nofollow = _extract_robots_meta(soup)
        assert noindex is True
        assert nofollow is False

    def test_nofollow_detected(self) -> None:
        html = '<html><head><meta name="robots" content="nofollow"/></head></html>'
        soup = _soup(html)
        noindex, nofollow = _extract_robots_meta(soup)
        assert noindex is False
        assert nofollow is True

    def test_both_detected(self) -> None:
        html = '<html><head><meta name="robots" content="noindex, nofollow"/></head></html>'
        soup = _soup(html)
        noindex, nofollow = _extract_robots_meta(soup)
        assert noindex is True
        assert nofollow is True

    def test_no_robots_meta(self) -> None:
        soup = _soup("<html><head></head></html>")
        noindex, nofollow = _extract_robots_meta(soup)
        assert noindex is False
        assert nofollow is False


# ---------------------------------------------------------------------------
# _extract_freshness tests
# ---------------------------------------------------------------------------


class TestExtractFreshness:
    def test_article_published_time(self) -> None:
        html = '<html><head><meta property="article:published_time" content="2025-01-15T10:00:00Z"/></head></html>'
        soup = _soup(html)
        pub, mod = _extract_freshness(soup)
        assert pub == "2025-01-15T10:00:00Z"
        assert mod is None

    def test_article_modified_time(self) -> None:
        html = (
            '<html><head>'
            '<meta property="article:published_time" content="2024-01-01"/>'
            '<meta property="article:modified_time" content="2025-06-01"/>'
            '</head></html>'
        )
        soup = _soup(html)
        pub, mod = _extract_freshness(soup)
        assert pub == "2024-01-01"
        assert mod == "2025-06-01"

    def test_time_tag_fallback(self) -> None:
        html = '<html><body><time datetime="2025-03-10">March 10, 2025</time></body></html>'
        soup = _soup(html)
        pub, mod = _extract_freshness(soup)
        assert pub == "2025-03-10"

    def test_no_dates(self) -> None:
        soup = _soup("<html><body><p>No dates here</p></body></html>")
        pub, mod = _extract_freshness(soup)
        assert pub is None
        assert mod is None


# ---------------------------------------------------------------------------
# _extract_author tests
# ---------------------------------------------------------------------------


class TestExtractAuthor:
    def test_meta_author(self) -> None:
        html = '<html><head><meta name="author" content="Jane Smith"/></head></html>'
        soup = _soup(html)
        has_auth, name = _extract_author(soup)
        assert has_auth is True
        assert name == "Jane Smith"

    def test_rel_author_link(self) -> None:
        html = '<html><body><a rel="author" href="/authors/jane">Jane Smith</a></body></html>'
        soup = _soup(html)
        has_auth, name = _extract_author(soup)
        assert has_auth is True
        assert name == "Jane Smith"

    def test_author_class_pattern(self) -> None:
        html = '<html><body><span class="post-author">John Doe</span></body></html>'
        soup = _soup(html)
        has_auth, name = _extract_author(soup)
        assert has_auth is True

    def test_no_author(self) -> None:
        soup = _soup("<html><body><p>Just content</p></body></html>")
        has_auth, name = _extract_author(soup)
        assert has_auth is False
        assert name is None


# ---------------------------------------------------------------------------
# _has_mixed_content tests
# ---------------------------------------------------------------------------


class TestHasMixedContent:
    def test_https_page_with_http_script(self) -> None:
        html = '<html><body><script src="http://cdn.example.com/x.js"></script></body></html>'
        soup = _soup(html)
        assert _has_mixed_content(soup, "https://example.com/page") is True

    def test_https_page_no_http_resources(self) -> None:
        html = '<html><body><script src="https://cdn.example.com/x.js"></script></body></html>'
        soup = _soup(html)
        assert _has_mixed_content(soup, "https://example.com/page") is False

    def test_http_page_always_false(self) -> None:
        # Only applicable on HTTPS pages
        html = '<html><body><script src="http://cdn.example.com/x.js"></script></body></html>'
        soup = _soup(html)
        assert _has_mixed_content(soup, "http://example.com/page") is False

    def test_http_img_counts(self) -> None:
        html = '<html><body><img src="http://images.example.com/photo.jpg" alt=""/></body></html>'
        soup = _soup(html)
        assert _has_mixed_content(soup, "https://example.com/page") is True


# ---------------------------------------------------------------------------
# _is_ssr tests
# ---------------------------------------------------------------------------


class TestIsSsr:
    def test_page_with_lots_of_text_is_ssr(self) -> None:
        words = " ".join(["word"] * 200)
        html = f"<html><body><p>{words}</p></body></html>"
        soup = _soup(html)
        assert _is_ssr(soup) is True

    def test_page_with_only_scripts_is_not_ssr(self) -> None:
        html = '<html><body><script>var app = {};</script></body></html>'
        soup = _soup(html)
        assert _is_ssr(soup) is False

    def test_empty_body_is_not_ssr(self) -> None:
        soup = _soup("<html><body></body></html>")
        assert _is_ssr(soup) is False

    def test_no_body_returns_false(self) -> None:
        soup = _soup("<html></html>")
        assert _is_ssr(soup) is False


# ---------------------------------------------------------------------------
# analyze_single_page integration tests
# ---------------------------------------------------------------------------


class TestAnalyzeSinglePage:
    """Integration tests for the full analyze_single_page() function."""

    def test_well_formed_html_no_crash(self) -> None:
        result = analyze_single_page(
            url=_URL,
            html=_WELL_FORMED,
            depth=0,
            status_code=200,
            redirect_url=None,
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert isinstance(result, PageAuditResult)
        assert result.url == _URL

    def test_well_formed_html_extracts_title(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert "AI Search Citations" in result.title

    def test_well_formed_html_extracts_h1(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.h1_count == 1
        assert "AI Search Citations" in result.h1_text

    def test_well_formed_html_has_canonical(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.has_canonical is True

    def test_well_formed_html_has_author(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.has_author is True

    def test_minimal_html_no_crash(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_MINIMAL_HTML, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert isinstance(result, PageAuditResult)
        assert result.url == _URL

    def test_empty_html_no_crash(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_EMPTY_HTML, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert isinstance(result, PageAuditResult)

    def test_no_headings_no_crash(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_NO_HEADINGS, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.h1_count == 0
        # Should have missing_h1 finding
        assert any(f.finding_type == "missing_h1" for f in result.findings)

    def test_many_h1_detected(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_MANY_H1, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.h1_count == 50
        assert any(f.finding_type == "multiple_h1" for f in result.findings)

    def test_no_title_critical_finding(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_NO_TITLE, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.title == ""
        assert any(f.finding_type == "missing_title" for f in result.findings)
        title_findings = [f for f in result.findings if f.finding_type == "missing_title"]
        assert title_findings[0].severity == AuditCheckSeverity.critical

    def test_unicode_content_no_crash(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_UNICODE, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert isinstance(result, PageAuditResult)
        assert "cödé" in result.title or "title" in result.title.lower() or len(result.title) > 0

    def test_deeply_nested_html_no_crash(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_DEEPLY_NESTED, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert isinstance(result, PageAuditResult)

    def test_http_url_critical_https_finding(self) -> None:
        http_url = "http://example.com/page"
        result = analyze_single_page(
            url=http_url, html=_HTTP_PAGE, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert any(f.finding_type == "not_https" for f in result.findings)
        https_findings = [f for f in result.findings if f.finding_type == "not_https"]
        assert https_findings[0].severity == AuditCheckSeverity.critical

    def test_noindex_page_info_finding(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_META_NOINDEX, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.is_noindex is True
        assert any(f.finding_type == "noindex_page" for f in result.findings)

    def test_mixed_content_detected(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_MIXED_CONTENT, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.has_mixed_content is True
        assert any(f.finding_type == "mixed_content" for f in result.findings)

    def test_depth_stored_in_result(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=3,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.crawl_depth == 3

    def test_status_code_stored(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=404, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.status_code == 404

    def test_redirect_url_stored(self) -> None:
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=301, redirect_url="https://example.com/new",
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert result.redirect_url == "https://example.com/new"

    def test_findings_are_list_of_audit_findings(self) -> None:
        from core.models.site_audit import AuditFinding
        result = analyze_single_page(
            url=_URL, html=_WELL_FORMED, depth=0,
            status_code=200, redirect_url=None, config=DEFAULT_AUDIT_CONFIG,
        )
        assert isinstance(result.findings, list)
        for finding in result.findings:
            assert isinstance(finding, AuditFinding)


# ---------------------------------------------------------------------------
# analyze_all_pages tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAnalyzeAllPages:
    """Tests for the async analyze_all_pages() orchestrator."""

    async def test_empty_pages_returns_empty(self) -> None:
        results = await analyze_all_pages(
            pages=[], depth_map={}, status_code_map={}, redirect_map={},
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert results == []

    async def test_single_page_processed(self) -> None:
        results = await analyze_all_pages(
            pages=[(_URL, _WELL_FORMED)],
            depth_map={_URL: 0},
            status_code_map={_URL: 200},
            redirect_map={},
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert len(results) == 1
        assert results[0].url == _URL

    async def test_multiple_pages_all_processed(self) -> None:
        pages = [
            ("https://example.com/", _WELL_FORMED),
            ("https://example.com/about", _NO_TITLE),
            ("https://example.com/blog", _MINIMAL_HTML),
        ]
        results = await analyze_all_pages(
            pages=pages,
            depth_map={
                "https://example.com/": 0,
                "https://example.com/about": 1,
                "https://example.com/blog": 1,
            },
            status_code_map={
                "https://example.com/": 200,
                "https://example.com/about": 200,
                "https://example.com/blog": 200,
            },
            redirect_map={},
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert len(results) == 3

    async def test_missing_depth_defaults_to_zero(self) -> None:
        results = await analyze_all_pages(
            pages=[(_URL, _WELL_FORMED)],
            depth_map={},  # URL not in depth_map
            status_code_map={},
            redirect_map={},
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert results[0].crawl_depth == 0

    async def test_missing_status_defaults_to_200(self) -> None:
        results = await analyze_all_pages(
            pages=[(_URL, _WELL_FORMED)],
            depth_map={},
            status_code_map={},  # URL not in status_code_map
            redirect_map={},
            config=DEFAULT_AUDIT_CONFIG,
        )
        assert results[0].status_code == 200

    async def test_error_in_one_page_does_not_crash_others(self) -> None:
        """An exception in one page analysis still returns results for others."""
        pages = [
            ("https://example.com/good", _WELL_FORMED),
            ("https://example.com/bad", _WELL_FORMED),
        ]

        original_func = analyze_single_page
        call_count = 0

        def patched_analyze(url: str, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "bad" in url:
                raise ValueError("Simulated analysis failure")
            return original_func(url, *args, **kwargs)

        with patch(
            "core.site_audit.steps.s2_analyze_pages.analyze_single_page",
            side_effect=patched_analyze,
        ):
            results = await analyze_all_pages(
                pages=pages,
                depth_map={},
                status_code_map={},
                redirect_map={},
                config=DEFAULT_AUDIT_CONFIG,
            )

        # Should still return 2 results (one may be a default PageAuditResult)
        assert len(results) == 2
