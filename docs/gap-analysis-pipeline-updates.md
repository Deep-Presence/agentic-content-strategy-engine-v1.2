# Gap Analysis Pipeline — Structural Signal Overhaul

## Context for Claude Code

This document describes a set of critical upgrades to the **Gap Analysis Pipeline** (Steps S4 → S6 → S7 → S8). These changes are required because the downstream **Content Generation Engine (v2.0)** now expects a rich set of structural signals that the gap analysis pipeline does not currently compute. Without these changes, the content engine's planner hallucinate or defaults to 0/empty for missing fields, and half of its structural evaluator checks silently skip.

Read this document fully before planning. Understand the dependency chain. Then make your own implementation plan and execute phase by phase, running tests between phases.

---

## 1. The Root Problem

### 1.1 Full-Page Contamination (Critical)

The `_extract_paragraphs` function in `s4_enrich_citations.py` currently operates on the **entire HTML document** — navigation bars, sidebars, footers, cookie banners, related post widgets, everything. When the pipeline reports `headers=33, lists=276, citations=308` for a blog post, those numbers include global navigation `<li>` items, footer link lists, sidebar CTAs, and so on. The actual article body might have 8 headers, 12 list items, and 5 outbound citations — radically different numbers.

This one flaw cascades through the entire pipeline:
- S6 aggregates these inflated numbers into cluster specs
- S8 prints them in gap briefs and feeds them to the LLM for recommendations
- The content engine's planner receives garbage structural targets
- The structural evaluator checks against meaningless baselines

**This is the single highest-priority fix.** Just isolating the main content before counting would immediately make every downstream step more accurate with zero changes to S6 or S8.

### 1.2 Missing Structural Signal Categories

The current `StructuralSignals` model has approximately 11 fields:

```
word_count, paragraph_count, header_count, list_item_count,
stat_count, citation_count, has_headers, has_lists, has_numbers,
authority_type, content_type
```

The content engine v2.0's expanded `structural_targets` expects 22+ fields including:
- Per-paragraph word counts (avg, max, median)
- Sentence-level metrics (count, avg length, per-paragraph count)
- HTML element detection (FAQ sections, tables, definition lists, code blocks, key takeaways)
- Per-list-block metrics (list_block_count, bullets per list block)
- Content pattern booleans (definition opening, step-by-step, expert quotes, research refs)
- Factual density (data points, citation density per 1k words, self-contained claim ratio)
- Reading level (Flesch-Kincaid)
- Cluster-level aggregates (faq_rate, table_rate, dominant_content_type, exemplar_themes)

### 1.3 Missing Per-Query Content Briefs

S6 computes per-query gap objects and per-cluster specs, but there is no per-query `ContentBrief` that synthesizes the structural signals of the top-cited exemplars for a specific query into actionable writing specifications. This is the missing data contract between the gap analysis pipeline and the content generation engine.

---

## 2. Why These Changes Matter

### For the Content Engine

The content engine v2.0 has a sophisticated structural evaluator running 14 checks (4 hard gates + 10 weighted soft checks). These checks examine paragraph length, sentence length, FAQ presence, table presence, self-contained claims, and bullet density. But they're all gated on fields like `brief.structural_targets.faq_rate` — and since S6 never computes `faq_rate`, the planner has no data to populate this field. It defaults to 0.0, meaning the FAQ check always skips. Same for `table_rate`, `avg_paragraph_word_count`, `avg_sentence_count_per_paragraph`, etc.

### For the Gap Report

The current gap report only gives in-depth analysis for 5-10 queries (markdown readability constraint) while the data for all 100-200 queries exists. With enriched signals and a structured JSON output, we can produce full-depth analysis for every query and present it through an interactive dashboard rather than a static markdown file.

### For Competitive Intelligence

With main-content-scoped signals, we can accurately fingerprint what makes cited content structurally successful and produce genuine competitive comparisons rather than noise-contaminated approximations.

---

## 3. Implementation Phases (Strict Dependency Order)

### Phase 0: Main Content Extraction

**Files to modify:** `s4_enrich_citations.py`
**New dependency:** `trafilatura`
**Impact:** Fixes all existing structural signals immediately

Add a `_extract_main_content(html: str) -> str` function that isolates the article body from the page chrome. This must be called at the top of `_extract_paragraphs` before any counting happens.

**Fallback chain (in priority order):**

```python
import trafilatura
from bs4 import BeautifulSoup

def _extract_main_content(html: str) -> str:
    """Isolate main article content from full page HTML.
    
    Three-tier fallback:
    1. trafilatura (best general-purpose, research-grade extraction)
    2. Semantic HTML tags (<article>, <main>, CMS-specific selectors)
    3. Full page fallback (current behavior, last resort)
    """
    # Tier 1: trafilatura — handles multi-column layouts, CMS markup, embedded widgets
    try:
        main_html = trafilatura.extract(
            html, 
            output_format='html',
            include_tables=True, 
            include_links=True
        )
        if main_html and len(main_html) > 200:
            return main_html
    except Exception:
        pass
    
    # Tier 2: Semantic HTML tags
    soup = BeautifulSoup(html, "html.parser")
    for selector in ["article", "main", '[role="main"]', ".post-content", ".entry-content"]:
        el = soup.select_one(selector)
        if el and len(el.get_text()) > 200:
            return str(el)
    
    # Tier 3: Full page fallback (current behavior)
    return html
```

**Why trafilatura over readability-lxml:** `trafilatura` is designed specifically for web content extraction in research/analysis contexts. It handles edge cases better (multi-column layouts, embedded widgets, CMS-specific markup) and has zero additional system dependencies. It's the right tool for a structural analysis pipeline.

**Integration point:** Call `_extract_main_content(html)` at the very beginning of `_extract_paragraphs`. All downstream parsing (paragraph extraction, header counting, list counting, everything) operates on the cleaned HTML rather than the full page.

**Validation:** After implementing, re-run an existing analysis (e.g., Ramp or Carta) and compare the structural signal numbers. You should see dramatic reductions in header_count, list_item_count, citation_count — numbers that now reflect actual article content rather than full-page chrome.

---

### Phase 1: Enriched StructuralSignals Model

**Files to modify:** 
- Pydantic models file (likely `core/models/gap_analysis.py` or wherever `StructuralSignals` is defined)
- `s4_enrich_citations.py` (extraction logic)

**New dependency:** `textstat` (for Flesch-Kincaid reading level — lightweight, ~15 lines equivalent)

**Design principle:** All new fields must have sensible defaults so existing serialized artifacts don't break on deserialization. Use `Optional[...]` or default values.

Expand `StructuralSignals` from ~11 fields to ~35 fields, organized into four categories:

#### Category A: Text Composition Metrics
```python
main_content_word_count: int = 0           # Word count of isolated main content only
sentence_count: int = 0                     # Total sentences in main content
avg_paragraph_length: float = 0.0           # Mean words per paragraph
median_paragraph_length: float = 0.0        # Median words per paragraph
max_paragraph_word_count: int = 0           # Longest paragraph in words
avg_sentence_length: float = 0.0            # Mean words per sentence
avg_sentence_count_per_paragraph: float = 0.0
reading_level: float = 0.0                  # Flesch-Kincaid grade level
self_contained_ratio: float = 0.0           # Fraction of paragraphs that work as standalone answers
per_paragraph_word_counts: List[int] = []   # Distribution data for S6 aggregation
```

#### Category B: Structural Elements (by level, scoped to main content)
```python
h1_count: int = 0
h2_count: int = 0
h3_count: int = 0
h4_count: int = 0
ordered_list_count: int = 0                 # Signals step-by-step processes
unordered_list_count: int = 0               # Signals feature lists / comparisons
table_count: int = 0
definition_list_count: int = 0              # <dl> elements
blockquote_count: int = 0
code_block_count: int = 0                   # <pre> and/or <code> blocks
list_block_count: int = 0                   # Total distinct list blocks (<ul> + <ol>)
bullets_per_list_block: List[int] = []      # Per-block bullet counts
min_bullets_per_list: int = 0               # Minimum across list blocks
```

#### Category C: Content Pattern Detection (boolean + count)
```python
has_faq_section: bool = False               # Heading patterns "FAQ"/"Frequently Asked" or <details>/<summary>
has_definition_opening: bool = False        # First 100 words contain "X is..." pattern
has_key_takeaways: bool = False             # "Key Takeaway"/"TL;DR"/"Summary" heading patterns
has_toc: bool = False                       # Table of contents detected
has_comparison_table: bool = False          # Table with comparison-like structure
has_step_by_step: bool = False              # Ordered list or "Step N" heading patterns
has_research_refs: bool = False             # Bibliography/references section detected
has_expert_quotes: bool = False             # Blockquotes or attribution patterns
```

#### Category D: Factual Density Metrics
```python
data_point_count: int = 0                   # Numbers with context (%, $, dates, named statistics)
citation_density: float = 0.0               # Outbound links per 1000 words (main content scoped)
named_entity_density: float = 0.0           # Capitalized multi-word phrases (regex heuristic)
```

**Implementation notes for extraction logic:**

1. **Sentence splitting:** Use a simple regex split on `.!?` followed by whitespace and capital letter, or `nltk.sent_tokenize` if already available. Don't add spaCy.

2. **Reading level:** Use `textstat.flesch_kincaid_grade(text)` — it's a lightweight library. Alternatively, implement Flesch-Kincaid directly: `0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59`.

3. **Self-contained ratio:** Count paragraphs of 20-150 words that do NOT start with referential pronouns ("This", "That", "These", "It", "They" when first word) AND contain at least one of: a statistic/number, a named entity, or a definitional statement. Divide by total qualifying paragraphs.

4. **FAQ detection:** `bool(soup.find(string=re.compile(r'FAQ|Frequently Asked', re.I)))` OR presence of `<details>`/`<summary>` elements.

5. **Definition opening:** Check first 100 words of main content for patterns like `"{Topic} is "`, `"{Topic} refers to"`, `"{Topic} are "`.

6. **Data point detection:** Regex for `\d+[%$€£]`, `\$\d+`, `\d{4}` (years), `\d+\.\d+x`, and phrases like "according to", "study shows", "research from".

7. **Named entity density:** Regex heuristic — count capitalized multi-word phrases (2+ consecutive capitalized words not at sentence starts, not common title words like "The", "A", "In"). Divide by total words × 1000. This gives ~80% of NER value at 1% of the complexity.

8. **Per-list-block metrics:** Find each `<ul>` and `<ol>` block separately, count `<li>` children per block. Store as `bullets_per_list_block: List[int]`.

**What NOT to do:**
- Do NOT add spaCy or any heavy NLP library. This is a structural analysis pipeline.
- Do NOT use LLM calls for any signal extraction. Everything here is deterministic.
- Do NOT break existing test fixtures — all new fields must have defaults.

---

### Phase 2: Per-Query ContentBrief + Cluster Aggregates (S6)

**Files to modify:**
- Pydantic models file (add `ContentBrief` model)
- `s6_*.py` (the semantic/structural analysis step — wherever `_compute_cluster_specs` and per-query gap computation live)

**Concept:** For each `QueryGap`, compute a `ContentBrief` that synthesizes the enriched structural signals of that query's top-cited exemplars into ranges and recommendations. This is purely deterministic — no LLM calls.

#### New ContentBrief model:

```python
from typing import Tuple, Dict, Optional, List
from pydantic import BaseModel

class ContentBrief(BaseModel):
    """Synthesized content specification from top-cited exemplars for a query.
    
    Each field is computed as a range or rate from the top-N exemplars.
    This gives the content generation workflow exact numeric targets.
    """
    target_word_count: Tuple[int, int] = (0, 0)          # (min, max) from exemplars
    target_reading_level: Tuple[float, float] = (0.0, 0.0)  # Flesch-Kincaid range
    avg_paragraph_length: Tuple[int, int] = (0, 0)       # Word count range
    recommended_header_count: Tuple[int, int] = (0, 0)
    header_hierarchy: Dict[str, int] = {}                  # {"h2": 5, "h3": 8} median counts
    has_ordered_lists: float = 0.0                         # Rate across exemplars
    has_unordered_lists: float = 0.0
    has_tables: float = 0.0
    has_faq_section: float = 0.0
    has_definition_opening: float = 0.0
    has_key_takeaways: float = 0.0
    has_step_by_step: float = 0.0
    target_data_point_density: float = 0.0                 # Per 1000 words
    target_citation_density: float = 0.0                   # Outbound links per 1000 words
    dominant_authority_type: str = ""
    dominant_content_type: str = ""
    exemplar_count: int = 0
```

#### Expand cluster-level aggregates in `_compute_cluster_specs`:

Currently computes rates for headers, lists, stats, citations. Add:

- **faq_rate:** Count exemplars with `has_faq_section=True` / total exemplars
- **table_rate:** Count exemplars with `table_count > 0` / total
- **definition_rate:** Count exemplars with `has_definition_opening=True` / total  
- **code_block_rate:** Count exemplars with `code_block_count > 0` / total
- **key_takeaways_rate:** Count exemplars with `has_key_takeaways=True` / total
- **avg_word_count:** Mean of exemplar `main_content_word_count` values
- **avg_paragraph_word_count:** Median of exemplar `avg_paragraph_length` values
- **avg_sentence_count_per_paragraph:** Median across exemplars
- **min_bullets_per_list:** Median of exemplar `min_bullets_per_list` values
- **dominant_content_type:** `Counter(content_type values).most_common(1)`
- **dominant_authority_type:** `Counter(authority_type values).most_common(1)`
- **exemplar_themes:** TF-IDF keyword extraction from concatenated exemplar content per cluster (deterministic, no LLM). Extract top-N keywords, filter stop words and generic terms. Output is `List[str]` like `["expense management", "receipt scanning", "compliance automation"]`.

#### ContentBrief computation per QueryGap:

For each query gap, iterate its top-cited exemplars. For numeric fields, compute (min, max) or median across exemplars. For boolean fields, compute the rate (fraction of exemplars that have it). Attach the resulting `ContentBrief` as a new field on the `QueryGap` model:

```python
# On QueryGap model, add:
content_brief: Optional[ContentBrief] = None
```

---

### Phase 3: Three-Tier Output (S7/S8)

**Files to modify:**
- `s7_*.py` (visualization step)
- `s8_*.py` (report generation step)

**Concept:** Separate data from presentation. Currently S8 renders detailed briefs for only 5-10 queries and dumps the rest into an appendix table. This is a markdown readability constraint, not a data constraint.

#### Tier 1: Structured Data Artifact (`gap_analysis_complete.json`)

Full-fidelity JSON with complete analysis for every query. Every `QueryGap` with its `ContentBrief`, every exemplar with enriched structural signals, every cluster spec with distribution data. This is the canonical API contract that the content generation pipeline consumes programmatically. It replaces (or supplements) the current partial `gap_report.json`.

#### Tier 2: Interactive Dashboard (future — do not implement in this PR)

This will be a self-contained HTML/React artifact with query explorer, cluster deep-dive, and exemplar library. **Skip this for now** — the JSON output (Tier 1) is the critical deliverable. The dashboard will be built separately as a frontend feature.

#### Tier 3: Enhanced Executive Summary (markdown)

Update `_build_gap_report_md` to:
1. Include per-query content briefs inline with each gap brief (for ALL queries, not just top 10)
2. Show main-content-scoped metrics instead of full-page metrics for exemplars
3. Include cluster-level structural fingerprints (rates, dominant types, themes)
4. Keep the LLM-generated executive summary and recommendations as-is — the LLM's job is strictly high-level prioritization, not structural analysis

**Key principle:** The structural analysis (content briefs, cluster specs, rates) must be computed deterministically. Do NOT throw these new signals at the LLM and ask it to generate richer recommendations. The LLM in S8 only handles the executive summary and high-level strategic recommendations.

---

## 4. Libraries & Dependencies

| Library | Purpose | Why this one |
|---------|---------|-------------|
| `trafilatura` | Main content extraction from HTML | Research-grade, handles CMS markup, zero system deps, better than readability-lxml for this use case |
| `textstat` | Flesch-Kincaid reading level | Lightweight, single-purpose. Alternative: implement FK formula directly in ~15 lines |
| `scikit-learn` (TfidfVectorizer) | Exemplar theme extraction via TF-IDF | Already likely in your deps for embedding analysis |

**Do NOT add:** spaCy, NLTK (unless already present), or any heavy NLP library. Use regex heuristics for entity density, data point detection, and pattern matching. This keeps the pipeline lightweight and fast.

**Add to requirements.txt / pyproject.toml:**
```
trafilatura>=1.6.0
textstat>=0.7.0
```

---

## 5. File Change Map

| File | Changes |
|------|---------|
| `s4_enrich_citations.py` | Add `_extract_main_content()`, rewrite `_extract_paragraphs()` to use it, add all new signal extraction logic |
| Pydantic models (StructuralSignals) | Expand from ~11 to ~35 fields with defaults |
| Pydantic models (new ContentBrief) | Add new `ContentBrief` model |
| Pydantic models (QueryGap) | Add `content_brief: Optional[ContentBrief] = None` field |
| Pydantic models (ClusterSpec or equivalent) | Add new rate/aggregate fields |
| `s6_*.py` | Expand `_compute_cluster_specs` with new aggregates, add per-query ContentBrief computation |
| `s8_*.py` | Update report rendering to use enriched signals, render content briefs for all queries |
| `requirements.txt` / `pyproject.toml` | Add `trafilatura`, `textstat` |
| Test fixtures | Update with new fields (defaults should handle this, but verify) |

---

## 6. Implementation Order & Validation

**Step 1:** Add `trafilatura` and `textstat` to dependencies. Verify installation.

**Step 2:** Implement `_extract_main_content()` in S4. Write a quick test: pass in a full HTML page from one of your existing analyses (Ramp or Carta), verify the output is the article body only, not nav/footer/sidebar.

**Step 3:** Expand the `StructuralSignals` Pydantic model with all new fields (with defaults). Run existing tests — they should all pass since defaults prevent deserialization breaks.

**Step 4:** Rewrite `_extract_paragraphs` to:
1. Call `_extract_main_content(html)` first
2. Parse the cleaned HTML
3. Extract all new signals (text composition, structural elements, content patterns, factual density)
4. Return the enriched `StructuralSignals`

**Step 5:** Run the pipeline on an existing dataset. Compare old vs new structural signal outputs. Verify that counts like `header_count`, `list_item_count` are now reasonable (single digits to low tens, not hundreds).

**Step 6:** Add `ContentBrief` model. Add `content_brief` field to `QueryGap`.

**Step 7:** Expand `_compute_cluster_specs` with new rate aggregates (faq_rate, table_rate, etc.), dominant types (Counter.most_common), and exemplar themes (TF-IDF).

**Step 8:** Add per-query `ContentBrief` computation in S6. For each QueryGap, iterate top-cited exemplars, compute ranges/rates, attach the brief.

**Step 9:** Update S8 report rendering to use enriched signals and include content briefs.

**Step 10:** Run full pipeline end-to-end. Verify the output JSON contains ContentBriefs for every query. Verify the markdown report has enriched structural data.

---

## 7. What the Content Engine Expects (Downstream Consumer)

For reference, these are the fields the content engine v2.0's planner, outliner, drafter, and structural evaluator expect to receive from the gap analysis output. After these changes, the gap analysis pipeline should populate ALL of them:

### Fields the planner uses to set structural_targets:
- `min_headers`, `min_lists`, `min_citations`, `min_stats`, `min_paragraphs`
- `avg_paragraph_word_count`, `max_paragraph_word_count`
- `avg_sentence_count_per_paragraph`
- `min_self_contained_claims`
- `min_bullets_per_list`
- `faq_rate`, `table_rate`, `definition_rate`, `code_block_rate`
- `has_key_takeaways`
- `dominant_authority_type`, `dominant_content_type`
- `avg_word_count`
- `exemplar_themes`

### Structural evaluator checks that depend on these fields:
- `_check_faq_presence` → needs `faq_rate`
- `_check_table_presence` → needs `table_rate`
- `_check_paragraph_length` → needs `avg_paragraph_word_count`, `max_paragraph_word_count`
- `_check_sentence_length` → needs `avg_sentence_count_per_paragraph`
- `_check_self_contained_claims` → needs `min_self_contained_claims`
- `_check_bullet_density` → needs `min_bullets_per_list`

If any of these fields are missing or 0, the corresponding evaluator check silently skips — defeating the purpose of the content engine v2.0 upgrade.

---

## 8. Constraints & Anti-Patterns

1. **No LLM calls for structural analysis.** All signal extraction and content brief computation must be deterministic. The only LLM use in this pipeline is S8's executive summary and S4's existing citation enrichment.

2. **No heavy NLP libraries.** Use regex heuristics for entity density and pattern detection. Use `textstat` for reading level. BeautifulSoup for HTML parsing.

3. **Backward compatibility.** All new Pydantic fields must have defaults. Existing serialized artifacts must deserialize without errors. Existing tests must pass before any new test logic is added.

4. **Main content extraction is non-negotiable.** Do not skip Phase 0 or implement it partially. Every metric computed on full-page HTML is actively harmful — it's worse than not having the metric at all because it creates false confidence.

5. **Keep `_extract_paragraphs` return signature compatible** or update all callers. If you change it to return additional data (like `ContentProfile` with paragraph-level distributions), make sure S6 and any other consumers are updated.

6. **trafilatura's `output_format='html'` is essential.** You need the HTML structure preserved (not just plain text) because you're counting HTML elements like `<table>`, `<ol>`, `<dl>`, `<details>`, etc. Plain text extraction would lose this information.
