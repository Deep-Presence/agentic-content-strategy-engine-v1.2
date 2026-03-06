# SQLAlchemy + Alembic Migration — Planning & Execution Prompt

## 1. Context & Motivation

We are adding a proper database layer (SQLAlchemy ORM + Alembic migrations) to the Content Strategy Engine. We are using our **own PostgreSQL database** (NOT Supabase — ignore all Supabase references in the codebase). The system currently uses the filesystem as the source of truth for all data, with JSON-file-backed auth and artifact storage.

### Why Now — The Three Drivers

**Driver 1 — Upcoming modules require relational/time-series data:**
1. **Site Audit Module** — recurring audits per site, queryable findings, historical comparison across audit runs
2. **Topic Discovery Module** — another agentic pipeline producing discoverable, linkable topic artifacts
3. **Daily Run Tracker** — time-series mention rate, citation rate, and traffic tracking per content piece per day per platform

Building these on JSON files would create an ad-hoc, unqueryable mess.

**Driver 2 — Incremental content-refresh pipeline:**
After the content engine publishes a piece targeting a specific gap (e.g., query C5-Q1), the gap analysis outputs currently don't reflect that new content. We need a `content-refresh` pipeline that: embeds the new content, recomputes similarity for targeted queries only, patches individual `QueryGap` entries, recomputes cluster-level stats for affected clusters only, and regenerates affected visualizations — all WITHOUT re-running the full 80-minute gap analysis pipeline. This requires granular, row-level update capability that JSON files fundamentally cannot support. With a JSON file, updating one query's gap score means loading the entire 5-10MB file, parsing it, modifying one entry, re-serializing, and writing the whole file back.

**Driver 3 — Pipeline performance optimization via caching:**
The gap analysis pipeline currently takes ~80 minutes for 75 queries because every run re-searches all platforms, re-scrapes all URLs, and re-embeds all content from scratch. With a database-backed cache layer, subsequent runs can reuse cached platform results (TTL-based), cached URL enrichments (TTL-based), and cached paragraph embeddings (content-addressed). This can reduce repeat runs from 80 minutes to ~25 minutes and content-refresh runs to ~4 minutes.

---

## 2. What Already Exists (Read These First)

Before writing any code, thoroughly read and understand these existing files. This is critical — the schema design must be informed by the actual data shapes and access patterns in these files.

### Core Pydantic Models (these inform the ORM models — do NOT modify these files)
- `core/models/organization.py` — `Company`, `Product`, `UserProfile`, `PipelineScope`, `CompanyPipelineDefaults`
- `core/models/artifacts.py` — `CompanyResearchInput`, `CompanyContextArtifact`, `SourceDoc`, `FactRow`
- `core/models/personas.py` — `PersonaResearchInput`, `PersonaArtifact`
- `core/models/style_guide.py` — `StyleGuideResearchInput`, `WritingStyleGuideArtifact`
- `core/models/gap_analysis.py` — **Read this file especially carefully.** It defines `GapAnalysisInput`, `SemanticUnit`, `QueryCluster`, `GeneratedQuery`, `CitationRef`, `PlatformResult`, `StructuralSignals` (45 fields across 4 categories), `EnrichedCitation`, `SpaResult`, `CentroidResult`, `QueryGap`, `ClusterContentSpec`, `AnalysisResult`, `GapReport`, `DiscoveredPage`, `SiteDiscoveryResult`
- `core/models/knowledge_docs.py` — `KnowledgeDocument`

### Pipeline Steps (read these to understand data flow and access patterns)
- `core/gap_analysis/steps/s1_embed_assets.py` — Crawls company website, builds SemanticUnits, embeds via OpenAI, stores in ChromaDB
- `core/gap_analysis/steps/s2_generate_queries.py` — LLM generates 75 buyer-intent queries across 9 clusters
- `core/gap_analysis/steps/s3_search_platforms.py` — Searches 4 AI platforms (ChatGPT, Claude, Perplexity, Gemini), produces PlatformResult objects
- `core/gap_analysis/steps/s4_enrich_citations.py` — **Read carefully.** Scrapes cited URLs, extracts ~45 structural signals per page, produces `enriched_citations.json` (can be 20MB+). The `paragraphs` field (all extracted paragraphs per URL) accounts for ~80% of file size but is only consumed once by s5.
- `core/gap_analysis/steps/s5_embed_content.py` — **Read carefully.** Embeds citation paragraphs, selects top-3 best-matching paragraphs per citation, upserts to ChromaDB. Has deduplication logic (`text_to_idx` dict) within a single run.
- `core/gap_analysis/steps/s6_analyze.py` — **Read carefully.** Computes gap scores, SPA results, cluster specs, content briefs. Iterates all enriched citations to compute per-query and per-cluster metrics. Produces `AnalysisResult`.
- `core/gap_analysis/steps/s7_visualize.py` — Generates UMAP/t-SNE projections, interactive Plotly charts
- `core/gap_analysis/steps/s8_generate_report.py` — Generates gap_report.json, generation_spec.json, gap_analysis_complete.json

### Service Layer (read these to understand how pipeline outputs are consumed by the API)
- `api/services/gap_data_service.py` — **Read this file carefully.** It loads `enriched_citations.json` and `gap_analysis_complete.json` from disk and performs Python-based aggregations: `_compute_signal_averages()` iterates all citations computing means across 45 signals, `_compute_signal_correlations()` computes Pearson correlations, `_compute_cluster_patterns()` groups by cluster and aggregates boolean patterns. These are textbook SQL GROUP BY / AVG / CORR operations being performed in Python by loading 20MB into memory. Uses file-mtime-based caching (max 10 entries, FIFO eviction).
- `api/services/brand_data_service.py` — Reads research artifacts + run history from filesystem
- `api/services/content_data_service.py` — Reads content briefs from filesystem
- `api/services/knowledge_doc_service.py` — File upload + metadata via JSON

### Existing Auth System (will be replaced by auth repository)
- `api/auth/store.py` — `AuthStore` class: JSON-file persistence (`artifacts/_auth/companies.json`, `artifacts/_auth/users.json`), PBKDF2-HMAC-SHA256 hashing (260k iterations), HMAC-signed tokens, `threading.RLock`, `normalize_domain()`, registration/invite flows, mutable field allowlists (`_COMPANY_MUTABLE_FIELDS`, `_PRODUCT_MUTABLE_FIELDS`, `_USER_MUTABLE_FIELDS`)
- `api/auth/middleware.py` — Auth middleware extracting and validating tokens

### Existing Storage Abstraction
- `core/storage/backends/base.py` — Abstract `StorageBackend` interface (`read/write/exists/delete/list_dir`) — defined but no concrete implementations yet
- `core/storage/supabase_mirror.py` — Supabase mirror functions (will eventually be deprecated, don't touch now)

### Existing Supabase SQL Migrations (use as REFERENCE only, do not copy directly)
- `supabase/migrations/20250206120000_initial_schema.sql` — 18 tables including companies, sites, agents, site_audits, artifacts, knowledge_chunks, workflows, agent_runs, content_assets, audit_findings, task_queue
- `supabase/migrations/20260207120000_rls_enums_hnsw.sql` — 13 enum types, HNSW vector indexes (m=16, ef_construction=64), RLS policies

### API Response Schemas (must remain compatible — the frontend depends on these)
- `api/schemas/company.py` — `CompanyProfileResponse`, `ProductSummary`, `ProductDetailResponse`
- `api/schemas/gap_data.py` — 20+ response models for gap analysis endpoints (GapSummaryResponse, QueryRow, QueryContentBrief, ClusterSpecResponse, SignalAverageRow, SignalCorrelationRow, etc.)
- `api/schemas/brand_data.py` — `ResearchArtifactsResponse`, `RunHistoryResponse`, `SPATrendResponse`
- `api/schemas/content_data.py` — Content brief/stage response models
- `api/schemas/knowledge_docs.py` — Knowledge doc upload response models

### Task System
- `api/services/task_store.py` — `TaskStore` class with JSON persistence for pipeline run tracking

### Configuration
- `core/config/settings.py` — Pydantic `BaseSettings` singleton, loads from `.env` / `.env.local`

### Test Suite
- 766+ tests across `tests/api/` and `tests/` directories
- `tests/api/conftest.py` — Shared fixtures with `_AuthTestClient`, 4 client fixtures (client, public_client, viewer_client, superuser_client), tmpdir-based auth store
- Tests use tmpdir-based fixtures for filesystem isolation

---

## 3. Storage Architecture Philosophy

### The Core Insight: One JSON File Contains Four Different Data Types

After analyzing the pipeline code, the current `enriched_citations.json` (20MB+) and `gap_analysis_complete.json` actually contain four fundamentally different types of data with different optimal storage strategies:

**Type 1 — Structured queryable data (~0.5MB):** Citation metadata (url, domain, title, query_id, cluster_name, engine). The service layer filters, joins, and groups this data constantly. This is classic relational data.

**Type 2 — Fixed-schema analytical data (~2MB):** The 45 structural signals per citation. `gap_data_service.py` computes averages, Pearson correlations, and cluster-level aggregation across ALL citations for ALL 45 signals. Currently done in Python with 100k+ dict lookups. These are textbook SQL `AVG()`, `CORR()`, `GROUP BY` operations.

**Type 3 — Ephemeral intermediate data (~16MB):** The raw `paragraphs: List[str]` field on each `EnrichedCitation`. This is only consumed once by s5 (to select top-3 best paragraphs). After s5 completes, NO downstream step or API endpoint ever reads this field again. It accounts for ~80% of `enriched_citations.json` file size.

**Type 4 — Embedding vectors (~80MB in `citations_with_embeddings.json`):** 1536-float vectors for paragraph embeddings and query embeddings. Currently stored in ChromaDB AND duplicated in JSON files. Consumed by s6 for cosine similarity and s7 for UMAP/t-SNE projections.

### The Three-Tier Storage Model

The schema MUST use different storage strategies for each data type:

**Tier 1 — Normalized Postgres Tables:** Data that is filtered, joined, aggregated, or updated at row level. This includes: citation metadata, structural signals (as individual typed columns, NOT JSONB), query gaps, cluster specs, SPA results, pipeline run status, daily tracking metrics, auth data.

**Tier 2 — pgvector Columns in Postgres:** Embedding vectors for similarity search. Replaces ChromaDB with a single unified storage layer. This includes: company semantic unit embeddings, citation paragraph embeddings, query embeddings.

**Tier 3 — Object Storage (filesystem now, S3/GCS later):** Large blobs written once and read as a whole unit, or never read again after the pipeline stage that produced them. This includes: raw extracted paragraphs (ephemeral, from s4), platform LLM response texts, generated HTML visualizations, pipeline JSON archives (for reproducibility/export).

### Why NOT JSONB for Large Artifacts

Storing `enriched_citations.json` or `gap_analysis_complete.json` as JSONB columns would be the wrong approach for this project because:

1. **Every service layer operation requires iterating individual citations** — `_compute_signal_averages()`, `_compute_signal_correlations()`, `_compute_cluster_patterns()` all loop over every citation extracting individual signal values. JSONB requires `jsonb_extract_path_text()` casts that bypass indexes.
2. **Incremental updates are impossible with JSONB blobs** — updating one query's gap score means rewriting the entire JSONB column.
3. **The structural signals have a fixed, well-known schema** — 45 fields with known types (int, float, bool). This is the textbook case for normalized columns, not JSONB. Postgres's query planner can use column statistics to optimize aggregation queries.
4. **Postgres handles JSONB poorly above ~5-10MB** per row — and `enriched_citations.json` exceeds that.

JSONB IS appropriate for: lightweight summary data on pipeline_runs (dashboard stats), small variable-structure metadata (pipeline config, platform citation breakdown per tracking snapshot), and content briefs (relatively small, ~500 bytes each, variable structure).

### Why NOT NoSQL

The data has strong relational structure: citations belong to queries, queries belong to clusters, clusters belong to pipeline runs, runs belong to companies/products. Access patterns are join-heavy ("average structural signals for citations in cluster X across runs from the last month"). This is exactly what relational databases are designed for. The only document-like data (large JSON artifacts) belongs in object storage, not a document database.

---

## 4. Complete Schema Design

### Design Principles Applied to Every Table
- All primary keys: UUID (`uuid4`), stored as `varchar` or native `uuid`
- Multi-tenancy: `company_id` foreign key on all tenant-scoped tables
- Timestamps: `created_at` and `updated_at` with `timezone=True` (UTC)
- Soft deletes: `is_archived` boolean where appropriate (not hard DELETE)
- Enums: Python enums mapped to Postgres enum types for status fields
- Indexes: Explicitly designed for known query patterns documented below

### 4.1 Organization & Auth Tables

```
companies
├── id              uuid PK DEFAULT uuid4
├── slug            varchar UNIQUE NOT NULL  — kebab-case, used for artifact directories
├── name            varchar NOT NULL
├── domain          varchar NOT NULL  — primary root domain (normalized)
├── additional_domains  text[]  — subdomains discovered during registration
├── is_archived     boolean DEFAULT false
├── created_at      timestamptz DEFAULT now()
├── updated_at      timestamptz DEFAULT now()
├── INDEX on (domain)
├── INDEX on (slug)

products
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── slug            varchar NOT NULL
├── name            varchar NOT NULL
├── domain          varchar  — nullable, product-specific domain
├── description     text
├── created_at      timestamptz
├── updated_at      timestamptz
├── UNIQUE (company_id, slug)

users
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── email           varchar UNIQUE NOT NULL
├── password_hash   varchar NOT NULL  — PBKDF2-HMAC-SHA256
├── first_name      varchar DEFAULT ''
├── last_name       varchar DEFAULT ''
├── role            enum('superuser','member','viewer') DEFAULT 'member'
├── is_active       boolean DEFAULT true
├── created_at      timestamptz
├── updated_at      timestamptz
├── INDEX on (company_id)
├── INDEX on (email)

invites
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL  — which company this invite is for
├── code            varchar UNIQUE NOT NULL  — 16-char hex, single-use
├── role            enum('superuser','member','viewer') DEFAULT 'member'
├── created_by      uuid FK → users
├── redeemed_by     uuid FK → users NULLABLE  — set when invite is used
├── redeemed_at     timestamptz NULLABLE
├── expires_at      timestamptz
├── created_at      timestamptz

company_pipeline_defaults
├── id              uuid PK
├── company_id      uuid FK → companies UNIQUE  — one row per company
├── defaults_json   JSONB  — the CompanyPipelineDefaults fields, variable structure
├── updated_at      timestamptz
```

### 4.2 Pipeline Infrastructure

This is the backbone that tracks all pipeline executions and supports both full runs and incremental refresh runs.

```
pipeline_runs
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── product_id      uuid FK → products NULLABLE  — null for company-level runs
├── effective_slug  varchar NOT NULL  — '{company_slug}' or '{company_slug}__{product_slug}'
├── pipeline_type   enum('research','gap_analysis','content','content_refresh','site_audit','topic_discovery') NOT NULL
├── parent_run_id   uuid FK → pipeline_runs NULLABLE
│   ↑ For content_refresh runs, points to the original gap_analysis run being patched.
│     This creates an audit trail: "gap analysis ran Feb 15, refreshed Feb 20 after 3 new pieces."
├── status          enum('pending','running','completed','failed','cancelled') NOT NULL
├── config          JSONB  — input parameters, skip_steps list, model selections
├── summary         JSONB  — lightweight dashboard stats computed at pipeline completion:
│                            {spa_score, query_count, total_citations, avg_gap, classification_counts, ...}
│   ↑ This JSONB column is small (~1KB) and used ONLY for dashboard overview queries.
│     All detailed data lives in normalized tables below.
├── stages_executed text[]  — which stages actually ran vs served from cache: ['s1','s3','s4','s6']
│   ↑ Enables performance tracking: "this run skipped s2 (queries cached) and s5 (embeddings cached)"
├── started_at      timestamptz
├── completed_at    timestamptz
├── duration_seconds integer
├── error_message   text NULLABLE  — populated on failure
├── created_at      timestamptz
├── updated_at      timestamptz
├── INDEX on (company_id, pipeline_type)
├── INDEX on (effective_slug, pipeline_type)
├── INDEX on (status) WHERE status IN ('pending','running')  — partial index for active runs

pipeline_stage_logs
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── stage_name      varchar NOT NULL  — 's1_embed_assets', 's4_enrich_citations', etc.
├── status          enum('pending','running','completed','failed','skipped','cached')
├── started_at      timestamptz
├── completed_at    timestamptz
├── duration_seconds integer
├── items_processed integer  — e.g., "2234 citations enriched", "75 queries embedded"
├── items_from_cache integer  — e.g., "1500 URLs served from cache, 734 newly scraped"
├── metadata        JSONB  — stage-specific stats
├── INDEX on (run_id)
```

### 4.3 Cache Layer (Enables Pipeline Performance Optimization)

These tables are GLOBAL caches shared across companies and pipeline runs. They are the key architectural addition that makes subsequent runs fast. Each cache table has a TTL-based staleness model.

**Design rationale:** The gap analysis pipeline spends ~60 of its 80 minutes on s3 (searching platforms) and s4 (scraping URLs). Both operations are deterministic for a given input — the same query to the same engine returns similar results within a time window, and the same URL returns the same structural signals unless the page content changes. By caching these results with a configurable TTL, we avoid redundant work across runs and across companies.

```
platform_result_cache
├── id              uuid PK
├── query_text_hash varchar NOT NULL  — SHA256 of normalized query text (for fast lookup)
├── query_text      text NOT NULL  — the actual query string
├── engine          enum('chatgpt','claude','perplexity','gemini') NOT NULL
├── model_version   varchar  — 'gpt-4o', 'claude-sonnet-4.5', etc. (for cache invalidation on model updates)
├── response_text   text  — the full LLM response (Tier 3 candidate if too large, but usually <10KB)
├── citations       JSONB NOT NULL  — [{url, rank, title, snippet, confidence, source}]
│   ↑ JSONB is appropriate here: small (<5KB), variable-length list, never queried inside
├── fetched_at      timestamptz NOT NULL  — when this result was fetched, for TTL expiry
├── created_at      timestamptz
├── UNIQUE (query_text_hash, engine)  — one cached result per query+engine pair
├── INDEX on (query_text_hash, engine, fetched_at)
│   ↑ Supports the primary lookup: "do I have a fresh result for this query on this engine?"

url_enrichment_cache
├── id              uuid PK
├── url_hash        varchar NOT NULL  — SHA256 of normalized URL
├── url             text NOT NULL
├── final_url       text  — after redirect resolution (e.g., Vertex AI wrappers → real URL)
├── domain          varchar
├── title           text
├── authority_type  varchar  — 'vendor', 'media', 'government', etc.
├── content_type    varchar  — 'blog', 'guide', 'documentation', etc.
├── paragraph_count integer  — total paragraphs extracted
├── http_status     integer  — 200, 403, 404, 500 — cache failures too so we don't retry dead URLs
├── scraped_at      timestamptz NOT NULL  — for TTL-based re-scraping
├── raw_paragraphs_storage_key  varchar NULLABLE  — pointer to Tier 3 object storage if retained
│   ↑ The full paragraphs list (~5-15KB per URL) is Tier 3 data. Store a key if you want
│     reproducibility; omit to save storage since paragraphs are only needed by s5.
├── created_at      timestamptz
├── UNIQUE (url_hash)
├── INDEX on (url_hash, scraped_at)
│   ↑ Supports: "is this URL's enrichment still fresh?"
├── INDEX on (domain)

url_structural_signals
├── url_enrichment_id   uuid FK → url_enrichment_cache PK  — one-to-one
│   ↑ Separate table because: (a) 45 columns is wide, (b) these are the most heavily
│     queried columns in the system, (c) keeps the cache table lean for TTL lookups
├── word_count                  integer DEFAULT 0
├── main_content_word_count     integer DEFAULT 0
├── sentence_count              integer DEFAULT 0
├── paragraph_count             integer DEFAULT 0
├── header_count                integer DEFAULT 0
├── list_item_count             integer DEFAULT 0
├── stat_count                  integer DEFAULT 0
├── citation_count              integer DEFAULT 0
├── has_headers                 boolean DEFAULT false
├── has_lists                   boolean DEFAULT false
├── has_numbers                 boolean DEFAULT false
│   ↑ Original 11 fields preserved for backward compatibility
├── avg_paragraph_length        float DEFAULT 0.0
├── median_paragraph_length     float DEFAULT 0.0
├── max_paragraph_word_count    integer DEFAULT 0
├── avg_sentence_length         float DEFAULT 0.0
├── avg_sentence_count_per_paragraph  float DEFAULT 0.0
├── reading_level               float DEFAULT 0.0
├── self_contained_ratio        float DEFAULT 0.0
│   ↑ Category A: Text Composition
├── h1_count                    integer DEFAULT 0
├── h2_count                    integer DEFAULT 0
├── h3_count                    integer DEFAULT 0
├── h4_count                    integer DEFAULT 0
├── ordered_list_count          integer DEFAULT 0
├── unordered_list_count        integer DEFAULT 0
├── table_count                 integer DEFAULT 0
├── definition_list_count       integer DEFAULT 0
├── blockquote_count            integer DEFAULT 0
├── code_block_count            integer DEFAULT 0
├── list_block_count            integer DEFAULT 0
├── bullets_per_list_block      float DEFAULT 0.0
├── min_bullets_per_list        integer DEFAULT 0
│   ↑ Category B: Structural Elements
├── has_faq_section             boolean DEFAULT false
├── has_definition_opening      boolean DEFAULT false
├── has_key_takeaways           boolean DEFAULT false
├── has_toc                     boolean DEFAULT false
├── has_comparison_table        boolean DEFAULT false
├── has_step_by_step            boolean DEFAULT false
├── has_research_refs           boolean DEFAULT false
├── has_expert_quotes           boolean DEFAULT false
│   ↑ Category C: Content Patterns
├── data_point_count            integer DEFAULT 0
├── citation_density            float DEFAULT 0.0
├── named_entity_density        float DEFAULT 0.0
│   ↑ Category D: Factual Density
│
│ WHY 45 individual columns instead of JSONB:
│ 1. gap_data_service computes AVG() across all citations for each signal — SQL does this natively
│ 2. Signal correlations (Pearson) against similarity — SQL corr() function
│ 3. Cluster-level GROUP BY on boolean patterns — trivial with columns, painful with JSONB
│ 4. Fixed schema, known types — no benefit from JSONB flexibility
│ 5. Postgres column statistics enable query planner optimization
│ 6. If we add signal #46 in the future, that's one Alembic migration: ALTER TABLE ADD COLUMN
```

### 4.4 Gap Analysis Run-Scoped Tables

These tables store per-run analytical results. They reference the global cache layer for URL-level data but contain run-specific scoring and classification.

**Design rationale:** Separating run-scoped data (query gaps, scores, classifications) from global caches (URL enrichments, embeddings) is what enables both cross-run caching AND incremental content-refresh. The same URL enrichment is reused across runs; the gap score is run-specific and updatable.

```
run_queries
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── query_id        varchar NOT NULL  — 'C5-Q1', matches GeneratedQuery.query_id
├── cluster_id      varchar
├── cluster_name    varchar NOT NULL
├── query_text      text NOT NULL
├── buyer_stage     varchar
├── persona_tag     varchar
├── created_at      timestamptz
├── UNIQUE (run_id, query_id)
├── INDEX on (run_id, cluster_name)

run_citations
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── query_id        varchar NOT NULL  — links to run_queries.query_id
├── cluster_name    varchar
├── engine          enum('chatgpt','claude','perplexity','gemini') NOT NULL
├── url_enrichment_id  uuid FK → url_enrichment_cache NULLABLE
│   ↑ Links to the global cache. Same URL cited across different runs points to same enrichment.
│     NULL if the URL was unreachable and not enriched.
├── citation_rank   integer  — position in the LLM response (1-based)
├── snippet         text  — the snippet the LLM provided for this citation
├── title           text
├── url             text NOT NULL  — denormalized for fast reads; canonical URL from enrichment
├── domain          varchar  — denormalized for fast reads
├── created_at      timestamptz
├── INDEX on (run_id, query_id)
├── INDEX on (run_id, engine)
├── INDEX on (url_enrichment_id)

query_gaps
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── query_id        varchar NOT NULL
├── query_text      text NOT NULL  — denormalized for API reads
├── cluster_name    varchar NOT NULL
├── cluster_id      varchar
├── avg_citation_similarity     float  — mean similarity of top-N citation paragraphs to query
├── best_company_similarity     float  — best matching company semantic unit similarity
├── best_company_unit_id        varchar NULLABLE  — which company unit matched best
├── best_company_unit_text      text NULLABLE  — first 200 chars of the best-matching unit
├── gap                         float NOT NULL  — avg_citation_similarity - best_company_similarity
├── classification  enum('significant_gap','gap_to_close','roughly_equal','company_wins') NOT NULL
├── content_brief   JSONB NULLABLE  — the GapContentBrief object (~500 bytes, variable structure)
│   ↑ JSONB is appropriate here: small, variable-structure, read as a whole unit, never queried inside
├── targeted_by_content_id  uuid NULLABLE  — FK to content_pieces when a published piece addresses this gap
│   ↑ CRITICAL for content-refresh: marks which gaps have been addressed by content
├── last_refreshed_at   timestamptz NULLABLE  — when this gap was last recomputed by a content-refresh
├── refreshed_by_run_id uuid FK → pipeline_runs NULLABLE  — which content-refresh run updated this
├── created_at      timestamptz
├── updated_at      timestamptz
├── UNIQUE (run_id, query_id)
├── INDEX on (run_id, classification)  — for dashboard classification counts
├── INDEX on (run_id, cluster_name)  — for cluster-level aggregation
├── INDEX on (targeted_by_content_id) WHERE targeted_by_content_id IS NOT NULL

query_exemplars
├── id              uuid PK
├── query_gap_id    uuid FK → query_gaps NOT NULL
├── url_enrichment_id  uuid FK → url_enrichment_cache NULLABLE
├── url             text NOT NULL  — denormalized
├── domain          varchar
├── similarity      float NOT NULL
├── snippet         text  — first 300 chars of best-matching paragraph
├── authority_type  varchar
├── rank            integer NOT NULL  — 1-3, position among top exemplars for this query
├── INDEX on (query_gap_id)

cluster_specs
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── cluster_id      varchar
├── cluster_name    varchar NOT NULL
├── query_count     integer DEFAULT 0
├── total_citations_analyzed  integer DEFAULT 0
├── min_similarity_threshold  float
├── word_count_min  integer DEFAULT 0
├── word_count_max  integer DEFAULT 0
├── avg_word_count  float DEFAULT 0.0
├── avg_paragraph_word_count    float DEFAULT 0.0
├── avg_sentence_count_per_paragraph  float DEFAULT 0.0
├── min_bullets_per_list        integer DEFAULT 0
├── faq_rate        float DEFAULT 0.0
├── table_rate      float DEFAULT 0.0
├── definition_rate float DEFAULT 0.0
├── code_block_rate float DEFAULT 0.0
├── key_takeaways_rate  float DEFAULT 0.0
├── dominant_content_type   varchar
├── dominant_authority_type varchar
├── required_elements       text[]
├── structural_rates        JSONB  — {signal_name: rate} for all structural signals
├── exemplar_themes         text[]  — TF-IDF extracted themes
├── created_at      timestamptz
├── updated_at      timestamptz  — updated during content-refresh
├── UNIQUE (run_id, cluster_name)

spa_results
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── cluster_id      varchar
├── cluster_name    varchar NOT NULL
├── t_stat          float
├── p_value         float
├── mean_citation_similarity   float
├── mean_company_similarity    float
├── effect          varchar  — 'significant', 'moderate', 'none'
├── created_at      timestamptz
├── UNIQUE (run_id, cluster_name)

centroid_results
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── cluster_name    varchar NOT NULL
├── distance        float  — distance between query centroid and citation centroid
├── created_at      timestamptz
│   Note: query_centroid and citation_centroid vectors (1536-dim each) go in Tier 2 embedding
│   tables below if needed for re-analysis. The distance scalar is what the API serves.
├── UNIQUE (run_id, cluster_name)
```

### 4.5 Embedding Layer (pgvector — Replaces ChromaDB)

**Design rationale:** Unifying all embeddings in Postgres via pgvector eliminates ChromaDB as an operational dependency (one fewer system to maintain, back up, monitor). HNSW indexes provide sub-millisecond similarity search at the scale of this project. The separation between global embeddings (paragraph_embeddings, computed once per unique text) and run-scoped scoring (run_paragraph_scores, computed per run per citation) avoids redundant embedding computation while preserving per-run analytical context.

```
semantic_units
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── run_id          uuid FK → pipeline_runs NOT NULL  — which s1 run produced this
├── unit_id         varchar NOT NULL  — 'unit_1', 'unit_2', etc.
├── url             text NULLABLE  — null for knowledge docs
├── title           text NULLABLE
├── text            text NOT NULL
├── embedding       vector(1536) NOT NULL  — pgvector column
├── discovery_source varchar DEFAULT 'website'  — 'website' or 'knowledge_doc'
├── char_count      integer DEFAULT 0
├── word_count      integer DEFAULT 0
├── created_at      timestamptz
├── INDEX using hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
├── INDEX on (company_id, run_id)

query_embeddings
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL
├── query_id        varchar NOT NULL
├── query_text      text NOT NULL
├── embedding       vector(1536) NOT NULL
├── created_at      timestamptz
├── UNIQUE (run_id, query_id)
├── INDEX using hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)

paragraph_embeddings
├── id              uuid PK
├── url_enrichment_id  uuid FK → url_enrichment_cache NOT NULL
├── embedding_id    varchar UNIQUE NOT NULL  — stable hash: 'cite_{sha256(url_paraIdx)[:24]}'
│   ↑ Matches the existing _embedding_id() function in s5_embed_content.py
├── paragraph_text  text NOT NULL
├── embedding       vector(1536) NOT NULL
├── original_paragraph_index  integer  — position in the source page's paragraph list
├── created_at      timestamptz
├── INDEX using hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
├── INDEX on (url_enrichment_id)

run_paragraph_scores
├── id              uuid PK
├── run_citation_id     uuid FK → run_citations NOT NULL
├── paragraph_embedding_id  uuid FK → paragraph_embeddings NOT NULL
├── similarity      float NOT NULL  — cosine similarity to anchor text
├── rank            integer NOT NULL  — 1-3, within this citation for this run
├── INDEX on (run_citation_id)
│
│ WHY separate from paragraph_embeddings:
│ The same paragraph from hubspot.com/blog/x might be scored differently depending
│ on which query's anchor text it's compared against. The embedding is computed once
│ and reused globally; the scoring is run-specific and query-specific.
```

### 4.6 Research Artifacts

Research artifacts (company context, personas, style guides) are primarily Markdown documents. They remain in the filesystem as the authoring/approval medium. The database stores metadata and a pointer for API access.

```
research_artifacts
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── product_id      uuid FK → products NULLABLE
├── effective_slug  varchar NOT NULL
├── artifact_type   enum('company_context','persona','style_guide') NOT NULL
├── title           varchar
├── status          enum('draft','approved','archived') DEFAULT 'draft'
├── version         integer DEFAULT 1
├── storage_key     varchar NOT NULL  — filesystem path: 'artifacts/company_context/ramp.md'
├── content_hash    varchar  — SHA256 of content for integrity/change detection
├── metadata        JSONB NULLABLE  — type-specific: persona_kind, persona_name, etc.
├── created_at      timestamptz
├── updated_at      timestamptz
├── INDEX on (company_id, artifact_type)
├── INDEX on (effective_slug, artifact_type)
```

### 4.7 Content Engine Tables

```
content_pieces
├── id              uuid PK
├── run_id          uuid FK → pipeline_runs NOT NULL  — which content pipeline run produced this
├── gap_run_id      uuid FK → pipeline_runs NULLABLE  — which gap analysis run this targets
├── query_id        varchar NULLABLE  — which specific query gap this addresses
├── cluster_name    varchar
├── title           varchar NOT NULL
├── content_type    varchar  — 'blog', 'guide', 'case_study', 'product_page'
├── status          enum('suggested','drafting','evaluating','review','approved','published','rejected')
├── storage_key     varchar  — pointer to Markdown file on disk
├── word_count      integer DEFAULT 0
├── citability_score float NULLABLE  — from evaluator
├── evaluation_results  JSONB NULLABLE  — detailed scores from evaluator loop
├── revision_count  integer DEFAULT 0
├── created_at      timestamptz
├── updated_at      timestamptz
├── published_at    timestamptz NULLABLE
├── published_url   text NULLABLE  — live URL after publishing
├── INDEX on (run_id)
├── INDEX on (gap_run_id, query_id)
├── INDEX on (status)
```

### 4.8 Daily Tracker Tables

**Design rationale:** This is pure time-series data. The key access pattern is: "show me how Company X's mention rate for cluster Y has changed over the last 30 days." This requires a (company_id, date) partitioned structure with per-query-per-platform granularity.

```
tracking_snapshots
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── product_id      uuid FK → products NULLABLE
├── snapshot_date   date NOT NULL  — one snapshot per company per day
├── gap_run_id      uuid FK → pipeline_runs NULLABLE  — the gap analysis run this snapshot measures against
├── status          enum('pending','running','completed','failed') DEFAULT 'pending'
├── queries_checked integer DEFAULT 0
├── created_at      timestamptz
├── completed_at    timestamptz NULLABLE
├── UNIQUE (company_id, product_id, snapshot_date)  — one snapshot per scope per day
├── INDEX on (company_id, snapshot_date)

content_mention_tracking
├── id              uuid PK
├── snapshot_id     uuid FK → tracking_snapshots NOT NULL
├── query_text      text NOT NULL
├── query_id        varchar NULLABLE  — links back to gap analysis query if applicable
├── cluster_name    varchar
├── engine          enum('chatgpt','claude','perplexity','gemini') NOT NULL
├── company_mentioned   boolean NOT NULL  — was the company cited for this query on this engine?
├── company_citation_rank  integer NULLABLE  — position in citations, null if not cited
├── company_url_cited      text NULLABLE  — which company URL was cited
├── competitor_urls_cited  JSONB  — [{url, domain, rank}]
├── checked_at      timestamptz
├── INDEX on (snapshot_id, engine)
├── INDEX on (snapshot_id, cluster_name)

content_piece_tracking
├── id              uuid PK
├── snapshot_id     uuid FK → tracking_snapshots NOT NULL
├── content_piece_id uuid FK → content_pieces NULLABLE
├── url             text NOT NULL
├── mention_count   integer DEFAULT 0  — how many queries cited this URL today
├── citation_count_by_platform  JSONB  — {chatgpt: 3, claude: 2, perplexity: 1, gemini: 0}
├── avg_citation_rank  float NULLABLE  — average position when cited
├── traffic_estimate   integer NULLABLE  — if analytics integration is available
├── created_at      timestamptz
├── INDEX on (snapshot_id, url)
├── INDEX on (content_piece_id, snapshot_id)
```

### 4.9 Site Audit & Topic Discovery Tables

```
site_audits
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── site_domain     varchar NOT NULL  — which domain was audited
├── status          enum('pending','running','completed','failed') DEFAULT 'pending'
├── started_at      timestamptz
├── completed_at    timestamptz
├── findings_count  integer DEFAULT 0
├── pages_crawled   integer DEFAULT 0
├── config          JSONB  — audit parameters
├── created_at      timestamptz
├── INDEX on (company_id, created_at)

audit_findings
├── id              uuid PK
├── audit_id        uuid FK → site_audits NOT NULL
├── page_url        text NOT NULL
├── finding_type    varchar NOT NULL  — 'missing_schema', 'broken_link', 'thin_content', etc.
├── severity        enum('critical','high','medium','low','info') NOT NULL
├── details         JSONB  — finding-specific structured details
├── is_resolved     boolean DEFAULT false
├── resolved_at     timestamptz NULLABLE
├── created_at      timestamptz
├── INDEX on (audit_id, severity)
├── INDEX on (audit_id, finding_type)
├── INDEX on (audit_id, is_resolved)

topic_discoveries
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── product_id      uuid FK → products NULLABLE
├── pipeline_run_id uuid FK → pipeline_runs NULLABLE
├── status          enum('pending','running','completed','failed') DEFAULT 'pending'
├── discovered_at   timestamptz
├── created_at      timestamptz
├── INDEX on (company_id)

discovered_topics
├── id              uuid PK
├── discovery_id    uuid FK → topic_discoveries NOT NULL
├── topic_text      text NOT NULL
├── relevance_score float
├── cluster_id      varchar NULLABLE  — maps to existing query cluster taxonomy
├── buyer_stage     varchar NULLABLE
├── metadata        JSONB  — topic-specific details
├── created_at      timestamptz
├── INDEX on (discovery_id)
```

### 4.10 Knowledge Documents

```
knowledge_documents
├── id              uuid PK
├── company_id      uuid FK → companies NOT NULL
├── effective_slug  varchar NOT NULL
├── filename        varchar NOT NULL
├── content_type    varchar NOT NULL  — MIME type
├── file_size_bytes integer NOT NULL
├── word_count      integer DEFAULT 0
├── storage_key     varchar NOT NULL  — filesystem path
├── is_embedded     boolean DEFAULT false
├── last_embedded_at timestamptz NULLABLE
├── uploaded_at     timestamptz
├── created_at      timestamptz
├── INDEX on (company_id, effective_slug)
```

---

## 5. Architecture Requirements

### 5.1 Database Choice & Configuration
- **PostgreSQL 15+** (self-hosted, NOT Supabase)
- Add `DATABASE_URL` to `core/config/settings.py` with a sensible default: `postgresql+asyncpg://localhost:5432/deep_presence`
- Add `DATABASE_URL_SYNC` for Alembic migrations (Alembic needs a sync driver): `postgresql://localhost:5432/deep_presence`
- Support loading from `.env` / `.env.local`
- Enable `pgvector` extension in the first migration: `CREATE EXTENSION IF NOT EXISTS vector`
- Async support: use `asyncpg` driver with `create_async_engine` since FastAPI is async

### 5.2 ORM Library Decision
Evaluate and choose between:
- **Option A: SQLModel** — Pydantic + SQLAlchemy hybrid, minimizes model duplication since we already have Pydantic models everywhere
- **Option B: Pure SQLAlchemy 2.0 declarative** — More control, separate ORM models with explicit Pydantic conversion

**My preference is SQLModel** because our entire codebase is Pydantic-native. But if you identify concrete reasons SQLModel would cause problems with our patterns (e.g., the 45-column structural signals table, pgvector Vector columns, JSONB with complex defaults, Alembic autogenerate compatibility), choose pure SQLAlchemy 2.0 and explain why. Key consideration: the `url_structural_signals` table has 45 typed columns — verify that your chosen ORM handles this cleanly.

### 5.3 Package Structure
```
core/db/
├── __init__.py
├── engine.py              # Engine + async session factory
├── base.py                # Declarative base / SQLModel base
├── models/                # ORM models
│   ├── __init__.py
│   ├── organization.py    # Company, Product, User, Invite
│   ├── pipelines.py       # PipelineRun, PipelineStageLog
│   ├── cache.py           # PlatformResultCache, UrlEnrichmentCache, UrlStructuralSignals
│   ├── gap_analysis.py    # RunQuery, RunCitation, QueryGap, QueryExemplar, ClusterSpec, SpaResult
│   ├── embeddings.py      # SemanticUnit, QueryEmbedding, ParagraphEmbedding, RunParagraphScore
│   ├── content.py         # ContentPiece, ResearchArtifact
│   ├── tracking.py        # TrackingSnapshot, ContentMentionTracking, ContentPieceTracking
│   ├── site_audit.py      # SiteAudit, AuditFinding
│   ├── topic_discovery.py # TopicDiscovery, DiscoveredTopic
│   └── knowledge_docs.py  # KnowledgeDocument
├── repositories/          # Repository pattern
│   ├── __init__.py
│   ├── base.py            # Abstract base repository with generic CRUD
│   ├── company_repo.py    # CompanyRepository (abstract + SQLAlchemy impl)
│   ├── auth_repo.py       # AuthRepository (abstract + SQLAlchemy impl)
│   ├── pipeline_repo.py   # PipelineRunRepository
│   ├── cache_repo.py      # PlatformCacheRepository, UrlEnrichmentCacheRepository
│   ├── gap_analysis_repo.py  # QueryGapRepository, CitationRepository, etc.
│   ├── embedding_repo.py  # SemanticUnitRepository, ParagraphEmbeddingRepository
│   ├── tracking_repo.py   # TrackingRepository
│   └── content_repo.py    # ContentPieceRepository
└── migrations/            # Alembic
    ├── env.py
    ├── script.py.mako
    └── versions/

alembic.ini                # At project root, points to core/db/migrations/
```

### 5.4 Alembic Configuration
- Use async-compatible Alembic (run migrations with sync driver, `DATABASE_URL_SYNC`)
- `alembic.ini` reads `DATABASE_URL_SYNC` from the same `.env` that `settings.py` reads
- Auto-generate migrations from ORM model changes (`--autogenerate`)
- First migration creates ALL tables defined in Section 4, enables pgvector extension, creates all enum types
- Place `alembic.ini` at project root, migrations inside `core/db/migrations/`

### 5.5 Repository Pattern

Each repository provides a clean async interface that the service layer calls. Abstract base classes define the contract; SQLAlchemy implementations fulfill it.

```python
# Abstract interface
class CompanyRepository(ABC):
    async def get_by_slug(self, slug: str) -> Optional[Company]: ...
    async def get_by_domain(self, domain: str) -> Optional[Company]: ...
    async def create(self, data: CompanyCreate) -> Company: ...
    async def update(self, slug: str, **kwargs) -> Company: ...
    async def list_all(self) -> List[Company]: ...

# SQLAlchemy implementation
class SQLAlchemyCompanyRepository(CompanyRepository):
    def __init__(self, session: AsyncSession):
        self._session = session
    # ... implementations using session.execute(), session.add(), etc.
```

**Dependency injection:** Use FastAPI's `Depends()` to inject repositories into route handlers. A factory function provides the appropriate session and repository. Example:

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def get_company_repo(session: AsyncSession = Depends(get_db_session)) -> CompanyRepository:
    return SQLAlchemyCompanyRepository(session)

@router.get("/companies/{slug}")
async def get_company(slug: str, repo: CompanyRepository = Depends(get_company_repo)):
    company = await repo.get_by_slug(slug)
    ...
```

### 5.6 AuthStore Migration
The current `api/auth/store.py` AuthStore must be replaceable by the new `auth_repo.py`:
- Move password hashing logic (`_hash_password`, `_verify_password`) into `core/db/utils/auth.py` — reusable regardless of storage backend
- Move token logic (HMAC signing/verification) into `core/db/utils/tokens.py`
- Move `normalize_domain()` into `core/db/utils/domain.py`
- The repository handles CRUD only; an auth *service* (`core/db/services/auth_service.py`) handles business logic (registration flow, invite redemption, domain normalization, duplicate checks)
- Maintain the same external behavior: registration, login, invite, join, token generation/verification
- Existing tests should pass with minimal fixture changes (swap file-backed store for DB-backed repository in conftest)

---

## 6. Pipeline Integration Guide

### 6.1 How Pipeline Steps Write to the Database

Pipelines currently write JSON files to disk. With the database layer, each step gains a **post-write hook** that also persists structured data to the database. The filesystem write is NOT removed — it stays as an export/archive format. The database becomes the primary read source for the API.

```
s1: embed_company_assets()
    → filesystem: artifacts/gap_analysis/{slug}/company_embeddings.json (no raw vectors, just metadata)
    → database: INSERT INTO semantic_units (company_id, run_id, unit_id, url, text, embedding, ...)
    → replaces: ChromaDB upsert for company embeddings

s2: generate_queries()
    → filesystem: artifacts/gap_analysis/{slug}/queries.json
    → database: INSERT INTO run_queries (run_id, query_id, cluster_name, query_text, ...)

s3: search_platforms()
    → filesystem: artifacts/gap_analysis/{slug}/platform_results/*.jsonl
    → database: For each (query, engine) pair:
        1. Check platform_result_cache for fresh result (TTL check)
        2. If cache hit: skip API call, read from cache
        3. If cache miss: make API call, INSERT INTO platform_result_cache, then proceed
        4. INSERT INTO run_citations for each citation in the result

s4: enrich_citations()
    → filesystem: artifacts/gap_analysis/{slug}/enriched_citations.json
    → database: For each unique URL to scrape:
        1. Check url_enrichment_cache for fresh result (TTL check)
        2. If cache hit: skip scrape, read structural signals from cache
        3. If cache miss: scrape URL, INSERT INTO url_enrichment_cache + url_structural_signals
        4. Raw paragraphs: store in object storage via storage_key (Tier 3), NOT in database
    → UPDATE run_citations SET url_enrichment_id = ... (link citations to their enrichments)

s5: embed_content()
    → filesystem: artifacts/gap_analysis/{slug}/embeddings/ (queries + citations with embeddings)
    → database: For each unique paragraph to embed:
        1. Check paragraph_embeddings for existing embedding by embedding_id
        2. If exists: skip embed call, reuse
        3. If new: embed via OpenAI, INSERT INTO paragraph_embeddings
    → INSERT INTO query_embeddings (run_id, query_id, embedding)
    → INSERT INTO run_paragraph_scores (run_citation_id, paragraph_embedding_id, similarity, rank)
    → replaces: ChromaDB upsert for citation embeddings

s6: run_analysis()
    → filesystem: artifacts/gap_analysis/{slug}/analysis.json, gap_report.json, gap_analysis_complete.json
    → database:
        INSERT INTO query_gaps (run_id, query_id, gap, classification, content_brief, ...)
        INSERT INTO query_exemplars (query_gap_id, url_enrichment_id, similarity, ...)
        INSERT INTO cluster_specs (run_id, cluster_name, faq_rate, ...)
        INSERT INTO spa_results (run_id, cluster_name, t_stat, p_value, ...)
        INSERT INTO centroid_results (run_id, cluster_name, distance)
        UPDATE pipeline_runs SET summary = {lightweight JSON stats}

s7/s8: visualize + report
    → filesystem only (HTML, Plotly charts, Markdown reports)
    → These are Tier 3 blobs. Store storage_key references in pipeline_runs.config if needed.
```

### 6.2 Content-Refresh Pipeline (New)

This is a lightweight pipeline that runs after content is published. It does NOT re-run s2/s3/s4.

```
Input: content_piece_id, gap_run_id (the gap analysis run to patch)

Step 1: Embed the new content piece as a new SemanticUnit
    → INSERT INTO semantic_units (company_id, run_id=refresh_run, text=content_body, embedding=...)

Step 2: For each query in the targeted cluster:
    → Compute cosine similarity between query embedding and new content embedding
    → If new_similarity > existing best_company_similarity:
        UPDATE query_gaps SET
            best_company_similarity = new_similarity,
            best_company_unit_id = new_unit_id,
            gap = avg_citation_similarity - new_similarity,
            classification = recompute_classification(new_gap),
            targeted_by_content_id = content_piece_id,
            last_refreshed_at = NOW(),
            refreshed_by_run_id = refresh_run_id

Step 3: Recompute cluster-level stats for affected cluster:
    UPDATE cluster_specs SET
        ... (recompute from query_gaps where cluster_name = affected_cluster)

Step 4: Regenerate visualizations for affected cluster only (Tier 3)

Step 5: UPDATE pipeline_runs SET summary = recomputed_summary, status = 'completed'
```

### 6.3 Cache TTL Configuration

Add to `core/config/settings.py`:
```python
platform_cache_ttl_days: int = 7       # Re-search platforms after 7 days
url_enrichment_cache_ttl_days: int = 14 # Re-scrape URLs after 14 days
```

The pipeline steps use these to determine whether a cached result is fresh enough to reuse.

---

## 7. Migration Strategy

The migration is incremental, not big-bang. Each phase is independently deployable and testable.

**Phase 1 (this task — infrastructure + models + first migration):**
- Set up `core/db/engine.py`, `core/db/base.py`
- Define ALL ORM models in `core/db/models/` matching the schema in Section 4
- Configure Alembic, write the first migration that creates all tables + pgvector extension + all enums
- Add `DATABASE_URL` / `DATABASE_URL_SYNC` to settings
- Implement base repository with generic CRUD
- Implement `SQLAlchemyCompanyRepository` and `SQLAlchemyAuthRepository`
- Add dependency injection wiring for FastAPI
- Write comprehensive tests for all ORM models and repositories
- Update `pyproject.toml` and `requirements.txt` with new dependencies
- **Do NOT modify any existing pipeline code or service layer code in this phase**

**Phase 2 (next task — auth migration):**
- Wire `auth_repo` into auth middleware and registration flows, replacing `AuthStore` JSON persistence
- Extract auth utilities (hashing, tokens, domain normalization) into `core/db/utils/`
- Update auth tests to use DB-backed repository

**Phase 3 (future — gap analysis service migration):**
- Migrate `gap_data_service.py` to use repositories instead of JSON file loading
- This is where the performance wins materialize: `_compute_signal_averages()` becomes a SQL query
- Filesystem artifacts remain as export/archive format

**Phase 4 (future — pipeline write hooks):**
- Add database write hooks to pipeline steps (s1-s6) as described in Section 6.1
- Implement cache layer checks in s3 and s4
- Implement paragraph embedding deduplication in s5

**Phase 5 (future — new modules):**
- Build site audit, topic discovery, and daily tracker directly on the repository layer
- Build content-refresh pipeline as described in Section 6.2

---

## 8. Testing Strategy

- Add a `tests/db/` directory for database-specific tests
- Use `pytest-asyncio` for async test support
- For unit tests: mock repositories (do NOT use SQLite — pgvector and Postgres enums won't work)
- For integration tests: use a test Postgres database configurable via `TEST_DATABASE_URL` env var
- Add a `tests/db/conftest.py` that:
    - Creates all tables at session start, drops at session end
    - Provides an async session fixture that wraps each test in a transaction and rolls back after
    - Provides repository fixtures pre-configured with the test session
- **Do NOT break existing tests** — the 766+ tests that use filesystem fixtures must continue passing unchanged. The database layer is additive; no existing code is modified in Phase 1.
- All new ORM models should have tests verifying: table creation, CRUD operations, relationship loading, constraint enforcement (unique, not-null, FK), enum column behavior
- All new repositories should have tests verifying: create, read, update, list, filter, edge cases (not found, duplicate, constraint violation)

---

## 9. Dependencies to Add

```
sqlalchemy[asyncio]>=2.0
asyncpg                    # Async Postgres driver
alembic                    # Schema migrations
pgvector                   # Vector column type for SQLAlchemy
sqlmodel                   # If choosing SQLModel (Option A)
pytest-asyncio             # For async test support
```

Add to both `pyproject.toml` and `requirements.txt`.

---

## 10. Execution Instructions

### Step 1: Plan (REQUIRED before writing any code)
Produce a detailed plan that includes:
1. Which ORM library you chose (SQLModel vs pure SQLAlchemy 2.0) and concrete reasons why
2. Complete list of all ORM model classes with their columns, relationships, indexes, and constraints — verify it matches Section 4 of this prompt
3. How pgvector Vector columns are declared and indexed
4. How the repository pattern integrates with FastAPI's `Depends()` system
5. The complete Alembic migration DDL (CREATE TABLE statements, CREATE INDEX, CREATE TYPE for enums, CREATE EXTENSION)
6. Test fixture design: how you provide async sessions, how you handle table setup/teardown
7. Exact list of files to create and modify

### Step 2: Implement Core Infrastructure
- `core/db/__init__.py`
- `core/db/engine.py` — `create_async_engine`, `async_session_factory`, connection pool settings
- `core/db/base.py` — Base model class
- All ORM models in `core/db/models/*.py`
- `alembic.ini` at project root
- `core/db/migrations/env.py` and `script.py.mako`
- First migration in `core/db/migrations/versions/`
- `core/config/settings.py` updates (DATABASE_URL, DATABASE_URL_SYNC, cache TTL settings)
- `pyproject.toml` and `requirements.txt` updates

### Step 3: Implement Repository Layer
- `core/db/repositories/base.py` — Abstract base with generic CRUD
- `core/db/repositories/company_repo.py` — CompanyRepository
- `core/db/repositories/auth_repo.py` — AuthRepository
- `core/db/repositories/pipeline_repo.py` — PipelineRunRepository
- `core/db/repositories/cache_repo.py` — PlatformCacheRepo, UrlEnrichmentCacheRepo
- `core/db/repositories/gap_analysis_repo.py` — QueryGapRepo, CitationRepo, ClusterSpecRepo
- `core/db/repositories/embedding_repo.py` — SemanticUnitRepo, ParagraphEmbeddingRepo
- FastAPI dependency injection wiring (session factory, repo factory functions)

### Step 4: Tests
- `tests/db/conftest.py` — Async session fixtures, table setup/teardown
- `tests/db/test_models.py` — ORM model creation, constraint tests
- `tests/db/test_company_repo.py` — Company CRUD
- `tests/db/test_auth_repo.py` — User CRUD, invite flow
- `tests/db/test_pipeline_repo.py` — Pipeline run CRUD
- `tests/db/test_cache_repo.py` — Cache lookup with TTL, cache miss/hit scenarios
- `tests/db/test_gap_analysis_repo.py` — Query gap CRUD, bulk insert, incremental update
- `tests/db/test_embedding_repo.py` — pgvector operations, similarity queries
- Verify all existing 766+ tests still pass (run full test suite)

---

## 11. Critical Constraints

1. **Never import from `api/` inside `core/`** — existing architectural rule. The DB layer lives in `core/db/` and must not import from `api/`. API routes import from core, not the other way around.
2. **Do NOT modify existing Pydantic models** in `core/models/` — they are used by pipelines, CLI, and tests. ORM models in `core/db/models/` are separate but must be convertible to/from the existing Pydantic models via explicit mapping functions.
3. **Do NOT modify any existing pipeline step code** (s1-s8) in this phase — database write hooks are Phase 4. This phase is infrastructure only.
4. **Do NOT modify any existing service layer code** in this phase — service migration is Phase 3.
5. **Do NOT break the filesystem artifact flow** — pipelines continue writing JSON/Markdown to disk. The database is additive.
6. **Maintain all 766+ existing passing tests** — zero regressions.
7. **All new code must have tests** — maintain the project's TDD culture.
8. **Use async throughout** — FastAPI is async; the DB layer must be async-native (`asyncpg` + `AsyncSession`).
9. **Do NOT use Supabase client libraries** — we use raw SQLAlchemy against our own Postgres. The existing `core/storage/supabase_mirror.py` will eventually be deprecated; don't touch it now.
10. **Structural signals are 45 individual typed columns** — NOT a JSONB blob. See Section 4.3 for the rationale. Do not deviate from this.
11. **Respect the cache layer design** — `platform_result_cache` and `url_enrichment_cache` are global (not company-scoped), shared across all companies and runs. The run-scoped tables (`run_citations`, `query_gaps`, etc.) reference the cache via foreign keys.
