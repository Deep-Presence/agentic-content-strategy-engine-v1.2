# Agent — Technical Readiness Page (v3 — Production)

> **Read CLAUDE.md and brand-system.md first, then this file.** This builds/rebuilds the `/technical-readiness` page.

---

## Mission

Build the Technical Readiness page — the page that answers **"Is my site technically ready for AI engines to discover and cite me?"** Shows the critical gap between traditional site health (high) and AI citation readiness (low). Absorbs 31 metrics from AEO Technical Readiness (#117-147) plus 7 Platform Intelligence metrics (#174-180).

**THE KEY INSIGHT:** Site Health is 95/100. AEO Readiness is 38.7/100. That gap IS the entire story. The site is technically excellent — fast, crawlable, secure. But the CONTENT isn't structured for AI citation. Make this gap visually unmissable.

---

## Files You Own

```
src/app/(dashboard)/technical-readiness/page.tsx
src/app/(dashboard)/technical-readiness/_components/
```

**Never touch** shared UI components, other pages, stores, or layout files.

---

## MANDATORY LAYOUT STANDARDS

### Density & Spacing

```
Page-level horizontal padding: max 24px — NO max-w-7xl or container wrappers
Section gaps: 16px
Card internal padding: 12px-16px
Table cell padding: 6px vertical, 8px horizontal
Table row height: 40px
```

Replace `p-6`/`p-8`/`gap-6`/`gap-8` with `p-3`/`p-4`/`gap-3`/`gap-4`. Remove `max-w-7xl mx-auto`.

### Font Sizes (non-negotiable)

```
Page title: 22px, font-weight 600, Space Grotesk
Page subtitle: 13px, var(--text-secondary)
KPI numbers: 28px, JetBrains Mono, font-weight 600
KPI labels: 11px, uppercase, letter-spacing 0.05em, var(--text-secondary)
Gauge score text: 40px, JetBrains Mono, font-weight 700
Gauge label: 14px, font-weight 500
Gauge grade badge: 12px, font-weight 600
Section headers: 15px, font-weight 600
Section subtitles: 12px, var(--text-secondary)
Table headers: 11px, uppercase, letter-spacing 0.05em
Table body: 13px
Table data values: 13px, JetBrains Mono
Radar axis labels: 11px
Bot names: 13px, font-weight 500
Bot company names: 12px, var(--text-secondary)
Status text (ALLOWED/BLOCKED): 11px, uppercase, font-weight 600
Platform tab labels: 12px
Preference values: 13px, JetBrains Mono
Severity badges: 10px, uppercase, font-weight 600
Drawer section headers: 14px, uppercase, font-weight 600
```

### Global Filter Bar

```tsx
<div className="flex items-center gap-3 px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <DateRangePicker /> {/* Mar 1, 2026 – Mar 28, 2026 */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <SeverityFilter /> {/* All Severities ▾ */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <DimensionFilter /> {/* All Dimensions ▾ */}
  <button className="ml-auto text-xs" style={{ color: 'var(--text-secondary)' }}>× Clear</button>
</div>
```

Full-width toolbar. No rounded corners. Height 44px. 0 gap below page title.

---

## Page Structure

### KPI Strip (6 cards, single row)

| KPI | Value | Sub | Styling | Metric # |
|-----|-------|-----|---------|----------|
| Site Health | 95 | /100 — Grade A | Green accent | #117 |
| AEO Readiness | 38.7 | /100 — THE GAP | Red accent | #118 |
| Snippet Readiness | 38.7 | /100 avg across pages | Red accent | #127 |
| Question Headings | 14.8% | vs 30% target | Amber | #129 |
| Critical Issues | 7 | findings blocking citation | Red text | #137 |
| llms.txt | Missing | not implemented | Red pill badge | #132 |

Cards: `1px solid var(--border)`, 12px padding. 28px JetBrains Mono values.

---

### Section 1: The Gap Visualization — HERO (full width)

Two large semi-circular gauges side by side. This is the hero visual — make it visually dominant.

**SVG Gauge Implementation:**

```tsx
interface GaugeProps {
  score: number;
  max?: number;
  color: string;
  label: string;
  grade: string;
  gradeColor: string;
  description: string;
}

function ScoreGauge({ score, max = 100, color, label, grade, gradeColor, description }: GaugeProps) {
  const pct = score / max;
  const r = 70; // radius
  const circumference = Math.PI * r; // semi-circle
  const offset = circumference * (1 - pct);

  return (
    <div className="text-center">
      <svg viewBox="0 0 160 95" width={240} height={140}>
        {/* Background arc */}
        <path d="M 10 85 A 70 70 0 0 1 150 85" fill="none" stroke="var(--border)" strokeWidth="14" strokeLinecap="round" />
        {/* Fill arc */}
        <path d="M 10 85 A 70 70 0 0 1 150 85" fill="none" stroke={color} strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${circumference}`} strokeDashoffset={`${offset}`}
          style={{ transition: 'stroke-dashoffset 1.2s ease-out' }} />
        {/* Score text */}
        <text x="80" y="72" textAnchor="middle" style={{ fontFamily: 'JetBrains Mono', fontSize: '40px', fontWeight: 700, fill: 'var(--text-primary)' }}>
          {score}
        </text>
      </svg>
      <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>{label}</div>
      <span style={{
        fontSize: '12px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
        background: gradeColor, color: 'white', display: 'inline-block', marginTop: '4px'
      }}>
        {grade}
      </span>
      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '200px', margin: '8px auto 0' }}>
        {description}
      </div>
    </div>
  );
}
```

**Left gauge:** `score={95}` `color="#34B27B"` `label="Site Health"` `grade="Grade A"` `gradeColor="#34B27B"` `description="Your site is technically excellent."`

**Right gauge:** `score={38.7}` `color="#E5484D"` `label="AEO Readiness"` `grade="Grade F"` `gradeColor="#E5484D"` `description="Your content isn't structured for AI citation."`

**Between/below gauges:** Narrative card — centered, max-width 400px, `border: 1px solid var(--border)`, `background: var(--surface)`, 16px padding, 12px text:

> "Your site is healthy, but AI engines can't extract useful answers from it. Focus: question headings, FAQ sections, comparison tables, and llms.txt."

---

### Section 2: Dimension Radar + Table (40% / 60% split)

**Left: Recharts `RadarChart`**

8 dimensions. Fill: `var(--accent)` at 12% opacity. Stroke: `var(--accent)` 2px. Grid: `var(--border)`. Labels: 11px. Ensure labels don't overlap.

**Right: Dimension Scores Table**

| Dimension | Score | Weight | Findings | Status |
|-----------|-------|--------|----------|--------|

Status icons: ✅ (score ≥ 90), ⚠ (70-89), ❌ (< 70).

**Rows are clickable** — `cursor-pointer`, hover `var(--accent-subtle)`. Clicking a dimension **filters the Findings table** (Section 6) to only that dimension. When filtered: selected row gets `background: var(--accent-subtle)` + small "×" button to clear filter.

Hint below table: "Click a dimension to filter findings below" — 11px var(--text-secondary).

```typescript
const DIMENSIONS = [
  { name: "Crawlability", score: 100, weight: "20%", findings: 4, status: "pass" },
  { name: "Performance", score: 88, weight: "10%", findings: 899, status: "warn" },
  { name: "On-Page SEO", score: 84, weight: "15%", findings: 458, status: "warn" },
  { name: "Extractability", score: 95, weight: "20%", findings: 377, status: "pass" },
  { name: "Schema Markup", score: 98, weight: "10%", findings: 228, status: "pass" },
  { name: "E-E-A-T", score: 100, weight: "15%", findings: 28, status: "pass" },
  { name: "Freshness", score: 100, weight: "5%", findings: 41, status: "pass" },
  { name: "Security", score: 97, weight: "5%", findings: 600, status: "pass" },
];
```

---

### Section 3: Two-column — AI Bot Access + Snippet Distribution

**Left: AI Bot Access Card (#130, #131, #132, #133)**

Compact card. Each bot row: **32px height**.

```typescript
const BOT_STATUS = [
  { name: "GPTBot", company: "OpenAI", domain: "openai.com", status: "allowed", robotsTxt: true },
  { name: "ClaudeBot", company: "Anthropic", domain: "anthropic.com", status: "allowed", robotsTxt: true },
  { name: "PerplexityBot", company: "Perplexity", domain: "perplexity.ai", status: "allowed", robotsTxt: true },
  { name: "Google-Extended", company: "Google", domain: "google.com", status: "allowed", robotsTxt: true },
  { name: "CCBot", company: "Common Crawl", domain: "commoncrawl.org", status: "allowed", robotsTxt: true },
];
```

Each row: favicon (16px, from `domain`) + bot name (13px font-weight 500) + company (12px var(--text-secondary) in parentheses) + status dot (green ALLOWED / red BLOCKED, 11px uppercase) + robots.txt checkmark (✓ green / ✗ red, 10px).

Below bots, three status lines:
```
robots.txt   ✅ Present
llms.txt     ❌ Missing            ← this row: background: rgba(229, 72, 77, 0.06) — critical gap highlight
Sitemap      ✅ Found (847 URLs)
```

**Right: Snippet Readiness Distribution (#127, #144)**

Recharts `BarChart`. Height: **200px**.

```typescript
const SNIPPET_DISTRIBUTION = [
  { range: "0-20", count: 62, label: "Uncitable", color: "#E5484D" },
  { range: "21-40", count: 45, label: "Poor", color: "#E87C3F" },
  { range: "41-60", count: 38, label: "Fair", color: "#F5A623" },
  { range: "61-80", count: 32, label: "Good", color: "#6CB8D2" },
  { range: "81-100", count: 23, label: "Excellent", color: "#34B27B" },
];
```

Count numbers displayed **on top of each bar** (NOT inside) — 11px JetBrains Mono.

X-axis labels: "0-20 Uncitable", "21-40 Poor", etc. Rotate 45° if needed: `<XAxis angle={-45} textAnchor="end" tick={{ fontSize: 10 }} />`

**Callout below chart:** full-width bar, `background: rgba(229, 72, 77, 0.06)`, `border: 1px solid rgba(229, 72, 77, 0.15)`, 8px padding, 12px text:
"⚠ 62 pages have snippet readiness below 20 — these are virtually uncitable by AI engines."

---

### Section 4: Bot Crawl Activity (#134-136, #174-180) — full width

Recharts `LineChart`. Height: **260px**. 28 days. One line per bot.

Platform brand colors (constants — these represent external brands):
```typescript
const BOT_COLORS = {
  GPTBot: "#10A37F",
  ClaudeBot: "#D4A574",
  PerplexityBot: "#20B8CD",
  "Google-Extended": "#4285F4",
  Gemini: "#886FBF",
};
```

**Legend:** Inline with section title (right-aligned on same line). Each item: colored line (16px wide) + bot name (11px) + real favicon (12px from parent company domain).

**Mock data:**
```typescript
const generateBotCrawlData = () => {
  return Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    GPTBot: 280 + Math.floor(Math.random() * 40) + i * 2,
    ClaudeBot: 260 + Math.floor(Math.random() * 30) + i * 3,
    PerplexityBot: 220 + Math.floor(Math.random() * 40) + i * 4,
    "Google-Extended": 300 + Math.floor(Math.random() * 20) + i * 1,
    Gemini: 180 + Math.floor(Math.random() * 30) + i * 2,
  }));
};
```

Y-axis: "Requests/day" (11px). Hover tooltip: exact count per bot for that day.

**Summary rows below chart (two rows, 11px labels, JetBrains Mono values):**
```
TOTAL CRAWLS (28d):  [favicon] GPTBot 8,400  |  [favicon] ClaudeBot 7,900  |  [favicon] PerplexityBot 7,200  |  [favicon] Google 8,800  |  [favicon] Gemini 5,600
LAST CRAWL:          [favicon] GPTBot 2h ago  |  [favicon] ClaudeBot 4h ago  |  [favicon] PerplexityBot 1h ago  |  [favicon] Google 6h ago  |  [favicon] Gemini 12h ago
```

---

### Section 5: Platform Citation Preferences (#174, #175, #180) — full width

Full-width card. Platform selector tabs at top.

Tabs: real favicon (14px) + platform name (12px). Selected: `border-bottom: 2px solid var(--accent)`, font-weight 600. Inactive: no border, var(--text-secondary).

Below tabs: **40% radar / 60% preference table** (consistent split with Section 2).

**Radar:** 8 structural signals. Fill: `var(--accent)` at 12% opacity. Stroke: 2px.

**Preference table:**
| Signal | Preference | Strength |
|--------|-----------|----------|
Each row: signal name (13px) + percentage (13px JetBrains Mono) + thin horizontal bar (8px height, var(--accent) fill proportional to %).

```typescript
const PLATFORM_PREFERENCES: Record<string, { signal: string; value: number }[]> = {
  chatgpt: [
    { signal: "FAQ Sections", value: 72 },
    { signal: "Tables", value: 65 },
    { signal: "Headers", value: 88 },
    { signal: "Word Count", value: 78 },
    { signal: "Lists", value: 70 },
    { signal: "Schema", value: 45 },
    { signal: "Citations", value: 82 },
    { signal: "Reading Level", value: 60 },
  ],
  claude: [
    { signal: "FAQ Sections", value: 55 },
    { signal: "Tables", value: 48 },
    { signal: "Headers", value: 92 },
    { signal: "Word Count", value: 85 },
    { signal: "Lists", value: 58 },
    { signal: "Schema", value: 35 },
    { signal: "Citations", value: 90 },
    { signal: "Reading Level", value: 75 },
  ],
  perplexity: [
    { signal: "FAQ Sections", value: 80 },
    { signal: "Tables", value: 72 },
    { signal: "Headers", value: 78 },
    { signal: "Word Count", value: 65 },
    { signal: "Lists", value: 82 },
    { signal: "Schema", value: 55 },
    { signal: "Citations", value: 88 },
    { signal: "Reading Level", value: 70 },
  ],
  google_ai: [
    { signal: "FAQ Sections", value: 68 },
    { signal: "Tables", value: 58 },
    { signal: "Headers", value: 85 },
    { signal: "Word Count", value: 72 },
    { signal: "Lists", value: 65 },
    { signal: "Schema", value: 78 },
    { signal: "Citations", value: 75 },
    { signal: "Reading Level", value: 82 },
  ],
  gemini: [
    { signal: "FAQ Sections", value: 62 },
    { signal: "Tables", value: 55 },
    { signal: "Headers", value: 80 },
    { signal: "Word Count", value: 88 },
    { signal: "Lists", value: 60 },
    { signal: "Schema", value: 42 },
    { signal: "Citations", value: 85 },
    { signal: "Reading Level", value: 68 },
  ],
};
```

**Dynamic insight callout below:** Bordered card, 12px text. Changes per selected platform:

```typescript
const PLATFORM_INSIGHTS: Record<string, string> = {
  chatgpt: "ChatGPT favors content with strong header hierarchy (88%) and external citations (82%). Your content's FAQ rate (20%) is well below ChatGPT's preference (72%).",
  claude: "Claude heavily weights word count (85%) and external citations (90%). It's less concerned with Schema markup (35%). Focus on depth and sourcing.",
  perplexity: "Perplexity strongly prefers external citations (88%) and list formatting (82%). FAQ sections (80%) are also highly valued. It rewards well-structured, reference-heavy content.",
  google_ai: "Google AI Mode weights Schema markup (78%) highest among all platforms. Headers (85%) and reading level accessibility (82%) are also key drivers.",
  gemini: "Gemini prioritizes word count depth (88%) and external citations (85%). It's the least Schema-dependent platform (42%). Long-form, well-cited content wins.",
};
```

---

### Section 6: Top Findings (#137-147) — full width table with drawer

Sorted by severity (Critical → High → Medium → Low). When dimension filter is active (from Section 2), only show findings for that dimension.

| Severity | Finding | Dimension | Pages | Fix | Impact |
|----------|---------|-----------|-------|-----|--------|

Severity pill badges: CRITICAL = `background: #E5484D`, white text. HIGH = `background: #F5A623`, dark text. MEDIUM = `background: var(--accent)`, white text. LOW = `background: var(--text-secondary)` at 20%, dark text. 10px uppercase.

```typescript
const FINDINGS = [
  { severity: "critical", finding: "AEO snippet readiness < 25/100", dimension: "Extractability", pages: 62, fix: "Add question headings + direct answers", impact: "critical" },
  { severity: "critical", finding: "Question-heading ratio < 30%", dimension: "Extractability", pages: 200, fix: "Rephrase 30%+ headings as questions", impact: "critical" },
  { severity: "high", finding: "Page has no H1 heading", dimension: "On-Page SEO", pages: 7, fix: "Add exactly one H1 tag per page", impact: "high" },
  { severity: "high", finding: "Missing Article/BlogPosting schema", dimension: "Schema Markup", pages: 28, fix: "Add JSON-LD with headline, author, date", impact: "high" },
  { severity: "high", finding: "Title too long (>60 chars)", dimension: "On-Page SEO", pages: 87, fix: "Shorten to 60 characters", impact: "medium" },
  { severity: "high", finding: "Images missing alt text", dimension: "On-Page SEO", pages: 45, fix: "Add descriptive alt text", impact: "medium" },
  { severity: "medium", finding: "Meta description too short (<120)", dimension: "On-Page SEO", pages: 84, fix: "Expand to 120-160 characters", impact: "low" },
  { severity: "medium", finding: "No FAQ schema on pages with FAQ content", dimension: "Schema Markup", pages: 15, fix: "Add FAQPage JSON-LD", impact: "medium" },
  { severity: "medium", finding: "Internal link depth > 3 clicks", dimension: "Crawlability", pages: 34, fix: "Flatten site structure", impact: "low" },
  { severity: "medium", finding: "Avg HTML size > 200KB", dimension: "Performance", pages: 23, fix: "Remove unused scripts/styles", impact: "low" },
  { severity: "low", finding: "No llms.txt file present", dimension: "Crawlability", pages: 1, fix: "Create llms.txt with citation guidance", impact: "medium" },
  { severity: "low", finding: "External resources > 50 per page", dimension: "Performance", pages: 18, fix: "Reduce third-party scripts", impact: "low" },
];
```

All rows: `cursor-pointer`, hover `var(--accent-subtle)`.

**Row click → Side Drawer (50% viewport width)**

Backdrop: `rgba(0,0,0,0.15)`. Close button top-right.

Drawer header: Finding text (16px font-weight 600), Severity badge, Dimension badge.

**Drawer Section A: AFFECTED PAGES**

Scrollable list, max-height 300px. First 10 URLs with individual snippet readiness scores.

```typescript
const AFFECTED_PAGES_EXAMPLE = [
  { url: "/blog/getting-started", score: 12 },
  { url: "/docs/api-reference", score: 18 },
  { url: "/blog/changelog-march", score: 8 },
  { url: "/docs/deployment", score: 22 },
  { url: "/blog/team-update", score: 15 },
  { url: "/docs/authentication", score: 19 },
  { url: "/blog/vibe-coding-intro", score: 11 },
  { url: "/docs/webhooks", score: 20 },
  { url: "/blog/ai-trends-2026", score: 14 },
  { url: "/docs/database-setup", score: 16 },
];
```

Each URL: 12px, clickable (external link icon ↗), score in JetBrains Mono (colored: red < 20, amber 20-40, green > 40). "Showing 10 of 62 pages" at bottom (11px var(--text-secondary)).

**Drawer Section B: HOW TO FIX**

Numbered steps (13px). Technical terms in JetBrains Mono.

```
1. Add question-format H2 headings that match user queries
   Example: "How does AI handle patient phone calls?"

2. Follow each question heading with a direct 2-3 sentence answer
   The first sentence should directly answer the question.

3. Add FAQ sections with 3-5 common questions per page
   Use <details> or dedicated FAQ blocks.

4. Include comparison tables where relevant
   Side-by-side feature comparisons increase citation likelihood.

5. Add key takeaways section at top or bottom
   Summarize the 3-5 most important points.

6. Ensure external citations link to authoritative sources
   Reference studies, documentation, or industry reports.
```

**Drawer Section C: ESTIMATED IMPACT**

"Fixing this would improve AEO Readiness by approximately +12 points (38.7 → ~51)"

Show as mini before/after indicator:
```
Current: 38.7  [████████░░░░░░░░░░░░░░░░░] 
After:   ~51   [█████████████░░░░░░░░░░░░░]  (+12 pts)
```

**Drawer Section D: ACTION**

"Mark as Fixed" toggle button. On click: show toast "Marked as fixed — will re-audit on next scan."

---

## Metrics Coverage Checklist

### AEO Technical Readiness (#117-147) — 31 metrics:

- [x] #117 Overall Site Health Score → KPI strip + Left gauge (95/100)
- [x] #118 AEO Readiness Score → KPI strip + Right gauge (38.7/100)
- [x] #119 Crawlability Score → Dimension radar + table (100)
- [x] #120 Performance Score → Dimension radar + table (88)
- [x] #121 On-Page SEO Score → Dimension radar + table (84)
- [x] #122 Extractability Score → Dimension radar + table (95)
- [x] #123 Schema Markup Score → Dimension radar + table (98)
- [x] #124 E-E-A-T Score → Dimension radar + table (100)
- [x] #125 Freshness Score → Dimension radar + table (100)
- [x] #126 Security Score → Dimension radar + table (97)
- [x] #127 Snippet Readiness per Page → KPI strip + Distribution chart
- [x] #128 Pages with Structured Data → Bot Access card (Schema Markup dimension)
- [x] #129 Question-Heading Ratio → KPI strip (14.8% vs 30% target)
- [x] #130 AI Bot Access Status → Bot Access card (5 bots with status)
- [x] #131 robots.txt Status → Bot Access card (✅ Present)
- [x] #132 llms.txt Status → KPI strip (Missing) + Bot Access card (❌ Missing, highlighted)
- [x] #133 Sitemap Health → Bot Access card (✅ Found 847 URLs)
- [x] #134 Bot Crawl Frequency → Bot Crawl Activity chart (5 lines, 28 days)
- [x] #135 Bot Crawl Recency → Bot Crawl summary row "LAST CRAWL"
- [x] #136 Bot Crawl Depth → Bot Crawl summary row "TOTAL CRAWLS"
- [x] #137 Critical Findings Count → KPI strip (7) + Findings table (CRITICAL rows)
- [x] #138 High Findings Count → Findings table (HIGH rows)
- [x] #139 Pages Missing H1 → Findings table row (7 pages)
- [x] #140 Pages with Duplicate Titles → Findings table (implied in On-Page SEO findings)
- [x] #141 Pages Missing Alt Text → Findings table row (45 pages)
- [x] #142 Pages Missing Meta Description → Findings table row (84 pages)
- [x] #143 Pages Missing Article Schema → Findings table row (28 pages)
- [x] #144 Pages with Poor AEO Snippet Readiness → Findings table row (62 pages) + Distribution chart
- [x] #145 Average HTML Size → Findings table row (23 pages > 200KB)
- [x] #146 External Resources per Page → Findings table row (18 pages > 50)
- [x] #147 Inline JS Size → Findings table (implied in Performance findings)

### Platform Intelligence (#174-180) — 7 metrics:

- [x] #174 Platform Citation Preference Profile → Platform Preference radar (8 signals per platform)
- [x] #175 Platform-Specific CPS → Platform Preference table (preference % per signal)
- [x] #176 Platform Citation Latency → Bot Crawl summary "LAST CRAWL" times
- [x] #177 Platform-Specific SOV → Platform Preference section (per-platform view)
- [x] #178 Platform Query Coverage → Platform Preference section
- [x] #179 Platform-Specific Competitor Ranking → Platform Preference insight text
- [x] #180 Platform Response Format → Platform Preference section (signal preferences)

---

## Brand System Rules

- CSS variables for all UI colors — never hardcode hex
- Platform brand colors for bot crawl chart lines are acceptable as constants
- 1px borders on all cards — no borderless, no shadows, no gradients
- JetBrains Mono for ALL data values. Space Grotesk for ALL text.
- Real platform logos via Google Favicon API — never colored circles
- Do NOT set `crossOrigin="anonymous"` on favicon images
- Light + dark mode via CSS variables

---

## Verification

```bash
npm run dev
npx tsc --noEmit
```

1. Padding tight — 24px max horizontal, 16px between sections
2. Filter bar full-width toolbar, no rounded corners, 44px
3. KPI strip: 6 cards, 28px JetBrains Mono values
4. Dual gauges: large (240×140), 40px score text, grade pill badges, gap narrative in bordered card
5. Dimension radar: 8 axes, labels readable, no overlap
6. Dimension table: 8 rows, clickable, filters findings table on click
7. Bot access: 5 bots, 32px rows, real favicons, llms.txt missing highlighted red
8. Snippet distribution: 5 bars, counts on top, callout annotation below
9. Bot crawl: 260px, 5 lines with platform colors, inline legend with favicons, summary rows
10. Platform preferences: 5 tabs with favicons, radar changes per selection, insight text changes dynamically
11. Findings table: 12 rows, severity pills, dimension filter from Section 2 works
12. Findings drawer: opens on row click, 4 sections (affected pages, fix steps, impact, action)
13. All favicons loading — Network tab 0 404s
14. Both light and dark mode work
15. `npm run build` succeeds

---

## Completion Criteria

- [ ] Page loads at `/technical-readiness` with no console errors
- [ ] Filter bar: full-width toolbar with date + severity + dimension filters
- [ ] KPI strip: 6 cards with correct values and styling
- [ ] Dual gauge hero: Site Health 95 (green arc) vs AEO Readiness 38.7 (red arc), 40px scores
- [ ] Grade badges: "Grade A" green pill, "Grade F" red pill
- [ ] Gap narrative: bordered card, centered between gauges
- [ ] Dimension radar: 8 axes with correct scores
- [ ] Dimension table: 8 rows, status icons, clickable → filters findings
- [ ] Dimension filter state: selected row highlighted, "×" to clear, hint text
- [ ] Bot access: 5 bots with real favicons, 32px row height, status indicators
- [ ] llms.txt "Missing" row visually highlighted with red background
- [ ] Snippet distribution: 5 colored bars, counts on top, callout below
- [ ] Bot crawl: 260px, 5 lines, platform brand colors, inline legend with favicons
- [ ] Bot crawl summary: 2 rows with totals and last crawl times
- [ ] Platform preferences: 5 tabs with real favicons, radar + table, dynamic insight
- [ ] All 5 platform preference datasets render correctly when switching tabs
- [ ] Findings table: 12 rows, severity pills, sorted Critical → Low
- [ ] Findings drawer: opens on click, 4 sections populated
- [ ] Drawer affected pages: scrollable list with scores, "Showing X of Y"
- [ ] Drawer fix steps: numbered, concrete instructions
- [ ] Drawer impact: before/after indicator
- [ ] All 38 metrics from checklist verified present
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts, real logos
- [ ] Density: no gap > 16px, no padding > 16px, no page margin > 24px
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds