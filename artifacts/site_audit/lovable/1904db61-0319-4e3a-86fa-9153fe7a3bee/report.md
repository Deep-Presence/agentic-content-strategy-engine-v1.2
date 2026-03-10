# Site Audit Report — lovable.dev

**Overall Score: 97/100 🟢 Grade A**

- Pages crawled: 10
- Pages discovered: 1005
- Total findings: 64

## Dimension Scores

| Dimension | Score | Weight | Weighted | Findings |
|-----------|-------|--------|----------|----------|
| Crawlability | 100 | 20% | 20.0 | 0 |
| Performance | 100 | 10% | 10.0 | 0 |
| On Page Seo | 93 | 15% | 14.0 | 20 |
| Extractability | 95 | 20% | 19.1 | 20 |
| Schema Markup | 96 | 10% | 9.6 | 17 |
| Eeat | 99 | 15% | 14.8 | 7 |
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
- URLs in sitemap: 939

## AEO Readiness

- Average snippet readiness: 37.9/100
- Pages with structured data: 10/10
- Average question heading ratio: 13.9%

## Top Findings

### 1. [CRITICAL] Page has no H1 heading.

- **Dimension:** On Page Seo
- **Affected pages:** 1
- **Recommendation:** Add exactly one H1 tag containing the page's primary keyword. AI models use the H1 as a strong signal for page topic.

### 2. [HIGH] Title is too long (68 chars; maximum: 60).

- **Dimension:** On Page Seo
- **Affected pages:** 5
- **Recommendation:** Shorten the title to 60 characters or fewer to prevent truncation in search and AI results.

### 3. [HIGH] Article page is missing Article or BlogPosting schema. AI engines use Article schema to identify authoritative content.

- **Dimension:** Schema Markup
- **Affected pages:** 7
- **Recommendation:** Add an Article or BlogPosting JSON-LD block with headline, author, datePublished, and image fields.

### 4. [HIGH] AEO snippet readiness score is 25/100 — poor. This page is unlikely to be cited in AI search results.

- **Dimension:** Extractability
- **Affected pages:** 2
- **Recommendation:** Improve content structure for AI extraction: add question-format headings followed by direct 40-60 word answer paragraphs, ensure paragraphs stand alone without needing prior context, and add structured sections like FAQ, Key Takeaways, or How-To steps.

### 5. [HIGH] Title is too short (7 chars; minimum: 30).

- **Dimension:** On Page Seo
- **Affected pages:** 1
- **Recommendation:** Expand the title to at least 30 characters to improve keyword coverage and click-through rates.

### 6. [MEDIUM] Meta description is too short (77 chars; minimum: 120).

- **Dimension:** On Page Seo
- **Affected pages:** 7
- **Recommendation:** Expand the meta description to at least 120 characters to improve snippet quality in AI and search results.

### 7. [MEDIUM] No author attribution detected on this page.

- **Dimension:** Eeat
- **Affected pages:** 7
- **Recommendation:** Add a visible author byline with the author's name. Linking to an author bio page with credentials further strengthens E-E-A-T signals for AI citation systems.

### 8. [MEDIUM] Only 5% of headings are phrased as questions (threshold: 30%). Question-format headings improve AI snippet extraction.

- **Dimension:** Extractability
- **Affected pages:** 10
- **Recommendation:** Rephrase at least 30% of subheadings as questions that your audience is actually asking (e.g. 'How does X work?' instead of 'About X'). This increases the likelihood of appearing in AI-generated answers.

### 9. [MEDIUM] AEO snippet readiness score is 59/100 — moderate. There is room for improvement.

- **Dimension:** Extractability
- **Affected pages:** 8
- **Recommendation:** Enhance content structure: aim for more question headings with direct-answer paragraphs of 40–60 words, add a FAQ section or Key Takeaways block, and ensure paragraphs don't start with continuity markers like 'However' or 'Additionally'.

### 10. [MEDIUM] 3 of 7 images are missing alt text.

- **Dimension:** On Page Seo
- **Affected pages:** 2
- **Recommendation:** Add descriptive alt text to all images that convey information.

## Findings by Severity

- **Critical:** 1
- **High:** 15
- **Medium:** 38
- **Low:** 10
