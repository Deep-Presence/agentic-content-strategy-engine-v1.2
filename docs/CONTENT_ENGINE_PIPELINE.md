# Content Generation Engine (Pipeline 3) — Complete Technical Documentation

> **Document Date:** 2026-02-20
> **Author:** Auto-generated from codebase analysis
> **Pipeline Version:** v1.0 (with v2.0 structural intelligence enhancements)
> **Total Codebase:** ~3,500 lines across 25 files

---

## Table of Contents

1. [Overview](#1-overview)
2. [Inputs — What the Pipeline Consumes](#2-inputs--what-the-pipeline-consumes)
   - [Entry Point & CLI](#21-entry-point--cli)
   - [Input Model](#22-input-model)
   - [The Five Input Artifacts](#23-the-five-input-artifacts)
   - [How Inputs Are Loaded](#24-how-inputs-are-loaded)
   - [Gap Slug Auto-Discovery](#25-gap-slug-auto-discovery)
3. [Pipeline Orchestrator](#3-pipeline-orchestrator)
   - [Main Function](#31-main-function)
   - [Orchestration Flow](#32-orchestration-flow)
   - [Stage Skipping](#33-stage-skipping)
   - [CLI Progress Output](#34-cli-progress-output)
4. [Stage 1 — Strategic Planner](#4-stage-1--strategic-planner)
   - [What It Does](#41-what-it-does)
   - [Model & Parameters](#42-model--parameters)
   - [System Prompt](#43-system-prompt)
   - [User Prompt Construction](#44-user-prompt-construction)
   - [Output — ContentBrief](#45-output--contentbrief)
   - [StructuralTargets (22 Fields)](#46-structuraltargets-22-fields)
   - [ExemplarSummary](#47-exemplarsummary)
   - [Persistence](#48-persistence)
5. [Stage 2 — Content Workers](#5-stage-2--content-workers)
   - [Dispatcher — Parallel Orchestration](#51-dispatcher--parallel-orchestration)
   - [Worker Chain](#52-worker-chain-per-brief)
   - [Step 1: Outliner](#53-step-1-outliner)
   - [Step 2: Drafter](#54-step-2-drafter)
   - [Step 3: Fact Enricher](#55-step-3-fact-enricher)
   - [Step 4: Formatter](#56-step-4-formatter)
6. [Stage 3 — Evaluator Loop](#6-stage-3--evaluator-loop)
   - [Loop Logic](#61-loop-logic)
   - [Dimension 1: Structural Evaluator](#62-dimension-1-structural-evaluator-sync-no-llm)
   - [Dimension 2: Semantic Evaluator](#63-dimension-2-semantic-evaluator-async)
   - [Dimension 3: Style Judge](#64-dimension-3-style-judge-async-llm)
   - [Dimension 4: Factual Judge](#65-dimension-4-factual-judge-async-llm)
   - [Revision Cycle](#66-revision-cycle)
   - [Output](#67-output)
7. [Stage 4 — Human Review (HITL)](#7-stage-4--human-review-hitl)
   - [LangGraph State Machine](#71-langgraph-state-machine)
   - [Node Functions](#72-node-functions)
   - [Output](#73-output)
8. [Prompt Management](#8-prompt-management)
9. [Tracing & Observability](#9-tracing--observability)
10. [Utilities](#10-utilities)
11. [Model & Token Limits Summary](#11-model--token-limits-summary)
12. [Artifact Directory Structure](#12-artifact-directory-structure-output)
13. [Configuration](#13-configuration)
14. [Test Coverage](#14-test-coverage)
15. [Key Design Decisions](#15-key-design-decisions)
16. [Data Flow Diagram](#16-data-flow-diagram)
17. [File Manifest](#17-file-manifest)

---

## 1. Overview

The Content Generation Engine is **Pipeline 3** of the Deep Presence system. It consumes the outputs of Pipeline 1 (Research Artifacts) and Pipeline 2 (Gap Analysis) and automatically generates content pieces optimized for AI search engine citation (Perplexity, ChatGPT, Claude, Gemini).

It is a **4-stage async pipeline**:

```
[1/4] Strategic Planner   -> Reads gap analysis + research artifacts, produces content briefs
[2/4] Content Workers     -> Parallel: Outline -> Draft -> Fact-Enrich -> Format (per brief)
[3/4] Evaluator Loop      -> 4-dimension quality gate with revision cycles
[4/4] Human Review (HITL) -> LangGraph state machine: approve / edit / reject
```

### Architecture Patterns Used

| Pattern | Where Applied |
|---------|---------------|
| **Orchestrator-Workers** (Anthropic) | Stage 2 — parallel content production with semaphore concurrency |
| **Evaluator-Optimizer** (Anthropic) | Stage 3 — 4-dimension quality gate with revision loops |
| **HITL State Machine** (LangGraph) | Stage 4 — `interrupt()` for human approval with approve/edit/reject |
| **Raw SDK Clients** | All LLM calls — no LangChain wrappers, direct `AsyncAnthropic` and Perplexity |

---

## 2. Inputs — What the Pipeline Consumes

### 2.1 Entry Point & CLI

**File**: `scripts/run_content_engine.py`

```bash
python scripts/run_content_engine.py \
  --company-name "Carta" --domain carta.com \
  --company-context-path artifacts/company_context/carta.md \
  --persona-path artifacts/personas/carta__persona-icp.md \
  --persona-path artifacts/personas/carta__persona-2.md \
  --style-guide-path artifacts/style_guides/carta.md \
  --gap-slug carta \
  --max-briefs 5 --max-workers 3 --max-revisions 2 \
  --auto-approve
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--company-name` | Yes | — | Company name |
| `--domain` | Yes | — | Company domain (e.g., `carta.com`) |
| `--company-context-path` | No | None | Path to company context `.md` |
| `--persona-path` | No | [] | Path to persona `.md` (repeatable) |
| `--style-guide-path` | No | None | Path to style guide `.md` |
| `--gap-slug` | No | None | Auto-discovers `gap_report.json`, `generation_spec.json`, `analysis.json` |
| `--gap-report-json-path` | No | None | Explicit path to gap report JSON |
| `--generation-spec-json-path` | No | None | Explicit path to generation spec JSON |
| `--analysis-json-path` | No | None | Explicit path to analysis JSON |
| `--max-briefs` | No | 10 | Max content briefs to generate |
| `--max-workers` | No | 3 | Max concurrent worker chains |
| `--max-revisions` | No | 2 | Max revision cycles per brief |
| `--auto-approve` | No | False | Skip HITL review, auto-approve all |
| `--skip-stage` | No | [] | Skip stage number 1-4 (repeatable) |

### 2.2 Input Model

**File**: `core/models/content_generation.py` — lines 22-37

```python
class ContentGenerationInput(BaseModel):
    company_name: str                                        # Required
    domain: str                                              # Required
    company_context_path: Optional[str] = None               # artifacts/company_context/{slug}.md
    persona_paths: List[str] = Field(default_factory=list)   # [artifacts/personas/{slug}__persona-*.md]
    style_guide_path: Optional[str] = None                   # artifacts/style_guides/{slug}.md
    gap_report_json_path: Optional[str] = None               # artifacts/gap_analysis/{slug}/gap_report.json
    generation_spec_json_path: Optional[str] = None          # artifacts/gap_analysis/{slug}/generation_spec.json
    analysis_json_path: Optional[str] = None                 # artifacts/gap_analysis/{slug}/analysis.json
    max_briefs: int = 10                                     # Max content pieces to generate
    max_concurrent_workers: int = 3                          # Semaphore concurrency limit
    max_revision_cycles: int = 2                             # Max eval->revise loops per brief
    auto_approve: bool = False                               # Skip HITL review
    skip_stages: List[int] = Field(default_factory=list)     # [1,2,3,4] — skip individual stages
```

### 2.3 The Five Input Artifacts

The pipeline consumes **5 artifact types** — 3 Markdown + 3 JSON — produced by Pipelines 1 and 2:

#### Artifact 1: Company Context (Markdown)

| Property | Value |
|----------|-------|
| **Source** | Pipeline 1 — Research Artifacts, Stage 1 |
| **Location** | `artifacts/company_context/{slug}.md` |
| **Format** | Markdown |
| **Loaded by** | `_load_artifact_md(input_data.company_context_path)` |

**Content covered**:
- Company origin story and mission
- Products and services
- Market positioning and differentiators
- Target audience and ideal customer profile
- Competitors and competitive landscape
- Growth drivers and revenue model
- Bottlenecks and challenges
- Strategic goals and priorities
- Key risks and market headwinds

#### Artifact 2: Persona Profiles (Markdown, 1-3 files)

| Property | Value |
|----------|-------|
| **Source** | Pipeline 1 — Research Artifacts, Stage 2 |
| **Location** | `artifacts/personas/{slug}__persona-{icp\|2\|3}.md` |
| **Format** | Markdown |
| **Loaded by** | `[_load_artifact_md(p) for p in input_data.persona_paths]` |

**Content covered (per persona)**:
- Persona name and role/title
- Summary description
- Day-in-the-life narrative
- Pain points and frustrations
- Buying triggers (what makes them evaluate solutions)
- Trust builders (what content earns their confidence)
- Messaging angles (how to speak to them)
- Sample quotes and objections

#### Artifact 3: Writing Style Guide (Markdown)

| Property | Value |
|----------|-------|
| **Source** | Pipeline 1 — Research Artifacts, Stage 3 |
| **Location** | `artifacts/style_guides/{slug}.md` |
| **Format** | Markdown |
| **Loaded by** | `_load_artifact_md(input_data.style_guide_path)` |

**Content covered**:
- Voice and tone descriptors (e.g., "conversational but authoritative")
- Channel-specific variations (blog vs. help center vs. landing page)
- Sentence patterns and length guidelines
- Jargon rules (required terms, avoided terms, product name conventions)
- Audience resonance notes
- Product positioning language
- Do's and don'ts
- Formatting conventions (heading case, list style, citation format, number formatting)

#### Artifact 4: Gap Report (JSON)

| Property | Value |
|----------|-------|
| **Source** | Pipeline 2 — Gap Analysis, Step 8 |
| **Location** | `artifacts/gap_analysis/{slug}/gap_report.json` |
| **Format** | JSON |
| **Loaded by** | `_load_artifact_json(input_data.gap_report_json_path)` |

**Content covered**:
- Executive summary of citation gaps
- Proximity statistics (avg company similarity vs. avg citation similarity)
- 5-10 content recommendations with:
  - Suggested title ideas
  - Target query clusters
  - Structural guidance (format, length, elements)
  - Priority level

#### Artifact 5: Generation Spec (JSON)

| Property | Value |
|----------|-------|
| **Source** | Pipeline 2 — Gap Analysis, Step 8 |
| **Location** | `artifacts/gap_analysis/{slug}/generation_spec.json` |
| **Format** | JSON |
| **Loaded by** | `_load_artifact_json(input_data.generation_spec_json_path)` |

**Content covered — array of 8-9 cluster specs, each containing**:

```json
{
  "cluster_name": "Mechanism",
  "query_count": 8,
  "word_count_range": [39, 9517],
  "min_similarity_threshold": 0.5975,
  "required_elements": ["headers", "lists", "citations"],
  "structural_rates": {
    "headers": 0.9,
    "lists": 0.8,
    "stats": 0.62,
    "citations": 0.96
  },
  "authority_signals": {
    "nonprofit": 2,
    "commercial_or_media": 167
  },
  "total_citations_analyzed": 169,
  "faq_rate": 0.32,
  "table_rate": 0.21,
  "avg_word_count": 1739.5,
  "avg_paragraph_word_count": 29.2,
  "avg_sentence_count_per_paragraph": 1.8,
  "min_bullets_per_list": 2,
  "dominant_content_type": "blog_or_article",
  "dominant_authority_type": "commercial_or_media",
  "exemplar_themes": ["build", "cms", "code", "content", "design"]
}
```

#### Artifact 6: Analysis (JSON) — The Most Critical Input

| Property | Value |
|----------|-------|
| **Source** | Pipeline 2 — Gap Analysis, Step 6 |
| **Location** | `artifacts/gap_analysis/{slug}/analysis.json` |
| **Format** | JSON |
| **Loaded by** | `_load_artifact_json(input_data.analysis_json_path)` |

**Content covered**:

- **`gaps[]` array** (100+ entries): The core priority engine. Each gap object contains:
  - `query_id`, `query_text`: The search query to optimize for
  - `cluster_name`: Which of the 9 clusters this query belongs to
  - `gap`: The gap metric (`avg_citation_similarity - best_company_similarity`). **Larger gap = higher priority.**
  - `best_company_similarity`: How close the company's existing content is to this query
  - `avg_citation_similarity`: How close AI-cited content is to this query
  - `top_cited_exemplars[]`: Array of URLs that AI search engines actually cite, each with 40+ `structural_signals`:
    - Text composition: `word_count`, `paragraph_count`, `sentence_count`, `reading_level`
    - Structural elements: `header_count` (by level), `table_count`, `ordered_list_count`, `unordered_list_count`, `code_block_count`, `definition_list_count`
    - Content patterns: `has_faq_section`, `has_step_by_step`, `has_comparison_table`, `has_statistics_section`
    - Factual density: `data_point_count`, `citation_density`, `named_entity_density`
    - Authority: `authority_type`, `content_type`

- **`cluster_specs[]`**: Per-cluster structural rates and authority distributions
- **`proximity_stats`**: SPA results and query centroids

### 2.4 How Inputs Are Loaded

**File**: `core/content_engine/pipeline.py` — lines 115-134

```python
def _load_artifact_md(path: Optional[str]) -> str:
    """Load markdown artifact. Returns empty string if not found."""
    if not path:
        return ""
    p = Path(path) if Path(path).is_absolute() else _PROJECT_ROOT / path.lstrip("/")
    if p.exists():
        return p.read_text(encoding="utf-8")
    logger.warning("Artifact not found: %s", p)
    return ""

def _load_artifact_json(path: Optional[str]) -> dict:
    """Load JSON artifact. Returns empty dict if not found."""
    if not path:
        return {}
    p = Path(path) if Path(path).is_absolute() else _PROJECT_ROOT / path.lstrip("/")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    logger.warning("Artifact not found: %s", p)
    return {}
```

**Key behaviors**:
- Resolves relative paths against `_PROJECT_ROOT` (content-strategy-engine/)
- Returns empty string/dict if file not found (graceful degradation)
- **No transformation on load** — markdown returned as raw string, JSON as parsed dict
- The LLM does all semantic synthesis in the planner prompt

Loading happens at pipeline.py lines 172-178:
```python
company_context_md = _load_artifact_md(input_data.company_context_path)
style_guide_md = _load_artifact_md(input_data.style_guide_path)
persona_mds = [_load_artifact_md(p) for p in input_data.persona_paths]
gap_report_json = _load_artifact_json(input_data.gap_report_json_path)
generation_spec_json = _load_artifact_json(input_data.generation_spec_json_path)
analysis_json = _load_artifact_json(input_data.analysis_json_path)
```

### 2.5 Gap Slug Auto-Discovery

**File**: `scripts/run_content_engine.py` — lines 86-106

When `--gap-slug carta` is provided, `_resolve_gap_artifacts()` looks for:

```
artifacts/gap_analysis/carta/
  ├── gap_report.json       -> --gap-report-json-path
  ├── generation_spec.json  -> --generation-spec-json-path
  └── analysis.json         -> --analysis-json-path
```

Only resolves paths that weren't already explicitly provided via flags.

---

## 3. Pipeline Orchestrator

**File**: `core/content_engine/pipeline.py` — 436 lines

### 3.1 Main Function

```python
async def run_content_generation(
    input_data: ContentGenerationInput,
) -> ContentGenerationOutput:
```

### 3.2 Orchestration Flow

```
1. Compute slug from company_name
2. Create artifact directory: artifacts/content/{slug}/
3. Create Langfuse session + pipeline trace
4. Load all 5 input artifacts
5. [Stage 1] Strategic Planner -> PlannerOutput (briefs)
6. Persist briefs.json
7. [Stage 2] Content Workers -> List[FormattedContent]
8. [Stage 3] Evaluator Loop -> List[RevisionHistory] (+ updated FormattedContent)
9. Persist eval_history.json per brief
10. [Stage 4] Human Review -> List[ContentPiece]
11. Persist run_metadata.json
12. Flush Langfuse events
13. Return ContentGenerationOutput
```

### 3.3 Stage Skipping

Each stage can be independently skipped via `skip_stages`:

| Stage Skipped | Behavior |
|---------------|----------|
| 1 | Loads `briefs.json` from previous run. Raises `RuntimeError` if not found. |
| 2 | Loads `formatted.md` per brief from disk. Recomputes structural counts via `_count_structural_elements()`. |
| 3 | Passes through with `RevisionHistory(final_passed=True)` for each content piece. Also skipped if `max_revision_cycles=0`. |
| 4 | Auto-approves all content pieces, writes `final.md` to disk. Also auto-approves if `auto_approve=True`. |

### 3.4 CLI Progress Output

```
----------------------------------------------------
  Content Generation Pipeline -- carta
----------------------------------------------------

  [1/4] Strategic Planner .............. 12.3s (5 briefs)
         Worker #1: Outlining "How Carta Simplifies Cap Table..."
         Worker #1: Drafting "How Carta Simplifies Cap Table..."
         Worker #1: Enriching "How Carta Simplifies Cap Table..."
         Worker #1: Formatting "How Carta Simplifies Cap Table..."
         Worker #1: DONE (1,847 words, 9 headers, 6 citations)
         Worker #2: Outlining "Carta vs Pulley: ..."
         ...
         Workers complete: 5/5 briefs
  [2/4] Content Workers ................ 2m 15.3s (5/5 briefs)
         Evaluating brief-1/5: "How Carta Simplifies..."
         brief-001: Structural PASSED (0.82), Semantic PASSED (0.71), Style PASSED (0.78), Factual PASSED (0.73)
         brief-001: ALL PASSED (overall: 0.76)
         ...
  [3/4] Evaluator Loop ................. 1m 42.1s (4/5 passed)
  [4/4] Human Review ................... 0.1s (auto-approved)

----------------------------------------------------
  Done -- 4m 9.8s total | 5 approved, 0 rejected
----------------------------------------------------
```

---

## 4. Stage 1 — Strategic Planner

**Files**: `core/content_engine/planner.py` (180 lines), `core/content_engine/prompts/planner_prompts.py` (302 lines)

### 4.1 What It Does

A single LLM call that reads all input artifacts and produces prioritized `ContentBrief` objects — one per content piece to generate. The planner is the intelligence layer that decides **what** to write, **how** to structure it, and **which gaps** to fill first.

### 4.2 Model & Parameters

| Setting | Value |
|---------|-------|
| Model | `claude-opus-4-6` (configurable via `settings.content_engine_planner_model`) |
| Max output tokens | 16,384 |
| Max input tokens | ~150,000 (context window guard via `truncate_to_token_limit()`) |
| Retry | 3 retries with jittered exponential backoff |
| Client | `AsyncAnthropic(api_key=settings.anthropic_api_key)` |

### 4.3 System Prompt

**Constant**: `PLANNER_SYSTEM_PROMPT` in `core/content_engine/prompts/planner_prompts.py` (lines 10-147)

The system prompt covers:

1. **Role**: "Strategic content planner for B2B SaaS companies optimizing for AI search citation"

2. **Output Format**: Strict JSON schema defining:
   - `briefs[]` array with all ContentBrief fields
   - `planning_metadata` with totals and model info

3. **Structural Intelligence Guidelines** (7 rules):
   - Derive `structural_targets` from cluster-level rates and exemplar analysis
   - Paragraph targets: AI engines cite self-contained paragraphs of 50-150 words
   - Authority type from cluster's `authority_signals` distribution
   - FAQ/table/definition inclusion when rate > 30%
   - Self-contained claims formula: `max(5, ceil(word_count_range[0] / 200))`
   - Top 3-5 exemplar summaries per brief with structural fingerprints
   - 2-4 exemplar themes (common patterns across cited content)

4. **Content Strategy Guidelines** (6 rules):
   - Priority scoring from gap metric (gap > 0.3 is critical)
   - Format selection logic (how_to, comparison, short_faq, pillar_page, long_blog)
   - Word count from exemplar median +/-20%
   - Deduplication across similar-gap queries
   - Cluster coverage breadth
   - Exact count = max_briefs

5. **Style Guide Awareness**: Informs format choices and angles but NOT structural targets

### 4.4 User Prompt Construction

**Function**: `build_planner_user_prompt()` in `core/content_engine/prompts/planner_prompts.py` (lines 150-217)

The assembled prompt includes these sections in order:

```
## Company
Name: {company_name}
Domain: {domain}

## Company Context
{full company context markdown}

## Writing Style Guide
{full style guide markdown}

## Persona Profiles
### Persona 1
{persona 1 markdown}
### Persona 2
{persona 2 markdown}
...

## Top Query Gaps (sorted by gap size)
### "query text" (cluster: cluster-name)
Gap: 0.45 | Company sim: 0.21 | Citation sim: 0.66
Top cited exemplars:
  - https://example.com: 2100 words, 9 headers, 14 lists, 7 stats, authority=commercial_or_media
  - ...

## Cluster Content Specs
### Cluster: Problem/Awareness
Word count range: [800, 3000]
Required elements: ["headers", "lists", "citations"]
Structural rates: {"headers": 0.92, "lists": 0.85, ...}
Authority distribution: {"commercial_or_media": 143, "academic": 12, ...}

## Generation Spec (from gap analysis)
```json
{generation_spec_json}
```

## Gap Report Summary
```json
{gap_report_json}
```

## Instructions
Produce exactly {max_briefs} content briefs as JSON. Prioritize the largest gaps first.
Ensure briefs cover different clusters for maximum coverage breadth.
```

The `_build_gaps_summary()` helper extracts the top 50 gaps (sorted by gap size) and all cluster specs from `analysis.json`.

### 4.5 Output — ContentBrief

**Model**: `core/models/content_generation.py` — lines 113-140

```python
class ContentBrief(BaseModel):
    brief_id: str                          # "brief-001"
    title: str                             # "How Carta Simplifies Cap Table Management"
    target_queries: List[TargetQuery]      # Queries to optimize for
    target_cluster: str                    # "Problem/Awareness"
    content_format: Literal[...]           # "long_blog"|"short_faq"|"pillar_page"|"comparison"|"how_to"
    funnel_stage: Literal[...]             # "awareness"|"consideration"|"decision"|"retention"
    channel: Literal[...]                  # "blog"|"help_center"|"landing_page"|"resource_hub"
    priority_score: float                  # 0.0-1.0 (from gap metric)
    word_count_range: Tuple[int, int]      # (1200, 2000)
    structural_targets: StructuralTargets  # 22-field structural blueprint
    required_structural_elements: List[str] # ["headers", "lists", "citations", "statistics"]
    key_topics: List[str]                  # ["cap table management", "equity tracking"]
    key_angles: List[str]                  # ["compliance simplification", "409A automation"]
    competitor_exemplars: List[str]        # ["https://competitor.com/article"]
    semantic_threshold: float = 0.65       # For semantic eval pass/fail
    exemplar_summaries: List[ExemplarSummary]  # Top-cited content structural fingerprints
    exemplar_themes: List[str]             # ["step-by-step", "data-heavy", "FAQ-driven"]
```

### 4.6 StructuralTargets (22 Fields)

**Model**: `core/models/content_generation.py` — lines 53-92

```python
class StructuralTargets(BaseModel):
    # --- v1.0 fields (rates + minimums) ---
    header_rate: float = 0.0          # Fraction of cited content with headers
    list_rate: float = 0.0            # Fraction with lists
    stat_rate: float = 0.0            # Fraction with statistics
    citation_rate: float = 0.0        # Fraction with citations
    min_headers: int = 3              # Minimum header count
    min_lists: int = 1                # Minimum list item count
    min_citations: int = 2            # Minimum citation count

    # --- v2.0 paragraph & sentence targets ---
    min_paragraphs: int = 8                          # Minimum paragraph count
    avg_paragraph_word_count: int = 80               # Target avg words per paragraph
    max_paragraph_word_count: int = 150              # Max words per paragraph
    avg_sentence_count_per_paragraph: float = 3.5    # Target sentences per paragraph

    # --- v2.0 granular structural rates ---
    table_rate: float = 0.0           # Fraction of cited content with tables
    definition_rate: float = 0.0      # Fraction with definitions
    faq_rate: float = 0.0             # Fraction with FAQ sections
    code_block_rate: float = 0.0      # Fraction with code blocks

    # --- v2.0 count targets ---
    min_stats: int = 2                    # Minimum statistics/data points
    min_self_contained_claims: int = 5    # Minimum independently-citable paragraphs
    min_bullets_per_list: int = 3         # Minimum items per list block

    # --- v2.0 authority / content intelligence ---
    dominant_authority_type: Optional[str] = None   # e.g., "commercial_or_media"
    dominant_content_type: Optional[str] = None     # e.g., "blog_or_article"
    avg_word_count: int = 0                         # Avg word count of cited content
```

### 4.7 ExemplarSummary

**Model**: `core/models/content_generation.py` — lines 95-110

```python
class ExemplarSummary(BaseModel):
    url: str = ""                  # URL of the cited content
    word_count: int = 0            # Total words
    header_count: int = 0          # Number of headers
    list_item_count: int = 0       # Number of list items
    stat_count: int = 0            # Number of statistics/data points
    citation_count: int = 0        # Number of source citations
    authority_type: str = ""       # "commercial_or_media", "academic", "government", etc.
    content_type: str = ""         # "blog_or_article", "guide", "documentation", etc.
    snippet: str = ""              # First 200 chars of cited content
```

### 4.8 Persistence

Briefs are written to `artifacts/content/{slug}/briefs.json` as:
```python
json.dumps(planner_output.model_dump(mode="json"), indent=2, default=str)
```

---

## 5. Stage 2 — Content Workers

**Files**: `core/content_engine/workers/dispatcher.py` (241 lines), `workers/outliner.py`, `workers/drafter.py`, `workers/fact_enricher.py`, `workers/formatter.py`

### 5.1 Dispatcher — Parallel Orchestration

**Function**: `dispatch_workers()` in `core/content_engine/workers/dispatcher.py` — lines 174-240

```python
async def dispatch_workers(
    briefs: List[ContentBrief],
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    max_concurrent: int = 3,
    *,
    session_id: str = "",
    artifact_dir: Path = Path("."),
    parent_span: Optional[object] = None,
) -> List[FormattedContent]:
```

**Behavior**:
- Creates `asyncio.Semaphore(max_concurrent)` (default 3)
- Launches one `_run_worker_chain()` coroutine per brief
- Uses `asyncio.gather(*tasks, return_exceptions=True)` — **one failing brief does NOT cancel the batch**
- Failed briefs are logged and excluded from results
- Returns only successful `FormattedContent` objects

### 5.2 Worker Chain (per brief)

`_run_worker_chain()` runs 4 sequential steps under the semaphore:

```
ContentBrief
    |
    v
[Step 1: Outliner]  -->  ContentOutline  -->  outline.json
    |
    v
[Step 2: Drafter]   -->  ContentDraft    -->  draft.md
    |
    v
[Step 3: Enricher]  -->  EnrichedDraft   -->  enriched.md
    |
    v
[Step 4: Formatter]  --> FormattedContent --> formatted.md
```

Each intermediate artifact is persisted to `artifacts/content/{slug}/content/{brief_id}/`.

### 5.3 Step 1: Outliner

**Prompt file**: `core/content_engine/prompts/outliner_prompts.py` (212 lines)

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-5-20250929` (via `settings.content_engine_worker_model`) |
| Max output tokens | 4,096 |
| Max input tokens | ~150,000 |

**System prompt** (`OUTLINER_SYSTEM_PROMPT`) key guidelines:
- JSON output matching `ContentOutline` schema
- Per-section `structural_elements` (bullet_list, table, definition, statistics, etc.)
- Per-section `self_contained_claims` count
- Answer-first structure (lead with key info)
- Self-contained paragraphs of 50-150 words
- Structural competitiveness with exemplars
- Conditional FAQ section if `faq_rate > 0.3`
- Conditional table section if `table_rate > 0.3`

**User prompt** (`build_outliner_user_prompt()`) includes:
- Brief metadata (ID, title, format, funnel stage, word count range)
- Target queries with cluster names
- Key topics and key angles
- Full 22-field structural targets (formatted as readable list)
- Top 5 exemplar summaries with structural fingerprints
- Exemplar themes
- Company context

**Output model**:

```python
class ContentOutline(BaseModel):
    brief_id: str
    title: str
    sections: List[OutlineSection]    # List of sections
    total_target_words: int = 1500
    has_faq_section: bool = False     # v2.0
    has_table_section: bool = False   # v2.0
    has_key_takeaways: bool = False   # v2.0

class OutlineSection(BaseModel):
    heading: str
    level: int = 2                    # H2, H3, etc.
    key_points: List[str]
    target_word_count: int = 300
    structural_elements: List[str]    # v2.0 — what to include in this section
    self_contained_claims: int = 0    # v2.0 — how many citable paragraphs
```

### 5.4 Step 2: Drafter

**Prompt file**: `core/content_engine/prompts/drafter_prompts.py` (216 lines)

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-5-20250929` |
| Max output tokens | 8,192 |
| Max input tokens | ~100,000 |

**Two system prompts**:

1. **`DRAFTER_SYSTEM_PROMPT`** (initial drafting):
   - Lead with answers
   - Be specific and quantitative
   - Natural keyword integration
   - Authoritative tone
   - Structured for scannability
   - Self-contained paragraphs (50-150 words)
   - Use `[STAT: description]` placeholders for facts
   - Match the structural blueprint from the brief
   - Style guide is PRIMARY voice reference

2. **`REVISION_SYSTEM_PROMPT`** (used during evaluator revision cycles):
   - Address ALL evaluation feedback
   - Structural targets are PRIMARY constraints
   - CAN add new sections (FAQ, tables, key takeaways)
   - Never shrink below word count target
   - Self-contained paragraphs must remain citable
   - Maintain brand voice from style guide

**User prompt** (`build_drafter_user_prompt()`) structure:

```
## Writing Style Guide (PRIMARY voice reference -- follow precisely)
{full style guide markdown}

## Content Outline
```json
{outline as JSON}
```

## Target Queries (weave naturally into the content)
  - "query 1"
  - "query 2"

## Structural Blueprint (from gap analysis -- match or exceed these targets)
**Word count target: 1200-2000 words**
- Min headers: 7
- Min lists: 3
- Min citations: 5
- Min stats/data points: 4
- Min paragraphs: 12
- Target paragraph length: 80 words avg, 150 max
- Min self-contained claims: 6
- Min bullets per list: 3
- **Include FAQ section** (if faq_rate > 0.3)
- **Include comparison/data table** (if table_rate > 0.3)

## Exemplar Intelligence (what top-cited content looks like)
Exemplar 1: 2100 words, 9 headers, 14 lists, 7 stats
  "First 200 chars of cited content..."
  Source: https://example.com

## Exemplar Themes
- step-by-step format
- data-heavy with industry benchmarks

### Company Context
{company context snippet}
```

**Post-processing**: Strips markdown code fences if LLM wraps output:
```python
if markdown.startswith("```markdown"): markdown = markdown[len("```markdown"):].strip()
if markdown.startswith("```"): markdown = markdown[3:].strip()
if markdown.endswith("```"): markdown = markdown[:-3].strip()
```

**Output model**:
```python
class ContentDraft(BaseModel):
    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
```

### 5.5 Step 3: Fact Enricher

**Prompt file**: `core/content_engine/prompts/enricher_prompts.py` (54 lines)

| Setting | Value |
|---------|-------|
| Model | `sonar-pro` (Perplexity — web search enabled) |
| Max output tokens | 8,192 |
| Timeout | 120 seconds |
| Client | OpenAI-compatible Perplexity client |

**System prompt** (`ENRICHER_SYSTEM_PROMPT`):
1. Replace `[STAT: description]` placeholders with real, sourced statistics
2. Verify factual claims and add source citations
3. Add relevant data points that strengthen authority
4. Ensure all numerical claims are accurate and current
5. Output format: `[Source Name, Year]` inline citations

**User prompt** (`build_enricher_user_prompt()`):
```
## Article to Enrich
Title: {title}
Company: {company_name} ({domain})
Key Topics: {key_topics}

## Draft Content
{full draft markdown}

## Instructions
1. Find and replace ALL [STAT: ...] placeholders with real statistics
2. Verify any existing numerical claims -- correct if inaccurate
3. Add 2-3 additional relevant statistics
4. Add inline source citations in [Source Name, Year] format
5. Return the complete enriched article in Markdown
```

**Citation extraction** (post-processing):
```python
citations_found = re.findall(r"\[([^\]]+?,\s*\d{4})\]", enriched_text)
facts_added: List[Dict[str, str]] = [{"citation": c} for c in citations_found]
```

**Graceful degradation**: If `PERPLEXITY_API_KEY` is not set, passes through the draft unchanged.

**Output model**:
```python
class EnrichedDraft(BaseModel):
    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
    facts_added: List[Dict[str, str]] = Field(default_factory=list)
```

### 5.6 Step 4: Formatter

**Prompt file**: `core/content_engine/prompts/formatter_prompts.py` (98 lines)

| Setting | Value |
|---------|-------|
| Model | `claude-haiku-4-5-20251001` (fast, lightweight) |
| Max output tokens | 8,192 |
| Max input tokens | ~150,000 |

**System prompt** (`FORMATTER_SYSTEM_PROMPT`) — 10 formatting rules:
1. Heading hierarchy (H2 -> H3 -> H4, no skips)
2. Convert run-on enumerations into lists (min 3 items)
3. Bold key terms on first mention
4. Statistics prominently displayed
5. Whitespace between sections
6. Standardize citations to `[Source, Year]`
7. Remove `[STAT: ...]` leftovers
8. FAQ formatted as Q&A (bold questions)
9. Tables in proper Markdown syntax
10. Key takeaways as highlighted section

**User prompt** (`build_formatter_user_prompt()`):
- Full enriched markdown
- Full style guide (no truncation)
- Structural targets for compliance checking (min headers/lists/citations, FAQ/table flags)

**Structural element counting** (`_count_structural_elements()`):
```python
header_count  = lines matching /^#{1,6}\s/
list_count    = lines matching /^\s*[-*+]\s/ or /^\s*\d+\.\s/
stat_count    = lines with numbers + % or $ or "million"/"billion"/"percent"
citation_count = matches of /\[[^\]]+?,\s*\d{4}\]/ or /\[https?://[^\]]+\]/
```

**Output model**:
```python
class FormattedContent(BaseModel):
    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
    header_count: int = 0
    list_count: int = 0
    stat_count: int = 0
    citation_count: int = 0
```

---

## 6. Stage 3 — Evaluator Loop

**Files**: `core/content_engine/evaluator/loop.py` (344 lines), `evaluator/structural.py` (483 lines), `evaluator/semantic.py` (146 lines), `evaluator/style_judge.py`, `evaluator/factual_judge.py`

### 6.1 Loop Logic

**Function**: `evaluate_and_optimize()` in `core/content_engine/evaluator/loop.py` — lines 121-343

```python
async def evaluate_and_optimize(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str,
    style_guide_md: str,
    input_data: ContentGenerationInput,
    max_cycles: int = 2,
    ...
) -> Tuple[FormattedContent, RevisionHistory]:
```

**Algorithm**:

```
max_cycles = format_aware_lookup(brief.content_format)  # Override default
prev_score = None

for cycle in 0..max_cycles:
    1. Run all 4 evaluations in parallel:
       - Structural (sync) | Semantic (async) | Style (async) | Factual (async)

    2. Compute overall:
       - overall_score = average(4 dimension scores)
       - overall_passed = all(4 dimensions passed)

    3. If all passed -> break (success)

    4. If cycle > 0 and improvement < 0.02 -> early-stop (score plateau)

    5. If cycle == max_cycles -> break (failed, flagged for HITL)

    6. Compile feedback from failed dimensions:
       "[STRUCTURAL] feedback | [STYLE] feedback | [FACTUAL] feedback"

    7. Revision cycle:
       - revise_draft() with REVISION_SYSTEM_PROMPT + feedback
       - enrich_with_facts() (Perplexity re-enrichment)
       - format_content() (recount structural elements)

    8. Loop back to step 1
```

**Format-aware revision cycles** (from settings):
```json
{
  "pillar_page": 3,
  "comparison": 3,
  "long_blog": 2,
  "how_to": 2,
  "short_faq": 1
}
```

### 6.2 Dimension 1: Structural Evaluator (Sync, No LLM)

**File**: `core/content_engine/evaluator/structural.py` — 483 lines

Pure Python evaluation with **14 checks** — no LLM calls.

#### 4 Hard Gates (must pass; score capped at 0.5 if ANY fail)

| Gate | Check Logic | Feedback on Failure |
|------|-------------|---------------------|
| `word_count` | `min_wc <= content.word_count <= max_wc` | "Word count {wc} is below/above {limit}" |
| `heading_hierarchy` | No level skips (H2->H4 without H3) | "Heading hierarchy skip: H{x} -> H{y}" |
| `no_empty_sections` | No heading immediately followed by another heading | "Empty sections found: {headings}" |
| `required_elements` | All `brief.required_structural_elements` present | "Missing required elements: {list}" |

#### 10 Soft Weighted Checks (conditional -- skipped if target=0 or rate<=0.3)

| Check | Weight | Pass Condition |
|-------|--------|----------------|
| `header_count` | 0.12 | `content.header_count >= brief.structural_targets.min_headers` |
| `list_count` | 0.08 | `content.list_count >= brief.structural_targets.min_lists` |
| `citation_count` | 0.12 | `content.citation_count >= brief.structural_targets.min_citations` |
| `stat_presence` | 0.10 | `content.stat_count >= brief.structural_targets.min_stats` |
| `paragraph_length` | 0.12 | Avg paragraph word count within +/-30% of target |
| `sentence_length` | 0.08 | <10% of sentences exceed 30 words |
| `faq_presence` | 0.10 | If `faq_rate > 0.3`, content has FAQ section (regex match) |
| `table_presence` | 0.08 | If `table_rate > 0.3`, content has markdown table (`\|.+\|.+\|`) |
| `self_contained_claims` | 0.12 | Paragraphs 20-150 words with stat/definitive pattern |
| `bullet_density` | 0.08 | Avg bullets per list block >= `min_bullets_per_list` |

**Scoring formula**:
```
soft_score = sum(weight for passing checks) / sum(weight for active checks)

if any hard gate fails:
    score = min(soft_score, 0.5)
else:
    score = soft_score

passed = (score >= 0.70)
```

### 6.3 Dimension 2: Semantic Evaluator (Async)

**File**: `core/content_engine/evaluator/semantic.py` — 146 lines

1. Embed each target query via `async_embed_texts(query_texts)`
2. Embed first ~2000 words of content via `async_embed_texts([content_text])`
3. Compute cosine similarity (numpy) between content embedding and each query embedding
4. Average all similarities
5. Pass if `avg_similarity >= brief.semantic_threshold` (default 0.65)
6. Score = `avg_similarity`

**Embedding model**: `text-embedding-3-small` (1536 dimensions, OpenAI)

### 6.4 Dimension 3: Style Judge (Async LLM)

**Prompt file**: `core/content_engine/prompts/style_judge_prompts.py` — 94 lines

| Setting | Value |
|---------|-------|
| Model | `claude-haiku-4-5-20251001` |
| Max output tokens | 2,048 |
| Pass threshold | `score >= 0.75` |

**4 weighted criteria**:

| Criterion | Weight | What It Checks |
|-----------|--------|----------------|
| Voice & Tone | 0.30 | Does article match brand's specified voice? |
| Terminology | 0.25 | Correct industry/product terms? Required terms used? Avoided terms absent? |
| Formatting Conventions | 0.25 | Heading capitalization, list style, citation format, number formatting |
| Structural Voice | 0.20 | Paragraph length consistency, active/passive balance, sentence variety |

**Input**: Full content markdown + full style guide (no truncation except 150K token limit).

**Output**: JSON with `score`, `passed`, `feedback`, `criteria_scores` (per-criterion breakdown).

### 6.5 Dimension 4: Factual Judge (Async LLM)

**Prompt file**: `core/content_engine/prompts/factual_judge_prompts.py` — 62 lines

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-5-20250929` |
| Max output tokens | 2,048 |
| Pass threshold | `score >= 0.70` |

**4 weighted criteria**:

| Criterion | Weight | What It Checks |
|-----------|--------|----------------|
| Claim accuracy | 0.30 | Are factual claims correct and verifiable? |
| Source quality | 0.25 | Are sources cited? Are they authoritative? |
| Recency | 0.20 | Are statistics current (within 2 years)? |
| Completeness | 0.25 | Are key claims backed by evidence? |

**Output**: JSON with `score`, `passed`, `feedback`, `criteria_scores`, and `flagged_claims[]`.

### 6.6 Revision Cycle

When any dimension fails, the revision cycle triggers:

1. **Compile feedback**: Collects feedback from all failed dimensions, prefixed with `[DIMENSION_NAME]`
2. **Re-draft**: Calls `revise_draft()` with `REVISION_SYSTEM_PROMPT` + compiled feedback (Sonnet 4.5)
3. **Re-enrich**: Calls `enrich_with_facts()` (Perplexity sonar-pro)
4. **Re-format**: Calls `format_content()` (Haiku 4.5, recounts structural elements)
5. **Re-evaluate**: Loops back to all 4 evaluations

**Early-stop condition**: If `improvement < 0.02` between consecutive cycles, stops to prevent infinite/wasteful loops.

### 6.7 Output

```python
class DimensionResult(BaseModel):
    dimension: str           # "structural" | "semantic" | "style" | "factual"
    passed: bool = False
    score: float = 0.0
    feedback: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)

class EvalResult(BaseModel):
    brief_id: str
    cycle: int = 0
    dimensions: List[DimensionResult]
    overall_passed: bool = False
    overall_score: float = 0.0

class RevisionHistory(BaseModel):
    brief_id: str
    cycles: List[EvalResult]
    final_passed: bool = False
```

Persisted to `artifacts/content/{slug}/content/{brief_id}/eval_history.json`.

---

## 7. Stage 4 — Human Review (HITL)

**File**: `core/content_engine/graph.py` — 270 lines

### 7.1 LangGraph State Machine

```
present_content
    |
    v
approval_gate (interrupt)
    |
    v
route (conditional)
    |-- "approve" --> finalize --> END
    |-- "edit"    --> apply_edits --> approval_gate (loop back)
    |-- "reject"  --> END
```

Built with `langgraph.graph.StateGraph(dict)` and `langgraph.types.interrupt()`.

### 7.2 Node Functions

| Node | What It Does |
|------|-------------|
| `_present_content` | Assembles eval summary from revision history (last cycle's dimension scores) |
| `_approval_gate` | If `auto_approve=True`, immediately returns `"approve"`. Otherwise, calls `interrupt()` with brief_id, title, word_count, eval_summary, and content preview (first 1000 chars). |
| `_route` | Pass-through; routing handled by conditional edges |
| `_apply_edits` | Stores `editor_notes` in state, loops back for re-review. (v1.1 will trigger LLM revision.) |
| `_finalize` | Writes `final.md` to `artifacts/content/{slug}/content/{brief_id}/final.md` |
| `_get_decision` | Extracts `approval_decision` from state: `"approve"` / `"edit"` / `"reject"` |

**Resume from interrupt** with:
```python
{"approval_decision": "approve"|"edit"|"reject", "editor_notes": "..."}
```

### 7.3 Output

```python
class ContentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"

class ContentPiece(BaseModel):
    brief_id: str
    title: str
    status: ContentStatus = ContentStatus.PENDING
    final_markdown: str = ""
    eval_summary: Dict[str, Any] = Field(default_factory=dict)
    human_notes: Optional[str] = None
    artifact_path: Optional[str] = None

class ContentGenerationOutput(BaseModel):
    company_slug: str
    total_briefs: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    pieces: List[ContentPiece] = Field(default_factory=list)
    run_metadata: Dict[str, Any] = Field(default_factory=dict)
```

`run_metadata` includes: `session_id`, `total_time_s`, `skip_stages`, `auto_approve`.

---

## 8. Prompt Management

All prompts are stored in dedicated files under `core/content_engine/prompts/`:

| File | Lines | Constants | Builder Function | Used By |
|------|-------|-----------|-----------------|---------|
| `planner_prompts.py` | 302 | `PLANNER_SYSTEM_PROMPT` | `build_planner_user_prompt()` | Stage 1 |
| `outliner_prompts.py` | 212 | `OUTLINER_SYSTEM_PROMPT` | `build_outliner_user_prompt()` | Stage 2, Step 1 |
| `drafter_prompts.py` | 216 | `DRAFTER_SYSTEM_PROMPT`, `REVISION_SYSTEM_PROMPT` | `build_drafter_user_prompt()` | Stage 2, Step 2 + revision |
| `enricher_prompts.py` | 54 | `ENRICHER_SYSTEM_PROMPT` | `build_enricher_user_prompt()` | Stage 2, Step 3 |
| `formatter_prompts.py` | 98 | `FORMATTER_SYSTEM_PROMPT` | `build_formatter_user_prompt()` | Stage 2, Step 4 |
| `style_judge_prompts.py` | 94 | `STYLE_JUDGE_SYSTEM_PROMPT` | `build_style_judge_user_prompt()` | Stage 3 |
| `factual_judge_prompts.py` | 62 | `FACTUAL_JUDGE_SYSTEM_PROMPT` | `build_factual_judge_user_prompt()` | Stage 3 |

**Pattern**: Each file exports:
- A `*_SYSTEM_PROMPT` constant (multi-line string with role, guidelines, and JSON output schema)
- A `build_*_user_prompt()` function that assembles the user message from structured inputs

---

## 9. Tracing & Observability

**File**: `core/content_engine/tracing.py` — 327 lines (Langfuse v3 SDK)

**Optional** — gracefully returns `None` for all operations if `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are not configured.

### Trace Hierarchy

```
Session: content-gen-{slug}-{timestamp}
  |
  +-- Pipeline Trace: content-pipeline/{slug}
      |
      +-- stage/1-planner
      |   +-- planner
      |       +-- Generation: plan_content
      |
      +-- stage/2-workers
      |   +-- Worker #1: {title}
      |   |   +-- outliner -> Generation
      |   |   +-- drafter -> Generation
      |   |   +-- fact_enricher -> Generation
      |   |   +-- formatter -> Generation
      |   +-- Worker #2: ...
      |
      +-- stage/3-evaluator
      |   +-- evaluator/{brief_id}
      |       +-- eval_cycle_0
      |       |   +-- structural_check (sync, no generation)
      |       |   +-- semantic_check -> Generation (embedding)
      |       |   +-- style_judge -> Generation
      |       |   +-- factual_judge -> Generation
      |       +-- revision_cycle_1 (if failed)
      |       +-- eval_cycle_1
      |
      +-- stage/4-review
          +-- Review: {title}
              +-- Score: human_decision
```

### API Functions

| Function | Purpose |
|----------|---------|
| `create_session(slug)` | Create Langfuse session, return session_id |
| `create_pipeline_trace(...)` | Root pipeline trace |
| `create_trace(session_id, name, ...)` | Root span under session |
| `create_span(parent, name, ...)` | Child span |
| `end_span(span, output, ...)` | End span with output |
| `log_generation(trace, name, model, ...)` | Log LLM call |
| `log_score(trace, name, value, ...)` | Log numeric/string/bool score |
| `update_trace_output(trace, output, ...)` | Update trace output |
| `flush()` | Flush pending events |

---

## 10. Utilities

**File**: `core/content_engine/utils.py` — 155 lines

| Function | Purpose |
|----------|---------|
| `_extract_json_block(text)` | Extract JSON from markdown code fences (`\`\`\`json...\`\`\``) or bare `{...}` / `[...]` |
| `safe_parse(text, model_cls)` | Robust LLM text -> Pydantic model. Handles trailing commas, single-line comments. Two-attempt parse. |
| `_retry_async_anthropic(fn, max_retries=3, base_delay=1.0)` | Retry with jittered exponential backoff. Handles `RateLimitError`, `APIError`, `APIConnectionError` for both Anthropic and OpenAI. |
| `_estimate_tokens(text)` | Rough estimate: `len(text) // 4` |
| `truncate_to_token_limit(text, max_tokens, label)` | Context window guard. Truncates with `[... truncated]` note and warning log. |

---

## 11. Model & Token Limits Summary

| Component | Model | Provider | Max Output | Max Input | Timeout |
|-----------|-------|----------|-----------|-----------|---------|
| Planner | `claude-opus-4-6` | Anthropic | 16,384 | ~150K tokens | — |
| Outliner | `claude-sonnet-4-5-20250929` | Anthropic | 4,096 | ~150K tokens | — |
| Drafter | `claude-sonnet-4-5-20250929` | Anthropic | 8,192 | ~100K tokens | — |
| Fact Enricher | `sonar-pro` | Perplexity | 8,192 | — | 120s |
| Formatter | `claude-haiku-4-5-20251001` | Anthropic | 8,192 | ~150K tokens | — |
| Style Judge | `claude-haiku-4-5-20251001` | Anthropic | 2,048 | ~150K tokens | — |
| Factual Judge | `claude-sonnet-4-5-20250929` | Anthropic | 2,048 | ~150K tokens | — |
| Embeddings | `text-embedding-3-small` | OpenAI | — | — | — |

---

## 12. Artifact Directory Structure (Output)

```
artifacts/content/{slug}/
|-- briefs.json                          <-- Stage 1 output (PlannerOutput)
|-- run_metadata.json                    <-- Final pipeline output (ContentGenerationOutput)
+-- content/
    |-- brief-001/
    |   |-- outline.json                 <-- Stage 2, Step 1 (ContentOutline)
    |   |-- draft.md                     <-- Stage 2, Step 2 (raw markdown)
    |   |-- enriched.md                  <-- Stage 2, Step 3 (with [Source, Year] citations)
    |   |-- formatted.md                 <-- Stage 2, Step 4 (polished markdown)
    |   |-- eval_history.json            <-- Stage 3 (RevisionHistory with all cycles)
    |   +-- final.md                     <-- Stage 4 (if approved)
    |-- brief-002/
    |   +-- ...
    +-- brief-003/
        +-- ...
```

---

## 13. Configuration

**File**: `core/config/settings.py` (Pydantic `BaseSettings`, env vars from `.env.local`)

```python
# Content Engine Models
content_engine_planner_model: str = "claude-opus-4-6"
content_engine_worker_model: str = "claude-sonnet-4-5-20250929"
content_engine_formatter_model: str = "claude-haiku-4-5-20251001"
content_engine_style_judge_model: str = "claude-haiku-4-5-20251001"
content_engine_factual_judge_model: str = "claude-sonnet-4-5-20250929"
content_engine_fact_enricher_model: str = "sonar-pro"

# Concurrency & Limits
content_engine_max_concurrent_workers: int = 3
content_engine_max_revision_cycles: int = 2
content_engine_revision_cycles_by_format: str = \
    '{"pillar_page": 3, "comparison": 3, "long_blog": 2, "how_to": 2, "short_faq": 1}'

# Embeddings
embedding_model: str = "text-embedding-3-small"

# Langfuse (optional)
langfuse_public_key: str | None = None
langfuse_secret_key: str | None = None
langfuse_host: str = "https://us.cloud.langfuse.com"

# API Keys
anthropic_api_key: str | None = None
openai_api_key: str | None = None
perplexity_api_key: str | None = None
```

All settings can be overridden via environment variables (e.g., `CONTENT_ENGINE_PLANNER_MODEL=claude-sonnet-4-5`).

---

## 14. Test Coverage

**Location**: `tests/content_engine/` — 12 files, 40+ tests, 57 passing

| File | Tests | What It Covers |
|------|-------|----------------|
| `conftest.py` | — | Shared fixtures: sample_input, sample_brief, sample_outline, sample_draft, sample_enriched, sample_formatted, mock LLM clients (MockAnthropicResponse), mock embeddings |
| `test_models.py` | 16+ | All Pydantic models: construction, defaults, JSON round-trip, backward compatibility (v1 JSON -> v2 model) |
| `test_planner.py` | 2 | Plan generation produces briefs, respects max_briefs |
| `test_outliner.py` | 1 | Outline generation with structural elements |
| `test_drafter.py` | 1 | Draft generation produces markdown with word count |
| `test_fact_enricher.py` | 2 | Citation enrichment; graceful skip when API key missing |
| `test_formatter.py` | 6 | `_count_structural_elements()` unit tests (headers, lists, stats, citations, empty); full format_content() |
| `test_dispatcher.py` | 2 | Full worker chain; fault isolation (brief-002 fails, brief-001 succeeds) |
| `test_structural.py` | 13 | All 14 checks: 4 hard gates, 10 soft checks, v2.0 new checks (FAQ, table, sentence, bullet, claims, paragraphs), paragraph extraction |
| `test_evaluator.py` | 2 | Full eval loop: all-pass scenario; revision-triggered scenario |
| `test_graph.py` | 2 | Graph compilation; auto-approve flow |
| `test_integration.py` | 2 | End-to-end pipeline (all stages mocked); skip_stages support |

---

## 15. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Raw AsyncAnthropic SDK** (no LangChain) | Consistent with gap analysis pattern. Fine-grained control over parameters, retries, and response parsing. |
| 2 | **Semaphore concurrency** | `asyncio.Semaphore(max_concurrent)` for worker parallelism. Same pattern as gap analysis `s3_search_platforms.py`. |
| 3 | **Evaluator-Optimizer pattern** | Anthropic's recommended agentic pattern for automated quality gates with revision loops. |
| 4 | **LangGraph HITL** | `interrupt()` + `StateGraph(dict)` for human-in-the-loop review. Same pattern as research pipeline. |
| 5 | **Structural intelligence propagation** | Gap analysis exemplar data flows through planner -> outliner -> drafter -> evaluator. Not lost at any stage. |
| 6 | **Style guide prominence** | Placed FIRST in drafter prompt, marked "PRIMARY voice reference" to ensure brand compliance. |
| 7 | **Format-aware revision cycles** | Pillar pages get 3 revision cycles, short FAQ gets 1. Prevents over-engineering short content. |
| 8 | **return_exceptions=True** | One failing brief doesn't cancel the batch. Fault isolation in parallel workers. |
| 9 | **Langfuse v3 tracing** | Full hierarchical observability. Optional — gracefully degrades if keys not set. |
| 10 | **Dual system prompts for drafting** | `DRAFTER_SYSTEM_PROMPT` for initial writing, `REVISION_SYSTEM_PROMPT` for feedback-driven revision. Different guidelines for different modes. |
| 11 | **Early-stop on score plateau** | If improvement < 0.02 between revision cycles, stops to prevent infinite/wasteful loops. |
| 12 | **Conditional structural checks** | Checks with target=0 or rate<=0.3 are skipped entirely, not penalized. Prevents false failures on intentionally omitted elements. |

---

## 16. Data Flow Diagram

```
                            INPUTS
    ===================================================================
    |                           |                          |
    v                           v                          v
 company_context.md      persona_*.md              style_guide.md
    |                           |                          |
    |    gap_report.json   generation_spec.json   analysis.json
    |         |                  |                     |
    ===================================================================
                                |
                                v
                    [STAGE 1: STRATEGIC PLANNER]
                    Model: claude-opus-4-6
                                |
                                v
                    PlannerOutput { briefs[] }
                    -> briefs.json
                                |
                    +-----------+-----------+
                    |           |           |
                    v           v           v
              [STAGE 2: CONTENT WORKERS — parallel via semaphore]
              Per brief:
                  Outliner (Sonnet)    -> outline.json
                      |
                  Drafter (Sonnet)     -> draft.md
                      |
                  Fact Enricher (Perplexity) -> enriched.md
                      |
                  Formatter (Haiku)    -> formatted.md
                    |           |           |
                    +-----------+-----------+
                                |
                                v
                    List[FormattedContent]
                                |
                                v
                    [STAGE 3: EVALUATOR LOOP]
                    Per content piece:
                    +----------------------------------+
                    | Parallel evaluation:             |
                    |   Structural (sync, 14 checks)   |
                    |   Semantic (async, embeddings)    |
                    |   Style Judge (Haiku LLM)        |
                    |   Factual Judge (Sonnet LLM)     |
                    +----------------------------------+
                                |
                        All passed? --> YES --> done
                                |
                              NO (+ score plateau check)
                                |
                        Compile feedback
                                |
                        revise_draft() -> enrich() -> format()
                                |
                        Loop back (max N cycles)
                                |
                                v
                    List[FormattedContent] + List[RevisionHistory]
                    -> eval_history.json
                                |
                                v
                    [STAGE 4: HUMAN REVIEW (HITL)]
                    LangGraph: present -> interrupt -> route
                        approve -> finalize -> final.md
                        edit    -> apply_edits -> loop back
                        reject  -> END
                                |
                                v
                    ContentGenerationOutput
                    -> run_metadata.json
```

---

## 17. File Manifest

### Core Pipeline
| File | Lines | Description |
|------|-------|-------------|
| `core/content_engine/__init__.py` | 0 | Package marker |
| `core/content_engine/pipeline.py` | 436 | Main orchestrator (4 stages, skip support, CLI progress) |
| `core/content_engine/planner.py` | 180 | Stage 1: Strategic planner (AsyncAnthropic call) |
| `core/content_engine/graph.py` | 270 | Stage 4: LangGraph HITL review state machine |
| `core/content_engine/tracing.py` | 327 | Langfuse v3 tracing integration |
| `core/content_engine/utils.py` | 155 | safe_parse, retry, token estimation |

### Workers (Stage 2)
| File | Description |
|------|-------------|
| `core/content_engine/workers/__init__.py` | Package marker |
| `core/content_engine/workers/dispatcher.py` | Semaphore-controlled parallel dispatch |
| `core/content_engine/workers/outliner.py` | Step 1: Outline generation |
| `core/content_engine/workers/drafter.py` | Step 2: Draft generation + revision |
| `core/content_engine/workers/fact_enricher.py` | Step 3: Perplexity fact enrichment |
| `core/content_engine/workers/formatter.py` | Step 4: Formatting + structural counting |

### Evaluators (Stage 3)
| File | Description |
|------|-------------|
| `core/content_engine/evaluator/__init__.py` | Package marker |
| `core/content_engine/evaluator/loop.py` | Evaluator-optimizer loop orchestrator |
| `core/content_engine/evaluator/structural.py` | 14-check deterministic evaluator |
| `core/content_engine/evaluator/semantic.py` | Embedding cosine similarity evaluator |
| `core/content_engine/evaluator/style_judge.py` | LLM style guide compliance judge |
| `core/content_engine/evaluator/factual_judge.py` | LLM factual accuracy judge |

### Prompts
| File | Lines | Used By |
|------|-------|---------|
| `core/content_engine/prompts/__init__.py` | 0 | Package marker |
| `core/content_engine/prompts/planner_prompts.py` | 302 | Stage 1 |
| `core/content_engine/prompts/outliner_prompts.py` | 212 | Stage 2, Step 1 |
| `core/content_engine/prompts/drafter_prompts.py` | 216 | Stage 2, Step 2 + revision |
| `core/content_engine/prompts/enricher_prompts.py` | 54 | Stage 2, Step 3 |
| `core/content_engine/prompts/formatter_prompts.py` | 98 | Stage 2, Step 4 |
| `core/content_engine/prompts/style_judge_prompts.py` | 94 | Stage 3 |
| `core/content_engine/prompts/factual_judge_prompts.py` | 62 | Stage 3 |

### Models & Config
| File | Description |
|------|-------------|
| `core/models/content_generation.py` | All 16 Pydantic models (283 lines) |
| `core/config/settings.py` | Environment configuration |
| `scripts/run_content_engine.py` | CLI entry point (156 lines) |

---

*Generated from codebase analysis on 2026-02-20. Total: ~3,500 lines across 25 files.*
