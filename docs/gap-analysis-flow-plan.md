# Gap Analysis Pipeline Upgrade — Claude Code Plan-Mode Prompt

## Context: What This Codebase Does

You are working on `content-strategy-engine/`, a Python project that helps B2B companies get cited in AI search results (Perplexity, ChatGPT, Claude, Gemini). The **gap analysis pipeline** (Pipeline 2) is an 8-step pipeline under `core/gap_analysis/` that:

1. Crawls a company's website and embeds the content (`s1_embed_assets.py`)
2. Generates search queries a buyer persona would ask (`s2_generate_queries.py`)
3. Sends those queries to AI search platforms and collects responses + citations (`s3_search_platforms.py`)
4. Crawls each cited URL and extracts paragraphs + structural signals (`s4_enrich_citations.py`)
5. Embeds all queries + citation paragraphs, matches best paragraphs to each citation (`s5_embed_content.py`)
6. Computes semantic proximity analysis: how well the company's content matches what gets cited vs. competitors (`s6_analyze.py`)
7. Generates UMAP + heatmap + radar visualizations (`s7_visualize.py`)
8. Produces a gap report (markdown + JSON) and a content generation spec (`s8_generate_report.py`)

The pipeline orchestrator is `core/gap_analysis/pipeline.py`. Pydantic v2 models are in `core/models/gap_analysis.py`.

---

## The Problem: Current Output vs. Benchmark

The current pipeline produces **shallow, generic outputs**. Compare:

### Current `analysis.json` (for Carta):
```json
{
  "proximity_stats": {
    "citation_similarity_mean": 0.0,
    "citation_similarity_median": 0.0,
    "company_similarity_mean": 0.0,
    "company_similarity_median": 0.0
  },
  "gaps": [],
  "spa_results": []
}
```
All zeros. Empty gaps. The pipeline runs but produces no meaningful analysis.

### Current `gap_report.md` (for Carta):
Generic 15-line report with vague recommendations like "Diversify Sources" — no data, no per-query breakdowns, no citation exemplars.

### Current `generation_spec.md` (for Carta):
Generic 15-line spec with no cluster-level specifications, no word count ranges, no structural signal targets.

### Benchmark `step2_gap_report_perplexity_mynd_canonical.md` (for MYND):
- SPA score computed and displayed
- Per-query gap briefs with top-3 cited exemplar URLs, similarity scores, snippet text, structural signals (word count, paragraph count, header count, list count, stat count, citation count), and authority type
- Complete gap table with all 20 queries sorted by gap magnitude
- Each gap labeled with interpretation (significant_gap, gap_to_close, roughly_equal)

### Benchmark `step2_generation_spec_perplexity_mynd_canonical.md` (for MYND):
- Per-cluster content specifications with:
  - Semantic target (cluster centroid embedding)
  - Min similarity threshold
  - Word count range (e.g., 1837–3408)
  - Required structural elements (headers, lists, statistics, source_citations)
  - Authority signal distribution (e.g., commercial_or_media: 11, government: 2, academic: 1)
  - Structural rates (e.g., headers=1.0, lists=1.0, stats=0.87, citations=1.0)

---

## Root Causes of the Quality Gap

### 0. Query Generation (s2)
The current prompt is too generic — it hands the taxonomy to the LLM and says "generate queries." The benchmark shows queries that are tightly mapped to real search behavior. Here's what's missing:
Pipeline-level issues:

No validation loop. You generate queries once and hope they're good.
No deduplication or semantic diversity check (you could have 5 near-identical queries in the same cluster).
The citation_behavior field in your taxonomy isn't being leveraged to shape query phrasing.

What I'd recommend:
Rather than a SKILL.md (which is for document creation), you need a multi-pass query generation strategy baked into s2_generate_queries.py:
Pass 1 — Seed generation: Generate 2-3x the target count per cluster, using a prompt that's much more specific about what "natural buyer language" looks like for each cluster's intent and buyer stage.
Pass 2 — Deduplication via embedding: Embed all candidates, then within each cluster, prune queries that are too semantically similar (cosine > 0.85). This prevents the "5 versions of the same question" problem.
Pass 3 — Coverage validation: Check that every cluster has at least N queries and that buyer stages are balanced. If gaps exist, generate targeted fill-ins.
Here's the concrete prompt improvement for Pass 1:
pythonQUERY_GEN_PROMPT = """
You are a search behavior expert for B2B buyers. Generate realistic search queries 
that a {persona_summary} would type into Google, ChatGPT, or Perplexity when 
researching solutions in the {company_domain} space.

CRITICAL RULES:
- Queries must sound like REAL searches, not marketing copy
- Mix question formats: "How does...", "What is...", "Best X for Y", "X vs Y"
- Include branded queries (mentioning {company_name} or competitors by name)
- Include unbranded queries (category-level, no brand names)
- Each cluster has a specific INTENT and BUYER STAGE — match them precisely
- For "Branded Evaluation" (C8): always include at least 2 named competitors
- For "Feature Verification" (C9): reference specific capabilities, not vague features
- For "Problem/Awareness" (C6): frame as pain points, not solutions

For each query, also provide:
- search_intent: informational | navigational | commercial | transactional
- branded: true | false
- expected_citation_types: what kinds of pages would rank for this query

CLUSTER TAXONOMY:
{clusters_json}

COMPANY CONTEXT (condensed):
{company_context_condensed}

PERSONA:
{persona_condensed}

Generate {target_count} queries total. Distribute across clusters proportionally,
with heavier weight on C1 (Mechanism), C3 (Category Comparison), and C7 (Best-of).

Return JSON array only.
"""
The key additions: branded vs unbranded mix, expected citation types per query (which feeds downstream analysis), and explicit instruction about search intent types.
For the dedup pass, add this to s2_generate_queries.py:
pythondef deduplicate_queries(queries: List[GeneratedQuery], threshold: float = 0.85) -> List[GeneratedQuery]:
    """Remove semantically redundant queries within each cluster."""
    from collections import defaultdict
    clusters = defaultdict(list)
    for q in queries:
        clusters[q.cluster_id].append(q)
    
    kept = []
    for cluster_id, cluster_queries in clusters.items():
        embeddings = _embed_texts([q.query_text for q in cluster_queries])
        selected = []
        selected_embs = []
        for q, emb in zip(cluster_queries, embeddings):
            if not selected_embs:
                selected.append(q)
                selected_embs.append(emb)
                continue
            max_sim = max(_cosine_similarity(emb, s) for s in selected_embs)
            if max_sim < threshold:
                selected.append(q)
                selected_embs.append(emb)
        kept.extend(selected)
    return kept


### Root Cause 1: Structural signals in s4 are too basic

`s4_enrich_citations.py` currently captures:
```python
class StructuralSignals(BaseModel):
    word_count: int = 0
    has_headers: bool = False
    has_lists: bool = False
    has_numbers: bool = False
    authority_type: Optional[str] = None
    content_type: Optional[str] = None
```

The benchmark captures **counts**, not booleans — header count, list item count, stat/number count, citation/link count, paragraph count. This granular data is essential for the generation spec to tell content creators "your article needs ~9 headers, ~137 list items, ~85 stats, ~99 citations" (matching what actually gets cited).

### Root Cause 2: s6 analysis doesn't attach exemplars to gaps

`s6_analyze.py` computes `QueryGap` objects with `best_company_similarity` and `avg_citation_similarity`, but does NOT attach:
- Which specific cited pages scored highest for that query
- The snippet text from those pages
- Their structural signals and authority type
- The best matching company content unit (ID and text)

Without this, the report generator (s8) has no data to produce per-query gap briefs.

### Root Cause 3: s6 doesn't compute cluster-level specs

There is no aggregation of citation structural signals per cluster. The generation spec needs to know: "For queries in the 'Mechanism' cluster, winning cited content has 1837–3408 words, always has headers, always has lists, 87% have stats, authority is mostly commercial_or_media." This requires a dedicated aggregation pass in s6.

### Root Cause 4: s8 over-relies on LLM for structure

The current `s8_generate_report.py` sends the entire analysis JSON to an LLM and asks it to produce both the gap report AND generation spec as a single JSON response. This causes:
- Hallucinated numbers (the LLM invents metrics instead of using computed ones)
- Missing detail (the LLM can't fit per-query breakdowns in one response)
- Inconsistent structure between runs

The fix: build the report **programmatically** from computed data. Only use the LLM for the executive summary and prioritized recommendations.

### Root Cause 5: Query generation is single-pass with a generic prompt

`s2_generate_queries.py` generates queries in one LLM call with no deduplication, no coverage validation, and no use of the `citation_behavior` field from the taxonomy. This leads to redundant queries and poor cluster coverage.

---

## What to Change — Step by Step

### Change 1: Enhance `StructuralSignals` in `core/models/gap_analysis.py`

Replace boolean fields with integer counts. Add new fields for paragraph count and citation/link count.

```python
class StructuralSignals(BaseModel):
    word_count: int = 0
    paragraph_count: int = 0
    header_count: int = 0
    list_item_count: int = 0
    stat_count: int = 0          # count of numbers/percentages/statistics in text
    citation_count: int = 0      # count of outbound links and inline references
    has_headers: bool = False     # keep for backward compat
    has_lists: bool = False       # keep for backward compat
    has_numbers: bool = False     # keep for backward compat
    authority_type: Optional[str] = None
    content_type: Optional[str] = None
```

### Change 2: Update `s4_enrich_citations.py` to compute counts

In `_extract_paragraphs()`, count headers, list items, stats, and citations instead of just checking booleans:

```python
def _extract_paragraphs(html: str) -> Tuple[List[str], StructuralSignals]:
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.find_all(["p", "li", "h2", "h3"])
    paragraphs = []
    for el in elements:
        text = " ".join(el.get_text(" ", strip=True).split())
        if text and len(text) >= 50:
            paragraphs.append(text)

    header_count = len(soup.find_all(["h1", "h2", "h3", "h4"]))
    list_item_count = len(soup.find_all("li"))
    # Count numbers/percentages/dollar amounts in paragraph text
    all_text = " ".join(paragraphs)
    stat_count = len(re.findall(r'\d+\.?\d*\s*%|\$\d+|\d{2,}', all_text))
    # Count outbound links
    citation_count = len(soup.find_all("a", href=True))
    word_count = sum(len(p.split()) for p in paragraphs)

    signals = StructuralSignals(
        word_count=word_count,
        paragraph_count=len(paragraphs),
        header_count=header_count,
        list_item_count=list_item_count,
        stat_count=stat_count,
        citation_count=citation_count,
        has_headers=header_count > 0,
        has_lists=list_item_count > 0,
        has_numbers=stat_count > 0,
    )
    return paragraphs, signals
```

### Change 3: Add enriched gap model to `core/models/gap_analysis.py`

Add a model for citation exemplars that get attached to each gap:

```python
class CitationExemplar(BaseModel):
    """A top-scoring cited page for a specific query."""
    similarity: float
    domain: Optional[str] = None
    url: str
    snippet: Optional[str] = None  # first 300 chars of best paragraph
    structural_signals: Optional[StructuralSignals] = None
    authority_type: Optional[str] = None
```

Extend `QueryGap` to hold exemplars and the best company unit info:

```python
class QueryGap(BaseModel):
    query_id: str
    cluster_name: Optional[str] = None
    query_text: str
    best_company_unit: Optional[str] = None       # unit_id
    best_company_unit_text: Optional[str] = None   # first 200 chars of best unit
    best_company_similarity: Optional[float] = None
    avg_citation_similarity: Optional[float] = None
    gap: Optional[float] = None
    interpretation: Optional[str] = None
    top_cited_exemplars: List[CitationExemplar] = Field(default_factory=list)  # NEW
```

Add a model for cluster-level content specs:

```python
class ClusterContentSpec(BaseModel):
    """Per-cluster content specification derived from citation analysis."""
    cluster_id: Optional[str] = None
    cluster_name: str
    query_count: int = 0
    word_count_range: List[int] = Field(default_factory=lambda: [0, 0])  # [min, max]
    min_similarity_threshold: Optional[float] = None  # e.g. mean - 1 std of citation sims
    required_elements: List[str] = Field(default_factory=list)
    authority_signals: Dict[str, int] = Field(default_factory=dict)
    structural_rates: Dict[str, float] = Field(default_factory=dict)  # header_rate, list_rate, etc.
    total_citations_analyzed: int = 0
```

Add `cluster_specs` to `AnalysisResult`:

```python
class AnalysisResult(BaseModel):
    proximity_stats: Dict[str, Any] = Field(default_factory=dict)
    spa_results: List[SpaResult] = Field(default_factory=list)
    centroids: List[CentroidResult] = Field(default_factory=list)
    gaps: List[QueryGap] = Field(default_factory=list)
    citation_patterns: Dict[str, Any] = Field(default_factory=dict)
    decision_metrics: Dict[str, Any] = Field(default_factory=dict)
    cluster_specs: List[ClusterContentSpec] = Field(default_factory=list)  # NEW
```

### Change 4: Update `s6_analyze.py` to compute exemplars and cluster specs

In `compute_gap_analysis()`, when computing per-query gaps:

**A) Attach top-3 citation exemplars to each QueryGap:**

For each query, collect all citation paragraphs that were matched to it, compute their similarity to the query embedding, rank them, and attach the top 3 with their source citation's domain, URL, snippet, structural signals, and authority type.

**B) Attach best company unit info:**

When finding the best company unit match, also store the unit_id and a text snippet (first 200 chars).

**C) Add a new function `_compute_cluster_specs()`:**

Group enriched citations by cluster. For each cluster:
- Collect word counts from structural signals → compute min/max range
- Count authority types → build distribution dict
- Compute structural rates: what fraction of citations in this cluster have headers, lists, stats, citations
- Compute a min similarity threshold (e.g., the mean citation similarity for that cluster minus 0.5 standard deviations — this becomes the target for generated content)
- Determine required elements: if a structural rate >= 0.8, that element is "required"

Return `List[ClusterContentSpec]` and attach to `AnalysisResult`.

### Change 5: Rewrite `s8_generate_report.py` — programmatic report + LLM summary

The new s8 should work in two phases:

**Phase A: Build reports programmatically (no LLM needed)**

Build `gap_report.md` from the computed `AnalysisResult`:
- Summary section: SPA score, mean cited similarity, mean company similarity, top 5 gap query IDs
- Gap Briefs section: For each of the top 10 gaps (sorted by gap magnitude descending):
  - Query text, cluster name
  - Best company unit (ID + similarity)
  - Avg citation similarity
  - Gap value and interpretation
  - Top 3 cited exemplars with: similarity score, domain, URL, snippet (first 300 chars), structural signals (words, paras, headers, lists, stats, citations), authority type
- Appendix table: All queries with their gap values and interpretations

Build `generation_spec.md` from `cluster_specs`:
- For each cluster:
  - Semantic target note (cluster centroid embedding)
  - Min similarity threshold
  - Word count range
  - Required elements
  - Authority signals to mirror (sorted by count)
  - Structural rates

**Phase B: LLM generates executive summary + recommendations only**

Send a focused prompt to the LLM with:
- The computed SPA score, proximity stats
- The top 10 gap queries with their gaps and clusters
- The cluster specs
- The authority distribution

Ask it to produce:
1. A 4-6 sentence executive summary of the company's citation position
2. Top 5 prioritized content recommendations, each with:
   - Specific content piece to create (title idea)
   - Target cluster
   - Structural signals to match (from cluster specs)
   - Expected impact reasoning

Prepend the LLM's executive summary to the programmatically-built report.

### Change 6: Improve query generation in `s2_generate_queries.py`

This is the most impactful change. Implement a 3-pass strategy:

**Pass 1: Seed generation with an improved prompt**

The new prompt must:
- Reference the `citation_behavior` field from each cluster to shape query phrasing
- Require a mix of branded queries (mentioning the company or competitors by name) and unbranded queries (category-level)
- Require specific search intent classification per query (informational / commercial / navigational / transactional)
- Use natural buyer language, not marketing copy
- Generate 2x the target count (to allow for dedup pruning)

Here is the improved prompt template (store as a constant in the file):

```
You are a search behavior expert for B2B buyers. Generate realistic search queries
that a real person in this role would type into Google, ChatGPT, or Perplexity.

PERSONA (condensed):
{persona_condensed}

COMPANY being analyzed:
- Name: {company_name}
- Domain: {company_domain}
- Category: {company_category}
- Key competitors: {competitor_names}

QUERY CLUSTER TAXONOMY:
Each cluster has an intent pattern and expected citation behavior. Your queries MUST match
the intent and buyer stage of the cluster they belong to.

{clusters_with_citation_behavior}

RULES:
1. Queries must sound like REAL typed searches, not marketing copy or article titles.
   Good: "how does carta handle 409a valuations"
   Bad: "Understanding the Comprehensive Benefits of Cap Table Management Solutions"

2. Mix branded and unbranded queries:
   - Branded: mention {company_name} or a specific competitor by name
   - Unbranded: category-level, no brand names
   - Target ratio: ~40% branded, ~60% unbranded

3. For cluster C8 (Branded Evaluation): ALWAYS include 2-3 named companies (e.g., "Carta vs Pulley vs AngelList")
4. For cluster C9 (Feature Verification): reference SPECIFIC capabilities, not vague features
   Good: "does carta provide ASC 718 audit reports"
   Bad: "does carta have good features"
5. For cluster C6 (Problem/Awareness): frame as PAIN POINTS, not solutions
   Good: "how to avoid cap table errors during fundraising"
   Bad: "best cap table management solution"

6. Each query must include:
   - cluster_id and cluster_name (from taxonomy)
   - query_text (the actual search query)
   - buyer_stage (from cluster taxonomy)
   - branded: true/false
   - search_intent: informational | commercial | navigational | transactional
   - persona_tag: "icp"

7. Generate {seed_count} total queries (we will deduplicate later).
   Distribute across ALL 9 clusters. Weight heavier toward C1, C3, C7, C8.

Return ONLY a JSON object: { "queries": [ ... ] }
```

**Pass 2: Semantic deduplication**

After generating queries, embed them all. Within each cluster, remove queries where cosine similarity to any already-kept query exceeds 0.85. This prevents the "5 versions of the same question" problem.

Add this function:

```python
def _deduplicate_queries(
    queries: List[GeneratedQuery],
    threshold: float = 0.85,
) -> List[GeneratedQuery]:
    """Remove semantically redundant queries within each cluster."""
    # Group by cluster
    # Embed all query texts
    # Within each cluster, greedily select queries that are < threshold similar to all previously selected
    # Return the pruned list
```

**Pass 3: Coverage validation**

After dedup, check that:
- Every cluster has at least `max(2, total_target // 9)` queries
- No cluster has more than 30% of total queries
- All buyer stages (Awareness, Consideration, Evaluation, Decision) are represented

If gaps exist, generate targeted fill-in queries for the underrepresented clusters with a focused prompt.

Wire these three passes into `generate_queries()`.

---

## Files to Modify (in order)

1. `core/models/gap_analysis.py` — Add `CitationExemplar`, `ClusterContentSpec`, extend `StructuralSignals` and `QueryGap` and `AnalysisResult`
2. `core/gap_analysis/steps/s4_enrich_citations.py` — Update `_extract_paragraphs()` to compute counts
3. `core/gap_analysis/steps/s6_analyze.py` — Add exemplar attachment, best unit tracking, and `_compute_cluster_specs()`
4. `core/gap_analysis/steps/s8_generate_report.py` — Rewrite to programmatic report + LLM summary only
5. `core/gap_analysis/steps/s2_generate_queries.py` — 3-pass query generation
6. `core/gap_analysis/pipeline.py` — No structural changes needed, but verify the data flows correctly with the new model fields

## Files NOT to modify

- `s3_search_platforms.py` — No changes needed
- `s5_embed_content.py` — No changes needed (it already computes paragraph embeddings and similarities)
- `s7_visualize.py` — No changes needed (reads from AnalysisResult which is backward compatible)
- Engine files (`engines/*.py`) — No changes needed
- Everything under `core/research/` — Out of scope

---

## Testing Strategy

After making changes:

1. **Model validation**: Run `python -c "from core.models.gap_analysis import AnalysisResult, QueryGap, ClusterContentSpec, CitationExemplar; print('Models OK')"` to verify models parse correctly.

2. **Backward compatibility**: The existing `analysis.json` files should still load into the updated `AnalysisResult` because all new fields have defaults. Verify with: `python -c "import json; from core.models.gap_analysis import AnalysisResult; AnalysisResult(**json.loads(open('artifacts/gap_analysis/carta/analysis.json').read())); print('Backward compat OK')"`

3. **s4 unit test**: Create a small HTML string with known structure (3 headers, 5 list items, 2 stats) and verify `_extract_paragraphs()` returns the correct counts.

4. **s6 unit test**: Create mock queries, company units, and enriched citations with known embeddings. Verify that `compute_gap_analysis()` produces gaps with non-empty `top_cited_exemplars` and that `cluster_specs` are populated.

5. **s8 unit test**: Create a mock `AnalysisResult` with populated gaps and cluster specs. Verify that the programmatic report builder produces valid markdown with the expected sections.

---

## Important Constraints

- Use Pydantic v2 syntax (`model_dump(mode="json")`, not `.dict()`)
- All new model fields MUST have defaults so existing serialized data still loads
- The `_embed_texts()` helper is already defined in both s1 and s5 — reuse the s5 version for the query dedup pass in s2 (import it, or copy the pattern)
- The pipeline uses `json.dumps(..., default=str)` for serialization — make sure new model fields serialize cleanly
- Keep `openai` as the embedding provider (text-embedding-3-large via `settings.embedding_model`)
- The LLM call in s8 should use `settings.openai_api_key` and model `gpt-4o` (same as current)
- s2 query gen LLM call should also use `gpt-4o` via the existing `_call_openai()` helper

---

## Definition of Done

The pipeline should produce outputs matching the **structure and detail level** of the benchmark files:

1. `gap_report.md` has:
   - Summary with SPA, mean similarities, top gap query IDs
   - Per-query gap briefs (top 10) with citation exemplars including similarity, domain, URL, snippet, structural signal counts, authority type
   - Appendix table with all queries

2. `generation_spec.md` has:
   - Per-cluster specs with word count ranges, required elements, authority signal distributions, structural rates

3. `analysis.json` has:
   - Non-zero proximity_stats
   - Populated gaps list with top_cited_exemplars
   - Populated cluster_specs list
   - Populated spa_results

4. All existing serialized data (analysis.json, enriched_citations.json, queries.json) still loads without errors (backward compatibility).