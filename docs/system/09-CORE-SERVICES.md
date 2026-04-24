# Core Services Layer

> **Location:** `core/services/`
> **Owner:** Core
> **Dependencies:** `core/db/repositories/`, `core/storage/`, `core/models/`, Redis
> **Dependents:** All API routers, `api/dependencies.py`
> **Last Updated:** 2026-04-24

## Overview

The services module contains 35 files (~10,200 lines) implementing the data access layer between API routers and backend storage. It follows a **Protocol -> JsonService -> DbService** three-layer pattern across 8 data domains. Protocols define async interfaces, JsonServices read from the filesystem (legacy), and DbServices read from PostgreSQL (production). The DI switch in `api/dependencies.py` selects the implementation at startup based on `DATABASE_URL` presence.

In addition to the 8 Protocol/Service triads, the module contains standalone orchestrator services (CMSService, ContentPerformanceService, ContentInventoryService) and the new `ContentEngineTopicRunService` — the durable state service for TD-entry Content Engine parallel execution.

## Architecture

```
+-------------------------------------------+
|           API Routers (async)             |
|    Depend on Protocol interfaces          |
+-------------------------------------------+
|         8 Protocol Definitions            |
|   Runtime-checkable, all methods async    |
+--------------------+----------------------+
| JsonService        |      DbService       |
| (filesystem)       |   (PostgreSQL + FS)   |
| Legacy             |   Production          |
| to_thread()        |   Hybrid metadata/    |
|                    |   content             |
+--------------------+----------------------+
         |                   |
    StorageBackend      Repositories
    (R2 / Local)       (SQLAlchemy)
         |
    +----+----+
    |         |
  Standalone  Durable State
  Services    Service
    |         |
  CMSService  ContentEngineTopicRunService
  ContentPerf   (scheduler state machine,
  ContentInv     startup reconciliation,
                 claim-resume pattern)
```

## File Structure (35 files)

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

### Helper & Utility Services (9 files)

| File | Class/Purpose | Lines |
|------|---------------|-------|
| `task_store.py` | `TaskStoreProtocol` -- task lifecycle, locks, semaphore, HITL | 117 |
| `db_task_store.py` | `DbTaskStore` -- PostgreSQL task store with per-company CE pool | ~900 |
| `gap_context_helper.py` | Gap context extraction for content briefs | 300 |
| `cms_service.py` | `CMSService` -- CMS orchestrator | 658+ |
| `cms_cache.py` | Redis cache for CMS data | 231 |
| `analytics_cache.py` | Redis cache for GA4 data | 222 |
| `content_performance_service.py` | `ContentPerformanceService` -- structural scoring + freshness | 537+ |
| `content_inventory_service.py` | `ContentInventoryService` -- content registry + embedding | 645+ |
| `content_engine_topic_runs.py` | `ContentEngineTopicRunService` -- durable TD-entry CE state | 898 |

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
# Properties
@property
def semaphore(self) -> asyncio.Semaphore

def pipeline_semaphore(
    self,
    task_id: str,
    *,
    pool: str = "default",
    company_slug: Optional[str] = None,
) -> AsyncContextManager

# CRUD
def create_task(pipeline, company_slug, product_slug=None, allow_parallel=False) -> PipelineTask
def get_task(task_id) -> PipelineTask
def update_task(task_id, **kwargs) -> PipelineTask
def list_tasks(pipeline=None, status=None, ...) -> List[PipelineTask]

# Slug Locks
def acquire_slug_lock(slug, task_id=None) -> None
def release_slug_lock(slug) -> None

# Task Handle Tracking
def register_task_handle(task_id, handle) -> None
def cancel_task_handle(task_id) -> bool
def remove_task_handle(task_id) -> None

# HITL Approval
async def wait_for_approval(task_id, timeout=86400) -> Dict[str, Any]
def submit_approval(task_id, decision, revision_note=None, stage=None,
                    approval_data=None, expected_nonce=None, delivery_mode="queue") -> None
def validate_approval_submission(task_id, *, expected_nonce=None) -> None
def record_approval_submission(task_id, *, decision, revision_note=None, stage=None) -> None

# Durability
async def ensure_created(task_id) -> None
async def flush_terminal(task_id) -> None
async def drain_pending() -> None
```

**`pipeline_semaphore` pool parameter:** The `pool` parameter enables per-company CE concurrency pools for TD-entry parallel execution. When `pool="ce_content"` and `company_slug` is provided, the semaphore is scoped to that company rather than sharing the global pipeline concurrency limit.

**File ref:** `task_store.py:1-117`

## Complex Service Deep-Dives

### `DbContentDataService` (596 lines)

The most complex service. Manages the Content Studio Kanban board.

**`get_briefs()` flow:**
1. Load GA-phase cards from Redis via `read_ga_phase_cards_async()` (topic assignments in gap analysis)
2. Query DB `content_pieces` by `effective_slug`
3. Load gap analysis context for sidebar enrichment
4. Dedup GA cards against DB pieces by `topic_assignment_id`
5. Prepend GA cards before DB brief cards
6. Self-heal: validate GA-phase cards against DB status, purge orphans

**GA-phase self-healing:** When `get_briefs()` reads GA-phase cards from Redis, it validates each card's `topic_assignment_id` against the DB `topic_assignments` table. If the assignment status is not in `_ACTIVE_ASSIGNMENT_STATUSES` (approved, in_gap_analysis, gap_analysis_complete, in_content_production), the Redis entry is purged. This prevents stale GA-phase cards from appearing on the Kanban board after a topic assignment is completed or cancelled.

**Topic-assignment metadata enrichment:** For DB content pieces with `topic_assignment_id` set, the service looks up the associated `TopicAssignmentModel` to enrich the brief list item with topic-level metadata (display_id, buyer_stage, intent_type, persona, priority_factors, cannibalization data).

**`get_brief_detail()` flow:**
1. Try `slug+brief_id` lookup, fallback to UUID
2. Read blueprint from DB JSONB (`evaluation_results` column) or StorageBackend
3. Extract evaluation results for `eval_history`

**File ref:** `db_content_data.py:1-80+`

### `DbGapDataService` (813 lines)

Richest data service with 10 methods. All SQL-backed except embedding projections.

**Signal definitions:** 23 structured signals (word_count, reading_level, has_faq_section, etc.) with display names and group categorization.

**`get_cluster_profiles()` and `get_territory_gaps()`:** These two endpoints bypass the DB and delegate to filesystem loading. No SQL, no repository, no DB tables. This is intentional tech debt documented in the Embedding Lab integration notes.

### `JsonSiteAuditDataService` (641 lines)

Most sophisticated caching with 3-layer fallback:
- **L1 (Redis):** 600s TTL, shared across workers
- **L2 (In-memory FIFO):** 10 entries, 600s TTL
- **L3 (StorageBackend):** File/R2 reads

Input validation: regex for slug format, strict UUID4 for audit_id.

---

## ContentEngineTopicRunService (898 lines -- NEW)

> **File:** `core/services/content_engine_topic_runs.py`
> **Tables:** `content_engine_batch_runs`, `content_engine_topic_runs`, `content_engine_topic_events`
> **Migrations:** 0038 (tables), 0039 (scheduler state columns)
> **Design doc:** `docs/TD_ENTRY_PARALLEL_EXECUTION_PLAN.md`

### Purpose

The `ContentEngineTopicRunService` is the durable state service for TD-entry Content Engine parallel execution. It owns the lifecycle of batch runs, per-topic execution state, and the scheduler state machine that enables topic-level concurrency with crash-safe recovery.

### Constructor

```python
class ContentEngineTopicRunService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
```

Single dependency: SQLAlchemy async session factory. All methods open their own sessions and commit.

### Dataclasses (5 DTOs)

#### `TopicRunSnapshot`

Lightweight DTO returned to API/router callers. Read-only view of a topic run.

```python
@dataclass(slots=True)
class TopicRunSnapshot:
    topic_run_id: str
    batch_run_id: str
    topic_assignment_id: str
    display_id: str
    topic_text: str
    brief_id: str
    ga_run_id: str | None
    pipeline_task_id: str | None
    status: str
    stage: str
    seq: int
    scheduler_state: str
    content_piece_id: str | None
    created_at: str
    updated_at: str
```

#### `TopicRunEventSnapshot`

Append-only execution event DTO for one durable topic run.

```python
@dataclass(slots=True)
class TopicRunEventSnapshot:
    topic_event_id: str
    topic_run_id: str
    topic_assignment_id: str
    display_id: str
    brief_id: str
    event_type: str
    stage: str
    status: str
    seq: int
    content_piece_id: str | None
    pipeline_task_id: str | None
    payload_json: dict
    created_at: str
```

The `payload_json` is enriched with contextual fields from the parent `ContentEngineTopicRunModel`: `brief_id`, `display_id`, `topic_text`, `entry_mode`, `effective_slug`, `batch_run_id`, `content_piece_id`, `buyer_stage`, `intent_type`.

#### `QueuedTopicRunClaimSnapshot`

Dispatchable claim for the Phase 3 CE dispatcher.

```python
@dataclass(slots=True)
class QueuedTopicRunClaimSnapshot:
    topic_run_id: str
    batch_run_id: str
    topic_assignment_id: str
    display_id: str
    topic_text: str
    brief_id: str
    ga_run_id: str | None
    pipeline_task_id: str | None
    effective_slug: str
    company_slug: str
    scheduler_state: str
    launch_context: dict[str, Any]
    continuation_payload: dict[str, Any]
```

**`launch_context`:** Extracted from `metadata_json["launch_context"]` -- carries the original dispatch configuration (GA run settings, persona filters, etc.).

**`continuation_payload`:** For `resume_queued` claims, contains the full HITL continuation data: `resume_stage`, `blueprint`, `approval_data`, etc.

#### `StartupSchedulerRecoverySnapshot`

Result of `reconcile_startup_scheduler()`.

```python
@dataclass(slots=True)
class StartupSchedulerRecoverySnapshot:
    companies_to_dispatch: list[str]
    queued_ready_count: int = 0
    requeued_count: int = 0
    waiting_human_restored_count: int = 0
    stale_task_ids_cleared_count: int = 0
```

### Exceptions (2)

```python
class TopicRunResumeNotFoundError(ValueError):
    """No durable waiting-human topic run matched the requested task."""

class TopicRunResumeConflictError(ValueError):
    """A durable topic run exists, but it cannot accept another approval resume."""
```

Raised by `queue_topic_run_resume()` when:
- No topic run found for the given `pipeline_task_id` (`NotFound`)
- Topic run is already in `resume_queued` state (`Conflict`)
- Topic run is not in `waiting_human` state (`Conflict`)

### Public Methods

#### `create_td_batch()`

```python
async def create_td_batch(
    self,
    *,
    company_slug: str,
    effective_slug: str,
    topic_assignment_ids: Sequence[str],
    pipeline_task_id: str | None,
    product_slug: str | None = None,
    source: str = "topic_discovery_pipeline_b",
    source_mode: str = "td_entry_mode",
    entry_mode: str = "topic_discovery",
    initial_status: str = "gap_analysis_pending",
    initial_stage: str = "gap_analysis_pending",
    ga_run_id: str | None = None,
    metadata_json: dict | None = None,
) -> tuple[ContentEngineBatchRunModel, list[TopicRunSnapshot]]:
```

Creates a batch run and N topic runs for the given topic assignments. Copies `display_id` from `TopicAssignmentModel` at creation time. Sets `brief_id = display_id` initially. Creates `topic_run_created` events for each run.

**Identity enforcement:** Each topic run carries both `topic_assignment_id` (FK) and `display_id` (human-readable label) from the source `TopicAssignmentModel`. The `display_id` is immutable after creation -- it represents the user-facing identity throughout the lifecycle.

**Ordering:** Assignments are ordered by the input `topic_assignment_ids` sequence, preserving the user's selection order.

**File ref:** `content_engine_topic_runs.py:126-227`

#### `advance_topic_runs()`

```python
async def advance_topic_runs(
    self,
    *,
    effective_slug: str,
    topic_assignment_ids: Sequence[str],
    status: str,
    stage: str,
    ga_run_id: str | None = None,
    match_ga_run_id: str | None = None,
    match_pipeline_task_id: str | None = None,
    pipeline_task_id: Any = _UNSET,
    content_piece_ids: dict[str, str] | None = None,
    last_error: str | None = None,
    event_type: str = "topic_run_changed",
    payload_json: dict | None = None,
    metadata_updates: dict | None = None,
    scheduler_state: str | None = None,
    clear_claim_token: bool = False,
    queued_at: Any = _UNSET,
    claimed_at: Any = _UNSET,
    waiting_for_human_at: Any = _UNSET,
    continuation_payload_json: Any = _UNSET,
) -> list[TopicRunSnapshot]:
```

The core state advancement method. Advances topic runs identified by `topic_assignment_ids`, scoped by `effective_slug` and optionally by `match_ga_run_id` or `match_pipeline_task_id`.

**Key behaviors:**
- Increments `status_seq` monotonically (optimistic concurrency)
- Sets timestamps: `started_at`, `completed_at`, `failed_at` based on status
- Merges `metadata_updates` into existing `metadata_json` (shallow merge)
- Appends event to `content_engine_topic_events`
- Supports `_UNSET` sentinel for optional fields (distinguishes "not provided" from "set to None")

**Scoping logic:** When `match_pipeline_task_id` is provided, only runs with that `pipeline_task_id` are advanced. When `match_ga_run_id` is provided, only runs with that `ga_run_id` are advanced. This prevents cross-run state corruption when multiple batches coexist.

**File ref:** `content_engine_topic_runs.py:229-328`

#### `advance_topic_runs_by_brief_ids()`

```python
async def advance_topic_runs_by_brief_ids(
    self,
    *,
    effective_slug: str,
    brief_ids: Sequence[str],
    status: str,
    stage: str,
    pipeline_task_id: Any = _UNSET,
    match_pipeline_task_id: str | None = None,
    # ... same optional params as advance_topic_runs
) -> list[TopicRunSnapshot]:
```

Same as `advance_topic_runs()` but looks up topic runs by `brief_id` instead of `topic_assignment_id`. Used by `_sync_td_topic_runs_for_briefs()` in `state_helpers.py` to propagate CE pipeline state writes into durable topic runs.

**File ref:** `content_engine_topic_runs.py:330-412`

#### `list_topic_runs_by_assignment_ids()`

```python
async def list_topic_runs_by_assignment_ids(
    self,
    *,
    effective_slug: str,
    topic_assignment_ids: Sequence[str],
    ga_run_id: str | None = None,
) -> list[TopicRunSnapshot]:
```

Read-only query returning topic run snapshots for the given assignment IDs. Returns at most one run per assignment (latest by creation order). Used by the orchestrator to check pre-existing runs before creating new ones.

**File ref:** `content_engine_topic_runs.py:414-438`

#### `claim_queued_topic_runs()`

```python
async def claim_queued_topic_runs(
    self,
    *,
    company_slug: str,
    limit: int,
) -> list[QueuedTopicRunClaimSnapshot]:
```

Claims up to `limit` queued (or `resume_queued`) topic runs for a company. Uses a unique `claim_token` (UUID4) to prevent concurrent dispatchers from claiming the same runs. The claim query uses `SELECT FOR UPDATE` semantics via the repository.

**Claim includes `resume_queued` runs:** Runs waiting for re-dispatch after HITL approval are included in the claim pool alongside fresh `queued` runs.

**Returns:** `QueuedTopicRunClaimSnapshot` with the full context needed to dispatch: `launch_context`, `continuation_payload`, `company_slug`, `effective_slug`.

**File ref:** `content_engine_topic_runs.py:440-464`

#### `mark_claimed_topic_runs_dispatched()`

```python
async def mark_claimed_topic_runs_dispatched(
    self,
    *,
    topic_run_task_ids: dict[str, str],  # {topic_run_id: pipeline_task_id}
) -> list[TopicRunSnapshot]:
```

After the dispatcher creates pipeline tasks for claimed runs, this method transitions them to `scheduler_state = "running"` and records the `pipeline_task_id`. Clears the `claim_token`.

**Resume detection:** If the run was previously `claimed` with a `continuation_payload_json`, the event note is "Approval continuation claimed for execution" instead of "Queued topic claimed for execution".

**File ref:** `content_engine_topic_runs.py:466-515`

#### `release_topic_run_claims()`

```python
async def release_topic_run_claims(
    self,
    *,
    topic_run_ids: Sequence[str],
) -> None:
```

Releases claimed runs back to the queue (either `queued` or `resume_queued` depending on whether `continuation_payload_json` is present). Called when a dispatcher fails to create pipeline tasks for claimed runs.

**File ref:** `content_engine_topic_runs.py:517-535`

#### `queue_topic_runs_for_dispatch()`

```python
async def queue_topic_runs_for_dispatch(
    self,
    *,
    effective_slug: str,
    topic_assignment_ids: Sequence[str],
    pipeline_task_id: str | None = None,
    ga_run_id: str | None = None,
    match_ga_run_id: str | None = None,
    launch_context: dict[str, Any] | None = None,
) -> list[TopicRunSnapshot]:
```

Transitions topic runs to `content_queued` status with `scheduler_state = "queued"`. Stores `launch_context` in `metadata_json` for later retrieval by the dispatcher. Clears `claim_token`, `claimed_at`, `waiting_for_human_at`. Sets `queued_at` to now. Resets `continuation_payload_json` to empty dict.

**File ref:** `content_engine_topic_runs.py:537-568`

#### `mark_topic_run_waiting_human()`

```python
async def mark_topic_run_waiting_human(
    self,
    *,
    effective_slug: str,
    pipeline_task_id: str,
    status: str,
    stage: str,
    continuation_payload: dict[str, Any],
    payload_json: dict | None = None,
) -> list[TopicRunSnapshot]:
```

Called when the CE pipeline raises `ApprovalPauseRequested`. Transitions the topic run to `scheduler_state = "waiting_human"` and stores the full continuation payload (blueprint, final content, history, etc.) in `continuation_payload_json`.

**File ref:** `content_engine_topic_runs.py:570-594`

#### `queue_topic_run_resume()`

```python
async def queue_topic_run_resume(
    self,
    *,
    effective_slug: str,
    pipeline_task_id: str,
    approval_data: dict[str, Any],
) -> TopicRunSnapshot:
```

Called when a user submits an HITL approval for a TD-entry topic run. Merges `approval_data` and `resumed_at` timestamp into the existing `continuation_payload_json` and transitions `scheduler_state` from `waiting_human` to `resume_queued`.

**Validation:**
- `TopicRunResumeNotFoundError` if no run found for `pipeline_task_id`
- `TopicRunResumeConflictError` if already `resume_queued` (duplicate submission)
- `TopicRunResumeConflictError` if not `waiting_human` (wrong state)

**File ref:** `content_engine_topic_runs.py:596-630`

#### `reconcile_startup_scheduler()`

```python
async def reconcile_startup_scheduler(
    self,
    *,
    task_by_id: dict[str, Any],  # {task_id: PipelineTask}
) -> StartupSchedulerRecoverySnapshot:
```

Called once at server startup. Scans all non-terminal topic runs and recovers stranded entries based on their scheduler state and the status of their associated pipeline tasks.

**Recovery logic (per run):**

| Scheduler State | Task Status | Recovery Action |
|----------------|-------------|-----------------|
| `waiting_human` | Any | Skip (user action pending) |
| `queued` / `resume_queued` | Any | Ready for dispatch (clear stale task IDs) |
| `claimed` / `running` | RUNNING or PENDING_APPROVAL | Skip (still active) |
| `claimed` / `running` | FAILED_RESTART + has HITL payload + continuation | Restore to `waiting_human` |
| `claimed` / `running` | Dead/missing + has continuation | Requeue as `resume_queued` |
| `claimed` / `running` | Dead/missing + no continuation | Requeue as `queued` from scratch |

**Returns:** `StartupSchedulerRecoverySnapshot` with:
- `companies_to_dispatch`: sorted list of company slugs that have queued runs
- `queued_ready_count`: runs ready for immediate dispatch
- `requeued_count`: runs re-queued from scratch after crash
- `waiting_human_restored_count`: runs restored to waiting state
- `stale_task_ids_cleared_count`: pipeline_task_ids cleared for missing tasks

**File ref:** `content_engine_topic_runs.py:632-778`

#### `list_topic_runs()`

```python
async def list_topic_runs(
    self,
    *,
    effective_slug: str,
    limit: int = 200,
) -> list[TopicRunSnapshot]:
```

Lists topic runs for an effective slug, ordered by creation time. Used by the Content Studio board hydration endpoint.

**File ref:** `content_engine_topic_runs.py:780-789`

#### `list_topic_run_events()`

```python
async def list_topic_run_events(
    self,
    *,
    effective_slug: str,
    topic_run_id: str,
    limit: int = 200,
) -> tuple[TopicRunSnapshot | None, list[TopicRunEventSnapshot]]:
```

Returns the topic run snapshot and its ordered event log. Used by the detail view timeline.

**File ref:** `content_engine_topic_runs.py:791-810`

### Internal Methods

#### `_order_assignments()`

Orders `TopicAssignmentModel` instances to match the input `ordered_ids` sequence. Preserves user's selection order.

#### `_to_snapshot()`, `_to_event_snapshot()`, `_to_claim_snapshot()`

Static methods that convert ORM models to DTOs. The `_to_event_snapshot()` enriches `payload_json` with contextual fields from the parent run (display_id, topic_text, entry_mode, effective_slug, batch_run_id, buyer_stage, intent_type).

### Scheduler State Machine (Cross-Reference)

The scheduler state machine is documented in detail in `docs/system/15-PIPELINE-CONTENT-ENGINE.md` under "Parallelism & Scalability Design". The service is the single owner of state transitions -- no other code directly mutates `scheduler_state`.

```
idle --> queued --> claimed --> running --> completed
                      |                      |
                      v                      v
                  (released)          waiting_human
                      |                      |
                      v                      v
                   queued              resume_queued
                                            |
                                            v
                                        claimed (re-enter)
```

---

## Utility Services

### `CMSService` (658+ lines)

Standalone orchestrator (not Protocol-based). Coordinates:
- CMS adapter (WordPress API calls)
- DB repositories (connections, publish records, synced posts)
- Fernet encryption for credentials
- StorageBackend for content reads

**Key methods:**

| Method | Purpose |
|--------|---------|
| `connect()` | Validate credentials, store encrypted connection |
| `sync_posts()` | Pull existing CMS posts into local index |
| `publish_content()` | Push content piece to CMS with SEO metadata |
| `refresh_content()` | Update existing CMS post with new content |
| `list_stale_posts()` | Find posts older than `STALE_THRESHOLD_DAYS` (30 days) |

**SEO metadata:** The `publish_content()` method generates SEO metadata (slug, meta_title, meta_description, canonical_url, schema_markup, tags) and passes it to the CMS adapter.

**Auto-sync on publish:** After successful CMS publish, the service can trigger:
1. Content inventory registration (`register_published_content()`)
2. Auto-prompt generation via `ContentToPromptOrchestrator`
3. Cache invalidation (`cache:cms:*`)

**File ref:** `cms_service.py:1-80+`

### `ContentPerformanceService` (537+ lines)

DB-only. Computes structural quality scores (0-100) from 20+ signals.

**Structural Score Formula:**

| Category | Weight | Signals |
|---------|--------|---------|
| Text Composition | 30 pts | word_count, sentence_count, paragraph_count, avg_paragraph_length, reading_level, self_contained_ratio |
| Structural Elements | 25 pts | h2_count, h3_count, list_block_count, table_count, ordered_list_count, code_block_count |
| Content Patterns | 30 pts | has_faq_section, has_definition_opening, has_key_takeaways, has_comparison_table, has_step_by_step, has_research_refs, has_expert_quotes |
| Factual Density | 15 pts | data_point_count, citation_density, named_entity_density |

**Numeric signal scoring:** `score = min(1.0, value / benchmark)` -- e.g., word_count benchmark is 1800, so a 2000-word article scores 1.0.

**Boolean signal scoring:** 1.0 if present, 0.0 if absent. Cited articles tend to have FAQ sections, key takeaways, comparison tables, etc.

**Freshness benchmark:** Computes freshness relative to cited exemplars from gap analysis. Pages older than exemplar averages are flagged as stale.

**Readiness classification:** Combines structural score + traffic velocity to classify pages into lifecycle stages: growing, peaking, stable, stale, declining.

**File ref:** `content_performance_service.py:1-80+`

### `ContentInventoryService` (645+ lines)

DB-only. Ingests pages from site audit into `content_inventory` table. Computes embeddings for similarity search and cannibalization detection.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `ingest_crawled_pages()` | Bulk insert/update pages from site audit |
| `compute_embeddings()` | Embed page text via OpenRouter, store as pgvector |
| `check_cannibalization()` | Single-query pgvector similarity search |
| `check_cannibalization_batch()` | Batch pgvector similarity search (used by TD cannibalization) |
| `enrich_thin_pages()` | Fetch content via trafilatura for pages with <100 chars content_preview |
| `register_published_content()` | Register a newly published page in inventory |
| `get_existing_coverage()` | Find inventory pages covering a given topic |

**Embedding text formula:**
```
{title} | {h1_text} | {meta_description} | {content_preview[:300]}
```

**enrich_thin_pages():** Fetches page content via trafilatura for pages that have < 100 characters in `content_preview`. After enrichment, recomputes structural signals and embeddings. This enables cannibalization detection to work even for pages whose initial crawl only captured metadata.

**register_published_content():** Called after CMS publish. Creates or updates the `content_inventory` entry for the published URL, computes embeddings, and triggers delta cannibalization recomputation via `resolve_impacted_assignment_scope_for_inventory_changes()`.

**File ref:** `content_inventory_service.py:1-80+`

---

## DbContentDataService: GA-Phase Self-Healing

The GA-phase self-healing logic in `get_briefs()` validates Redis GA-phase cards against the DB:

1. For each GA-phase card (status in `_GA_PHASES`), look up the `topic_assignment_id` in `topic_assignments`
2. If the assignment status is not in `_ACTIVE_ASSIGNMENT_STATUSES`, purge the Redis entry
3. If the assignment has been completed and has a `content_pieces` record, the GA card is redundant

**Active assignment statuses:** `approved`, `in_gap_analysis`, `gap_analysis_complete`, `in_content_production`

This prevents:
- Stale GA-phase cards from appearing after a topic assignment completes
- Orphaned Redis entries from crashed pipelines
- Cards stuck in `briefing` status when the pipeline failed without cleanup

**File ref:** `db_content_data.py:60-62`

## DbContentDataService: Topic-Assignment Metadata Enrichment

When DB content pieces have `topic_assignment_id` set, `get_briefs()` loads the associated `TopicAssignmentModel` to enrich the list item with:

- `display_id` (universal card identity)
- `buyer_stage`, `intent_type` (from assignment dimensions)
- `persona_name`, `persona_id`, `persona_affinity` (from persona scoring)
- `priority_score`, `priority_factors` (from CPS/priority ranking)
- `content_format`, `estimated_word_count` (from expansion metadata)
- `cannibalization_risk_level`, `cannibalization_risk_score` (from cannibalization assessment)
- `target_keywords`, `content_angle`, `gap_context` (from assignment metadata)

This enrichment enables the Content Studio to display topic-level context without requiring separate API calls per card.

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

### 5. _UNSET Sentinel (ContentEngineTopicRunService)
Distinguishes "caller did not provide this field" from "caller wants to set it to None":
```python
_UNSET = object()

if pipeline_task_id is not _UNSET:
    run.pipeline_task_id = pipeline_task_id
```

### 6. Snapshot DTO Pattern (ContentEngineTopicRunService)
ORM models are never exposed to callers. Static `_to_snapshot()` methods convert to frozen `@dataclass(slots=True)` DTOs that are safe to serialize and cache.

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
| `/api/v1/content/v13/from-topics/*` | ContentEngineTopicRunService | TD-Entry CE |
| `/api/v1/companies/{slug}/content/topic-runs/*` | ContentEngineTopicRunService | Content Studio board |

## Tech Debt

1. **`DbGapDataService.get_cluster_profiles()` and `get_territory_gaps()` bypass DB:** These methods delegate to filesystem loading with no SQL, no repository, no DB tables. Documented in Embedding Lab integration notes.

2. **JsonTopicDiscoveryDataService deprecated:** Marked as deprecated but still importable. All production uses should go through DbTopicDiscoveryDataService.

3. **`ContentEngineTopicRunService` has no Protocol:** Unlike the 8 data services, the topic run service is used directly without a Protocol interface. Adding a protocol would enable testing with mock implementations.

4. **`_compute_query_overlap_signals` imported from repository:** This utility function is defined in `ContentInventoryPromptRepository` but used by `cannibalization_service.py`. Should be extracted to a shared module.

5. **GA-phase self-healing runs on every `get_briefs()` call:** The validation queries add latency to every Kanban board load. Could be moved to a background periodic cleanup.

6. **Topic-assignment metadata enrichment requires N+1 queries:** Each content piece with a `topic_assignment_id` triggers a separate DB lookup. Should be batch-loaded in a single query.
