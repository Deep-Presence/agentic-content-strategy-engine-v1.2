# Session 4: Redis Approval Queues — HITL Cross-Worker Delivery

## Prerequisites

- Session 0 (Redis Infrastructure) complete
- Session 2 (Redis Hashes / Distributed Locks) complete — `DbTaskStore` already has `self._redis_sync`
- Session 3 (RedisSaver) complete — checkpoint state persists in Redis

## Objective

Replace the in-memory `asyncio.Queue` used for HITL approval delivery with Redis Lists (`LPUSH` / `BRPOP`). After this session, a user can submit an approval on any Uvicorn worker and the pipeline blocked on `wait_for_approval()` on any other worker receives it. **This is the final piece that makes the entire HITL flow multi-worker safe.** Combined with Sessions 1-3, the system is ready for multi-worker deployment.

No changes to the `TaskStoreProtocol` interface. No changes to approval API endpoints. No changes to graph invocation helpers. No changes to the frontend.

---

## 1. Current Implementation — Identical in Both Task Stores

### `wait_for_approval()` — async, blocks until approval arrives

Both `TaskStore` (JSON) and `DbTaskStore` have the same logic:

```python
async def wait_for_approval(self, task_id: str, timeout: float = 86400) -> Dict[str, Any]:
    if task_id not in self._approval_queues:
        self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
    try:
        data = await asyncio.wait_for(
            self._approval_queues[task_id].get(), timeout=timeout
        )
    except asyncio.TimeoutError:
        data = {"decision": "reject", "revision_note": f"Approval timed out after {int(timeout)}s"}
    self._approval_queues.pop(task_id, None)  # cleanup after consumption
    return data
```

**Key behaviors to preserve:**
- Blocks until data appears or timeout expires
- On timeout: returns a reject decision (pipeline doesn't hang forever)
- After consumption: cleans up the queue (one-shot delivery)
- Can be called before or after `submit_approval` — ordering doesn't matter

### `submit_approval()` — sync, pushes data into the queue

Both implementations have the same logic:

```python
def submit_approval(self, task_id, decision, revision_note=None,
                    stage=None, approval_data=None, expected_nonce=None):
    # 1. Validate task exists
    if task_id not in self._tasks:
        raise TaskNotFoundError(task_id)
    task = self._tasks[task_id]

    # 2. Nonce validation (TOCTOU / replay prevention)
    if expected_nonce is not None:
        current_nonce = (task.approval_payload or {}).get("checkpoint_nonce")
        if current_nonce != expected_nonce:
            raise ApprovalWindowError("Stale or replayed approval: nonce mismatch")

    # 3. Record in approval_history (audit trail)
    record = ApprovalRecord(task_id=task_id, stage=resolved_stage, decision=decision, ...)
    task.approval_history.append(record)

    # 4. Persist approval history to DB (DbTaskStore only)
    asyncio.create_task(self._db_update(task_id, approval_history=[...]))

    # 5. Queue the payload
    payload = approval_data if approval_data is not None else {"decision": decision, "revision_note": revision_note}
    if task_id not in self._approval_queues:
        self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
    try:
        self._approval_queues[task_id].put_nowait(payload)
    except asyncio.QueueFull:
        raise ApprovalWindowError("Approval already submitted — queue full")
```

**Key behaviors to preserve:**
- `submit_approval()` is **synchronous** (not async) — all router callers call it as a plain function
- Nonce validation happens **before** queuing — atomic in single-threaded async Python
- `QueueFull` → `ApprovalWindowError` prevents duplicate submissions
- `approval_data` (if provided) is the exact dict placed on the queue — the graph invocation helper reads it directly
- `approval_history` is persisted for audit

### Callers of `submit_approval()` — all approval API endpoints:

| Router file | Endpoint | Stage |
|------------|----------|-------|
| `api/routers/content_v13.py` | `POST /{run_id}/approve/topics` | `topic_approval` |
| `api/routers/content_v13.py` | `POST /{run_id}/approve/briefs` | `brief_approval` |
| `api/routers/content_v13.py` | `POST /{run_id}/approve/content` | `content_review` |
| `api/routers/knowledge_base.py` | `POST /{run_id}/approve` | `kb_checkpoint_{1,2,3}` |
| `api/routers/audience_persona.py` | `POST /{run_id}/approve/briefs` | `persona_brief_review` |
| `api/routers/audience_persona.py` | `POST /{run_id}/approve/profiles` | `persona_profile_review` |
| `api/routers/voice_style_guide.py` | `POST /{run_id}/approve/authors` | `vsg_author_review` |
| `api/routers/topic_discovery.py` | `POST /{run_id}/approve/taxonomy` | `td_taxonomy_review` |
| `api/routers/topic_discovery.py` | `POST /{run_id}/approve/subdomains` | `td_subdomain_selection` |
| `api/routers/topic_discovery.py` | `POST /{run_id}/approve/matrix` | `td_matrix_review` |

**None of these change.** They all call `task_store.submit_approval(...)` which is the same protocol method.

### Callers of `wait_for_approval()` — all graph invocation helpers:

| File | Function | Called from |
|------|----------|------------|
| `core/content_engine/graph_v13.py` | `run_hitl_checkpoint()` | Content v1.3 pipeline |
| `core/content_engine/pipeline.py` | `_run_v10_api_review()` | Content v1.0 pipeline |
| `core/research/knowledge_base/graph.py` | `run_kb_hitl_checkpoint()` | KB pipeline |
| `core/research/audience_persona/graph.py` | `run_ap_hitl_checkpoint()` | AP pipeline |
| `core/research/voice_style_guide/graph.py` | `run_vsg_hitl_checkpoint()` | VSG pipeline |
| `core/topic_discovery/graph.py` | `run_td_hitl_checkpoint()` | TD pipeline |

**None of these change.** They all call `await task_store.wait_for_approval(task_id)` which is the same protocol method.

---

## 2. Redis Design

### Key: `approval:{task_id}`

Redis List — used as a blocking queue.

**Producer (submit_approval):**
```
LPUSH approval:{task_id} '{"decision":"approve","topic_decision":"approve",...}'
```

**Consumer (wait_for_approval):**
```
BRPOP approval:{task_id} 86400
```

`BRPOP` blocks until an element is available or the timeout expires. This is the exact semantic as `asyncio.Queue.get()` with timeout.

### Duplicate submission prevention

With `asyncio.Queue(maxsize=1)`, a second `put_nowait()` raises `QueueFull`. With Redis Lists, there's no built-in maxsize. Use a Redis key as a "submitted" flag:

```
SET approval:flag:{task_id} 1 NX EX 86400
```

If `SET NX` returns `False`, the approval was already submitted → raise `ApprovalWindowError`. This is checked in `submit_approval()` before `LPUSH`.

### Nonce validation in multi-worker context

The nonce is stored in `task.approval_payload.checkpoint_nonce`. In the current single-worker model, `submit_approval()` reads it from the in-memory `_tasks` dict. In multi-worker mode, the task object on the submitting worker might be stale.

**Solution:** Store the current nonce in Redis when the pipeline sets it:

```
SET approval:nonce:{task_id} "{nonce}" EX 86400
```

Written by `update_task()` when `approval_payload` is set (the invocation helpers do `task_store.update_task(task_id, approval_payload={...checkpoint_nonce...})`). Read by `submit_approval()` for validation instead of reading from local `_tasks` dict.

### TTL / cleanup

All approval keys get 24-hour TTL:
- `approval:{task_id}` — the queue itself
- `approval:flag:{task_id}` — duplicate prevention flag  
- `approval:nonce:{task_id}` — current checkpoint nonce

After `wait_for_approval()` consumes the message, delete all three keys explicitly. TTL is the safety net for cases where cleanup doesn't happen (crash, timeout).

---

## 3. Implementation in `DbTaskStore`

### File: `core/services/db_task_store.py`

This is where all changes go. The `DbTaskStore` is the primary task store (Session 2 already added `self._redis_sync` to it).

### Modified `wait_for_approval()`:

```python
async def wait_for_approval(self, task_id: str, timeout: float = 86400) -> Dict[str, Any]:
    if self._redis_sync is not None:
        return await self._wait_for_approval_redis(task_id, timeout)
    # Fallback: existing asyncio.Queue logic
    ...existing code...

async def _wait_for_approval_redis(self, task_id: str, timeout: float) -> Dict[str, Any]:
    """Block on Redis BRPOP until approval arrives or timeout."""
    key = f"approval:{task_id}"
    flag_key = f"approval:flag:{task_id}"
    nonce_key = f"approval:nonce:{task_id}"
    
    # BRPOP is a blocking call — run in thread to avoid blocking the event loop
    result = await asyncio.to_thread(
        self._redis_sync.brpop, key, timeout=int(timeout)
    )
    
    if result is None:
        # Timeout
        logger.warning("Approval timed out after %.0fs for task %s", timeout, task_id)
        data = {"decision": "reject", "revision_note": f"Approval timed out after {int(timeout)}s"}
    else:
        # result is (key_name, value_string)
        _, raw = result
        data = json.loads(raw)
    
    # Cleanup
    self._redis_sync.delete(key, flag_key, nonce_key)
    
    # Also clean local queue if it exists (hybrid safety)
    self._approval_queues.pop(task_id, None)
    
    return data
```

**Why `asyncio.to_thread(self._redis_sync.brpop, ...)`?**

`wait_for_approval()` is `async def` and called with `await` from graph invocation helpers. `BRPOP` is a blocking call that blocks the calling thread for up to `timeout` seconds. We can't use `self._redis_sync.brpop()` directly in async context — it would block the event loop. `asyncio.to_thread()` runs it in the thread pool, freeing the event loop.

This is the same pattern used for `graph.invoke()` in the HITL invocation helpers.

### Modified `submit_approval()`:

```python
def submit_approval(self, task_id, decision, revision_note=None,
                    stage=None, approval_data=None, expected_nonce=None):
    # 1. Task existence check (still in-memory — fast path)
    if task_id not in self._tasks:
        raise TaskNotFoundError(task_id)
    task = self._tasks[task_id]

    # 2. Nonce validation — Redis-first if available
    if expected_nonce is not None:
        if self._redis_sync is not None:
            nonce_key = f"approval:nonce:{task_id}"
            current_nonce = self._redis_sync.get(nonce_key)
        else:
            current_nonce = (task.approval_payload or {}).get("checkpoint_nonce")
        if current_nonce != expected_nonce:
            raise ApprovalWindowError(
                f"Stale or replayed approval: nonce mismatch "
                f"(expected {expected_nonce}, current {current_nonce})"
            )

    # 3. Duplicate submission check — Redis-first if available
    if self._redis_sync is not None:
        flag_key = f"approval:flag:{task_id}"
        was_set = self._redis_sync.set(flag_key, "1", nx=True, ex=86400)
        if not was_set:
            raise ApprovalWindowError(
                f"Approval already submitted for task {task_id}"
            )

    # 4. Record in approval_history (unchanged)
    resolved_stage = stage or (task.approval_payload or {}).get("stage") or task.current_step or "unknown"
    record = ApprovalRecord(task_id=task_id, stage=resolved_stage, decision=decision, revision_note=revision_note)
    task.approval_history.append(record)
    task.updated_at = datetime.now(timezone.utc)
    asyncio.create_task(self._db_update(task_id, approval_history=[r.model_dump(mode="json") for r in task.approval_history]))

    # 5. Queue the payload — Redis or local
    payload = approval_data if approval_data is not None else {"decision": decision, "revision_note": revision_note}
    
    if self._redis_sync is not None:
        key = f"approval:{task_id}"
        self._redis_sync.lpush(key, json.dumps(payload))
        self._redis_sync.expire(key, 86400)
    else:
        # Fallback: existing asyncio.Queue logic
        if task_id not in self._approval_queues:
            self._approval_queues[task_id] = asyncio.Queue(maxsize=1)
        try:
            self._approval_queues[task_id].put_nowait(payload)
        except asyncio.QueueFull:
            raise ApprovalWindowError(f"Approval already submitted for task {task_id} — queue full")
```

### Modified `update_task()` — store nonce in Redis:

When the invocation helper sets `approval_payload` (which contains the `checkpoint_nonce`), also write the nonce to Redis:

```python
def update_task(self, task_id: str, **kwargs: Any) -> PipelineTask:
    ...existing code...
    
    # If approval_payload is being set and contains a nonce, store in Redis
    if self._redis_sync is not None and "approval_payload" in kwargs:
        payload = kwargs["approval_payload"]
        if payload is not None:
            nonce = payload.get("checkpoint_nonce")
            if nonce:
                nonce_key = f"approval:nonce:{task_id}"
                self._redis_sync.set(nonce_key, nonce, ex=86400)
        else:
            # approval_payload being cleared (set to None) — clean up nonce
            nonce_key = f"approval:nonce:{task_id}"
            self._redis_sync.delete(nonce_key)
            # Also clean up the flag for next checkpoint
            flag_key = f"approval:flag:{task_id}"
            self._redis_sync.delete(flag_key)
    
    ...rest of existing code...
```

This is critical: after each HITL checkpoint is consumed, the invocation helper does `task_store.update_task(task_id, approval_payload=None)`. This clears the nonce and flag, allowing the next checkpoint in the same pipeline to accept a new approval.

---

## 4. The Atomicity Question

In single-worker mode, `submit_approval()` has a nice atomicity property: nonce check + queue put happen in the same synchronous function with no `await` between them. In Python's cooperative multitasking, no other coroutine can run between the nonce check and the queue put.

With Redis, there's a gap between `redis.get(nonce_key)` and `redis.lpush(approval:...)`. Another request could theoretically submit between those two calls. But this is a very narrow window (microseconds), and the duplicate flag (`SET NX`) provides the real protection. The nonce check prevents stale/replayed approvals; the flag prevents concurrent duplicates. Together they cover the same ground as the old atomic check.

If you want true atomicity, use a Lua script:

```lua
-- Atomic nonce check + flag set + queue push
local nonce_key = KEYS[1]  -- approval:nonce:{task_id}
local flag_key = KEYS[2]   -- approval:flag:{task_id}
local queue_key = KEYS[3]  -- approval:{task_id}
local expected_nonce = ARGV[1]
local payload = ARGV[2]
local ttl = tonumber(ARGV[3])

-- Nonce check
local current = redis.call("GET", nonce_key)
if expected_nonce ~= "" and current ~= expected_nonce then
    return {err = "nonce_mismatch"}
end

-- Duplicate check
if redis.call("SET", flag_key, "1", "NX", "EX", ttl) == false then
    return {err = "already_submitted"}
end

-- Push
redis.call("LPUSH", queue_key, payload)
redis.call("EXPIRE", queue_key, ttl)
return "ok"
```

This is optional but cleaner. Evaluate whether the complexity is worth it for the current scale. The non-Lua version is simpler and functionally correct for single-digit concurrent users per company.

---

## 5. The JSON `TaskStore` — Minimal Changes

### File: `api/tasks/store.py`

The JSON `TaskStore` is the fallback when `DATABASE_URL` is not set. It doesn't have a Redis client. **Leave its approval queue logic unchanged** — it continues using `asyncio.Queue`. When Redis migration is complete and `DATABASE_URL` is mandatory (Phase A from the migration plan), this class gets deleted entirely.

No changes to this file in this session.

---

## 6. Configuration

No new config toggle needed. The approval queue uses Redis when `self._redis_sync is not None` on `DbTaskStore` (set in Session 2 when `redis_client` is passed to the constructor). This is an automatic upgrade — if Redis is available and the DbTaskStore has a Redis client, approvals go through Redis.

---

## 7. What Does NOT Change

| Component | Reason unchanged |
|-----------|-----------------|
| `TaskStoreProtocol` | Same `wait_for_approval` / `submit_approval` signatures |
| `api/tasks/store.py` (JSON TaskStore) | Fallback, keeps asyncio.Queue |
| All 10 approval router endpoints | Call `task_store.submit_approval(...)` — same interface |
| All 6 graph invocation helpers | Call `await task_store.wait_for_approval(task_id)` — same interface |
| `_SubPipelineEventProxy` | No interaction with approval flow |
| `ApprovalRecord` model | Unchanged |
| `approval_history` persistence | Unchanged — still appended locally, persisted to DB |
| Frontend approval UI | Sends same POST requests to same endpoints |
| `EventBus` / `RedisEventBus` | Separate concern — SSE event delivery |
| LangGraph checkpointer | Separate concern — graph state persistence |

---

## 8. File Summary

| File | Action | Description |
|------|--------|-------------|
| `core/services/db_task_store.py` | Edit | Modify `wait_for_approval()`, `submit_approval()`, `update_task()` to use Redis BRPOP/LPUSH with asyncio.Queue fallback |
| `tests/unit/test_approval_queue_redis.py` | **Create** | Unit tests for Redis approval flow |
| `CLAUDE.md` | Edit | Document Redis approval keys, flow diagram |

That's it. **Three files.** This is the smallest session scope of all six Redis services because the change is entirely internal to `DbTaskStore` — no callers change.

---

## 9. Redis Key Schema (Cumulative)

| Key Pattern | Type | TTL | Purpose | Session |
|---|---|---|---|---|
| `sse:{task_id}` | Stream | 24h | SSE event stream | 1 |
| `sse:counter:{task_id}` | String | 24h | Monotonic event ID counter | 1 |
| `pipeline_state:{effective_slug}` | Hash | 24h | Per-brief in-flight status | 2 |
| `lock:{pipeline}:{effective_slug}` | String | 2h | Distributed slug lock | 2 |
| `langgraph:checkpoint:*` | (RedisSaver internal) | 48h | HITL graph checkpoint state | 3 |
| `approval:{task_id}` | List | 24h | HITL approval payload queue | **4** |
| `approval:flag:{task_id}` | String | 24h | Duplicate submission prevention | **4** |
| `approval:nonce:{task_id}` | String | 24h | Current checkpoint nonce | **4** |

---

## 10. Tests

### `tests/unit/test_approval_queue_redis.py`

1. **`wait_for_approval` returns data from Redis BRPOP.** Mock `_redis_sync.brpop()` returning `("approval:task-1", '{"decision":"approve"}')`. Verify returned dict is `{"decision": "approve"}`.

2. **`wait_for_approval` returns reject on timeout.** Mock `_redis_sync.brpop()` returning `None` (timeout). Verify returned dict has `decision: "reject"`.

3. **`wait_for_approval` cleans up keys after consumption.** Verify `_redis_sync.delete()` called with `approval:{task_id}`, `approval:flag:{task_id}`, `approval:nonce:{task_id}`.

4. **`submit_approval` pushes to Redis.** Verify `_redis_sync.lpush("approval:{task_id}", ...)` called with JSON-serialized payload.

5. **`submit_approval` sets duplicate flag.** Verify `_redis_sync.set("approval:flag:{task_id}", "1", nx=True, ex=86400)` called.

6. **`submit_approval` raises `ApprovalWindowError` on duplicate.** Mock `_redis_sync.set(nx=True)` returning `False` (flag already set). Verify `ApprovalWindowError` raised.

7. **`submit_approval` validates nonce from Redis.** Set `_redis_sync.get("approval:nonce:{task_id}")` → `"nonce-abc"`. Call with `expected_nonce="nonce-abc"` → succeeds. Call with `expected_nonce="nonce-xyz"` → `ApprovalWindowError`.

8. **`update_task` writes nonce to Redis when approval_payload set.** Call `update_task(task_id, approval_payload={"checkpoint_nonce": "nonce-abc", ...})`. Verify `_redis_sync.set("approval:nonce:{task_id}", "nonce-abc", ex=86400)`.

9. **`update_task` clears nonce and flag when approval_payload cleared.** Call `update_task(task_id, approval_payload=None)`. Verify `_redis_sync.delete("approval:nonce:...", "approval:flag:...")`.

10. **Fallback: asyncio.Queue used when Redis is None.** Set `self._redis_sync = None`. Verify existing asyncio.Queue behavior works unchanged.

11. **Full cycle: submit before wait.** Push approval to Redis list first, then call `wait_for_approval()` — verify it picks up the pre-existing message immediately (no blocking).

12. **Full cycle: wait before submit.** Start `wait_for_approval()` in a background task, then `submit_approval()` — verify the waiter unblocks and receives the payload.

13. **Multi-checkpoint cycle.** Simulate a pipeline hitting HITL-1, getting approved, then hitting HITL-2. Verify that `update_task(approval_payload=None)` between checkpoints clears the flag so the second `submit_approval()` succeeds.

---

## 11. Validation Checklist

### Without Redis (`_redis_sync` is None):
1. All HITL flows work with asyncio.Queue as before
2. All existing tests pass

### With Redis:
3. Start content v1.3 pipeline (`auto_approve: false`):
   - HITL-1 (Topic): pipeline blocks → submit approval → pipeline resumes
   - HITL-2 (Brief): pipeline blocks → submit approval → pipeline resumes
   - HITL-3 (Content): pipeline blocks → submit approval → pipeline completes
4. Start KB pipeline (`auto_approve: false`):
   - 3 HITL checkpoints each work correctly
5. Submit same approval twice → second returns 409 ("already submitted")
6. Submit approval with wrong nonce → returns 409 ("nonce mismatch")
7. Let approval timeout (set a short timeout for testing) → pipeline auto-rejects
8. `redis-cli LLEN approval:{task_id}` shows 1 after submit, 0 after consumption
9. `redis-cli GET approval:flag:{task_id}` shows "1" after submit, gone after next checkpoint
10. `redis-cli GET approval:nonce:{task_id}` shows nonce after `pending_approval`, gone after consumption

### Multi-worker validation (Sessions 1-4 complete + Gunicorn with 2 workers):
11. Start pipeline on worker A → hits HITL checkpoint
12. Submit approval POST lands on worker B (check Gunicorn access log for PID)
13. Pipeline on worker A resumes and completes
14. Verify via `redis-cli MONITOR` that `BRPOP` and `LPUSH` happen on different connections (different workers)

---

## 12. Scope Boundaries — Do NOT Do These

- Do NOT change `TaskStoreProtocol` interface signatures
- Do NOT change the JSON `TaskStore` class (it's the fallback)
- Do NOT change any approval router endpoint
- Do NOT change any graph invocation helper
- Do NOT change any graph node function
- Do NOT change EventBus / RedisEventBus
- Do NOT change LangGraph checkpointer
- Do NOT change the frontend
- Do NOT implement the distributed semaphore (Session 5)
- Do NOT implement Redis caching (Session 6)
- Do NOT add the Lua script for atomic nonce+flag+push (optional optimization, not required for correctness at current scale)
