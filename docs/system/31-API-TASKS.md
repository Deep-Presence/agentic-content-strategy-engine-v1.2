# API Tasks — TaskStore, EventBus, Runner

> **Location:** `api/tasks/`
> **Owner:** API
> **Dependencies:** Redis (Streams, Sorted Sets, Lists), PostgreSQL, `core/` pipelines, `core/services/content_engine_topic_runs.py`
> **Dependents:** All pipeline routers, SSE endpoints
> **Last Updated:** 2026-04-15

## Overview

The tasks module manages the complete lifecycle of background pipeline executions: task creation with distributed locking, SSE event streaming via Redis Streams, HITL approval delivery, and 20+ pipeline runner functions. `DbTaskStore` is the production implementation with Redis distributed locks, Redis semaphore (max 3 concurrent globally; additionally a **per-company Content Engine pool** of 3 via `max_concurrent_content_engine_per_company`), and Redis approval queues.

The **TD-entry parallel execution** work centralized CE scalability in `runner.py`: the runner now hosts a **per-company Content Engine dispatcher** (`dispatch_queued_td_content_runs`) that drains queued topic runs from the DB, admits them to a named `content_engine` pool, and rehydrates paused HITL continuations so users can approve/edit briefs out of order without losing task identity.

## File Structure

| File | Purpose |
|------|---------|
| `runner.py` | 20+ async pipeline runner functions + scope resolution + artifact resolution + TD-entry dispatcher |
| `redis_event_bus.py` | `RedisEventBus` — Redis Streams SSE with in-memory mirror |
| `event_bus.py` | `EventBusProtocol` — structural type (production uses `RedisEventBus`) |
| `models.py` | `PipelineTask`, `ApprovalRecord`, `TaskStatus` |
| `exceptions.py` | `TaskNotFoundError`, `TaskConflictError`, `ApprovalDeliveryError`, `ApprovalWindowError` |

## `models.py`

- **`ApprovalRecord`**: audit trail — `task_id`, `stage`, `decision`, `revision_note?`, `decided_at`.
- **`PipelineTask`**: `task_id`, `pipeline` (Literal enum including `content_v13`, `td_content`, `td_gap_analysis`, `td_cannibalization`, `cms_sync`, `ga4_sync`, `fanout_generation`, etc.), `status: TaskStatus`, `company_slug`, `product_slug?`, `effective_slug?`, `current_step?`, `progress_pct?`, `created_at`, `updated_at`, `result?`, `error?`, `approval_payload?`, `approval_history: list[ApprovalRecord]`. `TaskStatus` is re-exported from `core.shared_tools.task_status`.

The `pipeline` literal was widened to include `td_content`, `td_gap_analysis`, and `td_cannibalization` as first-class values. Each topic-scoped CE run from TD-entry Phase 2 is a distinct `td_content` task.

## `event_bus.py`

`EventBusProtocol` is the structural type used by runners and routers. Only two implementations exist: `RedisEventBus` (production) and `InMemoryEventBus` (tests). The legacy filesystem fallback was removed in Phase 6.

```python
class EventBusProtocol(Protocol):
    def publish(self, task_id, event_type, data) -> None: ...
    def get_history(self, task_id) -> list[dict]: ...
    def is_terminal(self, task_id) -> bool: ...
    async def stream(self, task_id, last_event_id=None, task_status_fn=None) -> AsyncGenerator[str, None]: ...
```

## `RedisEventBus`

Production SSE implementation using Redis Streams + in-memory mirror.

**Atomic Lua script**: `INCR counter -> XADD stream -> EXPIRE both` (single Redis call, no out-of-order writes, globally monotonic event IDs even across workers).

| Method | Description |
|--------|-------------|
| `publish(task_id, event_type, data)` | Sync fire-and-forget. Updates mirror + schedules async Redis write |
| `stream(task_id, last_event_id)` | Async generator: replay (XRANGE) -> live tail (XREAD) -> terminal detection |
| `get_history(task_id)` | Thread-safe mirror read |
| `is_terminal(task_id)` | Check if last event is completed/failed/cancelled |

**Resilience**: terminal events retry 3x. DB fallback every ~30s checks task status if Redis stream lost. Heartbeat keepalive every 15s. `stream()` wrapped in try/except — Redis errors close SSE gracefully so the client can reconnect.

**In-memory mirror**: thread-safe (RLock), capped at 1000 tasks, oldest terminal evicted first.

## `runner.py` — Deep Dive

`runner.py` hosts 20+ async pipeline runners plus the TD-entry dispatcher. Each runner follows the same skeleton (bind structlog context -> acquire semaphore -> emit `pipeline_start` -> run core pipeline -> publish `completed`/`failed`/`cancelled` -> flush events -> release slug lock / dispatch -> `clear_context`), with the runners differing mainly in cleanup logic and durable state updates.

### Shared Scaffolding

- **`RunScope`** dataclass (`runner.py:45`) — `company_slug`, `product_slug`, `effective_slug` (`{company}__{product}` convention), `product_name`, `product_description`, `product_domain`.
- **`_resolve_scope`** / **`_resolve_scope_async`** (lines 56, 88) — derives the scope, optionally looking up product metadata via `AuthServiceProtocol`.
- **`_derive_slug`** (line 116) — slug factory used by every launch endpoint.
- **`resolve_artifacts(slug, artifacts_root, effective_slug, backend)`** (line 122) — auto-discovers approved company_context / persona / style_guide files via a double-candidate fallback chain (`effective_slug -> company_slug`). Always returns storage keys compatible with R2 or local.
- **`_resolve_db_context(company_slug, effective_slug)`** (line 173) — returns `(session_factory, run_id, company_id)` for `PipelineRunModel` persistence. Never raises; returns `(None, None, None)` on any failure.
- **`_create_pipeline_run`** / **`_mark_pipeline_run_complete`** / **`_mark_pipeline_run_failed`** — idempotent lifecycle helpers for `PipelineRunModel`.
- **`_cleanup_stale_pipeline_state(artifacts_root, effective_slug, redis_client, task_id)`** (line 290) — **task-scoped** Redis cleanup via `cleanup_stale_pipeline_state_redis(... task_id=task_id)` so parallel manual runs sharing a slug do not clobber each other's briefs, plus legacy full-file deletion as a safety net.
- **`_CONTENT_ENGINE_TASK_PIPELINES = {"content","content_v13","td_content"}`** — membership check used by the dispatcher's per-company active-task counter.
- **`_TERMINAL_TASK_STATUSES = {COMPLETED, FAILED, CANCELLED, FAILED_RESTART}`** — filter for the same counter.

### TD-Entry Dispatcher

The dispatcher is the heart of CE parallelism.

#### `_count_active_company_ce_tasks(task_store, company_slug)` (line 1880)

Counts tasks in `_CONTENT_ENGINE_TASK_PIPELINES` for `company_slug` that are neither terminal nor `PENDING_APPROVAL`. `PENDING_APPROVAL` is explicitly excluded so a paused HITL topic run does **not** consume a pool slot — other topics can keep flowing through while a human reviews briefs.

#### `_create_td_content_dispatch_task(task_store, company_slug, product_slug)` (line 1895)

Creates a fresh `td_content` task with `allow_parallel=True`, awaits `task_store.ensure_created()` for DB durability, and rolls back via `rollback_create()` on persist failure. Returns the `PipelineTask` or `None`.

#### `_reuse_td_content_dispatch_task(task_store, task_id)` (line 1920)

Fetches an existing paused task to rehydrate it. Used for **claimed resumes** (HITL-2/HITL-3 continuations) so the original task identity — `task_id`, SSE stream, `pipeline_task_id` in the topic run row — survives across pause -> resume.

#### `dispatch_queued_td_content_runs(company_slug, task_store, event_bus, session_factory)` (line 1932)

The drain loop. High-level flow:

1. Return `[]` when `session_factory is None`.
2. Compute `available_slots = max(api_settings.max_concurrent_content_engine_per_company - _count_active_company_ce_tasks(...), 0)`. Return `[]` when the pool is full.
3. Call `ContentEngineTopicRunService.claim_queued_topic_runs(company_slug, limit=available_slots)` — atomic DB claim that flips rows from `queued` to `claimed` and returns claim descriptors with `launch_context` and optional `continuation_payload`.
4. For each claim: if `continuation_payload` is set **and** `claim.pipeline_task_id` exists, `_reuse_td_content_dispatch_task(task_id=pipeline_task_id)` (paused resume); otherwise `_create_td_content_dispatch_task(...)` (fresh topic run). Missing `company_name`/`domain`/`ga_run_id` in `launch_context` -> release the claim and skip.
5. Bulk-commit the `{topic_run_id: task_id}` mapping via `service.mark_claimed_topic_runs_dispatched(...)`. On bulk-commit failure, release all claims and mark the newly-created tasks as `FAILED`.
6. For each successfully dispatched claim, kick off `asyncio.create_task(run_td_content_production_task(task_id, effective_slug, [topic_assignment_id], ..., td_resume_payload=..., td_resume_approval=...))`. Resume payloads become `task_store.update_task(status=RUNNING, approval_payload=None)` before launch so the HITL drawer clears.
7. Return `[{topic_run_id, topic_assignment_id, task_id}, ...]`.

The dispatcher is idempotent and safe to call from multiple sites: `POST /from-topics/start-production`, `POST /approve/briefs` (TD-entry path), `POST /approve/content` (TD-entry path), `run_td_content_production_task.finally`, and `_recover_td_entry_scheduler` at startup. Every completion naturally pulls the next queued topic run up to the pool cap.

### Pipeline Runners (key ones)

| Runner | Purpose | Special behavior |
|---|---|---|
| `run_gap_pipeline_task` | Gap Analysis (standalone) | Research artifact fallback; product-domain override; knowledge-doc slug fallback. |
| `run_site_audit_task` | Deterministic site audit | — |
| `run_content_v13_pipeline_task` (line 760) | v1.3 direct entry | Acquires the CE pool via `task_store.pipeline_semaphore(task_id, pool="content_engine", company_slug=...)`. Releases slug lock only when `is_parallel=False`. Writes pipeline state to Redis; cleans up with task-scoped cleanup on cancel/error. Invalidates `cache:content:{effective}:*` on exit. |
| `run_td_gap_analysis_task` (line 1706) | TD-entry Phase 1 | Runs `run_td_gap_analysis_only()`. On success, advances topic runs to `gap_analysis_complete`. On error/cancel, reverts `TopicAssignmentStatus` to `approved`, purges GA-phase Redis state, advances topic runs to `cancelled`/`failed`. Uses `allow_parallel=True` — no slug lock. |
| `run_td_content_production_task` (line 2071) | TD-entry Phase 2 per-topic CE | See dedicated section below. |
| `run_td_cannibalization_recompute_task` | Async cannibalization recompute | Fire-and-forget via `_spawn_td_cannibalization_recompute_task`; honored by `td_cannibalization_async_recompute_enabled` flag. |
| `run_cms_sync_task` (line 3101) | CMS sync | Chains into `_run_auto_prompt_generation` to auto-generate page prompts for freshly synced pages. |
| `run_ga4_sync_task` (line 3355) | GA4 traffic sync | Stamps AI referrals; invalidates `cache:content_perf:*`. |

### `run_td_content_production_task` — Per-Topic CE

This is the workhorse of TD-entry parallelism.

**Signature** (line 2071):
```python
async def run_td_content_production_task(
    task_id, effective_slug, topic_assignment_ids, company_name, domain, ga_run_id,
    task_store, event_bus, *,
    product_slug=None, product_name=None, product_description=None,
    auto_approve=False,
    td_resume_payload=None,          # Continuation descriptor from queue_topic_run_resume
    td_resume_approval=None,         # Approval data to feed the graph when resuming
)
```

**Flow**:

1. **Scope + DB context**: derive `company_slug`, `_resolve_db_context`, `_create_pipeline_run(pipeline_type="content")`, build `topic_run_service = ContentEngineTopicRunService(session_factory)` when DB is available.
2. **Bind structlog** (`bind_context`) with `pipeline_name="td_content_production"`.
3. **CE pool admission**: `async with task_store.pipeline_semaphore(task_id, pool="content_engine", company_slug=company_slug):` — this is the global named CE pool separate from the general pipeline semaphore.
4. **Durable state transition** (only on non-resume launches): `topic_run_service.advance_topic_runs(status="briefing", stage="briefing", ga_run_id=..., match_ga_run_id=..., pipeline_task_id=task_id)` — idempotent with `match_ga_run_id` so stale claims don't overwrite fresh ones.
5. **Publish `pipeline_start`** on the per-task event bus.
6. **Invoke orchestrator**: `output = await run_td_content_production_only(...)`. This call respects `td_resume_payload` to rehydrate the LangGraph HITL checkpoint from the continuation descriptor.
7. **Terminal success path**: build `result` dict, `task_store.update_task(status=COMPLETED, result=...)`, publish `completed`, call `_advance_td_topic_runs_for_output(...)`.
8. **`ApprovalPauseRequested` path**: the graph signals HITL needed. Extract `continuation_payload`, call `topic_run_service.mark_topic_run_waiting_human(...)`. Task stays `PENDING_APPROVAL`; CE pool slot released.
9. **`asyncio.CancelledError` path**: log + `_cleanup_stale_pipeline_state(...)`.
10. **Generic exception path**: **F18 fix** — `_update_ga_phase_status(..., "gap_analysis_complete")` reverts Redis GA-phase so Kanban card snaps back; revert DB; emit `_emit_company_event`; advance durable topic runs back; `task_store.update_task(FAILED)`.
11. **Finally**: `task_store.flush_terminal(task_id)`, invalidate `cache:content:{effective_slug}:*`, **re-dispatch** with `dispatch_queued_td_content_runs(...)` so freed CE pool slot is immediately consumed, `task_store.remove_task_handle(task_id)`, `clear_context()`.

### Terminal State Mapping

`_td_terminal_state_for_piece(piece)` (line 2307) maps a CE `ContentPiece` to the durable topic-run terminal tuple:
- `eval_summary.worker_error` → `("failed","failed", worker_error, ...)`
- `status in {approved, edited}` → `("content_produced","completed", None, ...)`
- `status == "rejected"` → `("rejected","rejected", None, ...)`
- Anything else → `("failed","failed","Unexpected terminal piece status", ...)`

`_advance_td_topic_runs_for_output(...)` groups pieces by terminal tuple so mixed batches flip each assignment independently. Zero-piece batches roll back to `gap_analysis_complete`.

## Task Lifecycle

### Standard (non-TD-entry)

```
POST /start → create_task_durable() → asyncio.create_task(runner)
    │                                      │
    ▼                                      ▼
202 { task_id }                    Pipeline running...
    │                                      │
    ▼                                      ▼
GET /tasks/{id}/events → SSE       publish("step_completed")
    │                                      │
    ▼                                      ▼
Receive events...                  PENDING_APPROVAL (HITL)
    │                                      │
    ▼                                      ▼
POST /{id}/approve                 wait_for_approval() → BRPOP
    │                                      │
    ▼                                      ▼
  Resume                             Continue pipeline
```

### TD-Entry Parallel

```
POST /from-topics/gap-analysis
    │
    ▼
create_task_durable(td_gap_analysis, allow_parallel=True)
_try_create_td_batch_records()        ← one batch row + N topic_run rows
asyncio.create_task(run_td_gap_analysis_task)
    │
    ▼ (GA completes → advance topic runs → gap_analysis_complete)
    │
POST /from-topics/start-production
    │
    ▼
queue_topic_runs_for_dispatch()  ← flips N rows to queued
dispatch_queued_td_content_runs()
    │
    ▼
   For up to max_concurrent_content_engine_per_company slots:
   claim_queued_topic_runs() → create or reuse task → asyncio.create_task(...)
    │
    ▼
Each task (per topic) acquires pool="content_engine" slot,
emits state_changed + topic events, may hit ApprovalPauseRequested
   │
   ├── HITL pause   → mark_topic_run_waiting_human → slot released
   │                  POST /approve/briefs → queue_topic_run_resume →
   │                  dispatch picks up resume → rehydrates original task
   │
   └── Completion   → _advance_td_topic_runs_for_output → finally: re-dispatch
```

## Approval Flow

### Standard

1. Pipeline calls `task_store.update_task(status=PENDING_APPROVAL, approval_payload=...)`.
2. Redis: SET nonce, publish SSE `pending_approval`.
3. Frontend: `POST /approve` → `task_store.submit_approval(task_id, decision, expected_nonce, delivery_mode="queue")`.
4. Redis: check nonce, SET flag (dedup), LPUSH payload to approval queue.
5. Pipeline: `BRPOP approval:{task_id}` unblocks → resumes with decision.
6. Cleanup: DELETE nonce, flag, queue keys.

### TD-Entry Durable Continuation

1. `run_td_content_production_task` raises `ApprovalPauseRequested` with `continuation` descriptor.
2. Runner catches and calls `topic_run_service.mark_topic_run_waiting_human(...)`, persisting continuation in `content_engine_topic_runs.continuation_payload_json`.
3. Task stays `PENDING_APPROVAL`; CE pool slot released.
4. Router detects `_uses_td_durable_continuation(task)` → calls `topic_run_service.queue_topic_run_resume(...)`.
5. Router re-runs `dispatch_queued_td_content_runs(...)`.
6. Dispatcher claims the resume row, `_reuse_td_content_dispatch_task(task_id=pipeline_task_id)` recovers the original paused task, launches a new coroutine with `td_resume_payload` and `td_resume_approval`.
7. The orchestrator rehydrates the LangGraph HITL checkpoint and continues.

## Startup Reconciliation — `_recover_td_entry_scheduler`

`api/app.py:95` runs during `lifespan` startup after the task store is initialized:

1. Grabs `task_store.list_tasks()` into a `{task_id: PipelineTask}` map.
2. Calls `ContentEngineTopicRunService.reconcile_startup_scheduler(task_by_id=...)` which:
   - Requeues `claimed` rows whose `pipeline_task_id` is no longer in the live task store (stranded from crashed worker).
   - Clears stale task IDs.
   - Restores `waiting_human` rows whose underlying task was terminated before approval.
   - Collects companies with claimable work.
3. For each company, runs `dispatch_queued_td_content_runs(...)`.
4. Logs aggregate counts: `queued_ready`, `requeued`, `waiting_human_restored`, `stale_task_ids_cleared`, `companies_dispatched`.

This makes TD-entry parallelism **durable across worker restarts** — a crashed worker mid-brief leaves the row as `claimed` with its original `pipeline_task_id`, startup detects the dead task_id and requeues it, and the dispatcher picks it up into a fresh task.

## Error Path Guarantees

- **Cleanup of stale pipeline state**: `_cleanup_stale_pipeline_state()` purges task-scoped Redis entries AND legacy file, on both cancel and exception paths.
- **GA-phase Redis reversion**: exception handler calls `_update_ga_phase_status(..., "gap_analysis_complete")` so Kanban card snaps back (F18 fix).
- **CompanyEventBus emission on rollback**: `_emit_company_event("state_changed", ...)` ensures frontend re-polls after error.
- **Durable rollback in DB**: `_update_assignment_statuses_db` + `topic_run_service.advance_topic_runs(rollback_target="gap_analysis_complete")` keeps DB consistent.
- **Post-terminal re-dispatch**: every finally block calls `dispatch_queued_td_content_runs` so freed slots don't sit idle.
- **Redis event bus flush**: `task_store.flush_terminal(task_id)` guarantees terminal event reaches subscribers before handle removal.

## Heartbeat + Task Lifecycle

- **SSE heartbeat**: per-task stream emits keepalives every 15s; company-wide stream every 30s.
- **In-memory mirror eviction**: 1000-task cap; oldest terminal evicted first.
- **Task handle registry**: routers call `register_task_handle(task_id, handle)` after `asyncio.create_task()`; runners call `remove_task_handle(task_id)` in finally.
- **Slug locks vs per-topic parallelism**: runners using `allow_parallel=True` skip `release_slug_lock()` in finally — releasing when no lock was taken would pop an unrelated run's entry.

## Cross-References

- **Service-layer contract**: See [09-CORE-SERVICES.md](09-CORE-SERVICES.md) for `ContentEngineTopicRunService` full reference.
- **DbTaskStore**: See [09-CORE-SERVICES.md](09-CORE-SERVICES.md) for `pipeline_semaphore(pool="content_engine", company_slug=...)`.
- **Plan**: See [TD_ENTRY_PARALLEL_EXECUTION_PLAN.md](../TD_ENTRY_PARALLEL_EXECUTION_PLAN.md) for architectural rationale.
- **Schemas**: See [29-API-SCHEMAS.md](29-API-SCHEMAS.md) for `TopicRunSummaryV13`, `TopicRunEventV13`, etc.
- **Routers**: See [28-API-ROUTERS.md](28-API-ROUTERS.md) for HTTP surface wrapping these runners.
