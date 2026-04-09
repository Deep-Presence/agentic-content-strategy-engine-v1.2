# Core Content Inventory

> **Location:** `core/content_inventory/`
> **Owner:** Core
> **Dependencies:** pgvector, `core/db/repositories/content_inventory_repo.py`
> **Dependents:** Pipeline 4 (cannibalization detection), Content Performance, CMS sync
> **Last Updated:** 2026-04-09

## Overview

The content inventory module maintains a universal, CMS-agnostic registry of all content pages for a company. Pages are ingested from multiple sources (site audit crawls, gap analysis crawls, CMS syncs, CSV imports, content engine output) and deduplicated via aggressive URL normalization. Each page can have a pgvector embedding for similarity search and cannibalization detection.

## File Structure

| File | Purpose |
|------|---------|
| `models.py` | DTOs: `CrawledPageData`, `CannibalizationMatch`, `ExistingCoverageResult` |
| `hydration.py` | Ingest from site audit and gap analysis into DB |
| `url_utils.py` | URL normalization and path extraction |

## URL Normalization

More aggressive than site audit's normalize_url (which preserves query params):
- Force HTTPS, strip www, lowercase host
- **Strip ALL query parameters** and fragments
- Remove trailing slash (unless root)
- Example: `HTTP://WWW.Example.Com/Blog/Post/?utm=x#section` → `https://example.com/blog/post`

## Hydration Sources

### From Site Audit
Extracts metadata from `PageAuditResult` (title, h1, meta description, word count, structural signals). Bulk upserts via `ContentInventoryRepository.upsert_by_url()`.

### From Gap Analysis
Reads `company_page_analysis.json` and `discovered_pages.json` from artifacts. Pre-computed structural signals from S4.

Both hydration functions use **graceful degradation** — all exceptions caught, logged, never crash the pipeline. Returns `{"upserted": N, "skipped": N}` or `None` on failure.

## Cannibalization Detection

Used by Topic Discovery Pipeline B expansion:
1. Build enriched query text from topic assignment
2. Query pgvector similarity index against content_inventory embeddings
3. Apply penalty: 0.80-0.90 sim → 0-20% reduction, 0.90+ → 20-35% reduction
4. Enrich assignment metadata with `cannibalization_risk` and `cannibalization_matches`

## Service Layer

`ContentInventoryService` (in `core/services/content_inventory_service.py`, 645 lines, DB-only):
- `ingest_from_site_audit()` — bulk page ingestion
- Embedding text formula: `"{title} | {h1_text} | {meta_description} | {content_preview}"`
- Structural signal computation from page audit results
