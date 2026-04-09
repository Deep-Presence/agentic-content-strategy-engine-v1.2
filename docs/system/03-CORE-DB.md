# Core Database Layer

> **Location:** `core/db/`
> **Owner:** Core
> **Dependencies:** SQLAlchemy 2.0, asyncpg, pgvector, Alembic
> **Dependents:** All services, repositories, API layer, pipeline persistence
> **Last Updated:** 2026-04-09

## Overview

The database module provides the complete data persistence layer using SQLAlchemy 2.0 with async support. It contains 25 ORM table models, 30 repository classes, 29 PostgreSQL enum types, and 37 Alembic migration files. The architecture uses lazy engine initialization, per-request unit-of-work sessions, and a generic CRUD base repository. pgvector extension provides native vector storage for 1536-dimensional OpenAI embeddings with HNSW indexes.

## Architecture

```
core/db/
├── engine.py          ← Lazy async engine + session factory (thread-safe)
├── base.py            ← DeclarativeBase + UUIDPKMixin + TimestampMixin
├── enums.py           ← 29 PostgreSQL ENUM types
├── dependencies.py    ← FastAPI DI: session lifecycle + repository factories
├── models/            ← 25 ORM models (one file per domain)
│   └── __init__.py    ← Registry import (loads all models for metadata)
├── repositories/      ← 30 repository classes
│   └── base.py        ← SQLAlchemyRepository[ModelT] generic CRUD
└── migrations/        ← 37 Alembic migration files
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
| `get_engine` | `() -> AsyncEngine` | Lazy-initialized async engine. Pool: size=5, overflow=10, pre-ping=True, recycle=3600s |
| `get_session_factory` | `() -> async_sessionmaker[AsyncSession]` | Lazy session factory. `expire_on_commit=False` |
| `reset_engine` | `async () -> None` | Dispose pool (testing cleanup) |

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

## ORM Models (25 Tables)

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

### Topic Discovery Domain (6 tables)

| Table | Key Purpose |
|-------|------------|
| `topic_discoveries` | Discovery run metadata |
| `taxonomy_trees` | Versioned taxonomy snapshots (JSON tree) |
| `subdomain_nodes` | Self-referencing hierarchy with priority scores |
| `topic_assignments` | Content opportunities in dimensionality matrix. Has `display_id` |
| `td_source_results` | Per-source S1 generation statistics |
| `td_persona_affinity` | Many-to-many persona↔subdomain scores |

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

`platform_result_cache`, `url_enrichment_cache`, `url_structural_signals` (45 signal columns)

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

## Repository Layer (30 Repositories)

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
| `GapAnalysisRepository` | `bulk_insert_query_gaps`, `get_gaps_by_run`, `update_gap`, `bulk_insert_exemplars` |
| `PipelineRepository` | `create_run`, `update_status`, `list_by_company`, `add_stage_log`, `get_latest_completed` |
| `TopicDiscoveryRepository` | `create_discovery`, `list_by_company`, `upsert_taxonomy`, `list_assignments`, `bulk_insert_assignments` |
| `ContentInventoryRepository` | `upsert_by_url`, `list_by_company`, `list_with_pagination`, `update_embedding` |
| `DailyTrackerRepository` | `create_prompt`, `list_prompts`, `create_run`, `create_response`, `list_responses_by_run` |
| `EmbeddingRepository` | `create_semantic_unit`, `list_by_company`, `create_query_embedding` |
| `SiteAuditRepository` | `create_audit`, `list_by_company`, `create_finding`, `list_findings` |
| `CmsRepository` | `get_connection_by_slug`, `create_publish_record`, `upsert_synced_post` |
| `AnalyticsRepository` | `create_connection`, `list_traffic_data`, `create_conversion_event` |

Plus 19 more: auth, cache, cost, invite, kb, persona, platform, platform_defaults, product, research_artifact, signal, task, tracking, vsg, audit_log, content_artifact, content_inventory_prompt, knowledge_docs.

## Migrations (37)

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

## Key Architectural Decisions

1. **Async-only**: `AsyncSession`, `async_sessionmaker`, `create_async_engine` (asyncpg driver)
2. **Thread-safe globals**: RLock double-checked locking on `_engine`, `_session_factory`
3. **pgvector for embeddings**: Native Postgres vector storage (1536-dim, HNSW indexes)
4. **JSONB flexibility**: Structural signals, metadata, evaluation results in JSONB
5. **String company_id in daily_tracker**: Not FK — allows standalone operation before auth
6. **Immutable audit_logs**: No `updated_at`, pure append-only
7. **Display ID system**: Company-scoped prefix + counter (e.g., "WE-001")
8. **Composite foreign keys**: `(run_id, query_id)` references across gap analysis tables
9. **Partial unique indexes**: Handle nullable `product_id` in tracking snapshots
