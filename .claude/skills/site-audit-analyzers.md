# Site Audit — Schema + AEO Analyzers Specification

## s3_check_schema.py — JSON-LD Structured Data Detection

### Core Functions

**`detect_schema(html: str, url: str) -> SchemaDetectionResult`** — Main entry point. Parse HTML, find all `<script type="application/ld+json">` blocks, extract and validate.

**`generate_schema_findings(url: str, result: SchemaDetectionResult) -> list[AuditFinding]`** — Generate findings based on what's missing/wrong.

### JSON-LD Parsing Logic

1. Use BeautifulSoup to find all `<script type="application/ld+json">` tags.
2. For each, parse JSON inside `try/except json.JSONDecodeError` — if invalid, add to validation_errors and continue.
3. Handle `@graph` containers — iterate each item in the graph array.
4. Handle `@type` as both string and list (some sites use `"@type": ["Article", "BlogPosting"]`).
5. Identify known schema types: Organization, Article, BlogPosting, FAQPage, HowTo, Product, BreadcrumbList, LocalBusiness, Person, WebSite, WebPage, Speakable.
6. Store raw blocks for reference.

### Schema Validation (lightweight, not full JSON-LD spec)

**Article/BlogPosting:** Must have `headline`, `author` (or `author.name`), `datePublished`. Warning if missing `image` or `dateModified`.

**FAQPage:** Must have `mainEntity` array. Each entity must have `@type: Question`, `name` (the question), `acceptedAnswer` with `text`.

**HowTo:** Must have `name`, `step` array. Each step must have `text` or `itemListElement`.

**Organization:** Must have `name`, `url`. Warning if missing `logo`.

**BreadcrumbList:** Must have `itemListElement` array with `position` and `name`.

### Page Type Inference

`infer_page_type(url: str, html: str) -> str` — Heuristic-based:
- URL contains `/blog/` or `/posts/` or `/articles/` → "article"
- URL contains `/product/` or `/shop/` → "product"
- URL contains `/faq/` or `/help/` → "faq"
- URL contains `/about/` → "about"
- URL is exactly the domain root (path is "/" or "") → "homepage"
- URL contains `/pricing/` → "pricing"
- Default → "page"

### Finding Generation

Based on page type, generate findings for MISSING recommended schema:
- "homepage" without Organization → medium finding
- "article" without Article/BlogPosting → high finding
- "faq" without FAQPage → high finding
- "product" without Product → medium finding
- Any page without BreadcrumbList → low finding
- Schema present but validation errors → medium finding per error

## s4_check_aeo.py — AEO Content Extractability

This is the DIFFERENTIATOR. Traditional SEO tools don't check any of this.

### Core Functions

**`analyze_aeo_readiness(html: str, url: str, config: AuditConfig) -> tuple[AEOReadinessResult, list[AuditFinding]]`** — Main entry point. Returns both the result and any findings.

### Extractability Check Functions (in checks/extractability.py)

All PURE functions. No I/O.

**`classify_heading_as_question(text: str) -> bool`** — True if the heading is a question. Rules:
- Starts with: What, How, Why, When, Where, Who, Which, Can, Does, Is, Are, Should, Will, Do (case-insensitive, check word boundary not just prefix — "Whoever" is NOT a question)
- Ends with `?`
- Contains comparison patterns: "vs", "versus", "compared to", "difference between", "or" (as full words between nouns)
- Does NOT classify purely declarative headings as questions: "Benefits of AEO" → False, "Understanding Schema" → False

**`detect_quick_answer_hook(heading_element, soup) -> bool`** — After a question heading, check if the immediately following paragraph (first `<p>` sibling or first `<p>` child of next sibling `<div>`) has 30-70 words and directly answers the question. Skip over non-text siblings (`<img>`, `<div>` without text). Return False if no suitable paragraph found within 3 siblings.

**`is_self_contained_paragraph(text: str) -> bool`** — True if the paragraph is 20-80 words AND does NOT start with continuity markers: "However", "Additionally", "Furthermore", "Moreover", "In addition", "As mentioned", "As noted", "As discussed", "That said", "On the other hand", "Meanwhile", "Nevertheless", "Consequently", "Therefore" (case-insensitive). These markers indicate the paragraph depends on prior context and isn't suitable for AI extraction in isolation.

**Content pattern detectors** (all return bool):
- `detect_faq_section(soup)` — Looks for: FAQ/Frequently Asked Questions heading, `<dl>` definition lists, structured Q&A patterns (question heading followed by answer paragraph repeating 3+ times).
- `detect_definition_opening(text: str)` — First paragraph matches pattern "{Topic} is..." or "{Topic} are..." or "{Topic} refers to...".
- `detect_key_takeaways(soup)` — Heading containing "Key Takeaways", "Key Points", "Summary", "TL;DR" followed by a list.
- `detect_comparison_table(soup)` — `<table>` with 3+ rows and 2+ columns where header row contains comparison-like terms.
- `detect_numbered_steps(soup)` — Ordered list `<ol>` with 3+ items, OR headings matching "Step 1:", "Step 2:" pattern.
- `detect_toc(soup)` — Element with common TOC patterns: id/class containing "toc", "table-of-contents", "contents"; or a list of internal anchor links near the top.

### Snippet Readiness Score (0-100)

Composite score with these weights:
- question_heading_ratio × 25 pts (ratio of headings that are questions)
- quick_answer_hook_ratio × 25 pts (ratio of question headings with hooks)
- self_contained_paragraph_ratio × 20 pts (ratio of paragraphs that are self-contained)
- paragraph_length_score × 15 pts (score 0-1 based on how close avg paragraph word count is to ideal range 20-80)
- content_pattern_score × 15 pts (each detected pattern adds points: faq=4, definition=3, takeaways=3, comparison_table=2, numbered_steps=2, toc=1; capped at 15)

Clamp final score to [0, 100].

### AEO Findings

- question_heading_ratio < config.aeo_min_question_heading_ratio → medium finding: "Low question-based heading ratio"
- snippet_readiness_score < 30 → high finding: "Poor AEO readiness"
- snippet_readiness_score 30-60 → medium finding: "Moderate AEO readiness — room for improvement"
- No FAQ section detected on FAQ-type pages → medium finding
- No self-contained answer paragraphs → medium finding

## checks/performance.py

**`check_ssr_content(html: str, url: str) -> list[AuditFinding]`** — Parse HTML, extract text from `<body>`. If <100 words of visible text → high finding: "Page may be client-side rendered — AI crawlers cannot extract content."

**`fetch_core_web_vitals(url: str, api_key: str | None) -> dict | None`** — Optional. Call PageSpeed Insights API. If no API key or API fails, return None (graceful degradation). If available, check LCP, FID/INP, CLS against CWV "good" thresholds.

## Test Requirements

**test_schema.py (20+ tests):** Valid JSON-LD with single type, @graph container, multiple JSON-LD blocks, invalid JSON (doesn't crash), @type as array, nested objects, empty script tag, Article missing required fields, FAQPage with valid Q&A, FAQPage missing mainEntity, page type inference for /blog/, /product/, /faq/, /about/, /, /random-path.

**test_aeo.py (25+ tests):** Question classifier — test with 15+ headings (mix of true questions and false positives like "Understanding X"), quick answer hook detection with various HTML structures, self-contained paragraph detection with continuity markers, each content pattern detector with positive and negative cases, snippet readiness score calculation (verify manually: given specific ratios, does the formula produce the expected score?), score clamped to [0, 100] (test with extreme values), AEO findings generated at correct severity thresholds.
