# Core Orchestration

> **Location:** `core/orchestration/`
> **Owner:** Core
> **Dependencies:** Pipelines 2, 3, 4, Redis, DB, CompanyEventBus
> **Dependents:** `api/routers/content_v13.py`, `api/routers/topic_discovery.py`, `api/tasks/runner.py`
> **Last Updated:** 2026-04-24

## Overview

The orchestration module provides the TD -> Content Engine pipeline, chaining approved Topic Discovery assignments through topic-scoped Gap Analysis into Content Generation. It supports three entry patterns: combined (atomic), GA-only (Phase 1), and CE-only (Phase 2), enabling the user to review GA results before triggering content production.

The orchestrator no longer holds a slug-level lock during execution. Concurrency is managed by the pipeline semaphore (`RedisSemaphore`) acquired in the runner layer. The orchestrator focuses on preflight validation, status transitions, Redis GA-phase card management, CompanyEventBus notifications, and error rollback.

## Architecture

```
TopicAssignment IDs (from HITL-2 approval)
    |
    v Preflight (validate context, personas, matrix via DB)
    |
Phase 1: Topic-Scoped Gap Analysis
    |   -> Reuses S1 embeddings from base GA run (existing_ga_slug)
    |   -> topic-specific queries via S2
    |   -> S3-S8 with scoped queries
    |   -> Write GA-phase cards to Redis (ta-{id} keys)
    |   -> CompanyEventBus: state_changed hint=gap_analysis
    |   -> On complete: status -> gap_analysis_complete
    |   -> CompanyEventBus: state_changed hint=gap_analysis_complete
    |   -> Load topic-level gap_context summaries into Redis card data
    |
    v User reviews GA results (Content Studio shows analysis-ready cards)
    |
Phase 2: Content Engine (TOPIC_DISCOVERY mode)
    |   -> Step 2a: Snap-back guard (GA cards -> "briefing" in Redis)
    |   -> CompanyEventBus: state_changed hint=briefing
    |   -> Uses pre-computed analysis.json from Phase 1
    |   -> Per-query content pieces tagged by topic_assignment_id
    |   -> On success: cleanup ta-* Redis keys (graduate to CE briefs)
    |   -> DB status -> content_produced
    |
    v Cleanup GA-phase cards, update DB statuses
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `td_content_orchestrator.py` | TD -> GA -> CE orchestrator | `run_td_to_content_pipeline`, `run_td_gap_analysis_only`, `run_td_content_production_only`, `GapAnalysisOnlyResult`, `TDContentPipelineError` |

## Three Entry Patterns

| Pattern | Function | Use Case | Lock Held? |
|---------|----------|----------|------------|
| Combined | `run_td_to_content_pipeline()` | GA + CE as one atomic task | By runner (not orchestrator) |
| GA-only | `run_td_gap_analysis_only()` | Phase 1 only, user reviews before Phase 2 | By runner |
| CE-only | `run_td_content_production_only()` | Phase 2 from pre-computed GA results | By runner |

## Detailed Reference

### Preflight Validation (`_validate_preflight_db`)

All three entry patterns run DB-backed preflight checks:

1. **Company context:** Verifies `artifacts/company_context/{effective_slug}.md` exists and is non-empty. Raises `TDContentPipelineError` if missing (user must run KB pipeline first).
2. **Personas:** Checks `PersonaStorage.list_persona_paths()` returns at least one artifact. Raises if empty (user must run AP pipeline first).
3. **TD Matrix:** Reads `TopicAssignmentMatrix` from DB via `db_read_manifest()` + `db_read_latest_matrix()`. Validates that all requested `topic_assignment_ids` exist in the matrix. Raises on missing IDs.

Returns the full `TopicAssignmentMatrix` on success.

### `run_td_gap_analysis_only()` -- Phase 1

**Steps:**

| Step | Description | Redis | DB | SSE |
|------|-------------|-------|----|-----|
| 1 | Preflight validation | - | Read matrix | - |
| 2 | Filter valid assignments from matrix | - | - | - |
| 2b | Update status -> `in_gap_analysis` | - | Write | - |
| 2c | Write GA-phase state to Redis (`gap_analysis_pending`) | `_write_ga_phase_redis()` | - | - |
| 3a | Update GA-phase state -> `gap_analysis` (running) | `_write_ga_phase_redis()` | - | `state_changed` hint=gap_analysis |
| 3b | Run `run_topic_scoped_gap_analysis()` | - | - | - |
| 4a | Update status -> `gap_analysis_complete` | - | Write | - |
| 4b | Load topic-level gap_context summaries | Read analysis.json | - | - |
| 4c | Write GA-phase state -> `gap_analysis_complete` (with gap_context) | `_write_ga_phase_redis()` | - | `state_changed` hint=gap_analysis_complete |

**Returns:** `GapAnalysisOnlyResult` with `ga_run_id`, `valid_assignment_ids`, `analysis_path`, and `topic_query_map`.

**Gap Context Enrichment (Step 4b):** `_load_topic_gap_context_summaries()` reads the topic-scoped `analysis.json`, calls `extract_topic_contexts()` and `extract_gap_context()` to build per-assignment gap summaries, then writes them into the Redis GA-phase card data. This powers the Content Studio sidebar showing gap scores, company best URLs, and exemplars for each card.

**GA-Phase Card Data Fields:**

The Redis card data for each assignment (`_write_ga_phase_redis()`) includes:

| Field | Source | Description |
|-------|--------|-------------|
| `title` | `assignment.topic_text` | Topic title (truncated to 200 chars) |
| `cluster` | `assignment.subdomain_name` | Target cluster |
| `priority_score` | `assignment.priority_score` | CPS score |
| `buyer_stage` | `assignment.buyer_stage` | TOFU/MOFU/BOFU |
| `display_id` | `assignment.display_id` | Universal display ID |
| `intent_type` | `assignment.intent_type` | Informational/commercial/etc |
| `persona_name` | `assignment.persona_name` | Target persona |
| `persona_affinity` | `assignment.persona_affinity` | Affinity scores |
| `priority_factors` | `assignment.priority_factors` | Scoring breakdown |
| `content_format` | `metadata.content_format` | Blog/guide/etc |
| `estimated_word_count` | `metadata.estimated_word_count` | Target length |
| `description` | `metadata.description` | Topic description |
| `gap_context` | From `_load_topic_gap_context_summaries()` | Gap score, exemplars, company best URL |

### `run_td_content_production_only()` -- Phase 2

**Steps:**

| Step | Description | Redis | DB | SSE |
|------|-------------|-------|----|-----|
| 1 | Validate `analysis.json` exists (StorageBackend) | - | - | - |
| 2a | **Snap-back guard:** Transition GA cards -> `briefing` | `_update_ga_phase_status()` | Write status -> `in_content_production` | `state_changed` hint=briefing |
| 2b | Build `ContentGenerationInputV13` and run CE pipeline | - | - | - |
| 3 | On success with pieces > 0: cleanup GA-phase ta-* keys | `_cleanup_ga_phase_redis()` | Write status -> `content_produced` | - |
| alt | On zero pieces: revert GA cards to `gap_analysis_complete` | `_update_ga_phase_status()` | Write status -> `gap_analysis_complete` | - |

**Step 2a Snap-Back Guard:**

When the user clicks "Start Production" in Content Studio, the frontend re-polls card data. Without the snap-back guard, the cards would revert to `gap_analysis_complete` (their last Redis state) for a brief moment before CE writes new brief keys. Step 2a explicitly sets the GA-phase card status to `briefing` *before* launching CE, preventing visual snap-back in the kanban board.

**Error Recovery (CE Failure):**

If the Content Engine raises an exception (not `ApprovalPauseRequested`):

1. Redis GA-phase cards are reverted to `gap_analysis_complete` via `_update_ga_phase_status()`.
2. DB assignment statuses are reverted to `gap_analysis_complete`.
3. CompanyEventBus emits `state_changed` with hint `gap_analysis_complete`.
4. The exception is re-raised.

This ensures the user sees the cards return to the "Analysis Ready" state and can retry.

**`ApprovalPauseRequested` exception** is re-raised without rollback -- it indicates a HITL checkpoint, not a failure.

**Zero-Pieces Revert:**

If CE completes but produces zero pieces (all topics filtered or rejected), the GA cards are reverted to `gap_analysis_complete` and DB status is set accordingly. The user can retry or choose different topics.

### `run_td_to_content_pipeline()` -- Combined

Runs GA + CE as a single atomic operation. Simplified flow without intermediate Redis card management. On zero pieces, reverts to `gap_analysis_complete`. On success, updates to `content_produced`.

Acquires an async Redis client via `get_redis_or_none()` for CE pipeline state writes (prevents 4-min kanban sync lag caused by stale `pipeline_state.json` fallback).

### Redis GA-Phase State Helpers

All helpers are best-effort -- Redis errors are logged but never fail the pipeline.

| Helper | Purpose |
|--------|---------|
| `_write_ga_phase_redis()` | Full write: creates/updates `ta-{id}` entries with all card data fields. Calls `write_ga_phase_state()` from `state_redis.py`. |
| `_update_ga_phase_status()` | Lightweight update: changes only the status field (and optionally task_id) for existing entries. Does not require full `TopicAssignment` objects. |
| `_cleanup_ga_phase_redis()` | Removes `ta-{id}`, `__tid:ta-{id}`, and `__meta:ta-{id}` fields from the pipeline state hash. Called on graduation to CE briefs. |
| `_emit_company_event()` | Broadcasts a company-wide SSE event. Derives company slug from effective slug (strips `__product` suffix). Best-effort. |

## Status Machine

```
not_started -> approved -> in_gap_analysis -> gap_analysis_complete -> in_content_production -> content_produced
```

Status transitions are persisted to PostgreSQL via `persist_td_assignment_status_batch()` in `core/topic_discovery/persistence.py`.

## ContentEngineTopicRunService Handoff

| Stage | Responsibility | Actor |
|-------|---------------|-------|
| Topic approval | HITL-2 approves assignments | User (frontend) |
| Preflight | Validate context, personas, matrix | Orchestrator |
| GA execution | Run topic-scoped gap analysis | Orchestrator -> `run_topic_scoped_gap_analysis()` |
| GA card management | Write/update/cleanup ta-* Redis keys | Orchestrator |
| CE execution | Run content engine in TD mode | Orchestrator -> `run_content_generation_v13()` |
| Status tracking | Update assignment statuses in DB | Orchestrator -> `_update_assignment_statuses_db()` |
| SSE notifications | Emit state_changed events | Orchestrator -> `_emit_company_event()` |
| Concurrency control | Pipeline semaphore acquisition | Runner (not orchestrator) |

## Integration Points

| Component | Interaction |
|-----------|-------------|
| `api/tasks/runner.py` | Calls orchestrator functions within pipeline semaphore context |
| `core/gap_analysis/pipeline.py` | `run_topic_scoped_gap_analysis()` for Phase 1 |
| `core/content_engine/pipeline_v13.py` | `run_content_generation_v13()` for Phase 2 |
| `core/content_engine/state_redis.py` | `write_ga_phase_state()`, `cleanup_ga_phase_state()` for Redis card management |
| `core/events/company_event_bus.py` | `state_changed` events for real-time frontend updates |
| `core/topic_discovery/persistence.py` | `persist_td_assignment_status_batch()` for DB status writes |
| `core/topic_discovery/db_ops.py` | `db_read_manifest()`, `db_read_latest_matrix()` for preflight |
| `core/services/gap_context_helper.py` | `extract_gap_context()` for gap summary enrichment |
| `core/content_engine/context_router.py` | `extract_topic_contexts()` for per-topic GA context extraction |

## Configuration

The orchestrator has no dedicated settings. It uses:

- `_PROJECT_ROOT` (derived from file location) for artifact paths.
- `session_factory` (required) for all DB operations.
- Redis clients obtained lazily via `get_sync_redis_or_none()` and `get_redis_or_none()`.

## Error Handling

- **Preflight failures:** `TDContentPipelineError` raised immediately. No status changes made.
- **GA produces no queries:** `TDContentPipelineError` with descriptive message. Assignments left in `in_gap_analysis` status.
- **CE failure:** Redis + DB rollback to `gap_analysis_complete`, SSE notification, exception re-raised.
- **Zero pieces from CE:** Silent rollback to `gap_analysis_complete` (no exception).
- **Redis errors in helpers:** Logged at WARNING, never fail the pipeline. Cards may be stale but pipeline continues.
- **`session_factory=None`:** `TDContentPipelineError` raised before any work begins.

## Testing

Tests in `tests/orchestration/test_td_ga_only.py` cover:

- **Preflight validation:** Missing company context raises `TDContentPipelineError`. Missing persona artifacts raises error.
- **Filtering:** Excluded buyer_stage x intent combos return empty result (no GA run).
- **Happy path:** Mock GA pipeline returns result, verify `GapAnalysisOnlyResult` fields (ga_run_id, valid_assignment_ids, topic_query_map, analysis_path).
- **Status updates:** Verify `_update_assignment_statuses_db` called with `in_gap_analysis` then `gap_analysis_complete`.
- **Gap context enrichment:** Final `_write_ga_phase_redis` call carries `gap_context_by_assignment` with gap_score, classification, and company_best_url.
- **Phase 2 validation:** Missing `analysis.json` raises error. Cleanup called on success. Status updated to `content_produced`. `session_factory=None` raises error.
