"""Tests for Redis-backed distributed semaphore in RedisSemaphore + DbTaskStore."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.redis_semaphore import RedisSemaphore, _SemaphoreContext
from core.services.db_task_store import DbTaskStore


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_sync_redis() -> MagicMock:
    """Mock sync redis.Redis for semaphore operations."""
    r = MagicMock()
    r.zrem = MagicMock(return_value=1)
    r.zcard = MagicMock(return_value=0)
    r.zremrangebyscore = MagicMock(return_value=0)
    # register_script returns a callable mock for Lua scripts
    mock_acquire_script = MagicMock(return_value=1)  # Acquired
    r.register_script = MagicMock(return_value=mock_acquire_script)
    return r


@pytest.fixture
def semaphore(mock_sync_redis: MagicMock) -> RedisSemaphore:
    """RedisSemaphore with max_concurrent=3."""
    return RedisSemaphore(
        redis_sync=mock_sync_redis,
        name="pipelines",
        max_concurrent=3,
    )


@pytest.fixture
def mock_session_factory() -> AsyncMock:
    return AsyncMock()


def _sync_to_thread(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread that calls fn synchronously."""
    return fn(*args, **kwargs)


# ── try_acquire tests ─────────────────────────────────────────────────


class TestTryAcquire:
    def test_try_acquire_succeeds_under_limit(
        self, semaphore: RedisSemaphore, mock_sync_redis: MagicMock,
    ) -> None:
        """Lua script returns 1 → acquired."""
        # Lua script returns 1 (success)
        semaphore._acquire_script.return_value = 1

        result = semaphore.try_acquire("task-001")

        assert result is True
        # Verify Lua script called with correct args
        semaphore._acquire_script.assert_called_once()
        call_args = semaphore._acquire_script.call_args
        assert call_args.kwargs["keys"] == ["semaphore:pipelines"]
        args = call_args.kwargs["args"]
        assert args[0] == 3  # max_concurrent
        assert args[1] == 7200  # holder_ttl
        assert args[2] == "task-001"  # holder_id
        # args[3] is timestamp (float)

    def test_try_acquire_fails_at_limit(
        self, semaphore: RedisSemaphore, mock_sync_redis: MagicMock,
    ) -> None:
        """Lua script returns 0 → at capacity."""
        semaphore._acquire_script.return_value = 0

        result = semaphore.try_acquire("task-002")

        assert result is False


# ── release tests ─────────────────────────────────────────────────────


class TestRelease:
    def test_release_removes_holder(
        self, semaphore: RedisSemaphore, mock_sync_redis: MagicMock,
    ) -> None:
        """ZREM called with holder_id. Idempotent."""
        semaphore.release("task-001")

        mock_sync_redis.zrem.assert_called_once_with("semaphore:pipelines", "task-001")

    def test_release_idempotent_after_expiry(
        self, semaphore: RedisSemaphore, mock_sync_redis: MagicMock,
    ) -> None:
        """ZREM returns 0 if already expired/purged — no error."""
        mock_sync_redis.zrem.return_value = 0

        # Should not raise
        semaphore.release("expired-task")

        mock_sync_redis.zrem.assert_called_once_with("semaphore:pipelines", "expired-task")


# ── current_count tests ──────────────────────────────────────────────


class TestCurrentCount:
    def test_current_count_returns_active_holders(
        self, semaphore: RedisSemaphore, mock_sync_redis: MagicMock,
    ) -> None:
        """Purge expired + ZCARD returns count of active holders."""
        mock_sync_redis.zcard.return_value = 2

        count = semaphore.current_count()

        assert count == 2
        # Verify purge happened first
        mock_sync_redis.zremrangebyscore.assert_called_once()
        call_args = mock_sync_redis.zremrangebyscore.call_args
        assert call_args[0][0] == "semaphore:pipelines"
        assert call_args[0][1] == "-inf"
        # Third arg is now - ttl (float)
        mock_sync_redis.zcard.assert_called_once_with("semaphore:pipelines")


# ── acquire_context async tests ──────────────────────────────────────


class TestAcquireContext:
    @pytest.mark.asyncio
    @patch("core.redis_semaphore.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_acquire_context_acquires_and_releases(
        self, mock_to_thread, semaphore: RedisSemaphore,
    ) -> None:
        """async with acquires on enter, releases on exit."""
        semaphore._acquire_script.return_value = 1

        async with semaphore.acquire_context("task-001"):
            # Inside context — should have acquired
            semaphore._acquire_script.assert_called_once()

        # After exit — should have released
        semaphore._redis.zrem.assert_called_once_with("semaphore:pipelines", "task-001")

    @pytest.mark.asyncio
    @patch("core.redis_semaphore.asyncio.to_thread", side_effect=_sync_to_thread)
    @patch("core.redis_semaphore.asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_context_polls_when_full(
        self, mock_sleep, mock_to_thread, semaphore: RedisSemaphore,
    ) -> None:
        """try_acquire returns False twice then True — polls with sleep."""
        semaphore._acquire_script.side_effect = [0, 0, 1]

        async with semaphore.acquire_context("task-003", poll_interval=0.5):
            pass

        assert semaphore._acquire_script.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.5)

    @pytest.mark.asyncio
    @patch("core.redis_semaphore.asyncio.to_thread", side_effect=_sync_to_thread)
    @patch("core.redis_semaphore.asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_context_raises_timeout(
        self, mock_sleep, mock_to_thread, semaphore: RedisSemaphore,
    ) -> None:
        """try_acquire always False → TimeoutError after deadline."""
        semaphore._acquire_script.return_value = 0

        with pytest.raises(TimeoutError, match="Failed to acquire pipeline semaphore"):
            async with semaphore.acquire_context("task-004", timeout=0):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    @patch("core.redis_semaphore.asyncio.to_thread", side_effect=_sync_to_thread)
    async def test_acquire_context_releases_on_exception(
        self, mock_to_thread, semaphore: RedisSemaphore,
    ) -> None:
        """Release still called when exception raised inside context."""
        semaphore._acquire_script.return_value = 1

        with pytest.raises(ValueError, match="boom"):
            async with semaphore.acquire_context("task-005"):
                raise ValueError("boom")

        # Release must have been called
        semaphore._redis.zrem.assert_called_once_with("semaphore:pipelines", "task-005")


# ── DbTaskStore fallback test ────────────────────────────────────────


class TestPipelineSemaphoreFallback:
    def test_pipeline_semaphore_returns_asyncio_semaphore_when_no_redis(
        self, mock_session_factory: AsyncMock,
    ) -> None:
        """Without Redis, pipeline_semaphore returns asyncio.Semaphore."""
        store = DbTaskStore(
            session_factory=mock_session_factory,
            max_concurrent=3,
            redis_client=None,
        )

        result = store.pipeline_semaphore("task-001")

        assert isinstance(result, asyncio.Semaphore)

    def test_pipeline_semaphore_returns_context_when_redis_available(
        self, mock_session_factory: AsyncMock, mock_sync_redis: MagicMock,
    ) -> None:
        """With Redis, pipeline_semaphore returns _SemaphoreContext."""
        store = DbTaskStore(
            session_factory=mock_session_factory,
            max_concurrent=3,
            redis_client=mock_sync_redis,
        )

        result = store.pipeline_semaphore("task-001")

        assert isinstance(result, _SemaphoreContext)
