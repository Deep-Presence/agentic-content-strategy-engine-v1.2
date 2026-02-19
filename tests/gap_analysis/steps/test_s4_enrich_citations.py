"""Tests for s4_enrich_citations async conversion — TDD: written BEFORE implementation."""
from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.models.gap_analysis import (
    EnrichedCitation,
    PlatformResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SIMPLE_HTML = """
<html><body>
<h1>Main Title</h1>
<h2>Section One</h2>
<p>This is a paragraph with enough text to pass the 50-character minimum length filter in the parser.</p>
<p>Another paragraph that is long enough to be included in the results for testing purposes.</p>
<ul><li>List item one is long enough to pass the filter for minimum text length.</li></ul>
<a href="https://example.com">Link</a>
</body></html>
"""


def _make_platform_result(
    engine: str = "perplexity",
    query_id: str = "q1",
    citations: list | None = None,
) -> PlatformResult:
    """Create a minimal PlatformResult for testing."""
    if citations is None:
        citations = [
            {"url": "https://example.com/page1", "title": "Page 1"},
            {"url": "https://example.com/page2", "title": "Page 2"},
        ]
    return PlatformResult(
        engine=engine,
        model="test-model",
        query_id=query_id,
        query_text="test query",
        response_text="test response",
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Tests: async _fetch_html
# ---------------------------------------------------------------------------
class TestAsyncFetchHtml:
    """Tests for async _fetch_html."""

    @pytest.mark.asyncio
    async def test_returns_html_on_success(self):
        """Should return (html, resolved_url) tuple for successful requests."""
        mock_response = httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        from core.gap_analysis.steps.s4_enrich_citations import _fetch_html

        html, resolved_url = await _fetch_html("https://example.com", client=mock_client)
        assert html is not None
        assert "Main Title" in html
        assert resolved_url == "https://example.com"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self):
        """Should return (None, None) for 4xx error responses."""
        mock_response = httpx.Response(
            404,
            text="Not Found",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        from core.gap_analysis.steps.s4_enrich_citations import _fetch_html

        html, resolved_url = await _fetch_html("https://example.com/missing", client=mock_client)
        assert html is None
        assert resolved_url is None

    @pytest.mark.asyncio
    async def test_returns_none_on_non_html(self):
        """Should return (None, None) for non-HTML content (PDFs, images)."""
        mock_response = httpx.Response(
            200,
            content=b"%PDF-1.4",
            headers={"content-type": "application/pdf"},
            request=httpx.Request("GET", "https://example.com/doc.pdf"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        from core.gap_analysis.steps.s4_enrich_citations import _fetch_html

        html, resolved_url = await _fetch_html("https://example.com/doc.pdf", client=mock_client)
        assert html is None
        assert resolved_url is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        """Should return (None, None) on network errors without crashing."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        from core.gap_analysis.steps.s4_enrich_citations import _fetch_html

        html, resolved_url = await _fetch_html("https://broken.example.com", client=mock_client)
        assert html is None
        assert resolved_url is None


# ---------------------------------------------------------------------------
# Tests: async enrich_citations
# ---------------------------------------------------------------------------
class TestAsyncEnrichCitations:
    """Tests for async enrich_citations."""

    @pytest.mark.asyncio
    async def test_enriches_citations_concurrently(self):
        """Should fetch all unique URLs and return enriched citations."""
        results = [_make_platform_result()]

        mock_response = httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://example.com"),
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

            enriched = await enrich_citations(results)

        assert len(enriched) == 2
        assert all(isinstance(e, EnrichedCitation) for e in enriched)

    @pytest.mark.asyncio
    async def test_deduplicates_urls(self):
        """Should fetch each unique URL only once, even if it appears in multiple results."""
        # Two results citing the same URL
        results = [
            _make_platform_result(
                engine="perplexity",
                citations=[{"url": "https://example.com/same", "title": "Same Page"}],
            ),
            _make_platform_result(
                engine="openai",
                citations=[{"url": "https://example.com/same", "title": "Same Page Again"}],
            ),
        ]

        call_count = 0

        async def counting_get(url, **kw):
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", url),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=counting_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

            enriched = await enrich_citations(results)

        # Only 1 unique URL, should fetch only once
        assert call_count == 1
        assert len(enriched) == 1

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        """One failed URL should not crash enrichment of other URLs."""
        results = [
            _make_platform_result(
                citations=[
                    {"url": "https://good.example.com", "title": "Good"},
                    {"url": "https://bad.example.com", "title": "Bad"},
                ]
            )
        ]

        async def selective_get(url, **kw):
            if "bad" in str(url):
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=selective_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

            enriched = await enrich_citations(results)

        # Only the good URL should produce an enriched citation
        assert len(enriched) == 1
        assert "good" in str(enriched[0].url)

    @pytest.mark.asyncio
    async def test_preserves_output_order(self):
        """Enriched citations should appear in same order as input citations."""
        results = [
            _make_platform_result(
                citations=[
                    {"url": "https://alpha.example.com", "title": "Alpha"},
                    {"url": "https://beta.example.com", "title": "Beta"},
                    {"url": "https://gamma.example.com", "title": "Gamma"},
                ]
            )
        ]

        async def ordered_get(url, **kw):
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ordered_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

            enriched = await enrich_citations(results)

        urls = [str(e.url) for e in enriched]
        assert "alpha" in urls[0]
        assert "beta" in urls[1]
        assert "gamma" in urls[2]


class TestConcurrencyLimit:
    """[Codex] Tests for concurrency limit enforcement."""

    @pytest.mark.asyncio
    async def test_max_concurrent_connections(self):
        """Should never exceed 20 simultaneous connections."""
        # Create 50 unique URLs
        citations = [
            {"url": f"https://site{i}.example.com", "title": f"Site {i}"}
            for i in range(50)
        ]
        results = [_make_platform_result(citations=citations)]

        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracking_get(url, **kw):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.01)  # Simulate network delay
            async with lock:
                current_concurrent -= 1
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=tracking_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

            await enrich_citations(results, concurrency=20)

        assert max_concurrent <= 20, f"Max concurrent was {max_concurrent}, expected <= 20"


class TestFallbackPaths:
    """[Codex] Tests for HTTP error fallback behavior."""

    @pytest.mark.asyncio
    async def test_500_response_skipped(self):
        """500 Server Error should skip the citation, not crash."""
        results = [
            _make_platform_result(
                citations=[{"url": "https://error.example.com", "title": "Error Page"}]
            )
        ]

        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", "https://error.example.com"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

            enriched = await enrich_citations(results)

        assert len(enriched) == 0

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self):
        """Empty input should return empty output without errors."""
        from core.gap_analysis.steps.s4_enrich_citations import enrich_citations

        enriched = await enrich_citations([])
        assert enriched == []
