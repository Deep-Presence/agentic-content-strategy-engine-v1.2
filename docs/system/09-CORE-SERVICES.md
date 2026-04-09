# Core Services Layer

> **Location:** `core/services/`
> **Owner:** Core
> **Dependencies:** `core/db/repositories/`, `core/storage/`, `core/models/`, Redis
> **Dependents:** All API routers, `api/dependencies.py`
> **Last Updated:** 2026-04-09

## Overview

The services module contains 33 files (~8,500 lines) implementing the data access layer between API routers and backend storage. It follows a **Protocol -> JsonService -> DbService** three-layer pattern across 8 data domains. Protocols define async interfaces, JsonServices read from the filesystem (legacy), and DbServices read from PostgreSQL (production). The DI switch in `api/dependencies.py` selects the implementation at startup based on `DATABASE_URL` presence.

## Architecture

```
┌─────────────────────────────────────────┐
│           API Routers (async)           │
│    Depend on Protocol interfaces        │
├─────────────────────────────────────────┤
│         8 Protocol Definitions          │
│   Runtime-checkable, all methods async  │
├──────────────┬──────────────────────────┤
│ JsonService  │      DbService           │
│ (filesystem) │   (PostgreSQL + FS)      │
│ Legacy       │   Production             │
│ to_thread()  │   Hybrid metadata/content│
└──────────────┴──────────────────────────┘
         │                 │
    StorageBackend    Repositories
    (R2 / Local)     (SQLAlchemy)
```

## File Structure (33 files)

### Protocol Definitions (8 files)

| File | Protocol | Methods |
|------|----------|---------|
| `brand_data.py` | `BrandDataServiceProtocol` | `get_research_artifacts`, `get_run_history` |
| `content_data.py` | `ContentDataServiceProtocol` | `get_briefs`, `get_brief_detail`, `get_brief_stage_content`, `add_brief` |
| `gap_data.py` | `GapDataServiceProtocol` | `get_summary`, `get_queries`, `get_clusters`, `get_signals`, `get_platforms`, `get_heatmap`, `get_embedding_projection`, `get_spa_trend`, `get_cluster_profiles`, `get_territory_gaps` |
| `kb_data.py` | `KBDataServiceProtocol` | `get_summary`, `get_doc`, `get_synthesis`, `get_health`, `get_staleness_report` |
| `persona_data.py` | `PersonaDataServiceProtocol` | `list_personas`, `get_persona`, `get_summary`, `check_staleness` |
| `site_audit_data.py` | `SiteAuditDataServiceProtocol` | `get_audit_summary`, `get_audit_detail`, `list_audits`, `get_findings`, `get_page_results`, `audit_exists`, `get_latest_audit_id` |
| `topic_discovery_data.py` | `TopicDiscoveryDataServiceProtocol` | `get_discovery_summary`, `get_taxonomy`, `get_matrix`, `list_assignments`, `get_scored_subdomains`, `get_persona_affinity`, `update_assignment_status`, `create_assignment` |
| `vsg_data.py` | `VSGDataServiceProtocol` | `get_summary`, `get_guide`, `list_authors`, `get_author_research` |

### JsonService Implementations (8 files)

All JSON services wrap synchronous filesystem operations with `asyncio.to_thread()`.

| File | Class | Data Source |
|------|-------|-------------|
| `json_brand_data.py` | `JsonBrandDataService` | Filesystem + TaskStore |
| `json_content_data.py` | `JsonContentDataService` | StorageBackend |
| `json_gap_data.py` | `JsonGapDataService` | StorageBackend + TaskStore |
| `json_kb_data.py` | `JsonKBDataService` | Filesystem via KBStorage |
| `json_persona_data.py` | `JsonPersonaDataService` | Filesystem via PersonaStorage |
| `json_site_audit_data.py` | `JsonSiteAuditDataService` | StorageBackend + 3-layer cache |
| `json_topic_discovery_data.py` | `JsonTopicDiscoveryDataService` | Filesystem (**deprecated**) |
| `json_vsg_data.py` | `JsonVSGDataService` | Filesystem via VoiceStyleGuideStorage |

### DbService Implementations (8 files)

All DB services read metadata from PostgreSQL, content from StorageBackend. Hybrid pattern.

| File | Class | Lines | Repositories |
|------|-------|-------|-------------|
| `db_brand_data.py` | `DbBrandDataService` | 194 | PipelineRepository |
| `db_content_data.py` | `DbContentDataService` | 596 | ContentRepository, PipelineRepository, ContentArtifactRepository |
| `db_gap_data.py` | `DbGapDataService` | 813 | GapAnalysisRepository, PipelineRepository, SignalRepository, PlatformRepository |
| `db_kb_data.py` | `DbKBDataService` | 155 | KBRunRepository, KBDocumentRepository, KBSynthesisRepository |
| `db_persona_data.py` | `DbPersonaDataService` | 145 | PersonaRunRepository, PersonaProfileRepository |
| `db_site_audit_data.py` | `DbSiteAuditDataService` | 498 | SiteAuditRepository, CompanyRepository |
| `db_topic_discovery_data.py` | `DbTopicDiscoveryDataService` | 503 | TopicDiscoveryRepository, TaxonomyTreeRepository, TopicAssignmentRepository |
| `db_vsg_data.py` | `DbVSGDataService` | 160 | VSGRunRepository, VSGAuthorRepository, VSGGuideRepository |

### Helper & Utility Services (7 files)

| File | Class/Purpose | Lines |
|------|---------------|-------|
| `task_store.py` | `TaskStoreProtocol` — task lifecycle, locks, semaphore, HITL | 93 |
| `gap_context_helper.py` | Gap context extraction for content briefs | 300 |
| `cms_service.py` | `CMSService` — CMS orchestrator | 658 |
| `cms_cache.py` | Redis cache for CMS data | 231 |
| `analytics_cache.py` | Redis cache for GA4 data | 222 |
| `content_performance_service.py` | `ContentPerformanceService` — structural scoring | 537 |
| `content_inventory_service.py` | `ContentInventoryService` — content registry | 645 |

## Key Protocols in Detail

### `GapDataServiceProtocol` (most complex, 10 methods)

```python
async def get_summary(effective_slug, *, ga_run_id=None) -> GapSummaryResponse
async def get_queries(effective_slug, *, cluster=None, classification=None,
                      search=None, sort_by="gap_score", sort_dir="desc",
                      page=1, page_size=15) -> QueryListResponse
async def get_clusters(effective_slug) -> ClusterListResponse
async def get_signals(effective_slug) -> SignalAveragesResponse
async def get_platforms(effective_slug) -> PlatformListResponse
async def get_heatmap(effective_slug) -> HeatmapResponse
async def get_embedding_projection(effective_slug, method="umap") -> EmbeddingProjectionResponse
async def get_spa_trend(effective_slug) -> SPATrendResponse
async def get_cluster_profiles(effective_slug) -> ClusterProfileListResponse
async def get_territory_gaps(effective_slug) -> TerritoryGapsResponse
```

### `ContentDataServiceProtocol` (critical path, Kanban board)

```python
async def get_briefs(effective_slug) -> ContentBriefListResponse
async def get_brief_detail(effective_slug, brief_id) -> ContentBriefDetailResponse
async def get_brief_stage_content(effective_slug, brief_id, stage) -> StageContentResponse
async def add_brief(effective_slug, title, cluster="", description="",
                    source="manual", gap_query_id="") -> ContentBriefListItem
```

### `TaskStoreProtocol` (infrastructure)

```python
# CRUD
create_task(pipeline, company_slug, product_slug=None, allow_parallel=False) -> PipelineTask
get_task(task_id) -> PipelineTask
update_task(task_id, **kwargs) -> PipelineTask
list_tasks(pipeline=None, status=None, ...) -> List[PipelineTask]

# Concurrency
pipeline_semaphore(task_id) -> AsyncContextManager
acquire_slug_lock(slug, task_id=None) -> None
release_slug_lock(slug) -> None

# HITL
wait_for_approval(task_id, timeout=86400) -> Dict
submit_approval(task_id, decision, ...) -> None

# Durability
ensure_created(task_id) -> None
flush_terminal(task_id) -> None
drain_pending() -> None
```

## Complex Service Deep-Dives

### `DbContentDataService` (596 lines)

The most complex service. Manages the Content Studio Kanban board.

**`get_briefs()` flow:**
1. Load GA-phase cards from Redis (topic assignments in gap analysis)
2. Query DB content_pieces by effective_slug
3. Load gap analysis context for sidebar enrichment
4. Dedup GA cards against DB pieces by topic_assignment_id
5. Prepend GA cards before DB brief cards
6. Self-heal: validate GA-phase cards against DB status, purge orphans

**`get_brief_detail()` flow:**
1. Try slug+brief_id lookup, fallback to UUID
2. Read blueprint from DB JSONB or StorageBackend
3. Extract evaluation results for eval_history

### `DbGapDataService` (813 lines)

Richest data service with 10 methods. All SQL-backed except embedding projections.

**Signal definitions:** 23 structured signals (word_count, reading_level, has_faq_section, etc.) with display names and group categorization.

### `JsonSiteAuditDataService` (641 lines)

Most sophisticated caching with 3-layer fallback:
- **L1 (Redis):** 600s TTL, shared across workers
- **L2 (In-memory FIFO):** 10 entries, 600s TTL
- **L3 (StorageBackend):** File/R2 reads

Input validation: regex for slug format, strict UUID4 for audit_id.

## Utility Services

### `CMSService` (658 lines)

Standalone orchestrator (not Protocol-based). Coordinates:
- CMS adapter (WordPress API calls)
- DB repositories (connections, publish records, synced posts)
- Fernet encryption for credentials
- StorageBackend for content reads

### `ContentPerformanceService` (537 lines)

DB-only. Computes structural quality scores (0-100) from 20+ signals:
- Text composition (30%): word_count, reading_level, sentence_count
- Structural elements (25%): headers, lists, tables
- Content patterns (30%): FAQ, key takeaways, comparison tables
- Factual density (15%): data points, citations, named entities

### `ContentInventoryService` (645 lines)

DB-only. Ingests pages from site audit into content_inventory table. Computes embeddings for similarity search and cannibalization detection.

## Cache Layer

### `analytics_cache.py` TTLs

| Cache | TTL | Key Pattern |
|-------|-----|-------------|
| GA4 Connection | 30 min | `cache:ga4:conn:{slug}:{tenant}` |
| GA4 Properties | 1 hour | `cache:ga4:props:{slug}:{tenant}` |
| GA4 Perf Table | 5 min | `cache:ga4:perf:*` |
| GA4 Velocity | 10 min | `cache:ga4:velocity:*` |

### `cms_cache.py` TTLs

| Cache | TTL | Key Pattern |
|-------|-----|-------------|
| Categories | 1 hour | `cache:cms:cats:{url}` |
| Connection | 30 min | `cache:cms:conn:{slug}:{tenant}` |
| Stale Posts | 30 min | `cache:cms:stale:{slug}` |
| Synced Posts | 10 min | `cache:cms:posts:{slug}:*` |

## Design Patterns

### 1. asyncio.to_thread() Wrapper
All JsonServices wrap sync I/O:
```python
async def get_summary(self, slug):
    return await asyncio.to_thread(sync_function, self._storage, slug)
```

### 2. Hybrid DB/Filesystem (DbServices)
Metadata from DB, content from StorageBackend via `storage_key`:
```python
doc = await self._kb_doc_repo.get_by_type(run_id, doc_type)
content = await asyncio.to_thread(self._backend.read, doc.storage_key)
```

### 3. Per-Record Fallback (DbSiteAuditDataService)
DB-first, filesystem fallback per individual audit:
```python
if audit and audit.overall_score is not None:
    return _from_db(audit)  # Enriched DB record
return await self._fs_method(slug, audit_id)  # Legacy fallback
```

### 4. Self-Healing (DbContentDataService)
GA-phase cards validated against DB status; orphaned Redis entries purged automatically.

## Integration Map

| Route | Service | Pipeline |
|-------|---------|----------|
| `/api/v1/gap-data/*` | GapDataService | Gap Analysis |
| `/api/v1/content-data/*` | ContentDataService | Content Engine |
| `/api/v1/brand-data/*` | BrandDataService | KB + VSG + AP |
| `/api/v1/knowledge-base/data/*` | KBDataService | Knowledge Base |
| `/api/v1/audience-persona/data/*` | PersonaDataService | Audience Persona |
| `/api/v1/voice-style-guide/data/*` | VSGDataService | Voice Style Guide |
| `/api/v1/site-audit/data/*` | SiteAuditDataService | Site Audit |
| `/api/v1/topic-discovery/data/*` | TopicDiscoveryDataService | Topic Discovery |
| `/api/v1/content-performance/*` | ContentPerformanceService | Content + GA4 |
| `/api/v1/cms/*` | CMSService | CMS Integration |
