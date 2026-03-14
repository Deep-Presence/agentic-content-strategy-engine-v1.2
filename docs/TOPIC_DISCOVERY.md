# Topic Discovery Module — Technical Documentation

> Two-pipeline architecture for automated content opportunity discovery in B2B AI citation strategy.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Pipeline A: Discovery](#3-pipeline-a-discovery)
4. [Phase 0: Preflight](#4-phase-0-preflight)
5. [Phase 1 (S1): Multi-Source Subdomain Generation](#5-phase-1-s1-multi-source-subdomain-generation)
6. [Phase 2 (S2): Exhaustiveness Evaluation & Merge](#6-phase-2-s2-exhaustiveness-evaluation--merge)
7. [HITL-1: Taxonomy Approval](#7-hitl-1-taxonomy-approval)
8. [Phase 2.5: Algorithmic Subdomain Scoring](#8-phase-25-algorithmic-subdomain-scoring)
9. [Pipeline B: Expansion](#9-pipeline-b-expansion)
10. [Phase 3 (S3): On-Demand Expansion](#10-phase-3-s3-on-demand-expansion)
11. [HITL-2: Matrix Approval](#11-hitl-2-matrix-approval)
12. [Finalize](#12-finalize)
13. [Scoring Engine Deep Dive](#13-scoring-engine-deep-dive)
14. [Persona Affinity Deep Dive](#14-persona-affinity-deep-dive)
15. [API Endpoints](#15-api-endpoints)
16. [Data Models](#16-data-models)
17. [Storage Layout](#17-storage-layout)
18. [Configuration](#18-configuration)
19. [CLI Tools](#19-cli-tools)
20. [File Reference](#20-file-reference)

---

## 1. Overview

The Topic Discovery module identifies exhaustive content opportunities for a B2B company through two decoupled pipelines:

**Pipeline A (Discovery)** — generates and scores a taxonomy:
1. **Generate** subdomain candidates from 4 independent sources (company context, personas, competitors, adversarial gaps)
2. **Deduplicate** via embedding-based clustering
3. **Organize** into a hierarchical taxonomy tree
4. **Score** every subdomain algorithmically (zero LLM calls)
5. End with `status=discovery_complete` — no expansion, no matrix

**Pipeline B (Expansion)** — expands selected subdomains into a content matrix:
1. User triggers expansion with specific `subdomain_ids`
2. **Expand** each selected subdomain into topic assignments across buyer stages x intent types x personas
3. **Prioritize** each assignment for content production
4. End with `status=approved` — matrix produced

Two human-in-the-loop (HITL) checkpoints: HITL-1 (taxonomy review, Pipeline A) and HITL-2 (matrix review, Pipeline B).

### Design Principles

- **Decoupled pipelines**: Discovery and expansion run independently. Subdomain selection is the trigger for Pipeline B, not an inline checkpoint.
- **On-demand expansion**: Only expand subdomains the user selects (not all 100+). Reduces LLM calls from ~1,800 to ~20-30.
- **Re-entrant expansion**: Pipeline B can be called multiple times with different subdomains. Each call creates a new matrix version. Manifest accumulates `expanded_subdomain_ids`.
- **Algorithmic scoring**: Subdomain priority and persona affinity computed without LLM calls using source provenance, embedding similarity, and coverage signals.
- **Persona-aware**: Persona identity flows from Source B through dedup, scoring, affinity indexing, and into topic assignments.
- **Filesystem-first, DB-additive**: JSON artifacts are the source of truth. DB persistence is fire-and-forget (never crashes the pipeline).

### LLM Call Budget

| Phase | Pipeline | LLM Calls | Notes |
|-------|----------|-----------|-------|
| S1 (4 sources x ~4 rounds) | A | ~15-20 | Brainstorm |
| S2 (hierarchy construction) | A | 1-2 | Organize tree |
| Scoring + Affinity | A | 0 | Pure algorithmic |
| S3 (per selected subdomain) | B | 1 each | Consolidated expansion |
| **Typical full session** | A+B | **~25-30** | Down from ~1,800 |

---

## 2. Pipeline Architecture

### Pipeline A: Discovery

```
Phase 0: Preflight
  |  Load company context, persona profiles, build name->ID mapping
  |
  v
Phase 1 (S1): Multi-Source Generation
  |  Source A (company) --+
  |  Source B (personas) --+-- parallel --> SourceResult[]
  |  Source C (sitemaps) --+
  |  Source D (adversarial) ---- sequential (uses A+B+C names)
  |
  v
Phase 2 (S2): Merge & Hierarchy
  |  Deduplicate (embedding clusters, threshold=0.85)
  |  Coverage metrics (Chao1, capture-recapture)
  |  Hierarchy construction (LLM -> TaxonomyTree)
  |
  v
+------------------------------------------+
|  HITL-1: Taxonomy Review                 |
|  Actions: approve / modify / retry       |
|  Retry loops back to S1 (max 2 retries)  |
+------------------------------------------+
  |
  v
Phase 2.5: Algorithmic Scoring (zero LLM)
  |  Subdomain scoring (5 signals)
  |  Persona affinity index
  |  Backfill scores into taxonomy nodes
  |
  v
  END: status=discovery_complete, matrix=None
```

### Pipeline B: Expansion (triggered separately)

```
User provides subdomain_ids via POST /expand
  |
  v
Preflight: Load Pipeline A Artifacts
  |  Validate taxonomy + scoring versions exist
  |  Load taxonomy, scored subdomains, persona affinity
  |  Load company context + persona profiles
  |  Validate subdomain_ids against taxonomy
  |
  v
Phase 3 (S3): On-Demand Expansion
  |  1 LLM call per selected subdomain
  |  Generates TopicAssignment[] across all dimensions
  |  Topic priority scoring (zero LLM)
  |  Update expansion_status on taxonomy nodes
  |
  v
+------------------------------------------+
|  HITL-2: Matrix Review                   |
|  Actions: approve / modify               |
|  (no retry -- modify edits in place)     |
+------------------------------------------+
  |
  v
Finalize
  |  Write matrix, update manifest
  |  DB persistence (fire-and-forget)
  |  Emit SSE completed event
  |
  v
  END: status=approved, matrix produced
```

**Orchestrators**:
- Pipeline A: `core/topic_discovery/pipeline.py` -> `run_topic_discovery_pipeline()`
- Pipeline B: `core/topic_discovery/pipeline.py` -> `run_topic_expansion_pipeline()`

### Concurrency Model

Pipeline A and B use different slug-lock prefixes (`topic_discovery:` vs `topic_expansion:`), so they can technically run concurrently on the same slug. This is safe because:
- Pipeline A writes taxonomy/scoring/affinity; Pipeline B reads them at preflight (not mid-flight)
- Pipeline B writes matrix; Pipeline A doesn't touch matrix
- If Pipeline A reruns while Pipeline B is mid-flight, Pipeline B continues with the taxonomy version it loaded

---

## 3. Pipeline A: Discovery

**Function**: `run_topic_discovery_pipeline(input_data: TopicDiscoveryInput, ...)`

**Input model**: `TopicDiscoveryInput`
- `company_name`, `domain`, `company_slug`
- `auto_approve_checkpoints`: `[1]` = auto-approve taxonomy
- `max_expansion_rounds`: brainstorm rounds per source (default 4)
- `dedup_threshold`: embedding similarity threshold (default 0.85)

**Output model**: `TopicDiscoveryOutput`
- `taxonomy`: approved `TaxonomyTree`
- `matrix`: always `None` (expansion is Pipeline B's job)
- `coverage`: `CaptureRecaptureResult`
- `scored_subdomains`, `persona_affinity`
- `status`: `TopicDiscoveryStatus.discovery_complete`

**Status lifecycle**: `draft` -> `hitl_pending` (HITL-1) -> `discovery_complete`

---

## 4. Phase 0: Preflight

**Purpose**: Load all prerequisite data before generating subdomains.

**Steps**:

1. **Resolve slugs**: `company_slug` from company name, `effective_slug` = `{company}__{product}` if product-level.
2. **Load company context**: `company_context/{effective_slug}.md` (falls back to `{company_slug}.md`). Raises `RuntimeError` if empty -- Knowledge Base pipeline must run first.
3. **Load persona profiles**: Markdown files from `audience_personas/{slug}/profiles/`. Raises `RuntimeError` if none -- Audience Persona pipeline must run first.
4. **Build persona mappings**:
   - `persona_entries`: `[(persona_id, persona_name), ...]` from persona manifest
   - `persona_name_to_id`: `{"David Chen, CFO": "david", ...}` -- passed to Source B for persona ID resolution

**Prerequisite Pipelines**: Knowledge Base (1a) + Audience Persona (1b) must complete first.

**Files**: `pipeline.py:289-326`

---

## 5. Phase 1 (S1): Multi-Source Subdomain Generation

**Purpose**: Generate candidate content subdomains from 4 independent perspectives.

### Source A: Company-Perspective Brainstorm

- **Agent**: `run_source_a_company_brainstorm()`
- **Input**: Company context markdown
- **Mechanism**: Iterative LLM brainstorm (up to `max_expansion_rounds` rounds). Each round sends previously generated subdomains to avoid duplicates.
- **Output**: `SourceResult` with `SubdomainCandidate[]`, Chao1 estimate, sample coverage

### Source B: Audience/Persona Brainstorm

- **Agent**: `run_source_b_persona_brainstorm()`
- **Input**: Concatenated persona profiles + company context + `persona_name_to_id` mapping
- **Mechanism**: Same iterative pattern as Source A, but from audience perspective. The LLM output includes `source_personas` (persona names) and `pain_points_addressed` per subdomain.
- **Persona Resolution**: `_resolve_persona_ids()` fuzzy-matches LLM-output persona names to manifest persona IDs:
  1. Exact match: `"David Chen, CFO"` -> `"david"`
  2. Case-insensitive: `"david chen, cfo"` -> `"david"`
  3. Substring: `"David"` -> `"david"` (matches `"David Chen, CFO"`)
- **Output**: `SourceResult` with candidates carrying `persona_ids: ["david", ...]` and `pain_points: [...]`

### Source C: Competitor Sitemaps

- **Agent**: `run_source_c_competitor_sitemaps()`
- **Status**: Placeholder -- `sitemap_data = ""` in pipeline. Scoring weight set to 0.0.
- **Output**: `SourceResult` (typically empty or minimal)

### Source D: Adversarial Gap-Finding

- **Agent**: `run_source_d_adversarial()`
- **Input**: Company context + existing subdomain names from A+B+C
- **Mechanism**: Sequential (runs after A+B+C). Finds content gaps the other sources missed.
- **Output**: `SourceResult` with gap-filling candidates

### Execution

Sources A, B, C run in parallel via `asyncio.gather()`. Source D runs sequentially after, using the combined candidate names from A+B+C. All raw results are persisted to `raw/source_{x}_v1.json`.

**Files**: `pipeline.py:342-424`, `agents.py:200-470`

---

## 6. Phase 2 (S2): Exhaustiveness Evaluation & Merge

**Purpose**: Deduplicate candidates across sources, measure coverage, and organize into a hierarchy.

### Step 1: Deduplication

- **Function**: `deduplicate_subdomains_with_clusters(candidates, threshold=0.85)`
- **Mechanism**: Embeds all candidate names via OpenAI `text-embedding-3-small`, builds similarity clusters, keeps the highest-confidence candidate per cluster.
- **Persona merging**: When candidates are absorbed into a cluster, their `persona_ids` are merged into the kept candidate: `merged_persona_ids = set(kept.persona_ids) | set(absorbed.persona_ids)`
- **Output**: `DeduplicationResult` with `kept` candidates, `clusters`, `embeddings`, `source_of` mapping

### Step 2: Coverage Metrics

- **Function**: `compute_all_coverage_metrics(source_results, dedup_result)`
- **Metrics computed**:
  - **Chao1 lower bound**: Species estimation based on singleton/doubleton frequency
  - **Sample coverage**: % of estimated population covered
  - **Per-source coverage**: Independent metrics per source
  - **Pairwise capture-recapture**: Estimates between each pair of sources
  - **Semantic frequency classes**: Embedding-based frequency classification

### Step 3: Hierarchy Construction

- **Function**: `run_hierarchy_construction(deduped_names, domain, timeout_s=480)`
- **Mechanism**: LLM organizes flat subdomain names into a recursive tree (depth 0 = category, depth 1+ = subdomains)
- **Output**: `TaxonomyTree` with `root_nodes: List[SubdomainNode]`, coverage score, total subdomains, max depth
- **Node structure**: Each `SubdomainNode` has `id`, `name`, `description`, `depth`, `source_provenance` (Dict[str, bool]), `confidence`, `children` (recursive)

**Files**: `pipeline.py:426-483`, `agents.py:470-900`

---

## 7. HITL-1: Taxonomy Approval

**Purpose**: Human reviews the generated taxonomy before scoring.

### LangGraph Implementation

- **Graph**: `build_td_taxonomy_review_graph()` in `graph.py`
- **Interrupt payload**: Full taxonomy JSON + coverage metrics
- **Checkpoint**: `checkpoint=1` (auto-approve with `auto_approve_checkpoints=[1]`)

### User Actions

| Decision | Effect |
|----------|--------|
| `approve` | Proceed with taxonomy as-is |
| `modify` | Apply edits, then proceed |
| `retry` | Re-run S1+S2 with user feedback appended to prompts (max 2 retries) |

### Available Edit Operations

| Op | Parameters | Effect |
|----|-----------|--------|
| `add` | name, description, parent_id | Add new subdomain node |
| `delete` | node_id | Remove node and reparent children |
| `rename` | node_id, new_name | Rename subdomain |
| `reparent` | node_id, new_parent_id | Move node under different parent |

### API Endpoint

```
POST /api/v1/topic-discovery/{run_id}/approve/taxonomy
```

```json
{
  "batch_decision": "approve | modify | retry",
  "user_edits": [
    {"op": "rename", "node_id": "abc123", "new_name": "New Name"},
    {"op": "add", "name": "New Subdomain", "parent_id": "parent123"},
    {"op": "delete", "node_id": "xyz789"}
  ],
  "user_feedback": "Add more subdomains about compliance"
}
```

**Files**: `graph.py:1-250`, `pipeline.py:485-543`

---

## 8. Phase 2.5: Algorithmic Subdomain Scoring

**Purpose**: Rank every subdomain by priority without any LLM calls. Build persona-subdomain affinity index. This is the final phase of Pipeline A.

### Subdomain Scoring

- **Function**: `compute_subdomain_scores(taxonomy)` -> `ScoredSubdomainList`
- **Process**:
  1. Flatten taxonomy tree to list of `SubdomainNode`
  2. Compute 5 signals per node
  3. Exclude unavailable signals (return `None`), renormalize weights
  4. Weighted sum -> `composite_score`
  5. Sort descending, assign `rank`

See [Scoring Engine Deep Dive](#13-scoring-engine-deep-dive) for signal details.

### Persona Affinity

- **Function**: `compute_persona_affinity_index(...)` -> `PersonaAffinityIndex`
- **Process**: For each (persona, subdomain) pair, compute affinity from two signals

See [Persona Affinity Deep Dive](#14-persona-affinity-deep-dive) for details.

### Taxonomy Backfill

After scoring and affinity are computed and persisted, `_backfill_scores_into_taxonomy()` writes `priority_score`, `priority_factors`, and `persona_affinity` back into each `SubdomainNode` in the taxonomy tree, then re-persists the taxonomy. This ensures the taxonomy JSON reflects computed scores.

### Pipeline A Finalize

After Phase 2.5, Pipeline A writes the manifest with:
- `status = discovery_complete`
- `discovery_completed_at = <timestamp>`
- `matrix_version = 0` (no matrix produced)
- `expanded_subdomain_ids = []` (clean slate)

The output `TopicDiscoveryOutput` has `matrix=None`.

**Files**: `pipeline.py:556-697`, `scoring.py`

---

## 9. Pipeline B: Expansion

**Function**: `run_topic_expansion_pipeline(input_data: TopicExpansionInput, ...)`

**Trigger**: User calls `POST /api/v1/topic-discovery/expand` with specific `subdomain_ids`.

**Input model**: `TopicExpansionInput`
- `company_name`, `domain`, `company_slug`
- `subdomain_ids`: list of subdomain IDs to expand (required, non-empty)
- `persona_filter`: optional persona ID to focus expansion
- `taxonomy_version`: optional, defaults to latest
- `auto_approve_checkpoints`: `[2]` = auto-approve matrix

**Output model**: `TopicExpansionOutput`
- `matrix`: `TopicAssignmentMatrix`
- `matrix_version`: version number written
- `subdomains_expanded` / `subdomains_failed`: counters
- `total_assignments`: count of generated topics
- `status`: `TopicDiscoveryStatus.approved`

### Preflight

Pipeline B loads all Pipeline A artifacts before expanding:

1. **Validate discovery**: `manifest.taxonomy_version > 0` and `manifest.scoring_version > 0` (raises `RuntimeError` if not)
2. **Load taxonomy**: Uses `taxonomy_version` from input or manifest
3. **Load scored subdomains + persona affinity**: From manifest versions
4. **Load company context + persona profiles**: Needed for expansion prompts
5. **Validate subdomain_ids**: Must be non-empty. Unknown IDs are logged as warnings and skipped. Raises `ValueError` if no valid IDs remain.

### Re-entrant Behavior

Pipeline B can be called multiple times with different subdomains:
- Each call creates a **new matrix version** (e.g., v1, v2, v3)
- Manifest accumulates `expanded_subdomain_ids` across calls
- Taxonomy nodes get `expansion_status` updated: `"expanded"` / `"failed"` / `"not_expanded"`
- Use `GET /{slug}/expansion-status` to see which subdomains have been expanded

**Files**: `pipeline.py:772-1100`

---

## 10. Phase 3 (S3): On-Demand Expansion

**Purpose**: Generate concrete topic assignments for each selected subdomain.

### Expansion Agent

- **Function**: `run_subdomain_expansion(subdomain_name, subdomain_description, buyer_stages, intent_types, audience_segments, company_context, *, persona_context, timeout_s)` -> `List[TopicAssignment]`
- **Mechanism**: ONE LLM call per subdomain. The prompt includes:
  - Subdomain name + description
  - All dimension combinations (buyer stages x intent types x personas)
  - Company context (up to 40K chars)
  - Optional persona focus context (when persona_filter is set)
- **Self-pruning**: The LLM skips irrelevant dimension combinations (e.g., navigational + awareness) and counts them in `skipped_combos`
- **Output per call**: 15-40 `TopicAssignment` objects (2-5 per relevant dimension combo)

### Dimension Combinations

For each subdomain, the LLM evaluates:

| Dimension | Values |
|-----------|--------|
| Buyer Stages | `tofu`, `mofu`, `bofu` |
| Intent Types | `informational`, `commercial`, `transactional`, `navigational` |
| Personas | All active personas from manifest (e.g., `("david", "David Chen, CFO")`) |

**Total combos per subdomain**: `3 x 4 x N_personas` (e.g., 12 for 1 persona, 36 for 3 personas)

### Always-Irrelevant Combinations (auto-skipped)

- Navigational + any buyer stage (except decision)
- Transactional + Awareness
- Navigational + Awareness

### TopicAssignment Fields

Each generated assignment includes:

| Field | Description |
|-------|-------------|
| `subdomain_id` | ID of the expanded subdomain |
| `topic_text` | Production-ready article title (8-15 words) |
| `buyer_stage` | tofu / mofu / bofu |
| `intent_type` | informational / commercial / transactional |
| `persona_id` | Actual persona ID from manifest (e.g., `"david"`) |
| `persona_name` | Human-readable name (e.g., `"David Chen, CFO"`) |
| `audience_segment` | Same as persona_name |
| `angle` | how_to / strategic / data_driven / narrative / comparison / contrarian / future_looking |
| `description` | 2-3 sentence article description |
| `target_keywords` | `{primary: str, secondary: [str]}` |
| `ai_citation_potential` | HIGH / MEDIUM |
| `content_format` | long_form_article / guide / listicle / comparison / case_study / etc. |
| `estimated_word_count` | 1500-4000 |
| `priority_score` | Computed after expansion (see below) |

### Topic Priority Scoring

After expansion, each assignment gets a priority score (zero LLM):

```
priority = ((buyer_weight + intent_weight) / 2) x subdomain_composite_score
```

| Buyer Stage | Weight | Intent Type | Weight |
|-------------|--------|-------------|--------|
| tofu | 0.6 | informational | 0.5 |
| mofu | 0.8 | commercial | 0.8 |
| bofu | 1.0 | transactional | 1.0 |
| | | navigational | 0.2 |

Example: A `bofu` x `transactional` topic on a subdomain scored `0.85` -> priority = `((1.0 + 1.0) / 2) x 0.85 = 0.85`

### Expansion Status Tracking

After expansion, taxonomy nodes are updated with `expansion_status`:
- `"expanded"` -- successfully expanded
- `"failed"` -- expansion failed for this subdomain
- `"not_expanded"` -- default (not yet selected for expansion)

The updated taxonomy is re-persisted to storage.

### Concurrency & Timeout

- Concurrency capped by `topic_discovery_max_concurrent_sources` semaphore (default: 4)
- Total subdomains capped by `topic_discovery_max_subdomains_to_expand` (default: 20)
- Per-expansion timeout: `topic_discovery_expansion_timeout_s` (default: 300s / 5 minutes)

**Files**: `pipeline.py:887-1000`, `agents.py:900-1100`, `prompts/subdomain_expansion.py`

---

## 11. HITL-2: Matrix Approval

**Purpose**: Human reviews the generated topic assignments before finalizing. Part of Pipeline B.

### LangGraph Implementation

- **Graph**: `build_td_matrix_review_graph()` in `graph.py`
- **Interrupt payload**: Full matrix JSON
- **Checkpoint**: `checkpoint=2` (auto-approve with `auto_approve_checkpoints=[2]`)

### User Actions

| Decision | Effect |
|----------|--------|
| `approve` | Accept matrix as-is |
| `modify` | Apply edits, then approve |

No retry option -- modifications are applied in-place.

### Available Edit Operations

| Op | Parameters | Effect |
|----|-----------|--------|
| `adjust_priority` | assignment index, new priority | Override priority score |
| `remove` | assignment index | Remove topic assignment |
| `add` | topic_text, buyer_stage, intent_type, etc. | Add new assignment |

### API Endpoint

```
POST /api/v1/topic-discovery/{run_id}/approve/matrix
```

```json
{
  "batch_decision": "approve | modify",
  "user_edits": [
    {"op": "remove", "index": 5},
    {"op": "adjust_priority", "index": 0, "priority_score": 0.95}
  ]
}
```

**Files**: `graph.py:450-686`, `pipeline.py:1000-1043`

---

## 12. Finalize

### Pipeline A Finalize

Updates manifest with:
- `status = discovery_complete`
- `discovery_completed_at = <ISO timestamp>`
- `taxonomy_version`, `scoring_version`, `persona_affinity_version`
- `matrix_version = 0`
- `expanded_subdomain_ids = []`

DB persistence (fire-and-forget): `persist_td_status_update()`, `persist_pipeline_run_complete()`

**Files**: `pipeline.py:680-730`

### Pipeline B Finalize

Updates manifest with:
- `status = approved`
- `matrix_version = <new version>`
- `last_expansion_task_id = <task_id>`
- `expanded_subdomain_ids` -- accumulated from previous + current expansion

DB persistence (fire-and-forget): `persist_td_discovery()`, `persist_td_assignments()`

**Files**: `pipeline.py:1065-1100`

---

## 13. Scoring Engine Deep Dive

**File**: `core/topic_discovery/scoring.py`

### Five Scoring Signals

#### Signal 1: Source Confidence (always available)

```python
_score_source_confidence(node: SubdomainNode) -> float
```

- How many of the 4 sources discovered this subdomain?
- Range: 0.25 (1 source) to 1.0 (all 4 sources)
- Manually-added nodes (empty `source_provenance`) -> neutral 0.5
- **Example**: `source_provenance = {source_a: true, source_b: true, source_c: false, source_d: false}` -> `2/4 = 0.5`

#### Signal 2: Content Coverage (optional -- needs site audit)

```python
_score_content_coverage(subdomain_embedding, page_embeddings, threshold) -> Optional[float]
```

- Matches subdomain embedding against site audit page title embeddings
- Zero matching pages -> 1.0 (greenfield = high opportunity)
- Saturates at 10+ matching pages -> 0.0
- Returns `None` if no site audit data -> excluded from scoring

#### Signal 3: Gap Severity (optional -- needs gap analysis)

```python
_score_gap_severity(subdomain_embedding, gap_query_embeddings, gap_scores, threshold) -> Optional[float]
```

- Finds gap analysis queries semantically aligned with this subdomain
- Averages their gap scores (higher gap = client underperforming = higher priority)
- Returns `None` if no gap analysis data

#### Signal 4: Competitive Density (optional -- needs Source C)

```python
_score_competitive_density(subdomain_embedding, competitor_url_embeddings, threshold) -> Optional[float]
```

- Counts competitor pages aligned with this subdomain
- More competitor content = commercially important = higher score
- Saturates at 20+ pages
- **Currently disabled**: Default weight = 0.0 (Source C is placeholder)

#### Signal 5: Persona Breadth (always available)

```python
_score_persona_breadth(node: SubdomainNode) -> float
```

- How many sources mention this subdomain?
- Source B provenance gets a 0.15 bonus (persona-derived = broader audience reach)
- Range: 0.0 to 1.0
- Manually-added nodes -> neutral 0.5

### Weight Configuration

```python
DEFAULT_WEIGHTS = {
    "source_confidence": 0.30,
    "content_coverage": 0.20,
    "gap_severity": 0.25,
    "competitive_density": 0.0,   # disabled until Source C implemented
    "persona_breadth": 0.25,
}
```

When signals are unavailable (return `None`), they are excluded and remaining weights are renormalized to sum to 1.0.

**Current typical output** (only 2 signals available): source_confidence (renorm 0.5455) + persona_breadth (renorm 0.4545)

### Tie-Breaking

When composite scores are equal, subdomains are sorted alphabetically by name (deterministic).

---

## 14. Persona Affinity Deep Dive

**File**: `core/topic_discovery/scoring.py`

### Two Affinity Signals

#### Signal 1: Source B Provenance (weight 0.6)

Did Source B's persona-brainstorm surface this subdomain for this persona?

- The LLM outputs `source_personas: ["David Chen", ...]` per subdomain
- `_resolve_persona_ids()` fuzzy-matches these to persona IDs
- After dedup, persona_ids are merged across absorbed candidates
- `source_b_persona_map` maps `{subdomain_name_lower: [persona_ids]}`
- Binary signal: 1.0 if persona found, 0.0 if not

#### Signal 2: Embedding Similarity (weight 0.4)

Cosine similarity between persona profile embedding and subdomain description embedding.

- Uses first 500 words of persona profile to avoid length domination
- Returns 0.0 if either embedding is unavailable
- **Currently**: Embeddings are not pre-computed in Phase 2.5, so this signal defaults to 0.0. Affinity relies entirely on Source B provenance.

### Affinity Formula

```
affinity = 0.6 x provenance_signal + 0.4 x embedding_signal
```

### Provenance Labels

| Label | Condition |
|-------|-----------|
| `"both"` | provenance > 0 AND embedding > 0.3 |
| `"source_b"` | provenance > 0 |
| `"embedding"` | otherwise |

### Data Flow for Persona Resolution

```
Persona Manifest (audience_personas/{slug}/_manifest.json)
  |
  +- persona_entries: [(persona_id, persona_name), ...]
  |     e.g., [("david", "David Chen, CFO")]
  |
  +- persona_name_to_id: {"David Chen, CFO": "david"}
       |
       v
Source B LLM Prompt (includes persona profiles as markdown)
  |
  +- LLM outputs: {"source_personas": ["David Chen"], ...} per subdomain
       |
       v
_resolve_persona_ids(["David Chen"], {"David Chen, CFO": "david"})
  |  -> tries exact -> case-insensitive -> substring match
  +- returns: ["david"]
       |
       v
SubdomainCandidate.persona_ids = ["david"]
       |
       v
Dedup merges persona_ids from absorbed candidates
       |
       v
source_b_persona_map = {"cap table management": ["david"]}
       |
       v
compute_persona_affinity_index()
  |  -> for persona "david", subdomain "Cap Table Management":
  |     prov_signal = 1.0 (found in map)
  |     emb_signal = 0.0 (no embeddings)
  |     affinity = 0.6 x 1.0 + 0.4 x 0.0 = 0.6
  +- PersonaSubdomainEntry(affinity_score=0.6, provenance="source_b")
```

---

## 15. API Endpoints

**Router prefix**: `/api/v1/topic-discovery`

### Pipeline Control

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/start` | member/superuser | Start Pipeline A (returns 202 + run_id) |
| `POST` | `/expand` | member/superuser | Start Pipeline B with subdomain_ids (returns 202 + run_id) |
| `GET` | `/{run_id}/status` | any auth | Get task status, current step, approval payload |

### HITL Approvals

| Method | Path | Auth | HITL Stage | Pipeline |
|--------|------|------|------------|----------|
| `POST` | `/{run_id}/approve/taxonomy` | member/superuser | HITL-1 | A |
| `POST` | `/{run_id}/approve/matrix` | member/superuser | HITL-2 | B |
| `POST` | `/{run_id}/approve/subdomains` | member/superuser | DEPRECATED | -- |

> **Note**: `approve/subdomains` (HITL-1.5) is deprecated. Subdomain selection is now handled by the `/expand` endpoint's `subdomain_ids` parameter.

### Data Reads

| Method | Path | Auth | Returns |
|--------|------|------|---------|
| `GET` | `/{slug}/taxonomy` | any auth | Latest taxonomy tree |
| `GET` | `/{slug}/matrix` | any auth | Latest assignment matrix |
| `GET` | `/{slug}/scored-subdomains` | any auth | Scored + ranked subdomain list |
| `GET` | `/{slug}/personas` | any auth | Persona affinity index (optional `?persona_id=`) |
| `GET` | `/{slug}/expansion-status` | any auth | Which subdomains are expanded vs available |

### Pipeline A Start Request Body

```json
{
  "company_name": "Carta",
  "domain": "carta.com",
  "product_slug": null,
  "auto_approve_checkpoints": [1],
  "max_expansion_rounds": 4,
  "dedup_threshold": 0.85,
  "force_rerun": false,
  "language": "en",
  "region": "us"
}
```

- `auto_approve_checkpoints`: `[1]` = auto-approve taxonomy (only checkpoint relevant for Pipeline A)
- `force_rerun`: Override guard that prevents re-running completed discoveries

### Pipeline B Expand Request Body

```json
{
  "company_name": "Carta",
  "domain": "carta.com",
  "product_slug": null,
  "subdomain_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "persona_filter": null,
  "taxonomy_version": null,
  "auto_approve_checkpoints": [2]
}
```

- `subdomain_ids`: Required, non-empty list of subdomain IDs from the taxonomy to expand
- `taxonomy_version`: Optional, defaults to latest version from manifest
- `auto_approve_checkpoints`: `[2]` = auto-approve matrix (only valid checkpoint for Pipeline B)
- `persona_filter`: Optional persona_id to focus expansion

### Expansion Status Response

```json
{
  "slug": "carta",
  "effective_slug": "carta",
  "total_subdomains": 45,
  "expanded": 10,
  "not_expanded": 35,
  "expanded_ids": ["uuid-1", "uuid-2", ...],
  "available_for_expansion": [
    {"id": "uuid-3", "name": "Cap Table Management", "priority_score": 0.92, "expansion_status": "not_expanded"},
    {"id": "uuid-4", "name": "Equity Compensation", "priority_score": 0.88, "expansion_status": "not_expanded"}
  ]
}
```

`available_for_expansion` is sorted by `priority_score` descending -- pick the top entries for the next expansion call.

### Guard Behavior

If a completed discovery already exists (taxonomy + matrix both approved), the `/start` endpoint returns `200` with `already_exists: true` instead of starting a new run. Pass `force_rerun: true` to override.

The `/expand` endpoint requires `manifest.taxonomy_version > 0` (returns 409 if Pipeline A hasn't completed).

---

## 16. Data Models

### Core Enums

```python
class BuyerStage(str, Enum):
    tofu = "tofu"       # Top of funnel -- awareness
    mofu = "mofu"       # Middle -- consideration
    bofu = "bofu"       # Bottom -- decision

class IntentType(str, Enum):
    informational = "informational"
    commercial = "commercial"
    navigational = "navigational"
    transactional = "transactional"

class TDSource(str, Enum):
    source_a = "source_a"   # Company brainstorm
    source_b = "source_b"   # Persona brainstorm
    source_c = "source_c"   # Competitor sitemaps
    source_d = "source_d"   # Adversarial

class TopicDiscoveryStatus(str, Enum):
    draft = "draft"
    hitl_pending = "hitl_pending"
    discovery_complete = "discovery_complete"  # Pipeline A done, ready for expansion
    approved = "approved"                      # Pipeline B done, matrix produced
    archived = "archived"
```

### Key Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `SubdomainCandidate` | Raw candidate from a source | name, description, source, confidence, persona_ids, pain_points |
| `SourceResult` | Aggregated per-source output | source, candidates[], chao1, sample_coverage, error |
| `SubdomainNode` | Tree node in taxonomy | id, name, depth, source_provenance, priority_score, persona_affinity, expansion_status, children[] |
| `TaxonomyTree` | Complete taxonomy | root_nodes[], coverage_score, total_subdomains, max_depth |
| `SubdomainScore` | Scored subdomain | subdomain_id, composite_score, signal_scores, rank |
| `ScoredSubdomainList` | Ranked list | scores[], weights_config |
| `PersonaSubdomainEntry` | One (persona, subdomain) pair | subdomain_id, affinity_score, provenance |
| `PersonaAffinityIndex` | Per-persona index | persona_entries: {pid: [entries]} |
| `TopicAssignment` | Single content opportunity | subdomain_id, topic_text, buyer_stage, intent_type, persona_id, priority_score |
| `TopicAssignmentMatrix` | Full matrix | assignments[], distributions |
| `TopicDiscoveryManifest` | Artifact metadata | slug, versions, status, discovery_completed_at, expanded_subdomain_ids |
| `TopicDiscoveryInput` | Pipeline A input | company_name, domain, auto_approve_checkpoints, max_expansion_rounds, dedup_threshold |
| `TopicDiscoveryOutput` | Pipeline A output | taxonomy, coverage, scored_subdomains, persona_affinity (matrix=None) |
| `TopicExpansionInput` | Pipeline B input | company_name, domain, subdomain_ids, taxonomy_version, auto_approve_checkpoints |
| `TopicExpansionOutput` | Pipeline B output | matrix, matrix_version, subdomains_expanded, subdomains_failed |

All Pydantic models use defaults on every field for backward compatibility with existing JSON artifacts.

---

## 17. Storage Layout

```
artifacts/topic_discovery/{effective_slug}/
+-- _manifest.json                    # Top-level metadata
+-- taxonomy/
|   +-- v1.json                       # First taxonomy version
|   +-- v2.json                       # After HITL-1 edits
|   +-- v7.json                       # After scoring backfill
+-- matrix/
|   +-- v1.json                       # First expansion (Pipeline B call 1)
|   +-- v2.json                       # Second expansion (Pipeline B call 2)
+-- scoring/
|   +-- v1.json                       # Subdomain scores
+-- persona_affinity/
|   +-- v1.json                       # Persona-subdomain affinity index
+-- raw/
    +-- source_a_v1.json              # Source A candidates
    +-- source_b_v1.json              # Source B candidates (with persona_ids)
    +-- source_c_v1.json              # Source C candidates
    +-- source_d_v1.json              # Source D candidates
    +-- coverage_v1.json              # Coverage metrics
```

### Version Semantics

- `write_taxonomy(tree, version=0)` -> auto-increments: finds latest version + 1
- `write_taxonomy(tree, version=7)` -> overwrites v7 (used for backfill re-persist)
- `write_matrix(matrix, version=0)` -> auto-increments: each Pipeline B call creates a new version
- Manifest stores the current version number for each artifact type

### Atomicity

Version files are written atomically (tempfile + `os.replace()`). Manifest is updated last. If a write fails mid-way, the manifest still points to the last valid version.

### Manifest Fields

```json
{
  "slug": "carta",
  "effective_slug": "carta",
  "company_name": "Carta",
  "domain_name": "carta.com",
  "status": "discovery_complete",
  "taxonomy_version": 7,
  "matrix_version": 0,
  "scoring_version": 1,
  "persona_affinity_version": 1,
  "created_at": "2026-03-12T10:00:00Z",
  "last_updated": "2026-03-12T10:05:00Z",
  "discovery_completed_at": "2026-03-12T10:05:00Z",
  "last_expansion_task_id": null,
  "expanded_subdomain_ids": [],
  "source_results_written": ["source_a", "source_b", "source_c", "source_d"]
}
```

After Pipeline B completes:

```json
{
  "status": "approved",
  "matrix_version": 1,
  "last_expansion_task_id": "task-uuid-123",
  "expanded_subdomain_ids": ["sd-uuid-1", "sd-uuid-2", "sd-uuid-3"]
}
```

---

## 18. Configuration

**File**: `core/config/settings.py` -- environment variables with defaults.

| Setting | Default | Description |
|---------|---------|-------------|
| `TOPIC_DISCOVERY_BRAINSTORM_MODEL` | `anthropic/claude-sonnet-4-6` | LLM for S1 brainstorm agents |
| `TOPIC_DISCOVERY_DEDUP_MODEL` | `anthropic/claude-haiku-4-5-20251001` | LLM for deduplication |
| `TOPIC_DISCOVERY_MAX_EXPANSION_ROUNDS` | `4` | Max iterative brainstorm rounds per source |
| `TOPIC_DISCOVERY_DEDUP_THRESHOLD` | `0.85` | Embedding similarity threshold for dedup |
| `TOPIC_DISCOVERY_MAX_CONCURRENT_SOURCES` | `4` | Semaphore limit for concurrent expansion |
| `TOPIC_DISCOVERY_SOURCE_TIMEOUT_S` | `120.0` | Timeout for S1 source agents |
| `TOPIC_DISCOVERY_EXPANSION_TIMEOUT_S` | `300.0` | Timeout for S3 expansion (5 min) |
| `TOPIC_DISCOVERY_SCORING_WEIGHTS` | JSON string | Signal weights for subdomain scoring |
| `TOPIC_DISCOVERY_SCORING_SIMILARITY_THRESHOLD` | `0.60` | Cosine similarity threshold for scoring signals |
| `TOPIC_DISCOVERY_PERSONA_AFFINITY_WEIGHTS` | `{"provenance": 0.6, "embedding": 0.4}` | Persona affinity signal weights |
| `TOPIC_DISCOVERY_MAX_SUBDOMAINS_TO_EXPAND` | `20` | Cost cap on expansion per Pipeline B call |

---

## 19. CLI Tools

### Full Pipeline Run

```bash
# Pipeline A (Discovery):
curl -X POST http://localhost:8000/api/v1/topic-discovery/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Carta", "domain": "carta.com", "auto_approve_checkpoints": [1]}'

# Pipeline B (Expansion) -- after Pipeline A completes:
curl -X POST http://localhost:8000/api/v1/topic-discovery/expand \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Carta", "domain": "carta.com", "subdomain_ids": ["id1", "id2"], "auto_approve_checkpoints": [2]}'

# Check expansion status:
curl http://localhost:8000/api/v1/topic-discovery/carta/expansion-status \
  -H "Authorization: Bearer <token>"
```

### Re-score from Existing Artifacts

```bash
# Scoring only (zero LLM calls, instant):
python scripts/run_td_rescore.py --slug carta

# Score + expand top 5 subdomains:
python scripts/run_td_rescore.py --slug carta --expand --top-n 5

# Score + expand specific subdomains by ID:
python scripts/run_td_rescore.py --slug carta --expand --ids <id1>,<id2>,<id3>

# With persona filter:
python scripts/run_td_rescore.py --slug carta --expand --top-n 5 --persona david

# Product-level:
python scripts/run_td_rescore.py --slug carta__equity --company-slug carta --expand --top-n 3
```

---

## 20. File Reference

### Core Module (`core/topic_discovery/`)

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline.py` | ~1100 | Pipeline A (`run_topic_discovery_pipeline`) + Pipeline B (`run_topic_expansion_pipeline`) |
| `agents.py` | ~1500 | LLM agent functions (S1 sources, dedup, hierarchy, expansion) + statistical functions |
| `graph.py` | ~690 | 3 LangGraph HITL sub-graphs + interrupt/resume helper. HITL-1.5 graph deprecated. |
| `scoring.py` | ~415 | Algorithmic scoring (5 signals) + persona affinity + topic priority |
| `storage.py` | ~393 | Filesystem storage (versioned read/write for all artifact types) |
| `persistence.py` | ~373 | DB persistence hooks (fire-and-forget) |
| `prompts/` | 8 files | LLM prompt templates (system + user builders) |

### API Layer

| File | Purpose |
|------|---------|
| `api/routers/topic_discovery.py` | 11 REST endpoints (incl. `/expand` and `/expansion-status`) |
| `api/schemas/topic_discovery.py` | Request/response Pydantic schemas (incl. `TopicExpansionStartRequest`, `ExpansionStatusResponse`) |
| `api/tasks/models.py` | `PipelineTask` with `topic_expansion` pipeline type |
| `api/tasks/runner.py` | Task wrappers (`run_topic_discovery_pipeline_task`, `run_topic_expansion_pipeline_task`) |

### Services

| File | Purpose |
|------|---------|
| `core/services/topic_discovery_data.py` | `TopicDiscoveryDataServiceProtocol` |
| `core/services/json_topic_discovery_data.py` | JSON filesystem implementation |

### Models & Config

| File | Purpose |
|------|---------|
| `core/models/topic_discovery.py` | All Pydantic models (~25 classes incl. `TopicExpansionInput`, `TopicExpansionOutput`) |
| `core/config/settings.py` | 12 TD-specific settings |

### Tests

| File | Coverage |
|------|----------|
| `tests/topic_discovery/test_pipeline_td.py` | Pipeline A flow (28 tests) |
| `tests/topic_discovery/test_expansion_pipeline_td.py` | Pipeline B flow (15 tests) |
| `tests/topic_discovery/test_models_td.py` | Model serialization |
| `tests/topic_discovery/test_scoring_td.py` | Scoring engine |
| `tests/topic_discovery/test_expansion_td.py` | Expansion agent |
| `tests/topic_discovery/test_storage_td.py` | Storage + versioning |
| `tests/topic_discovery/test_graph_subdomain_selection.py` | HITL-1.5 graph (deprecated, kept for compat) |
| `tests/api/test_topic_discovery.py` | API endpoints (87 tests) |

### CLI

| File | Purpose |
|------|---------|
| `scripts/run_td_rescore.py` | Re-run scoring + optional expansion from existing artifacts |
