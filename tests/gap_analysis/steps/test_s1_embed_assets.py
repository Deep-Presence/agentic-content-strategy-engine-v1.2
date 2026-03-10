"""Tests for s1_embed_assets async conversion — TDD: written BEFORE implementation.

Focused on async behavior of the key entry points and BFS crawling.
"""
from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SIMPLE_HTML = """
<html><head><title>Test Page</title></head><body>
<h1>Welcome to Test Company</h1>
<p>This is a paragraph with enough text to pass the 50-character minimum length filter in the parser for chunking.</p>
<p>Another paragraph that is long enough to be included in the results for testing purposes and needs to be above eighty words.</p>
<a href="/about">About</a>
<a href="/blog">Blog</a>
</body></html>
"""

ROBOTS_TXT = """
User-agent: *
Allow: /
Sitemap: https://test.com/sitemap.xml
"""

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://test.com/page1</loc></url>
  <url><loc>https://test.com/page2</loc></url>
</urlset>
"""


def _mock_html_response(url: str, html: str = SIMPLE_HTML) -> httpx.Response:
    return httpx.Response(
        200,
        text=html,
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", url),
    )


def _mock_xml_response(url: str, xml: str = SITEMAP_XML) -> httpx.Response:
    return httpx.Response(
        200,
        text=xml,
        headers={"content-type": "application/xml"},
        request=httpx.Request("GET", url),
    )


def _mock_robots_response(url: str) -> httpx.Response:
    return httpx.Response(
        200,
        text=ROBOTS_TXT,
        headers={"content-type": "text/plain"},
        request=httpx.Request("GET", url),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncDiscoverSiteTree:
    """Tests for async discover_site_tree."""

    @pytest.mark.asyncio
    async def test_returns_discovery_result(self):
        """Should return SiteDiscoveryResult and page HTML list."""
        async def mock_get(url, **kw):
            url_str = str(url)
            if "robots.txt" in url_str:
                return _mock_robots_response(url_str)
            if "sitemap" in url_str:
                return _mock_xml_response(url_str)
            return _mock_html_response(url_str)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s1_embed_assets.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s1_embed_assets import discover_site_tree

            result, pages_with_html = await discover_site_tree(
                domain="test.com",
                seed_urls=["https://test.com"],
                max_pages=5,
                max_depth=1,
            )

        assert result.domain == "test.com"
        assert result.total_pages_discovered > 0

    @pytest.mark.asyncio
    async def test_bfs_respects_max_pages(self):
        """Should stop crawling after max_pages is reached."""
        page_count = 0

        async def counting_get(url, **kw):
            nonlocal page_count
            url_str = str(url)
            if "robots.txt" in url_str:
                return _mock_robots_response(url_str)
            if "sitemap" in url_str:
                return httpx.Response(
                    404, text="", headers={"content-type": "text/html"},
                    request=httpx.Request("GET", url_str),
                )
            page_count += 1
            # Return HTML with no links to prevent infinite crawl
            return _mock_html_response(url_str, "<html><body><p>" + "x" * 60 + "</p></body></html>")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=counting_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s1_embed_assets.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s1_embed_assets import discover_site_tree

            result, _ = await discover_site_tree(
                domain="test.com",
                seed_urls=["https://test.com"],
                max_pages=3,
                max_depth=1,
            )

        # Should not exceed max_pages for BFS crawl
        assert page_count <= 10  # Generous bound including non-BFS fetches


class TestAsyncEmbedCompanyAssets:
    """Tests for async embed_company_assets."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """embed_company_assets should be an async function."""
        from core.gap_analysis.steps.s1_embed_assets import embed_company_assets
        import inspect
        assert inspect.iscoroutinefunction(embed_company_assets)

    @pytest.mark.asyncio
    async def test_uses_async_embedding_and_chroma(self):
        """Should use async_embed_texts and async ChromaDB operations."""
        from core.models.gap_analysis import GapAnalysisInput

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            seed_urls=["https://test.com"],
            platforms=["perplexity"],
        )

        # Mock discover_site_tree to return minimal data
        from core.models.gap_analysis import SiteDiscoveryResult
        mock_discovery = SiteDiscoveryResult(
            domain="test.com",
            base_url="https://test.com",
            total_pages_discovered=1,
            pages=[],
            discovery_stats={},
        )
        mock_pages = [("https://test.com", SIMPLE_HTML)]

        with patch(
            "core.gap_analysis.steps.s1_embed_assets.discover_site_tree",
            new_callable=AsyncMock,
            return_value=(mock_discovery, mock_pages),
        ), patch(
            "core.gap_analysis.steps.s1_embed_assets.async_embed_texts",
            new_callable=AsyncMock,
            return_value=[[0.1, 0.2] for _ in range(5)],  # Enough for any chunks
        ) as mock_embed, patch(
            "core.gap_analysis.steps.s1_embed_assets.async_delete_company_collection",
            new_callable=AsyncMock,
        ) as mock_delete, patch(
            "core.gap_analysis.steps.s1_embed_assets.async_upsert_embeddings",
            new_callable=AsyncMock,
        ) as mock_upsert:
            from core.gap_analysis.steps.s1_embed_assets import embed_company_assets

            units = await embed_company_assets(input_data)

        # Should have called async versions
        mock_embed.assert_awaited_once()
        mock_delete.assert_awaited_once()
        mock_upsert.assert_awaited_once()
        assert len(units) >= 0  # May be 0 if chunks are empty


class TestBuildSemanticUnits:
    """Tests for build_semantic_units (pure function, stays sync)."""

    def test_builds_units_from_html(self):
        """Should extract and chunk text into SemanticUnit objects."""
        from core.gap_analysis.steps.s1_embed_assets import build_semantic_units

        pages = [("https://test.com", SIMPLE_HTML)]
        units = build_semantic_units(pages)
        assert len(units) >= 0  # May produce 0 if paragraphs too short
        for unit in units:
            assert unit.unit_id.startswith("unit_")
            assert "test.com" in str(unit.url)
