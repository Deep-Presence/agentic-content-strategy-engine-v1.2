# Sprint v2 PRD — Site Audit Bug Fixes

**Date:** 2026-03-03
**Sprint Goal:** Fix all bugs identified in the combined manual + Codex (gpt-5.3-codex) code review of the site-audit module.
**Branch:** `feat/front-back`
**Review sources:** Claude Opus 4.6 manual review + OpenAI gpt-5.3-codex automated review (319,237 tokens, high reasoning effort, live Python probes)

---

## P0 — Fix Before Production (Security + Data Integrity) ✅ ALL RESOLVED

### T-SA-01: Path traversal via unvalidated `audit_id` in filesystem service [H9] ✅ RESOLVED
- **Severity:** CRITICAL (security)
- **Source:** Codex (verified with live probe: `../../gap_analysis` escapes to `artifacts/gap_analysis/`)
- **File:** `core/services/json_site_audit_data.py`
- **Bug:** `audit_id` is user-supplied and concatenated directly into filesystem paths without UUID validation or `is_relative_to()` check.
- **Fix applied:** Single hardened `_audit_dir()` with UUID4 regex validation (`_AUDIT_ID_RE`) + `Path.resolve().is_relative_to()` defense-in-depth for symlink escapes. All read paths automatically protected.
- **Tests added:** 6 tests in `TestAuditIdValidation` — valid UUID, path traversal rejection, uppercase rejection, wrong format rejection, symlink escape rejection, direct validation function test.
- **Codex feedback incorporated:** Single trust-boundary function with symlink handling (not scattered validation).

### T-SA-02: XML entity expansion vulnerability in sitemap parsing [H2] ✅ RESOLVED
- **Severity:** CRITICAL (security)
- **Source:** Manual + Codex
- **Files:** `core/site_audit/steps/s1_discover.py`, `core/gap_analysis/steps/s1_embed_assets.py`, `pyproject.toml`
- **Bug:** `ET.fromstring(text)` uses stdlib ElementTree without protection against billion-laughs / entity expansion attacks.
- **Fix applied:** Replaced with `defusedxml.ElementTree.fromstring()` in both files. Added `_MAX_XML_BYTES = 10MB` size check before parsing. Added `max_depth=5` recursion limit to `_parse_sitemap()`. Handles `DTDForbidden` and `EntitiesForbidden` exceptions gracefully.
- **Tests added:** 6 tests in `TestXmlSecurity` — normal sitemap parses, empty XML returns None, HTTP error returns None, entity expansion blocked, oversized XML rejected, sitemap recursion depth capped.
- **Codex feedback incorporated:** Parse budget controls (size, recursion depth, defusedxml-specific exceptions) — not just a parser swap.

### T-SA-03: Cross-domain redirect following stores external content as internal pages [H6] ✅ RESOLVED
- **Severity:** HIGH (data integrity)
- **Source:** Codex (verified: 301 from `example.com` to `evil.com` stores evil content under original URL)
- **File:** `core/site_audit/steps/s1_discover.py`
- **Bug:** httpx follows redirects by default. If a page 301s to a different domain, the response HTML from the external domain gets stored under the original internal URL.
- **Fix applied:** Added cross-domain redirect gate in `_process_url()` — checks `is_same_domain(final_url, self.domain)` after HTTP fetch; rejects external content (records status, does NOT store HTML or enqueue child links). Added `_strip_www()` helper and upgraded `is_same_domain()` for www-alias canonicalization. Domain canonicalized at crawler init.
- **Tests added:** 3 tests in `TestCrossDomainRedirect` (cross-domain not stored, same-domain stored, www redirect accepted) + 6 tests in `TestIsSameDomainWwwAlias`.
- **Codex feedback incorporated:** T-SA-17 (www aliasing) pulled into P0 as blocking dependency — naive cross-domain check would reject `example.com → www.example.com` redirects.

### T-SA-04: BeautifulSoup DOM mutation via `decompose()` corrupts shared soup [H1] ✅ RESOLVED
- **Severity:** HIGH (correctness)
- **Source:** Manual
- **File:** `core/site_audit/steps/s2_analyze_pages.py`
- **Bug:** `_extract_content_metrics()` calls `tag.decompose()` on the shared soup object. All subsequent extractions see a mutilated DOM tree.
- **Fix applied:** `_extract_content_metrics()` fallback path now creates its own `fallback_soup = BeautifulSoup(html, "html.parser")` instead of mutating the shared soup. `_is_ssr(soup)` changed to `_is_ssr(html: str)` — now re-parses internally. Original soup remains untouched for all downstream extractors.
- **Tests added:** 4 tests in `TestDomMutationRegression` — soup not mutated after content metrics, mixed content detected after content metrics, fallback preserves soup, full page analysis mixed content correct.
- **Codex feedback incorporated:** Re-parse from raw HTML (not `copy.copy(soup)` which is fragile and parser-dependent).

### T-SA-05: BFS crawler deadlock when `max_pages` reached [H4] ✅ RESOLVED
- **Severity:** HIGH (reliability — confirmed hanging Lovable run for 1+ hour)
- **Source:** Codex (verified via timeout test)
- **File:** `core/site_audit/steps/s1_discover.py`
- **Bug:** When `max_pages` is reached, `_stop_crawling = True` is set. Workers exit without dequeuing remaining items. `queue.join()` hangs forever because `task_done()` is never called for queued-but-unprocessed items.
- **Fix applied:** Replaced `queue.join()` with dual-signal `asyncio.wait()` — waits for EITHER `queue.join()` (natural completion) OR `_stop_event` (max_pages reached), whichever fires first. Added `_stop_event = asyncio.Event()` set alongside `_stop_crawling = True` in `_process_url()`. After shutdown, workers are cancelled first, then remaining queue items drained — preserving queue accounting invariants.
- **Tests added:** 4 tests in `TestBfsDeadlockPrevention` — branching URL structure (concurrency=10), max_pages=1 immediate shutdown, high concurrency (concurrency=30), queue empty after crawl.
- **Codex feedback incorporated:** Drain AFTER worker cancellation to preserve queue accounting invariants. Event-based shutdown for immediate response instead of 300s timeout wait.

---

## P1 — Fix Before Customer-Facing Launch (Scoring Accuracy) ✅ ALL RESOLVED

### T-SA-06: Performance dimension (10% weight) generates ZERO findings [H3] ✅ RESOLVED
- **Severity:** HIGH (scoring integrity — 10% of the total score is fabricated)
- **Source:** Manual + Codex
- **Files:** `core/site_audit/checks/performance.py:33, :88`, `core/site_audit/steps/s2_analyze_pages.py:487`
- **Bug:** `check_ssr_content()` and `fetch_core_web_vitals()` exist in `performance.py` but are NEVER called from any pipeline step. The performance dimension always scores 100/100, inflating overall scores by up to 10 points.
- **Fix applied:** Imported and called `check_ssr_content(html, url)` in `analyze_single_page()` after the `_is_ssr(html)` block. `fetch_core_web_vitals` NOT wired this sprint (async, requires Google API key — deferred to T-SA-21 in P2 backlog). No weight redistribution to avoid breaking scoring comparability.
- **Tests added:** 3 tests in `TestPerformanceSsrFinding` — CSR page generates performance finding, SSR page no performance finding, integration test with full `analyze_single_page`.

### T-SA-07: Freshness dimension is orphaned — findings go to E-E-A-T instead [H7] ✅ RESOLVED
- **Severity:** HIGH (scoring integrity — 5% of score is fabricated, E-E-A-T double-penalized)
- **Source:** Codex (verified: `check_freshness` findings assigned to `AuditDimension.eeat`, not `freshness`)
- **File:** `core/site_audit/checks/eeat_signals.py:102, :120`
- **Bug:** `check_freshness()` creates findings with `dimension=AuditDimension.eeat`. The freshness dimension (5% weight) always scores 100. Additionally, severity is inverted: `>2y` is `low` and `>1y` is `medium` (older content should be more severely penalized).
- **Fix applied:** Changed `dimension=AuditDimension.eeat` → `AuditDimension.freshness` for both stale_content_2y and stale_content_1y findings. Swapped severities: `>2y` = `medium`, `>1y` = `low`. Updated corresponding old tests in `test_checks.py`.
- **Tests added:** 4 tests in `TestFreshnessDimension` — 2y→freshness+medium, 1y→freshness+low, recent→no findings, never assigns eeat dimension.

### T-SA-08: Penalty accumulation not normalized by page count [H5] ✅ RESOLVED
- **Severity:** HIGH (scoring fairness)
- **Source:** Manual + Codex
- **File:** `core/site_audit/scoring.py:58`
- **Bug:** Each finding across ALL pages deducts from a single 100-point pool per dimension. A 200-page site with one `low` finding per page = 200 penalty = score 0. A 2-page site with the same issue per page = 2 penalty = score 98. Scoring is completely unfair across site sizes.
- **Fix applied:** Implemented page-normalised mean penalty algorithm (Codex recommended model). Key design: (1) Separate site-level findings (`url=""`) from page-level — site penalties applied flat, not divided. (2) Page-level: group by URL, dedup by `finding_type` per page (max severity wins), compute per-page penalty, then MEAN across ALL crawled pages (unaffected pages contribute 0). (3) `pages_crawled` param added to `compute_dimension_score()` and `compute_all_dimension_scores()` (default=1 for backward compat). (4) `s5_aggregate.py` passes `pages_crawled=len(page_results)` to scoring.
- **Tests added:** 6 tests in `TestPageNormalisedScoring` — 200-page vs 2-page comparable scores, single finding on 200 pages = minor penalty, all pages affected = full penalty, zero pages no crash, site-level finding not divided, mixed severity same type takes worst. Updated 2 existing tests (`test_multiple_findings_accumulate`, `test_score_clamped_at_zero`) to use distinct finding_types for correct dedup behavior.

### T-SA-09: Partial-step failures return "completed" with inflated scores [H8] ✅ RESOLVED
- **Severity:** HIGH (misleading results)
- **Source:** Codex
- **File:** `core/site_audit/pipeline.py:176, :179`
- **Bug:** If s3 (schema) or s4 (AEO) fail, the pipeline catches the exception and continues. s5 aggregates whatever findings exist, producing a near-perfect score because the failed dimensions generated no findings. The result `status` is still `"completed"`.
- **Fix applied:** (1) Added `failed_steps: list[int]` and `degraded_dimensions: list[str]` fields to `SiteAuditResult` (with defaults for backward compat). (2) Pipeline tracks `failed_steps` — appends step number on catastrophic failure OR when all pages fail individually in a step. (3) `_STEP_DIMENSION_MAP` maps steps to dimensions. (4) Per-page resilience: inner try/except for s3/s4 per-page loops — individual page failures don't crash the step. (5) After s5, degraded dimensions get score=0 (conservative), overall score recomputed. (6) Runner propagates `degraded`/`failed_steps`/`degraded_dimensions` into task result. (7) Router guard accepts `"degraded"` status alongside `"completed"`.
- **Tests added:** 8 tests in `TestDegradedPipeline` — s3 failure→degraded, s4 failure→degraded, both fail→both degraded, degraded dim score=0, no failures→completed, s3 per-page resilience, degraded result JSON roundtrip, plus model defaults tests updated.

### T-SA-10: CLI script never sets `company_slug` — artifacts go to wrong path [B2] ✅ RESOLVED
- **Severity:** HIGH (CLI broken)
- **Files:** `scripts/run_site_audit.py:94`, `core/models/site_audit.py:62`, `core/site_audit/pipeline.py:108`
- **Bug:** `SiteAuditInput.company_slug` is `Optional[str] = None`. The CLI script passes `company_name` but not `company_slug`. Pipeline computes `effective_slug = product_slug or company_slug or ""` → empty string. Artifacts go to `artifacts/site_audit//<uuid>/` (collapsed path). Additionally, `run_site_audit.py:124` displays the wrong output path (uses `audit_id` without slug).
- **Fix applied:** (1) Added `model_validator(mode="before")` on `SiteAuditInput` — auto-derives `company_slug` from `company_name` via `re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")`. (2) Added `field_validator("product_slug")` — rejects path-traversal chars (must match `^[a-z0-9][a-z0-9-]*$`). (3) Fixed `effective_slug` in `pipeline.py` to use `{company_slug}__{product_slug}` double-underscore convention (matching rest of codebase). (4) Fixed CLI artifact path display to use `effective_slug / audit_id`.
- **Tests added:** 6 tests in `TestSiteAuditInput` — slug derived from company_name, special chars slugified, explicit slug preserved, product slug valid, path traversal rejected, uppercase rejected. Updated `test_defaults` to expect auto-derived slug.

---

## P2 — Signal Extraction Accuracy ✅ ALL RESOLVED (10/10)

### T-SA-11: `_extract_title` fails on nested tags [M1] ✅ RESOLVED
- **Severity:** MEDIUM (extraction accuracy)
- **Source:** Manual + Codex (verified: `<title><span>Deep Presence</span> Audit</title>` → `("", 0)`)
- **File:** `core/site_audit/steps/s2_analyze_pages.py:84`
- **Bug:** Uses `title_tag.string` which returns `None` when `<title>` contains child elements (e.g. `<span>`). Should use `title_tag.get_text(separator=" ", strip=True)`.
- **Fix applied:** Replaced `title_tag.string or ""` with `title_tag.get_text(" ", strip=True)` — same pattern used for headings.
- **Tests added:** 3 tests in `TestExtractTitle` — nested span, bold+italic, deeply nested.

### T-SA-12: No og:description fallback in meta description extraction [M2] ✅ RESOLVED
- **Severity:** MEDIUM (extraction accuracy)
- **Source:** Manual + Codex
- **File:** `core/site_audit/steps/s2_analyze_pages.py:88-101`
- **Bug:** Only checks `<meta name="description">`. Many sites use `og:description` or `twitter:description` instead/additionally.
- **Fix applied:** 3-tier fallback chain: `name="description"` → `property="og:description"` → `name="twitter:description"`. Each level checks for non-empty content before falling through.
- **Tests added:** 6 tests in `TestExtractMetaDescription` — og fallback, twitter fallback, name preferred over og, empty name falls to og, og preferred over twitter, all empty returns empty.

### T-SA-13: Author check fires for ALL pages, not just articles [M6] ✅ RESOLVED
- **Severity:** MEDIUM (false positives)
- **Source:** Manual + Codex (verified: homepage with 120 words triggers `missing_author`)
- **File:** `core/site_audit/steps/s2_analyze_pages.py:548`
- **Bug:** `check_author()` penalizes homepages, product pages, pricing pages, etc. that naturally don't have author attribution.
- **Fix applied:** Gated `check_author()` call with `if infer_page_type(url, html) == "article":`. Author data still extracted for all pages (for reporting). Only the *finding* is gated.
- **Tests added:** 5 tests in `TestAuthorPageTypeGating` — homepage no finding, product page no finding, blog page gets finding, blog with author no finding, author still extracted for non-article.

### T-SA-14: JSON-LD extraction misses charset variants and URI-style @type [M7] ✅ RESOLVED
- **Severity:** MEDIUM (extraction accuracy)
- **Source:** Codex
- **File:** `core/site_audit/checks/schema_checks.py:70, :128`
- **Bug:** `type="application/ld+json; charset=utf-8"` won't match exact string. URI-style `@type` like `http://schema.org/Article` aren't normalized.
- **Fix applied:** (1) Added `_JSONLD_TYPE_RE = re.compile(r"^application/ld\+json\s*(;.*)?$", re.IGNORECASE)` for case-insensitive charset-tolerant matching. (2) Added `_normalize_schema_type()` helper to strip schema.org URI prefixes. (3) Applied normalization in both `identify_schema_types()` and `validate_schema_block()` dispatch (Codex F-1 fix).
- **Tests added:** 11 tests — 8 in `TestParseJsonldBlocks`/`TestIdentifySchemaTypes` (charset UTF-8, uppercase, case-insensitive, URI normalization, dedup) + 3 in `TestValidateSchemaBlockURIType` (Codex F-1: URI article validates, missing fields detected, URI FAQ validates).

### T-SA-15: Mixed-content detector incomplete [M8] ✅ RESOLVED
- **Severity:** MEDIUM (extraction accuracy)
- **Source:** Codex
- **File:** `core/site_audit/steps/s2_analyze_pages.py:374-434`
- **Bug:** Missing detection for: `<img srcset>`, `<video poster>`, `<object data>`, `<embed src>`, inline CSS `url(http://...)`.
- **Fix applied:** Replaced `_has_mixed_content()` with 4-phase implementation: (1) Standard tag/attr pairs + new video/poster, object/data, embed/src. (2) srcset comma-separated URL parsing. (3) Inline style `url(http://...)` via `_HTTP_URL_IN_CSS_RE`. (4) `<style>` blocks.
- **Tests added:** 9 tests in `TestHasMixedContent` — srcset, video poster, object data, embed src, inline style, style block, HTTPS no trigger, data URI no trigger.

### T-SA-16: effective_slug convention mismatch [M9] ✅ RESOLVED (fixed as part of T-SA-10 P1)
- **Severity:** MEDIUM (architecture consistency)
- **Source:** Manual + Codex
- **File:** `core/site_audit/pipeline.py:108`
- **Bug:** Uses `product_slug or company_slug` (bare product slug) while the project convention is `{company_slug}__{product_slug}` (double underscore effective slug).
- **Fix applied:** Resolved as part of T-SA-10. Pipeline now uses `f"{company_slug}__{product_slug}"` when both present, matching project convention.

### T-SA-17: Domain validation weak + no www aliasing [M10] ✅ RESOLVED (pulled into P0 as T-SA-03 dependency)
- **Severity:** MEDIUM (crawl accuracy)
- **Source:** Codex
- **File:** `core/site_audit/steps/s1_discover.py`
- **Bug:** Strict host equality rejects `www.example.com` when domain is `example.com`. No domain canonicalization.
- **Fix applied:** Added `_strip_www()` helper, upgraded `is_same_domain()` for www-alias canonicalization, domain canonicalized at crawler init. Resolved as part of T-SA-03 (Codex identified as blocking dependency).
- **Tests added:** 6 tests in `TestIsSameDomainWwwAlias`.

### T-SA-18: Visited/depth logic permanently skips valid URLs at shallower depth [H10] ✅ RESOLVED
- **Severity:** MEDIUM (crawl coverage)
- **Source:** Codex
- **File:** `core/site_audit/steps/s1_discover.py:709-730`
- **Bug:** If URL is in `_visited` (already fetched), `_enqueue()` returns immediately without updating depth. URLs discovered first at depth 5, then at depth 1, keep depth 5.
- **Fix applied:** Restructured `_enqueue()` to check `_depth_map` BEFORE `_visited`. Always updates depth to minimum, even for already-visited/queued URLs. Already-fetched URLs don't get re-enqueued, but their depth is corrected.
- **Tests added:** 2 tests in `TestDepthMapUpdate` — visited URL depth updated to shallower, deeper rediscovery no depth change.

### T-SA-19: `detect_definition_opening()` regex too broad [M4] ✅ RESOLVED
- **Severity:** MEDIUM (AEO accuracy)
- **Source:** Manual
- **File:** `core/site_audit/checks/extractability.py:298-351`
- **Bug:** Pattern `^\S+(\s+\S+){0,4}\s+(is|are)\s+` matches nearly any sentence with "is"/"are" in the first 6 words: "The company is great" → true.
- **Fix applied:** (1) Added `_DEFINITIONAL_CONTINUATIONS` regex requiring the word after is/are to be an article, definitional verb, quantifier, adverb, or passive purpose verb. (2) Hyphenated compound term check for technical definitions like "machine-readable". (3) Non-topic starter rejection: pronouns (it, we, you, they), possessives (our, my, your, his, her, its), and existential "there" are rejected before pattern matching (Codex F-3 fix).
- **Tests added:** 12 tests in `TestDetectDefinitionOpening` — 8 for T-SA-19 (false generic, false possessive, true article, true indefinite, true known_as, true defined_as, true typically, true not_negation) + 4 for Codex F-3 (false existential there, false possessive our, false pronoun it, false pronoun we).

### T-SA-20: `detect_toc()` O(n) scan over ALL elements [M5] ✅ RESOLVED
- **Severity:** MEDIUM (performance)
- **Source:** Manual
- **File:** `core/site_audit/checks/extractability.py:461-510`
- **Bug:** `soup.find_all(True)` iterates every DOM element checking for toc-related id/class substrings. On large pages this is wasteful.
- **Fix applied:** Replaced Rule 1's O(n) scan with CSS `select_one()` using case-insensitive attribute selectors (`[id*="toc" i]`, `[class*="toc" i]`). CSS4 `i` flag supported by soupsieve ≥2.0 (Codex F-2 fix for case sensitivity).
- **Tests added:** 6 tests — 3 for T-SA-20 (class prefix, underscore variant, contents prefix) + 3 for Codex F-2 (uppercase id, mixed-case class, uppercase table-of-contents).

### T-SA-21: Config flags are dead code [M11] ✅ RESOLVED
- **Severity:** MEDIUM (API contract)
- **Source:** Codex
- **Files:** `core/site_audit/pipeline.py`, `core/site_audit/steps/s1_discover.py`, `core/site_audit/steps/s2_analyze_pages.py`
- **Bug:** `check_core_web_vitals`, `check_schema_validation`, `check_ai_bot_access` exist in API schema/model but aren't plumbed to pipeline behavior.
- **Fix applied:** (A) `check_schema_validation=False` → skips step 3 in pipeline.py. (B) `check_ai_bot_access=False` → `AsyncSiteCrawler` accepts flag, skips robots.txt AI bot parsing and llms.txt check, returns default `AIBotAccessResult()`. Pipeline passes flag through `discover_site()`. (C) `check_core_web_vitals=False` → `analyze_single_page()` and `analyze_all_pages()` accept flag, skip `check_ssr_content()` call. Pipeline passes flag through. All new params have defaults for backward compat.
- **Tests added:** 4 tests in `TestConfigFlagsWired` — schema_validation false skips s3, schema_validation true runs s3, ai_bot_access false passes flag to discover_site, core_web_vitals false skips SSR check.

### T-SA-22: API schema extraction drops `schema_result` key [M12] ✅ RESOLVED
- **Severity:** MEDIUM (data service)
- **Source:** Codex
- **File:** `core/services/json_site_audit_data.py:334`
- **Bug:** `PageAuditResult` uses `alias="schema"` for field `schema_result`. `model_dump(mode="json")` serializes with field name `schema_result`, but `p.get("schema", {})` only reads the alias.
- **Fix applied:** Changed to `p.get("schema_result", p.get("schema", {}))` — field name takes priority via nested `dict.get()` defaults.
- **Tests added:** 4 tests in `TestSchemaKeyFallback` — schema_result key used, schema alias key used, neither returns empty, both keys prefers field name.

---

## P3 — Backlog (Low Priority)

### T-SA-23: Fragile date parsing in `_extract_freshness()` [M3]
- **File:** `core/site_audit/steps/s2_analyze_pages.py`
- **Bug:** Limited date format coverage. No ISO 8601 `T` separator, no timezone-aware parsing.
- **Fix:** Use `dateutil.parser.parse()` with fallback.

### T-SA-24: No findings for pages missing both publish and modified dates [L1]
- **Bug:** Pages with no date metadata get no freshness finding at all (silent pass).
- **Fix:** Generate a `low` finding when no date metadata is found.

### T-SA-25: Title/description max lengths not configurable [L2]
- **Bug:** `max_recommended` values are hardcoded in `on_page_seo.py`, not in `AuditConfig`.
- **Fix:** Move thresholds to `AuditConfig`.

### T-SA-26: No validation for Product or Speakable schema types [L3]
- **Bug:** They're in `KNOWN_SCHEMA_TYPES` but have no validator function.
- **Fix:** Add `validate_product_schema()` and `validate_speakable_schema()`.

### T-SA-27: `normalize_url` doesn't sort query params [L4]
- **Bug:** `?a=1&b=2` and `?b=2&a=1` are treated as different URLs.
- **Fix:** Sort query params in `normalize_url()`.

### T-SA-28: No Crawl-delay respect from robots.txt [L5]
- **Bug:** `Crawl-delay` directive is parsed but not enforced.
- **Fix:** Add delay between requests when Crawl-delay is specified.

### T-SA-29: Question-heading classifier requires trailing `?` [L6]
- **Bug:** Misses "How to deploy your app" style headings without `?`.
- **Fix:** Accept question-word-starting headings without trailing `?`.

### T-SA-30: Quick-answer hook sibling-window misses CMS wrapper divs [L7]
- **Bug:** 3-sibling window is too narrow for CMS-heavy HTML structures.
- **Fix:** Expand to section-scoped search.

### T-SA-31: AuditConfig no `__post_init__` validation [L8]
- **Bug:** Custom configs can have weights that don't sum to 1.0 or non-monotonic grade thresholds.
- **Fix:** Add `__post_init__` assertions.

### T-SA-32: Integration test writes to real artifacts dir [B3]
- **File:** `tests/core/test_site_audit/test_integration.py:657`
- **Bug:** Full pipeline integration test calls `generate_report()` which writes to `artifacts/site_audit/example-corp/` — polluting the real artifacts directory on every test run.
- **Fix:** Either mock `generate_report` in the test, or use `tmp_path` fixture to redirect the output directory.

---

## Missing Checks (Future Sprints)

These are NOT bugs but missing functionality that should be added for a complete AI-readiness audit:

| Priority | Check | Dimension |
|----------|-------|-----------|
| High | Security headers (CSP, HSTS, X-Frame-Options, Referrer-Policy) | security |
| High | Broken internal link detection | crawlability |
| High | Duplicate title / meta description detection | on_page_seo |
| Medium | Real CWV telemetry (TTFB, LCP, resource hints, JS bundle) | performance |
| Medium | Mobile-friendliness / viewport meta check | on_page_seo |
| Medium | Structured data coverage ratio by page type | schema_markup |
| Medium | Robots/sitemap/AI-bot blocks as scoring findings | crawlability |
| Low | Response/body size caps and HTML parse safeguards | robustness |

---

## Acceptance Criteria

- [x] All P0 fixes implemented with tests (5/5 resolved, 29 new tests, reviewed by gpt-5.3-codex)
- [x] All P1 fixes implemented with tests (5/5 resolved, 27 new tests + 4 updated tests, plan reviewed by gpt-5.3-codex with 12 findings incorporated)
- [x] All P2 fixes implemented with tests (10/10 resolved, ~62 new tests, plan + implementation reviewed by gpt-5.3-codex with 4 findings — 3 incorporated, 1 deferred)
- [x] Existing test suite passes (715 site-audit tests passing)
- [ ] `python scripts/run_site_audit.py --company "Lovable" --domain lovable.dev --max-pages 10` completes successfully within 60s, writes to `artifacts/site_audit/lovable/<uuid>/`
- [ ] Integration test no longer pollutes real artifacts dir
- [x] Scoring model produces fair results across different site sizes (page-normalised mean penalty algorithm)

---

## P2 Codex Review (gpt-5.3-codex, high reasoning effort)

**Model:** gpt-5.3-codex | **Tokens used:** 113,847 | **Findings:** 4

| Finding | Severity | Action | Description |
|---------|----------|--------|-------------|
| F-1 | HIGH | **INCORPORATED** | `validate_schema_block()` dispatched on raw `@type` — URI-style types like `https://schema.org/Article` skipped article-field validation. Fixed: normalize types via `_normalize_schema_type()` in dispatch loop. +3 tests. |
| F-2 | MEDIUM | **INCORPORATED** | `detect_toc()` CSS `[id*="toc"]` selectors are case-sensitive — `id="TOC"` returns False. Fixed: added CSS4 `i` flag (`[id*="toc" i]`). Verified soupsieve ≥2.0 supports it. +3 tests. |
| F-3 | MEDIUM | **INCORPORATED** | `detect_definition_opening()` still matches "There is a lot..." (existential) and "Our support is top-notch" (possessive). Fixed: added non-topic starter rejection regex (there/it/our/we/you/they/my/your/his/her/its). +4 tests. |
| F-4 | MEDIUM | **DEFERRED** | `infer_page_type()` is URL-path heuristic only — misses `/news/`, `/insights/`, dated slugs. Expanding page-type inference with HTML/schema signals is a P3 enhancement (separate from T-SA-13 which only gated author checks). |