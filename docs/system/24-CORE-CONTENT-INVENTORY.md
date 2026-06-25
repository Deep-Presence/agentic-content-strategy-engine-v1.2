# Core Content Inventory

> **Location:** `core/content_inventory/`, `core/services/content_inventory_service.py`
> **Owner:** Core
> **Dependencies:** pgvector, trafilatura, `core/db/repositories/content_inventory_repo.py`, `core/db/repositories/content_inventory_prompt_repo.py`
> **Dependents:** Pipeline 4 (cannibalization detection), Content Performance, CMS sync + publish, Content-to-Prompt pipeline
> **Last Updated:** 2026-04-15

## Overview

Content inventory is the universal, CMS-agnostic registry of every content page a company owns. Pages are ingested from five sources (site audit, gap analysis, CMS sync, CSV import, content engine output), deduplicated via aggressive URL normalization, and stored alongside pgvector embeddings for similarity search.

Changes since `a9b85f5`:

- **`enrich_thin_pages()`** — trafilatura-powered post-hoc enrichment for pages with thin `content_preview` (commit `1755c27`).
- **Content-to-Prompt pipeline integration** — `content_inventory_prompts` join table, 6 API endpoints under `/api/v1/content-to-prompt/`, security hardened (commit `144b52d`).
- **Unpublished pages staging** (commit `6690e61`) — frontend-only contract: approved content engine pieces with `published_at=NULL` surfaced as "Unpublished" in Content Performance.

## Architecture

```
Ingestion sources                    Embedding                      Similarity queries
─────────────────────────────        ────────────────               ────────────────────
Site audit → hydration.py                                            check_cannibalization()
Gap analysis → hydration.py      →   _EMBED_TEMPLATE             →   find_existing_coverage()
CMS sync → ingest_from_cms_sync      title | h1 | meta | preview     find_similar_pages()
CSV import → ingest_from_csv         → OpenAI text-embedding-3        (pgvector cosine)
Content Engine publish →             → pgvector (1536-dim)
   register_published_content
                 │
                 ▼
       enrich_thin_pages (trafilatura fetch + update)
                 │
                 ▼
   content_to_prompt_orchestrator.run_for_pages(..., k=6, auto_approve=True)
                 │
                 ▼
   content_inventory_prompts join table (M:N with tracked_prompts)
```

## File Structure

| File | Purpose |
|------|---------|
| `core/content_inventory/models.py` | DTOs: `CrawledPageData`, `CannibalizationMatch`, `ExistingCoverageResult` |
| `core/content_inventory/hydration.py` | Ingest from site audit and gap analysis |
| `core/content_inventory/url_utils.py` | URL normalization + path extraction |
| `core/services/content_inventory_service.py` | Orchestrator (cross-ref [09-CORE-SERVICES.md](09-CORE-SERVICES.md)) |
| `core/db/repositories/content_inventory_repo.py` | SQL + pgvector queries for `content_inventory` |
| `core/db/repositories/content_inventory_prompt_repo.py` | M:N join table + metric rollups (see [03-CORE-DB.md](03-CORE-DB.md)) |

## URL Normalization

More aggressive than site audit's `normalize_url`:
- Force HTTPS, strip `www`, lowercase host.
- **Strip ALL query parameters** and fragments.
- Remove trailing slash (unless root).
- Example: `HTTP://WWW.Example.Com/Blog/Post/?utm=x#section` → `https://example.com/blog/post`.

## Service Layer

Full method signatures in [09-CORE-SERVICES.md](09-CORE-SERVICES.md). Key domain methods:

### Embedding
`_embed_texts()` — OpenAI `text-embedding-3-small`, 1536-dim. Embedding text formula: `"{title} | {h1_text} | {meta_description} | {content_preview[:300]}"`.

### Ingestion: Site Audit
`ingest_from_site_audit()` — walks `discovery_output.pages_with_html` + `page_results`, computes structural signals, bulk upserts with `ingestion_run_id=pipeline_run_id`.

### Ingestion: CMS Sync
`ingest_from_cms_sync()` — returns `(pairs, new_page_ids)` where `pairs` links inventory to CMS identifiers and `new_page_ids` triggers auto-prompt generation for genuinely new URLs.

### Register Published Content
`register_published_content()` — called by `CMSService.publish_brief` after CMS write. Computes structural signals from rendered HTML, upserts row, performs inline embedding. Exceptions in embedding are isolated (warn + return).

### Cannibalization Detection
- `check_cannibalization(company_id, topic_text, threshold=0.82)` — single-topic embed + pgvector query.
- `check_cannibalization_batch(company_id, topics, threshold=0.82)` — batch embed + multi-query pgvector scan via `find_similar_batch()`.
- `find_similar_pages(company_id, page_id, threshold=0.78, limit=5)` — intra-inventory cannibalization for Content Performance drawer.

### Thin-Page Enrichment (commit `1755c27`)
`enrich_thin_pages(company_id, min_content_chars=100, batch_size=10)`:

1. Pulls inventory rows, filters to `len(content_preview or "") < min_content_chars`.
2. For each thin row (up to `batch_size`): `asyncio.to_thread(_fetch_page_text, url)` — blocking trafilatura call.
3. If extracted text meets threshold, writes `content_preview = text[:500]` and `word_count`.
4. Per-page errors caught and logged; loop continues.
5. Returns count of pages enriched.

**Scalability notes**: `batch_size` is the single knob. No persistent queue — callers run on a schedule or after CMS sync.

## Content-to-Prompt Integration

### Join Table: `content_inventory_prompts`
See [03-CORE-DB.md](03-CORE-DB.md) for full ORM reference. Design decision: M:N chosen over FK on `tracked_prompts` for per-link metadata, multi-page coverage, and `company_id` type mismatch avoidance.

### Chaining from CMS Publish
`CMSService.publish_brief` → `_auto_generate_prompts_for_published_page()` → `content_to_prompt_orchestrator.run_for_pages(..., k=6, auto_approve=True)`.

### Security Hardening (commit `144b52d`)
- **Tenant isolation**: JOIN through `ContentInventoryModel` filtering on `company_id`.
- **Prompt injection guards**: orchestrator strips/sanitizes user-supplied fields before LLM.
- **Dedup race fix**: pre-existing link check + single `bulk_create_links` flush.

### API Endpoints
6 endpoints under `/api/v1/content-to-prompt/`:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/generate` | Run LLM pipeline for pages |
| GET | `/page/{inventory_id}` | List prompts linked to a page |
| GET | `/metrics` | Per-page metric rollups |
| GET | `/pending` | Unapproved links for review |
| POST | `/approve` | Bulk approve by link IDs |
| POST | `/regenerate` | Delete non-user-edited links + re-run |

## Unpublished Pages Staging (commit `6690e61`)

The backend contract is unchanged: `ContentPieceModel` rows with `status=approved` and `published_url=None` are the "unpublished" set. The frontend (`UnpublishedPagesTable.tsx`) filters existing briefs on these fields. No new DB state added.

## Integration Points

| Consumer | Method | Notes |
|----------|--------|-------|
| Site audit pipeline | `ingest_from_site_audit` | Called after S6 |
| Gap analysis hydration | `hydration.py` | Reads `company_page_analysis.json` |
| CMS sync | `ingest_from_cms_sync` | Savepoint-isolated |
| CMS publish | `register_published_content` | Inline embed + auto-prompt chain |
| Topic Discovery Pipeline B | `check_cannibalization_batch` | Batched per topic cluster |
| Content Engine (briefs) | `find_existing_coverage` | Injected into brief context |
| Content Performance drawer | `find_similar_pages` | Intra-inventory cannibalization |
| Content-to-Prompt | `content_inventory_prompt_repo` | Join-table CRUD |

## Error Handling

- Ingestion uses **graceful degradation** — all exceptions caught, logged, never crash the pipeline.
- Inline embedding during `register_published_content` logs `content_inventory.inline_embed_failed` at WARN.
- `enrich_thin_pages` catches per-item exceptions and continues.
- CMS sync hydration wrapped in nested savepoint.

## Testing

| Test file | Purpose |
|-----------|---------|
| `tests/services/test_content_inventory_service.py` | Ingestion, cannibalization, `enrich_thin_pages`, `register_published_content` |
| `tests/unit/test_content_inventory_prompt_repo.py` | Join-table CRUD, approval, dedup race, tenant isolation |
| `tests/db/test_content_inventory_repo.py` | pgvector similarity, bulk upsert, URL normalization |

## Related Commits

- `1755c27` — enrich published content performance pages
- `144b52d` — content-to-prompt security hardening
- `c0bbff7` — content-to-prompt pipeline
- `6690e61` — move approved content into unpublished pages staging
