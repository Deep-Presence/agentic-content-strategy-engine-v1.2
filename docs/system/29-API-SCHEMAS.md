# API Schemas

> **Location:** `api/schemas/`
> **Owner:** API
> **Dependencies:** Pydantic v2
> **Dependents:** All API routers
> **Last Updated:** 2026-04-15

## Overview

21 schema files defining request/response models for all API endpoints. Schemas are Pydantic v2 BaseModel classes that validate input and shape output. They mirror but are separate from `core/models/` — API schemas are the external contract, core models are the internal contract. All fields carry defaults per project constraint (backward compatibility).

## File Inventory

| File | Key Models | Purpose |
|------|-----------|---------|
| `common.py` | `PipelineRunResponse`, `TaskResponse`, `ErrorResponse` | Shared across pipelines |
| `analytics.py` | `AuthorizeResponse`, `ConnectionResponse`, `SyncResponse`, `DisconnectResponse` | GA4 |
| `cms.py` | `CMSConnectRequest`, `CMSPublishRequest`, `CMSPublishResponse`, `CMSCategoryItem` | CMS |
| `content_data.py` | `ContentBriefListResponse`, `ContentBriefDetailResponse`, `ContentPublishMetadata`, `SavePublishMetadataRequest` | Content Studio data |
| `content_performance.py` | `ContentPerformanceTableResponse`, `ContentPerformanceReadinessResponse`, `FreshnessAssessment`, `SimilarContentResponse` | Performance metrics |
| `content_v13.py` | `ContentStartRequestV13`, `TopicContentProductionRequest`, `TopicRunSummaryV13`, `TopicRunEventV13`, `PipelineRunResponseV13` | Content Engine v1.3 |
| `topic_discovery.py` | `TaxonomyApprovalRequest`, `MatrixApprovalRequest`, `ScoredSubdomainsResponse` | TD pipeline |

## `content_v13.py` — TD-Entry Parallel Contract

### `ContentStartRequestV13`

| Field | Type | Default | Notes |
|---|---|---|---|
| `company_name` | `str` | — | Derives `company_slug` |
| `domain` | `str` | — | |
| `entry_mode` | `Literal["autonomous","manual"]` | `"autonomous"` | |
| `max_topics` | `int` ge=1,le=15 | `6` | |
| `gap_slug` | `Optional[str]` | `None` | |
| `manual_prompt` | `Optional[str]` max_length=2000 | `None` | Required for manual |
| `brief_id_hint` | `Optional[str]` pattern=`^[A-Za-z][A-Za-z0-9]{0,9}-\d{1,4}$` | `None` | Accepts `brief-001` and display_id |
| `product_slug/name/description` | `Optional[str]` | `None` | |
| `auto_approve` | `bool` | `False` | |
| `max_concurrent_workers` | `int` ge=1,le=10 | `3` | |
| `max_revision_cycles` | `int` ge=0,le=5 | `2` | |
| `skip_stages` | `List[int]` | `[]` | Manual rejects {0,1,2} |

### `TopicApprovalRequest` (HITL-1)

- `decision: Literal["approve","modify","reject","retry"]`
- `approved_topic_ranks: List[int]` — validator rejects negative indices.
- `added_query_ids`, `removed_query_ids`: `List[str]`
- `feedback: Optional[str]`

### `BriefApprovalRequest` (HITL-2)

- `brief_id: str`, `decision: Literal["approve","feedback","reject"]`, `feedback: Optional[str]`

### `ContentApprovalRequestV13` (HITL-3)

- `brief_id: str`, `decision: Literal["approve","edit","reject"]`
- `editor_notes: Optional[str]` max_length=5000
- `content_markdown: Optional[str]` — saved to `review_draft.md` before approval
- `rethink: bool = False` — triggers major direction change

### `TopicContentStartRequest` (TD → GA Launch)

- `company_name`, `domain`, `effective_slug: str`
- `topic_assignment_ids: List[str]` min=1, max=20 — UUID-validated
- `product_slug/name/description`: `Optional[str]`
- `auto_approve: bool = False`
- `platforms: List[str]` default `["perplexity","openai","gemini","claude"]` — validator rejects unsupported

### `TopicContentProductionRequest` (TD → CE Production)

- `company_name`, `domain`, `effective_slug: str`
- `topic_assignment_ids: List[str]` min=1, max=20 — UUID-validated
- `ga_run_id: str` — UUID-validated; identifies completed topic-scoped GA run
- `product_slug/name/description`: `Optional[str]`
- `auto_approve: bool = False`

### `TopicRunSummaryV13`

Durable topic-run projection. All fields default to empty/None.

| Field | Type | Notes |
|---|---|---|
| `topic_run_id` | `str` | UUID |
| `batch_run_id` | `str` | FK to batch |
| `topic_assignment_id` | `str` | TD assignment UUID |
| `display_id` | `str` | Human-readable (e.g., `WE-003`) |
| `topic_text` | `str` | |
| `brief_id` | `str` | CE brief identifier |
| `ga_run_id` | `Optional[str]` | |
| `pipeline_task_id` | `Optional[str]` | Task currently owning this run |
| `status` | `str` | `gap_analysis_pending`, `content_queued`, `briefing`, `content_produced`, etc. |
| `stage` | `str` | Lifecycle stage hint |
| `seq` | `int` | Within batch |
| `content_piece_id` | `Optional[str]` | Set on successful production |
| `created_at` / `updated_at` | `str` | ISO |

### `TopicRunEventV13`

Append-only execution event per topic run.

| Field | Type |
|---|---|
| `topic_event_id`, `topic_run_id`, `topic_assignment_id`, `display_id`, `brief_id` | `str` |
| `event_type`, `stage`, `status` | `str` |
| `seq` | `int` |
| `content_piece_id`, `pipeline_task_id` | `Optional[str]` |
| `payload_json` | `Dict[str, Any]` |
| `created_at` | `str` |

### `PipelineRunResponseV13`

| Field | Type | Notes |
|---|---|---|
| `run_id` | `str` | First task's ID |
| `status` | `str` | `"started"` |
| `entry_mode` | `str` | `"autonomous"`, `"manual"`, `"topic_discovery"`, `"topic_discovery_ga"` |
| `message` | `Optional[str]` | |
| `batch_run_id` | `Optional[str]` | Present for TD-entry |
| `topic_runs` | `List[TopicRunSummaryV13]` | Load-bearing for frontend |

### Response / List Schemas

- `TopicRunListResponseV13`: `effective_slug`, `total`, `items: List[TopicRunSummaryV13]`
- `TopicRunEventListResponseV13`: metadata + `items: List[TopicRunEventV13]`
- `ApprovalResponseV13`: `status="accepted"`, `stage`, `brief_id?`, `message?`
- `TopicContentStatusItem/Response`: lightweight planner sidebar projection

## `content_performance.py`

- **`ContentPerformanceRow`**: `inventory_id`, `url`, `title`, `traffic`, `ai_referrals`, `velocity`, `freshness_days`, `lifecycle`, `structural_score: int`, `citations: int`, `platforms: dict[str,bool]`, `queries_covered: int`
- **`ContentPerformanceTableResponse`**: `items`, `period_start`, `period_end`, `total_items`
- **`ContentPerformanceReadinessResponse`** (new): `state` enum (`not_connected`, `property_required`, `never_synced`, `sync_failed`, `no_matching_pages`, `no_recent_data`, `no_data`), match stats, sample paths
- **`FreshnessAssessment`** (new): `content_age_days`, `last_updated_age_days`, `cited_exemplar_avg/median_age_days`, `benchmark_sample_size`, `freshness_delta_days`, `freshness_score`, `freshness_status`, `freshness_reason`
- **`ContentDetailResponse`**: traffic, structural signals/score, citation timeline, freshness assessment, platforms, queries_covered
- **`SimilarContentResponse`**: `similar_pages`, `threshold`, `embeddings_ready: bool`

## `content_data.py`

- **`ContentPublishMetadata`** (new, shared with `cms.py`): `slug`, `meta_title`, `meta_description`, `canonical_url`, `schema_markup`, `publish_date`, `author`, `tags`
- **`ContentBriefListItem`**: enriched with `display_id`, `topic_assignment_id`, `buyer_stage`, `source`, `ga_run_id`, `effective_slug`, TD fields, `publish_metadata`
- **`SavePublishMetadataRequest`** (new): `effective_slug?`, `publish_metadata`
- **`StageContentResponse`**: `brief_id`, `stage`, `content_type` (markdown/json), `content`

## `cms.py`

- **`CMSConnectResponse`**: gained `sync_task_id?` (set on auto-sync first connect)
- **`CMSPublishRequest`**: gained `publish_metadata: Optional[ContentPublishMetadata]`
- **`CMSCategoryItem`** (new): `cms_id`, `name`, `slug`, `parent_id?`, `post_count`

## `analytics.py`

- **`DisconnectResponse`** (new): `disconnected`, `data_purged`, `error`
- Existing schemas unchanged

## Validation Conventions

- **All new fields MUST have defaults** — backward compat with existing JSON artifacts.
- **UUIDs serialize as `str`** (Pydantic v2).
- **`site_url` is `str`, not `HttpUrl`** — Pydantic v2 HttpUrl serializes to URL object.
- **Literal types** gate enum-like fields at validation time.
- **`field_validator`** on list-typed ID fields validates UUIDs element-wise.
- **`model_validator(mode="after")`** for cross-field invariants (manual-mode required fields, skip_stages).
