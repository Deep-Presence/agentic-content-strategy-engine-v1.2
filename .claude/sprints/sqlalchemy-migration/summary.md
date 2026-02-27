# Sprint sqlalchemy-migration — Summary

**Date:** 2026-02-28
**Sprint Goal:** SQLAlchemy 2.0 migration — Phase 1 (DB infrastructure) + Phase 2 (Auth Migration from JSON AuthStore to async DB-backed AuthService)

## Completed Tasks
| Task ID | Description | Tests Added | Files Changed |
|---------|-------------|-------------|---------------|
| T-sqlalchemy-migration | Phase 1: ORM tables (31), Alembic migrations (2), repos (8), DI wiring | +44 DB tests | 44 new files |
| T-auth-migration-phase2 | Phase 2: Auth utility extraction, AuthServiceProtocol, JsonAuthService, DbAuthService, 3 new repos, DI wiring, middleware decoupling, all 8 routers migrated to async | +96 tests | 18 new + 32 modified |

## Decisions Made
- D-DB-1: Pure SQLAlchemy 2.0 Declarative (NOT SQLModel) — 6-0 scorecard. Lazy engine init, PgUUID PKs, flush-only repos, hand-written migrations, savepoint test isolation.
- D-AUTH-2: Three-layer decomposition (utilities → protocol+dual services → DI switch). Dual-mode adapter (JsonAuthService + DbAuthService) for zero test breakage. Middleware decoupled from AuthStore.

## Failures Encountered
- None

## Deferred to Backlog
- CHECK constraints on enum columns (Codex recommendation — deferred, Postgres enums already validate)
- Rank uniqueness constraint on tracking_snapshots (needs application-level handling)
- Cache model_version uniqueness (deferred to Phase 2B-services)
- Unit-of-work abstraction (over-engineering for current scale)
- Phase 2B-services: Wire service layers (GapData, ContentData, BrandData) to DB repos
- Phase 2C-taskstore: Migrate TaskStore from JSON to DB
- Phase 3: Wire repos into FastAPI routes via DI (artifact reads from DB)

## Phase 2 Architecture

### Three-Layer Decomposition
```
Layer 1 — Pure Utilities (core/auth/utils/)
  passwords.py: hash_password, verify_password, DUMMY_HASH
  tokens.py: create_access_token, create_stream_token, verify_token, get_secret_key
  domain.py: normalize_domain, derive_slug, mutable field frozensets

Layer 2 — Service Protocol + Dual Implementations
  core/auth/service.py:      AuthServiceProtocol (runtime_checkable)
  core/auth/json_service.py: JsonAuthService (wraps AuthStore via asyncio.to_thread)
  core/auth/db_service.py:   DbAuthService (uses DB repos)

Layer 3 — DI Switch (api/dependencies.py)
  get_auth_service() → DbAuthService if DATABASE_URL, else JsonAuthService
```

### New Repositories (Phase 2C)
- InviteRepository: get_by_code, mark_redeemed, list_by_company
- ProductRepository: get_by_slugs, list_by_company
- PipelineDefaultsRepository: get_by_company, upsert

### Router Migration (Phase 2F)
All 8 routers + runner migrated: `def` → `async def`, `auth_store` → `auth_service`, all store calls → `await`
- auth.py (5 endpoints), settings.py (6 + helper), companies.py (5), tasks.py (1)
- gap_analysis.py, research.py, content.py (parameter passthrough)
- knowledge_docs.py (unused imports cleaned)
- runner.py: _resolve_scope_async added alongside sync _resolve_scope

## Test Count
- Start of sprint: 1029 tests (from settings-knowledge-docs)
- After Phase 1: 1073 tests (+44 DB tests)
- After Phase 2: 1168 tests (+96 auth migration tests)
- Final: 1080 passed + 88 skipped = 1168 collected
- Pre-existing failure: PB-39 (HITL test_revise_loops_back_to_agent)

## Key Metrics
- Tasks completed: 2 (Phase 1 + Phase 2)
- Tasks deferred: 3 (Phase 2B-services, Phase 2C-taskstore, Phase 3)
- New files created: 62 (44 Phase 1 + 18 Phase 2)
- Files modified: 35 (3 Phase 1 + 32 Phase 2)
- ORM tables: 31
- Postgres enum types: 12
- Domain repositories: 11 (8 Phase 1 + 3 Phase 2)
- Total tests: 1168 (140 new across both phases)
