"""Tests for api.tasks.store — JSON-file-backed TaskStore."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.store import ApprovalWindowError, TaskConflictError, TaskNotFoundError, TaskStore


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def store(tmp_path: Path, event_bus: EventBus) -> TaskStore:
    return TaskStore(base_dir=tmp_path / "_jobs", event_bus=event_bus)


# ── CRUD ──────────────────────────────────────────────────────────────


class TestTaskStoreCRUD:
    def test_create_task(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        assert task.pipeline == "gap_analysis"
        assert task.company_slug == "ramp"
        assert task.status == TaskStatus.RUNNING
        assert task.task_id  # non-empty

    def test_get_task(self, store: TaskStore) -> None:
        created = store.create_task("research", "carta")
        retrieved = store.get_task(created.task_id)
        assert retrieved.task_id == created.task_id
        assert retrieved.pipeline == "research"

    def test_get_task_not_found(self, store: TaskStore) -> None:
        with pytest.raises(TaskNotFoundError):
            store.get_task("nonexistent-id")

    def test_update_task_status(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        original_updated_at = task.updated_at
        updated = store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.updated_at >= original_updated_at

    def test_update_task_with_result(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        updated = store.update_task(
            task.task_id,
            status=TaskStatus.COMPLETED,
            result={"report_md": "# Test Report"},
        )
        assert updated.result == {"report_md": "# Test Report"}

    def test_update_task_with_error(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        updated = store.update_task(
            task.task_id,
            status=TaskStatus.FAILED,
            error="Connection timeout",
        )
        assert updated.status == TaskStatus.FAILED
        assert updated.error == "Connection timeout"

    def test_update_nonexistent_task(self, store: TaskStore) -> None:
        with pytest.raises(TaskNotFoundError):
            store.update_task("nonexistent", status=TaskStatus.COMPLETED)

    def test_list_tasks(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp")
        store.create_task("research", "carta")
        tasks = store.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_filter_by_pipeline(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp")
        store.create_task("research", "carta")
        store.create_task("gap_analysis", "acme")
        tasks = store.list_tasks(pipeline="gap_analysis")
        assert len(tasks) == 2
        assert all(t.pipeline == "gap_analysis" for t in tasks)

    def test_list_tasks_filter_by_status(self, store: TaskStore) -> None:
        t1 = store.create_task("gap_analysis", "ramp")
        store.create_task("research", "carta")
        store.update_task(t1.task_id, status=TaskStatus.COMPLETED)
        tasks = store.list_tasks(status="completed")
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.COMPLETED


# ── Persistence ───────────────────────────────────────────────────────


class TestTaskStorePersistence:
    def test_creates_json_file(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        json_path = store._base_dir / f"{task.task_id}.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["task_id"] == task.task_id

    def test_update_persists(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        json_path = store._base_dir / f"{task.task_id}.json"
        data = json.loads(json_path.read_text())
        assert data["status"] == "completed"

    def test_reload_from_disk(
        self, tmp_path: Path, event_bus: EventBus
    ) -> None:
        base = tmp_path / "_jobs"
        store1 = TaskStore(base_dir=base, event_bus=event_bus)
        t1 = store1.create_task("gap_analysis", "ramp")
        store1.update_task(t1.task_id, status=TaskStatus.COMPLETED)
        t2 = store1.create_task("research", "carta")
        store1.update_task(t2.task_id, status=TaskStatus.FAILED, error="err")

        # New store from same dir
        store2 = TaskStore(base_dir=base, event_bus=event_bus)
        tasks = store2.list_tasks()
        assert len(tasks) == 2
        restored = store2.get_task(t1.task_id)
        assert restored.status == TaskStatus.COMPLETED

    def test_orphan_recovery(
        self, tmp_path: Path, event_bus: EventBus
    ) -> None:
        base = tmp_path / "_jobs"
        store1 = TaskStore(base_dir=base, event_bus=event_bus)
        task = store1.create_task("gap_analysis", "ramp")
        # Task is still "running" — simulate crash by creating new store
        store2 = TaskStore(base_dir=base, event_bus=event_bus)
        recovered = store2.get_task(task.task_id)
        assert recovered.status == TaskStatus.FAILED_RESTART


# ── Slug Locks ────────────────────────────────────────────────────────


class TestSlugLocks:
    def test_slug_conflict(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp")
        with pytest.raises(TaskConflictError):
            store.create_task("gap_analysis", "ramp")

    def test_different_slugs_ok(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp")
        task2 = store.create_task("gap_analysis", "carta")
        assert task2.company_slug == "carta"

    def test_slug_released_on_completion(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        store.release_slug_lock("ramp")
        # Should not raise
        task2 = store.create_task("gap_analysis", "ramp")
        assert task2.company_slug == "ramp"

    def test_slug_released_on_failure(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        store.update_task(task.task_id, status=TaskStatus.FAILED, error="err")
        store.release_slug_lock("ramp")
        task2 = store.create_task("gap_analysis", "ramp")
        assert task2.company_slug == "ramp"


# ── HITL Approval ─────────────────────────────────────────────────────


class TestHITLApproval:
    async def test_submit_and_wait_for_approval(self, store: TaskStore) -> None:
        task = store.create_task("research", "ramp")
        store.update_task(task.task_id, status=TaskStatus.PENDING_APPROVAL)

        async def approve_later():
            await asyncio.sleep(0.05)
            store.submit_approval(task.task_id, "approve")

        asyncio.create_task(approve_later())
        result = await store.wait_for_approval(task.task_id)
        assert result["decision"] == "approve"

    async def test_submit_approval_with_revision_note(
        self, store: TaskStore
    ) -> None:
        task = store.create_task("research", "ramp")
        store.update_task(task.task_id, status=TaskStatus.PENDING_APPROVAL)

        async def approve_later():
            await asyncio.sleep(0.05)
            store.submit_approval(task.task_id, "revise", "Add more detail")

        asyncio.create_task(approve_later())
        result = await store.wait_for_approval(task.task_id)
        assert result["decision"] == "revise"
        assert result["revision_note"] == "Add more detail"

    async def test_submit_approval_nonexistent_task(
        self, store: TaskStore
    ) -> None:
        with pytest.raises(TaskNotFoundError):
            store.submit_approval("nonexistent", "approve")


# ── Nonce Validation + TOCTOU Prevention ──────────────────────────────


class TestSubmitApprovalNonce:
    """Tests for atomic nonce validation in submit_approval."""

    def test_nonce_mismatch_raises(self, store: TaskStore) -> None:
        """Stale nonce → ApprovalWindowError (not silent acceptance)."""
        task = store.create_task("content_v13", "ramp")
        store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "topic_approval", "checkpoint_nonce": "nonce-abc"},
        )
        with pytest.raises(ApprovalWindowError, match="nonce mismatch"):
            store.submit_approval(
                task.task_id, "approve",
                expected_nonce="nonce-WRONG",
            )

    def test_nonce_match_succeeds(self, store: TaskStore) -> None:
        """Correct nonce → approval queued normally."""
        task = store.create_task("content_v13", "ramp")
        store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "topic_approval", "checkpoint_nonce": "nonce-abc"},
        )
        # Should not raise
        store.submit_approval(
            task.task_id, "approve",
            expected_nonce="nonce-abc",
        )
        # Verify approval was queued
        queue = store._approval_queues[task.task_id]
        assert not queue.empty()

    def test_no_nonce_skips_validation(self, store: TaskStore) -> None:
        """When expected_nonce is None (research/v1.0 callers), skip nonce check."""
        task = store.create_task("research", "ramp")
        store.update_task(task.task_id, status=TaskStatus.PENDING_APPROVAL)
        # No expected_nonce → backward compatible, no error
        store.submit_approval(task.task_id, "approve")
        queue = store._approval_queues[task.task_id]
        assert not queue.empty()

    def test_queue_full_raises_instead_of_replacing(self, store: TaskStore) -> None:
        """Duplicate approval → ApprovalWindowError (not silent drain-and-replace)."""
        task = store.create_task("content_v13", "ramp")
        store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "topic_approval", "checkpoint_nonce": "nonce-abc"},
        )
        # First approval succeeds
        store.submit_approval(
            task.task_id, "approve",
            expected_nonce="nonce-abc",
        )
        # Second approval for same checkpoint → queue full
        with pytest.raises(ApprovalWindowError, match="queue full"):
            store.submit_approval(
                task.task_id, "approve",
                expected_nonce="nonce-abc",
            )

    def test_nonce_none_in_payload_mismatches_expected(self, store: TaskStore) -> None:
        """Task has no nonce in payload but endpoint sends one → mismatch."""
        task = store.create_task("content_v13", "ramp")
        store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "topic_approval"},  # no checkpoint_nonce
        )
        with pytest.raises(ApprovalWindowError, match="nonce mismatch"):
            store.submit_approval(
                task.task_id, "approve",
                expected_nonce="nonce-abc",
            )

    def test_audit_history_not_recorded_on_nonce_failure(self, store: TaskStore) -> None:
        """Nonce failure must happen BEFORE audit logging."""
        task = store.create_task("content_v13", "ramp")
        store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "topic_approval", "checkpoint_nonce": "nonce-abc"},
        )
        with pytest.raises(ApprovalWindowError):
            store.submit_approval(
                task.task_id, "approve",
                expected_nonce="nonce-WRONG",
            )
        # No audit record should have been created
        assert len(task.approval_history) == 0
