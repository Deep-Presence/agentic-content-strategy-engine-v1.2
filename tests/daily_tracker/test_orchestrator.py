"""Tests for DailyTrackerOrchestrator.

Covers the full orchestration pipeline: prompt fetching, platform execution,
mention detection, and result assembly.  All dependencies are mocked — no
real LLM calls or DB operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.daily_tracker.orchestrator import DailyTrackerOrchestrator
from core.models.daily_tracker import (
    DailyRunResult,
    MentionAnalysis,
    PlatformResponse,
    RunStatus,
    TrackedPrompt,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_prompt(prompt_id: str = "p-1", text: str = "test prompt") -> TrackedPrompt:
    """Create a TrackedPrompt with minimal required fields."""
    return TrackedPrompt(
        id=prompt_id,
        company_id="company-abc",
        text=text,
        active=True,
    )


def _make_response(
    prompt_id: str = "p-1",
    engine: str = "openai",
    text: str = "Ramp is great.",
) -> PlatformResponse:
    """Create a PlatformResponse with sensible defaults."""
    return PlatformResponse(
        prompt_id=prompt_id,
        engine=engine,
        response_text=text,
        latency_ms=100.0,
        timestamp=datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_run_result(
    responses: list[PlatformResponse] | None = None,
    prompt_count: int = 1,
    engine_count: int = 1,
) -> DailyRunResult:
    """Create a DailyRunResult with given responses."""
    return DailyRunResult(
        run_id="run-001",
        company_id="company-abc",
        status=RunStatus.COMPLETED,
        responses=responses or [],
        started_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 2, 28, 12, 0, 1, tzinfo=timezone.utc),
        prompt_count=prompt_count,
        engine_count=engine_count,
    )


def _make_analysis(brand_mentioned: bool = True) -> MentionAnalysis:
    """Create a MentionAnalysis with given brand mention status."""
    return MentionAnalysis(
        brand_mentioned=brand_mentioned,
        brand_mention_count=2 if brand_mentioned else 0,
        competitor_mentions={"Brex": 1},
        citations=["https://ramp.com"],
        citation_rank=1 if brand_mentioned else None,
    )


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def mock_prompt_service() -> AsyncMock:
    """Mock PromptLibraryServiceProtocol."""
    service = AsyncMock()
    service.list_prompts = AsyncMock(return_value=[_make_prompt()])
    service.get_prompt = AsyncMock(return_value=_make_prompt())
    return service


@pytest.fixture()
def mock_runner_service() -> AsyncMock:
    """Mock PlatformRunnerServiceProtocol."""
    service = AsyncMock()
    service.run_prompts = AsyncMock(
        return_value=_make_run_result(
            responses=[_make_response()],
            prompt_count=1,
            engine_count=1,
        )
    )
    return service


@pytest.fixture()
def mock_mention_detector() -> MagicMock:
    """Mock MentionDetectorProtocol (sync method)."""
    detector = MagicMock()
    detector.detect_mentions = MagicMock(return_value=_make_analysis())
    return detector


@pytest.fixture()
def orchestrator(
    mock_prompt_service: AsyncMock,
    mock_runner_service: AsyncMock,
    mock_mention_detector: MagicMock,
) -> DailyTrackerOrchestrator:
    """Fully wired orchestrator with all mocks."""
    return DailyTrackerOrchestrator(
        prompt_service=mock_prompt_service,
        runner_service=mock_runner_service,
        mention_detector=mock_mention_detector,
    )


# ── Test: Full Run Success ───────────────────────────────────────────


class TestFullRunSuccess:
    """Tests for the happy path — complete daily run execution."""

    @pytest.mark.asyncio
    async def test_returns_completed_result(
        self, orchestrator: DailyTrackerOrchestrator
    ) -> None:
        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
            brand="Ramp",
        )
        assert result.status == RunStatus.COMPLETED
        assert result.run_id  # non-empty UUID string

    @pytest.mark.asyncio
    async def test_fetches_all_active_prompts_when_no_ids(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
    ) -> None:
        await orchestrator.execute_daily_run(company_id="company-abc")
        mock_prompt_service.list_prompts.assert_called_once_with(
            "company-abc", filters=None
        )

    @pytest.mark.asyncio
    async def test_runs_prompts_across_engines(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_runner_service: AsyncMock,
    ) -> None:
        await orchestrator.execute_daily_run(
            company_id="company-abc",
            engines=["openai", "claude"],
        )
        mock_runner_service.run_prompts.assert_called_once()
        call_kwargs = mock_runner_service.run_prompts.call_args
        assert call_kwargs.kwargs.get("engines") == ["openai", "claude"]

    @pytest.mark.asyncio
    async def test_detects_mentions_for_each_response(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_mention_detector: MagicMock,
    ) -> None:
        await orchestrator.execute_daily_run(
            company_id="company-abc",
            brand="Ramp",
            competitors=["Brex"],
        )
        mock_mention_detector.detect_mentions.assert_called_once()
        call_kwargs = mock_mention_detector.detect_mentions.call_args
        assert call_kwargs.kwargs.get("brand") == "Ramp"
        assert call_kwargs.kwargs.get("competitors") == ["Brex"]

    @pytest.mark.asyncio
    async def test_includes_responses_in_result(
        self, orchestrator: DailyTrackerOrchestrator
    ) -> None:
        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        assert len(result.responses) == 1
        assert result.responses[0].engine == "openai"

    @pytest.mark.asyncio
    async def test_counts_prompts_and_engines(
        self, orchestrator: DailyTrackerOrchestrator
    ) -> None:
        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        assert result.prompt_count == 1
        assert result.engine_count == 1

    @pytest.mark.asyncio
    async def test_has_start_and_end_timestamps(
        self, orchestrator: DailyTrackerOrchestrator
    ) -> None:
        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at


# ── Test: No Prompts ─────────────────────────────────────────────────


class TestRunWithNoPrompts:
    """Tests for when there are no prompts to run."""

    @pytest.mark.asyncio
    async def test_completes_with_zero_counts(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
    ) -> None:
        mock_prompt_service.list_prompts.return_value = []

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        assert result.status == RunStatus.COMPLETED
        assert result.prompt_count == 0
        assert result.engine_count == 0
        assert len(result.responses) == 0

    @pytest.mark.asyncio
    async def test_does_not_call_runner_or_detector(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
        mock_runner_service: AsyncMock,
        mock_mention_detector: MagicMock,
    ) -> None:
        mock_prompt_service.list_prompts.return_value = []

        await orchestrator.execute_daily_run(company_id="company-abc")
        mock_runner_service.run_prompts.assert_not_called()
        mock_mention_detector.detect_mentions.assert_not_called()


# ── Test: Specific Prompt IDs ────────────────────────────────────────


class TestRunWithSpecificPromptIds:
    """Tests for running with specific prompt IDs instead of all active."""

    @pytest.mark.asyncio
    async def test_fetches_specific_prompts(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
    ) -> None:
        await orchestrator.execute_daily_run(
            company_id="company-abc",
            prompt_ids=["p-1", "p-2"],
        )
        # Should call get_prompt for each ID, not list_prompts
        assert mock_prompt_service.get_prompt.call_count == 2
        mock_prompt_service.list_prompts.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_not_found_prompts(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
    ) -> None:
        # Second prompt not found
        mock_prompt_service.get_prompt.side_effect = [
            _make_prompt("p-1"),
            None,
        ]

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
            prompt_ids=["p-1", "p-2"],
        )
        assert result.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_all_prompt_ids_not_found_gives_empty_run(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
    ) -> None:
        mock_prompt_service.get_prompt.return_value = None

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
            prompt_ids=["p-1"],
        )
        assert result.status == RunStatus.COMPLETED
        assert result.prompt_count == 0

    @pytest.mark.asyncio
    async def test_rejects_cross_tenant_prompt_ids(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_prompt_service: AsyncMock,
    ) -> None:
        """Codex finding: prompt belonging to another company must be skipped."""
        other_tenant_prompt = TrackedPrompt(
            id="p-other", company_id="other-company", text="foreign", active=True,
        )
        own_prompt = _make_prompt("p-own")
        mock_prompt_service.get_prompt.side_effect = [other_tenant_prompt, own_prompt]

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
            prompt_ids=["p-other", "p-own"],
        )
        # Only the own prompt should be used (prompt_count=1, not 2)
        assert result.prompt_count == 1


# ── Test: Runner Failure ─────────────────────────────────────────────


class TestRunnerFailure:
    """Tests for when the platform runner raises an exception."""

    @pytest.mark.asyncio
    async def test_failure_returns_failed_status(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_runner_service: AsyncMock,
    ) -> None:
        mock_runner_service.run_prompts.side_effect = RuntimeError("API timeout")

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        assert result.status == RunStatus.FAILED
        assert "API timeout" in (result.error or "")

    @pytest.mark.asyncio
    async def test_failure_has_timestamps(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_runner_service: AsyncMock,
    ) -> None:
        mock_runner_service.run_prompts.side_effect = RuntimeError("boom")

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        assert result.started_at is not None
        assert result.completed_at is not None


# ── Test: Mention Counting ───────────────────────────────────────────


class TestMentionCounting:
    """Tests for correct mention analysis attachment and counting."""

    @pytest.mark.asyncio
    async def test_analyses_attached_to_result(
        self,
        orchestrator: DailyTrackerOrchestrator,
    ) -> None:
        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
            brand="Ramp",
        )
        # Analyses stored as _mention_analyses attribute
        analyses = getattr(result, "_mention_analyses", [])
        assert len(analyses) == 1
        assert analyses[0].brand_mentioned is True

    @pytest.mark.asyncio
    async def test_multiple_responses_counted(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_runner_service: AsyncMock,
        mock_mention_detector: MagicMock,
    ) -> None:
        # 3 responses, 2 with brand mentions
        mock_runner_service.run_prompts.return_value = _make_run_result(
            responses=[
                _make_response("p-1", "openai", "Ramp is great"),
                _make_response("p-1", "claude", "No mention here"),
                _make_response("p-2", "openai", "Ramp again"),
            ],
            prompt_count=2,
            engine_count=2,
        )
        mock_mention_detector.detect_mentions.side_effect = [
            _make_analysis(True),
            _make_analysis(False),
            _make_analysis(True),
        ]

        result = await orchestrator.execute_daily_run(
            company_id="company-abc",
            brand="Ramp",
        )
        analyses = getattr(result, "_mention_analyses", [])
        mentions_found = sum(1 for a in analyses if a.brand_mentioned)
        assert mentions_found == 2
        assert len(result.responses) == 3

    @pytest.mark.asyncio
    async def test_no_brand_name_uses_empty_string(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_mention_detector: MagicMock,
    ) -> None:
        await orchestrator.execute_daily_run(
            company_id="company-abc",
            # No brand parameter
        )
        call_kwargs = mock_mention_detector.detect_mentions.call_args
        assert call_kwargs.kwargs.get("brand") == ""


# ── Test: Get Run Status ─────────────────────────────────────────────


class TestGetRunStatus:
    """Tests for the get_run_status pass-through method."""

    @pytest.mark.asyncio
    async def test_returns_unknown_for_any_id(
        self, orchestrator: DailyTrackerOrchestrator
    ) -> None:
        # Why: orchestrator is stateless — this is for protocol compliance
        result = await orchestrator.get_run_status("run-999")
        assert result["run_id"] == "run-999"
        assert result["status"] == "unknown"


# ── Test: Concurrency forwarding ─────────────────────────────────────


class TestConcurrencyForwarding:
    """Tests that concurrency parameter is forwarded to runner."""

    @pytest.mark.asyncio
    async def test_custom_concurrency_forwarded(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_runner_service: AsyncMock,
    ) -> None:
        await orchestrator.execute_daily_run(
            company_id="company-abc",
            concurrency=2,
        )
        call_kwargs = mock_runner_service.run_prompts.call_args
        assert call_kwargs.kwargs.get("concurrency") == 2

    @pytest.mark.asyncio
    async def test_default_concurrency_is_six(
        self,
        orchestrator: DailyTrackerOrchestrator,
        mock_runner_service: AsyncMock,
    ) -> None:
        await orchestrator.execute_daily_run(
            company_id="company-abc",
        )
        call_kwargs = mock_runner_service.run_prompts.call_args
        assert call_kwargs.kwargs.get("concurrency") == 6
