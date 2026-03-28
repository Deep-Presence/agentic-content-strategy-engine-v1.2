# Session 3: HITL RedisSaver — Persistent LangGraph Checkpoints

## Prerequisites

- Session 0 (Redis Infrastructure) complete — `core/redis.py`, `app.state.redis` available
- Sessions 1-2 complete — confirms Redis is working in production

## Objective

Replace `MemorySaver()` with LangGraph's `RedisSaver` across all HITL checkpoint graphs. After this session, HITL checkpoint state (the graph's interrupted position + accumulated state) is persisted in Redis. A pipeline can be interrupted at a HITL checkpoint, the Uvicorn worker can restart (or a different worker can pick it up), and the graph resumes from the exact checkpoint state. **This is the third and final piece that unlocks multi-worker deployment** (alongside RedisEventBus from Session 1 and distributed locks from Session 2).

No graph logic, no node functions, no state schemas, no invocation helpers change. Only the checkpointer backend changes.

---

## 1. Current Architecture — Six Copies of the Same Pattern

There are **six `_resolve_checkpointer()` functions** across six files, all identical:

```python
def _resolve_checkpointer(checkpointer: Any) -> BaseCheckpointSaver:
    """Return checkpointer if valid, otherwise default to MemorySaver."""
    if isinstance(checkpointer, BaseCheckpointSaver):
        return checkpointer
    return MemorySaver()
```

| File | Graphs built | Invocation helper |
|------|-------------|-------------------|
| `core/content_engine/graph_v13.py` | `build_topic_approval_graph()`, `build_brief_approval_graph()`, `build_content_review_graph_v13()` | `run_hitl_checkpoint()` |
| `core/content_engine/graph.py` | `build_content_review_graph()` (v1.0) | `run_content_review()` (standalone, no shared helper) |
| `core/research/knowledge_base/graph.py` | `build_kb_doc_review_graph()`, `build_kb_synthesis_review_graph()` | `run_kb_hitl_checkpoint()` |
| `core/research/audience_persona/graph.py` | `build_ap_brief_review_graph()`, `build_ap_profile_review_graph()` | `run_ap_hitl_checkpoint()` |
| `core/research/voice_style_guide/graph.py` | `build_vsg_author_review_graph()` | `run_vsg_hitl_checkpoint()` |
| `core/topic_discovery/graph.py` | `build_td_taxonomy_review_graph()`, `build_td_matrix_review_graph()`, `build_td_subdomain_selection_graph()` (deprecated) | `run_td_hitl_checkpoint()` |

**Total: 12 graph builders + 5 invocation helpers + 1 standalone runner (v1.0 `run_content_review`).**

### How graphs are built and invoked

Every graph builder follows the same pattern:
```python
def build_X_graph(checkpointer: Optional[Any] = None) -> Any:
    graph = StateGraph(SomeTypedDict)
    graph.add_node(...)
    graph.set_entry_point(...)
    graph.add_edge(...)
    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))
```

Callers in the pipeline either:
1. Call the builder with no argument → `_resolve_checkpointer(None)` → `MemorySaver()` ← **this is what we're changing**
2. Call the builder with an explicit checkpointer (only v1.0 `run_content_review` does this: `checkpointer = MemorySaver(); graph = build_content_review_graph(checkpointer=checkpointer)`)

### The v1.0 pipeline special case

`core/content_engine/pipeline.py` → `_run_v10_api_review()` creates its own `MemorySaver()` per brief:
```python
checkpointer = MemorySaver()
graph = build_content_review_graph(checkpointer=checkpointer)
```

This is the only place that passes an explicit checkpointer to a graph builder. All other call sites rely on the default `_resolve_checkpointer(None)`.

---

## 2. Dependency

### Add to `requirements.txt`:

```
langgraph-checkpoint-redis>=0.0.1
```

**Important:** Check the current version on PyPI. The package is `langgraph-checkpoint-redis` (note: hyphens, not underscores). It provides `RedisSaver` which implements `BaseCheckpointSaver`.

Verify compatibility with your current `langgraph` version. The checkpoint interface changed between langgraph versions. Run:
```bash
pip install langgraph-checkpoint-redis
python -c "from langgraph.checkpoint.redis import RedisSaver; print('OK')"
```

If the import path is different (e.g., `langgraph_checkpoint_redis.RedisSaver`), adjust accordingly. The package README has the current import path.

---

## 3. Shared Checkpointer Factory

### New file: `core/checkpointer.py`

Instead of changing six identical `_resolve_checkpointer()` functions, create one shared factory:

```python
"""Shared LangGraph checkpointer factory.

Returns RedisSaver when Redis is configured, MemorySaver otherwise.
Replaces six duplicated _resolve_checkpointer() functions across
graph modules.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_redis_saver: Optional[BaseCheckpointSaver] = None
_init_attempted: bool = False


def _init_redis_saver() -> Optional[BaseCheckpointSaver]:
    """Lazily create a RedisSaver singleton. Returns None on failure."""
    global _redis_saver, _init_attempted
    if _init_attempted:
        return _redis_saver
    _init_attempted = True
    try:
        from core.config.settings import settings
        if not settings.redis_url:
            return None
        from langgraph.checkpoint.redis import RedisSaver
        _redis_saver = RedisSaver(redis_url=settings.redis_url)
        logger.info("LangGraph RedisSaver initialized")
        return _redis_saver
    except Exception:
        logger.warning("Failed to initialize RedisSaver — falling back to MemorySaver", exc_info=True)
        return None


def get_checkpointer(override: Any = None) -> BaseCheckpointSaver:
    """Return a LangGraph checkpointer.

    Priority:
    1. Explicit override (if it's a valid BaseCheckpointSaver)
    2. RedisSaver (if REDIS_URL is set and redis is available)
    3. MemorySaver (fallback)

    This replaces the six _resolve_checkpointer() functions.
    """
    if isinstance(override, BaseCheckpointSaver):
        return override

    from core.config.settings import settings
    if getattr(settings, "redis_checkpointer", True) and settings.redis_url:
        redis_saver = _init_redis_saver()
        if redis_saver is not None:
            return redis_saver

    return MemorySaver()


def reset_checkpointer() -> None:
    """Reset cached RedisSaver. For testing."""
    global _redis_saver, _init_attempted
    _redis_saver = None
    _init_attempted = False
```

**Key design decisions:**

- **Singleton `RedisSaver`:** LangGraph's `RedisSaver` manages its own connection pool. Creating one per graph compilation would leak connections. One shared instance is correct.
- **Lazy initialization:** The factory doesn't try to connect to Redis at import time. First call to `get_checkpointer()` triggers initialization. This matches the lazy pattern in `core/db/engine.py` and `core/redis.py`.
- **Override still works:** Tests and CLI scripts can pass their own checkpointer. The `if isinstance(override, BaseCheckpointSaver)` guard preserves this.

---

## 4. Changes to Each Graph Module

### Pattern — identical change in all six files:

**Before:**
```python
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

def _resolve_checkpointer(checkpointer: Any) -> BaseCheckpointSaver:
    if isinstance(checkpointer, BaseCheckpointSaver):
        return checkpointer
    return MemorySaver()

def build_X_graph(checkpointer: Optional[Any] = None) -> Any:
    ...
    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))
```

**After:**
```python
from core.checkpointer import get_checkpointer

# DELETE _resolve_checkpointer() function
# DELETE: from langgraph.checkpoint.memory import MemorySaver
# KEEP: from langgraph.checkpoint.base import BaseCheckpointSaver (if used in type hints)

def build_X_graph(checkpointer: Optional[Any] = None) -> Any:
    ...
    return graph.compile(checkpointer=get_checkpointer(checkpointer))
```

### File-by-file changes:

**`core/content_engine/graph_v13.py`**
- Delete `_resolve_checkpointer()` (lines ~35-38)
- Delete `from langgraph.checkpoint.memory import MemorySaver`
- Add `from core.checkpointer import get_checkpointer`
- Update 3 graph builders: `build_topic_approval_graph()`, `build_brief_approval_graph()`, `build_content_review_graph_v13()`
- `run_hitl_checkpoint()` — **no change** (it receives a pre-compiled graph, doesn't touch checkpointer)

**`core/content_engine/graph.py`** (v1.0)
- No local `_resolve_checkpointer()` to delete (this file passes checkpointer directly)
- `build_content_review_graph(checkpointer=None)` → change to `graph.compile(checkpointer=get_checkpointer(checkpointer))`
- `run_content_review()` — **no change** (calls `build_content_review_graph(checkpointer=checkpointer)`)

**`core/research/knowledge_base/graph.py`**
- Delete `_resolve_checkpointer()`
- Add `from core.checkpointer import get_checkpointer`
- Update 2 builders: `build_kb_doc_review_graph()`, `build_kb_synthesis_review_graph()`
- `run_kb_hitl_checkpoint()` — **no change**

**`core/research/audience_persona/graph.py`**
- Delete `_resolve_checkpointer()`
- Add `from core.checkpointer import get_checkpointer`
- Update 2 builders: `build_ap_brief_review_graph()`, `build_ap_profile_review_graph()`
- `run_ap_hitl_checkpoint()` — **no change**

**`core/research/voice_style_guide/graph.py`**
- Delete `_resolve_checkpointer()`
- Add `from core.checkpointer import get_checkpointer`
- Update 1 builder: `build_vsg_author_review_graph()`
- `run_vsg_hitl_checkpoint()` — **no change**

**`core/topic_discovery/graph.py`**
- Delete `_resolve_checkpointer()`
- Add `from core.checkpointer import get_checkpointer`
- Update 3 builders: `build_td_taxonomy_review_graph()`, `build_td_matrix_review_graph()`, `build_td_subdomain_selection_graph()`
- `run_td_hitl_checkpoint()` — **no change**

### The v1.0 pipeline special case:

**`core/content_engine/pipeline.py`** → `_run_v10_api_review()`:

```python
# Before:
checkpointer = MemorySaver()
graph = build_content_review_graph(checkpointer=checkpointer)

# After:
from core.checkpointer import get_checkpointer
checkpointer = get_checkpointer()
graph = build_content_review_graph(checkpointer=checkpointer)
```

This is the only call site that explicitly creates a `MemorySaver()`. After this change, it gets `RedisSaver` when Redis is available.

---

## 5. Configuration

### File: `core/config/settings.py`

Add one setting:

```python
# --- Redis ---
# ... (existing from Session 0)
redis_checkpointer: bool = True  # Use RedisSaver for LangGraph HITL checkpoints
```

Default is `True` (unlike the other Redis toggles which default to `False`). Rationale: if Redis is available (`redis_url` is set), you always want persistent checkpoints. There's no reason to opt out — `RedisSaver` is a strict upgrade over `MemorySaver`. The toggle exists purely as an emergency kill switch.

If `redis_url` is not set, `get_checkpointer()` falls back to `MemorySaver` regardless of this setting.

---

## 6. Thread Safety Consideration

LangGraph's `graph.invoke()` calls are wrapped in `asyncio.to_thread()` across all invocation helpers:

```python
result = await asyncio.to_thread(graph.invoke, initial_state, config)
```

This means the checkpointer's `put()` and `get()` methods are called from a worker thread, not the async event loop. `MemorySaver` handles this fine (it's just dict operations). `RedisSaver` uses `redis-py` sync client internally (not `redis.asyncio`), so it's also thread-safe for this pattern.

**Verify this:** Check the `RedisSaver` source code or docs to confirm it uses sync Redis. If it uses `redis.asyncio`, then calling it from `to_thread()` would fail. In that case, wrap invocations differently — but based on LangGraph's design, `RedisSaver` should use sync Redis precisely because `graph.invoke()` is synchronous.

---

## 7. Thread ID Uniqueness and Collisions

LangGraph uses `thread_id` in the config to namespace checkpoint state:
```python
config = {"configurable": {"thread_id": thread_id}}
```

With `MemorySaver`, thread_id collisions between different pipelines were harmless — each `MemorySaver` instance was isolated. With `RedisSaver`, **all graphs share the same Redis instance**, so thread_id collisions would cause one pipeline to load another's checkpoint state.

Check the current thread_id patterns:

| Module | Thread ID pattern | Risk |
|--------|-------------------|------|
| `graph_v13.py` `run_hitl_checkpoint()` | `f"{task_id or 'cli'}-topic-approval-r{retry}"` | Safe — task_id is UUID |
| `graph_v13.py` brief approval | `f"{task_id or 'cli'}-brief-approval-{brief_id}-r{retry}"` | Safe |
| `graph_v13.py` content review | `f"{task_id or 'cli'}-content-review-{brief_id}"` | Safe |
| `pipeline.py` v1.0 review | `f"{task_id}-content-review-{content.brief_id}"` | Safe |
| KB, AP, VSG, TD | Callers pass thread_id from pipeline code | Verify in pipeline code |

**Action:** Grep all `run_*_hitl_checkpoint()` call sites in pipeline files to verify thread_ids contain `task_id` (UUID). If any use only slug or brief_id without task_id, they could collide between runs. Add task_id prefix if missing.

---

## 8. Redis Key Cleanup / TTL

`RedisSaver` stores checkpoint data in Redis using its own key schema (typically `langgraph:checkpoint:{thread_id}:*`). These accumulate over time.

**Options:**
1. **Let them accumulate + periodic cleanup.** Run a weekly job that scans `langgraph:checkpoint:*` keys older than 48 hours and deletes them.
2. **Set TTL on checkpoint keys.** If `RedisSaver` supports a `ttl` parameter, use it. Check the constructor.
3. **Manual cleanup after pipeline completion.** After each pipeline run finishes (success or failure), delete checkpoint keys for that task's thread_ids.

**Recommended: Option 1 initially.** Checkpoint data per graph is small (a few KB of serialized state). Even 1000 pipeline runs would use <10MB. A weekly cleanup cron is sufficient. Don't over-engineer this.

If `RedisSaver` accepts a `ttl` parameter in its constructor, use `ttl=172800` (48 hours). This is the cleanest approach — zero manual cleanup.

---

## 9. What Does NOT Change

| Component | Reason unchanged |
|-----------|-----------------|
| All graph node functions (`_topic_present`, `_approval_gate`, etc.) | Pure state transformations, no checkpointer awareness |
| All state schemas (`TopicApprovalState`, `KBDocReviewState`, etc.) | TypedDict definitions, no checkpointer awareness |
| All invocation helpers (`run_hitl_checkpoint`, `run_kb_hitl_checkpoint`, etc.) | Receive pre-compiled graph, don't touch checkpointer |
| All pipeline orchestrators | Call graph builders, pass result to invocation helpers |
| `interrupt()` / `Command(resume=...)` mechanics | LangGraph core, checkpointer-agnostic |
| `TaskStoreProtocol` approval flow (`wait_for_approval`, `submit_approval`) | Orthogonal to checkpointer — handles the HTTP approval, not graph state |
| EventBus / RedisEventBus | SSE events are separate from checkpoint state |
| Frontend | No awareness of checkpointer backend |
| `_SubPipelineEventProxy` | Only wraps `publish()`, no checkpointer interaction |

---

## 10. File Summary

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | Edit | Add `langgraph-checkpoint-redis` |
| `core/checkpointer.py` | **Create** | Shared `get_checkpointer()` factory, singleton `RedisSaver` |
| `core/content_engine/graph_v13.py` | Edit | Delete `_resolve_checkpointer()`, import `get_checkpointer`, update 3 builders |
| `core/content_engine/graph.py` | Edit | Update `build_content_review_graph()` to use `get_checkpointer()` |
| `core/content_engine/pipeline.py` | Edit | Replace `MemorySaver()` with `get_checkpointer()` in `_run_v10_api_review()` |
| `core/research/knowledge_base/graph.py` | Edit | Delete `_resolve_checkpointer()`, import `get_checkpointer`, update 2 builders |
| `core/research/audience_persona/graph.py` | Edit | Same — delete local copy, update 2 builders |
| `core/research/voice_style_guide/graph.py` | Edit | Same — delete local copy, update 1 builder |
| `core/topic_discovery/graph.py` | Edit | Same — delete local copy, update 3 builders |
| `core/config/settings.py` | Edit | Add `redis_checkpointer: bool = True` |
| `tests/unit/test_checkpointer.py` | **Create** | Unit tests for `get_checkpointer()` factory |
| `CLAUDE.md` | Edit | Document RedisSaver, config, checkpoint key schema |

---

## 11. Tests

### `tests/unit/test_checkpointer.py`

1. **`get_checkpointer()` returns `MemorySaver` when no Redis URL.** Patch `settings.redis_url = None`, verify `isinstance(result, MemorySaver)`.

2. **`get_checkpointer()` returns `RedisSaver` when Redis URL is set.** Patch `settings.redis_url = "redis://localhost:6379"`, mock `RedisSaver` constructor, verify it's called and returned.

3. **`get_checkpointer()` falls back to `MemorySaver` on `RedisSaver` init failure.** Patch `RedisSaver` constructor to raise `ConnectionError`, verify `MemorySaver` returned.

4. **`get_checkpointer(override=custom)` returns the override.** Pass a mock `BaseCheckpointSaver`, verify it's returned as-is without touching Redis.

5. **Singleton: `RedisSaver` created only once.** Call `get_checkpointer()` twice, verify `RedisSaver` constructor called only once.

6. **`reset_checkpointer()` clears singleton.** Call `get_checkpointer()`, call `reset_checkpointer()`, call `get_checkpointer()` again — `RedisSaver` constructor called twice.

### Integration test (requires Redis):

7. **Graph interrupt/resume roundtrip through RedisSaver.** Build a minimal graph with one interrupt node, invoke it, verify interrupt, resume with approval data, verify final state. Use real Redis (test database).

8. **Checkpoint survives RedisSaver recreation.** Build graph, invoke until interrupt, delete the `RedisSaver` instance, create a new one from the same Redis URL, resume — verify state is recovered. This simulates a worker restart.

### Existing test compatibility:

9. **All existing HITL tests pass.** Most tests either use `auto_approve=True` (skip interrupt entirely) or mock the task_store approval flow. They should work with either `MemorySaver` or `RedisSaver`. If any test explicitly creates `MemorySaver()` and passes it as a checkpointer override, it continues to work via the `isinstance(override, BaseCheckpointSaver)` guard.

---

## 12. Redis Key Schema (Cumulative)

| Key Pattern | Type | TTL | Purpose | Session |
|---|---|---|---|---|
| `sse:{task_id}` | Stream | 24h | SSE event stream | 1 |
| `sse:counter:{task_id}` | String | 24h | Monotonic event ID counter | 1 |
| `pipeline_state:{effective_slug}` | Hash | 24h | Per-brief in-flight status | 2 |
| `lock:{pipeline}:{effective_slug}` | String | 2h | Distributed slug lock | 2 |
| `langgraph:checkpoint:*` | (RedisSaver internal) | 48h (if configurable) | HITL graph checkpoint state | **3** |

---

## 13. Validation Checklist

### Without Redis (REDIS_URL unset):
1. All HITL flows work with `MemorySaver` as before
2. `get_checkpointer()` returns `MemorySaver` — verify via log or debugger
3. All existing tests pass

### With Redis (REDIS_URL set):
4. App starts, `get_checkpointer()` returns `RedisSaver` — verify via log: "LangGraph RedisSaver initialized"
5. **Content v1.3 pipeline with `auto_approve: false`:**
   - Pipeline reaches Topic Approval → SSE emits `pending_approval` → submit approval via API → pipeline resumes correctly
   - Pipeline reaches Brief Approval → same flow
   - Pipeline reaches Content Review → same flow
6. **Knowledge Base pipeline with `auto_approve: false`:**
   - HITL-1 (doc review) → approve → HITL-2 (doc review) → approve → HITL-3 (synthesis) → approve
7. **Audience Persona pipeline:**
   - HITL-1 (brief review) → approve → HITL-2 (profile review) → approve
8. **Voice Style Guide pipeline:**
   - HITL-1 (author review) → approve
9. **Topic Discovery pipeline:**
   - HITL-1 (taxonomy review) → approve → HITL-2 (matrix review) → approve
10. **Research Orchestrator (KB → AP → VSG) with `auto_approve: false`:**
    - All HITL checkpoints across all three sub-pipelines work correctly
    - Sub-pipeline event proxying still works (terminal events rewritten)

### Crash recovery test (the key validation):
11. Start a content pipeline with `auto_approve: false`
12. Let it reach HITL-1 (Topic Approval) — SSE shows `pending_approval`
13. **Kill the Uvicorn process** (`kill -9`)
14. Restart Uvicorn
15. Submit the approval via API → verify the pipeline resumes from the checkpoint and completes successfully
16. Check Redis: `redis-cli KEYS langgraph:checkpoint:*` shows checkpoint data for the task

### Parity test:
17. Run same pipeline with `redis_checkpointer=false` (forces MemorySaver) then `=true`. Final pipeline output must be identical.

---

## 14. Scope Boundaries — Do NOT Do These

- Do NOT change any graph node function (`_topic_present`, `_approval_gate`, etc.)
- Do NOT change any state schema (`TopicApprovalState`, etc.)
- Do NOT change any invocation helper (`run_hitl_checkpoint`, `run_kb_hitl_checkpoint`, etc.)
- Do NOT change the `interrupt()` / `Command(resume=...)` pattern
- Do NOT change `TaskStoreProtocol` or approval flow
- Do NOT change EventBus / RedisEventBus
- Do NOT change pipeline orchestrator logic
- Do NOT refactor the five duplicated invocation helpers into one shared helper (tempting but out of scope — separate cleanup task)
- Do NOT refactor the `_has_interrupt` / `_get_interrupt_value` helper copies (same — out of scope)
- Do NOT change the frontend
- Do NOT migrate HITL approval queues to Redis (Session 4)
