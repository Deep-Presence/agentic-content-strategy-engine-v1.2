# Core Redis Infrastructure

> **Location:** `core/redis.py`, `core/redis_semaphore.py`, `core/cache.py`, `core/checkpointer.py`
> **Owner:** Core
> **Dependencies:** redis (sync), aioredis (async), langgraph-checkpoint-redis
> **Dependents:** EventBus, TaskStore, pipeline state, HITL checkpoints, cache layer, semaphore
> **Last Updated:** 2026-04-09

## Overview

Four files provide the complete Redis infrastructure for the application. Redis serves six distinct roles: SSE event streaming (Redis Streams), pipeline state (Hashes), distributed locks (String + NX), HITL checkpoints (RedisSaver), distributed semaphore (Sorted Sets), and API response cache (String + TTL). All Redis operations gracefully degrade when Redis is unavailable — the system falls back to in-memory alternatives.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Redis Server                      │
│                                                      │
│  Streams: sse:{task_id}              ← EventBus     │
│  Hashes:  pipeline_state:{slug}      ← State        │
│  Strings: lock:{pipeline}:{slug}     ← Locks        │
│  Lists:   approval:{task_id}         ← HITL         │
│  Sorted:  semaphore:pipelines        ← Concurrency  │
│  Strings: cache:*                    ← API Cache    │
│  Hash/JSON: checkpoint:*             ← LangGraph    │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   Async Client   Sync Client    RedisSaver
   (get_redis)   (get_sync_redis) (checkpointer)
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `redis.py` | Client singletons (async + sync) | `get_redis`, `get_redis_or_none`, `get_sync_redis`, `get_sync_redis_or_none`, `close_redis`, `redis_ping` |
| `redis_semaphore.py` | Distributed pipeline concurrency | `RedisSemaphore`, `_SemaphoreContext` |
| `cache.py` | Redis-backed API response cache | `cache_get`, `cache_set`, `cache_delete`, `cache_delete_pattern` |
| `checkpointer.py` | LangGraph checkpointer factory | `get_checkpointer`, `reset_checkpointer` |

## Detailed Reference

### `redis.py` — Client Singletons

Both async and sync clients use lazy initialization with double-checked locking (`threading.RLock`). No connection at import time.

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_redis` | `() -> aioredis.Redis` | Async client. Raises `RuntimeError` if `REDIS_URL` not set |
| `get_redis_or_none` | `() -> Optional[aioredis.Redis]` | Graceful variant. Returns `None` on any error |
| `get_sync_redis` | `() -> redis.Redis` | Sync client. For locks, semaphore, cache |
| `get_sync_redis_or_none` | `() -> Optional[redis.Redis]` | Graceful variant |
| `close_redis` | `async () -> None` | Closes both clients. Sync client closed via `asyncio.to_thread()` |
| `redis_ping` | `async () -> bool` | Health check via `PING` |
| `_redact_url` | `(url: str) -> str` | Masks password for safe logging |

**Connection Pool Config:**
- `max_connections`: from settings (default 20)
- `socket_timeout`: from settings (default 20s)
- `socket_connect_timeout`: from settings (default 2s)
- `retry_on_timeout`: from settings (default True)
- `health_check_interval`: from settings (default 30s)
- `decode_responses=True`: all values returned as `str`

### `redis_semaphore.py` — Distributed Semaphore

Controls global pipeline concurrency via Redis Sorted Sets. Uses atomic Lua scripts to prevent race conditions.

#### Lua Scripts

**`_ACQUIRE_LUA`** — Atomic: purge expired → check capacity → add holder
```lua
ZREMRANGEBYSCORE(key, "-inf", now - ttl)  -- self-healing
ZCARD(key)                                 -- count active
if count < max then ZADD(key, now, holder_id) return 1 end
return 0
```

**`_RENEW_LUA`** — Atomic: check existence → refresh timestamp
```lua
if ZSCORE(key, holder_id) then ZADD(key, now, holder_id) return 1 end
return 0
```

#### `RedisSemaphore`

| Method | Signature | Description |
|--------|-----------|-------------|
| `try_acquire` | `(holder_id: str) -> bool` | Atomic Lua acquire. Sub-ms latency |
| `renew` | `(holder_id: str) -> bool` | Refresh timestamp. Returns False if expired |
| `release` | `(holder_id: str) -> None` | Idempotent `ZREM` |
| `current_count` | `() -> int` | Active holders after purge |
| `force_clear` | `() -> int` | Remove all entries (startup recovery) |
| `acquire_context` | `(holder_id, poll_interval=1.0, timeout=300) -> _SemaphoreContext` | Async context manager |

#### `_SemaphoreContext`

Async context manager that polls for semaphore acquisition and runs a background renewal loop.

- `__aenter__`: Polls `try_acquire()` every `poll_interval` seconds. Raises `TimeoutError` after `timeout` seconds. On acquire, spawns `_renewal_loop()` as background task.
- `_renewal_loop`: Renews every 60s while held. Logs warnings on failure but continues.
- `__aexit__`: Sets `_released=True`, cancels renewal task, calls `release()`.

**Redis key:** `semaphore:pipelines` (Sorted Set, self-healing 2h member TTL)

### `cache.py` — API Response Cache

All operations are sync (callers run via `asyncio.to_thread()`). All operations catch exceptions and log at DEBUG level — never crash.

| Function | Signature | Description |
|----------|-----------|-------------|
| `cache_get` | `(redis_sync, key: str) -> Optional[Any]` | JSON deserialize from Redis GET. Returns `None` on miss/error |
| `cache_set` | `(redis_sync, key: str, value: Any, ttl: int = 300) -> None` | JSON serialize + SETEX. Uses `default=str` for non-serializable objects |
| `cache_delete_pattern` | `(redis_sync, pattern: str) -> int` | SCAN + batch DELETE. Returns count deleted |
| `cache_delete` | `(redis_sync, *keys: str) -> None` | Direct DELETE of specific keys |

### `checkpointer.py` — LangGraph Checkpointer

Factory for LangGraph `RedisSaver` (HITL checkpoint persistence). Required — raises `RuntimeError` if Redis not configured.

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_checkpointer` | `(override: Any = None) -> BaseCheckpointSaver` | Returns RedisSaver. Override for tests. Raises `RuntimeError` if no Redis |
| `reset_checkpointer` | `() -> None` | Reset singleton (testing) |

**Initialization:** Thread-safe double-checked locking. Transient failures do NOT set `_init_attempted` (allows retries). Only permanent decisions (no URL configured) are cached.

## Redis Key Schema

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| `sse:{task_id}` | Stream | 24h | SSE event stream |
| `sse:counter:{task_id}` | String | 24h | Monotonic event ID counter |
| `pipeline_state:{effective_slug}` | Hash | 24h | Per-brief status + task mapping |
| `lock:{pipeline}:{effective_slug}` | String | 2h | Distributed slug lock (value = task_id) |
| `approval:{task_id}` | List | 24h | HITL approval payload queue |
| `approval:flag:{task_id}` | String | 24h | Duplicate submission prevention |
| `approval:nonce:{task_id}` | String | 24h | Current checkpoint nonce |
| `semaphore:pipelines` | Sorted Set | Self-healing | Global pipeline concurrency |
| `checkpoint:*` | Hash/JSON | RedisSaver managed | LangGraph HITL state |
| `cache:gap:{slug}:*` | String | 5min | Gap analysis artifacts |
| `cache:content:{slug}:*` | String | 2min | Content pipeline artifacts |
| `cache:audit:{slug}:*` | String | 10min | Site audit results |
| `cache:gap_ctx:{slug}` | String | 5min | Gap context for content sidebar |
| `cache:brand:{slug}:*` | String | 5min | Research artifact detection |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `redis_url` | `None` | **Required.** Connection URL |
| `redis_max_connections` | `20` | Pool size |
| `redis_socket_timeout` | `20.0` | Socket timeout (s) |
| `redis_socket_connect_timeout` | `2.0` | Connect timeout (s) |
| `redis_retry_on_timeout` | `True` | Auto-retry |
| `redis_health_check_interval` | `30` | Health check interval (s) |
| `redis_event_bus` | `True` | Enable Redis Streams EventBus |
| `redis_pipeline_state` | `True` | Enable Redis Hashes for state |
| `redis_checkpointer` | `True` | Enable RedisSaver for HITL |

## Error Handling

- **Client singletons:** `*_or_none()` variants return `None` instead of raising
- **Cache operations:** All catch exceptions, log at DEBUG, return default values
- **Semaphore:** Lua scripts are atomic (no partial state). Renewal failures logged but non-fatal
- **Checkpointer:** Transient failures allow retry. `RuntimeError` only on permanent misconfiguration
- **Close:** Collects all errors, logs count, never re-raises
