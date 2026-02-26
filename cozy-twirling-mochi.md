# Plan: Existing-Company Pipeline Guard + Content-Gap Integration

> **Codex gpt-5.3-codex review complete (high reasoning, 2026-02-27).** 12 findings — 5 CRITICAL, 6 WARNING, 1 INFO. All incorporated below.

## Context

Two orthogonal features, both rooted in the same theme: **the gap analysis pipeline should be aware of work already done and reflect new content as it's produced.**

**Feature 1 — Existing Pipeline Guard:** Today the `/gap-analysis/start` and `/research/start` endpoints blindly launch new runs even when artifacts already exist for a company. When User 2 joins an already-analyzed company, there's no guard — they can accidentally queue expensive duplicate pipeline runs. Fix: add `force_rerun: bool = False` to start requests; when artifacts exist and `force_rerun=False`, return 200 with skip metadata instead of launching a task.

**Feature 2 — Content-Gap Integration:** After the content engine approves a content brief (e.g., targeting query C5-Q1), the gap analysis outputs don't reflect that new content. The embedding projections, radar charts, and gap scores all still show the original state. Fix: a new `content-refresh` pipeline that embeds approved content, patches QueryGap entries for targeted queries, recomputes cluster stats for affected clusters, regenerates all visualizations and reports.

---

## Feature 1: Existing Pipeline Guard

### Design

Add `force_rerun: bool = False` to `GapAnalysisStartRequest`, `ResearchStartRequest` in `api/schemas/common.py`.

**Artifact existence checks (filesystem-based — no Company model changes needed):**
- Gap analysis exists: check in order: `gap_analysis_complete.json` → `analysis.json` (mirrors fallback in `api/services/gap_data_service.py:112`)
- Research exists: any of `company_context/{slug}.md`, `personas/{slug}__persona-*.md`, `style_guides/{slug}.md` for the effective_slug AND company_slug (mirrors runner's fallback chain)

**Endpoint behavior:**
```python
# In start_gap_analysis() / start_research():
if not body.force_rerun:
    existing_run_id = _detect_existing_artifacts(artifacts_root, effective_slug, "gap_analysis")
    if existing_run_id:
        response.status_code = 200
        last_task = task_store.list_tasks(
            pipeline="gap_analysis",
            company_slug=slug,
            product_slug=body.product_slug,  # ← scope-aware (Codex W6)
        )
        return PipelineRunResponse(
            run_id=last_task[0].task_id if last_task else "",
            pipeline="gap_analysis",
            company_slug=slug,
            status="already_exists",
            created_at=last_task[0].created_at if last_task else datetime.utcnow(),
            already_exists=True,
            message="Artifacts already exist. Pass force_rerun=true to re-run.",
        )
```

**`PipelineRunResponse` additions** (non-breaking, all have defaults):
```python
already_exists: bool = False
message: Optional[str] = None
```
`run_id` and `created_at` are ALREADY required fields — populate from last task when returning "already exists". This preserves the full existing contract. (Codex C1 fix)

**Research guard must use effective_slug → company_slug fallback** (Codex W7):
```python
def _research_artifacts_exist(artifacts_root, effective_slug, company_slug):
    """Check both scopes — mirrors runner.py resolve_artifacts() fallback."""
    for slug in [effective_slug, company_slug]:
        ctx = artifacts_root / "company_context" / f"{slug}.md"
        if ctx.exists():
            return True
    return False
```

**No Company model changes.** Status always filesystem-derived.

### Files Changed (Feature 1)
| File | Change |
|------|--------|
| `api/schemas/common.py` | Add `force_rerun: bool = False` to `GapAnalysisStartRequest`, `ResearchStartRequest`; add `already_exists: bool = False`, `message: Optional[str] = None` to `PipelineRunResponse` |
| `api/routers/gap_analysis.py` | Inject `Response` param; add scoped artifact-exists guard before task creation |
| `api/routers/research.py` | Same guard using dual-scope fallback check |
| `tests/api/test_gap_analysis.py` | TDD: `test_start_returns_already_exists_when_artifacts_present`, `test_start_force_rerun_bypasses_guard`, `test_start_already_exists_includes_last_run_id` |
| `tests/api/test_research.py` | TDD: same for research pipeline |

---

## Feature 2: Content-Gap Integration

### Architecture Decision

The content refresh is a **separate pipeline mode** (`run_content_refresh()` in `pipeline.py`), NOT an extension of `skip_steps`. Rationale: the logic (embed new content, surgical patch of analysis, full cluster recompute for affected clusters, re-run s7+s8) is structurally different from the linear s1-s8 skip mechanism.

### Task Pipeline Type: Keep `"gap_analysis"` (Codex C2 fix)

Do NOT use `"gap_analysis_refresh"` as a pipeline literal — `PipelineTask.pipeline` is a strict Literal type (in `api/tasks/models.py:36`) and the frontend unions only allow `gap_analysis|research|content`. Instead, use `pipeline="gap_analysis"` and add a task metadata field `mode: str = "full"` (default) / `"content_refresh"` to distinguish runs. This keeps all existing TaskStore filters, RunHistory, and frontend pipeline tabs working without changes.

### New Data Model: `ApprovedContentPiece` (in `core/models/gap_analysis.py`)
```python
class ApprovedContentPiece(BaseModel):
    brief_id: str
    title: str = ""
    query_ids: List[str] = Field(default_factory=list)  # resolved from query_text lookup
    embedding: Optional[List[float]] = None
    content_excerpt: str = ""  # First 400 chars
    source_path: str = ""      # path to final.md
    approved_at: str = ""      # ISO timestamp
    word_count: int = 0
```

All fields have defaults → backward compatible. No changes to existing models.

### QueryGap Model Addendum (Codex W11)

`QueryGap` has fields beyond `best_company_similarity` describing the winning match. When approved content improves the score, we need provenance. Add to `QueryGap` (defaults = None, safe):
```python
best_content_piece_id: Optional[str] = None   # brief_id if content was best match
content_refresh_at: Optional[str] = None       # ISO timestamp of last content refresh
```
This keeps `best_company_similarity` semantically correct (it now includes content pieces in its "company" side) while surfacing provenance.

### Artifact Storage: `content_pieces/` directory

```
artifacts/gap_analysis/{slug}/content_pieces/
├── {brief_id}.json   ← ApprovedContentPiece with embedding
└── index.json        ← List of brief_ids processed
```

Separate from `company_embeddings.json` (website crawl assets) to preserve distinction for visualization.

### Brief-to-Query Linkage (Codex C4 — explicit strategy)

`ContentBrief.target_queries` carries `query_text` + `cluster_name`, but NOT `query_id`. Resolution strategy:
1. Load `embeddings/queries_with_embeddings.json` → build `Dict[query_text → query_id]` (case-insensitive, stripped)
2. For each `target_query.query_text`: exact match lookup → `query_id`
3. If no exact match: log WARNING with `(brief_id, query_text)`, skip that query (don't fail the refresh)
4. If zero queries resolved for a brief: fail with HTTP 422 (the brief has no overlap with existing analysis)
5. This is deterministic and auditable — no fuzzy matching that could silently mismatch.

### Content Refresh Pipeline (`core/gap_analysis/pipeline.py`)

New top-level `async def run_content_refresh()` alongside `run_gap_analysis()`:

```
Step A: Validate inputs
  - gap_analysis_complete.json OR analysis.json must exist (Codex W8 — dual sentinel)
  - Each brief_id validated against ^brief-\d{1,4}$ (Codex C5 — path traversal guard)
  - Approval check: load run_metadata.json, verify piece.status ∈ {"approved","edited"} (Codex W10)

Step B: Load existing artifacts
  - queries_with_embeddings.json → GeneratedQuery list
  - company_embeddings.json → SemanticUnit list
  - citations_with_embeddings.json → EnrichedCitation list
  - analysis.json → AnalysisResult

Step C: Embed content pieces
  - For each brief_id: read final.md
  - If content_pieces/{brief_id}.json already exists with non-null embedding → skip
  - Chunk long documents: split to ~2000-word chunks, embed each, take mean embedding
    (uses async_embed_texts() from shared_tools/async_embedding_client.py)
  - Save content_pieces/{brief_id}.json

Step D: Resolve target_query_ids
  - Build query_text → query_id lookup from loaded queries
  - Map brief.target_queries[*].query_text → query_ids (exact match; skip unresolved with warning)
  - target_query_ids = union across all refresh briefs

Step E: Patch analysis (new function in s6_analyze.py)
  - patch_analysis_with_content_pieces(analysis, content_pieces, queries, target_query_ids)
  - → Returns (updated_analysis, affected_cluster_ids)

Step F: Save analysis.json (overwrite existing)

Step G: Re-run s7 with content_pieces parameter
  - generate_visualizations(..., content_pieces=content_pieces)

Step H: Re-run s8 — generate_gap_report() + save_report()
```

### s6 Changes (`core/gap_analysis/steps/s6_analyze.py`) — Codex C3 fix

**No private helper functions exist in s6 currently.** `compute_gap_analysis()` is monolithic. Therefore `patch_analysis_with_content_pieces()` must implement the cluster-stat updates inline, reusing only the public scipy/numpy primitives that the existing function already uses:

```python
def patch_analysis_with_content_pieces(
    analysis: AnalysisResult,
    content_pieces: List[ApprovedContentPiece],
    queries: List[GeneratedQuery],
    target_query_ids: Set[str],
) -> Tuple[AnalysisResult, Set[str]]:
    """
    1. For each query in target_query_ids:
       - Compute max cosine_sim(content_piece.embedding, query.embedding) across all content_pieces
       - If > existing best_company_similarity: update it, set best_content_piece_id, content_refresh_at
       - Recompute gap = avg_citation_similarity - new best_company_similarity
       - Track affected_cluster_ids

    2. For each affected cluster:
       - Collect all QueryGap entries in that cluster (including un-targeted ones unchanged)
       - Recompute per-cluster proximity_stats["per_cluster"][cluster_name]["company_mean/std"]
       - Recompute SPA t-test: scipy.stats.ttest_ind(company_similarities, citation_similarities)
         → Update SpaResult entry for that cluster
       - Recompute centroid distance: mean(query embeddings) vs mean(content_piece embeddings in cluster)
         → Update CentroidResult entry for that cluster
       - Recompute decision_metrics.avg_gap from updated gaps list

    Returns: (patched_analysis, affected_cluster_ids)
    """
```

All scipy/numpy operations inline — no private helper extraction needed.

### s7 Changes (`core/gap_analysis/steps/s7_visualize.py`)

Signature change (optional param — backward compatible):
```python
def generate_visualizations(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    analysis: AnalysisResult,
    output_dir: Path,
    content_pieces: Optional[List[ApprovedContentPiece]] = None,  # NEW
) -> Dict[str, str]:
```

**`EmbeddingPoint.type` contract update (Codex W9):**
- Current type field accepts `"query" | "citation" | "company"`
- Add `"approved_content"` to the Literal in `api/schemas/content_data.py` (the schema used by the embeddings endpoint)
- Update `tests/api/test_content_data.py` test for point structure to allow `"approved_content"`
- Update `frontend-dashboard/src/components/charts/umap-scatter.tsx` to handle new type (star marker, sage-green)

New visualization behavior:
- UMAP/t-SNE: star marker, distinct color for approved_content points
- Radar chart: 3rd trace "Approved Content" showing mean similarity of content_pieces to cluster queries
- Content piece points labeled with `brief.title` (truncated to 40 chars)

### New API Endpoint (`api/routers/gap_analysis.py`)

```
POST /api/v1/gap-analysis/content-refresh
```

New request schema `ContentRefreshRequest` in `api/schemas/common.py`:
```python
_BRIEF_ID_RE = re.compile(r"^brief-\d{1,4}$")  # matches existing pattern

class ContentRefreshRequest(BaseModel):
    company_name: str
    brief_ids: List[str]
    product_slug: Optional[str] = None

    @field_validator("brief_ids")
    @classmethod
    def validate_brief_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("brief_ids must not be empty")
        for bid in v:
            if not _BRIEF_ID_RE.match(bid):
                raise ValueError(f"Invalid brief_id '{bid}'. Must match ^brief-\\d{{1,4}}$")
        return v

    @field_validator("product_slug")
    @classmethod
    def validate_product_slug(cls, v):
        return _check_product_slug(v)  # reuse existing validator
```

Endpoint logic:
1. Derive slug / resolve scope (reuse `_derive_slug()` and `_resolve_scope()`)
2. Validate gap analysis artifacts exist (dual-sentinel check)
3. Validate each brief_id: `run_metadata.json` status ∈ `{"approved","edited"}` and `final.md` exists
4. Create task: `task_store.create_task("gap_analysis", slug, product_slug=...)` — reuse existing type (Codex C2 fix)
5. Launch `asyncio.create_task(run_content_refresh_task(...))`
6. Return 202 with task_id

### New Runner (`api/tasks/runner.py`)

New function `run_content_refresh_task()`:
- Pattern mirrors `run_gap_pipeline_task()` — resolves scope, constructs input, handles SSE events and task state
- SSE events: `pipeline_start → embedding_content → patching_analysis → generating_visualizations → generating_report → completed`
- On failure: publish `failed` event, update task status
- Task metadata includes `{"mode": "content_refresh", "brief_ids": [...], "target_query_ids": [...]}`

### Files Changed (Feature 2)

| File | Change |
|------|--------|
| `core/models/gap_analysis.py` | Add `ApprovedContentPiece` model; add `best_content_piece_id`, `content_refresh_at` optional fields to `QueryGap` |
| `core/gap_analysis/pipeline.py` | Add `run_content_refresh()` function; add `embed_content_pieces()` helper |
| `core/gap_analysis/steps/s6_analyze.py` | Add `patch_analysis_with_content_pieces()` (inline scipy/numpy, no extracted helpers assumed) |
| `core/gap_analysis/steps/s7_visualize.py` | Add `content_pieces` optional param; add `"approved_content"` point type in HTML + JSON output |
| `api/schemas/common.py` | Add `ContentRefreshRequest` with brief_id pattern validation |
| `api/schemas/content_data.py` | Add `"approved_content"` to `EmbeddingPoint.type` Literal |
| `api/routers/gap_analysis.py` | Add `POST /content-refresh` endpoint |
| `api/tasks/runner.py` | Add `run_content_refresh_task()` |
| `tests/api/test_gap_analysis.py` | TDD tests for content-refresh endpoint (validation, 202 response, artifact guards) |
| `tests/gap_analysis/test_pipeline.py` | TDD: `test_run_content_refresh_patches_gaps`, `test_embed_content_pieces_creates_artifacts` |
| `tests/gap_analysis/steps/test_s6_analyze.py` | TDD: `test_patch_analysis_updates_best_similarity`, `test_patch_analysis_recomputes_cluster_stats`, `test_patch_analysis_no_update_when_content_worse` |
| `tests/gap_analysis/steps/test_s7_projections.py` | TDD: `test_visualize_includes_content_pieces_as_separate_type` |
| `tests/api/test_content_data.py` | Update embedding point type test to allow `"approved_content"` |
| `frontend-dashboard/src/components/charts/umap-scatter.tsx` | Handle `"approved_content"` type (star marker, sage-green) |

---

## Key Tradeoffs & Decisions

| Tradeoff | Decision | Rationale |
|----------|----------|-----------|
| Content refresh as `skip_steps` extension vs. separate function | **Separate `run_content_refresh()`** | Avoids complex branching; structurally different from linear s1-s8 |
| Patch query gaps only vs. full cluster recompute | **Full cluster recompute for affected clusters** | Required for consistency — SPA t-tests, centroids, proximity_stats must stay in sync |
| UMAP/t-SNE: full recalculation vs. `transform()` | **Full recalculation** | Dataset small (~200–400 pts); `transform()` drifts from original space; correctness > speed |
| Content piece storage: with company embeddings vs. separate directory | **Separate `content_pieces/`** | Preserves distinction for visualization; independently queryable |
| Trigger on content approval: auto vs. manual | **Manual only** | User retains full control |
| Pipeline type literal: new `"gap_analysis_refresh"` vs reuse `"gap_analysis"` | **Reuse `"gap_analysis"`** (Codex C2) | Avoids model/frontend/test cascade breakage; distinguish via task metadata `mode` |
| `force_rerun` response model: separate vs. extend `PipelineRunResponse` | **Extend with optional fields** (Codex C1) | Preserves frontend contract; `run_id` populated from last task |
| Brief-to-query matching: exact vs. fuzzy | **Exact match on `query_text`** (Codex C4) | Deterministic, auditable; unresolved queries logged+skipped individually |
| Brief approval validation: `final.md` exists vs. check `run_metadata.json` | **Check `run_metadata.json` status** (Codex W10) | `final.md` alone doesn't guarantee approval — same pattern as `content_data_service.py:165` |

---

## Codex Review Findings — Disposition

| # | Class | Finding | Disposition |
|---|-------|---------|-------------|
| C1 | CRITICAL | `PipelineRunResponse` uses `run_id`/`created_at` not `task_id=""` | **INCORPORATED** — populate from last task |
| C2 | CRITICAL | `gap_analysis_refresh` not a valid pipeline Literal | **INCORPORATED** — reuse `"gap_analysis"`, add task `mode` metadata |
| C3 | CRITICAL | s6 has no `_compute_spa()` / `_compute_centroid()` helpers | **INCORPORATED** — `patch_analysis_with_content_pieces()` implements inline |
| C4 | CRITICAL | `ContentBrief.target_queries` has no `query_id` | **INCORPORATED** — exact `query_text` match strategy with warn+skip |
| C5 | CRITICAL | `brief_ids` needs path traversal validation | **INCORPORATED** — `^brief-\d{1,4}$` validator on `ContentRefreshRequest` |
| W6 | WARNING | `last_run_at` must be scope-aware | **INCORPORATED** — pass `product_slug=` to `list_tasks()` |
| W7 | WARNING | Research guard must mirror fallback chain | **INCORPORATED** — dual-scope check for effective_slug and company_slug |
| W8 | WARNING | `gap_analysis_complete.json` alone is insufficient sentinel | **INCORPORATED** — dual sentinel: `gap_analysis_complete.json` OR `analysis.json` |
| W9 | WARNING | `approved_content` type breaks existing point type contracts | **INCORPORATED** — update `content_data.py` Literal + test + frontend |
| W10 | WARNING | `final.md` ≠ approved; check `run_metadata.json` status | **INCORPORATED** — validate piece status in endpoint |
| W11 | WARNING | `best_company_unit` semantics inconsistent if content becomes best match | **INCORPORATED** — add `best_content_piece_id`, `content_refresh_at` to `QueryGap` |
| I12 | INFO | Lock contracts before internals | **INCORPORATED** — Phase 0 contract lock added to sprint breakdown |

---

## Risks

1. **Pydantic model changes** — Two existing models change (`PipelineRunResponse`, `QueryGap`) — both are additive with defaults. New model `ApprovedContentPiece` is greenfield. Read `skills/model-changes.md` before implementation.
2. **Long document embedding** — `final.md` can be 2000–5000 words. Use same chunking pattern from s1 (`chunk_text()`) — split to ~2000-word chunks, embed each, take mean embedding.
3. **s6 cluster recomputation correctness** — When patching specific queries, the cluster-level SPA t-test requires ALL queries in the cluster (not just the patched ones). Must load all QueryGap entries for the cluster, use updated values for patched queries and original values for unpatched ones.
4. **Cache invalidation** — `gap_data_service.py` and `content_data_service.py` use mtime-based caches. Since content-refresh overwrites `analysis.json`, `gap_analysis_complete.json`, and visualization files, caches will self-invalidate on mtime change. No manual cache clearing needed.
5. **Concurrent refresh + regular run** — If a `gap_analysis` run and a `content-refresh` run start simultaneously for the same company, they'll conflict on the slug lock (both use `"gap_analysis"` pipeline, same effective_slug). This is the correct behavior — they should not run concurrently.

---

## Verification

```bash
# 1. Confirm no regressions
pytest tests/ -v --tb=short

# 2. Feature 1 — skip guard (heizen already has artifacts)
curl -sX POST http://localhost:8000/api/v1/gap-analysis/start \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"heizen","domain":"heizen.io","force_rerun":false}' | jq .
# Expect: {"already_exists":true,"run_id":"<last-task-id>","status":"already_exists",...}

curl -sX POST http://localhost:8000/api/v1/gap-analysis/start \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"heizen","domain":"heizen.io","force_rerun":true}' | jq .
# Expect: 202 with new task_id

# 3. Feature 2 — content refresh (heizen already has approved content)
curl -sX POST http://localhost:8000/api/v1/gap-analysis/content-refresh \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"heizen","brief_ids":["brief-001"]}' | jq .
# Expect: 202 with task_id

curl -N http://localhost:8000/api/v1/tasks/{task_id}/events
# Expect events: pipeline_start → embedding_content → patching_analysis → generating_visualizations → generating_report → completed

# 4. Verify artifacts updated
jq '.gaps[0].best_company_similarity' artifacts/gap_analysis/heizen/analysis.json
# Compare with original — should be equal or higher for targeted queries
jq '.gaps[0].best_content_piece_id' artifacts/gap_analysis/heizen/analysis.json
# Should be "brief-001" if content improved similarity

jq '.points[] | select(.type=="approved_content")' \
  artifacts/gap_analysis/heizen/visualizations/embedding_projections_umap.json
# Should have points with type="approved_content"

# 5. Validate brief_id path traversal rejection
curl -sX POST http://localhost:8000/api/v1/gap-analysis/content-refresh \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"heizen","brief_ids":["../evil"]}' | jq .status_code
# Expect: 422

# 6. Run all tests
pytest tests/ -v
```

---

## Sprint Breakdown (recommended)

**Phase 0 — Contract Lock (no logic, highest priority):**
- Add `"approved_content"` to `EmbeddingPoint.type` Literal in `api/schemas/content_data.py`
- Add `already_exists: bool`, `message: Optional[str]` to `PipelineRunResponse`
- Add `best_content_piece_id: Optional[str]`, `content_refresh_at: Optional[str]` to `QueryGap` (all defaults=None)
- Update `tests/api/test_content_data.py` and `tests/api/test_task_models.py` for new fields
- 5 files, ~5 tests, zero logic risk — locks the contracts before internals work

**Phase 1 — Feature 1: Pipeline Guard (~4 files, ~10 tests):**
- `force_rerun` + dual-sentinel existence check + scope-aware `last_run_at`
- Guards for both gap_analysis and research start endpoints

**Phase 2 — Feature 2 Core (~5 files, ~18 tests):**
- `ApprovedContentPiece` model
- `run_content_refresh()` + `embed_content_pieces()` in pipeline.py
- `patch_analysis_with_content_pieces()` in s6_analyze.py

**Phase 3 — Feature 2 Visualization + API (~5 files, ~12 tests):**
- s7 `content_pieces` param + `"approved_content"` point type in HTML/JSON
- New `/content-refresh` endpoint + `ContentRefreshRequest` schema
- `run_content_refresh_task()` in runner.py
- Frontend umap-scatter.tsx update for new type

**Total: ~19 files, ~45 new tests across 4 phases.**
