# Site Audit — Crawler & Page Analysis Specification

## s1_discover.py — Custom Async BFS Crawler

**CRITICAL: Do NOT import from core/gap_analysis/steps/s1_embed_assets.py. Build from scratch.**

### AsyncSiteCrawler Class

Build an async BFS crawler using `httpx.AsyncClient` with these capabilities:

**Constructor params:** domain, max_pages=200, max_depth=4, concurrency=30, respect_robots=True, timeout=15.0, user_agent="DeepPresence-SiteAudit/1.0"

**State:** _visited (set), _queue (asyncio.Queue of (url, depth) tuples), _results (list of (url, html) tuples), _depth_map (dict), _status_map (dict), _redirect_map (dict), _robots_disallowed (set)

### Multi-Phase Discovery

**Phase 1 — robots.txt + AI bot access:** Fetch `https://{domain}/robots.txt`. Parse for User-agent directives for GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot — check if `Disallow: /` follows each. Also fetch `https://{domain}/llms.txt` to check existence.

**Phase 2 — Sitemap extraction:** Parse robots.txt for `Sitemap:` directives. Fetch each sitemap XML. Parse with `xml.etree.ElementTree`. Extract `<loc>` URLs. Handle sitemap index files (sitemaps referencing other sitemaps). Add all URLs to BFS queue at depth 0.

**Phase 3 — RSS/Atom (lightweight):** Check homepage HTML for `<link rel="alternate" type="application/rss+xml">` or `atom+xml`. If found, fetch and extract URLs. Log and continue on failure.

**Phase 4 — BFS crawl:** Async workers with `asyncio.gather(*[worker(i) for i in range(concurrency)])`. Each worker loops: dequeue (url, depth) → check visited → check max_depth → acquire semaphore → fetch with httpx → extract links with BeautifulSoup → enqueue new links at depth+1 → release semaphore.

### Crawler Requirements (test each one)

1. **URL normalization:** Strip `#fragments`, normalize trailing slashes, resolve relative URLs with `urljoin`. Ignore `javascript:`, `mailto:`, `tel:` hrefs.
2. **Same-domain:** Compare `urlparse(url).netloc`. Subdomains are different domains.
3. **Robots.txt:** Use `urllib.robotparser.RobotFileParser`. Disallowed URLs tracked in discovered_urls but not fetched.
4. **Concurrency:** `asyncio.Semaphore(concurrency)` bounds parallel requests.
5. **Depth tracking:** Seeds at depth 0. Links from depth-N page get depth N+1. Keep minimum depth if discovered at multiple depths.
6. **Redirects:** `httpx.AsyncClient(follow_redirects=True, max_redirects=5)`. Record `original_url → response.url` in redirect_map.
7. **Status codes:** Record final status code for every URL.
8. **Content-type filtering:** Only parse `text/html` responses.
9. **Timeout handling:** 15s per request. On timeout: log warning, status_code=0, continue.
10. **Graceful shutdown:** When max_pages reached, stop enqueuing but finish in-flight requests.

### Output: S1DiscoveryOutput dataclass

```python
@dataclass
class S1DiscoveryOutput:
    pages_with_html: list[tuple[str, str]]     # (url, html) pairs
    ai_bot_access: AIBotAccessResult
    sitemap_health: SitemapHealthResult
    crawl_depth_map: dict[str, int]
    redirect_map: dict[str, str]
    status_code_map: dict[str, int]
    robots_txt_raw: str = ""
    discovered_urls: set[str] = field(default_factory=set)
```

## s2_analyze_pages.py — Parallel Page Analysis

**`analyze_all_pages(pages, depth_map, status_code_map, redirect_map, config)`** — Wraps `analyze_single_page()` calls with `asyncio.Semaphore(config.page_analysis_concurrency)` using `asyncio.gather()`. The `analyze_single_page()` function itself is SYNCHRONOUS (pure CPU, no I/O). Run it via `asyncio.to_thread()` or just call directly since it's fast.

**`analyze_single_page(url, html, depth, status_code, redirect_url, config)`** — Returns `PageAuditResult`. Uses BeautifulSoup to extract everything. Every `.find()` and `.get()` must handle None. Calls check functions from `checks/` modules to generate findings.

### What analyze_single_page extracts:

- **Title:** `soup.title.string` (handle None). Length check. Boilerplate detection ("Home", "Untitled").
- **Meta description:** `soup.find('meta', attrs={'name': 'description'})` → `.get('content', '')`. Length check.
- **Headings:** All h1-h6. Count H1s (should be exactly 1). Check hierarchy (no H1→H3 skipping H2).
- **Images:** All `<img>` tags. Count total, count with alt, count without alt.
- **Links:** All `<a href>`. Classify internal vs external by domain comparison.
- **Content metrics:** Use `trafilatura.extract()` for main content. Use `textstat.flesch_kincaid_grade()` for reading level. Word count.
- **SSR detection:** Check if `<body>` has >100 words of meaningful text (not just `<script>` tags).
- **Canonical:** `soup.find('link', rel='canonical')` → `.get('href')`.
- **Noindex/nofollow:** `soup.find('meta', attrs={'name': 'robots'})` → check for 'noindex', 'nofollow'.
- **Freshness:** Look for `<meta property="article:published_time">`, `<meta property="article:modified_time">`, `<time>` tags.
- **E-E-A-T:** Author bylines (look for `<meta name="author">`, `rel="author"`, common author class patterns). Outbound authority links (.gov, .edu, .org domains).

## Check Modules (core/site_audit/checks/)

All check functions are PURE — no I/O, no network calls, no side effects. Each takes relevant page data as input and returns `list[AuditFinding]`.

### crawlability.py
- `check_status_code(url, status_code)` → critical if 5xx, high if 4xx, info if 3xx
- `check_crawl_depth(url, depth, max_recommended=3)` → medium if >3, high if >5
- `check_canonical(url, has_canonical, canonical_url)` → medium if missing, high if self-referencing AND differs from actual URL
- `check_noindex(url, is_noindex)` → info finding (flagging, not penalizing)

### on_page_seo.py
- `check_title(url, title, title_length, config)` → critical if missing, high if too short/long
- `check_meta_description(url, meta_desc, meta_length, config)` → high if missing, medium if too short/long
- `check_h1(url, h1_count, h1_text)` → critical if 0 H1s, high if >1 H1
- `check_heading_hierarchy(url, headings)` → medium if levels skipped
- `check_images(url, total, without_alt)` → high if >50% missing alt, medium if any missing
- `check_internal_links(url, count)` → medium if 0 internal links

### eeat_signals.py
- `check_author(url, has_author)` → medium if no author on article-type pages
- `check_freshness(url, publish_date, modified_date)` → low if >2 years old, medium if >1 year

### security.py
- `check_https(url)` → critical if not HTTPS
- `check_mixed_content(url, has_mixed_content)` → high if mixed content detected

## Test Requirements

**test_crawler.py:** URL normalization (10+ cases), same-domain filtering, robots.txt parsing (200, 404, 500 responses), AI bot detection (blocked/allowed for each bot), sitemap parsing (valid XML, invalid XML, sitemap index, empty), BFS depth tracking, redirect following, timeout handling, max_pages enforcement.

**test_checks.py:** Every check function with: valid input → no findings, each error condition → correct severity + dimension, edge cases (empty string, None-like values, extremely long input).

**test_steps.py:** `analyze_single_page` with: well-formed HTML (correct extraction), minimal HTML (`<html></html>` → no crash), HTML with 0 headings, HTML with 50 H1s, HTML with no title tag, HTML with unicode, extremely nested HTML.
