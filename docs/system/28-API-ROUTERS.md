# API Routers

> **Location:** `api/routers/`
> **Owner:** API
> **Dependencies:** All services, task store, event bus, `core/services/content_engine_topic_runs.py`
> **Dependents:** Frontend (via BFF proxy)
> **Last Updated:** 2026-04-15

## Overview

31 router files defining 150+ endpoints organized by domain. All pipeline launch endpoints return 202 Accepted with a task_id for SSE tracking. Data endpoints return domain-specific response schemas.

The **Content Engine v1.3 router** (`content_v13.py`) is the most active evolution site for the TD-entry parallel execution work. Together with the runner (`api/tasks/runner.py`) and the `ContentEngineTopicRunService`, it wires per-topic durable runs, a per-company CE dispatcher, and SSE fanout enabling multiple briefs to flow through the Content Engine in parallel.

## Scalability Architecture (TD-Entry Parallelism)

Topic-level parallelism flow:

1. **Topic Discovery** approves `topic_assignment_id`s → user clicks "Run Gap Analysis".
2. `POST /content/v13/from-topics/gap-analysis` creates **batch run + N topic runs** in DB, launches a single `td_gap_analysis` task.
3. GA completes → topic runs advance to `gap_analysis_complete`. Users review and click "Start Production".
4. `POST /content/v13/from-topics/start-production` **queues** each topic run and kicks the **CE dispatcher** to claim rows up to per-company pool cap.
5. Each claim becomes its own `td_content` task. Resume claims rehydrate the original paused task.
6. On task terminal, the finally block re-runs the dispatcher so freed slots are consumed immediately.
7. Per-topic events exposed via `GET /content/v13/{slug}/topic-runs/{id}/events`.
8. `CompanyEventBus` fanout via `GET /companies/{slug}/stream` multiplexes all topic run changes.

## Route Inventory

### Infrastructure (18 routes)

| Router | Method | Path | Description |
|--------|--------|------|-------------|
| health | GET | `/health`, `/readiness` | Liveness + dependency health |
| auth | POST | `/auth/register`, `/auth/login`, `/auth/join`, `/auth/invite` | Auth lifecycle |
| auth | GET | `/auth/me` | Current user profile |
| tasks | GET | `/tasks`, `/tasks/{id}` | List + task detail |
| tasks | POST | `/tasks/{id}/cancel`, `/tasks/{id}/stream-token` | Cancel + SSE token |
| events | GET | `/tasks/{id}/events` | Per-task SSE stream |
| company_stream | GET | `/companies/{slug}/stream` | Company-wide SSE (TD-entry fanout) |

### Pipeline Launch

| Router | Key Routes |
|--------|------------|
| gap_analysis | `POST /start`, `GET /{id}/status` |
| content_v13 | Start, approve topics/briefs/content, drafts, TD-entry endpoints (15 endpoints) |
| knowledge_base | `POST /`, `GET /{id}/status`, `POST /{id}/approve` |
| audience_persona | `POST /`, approve briefs/profiles, add persona (7 endpoints) |
| voice_style_guide | `POST /`, approve authors (4 endpoints) |
| topic_discovery | `POST /`, approve taxonomy/subdomains/matrix, expansion, CRUD (14 endpoints) |
| site_audit | `POST /`, status, list/detail/findings/readiness (6 endpoints) |
| onboarding | `POST /start`, `GET /{id}/status` |

### Data Read/Write

| Router | Description |
|--------|-------------|
| gap_data | Summary, queries, clusters, signals, platforms, heatmap, embeddings, trend, profiles, gaps (10) |
| content_data | Briefs list/detail/stage, add brief, save publish metadata (5) |
| content_performance | Readiness, table, velocity, similar, detail (5) |
| content_to_prompt | Generate, list by page, metrics, pending, approve (7) |
| cms | Connect, sync, publish, refresh, stale actions, categories (11) |
| analytics | OAuth flow, connection, properties, sync (8) |

## `content_v13.py` — Deep Dive

Router prefix: `/api/v1/content/v13`. All endpoints require authentication; mutations require `member` or `superuser`. Tenant isolation enforced on every endpoint.

### Internal Helpers

- `_try_create_td_batch_records()` — best-effort durable batch/topic-run creation via `ContentEngineTopicRunService.create_td_batch()`. Failure returns `(None, [])`.
- `_validate_approval_window()` — fast-fail guard. 409 if task not `PENDING_APPROVAL`, stage mismatch, or `brief_id` doesn't match.
- `_uses_td_durable_continuation()` — detects whether approval uses TD-entry durable continuation (dispatcher path vs in-process queue).

### `POST /start` — Launch v1.3 Pipeline

- **Auth**: `member` or `superuser`.
- **Request**: `ContentStartRequestV13` (autonomous/manual entry_mode, max_topics, manual_prompt, gap_slug, product scoping, auto_approve, skip_stages).
- **Response**: `PipelineRunResponseV13(run_id, status="started", entry_mode)` with `202 Accepted`.
- **Flow**: Tenant check, gap_slug validation, build `ContentGenerationInputV13`, `create_task_durable()`, `asyncio.create_task(run_content_v13_pipeline_task(...))`.

### `POST /{run_id}/approve/topics` — HITL-1

- **Request**: `TopicApprovalRequest(decision, approved_topic_ranks, added_query_ids, removed_query_ids, feedback)`.
- **Flow**: `_validate_approval_window(task, "topic_approval")` → `task_store.submit_approval(...)`.

### `POST /{run_id}/approve/briefs` — HITL-2

Two-path endpoint. For **non-TD-entry** tasks: `task_store.submit_approval(stage="brief_approval", delivery_mode="queue")`. For **TD-entry durable continuation** tasks:

1. `task_store.validate_approval_submission(expected_nonce)`.
2. `ContentEngineTopicRunService.queue_topic_run_resume(effective_slug, pipeline_task_id, approval_data)`.
3. `task_store.record_approval_submission()`.
4. Re-run `dispatch_queued_td_content_runs(...)`.

Resume conflicts → 409. Dispatcher unavailability → 503.

### `POST /{run_id}/approve/content` — HITL-3

Same two-path pattern as HITL-2. Additional: if `body.content_markdown` provided, persisted to `review_draft.md` before approval queued. `editor_notes` truncated to 1000 tokens. `rethink=True` triggers major direction change.

### `GET/PUT /{run_id}/draft/content`

Read/write review draft. Storage key: `content/{effective_slug}/content/{brief_id}/review_draft.md`. Tenant-isolated.

### `POST /from-topics` — Legacy Single-Task TD → GA → CE

Creates single `td_content` task running the full orchestrator. Kept for older callers.

### `POST /from-topics/gap-analysis` — TD-Entry Phase 1

- **Request**: `TopicContentStartRequest`.
- **Flow**: `create_task_durable(pipeline="td_gap_analysis", allow_parallel=True)` → `_try_create_td_batch_records(initial_status="gap_analysis_pending")` → launch `run_td_gap_analysis_task()`.
- **Response**: `PipelineRunResponseV13(entry_mode="topic_discovery_ga", batch_run_id, topic_runs=[...])`.
- GA runs once per batch (one task per API call); CE production dispatches one task per topic.

### `POST /from-topics/start-production` — TD-Entry Phase 2

The dispatcher entry point.

- **Request**: `TopicContentProductionRequest(topic_assignment_ids[1..20], ga_run_id)`.
- **Flow**:
  1. Validate GA artifact exists.
  2. **Preflight conflict check**: 409 if any topic already `content_queued` or `briefing` for same `ga_run_id`.
  3. `queue_topic_runs_for_dispatch(...)` → flips to `queued`, embeds `launch_context`.
  4. Update Redis GA-phase cards + emit `state_changed`.
  5. `dispatch_queued_td_content_runs(...)` → creates up to `max_concurrent_content_engine_per_company` tasks.
  6. Audit-log each dispatched topic run.
- **Response**: `PipelineRunResponseV13(topic_runs=[TopicRunSummaryV13,...])`.

### `GET /{effective_slug}/topic-runs`

Lists all durable TD-entry topic runs. Powers Content Studio kanban hydration. Tenant isolation. Returns `TopicRunListResponseV13`.

### `GET /{effective_slug}/topic-runs/{topic_run_id}/events`

Append-only execution event log for single topic run. Returns `TopicRunEventListResponseV13` with per-event items.

## `content_performance.py`

5 endpoints under `/api/v1/content-performance`. All require auth + tenant isolation.

- `GET /readiness` — GA4 wiring state, match coverage, unmatched-path samples.
- `GET /` — Per-piece traffic, AI referrals, velocity, freshness, lifecycle, `structural_score`, citations, `platforms`. Redis-cached.
- `GET /insights/velocity` — Velocity + lifecycle per piece. Redis-cached.
- `GET /{inventory_id}/similar` — Intra-inventory cannibalization with `embeddings_ready` gate.
- `GET /{inventory_id}` — Detailed timeseries, source breakdown, AI platform breakdown, structural signals/score, citation timeline, `FreshnessAssessment`. Cached.

## `cms.py`

11 endpoints under `/api/v1/cms`.

- `POST /connect` auto-launches `cms_sync` on first connect, returns `sync_task_id`.
- `POST /publish` accepts `CMSPublishMetadata` (meta_title, meta_description, canonical_url, schema_markup). Invalidates GA4 caches after publish.
- Both `POST /publish` and `POST /refresh/{cms_post_id}` invalidate GA4 caches.
- `GET /categories` — CMS categories for publish UI.
- `POST /stale-to-triage` — queue stale post for refresh.
- CMS sync runner chains into per-page prompt generation.

## `company_stream.py`

Single endpoint: `GET /api/v1/companies/{company_slug}/stream` (auth + tenant-scoped).

- Reads `Last-Event-ID` for reconnection resume.
- Streams from `CompanyEventBus.stream()` with 30s heartbeat.
- Event types: `state_changed` (changed IDs + hint), `notification` (HITL/completion/error).
- Format: `id: {seq}\nevent: {type}\ndata: {json}\n\n`.
- **Scalability**: one EventSource per company tracks any number of concurrent CE runs.

## `content_data.py`

5 endpoints under `/api/v1/companies/{slug}/content`.

- `GET /briefs` — Brief list with inferred statuses + eval scores.
- `POST /briefs` — Manually add topic as brief.
- `GET /briefs/{brief_id}` — Full detail with eval history, exemplars, CPS.
- `GET /briefs/{brief_id}/{stage}` — Stage content (outline, draft, final, etc.).
- `PUT /briefs/{brief_id}/publish-metadata` — Persist SEO/publish metadata. **New.**

## `analytics.py`

8 GA4 endpoints (unchanged surface). `DisconnectResponse` added. Callback remains public.

## Common Patterns

- **TD-entry Phase 1**: `POST → create_task_durable(allow_parallel) → batch_records → asyncio.create_task(GA runner) → 202`.
- **TD-entry Phase 2**: `POST → validate GA → preflight Redis → queue → dispatch → 202`.
- **TD-entry approval**: `POST → validate_approval → queue_topic_run_resume → record → dispatch`.
- **Data read**: `GET → service.get_*() → schema → 200`, optionally Redis-cached.
- **Tenant isolation**: `require_tenant(slug)`, `require_company_access(slug)`, or `request.state.company_slug` check on every route.
- **Durable task creation**: `_helpers.create_task_durable()` wraps `create_task + ensure_created` with rollback on DB failure → HTTP 503.
