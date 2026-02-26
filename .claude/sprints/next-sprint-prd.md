# PRD — Next Sprint
**Status:** DRAFT — Pending Aryan Approval
**Date:** 2026-02-27
**Preceding Sprint:** pipeline-guard (900 tests, Feature 1 complete)
**Branch:** feat/next (to be created from feat/front-back)

---

## Sprint Options

Two possible sprint directions. Pick one or sequence them.

---

## Option A — Review-Issues Cleanup Sprint

**Goal:** Burn down the remaining deferred review findings from `.claude/sprints/v1/review-findings-deferred.md`. Harden the API layer before any external usage.

**Effort estimate:** Small (1 session). These are well-understood, scoped fixes.

### Tasks (Priority Order)

#### P0 — Test Regression Fix (from pipeline-guard self-review)

**T-guard-fix-1:** Fix `test_start_partial_stages_only_skip_if_requested_stages_present` in `tests/api/test_research.py`
- Add `mock_research_runner` fixture to the test
- Change `assert resp.status_code != 200` → `assert resp.status_code == 202`
- Eliminates `RuntimeWarning: The executor did not finishing joining its threads` background task leak
- **Scope:** 1 test, 1 file
- **Risk:** None

#### P1 — API Correctness

**T-w7-pagination:** Fix W7 — page > total_pages allowed
- `api/services/gap_data_service.py:756`
- Clamp: `page = max(1, min(page, max(1, total_pages)))`
- Add 1 test: `test_page_beyond_total_pages_returns_last_page`

**T-w4-sort-literal:** Fix W4 — `sort_dir` accepts any string
- `api/routers/gap_data.py:54`
- Change `sort_dir: str = "asc"` → `sort_dir: Literal["asc", "desc"] = "asc"`
- FastAPI auto-validates Query params — this gives free 422 on invalid values
- Add 1 test: `test_invalid_sort_dir_returns_422`

**T-w5-classification-sort:** Fix W5 — classification sort is alphabetical, not severity-ranked
- `api/services/gap_data_service.py:753`
- Add severity rank mapping: `significant_gap=4, gap_to_close=3, roughly_equal=2, company_wins=1`
- Sorting by `classification` then uses numeric rank, not lexicographic order

#### P2 — Guard Code Quality (from pipeline-guard self-review)

**T-guard-fix-2:** Deduplicate slug in `_research_stages_exist`
- `api/routers/research.py`
- `slugs = list(dict.fromkeys([s for s in [effective_slug, company_slug] if s]))`
- Prevents redundant double-check on company-level runs
- No test needed (behavior unchanged)

**T-guard-fix-3:** Move `force_rerun` field adjacent to other fields in schemas
- `api/schemas/common.py`
- Visual cleanup only — no behavior change

#### P3 — Deferred Warnings (if time permits)

**T-w1-jwt-docs:** W1 — Document `JWT_SECRET_KEY` as required for stable auth across restarts
- Add to `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md` §11 (Config & Env)
- Add `.env.example` entry with note about persistence

**T-w9-cache-size:** W9 — Reduce `_CACHE_MAX_ENTRIES` risk
- Monitor or reduce from 10 to 5 entries in both service files
- OR add comment explaining 200MB theoretical ceiling

### Tests Added (Option A)
~5-7 new tests. Total would reach ~907.

---

## Option B — Feature 2: Content-Gap Integration

**Goal:** When `/gap-analysis/start` returns `already_exists=True`, allow the frontend to immediately launch content generation using the existing gap analysis. One HTTP call goes from "analyze" to "generate content."

**Full design:** Preserved in `.claude/plans/cozy-twirling-mochi.md`

**Effort estimate:** Medium (2-3 sessions). Multi-file, multi-service change.

### High-Level Scope

1. **`POST /api/v1/companies/{slug}/gap-analysis/generate-content`**
   - Takes: `company_name`, `domain`, `product_slug` (optional), `max_briefs`, `auto_approve`, `force_rerun`
   - Discovers latest gap analysis artifacts for the slug
   - Launches content generation pipeline with `gap_slug` sourced from artifacts
   - Returns: `PipelineRunResponse` with `pipeline="content"`

2. **`ContentStartRequest` updates**
   - Add `gap_slug: Optional[str] = None` field — lets caller specify which gap analysis to use
   - When provided, content runner reads `artifacts/gap_analysis/{gap_slug}/gap_analysis_complete.json` directly instead of running gap analysis first

3. **Runner wiring**
   - `run_content_pipeline_task()` in `api/tasks/runner.py` — read gap analysis artifacts when `gap_slug` is set
   - Pass `GapReport` (or equivalent) into `run_content_generation()` as context

4. **Service discovery helper**
   - `api/services/gap_data_service.py` — add `find_latest_gap_slug(company_slug, product_slug) -> Optional[str]`
   - Returns the most-recent `effective_slug` that has complete gap analysis artifacts

### Design Considerations
- Reuse existing `ContentStartRequest` (add `gap_slug` field, backward-compat with default `None`)
- This is an **additive** endpoint — the existing `/content/start` is unchanged
- Frontend flow: `gap-analysis/start` returns `already_exists=True` → frontend shows "Generate Content from Analysis" button → calls new endpoint

### Tests (Option B)
~20-25 new tests:
- Service: `find_latest_gap_slug` (3 tests)
- Runner: gap_slug wiring (4 tests)
- Router: new endpoint (8 tests)
- Integration: full chain (2 tests)

Total would reach ~920-925.

---

## Option C — Hybrid Sprint

**Goal:** Do Option A (cleanup) THEN start Option B Feature 2.

**Recommended sequencing:**
1. T-guard-fix-1 (test fix, 15 min)
2. T-w7 + T-w4 + T-w5 (API correctness, 1 hour)
3. Feature 2 scoping and planning (with Codex plan review)
4. Feature 2 implementation

---

## Recommendation

**Start with Option A** — clean up the known issues before expanding scope. The test regression fix is blocking (RuntimeWarning in CI). The W7/W4/W5 fixes are small and increase production confidence. Then kick off Feature 2 in the same session or the next.

---

## Constraints (Unchanged from Previous Sprints)

- Backward compatibility with existing artifacts
- All Pydantic fields must have defaults
- Raw SDK clients for LLM calls (no LangChain wrappers)
- LangGraph >=1.0 interrupt model: check `__interrupt__` in result dict
- Frontend renders its own charts from raw JSON (not iframes)
- No Supabase yet — filesystem artifacts are source of truth
- `email-validator` required for auth models (`EmailStr`)
- Password `min_length=8`, `max_length=128` enforced in `LoginRequest` and `RegisterRequest`
- Double-underscore separator for effective slugs: `{company}__{product}`
- Product prompt guard: inject only when `product_slug AND product_name` both set

---

## Pre-Sprint Checklist

Before starting work:
- [ ] Aryan approves sprint direction (A, B, or C)
- [ ] Read `_memory/` files (progress, failures, decisions, context)
- [ ] Run `pytest tests/ -v` — confirm 900 passing
- [ ] Create feature branch: `feat/cleanup` or `feat/content-gap`
