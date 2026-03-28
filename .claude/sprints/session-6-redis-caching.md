# Session 6: Redis Caching — Shared Cross-Worker Response Cache

## Prerequisites

- Session 0 (Redis Infrastructure) complete — `core/redis.py`, sync and async Redis clients available
- Sessions 1-5 complete (functional dependency is only Session 0, but all sessions should be done before this final one)

## Objective

Replace the five module-level in-memory caches (each with its own `threading.Lock`, mtime-based invalidation, and FIFO eviction) with a shared Redis cache layer. After this session, parsed JSON artifacts are cached once in Redis and shared across all Uvicorn workers. No more per-worker memory duplication, no more `threading.Lock` blocking the event loop, and cache invalidation becomes explicit (pipeline writes `DEL` the relevant keys) instead of relying on filesystem mtime polling.

---

## 1. Complete Inventory of In-Memory Caches

There are **five separate cache instances** across the codebase, plus one that's related but different (prompt registry). Each has its own dict, its own lock, its own eviction logic, and none shares state with the others.

### Cache 1: Gap Analysis Data Service

**File:** `api/services/gap_data_service.py`

```python
_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10
_CACHE_LOCK = threading.Lock()
```

**`_load_json_cached(artifacts_root, slug, filename)`** — loads and caches gap analysis JSON files. Key is `(slug, filename)`, value is `(mtime_ns, parsed_data)`.

**Files cached:** `analysis.json` (~2-5MB), `gap_analysis_complete.json` (~5-10MB), `gap_report.json` (~500KB), `enriched_citations.json` (~20MB), `cluster_specs.json`, `embedding_projection.json`.

**Called by:** `get_gap_summary()`, `get_queries()`, `get_clusters()`, `get_heatmap()`, `get_platforms()`, `get_signal_averages()`, `get_spa_trend()`, `get_embedding_projection()` — essentially every gap data endpoint.

**Frequency:** Every dashboard page load that shows gap analysis data. For a user navigating the dashboard, this could be 5-10 calls per minute.

### Cache 2: Content Data Service

**File:** `api/services/content_data_service.py`

```python
_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10
_CACHE_LOCK = threading.Lock()
```

**`_load_json_cached(base_dir, filename)`** — loads and caches content pipeline JSON files. Key is `(str(base_dir), filename)`, value is `(mtime_ns, parsed_data)`.

**Files cached:** `blueprints.json`, `planner_selections.json`, `run_metadata_v13.json`, `run_metadata_v13_*.json` (namespaced), `pipeline_state.json` (already migrated to Redis in Session 2 but file fallback still uses this cache), per-brief `eval_history.json`.

**Called by:** `get_briefs()`, `get_brief_detail()`, `get_brief_stage_content()`, `_load_all_pieces()`.

**Frequency:** Every Content Studio page load, every Kanban board poll.

### Cache 3: Site Audit Data Service

**File:** `core/services/json_site_audit_data.py`

```python
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_MAX = 10
_CACHE_LOCK = threading.Lock()
```

**`_load_audit_result(audit_dir)`** — loads and caches `audit_result.json`. Key is full file path string, value is `(mtime, parsed_data)`.

**Called by:** Every site audit data endpoint (`get_summary()`, `get_page_results()`, etc.).

### Cache 4: Gap Context Helper

**File:** `core/services/gap_context_helper.py`

```python
_GAP_CACHE: Dict[str, Tuple[int, Any]] = {}
_GAP_CACHE_LOCK = threading.Lock()
```

**`load_analysis_json(artifacts_root, slug)`** — loads and caches `analysis.json` specifically for gap context sidebar enrichment on content briefs. Key is full file path string, value is `(mtime_ns, parsed_data)`.

**Called by:** `get_briefs()` and `get_brief_detail()` in both `JsonContentDataService` and `DbContentDataService`. This means the same `analysis.json` is potentially cached in both Cache 1 (gap_data_service) and Cache 4 (gap_context_helper) — duplicate caching of the same file.

### Cache 5: Brand Data Service

**File:** `api/services/brand_data_service.py`

```python
_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10
```

**Note:** This cache has NO `threading.Lock`. It's the only one without thread safety. Since `brand_data_service.py` functions are called via `asyncio.to_thread()`, concurrent reads/writes to this dict are technically a race condition — but Python's GIL makes dict operations atomic enough that it hasn't caused bugs in practice.

**Called by:** `get_research_artifacts()`, `_detect_artifact()`, `_detect_personas()`.

### NOT migrated: Prompt Registry Cache

**File:** `core/content_engine/prompt_registry.py`

```python
_CACHE: Dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 minutes
_LOCK = threading.Lock()
```

**`get_prompt(hub_name, local_fallback, tag)`** — caches LangSmith Hub prompt pulls with 5-minute TTL.

**This cache is different and should NOT be migrated in this session.** It caches external API responses (LangSmith Hub pulls) with TTL-based expiry, not filesystem artifacts with mtime-based invalidation. It also has a fundamentally different failure mode — Hub pull failure returns a local fallback, while file cache failure returns None. Moving this to Redis would add a Redis dependency to the prompt hot path, which runs during every LLM call. The current in-memory cache with 5-minute TTL is appropriate for this use case. Leave it alone.

---

## 2. Current Problems (Why These Caches Need Redis)

**Per-worker memory duplication.** Each Uvicorn worker maintains its own copy of every cached file. With 3 workers and `enriched_citations.json` at 20MB parsed, that's 60MB of duplicated data just for one file per one company. Redis stores it once, all workers read from the same cache.

**`threading.Lock` in async context.** Four of the five caches use `threading.Lock`. When `_load_json_cached()` is called via `asyncio.to_thread()`, the lock blocks a thread pool thread — which is fine. But `gap_context_helper.load_analysis_json()` is also called from `DbContentDataService.get_briefs()` which is `async def` — if a sync call to `load_analysis_json()` happens on the event loop thread (not via `to_thread`), the `threading.Lock` blocks the entire event loop until the file read completes. For a 20MB JSON file, that's noticeable.

**mtime-based invalidation is fragile.** It depends on filesystem stat calls, which are syscalls. For NFS or network-mounted volumes (not currently used but relevant for blob storage migration), stat calls can be slow or return stale data. And it doesn't help when the data source is PostgreSQL — the DB-backed services still read from these filesystem caches because the file-based data services are the fallback.

**No cross-worker invalidation.** When a pipeline writes new `analysis.json`, worker 1's cache notices on next request (mtime changed). But worker 2 doesn't check mtime until someone makes a request to worker 2. There's no push-based invalidation. With Redis, a pipeline can `DEL cache:gap:ramp:*` and all workers get fresh data on next request.

**FIFO eviction with max 10 entries is crude.** It doesn't account for entry size. Ten entries of `enriched_citations.json` at 20MB each would use 200MB per worker. Redis has proper memory management with configurable eviction policies.

---

## 3. Redis Cache Design

### Shared cache utility module

**New file:** `core/cache.py`

A thin wrapper that standardizes how all services cache and retrieve data:

```python
"""Redis-backed API response cache.

Replaces the five module-level _CACHE dicts with a shared Redis cache.
Each cached item gets a namespaced key and a TTL. Pipelines invalidate
by deleting keys matching a prefix pattern.

All operations are synchronous (sub-ms Redis calls) because the callers
are sync functions running in asyncio.to_thread().
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes


def cache_get(redis_sync, key: str) -> Optional[Any]:
    """Read a cached JSON value. Returns None on miss or error."""
    try:
        raw = redis_sync.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.debug("Cache miss (error) for %s", key, exc_info=True)
        return None


def cache_set(redis_sync, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Write a JSON value to cache with TTL. Fire-and-forget on error."""
    try:
        redis_sync.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        logger.debug("Cache write failed for %s", key, exc_info=True)


def cache_delete_pattern(redis_sync, pattern: str) -> int:
    """Delete all keys matching a pattern. Returns count deleted."""
    try:
        keys = redis_sync.keys(pattern)
        if keys:
            return redis_sync.delete(*keys)
        return 0
    except Exception:
        logger.debug("Cache pattern delete failed for %s", pattern, exc_info=True)
        return 0


def cache_delete(redis_sync, *keys: str) -> None:
    """Delete specific cache keys."""
    try:
        if keys:
            redis_sync.delete(*keys)
    except Exception:
        logger.debug("Cache delete failed", exc_info=True)
```

### Key naming convention

```
cache:{service}:{slug}:{identifier}
```

| Service | Key pattern | Example | TTL |
|---------|------------|---------|-----|
| Gap data | `cache:gap:{slug}:{filename}` | `cache:gap:ramp:analysis.json` | 5min |
| Content data | `cache:content:{slug}:{filename}` | `cache:content:ramp:blueprints.json` | 2min |
| Content brief detail | `cache:content:{slug}:brief:{brief_id}:{filename}` | `cache:content:ramp:brief:brief-001:eval_history.json` | 2min |
| Site audit | `cache:audit:{slug}:{audit_id}` | `cache:audit:ramp:abc-123-def` | 10min |
| Gap context | `cache:gap_ctx:{slug}` | `cache:gap_ctx:ramp` | 5min |
| Brand data | `cache:brand:{slug}:{type}` | `cache:brand:ramp:company_context` | 5min |

### TTL strategy

Shorter TTL for data that changes during pipeline execution (content briefs: 2 min). Longer TTL for data that only changes on pipeline completion (gap analysis: 5 min, site audit: 10 min). Pipeline finalization functions explicitly delete relevant cache keys for immediate freshness — the TTL is a safety net, not the primary invalidation mechanism.

---

## 4. Changes Per Service Module

### 4a. Gap Data Service

**File:** `api/services/gap_data_service.py`

**Delete:** `_CACHE`, `_CACHE_MAX_ENTRIES`, `_CACHE_LOCK`, the entire `_load_json_cached()` function.

**Replace with:**

```python
from core.cache import cache_get, cache_set
from core.redis import get_sync_redis_or_none

def _load_json_cached(artifacts_root: Path, slug: str, filename: str) -> Optional[Any]:
    """Load a gap analysis JSON file — Redis cache first, file fallback."""
    redis = get_sync_redis_or_none()
    
    if redis is not None:
        cache_key = f"cache:gap:{slug}:{filename}"
        cached = cache_get(redis, cache_key)
        if cached is not None:
            return cached
    
    # File read (fallback or cache miss)
    file_path = artifacts_root / "gap_analysis" / slug / filename
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    
    # Populate cache
    if redis is not None:
        cache_set(redis, cache_key, data, ttl=300)
    
    return data
```

No more mtime checking, no more threading.Lock, no more FIFO eviction. Redis handles all of it.

**Note on large files:** `enriched_citations.json` can be ~20MB. JSON-serialized into Redis, this is about 20MB per key. Redis handles this fine — single values up to 512MB are supported. The 5-minute TTL ensures it doesn't linger. But if memory becomes a concern, this specific file could be excluded from caching (read from file every time) or cached with a shorter TTL.

### 4b. Content Data Service

**File:** `api/services/content_data_service.py`

**Delete:** `_CACHE`, `_CACHE_MAX_ENTRIES`, `_CACHE_LOCK`, the `_load_json_cached()` function.

**Replace with** the same pattern, using `cache:content:{slug}:{filename}` keys and a 2-minute TTL (content data changes more frequently during pipeline execution).

The `_load_pipeline_state()` function (already modified in Session 2 to read from Redis hash) stays as-is — it's not part of this JSON file cache; it's the pipeline state system from Session 2.

### 4c. Site Audit Data Service

**File:** `core/services/json_site_audit_data.py`

**Delete:** `_CACHE`, `_CACHE_MAX`, `_CACHE_LOCK`, `_evict_if_full()`, and the mtime-based logic in `_load_audit_result()`.

**Replace with** the same pattern, using `cache:audit:{slug}:{audit_id}` keys and a 10-minute TTL (audit results don't change after completion).

### 4d. Gap Context Helper

**File:** `core/services/gap_context_helper.py`

**Delete:** `_GAP_CACHE`, `_GAP_CACHE_LOCK`, and the mtime-based logic in `load_analysis_json()`.

**Replace with** the same pattern, using `cache:gap_ctx:{slug}` key and a 5-minute TTL.

**Optimization opportunity:** This caches the same `analysis.json` that Cache 1 (gap_data_service) caches. After migration, you could deduplicate by having `load_analysis_json()` call `_load_json_cached()` from gap_data_service (now reading from the same Redis cache). But this introduces a cross-module dependency that might be messy. Simpler approach: let both cache under different keys — Redis deduplicates the storage internally if the data is identical, and the memory cost is minimal compared to the LLM API costs.

### 4e. Brand Data Service

**File:** `api/services/brand_data_service.py`

**Delete:** `_CACHE`, `_CACHE_MAX_ENTRIES`.

This one currently has no `threading.Lock` (the only unprotected cache). After migration, it gets the same Redis treatment as the others. Brand data artifacts (company context, style guide, personas) change only on research pipeline completion, so a 5-minute TTL is appropriate.

Note: `brand_data_service.py` doesn't have a `_load_json_cached()` function — it reads files directly in `_detect_artifact()` and `_detect_personas()`. The caching here should wrap the higher-level artifact detection, not individual file reads:

```python
def get_research_artifacts(artifacts_root: Path, slug: str) -> ResearchArtifactsResponse:
    redis = get_sync_redis_or_none()
    if redis is not None:
        cached = cache_get(redis, f"cache:brand:{slug}:artifacts")
        if cached is not None:
            return ResearchArtifactsResponse.model_validate(cached)
    
    # Compute (existing logic)
    result = _compute_research_artifacts(artifacts_root, slug)
    
    if redis is not None:
        cache_set(redis, f"cache:brand:{slug}:artifacts", result.model_dump(mode="json"), ttl=300)
    
    return result
```

---

## 5. Cache Invalidation — Pipeline Finalization

When a pipeline completes and writes new artifact files, it should explicitly invalidate the relevant cache keys so the next dashboard request gets fresh data.

### Where to add invalidation calls

| Pipeline | Finalization location | Keys to invalidate |
|----------|----------------------|-------------------|
| Gap Analysis | `api/tasks/runner.py` → `run_gap_pipeline_task()` finally block | `cache:gap:{slug}:*`, `cache:gap_ctx:{slug}` |
| Content v1.3 | `core/content_engine/pipeline_v13.py` → `_finalize_pipeline()` | `cache:content:{slug}:*` |
| Content v1.0 | `api/tasks/runner.py` → `run_content_pipeline_task()` finally block | `cache:content:{slug}:*` |
| KB / AP / VSG | respective runner finally blocks | `cache:brand:{slug}:*` |
| Site Audit | `api/tasks/runner.py` → `run_site_audit_task()` finally block | `cache:audit:{slug}:*` |
| Research Orchestrator | `api/tasks/runner.py` → `run_research_orchestrator_task()` finally block | `cache:brand:{slug}:*` |

**Pattern:**

```python
# In runner finally block (after pipeline completes or fails):
from core.cache import cache_delete_pattern
from core.redis import get_sync_redis_or_none

redis = get_sync_redis_or_none()
if redis:
    cache_delete_pattern(redis, f"cache:gap:{slug}:*")
    cache_delete_pattern(redis, f"cache:gap_ctx:{slug}")
```

**`KEYS` command warning:** `cache_delete_pattern()` uses `redis.keys(pattern)` which is O(N) over all keys. In production with many companies and cache entries, this could be slow. For now it's fine (likely <100 cache keys total). If this becomes a concern later, use `SCAN` instead of `KEYS`, or maintain a Redis Set of keys per slug for targeted deletion.

---

## 6. Sync Redis Client

The five cache consumers are all synchronous functions (called via `asyncio.to_thread()` or directly in sync context). They need a sync Redis client, not the async one from Session 0.

**File:** `core/redis.py`

Add a sync client alongside the existing async one (if not already added in Session 2 for distributed locks):

```python
_sync_client: Optional[redis.Redis] = None

def get_sync_redis() -> redis.Redis:
    """Return a synchronous Redis client (created lazily)."""
    global _sync_client
    if _sync_client is not None:
        return _sync_client
    with _lock:
        if _sync_client is not None:
            return _sync_client
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL is not set")
        _sync_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
        )
    return _sync_client

def get_sync_redis_or_none() -> Optional[redis.Redis]:
    """Sync Redis client or None if not configured."""
    if not settings.redis_url:
        return None
    try:
        return get_sync_redis()
    except RuntimeError:
        return None
```

If Session 2 already added this for `DbTaskStore._redis_sync`, reuse it. The key is making it available as a module-level import for the cache utility.

---

## 7. Configuration

No new config toggle needed. Cache uses Redis when `redis_url` is set and `get_sync_redis_or_none()` returns a client. When Redis is unavailable, each `_load_json_cached()` function falls through to direct file read with no caching (one-off file read on every request). This is slightly slower than the old in-memory cache but is the correct degradation behavior — it was always a cache, not a requirement.

---

## 8. What Does NOT Change

| Component | Reason unchanged |
|-----------|-----------------|
| `core/content_engine/prompt_registry.py` | Different cache type (LangSmith Hub TTL, not filesystem mtime). Keep in-memory. |
| Pipeline state (`pipeline_state.json` / Redis hash) | Already migrated in Session 2 |
| `DbContentDataService` / `DbGapDataService` | These read from PostgreSQL, not file caches. They might add Redis caching in the future but that's a separate concern. |
| All pipeline code | Pipelines write artifacts, they don't read from these caches |
| All graph modules | No cache interaction |
| EventBus / RedisEventBus | Separate concern |
| Approval flow | Separate concern |
| Distributed locks / semaphore | Separate concern |
| Frontend | No awareness of backend caching |

---

## 9. File Summary

| File | Action | Description |
|------|--------|-------------|
| `core/cache.py` | **Create** | `cache_get()`, `cache_set()`, `cache_delete_pattern()`, `cache_delete()` |
| `core/redis.py` | Edit | Add `get_sync_redis()` / `get_sync_redis_or_none()` if not already present from Session 2 |
| `api/services/gap_data_service.py` | Edit | Delete `_CACHE`, `_CACHE_LOCK`, old `_load_json_cached()`. Replace with Redis-backed version |
| `api/services/content_data_service.py` | Edit | Same pattern — delete old cache, replace with Redis |
| `core/services/json_site_audit_data.py` | Edit | Same — delete `_CACHE`, `_CACHE_LOCK`, `_evict_if_full()`, replace `_load_audit_result()` |
| `core/services/gap_context_helper.py` | Edit | Delete `_GAP_CACHE`, `_GAP_CACHE_LOCK`, replace `load_analysis_json()` |
| `api/services/brand_data_service.py` | Edit | Delete `_CACHE`, wrap `get_research_artifacts()` with Redis cache |
| `api/tasks/runner.py` | Edit | Add `cache_delete_pattern()` calls in pipeline finalization finally blocks (~6 runner functions) |
| `core/content_engine/pipeline_v13.py` | Edit | Add `cache_delete_pattern()` in `_finalize_pipeline()` |
| `tests/unit/test_redis_cache.py` | **Create** | Unit tests for `core/cache.py` and cache integration |
| `CLAUDE.md` | Edit | Document Redis cache key schema, invalidation strategy |

---

## 10. Redis Key Schema (Final — All Sessions)

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
| `semaphore:pipelines` | Sorted Set | Self-healing | Global pipeline concurrency limit | 5 |
| `cache:gap:{slug}:{filename}` | String (JSON) | 5min | Parsed gap analysis artifacts | **6** |
| `cache:content:{slug}:{filename}` | String (JSON) | 2min | Parsed content pipeline artifacts | **6** |
| `cache:content:{slug}:brief:{brief_id}:{filename}` | String (JSON) | 2min | Per-brief eval/stage data | **6** |
| `cache:audit:{slug}:{audit_id}` | String (JSON) | 10min | Parsed site audit result | **6** |
| `cache:gap_ctx:{slug}` | String (JSON) | 5min | analysis.json for content sidebar | **6** |
| `cache:brand:{slug}:artifacts` | String (JSON) | 5min | Research artifact detection results | **6** |

---

## 11. Tests

### `tests/unit/test_redis_cache.py`

1. **`cache_get` returns None on miss.** Mock `redis.get()` returning `None`. Verify `cache_get()` returns `None`.

2. **`cache_get` returns parsed JSON on hit.** Mock `redis.get()` returning `'{"a":1}'`. Verify `cache_get()` returns `{"a": 1}`.

3. **`cache_get` returns None on Redis error.** Mock `redis.get()` raising `ConnectionError`. Verify `cache_get()` returns `None` (graceful degradation).

4. **`cache_set` writes JSON with TTL.** Verify `redis.setex(key, ttl, json_string)` called.

5. **`cache_set` swallows errors.** Mock `redis.setex()` raising exception. Verify no exception propagates.

6. **`cache_delete_pattern` deletes matching keys.** Mock `redis.keys("cache:gap:ramp:*")` returning 3 keys. Verify `redis.delete(*keys)` called.

7. **Gap data `_load_json_cached` returns from Redis on hit.** Mock Redis returning cached data. Verify file is NOT read.

8. **Gap data `_load_json_cached` reads file and populates cache on miss.** Mock Redis returning `None`. Verify file is read, `cache_set()` called.

9. **Gap data `_load_json_cached` works without Redis.** Set `get_sync_redis_or_none()` → `None`. Verify file is read directly with no errors.

10. **Pipeline finalization invalidates cache.** After `_finalize_pipeline()`, verify `cache_delete_pattern(redis, "cache:content:{slug}:*")` called.

11. **Content data service uses 2min TTL.** Verify `cache_set(..., ttl=120)` called (not 300).

12. **Large file caching works.** Create a 20MB JSON dict, `cache_set` it, `cache_get` it back. Verify round-trip integrity.

---

## 12. Validation Checklist

### Without Redis (`get_sync_redis_or_none()` returns None):
1. All service functions read files directly — no errors
2. Performance is slightly worse (no caching) but functional
3. All existing tests pass

### With Redis:
4. First request for gap summary → cache miss → file read → Redis populated
5. Second request → cache hit → no file read (verify via logging or Redis `DEBUG OBJECT`)
6. `redis-cli GET cache:gap:ramp:analysis.json` returns JSON string
7. `redis-cli TTL cache:gap:ramp:analysis.json` returns ~300 (5min)
8. Run gap analysis pipeline → pipeline completes → `redis-cli GET cache:gap:ramp:analysis.json` returns nil (invalidated)
9. Next dashboard request → fresh file read → new data in cache
10. Content brief list uses 2-minute TTL: `redis-cli TTL cache:content:ramp:blueprints.json` returns ~120
11. Multiple workers serve requests → `redis-cli INFO memory` shows single copy (not per-worker duplicates)

### Performance test:
12. Load gap analysis dashboard with cold cache → measure response time
13. Load again with warm cache → measure response time — should be noticeably faster (file I/O eliminated)
14. For `enriched_citations.json` (~20MB): warm cache response should be significantly faster than cold (avoids 20MB JSON parse)

---

## 13. What Gets Deleted After This Session (Cleanup Inventory)

After Sessions 0-6, these are all the module-level constructs that are now dead code:

| Deleted construct | File | Replaced by |
|-------------------|------|-------------|
| `_CACHE: Dict` | `gap_data_service.py` | `core/cache.py` → Redis |
| `_CACHE_LOCK: threading.Lock` | `gap_data_service.py` | Redis (atomic) |
| `_CACHE_MAX_ENTRIES` | `gap_data_service.py` | Redis TTL + eviction |
| `_CACHE: Dict` | `content_data_service.py` | `core/cache.py` → Redis |
| `_CACHE_LOCK: threading.Lock` | `content_data_service.py` | Redis (atomic) |
| `_CACHE: dict` | `json_site_audit_data.py` | `core/cache.py` → Redis |
| `_CACHE_LOCK: threading.Lock` | `json_site_audit_data.py` | Redis (atomic) |
| `_evict_if_full()` | `json_site_audit_data.py` | Redis TTL |
| `_GAP_CACHE: Dict` | `gap_context_helper.py` | `core/cache.py` → Redis |
| `_GAP_CACHE_LOCK: threading.Lock` | `gap_context_helper.py` | Redis (atomic) |
| `_CACHE: Dict` | `brand_data_service.py` | `core/cache.py` → Redis |

That's 5 cache dicts, 4 threading locks, 5 FIFO eviction constants, and 1 helper function — all replaced by a single 40-line `core/cache.py` module backed by Redis.

---

## 14. Scope Boundaries — Do NOT Do These

- Do NOT migrate the prompt registry cache (`core/content_engine/prompt_registry.py`) — it's a different pattern (TTL-based API response cache, not filesystem mtime cache) and works correctly as-is
- Do NOT migrate any PostgreSQL-level cache (platform result cache, URL enrichment cache) — those are DB tables, not in-memory caches
- Do NOT change any pipeline code beyond adding invalidation calls in finally blocks
- Do NOT change any DB-backed service (`Db*DataService`) — they read from PostgreSQL, not these file caches
- Do NOT delete the file-reading logic from `_load_json_cached()` — it's the fallback when Redis is unavailable
- Do NOT change any graph module, approval flow, EventBus, semaphore, or distributed lock
- Do NOT change the frontend
- Do NOT attempt to cache the 20MB `enriched_citations.json` if Redis memory is constrained — exclude it and let it read from file every time. Caching correctness is more important than caching completeness.
