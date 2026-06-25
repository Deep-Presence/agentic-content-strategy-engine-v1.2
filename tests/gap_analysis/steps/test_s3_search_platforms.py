"""Tests for s3_search_platforms — per-engine concurrency pools.

Verifies two-level throttling, engine isolation, connection reuse,
deterministic ordering, error isolation, retry logic, and circuit breaker.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.model_config.schemas import ResolvedModelConfig
from core.models.gap_analysis import GeneratedQuery, PlatformResult


def _make_queries(n: int = 5) -> list[GeneratedQuery]:
    return [
        GeneratedQuery(
            query_id=f"q_{i}",
            cluster_id="C1",
            cluster_name="Test",
            query_text=f"test query {i}",
        )
        for i in range(1, n + 1)
    ]


def _make_mock_engine(name: str, delay: float = 0.0):
    """Create a mock engine that returns results after an optional delay."""
    engine = MagicMock()
    engine.engine_name = name
    engine.model = f"{name}-model"

    async def _search(query_text, query_id=None, *, client=None):
        if delay > 0:
            await asyncio.sleep(delay)
        return PlatformResult(
            engine=name,
            model=f"{name}-model",
            query_id=query_id or "",
            query_text=query_text,
            response_text=f"Response from {name}",
            citations=[],
        )

    engine.search = AsyncMock(side_effect=_search)
    return engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPerEngineConcurrency:
    """Verify per-engine + global semaphore isolation."""

    @pytest.mark.asyncio
    async def test_per_engine_semaphores_isolation(self):
        """Each engine should respect its own concurrency limit."""
        queries = _make_queries(20)
        max_concurrent_per_engine: dict[str, int] = {}
        current_per_engine: dict[str, int] = {"fast": 0, "slow": 0}
        lock = asyncio.Lock()

        async def _tracking_search(name, delay):
            async def _search(query_text, query_id=None, *, client=None):
                async with lock:
                    current_per_engine[name] += 1
                    if name not in max_concurrent_per_engine:
                        max_concurrent_per_engine[name] = 0
                    max_concurrent_per_engine[name] = max(
                        max_concurrent_per_engine[name], current_per_engine[name]
                    )
                await asyncio.sleep(delay)
                async with lock:
                    current_per_engine[name] -= 1
                return PlatformResult(
                    engine=name, query_id=query_id or "", citations=[]
                )
            return _search

        fast_engine = MagicMock()
        fast_engine.engine_name = "fast"
        fast_engine.search = AsyncMock(side_effect=await _tracking_search("fast", 0.01))

        slow_engine = MagicMock()
        slow_engine.engine_name = "slow"
        slow_engine.search = AsyncMock(side_effect=await _tracking_search("slow", 0.02))

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[fast_engine, slow_engine],
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms._engine_concurrency_map",
            return_value={"fast": 5, "slow": 3},
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test"
            mock_settings.perplexity_api_key = "test"

            from core.gap_analysis.steps.s3_search_platforms import (
                _run_engine_batch,
            )

            global_sem = asyncio.Semaphore(30)
            await asyncio.gather(
                _run_engine_batch(fast_engine, queries, 5, global_sem),
                _run_engine_batch(slow_engine, queries, 3, global_sem),
            )

        assert max_concurrent_per_engine["fast"] <= 5
        assert max_concurrent_per_engine["slow"] <= 3

    @pytest.mark.asyncio
    async def test_slow_engine_does_not_block_fast_engine(self):
        """Fast engine should finish well before slow engine."""
        queries = _make_queries(5)
        fast_engine = _make_mock_engine("openai", delay=0.01)
        slow_engine = _make_mock_engine("claude", delay=0.5)

        timings: dict[str, float] = {}

        async def _timed_batch(engine, queries, limit, global_sem, label):
            start = time.monotonic()
            from core.gap_analysis.steps.s3_search_platforms import _run_engine_batch
            result = await _run_engine_batch(engine, queries, limit, global_sem)
            timings[label] = time.monotonic() - start
            return result

        with patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test"
            mock_settings.perplexity_api_key = "test"

            global_sem = asyncio.Semaphore(30)
            await asyncio.gather(
                _timed_batch(fast_engine, queries, 10, global_sem, "fast"),
                _timed_batch(slow_engine, queries, 5, global_sem, "slow"),
            )

        # Fast engine should be significantly faster than slow
        assert timings["fast"] < timings["slow"] * 0.5

    @pytest.mark.asyncio
    async def test_engine_error_isolation(self):
        """One engine failing should not affect other engines."""
        queries = _make_queries(3)

        good_engine = _make_mock_engine("openai")
        bad_engine = MagicMock()
        bad_engine.engine_name = "broken"
        bad_engine.model = "broken-model"

        async def _failing_search(query_text, query_id=None, *, client=None):
            raise RuntimeError("API down")

        bad_engine.search = AsyncMock(side_effect=_failing_search)

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[good_engine, bad_engine],
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms._engine_concurrency_map",
            return_value={"openai": 5, "broken": 5},
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test"
            mock_settings.perplexity_api_key = "test"

            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms(queries, ["openai", "broken"])

        good_results = [r for r in results if r.engine == "openai"]
        bad_results = [r for r in results if r.engine == "broken"]
        assert len(good_results) == 3
        assert all("ERROR" not in (r.response_text or "") for r in good_results)
        assert len(bad_results) == 3
        assert all("ERROR" in (r.response_text or "") for r in bad_results)

    @pytest.mark.asyncio
    async def test_byok_mode_filters_native_engines(self):
        """Workspace-backed S3 runs only select BYOK-safe Perplexity search."""
        from core.gap_analysis.steps.s3_search_platforms import search_platforms

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[],
        ) as mock_select:
            results = await search_platforms(
                _make_queries(1),
                ["perplexity", "openai", "claude", "gemini"],
                workspace_id="ws-123",
                workspace_slug="ramp",
                company_slug="ramp",
            )

        assert results == []
        mock_select.assert_called_once_with(["perplexity"])

    @pytest.mark.asyncio
    async def test_perplexity_batch_uses_workspace_openrouter_client(self):
        """BYOK Perplexity search resolves agent config and never uses the singleton client."""
        from core.gap_analysis.engines.perplexity import PerplexityEngine
        from core.gap_analysis.steps.s3_search_platforms import _run_engine_batch

        resolved = ResolvedModelConfig(
            workspace_id="ws-123",
            workspace_slug="ramp",
            agent_key="gap.search.perplexity",
            model="perplexity/sonar-pro",
            base_url="https://openrouter.example/api/v1",
            api_key="sk-or-workspace",
            credential_id="cred-1",
            model_config_id="cfg-1",
        )

        msg = MagicMock()
        msg.content = "workspace search result"
        choice = MagicMock(message=msg)
        completion = MagicMock(
            choices=[choice],
            citations=["https://example.com"],
            model_extra={},
            usage=MagicMock(prompt_tokens=12, completion_tokens=8),
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        mock_client.close = MagicMock(return_value=None)

        engine = PerplexityEngine(model="perplexity/legacy")

        with (
            patch(
                "core.model_config.runtime.resolve_model_config_for_agent",
                new_callable=AsyncMock,
                return_value=resolved,
            ) as mock_resolve,
            patch(
                "core.shared_tools.openrouter_client.build_async_client_for_key",
                return_value=mock_client,
            ) as mock_build,
            patch("core.shared_tools.openrouter_client.get_async_client") as mock_singleton,
            patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track,
            patch("core.gap_analysis.steps.s3_search_platforms.settings") as mock_settings,
        ):
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            results = await _run_engine_batch(
                engine,
                _make_queries(1),
                1,
                asyncio.Semaphore(1),
                workspace_id="ws-123",
                workspace_slug="ramp",
                company_slug="ramp",
            )

        mock_singleton.assert_not_called()
        mock_resolve.assert_awaited_once()
        assert mock_resolve.await_args.kwargs["agent_key"] == "gap.search.perplexity"
        mock_build.assert_called_once_with(
            "sk-or-workspace",
            base_url="https://openrouter.example/api/v1",
            timeout_s=None,
        )
        assert engine.model == "perplexity/sonar-pro"
        assert results[0].engine == "perplexity"
        assert results[0].response_text == "workspace search result"
        kw = mock_track.call_args.kwargs
        assert kw["workspace_id"] == "ws-123"
        assert kw["agent_key"] == "gap.search.perplexity"
        assert kw["credential_id"] == "cred-1"
        assert kw["model_config_id"] == "cfg-1"


class TestBatchLevelErrorIsolation:
    """Verify batch-level failures (client init, import errors) don't crash other engines."""

    @pytest.mark.asyncio
    async def test_engine_batch_init_failure_isolated(self):
        """If _run_engine_batch raises for one engine, other engine results survive."""
        queries = _make_queries(3)
        good_engine = _make_mock_engine("openai")
        bad_engine = _make_mock_engine("broken")

        async def _exploding_batch(engine, queries, limit, global_sem):
            raise RuntimeError("Import error: no module named 'perplexity'")

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[good_engine, bad_engine],
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms._engine_concurrency_map",
            return_value={"openai": 5, "broken": 5},
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test"
            mock_settings.perplexity_api_key = "test"

            from core.gap_analysis.steps.s3_search_platforms import (
                _run_engine_batch,
                search_platforms,
            )

            original_run = _run_engine_batch

            async def _selective_batch(engine, queries, limit, global_sem, **kwargs):
                if engine.engine_name == "broken":
                    raise RuntimeError("Import error: no module named 'perplexity'")
                return await original_run(engine, queries, limit, global_sem)

            with patch(
                "core.gap_analysis.steps.s3_search_platforms._run_engine_batch",
                side_effect=_selective_batch,
            ):
                results = await search_platforms(queries, ["openai", "broken"])

        # Good engine results survive; broken engine produces nothing (not ERROR stubs)
        assert len(results) == 3
        assert all(r.engine == "openai" for r in results)

    @pytest.mark.asyncio
    async def test_sdk_clients_entered_into_exit_stack(self):
        """AsyncOpenAI/AsyncPerplexity should be entered into AsyncExitStack for cleanup."""
        queries = _make_queries(1)

        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        mock_sdk_client.__aexit__ = AsyncMock(return_value=False)

        from core.gap_analysis.engines.openai_engine import OpenAIEngine

        engine = OpenAIEngine(model="openai-test")
        engine.search = AsyncMock(
            return_value=PlatformResult(
                engine="openai",
                model="openai-test",
                query_id="q_1",
                query_text="test query 1",
                response_text="ok",
                citations=[],
            )
        )

        with patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test-key"

            # Patch the local import: `from openai import AsyncOpenAI`
            mock_openai_module = MagicMock()
            mock_openai_module.AsyncOpenAI = MagicMock(return_value=mock_sdk_client)

            with patch.dict("sys.modules", {"openai": mock_openai_module}):
                from core.gap_analysis.steps.s3_search_platforms import _run_engine_batch

                engine.engine_name = "openai"
                global_sem = asyncio.Semaphore(30)
                await _run_engine_batch(engine, queries, 5, global_sem)

            # Verify __aenter__ and __aexit__ were called (entered into stack)
            mock_sdk_client.__aenter__.assert_awaited_once()
            mock_sdk_client.__aexit__.assert_awaited_once()


class TestDeterministicOrdering:
    """Verify results are sorted by (query_id, engine) for stable dedup."""

    @pytest.mark.asyncio
    async def test_results_sorted_by_query_and_engine(self):
        """Output should be sorted by (query_id, engine) regardless of completion order."""
        queries = _make_queries(3)

        # Create engines that complete in reverse order
        engine_a = _make_mock_engine("aaa", delay=0.05)
        engine_b = _make_mock_engine("bbb", delay=0.01)

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=[engine_a, engine_b],
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms._engine_concurrency_map",
            return_value={"aaa": 10, "bbb": 10},
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test"
            mock_settings.perplexity_api_key = "test"

            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms(queries, ["aaa", "bbb"])

        # Verify sorted by (query_id, engine)
        keys = [(r.query_id, r.engine) for r in results]
        assert keys == sorted(keys)


class TestResultCompleteness:
    """Verify all engine results are present in flattened output."""

    @pytest.mark.asyncio
    async def test_all_results_preserved(self):
        """Every (query, engine) combination should produce a result."""
        queries = _make_queries(4)
        engines = [_make_mock_engine("eng1"), _make_mock_engine("eng2")]

        with patch(
            "core.gap_analysis.steps.s3_search_platforms._select_engines",
            return_value=engines,
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms._engine_concurrency_map",
            return_value={"eng1": 10, "eng2": 10},
        ), patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 100
            mock_settings.openai_api_key = "test"
            mock_settings.perplexity_api_key = "test"

            from core.gap_analysis.steps.s3_search_platforms import search_platforms
            results = await search_platforms(queries, ["eng1", "eng2"])

        assert len(results) == 8  # 4 queries × 2 engines

    @pytest.mark.asyncio
    async def test_empty_queries_returns_empty(self):
        from core.gap_analysis.steps.s3_search_platforms import search_platforms
        results = await search_platforms([], ["openai"])
        assert results == []

    @pytest.mark.asyncio
    async def test_empty_platforms_returns_empty(self):
        from core.gap_analysis.steps.s3_search_platforms import search_platforms
        results = await search_platforms(_make_queries(3), [])
        assert results == []


# ---------------------------------------------------------------------------
# _is_retryable tests
# ---------------------------------------------------------------------------


def _make_httpx_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Create a synthetic httpx.HTTPStatusError with a given status code."""
    response = httpx.Response(status_code=status_code, request=httpx.Request("GET", "http://test"))
    return httpx.HTTPStatusError(
        message=f"HTTP {status_code}", request=response.request, response=response,
    )


class TestIsRetryable:
    """Tests for the _is_retryable exception classifier."""

    def test_httpx_429_is_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(_make_httpx_status_error(429)) is True

    def test_httpx_500_is_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(_make_httpx_status_error(500)) is True

    def test_httpx_503_is_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(_make_httpx_status_error(503)) is True

    def test_httpx_400_not_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(_make_httpx_status_error(400)) is False

    def test_httpx_401_not_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(_make_httpx_status_error(401)) is False

    def test_timeout_exception_is_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(httpx.TimeoutException("timeout")) is True

    def test_asyncio_timeout_is_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(asyncio.TimeoutError()) is True

    def test_connect_error_is_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(httpx.ConnectError("connection refused")) is True

    def test_runtime_error_not_retryable(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable
        assert _is_retryable(RuntimeError("missing API key")) is False

    def test_sdk_rate_limit_error_by_class_name(self):
        """OpenAI/Perplexity SDK rate limit errors detected by class name."""
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable

        class RateLimitError(Exception):
            pass

        assert _is_retryable(RateLimitError()) is True

    def test_sdk_api_timeout_error_by_class_name(self):
        from core.gap_analysis.steps.s3_search_platforms import _is_retryable

        class APITimeoutError(Exception):
            pass

        assert _is_retryable(APITimeoutError()) is True


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for retry with exponential backoff in _run_one."""

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """Successful call on first attempt — no retry."""
        engine = _make_mock_engine("openai")
        query = _make_queries(1)[0]

        from core.gap_analysis.steps.s3_search_platforms import _run_one
        result = await _run_one(engine, query, max_retries=2)

        assert "ERROR" not in (result.response_text or "")
        assert engine.search.await_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure_then_success(self):
        """First call raises 429, second succeeds — result is success."""
        engine = MagicMock()
        engine.engine_name = "claude"
        engine.model = "claude-model"
        query = _make_queries(1)[0]

        ok_result = PlatformResult(
            engine="claude", query_id=query.query_id,
            response_text="OK", citations=[],
        )
        engine.search = AsyncMock(
            side_effect=[_make_httpx_status_error(429), ok_result],
        )

        with patch("core.gap_analysis.steps.s3_search_platforms.asyncio.sleep", new_callable=AsyncMock):
            from core.gap_analysis.steps.s3_search_platforms import _run_one
            result = await _run_one(engine, query, max_retries=2, retry_base_delay_s=0.01)

        assert result.response_text == "OK"
        assert engine.search.await_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self):
        """400 error — not retryable, only 1 call."""
        engine = MagicMock()
        engine.engine_name = "gemini"
        engine.model = "gemini-model"
        query = _make_queries(1)[0]

        engine.search = AsyncMock(side_effect=_make_httpx_status_error(400))

        from core.gap_analysis.steps.s3_search_platforms import _run_one
        result = await _run_one(engine, query, max_retries=2)

        assert "ERROR" in (result.response_text or "")
        assert engine.search.await_count == 1

    @pytest.mark.asyncio
    async def test_retry_exhaustion_returns_error(self):
        """All attempts fail — error PlatformResult returned."""
        engine = MagicMock()
        engine.engine_name = "openai"
        engine.model = "openai-model"
        query = _make_queries(1)[0]

        engine.search = AsyncMock(side_effect=_make_httpx_status_error(500))

        with patch("core.gap_analysis.steps.s3_search_platforms.asyncio.sleep", new_callable=AsyncMock):
            from core.gap_analysis.steps.s3_search_platforms import _run_one
            result = await _run_one(engine, query, max_retries=2, retry_base_delay_s=0.01)

        assert "ERROR" in (result.response_text or "")
        assert engine.search.await_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Verify increasing delays between retry attempts."""
        engine = MagicMock()
        engine.engine_name = "claude"
        engine.model = "claude-model"
        query = _make_queries(1)[0]

        engine.search = AsyncMock(side_effect=_make_httpx_status_error(429))
        sleep_calls: list[float] = []

        async def _mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("core.gap_analysis.steps.s3_search_platforms.asyncio.sleep", side_effect=_mock_sleep):
            from core.gap_analysis.steps.s3_search_platforms import _run_one
            await _run_one(engine, query, max_retries=2, retry_base_delay_s=2.0)

        assert len(sleep_calls) == 2
        # First delay: base * 2^0 + jitter = ~2.0-3.0
        assert 2.0 <= sleep_calls[0] < 3.5
        # Second delay: base * 2^1 + jitter = ~4.0-5.0
        assert 4.0 <= sleep_calls[1] < 6.0


# ---------------------------------------------------------------------------
# Circuit Breaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for the _CircuitBreaker class."""

    def test_starts_closed(self):
        from core.gap_analysis.steps.s3_search_platforms import _CircuitBreaker
        cb = _CircuitBreaker(threshold=5)
        assert cb.is_open is False

    def test_opens_after_threshold_failures(self):
        from core.gap_analysis.steps.s3_search_platforms import _CircuitBreaker
        cb = _CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True

    def test_success_resets_counter(self):
        from core.gap_analysis.steps.s3_search_platforms import _CircuitBreaker
        cb = _CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False  # reset after success

    def test_trip_count_incremented(self):
        from core.gap_analysis.steps.s3_search_platforms import _CircuitBreaker
        cb = _CircuitBreaker(threshold=2)
        assert cb.tripped_count == 0
        cb.record_failure()
        cb.record_failure()  # trips
        assert cb.tripped_count == 1


class TestCircuitBreakerIntegration:
    """Circuit breaker integration in _run_engine_batch."""

    @pytest.mark.asyncio
    async def test_skips_remaining_after_threshold(self):
        """After threshold consecutive failures, remaining queries are skipped."""
        queries = _make_queries(20)
        engine = MagicMock()
        engine.engine_name = "broken"
        engine.model = "broken-model"

        engine.search = AsyncMock(side_effect=_make_httpx_status_error(500))

        with patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0  # no retries
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 3

            from core.gap_analysis.steps.s3_search_platforms import _run_engine_batch
            global_sem = asyncio.Semaphore(30)
            results = await _run_engine_batch(engine, queries, 1, global_sem)

        # All 20 should have results (some errors, some circuit-breaker skips)
        assert len(results) == 20
        # Engine should NOT have been called 20 times — circuit breaker should have tripped
        # With concurrency=1, at most threshold + a few overshoot calls
        assert engine.search.await_count <= 6  # threshold(3) + small overshoot

    @pytest.mark.asyncio
    async def test_does_not_trip_on_intermittent_failures(self):
        """Intermittent failures (success between failures) don't trip the breaker."""
        queries = _make_queries(10)
        engine = MagicMock()
        engine.engine_name = "flaky"
        engine.model = "flaky-model"

        call_count = 0

        async def _alternating_search(query_text, query_id=None, *, client=None):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise _make_httpx_status_error(500)
            return PlatformResult(
                engine="flaky", query_id=query_id or "",
                response_text="OK", citations=[],
            )

        engine.search = AsyncMock(side_effect=_alternating_search)

        with patch(
            "core.gap_analysis.steps.s3_search_platforms.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_s3_global_concurrency = 30
            mock_settings.gap_analysis_s3_max_retries = 0
            mock_settings.gap_analysis_s3_retry_base_delay_s = 0.01
            mock_settings.gap_analysis_s3_circuit_breaker_threshold = 3

            from core.gap_analysis.steps.s3_search_platforms import _run_engine_batch
            global_sem = asyncio.Semaphore(30)
            # Use concurrency=1 for deterministic alternation
            results = await _run_engine_batch(engine, queries, 1, global_sem)

        # All 10 queries should have been attempted (breaker never trips)
        assert engine.search.await_count == 10
        ok_results = [r for r in results if "ERROR" not in (r.response_text or "")]
        assert len(ok_results) == 5  # half succeed
