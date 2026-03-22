"""Redis-backed distributed semaphore using Sorted Sets.

Limits global concurrent pipeline runs across all Uvicorn workers.
Self-healing: expired entries (dead workers) are purged on acquire.

The acquire operation is **atomic** (Lua script) to prevent race
conditions where two workers both see capacity and both ZADD.

Usage:
    sem = RedisSemaphore(redis_sync, "pipelines", max_concurrent=3)
    async with sem.acquire_context("task-uuid"):
        await run_pipeline(...)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Atomic acquire: purge expired → check capacity → add holder.
# Single Redis round-trip prevents race conditions.
_ACQUIRE_LUA = """\
local now = tonumber(ARGV[4])
local ttl = tonumber(ARGV[2])
redis.call("ZREMRANGEBYSCORE", KEYS[1], "-inf", now - ttl)
local count = redis.call("ZCARD", KEYS[1])
if count < tonumber(ARGV[1]) then
    redis.call("ZADD", KEYS[1], now, ARGV[3])
    return 1
end
return 0
"""


class RedisSemaphore:
    """Distributed semaphore backed by a Redis Sorted Set."""

    def __init__(
        self,
        redis_sync,           # sync redis.Redis client
        name: str,            # semaphore name (e.g., "pipelines")
        max_concurrent: int,  # max simultaneous holders
        holder_ttl: int = 7200,  # 2h — max time a holder can keep the slot
    ) -> None:
        self._redis = redis_sync
        self._key = f"semaphore:{name}"
        self._max = max_concurrent
        self._ttl = holder_ttl
        self._acquire_script = redis_sync.register_script(_ACQUIRE_LUA)

    def try_acquire(self, holder_id: str) -> bool:
        """Try to acquire a slot atomically. Returns True if acquired.

        Synchronous — single Lua script call (sub-ms).
        Purges expired holders before checking capacity.
        """
        now = time.time()
        result = self._acquire_script(
            keys=[self._key],
            args=[self._max, self._ttl, holder_id, now],
        )
        return bool(result)

    def release(self, holder_id: str) -> None:
        """Release a slot. Idempotent — safe if already expired/purged."""
        self._redis.zrem(self._key, holder_id)

    def acquire_context(
        self,
        holder_id: str,
        poll_interval: float = 1.0,
        timeout: float = 300,
    ) -> _SemaphoreContext:
        """Return an async context manager that acquires/releases the semaphore.

        Polls every poll_interval seconds until a slot is available or timeout.
        """
        return _SemaphoreContext(self, holder_id, poll_interval, timeout)

    def current_count(self) -> int:
        """Return the number of currently held slots (after purge)."""
        now = time.time()
        self._redis.zremrangebyscore(self._key, "-inf", now - self._ttl)
        return self._redis.zcard(self._key)

    def force_clear(self) -> int:
        """Remove ALL semaphore entries. For startup recovery (single-process).

        In a single-process deployment, any entries from a previous process
        are guaranteed stale (the previous process is dead). Returns the
        number of entries removed.
        """
        count = self._redis.zcard(self._key)
        if count:
            self._redis.delete(self._key)
            logger.info("Semaphore '%s': force-cleared %d stale entries", self._key, count)
        return count


class _SemaphoreContext:
    """Async context manager for RedisSemaphore — replaces ``async with semaphore:``."""

    def __init__(
        self,
        sem: RedisSemaphore,
        holder_id: str,
        poll_interval: float,
        timeout: float,
    ) -> None:
        self._sem = sem
        self._holder_id = holder_id
        self._poll_interval = poll_interval
        self._timeout = timeout

    async def __aenter__(self) -> _SemaphoreContext:
        deadline = time.monotonic() + self._timeout
        while True:
            acquired = await asyncio.to_thread(self._sem.try_acquire, self._holder_id)
            if acquired:
                logger.debug(
                    "Semaphore acquired",
                    extra={"holder_id": self._holder_id, "key": self._sem._key},
                )
                return self
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Failed to acquire pipeline semaphore within {self._timeout}s "
                    f"(max_concurrent={self._sem._max})"
                )
            logger.debug(
                "Semaphore full, polling",
                extra={"holder_id": self._holder_id, "poll_interval": self._poll_interval},
            )
            await asyncio.sleep(self._poll_interval)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await asyncio.to_thread(self._sem.release, self._holder_id)
        logger.debug(
            "Semaphore released",
            extra={"holder_id": self._holder_id, "key": self._sem._key},
        )
        return False  # Don't suppress exceptions
