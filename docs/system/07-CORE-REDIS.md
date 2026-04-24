# Core Redis Infrastructure

> **Location:** `core/redis.py`, `core/redis_semaphore.py`, `core/cache.py`, `core/checkpointer.py`
> **Owner:** Core
> **Dependencies:** redis (sync), aioredis (async), langgraph-checkpoint-redis
> **Dependents:** EventBus, CompanyEventBus, TaskStore, pipeline state, HITL checkpoints, cache layer, semaphore
> **Last Updated:** 2026-04-24

## Overview

Four files provide the complete Redis infrastructure for the application. Redis serves seven distinct roles: per-task SSE event streaming (Redis Streams), company-wide SSE event streaming (Redis Streams), pipeline state (Hashes), distributed locks (String + NX), HITL checkpoints (RedisSaver), distributed semaphore (Sorted Sets), and API response cache (String + TTL). All Redis operations gracefully degrade when Redis is unavailable -- the system falls back to in-memory alternatives.

## Architecture

```
+-------------------------------------------------------------+
|                       Redis Server                           |
|                                                              |
|  Streams: sse:{task_id}                  <- EventBus        |
|  Streams: company_sse:{slug}             <- CompanyEventBus |
|  Hashes:  pipeline_state:{slug}          <- State           |
|  Strings: lock:{pipeline}:{slug}         <- Locks           |
|  Lists:   approval:{task_id}             <- HITL            |
|  Sorted:  semaphore:pipelines            <- Concurrency     |
|  Sorted:  semaphore:content_engine:{slug}<- Per-company CE  |
|  Strings: cache:*                        <- API Cache       |
|  Hash/JSON: checkpoint:*                 <- LangGraph       |
+----------------------------+---------------------------------+
                             |
          +------------------+------------------+
          v                  v                  v
     Async Client       Sync Client        RedisSaver
     (get_redis)       (get_sync_redis)    (checkpointer)
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `redis.py` | Client singletons (async + sync) | `get_redis`, `get_redis_or_none`, `get_sync_redis`, `get_sync_redis_or_none`, `close_redis`, `redis_ping` |
| `redis_semaphore.py` | Distributed pipeline concurrency | `RedisSemaphore`, `_SemaphoreContext` |
| `cache.py` | Redis-backed API response cache | `cache_get`, `cache_set`, `cache_delete`, `cache_delete_pattern` |
| `checkpointer.py` | LangGraph checkpointer factory | `get_checkpointer`, `reset_checkpointer` |

## Detailed Reference

### `redis.py` -- Client Singletons

Both async and sync clients use lazy initialization with double-checked locking (`threading.RLock`). No connection at import time. Globals are snapshot-and-cleared in `close_redis()` before closing to prevent new callers from accessing closing clients.

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_redis` | `() -> aioredis.Redis` | Async client. Raises `RuntimeError` if `REDIS_URL` not set |
| `get_redis_or_none` | `() -> Optional[aioredis.Redis]` | Graceful variant. Returns `None` on any error (RuntimeError, ValueError, ConnectionError, TimeoutError) |
| `get_sync_redis` | `() -> redis.Redis` | Sync client. For locks, semaphore, cache |
| `get_sync_redis_or_none` | `() -> Optional[redis.Redis]` | Graceful variant |
| `close_redis` | `async () -> None` | Closes both clients + pool. Sync client closed via `asyncio.to_thread()`. Errors collected and logged, never re-raised. |
| `redis_ping` | `async () -> bool` | Health check via `PING` |
| `_redact_url` | `(url: str) -> str` | Masks password for safe logging |

**Connection Pool Config (async client):**
- `max_connections`: from settings (default 20)
- `socket_timeout`: from settings (default 20s)
- `socket_connect_timeout`: from settings (default 2s)
- `retry_on_timeout`: from settings (default True)
- `health_check_interval`: from settings (default 30s)
- `decode_responses=True`: all values returned as `str`

**Sync client** uses `from_url()` with `decode_responses=True`, `socket_timeout`, and `socket_connect_timeout` from settings.

### `redis_semaphore.py` -- Distributed Semaphore

Controls global pipeline concurrency via Redis Sorted Sets. Uses atomic Lua scripts to prevent race conditions where two workers both see capacity and both ZADD.

#### Lua Scripts

**`_ACQUIRE_LUA`** -- Atomic: purge expired -> check capacity -> add holder
```lua
local now = tonumber(ARGV[4])
local ttl = tonumber(ARGV[2])
ZREMRANGEBYSCORE(key, "-inf", now - ttl)  -- self-healing: purge expired
local count = ZCARD(key)                   -- count active
if count < max then ZADD(key, now, holder_id) return 1 end
return 0
```

**`_RENEW_LUA`** -- Atomic: check existence -> refresh timestamp
```lua
if ZSCORE(key, holder_id) then
    ZADD(key, now, holder_id)  -- update score only if member exists
    return 1
end
return 0
```

Uses Lua instead of `ZADD XX` because redis-py's `zadd(xx=True)` returns count of *added* members (always 0 with XX), not *updated* -- making success/failure indistinguishable.

#### `RedisSemaphore`

**Constructor:**
```python
RedisSemaphore(
    redis_sync,              # sync redis.Redis client
    name: str,               # semaphore name (e.g., "pipelines", "content_engine:acme")
    max_concurrent: int,     # max simultaneous holders
    holder_ttl: int = 7200,  # 2h -- max time a holder can keep the slot
)
```

The Redis key is derived as `semaphore:{name}`. For per-company Content Engine semaphores, `name` is `content_engine:{company_slug}`, producing keys like `semaphore:content_engine:acme`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `try_acquire` | `(holder_id: str) -> bool` | Atomic Lua acquire. Purges expired entries, checks capacity, adds holder. Sub-ms latency. |
| `renew` | `(holder_id: str) -> bool` | Atomic Lua: refresh holder's timestamp. Returns `False` if member no longer exists (legitimately expired). Never re-adds an expired slot. |
| `release` | `(holder_id: str) -> None` | Idempotent `ZREM`. Safe if already expired/purged. |
| `current_count` | `() -> int` | `ZREMRANGEBYSCORE` + `ZCARD`. Returns count of active holders after purge. |
| `force_clear` | `() -> int` | `DELETE` the entire sorted set. Returns count of entries removed. Used at startup to purge stale entries from a previous process. |
| `acquire_context` | `(holder_id, poll_interval=1.0, timeout=300) -> _SemaphoreContext` | Returns an async context manager. |

#### `_SemaphoreContext`

Async context manager that polls for semaphore acquisition and runs a continuous background renewal loop for the entire duration the semaphore is held.

**`_RENEWAL_INTERVAL = 60`** -- matches `DbTaskStore._LEASE_RENEWAL_INTERVAL`.

**Lifecycle:**

| Phase | Method | Behavior |
|-------|--------|----------|
| Acquire | `__aenter__` | Polls `try_acquire()` every `poll_interval` via `asyncio.to_thread()`. Raises `TimeoutError` after `timeout` seconds. On success, sets `_held=True` and spawns `_renewal_loop()` as named background task. |
| Hold | `_renewal_loop` | Runs for the full duration (not just HITL waits). Calls `renew()` every 60s via `asyncio.to_thread()`. Logs warnings on failure but continues -- ensures non-HITL pipelines (gap analysis, site audit, KB) never expire mid-run. |
| Release | `__aexit__` | Sets `_closed=True`, `_released=True`, cancels renewal task (awaits cancellation), calls `release()` via `asyncio.to_thread()`. Does NOT suppress exceptions (returns `False`). |
| Suspend | `suspend()` | Temporarily releases the slot without closing the context. Stops the renewal task, calls `release()`, sets `_held=False`. Used during HITL waits to free the concurrency slot. Returns `False` if already closed or not held. |
| Resume | `resume(timeout=None)` | Re-acquires after `suspend()`. Polls `try_acquire()` until success or timeout. Restarts the renewal task. Raises `TimeoutError` on failure. Returns `True` immediately if already held. |

**`suspend()`/`resume()` for HITL waits:**

Long HITL pauses (human approval) would otherwise hold a concurrency slot idle. The pattern is:

```python
async with sem.acquire_context("task-001") as ctx:
    await run_fast_phase()
    await ctx.suspend()    # free the slot during human review
    await wait_for_approval()
    await ctx.resume()     # re-acquire before continuing
    await run_next_phase()
```

#### Per-Company Content Engine Semaphore Pool

The `DbTaskStore.pipeline_semaphore()` method supports a `pool` parameter. When `pool="content_engine"` and `company_slug` is provided, the semaphore is scoped per company rather than globally:

```python
result = store.pipeline_semaphore(
    "task-001",
    pool="content_engine",
    company_slug="acme",
)
```

- **Redis key:** `semaphore:content_engine:acme` (separate sorted set per company).
- **Without Redis:** Per-company `asyncio.Semaphore` instances stored in `DbTaskStore._content_engine_semaphores` dict.
- **Isolation:** `acme` and `beta` have independent concurrency limits. Each company gets `max_concurrent` parallel CE runs.

### `cache.py` -- API Response Cache

All operations are sync (callers run via `asyncio.to_thread()`). All operations catch exceptions and log at DEBUG level -- never crash.

| Function | Signature | Description |
|----------|-----------|-------------|
| `cache_get` | `(redis_sync, key: str) -> Optional[Any]` | JSON deserialize from Redis GET. Returns `None` on miss/error |
| `cache_set` | `(redis_sync, key: str, value: Any, ttl: int = 300) -> None` | JSON serialize + SETEX. Uses `default=str` for non-serializable objects |
| `cache_delete_pattern` | `(redis_sync, pattern: str, *, _batch_size=500) -> int` | SCAN-based + batch DELETE. Returns count deleted. Processes in batches of 500. |
| `cache_delete` | `(redis_sync, *keys: str) -> None` | Direct DELETE of specific keys |

**Pattern deletion** uses `scan_iter()` (not `KEYS`) to avoid blocking Redis on large keysets.

### `checkpointer.py` -- LangGraph Checkpointer

Factory for LangGraph `RedisSaver` (HITL checkpoint persistence). Required -- raises `RuntimeError` if Redis not configured.

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_checkpointer` | `(override: Any = None) -> BaseCheckpointSaver` | Priority: (1) explicit override if valid `BaseCheckpointSaver`, (2) RedisSaver singleton. Raises `RuntimeError` if neither available. |
| `reset_checkpointer` | `() -> None` | Reset singleton for testing |

**Initialization:** Thread-safe double-checked locking via `_init_lock`. Transient failures (connection errors) do NOT set `_init_attempted` -- the next call retries. Only permanent decisions (no `redis_url` configured, or successful init) set the flag to prevent repeated attempts.

**RedisSaver construction** (`_import_redis_saver()`):
```python
RedisSaver(
    redis_url=settings.redis_url,
    connection_args={
        "socket_timeout": settings.redis_socket_timeout,
        "socket_connect_timeout": settings.redis_socket_connect_timeout,
    },
)
saver.setup()
```

## Redis Key Schema

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| `sse:{task_id}` | Stream | 24h | Per-task SSE event stream |
| `sse:counter:{task_id}` | String | 24h | Per-task monotonic event ID counter |
| `company_sse:{company_slug}` | Stream | 24h | Company-wide SSE event stream (MAXLEN ~200) |
| `company_sse:counter:{company_slug}` | String | 24h | Company-wide monotonic event ID counter |
| `pipeline_state:{effective_slug}` | Hash | 24h | Per-brief status + task mapping |
| `lock:{pipeline}:{effective_slug}` | String | 2h | Distributed slug lock (value = task_id) |
| `approval:{task_id}` | List | 24h | HITL approval payload queue |
| `approval:flag:{task_id}` | String | 24h | Duplicate submission prevention |
| `approval:nonce:{task_id}` | String | 24h | Current checkpoint nonce |
| `semaphore:pipelines` | Sorted Set | Self-healing (2h member TTL) | Global pipeline concurrency |
| `semaphore:content_engine:{slug}` | Sorted Set | Self-healing (2h member TTL) | Per-company CE concurrency |
| `checkpoint:*` | Hash/JSON | RedisSaver managed | LangGraph HITL state |
| `cache:gap:{slug}:*` | String | 5min | Gap analysis artifacts |
| `cache:content:{slug}:*` | String | 2min | Content pipeline artifacts |
| `cache:audit:{slug}:*` | String | 10min | Site audit results |
| `cache:gap_ctx:{slug}` | String | 5min | Gap context for content sidebar |
| `cache:brand:{slug}:*` | String | 5min | Research artifact detection |
| `cache:cms:categories:{site_url}` | String | 1h | CMS categories |
| `cache:cms:{slug}:connection:{tenant}` | String | 30min | CMS connection display info |
| `cache:cms:{slug}:stale` | String | 30min | CMS stale action cards |
| `cache:cms:{slug}:posts:*` | String | 10min | CMS synced posts (paginated) |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `redis_url` | `None` | **Required.** Connection URL |
| `redis_max_connections` | `20` | Async pool size |
| `redis_socket_timeout` | `20.0` | Socket timeout (s) |
| `redis_socket_connect_timeout` | `2.0` | Connect timeout (s) |
| `redis_retry_on_timeout` | `True` | Auto-retry |
| `redis_health_check_interval` | `30` | Health check interval (s) |
| `redis_event_bus` | `True` | Enable Redis Streams EventBus |
| `redis_pipeline_state` | `True` | Enable Redis Hashes for state |
| `redis_checkpointer` | `True` | Enable RedisSaver for HITL |

## Error Handling

- **Client singletons:** `*_or_none()` variants catch all exceptions and return `None` instead of raising
- **Cache operations:** All catch exceptions, log at DEBUG, return default values. Never crash callers.
- **Semaphore:** Lua scripts are atomic (no partial state). `renew()` failure logged as WARNING but non-fatal. `_renewal_loop` continues after transient errors.
- **Checkpointer:** Transient failures allow retry (do not set `_init_attempted`). `RuntimeError` only on permanent misconfiguration.
- **Close:** Snapshot-and-clear globals first, then close each resource independently. Errors collected and logged as single WARNING, never re-raised.

## Testing

Tests in `tests/services/test_redis_semaphore.py` cover:

- **`TestTryAcquire`:** Lua script called with correct `keys` (`semaphore:pipelines`) and `args` (max_concurrent=3, holder_ttl=7200, holder_id, timestamp). Returns `True` on acquire, `False` at capacity.
- **`TestRelease`:** `ZREM` called with correct key and holder_id. Idempotent when already expired (returns 0, no error).
- **`TestCurrentCount`:** Purge via `ZREMRANGEBYSCORE` before `ZCARD`.
- **`TestAcquireContext`:** Acquire on enter starts renewal task; release on exit cancels it. Polls when full (sleep between attempts). Raises `TimeoutError` at deadline. Releases on exception.
- **`TestSemaphoreRenewalLoop`:** Renewal continues after transient Redis errors. Task cancelled cleanly on exit.
- **`TestPipelineSemaphoreFallback`:** Without Redis, returns `_TrackedSemaphoreContext` wrapping `_AsyncioSemaphoreContext`. With Redis, returns `_TrackedSemaphoreContext` wrapping `_SemaphoreContext`. CE semaphores use per-company keys (`semaphore:content_engine:acme` vs `semaphore:content_engine:beta`) and are isolated.
