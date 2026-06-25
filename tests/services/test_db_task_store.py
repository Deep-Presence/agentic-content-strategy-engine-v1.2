"""Tests for DbTaskStore in-memory behavior.

These tests verify CRUD, slug locks, task handles, and approval
queues — all of which are in-memory operations. DB write-through is
intercepted by patching asyncio.create_task to be a no-op.
All tests are async to ensure a running event loop exists.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.models import PipelineTask, TaskStatus
from core.services.db_task_store import DbTaskStore
from core.services.task_store import TaskConflictError, TaskNotFoundError

# Patch asyncio.create_task at the module level where DbTaskStore uses it
_PATCH_TARGET = "core.services.db_task_store.asyncio.create_task"


@pytest.fixture
def store():
    """DbTaskStore with mocked session_factory (no real DB)."""
    mock_factory = MagicMock()
    return DbTaskStore(session_factory=mock_factory, max_concurrent=2)


class TestDbTaskStoreCRUD:
    """Create, get, update, list — all in-memory."""

    @pytest.mark.asyncio
    async def test_create_task(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("gap_analysis", "test-co")
        assert task.pipeline == "gap_analysis"
        assert task.company_slug == "test-co"
        assert task.effective_slug == "test-co"
        assert task.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_create_task_with_product_slug(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co", product_slug="widget")
        assert task.effective_slug == "test-co__widget"
        assert task.product_slug == "widget"

    @pytest.mark.asyncio
    async def test_create_task_with_workspace_id(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task(
                "gap_analysis",
                "second-co",
                workspace_id="11111111-1111-1111-1111-111111111111",
            )
        assert task.company_slug == "second-co"
        assert task.workspace_id == "11111111-1111-1111-1111-111111111111"

    @pytest.mark.asyncio
    async def test_get_task(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
        fetched = store.get_task(task.task_id)
        assert fetched.task_id == task.task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, store):
        with pytest.raises(TaskNotFoundError):
            store.get_task("nonexistent")

    @pytest.mark.asyncio
    async def test_update_task(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            updated = store.update_task(
                task.task_id,
                status=TaskStatus.COMPLETED,
                current_step="style_guide",
            )
        assert updated.status == TaskStatus.COMPLETED
        assert updated.current_step == "style_guide"

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, store):
        with pytest.raises(TaskNotFoundError):
            store.update_task("nonexistent", status=TaskStatus.FAILED)

    @pytest.mark.asyncio
    async def test_list_tasks_no_filter(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            store.create_task("research", "test-co")
            store.create_task("gap_analysis", "acme")
        all_tasks = store.list_tasks()
        assert len(all_tasks) == 2

    @pytest.mark.asyncio
    async def test_list_tasks_filter_pipeline(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            store.create_task("research", "test-co")
            store.create_task("gap_analysis", "acme")
        research = store.list_tasks(pipeline="research")
        assert len(research) == 1
        assert research[0].pipeline == "research"

    @pytest.mark.asyncio
    async def test_list_tasks_filter_status(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        completed = store.list_tasks(status="completed")
        assert len(completed) == 1


class TestDbTaskStoreSlugLocks:
    """Slug lock acquire/release behavior."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
        # Lock held — second create should fail
        with pytest.raises(TaskConflictError):
            store.create_task("research", "test-co")
        # Release and retry
        store.release_slug_lock("research:test-co")
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task2 = store.create_task("research", "test-co")
        assert task2.task_id != task.task_id

    @pytest.mark.asyncio
    async def test_stale_lock_cleared(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            # Mark completed — lock becomes stale
            store.update_task(task.task_id, status=TaskStatus.COMPLETED)
            # Should succeed (stale lock auto-cleared)
            task2 = store.create_task("research", "test-co")
        assert task2.task_id != task.task_id


class TestDbTaskStoreHandles:
    """Task handle registration and cancellation."""

    @pytest.mark.asyncio
    async def test_register_and_cancel(self, store):
        mock_handle = MagicMock()
        mock_handle.done.return_value = False
        store.register_task_handle("t1", mock_handle)
        assert store.cancel_task_handle("t1") is True
        mock_handle.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self, store):
        assert store.cancel_task_handle("nope") is False

    @pytest.mark.asyncio
    async def test_remove_handle(self, store):
        store.register_task_handle("t1", MagicMock())
        store.remove_task_handle("t1")
        assert store.cancel_task_handle("t1") is False


class TestDbTaskStoreApproval:
    """HITL approval queue (in-memory)."""

    @pytest.mark.asyncio
    async def test_submit_then_wait(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            store.update_task(
                task.task_id,
                status=TaskStatus.PENDING_APPROVAL,
                approval_payload={"stage": "company"},
            )
            store.submit_approval(task.task_id, decision="approve", stage="company")
        result = await store.wait_for_approval(task.task_id, timeout=1.0)
        assert result["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_wait_then_submit(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            store.update_task(
                task.task_id,
                status=TaskStatus.PENDING_APPROVAL,
                approval_payload={"stage": "persona"},
            )

        async def delayed_submit():
            await asyncio.sleep(0.05)
            with patch(_PATCH_TARGET, return_value=MagicMock()):
                store.submit_approval(task.task_id, decision="revise", revision_note="Fix tone")

        asyncio.create_task(delayed_submit())
        result = await store.wait_for_approval(task.task_id, timeout=2.0)
        assert result["decision"] == "revise"
        assert result["revision_note"] == "Fix tone"

    @pytest.mark.asyncio
    async def test_approval_timeout(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
        result = await store.wait_for_approval(task.task_id, timeout=0.05)
        assert result["decision"] == "reject"
        assert "timed out" in result["revision_note"]

    @pytest.mark.asyncio
    async def test_submit_approval_not_found(self, store):
        with pytest.raises(TaskNotFoundError):
            store.submit_approval("nonexistent", decision="approve")

    @pytest.mark.asyncio
    async def test_approval_recorded_in_history(self, store):
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            store.update_task(
                task.task_id,
                status=TaskStatus.PENDING_APPROVAL,
                approval_payload={"stage": "company"},
            )
            store.submit_approval(task.task_id, decision="approve", stage="company")
        fetched = store.get_task(task.task_id)
        assert len(fetched.approval_history) == 1
        assert fetched.approval_history[0].decision == "approve"


# ── Session 3: DB Durability & Recovery ──────────────────────────────


class TestDbTaskStoreDurableWrites:
    """Tests for Fix 1d: ensure_created, flush_terminal, rollback_create, drain_pending."""

    @pytest.mark.asyncio
    async def test_create_task_tracks_pending_write(self, store):
        """After create_task(), _pending_creates[task_id] should contain a task."""
        with patch(_PATCH_TARGET, return_value=MagicMock()) as mock_ct:
            task = store.create_task("gap_analysis", "test-co")
        assert task.task_id in store._pending_creates

    @pytest.mark.asyncio
    async def test_ensure_created_awaits_and_removes_pending(self, store):
        """ensure_created() awaits the pending future and removes it from the dict."""
        async def noop():
            pass

        store._pending_creates["task-001"] = asyncio.create_task(noop())
        await store.ensure_created("task-001")
        assert "task-001" not in store._pending_creates

    @pytest.mark.asyncio
    async def test_ensure_created_raises_on_db_failure(self, store):
        """ensure_created() propagates exceptions from the DB write."""
        async def failing():
            raise RuntimeError("DB down")

        store._pending_creates["task-001"] = asyncio.create_task(failing())
        await asyncio.sleep(0)  # let the task complete
        with pytest.raises(RuntimeError, match="DB down"):
            await store.ensure_created("task-001")

    @pytest.mark.asyncio
    async def test_ensure_created_noop_when_no_pending(self, store):
        """ensure_created() should not raise when task_id has no pending write."""
        await store.ensure_created("nonexistent-id")
        # No exception means success

    @pytest.mark.asyncio
    async def test_terminal_status_tracked_in_pending_terminals(self, store):
        """Terminal status updates (COMPLETED, FAILED, CANCELLED) are tracked in _pending_terminals."""
        for status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            with patch(_PATCH_TARGET, return_value=MagicMock()):
                task = store.create_task("research", f"co-{status.value}")
                store.update_task(task.task_id, status=status)
            assert task.task_id in store._pending_terminals

    @pytest.mark.asyncio
    async def test_non_terminal_update_not_tracked(self, store):
        """Non-terminal updates (e.g., progress_pct) should NOT appear in _pending_terminals."""
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
            store.update_task(task.task_id, progress_pct=50.0)
        assert task.task_id not in store._pending_terminals

    @pytest.mark.asyncio
    async def test_flush_terminal_awaits_and_removes(self, store):
        """flush_terminal() awaits the pending future and removes it."""
        async def noop():
            pass

        store._pending_terminals["task-001"] = asyncio.create_task(noop())
        await store.flush_terminal("task-001")
        assert "task-001" not in store._pending_terminals

    @pytest.mark.asyncio
    async def test_flush_terminal_swallows_exception(self, store):
        """flush_terminal() swallows exceptions (best-effort) so cleanup continues."""
        async def failing():
            raise RuntimeError("DB down")

        store._pending_terminals["task-001"] = asyncio.create_task(failing())
        await asyncio.sleep(0)  # let the task complete
        # Should NOT raise
        await store.flush_terminal("task-001")
        assert "task-001" not in store._pending_terminals

    @pytest.mark.asyncio
    async def test_rollback_create_cleans_up(self, store):
        """rollback_create() removes task from memory and releases slug lock."""
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task = store.create_task("research", "test-co")
        store.rollback_create(task.task_id)

        # Task should be gone
        with pytest.raises(TaskNotFoundError):
            store.get_task(task.task_id)

        # Slug lock released — can create again
        with patch(_PATCH_TARGET, return_value=MagicMock()):
            task2 = store.create_task("research", "test-co")
        assert task2.task_id != task.task_id

    @pytest.mark.asyncio
    async def test_drain_pending_awaits_all(self, store):
        """drain_pending() awaits all pending creates and terminals, then clears both dicts."""
        async def noop():
            pass

        store._pending_creates["c1"] = asyncio.create_task(noop())
        store._pending_creates["c2"] = asyncio.create_task(noop())
        store._pending_terminals["t1"] = asyncio.create_task(noop())

        await store.drain_pending()
        assert len(store._pending_creates) == 0
        assert len(store._pending_terminals) == 0


class TestDbTaskStoreWorkerRecovery:
    """Tests for Fix 1e: worker_id, scoped recovery, scoped semaphore cleanup."""

    def test_worker_id_set_explicitly(self):
        """Explicit worker_id is stored as-is."""
        mock_factory = MagicMock()
        s = DbTaskStore(session_factory=mock_factory, worker_id="host1:1234")
        assert s._worker_id == "host1:1234"

    def test_worker_id_auto_generated(self):
        """Auto-generated worker_id contains ':' and the current PID."""
        import os

        mock_factory = MagicMock()
        s = DbTaskStore(session_factory=mock_factory)
        assert ":" in s._worker_id
        assert str(os.getpid()) in s._worker_id

    @pytest.mark.asyncio
    async def test_scoped_semaphore_cleanup_removes_specific_ids(self):
        """_cleanup_semaphore_entries releases each task_id from the semaphore."""
        mock_factory = MagicMock()
        store = DbTaskStore(session_factory=mock_factory)
        mock_sem = MagicMock()
        store._redis_semaphore = mock_sem

        cleaned = store._cleanup_semaphore_entries(["task-1", "task-2"])

        assert cleaned == 2
        assert mock_sem.release.call_count == 2
        mock_sem.release.assert_any_call("task-1")
        mock_sem.release.assert_any_call("task-2")

    @pytest.mark.asyncio
    async def test_scoped_semaphore_cleanup_empty_list(self):
        """Empty list returns 0 and release is not called."""
        mock_factory = MagicMock()
        store = DbTaskStore(session_factory=mock_factory)
        mock_sem = MagicMock()
        store._redis_semaphore = mock_sem

        cleaned = store._cleanup_semaphore_entries([])

        assert cleaned == 0
        mock_sem.release.assert_not_called()

    @pytest.mark.asyncio
    async def test_scoped_semaphore_cleanup_tolerates_individual_errors(self):
        """If release raises on one call, others still proceed."""
        mock_factory = MagicMock()
        store = DbTaskStore(session_factory=mock_factory)
        mock_sem = MagicMock()
        mock_sem.release.side_effect = [RuntimeError("boom"), None]
        store._redis_semaphore = mock_sem

        cleaned = store._cleanup_semaphore_entries(["task-1", "task-2"])

        assert cleaned == 1
        assert mock_sem.release.call_count == 2

    @pytest.mark.asyncio
    async def test_drain_pending_handles_mixed_success_failure(self, store):
        """drain_pending() doesn't raise when some futures fail, and clears both dicts."""
        async def noop():
            pass

        async def failing():
            raise RuntimeError("DB down")

        store._pending_creates["ok"] = asyncio.create_task(noop())
        store._pending_terminals["fail"] = asyncio.create_task(failing())

        # Should NOT raise
        await store.drain_pending()
        assert len(store._pending_creates) == 0
        assert len(store._pending_terminals) == 0
