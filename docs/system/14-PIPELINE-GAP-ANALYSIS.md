# Pipeline 2: Gap Analysis

> **Location:** `core/gap_analysis/`
> **Owner:** Core
> **Dependencies:** OpenAI, Anthropic, Google, Perplexity, pgvector, numpy, scipy, Plotly
> **Dependents:** Pipeline 3 (Content Engine), Pipeline 4 (Topic Discovery), frontend Embedding Lab
> **Last Updated:** 2026-04-09

## Overview

Pipeline 2 is an 8-step citation gap analysis system that measures how well a company's content is cited by AI search platforms compared to competitors. It crawls and embeds the company's website (Branch A), generates search queries across buyer stages, searches 4 AI platforms, extracts and embeds citation content (Branch B), then computes semantic similarity gaps, generates visualizations, and produces actionable reports. This is the most complex pipeline in the system with ~8,100 lines of code.

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
                                       S4: Enrich Citations
                                         crawl URLs → extract text + signals
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

## File Structure

| Directory | File | Lines | Purpose |
|-----------|------|-------|---------|
| root | `pipeline.py` | 836 | Main orchestrator |
| root | `persistence.py` | 703 | DB persistence hooks (per-step) |
| root | `topic_cluster_map.py` | 228 | Buyer stage x intent → cluster mapping |
| steps | `s1_embed_assets.py` | 1,427 | Crawl + chunk + embed company website |
| steps | `s2_generate_queries.py` | 990 | LLM query generation + cluster taxonomy |
| steps | `s3_search_platforms.py` | 454 | Multi-engine search with circuit breaker |
| steps | `s4_enrich_citations.py` | 591 | URL crawling + structural signal extraction |
| steps | `s5_embed_content.py` | 389 | Query + paragraph embedding |
| steps | `s6_analyze.py` | 573 | Gap computation + exemplar selection |
| steps | `s7_visualize.py` | 763 | UMAP/t-SNE + Plotly visualizations |
| steps | `s8_generate_report.py` | 573 | Markdown + JSON report generation |
| engines | `base.py` | 23 | Abstract SearchEngine base |
| engines | `openai_engine.py` | 113 | OpenAI with web_search tool |
| engines | `claude.py` | 187 | Claude with web_search beta |
| engines | `gemini.py` | 163 | Gemini with google_search tool |
| engines | `perplexity.py` | 76 | Perplexity via OpenRouter |

## The 8 Steps

### S1: Embed Company Assets (1,427 lines)
Crawls company website via robots.txt/sitemaps/BFS, chunks text semantically, embeds with OpenAI `text-embedding-3-small` (1536-dim), stores in pgvector.

**Output:** `company_embeddings.json`, `company_page_analysis.json`, pgvector collection

### S2: Generate Queries (990 lines)
LLM generates search queries aligned to 9 clusters (C1-C9) mapped across buyer stages (TOFU/MOFU/BOFU) and intent types (informational/commercial/transactional/navigational).

**9 Clusters:** Mechanism, Boundary, Category Comparison, Decision Criteria, Definition, Problem/Awareness, Best-of/Consideration, Branded Evaluation, Feature Verification

**Output:** `queries.json`

### S3: Search Platforms (454 lines)
Executes queries across 4 engines in parallel with per-engine concurrency limits and circuit breaker.

**Engines:**
| Engine | Model | Citation Source |
|--------|-------|----------------|
| OpenAI | gpt-5.2 + web_search | response.output annotations |
| Claude | claude-sonnet-4-6 + web_search beta | citations array |
| Gemini | gemini-3-flash + google_search | groundingMetadata |
| Perplexity | sonar-pro via OpenRouter | native citations |

**Resilience:** Exponential backoff retry (429, 5xx, timeout), circuit breaker after N consecutive failures.

**Output:** `platform_results/{engine}_results.jsonl`

### S4: Enrich Citations (591 lines)
Crawls citation URLs, extracts text via trafilatura/BeautifulSoup, computes 45 structural signals per URL. Three-tier content extraction fallback.

**45 Structural Signals:** word_count, reading_level, header hierarchy, list elements, content patterns (FAQ, definitions, key takeaways, comparison tables, steps), factual density, authority/content type classification.

**Output:** `enriched_citations.json`

### S5: Embed Content (389 lines)
Three-phase pipeline: collect + sanitize paragraphs, bulk embed via OpenAI, cosine similarity scoring (top-K per citation). Garbage detection for binary/base64 content.

**Output:** Embeddings in pgvector, `queries_with_embeddings.json`, `citations_with_embeddings.json`

### S6: Analyze Gaps (573 lines)
**The core algorithm.** Computes per-query gap scores:

```
gap = max_citation_similarity - max_company_similarity
```

**Classification:**
| Gap Range | Classification |
|-----------|---------------|
| >= 0.15 | significant_gap |
| >= 0.05 | gap_to_close |
| <= -0.05 | company_wins |
| else | roughly_equal |

Also computes: exemplar selection (top-3 per query), content briefs from exemplar signals, cluster specs, SPA (Statistical Proximity Analysis via t-test), centroid distances.

**Output:** `analysis.json`

### S7: Visualize (763 lines)
Generates interactive Plotly HTML visualizations: UMAP/t-SNE embedding projections, gap distribution histograms, cluster heatmaps, citation rankings.

**Output:** `visualizations/*.html`

### S8: Report (573 lines)
Programmatic markdown (top 25 gaps) + LLM-generated executive summary + 5 prioritized content recommendations. Per-cluster generation specs.

**Output:** `gap_report.md`, `gap_report.json`, `generation_spec.md`, `generation_spec.json`

## DB Persistence

Per-step hooks in `persistence.py`. Filesystem-first, DB-additive. Idempotent (delete + re-insert per run_id).

| Step | Tables |
|------|--------|
| S2 | `run_queries` |
| S3 | `run_citations`, `platform_result_cache` |
| S4 | `url_enrichment_cache`, `url_structural_signals` |
| S5 | `query_embeddings` |
| S6 | `query_gaps`, `query_exemplars`, `cluster_specs`, `spa_results`, `centroids`, `cluster_proximity_stats` |

## Topic-Scoped GA

Integration with Topic Discovery: uses `generate_queries_from_topics()` for topic-specific queries, reuses S1 embeddings from base run, runs S3-S8 with scoped queries.

## Configuration

All settings prefixed `gap_analysis_*` in `core/config/settings.py`. Key params: concurrency limits per engine, retry counts, circuit breaker thresholds, embedding batch sizes, model selections.
