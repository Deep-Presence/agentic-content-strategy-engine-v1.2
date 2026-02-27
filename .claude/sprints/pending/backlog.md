# Pending Backlog

> **Last synced:** 2026-02-27
> **Total items:** 15

## Critical (Fix Before Production)

### PB-1: `update_company` allows overwriting `id`, `created_at`, `slug` via `**kwargs`
- **Source:** Phase 1+2 code review (C5) — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** No allowlist on `setattr` in `update_company()` — caller can corrupt internal state. Needs allowlist of mutable fields. Note: `update_company` and `update_product` now have `_COMPANY_MUTABLE_FIELDS` / `_PRODUCT_MUTABLE_FIELDS` allowlists (resolved by T-review-action-items), but verify coverage is complete.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-26 (T-review-action-items P0 C2/C5)

## High Priority

### PB-2: `_secret_key` regenerated on restart if `JWT_SECRET_KEY` not set (W1)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Auth tokens become invalid on server restart unless `JWT_SECRET_KEY` env var is set. Document requirement or add stable dev default.
- **Files affected:** `api/auth/store.py:109`
- **Blocked by:** nothing

### PB-3: Token expiry test race condition (W2)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Use `expires_hours=-1` in tests, or change comparison to `>=`.
- **Files affected:** `api/auth/store.py:336`
- **Blocked by:** nothing

### PB-4: `BaseHTTPMiddleware` may break SSE streaming (W3)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Exclude `/events` path from logging middleware, or use pure ASGI middleware.
- **Files affected:** `api/app.py:54`
- **Blocked by:** nothing
- **Note:** Partially addressed — SSE path exclusion added in T-review-action-items (M3), but still using BaseHTTPMiddleware.

### PB-5: No rate limiting on `/register` (W8)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Add simple rate limiter (slowapi or custom) before real usage.
- **Files affected:** `api/routers/auth.py`
- **Blocked by:** nothing

## Medium Priority

### PB-6: `sort_dir` accepts any string value (W4)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Use `Literal["asc", "desc"]` type annotation.
- **Files affected:** `api/routers/gap_data.py:54`
- **Blocked by:** nothing

### PB-7: Classification sort is alphabetical, not by severity (W5)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Add severity-rank mapping: `significant_gap=4, gap_to_close=3, roughly_equal=2, company_wins=1`.
- **Files affected:** `api/services/gap_data_service.py:753`
- **Blocked by:** nothing

### PB-8: `company_avg` always 0.0 in signal averages (W6)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Requires s1 pipeline enhancement to crawl company pages for structural signals. Major work.
- **Files affected:** `api/services/gap_data_service.py:285`
- **Blocked by:** s1 pipeline enhancement

### PB-9: Pagination allows `page > total_pages` (W7)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Clamp `page = min(page, total_pages)` or return 400 for out-of-range.
- **Files affected:** `api/services/gap_data_service.py:756`
- **Blocked by:** nothing

### PB-10: Enriched citations ~20MB cached x 10 = 200MB memory risk (W9)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Monitor, reduce `_CACHE_MAX_ENTRIES`, or add size-based eviction.
- **Files affected:** `api/services/gap_data_service.py:131`
- **Blocked by:** nothing

### PB-11: Fix sync/async inconsistency — `get_research_status` and `get_content_status` use `def` instead of `async def`
- **Source:** Code review 2026-02-17 (T-api-cleanup-3)
- **Date added:** 2026-02-17
- **Description:** Gap analysis uses `async def` but research and content use sync `def`. Inconsistent.
- **Files affected:** `api/routers/research.py`, `api/routers/content.py`
- **Blocked by:** nothing

### PB-12: Add runner-level tests for `produced_artifacts` in research and content runners
- **Source:** Code review 2026-02-17 (T-api-cleanup-4)
- **Date added:** 2026-02-17
- **Description:** Only gap_analysis runner has this test currently.
- **Files affected:** `tests/api/`
- **Blocked by:** nothing

### PB-13: Add `max(1, concurrency)` guard in s4_enrich_citations
- **Source:** Codex review 2026-02-18 (T-sso-followup-1)
- **Date added:** 2026-02-18
- **Description:** Prevent zero-concurrency edge case.
- **Files affected:** `core/gap_analysis/steps/s4_enrich_citations.py`
- **Blocked by:** nothing

### PB-14: Add try/except around `_cosine_similarity` for dimension mismatch resilience
- **Source:** Codex review 2026-02-18 (T-sso-followup-2)
- **Date added:** 2026-02-18
- **Description:** Protect s6_analyze from embedding dimension mismatch.
- **Files affected:** `core/gap_analysis/steps/s6_analyze.py`
- **Blocked by:** nothing

## Low Priority / Nice to Have

### PB-15: Test Playwright fallback on carta.com
- **Source:** Sprint v3-async (T-async-13)
- **Date added:** 2026-02-15
- **Description:** Run step 1 on carta.com to verify Playwright + Wayback fallback works.
- **Files affected:** none (manual testing)
- **Blocked by:** nothing

### PB-16: Unused `Field` import in `api/auth/models.py:11` (I1)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Cleanup unused import.
- **Files affected:** `api/auth/models.py`
- **Blocked by:** nothing

### PB-17: `base64` imported inside method in `api/auth/store.py:343` (I2)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Move to module level.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing

### PB-18: `_derive_slug` duplicated across auth store and content router (I3)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Extract to shared utility.
- **Files affected:** `api/auth/store.py:96`, `api/routers/content.py:26`
- **Blocked by:** nothing

### PB-19: No test for `normalize_domain` with port numbers (I4)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Test `ramp.com:8080` case.
- **Files affected:** `tests/api/test_registration.py`
- **Blocked by:** nothing

### PB-20: No test for slug collision in registration (I5)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Two companies same name, different domains.
- **Files affected:** `tests/api/test_registration.py`
- **Blocked by:** nothing

### PB-21: Cache eviction is FIFO not LRU (I7)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Consider LRU if cache hit patterns warrant it.
- **Files affected:** `api/services/gap_data_service.py:67`
- **Blocked by:** nothing

### PB-22: `gap_data_service` raises `HTTPException` directly from service layer (I8)
- **Source:** Phase 1+2 code review
- **Date added:** 2026-02-25
- **Description:** Couples service to FastAPI. Consider raising domain exceptions instead.
- **Files affected:** `api/services/gap_data_service.py`
- **Blocked by:** nothing

### PB-23: Clean up stale `test_name` field in S8 test fixture (T-sso-followup-3)
- **Source:** Codex review 2026-02-18
- **Date added:** 2026-02-18
- **Description:** SpaResult uses 'cspa' but Codex flagged as non-standard.
- **Files affected:** `tests/gap_analysis/steps/test_s8_generate_report.py`
- **Blocked by:** nothing

### PB-24: Reddit HIL — ZERO test coverage
- **Source:** Known tech debt (CLAUDE.md)
- **Date added:** 2026-02-27
- **Description:** PRAW mocking, webhook delivery, graph state machine all untested.
- **Files affected:** `core/reddit_hil/`, `tests/reddit_hil/`
- **Blocked by:** nothing

### PB-25: Content-Gap Integration (Feature 2 from pipeline-guard sprint)
- **Source:** Sprint pipeline-guard — deferred by design
- **Date added:** 2026-02-27
- **Description:** Auto-trigger content generation when gap analysis completes. Full design in `.claude/plans/cozy-twirling-mochi.md`.
- **Files affected:** `api/tasks/runner.py`, `api/routers/gap_analysis.py`, `api/routers/content.py`
- **Blocked by:** nothing

---

## Resolved

### PB-1: `update_company` allows overwriting immutable fields ✅ RESOLVED 2026-02-26
- **Resolved by:** T-review-action-items (P0 C2/C5) — added `_COMPANY_MUTABLE_FIELDS` + `_PRODUCT_MUTABLE_FIELDS` allowlists
