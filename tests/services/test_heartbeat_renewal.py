"""Tests for HITL lease renewal heartbeat in DbTaskStore + RedisSemaphore.

Covers:
- RedisSemaphore.renew() — Lua ZSCORE+ZADD atomic renewal
- DbTaskStore._renew_leases() — lock + semaphore renewal, parallel skip, errors
- BRPOP loop integration — heartbeat fires at correct intervals, stops on fallback
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.models import PipelineTask
from core.redis_semaphore import RedisSemaphore, _RENEW_LUA
from core.services.db_task_store import DbTaskStore
from core.shared_tools.task_status import TaskStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sync_redis() -> MagicMock:
    """Mock sync redis.Redis for heartbeat operations."""
    r = MagicMock()
    r.brpop = MagicMock(return_value=None)
    r.lpush = MagicMock(return_value=1)
    r.expire = MagicMock(return_value=True)
    r.get = MagicMock(return_value=None)
    r.set = MagicMock(return_value=True)
    r.delete = MagicMock(return_value=1)
    # register_script returns callable mocks for Lua scripts
    mock_release_script = MagicMock(return_value=1)
    mock_renew_lock_script = MagicMock(return_value=1)
    mock_acquire_script = MagicMock(return_value=1)
    mock_renew_sem_script = MagicMock(return_value=1)
    # Return different script mocks in order of registration:
    # 1) _RELEASE_LOCK_LUA, 2) _RENEW_LOCK_LUA, 3) RedisSemaphore._ACQUIRE_LUA,
    # 4) RedisSemaphore._RENEW_LUA
    r.register_script = MagicMock(
        side_effect=[
            mock_release_script,
            mock_renew_lock_script,
            mock_acquire_script,
            mock_renew_sem_script,
        ]
    )
    return r


@pytest.fixture
def mock_session_factory() -> MagicMock:
    return MagicMock()


@pytest.fixture
def store_with_redis(
    mock_session_factory: MagicMock, mock_sync_redis: MagicMock
) -> DbTaskStore:
    """DbTaskStore with Redis enabled."""
    return DbTaskStore(
        session_factory=mock_session_factory,
        max_concurrent=3,
        redis_client=mock_sync_redis,
    )


def _seed_task(
    store: DbTaskStore,
    task_id: str = "task-001",
    pipeline: str = "gap_analysis",
    company_slug: str = "test-co",
    effective_slug: str = "test-co",
    with_lock: bool = True,
) -> PipelineTask:
    """Insert a task into the store's in-memory dict, optionally with slug lock."""
    task = PipelineTask(
        task_id=task_id,
        pipeline=pipeline,
        company_slug=company_slug,
        effective_slug=effective_slug,
        status=TaskStatus.PENDING_APPROVAL,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    store._tasks[task_id] = task
    if with_lock:
        lock_slug = f"{pipeline}:{effective_slug}"
        store._slug_locks[lock_slug] = task_id
    return task


async def _sync_to_thread(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread that calls fn synchronously."""
    return fn(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════
# 1-3: RedisSemaphore.renew() tests
# ═══════════════════════════════════════════════════════════════════════


class TestSemaphoreRenew:
    def test_renew_updates_score(self, mock_sync_redis: MagicMock) -> None:
        """renew() calls Lua script with correct args and returns True on success."""
        mock_renew = MagicMock(return_value=1)
        mock_sync_redis.register_script = MagicMock(
            side_effect=[MagicMock(), mock_renew]  # acquire, renew
        )
        sem = RedisSemaphore(mock_sync_redis, "pipelines", max_concurrent=3)

        result = sem.renew("task-001")

        assert result is True
        mock_renew.assert_called_once()
        call_args = mock_renew.call_args
        assert call_args.kwargs["keys"] == ["semaphore:pipelines"]
        assert call_args.kwargs["args"][0] == "task-001"
        # Second arg is timestamp (float)
        assert isinstance(call_args.kwargs["args"][1], float)

    def test_renew_returns_false_when_not_member(
        self, mock_sync_redis: MagicMock
    ) -> None:
        """renew() returns False when Lua script returns 0 (member not found)."""
        mock_renew = MagicMock(return_value=0)
        mock_sync_redis.register_script = MagicMock(
            side_effect=[MagicMock(), mock_renew]
        )
        sem = RedisSemaphore(mock_sync_redis, "pipelines", max_concurrent=3)

        result = sem.renew("task-missing")

        assert result is False

    def test_renew_script_registered_on_init(
        self, mock_sync_redis: MagicMock
    ) -> None:
        """_RENEW_LUA is registered as the second script in __init__."""
        mock_sync_redis.register_script = MagicMock(
            side_effect=[MagicMock(), MagicMock()]
        )
        sem = RedisSemaphore(mock_sync_redis, "pipelines", max_concurrent=3)

        # Second call to register_script should be _RENEW_LUA
        calls = mock_sync_redis.register_script.call_args_list
        assert len(calls) == 2
        assert _RENEW_LUA in calls[1].args[0]


# ═══════════════════════════════════════════════════════════════════════
# 4-10: DbTaskStore._renew_leases() tests
# ═══════════════════════════════════════════════════════════════════════


class TestRenewLeases:
    def test_renew_leases_refreshes_lock_via_lua(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """Lock renewal calls Lua compare-and-expire script with correct args."""
        _seed_task(store_with_redis, "task-001")

        store_with_redis._renew_leases("task-001")

        store_with_redis._renew_lock_script.assert_called_once_with(
            keys=["lock:gap_analysis:test-co"],
            args=["task-001", 7200],
        )

    def test_renew_leases_refreshes_semaphore(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """Semaphore renewal calls renew() on the RedisSemaphore instance."""
        _seed_task(store_with_redis, "task-001")

        # Mock the semaphore's renew method directly
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        store_with_redis._renew_leases("task-001")

        store_with_redis._redis_semaphore.renew.assert_called_once_with("task-001")

    def test_renew_leases_refreshes_company_content_engine_semaphore(
        self, mock_session_factory: MagicMock
    ) -> None:
        """CE tasks renew the company-scoped semaphore instead of the shared pool."""
        mock_sync_redis = MagicMock()
        mock_sync_redis.brpop = MagicMock(return_value=None)
        mock_sync_redis.delete = MagicMock(return_value=1)
        mock_sync_redis.register_script = MagicMock(
            side_effect=lambda _script: MagicMock(return_value=1)
        )
        store = DbTaskStore(
            session_factory=mock_session_factory,
            max_concurrent=3,
            redis_client=mock_sync_redis,
        )
        mock_sync_redis.register_script = MagicMock(
            side_effect=lambda _script: MagicMock(return_value=1)
        )
        _seed_task(
            store,
            "task-001",
            pipeline="content_v13",
            company_slug="test-co",
            effective_slug="test-co__widget",
            with_lock=False,
        )
        store.pipeline_semaphore(
            "task-001",
            pool="content_engine",
            company_slug="test-co",
        )
        store._redis_semaphore.renew = MagicMock(return_value=True)
        store._content_engine_semaphores["test-co"].renew = MagicMock(return_value=True)

        store._renew_leases("task-001")

        store._content_engine_semaphores["test-co"].renew.assert_called_once_with("task-001")
        store._redis_semaphore.renew.assert_not_called()

    def test_renew_leases_skips_lock_for_parallel_task(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """Tasks without slug lock (allow_parallel=True) skip lock renewal."""
        _seed_task(store_with_redis, "task-001", with_lock=False)
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        store_with_redis._renew_leases("task-001")

        # Lock script should NOT be called
        store_with_redis._renew_lock_script.assert_not_called()
        # Semaphore should still be renewed
        store_with_redis._redis_semaphore.renew.assert_called_once_with("task-001")

    def test_renew_leases_lock_ownership_lost(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """Lua script returns 0 (ownership lost) → warning logged, no exception."""
        _seed_task(store_with_redis, "task-001")
        store_with_redis._renew_lock_script.return_value = 0
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        # Should not raise
        store_with_redis._renew_leases("task-001")

        store_with_redis._renew_lock_script.assert_called_once()

    def test_renew_leases_survives_redis_error(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """Redis error during renewal → logged, not raised."""
        _seed_task(store_with_redis, "task-001")
        store_with_redis._renew_lock_script.side_effect = ConnectionError("down")
        store_with_redis._redis_semaphore.renew = MagicMock(
            side_effect=ConnectionError("down")
        )

        # Should not raise
        store_with_redis._renew_leases("task-001")

    def test_renew_leases_skips_unknown_task(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """Unknown task_id → no Redis calls."""
        store_with_redis._renew_leases("nonexistent")

        store_with_redis._renew_lock_script.assert_not_called()

    def test_renew_leases_skips_without_redis(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Store without Redis → _renew_leases is a no-op."""
        store = DbTaskStore(session_factory=mock_session_factory, max_concurrent=3)
        task = PipelineTask(
            task_id="task-001",
            pipeline="content_v13",
            company_slug="test-co",
            effective_slug="test-co",
            status=TaskStatus.PENDING_APPROVAL,
        )
        store._tasks["task-001"] = task

        # Should not raise (no Redis, immediate return)
        store._renew_leases("task-001")


# ═══════════════════════════════════════════════════════════════════════
# 11-15: BRPOP loop integration tests
# ═══════════════════════════════════════════════════════════════════════


class TestHeartbeatBrpopIntegration:
    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_wait_for_approval_releases_and_reacquires_content_engine_slot(
        self,
        _mock_to_thread: MagicMock,
        mock_session_factory: MagicMock,
        mock_sync_redis: MagicMock,
    ) -> None:
        """CE HITL waits should free the company slot until approval resumes work."""
        store = DbTaskStore(
            session_factory=mock_session_factory,
            max_concurrent=3,
            redis_client=mock_sync_redis,
        )
        mock_sync_redis.register_script = MagicMock(
            side_effect=lambda _script: MagicMock(return_value=1)
        )
        _seed_task(
            store,
            "task-001",
            pipeline="td_content",
            company_slug="test-co",
            effective_slug="test-co__widget",
            with_lock=False,
        )
        sem_ctx = store.pipeline_semaphore(
            "task-001",
            pool="content_engine",
            company_slug="test-co",
        )
        sem = store._content_engine_semaphores["test-co"]
        sem.try_acquire = MagicMock(return_value=True)
        sem.release = MagicMock()

        approval_payload = json.dumps({"decision": "approve"})
        mock_sync_redis.brpop.side_effect = [("approval:task-001", approval_payload)]

        async with sem_ctx:
            result = await store.wait_for_approval("task-001")

        assert result["decision"] == "approve"
        assert sem.try_acquire.call_count == 2
        assert sem.release.call_count == 2

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_heartbeat_fires_during_brpop_loop(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """Heartbeat fires once after 60 iterations of BRPOP returning None."""
        _seed_task(store_with_redis, "task-001")
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        approval_payload = json.dumps({"decision": "approve"})
        # 64 None returns (no approval), then approval on 65th
        brpop_returns = [None] * 64 + [("approval:task-001", approval_payload)]
        mock_sync_redis.brpop.side_effect = brpop_returns

        result = await store_with_redis.wait_for_approval("task-001")

        assert result["decision"] == "approve"
        # Heartbeat should have fired once (at iteration 60)
        store_with_redis._renew_lock_script.assert_called_once_with(
            keys=["lock:gap_analysis:test-co"],
            args=["task-001", 7200],
        )
        store_with_redis._redis_semaphore.renew.assert_called_once_with("task-001")

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_heartbeat_does_not_fire_before_interval(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """Approval arrives before heartbeat interval → no renewal calls."""
        _seed_task(store_with_redis, "task-001")
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        approval_payload = json.dumps({"decision": "approve"})
        # 4 None returns, then approval on 5th
        brpop_returns = [None] * 4 + [("approval:task-001", approval_payload)]
        mock_sync_redis.brpop.side_effect = brpop_returns

        result = await store_with_redis.wait_for_approval("task-001")

        assert result["decision"] == "approve"
        # Heartbeat should NOT have fired (only 5 iterations < 60)
        store_with_redis._renew_lock_script.assert_not_called()
        store_with_redis._redis_semaphore.renew.assert_not_called()

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_heartbeat_multiple_renewals(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """Heartbeat fires 3 times across 185 BRPOP iterations."""
        _seed_task(store_with_redis, "task-001")
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        approval_payload = json.dumps({"decision": "reject"})
        # 184 None returns, then approval on 185th
        brpop_returns = [None] * 184 + [("approval:task-001", approval_payload)]
        mock_sync_redis.brpop.side_effect = brpop_returns

        result = await store_with_redis.wait_for_approval("task-001")

        assert result["decision"] == "reject"
        # Heartbeat should fire at iterations 60, 120, 180 → 3 times
        assert store_with_redis._renew_lock_script.call_count == 3
        assert store_with_redis._redis_semaphore.renew.call_count == 3

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.sleep", new_callable=AsyncMock)
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_heartbeat_stops_on_redis_gave_up(
        self,
        _mock_to_thread: MagicMock,
        _mock_sleep: AsyncMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """After 10 consecutive BRPOP errors → Queue fallback, no more heartbeats."""
        _seed_task(store_with_redis, "task-001")
        store_with_redis._redis_semaphore.renew = MagicMock(return_value=True)

        # 10 consecutive BRPOP errors → triggers redis_gave_up
        mock_sync_redis.brpop.side_effect = ConnectionError("Redis down")

        # Pre-seed the fallback queue so we don't hang
        import asyncio
        q = asyncio.Queue(maxsize=1)
        await q.put({"decision": "reject", "revision_note": "fallback"})
        store_with_redis._approval_queues["task-001"] = q

        result = await store_with_redis.wait_for_approval("task-001", timeout=120)

        assert result["decision"] == "reject"
        # Only 10 BRPOP attempts (< 60 interval), so heartbeat never fired
        store_with_redis._renew_lock_script.assert_not_called()
        store_with_redis._redis_semaphore.renew.assert_not_called()

    def test_renew_lock_script_registered_on_init(
        self, store_with_redis: DbTaskStore
    ) -> None:
        """_RENEW_LOCK_LUA script is registered during __init__."""
        assert store_with_redis._renew_lock_script is not None
        # It should be a callable mock (from register_script)
        assert callable(store_with_redis._renew_lock_script)
