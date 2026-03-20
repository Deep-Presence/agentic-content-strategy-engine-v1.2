"""Unit tests for core.daily_tracker.persistence — DB + filesystem persistence hooks.

Pure unit tests — no real DB needed. All DB interaction is mocked via
AsyncMock session factories and patched repositories.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.daily_tracker import (
    DailyRunResult,
    MentionAnalysis,
    PlatformResponse,
    RunStatus,
)

# Deterministic UUIDs for DB-interacting tests (must be valid UUIDs
# because persistence functions call uuid.UUID(run_id)).
_RUN_UUID_1 = "11111111-1111-1111-1111-111111111111"
_RUN_UUID_2 = "22222222-2222-2222-2222-222222222222"
_RUN_UUID_3 = "33333333-3333-3333-3333-333333333333"
_RUN_UUID_4 = "44444444-4444-4444-4444-444444444444"



# ── _should_persist tests ────────────────────────────────────────────────


class TestShouldPersist:
    """Guard function that checks if DB persistence is configured."""

    def test_false_when_no_session_factory(self) -> None:
        from core.daily_tracker.persistence import _should_persist

        assert _should_persist(None, "ramp") is False

    def test_false_when_no_company_slug(self) -> None:
        from core.daily_tracker.persistence import _should_persist

        sf = MagicMock()
        assert _should_persist(sf, "") is False
        assert _should_persist(sf, None) is False  # type: ignore[arg-type]

    def test_true_when_all_set(self) -> None:
        from core.daily_tracker.persistence import _should_persist

        sf = MagicMock()
        assert _should_persist(sf, "ramp") is True


# ── write_run_artifact tests ─────────────────────────────────────────────


class TestWriteRunArtifact:
    """Filesystem-first: write run result + mention analyses to JSON."""

    @pytest.fixture()
    def sample_result(self) -> DailyRunResult:
        return DailyRunResult(
            run_id="run-001",
            company_id="ramp",
            status=RunStatus.COMPLETED,
            responses=[
                PlatformResponse(
                    prompt_id=str(uuid.uuid4()),
                    engine="openai",
                    response_text="Ramp is great",
                    latency_ms=120.0,
                    timestamp=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
                ),
            ],
            started_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 3, 15, 12, 1, tzinfo=timezone.utc),
            prompt_count=1,
            engine_count=1,
        )

    @pytest.fixture()
    def sample_analyses(self) -> list[MentionAnalysis]:
        return [
            MentionAnalysis(
                brand_mentioned=True,
                brand_mention_count=2,
                competitor_mentions={"brex": 1},
                citations=["https://ramp.com"],
                citation_rank=1,
            ),
        ]

    @pytest.mark.asyncio
    async def test_creates_dir_and_json(
        self, tmp_path: Path, sample_result: DailyRunResult, sample_analyses: list[MentionAnalysis]
    ) -> None:
        from core.daily_tracker.persistence import write_run_artifact

        out_path = await write_run_artifact(tmp_path, "ramp", sample_result, sample_analyses)

        assert out_path.exists()
        assert out_path.name == "run-001.json"
        assert out_path.parent.name == "runs"
        assert out_path.parent.parent.name == "ramp"

        data = json.loads(out_path.read_text())
        assert data["run_id"] == "run-001"
        assert data["company_id"] == "ramp"
        assert len(data["mention_analyses"]) == 1
        assert data["mention_analyses"][0]["brand_mentioned"] is True

    @pytest.mark.asyncio
    async def test_includes_mention_analyses(
        self, tmp_path: Path, sample_result: DailyRunResult, sample_analyses: list[MentionAnalysis]
    ) -> None:
        from core.daily_tracker.persistence import write_run_artifact

        out_path = await write_run_artifact(tmp_path, "ramp", sample_result, sample_analyses)
        data = json.loads(out_path.read_text())

        analysis = data["mention_analyses"][0]
        assert analysis["brand_mention_count"] == 2
        assert analysis["competitor_mentions"] == {"brex": 1}
        assert analysis["citations"] == ["https://ramp.com"]
        assert analysis["citation_rank"] == 1

    @pytest.mark.asyncio
    async def test_handles_empty_responses(self, tmp_path: Path) -> None:
        from core.daily_tracker.persistence import write_run_artifact

        result = DailyRunResult(run_id="run-empty", company_id="ramp", status=RunStatus.COMPLETED)
        out_path = await write_run_artifact(tmp_path, "ramp", result, [])

        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["responses"] == []
        assert data["mention_analyses"] == []

    @pytest.mark.asyncio
    async def test_handles_write_error(self, sample_result: DailyRunResult, sample_analyses: list[MentionAnalysis]) -> None:
        from core.daily_tracker.persistence import write_run_artifact

        # Pass a path that cannot be created (file where dir expected)
        bad_root = Path("/dev/null/impossible")
        out_path = await write_run_artifact(bad_root, "ramp", sample_result, sample_analyses)
        # Should return the intended path but not crash
        assert out_path is not None


# ── create_daily_run_record tests ────────────────────────────────────────


class TestCreateDailyRunRecord:
    """Create DailyRunModel row at task start with status=running."""

    @pytest.mark.asyncio
    async def test_creates_running_row(self) -> None:
        from core.daily_tracker.persistence import create_daily_run_record

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("core.daily_tracker.persistence.DailyRunModel") as MockModel:
            await create_daily_run_record(
                mock_sf, "ramp", _RUN_UUID_1, {"engines": ["openai"]}
            )

            MockModel.assert_called_once()
            call_kwargs = MockModel.call_args[1]
            assert call_kwargs["company_id"] == "ramp"
            assert call_kwargs["status"] == "running"
            mock_session.add.assert_called_once()
            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self) -> None:
        from core.daily_tracker.persistence import create_daily_run_record

        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        # Should not raise
        await create_daily_run_record(mock_sf, "ramp", _RUN_UUID_1, {})


# ── persist_daily_run_result tests ───────────────────────────────────────


class TestPersistDailyRunResult:
    """Persist completed/failed run results to DB."""

    @pytest.fixture()
    def prompt_id(self) -> str:
        return str(uuid.uuid4())

    @pytest.fixture()
    def sample_result(self, prompt_id: str) -> DailyRunResult:
        return DailyRunResult(
            run_id=_RUN_UUID_1,
            company_id="ramp",
            status=RunStatus.COMPLETED,
            responses=[
                PlatformResponse(
                    prompt_id=prompt_id,
                    engine="openai",
                    response_text="Ramp is mentioned",
                    latency_ms=100.0,
                    timestamp=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
                ),
            ],
            started_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 3, 15, 12, 1, tzinfo=timezone.utc),
            prompt_count=1,
            engine_count=1,
        )

    @pytest.fixture()
    def sample_analyses(self) -> list[MentionAnalysis]:
        return [
            MentionAnalysis(
                brand_mentioned=True,
                brand_mention_count=1,
                competitor_mentions={},
                citations=[],
            ),
        ]

    def _make_session_factory(self) -> tuple[MagicMock, AsyncMock]:
        """Helper to create a mock session factory with async context manager."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=MagicMock())  # existing run row
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        return mock_sf, mock_session

    @pytest.mark.asyncio
    async def test_skips_when_not_configured(
        self, sample_result: DailyRunResult, sample_analyses: list[MentionAnalysis]
    ) -> None:
        from core.daily_tracker.persistence import persist_daily_run_result

        # None session_factory — should return immediately
        await persist_daily_run_result(None, "ramp", sample_result, sample_analyses)

    @pytest.mark.asyncio
    async def test_skips_empty_company_slug(
        self, sample_result: DailyRunResult, sample_analyses: list[MentionAnalysis]
    ) -> None:
        from core.daily_tracker.persistence import persist_daily_run_result

        mock_sf, _ = self._make_session_factory()
        await persist_daily_run_result(mock_sf, "", sample_result, sample_analyses)
        # Session factory should NOT have been called
        mock_sf.return_value.__aenter__.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_updates_run_and_creates_responses(
        self,
        prompt_id: str,
        sample_result: DailyRunResult,
        sample_analyses: list[MentionAnalysis],
    ) -> None:
        from core.daily_tracker.persistence import persist_daily_run_result

        mock_sf, mock_session = self._make_session_factory()

        # Mock the run row returned by session.get()
        mock_run = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_run)

        with (
            patch("core.daily_tracker.persistence.DailyRunResponseModel") as MockResp,
            patch("core.daily_tracker.persistence.delete") as mock_delete,
        ):
            mock_delete.return_value.where.return_value = "mock_del_stmt"

            await persist_daily_run_result(
                mock_sf, "ramp", sample_result, sample_analyses
            )

            # Run row should be updated
            assert mock_run.status == "completed"
            assert mock_run.prompt_count == 1
            assert mock_run.engine_count == 1

            # Response model should be created
            MockResp.assert_called_once()
            call_kwargs = MockResp.call_args[1]
            assert call_kwargs["engine"] == "openai"
            assert call_kwargs["brand_mentioned"] is True
            assert call_kwargs["brand_mention_count"] == 1

            # Two commits: one for run-row update, one for response inserts
            assert mock_session.commit.await_count == 2

    @pytest.mark.asyncio
    async def test_handles_multiple_responses(self) -> None:
        from core.daily_tracker.persistence import persist_daily_run_result

        pid1, pid2 = str(uuid.uuid4()), str(uuid.uuid4())
        result = DailyRunResult(
            run_id=_RUN_UUID_2,
            company_id="ramp",
            status=RunStatus.COMPLETED,
            responses=[
                PlatformResponse(prompt_id=pid1, engine="openai", response_text="resp1"),
                PlatformResponse(prompt_id=pid2, engine="claude", response_text="resp2"),
            ],
            prompt_count=2,
            engine_count=2,
        )
        analyses = [
            MentionAnalysis(brand_mentioned=True, brand_mention_count=1),
            MentionAnalysis(brand_mentioned=False, brand_mention_count=0),
        ]

        mock_sf, mock_session = self._make_session_factory()
        mock_session.get = AsyncMock(return_value=MagicMock())

        with (
            patch("core.daily_tracker.persistence.DailyRunResponseModel"),
            patch("core.daily_tracker.persistence.delete") as mock_delete,
        ):
            mock_delete.return_value.where.return_value = "mock_del_stmt"

            await persist_daily_run_result(mock_sf, "ramp", result, analyses)
            # session.add should be called for each response
            assert mock_session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_catches_exceptions_gracefully(
        self, sample_result: DailyRunResult, sample_analyses: list[MentionAnalysis]
    ) -> None:
        from core.daily_tracker.persistence import persist_daily_run_result

        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        # Should not raise
        await persist_daily_run_result(mock_sf, "ramp", sample_result, sample_analyses)

    @pytest.mark.asyncio
    async def test_skips_invalid_prompt_id(self) -> None:
        from core.daily_tracker.persistence import persist_daily_run_result

        result = DailyRunResult(
            run_id=_RUN_UUID_3,
            company_id="ramp",
            status=RunStatus.COMPLETED,
            responses=[
                PlatformResponse(
                    prompt_id="not-a-uuid",
                    engine="openai",
                    response_text="resp",
                ),
            ],
            prompt_count=1,
            engine_count=1,
        )
        analyses = [MentionAnalysis(brand_mentioned=True)]

        mock_sf, mock_session = self._make_session_factory()
        mock_session.get = AsyncMock(return_value=MagicMock())

        with (
            patch("core.daily_tracker.persistence.DailyRunResponseModel") as MockResp,
            patch("core.daily_tracker.persistence.delete") as mock_delete,
        ):
            mock_delete.return_value.where.return_value = "mock_del_stmt"

            await persist_daily_run_result(mock_sf, "ramp", result, analyses)
            # Invalid prompt_id should be skipped
            MockResp.assert_not_called()

    @pytest.mark.asyncio
    async def test_idempotent_delete_before_insert(self) -> None:
        """Idempotency guard: existing responses are deleted before re-inserting."""
        from core.daily_tracker.persistence import persist_daily_run_result

        pid = str(uuid.uuid4())
        result = DailyRunResult(
            run_id=_RUN_UUID_1,
            company_id="ramp",
            status=RunStatus.COMPLETED,
            responses=[
                PlatformResponse(prompt_id=pid, engine="openai", response_text="resp"),
            ],
            prompt_count=1,
            engine_count=1,
        )
        analyses = [MentionAnalysis(brand_mentioned=True)]

        mock_sf, mock_session = self._make_session_factory()
        mock_session.get = AsyncMock(return_value=MagicMock())

        with (
            patch("core.daily_tracker.persistence.DailyRunResponseModel"),
            patch("core.daily_tracker.persistence.delete") as mock_delete,
        ):
            mock_delete.return_value.where.return_value = "mock_del_stmt"

            await persist_daily_run_result(mock_sf, "ramp", result, analyses)

            # Phase 2 should call delete() then execute the statement
            mock_delete.assert_called_once()
            mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_insert_on_mixed_validity(self) -> None:
        """Codex finding: one bad prompt_id should not prevent good ones from being stored."""
        from core.daily_tracker.persistence import persist_daily_run_result

        good_pid = str(uuid.uuid4())
        result = DailyRunResult(
            run_id=_RUN_UUID_4,
            company_id="ramp",
            status=RunStatus.COMPLETED,
            responses=[
                PlatformResponse(prompt_id=good_pid, engine="openai", response_text="good"),
                PlatformResponse(prompt_id="invalid", engine="claude", response_text="bad"),
            ],
            prompt_count=2,
            engine_count=2,
        )
        analyses = [
            MentionAnalysis(brand_mentioned=True),
            MentionAnalysis(brand_mentioned=False),
        ]

        mock_sf, mock_session = self._make_session_factory()
        mock_session.get = AsyncMock(return_value=MagicMock())

        with (
            patch("core.daily_tracker.persistence.DailyRunResponseModel") as MockResp,
            patch("core.daily_tracker.persistence.delete") as mock_delete,
        ):
            mock_delete.return_value.where.return_value = "mock_del_stmt"

            await persist_daily_run_result(mock_sf, "ramp", result, analyses)
            # Only 1 response should be created (the good one)
            assert MockResp.call_count == 1
            assert MockResp.call_args[1]["engine"] == "openai"
