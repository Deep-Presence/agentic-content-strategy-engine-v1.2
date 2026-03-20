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


class TestThreadOffloadedParsing:
    """Tests for Phase 3: thread-offloaded HTML parsing."""

    @pytest.mark.asyncio
    async def test_parsing_uses_thread_pool(self):
        """_extract_paragraphs should be called via asyncio.to_thread, not inline."""
        results = [_make_platform_result(
            citations=[{"url": "https://example.com/thread-test", "title": "Thread Test"}]
        )]

        mock_response = httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://example.com/thread-test"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ), patch(
            "core.gap_analysis.steps.s4_enrich_citations.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            # Make to_thread return valid parse results
            from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs
            mock_to_thread.return_value = _extract_paragraphs(SIMPLE_HTML)

            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations
            enriched = await enrich_citations(results)

        assert mock_to_thread.called, "asyncio.to_thread was not called for parsing"
        assert len(enriched) == 1

    @pytest.mark.asyncio
    async def test_parse_concurrency_limited(self):
        """Max concurrent parse workers should respect parse_workers setting."""
        citations = [
            {"url": f"https://site{i}.example.com", "title": f"Site {i}"}
            for i in range(30)
        ]
        results = [_make_platform_result(citations=citations)]

        max_concurrent_parse = 0
        current_concurrent_parse = 0
        lock = asyncio.Lock()

        original_extract = None

        def _tracking_extract(html):
            """Synchronous wrapper that tracks concurrency via thread-safe counter."""
            import threading
            nonlocal max_concurrent_parse, current_concurrent_parse
            # Use threading lock since this runs in thread pool
            current_concurrent_parse += 1
            if current_concurrent_parse > max_concurrent_parse:
                max_concurrent_parse = current_concurrent_parse
            import time
            time.sleep(0.02)  # Simulate CPU work
            current_concurrent_parse -= 1
            return original_extract(html)

        async def simple_get(url, **kw):
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=simple_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import (
                _extract_paragraphs,
                enrich_citations,
            )
            original_extract = _extract_paragraphs

            with patch(
                "core.gap_analysis.steps.s4_enrich_citations._extract_paragraphs",
                side_effect=_tracking_extract,
            ):
                await enrich_citations(results, parse_workers=4)

        assert max_concurrent_parse <= 4, (
            f"Max concurrent parse was {max_concurrent_parse}, expected <= 4"
        )

    @pytest.mark.asyncio
    async def test_trafilatura_serialized_across_threads(self):
        """trafilatura.extract must never run in more than 1 thread at a time.

        lxml (used by trafilatura) is not thread-safe when the GIL is released.
        The _TRAFILATURA_LOCK in s4 must serialize all trafilatura.extract() calls.
        """
        import threading
        import time

        citations = [
            {"url": f"https://site{i}.example.com", "title": f"Site {i}"}
            for i in range(12)
        ]
        results = [_make_platform_result(citations=citations)]

        max_concurrent_traf = 0
        current_concurrent_traf = 0
        counter_lock = threading.Lock()

        real_extract = None

        def _tracking_trafilatura(*args, **kwargs):
            """Wraps trafilatura.extract to track max concurrent callers."""
            nonlocal max_concurrent_traf, current_concurrent_traf
            with counter_lock:
                current_concurrent_traf += 1
                if current_concurrent_traf > max_concurrent_traf:
                    max_concurrent_traf = current_concurrent_traf
            time.sleep(0.05)  # Widen the race window
            try:
                return real_extract(*args, **kwargs) if real_extract else None
            finally:
                with counter_lock:
                    current_concurrent_traf -= 1

        async def simple_get(url, **kw):
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=simple_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        import trafilatura
        real_extract = trafilatura.extract

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ), patch(
            "core.gap_analysis.steps.s4_enrich_citations.trafilatura.extract",
            side_effect=_tracking_trafilatura,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations
            enriched = await enrich_citations(results, parse_workers=8)

        # The lock must serialize trafilatura — never more than 1 concurrent caller
        assert max_concurrent_traf <= 1, (
            f"trafilatura ran in {max_concurrent_traf} threads simultaneously — "
            f"_TRAFILATURA_LOCK is missing or broken"
        )
        # All URLs should still be processed
        assert len(enriched) > 0, "No citations were enriched"

    @pytest.mark.asyncio
    async def test_fetch_concurrency_uses_settings(self):
        """Fetch semaphore should use settings value when concurrency param is None."""
        results = [_make_platform_result(
            citations=[{"url": "https://example.com/settings-test", "title": "Test"}]
        )]

        mock_response = httpx.Response(
            200, text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://example.com/settings-test"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ), patch(
            "core.gap_analysis.steps.s4_enrich_citations.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s4_fetch_concurrency = 42
            mock_settings.gap_analysis_s4_parse_workers = 8
            mock_settings.gap_analysis_s4_http_pool_size = 50

            with patch(
                "core.gap_analysis.steps.s4_enrich_citations.asyncio.Semaphore"
            ) as mock_sem_cls:
                mock_sem_cls.return_value = asyncio.Semaphore(42)

                from core.gap_analysis.steps.s4_enrich_citations import enrich_citations
                await enrich_citations(results)

            # First call to Semaphore should be with fetch concurrency value
            calls = mock_sem_cls.call_args_list
            assert any(c.args == (42,) for c in calls), (
                f"Expected Semaphore(42) call, got: {calls}"
            )

    @pytest.mark.asyncio
    async def test_order_preserved_after_threaded_parse(self):
        """Output order must match input order even with thread-pool parsing."""
        results = [
            _make_platform_result(
                citations=[
                    {"url": f"https://site-{i}.example.com", "title": f"Site {i}"}
                    for i in range(5)
                ]
            )
        ]

        async def ordered_get(url, **kw):
            return httpx.Response(
                200, text=SIMPLE_HTML,
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
        for i in range(5):
            assert f"site-{i}" in urls[i], f"Expected site-{i} at index {i}, got {urls[i]}"


class TestParseErrorIsolation:
    """Tests for Fix 5: parse gather error isolation."""

    @pytest.mark.asyncio
    async def test_parse_failure_does_not_crash_other_citations(self):
        """One _extract_paragraphs crash should not prevent other citations from enriching."""
        results = [
            _make_platform_result(
                citations=[
                    {"url": "https://good.example.com", "title": "Good"},
                    {"url": "https://crashy.example.com", "title": "Crashy"},
                ]
            )
        ]

        async def simple_get(url, **kw):
            return httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
                request=httpx.Request("GET", str(url)),
            )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=simple_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        call_count = 0
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs
        original_extract = _extract_paragraphs

        def _crashing_extract(html):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second URL crashes
                raise ValueError("Malformed HTML explosion")
            return original_extract(html)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ), patch(
            "core.gap_analysis.steps.s4_enrich_citations._extract_paragraphs",
            side_effect=_crashing_extract,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations
            enriched = await enrich_citations(results)

        # First URL should still produce a citation; second crashed and was skipped
        assert len(enriched) == 1
        assert "good" in str(enriched[0].url)


class TestFetchGatherIsolation:
    """Tests for Fix 4: fetch gather defense-in-depth."""

    @pytest.mark.asyncio
    async def test_fetch_gather_exception_normalized(self):
        """Exceptions escaping _fetch_html should be normalized to (None, None)."""
        results = [
            _make_platform_result(
                citations=[
                    {"url": "https://ok.example.com", "title": "OK"},
                    {"url": "https://boom.example.com", "title": "Boom"},
                ]
            )
        ]

        call_count = 0

        async def selective_fetch(url, client=None, semaphore=None):
            nonlocal call_count
            call_count += 1
            if "boom" in str(url):
                raise RuntimeError("Semaphore destroyed")
            return (SIMPLE_HTML, str(url))

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_client,
        ), patch(
            "core.gap_analysis.steps.s4_enrich_citations._fetch_html",
            side_effect=selective_fetch,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import enrich_citations
            enriched = await enrich_citations(results)

        # Only the OK URL should produce a result
        assert len(enriched) == 1
        assert "ok" in str(enriched[0].url)


class TestFetchHtmlClientCleanup:
    """Tests for Fix 3: _fetch_html fallback client cleanup."""

    @pytest.mark.asyncio
    async def test_fetch_html_closes_fallback_client(self):
        """When client=None, internally created httpx client should be closed."""
        mock_response = httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_fallback = AsyncMock()
        mock_fallback.get = AsyncMock(return_value=mock_response)
        mock_fallback.aclose = AsyncMock()

        with patch(
            "core.gap_analysis.steps.s4_enrich_citations.httpx.AsyncClient",
            return_value=mock_fallback,
        ):
            from core.gap_analysis.steps.s4_enrich_citations import _fetch_html
            html, resolved = await _fetch_html("https://example.com", client=None)

        assert html is not None
        mock_fallback.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_html_does_not_close_shared_client(self):
        """When a shared client is passed, it should NOT be closed by _fetch_html."""
        mock_response = httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://example.com"),
        )
        shared_client = AsyncMock()
        shared_client.get = AsyncMock(return_value=mock_response)
        shared_client.aclose = AsyncMock()

        from core.gap_analysis.steps.s4_enrich_citations import _fetch_html
        html, resolved = await _fetch_html("https://example.com", client=shared_client)

        assert html is not None
        shared_client.aclose.assert_not_awaited()


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
