# Topic Discovery Module — Phase I Implementation Plan

## Context

The Topic Discovery Module is a new strategic planning layer that produces an exhaustive taxonomy of content opportunities for a client. It sits between the Research Pipeline (Stage 1) and Gap Analysis (Stage 3) in the platform dependency chain. Phase I covers Stages S1-S3 + HITL-1 + HITL-2; Phase II (deferred) covers embedding generation, UMAP projection, gap analysis integration, and weekly planning overlay.

**Problem:** Content planning is currently ad-hoc. The Gap Analysis pipeline generates queries independently. The Topic Discovery Module will provide a mathematically-grounded exhaustive map of all content opportunities, enabling systematic coverage planning.

**Trigger:** This module runs after the Research Pipeline finalizes its three artifacts (Company Profile, Audience Personas, Voice Style Guide). It consumes them as read-only inputs.

---

## Scope: Phase I Only

| Include | Exclude (Phase II) |
|---------|-------------------|
| S1: Multi-Source Subdomain Generation | S4: Embedding Generation |
| S2: Exhaustiveness Evaluation & Merge | S5: Gap Analysis Query Derivation |
| HITL-1: Taxonomy Approval | Weekly Planning Overlay |
| S3: Dimensionality Expansion | UMAP/t-SNE Projection |
| HITL-2: Matrix Review | |

---

## Key Decision: Standalone Module + DB+Filesystem Dual Storage

1. **Module location:** `core/topic_discovery/` — standalone, independent module. NOT under `core/research/`. This module does not interfere with any existing pipeline module.

2. **Dual storage from Phase I:** Both filesystem (JSON artifacts) and DB (SQLAlchemy ORM) from day one, following the project's filesystem-first + DB-additive pattern.

3. **ORM assessment:**
   - **Extend** `TopicDiscoveryModel` — add `domain_name`, `effective_slug`, `taxonomy_version`, `matrix_version`, `updated_at`
   - **Drop** `DiscoveredTopicModel` — too simplistic for the architecture's requirements
   - **Add 3 new tables:** `taxonomy_trees`, `subdomain_nodes`, `topic_assignments`
   - **New Alembic migration:** `0006_topic_discovery_v2.py`
   - **6 new DB enums** in `core/db/enums.py`

---

## Directory Structure

```
core/topic_discovery/                    ← NEW standalone package
  __init__.py
  pipeline.py                            ← Main orchestrator (S1→S2→HITL1→S3→HITL2)
  agents.py                              ← All agent functions + statistical utils
  graph.py                               ← 2 LangGraph HITL graphs
  storage.py                             ← TopicDiscoveryStorage (filesystem)
  repository.py                          ← TopicDiscoveryRepository (DB)

  prompts/                               ← Prompts (co-located with module)
    __init__.py
    source_a_company.py
    source_b_persona.py
    source_c_sitemap.py
    source_d_adversarial.py
    hierarchy_construction.py
    relevance_filtering.py
    topic_generation.py

core/models/topic_discovery.py           ← NEW Pydantic models
core/db/models/topic_discovery.py        ← MODIFY existing ORM models
core/db/enums.py                         ← ADD 6 new enums
core/db/migrations/versions/0006_topic_discovery_v2.py  ← NEW migration

api/routers/topic_discovery.py           ← NEW (5 endpoints)
api/schemas/topic_discovery.py           ← NEW request/response schemas

tests/topic_discovery/                   ← NEW test package
  __init__.py
  conftest.py
  test_models_td.py
  test_storage_td.py
  test_repository_td.py
  test_agents_td.py
  test_prompts_td.py
  test_graph_td.py
  test_pipeline_td.py
tests/api/test_topic_discovery.py
```

## Files Modified (Existing)

| File | Change |
|------|--------|
| `core/config/settings.py` | Add 6 Topic Discovery settings |
| `core/db/enums.py` | Add 6 new enums (TDStatus, BuyerStage, IntentType, etc.) |
| `core/db/models/topic_discovery.py` | Extend TopicDiscoveryModel, drop DiscoveredTopicModel, add 3 new tables |
| `core/db/models/__init__.py` | Verify imports (already imports topic_discovery) |
| `api/tasks/runner.py` | Add `run_topic_discovery_pipeline_task` wrapper |
| `api/tasks/models.py` | Add `"topic_discovery"` to `PipelineTask.pipeline` Literal |
| `api/app.py` | Import and register `topic_discovery` router |

---

## Implementation Phases

### Phase A: Data Models + DB Layer (~40 tests)

#### A1: Pydantic Models
**File:** `core/models/topic_discovery.py`

**Enums:**
- `BuyerStage(str, Enum)`: TOFU, MOFU, BOFU
- `IntentType(str, Enum)`: informational, commercial, navigational, transactional
- `AudienceSegmentType(str, Enum)`: individual_persona, team_group
- `TopicDiscoveryStatus(str, Enum)`: draft, hitl_pending, approved, archived
- `TDSource(str, Enum)`: source_a, source_b, source_c, source_d
- `RelevanceCell(str, Enum)`: relevant, marginal, irrelevant
- `TopicAssignmentStatus(str, Enum)`: not_started, in_gap_analysis, content_produced, published

**Models (all fields have defaults, UUIDs as `str` with `Field(default_factory=_uuid)`):**

| Model | Purpose |
|-------|---------|
| `TopicDiscoveryInput` | Pipeline input (company_name required, rest defaulted) |
| `SubdomainCandidate` | Single subdomain from one source/round |
| `SourceResult` | Aggregated output from one source across rounds |
| `CaptureRecaptureResult` | Statistical coverage metrics |
| `SubdomainNode` | Recursive tree node (self-referencing children) |
| `TaxonomyTree` | Complete taxonomy with coverage metadata |
| `TopicAssignment` | Single content opportunity in the matrix |
| `TopicAssignmentMatrix` | Full matrix with aggregate stats |
| `TopicDiscoveryManifest` | Top-level artifact manifest |
| `TopicDiscoveryOutput` | Pipeline output |

**Conventions:** `from __future__ import annotations`, `_utcnow()` helper, `_uuid()` helper, `(str, Enum)` pattern, self-referencing via `List[SubdomainNode]`.

#### A2: DB Enums
**File:** `core/db/enums.py`

Add 6 new enums mirroring Pydantic enums:
- `TDStatus`, `BuyerStage`, `IntentType`, `AudienceSegmentType`, `RelevanceCell`, `TopicAssignmentStatus`

Note: `PipelineType.topic_discovery` already exists in this file.

#### A3: ORM Models
**File:** `core/db/models/topic_discovery.py`

**Extend `TopicDiscoveryModel`:**
```python
# ADD columns:
domain_name: Mapped[str | None]           # company domain
effective_slug: Mapped[str | None]        # {company}__{product}
taxonomy_version: Mapped[int]             # default 0
matrix_version: Mapped[int]               # default 0
status: Mapped[TDStatus]                  # replace PipelineStatus with TDStatus
updated_at: Mapped[datetime | None]       # TimestampMixin-style
```

**Drop `DiscoveredTopicModel`** — replaced by the 3 tables below.

**Add `TaxonomyTreeModel`:**
```python
class TaxonomyTreeModel(UUIDPKMixin, Base):
    __tablename__ = "taxonomy_trees"
    discovery_id: FK → topic_discoveries.id (CASCADE)
    version: int
    total_subdomains: int
    max_depth: int
    coverage_score: float | None
    chao1_estimate: float | None
    tree_json: JSONB                       # serialized TaxonomyTree
    created_at: DateTime(tz)
```

**Add `SubdomainNodeModel`:**
```python
class SubdomainNodeModel(UUIDPKMixin, Base):
    __tablename__ = "subdomain_nodes"
    taxonomy_id: FK → taxonomy_trees.id (CASCADE)
    parent_id: FK → subdomain_nodes.id (self-ref, nullable)
    name: str
    depth: int
    source: TDSource enum
    relevance_score: float | None
    metadata_json: JSONB | None
    created_at: DateTime(tz)
```

**Add `TopicAssignmentModel`:**
```python
class TopicAssignmentModel(UUIDPKMixin, Base):
    __tablename__ = "topic_assignments"
    discovery_id: FK → topic_discoveries.id (CASCADE)
    matrix_version: int
    subdomain_node_id: FK → subdomain_nodes.id
    topic_text: str
    buyer_stage: BuyerStage enum
    intent_type: IntentType enum
    audience_segment: str
    audience_segment_type: AudienceSegmentType enum
    relevance: RelevanceCell enum
    priority_score: float | None
    status: TopicAssignmentStatus enum
    metadata_json: JSONB | None
    created_at: DateTime(tz)
```

#### A4: Alembic Migration
**File:** `core/db/migrations/versions/0006_topic_discovery_v2.py`

Operations:
1. Create 6 new PG ENUMs
2. ALTER `topic_discoveries`: add new columns, change `status` type
3. DROP `discovered_topics` table
4. CREATE `taxonomy_trees`, `subdomain_nodes`, `topic_assignments` tables
5. Add indexes: `ix_taxonomy_trees_discovery`, `ix_subdomain_nodes_taxonomy`, `ix_topic_assignments_discovery`, `ix_topic_assignments_subdomain`

**Tests (~40):**
- Pydantic: instantiation, serialization round-trips, enum values, recursive SubdomainNode, field defaults
- ORM: model instantiation, relationship FK constraints, column defaults
- Migration: upgrade/downgrade (if DB available, else skip)

---

### Phase B: Storage (~30 tests)

#### B1: Filesystem Storage
**File:** `core/topic_discovery/storage.py`
**Pattern:** `VoiceStyleGuideStorage` (atomic writes, manifest CRUD, versioned artifacts)

**Filesystem layout:**
```
artifacts/topic_discovery/{effective_slug}/
  _manifest.json
  taxonomy/v1.json
  matrix/v1.json
  raw/source_a_v1.json
  raw/source_b_v1.json
  raw/source_c_v1.json
  raw/source_d_v1.json
  raw/coverage_v1.json
```

**Class: `TopicDiscoveryStorage`**
- `__init__(artifacts_root, slug)` → base_dir = `artifacts_root / "topic_discovery" / slug`
- `_atomic_write(path, content)` — tempfile + os.replace
- Manifest: `read_manifest() / write_manifest()`
- Raw sources: `write_source_result(source, result) / read_source_result(source, version)`
- Taxonomy: `write_taxonomy(tree) / read_taxonomy(version) / get_latest_taxonomy_version()`
- Coverage: `write_coverage(metrics, version) / read_coverage(version)`
- Matrix: `write_matrix(matrix) / read_matrix(version) / get_latest_matrix_version()`

#### B2: DB Repository
**File:** `core/topic_discovery/repository.py`
**Pattern:** Existing repositories in `core/db/repositories/`

**Class: `TopicDiscoveryRepository`**
- `__init__(session: AsyncSession)`
- `create_discovery(input_data) → TopicDiscoveryModel`
- `get_discovery(discovery_id) → TopicDiscoveryModel | None`
- `get_discovery_by_slug(effective_slug) → TopicDiscoveryModel | None`
- `update_discovery_status(discovery_id, status)`
- `save_taxonomy_tree(discovery_id, tree, version) → TaxonomyTreeModel`
- `get_taxonomy_tree(discovery_id, version) → TaxonomyTreeModel | None`
- `get_latest_taxonomy(discovery_id) → TaxonomyTreeModel | None`
- `save_subdomain_nodes(taxonomy_id, nodes: list)` — bulk insert flattened tree
- `save_topic_assignments(discovery_id, assignments: list, matrix_version)` — bulk insert
- `get_topic_assignments(discovery_id, matrix_version) → list[TopicAssignmentModel]`
- `update_assignment_status(assignment_id, status)`

**Tests (~30):**
- Filesystem: manifest CRUD, versioning auto-increment, atomic write with dir creation, read missing returns None, corrupted JSON, version edge cases (empty dir)
- Repository: CRUD operations, slug lookup, taxonomy versioning, bulk inserts (DB tests with `pytestmark = pytest.mark.skipif(not DATABASE_URL)`)

---

### Phase C: Agents (~45 tests)
**File:** `core/topic_discovery/agents.py`
**Deps:** Phase A (models), Phase D (prompts)
**Pattern:** `voice_style_guide/agents.py` (LiteLLM async calls)

**LLM Model Selection:**
- Brainstorming/generation: Claude Sonnet via LiteLLM (`settings.topic_discovery_brainstorm_model`)
- Dedup/hierarchy/relevance: Claude Haiku via LiteLLM (`settings.topic_discovery_dedup_model`)
- Embeddings: text-embedding-3-small via `core/shared_tools/embedding_client.embed_texts()`

**Agent Functions:**

| Function | Stage | LLM | Pattern |
|----------|-------|-----|---------|
| `run_source_a_company_brainstorm()` | S1 | Sonnet | Iterative expansion (N rounds) |
| `run_source_b_persona_brainstorm()` | S1 | Sonnet | Iterative expansion (N rounds) |
| `run_source_c_competitor_sitemaps()` | S1 | Haiku | httpx fetch + LLM normalization |
| `run_source_d_adversarial()` | S1 | Sonnet | Specialist-lens iterative |
| `deduplicate_subdomains()` | S2 | None | embed_texts() + cosine similarity |
| `run_hierarchy_construction()` | S2 | Sonnet | Single LLM call → JSON tree |
| `run_relevance_filtering()` | S3 | Haiku | Batched binary classification |
| `run_topic_generation()` | S3 | Sonnet | Batched generation + priority |

**Statistical Functions (pure Python, no LLM):**
- `compute_capture_recapture(source_a_count, source_b_count, overlap)` → estimated total
- `compute_chao1_lower_bound(observed, singletons, doubletons)` → lower bound
- `compute_sample_coverage(singletons, total)` → coverage ratio (0-1)
- `compute_all_coverage_metrics(source_results)` → `CaptureRecaptureResult`

**Guards:**
- `_MAX_PAUSE_TURNS = 5` cap per agent (VSG pattern)
- `_strip_code_fences()` for JSON responses
- Embedding batch size = 64 with `asyncio.to_thread()`

**Async pattern:** All agent functions `async def`, use `litellm.acompletion()` wrapped in `asyncio.wait_for(timeout=timeout_s)`. Errors caught in result objects (never fatal).

**Tests:**
- Each agent: happy path (mocked LLM), timeout, API error, malformed JSON
- Statistical functions: hand-computed expected values
- Deduplication: mock `embed_texts()` with deterministic vectors
- Competitor sitemap: mock httpx transport
- NO evaluation of LLM output quality

---

### Phase D: Prompts (~15 tests)
**Files:** `core/topic_discovery/prompts/*.py` (7 files)
**Deps:** Phase A
**Pattern:** `core/research/prompts/voice_style_guide/` (SYSTEM_PROMPT + builder functions)

Each file exports:
- `get_*_system_prompt() -> str`
- `build_*_user_prompt(context_vars, round_number=None, previous_subdomains=None) -> str`

**Prompt design:**
- Source A/B/D: iterative expansion prompts with `round_number` and `previous_subdomains`
- Source D: `specialist_lens` parameter
- All generation prompts require JSON output
- Hierarchy construction: structured JSON tree output matching SubdomainNode schema

**Tests:** System prompts non-empty, user prompt builders produce strings containing expected fragments, round-number injection works.

---

### Phase E: HITL Graphs (~25 tests)
**File:** `core/topic_discovery/graph.py`
**Deps:** Phase A
**Pattern:** `voice_style_guide/graph.py` (interrupt/resume, TypedDict state)

**HITL-1: Taxonomy Review (`build_td_taxonomy_review_graph()`)**
- State: `TDTaxonomyReviewState(TypedDict, total=False)`
- Nodes: `present → gate → route → END`
- Gate: auto-approve or `interrupt()` with taxonomy + coverage payload
- Resume: processes user_edits (add/delete/rename/reparent)
- `_process_taxonomy_edits()` helper

**HITL-2: Matrix Review (`build_td_matrix_review_graph()`)**
- State: `TDMatrixReviewState(TypedDict, total=False)`
- Same node pattern, processes priority adjustments + add/remove assignments

**Shared helper:**
- `run_td_hitl_checkpoint()` — invoke graph, detect `__interrupt__`, publish SSE, wait_for_approval, resume with `Command(resume=approval)`.
- `_has_interrupt()` / `_get_interrupt_value()` — 5th copy (defer refactor)

**Tests:** Auto-approve flow, interrupt payload, approve/modify/retry, edit application, invocation with mock task_store.

---

### Phase F: Pipeline Orchestrator (~30 tests)
**File:** `core/topic_discovery/pipeline.py`
**Deps:** Phases A-E
**Pattern:** `voice_style_guide/pipeline.py`

**Main function:**
```python
async def run_topic_discovery_pipeline(
    input_data: TopicDiscoveryInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    db_session: Optional[Any] = None,      # ← for DB persistence
) -> TopicDiscoveryOutput
```

**Execution flow:**
```
Phase 0: Preflight
  ├── Resolve slug / effective_slug
  ├── Initialize TopicDiscoveryStorage (filesystem)
  ├── Initialize TopicDiscoveryRepository (DB, if db_session provided)
  ├── Load company context (company_context/{slug}.md, fallback chain)
  ├── Load persona profiles (PersonaStorage)
  ├── Configure LiteLLM callbacks + tracing
  └── Validate prereqs (company context + personas must exist)

Phase 1 (S1): Multi-Source Subdomain Generation
  ├── asyncio.gather(source_a, source_b, source_c)  ← parallel
  ├── Collect results from A+B+C
  ├── run_source_d_adversarial(existing=A+B+C results)  ← sequential
  ├── Write raw source results to filesystem storage
  └── Emit SSE events per source completion

Phase 2 (S2): Exhaustiveness Evaluation & Merge
  ├── Collect all candidates from 4 sources
  ├── deduplicate_subdomains() via embeddings + cosine similarity
  ├── compute_all_coverage_metrics()
  ├── run_hierarchy_construction() → TaxonomyTree
  ├── Write taxonomy + coverage to filesystem storage
  ├── Persist taxonomy to DB (if db_session)
  └── Emit SSE events

HITL-1: Taxonomy Approval
  ├── build_td_taxonomy_review_graph()
  ├── run_td_hitl_checkpoint() → decision
  ├── If "retry": re-run S1+S2 with feedback (max _MAX_TAXONOMY_RETRIES=2)
  ├── If "modify": apply edits to taxonomy
  ├── Write approved taxonomy to storage + DB
  └── Emit approval SSE

Phase 3 (S3): Dimensionality Expansion
  ├── Load approved taxonomy
  ├── Define dimensions (buyer_stage × intent × audience_segments)
  ├── Pass 1: run_relevance_filtering() → filter irrelevant cells
  ├── Pass 2: run_topic_generation() → generate for relevant cells
  ├── Compute priority scores
  ├── Write matrix to filesystem storage
  ├── Persist assignments to DB (if db_session)
  └── Emit SSE events

HITL-2: Matrix Review
  ├── build_td_matrix_review_graph()
  ├── run_td_hitl_checkpoint() → decision
  ├── If "modify": apply edits to matrix
  ├── Write approved matrix to storage + DB
  └── Emit approval SSE

Finalize:
  ├── Update manifest (versions, timestamps, status) — filesystem + DB
  └── Return TopicDiscoveryOutput
```

**Error handling:** Top-level try/except logs + emits "failed" SSE + re-raises. Individual source failures captured in SourceResult.error (non-fatal).

**Tests:**
- Slug resolution, preflight loading
- Full happy path (all agents mocked, both HITLs auto-approved)
- Missing company context → RuntimeError
- Partial source failure → pipeline continues
- HITL-1 modify/retry flows (bounded by _MAX_TAXONOMY_RETRIES=2)
- HITL-2 priority adjustment flow
- SSE events emitted at each phase boundary
- Task store status transitions
- DB persistence calls (when db_session provided)
- DB-less mode (db_session=None → filesystem only)

---

### Phase G: API Layer (~20 tests)
**Deps:** Phase F

**New files:**
- `api/schemas/topic_discovery.py` — request/response schemas
- `api/routers/topic_discovery.py` — 5 endpoints

**Modified files:**
- `api/tasks/models.py` — add `"topic_discovery"` to `PipelineTask.pipeline` Literal
- `api/tasks/runner.py` — add `run_topic_discovery_pipeline_task()`
- `api/app.py` — register router
- `core/config/settings.py` — add 6 settings

**Endpoints:**
```
POST /api/v1/topic-discovery/start                     → 202 (launch) / 200 (already_exists)
GET  /api/v1/topic-discovery/{run_id}/status            → TaskResponse
POST /api/v1/topic-discovery/{run_id}/approve           → ApprovalResponse
GET  /api/v1/topic-discovery/{slug}/taxonomy            → TaxonomyTree JSON
GET  /api/v1/topic-discovery/{slug}/matrix              → TopicAssignmentMatrix JSON
```

**Router pattern (KB/VSG):**
- RBAC: `require_role("member", "superuser")`
- Tenant isolation: validate company_slug from token
- Guard: 200 if manifest already exists and `force_rerun=False`
- Background task: `asyncio.create_task()` + `register_task_handle()`
- Approval: nonce validation + `submit_approval()`
- Taxonomy/Matrix read: filesystem-first, DB fallback

**Settings to add in `core/config/settings.py`:**
```python
topic_discovery_brainstorm_model: str = "anthropic/claude-sonnet-4-6"
topic_discovery_dedup_model: str = "anthropic/claude-haiku-4-5-20251001"
topic_discovery_max_expansion_rounds: int = 4
topic_discovery_dedup_threshold: float = 0.85
topic_discovery_max_concurrent_sources: int = 4
topic_discovery_source_timeout_s: float = 120.0
```

**Tests:**
- Start: 202 launch, 200 already_exists, 403 tenant isolation, 409 concurrent run
- Status: returns task state
- Approve: nonce validation, 409 wrong status
- Taxonomy/Matrix read: 200 with data, 404 missing
- Runner: mock pipeline, task store lifecycle

---

### Phase H: Integration (~10 tests)
**Deps:** All phases

**Shared fixtures in `tests/topic_discovery/conftest.py`:**
- `td_input()` → TopicDiscoveryInput fixture
- `artifacts_dir(tmp_path)` → pre-populated with company_context + personas
- `storage(tmp_path)` → TopicDiscoveryStorage
- `mock_taxonomy()` → sample TaxonomyTree
- `mock_matrix()` → sample TopicAssignmentMatrix

**Integration tests:** Full pipeline flow with all LLM calls mocked, verify artifacts written to filesystem at each stage, verify DB records created, verify SSE event ordering, verify task_store transitions.

---

## Test Summary

| Phase | Test File | Est. Tests |
|-------|-----------|-----------|
| A: Models + DB | `test_models_td.py` | 40 |
| B: Storage + Repo | `test_storage_td.py`, `test_repository_td.py` | 30 |
| C: Agents | `test_agents_td.py` | 45 |
| D: Prompts | `test_prompts_td.py` | 15 |
| E: HITL Graphs | `test_graph_td.py` | 25 |
| F: Pipeline | `test_pipeline_td.py` | 30 |
| G: API | `test_topic_discovery.py` | 20 |
| H: Integration | (in pipeline tests) | 10 |
| **Total** | | **~215** |

---

## Implementation Sequence

```
Phase A (Models + DB) ────────────────┐
                                      ├── Phase C (Agents) ─────┐
Phase D (Prompts, parallel with A) ───┘                         │
                                                                │
Phase B (Storage + Repo, after A) ──────────────────────────────┤
                                                                │
Phase E (HITL Graphs, after A) ─────────────────────────────────┤
                                                                │
Phase F (Pipeline, after A-E) ──────────────────────────────────┤
                                                                │
Phase G (API, after F) ─────────────────────────────────────────┤
                                                                │
Phase H (Integration, after G) ─────────────────────────────────┘
```

---

## Verification Plan

1. **Per-phase:** Run `pytest tests/topic_discovery/ -v` after each phase
2. **API phase:** Run `pytest tests/api/test_topic_discovery.py -v`
3. **Full regression:** Run `pytest tests/ -v --timeout=120` to ensure no existing tests broken
4. **Manual E2E:** After all phases, run the pipeline with `auto_approve_checkpoints=[1,2]` to verify LLM call patterns and artifact quality

---

## Critical Integration Points

1. **`PipelineTask.pipeline` Literal** — `api/tasks/models.py:29`. Must add `"topic_discovery"`. Also update `tests/api/test_task_models.py:84`.
2. **`_has_interrupt` / `_get_interrupt_value` duplication** — 5th copy. Defer shared refactor.
3. **HITL-1 "retry" loop bound** — `_MAX_TAXONOMY_RETRIES = 2` in pipeline.py.
4. **Source C network failure** — Per-domain 10s timeout + graceful skip via `httpx.AsyncClient(timeout=10.0)`.
5. **Embedding batch size** — Batch `embed_texts()` calls (batch_size=64), `asyncio.to_thread()`.
6. **Storage version detection** — `glob("v*.json")`, parse highest, increment. Handle empty dir (start at v1).
7. **LiteLLM pause_turn** — `_MAX_PAUSE_TURNS = 5` cap per agent.
8. **JSON code fence stripping** — `_strip_code_fences()` for all LLM JSON responses.
9. **DB enum registration** — New PG ENUMs must use `create_type=True` in mapped_column.
10. **Migration ordering** — `0006` depends on `0005`. Verify Alembic `down_revision` chain.

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| S1 expansion rounds produce repetitive subdomains | Configurable max_rounds + singleton tracking |
| Semantic dedup threshold too aggressive/lenient | Configurable via settings (default 0.85) |
| Capture-recapture math invalid if sources not independent | Source D breaks correlation; Source C is empirical |
| S3 combinatorial explosion | Relevance filtering eliminates ~50-70% cells |
| LLM JSON parsing failures | `_strip_code_fences()` + tolerant parser + retry |
| HITL-1 retry infinite loop | `_MAX_TAXONOMY_RETRIES = 2` cap |
| Source C network hangs | Per-domain 10s timeout + graceful skip |
| LiteLLM pause_turn runaway | `_MAX_PAUSE_TURNS = 5` cap |
| Migration conflicts with other branches | Check `down_revision` chain before merge |
