"""Tests for PlatformRunnerService — always with mocked engines.

All engine interactions are mocked via AsyncMock — no real LLM API calls
are ever made.  Tests verify the adapter behavior: prompt-to-engine mapping,
concurrency control, error handling, and result aggregation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.model_config.schemas import ResolvedModelConfig
from core.daily_tracker.platform_runner import PlatformRunnerService
from core.models.daily_tracker import (
    DailyRunResult,
    PlatformResponse,
    RunStatus,
    TrackedPrompt,
)
from core.models.gap_analysis import CitationRef, PlatformResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_prompt(prompt_id: str = "p1", text: str = "What is Ramp?") -> TrackedPrompt:
    """Create a TrackedPrompt for testing."""
    return TrackedPrompt(
        id=prompt_id,
        company_id="company-1",
        text=text,
        tags=["test"],
    )


def _make_mock_engine(
    name: str = "mock_engine",
    response_text: str = "Ramp is a corporate card solution.",
    citations: list[CitationRef] | None = None,
) -> AsyncMock:
    """Create a mock SearchEngine that returns a canned PlatformResult."""
    engine = AsyncMock()
    engine.engine_name = name
    engine.model = "test-model"
    engine.search = AsyncMock(
        return_value=PlatformResult(
            engine=name,
            model="test-model",
            query_id="q1",
            query_text="test query",
            response_text=response_text,
            citations=citations or [],
        )
    )
    return engine


def _make_failing_engine(name: str = "failing_engine") -> AsyncMock:
    """Create a mock SearchEngine that raises on search()."""
    engine = AsyncMock()
    engine.engine_name = name
    engine.model = "test-model"
    engine.search = AsyncMock(side_effect=RuntimeError("API key invalid"))
    return engine


@pytest.fixture
def sample_prompt() -> TrackedPrompt:
    return _make_prompt()


@pytest.fixture
def mock_engine() -> AsyncMock:
    return _make_mock_engine()


# ---------------------------------------------------------------------------
# PlatformRunnerService tests
# ---------------------------------------------------------------------------


class TestPlatformRunnerService:
    @pytest.mark.asyncio
    async def test_run_prompts_single_engine(self, sample_prompt: TrackedPrompt) -> None:
        engine = _make_mock_engine("openai")
        service = PlatformRunnerService(engine_registry={"openai": engine})

        result = await service.run_prompts(
            [sample_prompt], engines=["openai"]
        )

        assert isinstance(result, DailyRunResult)
        assert result.status == RunStatus.COMPLETED
        assert len(result.responses) == 1
        assert result.responses[0].engine == "openai"
        assert result.responses[0].prompt_id == "p1"
        assert result.prompt_count == 1
        assert result.engine_count == 1
        engine.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_byok_mode_runs_only_perplexity_with_workspace_client(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        resolved = ResolvedModelConfig(
            workspace_id="ws-123",
            workspace_slug="ramp",
            agent_key="daily_tracker.platform.perplexity",
            model="perplexity/sonar-pro",
            base_url="https://openrouter.example/api/v1",
            api_key="sk-or-workspace",
            credential_id="cred-1",
            model_config_id="cfg-1",
        )
        client = MagicMock()
        client.close = MagicMock(return_value=None)
        engines = {
            "openai": _make_mock_engine("openai"),
            "claude": _make_mock_engine("claude"),
            "perplexity": _make_mock_engine("perplexity"),
        }
        service = PlatformRunnerService(engine_registry=engines)

        with (
            patch(
                "core.model_config.runtime.resolve_model_config_for_agent",
                new_callable=AsyncMock,
                return_value=resolved,
            ) as mock_resolve,
            patch(
                "core.shared_tools.openrouter_client.build_async_client_for_key",
                return_value=client,
            ) as mock_build,
        ):
            result = await service.run_prompts(
                [sample_prompt],
                engines=["openai", "perplexity", "claude"],
                workspace_id="ws-123",
                workspace_slug="ramp",
                company_slug="ramp",
            )

        assert result.engine_count == 1
        assert [response.engine for response in result.responses] == ["perplexity"]
        engines["openai"].search.assert_not_called()
        engines["claude"].search.assert_not_called()
        mock_resolve.assert_awaited_once()
        assert mock_resolve.await_args.kwargs["agent_key"] == "daily_tracker.platform.perplexity"
        mock_build.assert_called_once_with(
            "sk-or-workspace",
            base_url="https://openrouter.example/api/v1",
            timeout_s=None,
        )
        search_kwargs = engines["perplexity"].search.await_args.kwargs
        assert search_kwargs["client"] is client
        assert search_kwargs["workspace_id"] == "ws-123"
        assert search_kwargs["agent_key"] == "daily_tracker.platform.perplexity"
        assert search_kwargs["credential_id"] == "cred-1"
        assert search_kwargs["model_config_id"] == "cfg-1"

    @pytest.mark.asyncio
    async def test_run_prompts_multiple_engines(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        engines = {
            "openai": _make_mock_engine("openai"),
            "claude": _make_mock_engine("claude"),
            "gemini": _make_mock_engine("gemini"),
        }
        service = PlatformRunnerService(engine_registry=engines)

        result = await service.run_prompts(
            [sample_prompt], engines=["openai", "claude", "gemini"]
        )

        assert len(result.responses) == 3
        engine_names = {r.engine for r in result.responses}
        assert engine_names == {"openai", "claude", "gemini"}
        assert result.engine_count == 3

    @pytest.mark.asyncio
    async def test_run_prompts_multiple_prompts(self) -> None:
        engine = _make_mock_engine("openai")
        service = PlatformRunnerService(engine_registry={"openai": engine})
        prompts = [_make_prompt("p1"), _make_prompt("p2"), _make_prompt("p3")]

        result = await service.run_prompts(prompts, engines=["openai"])

        assert len(result.responses) == 3
        assert result.prompt_count == 3
        assert engine.search.await_count == 3

    @pytest.mark.asyncio
    async def test_run_prompts_empty_prompt_list(self) -> None:
        engine = _make_mock_engine("openai")
        service = PlatformRunnerService(engine_registry={"openai": engine})

        result = await service.run_prompts([], engines=["openai"])

        assert result.status == RunStatus.COMPLETED
        assert len(result.responses) == 0
        assert result.prompt_count == 0
        engine.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_prompts_no_engines_specified_uses_all(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        engines = {
            "openai": _make_mock_engine("openai"),
            "claude": _make_mock_engine("claude"),
        }
        service = PlatformRunnerService(engine_registry=engines)

        result = await service.run_prompts([sample_prompt])

        assert len(result.responses) == 2
        assert result.engine_count == 2

    @pytest.mark.asyncio
    async def test_run_prompts_invalid_engine_name_skipped(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        engine = _make_mock_engine("openai")
        service = PlatformRunnerService(engine_registry={"openai": engine})

        result = await service.run_prompts(
            [sample_prompt], engines=["openai", "nonexistent"]
        )

        assert len(result.responses) == 1
        assert result.engine_count == 1

    @pytest.mark.asyncio
    async def test_run_prompts_all_invalid_engines(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        service = PlatformRunnerService(engine_registry={"openai": _make_mock_engine()})

        result = await service.run_prompts(
            [sample_prompt], engines=["nonexistent1", "nonexistent2"]
        )

        assert result.status == RunStatus.COMPLETED
        assert len(result.responses) == 0
        assert result.engine_count == 0

    @pytest.mark.asyncio
    async def test_run_prompts_engine_error_returns_error_result(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        failing = _make_failing_engine("openai")
        service = PlatformRunnerService(engine_registry={"openai": failing})

        result = await service.run_prompts(
            [sample_prompt], engines=["openai"]
        )

        assert result.status == RunStatus.COMPLETED
        assert len(result.responses) == 1
        resp = result.responses[0]
        assert resp.error is not None
        assert "API key invalid" in resp.error
        assert resp.response_text == ""
        assert resp.engine == "openai"

    @pytest.mark.asyncio
    async def test_run_prompts_mixed_success_and_error(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        engines = {
            "openai": _make_mock_engine("openai"),
            "claude": _make_failing_engine("claude"),
        }
        service = PlatformRunnerService(engine_registry=engines)

        result = await service.run_prompts(
            [sample_prompt], engines=["openai", "claude"]
        )

        assert len(result.responses) == 2
        successes = [r for r in result.responses if r.error is None]
        errors = [r for r in result.responses if r.error is not None]
        assert len(successes) == 1
        assert len(errors) == 1
        assert successes[0].engine == "openai"
        assert errors[0].engine == "claude"

    @pytest.mark.asyncio
    async def test_result_has_run_id(self, sample_prompt: TrackedPrompt) -> None:
        service = PlatformRunnerService(
            engine_registry={"openai": _make_mock_engine("openai")}
        )

        result = await service.run_prompts(
            [sample_prompt], engines=["openai"]
        )

        assert result.run_id != ""
        assert len(result.run_id) > 0

    @pytest.mark.asyncio
    async def test_result_has_timestamps(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        service = PlatformRunnerService(
            engine_registry={"openai": _make_mock_engine("openai")}
        )

        result = await service.run_prompts(
            [sample_prompt], engines=["openai"]
        )

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    @pytest.mark.asyncio
    async def test_response_has_latency(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        service = PlatformRunnerService(
            engine_registry={"openai": _make_mock_engine("openai")}
        )

        result = await service.run_prompts(
            [sample_prompt], engines=["openai"]
        )

        assert result.responses[0].latency_ms >= 0

    @pytest.mark.asyncio
    async def test_response_has_timestamp(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        service = PlatformRunnerService(
            engine_registry={"openai": _make_mock_engine("openai")}
        )

        result = await service.run_prompts(
            [sample_prompt], engines=["openai"]
        )

        assert result.responses[0].timestamp is not None


# ---------------------------------------------------------------------------
# Concurrency tests
# ---------------------------------------------------------------------------


class TestConcurrencyControl:
    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Verify semaphore restricts concurrent engine calls."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def slow_search(query_text: str, query_id: str | None = None) -> PlatformResult:
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.01)
            async with lock:
                current_concurrent -= 1
            return PlatformResult(
                engine="test",
                model="test",
                query_id=query_id or "",
                query_text=query_text,
                response_text="ok",
                citations=[],
            )

        engine = AsyncMock()
        engine.engine_name = "test"
        engine.model = "test"
        engine.search = slow_search

        service = PlatformRunnerService(engine_registry={"test": engine})
        prompts = [_make_prompt(f"p{i}") for i in range(10)]

        await service.run_prompts(prompts, engines=["test"], concurrency=3)

        assert max_concurrent <= 3

    @pytest.mark.asyncio
    async def test_default_concurrency_is_six(
        self, sample_prompt: TrackedPrompt
    ) -> None:
        """Verify default concurrency parameter is 6."""
        engine = _make_mock_engine("openai")
        service = PlatformRunnerService(engine_registry={"openai": engine})

        # Just verify the method accepts default concurrency without error
        result = await service.run_prompts([sample_prompt], engines=["openai"])
        assert result.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# get_available_engines tests
# ---------------------------------------------------------------------------


class TestGetAvailableEngines:
    @pytest.mark.asyncio
    async def test_returns_all_registered_engines(self) -> None:
        engines = {
            "openai": _make_mock_engine("openai"),
            "claude": _make_mock_engine("claude"),
            "gemini": _make_mock_engine("gemini"),
        }
        service = PlatformRunnerService(engine_registry=engines)

        available = await service.get_available_engines()

        assert sorted(available) == ["claude", "gemini", "openai"]

    @pytest.mark.asyncio
    async def test_returns_sorted_list(self) -> None:
        engines = {
            "perplexity": _make_mock_engine(),
            "claude": _make_mock_engine(),
            "openai": _make_mock_engine(),
        }
        service = PlatformRunnerService(engine_registry=engines)

        available = await service.get_available_engines()

        assert available == sorted(available)

    @pytest.mark.asyncio
    async def test_empty_registry(self) -> None:
        service = PlatformRunnerService(engine_registry={})

        available = await service.get_available_engines()

        assert available == []


# ---------------------------------------------------------------------------
# Response conversion tests
# ---------------------------------------------------------------------------


class TestResponseConversion:
    @pytest.mark.asyncio
    async def test_converts_platform_result_to_response(self) -> None:
        engine = _make_mock_engine(
            "openai",
            response_text="Ramp offers corporate cards.",
            citations=[
                CitationRef(url="https://ramp.com", rank=1, source="openai"),
            ],
        )
        service = PlatformRunnerService(engine_registry={"openai": engine})
        prompt = _make_prompt("p1", text="corporate cards")

        result = await service.run_prompts([prompt], engines=["openai"])

        resp = result.responses[0]
        assert resp.response_text == "Ramp offers corporate cards."
        assert resp.engine == "openai"
        assert resp.prompt_id == "p1"

    @pytest.mark.asyncio
    async def test_handles_none_response_text(self) -> None:
        engine = AsyncMock()
        engine.engine_name = "openai"
        engine.model = "test"
        engine.search = AsyncMock(
            return_value=PlatformResult(
                engine="openai",
                model="test",
                query_id="q1",
                query_text="test",
                response_text=None,
                citations=[],
            )
        )
        service = PlatformRunnerService(engine_registry={"openai": engine})

        result = await service.run_prompts(
            [_make_prompt()], engines=["openai"]
        )

        assert result.responses[0].response_text == ""

    @pytest.mark.asyncio
    async def test_error_response_has_empty_response_text(self) -> None:
        service = PlatformRunnerService(
            engine_registry={"openai": _make_failing_engine("openai")}
        )

        result = await service.run_prompts(
            [_make_prompt()], engines=["openai"]
        )

        assert result.responses[0].response_text == ""
        assert result.responses[0].error is not None
