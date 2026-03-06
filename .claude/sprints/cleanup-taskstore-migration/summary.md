# Sprint cleanup-taskstore-migration — Summary

**Date:** 2026-02-28
**Sprint Goal:** Cleanup fixes (security, data correctness, API validation) + TaskStore DB migration (protocol, ORM, DbTaskStore, lifespan DI switch)
**Plan:** `.claude/plans/sleepy-moseying-charm.md` (Option D — Codex-reviewed)
**Branch:** `feat/front-back`

## Completed Tasks

| Task ID | Phase | Description | Tests Added | Files Changed |
|---------|-------|-------------|-------------|---------------|
| T1 | A | PB-34: `/me` require_auth fix (SECURITY) | +4 | api/routers/auth.py, tests/api/test_auth_endpoints.py |
| T2 | A | Auth cleanup (create_invite async, get_company_by_id, stale docstrings) | +2 | core/auth/service.py, core/auth/json_service.py, core/auth/db_service.py, api/routers/auth.py, api/auth/middleware.py, tests/api/test_auth_endpoints.py |
| T3 | A | `_derive_slug` consolidation (PB-18) | 0 | api/routers/gap_analysis.py, api/routers/research.py, api/tasks/runner.py |
| T4 | A | Signal repo has_expert_quotes + cluster perf data | +3 | core/db/repositories/signal_repo.py, core/services/db_gap_data.py |
| T5 | A | Gap data validation (sort_dir Literal, page clamping, classification sort) | +5 | api/routers/gap_data.py, core/db/repositories/gap_analysis_repo.py, api/services/gap_data_service.py, core/services/db_gap_data.py, tests/api/test_gap_data.py |
| T6 | B | TaskStoreProtocol definition | +2 | core/services/task_store.py (new) |
| T7 | B | DI wiring + type hint migration to protocol | +2 | api/dependencies.py, api/tasks/runner.py, api/routers/{gap_analysis,research,content,tasks,events}.py |
| T8 | B | ApiTaskModel ORM + TaskRepository + migration 0004 | +10 | core/db/models/api_tasks.py (new), core/db/repositories/task_repo.py (new), core/db/migrations/versions/0004_api_tasks.py (new), core/db/models/__init__.py |
| T9 | C | DbTaskStore with write-through cache | +21 | core/services/db_task_store.py (new), tests/services/test_db_task_store.py (new), tests/services/test_protocol_conformance.py |
| T10 | C | Lifespan integration + DI switch | +4 | api/app.py, tests/api/test_lifespan_task_store.py (new) |

## Decisions Made
- D-TASKSTORE-1: TaskStoreProtocol + DbTaskStore write-through architecture (single-instance durability, horizontal scaling deferred)

## Failures Encountered
- F9: `from __future__ import annotations` makes type annotations strings at runtime → use `get_type_hints()` for introspection
- F10: DB test files need their own `pytestmark` for auto-skip (conftest pytestmark doesn't propagate)
- F11: `asyncio.create_task()` in sync methods requires running event loop — tests must be async with module-level patch

## Deferred to Backlog
- Phase 4 — Pipeline write hooks (populate DB tables during pipeline execution)
- Multi-instance scaling (Redis pub/sub or PG LISTEN/NOTIFY for SSE/cancellation)

## Test Count
- Start of session: 1213 tests (1088 passed + 125 skipped)
- End of session: 1262 tests (1127 passed + 135 skipped)
- New tests: +49

## Key Metrics
- Tasks completed: 10
- Tasks deferred: 0
- New files: 8
- Modified files: ~24
- Phases: 3 (A: Cleanup, B: Protocol+ORM, C: DbTaskStore+Integration)
