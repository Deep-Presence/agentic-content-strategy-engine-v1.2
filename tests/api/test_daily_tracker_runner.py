"""Tests for daily tracker runner background task logic.

Lazy imports inside ``run_daily_tracker_task`` require patching at the SOURCE
module level (not ``api.tasks.runner.*``), since ``from X import Y`` inside a
function body creates a local variable from the source module's attribute.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.runner import run_daily_tracker_task
from api.tasks.store import TaskStore
from core.models.daily_tracker import DailyRunResult, MentionAnalysis, RunStatus


# task_store, event_bus, artifacts_root fixtures come from tests/api/conftest.py

# ── Patch targets (source modules for lazy imports) ──────────────────

_P_ORCH = "core.daily_tracker.orchestrator.DailyTrackerOrchestrator"
_P_PROMPT_REPO = "core.db.repositories.daily_tracker_repo.TrackedPromptRepository"
_P_PROMPT_SVC = "core.daily_tracker.prompt_library.PromptLibraryService"
_P_RUNNER_SVC = "core.daily_tracker.platform_runner.PlatformRunnerService"
_P_DETECTOR = "core.daily_tracker.mention_detector.MentionDetector"
_P_CREATE_REC = "core.daily_tracker.persistence.create_daily_run_record"
_P_WRITE_ART = "core.daily_tracker.persistence.write_run_artifact"
_P_PERSIST = "core.daily_tracker.persistence.persist_daily_run_result"
_P_MARK_FAIL = "core.daily_tracker.persistence.mark_daily_run_failed"
# Module-level targets (OK to patch on runner directly)
_P_RESOLVE_DB = "api.tasks.runner._resolve_db_context"
_P_CREATE_PR = "api.tasks.runner._create_pipeline_run"
_P_MARK_PR_COMPLETE = "api.tasks.runner._mark_pipeline_run_complete"
_P_MARK_PR_FAILED = "api.tasks.runner._mark_pipeline_run_failed"


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def run_request() -> SimpleNamespace:
    """Mimics TriggerRunRequest fields."""
    return SimpleNamespace(
        engines=["openai"],
        prompt_ids=None,
        brand="Ramp",
        competitors=["Brex"],
        concurrency=6,
    )


_MOCK_RUN_ID = str(uuid.uuid4())


def _make_completed_result(run_id: str = _MOCK_RUN_ID) -> DailyRunResult:
    result = DailyRunResult(
        run_id=run_id, company_id="ramp", status=RunStatus.COMPLETED,
        prompt_count=2, engine_count=1,
    )
    result._mention_analyses = [  # type: ignore[attr-defined]
        MentionAnalysis(brand_mentioned=True, brand_mention_count=1),
    ]
    return result


def _make_failed_result(run_id: str = _MOCK_RUN_ID) -> DailyRunResult:
    result = DailyRunResult(
        run_id=run_id, company_id="ramp", status=RunStatus.FAILED,
        error="Platform timeout", prompt_count=0, engine_count=0,
    )
    result._mention_analyses = []  # type: ignore[attr-defined]
    return result


def _session_factory() -> MagicMock:
    """Create a mock async session factory."""
    mock_session = AsyncMock()
    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_sf


def _apply_common_patches(
    stack: ExitStack,
    result: DailyRunResult,
    sf: MagicMock | None = None,
    *,
    no_db: bool = False,
) -> dict[str, AsyncMock]:
    """Apply all common patches via ExitStack, returns named mocks."""
    mocks: dict[str, AsyncMock] = {}

    # DB context
    if no_db:
        stack.enter_context(patch(
            _P_RESOLVE_DB, new_callable=AsyncMock,
            return_value=(None, None, None),
        ))
    else:
        sf = sf or _session_factory()
        stack.enter_context(patch(
            _P_RESOLVE_DB, new_callable=AsyncMock,
            return_value=(sf, uuid.uuid4(), uuid.uuid4()),
        ))

    stack.enter_context(patch(_P_CREATE_PR, new_callable=AsyncMock))

    # Orchestrator deps (source-module patches)
    mock_orch = AsyncMock()
    mock_orch.execute_daily_run = AsyncMock(return_value=result)
    mock_orch._fetch_prompts = AsyncMock(return_value=[])  # pre-fetch returns empty
    mock_orch_cls = MagicMock(return_value=mock_orch)
    stack.enter_context(patch(_P_ORCH, mock_orch_cls))
    stack.enter_context(patch(_P_PROMPT_REPO, MagicMock()))
    stack.enter_context(patch(_P_PROMPT_SVC, MagicMock()))
    stack.enter_context(patch(_P_RUNNER_SVC, MagicMock()))
    stack.enter_context(patch(_P_DETECTOR, MagicMock()))
    mocks["orch"] = mock_orch

    # Persistence (source-module patches)
    mocks["create_rec"] = stack.enter_context(patch(_P_CREATE_REC, new_callable=AsyncMock))
    mocks["write_art"] = stack.enter_context(patch(_P_WRITE_ART, new_callable=AsyncMock))
    mocks["persist"] = stack.enter_context(patch(_P_PERSIST, new_callable=AsyncMock))
    mocks["mark_fail"] = stack.enter_context(patch(_P_MARK_FAIL, new_callable=AsyncMock))

    # Module-level runner helpers
    mocks["pr_complete"] = stack.enter_context(patch(_P_MARK_PR_COMPLETE, new_callable=AsyncMock))
    mocks["pr_failed"] = stack.enter_context(patch(_P_MARK_PR_FAILED, new_callable=AsyncMock))

    return mocks


async def _run_task(
    task_store: TaskStore, event_bus: EventBus,
    run_request: SimpleNamespace, artifacts_root: Path,
    task_id: str,
) -> None:
    """Shorthand for calling run_daily_tracker_task."""
    await run_daily_tracker_task(
        task_id=task_id,
        request=run_request,
        company_slug="ramp",
        artifacts_root=artifacts_root,
        task_store=task_store,
        event_bus=event_bus,
    )


# ── Tests ───────────────────────────────────────────────────────────


class TestRunDailyTrackerTask:
    """Background task wrapper for daily tracker pipeline."""

    @pytest.mark.asyncio
    async def test_publishes_start_and_completed_events(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        collected: list[tuple] = []
        original_publish = event_bus.publish

        def capture(tid, etype, data=None):
            collected.append((tid, etype))
            return original_publish(tid, etype, data)

        event_bus.publish = capture  # type: ignore[assignment]

        with ExitStack() as stack:
            _apply_common_patches(stack, result)
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

        event_types = [e[1] for e in collected]
        assert "pipeline_start" in event_types
        assert "completed" in event_types

    @pytest.mark.asyncio
    async def test_writes_filesystem_artifact(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

            mocks["write_art"].assert_awaited_once()
            assert mocks["write_art"].call_args[0][0] == artifacts_root
            assert mocks["write_art"].call_args[0][1] == "ramp"

    @pytest.mark.asyncio
    async def test_calls_persist_daily_run_result(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

            mocks["persist"].assert_awaited_once()
            assert mocks["persist"].call_args[0][1] == "ramp"

    @pytest.mark.asyncio
    async def test_handles_orchestrator_exception(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()  # won't be used — orch raises

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            mocks["orch"].execute_daily_run = AsyncMock(
                side_effect=RuntimeError("Platform exploded"),
            )
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "Platform exploded" in (updated.error or "")

    @pytest.mark.asyncio
    async def test_releases_slug_lock_on_failure(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        """Verify correct slug key format: 'daily_tracker:{company_slug}'."""
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            mocks["orch"].execute_daily_run = AsyncMock(
                side_effect=RuntimeError("boom"),
            )
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

        # Slug lock released — creating a new task should work
        task2 = task_store.create_task("daily_tracker", "ramp")
        assert task2 is not None

    @pytest.mark.asyncio
    async def test_handles_cancelled_error(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            mocks["orch"].execute_daily_run = AsyncMock(
                side_effect=asyncio.CancelledError(),
            )
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

        # Should not crash — CancelledError path just logs

    @pytest.mark.asyncio
    async def test_marks_pipeline_run_complete(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

            mocks["pr_complete"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_marks_pipeline_run_failed_on_error(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            mocks["orch"].execute_daily_run = AsyncMock(
                side_effect=RuntimeError("DB crash"),
            )
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

            mocks["pr_failed"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_works_without_db(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        """When no DATABASE_URL is set, runner fails gracefully."""
        task = task_store.create_task("daily_tracker", "ramp")

        with ExitStack() as stack:
            stack.enter_context(patch(
                _P_RESOLVE_DB, new_callable=AsyncMock,
                return_value=(None, None, None),
            ))
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "DATABASE_URL" in (updated.error or "")

    @pytest.mark.asyncio
    async def test_handles_failed_result_without_exception(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        """Codex finding: orchestrator returns FAILED without raising."""
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_failed_result()

        with ExitStack() as stack:
            mocks = _apply_common_patches(stack, result)
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

            mocks["pr_failed"].assert_awaited_once()

        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.FAILED
        assert "Platform timeout" in (updated.error or "")

    @pytest.mark.asyncio
    async def test_completed_run_sets_result(
        self, task_store: TaskStore, event_bus: EventBus,
        run_request: SimpleNamespace, artifacts_root: Path,
    ) -> None:
        task = task_store.create_task("daily_tracker", "ramp")
        result = _make_completed_result()

        with ExitStack() as stack:
            _apply_common_patches(stack, result)
            await _run_task(task_store, event_bus, run_request, artifacts_root, task.task_id)

        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.COMPLETED
        # run_id is now pre-generated by the runner (not the orchestrator)
        assert updated.result["run_id"] is not None
        assert len(updated.result["run_id"]) == 36  # UUID string format
        assert updated.result["prompt_count"] == 2
        assert updated.result["engine_count"] == 1
