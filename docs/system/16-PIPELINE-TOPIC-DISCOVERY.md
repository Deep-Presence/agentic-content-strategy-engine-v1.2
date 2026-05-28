# Pipeline 4: Topic Discovery

> **Location:** `core/topic_discovery/`
> **Owner:** Core
> **Dependencies:** OpenRouter (Claude, Perplexity), pgvector, LangGraph, Content Inventory
> **Dependents:** Pipeline 3 (Content Engine), Content Studio (frontend Planner page), TD-Content Orchestrator
> **Last Updated:** 2026-04-24

## Overview

Pipeline 4 is a multi-source topic discovery and scoring system consisting of two sub-pipelines. **Pipeline A (Discovery)** generates subdomains from 4 independent perspectives, deduplicates via embedding similarity, builds a taxonomy hierarchy, and scores each node on 4 dimensions with persona affinity. **Pipeline B (Expansion)** takes approved subdomains and expands them into concrete topic assignments across buyer stages, intent types, and personas, with cannibalization detection against existing content. Total: ~9,664 lines of code.

The cannibalization detection subsystem (Phase 1 planner scoring + Phase 2 fanout-aware overlap evidence) is a zero-LLM, pure pgvector + SQL system that persists assessments durably to a dedicated table and enriches them incrementally as content inventory and prompt tracking data change.

## Architecture

```
PIPELINE A: DISCOVERY
---------------------
Phase 0: Preflight (load company context, personas)
    |
Phase 1 (S1): Multi-Source Generation
    +-- Source A: Company Brainstorm (iterative, 1-4 rounds)
    +-- Source B: Persona Brainstorm (iterative, persona-driven)
    +-- Source C: Competitive Landscape (Perplexity deep research)
    +-- Source D: Adversarial Diversity (5 specialist lenses)
    |
    Deduplication (embedding similarity, threshold 0.85)
    |
Phase 2 (S2): Unified Scoring
    |   Single LLM call: hierarchy + 4-dim scoring + persona affinity
    |
HITL-1: Taxonomy Review (approve / modify tree / retry)
    |
Phase 2.5: Source Confidence Blending
    |
Output: Scored Taxonomy + PersonaAffinityIndex

PIPELINE B: EXPANSION
---------------------
Preflight: Load taxonomy + scores + personas from Pipeline A artifacts
    |
Phase 3 (S3): On-Demand Expansion
    |   Per-subdomain: relevance pruning + topic generation (2-5 per cell)
    |   Cannibalization detection via pgvector (Phase 1 planner scoring)
    |
HITL-2: Matrix Review (approve / modify assignments)
    |
Post-HITL-2: Durable cannibalization persistence
    |   recalculate_assignment_cannibalization_records() (Phase 2 overlap evidence)
    |
Output: TopicAssignmentMatrix -> Content Engine
```

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline.py` | 1,455 | Main orchestrator (Pipeline A + B) |
| `agents.py` | 1,941 | All agent functions (S1-S3) |
| `cannibalization_service.py` | 788 | Zero-LLM cannibalization scoring + persistence |
| `db_ops.py` | 1,295 | Async Postgres I/O |
| `graph.py` | 719 | LangGraph HITL (2 checkpoints) |
| `scoring.py` | 626 | Priority scoring + persona affinity |
| `persistence.py` | 643 | DB hooks for pipeline artifacts |
| `storage.py` | 393 | JSON/filesystem helpers |
| `display_id.py` | 135 | Human-readable ID generation |
| `repository.py` | 24 | Re-export from canonical location |
| `prompts/` (10 files) | 2,454 | All prompt templates |

### DB Tables

| Table | Model | Purpose |
|-------|-------|---------|
| `topic_discoveries` | `TopicDiscoveryModel` | Top-level discovery run per company |
| `taxonomy_trees` | `TaxonomyTreeModel` | Versioned taxonomy snapshots |
| `subdomain_nodes` | `SubdomainNodeModel` | Individual nodes in taxonomy hierarchy |
| `topic_assignments` | `TopicAssignmentModel` | Content opportunities in dimensionality matrix |
| `td_source_results` | `SourceResultModel` | Per-source S1 generation statistics |
| `td_persona_affinity` | `PersonaAffinityModel` | Persona-subdomain affinity scores |
| `topic_assignment_cannibalization` | `TopicAssignmentCannibalizationModel` | Durable cannibalization assessments (migration 0041) |

### Repository Classes (7 total)

All in `core/db/repositories/topic_discovery_repo.py`, re-exported from `core/topic_discovery/repository.py`:

| Repository | Table | Key Methods |
|-----------|-------|-------------|
| `TopicDiscoveryRepository` | `topic_discoveries` | `upsert_discovery`, `get_latest_by_company`, `update_versions`, `update_status` |
| `TaxonomyTreeRepository` | `taxonomy_trees` | `upsert_taxonomy`, `get_by_discovery`, `invalidate_tree_json`, `update_tree_json` |
| `SubdomainNodeRepository` | `subdomain_nodes` | `bulk_create`, `get_by_taxonomy`, `get_root_nodes`, `delete_by_taxonomy`, `claim_for_expansion` |
| `TopicAssignmentRepository` | `topic_assignments` | `bulk_create`, `delete_by_discovery`, `update_assignment_status`, `bulk_merge_metadata`, `list_for_cannibalization`, `list_delta_recompute_assignment_ids` |
| `TopicAssignmentCannibalizationRepository` | `topic_assignment_cannibalization` | `bulk_upsert_assessments`, `get_assignment_ids_by_top_match_inventory_ids` |
| `SourceResultRepository` | `td_source_results` | `bulk_create`, `delete_by_discovery` |
| `PersonaAffinityRepository` | `td_persona_affinity` | `bulk_create`, `delete_by_discovery` |

## Multi-Source Generation (S1)

### 4 Sources

| Source | Perspective | Method | Model | Rounds |
|--------|------------|--------|-------|--------|
| **A** | Company brainstorm | Iterative expansion | Claude Sonnet | 1-4 |
| **B** | Persona needs | Iterative, persona-driven | Claude Sonnet | 1-4 |
| **C** | Competitive landscape | Single deep research call | Perplexity sonar-deep-research | 1 |
| **D** | Adversarial diversity | 5 specialist lenses | Claude Sonnet | 1 per lens |

**Source D specialist lenses:** Regulatory compliance, Enterprise procurement, Accessibility advocacy, Customer success, Security & risk analysis.

### Coverage Metrics (Capture-Recapture)

Per-source: **Chao1 estimator** (`S_obs + f1^2/2f2`) for unseen species richness, **Good-Turing sample coverage** (`1 - f1/N`).

Between-source: **Lincoln-Petersen** pairwise estimates.

Target: 95% aggregate sample coverage.

### Deduplication

Embedding-based clustering (cosine similarity >= 0.85). Merges persona_ids + pain_points from absorbed duplicates into canonical candidates.

## Scoring System (S2 -- Unified)

Single LLM call (Claude Sonnet) computes hierarchy + 4-dimension scoring + persona affinity simultaneously.

### 4 Priority Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Strategic Centrality | 0.35 | Value of being cited (core vs peripheral) |
| Citation Opportunity | 0.25 | Probability of getting cited (whitespace vs saturated) |
| Content Authority | 0.20 | Feasibility of production (proprietary data, expertise) |
| Conversion Potential | 0.20 | Value density per citation (buyer proximity) |

**Composite:** `0.35*centrality + 0.25*opportunity + 0.20*authority + 0.20*conversion`

### Source Confidence Blending (Phase 2.5)

After HITL-1, blends LLM composite with cross-source signal:
- `blended_score = 0.75 * llm_composite + 0.25 * source_confidence`
- Source confidence: 0.25 (1 source) to 1.0 (all 4 sources)

### Persona Affinity

Per-node, per-persona score (0.0-1.0). During expansion (Phase 3), algorithmic adjustments:
- Direct persona match: +0.2
- Role-based buyer stage boost (executives +0.1 for BOFU, practitioners +0.1 for TOFU)

## HITL Checkpoints

### HITL-1: Taxonomy Review
User can: approve, modify (add/delete/rename/reparent nodes), retry (max 2). Edits applied to tree, recomputes depths and sort order.

### HITL-2: Matrix Review
User can: approve, modify (adjust priority, remove, add assignments).

## Expansion (S3)

Per-subdomain, single LLM call generates 2-5 topic assignments per relevant `buyer_stage x intent_type x persona` cell. Self-pruning: LLM skips irrelevant combinations.

### Subdomain Claim for Expansion

`SubdomainNodeRepository.claim_for_expansion()` uses optimistic concurrency with `UPDATE ... WHERE` to atomically claim a subdomain for expansion. Eligible states: `not_expanded`, `failed`, `expanded` (if re-expand allowed). Stale `expanding` entries (>20 minutes) are also claimable (crash recovery).

**File ref:** `core/db/repositories/topic_discovery_repo.py:316-348`

## Cannibalization Detection Subsystem

### Design Philosophy

The cannibalization detection system is a **zero-LLM, pure pgvector + SQL** design. No LLM calls are made during scoring. All signals are computed deterministically from embedding similarity, lexical overlap, intent classification, format matching, tracked query overlap, and citation overlap. This makes the system:

- **Fast:** No LLM latency, runs in milliseconds per assignment
- **Deterministic:** Same inputs always produce same scores
- **Cheap:** Only pgvector similarity search + SQL queries
- **Incrementally refreshable:** Can be re-run when content inventory or prompt tracking data changes

### Two Phases

#### Phase 1: Planner Scoring (During Pipeline B)

Runs inline during the expansion phase (Pipeline B, Phase 3) to provide immediate cannibalization risk feedback to the planner before HITL-2 review.

**Entry point:** `assess_assignment_cannibalization()` in `cannibalization_service.py:106-167`

**Flow:**
1. For each topic assignment, build a similarity query via `build_assignment_similarity_query()`:
   ```
   {topic_text} | {description} | {keyword1, keyword2, ...}
   ```
2. Call `ContentInventoryService.check_cannibalization_batch()` for pgvector similarity search against `content_inventory` table
3. For each match above `td_cannibalization_threshold` (default 0.80):
   - Compute 6 scoring signals
   - Compute weighted risk score
   - Classify risk level and recommended action
4. Write assessment to `topic_assignments.metadata_json` (inline metadata)

**Output (per assignment):**
```json
{
  "cannibalization_risk": 0.87,
  "cannibalization_risk_score": 0.82,
  "cannibalization_risk_level": "high",
  "cannibalization_recommended_action": "merge_or_refresh_existing",
  "cannibalization_reasons": [
    "87% semantic similarity to an existing published page.",
    "Title, URL, or keyword overlap suggests the same search demand."
  ],
  "cannibalization_matches": [
    {
      "inventory_id": "uuid",
      "url": "https://...",
      "title": "...",
      "similarity": 0.87,
      "word_count": 2400,
      "risk_score": 0.82,
      "risk_level": "high",
      "signals": {
        "semantic_similarity": 0.87,
        "lexical_overlap": 0.34,
        "intent_overlap": 1.0,
        "format_overlap": 1.0,
        "query_overlap": 0.0,
        "citation_overlap": 0.0
      }
    }
  ]
}
```

#### Phase 2: Fanout-Aware Overlap Evidence (Post HITL-2)

Runs after `persist_td_assignments()` to enrich assessments with cross-system overlap signals that require joins against `content_inventory_prompts` and `tracked_prompts`.

**Entry point:** `recalculate_assignment_cannibalization_records()` in `cannibalization_service.py:197-347`

**Additional signals computed (beyond Phase 1):**
- **Query overlap** (`query_overlap_score`): How many of the assignment's candidate queries are already tracked by prompt tracking for the matched page. Uses `ContentInventoryPromptRepository.get_page_prompt_scopes_batch()` to find root/direct/fanout prompt IDs associated with each matched inventory page.
- **Citation overlap** (`citation_overlap_score`): How many times the matched page has been cited in Daily Tracker responses. Uses `ContentInventoryPromptRepository.get_citation_metrics_batch()` with a configurable window (default 90 days).

**Flow:**
1. Load assignments from DB via `TopicAssignmentRepository.list_for_cannibalization()`
2. Build similarity queries and run batch pgvector search
3. For each match, fetch citation metrics and prompt scope data
4. Compute `_compute_query_overlap_signals()` for each match
5. Build full assessments with signal overrides
6. Persist to `topic_assignment_cannibalization` table via `bulk_upsert_assessments()`
7. Merge metadata back into `topic_assignments.metadata_json` via `bulk_merge_metadata()`

**File ref:** `cannibalization_service.py:197-347`

### Scoring Formula

The risk score is a weighted sum of 6 signals, capped at 1.0:

```
risk_score = min(1.0,
    (semantic_similarity * 0.58)
  + (lexical_overlap    * 0.12)
  + (intent_overlap     * 0.05)
  + (format_overlap     * 0.03)
  + (query_overlap      * 0.14)
  + (citation_overlap   * 0.08)
)
```

**High-risk floor:** When `semantic_similarity >= td_cannibalization_high_risk_threshold` AND any corroborating signal is present (lexical >= 0.1 OR intent >= 0.75 OR query >= 0.5 OR citation >= 0.3), the risk score is floored at the high-risk threshold plus a scaled delta:

```
risk_score = max(risk_score,
    min(1.0,
        high_risk_threshold
        + ((semantic_similarity - high_risk_threshold) * 0.5)
    )
)
```

**File ref:** `cannibalization_service.py:565-593`

### Signal Computation Details

#### 1. Semantic Similarity (weight: 0.58)
Direct pgvector cosine similarity from `ContentInventoryService.check_cannibalization_batch()`. Uses `text-embedding-3-small` (1536-dim) embeddings.

#### 2. Lexical Overlap (weight: 0.12)
Jaccard similarity between tokenized sets from:
- **Assignment tokens:** topic_text + description + target_keywords
- **Page tokens:** title + URL path (hyphen/slash-separated) + content_preview

Tokenization strips stop words and tokens < 3 chars.

**File ref:** `cannibalization_service.py:667-699`

#### 3. Intent Overlap (weight: 0.05)
Comparison between the assignment's declared `intent_type` and the page's inferred intent.

Page intent is inferred from title, URL, and content_preview using keyword-set membership:
- Commercial hints: best, compare, pricing, review, alternative, etc.
- Informational hints: guide, how, tutorial, what, template, etc.
- Navigational hints: api, dashboard, docs, login, etc.
- Transactional hints: book, buy, demo, signup, trial, etc.

**Scoring:**
| Condition | Score |
|-----------|-------|
| Same intent | 1.0 |
| Both commercial/transactional | 0.65 |
| Unknown page intent | 0.35 |
| Different intent families | 0.0 |

**File ref:** `cannibalization_service.py:717-743`

#### 4. Format Overlap (weight: 0.03)
Comparison between the assignment's `content_format` and the page's detected/inferred format.

**Format families:**
- `guide`: comprehensive_guide, explainer, how_to, tutorial, pillar_page, long_blog, etc.
- `comparison`: comparison, comparison_guide, listicle
- `case_study`: case_study
- `landing_page`: docs, landing_page, navigational

**Scoring:**
| Condition | Score |
|-----------|-------|
| Same family | 1.0 |
| guide + landing_page | 0.35 |
| Different families | 0.0 |
| Either unknown | 0.0 |

**File ref:** `cannibalization_service.py:746-789`

#### 5. Query Overlap (weight: 0.14) -- Phase 2 Only
Uses `_compute_query_overlap_signals()` from `ContentInventoryPromptRepository` to check how many of the assignment's candidate queries overlap with the tracked prompts associated with the matched inventory page.

Candidate queries are built by `build_assignment_candidate_queries()`:
1. The topic_text itself
2. Keywords extracted from `metadata.target_keywords` (supports both list and `{primary, secondary[]}` dict formats)

**File ref:** `cannibalization_service.py:59-73`

#### 6. Citation Overlap (weight: 0.08) -- Phase 2 Only
Uses `ContentInventoryPromptRepository.get_citation_metrics_batch()` to count how many times the matched page has been cited in Daily Tracker responses within the overlap window.

Score: `min(citation_count / 5, 1.0)` — caps at 5 citations.

### Risk Level Classification

| Level | Condition |
|-------|-----------|
| `high` | `max_similarity >= td_cannibalization_high_risk_threshold` (default 0.90) |
| `medium` | `max_similarity >= td_cannibalization_threshold` (default 0.80) OR `risk_score >= td_cannibalization_medium_risk_threshold` |
| `low` | `max_similarity > 0` but below thresholds |
| `none` | No matches found |

**File ref:** `cannibalization_service.py:644-654`

### Recommended Actions

| Risk Level | Condition | Action |
|-----------|-----------|--------|
| `high` | lexical >= 0.2 OR intent >= 0.75 | `merge_or_refresh_existing` |
| `high` | otherwise | `optimize_existing` |
| `medium` | any | `differentiate_angle` |
| `low` or `none` | any | `safe_to_create_new` |

**File ref:** `cannibalization_service.py:657-664`

### Two-Surface Persistence

Cannibalization assessments are persisted in two locations:

#### Surface 1: Assignment Metadata (Inline)

Each `TopicAssignmentModel.metadata_json` is enriched with the 6 cannibalization keys via `TopicAssignmentRepository.bulk_merge_metadata()`. This is a shallow merge that preserves existing metadata while adding/updating cannibalization fields.

**Keys written:**
- `cannibalization_risk` (float, max similarity)
- `cannibalization_risk_score` (float, weighted composite)
- `cannibalization_risk_level` (string: none/low/medium/high)
- `cannibalization_recommended_action` (string)
- `cannibalization_reasons` (list of strings, max 3)
- `cannibalization_matches` (list of match dicts, max `td_cannibalization_max_matches`)

This surface is read by the Planner frontend for inline risk badges and by the Content Studio for priority queue ranking.

#### Surface 2: Durable Table (`topic_assignment_cannibalization`)

The `TopicAssignmentCannibalizationModel` table (migration 0041) stores a normalized, queryable representation:

| Column | Type | Purpose |
|--------|------|---------|
| `assignment_id` | UUID FK (unique) | One assessment per assignment |
| `discovery_id` | UUID FK | Scoped to discovery run |
| `company_id` | UUID FK | For company-level queries |
| `top_match_inventory_id` | UUID FK (nullable) | FK to content_inventory for join queries |
| `max_similarity` | Float | Highest semantic similarity |
| `risk_score` | Float | Weighted composite score |
| `risk_level` | String(32) | none/low/medium/high |
| `recommended_action` | String(64) | Action classification |
| `reasons_json` | JSONB | Human-readable reasons (max 3) |
| `matches_json` | JSONB | Full match array with signals |
| `signals_json` | JSONB | Top match signal breakdown |
| `metadata_json` | JSONB | Source, matrix_version, embedding_model, evaluated_at |

**Indexes:**
- `ix_td_assignment_cannibalization_discovery` on `discovery_id`
- `ix_td_assignment_cannibalization_company_level` on `(company_id, risk_level)`

**Persistence via:** `TopicAssignmentCannibalizationRepository.bulk_upsert_assessments()` — upsert by `assignment_id` (unique constraint).

**File ref:** `cannibalization_service.py:412-515`, `core/db/models/topic_discovery.py:281-299`

### Delta Scope Resolver

When content inventory or prompt tracking data changes (e.g., new page crawled, new prompt linked, page published via CMS), the system can re-evaluate only the affected assignments instead of the entire matrix.

**Entry point:** `resolve_impacted_assignment_scope_for_inventory_changes()` in `cannibalization_service.py:350-409`

**Strategy:**
1. **Direct impact:** Find assignments whose durable `top_match_inventory_id` points at any of the changed pages. Uses `TopicAssignmentCannibalizationRepository.get_assignment_ids_by_top_match_inventory_ids()`.
2. **Indirect impact:** Include a capped slice of planner-open assignments from the latest discovery so newly added pages can affect current planning work. Uses `TopicAssignmentRepository.list_delta_recompute_assignment_ids()`.
3. **Union and deduplicate** both sets, preserving order (direct first).

**Cap:** `td_cannibalization_delta_assignment_cap` (configurable, prevents unbounded recomputation).

**Returns:** `(discovery_id, assignment_ids)` tuple for downstream `recalculate_assignment_cannibalization_records()`.

**File ref:** `cannibalization_service.py:350-409`

### Async Runner Integration

Cannibalization recalculation is triggered from:

1. **Pipeline B `persist_td_assignments()`** (post HITL-2) — calls `recalculate_assignment_cannibalization_records()` with `source="td_matrix_persist"`. Best-effort: failure logged but does not crash the pipeline.

2. **CMS publish flow** — when a page is published via CMS, `ContentInventoryService.register_published_content()` can trigger delta recomputation for affected assignments.

3. **Content Inventory enrichment** — when `enrich_thin_pages()` updates page content previews and embeddings, delta scope resolution identifies affected assignments.

4. **Manual re-run** — API endpoint can trigger full recalculation for a discovery.

**File ref:** `persistence.py:361-374`

### Frontend Surface

The cannibalization data surfaces in two places:

1. **Planner Page (PriorityQueue badges):** Each topic assignment card displays a colored risk badge based on `cannibalization_risk_level`:
   - High (red): "Cannibalizes existing content"
   - Medium (amber): "Partial overlap with existing content"
   - Low/None: No badge

2. **Content Studio Detail Drawer (evidence panel):** When a user clicks a topic assignment card, the detail drawer shows:
   - Risk score and level
   - Recommended action
   - Human-readable reasons (up to 3)
   - Matched pages with similarity scores and signal breakdowns
   - Link to the matched content inventory page

### Persist Lifecycle

```
Phase 1 (inline, Pipeline B)
    |
    v
assess_assignment_cannibalization()
    |
    v
metadata_json enriched on TopicAssignment (in-memory)
    |
    v
persist_td_assignments() writes to DB
    |
    v (Post HITL-2, async)
recalculate_assignment_cannibalization_records()
    |
    v
Phase 2 (durable, with overlap evidence)
    |
    +--> TopicAssignmentCannibalizationRepository.bulk_upsert_assessments()
    +--> TopicAssignmentRepository.bulk_merge_metadata()
    |
    v
Delta triggers (CMS publish, inventory enrichment)
    |
    v
resolve_impacted_assignment_scope_for_inventory_changes()
    |
    v
recalculate_assignment_cannibalization_records()
    (scoped to affected assignments only)
```

## Display ID System

Company-scoped human-readable IDs (e.g., "WE-042"):
- Prefix: company initials or first 2 letters
- Counter: `SELECT FOR UPDATE` serialized allocation
- Backfilled after every bulk write

Display IDs persist throughout the entire lifecycle: TD -> Planner -> GA -> CE -> Content Studio -> Published Article.

## DB Persistence (`persistence.py`)

8 persistence hooks, all following the same pattern:
- `_should_persist()` guard: session_factory + run_id + company_id required
- Per-function transaction isolation
- Graceful degradation: DB errors NEVER crash the pipeline
- Idempotent: delete-before-insert or upsert

| Hook | When Called | What It Writes |
|------|-----------|---------------|
| `persist_td_discovery` | Pipeline start | `TopicDiscoveryModel` row |
| `persist_td_source_results` | After S1 | `SourceResultModel` rows |
| `persist_td_taxonomy` | After HITL-1 | `TaxonomyTreeModel` + `SubdomainNodeModel` rows |
| `persist_td_persona_affinity` | After Phase 2.5 | `PersonaAffinityModel` rows |
| `persist_td_scoring_metadata` | After Phase 2.5 | Version counters on discovery |
| `persist_td_assignments` | After HITL-2 | `TopicAssignmentModel` rows + cannibalization |
| `persist_td_assignment_status_batch` | TD->Content orchestrator | Bulk status updates |
| `persist_td_status_update` | Pipeline transitions | Discovery status |

**File ref:** `persistence.py:1-643`

## DB Operations (`db_ops.py`)

Module-level async functions (no class) for direct Postgres reads/writes via TD repositories.

**Design differences from `persistence.py`:**
- **No try/except swallowing** — errors propagate to caller (pipeline fails visibly)
- Naming convention: `db_read_*`, `db_write_*`, `db_get_*`
- Same `_db_row_to_pydantic_assignment()` converter shared with `cannibalization_service.py`

**Key functions:**
- `db_read_manifest()` — load `TopicDiscoveryManifest` from DB
- `db_write_manifest()` — update manifest_json on discovery row
- `db_read_taxonomy()` — reconstruct `TaxonomyTree` from DB nodes
- `db_write_taxonomy()` — flatten tree + bulk insert nodes
- `db_read_assignments()` — load `TopicAssignmentMatrix` from DB
- `db_write_assignments()` — bulk insert/update assignment rows

**File ref:** `db_ops.py:1-100+`

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `topic_discovery_brainstorm_model` | `anthropic/claude-sonnet-4-6` | Source A+B+D LLM |
| `topic_discovery_dedup_model` | `anthropic/claude-haiku-4-5` | Deduplication LLM |
| `topic_discovery_source_c_model` | `perplexity/sonar-deep-research` | Competitive research |
| `topic_discovery_unified_s2_model` | `anthropic/claude-sonnet-4-6` | Unified scoring LLM |
| `topic_discovery_dedup_threshold` | 0.85 | Embedding similarity threshold for dedup |
| `topic_discovery_max_expansion_rounds` | 4 | Max iterative expansion rounds |
| `topic_discovery_max_concurrent_sources` | 4 | Source parallelism |
| `td_cannibalization_threshold` | 0.80 | Min similarity for cannibalization match |
| `td_cannibalization_high_risk_threshold` | 0.90 | Similarity floor for high-risk classification |
| `td_cannibalization_medium_risk_threshold` | — | Risk score floor for medium classification |
| `td_cannibalization_max_matches` | — | Max matches stored per assignment |
| `td_cannibalization_overlap_window_days` | 90 | Citation metrics lookback window |
| `td_cannibalization_delta_assignment_cap` | — | Max assignments in delta recompute |
| `embedding_model` | `text-embedding-3-small` | Embedding model for similarity search |

## Integration with Content Engine

Topic assignments flow to Content Engine via orchestration:
- TD HITL-2 approved assignments -> `topic_assignment_ids` in `ContentGenerationInputV13`
- Display IDs persist throughout lifecycle: TD -> Planner -> GA -> CE -> Content Studio -> Published

### Durable Topic Run Bridge

When TD assignments enter the Content Engine via `ContentEngineTopicRunService.create_td_batch()`:
1. Batch run created in `content_engine_batch_runs`
2. Per-topic runs created in `content_engine_topic_runs` with `display_id` copied from `TopicAssignmentModel`
3. `brief_id` initially set to `display_id` (unified identity until CE generates its own)
4. Status transitions propagated back to `topic_assignments.status` via `persist_td_assignment_status_batch()`

**File ref:** `core/services/content_engine_topic_runs.py:126-227`

## Error Handling

### Pipeline-Level

Pipeline B `persist_td_assignments()` catches all exceptions from `recalculate_assignment_cannibalization_records()` — cannibalization recalculation failure does not crash the main pipeline.

### Cannibalization Service

All functions in `cannibalization_service.py` are designed to be side-effect-safe:
- Scoring functions are pure (no I/O)
- Persistence functions open their own transactions
- Delta scope resolver returns empty results on any error

### Persistence Hooks

Every `persist_td_*()` function catches all exceptions and logs warnings. DB errors never crash the pipeline (filesystem-first, DB-additive pattern).

## Tech Debt

1. **Phase 1 and Phase 2 scoring run separately:** The Phase 1 inline scoring during expansion does not have access to query_overlap and citation_overlap signals. These are only available in Phase 2 (post HITL-2). This means the planner sees a less accurate risk score than the final persisted score.

2. **`_compute_query_overlap_signals` imported from `content_inventory_prompt_repo`:** This is a function defined in a repository module but used as a pure utility. Should be extracted to a shared module.

3. **No incremental embedding cache:** Each recalculation re-embeds all assignment similarity queries. A cache of assignment embeddings keyed by `(assignment_id, topic_text_hash)` would reduce embedding API calls during delta recomputation.

4. **Expansion batch concurrency:** `claim_for_expansion()` on `SubdomainNodeModel` uses optimistic concurrency with a 20-minute stale timeout. If multiple workers expand the same subdomain concurrently due to clock skew, duplicate assignments could be created (mitigated by the dedup layer but not prevented at the DB level).

5. **O(n*m) match scoring:** Each assignment's matches are scored individually against every matched page. For large content inventories with many matches, this could become slow. Current max_matches cap mitigates this.
