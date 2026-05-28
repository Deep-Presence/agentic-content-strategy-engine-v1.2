# Pipeline 3: Content Engine v1.3

> **Location:** `core/content_engine/`
> **Owner:** Core
> **Dependencies:** LiteLLM (via OpenRouter), LangGraph, pgvector, Redis
> **Dependents:** `api/routers/content_v13.py`, Content Studio (frontend), CMS publish, TD-Content Orchestrator
> **Last Updated:** 2026-04-24

## Overview

Pipeline 3 v1.3 is a 6-stage async content generation pipeline that produces AI-citation-optimized articles. It features a Strategic Planner for topic triage, Brief Builder for content architecture, a 4-worker chain (Outliner -> Drafter -> Linker -> Fact Checker), a 5-dimension evaluator loop with revision cycles, and 3 HITL checkpoints. All LLM calls route through OpenRouter via LiteLLM.

The pipeline supports **two execution models**: a legacy/manual single-run model (company-scoped locking) and a newer TD-entry parallel model (topic-scoped durable state with per-company CE pool). The parallel model is designed around the `ContentEngineTopicRunService` and durable scheduler state machine, enabling multiple topic assignments to flow through gap analysis and content production concurrently.

## Architecture

### Legacy/Manual Execution Model

```
AUTONOMOUS MODE:                          MANUAL MODE:
Entry Router                              Entry Router
    |                                         |
Stage 1: Strategic Planner                    | (skip)
    |    (Agent 1: topic triage)              |
    v                                         |
HITL-1: Topic Approval                        |
    |                                         |
Stage 2: Brief Builder                   Stage 2: Brief Builder
    |    (Agent 2: content architecture)      |
    v                                         v
HITL-2: Brief Approval (per-brief)       HITL-2: Brief Approval
    |                                         |
Stage 3: Workers (4-step chain)          Stage 3: Workers
    |    Outliner -> Drafter ->               |
    |    Linker -> Fact Checker               |
    v                                         v
Stage 4: Evaluator Loop                  Stage 4: Evaluator Loop
    |    5 dimensions, max 2 cycles           |
    v                                         v
HITL-3: Content Review (per-piece)       HITL-3: Content Review
    |                                         |
Publish                                  Publish
```

### TD-Entry Parallel Execution Model

```
User selects N topics in Planner
            |
            v
  +--------------------+
  | Batch Run Created   |  (content_engine_batch_runs)
  | N Topic Runs        |  (content_engine_topic_runs)
  +--------------------+
            |
            v (each topic independently)
  +------------------------------------+
  |  Scheduler State Machine           |
  |                                    |
  |  idle --> queued --> claimed        |
  |             ^          |           |
  |             |          v           |
  |             |       running        |
  |             |       /    \         |
  |             |      v      v        |
  |     resume_queued   waiting_human  |
  |             ^          |           |
  |             |          v           |
  |             +-- approval submitted |
  |                                    |
  |  Terminal: completed | failed      |
  +------------------------------------+
            |
            v (per topic, independently)
  +-------------------------------------------------+
  | gap_analysis_pending --> gap_analysis            |
  |   --> gap_analysis_complete --> content_queued   |
  |   --> briefing --> outlining --> drafting         |
  |   --> linking --> enriching --> evaluating        |
  |   --> review --> completed                       |
  +-------------------------------------------------+
            |
            v
  Per-card SSE via topic_run_changed events
  Company-wide SSE via state_changed events
```

**Key differences from legacy model:**

| Aspect | Legacy (Manual/Autonomous) | TD-Entry Parallel |
|--------|---------------------------|-------------------|
| Lock boundary | Company-slug exclusive | Per-topic-run |
| Concurrency | Global semaphore (max 3) | Per-company CE pool |
| State durability | Redis Hash + file fallback | Postgres `content_engine_topic_runs` |
| HITL suspend | In-process `wait_for_approval` | `ApprovalPauseRequested` + scheduler re-queue |
| Identity | `brief-001`, `brief-002` | `display_id` from Topic Discovery |
| Event model | Single task SSE stream | Per-card `topic_run_changed` + company SSE |
| Crash recovery | None (manual restart) | Startup reconciliation via `reconcile_startup_scheduler` |

## File Structure

| Directory | File | Lines | Purpose |
|-----------|------|-------|---------|
| root | `pipeline_v13.py` | 2,544 | Main 6-stage orchestrator |
| root | `strategic_planner.py` | 136 | Agent 1: topic triage |
| root | `brief_builder.py` | 271 | Agent 2: content architecture |
| root | `context_router.py` | 498 | 2-phase context extraction |
| root | `graph_v13.py` | 567 | 3 LangGraph HITL state machines |
| root | `llm_client.py` | 199 | Unified OpenRouter LLM interface |
| root | `state_helpers.py` | 353 | Shared state write/cleanup + SSE helpers |
| root | `state_redis.py` | 634 | Redis Hash pipeline state (sync + async) |
| root | `persistence.py` | 376 | DB persistence hooks (filesystem-first) |
| root | `artifact_writer.py` | — | StorageBackend artifact persistence |
| workers | `dispatcher.py` | 541 | Parallel worker orchestration (v1.0 + v1.3) |
| workers | `outliner.py` | 130 | Worker 1: structure design |
| workers | `drafter.py` | 272 | Worker 2: content generation |
| workers | `linker.py` | 197 | Worker 3: link + stat resolution |
| workers | `formatter.py` | 156 | Worker 4: style polish |
| evaluator | `loop.py` | 574 | Evaluator orchestration + revision |
| evaluator | `structural.py` | 482 | Structural quality checks (no LLM) |
| evaluator | `semantic.py` | 145 | Semantic alignment evaluation |
| evaluator | `style_judge.py` | 144 | Style guide compliance |
| evaluator | `factual_judge.py` | 147 | Factual accuracy verification |
| evaluator | `eeat_judge.py` | 162 | E-E-A-T dimension (v1.3 new) |
| prompts | 11 files | 1,853 | System + user prompts |

### Durable State Tables (TD-Entry Parallel)

| Table | Migration | Purpose |
|-------|-----------|---------|
| `content_engine_batch_runs` | 0038 | User-submitted batch of TD topics |
| `content_engine_topic_runs` | 0038 + 0039 | Per-topic execution row with scheduler state |
| `content_engine_topic_events` | 0038 | Append-only per-topic event audit log |

## Stages

### Stage 0: Entry Router

Routes based on `entry_mode`:

| Mode | Description | Stages Executed |
|------|-------------|-----------------|
| `AUTONOMOUS` | Gap Analysis input | 0, 1, 2, 3, 4, 5 |
| `MANUAL` | User prompt input | 0, 2, 3, 4, 5 |
| `TOPIC_DISCOVERY` | TD pipeline entry | 0, 2, 3, 4, 5 (with resume support) |

Loads artifacts via `StorageBackend` (R2-compatible) with filesystem fallback:
- `company_context_md` — from `company_context/{slug}.md`
- `style_guide_md` — from `style_guides/{slug}.md`
- `analysis_json` — gap analysis output for query data
- `persona_mds` — audience persona profiles

**File ref:** `pipeline_v13.py:898-908`

### Stage 1: Strategic Planner (Agent 1) — Autonomous Only

**Model:** Claude Sonnet 4.6. Receives lightweight ~11K token scorecard from `context_router.py` Phase 1. Selects top-K topics (default 6) based on gap magnitude, exemplar richness, and cluster diversity.

**HITL-1: Topic Approval** — approve / modify ranks / retry (max 2 retries) / reject. On reject: pipeline finalizes immediately with `exit_reason: topic_rejected`.

**File ref:** `pipeline_v13.py:920-1104`, `graph_v13.py:89-171`

### Stage 2: Brief Builder (Agent 2)

**Model:** Claude Sonnet 4.6. Receives full `WorkerQueryContext` per approved topic from `context_router.py` Phase 2. Produces `ContentBlueprint` with sections, 22 structural targets, gap reasoning, tone/voice guidance.

**HITL-2: Brief Approval (per-blueprint)** — approve / feedback (max 1 retry) / reject. Feedback triggers re-run of Agent 2 with user notes embedded in rationale.

**TD-Entry Resume:** When `entry_mode == TOPIC_DISCOVERY` and `td_resume_payload.resume_stage == "brief_approval"`, the pipeline skips Stage 1 and resumes HITL-2 with `initial_resume_approval` from the stored continuation payload. Uses `external_resume=True` to raise `ApprovalPauseRequested` instead of blocking in-process.

**Blueprint early persistence:** `persist_blueprints_early()` writes minimal `ContentPiece` records to DB before HITL-2 so `DbContentDataService.get_briefs()` returns them during the approval pause.

**File ref:** `pipeline_v13.py:1106-1270`, `graph_v13.py:174-264`, `persistence.py:55-159`

### Stage 3: Content Workers (4-step chain)

Per-brief, runs in series. Multiple briefs run in parallel via `asyncio.Semaphore`.

| Worker | Model | Input | Output |
|--------|-------|-------|--------|
| Outliner | Claude Sonnet | Blueprint | Section-by-section outline with word counts |
| Drafter | Claude Sonnet | Outline + brief + style guide | Markdown with placeholders |
| Linker | Perplexity sonar-pro | Draft + site pages | Resolved links + stats |
| Fact Checker | Perplexity sonar-pro | Linked draft + brief | Verified factual content |

**State tracking per worker step:** Each sub-step writes pipeline state (`outlining`, `drafting`, `linking`, `enriching`) via `_write_pipeline_state_async()` for real-time Kanban card updates.

**Structural counts computed inline** — no separate Formatter worker in v1.3 chain. `_count_structural_elements()` runs synchronously after fact checking.

**Artifact persistence:** When `StorageBackend` is available, stage artifacts are written via `persist_stage_artifact()` to R2 with `ContentArtifactStage` enum keys. Falls back to filesystem.

**File ref:** `dispatcher.py:253-541`

### Stage 4: Evaluator Loop

5 independent evaluation dimensions run in parallel via `asyncio.gather`:

| Dimension | Model | Pass Threshold | What It Checks |
|-----------|-------|---------------|----------------|
| Structural | None (sync) | Configurable | Word count, headers, lists, stats, FAQ, tables |
| Semantic | Claude Sonnet | 0.5 | Query intent alignment |
| Style | Claude Haiku | 0.7 | Style guide compliance |
| Factual | Claude Sonnet | 0.7 | Claim accuracy, flagged claims |
| E-E-A-T | Claude Sonnet | 0.6 | Experience, Expertise, Authority, Trust |

**Feedback routing (v1.3 dual feedback):**

| Route | Condition | Action |
|-------|-----------|--------|
| `PASS` | All dimensions passed | Proceed to HITL-3 |
| `SECTION_LEVEL` | Any dimension failed (semantic >= 0.5) | Targeted revision: drafter + fact_checker |
| `MAJOR_CHANGE` | Semantic < 0.5 | Escalate to HITL-3 for re-brief |

**Targeted revision plan:**
- Structural/Style/Semantic/E-E-A-T fail -> drafter + fact_checker
- Factual fail -> fact_checker only
- If drafter revises, always re-verify facts

**Early-stop:** Score improvement < 0.02 between revision cycles triggers early stop.

**Format-aware cycles:** `settings.content_engine_revision_cycles_by_format` JSON map overrides default max cycles (2) per content format.

**File ref:** `evaluator/loop.py:1-574`

### Stage 5: Final Review (HITL-3)

Human reviews content with evaluation summary. Options: approve, edit (with notes), reject.

**TD-Entry Mode:** Uses `external_resume=True` so the pipeline raises `ApprovalPauseRequested` with a continuation payload containing the blueprint, final content, revision history, and CPS data. The scheduler queues this as `waiting_human` and the dispatcher re-launches the pipeline with `td_resume_payload.resume_stage == "content_review"` when the user responds.

**Re-brief support:** When `rethink=True` in the approval response, `_rebrief_and_rerun()` re-runs Agent 2 with editor notes, then executes the full worker chain and evaluator loop on the revised blueprint. Max 1 re-brief per piece.

**File ref:** `pipeline_v13.py:656-761` (finalization), `graph_v13.py:267-409`

## 3 HITL Checkpoints

All use LangGraph `interrupt()` + `Command(resume=...)` pattern with Redis checkpointing via `RedisSaver`.

| Checkpoint | After | Decisions | On Reject | TD-Entry Behavior |
|-----------|-------|-----------|-----------|-------------------|
| HITL-1 | Strategic Planner | approve / modify ranks / retry / reject | Abort pipeline | N/A (TD skips Stage 1) |
| HITL-2 | Brief Builder (per-brief) | approve / feedback / reject | Skip brief | `ApprovalPauseRequested` -> scheduler `waiting_human` -> `resume_queued` |
| HITL-3 | Evaluator (per-piece) | approve / edit / reject | Mark as rejected | `ApprovalPauseRequested` -> scheduler `waiting_human` -> `resume_queued` |

### ApprovalPauseRequested Exception

When `external_resume=True` is passed to `run_hitl_checkpoint()`, the function raises `ApprovalPauseRequested` instead of calling `wait_for_approval()`. This exception carries a continuation payload that the runner persists into the durable `content_engine_topic_runs.continuation_payload_json` column. The scheduler re-queues the topic run when the approval arrives.

**File ref:** `graph_v13.py:34-39`, `graph_v13.py:523-524`

### Generic Invocation Loop (`run_hitl_checkpoint`)

Single function handles all three checkpoints:

1. Initial invoke or resume with `initial_resume_approval`
2. Loop while `__interrupt__` present in result
3. Generate nonce, publish SSE `pending_approval` event
4. Update task store with `PENDING_APPROVAL` status
5. If `external_resume`: raise `ApprovalPauseRequested`
6. Else: `wait_for_approval()` (BRPOP with 1s polling)
7. Normalize generic `decision` key to stage-specific keys
8. Resume graph with `Command(resume=approval)`

**File ref:** `graph_v13.py:431-567`

## Parallelism & Scalability Design

### Durable State Architecture

The TD-entry parallel execution model uses three Postgres tables (migration 0038 + 0039) to track topic-level execution state durably:

```
+----------------------------+     +----------------------------+
| content_engine_batch_runs  |     | content_engine_topic_events|
|----------------------------|     |----------------------------|
| id (PK)                   |     | id (PK)                   |
| company_id (FK)           |     | topic_run_id (FK)         |
| effective_slug            |     | topic_assignment_id (FK)  |
| source                    |     | display_id                |
| submitted_count           |     | event_type                |
| completed/failed/cancelled|     | stage, status, seq        |
+----------------------------+     | payload_json              |
            |                      +----------------------------+
            | 1:N
            v
+----------------------------+
| content_engine_topic_runs  |
|----------------------------|
| id (PK)                   |
| batch_run_id (FK)         |
| topic_assignment_id (FK)  |
| display_id                |
| topic_text                |
| brief_id                  |
| status, current_stage     |
| status_seq (monotonic)    |
| scheduler_state           |
| claim_token               |
| queued_at, claimed_at     |
| waiting_for_human_at      |
| continuation_payload_json |
| pipeline_task_id          |
| content_piece_id (FK)     |
| ga_run_id                 |
| metadata_json             |
+----------------------------+
```

**Identity rule:** Every topic run carries both `topic_assignment_id` (internal FK) and `display_id` (human-readable label from Topic Discovery, e.g. "WE-042"). Both are propagated through every event payload and SSE broadcast.

### Scheduler State Machine

Each `content_engine_topic_runs` row has a `scheduler_state` column that tracks its position in the dispatch lifecycle:

```
                     create_td_batch()
                           |
                           v
                        [idle]
                           |
          queue_topic_runs_for_dispatch()
                           |
                           v
                       [queued]
                           |
              claim_queued_topic_runs()
                (SELECT FOR UPDATE + claim_token)
                           |
                           v
                      [claimed]
                           |
           mark_claimed_topic_runs_dispatched()
                           |
                           v
                      [running]
                      /        \
                     /          \
                    v            v
            [completed]    [waiting_human]
                                |
                   queue_topic_run_resume()
                     (approval_data merged
                      into continuation_payload)
                                |
                                v
                        [resume_queued]
                                |
                  claim_queued_topic_runs()
                    (resume_queued included
                     in claim query)
                                |
                                v
                           [claimed]
                                |
                           ... (re-enters running)
```

**Scheduler states explained:**

| State | Meaning | Transition |
|-------|---------|------------|
| `idle` | Created but not yet dispatched | -> `queued` via `queue_topic_runs_for_dispatch()` |
| `queued` | Ready for claim by dispatcher | -> `claimed` via `claim_queued_topic_runs()` |
| `claimed` | Locked by a dispatcher instance | -> `running` via `mark_claimed_topic_runs_dispatched()` |
| `running` | Pipeline actively executing | -> `completed` or `waiting_human` |
| `waiting_human` | HITL checkpoint paused | -> `resume_queued` via `queue_topic_run_resume()` |
| `resume_queued` | Approval received, ready to re-dispatch | -> `claimed` via `claim_queued_topic_runs()` |

### Per-Company CE Pool

The `pipeline_semaphore()` method on `TaskStoreProtocol` accepts a `pool` parameter and optional `company_slug`. For TD-entry flows, the runner uses `pool="ce_content"` with the company slug, providing per-company concurrency budgets instead of global pipeline exclusivity.

```python
# In TaskStoreProtocol
def pipeline_semaphore(
    self,
    task_id: str,
    *,
    pool: str = "default",
    company_slug: Optional[str] = None,
): ...
```

**File ref:** `core/services/task_store.py:27-33`

### Slot Suspend/Resume Across HITL

When a TD-entry topic run reaches a HITL checkpoint:

1. Pipeline raises `ApprovalPauseRequested` with continuation payload
2. Runner catches the exception and calls `mark_topic_run_waiting_human()`
3. The topic run's `scheduler_state` becomes `waiting_human`
4. The semaphore slot is **released** — other topics can use it
5. When approval arrives, `queue_topic_run_resume()` sets `scheduler_state = resume_queued`
6. Dispatcher claims and re-dispatches with `td_resume_payload` + `td_resume_approval`
7. Pipeline resumes at the stored `resume_stage` (either `brief_approval` or `content_review`)

This slot-release pattern prevents HITL waits from blocking the per-company CE pool.

### Startup Reconciliation

On server restart, `reconcile_startup_scheduler()` scans all non-terminal `content_engine_topic_runs` and recovers stranded entries:

```
For each recovery candidate:
  1. Skip if scheduler_state == "waiting_human" (user action pending)
  2. Skip if associated task is still RUNNING or PENDING_APPROVAL
  3. If task was FAILED_RESTART with a HITL payload + continuation:
     -> Restore to "waiting_human" (emit topic_run_recovered event)
  4. If has continuation but task is dead/missing:
     -> Requeue as "resume_queued" (emit topic_run_recovered event)
  5. If no continuation and task is dead/missing:
     -> Requeue as "queued" from scratch (emit topic_run_recovered event)
  6. Clear stale pipeline_task_ids for missing tasks
```

**Returns:** `StartupSchedulerRecoverySnapshot` with counts of dispatched companies, re-queued runs, restored waits, and cleared stale task IDs.

**File ref:** `core/services/content_engine_topic_runs.py:632-778`

### Claimed-Resume Pattern

When a dispatcher claims a `resume_queued` topic run, the `QueuedTopicRunClaimSnapshot` carries the full `continuation_payload` which includes:

- `resume_stage`: `"brief_approval"` or `"content_review"`
- `topic_assignment_id`, `brief_id`, `thread_id`
- `blueprint` (serialized `ContentBlueprint`)
- `approval_data` (the user's HITL decision)
- For content review: `final_content`, `history`, `feedback_route`, `cps_data`, `piece_id`

The dispatcher reconstructs `td_resume_payload` and `td_resume_approval` from this snapshot and launches the pipeline at the stored resume point.

### Per-Card SSE Fanout

State transitions in the TD-entry flow emit two types of SSE events:

1. **`topic_run_changed`** — per-topic granularity, carries full snapshot:
   ```json
   {
     "topic_run_id": "...",
     "batch_run_id": "...",
     "topic_assignment_id": "...",
     "display_id": "WE-042",
     "brief_id": "WE-042",
     "status": "drafting",
     "stage": "drafting",
     "seq": 7,
     "pipeline_task_id": "...",
     "effective_slug": "..."
   }
   ```

2. **`state_changed`** — coarse invalidation hint (legacy bridge):
   ```json
   {
     "changed": ["WE-042"],
     "hint": "drafting"
   }
   ```

Events are emitted from `_write_pipeline_state_async()` via `_sync_td_topic_runs_for_briefs()` which advances durable topic-run state and then broadcasts via `_emit_company()`.

**File ref:** `state_helpers.py:41-311`

### Async DB Pool Sizing

The default async connection pool was increased from 15 to 20 to accommodate parallel TD-entry topic runs that each hold a session during their pipeline execution. The increase is configured in `core/config/settings.py` via `db_pool_size`.

## State Management

### Redis Hash (Primary — Hot State)

**Key:** `pipeline_state:{effective_slug}`

**Structure:**
```
  brief-001          -> "generating"           (CE brief status)
  __tid:brief-001    -> "task-uuid"            (task ID for HITL discovery)
  ta-{uuid}          -> "gap_analysis"         (GA-phase card status)
  __tid:ta-{uuid}    -> "ga-task-uuid"         (GA task ID for SSE)
  __meta:ta-{uuid}   -> JSON metadata          (title, cluster, display_id, etc.)
```

**TTL:** 24 hours, refreshed on every write.

**Write path:** `_write_pipeline_state_async()` in `state_helpers.py` is the single entry point for all state writes. It:
1. Self-acquires async Redis when caller doesn't provide a client
2. Writes to Redis Hash via pipeline (atomic HSET + EXPIRE)
3. Refreshes associated slug lock TTL (prevents expiry during HITL waits)
4. Calls `_sync_td_topic_runs_for_briefs()` for durable topic-run state propagation
5. Broadcasts company-wide SSE events
6. Falls back to file write **only** when Redis is unavailable

**File ref:** `state_helpers.py:229-311`, `state_redis.py:56-170`

### GA-Phase Cards

Topic assignments entering the Content Engine from Topic Discovery first appear as GA-phase cards in the Redis Hash. These use `ta-{topic_assignment_id}` keys and coexist with `brief-NNN` keys.

**Valid GA phases:** `gap_analysis_pending`, `gap_analysis`, `gap_analysis_complete`, `content_queued`, `briefing`

**Metadata:** Stored under `__meta:ta-{uuid}` as JSON with title, cluster, priority_score, buyer_stage, display_id, intent_type, persona, content_format, etc.

**Graduation:** When a topic assignment enters CE production, `cleanup_ga_phase_state()` removes the `ta-*` keys and the brief appears under its `brief-NNN` key.

**File ref:** `state_redis.py:321-634`

### File-Based State (Fallback Only)

`pipeline_state.json` in the artifact directory is written **only** when Redis is unavailable. It is never written unconditionally. Readers (`DbContentDataService`) check Redis exclusively when available. File-based state caused 4-minute kanban sync lag in prior versions.

**File ref:** `state_helpers.py:94-159`

### Durable State (Postgres — TD-Entry Only)

See "Parallelism & Scalability Design" above. The `content_engine_topic_runs` table is the authoritative execution state for TD-entry flows. Redis Hash remains the hot-state layer for real-time Kanban updates.

## Context Router (Two-Phase)

**Phase 1 (Scorecard):** Lightweight ~11K token summary for topic triage. 200 queries with gap scores.

**Phase 2 (Full Context):** Complete `WorkerQueryContext` per approved topic (4-6 out of 200). Natural HITL boundary between phases.

**Manual mode context:** 3-tier gap data lookup:
1. Direct `gap_query_id` lookup (from Analytics "Add to Content Cycle")
2. `query_text` match fallback
3. Cluster-level fallback (case-insensitive) with deduplicated exemplars

**File ref:** `context_router.py:1-498`, `pipeline_v13.py:1273-1399`

## LLM Client

Unified `llm_call()` function routing all calls through OpenRouter with jittered exponential backoff retry, cost tracking, and model prefix validation.

## Centralized Finalization

**`_finalize_pipeline()`** — Single exit path for all pipeline terminations:

1. Save `run_metadata_v13.json` (namespaced by brief_id for manual parallel runs)
2. `persist_content_pieces()` — upsert by `(effective_slug, brief_id)` preserving existing IDs and FK relationships
3. `persist_content_run_summary()` — update `PipelineRunModel` with completion stats
4. Clean up pipeline state (Redis HDEL for this run's brief IDs only)
5. Invalidate content cache (`cache:content:{slug}:*`)
6. Update trace output + flush LangSmith
7. Mark task as completed + emit SSE events

**Concurrency safety:** Pipeline state cleanup removes only this run's brief IDs. Other parallel manual runs sharing the same slug retain their entries. Task-scoped cleanup via `__tid:` prefix matching.

**File ref:** `pipeline_v13.py:656-761`

## Persistence Layer

### Upsert Strategy

Content pieces use **upsert by `(effective_slug, brief_id)`** instead of delete-recreate. This preserves:
- Existing `content_pieces.id` (used by FK references: `query_gaps.targeted_by_content_id`, `content_artifacts.piece_id`, `content_inventory_prompts.content_piece_id`)
- `evaluation_results.gap_context` from earlier pipeline stages
- `topic_assignment_id` linkage

**File ref:** `persistence.py:162-241`

### Blueprint Early Persistence

`persist_blueprints_early()` creates minimal `ContentPiece` records in `planned` status before HITL-2 so the Content Studio Kanban board shows them during the approval pause. Uses upsert — safe to call even if records already exist.

**File ref:** `persistence.py:55-159`

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `content_engine_v13_planner_model` | `anthropic/claude-sonnet-4-6` | Strategic Planner LLM |
| `content_engine_v13_worker_model` | `anthropic/claude-sonnet-4-6` | Outliner + Drafter |
| `content_engine_v13_formatter_model` | `anthropic/claude-haiku-4-5` | (unused in v1.3 chain) |
| `content_engine_v13_fact_enricher_model` | `perplexity/sonar-pro` | Linker + Fact Checker |
| `content_engine_v13_linker_model` | `perplexity/sonar-pro` | Internal link resolver |
| `content_engine_v13_eeat_judge_model` | `anthropic/claude-sonnet-4-6` | E-E-A-T evaluator |
| `content_engine_v13_max_topics` | 6 | Max topics from planner |
| `content_engine_v13_max_concurrent_workers` | 3 | Worker semaphore limit |
| `content_engine_revision_cycles_by_format` | JSON map | Per-format max revision cycles |
| `db_pool_size` | 20 | Async DB pool size (increased from 15) |

## Error Handling

### Pipeline-Level

All stages wrapped in try/except at `run_content_generation_v13()`:
- `ApprovalPauseRequested` — re-raised to runner for TD scheduler handling
- All other exceptions — trace finalized, task marked FAILED, SSE error emitted

### Worker-Level

`dispatch_workers_v13()` uses `asyncio.gather(return_exceptions=True)`. Individual worker failures do not cancel other workers. Returns `(successes, failures)` tuple.

### Evaluator-Level

Individual evaluation dimension failures produce `DimensionResult(passed=False, score=0.0)` — the loop continues and treats the dimension as failed.

### State Cleanup on Error

Error paths call `_cleanup_pipeline_state_async()` for this run's brief IDs. Task-scoped cleanup uses `__tid:` prefix matching to avoid clobbering other runs' state.

## Tech Debt

1. **`_company_slug` NameError (F17):** `_company_slug` is defined in `run_content_generation_v13()` (line 810) and in `_run_pipeline_stages()` (line 892), but if exception handling paths reference it before assignment, a NameError can occur. Each function re-derives it from `slug.split("__")[0]`.

2. **Redis GA-phase not reverted on failure (F18):** Zero-pieces path in the orchestrator and exception handler in the runner revert DB but not Redis GA-phase state. Cards can get stuck in `briefing` status.

3. **File-based pipeline state still in code path:** Although Redis is primary and file writes only trigger when Redis is unavailable, the file-write code path remains in `state_helpers.py` for dev/no-Redis fallback. TD-entry should be fully Redis-only (per `TD_ENTRY_PARALLEL_EXECUTION_PLAN.md` Phase 5).

4. **CompanyEventBus is single-process:** `_emit_company()` uses an in-memory pub/sub singleton. Multi-worker deployment requires Redis Pub/Sub replacement.

5. **No multi-worker SSE `id:` field:** SSE events lack `id:` field for client-side reconnection replay.

6. **`brief-{idx:03d}` ID scheme in autonomous mode:** Resets per run, can clobber previous briefs via upsert. TD-entry uses `display_id` which is unique and persistent.

7. **`agentProgress` wiped by version-aware merge:** Server card replaces existing card without preserving local-only `agentProgress` field in the frontend merge logic.
