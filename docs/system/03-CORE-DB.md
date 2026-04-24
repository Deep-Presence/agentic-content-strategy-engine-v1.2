# Core Database Layer

> **Location:** `core/db/`
> **Owner:** Core
> **Dependencies:** SQLAlchemy 2.0, asyncpg, pgvector, Alembic
> **Dependents:** All services, repositories, API layer, pipeline persistence
> **Last Updated:** 2026-04-15

## Overview

The database module provides the complete data persistence layer using SQLAlchemy 2.0 with async support. It contains 28 ORM table models, 33 repository classes, 29 PostgreSQL enum types, and 41 Alembic migration files. The architecture uses lazy engine initialization, per-request unit-of-work sessions, and a generic CRUD base repository. pgvector extension provides native vector storage for 1536-dimensional OpenAI embeddings with HNSW indexes.

## Architecture

```
core/db/
├── engine.py          ← Lazy async engine + session factory (thread-safe)
├── base.py            ← DeclarativeBase + UUIDPKMixin + TimestampMixin
├── enums.py           ← 29 PostgreSQL ENUM types
├── dependencies.py    ← FastAPI DI: session lifecycle + repository factories
├── models/            ← 28 ORM models (one file per domain)
│   └── __init__.py    ← Registry import (loads all models for metadata)
├── repositories/      ← 33 repository classes
│   └── base.py        ← SQLAlchemyRepository[ModelT] generic CRUD
└── migrations/        ← 41 Alembic migration files
    ├── env.py
    └── versions/
```

### Key Patterns

1. **Lazy Engine:** No DB connection at import time. `get_engine()` uses double-checked locking with `threading.RLock`.
2. **Unit of Work:** `get_db_session()` commits on success, rolls back on error. One transaction per HTTP request.
3. **Repository Flush Contract:** Repositories call `session.add()` + `session.flush()` only. Never `session.commit()`.
4. **UUID Primary Keys:** All tables use Postgres-native UUID via `UUIDPKMixin`.
5. **Automatic Timestamps:** `TimestampMixin` provides `created_at`/`updated_at` with timezone.

## Engine & Session Management

### `engine.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_engine` | `() -> AsyncEngine` | Lazy-initialized async engine. Pool: size=15, overflow=20, pre-ping=True, recycle=3600s |
| `get_session_factory` | `() -> async_sessionmaker[AsyncSession]` | Lazy session factory. `expire_on_commit=False` |
| `reset_engine` | `async () -> None` | Dispose pool (testing cleanup) |

**Pool sizing:** Defaults raised from `pool_size=5` / `max_overflow=10` to `pool_size=15` / `max_overflow=20` in commit `cfcf7fd` ("Harden TD-entry scheduler recovery"). The larger pool absorbs concurrent QA traffic against topic-run endpoints (`/content/briefs`, Content Studio polling, company-wide SSE) while the TD-entry parallelism work lets many topic runs hit the DB simultaneously. Override via `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` in settings.

### `base.py`

| Class | Purpose |
|-------|---------|
| `Base(DeclarativeBase)` | SQLAlchemy 2.0 declarative base |
| `UUIDPKMixin` | `id: Mapped[UUID]` primary key, auto `uuid.uuid4()` |
| `TimestampMixin` | `created_at`, `updated_at` with `server_default=func.now()` |

### `dependencies.py`

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    # Yields session, commits on success, rolls back on error

# Repository factories (FastAPI Depends):
get_company_repo, get_auth_repo, get_pipeline_repo, get_cache_repo,
get_gap_analysis_repo, get_embedding_repo, get_tracking_repo, get_content_repo
```

## PostgreSQL Enums (29 types)

| Category | Enum Types |
|----------|-----------|
| **Auth** | `UserRole` (superuser, member, viewer) |
| **Pipeline** | `PipelineType` (13 values), `PipelineStatus` (5), `StageStatus` (6) |
| **Gap Analysis** | `SearchEngine` (4), `GapClassification` (5) |
| **Research** | `ArtifactType` (4), `ArtifactStatus` (6), `ResearchRunStatus` (5) |
| **Content** | `ContentPieceStatus` (6), `ContentArtifactStage` (6) |
| **Site Audit** | `FindingSeverity` (5) |
| **Tracking** | `TrackingStatus` (3) |
| **Topic Discovery** | `TDStatus` (5), `BuyerStage` (3), `IntentType` (4), `AudienceSegmentType` (2), `RelevanceCell` (3), `TopicAssignmentStatus` (8) |
| **CMS** | `CMSProvider` (5), `CMSPostStatus` (4), `CMSPublishAction` (3) |
| **Analytics** | `AnalyticsProvider` (1), `AnalyticsSyncStatus` (5) |
| **Content Inventory** | `ContentIngestionSource` (6) |

Content engine batch/topic run status and scheduler-state values are stored as plain `String(64)` columns (not enums) so the TD-entry scheduler can evolve its state machine without Alembic type migrations.

## ORM Models (28 Tables)

### Organization Domain (5 tables)

| Table | Model | Key Columns |
|-------|-------|------------|
| `companies` | `CompanyModel` | slug (unique), name, domain, display_id_prefix, display_id_counter |
| `products` | `ProductModel` | company_id (FK), slug, name, domain. Unique: (company_id, slug) |
| `users` | `UserModel` | company_id (FK), email (unique), password_hash, role (enum) |
| `invites` | `InviteModel` | company_id (FK), code (unique), role, expires_at |
| `company_pipeline_defaults` | `PipelineDefaultsModel` | company_id (FK, unique), defaults_json (JSONB) |

### Pipeline Execution (2 tables)

| Table | Model | Key Columns |
|-------|-------|------------|
| `pipeline_runs` | `PipelineRunModel` | company_id, effective_slug, pipeline_type, status, config (JSONB), summary (JSONB), parent_run_id (self-ref) |
| `pipeline_stage_logs` | `PipelineStageLogModel` | run_id (FK), stage_name, status, duration_seconds, items_processed |

### Content Engine Runs (3 tables — NEW in 0038/0039)

Dedicated durable state for the TD-entry Content Engine flow. These tables replace the old filesystem-backed per-brief pipeline state with per-topic rows that can progress independently and be resumed after restart. See the [Content Engine Runs ORM](#content-engine-runs-orm) section below for full field reference.

| Table | Model | Purpose |
|-------|-------|---------|
| `content_engine_batch_runs` | `ContentEngineBatchRunModel` | Groups topic runs by launch submission (source = td_pipeline_b, etc.) |
| `content_engine_topic_runs` | `ContentEngineTopicRunModel` | One row per TopicAssignment executing through CE — durable identity + scheduler state |
| `content_engine_topic_events` | `ContentEngineTopicEventModel` | Append-only per-topic event log (activity feed + replay) |

### Gap Analysis Domain (8 tables)

| Table | Key Purpose |
|-------|------------|
| `run_queries` | Query per run. Unique: (run_id, query_id) |
| `run_citations` | Citation per query per engine. Composite FK to run_queries |
| `query_gaps` | Gap classification per query. FK to content_pieces (targeted_by) |
| `query_exemplars` | Top citation exemplars per gap |
| `cluster_specs` | Per-cluster structural content specs |
| `spa_results` | Semantic Proximity Analysis statistics |
| `centroid_results` | Centroid distance per cluster |
| `cluster_proximity_stats` | Citation/company similarity distributions |

### Content Domain (3 tables)

| Table | Key Purpose |
|-------|------------|
| `content_pieces` | Generated content. FK to pipeline_runs, topic_assignments |
| `content_artifacts` | Stage-level artifacts. Unique: (piece_id, stage) |
| `research_artifacts` | Versioned research outputs (KB, persona, VSG) |

### Topic Discovery Domain (7 tables)

| Table | Key Purpose |
|-------|------------|
| `topic_discoveries` | Discovery run metadata |
| `taxonomy_trees` | Versioned taxonomy snapshots (JSON tree) |
| `subdomain_nodes` | Self-referencing hierarchy with priority scores |
| `topic_assignments` | Content opportunities in dimensionality matrix. Has `display_id` |
| `topic_assignment_cannibalization` | **NEW (0041)** — Durable cannibalization assessment per assignment |
| `td_source_results` | Per-source S1 generation statistics |
| `td_persona_affinity` | Many-to-many persona↔subdomain scores |

See [Topic Assignment Cannibalization](#topic-assignment-cannibalization-0041) below for full schema.

### Research Domain (7 tables)

KB: `kb_runs`, `kb_documents`, `kb_syntheses`
AP: `persona_runs`, `persona_profiles`
VSG: `vsg_runs`, `vsg_authors`, `vsg_guides`

### Site Audit (3 tables)

`site_audits` (enriched with 20+ columns), `audit_findings`, `audit_page_results`

### Tracking (3 tables)

`tracking_snapshots`, `content_mention_tracking`, `content_piece_tracking`

### Daily Tracker (3 tables)

`tracked_prompts` (with fanout self-ref), `daily_runs`, `daily_run_responses`

### Embeddings (5 tables, all pgvector 1536-dim)

`semantic_units`, `query_embeddings`, `paragraph_embeddings`, `run_paragraph_scores`, `persona_embeddings`

### Cache (3 tables)

`platform_result_cache`, `url_enrichment_cache` (now with `published_at` / `modified_at` — see 0040), `url_structural_signals` (45 signal columns)

### CMS (3 tables)

`cms_connections`, `cms_publish_records`, `cms_synced_posts`

### Analytics (3 tables)

`analytics_connections` (GA4 OAuth), `ga4_traffic_data`, `ga4_conversion_events`

### Content Inventory (2 tables)

`content_inventory` (universal CMS-agnostic registry with embedding), `content_inventory_prompts` (M:N join)

### Infrastructure (3 tables)

`api_tasks` (pipeline task persistence), `audit_logs` (append-only, no updated_at), `knowledge_documents`

### Cost Tracking (2 tables)

`llm_cost_events`, `model_pricing`

## Content Engine Runs ORM

**File:** `core/db/models/content_engine_runs.py`
**Why it exists:** From `docs/TD_ENTRY_PARALLEL_EXECUTION_PLAN.md` — the TD-entry Content Engine needed to move from company-level pipeline exclusivity (one slug lock, one `pipeline_state.json`) to topic-level parallelism where N topic assignments within a batch run independently, survive worker restart, and retain durable per-card identity (`topic_assignment_id` + `display_id`) all the way from the Planner into the Content Studio kanban. Filesystem-backed pipeline state was explicitly ruled out of the target architecture, so these tables became the source of truth.

### `ContentEngineBatchRunModel` → `content_engine_batch_runs`

A user-submitted batch of TD-originated topics sent to Content Engine. Groups topic runs by launch submission — useful for retry, cancel, activity feeds, and audit. The batch is **not** a lock boundary; topic runs inside a batch execute independently.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | PK | via `UUIDPKMixin` |
| `company_id` | UUID | no | FK `companies.id` ON DELETE CASCADE |
| `product_id` | UUID | yes | FK `products.id` ON DELETE SET NULL |
| `effective_slug` | String | no | `{company}__{product}` scoping key |
| `source` | String(64) | no | Launch source, e.g. `td_pipeline_b`, `manual_batch` |
| `source_mode` | String(64) | no | Sub-mode flag (full, partial, resume) |
| `status` | String(64) | no | Batch-level aggregate (default `pending`) |
| `pipeline_task_id` | String(128) | yes | TaskStore task handle for the launching request |
| `source_run_id` | UUID | yes | FK `pipeline_runs.id` ON DELETE SET NULL — upstream TD run |
| `created_by_user_id` | UUID | yes | FK `users.id` ON DELETE SET NULL |
| `submitted_count` | Integer | no | default 0 |
| `completed_count` | Integer | no | default 0 |
| `failed_count` | Integer | no | default 0 |
| `cancelled_count` | Integer | no | default 0 |
| `metadata_json` | JSONB | yes | Launch options, UI context, planner filters |
| `created_at` / `updated_at` | Timestamptz | no | via `TimestampMixin` |

**Indexes:**
- `ix_ce_batch_runs_slug_status` → `(effective_slug, status)` for slug-scoped batch listings
- `ix_ce_batch_runs_company_created` → `(company_id, created_at)` for Home / Activity feeds

### `ContentEngineTopicRunModel` → `content_engine_topic_runs`

Durable execution row for one `TopicAssignment` through the TD-entry Content Engine. **This is the per-card identity** — everything the Content Studio kanban renders eventually hangs off one of these rows. Each topic run progresses independently through the CE stage machine (`gap_analysis_pending → gap_analysis → gap_analysis_complete → briefing → outlining → drafting → linking → enriching → evaluating → review → completed` / `failed` / `cancelled`).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | PK | |
| `batch_run_id` | UUID | no | FK `content_engine_batch_runs.id` ON DELETE CASCADE |
| `pipeline_run_id` | UUID | yes | FK `pipeline_runs.id` ON DELETE SET NULL — underlying CE run |
| `content_piece_id` | UUID | yes | FK `content_pieces.id` ON DELETE SET NULL — set after final-review completes |
| `company_id` | UUID | no | FK `companies.id` ON DELETE CASCADE |
| `product_id` | UUID | yes | FK `products.id` ON DELETE SET NULL |
| `effective_slug` | String | no | Routing key for Redis state + SSE streams |
| `topic_assignment_id` | UUID | no | FK `topic_assignments.id` ON DELETE **RESTRICT** — identity anchor |
| `display_id` | String(20) | no | Human-readable card label (e.g. `WE-042`) — carried end-to-end |
| `topic_text` | Text | no | Snapshot of the assignment's topic for stable display |
| `brief_id` | String(64) | yes | CE brief handle (replaces old `brief-001` reset-per-run scheme) |
| `ga_run_id` | UUID | yes | Upstream topic-scoped Gap Analysis run |
| `pipeline_task_id` | String(128) | yes | TaskStore task executing this topic |
| `entry_mode` | String(64) | no | `td_pipeline_b`, `manual`, `resume` |
| `status` | String(64) | no | Topic-run aggregate status |
| `current_stage` | String(64) | no | CE stage name (drives Content Studio pill) |
| `status_seq` | BigInteger | no | Monotonic version counter for version-aware merge (SSE reconciliation) |
| `started_at` | Timestamptz | yes | First CE stage enter |
| `completed_at` | Timestamptz | yes | Final-review completed |
| `failed_at` | Timestamptz | yes | Terminal failure |
| `last_error` | Text | yes | Truncated error for UI |
| `metadata_json` | JSONB | yes | Planner context, dispatch metadata, UI hints |
| `created_at` / `updated_at` | Timestamptz | no | |

**Scheduler-state columns (added by migration 0039):**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `scheduler_state` | String(64) | no | `idle` / `queued` / `resume_queued` / `claimed` / `running` / `waiting_human` — dedicated lane separate from `status` |
| `claim_token` | String(128) | yes | Identifies the worker holding the claim (populated by `claim_queued_runs_for_company`) |
| `queued_at` | Timestamptz | yes | When the row entered the scheduler queue |
| `claimed_at` | Timestamptz | yes | When a worker claimed it (SELECT … FOR UPDATE SKIP LOCKED) |
| `waiting_for_human_at` | Timestamptz | yes | HITL pause timestamp |
| `continuation_payload_json` | JSONB | yes | Opaque CE continuation state used on resume — replaces `pipeline_state.json` |

Migration 0039 backfills `scheduler_state` from legacy `status='content_queued'` values and seeds `claim_token` / `claimed_at` from any `metadata_json.dispatch_*` hints.

**Indexes:**
- `ix_ce_topic_runs_slug_status` → `(effective_slug, status)` — slug-scoped board queries
- `ix_ce_topic_runs_assignment` → `(topic_assignment_id)` — reverse lookup from Planner
- `ix_ce_topic_runs_display_id` → `(display_id)` — UI detail pages + conversational lookups
- `ix_ce_topic_runs_batch_created` → `(batch_run_id, created_at)` — batch detail views
- `ix_ce_topic_runs_ga_assignment` → `(ga_run_id, topic_assignment_id)` — GA → CE join for snap-back detection
- `ix_ce_topic_runs_company_scheduler` → `(company_id, scheduler_state, updated_at)` **(0039)** — scheduler claim scan

**Constraints:**
- `uq_ce_topic_runs_batch_assignment` → UNIQUE `(batch_run_id, topic_assignment_id)` — one row per assignment per batch (idempotent batch replays)
- `topic_assignment_id` ON DELETE RESTRICT — TD assignments cannot be hard-deleted while a topic run references them

### `ContentEngineTopicEventModel` → `content_engine_topic_events`

Append-only per-topic execution event log. Feeds the activity feed, post-mortem replay, and (eventually) the per-card audit timeline. Uses a per-topic monotonically increasing `seq` so consumers can detect gaps and reorder.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | PK | |
| `topic_run_id` | UUID | no | FK `content_engine_topic_runs.id` ON DELETE CASCADE |
| `topic_assignment_id` | UUID | no | FK `topic_assignments.id` ON DELETE RESTRICT (denormalized for query speed) |
| `display_id` | String(20) | no | Denormalized — activity feeds don't need a JOIN to resolve the card label |
| `content_piece_id` | UUID | yes | FK `content_pieces.id` ON DELETE SET NULL |
| `pipeline_task_id` | String(128) | yes | |
| `event_type` | String(64) | no | `stage_started`, `stage_completed`, `error`, `waiting_human`, `resumed`, … |
| `stage` | String(64) | no | CE stage name at event time |
| `status` | String(64) | no | Topic-run status snapshot |
| `seq` | BigInteger | no | Per-topic monotonic sequence (allocated via `get_next_seq`) |
| `payload_json` | JSONB | yes | Stage output summary, error details, HITL payloads |
| `created_at` | Timestamptz | no | Event time (no `TimestampMixin` — immutable) |

**Indexes:**
- `ix_ce_topic_events_assignment_seq` → `(topic_assignment_id, seq)` — replay timeline for one card
- `ix_ce_topic_events_display_created` → `(display_id, created_at)` — UI activity feeds

**Constraints:**
- `uq_ce_topic_events_run_seq` → UNIQUE `(topic_run_id, seq)` — enforces strict monotonic per-topic ordering

### Scalability Notes

- Each topic run has its own row, its own scheduler lane, and its own event stream — there is no company-wide lock. Hundreds of topic runs per company can make forward progress in parallel, bounded only by worker count and the global `semaphore:pipelines` Redis gate.
- `ix_ce_topic_runs_company_scheduler` + `SELECT … FOR UPDATE SKIP LOCKED` in `claim_queued_runs_for_company()` lets multiple workers race for claims without contention.
- `continuation_payload_json` means HITL pauses and worker restarts are resumable from the DB alone — the legacy `pipeline_state.json` file is no longer part of the target architecture.
- Append-only events table with bigint `seq` gives the frontend a cheap way to drive incremental activity feeds without re-polling status.

## Topic Assignment Cannibalization (0041)

**File:** `core/db/models/topic_discovery.py` → `TopicAssignmentCannibalizationModel`
**Table:** `topic_assignment_cannibalization`

Durable per-assignment cannibalization assessment, introduced by commit `ec9b4d4` ("Add fanout-aware cannibalization overlap evidence") alongside the planner cannibalization scoring phase 1 (`68656f8`). One row per topic assignment — UNIQUE on `assignment_id` — recomputed as inventory or prompts change.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | PK | |
| `assignment_id` | UUID | no | FK `topic_assignments.id` ON DELETE CASCADE — UNIQUE |
| `discovery_id` | UUID | no | FK `topic_discoveries.id` ON DELETE CASCADE |
| `company_id` | UUID | no | FK `companies.id` ON DELETE CASCADE |
| `top_match_inventory_id` | UUID | yes | FK `content_inventory.id` ON DELETE SET NULL — best-matching existing page |
| `max_similarity` | Float | no | default 0 — best cosine similarity found across inventory |
| `risk_score` | Float | no | default 0 — composite 0.0–1.0 score |
| `risk_level` | String(32) | no | default `none` — `none` / `low` / `medium` / `high` / `critical` |
| `recommended_action` | String(64) | no | default `safe_to_create_new` — e.g. `refresh_existing`, `merge_with_existing` |
| `reasons_json` | JSONB | yes | List of human-readable reason strings |
| `matches_json` | JSONB | yes | Top-K matching inventory rows with per-match similarity + evidence |
| `signals_json` | JSONB | yes | Query-overlap signals (fanout-aware), structural signals, prompt coverage |
| `metadata_json` | JSONB | yes | Scoring version, timestamps, feature flags |
| `created_at` / `updated_at` | Timestamptz | no | via `TimestampMixin` |

**Indexes / constraints:**
- `uq_topic_assignment_cannibalization_assignment` → UNIQUE `(assignment_id)` — one durable row per assignment
- `ix_td_assignment_cannibalization_discovery` → `(discovery_id)` — full-run sweeps
- `ix_td_assignment_cannibalization_company_level` → `(company_id, risk_level)` — Home / Planner risk dashboards

## URL Enrichment Freshness (0040)

**File:** `core/db/models/cache.py` → `UrlEnrichmentCacheModel`
**Commit:** `2b04149` ("feat: benchmark freshness against cited exemplars")

Migration 0040 adds two nullable datetime columns to `url_enrichment_cache`:

| Column | Type | Purpose |
|--------|------|---------|
| `published_at` | Timestamptz (nullable) | Original publish date parsed from page metadata (OpenGraph `article:published_time`, JSON-LD `datePublished`, HTML meta) |
| `modified_at` | Timestamptz (nullable) | Last-modified date from the same metadata family |

These feed the **cited-exemplar freshness benchmark**: when evaluating whether a targeted content piece is stale, the gap analysis repository reaches through `QueryExemplar` → `UrlEnrichmentCacheModel` and returns the exemplars' `modified_at` (falling back to `published_at`). The benchmark is computed per published URL via `GapAnalysisRepository.get_cited_exemplar_dates_for_inventory_url()`. Freshness is effectively "how old is my content relative to the exemplars that currently get cited for the same queries".

`CacheRepository.bulk_upsert_url_enrichment` was updated (+4 lines) to include `published_at` / `modified_at` in the `ON CONFLICT DO UPDATE` set clause so scraper re-runs refresh these columns.

## Repository Layer (33 Repositories)

### Generic Base

```python
class SQLAlchemyRepository[ModelT]:
    """Generic CRUD operations."""
    async def get_by_id(id: UUID | str) -> ModelT | None
    async def create(**kwargs) -> ModelT  # flush only
    async def update(id, **kwargs) -> ModelT | None
    async def delete(id) -> bool
    async def list_all(*, limit=100, offset=0) -> Sequence[ModelT]
```

### Specialized Repositories

| Repository | Key Methods |
|------------|------------|
| `CompanyRepository` | `get_by_slug`, `get_by_domain`, `slug_exists`, `list_active` |
| `ContentRepository` | `create_piece`, `update_status`, `list_by_run`, `get_by_gap_query`, `list_by_topic_assignment`, `get_by_slug_and_brief_id` |
| `GapAnalysisRepository` | `bulk_insert_query_gaps`, `get_gaps_by_run`, `update_gap`, `bulk_insert_exemplars`, `get_cited_exemplar_dates_for_inventory_url` |
| `PipelineRepository` | `create_run`, `update_status`, `list_by_company`, `add_stage_log`, `get_latest_completed` |
| `TopicDiscoveryRepository` | `create_discovery`, `get_by_company`, `get_latest_by_company`, `list_by_company`, `upsert_taxonomy`, `list_assignments`, `bulk_insert_assignments` |
| `TopicAssignmentRepository` | `list_for_cannibalization`, `list_delta_recompute_assignment_ids`, `bulk_merge_metadata`, `update_assignment_status` |
| `TopicAssignmentCannibalizationRepository` | `get_by_assignment_ids`, `get_assignment_ids_by_top_match_inventory_ids`, `bulk_upsert_assessments` |
| `ContentInventoryRepository` | `upsert_by_url`, `list_by_company`, `list_with_pagination`, `update_embedding`, `find_similar_batch`, `find_similar_to_page` |
| `ContentInventoryPromptRepository` | Content-to-Prompt M:N join — see below |
| `ContentEngineBatchRunRepository` | `list_by_slug` |
| `ContentEngineTopicRunRepository` | `bulk_create`, `list_by_slug`, `list_by_assignment_ids`, `list_by_brief_ids`, `get_latest_by_assignment`, `get_by_id_and_slug`, `get_by_pipeline_task_id`, `count_by_batch`, `claim_queued_runs_for_company`, `list_recovery_candidates` |
| `ContentEngineTopicEventRepository` | `get_next_seq`, `append_event`, `list_for_topic_run` |
| `DailyTrackerRepository` | `create_prompt`, `list_prompts`, `create_run`, `create_response`, `list_responses_by_run` |
| `EmbeddingRepository` | `create_semantic_unit`, `list_by_company`, `create_query_embedding` |
| `SiteAuditRepository` | `create_audit`, `list_by_company`, `create_finding`, `list_findings` |
| `CmsRepository` | `get_connection_by_slug`, `create_publish_record`, `upsert_synced_post` |
| `AnalyticsConnectionRepository` | `get_active_connection`, `get_by_company_slug`, `deactivate`, `update_tokens`, `update_sync_status`, `update_property`, `get_all_active` |
| `GA4TrafficDataRepository` | `bulk_upsert`, `get_by_date_range`, `get_ai_referrals`, `delete_by_connection`, `mark_ai_referrals`, `get_per_page_aggregates`, `count_rows`, `list_distinct_landing_page_urls`, `get_daily_timeseries`, `get_source_breakdown`, `get_ai_platform_breakdown` |
| `GA4ConversionEventRepository` | `bulk_upsert`, `get_by_date_range`, `get_ai_referrals`, `delete_by_connection`, `mark_ai_referrals` |
| `CacheRepository` | `bulk_upsert_url_enrichment` (now includes `published_at` / `modified_at`), platform cache upsert/lookup |

Plus 13 more: auth, cost, invite, kb, persona, platform, platform_defaults, product, research_artifact, signal, task, tracking, vsg, audit_log, content_artifact, knowledge_docs.

### `ContentEngineBatchRunRepository`

```python
class ContentEngineBatchRunRepository(SQLAlchemyRepository[ContentEngineBatchRunModel]):
    async def list_by_slug(effective_slug, *, limit=100, offset=0) -> Sequence[...]
```

Minimal surface — the orchestrator creates batch rows via `create()` from the base class and updates aggregate counters in place. Batch rows are almost entirely read in API responses (Content Studio "submissions" view, activity feed).

### `ContentEngineTopicRunRepository`

The core scheduler repository. Methods:

| Method | Purpose |
|--------|---------|
| `bulk_create(runs)` | Insert N topic-run rows per batch launch in one flush. |
| `list_by_slug(effective_slug, *, limit=200, offset=0)` | Slug-scoped Content Studio board query. |
| `list_by_assignment_ids(assignment_ids, *, ga_run_id, pipeline_task_id, effective_slug)` | Reverse lookup from Planner selection or GA snap-back detection. |
| `list_by_brief_ids(brief_ids, *, pipeline_task_id, effective_slug)` | Bridge legacy `brief_id` strings to topic-run rows during CE transition. |
| `get_latest_by_assignment(topic_assignment_id, *, ga_run_id)` | Fetch the most recent run for one assignment (Planner detail, resume). |
| `get_by_id_and_slug(topic_run_id, *, effective_slug)` | Tenant-safe single-row fetch for API routes. |
| `get_by_pipeline_task_id(pipeline_task_id, *, effective_slug)` | Map a TaskStore task back to its topic run (SSE reconciliation, approval flows). |
| `count_by_batch(batch_run_id)` | Aggregate count for batch progress UI. |
| `claim_queued_runs_for_company(*, company_id, limit, claim_token)` | **Atomic claim.** `SELECT … WHERE scheduler_state IN ('queued','resume_queued') ORDER BY scheduler_state DESC, updated_at ASC, created_at ASC LIMIT N FOR UPDATE SKIP LOCKED`, then transitions each claimed row to `scheduler_state='claimed'`, stamps `claim_token` and `claimed_at`. Prioritises resume-queued over fresh-queued so HITL approvals fast-path. Returns the claimed rows to the caller. |
| `list_recovery_candidates()` | Startup reconciliation. Returns all rows in `(queued, resume_queued, claimed, running, waiting_human)` so the scheduler can re-queue stranded work after a worker restart. |

The claim method + `ix_ce_topic_runs_company_scheduler` index is what makes the TD-entry scheduler safe under concurrent workers — multiple workers each `claim_queued_runs_for_company(limit=K)` in parallel and their claims never collide thanks to `FOR UPDATE SKIP LOCKED`.

### `ContentEngineTopicEventRepository`

| Method | Purpose |
|--------|---------|
| `get_next_seq(topic_run_id)` | `SELECT MAX(seq)+1` — allocates the next per-topic monotonic sequence number. |
| `append_event(*, topic_run_id, topic_assignment_id, display_id, event_type, stage, status, pipeline_task_id, content_piece_id, seq, payload_json)` | Append-only event write. If `seq` is omitted it's allocated via `get_next_seq`. Inserts with `datetime.now(timezone.utc)`. |
| `list_for_topic_run(topic_run_id, *, limit=200)` | Ordered-by-seq event list for the UI activity timeline. |

### `ContentInventoryPromptRepository` (Content-to-Prompt join)

`core/db/repositories/content_inventory_prompt_repo.py` — substantially extended in this range to support the Content Performance page and the fanout-aware cannibalization overlap evidence (commit `ec9b4d4`). Methods:

| Method | Purpose |
|--------|---------|
| `bulk_create_links(links)` | Create multiple `content_inventory_prompts` join rows in one flush. |
| `get_prompts_for_page(inventory_id, *, approved_only)` | List links for a content inventory page. |
| `get_pages_for_prompt(prompt_id)` | Reverse lookup. |
| `link_exists(inventory_id, prompt_id)` | Existence check (dedup race guard). |
| `count_links_for_prompt(prompt_id)` | Orphan-detection helper. |
| `delete_links_for_page(inventory_id, *, preserve_user_edited=True)` | Bulk delete during regeneration, optionally preserving user-edited rows. |
| `delete_links_by_run(generation_run_id)` | Bulk delete by generation run id. |
| `approve_links(link_ids)` | Bulk approve pending links. |
| `get_pending_for_company(company_id, *, limit, offset)` / `get_pending_by_slug(effective_slug, …)` | HITL review queue. |
| `get_page_prompt_ids(inventory_id)` | Approved prompt ids linked to a page. |
| `get_page_root_prompt_ids(inventory_id)` | **Fanout-aware.** Collapses fanout children to their parent prompt via `coalesce(parent_prompt_id, id)` so page-level analytics roll up the full prompt family. |
| `get_inventory_ids_for_root_prompt_ids(root_prompt_ids)` | Reverse prompt-family lookup. |
| `get_page_prompt_scope(inventory_id)` / `get_page_prompt_scopes_batch(inventory_ids)` | Returns `{root_prompt_ids, prompt_ids, fanout_prompt_ids, prompt_texts}` — batched variant does it in two DB round-trips for N pages. |
| `get_page_query_overlap_signals(inventory_id, candidate_queries)` | Deterministic token-overlap scoring between a TD assignment's candidate queries and the page's prompt scope. Powers the fanout-aware cannibalization evidence in the planner. |
| `get_page_metrics(inventory_id, start, end)` | Aggregates `mention_rate`, `citation_rate`, active prompt count, and per-buyer-stage breakdown across all linked prompt families (fanout-aware join on `daily_run_responses`). |
| `get_citation_metrics_batch(company_id, start, end, *, inventory_ids)` | Single-query per-engine citation presence for the Content Performance table. Builds a fanout-aware `linked_roots` CTE and returns `{inventory_id, total_cited, cited_openai, cited_claude, cited_gemini, cited_perplexity}`. |
| `get_citation_timeline(inventory_id, start, end)` | Daily cited/total timeseries for the content performance drawer. |
| `get_pages_without_prompts(company_id, *, limit)` | LEFT-JOIN anti-join to find inventory pages with zero linked prompts. |
| `get_pages_with_counts(company_id, *, limit, offset)` | Pages with per-page `prompt_count` + `approved_count`. |

Internal helpers `_tokenize_query_text`, `_build_page_scope`, `_compute_query_overlap_signals`, `_query_overlap_ratio` implement the deterministic token overlap used by `get_page_query_overlap_signals`. Stop-word list covers common English articles/prepositions; minimum token length is 3 chars; match threshold for `matched_queries` is 0.5 Jaccard-on-query-tokens.

### `AnalyticsRepository` updates

Two-part update. `AnalyticsConnectionRepository` gained a `get_by_company_slug(company_slug, tenant_id, *, active_only=True)` lookup needed by the GA4 reconnect / upsert flow — without `active_only=False`, reconnecting a previously deactivated connection would create a duplicate row. `GA4TrafficDataRepository.mark_ai_referrals(connection_id, source_platform_map)` is the batch CASE/WHEN classifier: it takes `{"chatgpt.com": "openai", "claude.ai": "anthropic", …}` and emits a single `UPDATE … WHERE is_ai_referral=false AND (source ILIKE '%chatgpt.com%' OR …)` setting `is_ai_referral=true` and `ai_platform=CASE WHEN source ILIKE '%chatgpt.com%' THEN 'openai' WHEN …`. The same helper exists on `GA4ConversionEventRepository`.

### `GapAnalysisRepository.get_cited_exemplar_dates_for_inventory_url`

Core of the freshness benchmark from commit `2b04149`. Given a `company_id` and an `inventory_url` (with optional `normalized_url` alternate form), it builds a URL candidate set including trailing-slash variants and executes:

```
SELECT url_enrichment_cache.modified_at, url_enrichment_cache.published_at
FROM query_exemplars
JOIN query_gaps ON query_gaps.id = query_exemplars.query_gap_id
JOIN content_pieces ON content_pieces.id = query_gaps.targeted_by_content_id
JOIN url_enrichment_cache ON url_enrichment_cache.id = query_exemplars.url_enrichment_id
WHERE content_pieces.company_id = :company_id
  AND content_pieces.published_url IN :url_candidates
```

Returns a list of best-freshness datetimes (modified first, published fallback) for every cited exemplar on every gap targeted by that inventory URL. The service layer then compares the inventory page's own `modified_at` against this distribution to produce the freshness benchmark surface.

### `TopicDiscoveryRepository` / `TopicAssignmentRepository` additions

| Method | Purpose |
|--------|---------|
| `TopicDiscoveryRepository.get_latest_by_company(company_id)` | Convenience wrapper over `get_by_company`, returning the most recent row — used heavily by cannibalization and Planner code paths that just need "the current discovery". |
| `TopicAssignmentRepository.list_for_cannibalization(discovery_id, *, matrix_version, subdomain_node_id, expansion_batch_id, assignment_ids)` | Durable cannibalization sync query. Any combination of filters works, sorted by `created_at ASC` for stable recompute ordering. |
| `TopicAssignmentRepository.list_delta_recompute_assignment_ids(discovery_id, *, matrix_version, limit)` | Returns **only planner-open** assignment ids (`not_started`, `approved`, `rejected`, `gap_analysis_complete`) ordered by `priority_score DESC NULLS LAST, created_at ASC`. Deliberately narrow — ensures inventory or prompt changes only re-evaluate current planner work, not the full historical universe. |
| `TopicAssignmentRepository.bulk_merge_metadata(metadata_by_assignment_id)` | Additive `metadata_json` merge (existing dict ∪ new dict per row). Used by scoring and cannibalization writers that want to stamp extra fields without clobbering peer writers. |

### `TopicAssignmentCannibalizationRepository`

New repository wrapping the 0041 table:

| Method | Purpose |
|--------|---------|
| `get_by_assignment_ids(assignment_ids)` | Bulk fetch durable assessments — keyed by assignment. |
| `get_assignment_ids_by_top_match_inventory_ids(inventory_ids, *, discovery_id)` | Reverse lookup: which assignments currently have this inventory page as their top match? Drives incremental recompute when inventory changes. |
| `bulk_upsert_assessments(assessments)` | Upsert-by-assignment_id. Loads existing rows for the target keys, updates in place, inserts the rest, single flush. |

### `ContentInventoryRepository.find_similar_batch`

New batched vector search method: takes a `dict[str, list[float]]` of keyed query embeddings and returns, per key, the top-K similar inventory pages above a similarity threshold. Emitted as a single raw-SQL CTE using `VALUES (:key_i, CAST(:emb_i AS vector))`, joined against `content_inventory` with `(1 - (ci.embedding <=> qe.embedding)) AS similarity`, then row-numbered per key with a `similarity_rank <= :limit` gate. Avoids N round-trips when the cannibalization pipeline evaluates many candidate queries at once.

### `CacheRepository.bulk_upsert_url_enrichment`

Updated for 0040: `ON CONFLICT DO UPDATE` set clauses now include `published_at` and `modified_at` so scraper re-runs refresh the freshness columns. Both code paths (single-row upsert and bulk path) were updated symmetrically.

## Migrations (41)

| Range | Purpose |
|-------|---------|
| `0001` | Initial schema: pgvector extension, all enums, 15+ core tables |
| `0002` | HNSW indexes on embedding columns |
| `0003-0009` | Bug fixes, api_tasks, daily_tracker, TD v2, site audit enrichment |
| `0010-0015` | Research tables (KB/AP/VSG), TD-content link, industry column |
| `0016-0020` | pgvector upgrade, CPS tables, audit_logs, pipeline enums, content artifacts |
| `0021-0025` | CMS integration, worker_id, LLM cost events, fanout queries, tracking indexes |
| `0026-0030` | Content inventory, analytics/GA4, planner statuses, TD DB-primary, career_role |
| `0031-0037` | TD additive upsert, GA phases, structural signals, content-to-prompt join, embedding lab, content production status, display ID system |
| `0038` | **Content Engine batch/topic runs** — creates `content_engine_batch_runs`, `content_engine_topic_runs`, `content_engine_topic_events` with all indexes and cross-table FKs. Foundation for TD-entry parallelism. |
| `0039` | **Topic-run scheduler state** — adds `scheduler_state`, `claim_token`, `queued_at`, `claimed_at`, `waiting_for_human_at`, `continuation_payload_json` to `content_engine_topic_runs` plus `ix_ce_topic_runs_company_scheduler` composite index. Backfills `scheduler_state` from legacy `status='content_queued'` and seeds `claim_token` / `claimed_at` from any `metadata_json.dispatch_*` hints. |
| `0040` | **URL enrichment freshness dates** — adds `published_at` and `modified_at` nullable timestamptz columns to `url_enrichment_cache`. Feeds the cited-exemplar freshness benchmark. |
| `0041` | **Topic assignment cannibalization** — creates `topic_assignment_cannibalization` table with UNIQUE on `assignment_id`, FKs to `topic_assignments` (CASCADE), `topic_discoveries` (CASCADE), `companies` (CASCADE), `content_inventory` (SET NULL). Adds `ix_td_assignment_cannibalization_discovery` and `ix_td_assignment_cannibalization_company_level`. |

## Key Architectural Decisions

1. **Async-only**: `AsyncSession`, `async_sessionmaker`, `create_async_engine` (asyncpg driver)
2. **Thread-safe globals**: RLock double-checked locking on `_engine`, `_session_factory`
3. **pgvector for embeddings**: Native Postgres vector storage (1536-dim, HNSW indexes)
4. **JSONB flexibility**: Structural signals, metadata, evaluation results in JSONB
5. **String company_id in daily_tracker**: Not FK — allows standalone operation before auth
6. **Immutable audit_logs**: No `updated_at`, pure append-only
7. **Display ID system**: Company-scoped prefix + counter (e.g., "WE-001"); `display_id` is carried on every topic run and event for stable per-card identity from Planner → GA → CE → Content Studio.
8. **Composite foreign keys**: `(run_id, query_id)` references across gap analysis tables
9. **Partial unique indexes**: Handle nullable `product_id` in tracking snapshots
10. **Topic-level parallelism over slug-level locking**: `content_engine_topic_runs` replaces the old per-slug `pipeline_state.json` file. Scheduler state lives in dedicated columns (not `status`) so the status machine and the scheduler machine evolve independently. `SELECT FOR UPDATE SKIP LOCKED` on `claim_queued_runs_for_company` is the multi-worker safety primitive.
11. **Durable cannibalization evidence**: `topic_assignment_cannibalization` persists scores, reasons, matches and fanout-aware signals per assignment so planner-open work can be delta-recomputed without rebuilding the full universe.
12. **Async pool sized for concurrent TD-entry QA**: `pool_size=15` / `max_overflow=20` (was 5/10) — required for the parallel topic-run world and the Content Studio polling + SSE reconciliation traffic it generates.
