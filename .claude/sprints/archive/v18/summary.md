# Sprint v18 — Structured Logging Layer 2: Correlation & Context Propagation

**Date:** 2026-03-15
**Branch:** `feat/deployment-prep-sprints`
**Status:** COMPLETE

---

## Goal

Complete the structured logging story — every log line becomes fully traceable from HTTP request through pipeline step through LangSmith trace. Layer 2 adds proper request_id vs correlation_id separation, LangSmith trace linkage, SSE context binding, auth failure logging, per-step/per-agent context enrichment, run_id binding, and async context propagation verification.

Resolves 3 deferred backlog items: PB-83, PB-84, PB-85.

## Architectural Decisions

- **D-L2-1:** X-Request-ID alongside X-Correlation-ID (not rename/alias) for proper distributed tracing semantics
- **D-L2-2:** Keep structlog contextvars (no explicit ContextVar objects) — single source of truth
- **D-L2-3:** Bind langsmith_trace_id in tracing.py as side-effect of trace creation (zero callsite changes)
- **D-L2-4:** Auth failure logging inside `_send_401()` helper (single point of change for all 4 auth failure paths)
- **D-L2-5:** Per-step/per-agent binding at pipeline orchestrator level using `scoped_bind()` context manager

## What Was Done

### Phase 1: Foundation — `get_context_value()` + `scoped_bind()`
- Added `get_context_value(key, default)` for single-value lookups
- Added `scoped_bind(**kwargs)` context manager — binds on enter, restores previous values on exit
- 8 new tests

### Phase 2: X-Request-ID + Middleware Hardening
- Generate `request_id` (always fresh UUID4) alongside `correlation_id` (forwarded or defaults to `request_id`)
- Set `X-Request-ID` response header
- Wrap `call_next` + logging in `try/finally` with `clear_context()` (context leak fix)
- Sanitize incoming `X-Correlation-ID` header (truncate to 128 chars)
- 5 new tests

### Phase 3: LangSmith Trace Linkage
- Bind `langsmith_trace_id=str(run_tree.id)` after `.post()` in `create_pipeline_trace()`, `create_trace()`, `create_research_trace()`
- 5 new tests

### Phase 4: SSE Context Binding (PB-83)
- SSE endpoint now binds `correlation_id`, `user_id`, `company_slug`, `task_id`, `pipeline_name`
- Generates correlation_id for SSE (since middleware doesn't run)
- Clears context on stream disconnect via `_stream_with_cleanup()` wrapper
- 6 new tests

### Phase 5: Auth Failure Logging (PB-84)
- `_send_401()` now logs structured `auth_failure` warning with `error_code`, `path`, `method`
- All 4 call sites updated to pass `path=path, method=method`
- 5 new tests

### Phase 6: Per-Step/Per-Agent Context Binding (PB-85)
- **Gap Analysis:** `scoped_bind(step_name=...)` for S1-S8 (both `run_gap_analysis()` and `run_topic_scoped_gap_analysis()`)
- **Knowledge Base:** `scoped_bind(agent_name=...)` for 6 agents (company_overview, customer_reviews, competitor_scanner, weakness_analyst, brand_perception, synthesis)
- **Audience Persona:** `scoped_bind(agent_name=...)` for persona_suggester and persona_profile_generator
- **Voice Style Guide:** `scoped_bind(agent_name=...)` for author_discovery, author_research, voice_synthesis
- **Content Engine v1.3:** `scoped_bind(step_name=...)` for stages 0, 3, 4, 5; `bind_context(step_name=...)` for stages 1, 2 (complex HITL loops)
- **Site Audit:** `scoped_bind(step_name=...)` for S1-S6
- 3 new tests (site audit binding, gap analysis binding)

### Phase 7: Bind `run_id` in Runner Functions
- 13 of 14 runner functions updated with `run_id=str(run_id)` in context binding
- Pattern A (9 functions): run_id added to existing bind_context call
- Pattern B (4 functions): separate bind_context after _resolve_db_context
- 1 function correctly skipped (no _resolve_db_context)

### Phase 8: Async Context Propagation Tests
- 5 integration tests proving asyncio.create_task context inheritance, parent/child isolation, gather independence
- 5 new tests

## Codex Review Summary (GPT-5.3 Codex)

- **6 findings incorporated:** Context leak on exceptions (try/finally), run_id UUID formatting, X-Correlation-ID sanitization, topic-scoped GA coverage, scoped_bind helper, SSE disconnect cleanup
- **2 findings rejected:** Pure ASGI middleware for request-id (too big a refactor), per-item identifiers in hot loops (not proposed)

## Files Changed

| Action | File |
|--------|------|
| **Modify** | `core/shared_tools/structured_logging.py` |
| **Modify** | `core/shared_tools/tracing.py` |
| **Modify** | `api/app.py` |
| **Modify** | `api/routers/events.py` |
| **Modify** | `api/auth/middleware.py` |
| **Modify** | `api/tasks/runner.py` |
| **Modify** | `core/gap_analysis/pipeline.py` |
| **Modify** | `core/research/knowledge_base/pipeline.py` |
| **Modify** | `core/research/audience_persona/pipeline.py` |
| **Modify** | `core/research/voice_style_guide/pipeline.py` |
| **Modify** | `core/content_engine/pipeline_v13.py` |
| **Modify** | `core/site_audit/pipeline.py` |
| **Modify** | `tests/shared_tools/test_structured_logging.py` |
| **Modify** | `tests/api/test_middleware.py` |
| **Create** | `tests/shared_tools/test_tracing_context.py` |
| **Create** | `tests/api/test_events_context.py` |
| **Create** | `tests/api/test_auth_failure_logging.py` |
| **Create** | `tests/api/test_context_propagation.py` |
| **Create** | `tests/test_step_context_binding.py` |

**Total: 14 modified files, 5 new test files, 48 new tests**

## Test Results

- 59/59 Layer 2 tests passing (all new tests)
- 1084 API tests passing (0 regressions)
- 111 site_audit + shared_tools tests passing (0 regressions)
- Pre-existing failures unchanged: 3 gap_analysis status tests, 1 HITL import error

## Backlog Resolution

| PB ID | Description | Resolved In |
|-------|-------------|-------------|
| PB-83 | SSE `/events` endpoint context binding | Phase 4 |
| PB-84 | Auth failure request logging | Phase 5 |
| PB-85 | Per-step and per-agent context binding | Phase 6 |
