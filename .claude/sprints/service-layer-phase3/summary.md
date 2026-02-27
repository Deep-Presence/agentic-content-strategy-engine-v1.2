# Sprint service-layer-phase3 — Summary

**Date:** 2026-02-28
**Sprint Goal:** Migrate three data service layers (Gap, Brand, Content) from filesystem-only to dual Json/Db implementations with service protocols, new SQL repositories, and comprehensive testing.
**Plan File:** `.claude/plans/glowing-soaring-turtle.md`

## Completed Tasks

| Step | Description | Tests Added | Key Files |
|------|-------------|-------------|-----------|
| Step 0 | GapClassification enum fix (significant_gap/gap_to_close/roughly_equal/company_wins/no_data) | 0 | core/db/enums.py |
| Step 1 | Protocols + JSON Wrappers — 3 service protocols, 3 JsonServices (asyncio.to_thread wrappers), DI functions, 14 router endpoints converted to async with service injection | 0 (existing tests pass) | core/services/*.py, api/dependencies.py, api/routers/{gap_data,brand_data,content_data}.py, tests/api/conftest.py |
| Step 2 | New Repositories — SignalRepo (averages, correlations, patterns), PlatformRepo (summaries, URL sets, exclusivity), enhanced gap_analysis/pipeline/content repos | +12 DB tests | core/db/repositories/{signal_repo,platform_repo}.py, tests/db/test_signal_repo.py, tests/db/test_platform_repo.py |
| Step 3 | DB Service Implementations — DbGapDataService, DbBrandDataService, DbContentDataService | 0 | core/services/db_{gap,brand,content}_data.py |
| Step 4 | Backfill Script — idempotent JSON-to-DB migration with composite FK ordering | 0 | scripts/backfill_gap_data.py |
| Step 5 | Integration Testing — protocol conformance (9 tests), DB service tests (25 tests, auto-skip) | +34 tests | tests/services/*.py |

## Decisions Made
- D-SVC-1: Three separate service protocols with dual Json/Db implementations (not one monolithic protocol)

## Failures Encountered
- Import error: `core.db.base` doesn't have engine/session — correct module is `core.db.engine` (get_engine, get_session_factory)
- CentroidResultModel doesn't have `cluster_id` column — only `cluster_name` and `distance`
- Composite FK: run_citations(run_id, query_id) requires run_queries to be inserted first with intermediate flush
- Wrong import: `core.db.models.url_enrichment` doesn't exist — correct module is `core.db.models.cache`

## Deferred to Backlog
- Phase 4 (pipeline write hooks) — populate DB tables during pipeline execution
- Phase 2C (TaskStore migration) — JSON to DB
- Parity tests (JSON vs DB response equality) — deferred, protocol conformance tests cover type compliance

## Test Count
- Start of session: 1168 tests (1080 passed + 88 skipped)
- End of session: 1213 tests (1088 passed + 125 skipped)
- New tests: +46 (9 protocol conformance passed + 37 DB tests skipped without TEST_DATABASE_URL)

## Key Metrics
- Tasks completed: 6 steps (Step 0-5)
- Files created: 16 new files
- Files modified: 14 files
- New repositories: 2 (SignalRepository, PlatformRepository)
- Enhanced repositories: 3 (gap_analysis_repo, pipeline_repo, content_repo)
- Service protocols: 3 (GapDataServiceProtocol, BrandDataServiceProtocol, ContentDataServiceProtocol)
- Service implementations: 6 (3 Json + 3 Db)

## Architecture Summary

```
Router (async def)
  → Depends(get_gap_data_service)
    → JsonGapDataService (default, wraps api/services/ via asyncio.to_thread)
    → DbGapDataService (opt-in with DATABASE_URL, uses SQL repos)
```

Each DbService resolves `effective_slug → latest completed pipeline_run.id` via `pipeline_repo.get_latest_completed()`, then queries domain-specific repos. Filesystem operations (embedding projections, research artifacts, stage content) remain filesystem-backed via `asyncio.to_thread` delegation even in Db services.