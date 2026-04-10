"""Unit tests for durable topic-run activity snapshot shaping."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.services.content_engine_topic_runs import ContentEngineTopicRunService
from core.shared_tools.task_status import TaskStatus


def test_to_event_snapshot_merges_run_context_into_payload() -> None:
    run = SimpleNamespace(
        id="run-1",
        batch_run_id="batch-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        topic_text="Equity dilution guide",
        brief_id="WE-003",
        effective_slug="test-co",
        entry_mode="topic_discovery",
        metadata_json={
            "buyer_stage": "tofu",
            "intent_type": "informational",
        },
    )
    event = SimpleNamespace(
        id="evt-1",
        topic_run_id="run-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        event_type="topic_run_changed",
        stage="drafting",
        status="drafting",
        seq=4,
        content_piece_id=None,
        pipeline_task_id="task-1",
        payload_json={"note": "Worker drafting started"},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )

    snapshot = ContentEngineTopicRunService._to_event_snapshot(run, event)

    assert snapshot.payload_json == {
        "note": "Worker drafting started",
        "brief_id": "WE-003",
        "display_id": "WE-003",
        "topic_text": "Equity dilution guide",
        "entry_mode": "topic_discovery",
        "buyer_stage": "tofu",
        "intent_type": "informational",
        "effective_slug": "test-co",
        "batch_run_id": "batch-1",
    }


def test_to_event_snapshot_preserves_explicit_payload_values() -> None:
    run = SimpleNamespace(
        id="run-1",
        batch_run_id="batch-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        topic_text="Equity dilution guide",
        brief_id="WE-003",
        effective_slug="test-co",
        entry_mode="topic_discovery",
        metadata_json={"buyer_stage": "tofu"},
    )
    event = SimpleNamespace(
        id="evt-1",
        topic_run_id="run-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        event_type="topic_run_created",
        stage="gap_analysis_pending",
        status="gap_analysis_pending",
        seq=1,
        content_piece_id=None,
        pipeline_task_id="task-1",
        payload_json={
            "brief_id": "CUSTOM-1",
            "display_id": "CUSTOM-1",
            "topic_text": "Custom topic",
            "entry_mode": "manual",
            "buyer_stage": "bofu",
            "batch_run_id": "batch-custom",
        },
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )

    snapshot = ContentEngineTopicRunService._to_event_snapshot(run, event)

    assert snapshot.payload_json["brief_id"] == "CUSTOM-1"
    assert snapshot.payload_json["display_id"] == "CUSTOM-1"
    assert snapshot.payload_json["topic_text"] == "Custom topic"
    assert snapshot.payload_json["entry_mode"] == "manual"
    assert snapshot.payload_json["buyer_stage"] == "bofu"
    assert snapshot.payload_json["batch_run_id"] == "batch-custom"


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_advance_topic_runs_can_clear_nullable_scheduler_fields() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session_factory = MagicMock(return_value=_FakeSessionContext(session))
    assignment_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    run = SimpleNamespace(
        id="run-1",
        batch_run_id="batch-1",
        topic_assignment_id=assignment_id,
        display_id="WE-003",
        topic_text="Equity dilution guide",
        brief_id="WE-003",
        ga_run_id=None,
        pipeline_task_id="stale-task",
        status="failed",
        current_stage="failed",
        status_seq=4,
        scheduler_state="running",
        claim_token="claim-1",
        queued_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        claimed_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        waiting_for_human_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        continuation_payload_json={"resume_stage": "brief_approval"},
        last_error=None,
        failed_at=None,
        completed_at=None,
        started_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        content_piece_id=None,
        effective_slug="test-co",
        metadata_json={},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    topic_run_repo = MagicMock()
    topic_run_repo.list_by_assignment_ids = AsyncMock(return_value=[run])
    event_repo = MagicMock()
    event_repo.append_event = AsyncMock()

    with patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicRunRepository",
        return_value=topic_run_repo,
    ), patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicEventRepository",
        return_value=event_repo,
    ):
            service = ContentEngineTopicRunService(session_factory)
            snapshots = await service.advance_topic_runs(
                effective_slug="test-co",
                topic_assignment_ids=[str(assignment_id)],
                status="content_queued",
                stage="content_queued",
                pipeline_task_id=None,
            scheduler_state="queued",
            clear_claim_token=True,
            claimed_at=None,
            waiting_for_human_at=None,
            continuation_payload_json={},
        )

    assert run.pipeline_task_id is None
    assert run.claim_token is None
    assert run.claimed_at is None
    assert run.waiting_for_human_at is None
    assert run.scheduler_state == "queued"
    assert run.continuation_payload_json == {}
    assert snapshots[0].pipeline_task_id is None


@pytest.mark.asyncio
async def test_reconcile_startup_scheduler_requeues_stranded_running_topic() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session_factory = MagicMock(return_value=_FakeSessionContext(session))
    assignment_id = uuid.UUID("22345678-1234-5678-1234-567812345678")
    run = SimpleNamespace(
        id=uuid.uuid4(),
        batch_run_id=uuid.uuid4(),
        topic_assignment_id=assignment_id,
        display_id="WE-177",
        topic_text="Equity dilution guide",
        brief_id="WE-177",
        ga_run_id=None,
        pipeline_task_id="old-task",
        status="drafting",
        current_stage="drafting",
        status_seq=4,
        scheduler_state="running",
        claim_token="claim-1",
        queued_at=None,
        claimed_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        waiting_for_human_at=None,
        continuation_payload_json=None,
        content_piece_id=None,
        effective_slug="test-co",
        metadata_json={},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    topic_run_repo = MagicMock()
    topic_run_repo.list_recovery_candidates = AsyncMock(return_value=[run])
    event_repo = MagicMock()
    event_repo.append_event = AsyncMock()

    with patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicRunRepository",
        return_value=topic_run_repo,
    ), patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicEventRepository",
        return_value=event_repo,
    ):
        service = ContentEngineTopicRunService(session_factory)
        recovery = await service.reconcile_startup_scheduler(
            task_by_id={"old-task": SimpleNamespace(task_id="old-task", status=TaskStatus.FAILED_RESTART, approval_payload=None)},
        )

    assert run.scheduler_state == "queued"
    assert run.status == "content_queued"
    assert run.current_stage == "content_queued"
    assert run.pipeline_task_id is None
    assert recovery.companies_to_dispatch == ["test-co"]
    assert recovery.requeued_count == 1
    assert recovery.stale_task_ids_cleared_count == 1
    event_repo.append_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_startup_scheduler_restores_waiting_human_from_failed_restart_task() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session_factory = MagicMock(return_value=_FakeSessionContext(session))
    assignment_id = uuid.UUID("32345678-1234-5678-1234-567812345678")
    run = SimpleNamespace(
        id=uuid.uuid4(),
        batch_run_id=uuid.uuid4(),
        topic_assignment_id=assignment_id,
        display_id="WE-142",
        topic_text="Visual web platforms",
        brief_id="WE-142",
        ga_run_id=None,
        pipeline_task_id="resume-task",
        status="briefing",
        current_stage="briefing",
        status_seq=7,
        scheduler_state="running",
        claim_token="claim-2",
        queued_at=None,
        claimed_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        waiting_for_human_at=None,
        continuation_payload_json=None,
        content_piece_id=None,
        effective_slug="test-co",
        metadata_json={},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    topic_run_repo = MagicMock()
    topic_run_repo.list_recovery_candidates = AsyncMock(return_value=[run])
    event_repo = MagicMock()
    event_repo.append_event = AsyncMock()
    approval_payload = {
        "stage": "brief_approval",
        "status": "pending_brief_approval",
        "continuation": {
            "resume_stage": "brief_approval",
            "topic_assignment_id": str(assignment_id),
            "brief_id": "WE-142",
            "thread_id": "thread-1",
        },
    }

    with patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicRunRepository",
        return_value=topic_run_repo,
    ), patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicEventRepository",
        return_value=event_repo,
    ):
        service = ContentEngineTopicRunService(session_factory)
        recovery = await service.reconcile_startup_scheduler(
            task_by_id={"resume-task": SimpleNamespace(task_id="resume-task", status=TaskStatus.FAILED_RESTART, approval_payload=approval_payload)},
        )

    assert run.scheduler_state == "waiting_human"
    assert run.status == "pending_brief_approval"
    assert run.current_stage == "brief_approval"
    assert run.continuation_payload_json["thread_id"] == "thread-1"
    assert recovery.waiting_human_restored_count == 1
    assert recovery.companies_to_dispatch == []
    event_repo.append_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_startup_scheduler_requeues_stranded_continuation_as_resume_queued() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session_factory = MagicMock(return_value=_FakeSessionContext(session))
    assignment_id = uuid.UUID("42345678-1234-5678-1234-567812345678")
    run = SimpleNamespace(
        id=uuid.uuid4(),
        batch_run_id=uuid.uuid4(),
        topic_assignment_id=assignment_id,
        display_id="WE-139",
        topic_text="No-code platform guide",
        brief_id="WE-139",
        ga_run_id=None,
        pipeline_task_id="resume-task",
        status="pending_content_approval",
        current_stage="content_review",
        status_seq=9,
        scheduler_state="running",
        claim_token="claim-3",
        queued_at=None,
        claimed_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        waiting_for_human_at=None,
        continuation_payload_json={
            "resume_stage": "content_review",
            "topic_assignment_id": str(assignment_id),
            "brief_id": "WE-139",
            "thread_id": "thread-2",
        },
        content_piece_id=None,
        effective_slug="test-co",
        metadata_json={},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    topic_run_repo = MagicMock()
    topic_run_repo.list_recovery_candidates = AsyncMock(return_value=[run])
    event_repo = MagicMock()
    event_repo.append_event = AsyncMock()

    with patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicRunRepository",
        return_value=topic_run_repo,
    ), patch(
        "core.services.content_engine_topic_runs.ContentEngineTopicEventRepository",
        return_value=event_repo,
    ):
        service = ContentEngineTopicRunService(session_factory)
        recovery = await service.reconcile_startup_scheduler(
            task_by_id={"resume-task": SimpleNamespace(task_id="resume-task", status=TaskStatus.FAILED_RESTART, approval_payload=None)},
        )

    assert run.scheduler_state == "resume_queued"
    assert run.pipeline_task_id == "resume-task"
    assert recovery.companies_to_dispatch == ["test-co"]
    assert recovery.queued_ready_count == 1
    event_repo.append_event.assert_awaited_once()
