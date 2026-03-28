# Sprint v17 — Structured Logging Foundation (Layer 1)

**Date:** 2026-03-15
**Branch:** `feat/deployment-prep-sprints`
**Status:** COMPLETE

---

## Goal

Implement structured logging foundation using structlog — every log line becomes a structured JSON object (in prod) or colored console output (in dev), with automatic context propagation (correlation_id, user_id, company_slug, task_id, pipeline_name) — without changing any of the 115 existing `logger.info("msg %s", arg)` call sites.

## Decision

**structlog over python-json-logger** (D-LOG-1). Key reasons: native contextvars integration, stdlib bridge mode (zero call-site changes), dev/prod renderer switching. Codex-reviewed with GPT-5.3 Codex.

## What Was Done

### Phase A: Foundation (zero call-site changes)

1. **Dependency** — Added `structlog>=24.1` to pyproject.toml
2. **Settings** — 3 new fields: `log_level` (Literal), `log_format` (Literal), `log_include_caller` (bool)
3. **Central module** — `core/shared_tools/structured_logging.py` (~140 lines). Exports: `configure_logging()`, `bind_context()`, `clear_context()`, `get_context()`
4. **App init** — `configure_logging()` in lifespan + early init in `scripts/run_server.py`
5. **Script migration** — 5 scripts: basicConfig → configure_logging
6. **Print elimination** — `persona_suggester.py` (80k char print deleted), `reddit_hil/cli.py` (7 prints → logger calls)
7. **Tests** — 17 tests covering JSON/console output, context binding, idempotency, stdlib bridge, Settings validation

### Phase B: Request Context Propagation

1. **Middleware rewrite** — `RequestLoggingMiddleware.dispatch()` now generates/extracts `X-Correlation-ID`, binds context (correlation_id, method, path, user_id, company_slug), logs `"request_completed"` with structured fields, clears context
2. **Runner context** — All 14 `run_*_task` functions bind task_id, pipeline_name, company_slug
3. **Middleware tests** — 5 tests (request_completed log, status_code, duration_ms, correlation_id, forwarded correlation_id)

### Phase C: Deferred to backlog

- PB-83: SSE `/events` context binding
- PB-84: Auth failure request logging
- PB-85: Per-step/per-agent context binding

## Codex Review Summary

- **6 findings incorporated:** Literal validation, database_echo respected, disable_existing_loggers=False, ExtraAdder processor, early init in run_server.py, persona_suggester print deletion
- **2 findings rejected:** Pure ASGI middleware (Starlette >=0.36 fixed contextvars), stdlib-only approach (reinventing structlog)
- **3 findings deferred:** SSE context, auth failure logging, run_in_executor threads

## Files Changed

| Action | File |
|--------|------|
| **Create** | `core/shared_tools/structured_logging.py` |
| **Create** | `tests/shared_tools/test_structured_logging.py` |
| **Modify** | `pyproject.toml` |
| **Modify** | `core/config/settings.py` |
| **Modify** | `api/app.py` |
| **Modify** | `api/tasks/runner.py` |
| **Modify** | `scripts/run_server.py` |
| **Modify** | `scripts/run_kb.py` |
| **Modify** | `scripts/run_topic_discovery.py` |
| **Modify** | `scripts/run_td_rescore.py` |
| **Modify** | `scripts/backfill_gap_data.py` |
| **Modify** | `scripts/migrate_chroma_to_pgvector.py` |
| **Modify** | `core/research/prompts/persona_suggester.py` |
| **Modify** | `core/reddit_hil/cli.py` |
| **Modify** | `tests/api/test_middleware.py` |

**Total: 2 new files, 13 modified files, 22 new tests**

## Test Results

- 17/17 structured logging tests passing
- 5/5 middleware tests passing
- 1063 API tests passing (0 regressions, 3 pre-existing failures confirmed)
- Pre-existing failures (not caused by this sprint): test_reads_and_truncates_company_context, 3 gap_analysis status tests, test_hitl_interrupt_resume import error
