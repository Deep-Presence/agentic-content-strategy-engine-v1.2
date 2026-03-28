# Session 2: Redis Hashes — Pipeline State & Distributed Locks

## Prerequisites

- Session 0 (Redis Infrastructure) complete — `core/redis.py`, `app.state.redis` available
- Session 1 (RedisEventBus) complete — not a functional dependency, but confirms Redis is working end-to-end

## Objective

Replace `pipeline_state.json` with Redis Hashes and replace in-memory `_slug_locks` with Redis distributed locks (`SET NX EX`). After this session, the Kanban board reads brief statuses from Redis instead of a JSON file, and slug locks work across multiple Uvicorn workers. **The `pipeline_state.json` file is no longer written or read in production when Redis is available.** Graceful fallback to the existing file-based approach when Redis is unavailable.

---

## PART A: Pipeline State → Redis Hash

### A1. What `pipeline_state.json` Does Today

**File:** `core/content_engine/state_helpers.py`

Two functions manage this file:

**`_write_pipeline_state(artifact_dir, brief_ids, phase, *, task_id=None)`**
- Reads existing `pipeline_state.json` (if present)
- Merges new brief statuses: `{"brief-001": "generating", "brief-002": "evaluating"}`
- Stores a `__task_ids__` mapping: `{"__task_ids__": {"brief-001": "task-uuid-abc"}}` — used by the frontend to discover which task_id to send HITL approval calls to
- Validates `phase` against `BriefPipelineStatus` enum
- Writes back atomically

**`_cleanup_pipeline_state(artifact_dir, brief_ids)`**
- Removes specific brief IDs (not the whole file) after pipeline finalization
- Also cleans up corresponding `__task_ids__` entries
- Deletes the file entirely only if no entries remain
- Concurrency-safe: parallel manual runs keep their entries

**Call sites for `_write_pipeline_state()`:**

| Location | When called |
|----------|-------------|
| `core/content_engine/pipeline_v13.py` | At each stage transition (suggested, brief_approved, generating, evaluating, review, etc.) — roughly 6-8 calls per pipeline run per brief |
| `core/content_engine/workers_v13.py` | Per-worker progress updates (if dispatcher calls it) |

**Call sites for `_cleanup_pipeline_state()`:**

| Location | When called |
|----------|-------------|
| `core/content_engine/pipeline_v13.py` → `_finalize_pipeline()` | After `run_metadata_v13.json` is written — per-brief cleanup |
| `api/tasks/runner.py` → `_cleanup_stale_pipeline_state()` | On error path — best-effort full file deletion |

### A2. Who Reads `pipeline_state.json`

**`api/services/content_data_service.py`** — `_infer_brief_status()` Phase 0:
```python
if pipeline_state and brief_id in pipeline_state:
    val = pipeline_state[brief_id]
    if isinstance(val, str):
        return val
```
Called from `get_briefs()` and `get_brief_detail()`. The `pipeline_state` dict is loaded from file earlier in those functions.

The `__task_ids__` mapping is also extracted and attached to each `ContentBriefListItem.task_id` field.

**`core/services/db_content_data.py`** — `get_briefs()`:
Same pattern. Even the DB-backed service reads `pipeline_state.json` from the filesystem because the DB doesn't have per-brief in-flight granularity:
```python
ps_path = content_root / "pipeline_state.json"
if ps_path.is_file():
    raw_ps = json.loads(ps_path.read_text(encoding="utf-8"))
    pipeline_state = raw_ps
```

### A3. Redis Hash Design

**Key:** `pipeline_state:{effective_slug}`

This is a Redis Hash where each field is a brief ID and the value is the status string:

```
HSET pipeline_state:ramp brief-001 "generating"
HSET pipeline_state:ramp brief-002 "evaluating"
HGET pipeline_state:ramp brief-001  →  "generating"
HDEL pipeline_state:ramp brief-001   # after finalization
HGETALL pipeline_state:ramp  →  {"brief-001": "generating", "brief-002": "evaluating"}
```

**Task ID mapping** uses a separate hash field per brief with a `__tid:` prefix:

```
HSET pipeline_state:ramp __tid:brief-001 "task-uuid-abc"
HSET pipeline_state:ramp __tid:brief-002 "task-uuid-def"
```

This avoids the `__task_ids__` nested dict and keeps everything in flat hash fields. The reader extracts task IDs by checking for the `__tid:` prefix.

**TTL:** `EXPIRE pipeline_state:{slug} 86400` (24 hours). Refreshed on every `HSET`. If all briefs are cleaned up but TTL hasn't expired, the key auto-expires. This replaces the "delete file if empty" logic.

### A4. New Helper Module

**New file:** `core/content_engine/state_redis.py`

```python
"""Redis-backed pipeline state helpers.

Drop-in replacements for _write_pipeline_state / _cleanup_pipeline_state
from state_helpers.py. Used when Redis is available; file-based fallback
otherwise.
"""
```

Contains:

**`write_pipeline_state_redis(redis, slug, brief_ids, phase, *, task_id=None)`**
- `HSET pipeline_state:{slug} {brief_id} {phase}` for each brief
- `HSET pipeline_state:{slug} __tid:{brief_id} {task_id}` if task_id provided
- `EXPIRE pipeline_state:{slug} 86400` — refresh TTL
- Validates phase against `BriefPipelineStatus` enum
- All operations in a single `pipeline()` call (Redis pipeline, not content pipeline) for atomicity

**`cleanup_pipeline_state_redis(redis, slug, brief_ids)`**
- `HDEL pipeline_state:{slug} {brief_id} __tid:{brief_id}` for each brief
- If hash is empty after deletion, let TTL handle final expiry (no explicit DELETE needed)

**`read_pipeline_state_redis(redis, slug) -> Dict[str, Any]`**
- `HGETALL pipeline_state:{slug}`
- Returns dict in same shape as what `_infer_brief_status()` expects: `{"brief-001": "generating", "__task_ids__": {"brief-001": "task-uuid"}}`
- Reconstructs `__task_ids__` from `__tid:*` fields for backward compatibility with existing reader code

**`cleanup_stale_pipeline_state_redis(redis, slug)`**
- `DELETE pipeline_state:{slug}`
- Error-path equivalent of `_cleanup_stale_pipeline_state()` in runner.py

### A5. Integration Into `state_helpers.py`

**File:** `core/content_engine/state_helpers.py`

Modify `_write_pipeline_state()` and `_cleanup_pipeline_state()` to try Redis first, fall back to file:

```python
def _write_pipeline_state(
    artifact_dir: Path,
    brief_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
    redis_client: Optional[Any] = None,
    effective_slug: Optional[str] = None,
) -> None:
    # Try Redis first
    if redis_client is not None and effective_slug:
        try:
            from core.content_engine.state_redis import write_pipeline_state_redis
            write_pipeline_state_redis(redis_client, effective_slug, brief_ids, phase, task_id=task_id)
            return
        except Exception:
            logger.warning("Redis pipeline state write failed — falling back to file", exc_info=True)

    # File-based fallback (existing code, unchanged)
    state_path = artifact_dir / "pipeline_state.json"
    ...
```

Same pattern for `_cleanup_pipeline_state()`.

**The two new parameters (`redis_client`, `effective_slug`) must be threaded through from callers.** The pipeline already has `effective_slug` available. The Redis client comes from `app.state.redis` → passed through the runner → into the pipeline.

### A6. Threading Redis Client Into Pipelines

**The key question: how does the Redis client reach `_write_pipeline_state()`?**

Current call chain:
```
api/tasks/runner.py (has event_bus, task_store)
  → core/content_engine/pipeline_v13.py (calls _write_pipeline_state)
    → core/content_engine/state_helpers.py (_write_pipeline_state)
```

The runner already passes `event_bus` and `task_store` into the pipeline. Add `redis_client` as another optional parameter following the same pattern:

**File: `api/tasks/runner.py`**
- `run_content_v13_pipeline_task()` gets Redis from `event_bus` or a module-level import
- Passes it to `run_content_generation_v13()` as `redis_client=...`

**File: `core/content_engine/pipeline_v13.py`**
- `run_content_generation_v13()` accepts `redis_client: Optional[Any] = None`
- Passes it through to every `_write_pipeline_state()` and `_cleanup_pipeline_state()` call
- The effective_slug is already computed as `slug` at the top of the function

**This is the most invasive part of the session** — adding `redis_client` and `effective_slug` parameters to ~8-10 `_write_pipeline_state()` call sites within `pipeline_v13.py`. But each change is mechanical: just adding two keyword arguments.

### A7. Reader Changes (Content Data Service)

**File: `api/services/content_data_service.py`**

In `get_briefs()` and `get_brief_detail()`, replace the file read with Redis:

```python
# Before:
pipeline_state = _load_json_cached(content_root, "pipeline_state.json") or {}

# After:
pipeline_state = {}
redis_client = _get_redis_or_none()  # module-level helper
if redis_client is not None:
    try:
        from core.content_engine.state_redis import read_pipeline_state_redis
        pipeline_state = await read_pipeline_state_redis(redis_client, slug)
    except Exception:
        logger.warning("Redis pipeline state read failed — falling back to file")
        pipeline_state = _load_json_cached(content_root, "pipeline_state.json") or {}
else:
    pipeline_state = _load_json_cached(content_root, "pipeline_state.json") or {}
```

**Problem:** `get_briefs()` and `get_brief_detail()` are synchronous functions (called via `asyncio.to_thread()`). Redis reads are async. Two options:

**Option A:** Convert `read_pipeline_state_redis` to use sync Redis client. Add `redis.Redis` (sync) alongside `redis.asyncio.Redis`.

**Option B (recommended):** Keep async Redis. In `read_pipeline_state_redis()`, use `asyncio.run_coroutine_threadsafe()` from within `to_thread`. Or better — the `JsonContentDataService` wrapper already runs these via `asyncio.to_thread()`, so the actual read happens in a thread. Instead, make `read_pipeline_state_redis` a synchronous function that uses `redis.Redis` (sync) for the `HGETALL` call. Redis operations are sub-millisecond; blocking a thread for <1ms is fine.

**Simplest approach:** Add a `_read_pipeline_state_sync()` function that uses a sync `redis.Redis` connection for the single `HGETALL` call. This avoids async/sync bridging entirely.

**File: `core/services/db_content_data.py`**

Same change. The `get_briefs()` method already reads `pipeline_state.json` from the filesystem. Replace with Redis read + file fallback. Since `DbContentDataService` methods are `async def`, you can call the async `read_pipeline_state_redis()` directly.

---

## PART B: Distributed Slug Locks → Redis `SET NX EX`

### B1. What Slug Locks Do Today

**Protocol:** `TaskStoreProtocol.acquire_slug_lock(slug)` / `release_slug_lock(slug)`

**Current implementations:**

Both `TaskStore` and `DbTaskStore` use an in-memory `_slug_locks: Dict[str, str]` dict:

```python
# acquire
def acquire_slug_lock(self, slug: str) -> None:
    if slug in self._slug_locks:
        existing_id = self._slug_locks[slug]
        if existing_id in self._tasks:
            existing = self._tasks[existing_id]
            if existing.status in (TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL):
                raise TaskConflictError(...)
        del self._slug_locks[slug]  # stale lock

# release
def release_slug_lock(self, slug: str) -> None:
    self._slug_locks.pop(slug, None)
```

**Lock key format:** `"{pipeline}:{effective_slug}"` — e.g., `"content_v13:ramp"`, `"gap_analysis:ramp__card"`

**Callers:**

| Location | Pattern |
|----------|---------|
| `DbTaskStore.create_task()` / `TaskStore.create_task()` | `acquire_slug_lock(lock_key)` before creating task (unless `allow_parallel=True`) |
| `api/tasks/runner.py` — every runner `finally:` block | `task_store.release_slug_lock(f"{pipeline}:{effective_slug}")` |
| `api/routers/tasks.py` — cancel endpoint | `task_store.release_slug_lock(f"{task.pipeline}:{effective}")` |

**Problem:** In-memory dict is process-local. Worker 1 acquires the lock; Worker 2 doesn't see it. With multi-worker deployment, two gap analysis runs for the same company could start simultaneously.

### B2. Redis Distributed Lock Design

**Key:** `lock:{pipeline}:{effective_slug}`
**Value:** `{task_id}` (for debugging/staleness detection)
**TTL:** 7200 seconds (2 hours) — pipelines should never run this long, but the TTL prevents orphan locks if a worker dies without releasing

```
SET lock:content_v13:ramp "task-uuid-abc" NX EX 7200
```

- `NX` — only set if key doesn't exist (atomic lock acquisition)
- `EX 7200` — auto-expire after 2 hours (dead worker safety)
- Returns `True` if lock acquired, `None` if already locked

**Release:**
```
DEL lock:content_v13:ramp
```

For safety, use a Lua script or `GET` + `DEL` to only release if the current holder matches (prevents releasing another task's lock):

```python
# Release only if we hold the lock
RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""
```

### B3. Implementation in `DbTaskStore`

**File:** `core/services/db_task_store.py`

The `DbTaskStore` is the primary task store when `DATABASE_URL` is set. Modify its slug lock methods:

```python
class DbTaskStore:
    def __init__(self, session_factory, max_concurrent=10, redis_client=None):
        ...
        self._redis = redis_client
        self._slug_locks: Dict[str, str] = {}  # Keep as fallback
        ...

    def acquire_slug_lock(self, slug: str) -> None:
        if self._redis is not None:
            return self._acquire_redis_lock(slug)
        # Existing in-memory fallback
        ...

    def _acquire_redis_lock(self, slug: str) -> None:
        """Acquire distributed lock via Redis SET NX EX."""
        import redis as sync_redis
        # Need sync call — acquire_slug_lock is sync in protocol
        # Use the sync interface on the connection pool
        key = f"lock:{slug}"
        # Try to get lock info first
        current_holder = self._redis_sync.get(key)
        if current_holder is not None:
            # Check if holder is still active
            task = self._tasks.get(current_holder)
            if task and task.status in (TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL):
                raise TaskConflictError(
                    f"A pipeline is already running for '{slug}' (task_id={current_holder})"
                )
            # Stale lock — delete it
            self._redis_sync.delete(key)
        
        # Acquire
        acquired = self._redis_sync.set(key, self._current_task_id, nx=True, ex=7200)
        if not acquired:
            raise TaskConflictError(f"Failed to acquire lock for '{slug}'")

    def release_slug_lock(self, slug: str) -> None:
        if self._redis is not None:
            key = f"lock:{slug}"
            self._redis_sync.delete(key)
            return
        self._slug_locks.pop(slug, None)
```

**Sync vs Async problem:** `acquire_slug_lock()` and `release_slug_lock()` are synchronous in the `TaskStoreProtocol`. Redis `SET` is sub-millisecond. Use a synchronous Redis connection (`redis.Redis` from the same URL) for lock operations. Create it alongside the async client in the constructor.

Add to `DbTaskStore.__init__()`:
```python
if redis_client is not None:
    import redis as sync_redis
    from core.config.settings import settings
    self._redis_sync = sync_redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=2.0,
    )
else:
    self._redis_sync = None
```

### B4. Passing Redis to `DbTaskStore`

**File:** `api/app.py`

In `_init_task_store()`, pass the Redis client:

```python
if settings.database_url:
    try:
        from core.services.db_task_store import DbTaskStore
        redis_client = getattr(app.state, "redis", None)
        db_store = DbTaskStore(
            session_factory=session_factory,
            max_concurrent=api_settings.max_concurrent_pipelines,
            redis_client=redis_client,  # NEW
        )
        ...
```

### B5. Runner Cleanup Changes

**File:** `api/tasks/runner.py`

The `_cleanup_stale_pipeline_state()` function currently deletes `pipeline_state.json` on error paths. Add Redis cleanup:

```python
def _cleanup_stale_pipeline_state(
    artifacts_root: Optional[Path],
    effective_slug: str,
    *,
    redis_client: Optional[Any] = None,
) -> None:
    # Redis cleanup
    if redis_client is not None:
        try:
            from core.content_engine.state_redis import cleanup_stale_pipeline_state_redis
            cleanup_stale_pipeline_state_redis(redis_client, effective_slug)
            return
        except Exception:
            logger.warning("Redis stale state cleanup failed — trying file", exc_info=True)

    # File-based fallback (existing code)
    ...
```

Thread `redis_client` through the runner functions that call `_cleanup_stale_pipeline_state()`.

---

## PART C: Configuration

### File: `core/config/settings.py`

Add one setting:

```python
redis_pipeline_state: bool = False  # Use Redis for pipeline_state + slug locks
```

Environment variable: `REDIS_PIPELINE_STATE=true`

When `True` AND `redis_url` is set AND Redis is healthy:
- `_write_pipeline_state()` writes to Redis
- `_cleanup_pipeline_state()` cleans up in Redis
- `acquire_slug_lock()` / `release_slug_lock()` use Redis SET NX
- Content data services read from Redis

When `False` or Redis unavailable:
- Everything falls back to existing behavior (file + in-memory dict)

---

## PART D: What Does NOT Change

| File | Reason unchanged |
|------|-----------------|
| `api/tasks/event_bus.py` / `redis_event_bus.py` | Already handled in Session 1 |
| `api/tasks/store.py` (JSON TaskStore) | Not modified — it's the fallback, and its slug lock stays in-memory |
| `TaskStoreProtocol` | Protocol interface unchanged — same method signatures |
| `api/tasks/models.py` | `PipelineTask` model unchanged |
| HITL approval queues (`_approval_queues`) | Session 4 |
| `asyncio.Semaphore` | Session 5 |
| `_tasks` in-memory dict | Not migrated in this session — task CRUD still uses in-memory dict + DB write-through. Redis caching of tasks is a future session. |
| `blueprints.json` | Not touched — that's a DB migration concern, not Redis |
| `run_metadata_v13.json` | Not touched |
| Phase 1 and Phase 2 of `_infer_brief_status()` | Unchanged — only Phase 0 changes |
| All HITL graph modules | Unchanged |
| Frontend | No changes — same API responses |

---

## PART E: File Summary

| File | Action | Description |
|------|--------|-------------|
| `core/content_engine/state_redis.py` | **Create** | `write_pipeline_state_redis()`, `cleanup_pipeline_state_redis()`, `read_pipeline_state_redis()`, `cleanup_stale_pipeline_state_redis()` |
| `core/content_engine/state_helpers.py` | Edit | Add `redis_client` + `effective_slug` params to `_write_pipeline_state()` and `_cleanup_pipeline_state()`, try Redis first with file fallback |
| `core/content_engine/pipeline_v13.py` | Edit | Thread `redis_client` and `effective_slug` to all `_write_pipeline_state()` / `_cleanup_pipeline_state()` call sites (~10 calls). Accept `redis_client` in `run_content_generation_v13()` |
| `core/services/db_task_store.py` | Edit | Accept `redis_client` in `__init__()`, add sync Redis client, modify `acquire_slug_lock()` / `release_slug_lock()` to use `SET NX EX` / `DEL` |
| `api/services/content_data_service.py` | Edit | `get_briefs()` and `get_brief_detail()` — read pipeline state from Redis before file fallback. Reconstruct `__task_ids__` from `__tid:` fields |
| `core/services/db_content_data.py` | Edit | Same — `get_briefs()` reads from Redis before filesystem |
| `api/tasks/runner.py` | Edit | Pass `redis_client` to pipeline functions. Thread it to `_cleanup_stale_pipeline_state()` |
| `api/app.py` | Edit | Pass `redis_client` to `DbTaskStore` constructor. Add `redis_pipeline_state` config check |
| `core/config/settings.py` | Edit | Add `redis_pipeline_state: bool = False` |
| `tests/unit/test_state_redis.py` | **Create** | Unit tests for Redis state helpers |
| `tests/unit/test_distributed_locks.py` | **Create** | Unit tests for Redis-backed slug locks |
| `CLAUDE.md` | Edit | Document Redis key schema additions, config toggle |

---

## PART F: Redis Key Schema (Cumulative)

| Key Pattern | Type | TTL | Purpose | Session |
|---|---|---|---|---|
| `sse:{task_id}` | Stream | 24h | SSE event stream | 1 |
| `sse:counter:{task_id}` | String | 24h | Monotonic event ID counter | 1 |
| `pipeline_state:{effective_slug}` | Hash | 24h (refreshed) | Per-brief in-flight status + `__tid:*` task mapping | **2** |
| `lock:{pipeline}:{effective_slug}` | String | 2h | Distributed slug lock, value = task_id | **2** |

---

## PART G: Tests

### `tests/unit/test_state_redis.py`

1. **`write_pipeline_state_redis` sets hash fields.** Mock Redis, verify `HSET` called with correct key/field/value for each brief_id. Verify `EXPIRE` called with 86400.
2. **`write_pipeline_state_redis` stores task_id mapping.** Verify `__tid:brief-001` field set when task_id provided.
3. **`cleanup_pipeline_state_redis` removes correct fields.** Verify `HDEL` called with brief_id and `__tid:brief_id` fields.
4. **`read_pipeline_state_redis` reconstructs expected dict shape.** Seed mock `HGETALL` return with `{"brief-001": "generating", "__tid:brief-001": "task-abc"}`. Verify returned dict is `{"brief-001": "generating", "__task_ids__": {"brief-001": "task-abc"}}`.
5. **Fallback: `_write_pipeline_state` falls back to file when Redis fails.** Pass a mock Redis that raises `ConnectionError`. Verify file is written instead.
6. **Fallback: `_write_pipeline_state` falls back to file when `redis_client` is None.** Verify existing file-based behavior is unchanged.

### `tests/unit/test_distributed_locks.py`

7. **`acquire_slug_lock` succeeds via Redis SET NX.** Mock `redis.set(nx=True)` returning `True`. Verify no exception.
8. **`acquire_slug_lock` raises `TaskConflictError` when lock held by active task.** Mock `redis.get()` returning a task_id, mock `_tasks` with that task in RUNNING status. Verify `TaskConflictError` raised.
9. **`acquire_slug_lock` clears stale lock.** Mock `redis.get()` returning a task_id NOT in `_tasks`. Verify `redis.delete()` called, then `redis.set(nx=True)` called.
10. **`release_slug_lock` deletes Redis key.** Verify `redis.delete(f"lock:{slug}")` called.
11. **Fallback: slug locks use in-memory dict when Redis is None.** Verify existing behavior preserved.

---

## PART H: Validation Checklist

### Without Redis (REDIS_PIPELINE_STATE=false):
1. Content pipeline writes `pipeline_state.json` as before
2. Kanban board shows correct statuses during pipeline execution
3. Slug locks work in-memory as before
4. All existing tests pass

### With Redis (REDIS_URL set + REDIS_PIPELINE_STATE=true):
5. Content pipeline writes to Redis hash instead of `pipeline_state.json`
6. `redis-cli HGETALL pipeline_state:ramp` shows brief statuses during execution
7. `redis-cli HGETALL pipeline_state:ramp` includes `__tid:brief-001` entries
8. Kanban board shows correct statuses during pipeline execution (reads from Redis)
9. After pipeline completes, `HGETALL pipeline_state:ramp` is empty (briefs cleaned up)
10. After 24h, `EXISTS pipeline_state:ramp` returns 0 (TTL expiry)
11. Starting two gap analysis runs for the same company → second one gets 409 Conflict
12. `redis-cli GET lock:gap_analysis:ramp` shows task_id while pipeline is running
13. After pipeline completes or is cancelled, `EXISTS lock:gap_analysis:ramp` returns 0
14. Kill the Uvicorn worker mid-pipeline → lock auto-expires after 2 hours (no orphan lock)

### Parity test:
15. Run same pipeline with `REDIS_PIPELINE_STATE=false` then `=true`. Compare Kanban board status sequence — must be identical.

---

## PART I: Scope Boundaries — Do NOT Do These

- Do NOT migrate HITL approval queues (`_approval_queues`) — that's Session 4
- Do NOT migrate the `asyncio.Semaphore` — that's Session 5
- Do NOT migrate the `_tasks` in-memory dict to Redis — task CRUD stays as-is (in-memory + DB write-through)
- Do NOT touch `blueprints.json` or `run_metadata_v13.json` — those are DB migration concerns
- Do NOT change Phase 1 or Phase 2 of `_infer_brief_status()` — only Phase 0 changes
- Do NOT delete `pipeline_state.json` support code — it's the fallback
- Do NOT delete the JSON `TaskStore` class
- Do NOT change the `TaskStoreProtocol` interface
- Do NOT change any HITL graph module
- Do NOT change the frontend
- Do NOT add `langgraph-checkpoint-redis`
