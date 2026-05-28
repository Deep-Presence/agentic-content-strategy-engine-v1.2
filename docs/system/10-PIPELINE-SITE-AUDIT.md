# Pipeline 0: Site Audit

> **Location:** `core/site_audit/`
> **Owner:** Core
> **Dependencies:** httpx, BeautifulSoup, `core/models/site_audit.py`
> **Dependents:** `api/routers/site_audit.py`, `core/services/site_audit_data.py`, `core/content_inventory/`
> **Last Updated:** 2026-04-09

## Overview

Pipeline 0 is a fully **deterministic** (no LLM) site audit system that diagnoses how AI-ready a website is across 8 dimensions. The 6-step async pipeline combines BFS crawling, HTML analysis, schema detection, AEO (Answer Engine Optimization) scoring, aggregation, and reporting to produce a 0-100 score with letter grades (A-F). Unlike all other pipelines, this one uses zero LLM calls — everything is rule-based.

## Architecture

```
SiteAuditInput
    │
    ▼
S1: Discover ── robots.txt, AI bot access, sitemaps, BFS crawl
    │             Output: pages_with_html, ai_bot_access, sitemap_health
    ▼
S2: Analyze ─── Per-page HTML parsing + structural extraction
    │             Output: list[PageAuditResult] with findings
    ▼
S3: Schema ──── JSON-LD extraction + validation (optional)
    │             Output: enriched PageAuditResult.schema_result
    ▼
S4: AEO ─────── Content extractability analysis (optional)
    │             Output: enriched PageAuditResult.aeo + snippet_readiness
    ▼
S5: Aggregate ── Cross-page analysis, dimension scoring, grading
    │             Output: SiteAuditResult (overall_score, grade, top_findings)
    ▼
S6: Report ──── Markdown + JSON report generation (optional)
    │             Output: report.md + audit_result.json
    ▼
SiteAuditResult (status: completed | degraded | failed)
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `pipeline.py` | Main orchestrator | `run_site_audit` |
| `config.py` | AuditConfig dataclass + defaults | `AuditConfig`, `DEFAULT_AUDIT_CONFIG` |
| `scoring.py` | Dimension scoring algorithm | `compute_dimension_score`, `compute_overall_score` |
| `persistence.py` | DB persistence hooks | `persist_site_audit` |
| `steps/s1_discover.py` | BFS crawler + robots/sitemap | S1 discovery |
| `steps/s2_analyze_pages.py` | Per-page HTML analysis | S2 analysis |
| `steps/s3_check_schema.py` | JSON-LD detection | S3 schema |
| `steps/s4_check_aeo.py` | AEO readiness scoring | S4 extractability |
| `steps/s5_aggregate.py` | Scoring + cross-page analysis | S5 aggregate |
| `steps/s6_report.py` | Report generation | S6 report |
| `checks/crawlability.py` | Status codes, depth, canonical | Crawlability checks |
| `checks/on_page_seo.py` | Titles, meta, headings, images | SEO checks |
| `checks/security.py` | HTTPS, headers, mixed content | Security checks |
| `checks/eeat_signals.py` | Author, freshness dates | E-E-A-T checks |
| `checks/extractability.py` | AEO: questions, answers, patterns | Extractability checks |
| `checks/schema_checks.py` | JSON-LD parsing + validation | Schema checks |
| `checks/performance.py` | SSR detection, Core Web Vitals | Performance checks |
| `checks/performance_structural.py` | Page size, resources, images | Structural perf checks |

## Scoring System

### 8 Dimensions (weights sum to 1.0)

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| `crawlability` | 0.20 | Can AI bots reach pages? Status codes, depth, canonical, noindex |
| `extractability` | 0.20 | Can AI extract content? Question headings, self-contained paragraphs, FAQ patterns |
| `on_page_seo` | 0.15 | Titles, meta descriptions, H1, heading hierarchy, images, links |
| `eeat` | 0.15 | Author attribution, content freshness signals |
| `performance` | 0.10 | SSR detection, Core Web Vitals, page load structure |
| `schema_markup` | 0.10 | JSON-LD presence, validation, required fields |
| `freshness` | 0.05 | Content age, staleness indicators |
| `security` | 0.05 | HTTPS, mixed content, security headers |

### Severity Penalties

| Severity | Penalty | Example Findings |
|----------|---------|-----------------|
| critical | 10.0 | Missing title, missing H1, 5xx error, not HTTPS |
| high | 5.0 | Multiple H1s, poor AEO score, 4xx error |
| medium | 2.0 | Title too short/long, missing meta, large HTML |
| low | 1.0 | No CSP header, stale content (>1yr) |
| info | 0.0 | Redirects, noindex pages |

### Grade Thresholds

| Grade | Minimum Score |
|-------|--------------|
| A | >= 90 |
| B | >= 75 |
| C | >= 60 |
| D | >= 40 |
| F | < 40 |

### Scoring Algorithm

Per dimension, **page-normalized** to avoid penalizing larger sites:
1. Filter findings to this dimension
2. Separate site-level (url="") from page-level findings
3. `site_penalty = sum(penalties for site-level findings)`
4. `page_penalty = mean(per-page penalties)` across ALL crawled pages
5. `raw_score = clamp(100 - site_penalty - page_penalty, 0, 100)`
6. `weighted_score = raw_score * dimension_weight`
7. `overall_score = sum(all weighted_scores)`

## AEO (Answer Engine Optimization) — Differentiator

Traditional SEO tools ignore AI extraction readiness. Pipeline 0 measures:
- **Question heading ratio** — % of headings that are questions (ends with "?", starts with who/what/how/etc.)
- **Quick-answer hooks** — question heading followed by 15-150 word paragraph
- **Self-contained paragraphs** — 20-80 words, no continuity markers ("However", "Additionally")
- **Content patterns** — FAQ sections, definition openings, key takeaways, comparison tables, numbered steps, TOC

Composite **snippet_readiness_score** (0-100): 25% question ratio + 25% quick-answer hooks + 20% self-contained paragraphs + 15% paragraph length + 15% content patterns.

## Step Details

### S1: Discovery
- Fetches `robots.txt`, checks AI bot access (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot)
- Detects `llms.txt` presence
- Recursive sitemap parsing (handles sitemap index, RSS/Atom feeds)
- BFS crawl with configurable depth/pages/concurrency
- Skips non-HTML extensions (.pdf, .jpg, .css, .js, etc.)

### S2: Analyze Pages
- Per-page structural extraction (BeautifulSoup): titles, meta, headings, images, links
- Content metrics: word count, reading level (Flesch-Kincaid)
- SSR detection: <100 visible words = likely CSR
- Security: HTTPS, mixed content, security headers
- Performance: page size, external resources, render-blocking scripts/CSS

### S3: Check Schema
- Extracts all `<script type="application/ld+json">` blocks
- Handles `@graph` containers
- Validates: Article (headline, author, datePublished), FAQPage (mainEntity), HowTo (steps), Organization (name, url), BreadcrumbList
- Infers page type from URL patterns

### S4: Check AEO
- Question heading detection with comparison pattern support
- Quick-answer hook detection within 5 siblings of question heading
- Self-contained paragraph analysis (excluding continuity markers)
- Content pattern detection (FAQ, definitions, key takeaways, comparison tables, steps, TOC)

### S5: Aggregate
- Cross-page analysis: duplicate titles/meta, orphan pages, thin content (<200 words)
- Computes all dimension scores, overall score, and grade
- Generates top 10 findings (most impactful)

### S6: Report
- Markdown executive summary with grade emoji
- Full JSON result (`audit_result.json`)

## Error Handling

- S1 failure = entire pipeline fails (discovery is required)
- S2-S4 failures = dimension scores zeroed (conservative), status = "degraded"
- Individual page parse errors = logged and skipped
- `failed_steps` and `degraded_dimensions` arrays track partial failures

## Configuration

Key settings from `core/config/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `site_audit_max_pages` | 200 | Max pages to crawl |
| `site_audit_max_depth` | 4 | Max BFS depth |
| `site_audit_concurrency` | 30 | Concurrent requests |
| `site_audit_request_timeout` | 15.0 | Per-request timeout (s) |
| `site_audit_max_redirects` | 5 | Max redirect hops |
