"""Tests for Redis-backed HITL approval queues in DbTaskStore.

Covers:
- wait_for_approval via Redis BRPOP (data, timeout, cleanup)
- submit_approval via Redis LPUSH (push, flag, duplicate, nonce)
- update_task nonce management (write, clear)
- Fallback to asyncio.Queue when Redis unavailable
- Full cycles: submit-before-wait, wait-before-submit, multi-checkpoint
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.models import PipelineTask
from core.services.db_task_store import DbTaskStore
from core.services.task_store import ApprovalWindowError
from core.shared_tools.task_status import TaskStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session_factory() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_sync_redis() -> MagicMock:
    """Mock sync redis.Redis for approval queue operations."""
    r = MagicMock()
    r.brpop = MagicMock(return_value=None)  # Default: timeout
    r.lpush = MagicMock(return_value=1)
    r.expire = MagicMock(return_value=True)
    r.get = MagicMock(return_value=None)
    r.set = MagicMock(return_value=True)  # SET NX succeeds
    r.delete = MagicMock(return_value=1)
    # register_script for Lua lock script
    r.register_script = MagicMock(return_value=MagicMock(return_value=1))
    return r


@pytest.fixture
def store_with_redis(
    mock_session_factory: AsyncMock, mock_sync_redis: MagicMock
) -> DbTaskStore:
    """DbTaskStore with Redis enabled."""
    return DbTaskStore(
        session_factory=mock_session_factory,
        max_concurrent=10,
        redis_client=mock_sync_redis,
    )


@pytest.fixture
def store_without_redis(mock_session_factory: AsyncMock) -> DbTaskStore:
    """DbTaskStore without Redis (asyncio.Queue fallback)."""
    return DbTaskStore(session_factory=mock_session_factory, max_concurrent=10)


def _seed_task(
    store: DbTaskStore,
    task_id: str = "task-001",
    approval_payload: dict | None = None,
) -> PipelineTask:
    """Insert a task directly into the store's in-memory dict."""
    task = PipelineTask(
        task_id=task_id,
        pipeline="content_v13",
        company_slug="test-co",
        status=TaskStatus.PENDING_APPROVAL,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    if approval_payload is not None:
        task.approval_payload = approval_payload
    store._tasks[task_id] = task
    return task


async def _sync_to_thread(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread that calls fn synchronously."""
    return fn(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════
# 1-3: wait_for_approval via Redis BRPOP
# ═══════════════════════════════════════════════════════════════════════


class TestWaitForApprovalRedis:
    """Tests for Redis BRPOP-based wait_for_approval."""

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_wait_returns_data_from_brpop(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """BRPOP returns data → parsed JSON dict returned."""
        payload = {"decision": "approve", "topic_decision": "approve"}
        mock_sync_redis.brpop.return_value = (
            "approval:task-001",
            json.dumps(payload),
        )

        result = await store_with_redis.wait_for_approval("task-001")

        assert result == payload
        # Polling loop uses 1s BRPOP intervals (not full timeout)
        mock_sync_redis.brpop.assert_called_once_with(
            "approval:task-001", timeout=1
        )

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_wait_returns_reject_on_timeout(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """BRPOP returns None (timeout) → auto-reject dict."""
        mock_sync_redis.brpop.return_value = None

        result = await store_with_redis.wait_for_approval("task-001", timeout=2)

        assert result["decision"] == "reject"
        assert "timed out" in result["revision_note"]

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_wait_cleans_up_keys(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """After consumption, all 3 approval keys are deleted."""
        mock_sync_redis.brpop.return_value = (
            "approval:task-001",
            '{"decision":"approve"}',
        )

        await store_with_redis.wait_for_approval("task-001")

        mock_sync_redis.delete.assert_called_once_with(
            "approval:task-001",
            "approval:flag:task-001",
            "approval:nonce:task-001",
        )


# ═══════════════════════════════════════════════════════════════════════
# 4-7: submit_approval via Redis
# ═══════════════════════════════════════════════════════════════════════


class TestSubmitApprovalRedis:
    """Tests for Redis LPUSH-based submit_approval."""

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_submit_pushes_to_redis(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Payload is LPUSH'd to approval:{task_id} with TTL."""
        _seed_task(store_with_redis, "task-001")

        store_with_redis.submit_approval("task-001", decision="approve")

        mock_sync_redis.lpush.assert_called_once()
        key, raw = mock_sync_redis.lpush.call_args[0]
        assert key == "approval:task-001"
        assert json.loads(raw)["decision"] == "approve"
        mock_sync_redis.expire.assert_called_once_with("approval:task-001", 86400)

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_submit_sets_duplicate_flag(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """SET NX on approval:flag:{task_id} called."""
        _seed_task(store_with_redis, "task-001")

        store_with_redis.submit_approval("task-001", decision="approve")

        # Find the SET call for the flag key
        flag_calls = [
            c for c in mock_sync_redis.set.call_args_list
            if c[0][0] == "approval:flag:task-001"
        ]
        assert len(flag_calls) == 1
        call_kwargs = flag_calls[0][1]
        assert call_kwargs.get("nx") is True
        assert call_kwargs.get("ex") == 86400

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_submit_raises_on_duplicate(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """SET NX returns False → ApprovalWindowError."""
        _seed_task(store_with_redis, "task-001")
        # Flag already set
        mock_sync_redis.set.return_value = False

        with pytest.raises(ApprovalWindowError, match="already submitted"):
            store_with_redis.submit_approval("task-001", decision="approve")

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_submit_validates_nonce_from_redis(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Nonce read from Redis GET; mismatch raises ApprovalWindowError."""
        _seed_task(
            store_with_redis,
            "task-001",
            approval_payload={"checkpoint_nonce": "nonce-abc", "stage": "topic_approval"},
        )
        mock_sync_redis.get.return_value = "nonce-abc"

        # Match → succeeds
        store_with_redis.submit_approval(
            "task-001", decision="approve", expected_nonce="nonce-abc"
        )

        # Reset for mismatch test
        mock_sync_redis.set.return_value = True  # flag check passes
        mock_sync_redis.get.return_value = "nonce-abc"

        with pytest.raises(ApprovalWindowError, match="nonce mismatch"):
            store_with_redis.submit_approval(
                "task-001", decision="approve", expected_nonce="nonce-xyz"
            )


# ═══════════════════════════════════════════════════════════════════════
# 8-9: update_task nonce management
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateTaskNonceRedis:
    """Tests for nonce write/clear in update_task."""

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_writes_nonce_on_payload_set(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Setting approval_payload with nonce → SET approval:nonce:{tid}."""
        _seed_task(store_with_redis, "task-001")

        store_with_redis.update_task(
            "task-001",
            approval_payload={
                "checkpoint_nonce": "nonce-abc",
                "stage": "topic_approval",
            },
        )

        # Find the SET call for the nonce key
        nonce_calls = [
            c for c in mock_sync_redis.set.call_args_list
            if len(c[0]) >= 1 and c[0][0] == "approval:nonce:task-001"
        ]
        assert len(nonce_calls) == 1
        assert nonce_calls[0][0][1] == "nonce-abc"
        assert nonce_calls[0][1].get("ex") == 86400

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_clears_nonce_and_flag_on_payload_clear(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Clearing approval_payload → DELETE nonce + flag keys."""
        _seed_task(
            store_with_redis,
            "task-001",
            approval_payload={"checkpoint_nonce": "nonce-abc"},
        )

        store_with_redis.update_task("task-001", approval_payload=None)

        mock_sync_redis.delete.assert_called_once_with(
            "approval:nonce:task-001",
            "approval:flag:task-001",
        )


# ═══════════════════════════════════════════════════════════════════════
# 10: Fallback to asyncio.Queue
# ═══════════════════════════════════════════════════════════════════════


class TestApprovalFallback:
    """asyncio.Queue used when Redis unavailable."""

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    async def test_asyncio_queue_when_no_redis(
        self, store_without_redis: DbTaskStore
    ) -> None:
        """Without Redis, submit → wait cycle uses asyncio.Queue."""
        _seed_task(store_without_redis, "task-001")

        # Submit first
        store_without_redis.submit_approval("task-001", decision="approve")

        # Wait should return immediately (data already in queue)
        result = await store_without_redis.wait_for_approval("task-001")
        assert result["decision"] == "approve"


# ═══════════════════════════════════════════════════════════════════════
# 11-13: Full cycle tests
# ═══════════════════════════════════════════════════════════════════════


class TestApprovalFullCycle:
    """End-to-end cycle tests with Redis."""

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_submit_before_wait(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """Submit pushes to list; wait consumes it immediately."""
        _seed_task(store_with_redis, "task-001")
        payload = {"decision": "approve", "topic_decision": "approve"}

        # Submit writes to Redis list
        store_with_redis.submit_approval(
            "task-001", decision="approve", approval_data=payload
        )

        # Configure brpop to return what was pushed
        mock_sync_redis.brpop.return_value = (
            "approval:task-001",
            json.dumps(payload),
        )

        result = await store_with_redis.wait_for_approval("task-001")
        assert result == payload

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_wait_before_submit(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """Wait starts blocking; submit unblocks it with data."""
        _seed_task(store_with_redis, "task-001")
        payload = {"decision": "reject", "revision_note": "needs work"}

        # Simulate: brpop blocks then returns data (mocked as immediate)
        mock_sync_redis.brpop.return_value = (
            "approval:task-001",
            json.dumps(payload),
        )

        result = await store_with_redis.wait_for_approval("task-001")
        assert result == payload
        assert result["decision"] == "reject"

    @pytest.mark.asyncio
    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    @patch("core.services.db_task_store.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_multi_checkpoint_cycle(
        self,
        _mock_to_thread: MagicMock,
        store_with_redis: DbTaskStore,
        mock_sync_redis: MagicMock,
    ) -> None:
        """HITL-1 approve → clear payload → HITL-2 approve works (flag reset)."""
        _seed_task(store_with_redis, "task-001")

        # --- HITL-1: set nonce, submit, wait, clear ---
        mock_sync_redis.get.return_value = "nonce-1"
        mock_sync_redis.set.return_value = True

        store_with_redis.update_task(
            "task-001",
            approval_payload={"checkpoint_nonce": "nonce-1", "stage": "hitl_1"},
        )
        store_with_redis.submit_approval(
            "task-001", decision="approve", expected_nonce="nonce-1"
        )

        mock_sync_redis.brpop.return_value = (
            "approval:task-001",
            '{"decision":"approve"}',
        )
        r1 = await store_with_redis.wait_for_approval("task-001")
        assert r1["decision"] == "approve"

        # Clear payload between checkpoints (resets flag + nonce)
        mock_sync_redis.delete.reset_mock()
        store_with_redis.update_task("task-001", approval_payload=None)
        mock_sync_redis.delete.assert_called_once_with(
            "approval:nonce:task-001", "approval:flag:task-001"
        )

        # --- HITL-2: new nonce, submit should succeed ---
        mock_sync_redis.get.return_value = "nonce-2"
        mock_sync_redis.set.return_value = True  # Flag SET NX succeeds again

        store_with_redis.update_task(
            "task-001",
            approval_payload={"checkpoint_nonce": "nonce-2", "stage": "hitl_2"},
        )
        # This should NOT raise "already submitted"
        store_with_redis.submit_approval(
            "task-001", decision="approve", expected_nonce="nonce-2"
        )

        mock_sync_redis.brpop.return_value = (
            "approval:task-001",
            '{"decision":"approve"}',
        )
        r2 = await store_with_redis.wait_for_approval("task-001")
        assert r2["decision"] == "approve"


# ═══════════════════════════════════════════════════════════════════════
# 14-19: LPUSH failure handling (Issue 1a)
# ═══════════════════════════════════════════════════════════════════════


class TestSubmitApprovalLpushFailure:
    """Tests for submit_approval behaviour when Redis LPUSH fails."""

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_lpush_failure_raises_approval_delivery_error(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """LPUSH raises → ApprovalDeliveryError raised, flag cleared for retry."""
        from api.tasks.exceptions import ApprovalDeliveryError

        _seed_task(store_with_redis, "task-001")
        mock_sync_redis.lpush.side_effect = ConnectionError("Redis down")

        with pytest.raises(ApprovalDeliveryError, match="task-001"):
            store_with_redis.submit_approval("task-001", decision="approve")

        # Flag should be cleared so user can retry
        mock_sync_redis.delete.assert_called_once_with("approval:flag:task-001")

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_lpush_failure_does_not_record_approval_history(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Failed LPUSH should NOT create a phantom approval history entry."""
        from api.tasks.exceptions import ApprovalDeliveryError

        task = _seed_task(store_with_redis, "task-001")
        mock_sync_redis.lpush.side_effect = ConnectionError("Redis down")

        with pytest.raises(ApprovalDeliveryError):
            store_with_redis.submit_approval("task-001", decision="approve")

        assert len(task.approval_history) == 0

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_expire_failure_after_lpush_success_still_succeeds(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """LPUSH succeeds, EXPIRE fails → should NOT raise (CX-1)."""
        task = _seed_task(store_with_redis, "task-001")
        mock_sync_redis.lpush.return_value = 1  # success
        mock_sync_redis.expire.side_effect = ConnectionError("Redis flaky")

        # Should not raise — EXPIRE failure is non-fatal
        store_with_redis.submit_approval("task-001", decision="approve")

        # Approval history SHOULD be recorded (delivery succeeded)
        assert len(task.approval_history) == 1
        assert task.approval_history[0].decision == "approve"

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_lpush_failure_clears_flag_even_when_delete_fails(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Both LPUSH and DELETE fail → ApprovalDeliveryError still raised."""
        from api.tasks.exceptions import ApprovalDeliveryError

        _seed_task(store_with_redis, "task-001")
        mock_sync_redis.lpush.side_effect = ConnectionError("Redis down")
        mock_sync_redis.delete.side_effect = ConnectionError("Redis still down")

        with pytest.raises(ApprovalDeliveryError):
            store_with_redis.submit_approval("task-001", decision="approve")

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_successful_submit_pushes_to_local_queue_hybrid(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """After LPUSH success, payload also pushed to local asyncio.Queue (CX-3)."""
        _seed_task(store_with_redis, "task-001")
        mock_sync_redis.lpush.return_value = 1

        store_with_redis.submit_approval("task-001", decision="approve")

        # Local queue should have the payload as hybrid safety net
        assert "task-001" in store_with_redis._approval_queues
        assert not store_with_redis._approval_queues["task-001"].empty()

    @patch("core.services.db_task_store.asyncio.create_task", new=MagicMock())
    def test_successful_lpush_records_approval_history(
        self, store_with_redis: DbTaskStore, mock_sync_redis: MagicMock
    ) -> None:
        """Successful LPUSH records exactly one approval history entry."""
        task = _seed_task(store_with_redis, "task-001")
        mock_sync_redis.lpush.return_value = 1

        store_with_redis.submit_approval(
            "task-001", decision="approve", stage="topic_approval"
        )

        assert len(task.approval_history) == 1
        assert task.approval_history[0].decision == "approve"
        assert task.approval_history[0].stage == "topic_approval"
