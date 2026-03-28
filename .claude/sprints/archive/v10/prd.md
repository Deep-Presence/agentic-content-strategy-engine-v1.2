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

---

## Post-Implementation Review (Codex gpt-5.3-codex)

**Date:** 2026-03-09
**Reviewed by:** Codex (gpt-5.3-codex) — 5 focused passes (~848K tokens)
**Passes:** agents.py, pipeline.py, graph.py, data layer (models+storage+repo), API layer (router+schemas)

---

### CRITICAL — Production Blockers (4 findings) — **ALL RESOLVED**

All 4 were in `core/topic_discovery/graph.py` → `run_td_hitl_checkpoint()`. **Fixed in sprint v10 hotfix (2026-03-09).**

| ID | Finding | Location | Fix | Status |
|----|---------|----------|-----|--------|
| C1 | `await` on sync `task_store.update_task()` — `TypeError` crash | graph.py:462 | Removed `await`, use `.value`, `approval_payload` with `checkpoint_nonce` key | **RESOLVED** |
| C2 | `event_bus.emit()` does not exist — `AttributeError` | graph.py:450 | Use sync `event_bus.publish(task_id, "pending_approval", payload)` | **RESOLVED** |
| C3 | Nonce passed as timeout to `wait_for_approval()` — `TypeError` | graph.py:474 | Call `await task_store.wait_for_approval(task_id)` without nonce arg | **RESOLVED** |
| C4 | Nonce/stage payload contract mismatch — approvals can't validate | graph.py:462-482 ↔ routers/topic_discovery.py:203 | Store `approval_payload={"stage": ..., "checkpoint_nonce": ...}`, add RUNNING reset + `approval_received` event | **RESOLVED** |

**Root cause:** TD HITL helper was written against a different contract than KB/AP/VSG. Resolved by rewriting `run_td_hitl_checkpoint()` to mirror `run_kb_hitl_checkpoint()` exactly. Tests updated in `test_graph_td.py` (mock types corrected from `AsyncMock` to `MagicMock` for sync calls, new assertions for 2x `update_task` + 2x `publish`).

---

### HIGH — Correctness & Security (11 findings) — **ALL RESOLVED**

| ID | Finding | Location | Fix | Status |
|----|---------|----------|-----|--------|
| H1 | **SECURITY:** Cross-tenant task data + approval access on run_id endpoints | routers/topic_discovery.py:160,190,232 | Added `http_request: Request` param + `task.company_slug != user_company_slug` → 403 on status, approve/taxonomy, approve/matrix | **RESOLVED** |
| H2 | **SECURITY:** Cross-tenant artifact read leak on `/{slug}/taxonomy` and `/{slug}/matrix` | routers/topic_discovery.py:272,296 | Added slug ownership check (`slug == company_slug or slug.startswith(f"{company_slug}__")`) for effective_slug support | **RESOLVED** |
| H3 | Taxonomy retry off-by-one + approved-draft inconsistency | pipeline.py:418-426,626 | Changed `>` to `>=` for retry limit; explicitly approve taxonomy + write to storage on exhaustion | **RESOLVED** |
| H4 | HITL retry feedback collected but never used in S1 regeneration | pipeline.py:420,427; agents.py; prompts/*.py | Added `revision_note` param to all 4 prompt builders + 4 agent functions; pipeline threads `user_feedback or None` to source calls on retry | **RESOLVED** |
| H5 | Source C invoked with empty sitemap data — hallucination risk | agents.py:321 | Early-return guard in `run_source_c_competitor_sitemaps()` — returns 0-candidate `SourceResult` without LLM call when `sitemap_data` is empty/whitespace | **RESOLVED** |
| H6 | Coverage math statistically inconsistent (Chao1/Sample Coverage) | agents.py:750-751 | Separated estimators by level: Chao1/Good-Turing within each source across expansion rounds; capture-recapture between sources. Added `PerSourceCoverage` model, `_count_frequency_classes_by_round()`, per-source Chao1/coverage on `SourceResult`, `aggregate_sample_coverage` on `CaptureRecaptureResult`. | **RESOLVED** |
| H7 | S3 aggregate counters drift on partial failures | pipeline.py:512,531-538 | Return per-subdomain `(assignments, counts)` and aggregate only successful results | **RESOLVED** |
| H8 | Taxonomy reparent can silently drop nodes (data loss) | graph.py:129 | Validate target parent exists before `_remove_node()`; reject edit if not found | **RESOLVED** |
| H9 | Shallow copy in taxonomy edit path mutates shared state | graph.py:225,101 | Use `copy.deepcopy(taxonomy)` before applying edits | **RESOLVED** |
| H10 | Tree metadata inconsistent after edits (depth, counts, max_depth) | graph.py:106,140 | Post-edit normalization pass to recalc depths/order and aggregate counts | **RESOLVED** |
| H11 | Timeout approvals interpreted as implicit approve | graph.py:227,376 | Changed gate functions to whitelist `("approve", "modify")` — unknown/timeout decisions produce empty `approved_taxonomy`/`approved_matrix` | **RESOLVED** |

---

### MEDIUM — Robustness (10 findings) — **ALL RESOLVED**

| ID | Finding | Location | Fix | Status |
|----|---------|----------|-----|--------|
| M1 | Round accounting incorrect — reports `max_rounds` not actual rounds executed | agents.py:221,291,426 | Added `rounds_executed` counter to Source A/B/D, incremented per loop iteration, used in SourceResult | **RESOLVED** |
| M2 | LLM JSON parsing brittle — one malformed field fails entire stage | agents.py:209,279,547 | `_parse_json_response()` now returns `None` on JSONDecodeError; added `_safe_float()` helper; all 8 callers handle `None` gracefully (break/continue/return empty) | **RESOLVED** |
| M3 | Blocking filesystem I/O on event loop | pipeline.py:250,620,630 | Wrapped company context `read_text()`, `storage.read_manifest()`, `storage.write_manifest()` in `asyncio.to_thread()` | **RESOLVED** |
| M4 | Artifact version mismatch (filename version ≠ JSON payload version) | storage.py:182,234 | `write_taxonomy()` and `write_matrix()` now use `model_copy(update={"version": version})` before serialization | **RESOLVED** |
| M5 | `get_by_effective_slug` can throw `MultipleResultsFound` | repository.py:34 | Changed to `scalars().first()` with `ORDER BY created_at DESC` to return latest discovery | **RESOLVED** |
| M6 | Migration/ORM nullability drift — NULLs possible where ORM expects non-null | 0006 migration vs ORM models | Added `nullable=False` + `server_default` on all required Integer/Boolean columns in both ORM models and Alembic migration | **RESOLVED** |
| M7 | Storage path traversal — `slug=".."` escapes root | storage.py:41 | Added `_SLUG_PATTERN` regex validation (`^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$`) + `Path.resolve()` in `TopicDiscoveryStorage.__init__()` | **RESOLVED** |
| M8 | Pydantic fields without defaults (`company_name: str`) | models/topic_discovery.py:107 | Changed to `company_name: str = ""`, requiredness enforced at API boundary via `TopicDiscoveryStartRequest` | **RESOLVED** |
| M9 | Matrix edit schemas accept invalid enum values as free strings | schemas/topic_discovery.py:79,87 | Changed `buyer_stage`/`intent_type` to typed `Optional[BuyerStage]`/`Optional[IntentType]` enums + `ConfigDict(extra="forbid")` on all request schemas | **RESOLVED** |
| M10 | Nonce anti-replay check optional (`None` disables validation) | routers/topic_discovery.py:203,245 | Hard-fail 409 if `checkpoint_nonce` missing from `approval_payload` | **RESOLVED** |

---

### LOW — Code Quality (4 findings) — **ALL RESOLVED**

| ID | Finding | Location | Fix | Status |
|----|---------|----------|-----|--------|
| L1 | Unused imports/dead code (`_emit_async`, `create_span`, `db_session` arg) | pipeline.py:108,45,208 | Removed `_emit_async` helper, `create_span` import, and `db_session` parameter | **RESOLVED** |
| L2 | Request schemas accept extra fields silently | schemas/topic_discovery.py:19 | Added `model_config = ConfigDict(extra="forbid")` on all 5 request schemas | **RESOLVED** |
| L3 | Dead `if not task:` check after `get_task()` (already raises) | routers/topic_discovery.py:163 | Removed dead code; replaced with tenant isolation check | **RESOLVED** |
| L4 | Taxonomy/matrix read endpoints return untyped `Dict[str, Any]` | routers/topic_discovery.py:274,298 | Defined `TaxonomyReadResponse` and `MatrixReadResponse` typed response models | **RESOLVED** |

---

### Open Architectural Questions

| # | Question | Recommendation |
|---|----------|----------------|
| Q1 | Should TD reuse the exact same `run_hitl_checkpoint()` helper as KB/AP/VSG? | **Yes** — eliminates C1-C4 in one refactor |
| Q2 | ~~Chao1 vs Chao2 for coverage estimation?~~ | **RESOLVED:** Per-source Chao1/Good-Turing within each source across expansion rounds; capture-recapture between sources. Hybrid eliminated. |
| Q3 | Orphan policy on parent delete — hard-delete subtree or promote children? | Define explicitly; current behavior is hard-delete |
| Q4 | Should `topic_discoveries` be unique per `effective_slug` or append-only per run? | Repository and index strategy currently conflict — resolve |
| Q5 | Should taxonomy/matrix versions be immutable snapshots? | Current storage allows overwrite — define versioning policy |

---

### Recommended Fix Priority

**Immediate (before any production use):** ✅ **ALL RESOLVED (2026-03-09)**
1. ~~Rewrite `run_td_hitl_checkpoint()` to match KB/AP/VSG contract (C1-C4, H11)~~ — **DONE**
2. ~~Add tenant isolation checks on all endpoints (H1, H2)~~ — **DONE**
3. ~~Hard-fail on missing nonce (M10)~~ — **DONE**

**Before first client run:** ✅ **ALL RESOLVED (2026-03-09)**
4. ~~Fix retry semantics (H3, H4)~~ — **DONE**
5. ~~Skip Source C when empty (H5)~~ — **DONE**
6. ~~Fix reparent data loss (H8) + shallow copy (H9) + metadata recompute (H10)~~ — **DONE**
7. ~~Fix S3 counter drift (H7)~~ — **DONE**
8. ~~Storage path traversal guard (M7)~~ — **DONE**

**Before GA:** ✅ **ALL RESOLVED (2026-03-09)**
9. ~~Fix coverage math (H6)~~ — **DONE** (per-source Chao1/Good-Turing + aggregate)
10. ~~All MEDIUM items (M1-M10)~~ — **DONE** (round accounting, JSON parsing, async I/O, version sync, slug query, nullability, path traversal, field defaults, typed enums, nonce validation)
11. ~~All LOW items (L1-L4)~~ — **DONE** (dead code removed, extra="forbid", dead checks removed, typed response models)

---

### Test Coverage Gaps Identified

1. **No integration test with real `TaskStore` + `EventBus`** for manual HITL path — tests use `AsyncMock`, masking C1-C4 (**Partially addressed:** graph tests now use `MagicMock` for sync calls + `AsyncMock` only for `wait_for_approval`, matching actual API. New `test_timeout_rejection_does_not_approve` test for H11.)
2. ~~**No cross-tenant test** verifying slug/run_id ownership enforcement~~ — **RESOLVED:** Added 7 cross-tenant tests: `test_status_tenant_isolation_403`, `test_approve_taxonomy_tenant_isolation_403`, `test_approve_matrix_tenant_isolation_403`, `test_taxonomy_tenant_isolation_403`, `test_taxonomy_effective_slug_other_company_blocked`, `test_matrix_tenant_isolation_403`, `test_matrix_effective_slug_other_company_blocked`
3. ~~**No test for reparent to non-existent parent** (H8 data loss scenario)~~ — **RESOLVED:** Added `TestReparentSafety` (3 tests) + `TestDeepCopyIsolation` (2 tests) + `TestTreeMetadataNormalization` (10 tests) + `TestS3CounterDrift` (1 test)
4. **No test for concurrent version writes** (M5 race condition)
5. ~~**No test for path traversal** with malicious slug values (M7)~~ — **RESOLVED:** Added `TestSlugPathTraversal` (5 tests for `..`, `/etc`, empty, uppercase, spaces)
6. ~~**No test for missing nonce**~~ — **RESOLVED:** Added `test_approve_taxonomy_missing_nonce_409` and `test_approve_matrix_missing_nonce_409`

---

## Hotfix Log

### 2026-03-09 — Codex Review Hotfix (C1-C4, H1, H2, H11, M10)

**8 issues resolved** across 4 files. All 270 topic_discovery tests passing (227 core + 43 API).

**Files modified:**

| File | Changes |
|------|---------|
| `core/topic_discovery/graph.py` | Rewrote `run_td_hitl_checkpoint()` to match KB/AP/VSG contract: sync `update_task()` + `event_bus.publish()`, correct `wait_for_approval()` signature, `approval_payload` with `checkpoint_nonce`, post-approval RUNNING reset + `approval_received` event. Hardened `_taxonomy_gate()` and `_matrix_gate()` to whitelist `("approve", "modify")` for approved output. |
| `api/routers/topic_discovery.py` | Added `http_request: Request` param + tenant isolation check on all 5 non-start endpoints: status (run_id), approve/taxonomy (run_id), approve/matrix (run_id), get taxonomy (slug), get matrix (slug). Slug-based reads support effective_slug (`company__product`). Added nonce hard-fail (409) on both approval endpoints. |
| `tests/topic_discovery/test_graph_td.py` | Fixed mock types (`MagicMock` for sync calls, `AsyncMock` only for `wait_for_approval`). Updated assertions for 2x `update_task` + 2x `publish`. Added `test_timeout_rejection_does_not_approve` for H11. |
| `tests/api/test_topic_discovery.py` | Added 9 new tests: 3 cross-tenant (run_id), 4 cross-tenant (slug + effective_slug), 2 nonce-missing. Updated 5 existing approval tests to include `checkpoint_nonce`. Fixed 2 not-found tests to use own-tenant slug. |

### 2026-03-09 — H3, H4, H5 Fixes

**3 issues resolved** across 8 files. All 301 topic_discovery tests passing (258 core + 43 API).

**Files modified:**

| File | Changes |
|------|---------|
| `core/topic_discovery/agents.py` | H5: Early-return guard in `run_source_c_competitor_sitemaps()` for empty sitemap data. H4: Added `revision_note: Optional[str] = None` to all 4 source agent functions, threaded to prompt builders. |
| `core/topic_discovery/prompts/source_a_company.py` | H4: Added `revision_note` param to `build_source_a_user_prompt()`, appends `## Reviewer Feedback` section when non-None. |
| `core/topic_discovery/prompts/source_b_persona.py` | H4: Same pattern for Source B. |
| `core/topic_discovery/prompts/source_c_sitemap.py` | H4: Same pattern for Source C. |
| `core/topic_discovery/prompts/source_d_adversarial.py` | H4: Same pattern for Source D. |
| `core/topic_discovery/pipeline.py` | H3: Changed `>` to `>=` for retry limit. Explicitly approve taxonomy + write to storage on exhaustion. H4: Thread `revision_note=user_feedback or None` to all 4 source calls. |
| `tests/topic_discovery/test_agents_td.py` | Added 13 tests: 2 H5 (empty sitemap guard), 6 H4 prompt builder (revision_note render/omit), 3 H4 agent (revision_note in LLM messages), 2 H5 whitespace. |
| `tests/topic_discovery/test_pipeline_td.py` | Added 3 tests: 1 H4 (retry threads feedback to sources), 2 H3 (retry exhaustion count + approved status). |

### 2026-03-09 — H7, H8, H9, H10 Fixes

**4 issues resolved** across 4 files. All 317 topic_discovery tests passing (274 core + 43 API). +16 new tests.

**Files modified:**

| File | Changes |
|------|---------|
| `core/topic_discovery/graph.py` | H9: `import copy`, replaced `dict(taxonomy)` / `dict(matrix)` with `copy.deepcopy()` in `_taxonomy_gate()` and `_matrix_gate()`. H8: Reparent now checks `_add_child_to_node()` return value; re-attaches at root if target parent not found (prevents data loss). H10: Added `_set_depths()`, `_count_nodes_and_max_depth()`, `_normalize_tree_metadata()` — post-edit normalization pass called at end of `_process_taxonomy_edits()` to fix depth, sort_order, total_subdomains, max_depth. |
| `core/topic_discovery/pipeline.py` | H7: Removed `nonlocal total_relevant, total_irrelevant` pattern. `_process_subdomain()` now returns `(assignments, relevant_count, irrelevant_count)` tuple. Outer loop only aggregates counts from successful (non-exception) results, making counters atomically consistent with assignments. |
| `tests/topic_discovery/test_graph_td.py` | Added 15 tests: `TestReparentSafety` (3: nonexistent parent preserves node, valid parent works, null parent to root), `TestDeepCopyIsolation` (2: taxonomy/matrix modify don't mutate original), `TestTreeMetadataNormalization` (10: add/delete update total, child depth correct, reparent updates depth, max_depth updated, sort_order recomputed, standalone normalize/set_depths/count helpers). |
| `tests/topic_discovery/test_pipeline_td.py` | Added 1 test: `TestS3CounterDrift::test_partial_subdomain_failure_counters_consistent` — verifies counters exclude failed subdomains. |

### 2026-03-09 — M1, M2, M3, M4, M5 Fixes

**5 issues resolved** across 4 source files + 3 test files. All 346 topic_discovery tests passing (300 core + 2 skipped repo + 43 API). +27 new tests.

**Files modified:**

| File | Changes |
|------|---------|
| `core/topic_discovery/agents.py` | M1: Added `rounds_executed` counter to Source A, B, D loops. Replaces `total_rounds=max_rounds` / `total_rounds=len(specialist_lenses)` with `total_rounds=rounds_executed` in both success and error return paths. M2: `_parse_json_response()` now catches `JSONDecodeError`/`ValueError` and returns `None` instead of raising. Added `_safe_float()` helper. All 8 callers updated: Source A/B break on `None`, Source C returns empty SourceResult, Source D continues to next lens, hierarchy/relevance/topic_gen return empty. Replaced 6 bare `float()` calls with `_safe_float()`. |
| `core/topic_discovery/pipeline.py` | M3: Wrapped 3 blocking filesystem I/O calls in `asyncio.to_thread()`: company context `read_text()` (line 250), `storage.read_manifest()` (line 620), `storage.write_manifest()` (line 630). |
| `core/topic_discovery/storage.py` | M4: `write_taxonomy()` and `write_matrix()` now sync the model's internal version field before serialization via `model_copy(update={"version": version})`. Original model not mutated. |
| `core/topic_discovery/repository.py` | M5: `get_by_effective_slug()` changed from `scalar_one_or_none()` to `scalars().first()` with `ORDER BY created_at DESC`. Returns latest discovery, never throws `MultipleResultsFound`. |
| `tests/topic_discovery/test_agents_td.py` | Added 22 tests: `TestM1RoundAccounting` (5: early break A/B, full rounds A, exception A, capped D), `TestParseJsonResponse` (4: valid/malformed/empty/fenced), `TestSafeFloat` (6: float/int/string/invalid/none/empty), `TestM2MalformedJsonRecovery` (5: mid-round A, one-lens D, hierarchy/relevance/topic_gen empty). Updated `test_malformed_json_returns_error` → `test_malformed_json_graceful_recovery`. |
| `tests/topic_discovery/test_storage_td.py` | Added 7 tests: M4 taxonomy (3: auto-increment sync, explicit sync, no-mutate), M4 matrix (2: auto-increment sync, explicit sync), M5 repository (2: uses scalars().first(), orders by created_at). |
| `tests/topic_discovery/test_pipeline_td.py` | No new tests needed — M3 changes verified by existing happy-path tests that now exercise the `asyncio.to_thread()` paths. |

### 2026-03-09 — M6, M7, M8, M9, L1, L2, L3, L4 Fixes

**8 issues resolved** across 7 source files + 3 test files. All 373 topic_discovery tests passing (322 core + 51 API). +27 new tests.

**Files modified:**

| File | Changes |
|------|---------|
| `core/db/models/topic_discovery.py` | M6: Added `nullable=False` + `server_default` on `taxonomy_version`, `matrix_version`, `total_subdomains`, `max_depth`, `depth`, `is_manually_added`, `sort_order`, `matrix_version` (assignments). Aligns ORM with migration constraints. |
| `core/db/migrations/versions/0006_topic_discovery_v2.py` | M6: Added `nullable=False` to all Integer/Boolean columns that have `server_default` — `taxonomy_version`, `matrix_version`, `total_subdomains`, `max_depth`, `depth`, `is_manually_added`, `sort_order`, `matrix_version` (assignments). |
| `core/topic_discovery/storage.py` | M7: Added `_SLUG_PATTERN` regex (`^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$`), validation in `__init__()`, and `Path.resolve()` to prevent traversal. |
| `core/models/topic_discovery.py` | M8: Changed `company_name: str` → `company_name: str = ""`. Added `PerSourceCoverage` model, `chao1_estimate`/`source_sample_coverage` on `SourceResult`, `per_source_coverage`/`aggregate_sample_coverage`/`aggregate_chao1_ratio` on `CaptureRecaptureResult`. |
| `api/schemas/topic_discovery.py` | M9: Changed `buyer_stage`/`intent_type` from `Optional[str]` to `Optional[BuyerStage]`/`Optional[IntentType]`. L2: Added `model_config = ConfigDict(extra="forbid")` on all 5 request schemas. L4: Added `TaxonomyReadResponse` and `MatrixReadResponse` typed response models. |
| `api/routers/topic_discovery.py` | L1: Removed unused `Dict`, `Any` imports. L3: Removed dead `if not task:` checks, replaced with tenant isolation. L4: Endpoints now return `TaxonomyReadResponse`/`MatrixReadResponse`. |
| `core/topic_discovery/pipeline.py` | L1: Removed `_emit_async` dead helper, `create_span` import, and unused `db_session` parameter. |
| `tests/topic_discovery/test_storage_td.py` | Added `TestSlugPathTraversal` (5 tests: `..`, `/etc/passwd`, empty string, uppercase, spaces). |
| `tests/topic_discovery/test_models_td.py` | Added M8 tests for `company_name` default + `PerSourceCoverage` model. |
| `tests/api/test_topic_discovery.py` | Added `TestSchemaValidation` (8 tests: extra fields rejected on all request schemas, typed enum validation on matrix edits, response model field checks). |
