# Pending Backlog

> **Last synced:** 2026-03-22 (Redis Sessions 3-4 + PB-39 fix)
> **Total items:** 58 (PB-39 resolved)

## Critical (Fix Before Production)

### PB-46: [v1.3-C1] v1.0 pipeline crashes — evaluator returns 3-tuple, v1.0 unpacks 2
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline.py:460`
- **Status:** ✅ RESOLVED 2026-03-02 — `optimized, history, _ = await evaluate_and_optimize(...)`

### PB-47: [v1.3-C2] Dispatcher/evaluator zip mismatch — wrong brief paired with content after worker failure
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/workers/dispatcher.py:439-458`, `core/content_engine/pipeline_v13.py:699-714`
- **Status:** ✅ RESOLVED 2026-03-02 — dispatcher returns `List[Tuple[str, FormattedContent]]`; Stage 4 uses `blueprint_by_id` dict lookup instead of positional zip.

### PB-48: [v1.3-C3] v1.3 API approval endpoints missing tenant ownership checks
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `api/routers/content_v13.py`
- **Status:** ✅ RESOLVED 2026-03-02 — Added `http_request: Request` + `task.company_slug != user_company_slug → 403` to all 4 endpoints (status, /approve/topics, /approve/briefs, /approve/content).

### PB-49: [v1.3-C4] Re-brief always generates `brief-001` — artifact overwrite in multi-piece runs
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/brief_builder.py`, `core/content_engine/pipeline_v13.py`
- **Status:** ✅ RESOLVED 2026-03-02 — Added `brief_id_overrides` param to `build_briefs_parallel()`; `_rebrief_and_rerun()` passes `f"rebrief-{uuid4().hex[:8]}"` as override.

### PB-1: `update_company` allows overwriting `id`, `created_at`, `slug` via `**kwargs`
- **Source:** Phase 1+2 code review (C5) — sprint front-back-integration
- **Date added:** 2026-02-25
- **Description:** No allowlist on `setattr` in `update_company()` — caller can corrupt internal state. Needs allowlist of mutable fields. Note: `update_company` and `update_product` now have `_COMPANY_MUTABLE_FIELDS` / `_PRODUCT_MUTABLE_FIELDS` allowlists (resolved by T-review-action-items), but verify coverage is complete.
- **Files affected:** `api/auth/store.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-02-26 (T-review-action-items P0 C2/C5)

## High Priority

### PB-50: [v1.3-H1] Re-brief context extraction is type-broken — gap_context always uses fallback
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline_v13.py:284-286`
- **Status:** ✅ RESOLVED 2026-03-02 — `isinstance(gap_context, dict)` replaced with direct Pydantic attribute access: `qid = blueprint.gap_context.query_gap.get("query_id", ...)` + pass full `WorkerQueryContext` (not a degraded stub).

### PB-51: [v1.3-H2] v1.3 API bypasses task semaphore, cancellation, and slug lock
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `api/routers/content_v13.py`, `api/tasks/runner.py`
- **Status:** ✅ RESOLVED 2026-03-02 — Added `run_content_v13_pipeline_task()` to runner.py with semaphore + handle + slug-lock pattern. Router removed local `_run_v13_pipeline_task` and calls `task_store.register_task_handle()` after `asyncio.create_task()`.

### PB-52: [v1.3-H3] HITL-1 "retry" and HITL-2 "feedback" are dead paths — no actual re-run
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `core/content_engine/pipeline_v13.py:499-676`
- **Status:** ✅ RESOLVED 2026-03-02 — H3a: bounded retry loop (`_MAX_TOPIC_RETRIES=2`) calls `select_topics(user_feedback=feedback)` on "retry". H3b: bounded feedback loop (`_MAX_BRIEF_FEEDBACK_RETRIES=1`) re-runs `build_briefs_parallel` with feedback in `TopicSelection.rationale`.

### PB-53: [v1.3-H4] Manual mode can silently produce zero blueprints with existing gap data
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** When `analysis_json` exists in manual mode, `extract_worker_context(["manual-1"])` is called but "manual-1" never matches real gap query_ids. Empty `worker_contexts` → `build_briefs_parallel` returns None for all topics → empty output. Fix: fallback to inline WorkerQueryContext when extraction is empty.
- **Files affected:** `core/content_engine/pipeline_v13.py:635-650`, `core/content_engine/context_router.py:168`
- **Blocked by:** nothing

### PB-54: [v1.3-H5] `gap_slug` unsanitized in filesystem path construction — path traversal
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Files affected:** `api/routers/content_v13.py:99,121`
- **Status:** ✅ RESOLVED 2026-03-02 — Added `_SLUG_PATTERN` regex validation + `Path.is_relative_to(artifacts_root)` guard before path construction. Returns 400 on violation.

### PB-55: [v1.3-H6] v1.3 workers/evaluators import Langfuse tracing — LangSmith spans silently degraded
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** `eeat_judge.py` and `evaluator/loop.py` import from `core.content_engine.tracing` (Langfuse v1.0). v1.3 pipeline passes LangSmith `RunTree` spans — incompatible types. Langfuse helpers are no-ops on unrecognized objects → evaluator dimension traces silently dropped.
- **Files affected:** `core/content_engine/evaluator/eeat_judge.py:22`, `core/content_engine/evaluator/loop.py:24`
- **Blocked by:** nothing

### PB-56: [v1.3-H7] Content review graph `apply_edits → approval_gate` loop bypasses pipeline edit_count guard
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** The graph has an `apply_edits → approval_gate` internal edge. A user repeatedly submitting "edit" in `run_hitl_checkpoint`'s interrupt loop bypasses the pipeline's `_MAX_EDIT_ATTEMPTS` guard. `_content_apply_edits` does nothing (only sets a flag), so the user sees the same unchanged content repeatedly. Fix: remove the `apply_edits → approval_gate` edge; let the pipeline's `while` loop handle edit cycles.
- **Files affected:** `core/content_engine/graph_v13.py:324`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-03-02 — Removed `apply_edits → approval_gate` edge from `graph_v13.py:324`; pipeline's `while not piece_resolved` loop handles all edit cycles.

### PB-57: [v1.3-H8] `persist_v13_brief_approval()` hardcodes all decisions as "approve"
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** `pipeline_v13.py:605-608` only persists approved blueprints and hardcodes `"decision": "approve"`. Rejected and feedback decisions not recorded — incomplete audit trail.
- **Files affected:** `core/content_engine/pipeline_v13.py:605-608`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-03-02 — `brief_decision_log` accumulates all decisions (approve/reject + feedback/feedback_attempts). ALL blueprints (not just approved) passed to `persist_v13_brief_approval`. 8 new tests in `TestHITL2BriefDecisionLogging` + `test_writes_reject_decision_correctly`.

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
- **Source:** Kanban-Pipeline Sync sprint, 2026-03-20 — `DbContentDataService.get_briefs()` returned stale `status: "suggested"` because it read from Postgres (which had `planned`) instead of `pipeline_state.json` (which had `brief_review`)
- **Date added:** 2026-03-20
- **Files affected:** `core/services/db_content_data.py` (fixed for `get_briefs`), potentially other DbService methods
- **Root cause:** The "filesystem-first, DB-additive" architecture means pipelines write real-time state to JSON artifacts, but DbService implementations query Postgres, which is only updated at coarser granularity. When `DATABASE_URL` is set, the frontend silently gets stale data. Additionally, the DB uses UUID primary keys as `id` while the pipeline uses filesystem IDs like `brief-016` — causing HITL approval mismatches.
- **Fixed so far:** `DbContentDataService.get_briefs()` now overlays `pipeline_state.json` (Phase 0 status), returns `task_id` from `__task_ids__`, and uses `piece.brief_id` instead of UUID as the response `id`.
- **Remaining work:**
  1. Audit ALL other DbService methods for similar disconnects (get_brief_detail, stage content, etc.)
  2. Audit `DbTaskStore` for any filesystem-state dependencies
  3. When migrating to Redis-backed TaskStore/state, replace `pipeline_state.json` with Redis pub/sub — eliminates the JSON/DB split entirely
  4. Consider writing pipeline status updates to both JSON AND DB simultaneously as an interim fix

### PB-86: Pre-existing test failure — test_persistence.py mock doesn't support await
- **Source:** Discovered during Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `tests/content_engine/test_persistence.py::TestPersistContentPieces::test_happy_path_single_piece`
- **Root cause:** `session2.execute` is a `MagicMock`, not an `AsyncMock`. Line 94 in `persistence.py` does `await repo.get_by_slug_and_brief_id(...)` on a sync mock.
- **Fix:** Replace `MagicMock` with `AsyncMock` for the session factory and repo methods.

### PB-87: Pre-existing test failure — tracing_v13 module attribute `_langsmith_available` removed
- **Source:** Discovered during Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `tests/content_engine/test_tracing_v13.py::TestCreatePipelineTrace::test_returns_none_when_disabled`
- **Root cause:** Test patches `core.content_engine.tracing_v13._langsmith_available` but the module no longer has this attribute (likely renamed or refactored).
- **Fix:** Update test to patch the current guard attribute in `tracing_v13.py`.

### PB-88: Pre-existing test failure — tracing_compat patches non-existent `_is_enabled` attribute
- **Source:** Discovered during Kanban-Pipeline Sync sprint, 2026-03-20
- **Date added:** 2026-03-20
- **Files affected:** `tests/content_engine/test_tracing_compat.py::TestCreateSpanCompat::test_input_kwarg_alias`
- **Root cause:** Test patches `core.content_engine.tracing_v13._is_enabled` but no such attribute exists in the module.
- **Fix:** Update test to use the correct attribute name or remove if obsolete.

### PB-58: [v1.3-M1] `"response" in dir()` check in E-E-A-T judge is unreliable
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** `eeat_judge.py:135` uses `if "response" in dir() else 0` to guard token count logging. `dir()` checks module scope, not local scope. Fix: use sentinel `response_obj = None` before try block.
- **Files affected:** `core/content_engine/evaluator/eeat_judge.py:135`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-03-02 — `response = None` sentinel added before try block; check changed to `if response is not None`. 4 tests in `TestEeatUsageLogging`.

### PB-59: [v1.3-M2] Unbounded user strings (editor_notes, manual_prompt) in LLM prompts
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** API schemas have no `max_length` on `editor_notes` or `manual_prompt`. Linker/fact-checker prompts don't call `truncate_to_token_limit()` on draft input. Increases prompt injection and token cost risk.
- **Files affected:** `api/schemas/content_v13.py`, `core/content_engine/workers/linker.py:80`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-03-02 — `max_length` added to `manual_prompt`/`manual_description` (2000) and `editor_notes` (5000) in schemas. `truncate_to_token_limit(max_tokens=120_000)` added to linker and fact_enricher after user_prompt build. Defense-in-depth truncation in router. 8 tests in `TestLinkerTruncation` + `TestContentV13SchemaValidation`.

### PB-60: [v1.3-M3] Pipeline trace not flushed on error paths
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** `update_trace_output()` and `flush()` only run on success path in `pipeline_v13.py:969`. Any exception leaves the LangSmith trace open. Fix: wrap with `try/finally: flush()`.
- **Files affected:** `core/content_engine/pipeline_v13.py:969`
- **Blocked by:** nothing

### PB-61: [v1.3-M4] v1.3 `_update_task(progress=...)` maps to nonexistent field
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** `pipeline_v13.py` calls `_update_task(..., progress={"stage": N, ...})` but `PipelineTask` has no `progress` field — only `current_step` and `progress_pct`. Stage info is silently dropped; UI shows no progress.
- **Files affected:** `core/content_engine/pipeline_v13.py:434+`, `api/tasks/models.py:41`
- **Blocked by:** nothing

### PB-62: [v1.3-M5] Manual mode skips HITL-2 — undocumented design decision
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** Manual mode goes directly from brief building to workers without HITL-2 checkpoint. Intentional (faster manual flow) but undocumented. Fix: add docstring clarification.
- **Files affected:** `core/content_engine/pipeline_v13.py:652-661`
- **Blocked by:** nothing

### PB-63: [v1.3] Add missing integration tests for v1.3 failure paths
- **Source:** v1.3 critical code review — content-engine-v13
- **Date added:** 2026-03-02
- **Description:** 379 tests pass (36 added this session for M1/M2/H8/H9). Still missing: v1.0 pipeline calling evaluator (C1), cross-tenant approval (C3), re-brief brief_id collision (C4), `_rebrief_and_rerun()` with Pydantic gap_context (H1), concurrent v1.3 runs (H2). Worker zip mismatch now covered by `TestEvaluatedTupleRouting`.
- **Files affected:** `tests/content_engine/`, `tests/api/test_content_v13.py`
- **Blocked by:** nothing (PB-46 through PB-59 all resolved)

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
- **Blocked by:** ~~s1 pipeline enhancement~~ — **Partially resolved 2026-03-07:** s1 now computes structural signals per company page (`company_page_analysis.json`), and `QueryGap.best_company_structural_signals` provides per-gap company signals. Remaining: `gap_data_service.py` aggregate endpoint needs to read `company_page_analysis.json` and compute `company_avg` from page-level signals.

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

### PB-64: Crawl-delay enforcement (rate limiting) in site audit crawler
- **Source:** Sprint v3 site-audit-p3-bugfixes (T-SA-28 deferred scope)
- **Date added:** 2026-03-04
- **Description:** Actual crawl-delay enforcement requires a shared domain-level rate limiter (`asyncio.Lock` + timestamp tracking) to throttle requests per `Crawl-delay` directive. Currently only parsed and reported. Needs `_CrawlDelayLimiter` class with `async with limiter.acquire(domain):` pattern.
- **Files affected:** `core/site_audit/steps/s1_discover.py`
- **Blocked by:** nothing

### PB-65: `_detect_personas()` in companies router + brand_data service reads legacy path only
- **Source:** Phase F Codex review (deferred finding #1)
- **Date added:** 2026-03-06
- **Description:** `api/routers/companies.py:_detect_personas()` and `api/services/brand_data_service.py` still read from `artifacts/personas/` only. After AP migration, dashboard/UI won't show AP-generated personas. Should be updated to check `audience_personas/` first, with legacy fallback — same pattern as `resolve_artifacts()`.
- **Files affected:** `api/routers/companies.py:56`, `api/services/brand_data_service.py`
- **Blocked by:** nothing

### PB-66: `PersonaStorage.list_persona_paths()` returns unsorted paths
- **Source:** Phase F Codex review (deferred finding #2)
- **Date added:** 2026-03-06
- **Description:** `list_persona_paths()` returns paths in manifest dict insertion order, not sorted. This means prompt context order can drift between runs depending on when personas were added. Should add `sorted()` for deterministic ordering.
- **Files affected:** `core/research/audience_persona/storage.py:263`
- **Blocked by:** nothing

### PB-67: [DB-M1] `get_latest_by_slug_and_type()` is redundant wrapper
- **Source:** Sprint v11 DB Foundation Review — M1
- **Date added:** 2026-03-10
- **Description:** `ResearchArtifactRepository.get_latest_by_slug_and_type()` delegates to `get_by_slug_and_type()` with no added value. Remove or document the distinction.
- **Files affected:** `core/db/repositories/research_artifact_repo.py:41-47`
- **Blocked by:** nothing

### PB-68: [DB-M2] No input validation on `upsert_artifact()`
- **Source:** Sprint v11 DB Foundation Review — M2
- **Date added:** 2026-03-10
- **Description:** Empty `effective_slug`, negative version, path traversal in `storage_key` — no validation at repo level. Add guards or document assumptions.
- **Files affected:** `core/db/repositories/research_artifact_repo.py`
- **Blocked by:** nothing

### PB-69: [DB-M3] TD `list_assignments()` shape divergence
- **Source:** Sprint v11 DB Foundation Review — M3
- **Date added:** 2026-03-10
- **Description:** JSON service uses `model_dump()`, DB service uses explicit field extraction with `.value` on enums. Define shared assignment DTO to avoid shape drift.
- **Files affected:** `core/services/json_topic_discovery_data.py`, `core/services/db_topic_discovery_data.py`
- **Blocked by:** nothing

### PB-70: [DB-M4] JSON VSG `get_guide()` ignores `version` parameter
- **Source:** Sprint v11 DB Foundation Review — M4
- **Date added:** 2026-03-10
- **Description:** `version` kwarg accepted but never used — always returns latest. Implement versioned reads or remove param.
- **Files affected:** `core/services/json_vsg_data.py`
- **Blocked by:** nothing

### PB-71: [DB-M5] Missing multi-tenancy isolation tests
- **Source:** Sprint v11 DB Foundation Review — M5
- **Date added:** 2026-03-10
- **Description:** No test verifying two companies with same slug don't collide in `upsert_artifact()`. C2 fix added `company_id` to WHERE but no integration test proves isolation.
- **Files affected:** `tests/db/test_research_artifact_repo.py`
- **Blocked by:** nothing

### PB-72: [DB-M6] DB services return `""` instead of `None` for missing content files
- **Source:** Sprint v11 DB Foundation Review — M6
- **Date added:** 2026-03-10
- **Description:** `content_md or ""` masks missing files. Downstream can't distinguish "empty doc" from "file not found". Consider returning `None` and letting callers decide.
- **Files affected:** `core/services/db_kb_data.py`, `core/services/db_persona_data.py`
- **Blocked by:** nothing

### PB-73: [SA-R1] Distributed lock for multi-worker site audit deployment
- **Source:** Sprint v12 Site Audit DB Persistence — Codex audit (deferred)
- **Date added:** 2026-03-10
- **Description:** Current slug lock is in-process only (`asyncio.Lock`). Multi-worker deployment needs PG advisory lock or Redis-based distributed lock to prevent duplicate audits across workers.
- **Files affected:** `api/tasks/runner.py`, `api/tasks/store.py`
- **Blocked by:** nothing

### PB-74: [SA-C2] Product-scoped read endpoints for site audit
- **Source:** Sprint v12 Site Audit DB Persistence — Codex audit (deferred)
- **Date added:** 2026-03-10
- **Description:** Routes use `{slug}` (company_slug) but DB stores `effective_slug` (`{company}__{product}`). Product-scoped reads need either an explicit `product_slug` query param or endpoint restructuring to `/companies/{slug}/products/{product}/audits`.
- **Files affected:** `api/routers/site_audit.py`, `core/services/db_site_audit_data.py`
- **Blocked by:** nothing

### PB-76: [RO-M6] VSG skip logic never fires — ap_manifest_version never written by VSG pipeline
- **Source:** Sprint v13 Research Orchestrator — Codex audit (deferred finding #6)
- **Date added:** 2026-03-11
- **Description:** `_should_skip_vsg()` in orchestrator compares `vsg_manifest.ap_manifest_version` against current AP manifest fingerprint (`last_full_run.isoformat()`). But the VSG pipeline's finalize phase never writes `ap_manifest_version` to the VSG manifest — only `company_name` and `last_full_run`. So VSG skip logic always sees `ap_manifest_version=None` and never skips.
- **Files affected:** `core/research/voice_style_guide/pipeline.py:445-448`, `core/models/voice_style_guide.py`, `core/research/orchestrator.py:170`
- **Blocked by:** nothing

### PB-77: [RO-M7] Process-local concurrency — slug locks/semaphore lost in multi-worker deployment
- **Source:** Sprint v13 Research Orchestrator — Codex audit (deferred finding #7)
- **Date added:** 2026-03-11
- **Description:** Slug locks, approval queues, task handles, and semaphore are in-memory only in both `TaskStore` and `DbTaskStore`. Multi-process deployments (gunicorn workers, horizontal scaling) can run the same slug concurrently and race on artifact writes. Known tech debt — needs PG advisory locks or Redis-based distributed locking.
- **Files affected:** `api/tasks/store.py`, `core/services/db_task_store.py`, `api/tasks/runner.py`
- **Blocked by:** nothing

### PB-75: [SA-DI] Session/service DI lifecycle cleanup
- **Source:** Sprint v12 Site Audit DB Persistence — Codex audit (deferred)
- **Date added:** 2026-03-10
- **Description:** `api/dependencies.py` creates DB services without `yield`/cleanup pattern. Session factories are created once at startup but services don't have explicit lifecycle management. Should use FastAPI `yield` dependencies for proper cleanup.
- **Files affected:** `api/dependencies.py`
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
- **Description:** `tests/api/test_hitl_interrupt_resume.py::TestResumeFlow::test_revise_loops_back_to_agent` — fails on assert not `_has_interrupt(r3)`. Root cause: `langgraph-checkpoint` v4.0.0 stores `__interrupt__` as a channel write; with `StateGraph(dict)` it bleeds into `state.values` (~15% intermittent failure rate). `StateGraph(TypedDict)` is immune because `__interrupt__` is not a declared field.
- **Files affected:** `tests/api/test_hitl_interrupt_resume.py`, `core/content_engine/graph.py`
- **Blocked by:** nothing
- **Status:** ✅ RESOLVED 2026-03-22 — Converted test graph + v1.0 production graph from `StateGraph(dict)` to `StateGraph(TypedDict)`. 20/20 passes (was 3/20 before fix).

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

### PB-45: D3 — Full lightweight gap analysis for manual mode
- **Source:** Content Engine v1.3 sprint — D3 deferred by design
- **Date added:** 2026-03-02
- **Description:** Manual mode currently constructs `WorkerQueryContext` inline with minimal data. Full s3-s6 reuse (search→enrich→embed→analyze on user's topic) would provide richer context but adds 2-5 min latency and requires s1 output (SemanticUnit list) as prerequisite. Current inline approach is sufficient for v0.
- **Files affected:** `core/content_engine/pipeline_v13.py` (lines 395-435)
- **Blocked by:** nothing

### PB-80: DB integration tests for migrations 0016+0017
- **Source:** pgvector-migration-v16 — Codex review deferred
- **Date added:** 2026-03-15
- **Description:** Migrations 0016 (pgvector_migration) and 0017 (cps_training_tables) need DB integration tests verifying table creation, HNSW indexes, backfill correctness, and downgrade safety. Requires `TEST_DATABASE_URL`.
- **Files affected:** `tests/db/test_pgvector_migration.py`
- **Status:** ✅ RESOLVED 2026-03-15 — 13 DB integration tests (persona_embeddings CRUD + unique constraints, semantic_units nullable run_id + slug query, paragraph_embeddings nullable FK, CPS training tables, EmbeddingRepository end-to-end). Auto-skip without TEST_DATABASE_URL.

### PB-81: Tests for new EmbeddingRepository methods
- **Source:** pgvector-migration-v16 — Phase 3 deferred
- **Date added:** 2026-03-15
- **Description:** 7 new methods added to `embedding_repo.py` (slug-based queries, upserts, persona embeddings, count/delete). Need mocked session unit tests.
- **Files affected:** `tests/shared_tools/test_embedding_repo_extended.py`
- **Status:** ✅ RESOLVED 2026-03-15 — 15 mocked-session unit tests covering all 7 methods (get_by_slug, get_by_ids, count, delete, upsert paragraphs, upsert personas, get personas).

### PB-82: Integration test for migrate_chroma_to_pgvector.py script
- **Source:** pgvector-migration-v16 — Phase 8 deferred
- **Date added:** 2026-03-15
- **Description:** Data migration script needs integration test with mock ChromaDB client + mock pgvector. Verify collection enumeration, batch processing, idempotent ON CONFLICT, dry-run mode, and summary report.
- **Files affected:** `tests/scripts/test_migrate_chroma_to_pgvector.py`
- **Status:** ✅ RESOLVED 2026-03-15 — 17 tests (slug extraction, 3 collection types, dry-run, empty collections, missing chroma dir, missing chromadb, missing DATABASE_URL, null documents, multi-company).

### PB-83: [LOG-C1] SSE `/events` endpoint context binding
- **Source:** Structured Logging v17 — Phase C deferred (Codex finding)
- **Date added:** 2026-03-15
- **Status:** ✅ RESOLVED 2026-03-15 — Sprint v18 Phase 4. SSE endpoint now binds correlation_id, user_id, company_slug, task_id, pipeline_name. Clears context on disconnect via _stream_with_cleanup(). 6 tests.

### PB-84: [LOG-C2] Auth failure request logging
- **Source:** Structured Logging v17 — Phase C deferred (Codex finding)
- **Date added:** 2026-03-15
- **Status:** ✅ RESOLVED 2026-03-15 — Sprint v18 Phase 5. _send_401() now logs structured auth_failure warning with error_code, path, method. All 4 call sites updated. 5 tests.

### PB-85: [LOG-C3] Per-step and per-agent context binding
- **Source:** Structured Logging v17 — Phase C deferred
- **Date added:** 2026-03-15
- **Status:** ✅ RESOLVED 2026-03-15 — Sprint v18 Phase 6. scoped_bind(step_name/agent_name) added to all 6 pipelines: GA (S1-S8), KB (6 agents), AP (2 agents), VSG (3 agents), CE v1.3 (6 stages), SA (S1-S6). 3 tests.

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

### PB-46: v1.0 pipeline evaluator 3-tuple unpack crash ✅ RESOLVED 2026-03-02
- **Resolved by:** v1.3 critical fixes — `pipeline.py:460` changed to `optimized, history, _ = ...`; 1 regression test added

### PB-47: Dispatcher zip mismatch — silent brief/content corruption ✅ RESOLVED 2026-03-02
- **Resolved by:** v1.3 critical fixes — `dispatch_workers_v13()` now returns `List[Tuple[str, FormattedContent]]`; Stage 4 uses dict-based brief_id lookup; `_rebrief_and_rerun()` unpacks tuple; 2 regression tests added

### PB-48: v1.3 approval endpoints missing tenant ownership check ✅ RESOLVED 2026-03-02
- **Resolved by:** v1.3 critical fixes — Added `Request` + `task.company_slug != user_company_slug → 403` to 4 endpoints in `content_v13.py`; 5 cross-tenant tests added

### PB-49: Re-brief brief_id collision overwrites original artifact ✅ RESOLVED 2026-03-02
- **Resolved by:** v1.3 critical fixes — Added `brief_id_overrides` to `build_briefs_parallel()`; `_rebrief_and_rerun()` passes `rebrief-{uuid8}` override; 4 collision-prevention tests added

### PB-83: SSE context binding ✅ RESOLVED 2026-03-15
- **Resolved by:** Sprint v18 Phase 4 — SSE endpoint binds correlation_id, user_id, company_slug, task_id, pipeline_name. Clears on disconnect. 6 tests.

### PB-84: Auth failure request logging ✅ RESOLVED 2026-03-15
- **Resolved by:** Sprint v18 Phase 5 — `_send_401()` logs structured auth_failure warning. All 4 call sites updated. 5 tests.

### PB-85: Per-step/per-agent context binding ✅ RESOLVED 2026-03-15
- **Resolved by:** Sprint v18 Phase 6 — `scoped_bind()` in all 6 pipelines (GA S1-S8, KB 6 agents, AP 2 agents, VSG 3 agents, CE 6 stages, SA S1-S6). 3 tests.
