# Pipeline 2: Gap Analysis

> **Location:** `core/gap_analysis/`
> **Owner:** Core
> **Dependencies:** OpenAI, Anthropic, Google, Perplexity, pgvector, numpy, scipy, Plotly
> **Dependents:** Pipeline 3 (Content Engine), Pipeline 4 (Topic Discovery), frontend Embedding Lab, Content Performance (freshness benchmarking)
> **Last Updated:** 2026-04-15

## Overview

Pipeline 2 is an 8-step citation gap analysis system that measures how well a company's content is cited by AI search platforms compared to competitors. It crawls and embeds the company's website (Branch A), generates search queries across buyer stages, searches 4 AI platforms, extracts and embeds citation content (Branch B), then computes semantic similarity gaps, generates visualizations, and produces actionable reports. This is the most complex pipeline in the system with ~8,100 lines of code.

Recent updates (post-`a9b85f5`):

- **S4 extracts freshness dates** from cited HTML (publication + modification timestamps) alongside structural signals. Commit `2b04149` "benchmark freshness against cited exemplars".
- **url_enrichment_cache** gained `published_at` / `modified_at` columns via migration `0040`.
- New repository method `GapAnalysisRepository.get_cited_exemplar_dates_for_inventory_url()` returns cited-exemplar freshness dates for a given published URL — consumed by Content Performance to benchmark staleness.

## Architecture

```
BRANCH A (Company Assets)              BRANCH B (Citation Search Chain)
─────────────────────────              ─────────────────────────────────
S1: Discover + Embed                   S2: Generate Queries
  crawl → chunk → embed →               LLM → cluster taxonomy
  pgvector                               → queries.json
                                         │
                                       S3: Search 4 Platforms
                                         OpenAI, Claude, Gemini, Perplexity
                                         → platform_results/
                                         │
                                       S4: Enrich Citations + Freshness
                                         crawl URLs → extract text + signals
                                         + published_at / modified_at
                                         → enriched_citations.json
                                         │
                                       S5: Embed Content
                                         queries + paragraphs → pgvector
                                         │
                    ┌──────────────────────┘
                    ▼
S6: Analyze (MERGE) ── cosine similarity → gaps → exemplars → content briefs
                    │
                    ▼
S7: Visualize ───── UMAP/t-SNE + Plotly HTML
                    │
                    ▼
S8: Report ──────── LLM summary + markdown + JSON
```

## The 8 Steps

### S1: Discover + Embed (~1,427 lines)
Crawl company website via multi-strategy async crawler, chunk content, embed via OpenAI, store in pgvector.

### S2: Generate Queries (~990 lines)
LLM generates search queries across buyer stages and intent types using cluster taxonomy.

### S3: Search 4 Platforms (~454 lines)
Multi-engine search with circuit breaker pattern across OpenAI, Claude, Gemini, and Perplexity.

### S4: Enrich Citations + Freshness (~625 lines)
Crawls citation URLs, extracts main content via trafilatura/BeautifulSoup, computes 45 structural signals per URL, **and extracts publication + modification dates**. Three-tier content extraction fallback (trafilatura → semantic selectors → full page). `trafilatura.extract()` calls serialized via module-level `threading.Lock()` (lxml not thread-safe).

**Freshness extraction** (commit `2b04149`, `core/gap_analysis/steps/s4_enrich_citations.py:381-390`):

```python
def _extract_freshness_dates(html: str) -> Tuple[datetime | None, datetime | None]:
    soup = BeautifulSoup(html, "html.parser")
    publish_date_str, modified_date_str = _extract_freshness(soup)
    published_at = _parse_date_robust(publish_date_str) if publish_date_str else None
    modified_at = _parse_date_robust(modified_date_str) if modified_date_str else None
    return published_at, modified_at
```

- Reuses `_extract_freshness` from `core/site_audit/steps/s2_analyze_pages.py` (Open Graph / schema.org / meta tags / `<time>` elements).
- Reuses `_parse_date_robust` from `core/site_audit/checks/eeat_signals.py` for resilient parsing across ISO, RFC 822, and free-form formats.
- Wrapped by `_parse_html_payload()` (lines 607-613) returning `(paragraphs, signals, published_at, modified_at)`.

**Parse phase** (`enrich_citations()` at lines 527-595): each fetched HTML run through `_parse_html_payload` under semaphore-bounded `asyncio.to_thread`. The unpacked tuple flows into `EnrichedCitation(..., published_at=..., modified_at=...)`.

**Model change** (`core/models/gap_analysis.py:321-327`):
```python
class EnrichedCitation(BaseModel):
    ...
    structural_signals: Optional[StructuralSignals] = None
    published_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    is_company_citation: bool = False
```

**45 Structural Signals** (unchanged): word_count, reading_level, header hierarchy, list elements, content patterns (FAQ, definitions, key takeaways, comparison tables, steps), factual density, authority/content type classification.

### S5: Embed Content (~389 lines)
Three-phase pipeline: collect + sanitize paragraphs, bulk embed via OpenAI, cosine similarity scoring.

### S6: Analyze Gaps (~573 lines)
The core algorithm: `gap = max_citation_similarity - max_company_similarity`. Classification, exemplar selection, content briefs, cluster specs, SPA (t-test), centroid distances.

### S7: Visualize (~763 lines)
UMAP/t-SNE dimensionality reduction + Plotly interactive HTML.

### S8: Report (~573 lines)
LLM-generated summary + markdown + JSON report.

## DB Persistence

Per-step hooks in `persistence.py`. Filesystem-first, DB-additive. Idempotent (delete + re-insert per run_id).

| Step | Tables |
|------|--------|
| S2 | `run_queries` |
| S3 | `run_citations`, `platform_result_cache` |
| S4 | `url_enrichment_cache` (now includes `published_at` / `modified_at`), `url_structural_signals` |
| S5 | `query_embeddings` |
| S6 | `query_gaps`, `query_exemplars`, `cluster_specs`, `spa_results`, `centroids`, `cluster_proximity_stats` |

**S4 persistence change** (`core/gap_analysis/persistence.py:287-291`): the `url_enrichment_cache` row payload now includes `published_at` and `modified_at`.

**Migration `0040`**: adds `published_at` and `modified_at` nullable timestamptz columns to `url_enrichment_cache`. Downgrade drops them in reverse order.

## Freshness Benchmarking — Feeding Content Performance

Commit `2b04149` introduces a dedicated query joining content inventory → content pieces → gap targets → cited exemplars → url_enrichment_cache.

`GapAnalysisRepository.get_cited_exemplar_dates_for_inventory_url(company_id, inventory_url, normalized_url=None)` — `core/db/repositories/gap_analysis_repo.py:253-309`. Full reference in [03-CORE-DB.md](03-CORE-DB.md).

**Query shape:**
```sql
SELECT url_enrichment_cache.modified_at, url_enrichment_cache.published_at
FROM url_enrichment_cache
JOIN query_exemplars ON query_exemplars.url_enrichment_id = url_enrichment_cache.id
JOIN query_gaps ON query_gaps.id = query_exemplars.query_gap_id
JOIN content_pieces ON content_pieces.id = query_gaps.targeted_by_content_id
WHERE content_pieces.company_id = :company_id
  AND content_pieces.published_url IN (:url_candidates)
```

- `url_candidates` built from `{inventory_url, normalized_url}` plus trailing-slash variants.
- Returns `best_date = modified_at or published_at` per row. Null rows dropped.
- Content Performance service computes freshness by comparing page's own `modified_at` against `max()` of exemplar dates.

**What it measures:** *the staleness of competing content that AI platforms are citing for queries targeted by this page*. A published page whose modification date lags the exemplar set is surfaced with a freshness delta, suggesting the user refresh.

**Consumed by:**
- `content_performance_service` — drawer freshness badge and refresh recommendation.
- Planner recommendations — briefs listing stale competing exemplars are prioritized.
- Not yet exposed in S8 report output.

## Topic-Scoped GA

Integration with Topic Discovery: uses `generate_queries_from_topics()` for topic-specific queries, reuses S1 embeddings from base run, runs S3-S8 with scoped queries. Unchanged by freshness work.

## Configuration

All settings prefixed `gap_analysis_*` in `core/config/settings.py`. Key params: concurrency limits per engine, retry counts, circuit breaker thresholds, embedding batch sizes, model selections.

## Testing

| Test file | Purpose |
|-----------|---------|
| `tests/gap_analysis/steps/test_s4_enrich_citations.py` | URL enrichment, freshness date extraction (happy + missing + malformed) |
| `tests/gap_analysis/test_persistence.py` | `persist_s4` writes `published_at`/`modified_at` |
| `tests/db/test_gap_analysis_repo.py` | `get_cited_exemplar_dates_for_inventory_url` JOIN correctness, URL candidate expansion |

## Error Handling

- HTML date extraction failures fall through to `None` — freshness always optional.
- `_parse_date_robust` swallows `ValueError`/`TypeError` and returns `None`.
- Repository returns empty list when no exemplars exist; callers treat empty as "no benchmark available".

## Related Commits

- `2b04149` — benchmark freshness against cited exemplars (s4 + persistence + repo + migration 0040)
- `2e811e1` — gap analysis backend enhancements + DI wiring for content performance gaps
