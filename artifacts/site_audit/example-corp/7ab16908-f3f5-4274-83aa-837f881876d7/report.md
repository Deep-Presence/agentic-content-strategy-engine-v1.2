# Site Audit Report — example.com

**Overall Score: 94/100 🟢 Grade A**

- Pages crawled: 2
- Pages discovered: 2
- Total findings: 15

## Dimension Scores

| Dimension | Score | Weight | Weighted | Findings |
|-----------|-------|--------|----------|----------|
| Crawlability | 93 | 20% | 18.6 | 2 |
| Performance | 100 | 10% | 10.0 | 0 |
| On Page Seo | 84 | 15% | 12.6 | 5 |
| Extractability | 91 | 20% | 18.2 | 3 |
| Schema Markup | 94 | 10% | 9.4 | 4 |
| Eeat | 98 | 15% | 14.7 | 1 |
| Freshness | 100 | 5% | 5.0 | 0 |
| Security | 100 | 5% | 5.0 | 0 |

## AI Bot Access

| Bot | Allowed |
|-----|---------|
| GPTBot (OpenAI) | Yes |
| ClaudeBot (Anthropic) | Yes |
| PerplexityBot | Yes |
| Google-Extended | Yes |
| CCBot (Common Crawl) | Yes |

- robots.txt present: Yes
- llms.txt present: No

## Sitemap Health

- Sitemap found: Yes
- URLs in sitemap: 10

## AEO Readiness

- Average snippet readiness: 33.4/100
- Pages with structured data: 1/2
- Average question heading ratio: 14.3%

## Top Findings

### 1. [HIGH] Canonical URL 'https://example.com/blog/optimize-for-ai' differs from the page URL 'https://example.com/'.

- **Dimension:** Crawlability
- **Affected pages:** 1
- **Recommendation:** Verify this is intentional (e.g. pagination or syndicated content). If not, update the canonical to point to this page's URL.

### 2. [HIGH] Title is too short (8 chars; minimum: 30).

- **Dimension:** On Page Seo
- **Affected pages:** 1
- **Recommendation:** Expand the title to at least 30 characters to improve keyword coverage and click-through rates.

### 3. [HIGH] Page is missing a meta description.

- **Dimension:** On Page Seo
- **Affected pages:** 1
- **Recommendation:** Add a meta description between 120 and 160 characters summarising the page content.

### 4. [HIGH] AEO snippet readiness score is 0/100 — poor. This page is unlikely to be cited in AI search results.

- **Dimension:** Extractability
- **Affected pages:** 1
- **Recommendation:** Improve content structure for AI extraction: add question-format headings followed by direct 40-60 word answer paragraphs, ensure paragraphs stand alone without needing prior context, and add structured sections like FAQ, Key Takeaways, or How-To steps.

### 5. [MEDIUM] Meta description is too long (210 chars; maximum: 160).

- **Dimension:** On Page Seo
- **Affected pages:** 1
- **Recommendation:** Shorten the meta description to 160 characters or fewer to avoid truncation.

### 6. [MEDIUM] Page has no internal links.

- **Dimension:** On Page Seo
- **Affected pages:** 2
- **Recommendation:** Add at least 2–3 internal links to related pages. Internal links help AI crawlers discover related content and distribute link equity across the site.

### 7. [MEDIUM] Homepage is missing Organization schema markup. AI engines use Organization schema to establish entity identity.

- **Dimension:** Schema Markup
- **Affected pages:** 1
- **Recommendation:** Add an Organization JSON-LD block to your homepage with at least name, url, and logo properties.

### 8. [MEDIUM] Schema validation error: Article/BlogPosting missing recommended field: image

- **Dimension:** Schema Markup
- **Affected pages:** 1
- **Recommendation:** Fix the schema markup error to ensure AI engines can parse and trust the structured data on this page.

### 9. [MEDIUM] Only 29% of headings are phrased as questions (threshold: 30%). Question-format headings improve AI snippet extraction.

- **Dimension:** Extractability
- **Affected pages:** 2
- **Recommendation:** Rephrase at least 30% of subheadings as questions that your audience is actually asking (e.g. 'How does X work?' instead of 'About X'). This increases the likelihood of appearing in AI-generated answers.

### 10. [MEDIUM] Page is missing a canonical URL tag.

- **Dimension:** Crawlability
- **Affected pages:** 1
- **Recommendation:** Add ``<link rel='canonical' href='...' />`` to the ``<head>`` to prevent duplicate content issues.

## Findings by Severity

- **High:** 4
- **Medium:** 9
- **Low:** 2
