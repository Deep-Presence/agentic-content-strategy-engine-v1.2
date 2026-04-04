# Pending Backlog

> **Last synced:** 2026-03-26 (merge feat/front-back → feat/redis-integration)
> **Total open items:** 31

## Critical (Fix Before Production)

### PB-95: Tenant isolation gap on per-prompt daily tracker endpoints
- **Source:** Codex review of prompt-tracking integration plan
- **Date added:** 2026-04-04
- **Description:** `GET /prompts/{id}/analytics`, `GET /prompts/{id}/answers`, and `GET /prompts/{id}/fanouts` look up by UUID only — no `company_id` JOIN. A user who obtains another tenant's prompt UUID can read their analytics/answers. Low probability (UUIDs are v4, unguessable) but high impact (data leak across tenants).
- **Fix:** Add `company_id` filter to repo queries (`get_responses_for_prompt`, per-prompt analytics path, `list_by_parent`). Thread `company_id` from auth middleware through router → repo.
- **Files affected:** `core/db/repositories/daily_tracker_repo.py`, `api/routers/daily_tracker.py`
- **Blocked by:** nothing

## High Priority

### PB-53: [v1.3-H4] Manual mode can silently produce zero blueprints with existing gap data
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** When `analysis_json` exists in manual mode, `extract_worker_context(["manual-1"])` is called but "manual-1" never matches real gap query_ids. Empty `worker_contexts` → `build_briefs_parallel` returns None for all topics → empty output. Fix: fallback to inline WorkerQueryContext when extraction is empty.
- **Files affected:** `core/content_engine/pipeline_v13.py:635-650`, `core/content_engine/context_router.py:168`
- **Blocked by:** nothing

### PB-55: [v1.3-H6] v1.3 workers/evaluators import Langfuse tracing — LangSmith spans silently degraded
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** `eeat_judge.py` and `evaluator/loop.py` import from `core.content_engine.tracing` (Langfuse v1.0). v1.3 pipeline passes LangSmith `RunTree` spans — incompatible types. Langfuse helpers are no-ops on unrecognized objects → evaluator dimension traces silently dropped.
- **Files affected:** `core/content_engine/evaluator/eeat_judge.py:22`, `core/content_engine/evaluator/loop.py:24`
- **Blocked by:** nothing

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

### PB-89: Stale pipeline_state.json entries on HITL-2 reject / zero-blueprint / exception paths
- **Source:** Codex backend review, Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `core/content_engine/pipeline_v13.py` (_finalize_pipeline, manual mode early returns)
- **Root cause:** `_cleanup_pipeline_state` only cleans brief IDs that made it into the `pieces` list. Briefs rejected at HITL-2, manual/TD zero-blueprint failures, or unhandled exceptions leave stale Phase-0 statuses in `pipeline_state.json` forever.
- **Fix:** Track a `touched_brief_ids` set for all state writes and cleanup in a `finally` block on all exit paths (including error/early-return branches).

### PB-90: Re-brief path writes state for old brief_id but reruns under new brief_id
- **Source:** Codex backend review, Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `core/content_engine/pipeline_v13.py` (Stage 5 rethink), `_rebrief_and_rerun()`
- **Root cause:** `_write_pipeline_state(... [final_content.brief_id], "briefing")` uses the original brief_id, but `_rebrief_and_rerun` generates a new `rebrief-{uuid}` brief_id. Cleanup uses piece IDs only. This orphans stale statuses.
- **Fix:** Either reuse original brief_id for rebrief (`brief_id_overrides=[blueprint.brief_id]`) or explicitly cleanup both old and new IDs.

### PB-91: pipeline_state.json read-modify-write is not process-safe
- **Source:** Codex backend review, Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `core/content_engine/state_helpers.py` (_write_pipeline_state, _cleanup_pipeline_state)
- **Root cause:** Concurrent writers in different processes can lose updates or read partial JSON. Currently single-process (Uvicorn), but will break with multi-process deployment.
- **Fix:** Add file lock (`fcntl.flock`) + atomic write (`write temp` + `os.replace`).

### PB-92: Stage-content API does not expose linked.md / fact_checked.md
- **Source:** Codex backend review, Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `api/services/content_data_service.py` (_STAGE_FILES, _VALID_STAGES)
- **Root cause:** v1.3 dispatcher writes `linked.md` and `fact_checked.md` but the GET `/briefs/{id}/{stage}` endpoint only recognizes legacy stage names (outline, draft, enriched, formatted, eval_history, final).
- **Fix:** Add `linked` and `fact_checked` to `_VALID_STAGES`/`_STAGE_FILES`.

### PB-93: Systematic audit — DbService ↔ filesystem state disconnect
- **Source:** Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `core/services/db_content_data.py` (fixed for `get_briefs`), potentially other DbService methods
- **Root cause:** The "filesystem-first, DB-additive" architecture means pipelines write real-time state to JSON artifacts, but DbService implementations query Postgres, which is only updated at coarser granularity.
- **Fixed so far:** `DbContentDataService.get_briefs()` now overlays `pipeline_state.json`.
- **Remaining work:**
  1. Audit ALL other DbService methods for similar disconnects
  2. Audit `DbTaskStore` for any filesystem-state dependencies
  3. When migrating to Redis-backed TaskStore/state, replace `pipeline_state.json` with Redis pub/sub
  4. Consider writing pipeline status updates to both JSON AND DB simultaneously as an interim fix

### PB-86: Pre-existing test failure — test_persistence.py mock doesn't support await
- **Source:** Discovered during Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `tests/content_engine/test_persistence.py::TestPersistContentPieces::test_happy_path_single_piece`
- **Root cause:** `session2.execute` is a `MagicMock`, not an `AsyncMock`.
- **Fix:** Replace `MagicMock` with `AsyncMock` for the session factory and repo methods.

### PB-87: Pre-existing test failure — tracing_v13 module attribute `_langsmith_available` removed
- **Source:** Discovered during Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `tests/content_engine/test_tracing_v13.py::TestCreatePipelineTrace::test_returns_none_when_disabled`
- **Fix:** Update test to patch the current guard attribute in `tracing_v13.py`.

### PB-88: Pre-existing test failure — tracing_compat patches non-existent `_is_enabled` attribute
- **Source:** Discovered during Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `tests/content_engine/test_tracing_compat.py::TestCreateSpanCompat::test_input_kwarg_alias`
- **Fix:** Update test to use the correct attribute name or remove if obsolete.

### PB-60: [v1.3-M3] Pipeline trace not flushed on error paths
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline_v13.py:969`
- **Blocked by:** nothing

### PB-61: [v1.3-M4] v1.3 `_update_task(progress=...)` maps to nonexistent field
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline_v13.py:434+`, `api/tasks/models.py:41`
- **Blocked by:** nothing

### PB-62: [v1.3-M5] Manual mode skips HITL-2 — undocumented design decision
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline_v13.py:652-661`
- **Blocked by:** nothing

### PB-63: [v1.3] Add missing integration tests for v1.3 failure paths
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `tests/content_engine/`, `tests/api/test_content_v13.py`
- **Blocked by:** nothing

### PB-8: `company_avg` always 0.0 in signal averages (W6)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Files affected:** `api/services/gap_data_service.py:285`
- **Note:** Partially resolved 2026-03-07 — s1 now computes signals. Remaining: aggregate endpoint needs to read `company_page_analysis.json`.

### PB-10: Enriched citations ~20MB cached x 10 = 200MB memory risk (W9)
- **Source:** Phase 1+2 code review — sprint front-back-integration
- **Date added:** 2026-02-25
- **Files affected:** `api/services/gap_data_service.py:131`
- **Blocked by:** nothing

### PB-11: Fix sync/async inconsistency — `get_research_status` and `get_content_status` use `def` instead of `async def`
- **Source:** Code review 2026-02-17
- **Date added:** 2026-02-17
- **Files affected:** `api/routers/research.py`, `api/routers/content.py`
- **Blocked by:** nothing

### PB-12: Add runner-level tests for `produced_artifacts` in research and content runners
- **Source:** Code review 2026-02-17
- **Date added:** 2026-02-17
- **Files affected:** `tests/api/`
- **Blocked by:** nothing

### PB-13: Add `max(1, concurrency)` guard in s4_enrich_citations
- **Source:** Codex review 2026-02-18
- **Date added:** 2026-02-18
- **Files affected:** `core/gap_analysis/steps/s4_enrich_citations.py`
- **Blocked by:** nothing

### PB-14: Add try/except around `_cosine_similarity` for dimension mismatch resilience
- **Source:** Codex review 2026-02-18
- **Date added:** 2026-02-18
- **Files affected:** `core/gap_analysis/steps/s6_analyze.py`
- **Blocked by:** nothing

### PB-64: Crawl-delay enforcement (rate limiting) in site audit crawler
- **Source:** Sprint v3 site-audit-p3-bugfixes
- **Date added:** 2026-03-04
- **Files affected:** `core/site_audit/steps/s1_discover.py`
- **Blocked by:** nothing

### PB-65: `_detect_personas()` reads legacy path only
- **Source:** Phase F Codex review
- **Date added:** 2026-03-06
- **Files affected:** `api/routers/companies.py:56`, `api/services/brand_data_service.py`
- **Blocked by:** nothing

### PB-66: `PersonaStorage.list_persona_paths()` returns unsorted paths
- **Source:** Phase F Codex review
- **Date added:** 2026-03-06
- **Files affected:** `core/research/audience_persona/storage.py:263`
- **Blocked by:** nothing

### PB-67: [DB-M1] `get_latest_by_slug_and_type()` is redundant wrapper
- **Date added:** 2026-03-10
- **Files affected:** `core/db/repositories/research_artifact_repo.py:41-47`

### PB-68: [DB-M2] No input validation on `upsert_artifact()`
- **Date added:** 2026-03-10
- **Files affected:** `core/db/repositories/research_artifact_repo.py`

### PB-69: [DB-M3] TD `list_assignments()` shape divergence
- **Date added:** 2026-03-10
- **Files affected:** `core/services/json_topic_discovery_data.py`, `core/services/db_topic_discovery_data.py`

### PB-70: [DB-M4] JSON VSG `get_guide()` ignores `version` parameter
- **Date added:** 2026-03-10
- **Files affected:** `core/services/json_vsg_data.py`

### PB-71: [DB-M5] Missing multi-tenancy isolation tests
- **Date added:** 2026-03-10
- **Files affected:** `tests/db/test_research_artifact_repo.py`

### PB-72: [DB-M6] DB services return `""` instead of `None` for missing content files
- **Date added:** 2026-03-10
- **Files affected:** `core/services/db_kb_data.py`, `core/services/db_persona_data.py`

### PB-73: [SA-R1] Distributed lock for multi-worker site audit deployment
- **Date added:** 2026-03-10
- **Files affected:** `api/tasks/runner.py`, `api/tasks/store.py`

### PB-74: [SA-C2] Product-scoped read endpoints for site audit
- **Date added:** 2026-03-10
- **Files affected:** `api/routers/site_audit.py`, `core/services/db_site_audit_data.py`

### PB-76: [RO-M6] VSG skip logic never fires — ap_manifest_version never written
- **Date added:** 2026-03-11
- **Files affected:** `core/research/voice_style_guide/pipeline.py`, `core/models/voice_style_guide.py`, `core/research/orchestrator.py`

### PB-77: [RO-M7] Process-local concurrency — slug locks/semaphore lost in multi-worker deployment
- **Date added:** 2026-03-11
- **Files affected:** `api/tasks/store.py`, `core/services/db_task_store.py`, `api/tasks/runner.py`

### PB-75: [SA-DI] Session/service DI lifecycle cleanup
- **Date added:** 2026-03-10
- **Files affected:** `api/dependencies.py`

### PB-94: Proper artifact version listing endpoints (replace client-side filename parsing)
- **Source:** Frontend-backend artifacts integration, 2026-04-04
- **Date added:** 2026-04-04
- **Description:** Currently, version history in the Brand Hub is derived client-side by parsing filenames from `GET /api/v1/artifacts/{type}/{slug}` (which returns all files including manifests, JSON, etc.). Add dedicated endpoints that use `StorageBackend.list_dir()` to discover versions and return structured metadata (version number, date, word count). Endpoints needed: `GET /api/v1/knowledge-base/{slug}/{doc_type}/versions`, `GET /api/v1/voice-style-guide/{slug}/guide/versions`, `GET /api/v1/audience-persona/{slug}/{persona_id}/versions`. Each should return `{ versions: [{ version: int, last_updated: str|null, word_count: int }] }`.
- **Files affected:** `core/research/knowledge_base/storage.py`, `core/research/voice_style_guide/storage.py`, `core/research/audience_persona/storage.py`, `core/services/kb_data.py`, `core/services/vsg_data.py`, `core/services/persona_data.py`, `api/routers/knowledge_base.py`, `api/routers/voice_style_guide.py`, `api/routers/audience_persona.py`
- **Blocked by:** nothing

## Low Priority / Nice to Have

### PB-15: Test Playwright fallback on carta.com
- **Date added:** 2026-02-15
- **Files affected:** none (manual testing)

### PB-19: No test for `normalize_domain` with port numbers (I4)
- **Date added:** 2026-02-25
- **Files affected:** `tests/api/test_registration.py`

### PB-20: No test for slug collision in registration (I5)
- **Date added:** 2026-02-25
- **Files affected:** `tests/api/test_registration.py`

### PB-21: Cache eviction is FIFO not LRU (I7)
- **Date added:** 2026-02-25
- **Files affected:** `api/services/gap_data_service.py:67`

### PB-22: `gap_data_service` raises `HTTPException` directly from service layer (I8)
- **Date added:** 2026-02-25
- **Files affected:** `api/services/gap_data_service.py`

### PB-23: Clean up stale `test_name` field in S8 test fixture
- **Date added:** 2026-02-18
- **Files affected:** `tests/gap_analysis/steps/test_s8_generate_report.py`

### PB-24: Reddit HIL — ZERO test coverage
- **Date added:** 2026-02-27
- **Files affected:** `core/reddit_hil/`, `tests/reddit_hil/`

### PB-25: Content-Gap Integration (auto-trigger content on gap completion)
- **Date added:** 2026-02-27
- **Files affected:** `api/tasks/runner.py`, `api/routers/gap_analysis.py`, `api/routers/content.py`

### PB-28: Stream tokens not single-use (W3)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/store.py`

### PB-29: Stream tokens not task-scoped (W4)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/store.py`, `api/routers/events.py`

### PB-30: Invite codes in-memory only — lost on restart (W5)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/store.py`

### PB-31: `require_tenant` uses slug comparison, not UUID (W6)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/dependencies.py`

### PB-32: DRY — tenant isolation pattern copy-pasted ~10 times across routers (W7)
- **Date added:** 2026-02-27
- **Files affected:** Multiple routers

### PB-33: JWT_SECRET_KEY enforcement depends on ENVIRONMENT env var naming (W8)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/store.py`

### PB-36: Authorization header check case-sensitive — lowercase only (I3)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/middleware.py`

### PB-38: Artifact company listing scans global tree then filters — O(N tenants) (I5)
- **Date added:** 2026-02-27
- **Files affected:** `api/routers/artifacts.py`

### PB-39: HITL test_revise_loops_back_to_agent failing (pre-existing)
- **Date added:** 2026-02-27
- **Description:** `tests/api/test_hitl_interrupt_resume.py::TestResumeFlow::test_revise_loops_back_to_agent` — fails on assert not `_has_interrupt(r3)`. Root cause: `langgraph-checkpoint` v4.0.0 stores `__interrupt__` as a channel write; with `StateGraph(dict)` it bleeds into `state.values` (~15% intermittent failure rate). `StateGraph(TypedDict)` is immune because `__interrupt__` is not a declared field.
- **Files affected:** `tests/api/test_hitl_interrupt_resume.py`, `core/content_engine/graph.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-03-22 — Converted test graph + v1.0 production graph from `StateGraph(dict)` to `StateGraph(TypedDict)`. 20/20 passes (was 3/20 before fix).

### PB-40: Phase 1D — API Key Configuration (deferred by design)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/store.py`, `api/routers/settings.py`, `api/tasks/runner.py`

### PB-41: update_pipeline_defaults silently ignores unknown kwargs (W2)
- **Date added:** 2026-02-27
- **Files affected:** `api/auth/store.py`

### PB-42: _save_metadata doesn't create parent directory (W4)
- **Date added:** 2026-02-27
- **Files affected:** `core/shared_tools/knowledge_doc_metadata.py`

### PB-43: No pagination on settings team list and knowledge docs list (W6)
- **Date added:** 2026-02-27
- **Files affected:** `api/routers/settings.py`, `api/routers/knowledge_docs.py`

### PB-44: Knowledge doc upload content_type inferred from extension only
- **Date added:** 2026-02-27
- **Files affected:** `api/services/knowledge_doc_service.py`

### PB-45: D3 — Full lightweight gap analysis for manual mode
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline_v13.py`

---

## Resolved

### PB-1: `update_company` allows overwriting immutable fields ✅ RESOLVED 2026-02-26
### PB-6: `sort_dir` accepts any string value ✅ RESOLVED 2026-02-28
### PB-7: Classification sort is alphabetical ✅ RESOLVED 2026-02-28
### PB-9: Pagination allows `page > total_pages` ✅ RESOLVED 2026-02-28
### PB-16: Unused `Field` import in auth/models.py ✅ FALSE POSITIVE
### PB-17: `base64` imported inside method ✅ FALSE POSITIVE
### PB-18: `_derive_slug` duplicated ✅ RESOLVED 2026-02-28
### PB-26: Register docstring stale ✅ RESOLVED 2026-02-28
### PB-27: Login dead code path ✅ RESOLVED 2026-02-28
### PB-34: /me endpoint missing require_auth ✅ RESOLVED 2026-02-28
### PB-35: Stale grace-mode docstrings ✅ RESOLVED 2026-02-28
### PB-37: No test for invite code reuse ✅ RESOLVED 2026-02-27
### PB-46: v1.0 pipeline evaluator 3-tuple unpack crash ✅ RESOLVED 2026-03-02
### PB-47: Dispatcher zip mismatch ✅ RESOLVED 2026-03-02
### PB-48: v1.3 approval endpoints missing tenant check ✅ RESOLVED 2026-03-02
### PB-49: Re-brief brief_id collision ✅ RESOLVED 2026-03-02
### PB-50: Re-brief context extraction type-broken ✅ RESOLVED 2026-03-02
### PB-51: v1.3 API bypasses task semaphore ✅ RESOLVED 2026-03-02
### PB-52: HITL-1/HITL-2 dead retry/feedback paths ✅ RESOLVED 2026-03-02
### PB-54: `gap_slug` path traversal ✅ RESOLVED 2026-03-02
### PB-56: Content review graph edit loop bypass ✅ RESOLVED 2026-03-02
### PB-57: `persist_v13_brief_approval()` hardcodes approve ✅ RESOLVED 2026-03-02
### PB-58: E-E-A-T judge `dir()` check unreliable ✅ RESOLVED 2026-03-02
### PB-59: Unbounded user strings in LLM prompts ✅ RESOLVED 2026-03-02
### PB-80: DB integration tests for migrations 0016+0017 ✅ RESOLVED 2026-03-15
### PB-81: Tests for new EmbeddingRepository methods ✅ RESOLVED 2026-03-15
### PB-82: Integration test for migrate_chroma_to_pgvector.py ✅ RESOLVED 2026-03-15
### PB-83: SSE context binding ✅ RESOLVED 2026-03-15
### PB-84: Auth failure request logging ✅ RESOLVED 2026-03-15
### PB-85: Per-step/per-agent context binding ✅ RESOLVED 2026-03-15
