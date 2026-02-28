# Pending Backlog

> **Last synced:** 2026-02-28 (post site-audit sprint)
> **Total items:** 27

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
- **Status:** ✅ RESOLVED 2026-02-28 (T5 — cleanup-taskstore sprint)

### PB-7: Classification sort is alphabetical, not by severity (W5)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** Add severity-rank mapping: `significant_gap=4, gap_to_close=3, roughly_equal=2, company_wins=1`.
- **Files affected:** `api/services/gap_data_service.py:753`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-28 (T5 — cleanup-taskstore sprint)

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
- **Status:** ✅ RESOLVED 2026-02-28 (T5 — cleanup-taskstore sprint)

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
- **Status:** ✅ RESOLVED 2026-02-28 (T3 — cleanup-taskstore sprint, consolidated to `core.auth.utils.domain.derive_slug`)

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

### PB-26: Register endpoint docstring still says domain auto-join works (W1)
- **Source:** Combined review (route-protection sprint) — Claude + Codex
- **Date added:** 2026-02-27
- **Description:** `auth.py:32` docstring still mentions "If company_domain matches an existing company, user joins as 'member'." — this is stale after Codex C1 hardening.
- **Files affected:** `api/routers/auth.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-28 (T2 — cleanup-taskstore sprint)

### PB-27: Login company lookup always fails on company_slug key — dead code path (W2)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** `auth.py:98` calls `get_company_by_slug(user.get("company_slug", ""))` but UserProfile dict never has `company_slug` key (it's `company_id`). Always falls through to the company_id loop fallback. Remove the dead code path.
- **Files affected:** `api/routers/auth.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-28 (T2 — cleanup-taskstore sprint, replaced with `get_company_by_id`)

### PB-28: Stream tokens not single-use (W3)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** `store.py:494` — plan said stream tokens would be single-use but they are not. A leaked token can be replayed for 5 minutes.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing

### PB-29: Stream tokens not task-scoped (W4)
- **Source:** Combined review (route-protection sprint) — Codex
- **Date added:** 2026-02-27
- **Description:** `store.py:505` — stream token has no `task_id` claim. A leaked token accesses any task in the tenant's company for 5 minutes.
- **Files affected:** `api/auth/store.py`, `api/routers/events.py`
- **Blocked by:** nothing

### PB-30: Invite codes in-memory only — lost on restart (W5)
- **Source:** Combined review (route-protection sprint) — Claude + Codex
- **Date added:** 2026-02-27
- **Description:** `store.py:396` uses `hasattr(self, "_invites")` pattern with in-memory dict. Invites are lost on server restart.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing

### PB-31: `require_tenant` uses slug comparison, not UUID (W6)
- **Source:** Combined review (route-protection sprint) — Claude (Codex I2)
- **Date added:** 2026-02-27
- **Description:** `dependencies.py:94` compares URL slug to token's company_slug. Should ideally compare company UUIDs for stronger guarantee.
- **Files affected:** `api/auth/dependencies.py`
- **Blocked by:** nothing

### PB-32: DRY — tenant isolation pattern copy-pasted ~10 times across routers (W7)
- **Source:** Combined review (route-protection sprint) — Claude + Codex
- **Date added:** 2026-02-27
- **Description:** `require_tenant` and `require_company_access` exist but some routers still inline slug checks. Consolidate.
- **Files affected:** Multiple routers
- **Blocked by:** nothing

### PB-33: JWT_SECRET_KEY enforcement depends on ENVIRONMENT env var naming (W8)
- **Source:** Combined review (route-protection sprint) — Codex
- **Date added:** 2026-02-27
- **Description:** `store.py:123` — environment check relies on `ENVIRONMENT` env var being exactly "development" or "test". Not documented anywhere.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing

### PB-34: /me endpoint doesn't use require_auth dependency (I1)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** `auth.py:131` — `/me` endpoint manually reads `request.state.user_id` instead of using `Depends(require_auth)`. Misses `is_active` check.
- **Files affected:** `api/routers/auth.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-28 (T1 — SECURITY — cleanup-taskstore sprint)

### PB-35: Stale docstrings/comments still reference grace-mode (I2)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** Multiple files still reference "grace mode" auth which was replaced by default-deny middleware.
- **Files affected:** Multiple
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-28 (T2 — cleanup-taskstore sprint)

### PB-36: Authorization header check case-sensitive — lowercase only (I3)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** `middleware.py:59` — only checks for `authorization` header (lowercase). RFC says headers are case-insensitive.
- **Files affected:** `api/auth/middleware.py`
- **Blocked by:** nothing

### PB-37: No test for invite code reuse after redemption (I4)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** Now covered by TestC5InviteRaceCondition.test_invite_code_single_use.
- **Status:** ✅ RESOLVED 2026-02-27 (security-fixes sprint)

### PB-38: Artifact company listing scans global tree then filters — O(N tenants) (I5)
- **Source:** Combined review (route-protection sprint) — Claude
- **Date added:** 2026-02-27
- **Description:** `artifacts.py:89` — scans all companies then filters to user's. Acceptable for <100 companies, but won't scale.
- **Files affected:** `api/routers/artifacts.py`
- **Blocked by:** nothing

### PB-39: HITL test_revise_loops_back_to_agent failing (pre-existing)
- **Source:** Discovered during security-fixes test run
- **Date added:** 2026-02-27
- **Description:** `tests/api/test_hitl_interrupt_resume.py::TestResumeFlow::test_revise_loops_back_to_agent` — fails on assert not `_has_interrupt(r3)`. Pre-existing, not caused by security fixes.
- **Files affected:** `tests/api/test_hitl_interrupt_resume.py`
- **Blocked by:** nothing

### PB-40: Phase 1D — API Key Configuration (deferred by design)
- **Source:** Settings-knowledge-docs sprint — intentionally deferred
- **Date added:** 2026-02-27
- **Description:** Encrypted per-company API keys (OpenAI, Anthropic, Perplexity, Google, Langfuse). RuntimeConfig passthrough (not env override) + encryption at rest (Fernet/KMS) + masked reads. Pre-YC, we run pipelines with our own keys.
- **Files affected:** `api/auth/store.py`, `api/routers/settings.py`, `api/tasks/runner.py`, new `api/services/api_key_service.py`
- **Blocked by:** nothing

### PB-41: update_pipeline_defaults silently ignores unknown kwargs (W2)
- **Source:** Settings-knowledge-docs sprint self-review
- **Date added:** 2026-02-27
- **Description:** `update_pipeline_defaults(**kwargs)` passes through Pydantic model_validate which silently drops unknown fields. A typo like `max_crawl_page` (missing 's') is silently ignored.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing

### PB-42: _save_metadata doesn't create parent directory (W4)
- **Source:** Settings-knowledge-docs sprint self-review
- **Date added:** 2026-02-27
- **Description:** `save_metadata()` in `knowledge_doc_metadata.py` writes to `_metadata.json` but doesn't create the parent directory. Works because upload creates it first, but `mark_documents_embedded()` could fail if called on a non-existent directory.
- **Files affected:** `core/shared_tools/knowledge_doc_metadata.py`
- **Blocked by:** nothing

### PB-43: No pagination on settings team list and knowledge docs list (W6)
- **Source:** Settings-knowledge-docs sprint self-review
- **Date added:** 2026-02-27
- **Description:** GET `/settings/team` and GET `/knowledge-docs` return all items without pagination. Acceptable for small teams/doc counts but won't scale.
- **Files affected:** `api/routers/settings.py`, `api/routers/knowledge_docs.py`
- **Blocked by:** nothing

### PB-44: Knowledge doc upload content_type inferred from extension only
- **Source:** Settings-knowledge-docs sprint self-review
- **Date added:** 2026-02-27
- **Description:** MIME type is determined by file extension mapping, not by inspecting actual file content. A renamed `.txt` file with PDF content would be stored with wrong content_type.
- **Files affected:** `api/services/knowledge_doc_service.py`
- **Blocked by:** nothing

---

## Resolved

### PB-1: `update_company` allows overwriting immutable fields ✅ RESOLVED 2026-02-26
- **Resolved by:** T-review-action-items (P0 C2/C5) — added `_COMPANY_MUTABLE_FIELDS` + `_PRODUCT_MUTABLE_FIELDS` allowlists

### PB-6: `sort_dir` accepts any string value ✅ RESOLVED 2026-02-28
- **Resolved by:** T5 (cleanup-taskstore sprint) — changed to `Literal["asc", "desc"]`

### PB-7: Classification sort is alphabetical ✅ RESOLVED 2026-02-28
- **Resolved by:** T5 (cleanup-taskstore sprint) — added `_CLASSIFICATION_RANK` severity mapping

### PB-9: Pagination allows `page > total_pages` ✅ RESOLVED 2026-02-28
- **Resolved by:** T5 (cleanup-taskstore sprint) — added page clamping in both JSON and DB paths

### PB-16: Unused `Field` import in auth/models.py ✅ FALSE POSITIVE
- **Resolved by:** Verified — `Field` IS used on lines 179 (InviteRequest) and 193 (JoinRequest)

### PB-17: `base64` imported inside method ✅ FALSE POSITIVE
- **Resolved by:** Verified — top-level import in `tokens.py:12`

### PB-18: `_derive_slug` duplicated ✅ RESOLVED 2026-02-28
- **Resolved by:** T3 (cleanup-taskstore sprint) — consolidated to `core.auth.utils.domain.derive_slug`

### PB-26: Register docstring stale ✅ RESOLVED 2026-02-28
- **Resolved by:** T2 (cleanup-taskstore sprint) — updated docstring

### PB-27: Login dead code path ✅ RESOLVED 2026-02-28
- **Resolved by:** T2 (cleanup-taskstore sprint) — replaced with `get_company_by_id`

### PB-34: /me endpoint missing require_auth ✅ RESOLVED 2026-02-28
- **Resolved by:** T1 SECURITY (cleanup-taskstore sprint) — added `Depends(require_auth)`

### PB-35: Stale grace-mode docstrings ✅ RESOLVED 2026-02-28
- **Resolved by:** T2 (cleanup-taskstore sprint) — updated to "default-deny ASGI middleware"

### PB-37: No test for invite code reuse ✅ RESOLVED 2026-02-27
- **Resolved by:** security-fixes sprint — TestC5InviteRaceCondition.test_invite_code_single_use
