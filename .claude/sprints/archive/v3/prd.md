# Sprint v3 — Site Audit P3 Bug Fixes

**Date:** 2026-03-04
**Branch:** `feat/front-back`
**Goal:** Fix 9 P3 bugs from the combined manual + Codex review (T-SA-25 dropped — already resolved).

---

## Context

These bugs were identified during v2 sprint's combined manual + Codex (gpt-5.3-codex) code review but deferred as P3. They affect audit accuracy, AEO scoring, crawl deduplication, and API robustness — directly impacting the quality of recommendations clients (Ramp, Carta, Mynd) receive.

**Codex review:** Plan reviewed by gpt-5.3-codex (229,077 tokens, high reasoning effort). 14 findings — 4 critical, 7 high, 3 medium. All critical and high findings incorporated. See Codex Review section at bottom.

---

## Implementation Order (reordered per Codex F-11: low-risk first, high-blast-radius last)

### Fix 1: T-SA-32 — Integration test artifact isolation
**Files:** `tests/core/test_site_audit/test_integration.py`, `core/site_audit/pipeline.py`
**Client impact:** None (internal quality). Do first to prevent test pollution during subsequent fixes.

**Changes (per Codex F-9):**
- Add `output_dir: Path | None = None` parameter to `run_site_audit()` in `pipeline.py` (default `None` preserves current behavior)
- When `output_dir` is None, compute as before: `Path("artifacts") / "site_audit" / effective_slug / audit_id`
- When provided, use it directly
- In `test_full_pipeline_with_mock_discovery()`, pass `output_dir=tmp_path` — real end-to-end coverage preserved, no mocking of `generate_report`
- **Tests:** 1 modified test + 1 new test (verify tmp_path used, verify default path unchanged)

### Fix 2: T-SA-31 — AuditConfig `__post_init__` validation
**Files:** `core/site_audit/config.py`
**Client impact:** API users who pass invalid configs get silently wrong results.

**Changes (per Codex F-7 — `ValueError` not assertions):**
- Add `__post_init__(self)` using `object.__setattr__()` pattern (frozen dataclass):
  1. `abs(sum(weights.values()) - 1.0) < 0.01` → `ValueError("dimension_weights must sum to 1.0")`
  2. Required grades A, B, C, D present → `ValueError("missing required grade")`
  3. Grade thresholds monotonically decreasing: A >= B >= C >= D → `ValueError`
  4. `title_min_length <= title_max_length` → `ValueError`
  5. `meta_min_length <= meta_max_length` → `ValueError`
  6. All severity penalties >= 0 → `ValueError`
  7. `0.0 <= aeo_min_question_heading_ratio <= 1.0` → `ValueError`
  8. `aeo_ideal_paragraph_word_count_min <= aeo_ideal_paragraph_word_count_max` → `ValueError`
- All `__post_init__` checks use explicit `raise ValueError(...)`, NOT assertions (assertions disabled under `-O`)
- **Tests:** 11 new in new file `tests/core/test_site_audit/test_config_validation.py` (separate from existing `test_config.py`)

### Fix 3: T-SA-23 — Robust date parsing in `check_freshness()`
**Files:** `core/site_audit/checks/eeat_signals.py`, `pyproject.toml`
**Client impact:** Freshness dimension (5% weight) produces wrong results for non-standard date formats.

**Changes (per Codex F-1 — fix in check layer, not extraction layer; per F-5 — explicit dep; per F-14 — input guards):**
- `_extract_freshness()` in `s2_analyze_pages.py` is LEFT UNCHANGED — it correctly extracts raw date strings
- Add `_parse_date_robust(date_str: str) -> datetime | None` helper in `eeat_signals.py`:
  1. **Guard:** reject strings > 100 chars (prevents DoS via fuzzy parser — Codex F-14)
  2. Try `dateutil.parser.isoparse(date_str)` first (ISO 8601 with timezones, `Z`, fractional seconds)
  3. Fallback to `dateutil.parser.parse(date_str, fuzzy=False)` for human-readable ("January 15, 2024")
  4. If both fail, return `None`
  5. Normalize timezone-naive results to UTC
- Replace the 4-format `strptime` loop (lines 78-90) and the `[:len(fmt)+6]` hack with `_parse_date_robust()`
- Add `python-dateutil>=2.9,<3` to `pyproject.toml` dependencies (explicit, pinned — Codex F-5)
- **Tests:** 8 new in `TestRobustDateParsing` class in `test_checks.py`:
  - ISO 8601 with `+05:30` timezone offset → parsed, finding generated if stale
  - ISO 8601 with `Z` suffix → parsed correctly
  - ISO 8601 with fractional seconds `2024-01-15T10:30:00.123456Z` → parsed
  - Human-readable `"January 15, 2024"` → parsed
  - Human-readable `"15 Jan 2024"` → parsed
  - Invalid date `"not-a-date"` → no findings (graceful skip)
  - Oversized string (>100 chars) → no findings (guard)
  - Partial date `"2024-01"` → parsed as first of month

### Fix 4: T-SA-24 — Missing date metadata finding (article pages only)
**Files:** `core/site_audit/checks/eeat_signals.py`, `core/site_audit/steps/s2_analyze_pages.py`
**Client impact:** Article pages without ANY date metadata silently pass freshness checks.

**Changes (per Codex F-3 — gate on page type, NOT all pages):**
- Add `page_type: str = "page"` parameter to `check_freshness()` signature (backward-compatible default)
- At the early return (line 73-74), when `best_date_str is None` AND `page_type == "article"`:
  - Generate a `low` severity finding `missing_date_metadata` with recommendation to add article:published_time
- Non-article pages (homepage, product, pricing, etc.) → no finding (current behavior preserved)
- Wire in `s2_analyze_pages.py`: pass `page_type=infer_page_type(url, html)` to `check_freshness()`
- **Tests:** 5 new (per Codex F-10 baseline):
  - Article page with no dates → `missing_date_metadata` finding generated
  - Homepage with no dates → no finding
  - Product page with no dates → no finding
  - Article page WITH dates → no `missing_date_metadata` finding
  - Default `page_type="page"` → no finding (backward compat)

### Fix 5: T-SA-29 — Question-heading classifier expansion
**Files:** `core/site_audit/checks/extractability.py`
**Client impact:** AEO score (extractability, 20% weight) under-reported for "How to..." style headings.

**Changes (per Codex F-12 — guard heuristics to prevent overclassification):**
- **Expand `_QUESTION_START_WORDS`:** Add `"have"`, `"has"`, `"could"`, `"would"`, `"might"`, `"may"`, `"did"`, `"was"`, `"were"`
- **Expand `_COMPARISON_PATTERNS`:** Add `r"\bvs\.\b"`, `r"\bpros and cons\b"`, `r"\bcomparison\b"`
- **Add Rule 3:** Question-word-starting headings WITHOUT trailing `?`:
  - ONLY for 7 core wh-words: `what`, `how`, `why`, `when`, `where`, `who`, `which`
  - NOT for auxiliaries (`is`, `can`, `does`, `should`, `will`, `do`, `have`, `has`, `could`, `would`, `might`, `may`, `did`, `was`, `were`, `are`) — these require `?` to avoid false positives
  - **Guard heuristic (Codex F-12):** Heading must have >= 4 words to qualify without `?` (filters out fragment headings like "How" or "What Now")
- **Tests:** 10 new in `test_aeo.py`:
  - "How to deploy your app" (no `?`, 5 words) → True
  - "What makes a great leader" (no `?`, 5 words) → True
  - "Why content matters for AI" (no `?`, 5 words) → True
  - "Where to find resources" (no `?`, 4 words) → True
  - "How" (no `?`, 1 word) → False (guard: < 4 words)
  - "Is your team ready for growth" (no `?`, auxiliary) → False
  - "Can we help you" (no `?`, auxiliary) → False
  - "Have you considered this?" (with `?`, new word) → True
  - "Ramp vs. Brex" (period in vs.) → True
  - "Pros and cons of equity management" → True

### Fix 6: T-SA-30 — Quick-answer hook window expansion
**Files:** `core/site_audit/checks/extractability.py`, `core/site_audit/config.py`, `core/site_audit/steps/s4_check_aeo.py`
**Client impact:** AEO quick-answer hook ratio drastically under-reported (25 of 100 AEO points).

**Changes (per Codex F-13 — bound search to heading boundary):**
- **Add config fields** to `AuditConfig` (backward-compatible defaults):
  - `aeo_quick_answer_min_words: int = 15`
  - `aeo_quick_answer_max_words: int = 150`
- **Update `detect_quick_answer_hook()` signature:** add `config: AuditConfig = DEFAULT_AUDIT_CONFIG`
- **Behavior changes:**
  1. Use `config.aeo_quick_answer_min_words` / `config.aeo_quick_answer_max_words` instead of hardcoded 30/70
  2. **Don't stop at first non-matching `<p>`** — continue searching (remove early `return False` at line 159)
  3. **Search inside nested containers:** check ALL `<p>` elements inside `<div>/<section>/<article>`, not just first
  4. **Bound search (Codex F-13):** stop at next heading element (`h1`-`h6`) — prevents matching unrelated paragraphs in the next section
  5. Expand sibling window from 3 to 5 (CMS wrapper divs consume slots)
- Update caller in `s4_check_aeo.py` to pass config
- **Tests:** 8 new + 2 modified in `test_aeo.py`:
  - Short answer (20 words) → True (was False with old 30-70)
  - Long answer (120 words) → True (was False with old 30-70)
  - Answer in nested div > div > p → True
  - Multiple paragraphs: first too short, second qualifying → True
  - Stops at next heading → False (bounded)
  - Answer beyond 5 siblings → False (window limit)
  - Custom config with old range (30-70) → backward compat
  - 2 existing tests updated for new word range defaults

### Fix 7: T-SA-26 — Product and Speakable schema validators
**Files:** `core/site_audit/checks/schema_checks.py`
**Client impact:** E-commerce clients get false "schema OK" for Product pages. Speakable errors unreported.

**Changes (per Codex F-8 — support `SpeakableSpecification` alias, conservative severities):**
- Add `validate_product_schema(block: dict[str, Any]) -> list[str]`:
  - Required: `name` → error
  - Required: `offers` OR (`price` AND `priceCurrency`) → error "missing pricing information"
  - Recommended: `description` → warning, `image` → warning, `brand` → warning, `sku` → warning
- Add `validate_speakable_schema(block: dict[str, Any]) -> list[str]`:
  - Required: `cssSelector` OR `xpath` → error "missing content selector"
  - Recommended: `name` → warning
- Update `validate_schema_block()` dispatcher:
  - `elif t == "Product":` → `validate_product_schema(block)`
  - `elif t in ("Speakable", "SpeakableSpecification"):` → `validate_speakable_schema(block)` (Codex F-8: support both canonical names)
- Update `KNOWN_SCHEMA_TYPES`: add `"SpeakableSpecification"` alongside existing `"Speakable"`
- **Tests:** 16 new in `test_schema.py`:
  - `TestValidateProductSchema` (8): valid, missing name, missing offers+price, offers present, price+currency present, missing description (warning), missing image (warning), brand+sku warnings
  - `TestValidateSpeakableSchema` (5): valid with cssSelector, valid with xpath, missing both selectors, SpeakableSpecification type, missing name (warning)
  - `TestValidateSchemaBlockDispatch` (3): dispatcher routes Product, routes Speakable, routes SpeakableSpecification

### Fix 8: T-SA-27 — URL normalization improvements
**Files:** `core/site_audit/steps/s1_discover.py`
**Client impact:** Duplicate pages inflate page count and skew scoring.

**Changes (per Codex F-4 — split canonical key from request URL):**
- **New function** `canonical_url(url: str) -> str` — full normalization for deduplication ONLY:
  1. Everything `normalize_url()` already does (lowercase, strip fragment, trailing slash)
  2. Sort query parameters: `parse_qsl(keep_blank_values=True)` → `sorted()` → `urlencode()`
  3. Strip www prefix via existing `_strip_www()`
  4. Remove default ports (`:443` for HTTPS, `:80` for HTTP)
  5. Normalize percent-encoding
- **Keep `normalize_url()` as-is** — it is used for request URLs and must preserve param order for signed URLs
- **Update `_enqueue()`**: use `canonical_url()` for `_depth_map` / `_visited` / `_discovered` keys
- **Update `_extract_links()`**: use `canonical_url()` for dedup set, but return `normalize_url()` URLs for fetching
- **Tests:** 8 new in `test_crawler.py`:
  - Query params sorted in canonical key
  - www stripped in canonical key
  - Default port removed (HTTPS :443)
  - Default port removed (HTTP :80)
  - Non-default port preserved (:8080)
  - Percent-encoding normalized
  - normalize_url() preserves query param order (regression)
  - Combined: all normalizations applied

### Fix 9: T-SA-28 — Crawl-delay parsing and reporting
**Files:** `core/site_audit/steps/s1_discover.py`, `core/models/site_audit.py`, `core/site_audit/pipeline.py`
**Client impact:** Clients unaware their robots.txt throttles AI bots.

**Changes (per Codex F-6 — cap delay, no enforcement this sprint):**
- **Scope clarification:** This fix is PARSE + REPORT only. Actual crawl-delay enforcement (rate limiting) is deferred — it requires a shared domain-level rate limiter (`asyncio.Lock` + timestamp) which is a separate feature.
- Add `_parse_crawl_delay(raw_robots: str) -> float | None` in `s1_discover.py`:
  - Parse `Crawl-delay:` directive for `User-agent: *` block
  - Regex: `r"(?:^|\n)\s*Crawl-delay:\s*(\d+\.?\d*)"` (case-insensitive)
  - Cap at `300.0` seconds (Codex F-14: prevent unbounded values)
  - Return None if not found
- Add `crawl_delay_seconds: float | None = None` to `AIBotAccessResult` model (backward-compatible)
- Wire in `_parse_ai_bot_access()`: call `_parse_crawl_delay()` and set field
- Generate crawlability findings in pipeline: `crawl_delay_high` (info, >10s), `crawl_delay_excessive` (medium, >30s)
- **Tests:** 10 new in `test_crawler.py` (per Codex F-10 baseline):
  - Crawl-delay: 5 parsed correctly
  - Crawl-delay with decimal (2.5)
  - No Crawl-delay → None
  - Multiple User-agent blocks → extracts `*` default
  - Crawl-delay: 500 → capped at 300
  - Crawl-delay: 5 → no finding
  - Crawl-delay: 15 → info finding
  - Crawl-delay: 45 → medium finding
  - AIBotAccessResult with crawl_delay field JSON roundtrip
  - Missing robots.txt → None

---

## T-SA-25: DROPPED (per Codex F-2)

Title/meta thresholds are already configurable via `AuditConfig` (`config.py:111-114`) and consumed by `check_title()` / `check_meta_description()`. The boilerplate list (`_BOILERPLATE_TITLES`) is a minor cosmetic issue — not worth the churn of adding a frozen set field to AuditConfig. Marking as resolved/won't-fix.

---

## Decisions for Aryan

### D1: T-SA-29 — Question-heading classification without `?`
**What:** Classify wh-word headings ("How to deploy...", "What makes...") as questions even without trailing `?`.
**Scope:** Only 7 core wh-words (what/how/why/when/where/who/which), NOT auxiliary verbs. Minimum 4 words guard to prevent fragment false positives.
**Impact:** AEO scores increase for well-structured content. This is correct — AI engines DO extract "How to..." headings as Q&A.
**Reversible:** Yes — remove Rule 3 from `classify_heading_as_question()`.

### D2: T-SA-30 — Quick-answer word range 15-150
**What:** Expand from 30-70 words to 15-150 words (configurable via `AuditConfig`).
**Why:** FAQ answers often 15-30 words, detailed answers 70-150. Current range misses both.
**Impact:** Quick-answer hook ratio increases → higher AEO scores for qualifying content.
**Reversible:** Yes — config fields allow reverting to any range.

### D3: T-SA-24 — Missing date finding for article pages only
**What:** Generate `low` severity finding when article pages lack date metadata.
**Scope:** Only `article` page type (blog/, posts/, articles/ paths). Homepage, product, pricing, etc. unaffected.
**Impact:** Slight freshness decrease for undated articles. Correct behavior — AI models deprioritize undated articles.
**Reversible:** Yes — remove the finding generation block.

### D4: T-SA-28 — Crawl-delay: parse+report only, no enforcement
**What:** Parse and report Crawl-delay from robots.txt. Defer actual rate-limiting enforcement.
**Findings:** `info` for >10s, `medium` for >30s.
**Impact:** Informational for clients — they see if their robots.txt throttles bots.
**Alternative:** Pure data (no findings, just the field on AIBotAccessResult).
**Reversible:** Yes.

### D5: T-SA-27 — Split canonical key from request URL (Codex F-4)
**What:** Create separate `canonical_url()` for deduplication (sorts params, strips www, removes default ports) while keeping `normalize_url()` unchanged for actual HTTP requests.
**Why:** Sorting query params in the request URL can break signed URLs and parameter-order-sensitive endpoints.
**Impact:** Better deduplication without breaking fetches.
**Reversible:** Yes.

---

## Codex Review (gpt-5.3-codex, 229,077 tokens)

| Finding | Severity | Action | Description |
|---------|----------|--------|-------------|
| F-1 | CRITICAL | **INCORPORATED** | Date parsing fix targeted wrong layer. Fixed: `_parse_date_robust()` goes in `check_freshness()` (check layer), not `_extract_freshness()` (extraction layer). |
| F-2 | CRITICAL | **INCORPORATED** | T-SA-25 already resolved. Dropped from plan. |
| F-3 | CRITICAL | **INCORPORATED** | Missing-date finding would over-penalize non-articles. Fixed: gated on `page_type == "article"` only. |
| F-4 | CRITICAL | **INCORPORATED** | Query param sorting in `normalize_url()` breaks signed URLs. Fixed: split into `canonical_url()` for dedup, `normalize_url()` unchanged for requests. |
| F-5 | HIGH | **INCORPORATED** | python-dateutil pinned as explicit dep `>=2.9,<3`. |
| F-6 | HIGH | **INCORPORATED** | Crawl-delay enforcement deferred. This sprint: parse+report only, cap at 300s. |
| F-7 | HIGH | **INCORPORATED** | `ValueError` not assertions. Already in plan, clarified. |
| F-8 | HIGH | **INCORPORATED** | Support `SpeakableSpecification` as type alias. Added to KNOWN_SCHEMA_TYPES and dispatcher. |
| F-9 | HIGH | **INCORPORATED** | Add `output_dir` param to `run_site_audit()` instead of mocking `generate_report`. |
| F-10 | HIGH | **INCORPORATED** | Test counts refined per Codex baseline. |
| F-11 | HIGH | **INCORPORATED** | Implementation reordered: test isolation first, then validation, then scoring changes, then crawler last. |
| F-12 | MEDIUM | **INCORPORATED** | Guard heuristic: >= 4 words required for question-word headings without `?`. |
| F-13 | MEDIUM | **INCORPORATED** | Quick-answer search stops at next heading element (h1-h6 boundary). |
| F-14 | MEDIUM | **INCORPORATED** | Input guards: max 100 char date strings, capped 300s crawl-delay. |

---

## Summary

| Fix | Bug ID | Files Changed | New Tests | Client Impact |
|-----|--------|--------------|-----------|---------------|
| 1 | T-SA-32 | test_integration.py, pipeline.py | 2 | None (test hygiene) |
| 2 | T-SA-31 | config.py | 11 | MEDIUM — API safety |
| 3 | T-SA-23 | eeat_signals.py, pyproject.toml | 8 | HIGH — freshness accuracy |
| 4 | T-SA-24 | eeat_signals.py, s2_analyze_pages.py | 5 | HIGH — undated content flagged |
| 5 | T-SA-29 | extractability.py | 10 | HIGH — AEO accuracy |
| 6 | T-SA-30 | extractability.py, config.py, s4_check_aeo.py | 10 | HIGH — AEO accuracy |
| 7 | T-SA-26 | schema_checks.py | 16 | HIGH — e-commerce schemas |
| 8 | T-SA-27 | s1_discover.py | 8 | HIGH — dedup accuracy |
| 9 | T-SA-28 | s1_discover.py, site_audit.py, pipeline.py | 10 | MEDIUM — crawl signal |
| — | T-SA-25 | DROPPED | — | Already resolved |
| **Total** | | **~11 files** | **~80 new** | |

## Verification

1. Run full site audit test suite: `pytest tests/core/test_site_audit/ -v`
2. Run model tests for backward compat: `pytest tests/core/test_site_audit/test_models.py -v`
3. Verify existing JSON artifacts still deserialize (no new required fields without defaults)
4. CLI smoke test: `python scripts/run_site_audit.py --company "Example Corp" --domain example.com --max-pages 5`
