# Sprint: Content Engine Pipeline v1.3

**Date:** 2026-03-01 — 2026-03-02 (COMPLETE)
**Branch:** `feat/front-back`
**Goal:** Restructure the 4-stage content engine into a 6-stage pipeline with two-phase context loading, Brief Builder agent, 3 HITL checkpoints, LiteLLM for model abstraction, E-E-A-T evaluation, and dual feedback loops.

---

## Problem Statement

The v1.0 content engine receives the **full** gap analysis output (80-120K tokens) in a single pass to the Strategic Planner. This creates a context explosion problem — the planner can't effectively triage 200 queries when they all arrive with full exemplar context at once.

v1.3 solves this by:
1. **Two-phase context loading** — lightweight scorecard (~11K tokens) for triage, full context only for approved topics
2. **New Brief Builder agent** — dedicated content architect producing rich blueprints from deep exemplar analysis
3. **Three HITL checkpoints** — topic approval, brief approval, final review (up from 1)
4. **LiteLLM** for all LLM calls — model abstraction, easy benchmarking, provider switching
5. **E-E-A-T** as 5th evaluation dimension
6. **Dual feedback loops** — section-level edits vs. major direction change

---

## Architecture

```
AUTONOMOUS MODE:
  Gap Analysis Output → [Stage 0: Entry Router]
    → [Stage 1: Strategic Planner (scorecard ~11K tokens)] → HITL-1: Topic Approval
    → [Stage 2: Brief Builder (full context, per-topic)] → HITL-2: Brief Approval
    → [Stage 3: Workers (outliner → drafter → enricher → formatter)]
    → [Stage 4: Evaluator (5 dimensions + dual feedback loops)]
    → [Stage 5: HITL-3: Final Review] → Publish

MANUAL MODE (future — D3):
  User Prompt → Single-Query Gap Analysis (s3-s6)
    → [Stage 2: Brief Builder] → HITL-2 → Stage 3 → Stage 4 → Stage 5 → Publish
```

---

## Implementation Phases

### Phase A: Foundation (COMPLETE)

| Task | File | Status |
|------|------|--------|
| A1: v1.3 Pydantic models | `core/models/content_generation_v13.py` | Done |
| A2: Context router | `core/content_engine/context_router.py` | Done |
| A3: LiteLLM client wrapper | `core/content_engine/llm_client.py` | Done |
| A4: LangSmith tracing | `core/content_engine/tracing_v13.py` | Done |
| A5: Settings additions | `core/config/settings.py` | Done |

### Phase B: Agents (COMPLETE)

| Task | File | Status |
|------|------|--------|
| B1: Strategic Planner | `core/content_engine/strategic_planner.py` + `prompts/strategic_planner_prompts.py` | Done |
| B2: Brief Builder | `core/content_engine/brief_builder.py` + `prompts/brief_builder_prompts.py` | Done |
| B3: E-E-A-T Judge | `core/content_engine/evaluator/eeat_judge.py` + `prompts/eeat_judge_prompts.py` | Done |

### Phase C: Graph + Orchestrator (COMPLETE)

| Task | File | Status |
|------|------|--------|
| C1: LangGraph v1.3 | `core/content_engine/graph_v13.py` | Done |
| C2: Evaluator loop updates | `core/content_engine/evaluator/loop.py` | Done |
| C3: Pipeline orchestrator | `core/content_engine/pipeline_v13.py` | Done |

### Phase D: API + Workers (COMPLETE)

| Task | File | Status |
|------|------|--------|
| D1: API schemas + router | `api/routers/content_v13.py`, `api/schemas/content_v13.py` | Done |
| D2: Worker LiteLLM migration | `outliner.py`, `drafter.py`, `fact_enricher.py`, `formatter.py`, `style_judge.py`, `factual_judge.py` | Done |
| D3: Manual mode entry path | Deferred to PB-45 — inline `WorkerQueryContext` sufficient for v0 | Done (deferred) |
| D4: DB persistence for new stages | `core/content_engine/persistence.py` (2 new funcs), `pipeline_v13.py` (wired) | Done (+12 tests) |

### Phase E: Polish (COMPLETE)

| Task | File | Status |
|------|------|--------|
| E1: Documentation update | `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md` §7, §15, §21 | Done |
| E2: Integration testing | 12 test files, 240+ new tests, 5 router bugs found+fixed via TDD | Done (+242 tests) |

---

## Key Design Decisions

1. **v1.0 coexistence** — Old pipeline (`/content/start`) preserved as-is. v1.3 runs via `/content/v13/start`. Zero downtime risk.

2. **ContentBlueprint extends ContentBrief** — Agent 2's output is a subclass. All existing workers accept it transparently without type hint changes.

3. **Workers modified in-place** — All 6 workers/judges use `llm_call()` from `llm_client.py` instead of direct SDK calls. Shared between v1.0 and v1.3 pipelines.

4. **`_ensure_litellm_model()` auto-prefix** — Maps `claude-*` → `anthropic/`, `sonar*` → `perplexity/`, `gpt-*` → `openai/`, `gemini-*` → `google/`. Backward-compatible with existing settings.

5. **Dual feedback routing** — `classify_feedback()` returns `pass`, `section_level`, or `major_change`. Section-level is default. Major change only from HITL-3 human rejection or semantic score < 0.5.

6. **Targeted revision** — Failed dimensions map to specific workers: structural→formatter, style/eeat→drafter, factual→enricher, semantic→full chain.

7. **Prompts stay in Python files** — LangSmith used for tracing/playground/re-run only, not runtime prompt pulls.

---

## Files Created (14 new)

- `core/models/content_generation_v13.py`
- `core/content_engine/context_router.py`
- `core/content_engine/llm_client.py`
- `core/content_engine/tracing_v13.py`
- `core/content_engine/strategic_planner.py`
- `core/content_engine/brief_builder.py`
- `core/content_engine/evaluator/eeat_judge.py`
- `core/content_engine/graph_v13.py`
- `core/content_engine/pipeline_v13.py`
- `core/content_engine/prompts/strategic_planner_prompts.py`
- `core/content_engine/prompts/brief_builder_prompts.py`
- `core/content_engine/prompts/eeat_judge_prompts.py`
- `api/routers/content_v13.py`
- `api/schemas/content_v13.py`

## Files Modified (9)

- `core/config/settings.py` — LiteLLM model IDs, LangSmith config fields
- `core/content_engine/workers/outliner.py` — `AsyncAnthropic` → `llm_call`
- `core/content_engine/workers/drafter.py` — `AsyncAnthropic` → `llm_call` (both generate + revise)
- `core/content_engine/workers/fact_enricher.py` — `httpx` → `llm_call` (full rewrite)
- `core/content_engine/workers/formatter.py` — `AsyncAnthropic` → `llm_call`
- `core/content_engine/evaluator/style_judge.py` — `AsyncAnthropic` → `llm_call`
- `core/content_engine/evaluator/factual_judge.py` — `AsyncAnthropic` → `llm_call`
- `core/content_engine/evaluator/loop.py` — E-E-A-T + dual feedback + targeted revision
- `tests/content_engine/conftest.py` — Mock fixtures updated for `llm_call`

---

## API Endpoints (v1.3)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/content/v13/start` | Launch v1.3 pipeline |
| `GET` | `/api/v1/content/v13/{run_id}/status` | Poll status with checkpoint info |
| `POST` | `/api/v1/content/v13/{run_id}/approve/topics` | HITL-1: topic approval |
| `POST` | `/api/v1/content/v13/{run_id}/approve/briefs` | HITL-2: brief approval |
| `POST` | `/api/v1/content/v13/{run_id}/approve/content` | HITL-3: final review |

---

## Test Status

- **~2235 total tests** (~1843 passed + 135 skipped) with 0 failures (+15 from Phase F security/correctness fixes)
- **329 content engine tests** (57 v1.0 + 272 v1.3) — all passing
- **43 API v1.3 tests** — all passing
- Test fixtures updated to mock `llm_call` instead of `AsyncAnthropic`/`httpx`
- v1.0 planner tests unchanged (still uses `AsyncAnthropic` directly)
- 5 production bugs discovered and fixed via TDD (router signature mismatches, missing Literal value, field reference errors)
- Phase F: 15 regression tests covering H1/H2/H3a/H3b/H5 fixes

---

## Dependencies Added

```
litellm>=1.50
langsmith>=0.2
```

---

---

## Phase F: Security & Correctness Fixes — H1/H2/H3/H5 (COMPLETE 2026-03-02)

Four high-priority bugs found in post-implementation code review, all fixed and tested.

| Fix | Issue | File | Status |
|-----|-------|------|--------|
| H1 | Re-brief context extraction always uses degraded fallback — `isinstance(gap_context, dict)` is always `False` on a Pydantic model | `pipeline_v13.py:284-286` | Done |
| H2 | v1.3 API uses bare `asyncio.create_task()` — bypasses global semaphore, cancellation handle, slug lock | `content_v13.py`, `runner.py` | Done |
| H3a | HITL-1 "retry" falls through as "approve" — planner never re-run with user feedback | `pipeline_v13.py:499-533` | Done |
| H3b | HITL-2 "feedback" stored on blueprint but Agent 2 never re-invoked | `pipeline_v13.py:612-676` | Done |
| H5 | `gap_slug` from request body flows into filesystem path without slug-regex validation — path traversal | `content_v13.py:99,121` | Done |

### Fix Details

**H1** (`pipeline_v13.py`): Replaced `isinstance(gap_context, dict)` guard with direct Pydantic attribute access. `gap_context.query_gap.get("query_id", ...)` extracts the primary query ID; the full `WorkerQueryContext` (exemplars, cluster_spec, gap_content_brief) is passed to `build_briefs_parallel` instead of a minimal `{"query_id": ...}` stub.

**H2** (`runner.py` + `content_v13.py`): Added `run_content_v13_pipeline_task()` to `runner.py` following the exact semaphore + handle + slug-lock pattern used by `run_content_pipeline_task`. Removed the local `_run_v13_pipeline_task` from the router. Router now calls `asyncio.create_task(run_content_v13_pipeline_task(...))` then immediately registers the handle via `task_store.register_task_handle(task.task_id, handle)`.

**H3a** (`pipeline_v13.py`): Added `_MAX_TOPIC_RETRIES = 2` bounded `while` loop after initial HITL-1 checkpoint. On "retry", calls `select_topics(user_feedback=topic_feedback)` and re-presents via a new checkpoint. Exhausted retries fall through to the early-exit path (same as "reject").

**H3b** (`pipeline_v13.py`): Replaced single-pass HITL-2 with a `while True` loop per blueprint. `_MAX_BRIEF_FEEDBACK_RETRIES = 1`. On "feedback", re-runs `build_briefs_parallel` with feedback embedded in `TopicSelection.rationale` (avoids prompt template changes). Uses `getattr(bp, "cluster_name", bp.target_cluster)` since `ContentBrief` has `target_cluster`, not `cluster_name`. Exhausted retries or "reject" break the loop without adding to `approved_blueprints`.

**H5** (`content_v13.py`): Added `_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")`. Validates `body.gap_slug` against regex before path construction. Also asserts `Path.is_relative_to(artifacts_root)` as defense-in-depth. Returns 400 on violation.

### New Tests Added (+15)

| Class | File | Count | Covers |
|-------|------|-------|--------|
| `TestRebriefContextExtraction` | `test_pipeline_v13.py` | 2 | H1 |
| `TestHITL1Retry` | `test_pipeline_v13.py` | 3 | H3a |
| `TestHITL2Feedback` | `test_pipeline_v13.py` | 3 | H3b |
| `TestGapSlugValidation` | `test_content_v13.py` | 6 | H5 |
| `TestTaskHandleRegistration` | `test_content_v13.py` | 1 | H2 |

**Resolved backlog items:** PB-50 (H1), PB-51 (H2), PB-52 (H3), PB-54 (H5)

---

## Remaining Work

All phases complete. Deferred items:
- **PB-45: Full lightweight gap analysis** (s3-s6 reuse) for manual mode entry path — deferred to backlog
- **PB-53 (H4):** Manual mode silently produces zero blueprints when existing gap data present — deferred
- **PB-55–57:** v1.3 tracing imports, graph edit loop guard, audit trail persistence — deferred

## Bugs Found & Fixed via TDD

1. Router used `effective_slug=` instead of `product_slug=` in `create_task()` — `content_v13.py`
2. `PipelineTask.pipeline` Literal missing `content_v13` — `api/tasks/models.py`
3. Router status endpoint referenced non-existent `task.progress` field — `content_v13.py`
4. `submit_approval` received dict instead of string decision — `content_v13.py` (Pydantic ValidationError)
5. `run_hitl_checkpoint` used `wait_for_approval` return value instead of `task.approval_payload` — `graph_v13.py`

## Test Files Created (12)

| File | Test Count |
|------|-----------|
| `tests/content_engine/test_context_router.py` | 25 |
| `tests/content_engine/test_llm_client.py` | 12 |
| `tests/content_engine/test_v13_models.py` | 10 |
| `tests/content_engine/test_strategic_planner.py` | 15 |
| `tests/content_engine/test_brief_builder.py` | 20 |
| `tests/content_engine/test_eeat_judge.py` | 10 |
| `tests/content_engine/test_tracing_v13.py` | 8 |
| `tests/content_engine/test_evaluator_v13.py` | 8 |
| `tests/content_engine/test_graph_v13.py` | 49 |
| `tests/content_engine/test_pipeline_v13.py` | 22 (+8 Phase F: H1, H3a, H3b) |
| `tests/content_engine/test_v13_persistence.py` | 12 |
| `tests/api/test_content_v13.py` | 35 (+7 Phase F: H2, H5) |
