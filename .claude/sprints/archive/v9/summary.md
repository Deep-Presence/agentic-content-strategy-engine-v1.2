# Sprint v9 — Gap Analysis → Content Engine Data Enrichment

**Date:** 2026-03-07
**Branch:** research-agent-v1.2.0
**Status:** Complete

## Goal

Enrich the data flow from Gap Analysis (Pipeline 2) to Content Engine (Pipeline 3) with three features that enable the content engine to distinguish between "optimize existing page" and "create new content" strategies.

## Features Implemented

### F1: Company URL Passthrough (Small)
- `SemanticUnit.url` was already populated in s1 but never threaded to `QueryGap`
- Added `best_company_url: Optional[str]` to `QueryGap`
- Added `company_best_url: str` to `WorkerQueryContext`
- s6 now tracks `best_unit_url` alongside ID/text
- Context router extracts and renders URL; Brief Builder prompt references it for optimize-vs-create decisions

### F2: Structural Analysis of Company Pages (Medium)
- s4's `_extract_paragraphs()` is self-contained; added public `compute_structural_signals(html)` wrapper
- s1 now computes structural signals per crawled page, builds `CompanyPageAnalysis` objects, saves to `company_page_analysis.json`
- Pipeline loads page analyses, builds URL→signals lookup, passes to s6
- s6 attaches `best_company_structural_signals` to each `QueryGap` by matching best unit URL
- Context router renders "Company Page Structure" section enabling structural comparison

### F3: Self-Citation Detection (Medium)
- Added `is_company_citation: bool` to `CitationRef` and `EnrichedCitation`
- Pipeline helper `_flag_company_citations()` matches citation URLs against company domain (handles www prefix, subdomains)
- `_build_company_citation_map()` runs BEFORE s4 dedup to preserve multi-engine information
- s6 sets `company_cited: bool` and `company_cited_platforms: List[str]` on QueryGap
- Scorecard includes `Cited` column; Strategic Planner considers self-citation status
- Brief Builder prompt distinguishes optimize-existing vs create-new strategies
- Gap report shows self-citation status per gap

## Key Design Decisions

1. **D-GCE-1:** Keep self-citations IN `avg_citation_similarity` calculation — add separate fields as explicit signals
2. **D-GCE-2:** `CompanyPageAnalysis` as separate per-page model, not per-chunk on `SemanticUnit`
3. **D-GCE-3:** Flag citations BEFORE s4 dedup to preserve multi-engine information

## Files Modified (14)

### Models (2)
- `core/models/gap_analysis.py` — `CitationRef`, `EnrichedCitation`, `CompanyPageAnalysis`, `QueryGap` (+5 fields)
- `core/models/content_generation_v13.py` — `QueryScorecard` (+1), `WorkerQueryContext` (+1)

### Pipeline Steps (4)
- `core/gap_analysis/steps/s1_embed_assets.py` — Company page structural analysis
- `core/gap_analysis/steps/s4_enrich_citations.py` — Public wrapper + is_company_citation carry-through
- `core/gap_analysis/steps/s6_analyze.py` — URL tracking, citation map, structural signals lookup
- `core/gap_analysis/steps/s8_generate_report.py` — URL, citation status, structural summary per gap

### Orchestration (1)
- `core/gap_analysis/pipeline.py` — `_flag_company_citations()`, `_build_company_citation_map()`, page analysis loading

### Content Engine (3)
- `core/content_engine/context_router.py` — Scorecard + worker context enrichment
- `core/content_engine/prompts/brief_builder_prompts.py` — Optimize-existing rules
- `core/content_engine/prompts/strategic_planner_prompts.py` — Self-citation criterion

### Tests (4)
- `tests/gap_analysis/steps/test_s6_analyze.py` — 7 new tests (URL, citation, structural)
- `tests/gap_analysis/test_pipeline.py` — 6 new tests (flag + map helpers)
- `tests/content_engine/conftest.py` — Updated fixtures with new fields
- `tests/content_engine/test_context_router.py` — 11 new tests

## Test Results

24 new tests added. All 74 targeted tests pass (gap_analysis + content_engine).

## Backlog Updates

- PB-8 (`company_avg always 0.0 in signal averages`) — Now partially resolved. `best_company_structural_signals` provides per-gap company signals. The gap_data_service aggregate still needs updating to use `company_page_analysis.json` for full resolution.
