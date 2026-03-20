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
