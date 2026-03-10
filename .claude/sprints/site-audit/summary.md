# Sprint: Site Audit — Summary

**Date:** 2026-02-28
**Sprint Goal:** Build production-grade site audit module (Pipeline 0) — 8-dimension deterministic website audit

## Completed Tasks

| Task ID | Description | Tests Added | Files Changed |
|---------|-------------|-------------|---------------|
| T1 | Pydantic v2 models (2 enums + 9 models) | +52 | core/models/site_audit.py |
| T2 | AuditConfig frozen dataclass + DEFAULT_AUDIT_CONFIG | +42 | core/site_audit/config.py |
| T3 | SiteAuditRepository (flush-only contract) | +24 | core/db/repositories/site_audit_repo.py |
| T4 | Pipeline skeleton + settings additions | (in T2) | core/site_audit/pipeline.py, core/config/settings.py |
| T5 | AsyncSiteCrawler — 4-phase BFS + AI bot detection | +60 | core/site_audit/steps/s1_discover.py |
| T6 | s2_analyze_pages + 4 check modules | +86 | core/site_audit/steps/s2_analyze_pages.py, checks/*.py |
| T7 | crawlability, on_page_seo, eeat_signals, security checks | (in T6) | core/site_audit/checks/*.py |
| T8 | s3_check_schema + schema_checks.py | +76 | core/site_audit/steps/s3_check_schema.py, checks/schema_checks.py |
| T9 | s4_check_aeo + extractability.py + performance.py | +125 | core/site_audit/steps/s4_check_aeo.py, checks/extractability.py, checks/performance.py |
| T10 | API router (6 endpoints) + schemas | +51 | api/routers/site_audit.py, api/schemas/site_audit.py |
| T11 | SiteAuditDataServiceProtocol + JsonService + runner | (in T10) | core/services/site_audit_data.py, core/services/json_site_audit_data.py |
| T12 | scoring.py — penalty-based dimension scoring | +61 (shared) | core/site_audit/scoring.py |
| T13 | s5_aggregate.py + s6_report.py | (in T12) | core/site_audit/steps/s5_aggregate.py, s6_report.py |
| T14 | Pipeline wiring — real orchestrator replacing skeleton | (in T12) | core/site_audit/pipeline.py |

## Key Architecture Decisions

- **Penalty-based scoring**: Start at 100, deduct per finding severity (critical=10, high=5, medium=2, low=1, info=0), clamp to [0,100]
- **Weighted dimensions**: crawlability(0.20), performance(0.10), on_page_seo(0.15), extractability(0.20), schema_markup(0.10), eeat(0.15), freshness(0.05), security(0.05)
- **Custom async BFS crawler**: Purpose-built (NOT reusing discover_site_tree from gap analysis — that crawler is unreliable)
- **AEO readiness scoring**: 5-component weighted formula (question headings, hooks, self-contained paragraphs, paragraph length, patterns)
- **httpx.MockTransport injection**: For test isolation in crawler (no real network calls)
- **Module-level imports in pipeline.py**: For testability (lazy imports caused AttributeError with mock.patch)

## Failures Encountered

- Pipeline step 3 had duplicate `detect_schema(page.url, page.url)` call using URL as HTML → fixed
- `NotImplementedError` tests broke when skeleton was replaced → converted to signature verification tests
- Lazy imports in pipeline.py caused `AttributeError` with `mock.patch` → moved to module-level imports

## Test Count

- Start of session: 1342 tests (1207 passed + 135 skipped)
- End of session: ~1978 tests (+636 new site audit tests)

## Key Metrics

- Tasks completed: 14
- Tasks deferred: 0
- Files created: ~30 new files
- Files modified: 4 existing files (api/app.py, api/dependencies.py, api/tasks/runner.py, api/tasks/models.py)
- Team size: 4 teammates + leader
