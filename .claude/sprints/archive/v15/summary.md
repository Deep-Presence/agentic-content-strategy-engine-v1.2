# Sprint v15 — Daily Tracker DB Persistence & Production Readiness

**Date:** 2026-03-15
**Branch:** `research-agent-v1.2.0`
**Status:** COMPLETE

## Goal

Make the Daily Tracker fully DB-ready, persistent, and production-capable — following all established codebase patterns (filesystem-first, graceful degradation, async task runner, SSE streaming).

## Phases Completed (6/6)

### Phase 1: Infrastructure Wiring
- Added `daily_tracker` to `PipelineType` enum, `PipelineTask` Literal, ORM model registry
- Created Alembic migration `0014_daily_tracker_enum.py` (`ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'daily_tracker'`)
- 6 infrastructure tests

### Phase 2: Persistence Layer
- Created `core/daily_tracker/persistence.py` — 5 functions: `_should_persist`, `write_run_artifact`, `create_daily_run_record`, `persist_daily_run_result`, `mark_daily_run_failed`
- Filesystem-first JSON artifacts + graceful DB persistence
- Two-phase write: create at start (running) → update at end (completed/failed)
- FK safety: pre-validate prompt_id UUIDs, skip invalid ones
- 16 unit tests

### Phase 3: Task Runner
- Added `run_daily_tracker_task()` to `api/tasks/runner.py`
- Full async background task: SSE events, slug lock, semaphore, pipeline run tracking
- Safety net: `mark_daily_run_failed` in finally block ensures no stuck "running" rows
- Source-module patching with ExitStack in tests
- 11 runner tests

### Phase 4: Router Refactor
- `POST /runs`: sync orchestrator call → async background task (returns 202 with task_id)
- `GET /runs/{run_id}`: stub → DB query with tenant isolation
- `GET /runs`: empty list → DB query with pagination
- 47 endpoint tests (existing updated + new)

### Phase 5: DB Integration Tests
- Created `tests/db/test_daily_tracker_persistence.py` — 8 integration tests
- Auto-skipped without `TEST_DATABASE_URL`
- Tests roundtrip writes, mention analysis fields, FK safety, idempotent mark_failed

### Phase 6: Analytics Verification + Docs Update
- Verified `_DbResponseDataProvider` reads persisted data correctly
- Updated `docs/API_DOCUMENTATION.md` with new response schemas

## Codex Review

**gpt-5.3-codex** reviewed the plan. Initial verdict: REJECT WITH REASONS (7 findings). All incorporated into revised plan. Re-review: APPROVE.

Key findings addressed:
- **CRITICAL**: 3-UUID confusion (task_id, pipeline_run_id, result.run_id) — resolved with clear separation
- **CRITICAL**: Company ID type mismatch (String vs UUID) — resolved: daily_tracker uses string
- **HIGH**: Failed runs silently marked completed — resolved: runner checks result.status
- **HIGH**: Bulk FK failure rollback — resolved: pre-validate + per-response fallback
- **HIGH**: PG ENUM migration missing — resolved: migration 0014

## Test Results

```
392 passed, 8 skipped (DB integration — no TEST_DATABASE_URL), 0 failures
```

## New Files (6)
| File | Purpose |
|------|---------|
| `core/daily_tracker/persistence.py` | Filesystem + DB persistence |
| `core/db/migrations/versions/0014_daily_tracker_enum.py` | PG ENUM migration |
| `tests/daily_tracker/test_persistence.py` | 16 persistence unit tests |
| `tests/daily_tracker/test_infra_wiring.py` | 6 infrastructure tests |
| `tests/api/test_daily_tracker_runner.py` | 11 runner tests |
| `tests/db/test_daily_tracker_persistence.py` | 8 DB integration tests |

## Modified Files (7)
| File | Change |
|------|--------|
| `core/db/models/__init__.py` | Added `daily_tracker` import |
| `core/db/enums.py` | Added `daily_tracker` to PipelineType |
| `api/tasks/models.py` | Added `"daily_tracker"` to PipelineTask Literal |
| `api/tasks/runner.py` | Added `run_daily_tracker_task()` |
| `api/routers/daily_tracker.py` | Refactored 3 endpoints (async + DB) |
| `tests/daily_tracker/test_api_endpoints.py` | Updated for new endpoint behavior |
| `docs/API_DOCUMENTATION.md` | Updated response schemas |

## Key Design Decisions
1. **String company_id** for daily_tracker tables (not UUID FK) — matches existing ORM
2. **Three-UUID separation**: task_id (SSE), pipeline_run_id (PipelineRunModel), result.run_id (daily_runs.id)
3. **Two-phase write**: create_daily_run_record (running) → persist_daily_run_result (completed/failed)
4. **Source-module patching** for lazy imports in runner tests (F12 lesson)
5. **Breaking API change**: POST /runs now async (returns task_id) — aligns with all other pipelines
