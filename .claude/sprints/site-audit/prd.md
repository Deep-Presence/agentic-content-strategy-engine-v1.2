# Sprint: Site Audit Module (Pipeline 0)

**Date:** 2026-02-28
**Branch:** feat/front-back
**Sprint Goal:** Build a production-grade site audit module that diagnoses how AI-ready a website is.

## Context

Pipeline 0 sits before the existing Gap Analysis pipeline. It audits 8 dimensions of a website (crawlability, performance, on-page SEO, content extractability/AEO, schema markup, E-E-A-T, freshness, security), scores them 0-100, and generates actionable reports. 100% deterministic — no LLM calls.

## Team Structure

4-teammate agent team with file ownership boundaries:

| Teammate | Role | Tasks |
|----------|------|-------|
| architect | Models, config, repo, pipeline skeleton | T1-T4 |
| crawler | s1 discovery, s2 page analysis, 4 check modules | T5-T7 |
| analyzers | s3 schema, s4 AEO, extractability, performance checks | T8-T9 |
| api-service | Router, schemas, data service, runner integration | T10-T11 |
| leader (me) | Scoring, aggregation, reporting, pipeline wiring | T12-T14 |

## Tasks (14 total)

### Phase 1: Foundation (architect)
- [x] T1: Pydantic v2 models (AuditDimension, AuditCheckSeverity, SiteAuditInput, AuditFinding, SchemaDetectionResult, AEOReadinessResult, PageAuditResult, DimensionScore, SiteAuditResult)
- [x] T2: AuditConfig frozen dataclass with penalty/grade helpers, dimension weights summing to 1.0
- [x] T3: SiteAuditRepository with flush-only contract
- [x] T4: Pipeline skeleton with run_site_audit() stub + settings additions

### Phase 2: Crawling & Checks (crawler)
- [x] T5: AsyncSiteCrawler — 4-phase discovery (robots.txt → sitemaps → RSS/Atom → BFS), AI bot detection, httpx.MockTransport injection
- [x] T6: s2_analyze_pages — per-page analysis with crawlability, on-page SEO, E-E-A-T, security, freshness checks
- [x] T7: 4 check modules — crawlability.py, on_page_seo.py, eeat_signals.py, security.py

### Phase 3: Analysis (analyzers)
- [x] T8: s3_check_schema — JSON-LD detection with @graph handling, type validation, per-block try/except
- [x] T9: s4_check_aeo + extractability.py + schema_checks.py + performance.py

### Phase 4: API Layer (api-service)
- [x] T10: Router (6 endpoints: start, status, list, detail, findings, pages) + schemas
- [x] T11: SiteAuditDataServiceProtocol + JsonSiteAuditDataService + runner integration

### Phase 5: Integration (leader)
- [x] T12: scoring.py — compute_dimension_score, compute_all_dimension_scores, compute_overall_score, compute_grade
- [x] T13: s5_aggregate.py + s6_report.py — aggregation, top findings, Markdown + JSON report generation
- [x] T14: Pipeline wiring — replace skeleton with real orchestrator, wire s1→s6 with skip_steps support

## Acceptance Criteria
- [x] All 636 site audit tests pass
- [x] Zero regressions on existing 1342 test baseline
- [x] No LLM calls in any audit step
- [x] Penalty-based scoring (critical=10, high=5, medium=2, low=1, info=0)
- [x] Weighted dimension scores (sum = 1.0)
- [x] Grade thresholds: A≥90, B≥75, C≥60, D≥40, F<40
- [x] API layer with tenant isolation and force_rerun guard
