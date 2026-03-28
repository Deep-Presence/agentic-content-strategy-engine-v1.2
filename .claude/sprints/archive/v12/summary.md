# Sprint v12 — Site Audit DB Persistence

**Date:** 2026-03-10
**Branch:** `research-agent-v1.2.0`
**Status:** COMPLETE

## Goal

Make the site audit module fully database-ready. When `DATABASE_URL` is set, all data should be retrievable from DB without filesystem access. Filesystem remains as write-through for backward compat.

## Completed (8 Phases)

### Phase 1: Alembic Migration
- `core/db/migrations/versions/0009_site_audit_full_schema.py`
- 17 new columns on `site_audits`, 3 new columns on `audit_findings`
- New `audit_page_results` table with composite indexes
- Status mapping: `degraded` -> `completed` + `is_degraded=True`

### Phase 2: ORM Model Updates
- `core/db/models/site_audit.py` — enriched columns + `AuditPageResultModel`

### Phase 3: Repository Enhancements
- `core/db/repositories/site_audit_repo.py` — 6 new methods:
  - `get_by_slug_and_audit_id`, `list_for_slug`, `get_findings_for_audit`
  - `get_page_results_for_audit`, `bulk_insert_page_results`, `has_enriched_data`

### Phase 4: Persistence Module (TDD)
- `core/site_audit/persistence.py` — `persist_site_audit_result()`
- `tests/site_audit/test_persistence.py` — 15 tests
- Finding dedup by `(url, finding_type, dimension)`, batch insert 100/flush
- Graceful degradation — never crashes pipeline

### Phase 5: Runner Integration
- `api/tasks/runner.py` — DB hooks in `run_site_audit_task()`
- `_resolve_db_context()`, `_create_pipeline_run()`, `persist_site_audit_result()`
- `_mark_pipeline_run_complete/failed()` wired up

### Phase 6: DbSiteAuditDataService — DB-First Reads
- `core/services/db_site_audit_data.py` — rewritten for DB-first with per-audit FS fallback
- UUID validation guards, null coalescing, `_is_enriched()` sentinel
- 32 tests in `tests/services/test_db_site_audit_data.py`

### Phase 7: Start Guard Update
- `api/routers/site_audit.py` — domain filter on `_get_latest_audit_run()`
- Prevents returning wrong `run_id` for multi-domain slugs
- DB-based guard deferred (FS guard sufficient for now)

### Phase 8: Full Test Suite Verification
- **899 tests passed** in 14.65s (0 failures)

## Codex Audit Fixes (5 Incorporated)

| # | Issue | Fix |
|---|-------|-----|
| I1 | Test hang — wrong mock path | Patch `api.routers.site_audit.run_site_audit_task` not source module |
| I2 | Thread safety — `_CACHE` under `asyncio.to_thread()` | Added `threading.Lock` in `json_site_audit_data.py` |
| I3 | UUID validation — DB crashes on invalid UUIDs | Added `_is_valid_uuid()` guard, invalid IDs fall through to FS |
| I4 | Domain filter — guard returns wrong `run_id` | Added `domain` param to `_get_latest_audit_run()` |
| I5 | Slug lock stranding — pre-try awaits throw | Moved `_resolve_db_context()` inside outer try block |

## Codex Audit Deferred (3 Items)

- PB-73: Distributed lock for multi-worker deployment
- PB-74: Product-scoped read endpoints
- PB-75: Session/service DI lifecycle cleanup

## Files Changed

| File | Action |
|------|--------|
| `core/db/migrations/versions/0009_site_audit_full_schema.py` | NEW |
| `core/db/models/site_audit.py` | MODIFIED |
| `core/db/repositories/site_audit_repo.py` | MODIFIED |
| `core/site_audit/persistence.py` | NEW |
| `core/services/db_site_audit_data.py` | MODIFIED |
| `core/services/json_site_audit_data.py` | MODIFIED (thread safety) |
| `api/tasks/runner.py` | MODIFIED |
| `api/routers/site_audit.py` | MODIFIED |
| `tests/site_audit/__init__.py` | NEW |
| `tests/content_engine/__init__.py` | NEW |
| `tests/site_audit/test_persistence.py` | NEW (15 tests) |
| `tests/services/test_db_site_audit_data.py` | MODIFIED (32 tests) |
| `tests/api/test_site_audit.py` | MODIFIED (mock path fix) |
| `tests/api/test_runner_db_persistence.py` | NEW (15 tests) |

## Test Summary

- 899 site audit tests passing (62 new)
- 15 persistence tests
- 32 DB service tests
- 15 runner DB hook tests
- 51 router tests (including fixed hang)
