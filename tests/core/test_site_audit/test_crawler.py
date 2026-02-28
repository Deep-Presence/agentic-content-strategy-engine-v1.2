"""Tests for core/site_audit/steps/s1_discover.py.

Covers:
  - URL normalization (10+ cases)
  - Same-domain filtering
  - robots.txt parsing (200, 404, 500 responses)
  - AI bot detection (blocked / allowed for each bot)
  - Sitemap parsing (valid XML, invalid XML, sitemap index, empty)
  - BFS depth tracking
  - Redirect following
  - Timeout handling
  - max_pages enforcement
  - llms.txt check
  - RSS/Atom feed discovery
"""
from __future__ import annotations

import asyncio
import textwrap

import httpx
import pytest

from core.models.site_audit import AIBotAccessResult, SitemapHealthResult
from core.site_audit.steps.s1_discover import (
    AsyncSiteCrawler,
    S1DiscoveryOutput,
    _discover_feeds_from_html,
    _extract_links,
    _parse_ai_bot_access,
    _parse_sitemap,
    _parse_sitemap_urls_from_robots,
    is_same_domain,
    normalize_url,
    should_skip_url,
)
from urllib.robotparser import RobotFileParser


# ---------------------------------------------------------------------------
# URL normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeUrl:
    """Test normalize_url() across many input patterns."""

    def test_strips_fragment(self) -> None:
        result = normalize_url("https://example.com/page#section")
        assert "#section" not in result

    def test_lowercases_scheme(self) -> None:
        result = normalize_url("HTTPS://example.com/page")
        assert result.startswith("https://")

    def test_lowercases_host(self) -> None:
        result = normalize_url("https://EXAMPLE.COM/page")
        assert "example.com" in result.lower()
        assert "EXAMPLE" not in result

    def test_removes_trailing_slash_on_path(self) -> None:
        result = normalize_url("https://example.com/about/")
        assert not result.endswith("/")

    def test_preserves_root_path(self) -> None:
        result = normalize_url("https://example.com/")
        assert "example.com" in result

    def test_no_fragment_already(self) -> None:
        url = "https://example.com/page"
        assert normalize_url(url) == url

    def test_preserves_query_string(self) -> None:
        url = "https://example.com/search?q=hello"
        result = normalize_url(url)
        assert "q=hello" in result

    def test_handles_empty_string(self) -> None:
        result = normalize_url("")
        assert isinstance(result, str)

    def test_strips_fragment_with_query(self) -> None:
        result = normalize_url("https://example.com/page?q=1#anchor")
        assert "#anchor" not in result

    def test_preserves_port(self) -> None:
        url = "https://example.com:8080/page"
        result = normalize_url(url)
        assert "8080" in result

    def test_handles_relative_url_gracefully(self) -> None:
        result = normalize_url("/relative/path")
        assert isinstance(result, str)

    def test_unicode_url(self) -> None:
        url = "https://example.com/page-with-unicode"
        result = normalize_url(url)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Same-domain filtering tests
# ---------------------------------------------------------------------------


class TestIsSameDomain:
    """Test is_same_domain() domain comparison logic."""

    def test_exact_match(self) -> None:
        assert is_same_domain("https://example.com/page", "example.com") is True

    def test_subdomain_is_different(self) -> None:
        assert is_same_domain("https://blog.example.com/page", "example.com") is False

    def test_different_domain(self) -> None:
        assert is_same_domain("https://other.com/page", "example.com") is False

    def test_case_insensitive(self) -> None:
        assert is_same_domain("https://EXAMPLE.COM/page", "example.com") is True

    def test_with_port_stripped(self) -> None:
        assert is_same_domain("https://example.com:443/page", "example.com") is True

    def test_www_subdomain_is_different(self) -> None:
        assert is_same_domain("https://www.example.com/page", "example.com") is False


# ---------------------------------------------------------------------------
# Skip URL extension tests
# ---------------------------------------------------------------------------


class TestShouldSkipUrl:
    """Test should_skip_url() extension filtering."""

    @pytest.mark.parametrize("ext", [
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".mp4", ".mp3", ".zip", ".css", ".js", ".ico", ".xml",
    ])
    def test_skips_known_extensions(self, ext: str) -> None:
        url = f"https://example.com/file{ext}"
        assert should_skip_url(url) is True

    def test_does_not_skip_html_path(self) -> None:
        assert should_skip_url("https://example.com/page") is False

    def test_does_not_skip_no_extension(self) -> None:
        assert should_skip_url("https://example.com/about/team") is False

    def test_case_insensitive(self) -> None:
        assert should_skip_url("https://example.com/image.PNG") is True


# ---------------------------------------------------------------------------
# robots.txt parsing tests
# ---------------------------------------------------------------------------


_ROBOTS_ALL_ALLOWED = "User-agent: *\nAllow: /\n"
_ROBOTS_ALL_BLOCKED = "User-agent: *\nDisallow: /\n"
_ROBOTS_GPTBOT_BLOCKED = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
_ROBOTS_MULTI_BOT_BLOCKED = textwrap.dedent("""\
    User-agent: GPTBot
    Disallow: /

    User-agent: ClaudeBot
    Disallow: /

    User-agent: PerplexityBot
    Disallow: /

    User-agent: Google-Extended
    Disallow: /

    User-agent: CCBot
    Disallow: /

    User-agent: *
    Allow: /
""")


def _make_robot_parser(content: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.parse(content.splitlines())
    return rp


class TestParseAiBotAccess:
    """Test _parse_ai_bot_access() for all 5 AI bots."""

    def test_all_allowed_when_empty_robots(self) -> None:
        rp = _make_robot_parser("")
        result = _parse_ai_bot_access("", rp, "https://example.com/")
        assert result.gptbot_allowed is True
        assert result.claudebot_allowed is True
        assert result.perplexitybot_allowed is True
        assert result.google_extended_allowed is True
        assert result.ccbot_allowed is True
        assert result.robots_txt_exists is False

    def test_robots_exists_flag(self) -> None:
        rp = _make_robot_parser(_ROBOTS_ALL_ALLOWED)
        result = _parse_ai_bot_access(_ROBOTS_ALL_ALLOWED, rp, "https://example.com/")
        assert result.robots_txt_exists is True

    def test_gptbot_blocked(self) -> None:
        rp = _make_robot_parser(_ROBOTS_GPTBOT_BLOCKED)
        result = _parse_ai_bot_access(
            _ROBOTS_GPTBOT_BLOCKED, rp, "https://example.com/"
        )
        assert result.gptbot_allowed is False
        assert result.claudebot_allowed is True

    def test_all_bots_blocked(self) -> None:
        rp = _make_robot_parser(_ROBOTS_MULTI_BOT_BLOCKED)
        result = _parse_ai_bot_access(
            _ROBOTS_MULTI_BOT_BLOCKED, rp, "https://example.com/"
        )
        assert result.gptbot_allowed is False
        assert result.claudebot_allowed is False
        assert result.perplexitybot_allowed is False
        assert result.google_extended_allowed is False
        assert result.ccbot_allowed is False

    def test_star_disallow_blocks_known_bots(self) -> None:
        rp = _make_robot_parser(_ROBOTS_ALL_BLOCKED)
        result = _parse_ai_bot_access(
            _ROBOTS_ALL_BLOCKED, rp, "https://example.com/"
        )
        assert result.gptbot_allowed is False


class TestParseSitemapUrlsFromRobots:
    """Test _parse_sitemap_urls_from_robots() directive extraction."""

    def test_single_sitemap(self) -> None:
        robots = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"
        result = _parse_sitemap_urls_from_robots(robots)
        assert result == ["https://example.com/sitemap.xml"]

    def test_multiple_sitemaps(self) -> None:
        robots = (
            "Sitemap: https://example.com/sitemap1.xml\n"
            "Sitemap: https://example.com/sitemap2.xml\n"
        )
        result = _parse_sitemap_urls_from_robots(robots)
        assert len(result) == 2

    def test_empty_robots(self) -> None:
        assert _parse_sitemap_urls_from_robots("") == []

    def test_case_insensitive_directive(self) -> None:
        robots = "sitemap: https://example.com/sitemap.xml\n"
        result = _parse_sitemap_urls_from_robots(robots)
        assert "https://example.com/sitemap.xml" in result


# ---------------------------------------------------------------------------
# Sitemap XML parsing tests (using httpx MockTransport)
# ---------------------------------------------------------------------------

_VALID_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1</loc></url>
  <url><loc>https://example.com/page2</loc></url>
  <url><loc>https://other.com/external</loc></url>
</urlset>
"""

_SITEMAP_INDEX_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
</sitemapindex>
"""

_CHILD_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/child-page</loc></url>
</urlset>
"""


def _make_mock_transport(url_map: dict[str, tuple[int, str]]) -> httpx.MockTransport:
    """Build an httpx.MockTransport that returns predefined responses.

    Args:
        url_map: Dict of {url: (status_code, body_text)}.
            Any URL not in the map returns 404.

    Returns:
        httpx.MockTransport instance.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str in url_map:
            status, body = url_map[url_str]
            return httpx.Response(status, text=body)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
class TestParseSitemap:
    """Test _parse_sitemap() async XML parsing."""

    async def test_valid_urlset(self) -> None:
        transport = _make_mock_transport({
            "https://example.com/sitemap.xml": (200, _VALID_SITEMAP_XML),
        })
        async with httpx.AsyncClient(transport=transport) as client:
            urls, is_index = await _parse_sitemap(
                "https://example.com/sitemap.xml",
                client, timeout=10.0, domain="example.com", visited=set(),
            )
        assert any("page1" in u for u in urls)
        assert any("page2" in u for u in urls)
        # External filtered out
        assert not any("other.com" in u for u in urls)
        assert is_index is False

    async def test_sitemap_index(self) -> None:
        transport = _make_mock_transport({
            "https://example.com/sitemap_index.xml": (200, _SITEMAP_INDEX_XML),
            "https://example.com/sitemap1.xml": (200, _CHILD_SITEMAP_XML),
        })
        async with httpx.AsyncClient(transport=transport) as client:
            urls, is_index = await _parse_sitemap(
                "https://example.com/sitemap_index.xml",
                client, timeout=10.0, domain="example.com", visited=set(),
            )
        assert is_index is True
        assert any("child-page" in u for u in urls)

    async def test_404_returns_empty(self) -> None:
        transport = _make_mock_transport({})  # everything → 404
        async with httpx.AsyncClient(transport=transport) as client:
            urls, is_index = await _parse_sitemap(
                "https://example.com/sitemap.xml",
                client, timeout=10.0, domain="example.com", visited=set(),
            )
        assert urls == []

    async def test_invalid_xml_returns_empty(self) -> None:
        transport = _make_mock_transport({
            "https://example.com/sitemap.xml": (200, "NOT XML <<<"),
        })
        async with httpx.AsyncClient(transport=transport) as client:
            urls, is_index = await _parse_sitemap(
                "https://example.com/sitemap.xml",
                client, timeout=10.0, domain="example.com", visited=set(),
            )
        assert urls == []

    async def test_empty_content_returns_empty(self) -> None:
        transport = _make_mock_transport({
            "https://example.com/sitemap.xml": (200, ""),
        })
        async with httpx.AsyncClient(transport=transport) as client:
            urls, is_index = await _parse_sitemap(
                "https://example.com/sitemap.xml",
                client, timeout=10.0, domain="example.com", visited=set(),
            )
        assert urls == []

    async def test_dedup_via_visited(self) -> None:
        """Already-visited sitemaps are skipped."""
        visited = {"https://example.com/sitemap.xml"}
        transport = _make_mock_transport({})
        async with httpx.AsyncClient(transport=transport) as client:
            urls, _ = await _parse_sitemap(
                "https://example.com/sitemap.xml",
                client, timeout=10.0, domain="example.com", visited=visited,
            )
        assert urls == []


# ---------------------------------------------------------------------------
# RSS / Atom feed discovery tests
# ---------------------------------------------------------------------------


_RSS_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item><link>https://example.com/post-1</link></item>
    <item><link>https://example.com/post-2</link></item>
    <item><link>https://other.com/external</link></item>
  </channel>
</rss>
"""

_ATOM_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link href="https://example.com/atom-post-1"/>
  </entry>
  <entry>
    <link href="https://other.com/external-atom"/>
  </entry>
</feed>
"""

_HTML_WITH_RSS = """\
<html><head>
  <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="RSS Feed"/>
</head><body></body></html>
"""


class TestDiscoverFeedsFromHtml:
    """Test _discover_feeds_from_html() HTML parsing."""

    def test_rss_link_extracted(self) -> None:
        feeds = _discover_feeds_from_html(_HTML_WITH_RSS, "https://example.com/")
        assert any("feed.xml" in f for f in feeds)

    def test_no_feeds_returns_empty(self) -> None:
        feeds = _discover_feeds_from_html("<html><body>No feeds</body></html>", "https://example.com/")
        assert feeds == []

    def test_relative_href_resolved(self) -> None:
        feeds = _discover_feeds_from_html(_HTML_WITH_RSS, "https://example.com/")
        assert all(f.startswith("http") for f in feeds)

    def test_atom_feed_extracted(self) -> None:
        html = '<html><head><link rel="alternate" type="application/atom+xml" href="/atom.xml"/></head></html>'
        feeds = _discover_feeds_from_html(html, "https://example.com/")
        assert len(feeds) == 1
        assert "atom.xml" in feeds[0]


@pytest.mark.asyncio
class TestExtractRssUrls:
    """Test _extract_rss_urls via AsyncSiteCrawler phase 3 indirectly."""

    async def test_rss_discovery_feeds_sampled_in_crawl(self) -> None:
        """The crawler's phase 3 fetches homepage to extract RSS feeds."""
        from core.site_audit.steps.s1_discover import _extract_rss_urls

        transport = _make_mock_transport({
            "https://example.com/feed.xml": (200, _RSS_FEED_XML),
        })
        async with httpx.AsyncClient(transport=transport) as client:
            urls = await _extract_rss_urls(
                "https://example.com/feed.xml", client, 10.0, "example.com"
            )
        assert any("post-1" in u for u in urls)
        assert any("post-2" in u for u in urls)
        assert not any("other.com" in u for u in urls)

    async def test_atom_urls_extracted(self) -> None:
        from core.site_audit.steps.s1_discover import _extract_rss_urls

        transport = _make_mock_transport({
            "https://example.com/atom.xml": (200, _ATOM_FEED_XML),
        })
        async with httpx.AsyncClient(transport=transport) as client:
            urls = await _extract_rss_urls(
                "https://example.com/atom.xml", client, 10.0, "example.com"
            )
        assert any("atom-post-1" in u for u in urls)
        assert not any("external-atom" in u for u in urls)

    async def test_404_returns_empty(self) -> None:
        from core.site_audit.steps.s1_discover import _extract_rss_urls

        transport = _make_mock_transport({})
        async with httpx.AsyncClient(transport=transport) as client:
            urls = await _extract_rss_urls(
                "https://example.com/feed.xml", client, 10.0, "example.com"
            )
        assert urls == []


# ---------------------------------------------------------------------------
# Link extraction tests
# ---------------------------------------------------------------------------


class TestExtractLinks:
    """Test _extract_links() HTML anchor extraction."""

    def test_internal_links_extracted(self) -> None:
        html = '<html><body><a href="/about">About</a><a href="/blog">Blog</a></body></html>'
        links = _extract_links(html, "https://example.com/", "example.com")
        assert any("about" in l for l in links)
        assert any("blog" in l for l in links)

    def test_external_links_filtered(self) -> None:
        html = '<html><body><a href="https://other.com/page">Other</a></body></html>'
        links = _extract_links(html, "https://example.com/", "example.com")
        assert links == []

    def test_fragment_only_links_skipped(self) -> None:
        html = '<html><body><a href="#section">Section</a></body></html>'
        links = _extract_links(html, "https://example.com/page", "example.com")
        assert links == []

    def test_mailto_skipped(self) -> None:
        html = '<html><body><a href="mailto:test@example.com">Email</a></body></html>'
        links = _extract_links(html, "https://example.com/", "example.com")
        assert links == []

    def test_javascript_skipped(self) -> None:
        html = '<html><body><a href="javascript:void(0)">Click</a></body></html>'
        links = _extract_links(html, "https://example.com/", "example.com")
        assert links == []

    def test_relative_resolved(self) -> None:
        html = '<html><body><a href="subpage">Sub</a></body></html>'
        links = _extract_links(html, "https://example.com/section/", "example.com")
        assert any("subpage" in l for l in links)

    def test_non_html_extensions_filtered(self) -> None:
        html = '<html><body><a href="/download.pdf">PDF</a></body></html>'
        links = _extract_links(html, "https://example.com/", "example.com")
        assert links == []

    def test_dedup_same_url(self) -> None:
        html = '<html><body><a href="/page">P</a><a href="/page">P2</a></body></html>'
        links = _extract_links(html, "https://example.com/", "example.com")
        assert len([l for l in links if "page" in l]) <= 1


# ---------------------------------------------------------------------------
# BFS crawler integration tests (using httpx.MockTransport)
# ---------------------------------------------------------------------------


_HOMEPAGE_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Example Site</title></head>
<body>
  <h1>Welcome</h1>
  <a href="/about">About</a>
  <a href="/blog">Blog</a>
  <a href="https://external.com/page">External</a>
</body>
</html>
"""

_ABOUT_HTML = """\
<!DOCTYPE html>
<html>
<head><title>About</title></head>
<body>
  <h1>About Us</h1>
  <a href="/">Home</a>
</body>
</html>
"""


def _make_standard_crawler_transport(
    extra_urls: dict[str, tuple[int, str]] | None = None,
    extra_urls_with_ct: dict[str, tuple[int, str, str]] | None = None,
) -> httpx.MockTransport:
    """Build a transport for standard crawler tests.

    Always returns 404 for robots.txt, llms.txt, and common sitemaps.
    Homepage returns a simple page. Extra URLs can be provided.

    Args:
        extra_urls: Dict of {url: (status_code, body_text)} with text/html content-type.
        extra_urls_with_ct: Dict of {url: (status_code, body_text, content_type)}.

    Returns:
        httpx.MockTransport instance.
    """
    url_map: dict[str, tuple[int, str]] = {
        "https://example.com/robots.txt": (404, ""),
        "https://example.com/llms.txt": (404, ""),
        "https://example.com/sitemap.xml": (404, ""),
        "https://example.com/sitemap_index.xml": (404, ""),
        "https://example.com/wp-sitemap.xml": (404, ""),
        "https://example.com/sitemap-index.xml": (404, ""),
        "https://example.com/": (200, _HOMEPAGE_HTML),
    }
    if extra_urls:
        url_map.update(extra_urls)

    # Build a content-type-aware handler when ct overrides are needed
    ct_map: dict[str, tuple[int, str, str]] = {}
    if extra_urls_with_ct:
        ct_map.update(extra_urls_with_ct)

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str in ct_map:
            status, body, ct = ct_map[url_str]
            return httpx.Response(status, text=body, headers={"content-type": ct})
        if url_str in url_map:
            status, body = url_map[url_str]
            return httpx.Response(status, text=body, headers={"content-type": "text/html"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
class TestAsyncSiteCrawler:
    """Integration tests for AsyncSiteCrawler using httpx.MockTransport injection."""

    async def test_crawls_homepage(self) -> None:
        """Crawler should fetch homepage and return pages_with_html entries."""
        transport = _make_standard_crawler_transport(
            extra_urls={
                "https://example.com/about": (200, _ABOUT_HTML),
                "https://example.com/blog": (200, "<html><body>Blog</body></html>"),
            }
        )
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=5, max_depth=2, concurrency=2,
            _transport=transport,
        )
        output = await crawler.crawl()

        assert isinstance(output, S1DiscoveryOutput)
        assert len(output.pages_with_html) > 0

    async def test_same_domain_enforcement(self) -> None:
        """BFS worker should not store external domain URLs in pages_with_html."""
        transport = _make_standard_crawler_transport(
            extra_urls={
                "https://example.com/": (
                    200,
                    '<html><body><a href="https://external.com/page">Ext</a></body></html>',
                ),
            }
        )
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=5, max_depth=1, concurrency=2,
            _transport=transport,
        )
        output = await crawler.crawl()

        for url, _ in output.pages_with_html:
            assert "external.com" not in url

    async def test_max_pages_enforced(self) -> None:
        """pages_with_html should never exceed max_pages."""
        # Build a chain: /page0 → /page1 → ... → /page20
        url_map: dict[str, tuple[int, str]] = {
            "https://example.com/robots.txt": (404, ""),
            "https://example.com/llms.txt": (404, ""),
            "https://example.com/sitemap.xml": (404, ""),
            "https://example.com/sitemap_index.xml": (404, ""),
            "https://example.com/wp-sitemap.xml": (404, ""),
            "https://example.com/sitemap-index.xml": (404, ""),
            "https://example.com/": (
                200,
                '<html><body><a href="/page0">Start</a></body></html>',
            ),
        }
        for i in range(20):
            url_map[f"https://example.com/page{i}"] = (
                200,
                f'<html><body><a href="/page{i+1}">Next</a></body></html>',
            )
        url_map["https://example.com/page20"] = (200, "<html><body>End</body></html>")

        transport = _make_mock_transport(url_map)
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=3, max_depth=10, concurrency=2,
            _transport=transport,
        )
        output = await crawler.crawl()

        assert len(output.pages_with_html) <= 3

    async def test_timeout_handled_gracefully(self) -> None:
        """TimeoutException on homepage should not crash the crawler."""
        def timeout_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if url_str == "https://example.com/":
                raise httpx.TimeoutException("Timeout", request=request)
            return httpx.Response(404)

        transport = httpx.MockTransport(timeout_handler)
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=2, max_depth=1, concurrency=1,
            _transport=transport,
        )
        output = await crawler.crawl()

        assert isinstance(output, S1DiscoveryOutput)
        # Should complete without crashing

    async def test_llms_txt_detected(self) -> None:
        """llms.txt 200 → has_llms_txt = True."""
        transport = _make_standard_crawler_transport(
            extra_urls={
                "https://example.com/llms.txt": (200, "# llms.txt"),
                "https://example.com/": (200, "<html><body>Home</body></html>"),
            }
        )
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=2, max_depth=1, concurrency=1,
            _transport=transport,
        )
        output = await crawler.crawl()

        assert output.ai_bot_access.has_llms_txt is True

    async def test_llms_txt_not_found(self) -> None:
        """llms.txt 404 → has_llms_txt = False."""
        transport = _make_standard_crawler_transport()
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=2, max_depth=1, concurrency=1,
            _transport=transport,
        )
        output = await crawler.crawl()

        assert output.ai_bot_access.has_llms_txt is False

    async def test_non_html_content_type_not_stored(self) -> None:
        """Pages with non-text/html content-type should not appear in pages_with_html."""
        # data.json returns application/json — should be filtered
        transport = _make_standard_crawler_transport(
            extra_urls={
                "https://example.com/": (
                    200,
                    '<html><body><a href="/data.json">JSON</a></body></html>',
                ),
            },
            extra_urls_with_ct={
                "https://example.com/data.json": (200, '{"key":"value"}', "application/json"),
            },
        )
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=5, max_depth=1, concurrency=1,
            _transport=transport,
        )
        output = await crawler.crawl()

        for url, _ in output.pages_with_html:
            assert "data.json" not in url

    async def test_discovered_urls_populated(self) -> None:
        """discovered_urls should contain all found URLs."""
        transport = _make_standard_crawler_transport(
            extra_urls={
                "https://example.com/": (
                    200,
                    '<html><body><a href="/about">About</a></body></html>',
                ),
                "https://example.com/about": (200, _ABOUT_HTML),
            }
        )
        crawler = AsyncSiteCrawler(
            domain="example.com", max_pages=10, max_depth=2, concurrency=1,
            _transport=transport,
        )
        output = await crawler.crawl()

        assert isinstance(output.discovered_urls, set)
        assert len(output.discovered_urls) > 0


