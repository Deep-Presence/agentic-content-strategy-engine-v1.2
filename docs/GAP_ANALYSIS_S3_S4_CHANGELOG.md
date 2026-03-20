# Gap Analysis S3 & S4 — Optimization Changelog

> Covers all changes from initial implementation (`98da1d9`, 2026-02-13) through the current state on `research-agent-v1.2.0`.

---

## Timeline

| Date | Commit | Summary |
|------|--------|---------|
| 2026-02-13 | `98da1d9` | Initial repo restructure — baseline s3/s4/engines |
| 2026-02-14 | `3bcc310` | Pipeline improvisation checkpoint |
| 2026-02-15 | `8e39b04` | **Async-first conversion** — s4 rewritten, engines rewritten |
| 2026-02-20 | `0b78f89` | Misc fixes |
| 2026-03-07 | `9b747d2` | Self-citation detection, company page structural analysis |

---

## S3 — Search Platforms (`core/gap_analysis/steps/s3_search_platforms.py`)

### Architecture (introduced in `8e39b04`, refined through `9b747d2`)

The s3 orchestrator was designed from the start as async with two-level throttling. The major changes were in the **engines** it calls and the **settings** that govern concurrency.

#### Two-Level Concurrency Model

```
Global Semaphore (30)
├── OpenAI Engine Semaphore (12)
│   └── 150 queries → ~13 waves
├── Claude Engine Semaphore (6)
│   └── 150 queries → ~25 waves
├── Gemini Engine Semaphore (10)
│   └── 150 queries → ~15 waves
└── Perplexity Engine Semaphore (8)
    └── 150 queries → ~19 waves
```

- **Global semaphore** caps total in-flight requests across all engines at `30`
- **Per-engine semaphores** prevent overloading individual providers
- All engine batches run in parallel via `asyncio.gather()`
- Results are sorted deterministically by `(query_id, engine)` to ensure stable URL dedup in s4

#### Settings Added (`core/config/settings.py`)

All configurable via environment variables:

```python
gap_analysis_s3_global_concurrency: int = 30
gap_analysis_s3_concurrency_default: int = 8
gap_analysis_s3_openai_concurrency: int = 12
gap_analysis_s3_claude_concurrency: int = 6
gap_analysis_s3_gemini_concurrency: int = 10
gap_analysis_s3_perplexity_concurrency: int = 8
```

#### Shared Client Connection Pooling

Each engine batch creates a single shared client for the batch lifetime:

| Engine | Client Type | Connection Limits |
|--------|------------|-------------------|
| Claude | `httpx.AsyncClient(timeout=90)` | `max_connections=6, max_keepalive_connections=6` |
| Gemini | `httpx.AsyncClient(timeout=90)` | `max_connections=10, max_keepalive_connections=10` |
| OpenAI | `AsyncOpenAI()` | SDK defaults |
| Perplexity | `AsyncPerplexity()` | SDK defaults |

#### Error Handling

- Individual query failures are caught in `_run_one()` and returned as `PlatformResult` with `response_text="ERROR: {exc}"` — they do not crash the batch.
- Entire engine batch failures (from `asyncio.gather`) are logged and skipped.

---

## Engine Rewrites (`core/gap_analysis/engines/`)

### Claude Engine (`claude.py`) — Full Rewrite in `8e39b04`

**Before (baseline):**
- Sync `anthropic.Anthropic` SDK wrapped in `asyncio.to_thread()`
- Hardcoded model: `claude-3-5-sonnet-20240620`
- `max_tokens=1024`
- Fallback: if web search tool failed, re-called without tools (silently lost search context)
- Citation extraction: via Python `getattr()` on SDK response objects
- No URL validation, no dedup

**After:**
- Direct async HTTP via `httpx.AsyncClient(timeout=90)` — eliminates `asyncio.to_thread()` overhead
- Configurable model via `settings.gap_analysis_claude_engine_model` (default: `claude-sonnet-4-5-20250929`)
- `max_tokens=4096` — allows longer, more detailed responses
- Uses `web_search_20250305` beta tool with `max_uses=5`
- System prompt added: *"You are a helpful research assistant. Search the web to answer queries accurately. Always cite your sources."*
- Citation extraction rewritten as `_extract_claude_output_from_json()`:
  - Parses raw JSON `dict` instead of SDK objects
  - Deduplicates URLs with a `seen` set
  - Handles nested `search_results` in `tool_result` blocks
  - `_safe_url()` validates URL format before creating `CitationRef`
- Structured error logging with query ID context
- Removed fallback-without-tools path (no longer silently degrades)

### Gemini Engine (`gemini.py`) — Full Rewrite in `8e39b04`

**Before (baseline):**
- Sync `google.genai.Client` wrapped in `asyncio.to_thread()`
- Hardcoded model: `gemini-2.0-flash`
- Citation extraction via `getattr(chunk, "url")` / `getattr(chunk.web, "uri")`
- No URL validation

**After:**
- Direct async HTTP via `httpx.AsyncClient(timeout=90)` to `generativelanguage.googleapis.com/v1beta`
- Configurable model via `settings.gap_analysis_gemini_engine_model` (default: `gemini-3-flash-preview`)
- `maxOutputTokens=4096`, `temperature=0` for deterministic output
- System instruction added via `systemInstruction` field
- Uses `google_search` tool (grounded search)
- Citation extraction rewritten as `_parse_gemini_response()`:
  - Parses `groundingMetadata.groundingChunks[].web.uri`
  - Handles Vertex AI redirect URLs (`vertexaisearch.cloud.google.com`)
  - Deduplicates with `seen` set
  - `_safe_url()` validates URL format
- Structured error logging with query ID context

### OpenAI Engine (`openai_engine.py`) — Enhanced in `8e39b04`

**Before (baseline):**
- Model: hardcoded `gpt-4o`
- Simple `client.responses.create(input=query_text, tools=[{"type": "web_search"}])`
- Fallback: `client.chat.completions.create()` (different API surface entirely)

**After:**
- Configurable model via `settings.gap_analysis_openai_engine_model` (default: `gpt-5.2-2025-12-11`)
- Enhanced API call:
  - `reasoning={"effort": "low"}` — reduces latency
  - `max_output_tokens=4096`
  - `tool_choice={"type": "web_search"}` — forces web search usage
  - `include=["web_search_call.action.sources"]` — ensures sources are returned
  - System message added for research assistant behavior
- Fallback simplified: uses `client.responses.create()` with plain input (same API surface)
- Still uses `asyncio.to_thread()` (SDK is sync-only)

### Perplexity Engine (`perplexity.py`) — Minor Enhancement in `8e39b04`

- Added system message: *"You are a helpful research assistant. Provide accurate, well-researched answers with citations to your sources."*
- Model unchanged (`sonar-pro`)
- Still uses `asyncio.to_thread()` (SDK is sync-only)

### Model Configuration Centralization

Settings added to centralize model selection across all engines:

```python
gap_analysis_query_gen_model: str = "gpt-5.2-2025-12-11"
gap_analysis_report_model: str = "gpt-5.2-2025-12-11"
gap_analysis_openai_engine_model: str = "gpt-5.2-2025-12-11"
gap_analysis_claude_engine_model: str = "claude-sonnet-4-5-20250929"
gap_analysis_gemini_engine_model: str = "gemini-3-flash-preview"
```

---

## S4 — Enrich Citations (`core/gap_analysis/steps/s4_enrich_citations.py`)

### Phase 1: Async-First Conversion (`8e39b04`)

**Before (baseline):**
- `_fetch_html()` was **synchronous** — `httpx.Client(timeout=20)`, blocking
- `enrich_citations()` was **synchronous** — fetched URLs sequentially in a loop
- No URL deduplication (fetched same URL multiple times if cited by multiple engines)
- No content-type checking (tried to parse PDFs/images as HTML)
- `_extract_paragraphs()` returned 4 basic signals: `word_count`, `has_headers`, `has_lists`, `has_numbers`

**After:**
- `_fetch_html()` rewritten as **async** — `httpx.AsyncClient` with optional semaphore
- Returns `Tuple[html, resolved_url]` — tracks redirect destinations (critical for Vertex AI Search URLs)
- Content-type guard: skips non-HTML responses
- `enrich_citations()` rewritten as **async**:
  1. **Dedup pass**: collects unique URLs from all platform results
  2. **Concurrent fetch**: `asyncio.gather()` with shared `httpx.AsyncClient` and semaphore
  3. **Enrich pass**: processes fetched HTML in order, builds `EnrichedCitation` objects
- Connection pooling: `httpx.Limits(max_connections=30, max_keepalive_connections=10)`
- Redirect resolution: Vertex AI Search wrapper URLs (`vertexaisearch.cloud.google.com`) are resolved to actual destinations

#### Concurrency Settings Added

```python
gap_analysis_s4_fetch_concurrency: int = 40    # Max concurrent HTTP requests
gap_analysis_s4_parse_workers: int = 16         # Thread pool for HTML parsing
gap_analysis_s4_http_pool_size: int = 50        # httpx connection pool
```

### Phase 2: Structural Intelligence Upgrade (`9b747d2`)

The `_extract_paragraphs()` function was massively expanded from ~15 lines to ~200 lines. Original 4 signals expanded to **~45 signals across 4 categories**.

#### Content Extraction Pipeline

Three-tier HTML processing was introduced:

```
Raw HTML
├── _extract_main_content()     → best text for paragraph extraction
│   ├── Tier 1: trafilatura     (research-grade boilerplate removal)
│   ├── Tier 2: BS4 semantic    (article/main/[role=main]/.post-content)
│   └── Tier 3: full page       (fallback)
│
└── _extract_structural_html()  → preserved HTML for element counting
    ├── BS4 semantic selectors
    └── Full page fallback
    (trafilatura intentionally excluded — it flattens ol/dl/table/details)
```

**Why two extraction paths?** Trafilatura produces the best paragraph text (strips nav, footer, sidebar) but destroys structural HTML elements. Structural element counting (lists, tables, code blocks) needs the raw HTML structure preserved.

#### Signal Categories

**Category A — Text Composition (10 new fields):**
- `main_content_word_count`, `sentence_count`
- `avg_paragraph_length`, `median_paragraph_length`, `max_paragraph_word_count`
- `avg_sentence_length`, `avg_sentence_count_per_paragraph`
- `reading_level` (Flesch-Kincaid via `textstat`)
- `self_contained_ratio` — fraction of paragraphs that are self-contained (20-150 words, no referential opening, contains fact/definition)
- `per_paragraph_word_counts` — raw list for downstream analysis

**Category B — Structural Elements (13 new fields):**
- `h1_count`, `h2_count`, `h3_count`, `h4_count`
- `ordered_list_count`, `unordered_list_count`
- `table_count`, `definition_list_count`, `blockquote_count`, `code_block_count`
- `list_block_count`, `bullets_per_list_block`, `min_bullets_per_list`

**Category C — Content Patterns (8 new fields):**
- `has_faq_section` — FAQ heading OR `<details>` OR `<dl>` tags
- `has_definition_opening` — starts with "[Term] is/are/refers to"
- `has_key_takeaways` — "key takeaway", "tl;dr", "summary", "highlights"
- `has_toc` — "table of contents" OR `.toc` nav element
- `has_comparison_table` — table with "vs", "compare", "feature", "pricing" headers
- `has_step_by_step` — "step-by-step", "how to", ordered list with step numbering
- `has_research_refs` — "according to", "research shows", "study finds"
- `has_expert_quotes` — `<blockquote>` + "says/said/according to [Name]"

**Category D — Factual Density (3 new fields):**
- `data_point_count` — percentage figures, dollar amounts, year references
- `citation_density` — links per 1000 words
- `named_entity_density` — capitalized multi-word phrases per 1000 words

#### Helper Functions Added

| Function | Purpose |
|----------|---------|
| `_extract_main_content()` | Three-tier boilerplate removal (trafilatura → BS4 → full page) |
| `_extract_structural_html()` | Semantic scoping preserving structural elements |
| `_split_sentences()` | English regex sentence splitter |
| `_safe_float()` | NaN/inf guard for computed ratios |
| `_compute_self_contained_ratio()` | AEO-relevant paragraph quality metric |
| `_detect_content_patterns()` | 8-boolean content pattern detection from HTML + text |
| `_compute_factual_density()` | Data points, citation density, named entity density |

### Phase 3: Self-Citation Detection (`9b747d2`)

Added `is_company_citation` propagation through s4:

- `EnrichedCitation.is_company_citation` field added (default `False`)
- During enrichment, citations already flagged in s3 (via `_flag_company_citations()` in pipeline.py) retain their `is_company_citation=True` flag
- Downstream: s6 uses this to populate `QueryGap.company_cited` and `QueryGap.company_cited_platforms`

---

## Crawl Settings Upgrade

```python
# Before
gap_analysis_max_crawl_pages: int = 50
gap_analysis_max_crawl_depth: int = 2

# After
gap_analysis_max_crawl_pages: int = 500
gap_analysis_max_crawl_depth: int = 4
```

10x increase in crawl scope (s1) means s4 processes richer company asset context.

---

## StructuralSignals Model Growth (`core/models/gap_analysis.py`)

The `StructuralSignals` Pydantic model grew from **4 fields** to **45 fields** across these changes:

| Phase | Fields | Total |
|-------|--------|-------|
| Baseline (`98da1d9`) | `word_count`, `has_headers`, `has_lists`, `has_numbers` | 4 |
| Async-first (`8e39b04`) | + `paragraph_count`, `header_count`, `list_item_count`, `stat_count`, `citation_count`, `authority_type`, `content_type` | 11 |
| Structural intelligence (`9b747d2`) | + 10 text composition + 13 structural elements + 8 content patterns + 3 factual density | 45 |

All new fields have defaults (`0`, `0.0`, `False`, `[]`) for backward compatibility with existing JSON artifacts.

---

## Performance Impact Summary

| Aspect | Before | After | Impact |
|--------|--------|-------|--------|
| s4 fetch model | Sync sequential | Async concurrent (40 slots) | ~10-20x faster for URL fetching |
| s4 URL dedup | None | Set-based dedup | Eliminates redundant fetches (typically 30-50% savings) |
| Engine HTTP | Sync SDK + `to_thread` (Claude, Gemini) | Direct async httpx | Eliminates thread pool overhead |
| Connection reuse | New client per request | Shared client per engine batch | Reduces TCP handshake overhead |
| Content extraction | BS4 only | trafilatura + BS4 dual-path | Better text quality, preserved structure |
| Structural signals | 4 fields | 45 fields | Richer downstream analysis (s6, content engine) |
| Crawl scope | 50 pages / depth 2 | 500 pages / depth 4 | Much richer company asset context |

---

## Known Limitations (as of 2026-03-13)

1. **No per-call timeout on OpenAI/Perplexity engines** — relies on SDK defaults, can hang
2. **No retry logic** — transient failures (429, 5xx) are terminal
3. **No exponential backoff** — rate limit headers ignored
4. **No circuit breaker** — a failing engine still processes all 150 queries
5. **Perplexity engine still sync** — uses `asyncio.to_thread()` (SDK limitation)
6. **OpenAI engine still sync** — uses `asyncio.to_thread()` (SDK limitation)
