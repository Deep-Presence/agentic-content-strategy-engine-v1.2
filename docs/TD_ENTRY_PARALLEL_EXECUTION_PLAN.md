# TD Entry Parallel Execution Plan

> **Scope:** Topic Discovery Pipeline B → topic-scoped Gap Analysis → Content Engine v1.3 entry mode
> **Branch:** `codex-td-entry-parallelism-plan`
> **Last Updated:** 2026-04-09

## Objective

Transition the TD-entry Content Engine flow from company-level pipeline exclusivity to topic-level parallel execution, while preserving the existing user-facing card identity model.

This plan assumes:

- Multiple TD-originated batches may coexist for the same company.
- Multiple topic assignments within and across batches may run in parallel.
- The frontend must reflect backend state at per-card granularity with low latency.
- Filesystem-backed pipeline state is not part of the target architecture.
- `topic_assignment_id` remains the canonical data-layer key.
- `display_id` remains the canonical user-facing label and must be carried through the execution model, not reconstructed ad hoc.

## Non-Negotiable Identity Rule

For this flow, every topic-run record and every event payload must carry both:

- `topic_assignment_id`: internal FK and stable data-layer identity
- `display_id`: human-readable universal card identity used in Kanban, detail views, reviews, and user conversations

This preserves the current Topic Discovery display-ID system in [display_id.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/topic_discovery/display_id.py), [topic_discovery.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/db/models/topic_discovery.py), and the frontend adapters in [adapters.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_lib/adapters.ts).

## Current Constraints In Code

### Backend

- TD gap-analysis creation is still serialized by slug lock in [content_v13.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/routers/content_v13.py), [\_helpers.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/routers/_helpers.py), and [db_task_store.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/services/db_task_store.py).
- TD start-production skips slug locking, but still runs under the global pipeline semaphore in [runner.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/tasks/runner.py) and [db_task_store.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/services/db_task_store.py).
- Runtime hot state is already partly topic-aware in [state_redis.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/content_engine/state_redis.py).
- Company-wide UI invalidation events are process-local in [company_event_bus.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/events/company_event_bus.py), which is not safe for multi-worker deployment.

### Frontend

- Planner sends approved assignments into the GA-only endpoint in [planner api.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/planner/_lib/api.ts).
- Content Studio computes one `activeTaskId` and subscribes to one task SSE stream in [content-studio page.tsx](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/page.tsx).
- Board freshness depends mainly on invalidation-style company SSE plus polling in [useCompanyStream.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_hooks/useCompanyStream.ts) and [useContentBriefs.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_hooks/useContentBriefs.ts).

## Target Execution Model

The execution model should become:

1. User selects N topic assignments and clicks `Send to Content Engine`.
2. Backend creates one `batch_run`.
3. Backend creates N `topic_run` rows, one per topic assignment.
4. Each `topic_run` moves independently through `gap_analysis_pending -> gap_analysis -> gap_analysis_complete -> briefing -> outlining -> drafting -> linking -> enriching -> evaluating -> review -> completed` or terminal failure/cancel states.
5. User can start production for any subset of `topic_run`s across one or more batches.
6. Frontend subscribes to company-scoped topic events and updates each card independently.

Batch remains a grouping construct for launch, audit, retry, cancel, and analytics. It is not the lock boundary.

## Data Model Changes

### 1. Add `content_engine_batch_runs`

Create a new table in a new Alembic migration after [0037_add_display_id_system.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/db/migrations/versions/0037_add_display_id_system.py).

Suggested columns:

- `id UUID PK`
- `company_id UUID NOT NULL`
- `product_id UUID NULL`
- `effective_slug VARCHAR NOT NULL`
- `source VARCHAR NOT NULL`
- `source_run_id UUID NULL`
- `source_mode VARCHAR NOT NULL`
- `status VARCHAR NOT NULL`
- `created_by UUID NULL`
- `submitted_count INT NOT NULL`
- `completed_count INT NOT NULL DEFAULT 0`
- `failed_count INT NOT NULL DEFAULT 0`
- `cancelled_count INT NOT NULL DEFAULT 0`
- `metadata_json JSONB NULL`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

Notes:

- `source` should be fixed to something like `topic_discovery_pipeline_b`.
- `source_mode` should distinguish `td_entry_mode` from future batch sources.

### 2. Add `content_engine_topic_runs`

This is the primary new durable execution table.

Suggested columns:

- `id UUID PK`
- `batch_run_id UUID FK -> content_engine_batch_runs.id`
- `pipeline_run_id UUID NULL FK -> pipeline_runs.id`
- `content_piece_id UUID NULL FK -> content_pieces.id`
- `company_id UUID NOT NULL`
- `product_id UUID NULL`
- `effective_slug VARCHAR NOT NULL`
- `topic_assignment_id UUID NOT NULL FK -> topic_assignments.id`
- `display_id VARCHAR(20) NOT NULL`
- `brief_id VARCHAR NULL`
- `ga_run_id UUID NULL`
- `entry_mode VARCHAR NOT NULL`
- `status VARCHAR NOT NULL`
- `current_stage VARCHAR NOT NULL`
- `status_seq BIGINT NOT NULL DEFAULT 0`
- `started_at TIMESTAMPTZ NULL`
- `completed_at TIMESTAMPTZ NULL`
- `failed_at TIMESTAMPTZ NULL`
- `last_error TEXT NULL`
- `metadata_json JSONB NULL`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

Indexes:

- `(effective_slug, status)`
- `(topic_assignment_id)`
- `(display_id)`
- `(batch_run_id, created_at)`
- unique `(batch_run_id, topic_assignment_id)` if the same batch must not duplicate topics

Identity rules:

- `topic_assignment_id` is the relational anchor.
- `display_id` is copied from `topic_assignments.display_id` at creation time and is retained as an execution label even if the related row is later archived or detached.
- `brief_id` remains the CE pipeline identifier if present, but should not replace `display_id` in the UX contract.

### 3. Add `content_engine_topic_events`

This table is the durable per-topic log and replaces reliance on pipeline-level log semantics for this flow.

Suggested columns:

- `id UUID PK`
- `topic_run_id UUID NOT NULL FK -> content_engine_topic_runs.id`
- `topic_assignment_id UUID NOT NULL`
- `display_id VARCHAR(20) NOT NULL`
- `content_piece_id UUID NULL`
- `pipeline_task_id VARCHAR NULL`
- `event_type VARCHAR NOT NULL`
- `stage VARCHAR NOT NULL`
- `status VARCHAR NOT NULL`
- `seq BIGINT NOT NULL`
- `payload_json JSONB NULL`
- `created_at TIMESTAMPTZ`

Indexes:

- `(topic_run_id, seq)` unique
- `(topic_assignment_id, seq)`
- `(display_id, created_at)`

This table is the audit log, replay source, and detail-view timeline.

## Backend Refactor Plan

### Phase 1: Durable topic-run service

Add a new service module:

- `core/services/content_engine_topic_runs.py`

Responsibilities:

- create batch run
- create topic runs from selected Topic Assignments
- enforce identity copy: `topic_assignment_id + display_id`
- advance topic status with optimistic `status_seq`
- write durable topic events
- expose list/query helpers for Content Studio

Add repository modules:

- `core/db/repositories/content_engine_batch_repo.py`
- `core/db/repositories/content_engine_topic_run_repo.py`
- `core/db/repositories/content_engine_topic_event_repo.py`

### Phase 2: TD entry orchestration split

Refactor [td_content_orchestrator.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/orchestration/td_content_orchestrator.py):

- keep existing business logic for topic validation and topic-scoped GA
- stop treating the request as only one opaque task outcome
- create and update `topic_run` rows before touching Redis state
- emit per-topic state transitions, not only batch-level invalidation hints
- preserve current `display_id` propagation from assignment objects

Recommended internal split:

- `prepare_td_batch_run(...)`
- `enqueue_gap_analysis_topic_runs(...)`
- `start_topic_production_runs(...)`
- `advance_topic_run_state(...)`

### Phase 3: Runner changes

Update [runner.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/tasks/runner.py):

- `run_td_gap_analysis_task(...)`
  - remove slug-lock exclusivity for TD-entry GA requests
  - keep bounded concurrency via configurable semaphore or per-pipeline quota
  - write topic-run events for each assignment transition
- `run_td_content_production_task(...)`
  - treat each selected topic assignment as an independently tracked topic-run even if one request starts several
  - attach `pipeline_task_id` to each `topic_run`
  - keep CE worker concurrency bounded by config, not by company exclusivity

Important policy change:

- Replace universal company-level exclusion with pipeline-specific concurrency budgets.
- TD-entry flow should be quota-limited, not lock-limited.

### Phase 4: CE pipeline state writes

Refactor [pipeline_v13.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/content_engine/pipeline_v13.py) and [state_helpers.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/content_engine/state_helpers.py):

- every state write must know the `topic_assignment_id`, `display_id`, `brief_id`, and `topic_run_id`
- `_write_pipeline_state_async(...)` should become a Redis hot-state update plus topic-event emit, not a filesystem dual-write helper
- when a `ContentPieceModel` is created or found, backfill `content_piece_id` onto the `topic_run`
- keep `brief_id` aligned with the current CE semantics, but do not use it as the only identity in events

Recommended change in [state_redis.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/content_engine/state_redis.py):

- move from mixed ad hoc card payloads to a stable topic-card schema
- Redis value should include:
  - `topic_assignment_id`
  - `display_id`
  - `topic_run_id`
  - `brief_id`
  - `content_piece_id`
  - `status`
  - `stage`
  - `seq`
  - `task_id`
  - `updated_at`

### Phase 5: Remove filesystem state from the target path

The TD-entry transition should explicitly stop relying on file-backed runtime state:

- remove filesystem fallback usage from [state_helpers.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/content_engine/state_helpers.py) for this pipeline path
- stop describing file-backed pipeline state as canonical in [15-PIPELINE-CONTENT-ENGINE.md](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/docs/system/15-PIPELINE-CONTENT-ENGINE.md)
- if legacy non-TD flows still need temporary compatibility, isolate that compatibility behind a narrower adapter rather than inside the core state write path

## Eventing And Transport Changes

### 1. Replace process-local company stream

Refactor [company_event_bus.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/core/events/company_event_bus.py) and [company_stream.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/routers/company_stream.py) to use Redis-backed fanout.

Two acceptable implementations:

- Redis Pub/Sub for low-latency live fanout plus DB reconciliation
- Redis Streams for replayable event delivery

Recommended choice: Redis Streams, because the app already uses Redis Streams for task SSE in [event_bus.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/tasks/event_bus.py) and the operational model is already familiar.

### 2. Introduce authoritative company event type

Add a new company-scoped event contract:

- `event_type = topic_run_changed`

Payload:

- `topic_run_id`
- `batch_run_id`
- `topic_assignment_id`
- `display_id`
- `brief_id`
- `content_piece_id`
- `task_id`
- `status`
- `stage`
- `seq`
- `updated_at`
- `effective_slug`

Rules:

- one event per committed topic state transition
- `seq` strictly increases per `topic_run`
- frontend applies only newer `seq`

Keep `state_changed` temporarily only as a coarse invalidation bridge during migration.

## API And Endpoint Changes

### Existing endpoints to modify

In [content_v13.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/routers/content_v13.py):

- `POST /content/v13/from-topics/gap-analysis`
  - allow parallel task creation for TD-entry mode
  - return `batch_run_id` plus created topic-run summaries
- `POST /content/v13/from-topics/start-production`
  - accept multiple topic assignments as it already does, but return per-topic accepted status instead of a single coarse message
- optional: deprecate or narrow the combined `/from-topics` path if it makes event ordering harder

### New endpoints

Add new content-studio BFF endpoints, likely under `api/routers/content_v13.py` or a new router if separation becomes cleaner:

- `GET /companies/{slug}/content/topic-runs`
  - list topic runs for board hydration
- `GET /companies/{slug}/content/topic-runs/{topicRunId}`
  - detail view source of truth
- `GET /companies/{slug}/content/topic-runs/{topicRunId}/events`
  - timeline for logs and debugging
- `POST /companies/{slug}/content/topic-runs/start-production`
  - bulk-start selected queued cards
- `POST /companies/{slug}/content/topic-runs/cancel`
  - bulk-cancel selected active cards
- `POST /companies/{slug}/content/topic-runs/retry`
  - bulk-retry failed cards

Schema files to update:

- [content_v13.py schema](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/schemas/content_v13.py)
- [content_data.py schema](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/api/schemas/content_data.py)

## Frontend Refactor Plan

### 1. Replace single-active-task assumption

Refactor [content-studio page.tsx](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/page.tsx):

- remove `activeTaskId` as the board’s primary runtime model
- board state should be normalized by `topicAssignmentId` or `topicRunId`
- detail panel may still subscribe to richer task/progress context, but the board cannot depend on one task stream

### 2. Add a normalized live store

Add a dedicated store:

- `frontend/src/app/(dashboard)/content-studio/_store/useTopicRunStore.ts`

Responsibilities:

- hold board state keyed by `topicRunId`
- secondary indexes by `topicAssignmentId`, `displayId`, `briefId`, `contentPieceId`
- apply event deltas idempotently using `seq`
- reconcile board hydration responses with live events

Display rule:

- render `displayId` on cards and in user-facing controls
- use `topicAssignmentId` only as the hidden relational key

### 3. Replace invalidation-only company stream handling

Refactor [useCompanyStream.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_hooks/useCompanyStream.ts):

- parse `topic_run_changed`
- update the normalized store directly
- use refetch only as recovery or initial hydration

### 4. Rework board data hook

Refactor [useContentBriefs.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_hooks/useContentBriefs.ts):

- hydrate from `topic-runs` endpoint, not only merged brief list state
- continue exposing board-friendly cards, but source them from topic runs
- reduce polling frequency once event transport is authoritative

### 5. Planner and bulk actions

Refactor planner and studio API clients:

- [planner api.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/planner/_lib/api.ts)
- [content-studio api.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_lib/api.ts)

Required UX changes:

- planner should no longer hard-fail on “another pipeline is already running” for this flow
- studio should support bulk `Start Production`
- bulk action response should map accepted/rejected items by `topic_assignment_id` and `display_id`

### 6. Type changes

Update [types.ts](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/frontend/src/app/(dashboard)/content-studio/_lib/types.ts) and adapters:

- add `topic_run_id`
- make `display_id` first-class, not optional in TD-originated cards
- add `seq`, `stage`, `batch_run_id`, `last_event_at`
- preserve `brief_id` and `content_piece_id` as downstream execution references

## Rollout Order

### Slice 1: Foundations

- add DB tables and repositories
- add topic-run service
- add Redis-backed company event stream

### Slice 2: Parallel GA

- allow parallel TD gap-analysis task creation
- create batch/topic-run rows on submission
- emit authoritative per-topic GA transitions

### Slice 3: Parallel production

- bulk-start production for queued topic runs
- wire CE stage transitions into topic-run state and event log
- keep `display_id` on every event and board card

### Slice 4: Frontend live model

- add normalized topic-run store
- switch board updates from invalidation+poll to event-driven deltas
- keep polling only as reconciliation

### Slice 5: Cleanup

- remove filesystem state dependency from TD-entry flow
- retire any now-redundant company-wide lock assumptions for this path
- update system docs

## Testing Plan

### Backend

- extend [test_td_ga_only.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/tests/orchestration/test_td_ga_only.py) for parallel batches
- extend [test_content_v13_ga_endpoints.py](/Users/aryankeshri/Documents/Deep_Presence/product/content-strategy-engine/tests/api/test_content_v13_ga_endpoints.py) for bulk acceptance and per-topic response payloads
- add tests for topic-run repos and state transitions
- add event ordering tests for `seq`
- add multi-worker delivery tests for the company stream

### Frontend

- add store reducer tests for out-of-order events
- add board tests for mixed-stage concurrent cards
- add bulk start-production flow tests

### Operational

- test worker crash recovery with in-flight topic runs
- test reconnect replay for the company stream
- test duplicate event application safety

## Estimated Effort

This is a medium-large cross-cutting change.

Rough implementation order:

1. data model and repositories
2. event transport
3. orchestration and runner refactor
4. frontend store and hook refactor
5. cleanup and hardening

The riskiest parts are:

- preserving event ordering and idempotency
- keeping CE stage identity aligned across `display_id`, `topic_assignment_id`, `brief_id`, and `content_piece_id`
- migrating the board from one-task thinking to many-topic live updates without regressions

## Explicit Out Of Scope For The Target Design

- filesystem-backed pipeline state as a first-class runtime system
- company-wide single-pipeline exclusivity for TD-entry Content Engine
- using `brief_id` alone as the user-facing identity for TD-originated cards
