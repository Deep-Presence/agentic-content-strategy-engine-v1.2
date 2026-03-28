# Session 5: Distributed Semaphore — Global Pipeline Concurrency Limit

## Prerequisites

- Session 0 (Redis Infrastructure) complete
- Session 2 (Redis Hashes / Distributed Locks) complete — `DbTaskStore` already has `self._redis_sync`

## Objective

Replace the process-local `asyncio.Semaphore` in `DbTaskStore` with a Redis-backed distributed semaphore. After this session, the global `max_concurrent_pipelines` limit (default 3) is enforced across all Uvicorn workers, not per-worker. With 2 workers and `max_concurrent=3`, the system allows exactly 3 total concurrent pipelines, not 6.

---

## 1. What Changes vs What Does NOT

This is the most important distinction in this session. There are **two types of semaphores** in the codebase. Only one migrates to Redis.

### Type 1: Global pipeline concurrency semaphore — MIGRATES TO REDIS

This is `task_store.semaphore`, exposed via `TaskStoreProtocol.semaphore` property. It limits how many pipeline runs (gap analysis, content generation, KB, AP, VSG, TD, onboarding, site audit, daily tracker) can execute concurrently across the entire system.

Created in `DbTaskStore.__init__()`:
```python
self._semaphore = asyncio.Semaphore(max_concurrent)
```

Configured via `API_MAX_CONCURRENT_PIPELINES` (default 3) in `api/config.py`.

**Every pipeline runner** wraps its execution in this semaphore:
```python
async with task_store.semaphore:
    output = await run_content_generation_v13(...)
```

### Callers (all in `api/tasks/runner.py`):

| Runner function | Pipeline |
|----------------|----------|
| `run_gap_pipeline_task()` | Gap Analysis |
| `run_content_pipeline_task()` | Content v1.0 |
| `run_content_v13_pipeline_task()` | Content v1.3 |
| `run_site_audit_task()` | Site Audit |
| `run_kb_pipeline_task()` | Knowledge Base |
| `run_audience_persona_pipeline_task()` | Audience Persona |
| `run_vsg_pipeline_task()` | Voice Style Guide |
| `run_topic_discovery_pipeline_task()` | Topic Discovery |
| `run_research_orchestrator_task()` | Research Orchestrator (KB→AP→VSG) |
| `run_onboarding_task()` | Onboarding Orchestrator |
| `run_daily_tracker_task()` | Daily Tracker |

All use `async with task_store.semaphore:` — they acquire the semaphore at the start of the pipeline and hold it until the pipeline completes, fails, or is cancelled.

### Type 2: Local operation semaphores — DO NOT CHANGE

These are `asyncio.Semaphore` instances created within individual pipeline stages to limit concurrency of sub-operations (LLM API calls, HTTP fetches, embedding batches). They are local to a single pipeline run within a single async task. They do NOT need Redis because they only coordinate coroutines within the same event loop.

| Location | What it limits |
|----------|---------------|
| `core/content_engine/workers/dispatcher.py` | Concurrent content worker chains (outliner→drafter→linker→fact-checker) |
| `core/content_engine/brief_builder.py` | Concurrent brief builds |
| `core/gap_analysis/steps/s3_search_platforms.py` | Global + per-engine concurrent LLM API calls |
| `core/gap_analysis/steps/s4_enrich_citations.py` | Concurrent URL fetch + parse operations |
| `core/shared_tools/async_embedding_client.py` | Concurrent embedding API batches |
| `core/site_audit/steps/s1_discover.py` | Concurrent page crawl requests |
| `core/daily_tracker/platform_runner.py` | Concurrent platform API calls |

**These are all left completely untouched.** They use `asyncio.Semaphore` directly (not `task_store.semaphore`) and are scoped to a single pipeline execution.

---

## 2. The Problem with Process-Local Semaphore

`asyncio.Semaphore` lives in a single event loop in a single process. With Gunicorn running N Uvicorn workers:

- Worker 1 has `Semaphore(3)` → allows 3 concurrent pipelines
- Worker 2 has `Semaphore(3)` → allows 3 concurrent pipelines
- System total: 6 concurrent pipelines (2 × 3)

But `max_concurrent_pipelines=3` means the operator intended a system-wide limit of 3. The extra pipelines can overwhelm LLM API rate limits (Anthropic, OpenAI, Perplexity all have per-key rate limits), exhaust database connection pools, and cause memory pressure from concurrent large JSON artifact loads.

---

## 3. Redis Distributed Semaphore Design

Use a Redis Sorted Set as the semaphore. Each holder is a member; the score is the acquisition timestamp. The count of members = number of currently held slots.

**Key:** `semaphore:pipelines`

### Acquire:

```python
async def acquire(self, holder_id: str, timeout: float = 300) -> bool:
    key = "semaphore:pipelines"
    ttl = 7200  # 2h max hold time (same as slug lock)
    now = time.time()
    
    # Clean expired entries first
    await redis.zremrangebyscore(key, "-inf", now - ttl)
    
    # Check capacity
    count = await redis.zcard(key)
    if count >= self._max_concurrent:
        return False
    
    # Add holder with current timestamp as score
    await redis.zadd(key, {holder_id: now})
    return True
```

### Release:

```python
async def release(self, holder_id: str) -> None:
    await redis.zrem("semaphore:pipelines", holder_id)
```

### Why Sorted Set and not a simple counter?

A simple `INCR`/`DECR` counter loses track of who holds the semaphore. If a worker crashes without decrementing, the counter is permanently inflated, reducing available slots until it's manually reset. With a Sorted Set, each member has a timestamp score. The `zremrangebyscore` call at acquisition time purges entries older than 2 hours (dead workers). This is self-healing — no manual intervention needed.

The holder_id is `task_id` — unique per pipeline run, and already available at the acquisition site.

### The `async with` pattern

The current code uses `async with task_store.semaphore:` which calls `__aenter__` (acquire) and `__aexit__` (release) on the `asyncio.Semaphore`. The Redis semaphore needs to support the same context manager pattern.

---

## 4. Implementation

### New file: `core/redis_semaphore.py`

```python
"""Redis-backed distributed semaphore using Sorted Sets.

Limits global concurrent pipeline runs across all Uvicorn workers.
Self-healing: expired entries (dead workers) are purged on acquire.

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

    def try_acquire(self, holder_id: str) -> bool:
        """Try to acquire a slot. Returns True if acquired, False if full.
        
        Synchronous — sub-ms Redis operation.
        """
        now = time.time()
        # Purge expired holders (dead workers)
        self._redis.zremrangebyscore(self._key, "-inf", now - self._ttl)
        # Check capacity
        count = self._redis.zcard(self._key)
        if count >= self._max:
            return False
        # Add holder
        self._redis.zadd(self._key, {holder_id: now})
        return True

    def release(self, holder_id: str) -> None:
        """Release a slot. Synchronous."""
        self._redis.zrem(self._key, holder_id)

    def acquire_context(self, holder_id: str, poll_interval: float = 1.0, timeout: float = 300):
        """Return an async context manager that acquires/releases the semaphore.
        
        Polls every poll_interval seconds until a slot is available or timeout.
        """
        return _SemaphoreContext(self, holder_id, poll_interval, timeout)

    def current_count(self) -> int:
        """Return the number of currently held slots (after purge)."""
        now = time.time()
        self._redis.zremrangebyscore(self._key, "-inf", now - self._ttl)
        return self._redis.zcard(self._key)


class _SemaphoreContext:
    """Async context manager for RedisSemaphore — replaces `async with semaphore:`."""

    def __init__(self, sem: RedisSemaphore, holder_id: str, poll_interval: float, timeout: float):
        self._sem = sem
        self._holder_id = holder_id
        self._poll_interval = poll_interval
        self._timeout = timeout

    async def __aenter__(self):
        deadline = time.monotonic() + self._timeout
        while True:
            acquired = await asyncio.to_thread(self._sem.try_acquire, self._holder_id)
            if acquired:
                return self
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Failed to acquire pipeline semaphore within {self._timeout}s "
                    f"(max_concurrent={self._sem._max})"
                )
            await asyncio.sleep(self._poll_interval)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.to_thread(self._sem.release, self._holder_id)
        return False  # Don't suppress exceptions
```

**Key design decisions:**

`try_acquire()` is synchronous (sub-ms Redis call, wrapped in `asyncio.to_thread` by the context manager). This matches the sync Redis client pattern from Session 2.

The polling loop in `__aenter__` with `asyncio.sleep(1.0)` replaces `asyncio.Semaphore`'s internal waitlist. When all slots are full, a new pipeline waits by polling every second. This is slightly less efficient than `asyncio.Semaphore`'s cooperative waitlist, but pipelines are long-running (minutes to hours) — 1-second poll granularity is irrelevant.

The `timeout=300` (5 minutes) prevents a pipeline from waiting forever if the system is saturated. If it can't acquire in 5 minutes, it raises `TimeoutError` which the runner catches and reports as a failure.

`holder_ttl=7200` (2 hours) auto-purges dead workers. If a Gunicorn worker dies holding a semaphore slot, the entry expires and the slot becomes available to other workers.

---

## 5. Integration into `DbTaskStore`

### File: `core/services/db_task_store.py`

**Replace the semaphore property:**

```python
class DbTaskStore:
    def __init__(self, session_factory, max_concurrent=10, redis_client=None):
        ...
        # Semaphore: Redis distributed if available, else local asyncio
        self._local_semaphore = asyncio.Semaphore(max_concurrent)
        self._redis_semaphore: Optional[RedisSemaphore] = None
        if redis_client is not None:
            from core.redis_semaphore import RedisSemaphore
            self._redis_semaphore = RedisSemaphore(
                redis_sync=redis_client,
                name="pipelines",
                max_concurrent=max_concurrent,
            )
        self._max_concurrent = max_concurrent
        ...
```

**The `semaphore` property problem:**

The `TaskStoreProtocol` defines:
```python
@property
def semaphore(self) -> asyncio.Semaphore: ...
```

Every runner does:
```python
async with task_store.semaphore:
    ...
```

`asyncio.Semaphore` is an async context manager. Our `RedisSemaphore` is not an `asyncio.Semaphore`. We can't return a `RedisSemaphore` from a property typed as `asyncio.Semaphore`.

**Two options:**

**Option A (minimal protocol change):** Change the protocol's return type to a generic async context manager protocol. The property returns either `asyncio.Semaphore` (which is an async context manager) or a wrapper around `RedisSemaphore` that also implements the async context manager protocol.

But there's a bigger problem: the runners use `async with task_store.semaphore:` without passing a `holder_id`. The Redis semaphore needs a `holder_id` (the task_id) to track who holds each slot.

**Option B (recommended — change the call pattern):** Instead of the bare `semaphore` property, add a method:

```python
# New method on TaskStoreProtocol and DbTaskStore:
def pipeline_semaphore(self, task_id: str):
    """Return an async context manager for the pipeline concurrency semaphore."""
    if self._redis_semaphore is not None:
        return self._redis_semaphore.acquire_context(task_id)
    return self._local_semaphore
```

**But this changes every runner call site** from:
```python
async with task_store.semaphore:
```
to:
```python
async with task_store.pipeline_semaphore(task_id):
```

There are 11 runner functions. Each change is mechanical — the `task_id` is already available at every call site.

**Option C (pragmatic — wrapper that extracts task_id from context):** Keep the property, return a wrapper that reads the task_id from contextvars or from the most recently created task. This avoids changing runners but adds implicit coupling.

**Go with Option B.** It's explicit, the 11 changes are trivial, and `task_id` is already in scope at every call site. Option C is too magical.

### Protocol change:

**File: `core/services/task_store.py`**

```python
@runtime_checkable
class TaskStoreProtocol(Protocol):
    @property
    def semaphore(self) -> asyncio.Semaphore: ...  # Keep for backward compat
    
    def pipeline_semaphore(self, task_id: str): ...  # New — returns async context manager
```

The `semaphore` property stays (backward compat for JSON TaskStore and tests). `pipeline_semaphore()` is the new preferred method.

### `DbTaskStore` implementation:

```python
def pipeline_semaphore(self, task_id: str):
    if self._redis_semaphore is not None:
        return self._redis_semaphore.acquire_context(task_id)
    return self._local_semaphore
```

### JSON `TaskStore` implementation (fallback):

```python
def pipeline_semaphore(self, task_id: str):
    return self._semaphore  # asyncio.Semaphore is already an async context manager
```

---

## 6. Runner Changes

### File: `api/tasks/runner.py`

Every runner function changes from:
```python
async with task_store.semaphore:
    output = await run_some_pipeline(...)
```
to:
```python
async with task_store.pipeline_semaphore(task_id):
    output = await run_some_pipeline(...)
```

**All 11 runner functions.** Each is a one-line change. `task_id` is already available as a local variable in every runner.

Complete list:

| Function | Current line | New line |
|----------|-------------|----------|
| `run_gap_pipeline_task()` | `async with task_store.semaphore:` | `async with task_store.pipeline_semaphore(task_id):` |
| `run_content_pipeline_task()` | same | same pattern |
| `run_content_v13_pipeline_task()` | same | same pattern |
| `run_site_audit_task()` | same | same pattern |
| `run_kb_pipeline_task()` | same | same pattern |
| `run_audience_persona_pipeline_task()` | same | same pattern |
| `run_vsg_pipeline_task()` | same | same pattern |
| `run_topic_discovery_pipeline_task()` | same | same pattern |
| `run_research_orchestrator_task()` | same | same pattern |
| `run_onboarding_task()` | same | same pattern |
| `run_daily_tracker_task()` | same | same pattern |

---

## 7. What Does NOT Change

| Component | Reason unchanged |
|-----------|-----------------|
| All local operation semaphores (dispatcher, S3, S4, embeddings, crawler, daily tracker) | Per-operation, single-event-loop — no Redis needed |
| `TaskStoreProtocol.semaphore` property | Kept for backward compat |
| `api/config.py` `max_concurrent_pipelines` | Same setting, same default (3) |
| Approval flow | Unrelated |
| EventBus / RedisEventBus | Unrelated |
| LangGraph checkpointer | Unrelated |
| Pipeline state Redis hashes | Unrelated |
| Distributed slug locks | Unrelated (different concern — per-slug, not global) |
| Frontend | No awareness of semaphore |
| All graph modules | No semaphore interaction |
| All pipeline functions | Called inside the semaphore, but don't touch it |

---

## 8. Configuration

No new settings needed. The existing `API_MAX_CONCURRENT_PIPELINES` (default 3) is passed to `DbTaskStore.__init__(max_concurrent=...)` which passes it to `RedisSemaphore(max_concurrent=...)`. Same config, same value, now enforced globally.

---

## 9. File Summary

| File | Action | Description |
|------|--------|-------------|
| `core/redis_semaphore.py` | **Create** | `RedisSemaphore` class + `_SemaphoreContext` async context manager |
| `core/services/task_store.py` | Edit | Add `pipeline_semaphore(task_id)` to `TaskStoreProtocol` |
| `core/services/db_task_store.py` | Edit | Add `_redis_semaphore` initialization + `pipeline_semaphore()` method |
| `api/tasks/store.py` | Edit | Add `pipeline_semaphore()` method (returns `self._semaphore`) |
| `api/tasks/runner.py` | Edit | Change 11 `async with task_store.semaphore:` → `async with task_store.pipeline_semaphore(task_id):` |
| `tests/unit/test_redis_semaphore.py` | **Create** | Unit tests |
| `CLAUDE.md` | Edit | Document distributed semaphore, key schema |

---

## 10. Redis Key Schema (Cumulative)

| Key Pattern | Type | TTL | Purpose | Session |
|---|---|---|---|---|
| `sse:{task_id}` | Stream | 24h | SSE event stream | 1 |
| `sse:counter:{task_id}` | String | 24h | Monotonic event ID counter | 1 |
| `pipeline_state:{effective_slug}` | Hash | 24h | Per-brief in-flight status | 2 |
| `lock:{pipeline}:{effective_slug}` | String | 2h | Distributed slug lock | 2 |
| `langgraph:checkpoint:*` | (RedisSaver internal) | 48h | HITL graph checkpoint state | 3 |
| `approval:{task_id}` | List | 24h | HITL approval payload queue | 4 |
| `approval:flag:{task_id}` | String | 24h | Duplicate submission prevention | 4 |
| `approval:nonce:{task_id}` | String | 24h | Current checkpoint nonce | 4 |
| `semaphore:pipelines` | Sorted Set | Self-healing (2h member TTL) | Global pipeline concurrency limit | **5** |

---

## 11. Tests

### `tests/unit/test_redis_semaphore.py`

1. **`try_acquire` succeeds when under limit.** Create `RedisSemaphore(max=3)`. Acquire with holder "a" → returns `True`. `ZADD` called.

2. **`try_acquire` fails when at limit.** Mock `ZCARD` returning 3 (at max). Acquire → returns `False`. No `ZADD` called.

3. **`release` removes holder.** Acquire holder "a", release holder "a". Verify `ZREM` called with "a".

4. **Expired holders are purged on acquire.** Seed sorted set with an entry scored at `time.time() - 8000` (older than 7200s TTL). Acquire new holder → `ZREMRANGEBYSCORE` removes the old entry, `ZCARD` returns 0, new holder acquired.

5. **`current_count` returns active holder count.** Seed 2 entries, one expired one fresh. `current_count()` returns 1 (after purge).

6. **`acquire_context` async context manager acquires and releases.** Use `async with sem.acquire_context("task-1"):` — verify `try_acquire` called on enter, `release` called on exit.

7. **`acquire_context` polls when full.** Mock `try_acquire` returning `False` twice then `True`. Verify it polls (sleeps between attempts) then succeeds.

8. **`acquire_context` raises `TimeoutError` when permanently full.** Mock `try_acquire` always returning `False`. Set `timeout=2`. Verify `TimeoutError` raised.

9. **`acquire_context` releases on exception.** Raise inside `async with` block. Verify `release` still called (`__aexit__`).

10. **Fallback: `pipeline_semaphore` returns local asyncio.Semaphore when Redis is None.** Set `self._redis_semaphore = None`. Call `pipeline_semaphore("task-1")`. Verify returned object is `asyncio.Semaphore`.

### Integration test (requires Redis + 2 workers):

11. **Global limit enforced across workers.** Set `max_concurrent=2`. Start 3 pipelines rapidly. Verify only 2 run concurrently (third waits). `redis-cli ZCARD semaphore:pipelines` shows 2 during execution.

12. **Slot freed on pipeline completion.** Start pipeline, verify `ZCARD` = 1. Pipeline completes, verify `ZCARD` = 0.

13. **Dead worker recovery.** Manually `ZADD semaphore:pipelines {old_timestamp} dead-task`. Start new pipeline — purge removes the dead entry, new pipeline acquires successfully.

---

## 12. Validation Checklist

### Without Redis (`_redis_semaphore` is None):
1. `pipeline_semaphore(task_id)` returns `asyncio.Semaphore` — existing behavior
2. All pipelines work as before
3. All existing tests pass

### With Redis:
4. Start 3 pipelines concurrently (at `max_concurrent=3`) → all 3 start
5. Start a 4th pipeline → it waits (logs show polling)
6. First pipeline completes → 4th pipeline starts
7. `redis-cli ZCARD semaphore:pipelines` shows correct count during execution
8. `redis-cli ZRANGE semaphore:pipelines 0 -1 WITHSCORES` shows task_ids and timestamps
9. After all pipelines complete → `ZCARD` = 0
10. Kill a worker holding a semaphore slot → slot auto-recovers after 2h (or immediately when next acquire purges expired entries)

### Multi-worker validation:
11. With 2 Gunicorn workers and `max_concurrent=2`: start 3 pipelines → only 2 run system-wide (not 2 per worker = 4)
12. Pipeline on worker A completes → pipeline waiting on worker B starts

---

## 13. Scope Boundaries — Do NOT Do These

- Do NOT change any local operation semaphore (dispatcher, S3, S4, embeddings, crawler)
- Do NOT delete the `semaphore` property from `TaskStoreProtocol` — keep for backward compat
- Do NOT change the JSON `TaskStore` beyond adding the `pipeline_semaphore()` method
- Do NOT change any pipeline function (they run inside the semaphore, they don't touch it)
- Do NOT change any graph module
- Do NOT change any approval flow
- Do NOT change EventBus / RedisEventBus
- Do NOT change frontend
- Do NOT implement Redis caching (Session 6)
