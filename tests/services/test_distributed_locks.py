"""Tests for Redis-backed distributed slug locks in DbTaskStore."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.db_task_store import DbTaskStore
from core.services.task_store import TaskConflictError
from core.shared_tools.task_status import TaskStatus


@pytest.fixture
def mock_session_factory() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_sync_redis() -> MagicMock:
    """Mock sync redis.Redis for lock operations."""
    r = MagicMock()
    r.set = MagicMock(return_value=True)  # SET NX succeeds
    r.get = MagicMock(return_value=None)  # No existing lock
    r.delete = MagicMock(return_value=1)
    # register_script returns a callable for Lua scripts
    mock_release_script = MagicMock(return_value=1)
    r.register_script = MagicMock(return_value=mock_release_script)
    return r


@pytest.fixture
def store_with_redis(mock_session_factory: AsyncMock, mock_sync_redis: MagicMock) -> DbTaskStore:
    """DbTaskStore with Redis enabled for locks."""
    return DbTaskStore(
        session_factory=mock_session_factory,
        max_concurrent=10,
        redis_client=mock_sync_redis,
    )


@pytest.fixture
def store_without_redis(mock_session_factory: AsyncMock) -> DbTaskStore:
    """DbTaskStore without Redis (in-memory fallback)."""
    return DbTaskStore(session_factory=mock_session_factory, max_concurrent=10)


# ── Acquire tests ──────────────────────────────────────────────────


class TestDistributedLockAcquire:
    def test_acquire_succeeds_via_redis_set_nx(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """SET NX EX returns True → no exception raised."""
        store_with_redis._acquire_redis_lock("content_v13:ramp", "task-abc")

        mock_sync_redis.set.assert_called_once()
        call_kwargs = mock_sync_redis.set.call_args
        assert call_kwargs[0][0] == "lock:content_v13:ramp"
        assert call_kwargs[0][1] == "task-abc"
        assert call_kwargs[1]["nx"] is True
        assert call_kwargs[1]["ex"] == 7200

    def test_acquire_raises_conflict_when_lock_held(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """SET NX returns False (lock held by another worker) → TaskConflictError."""
        mock_sync_redis.set.return_value = False

        with pytest.raises(TaskConflictError):
            store_with_redis._acquire_redis_lock("content_v13:ramp", "task-new")

    def test_acquire_slug_lock_uses_redis_when_available(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """acquire_slug_lock delegates to Redis when client is available."""
        store_with_redis.acquire_slug_lock("content_v13:ramp", task_id="task-abc")

        mock_sync_redis.set.assert_called_once()

    def test_acquire_slug_lock_fails_closed_on_redis_error(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Redis error → fail-closed (TaskConflictError, not in-memory fallback)."""
        mock_sync_redis.set.side_effect = ConnectionError("Redis down")

        with pytest.raises(TaskConflictError, match="Redis is unavailable"):
            store_with_redis.acquire_slug_lock("content_v13:ramp", task_id="task-abc")


# ── Release tests ──────────────────────────────────────────────────


class TestDistributedLockRelease:
    def test_release_uses_lua_compare_and_delete(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Release uses Lua script for ownership-safe delete."""
        # Simulate a lock was held
        store_with_redis._slug_locks["content_v13:ramp"] = "task-abc"

        store_with_redis.release_slug_lock("content_v13:ramp")

        # Lua release script should be called
        store_with_redis._release_script.assert_called_once()

    def test_release_clears_in_memory_too(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """release_slug_lock also removes from _slug_locks dict."""
        store_with_redis._slug_locks["content_v13:ramp"] = "task-abc"

        store_with_redis.release_slug_lock("content_v13:ramp")

        assert "content_v13:ramp" not in store_with_redis._slug_locks

    def test_release_without_stored_task_id_skips_redis(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """If no task_id in _slug_locks, Redis is not called (nothing to release)."""
        store_with_redis.release_slug_lock("content_v13:ramp")

        # Lua script should NOT be called
        store_with_redis._release_script.assert_not_called()


# ── Fallback tests ─────────────────────────────────────────────────


class TestDistributedLockFallback:
    def test_uses_in_memory_when_redis_is_none(
        self, store_without_redis: DbTaskStore
    ) -> None:
        """redis_client=None → existing in-memory dict behavior."""
        # Should not raise (no existing lock)
        store_without_redis.acquire_slug_lock("content_v13:ramp")

    def test_in_memory_conflict_detection_still_works(
        self, store_without_redis: DbTaskStore
    ) -> None:
        """In-memory lock detects conflicts when Redis is unavailable."""
        from api.tasks.models import PipelineTask

        # Simulate an existing running task
        task = PipelineTask(
            task_id="task-existing",
            pipeline="content_v13",
            company_slug="ramp",
            status=TaskStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store_without_redis._tasks["task-existing"] = task
        store_without_redis._slug_locks["content_v13:ramp"] = "task-existing"

        with pytest.raises(TaskConflictError):
            store_without_redis.acquire_slug_lock("content_v13:ramp")


# ── create_task integration ────────────────────────────────────────


class TestCreateTaskWithRedisLock:
    def test_create_task_acquires_redis_lock(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """create_task() acquires Redis lock with the new task_id."""
        with patch.object(store_with_redis, "_db_create", new_callable=AsyncMock):
            with patch("core.services.db_task_store.asyncio") as mock_asyncio:
                mock_asyncio.create_task = MagicMock()
                task = store_with_redis.create_task("content_v13", "ramp")

        # Redis SET NX should have been called with the generated task_id
        mock_sync_redis.set.assert_called_once()
        call_args = mock_sync_redis.set.call_args
        assert call_args[0][0] == "lock:content_v13:ramp"
        assert call_args[0][1] == task.task_id  # task_id as lock value


# ── Orphan lock cleanup ───────────────────────────────────────────


class TestOrphanLockCleanup:
    def test_cleanup_removes_locks_for_terminal_tasks(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Locks held by completed/failed tasks are removed on recovery."""
        from api.tasks.models import PipelineTask

        # Task completed but lock still in Redis
        task = PipelineTask(
            task_id="task-done",
            pipeline="content_v13",
            company_slug="ramp",
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store_with_redis._tasks["task-done"] = task

        # Mock SCAN to return one orphan lock
        mock_sync_redis.scan.return_value = (0, ["lock:content_v13:ramp"])
        mock_sync_redis.get.return_value = "task-done"

        cleaned = store_with_redis._cleanup_orphan_locks()

        assert cleaned == 1
        mock_sync_redis.delete.assert_called_once_with("lock:content_v13:ramp")

    def test_cleanup_keeps_locks_for_active_tasks(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Locks held by RUNNING tasks are NOT removed."""
        from api.tasks.models import PipelineTask

        task = PipelineTask(
            task_id="task-active",
            pipeline="content_v13",
            company_slug="ramp",
            status=TaskStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store_with_redis._tasks["task-active"] = task

        mock_sync_redis.scan.return_value = (0, ["lock:content_v13:ramp"])
        mock_sync_redis.get.return_value = "task-active"

        cleaned = store_with_redis._cleanup_orphan_locks()

        assert cleaned == 0
        mock_sync_redis.delete.assert_not_called()

    def test_cleanup_removes_locks_for_unknown_tasks(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Locks held by unknown task_ids (not in _tasks) are removed."""
        mock_sync_redis.scan.return_value = (0, ["lock:gap_analysis:ramp"])
        mock_sync_redis.get.return_value = "task-unknown-from-crashed-worker"

        cleaned = store_with_redis._cleanup_orphan_locks()

        assert cleaned == 1
        mock_sync_redis.delete.assert_called_once()
