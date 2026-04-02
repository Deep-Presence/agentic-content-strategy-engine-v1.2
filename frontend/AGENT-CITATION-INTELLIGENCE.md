# Agent — Citation Intelligence Page (v3 — Production)

> **Read CLAUDE.md and brand-system.md first, then this file.** This replaces whatever exists at `/analytics` with a full rebuild.

---

## Mission

Build the Citation Intelligence page — the **primary analytics page** that answers **"Am I visible in AI search, and how is my visibility changing?"** This is the first page a CMO opens on Monday morning. It must immediately communicate: are we growing, are we cited, which platforms cite us, and what's driving the numbers.

This page absorbs 40 metrics: Citation Core (#1-16), Citation Dynamics (#17-27), Platform Intelligence subset (#174, #177), and Revenue Proxy (#187-192).

Layout follows the AirOps pattern: **your metrics on the left, competitor context on the right.**

---

## Files You Own

```
src/app/(dashboard)/analytics/page.tsx
src/app/(dashboard)/analytics/_components/
```

**DELETE or replace** whatever currently exists at this route. This is a full rebuild. **Never touch** shared UI components, other pages, stores, or layout files.

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

Replace `p-6`/`p-8`/`gap-6`/`gap-8` → `p-3`/`p-4`/`gap-3`/`gap-4`. Remove `max-w-7xl mx-auto`.

### Font Sizes (non-negotiable)

```
Page title: 22px, font-weight 600, Space Grotesk
Page subtitle: 13px, var(--text-secondary)
KPI numbers: 28px, JetBrains Mono, font-weight 600
KPI labels: 11px, uppercase, letter-spacing 0.05em, var(--text-secondary)
KPI trend text: 12px
Section headers: 15px, font-weight 600
Section subtitles: 12px, var(--text-secondary)
Table headers: 11px, uppercase, letter-spacing 0.05em
Table body: 13px
Table data values: 13px, JetBrains Mono
Chart axis labels: 11px
Chart legend: 11px
Donut center text: 24px, JetBrains Mono, font-weight 600
Platform grid values: 20px, JetBrains Mono
Platform grid labels: 11px
Drawer section headers: 14px, uppercase, font-weight 600
```

### Global Filter Bar

```tsx
<div className="flex items-center gap-3 px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <DateRangePicker /> {/* Mar 1, 2026 – Mar 28, 2026 */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <PlatformFilter /> {/* All Platforms ▾ */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <ClusterFilter /> {/* All Clusters ▾ */}
  <button className="ml-auto text-xs" style={{ color: 'var(--text-secondary)' }}>× Clear</button>
</div>
```

Full-width toolbar. No rounded corners. Height 44px. 0 gap below page title.

---

## Page Structure

### KPI Strip (6 cards, single row)

| KPI | Value | Trend | Sub | Metric # |
|-----|-------|-------|-----|----------|
| Share of Voice | 12.4% | ↑ from 8.1% | across all platforms | #1 |
| Citation Presence | 67% | ↑ from 52% | queries where you appear | #3 |
| Avg Citation Position | 2.3 | ↑ from 3.1 | when cited, your rank | #4 |
| Total Citations | 847 | +124 this period | across 5 platforms | #6 |
| Brand Mentions | 1,203 | +89 this period | mentioned without citation | #7 |
| Est. AI Referrals | ~3,200/mo | — | proxy from citation volume | #187 |

Cards: `1px solid var(--border)`, 12px padding. 28px JetBrains Mono values. Trend: 12px, green positive, red negative.

---

### Section 1: Citation Momentum — HERO (full width) (#9, #10, #11, #25, #27)

Recharts `ComposedChart`. Height: **300px**. Daily data, 28 days.

**Two y-axes:**
- Left: Citation count — stacked `Bar` components colored by platform
- Right: SOV % — `Line` showing your SOV trend

Platform bar colors (stacked):
```typescript
const PLATFORM_COLORS = {
  ChatGPT: "#10A37F",
  Claude: "#D4A574",
  Perplexity: "#20B8CD",
  "Google AI": "#4285F4",
  Gemini: "#886FBF",
};
```

Your SOV line: 3px stroke, `var(--accent)`, filled dots at each data point.

**Legend:** Inline with section title, right-aligned. Each item: colored indicator + platform name + real favicon (12px from domain).

**Mock data:**
```typescript
const generateMomentumData = () => {
  return Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    ChatGPT: Math.floor(8 + Math.random() * 4 + i * 0.3),
    Claude: Math.floor(5 + Math.random() * 3 + i * 0.2),
    Perplexity: Math.floor(4 + Math.random() * 3 + i * 0.25),
    "Google AI": Math.floor(3 + Math.random() * 2 + i * 0.15),
    Gemini: Math.floor(2 + Math.random() * 2 + i * 0.1),
    sov: 8.1 + (i * 0.16) + (Math.random() * 0.5 - 0.25),
  }));
};
```

Tooltip on hover: date, per-platform citation count, total citations that day, SOV %.

---

### Section 2: Two-column — Your Visibility (55% left) vs Competitor Leaderboard (45% right)

#### Left: Your Visibility Breakdown

**A. Citation vs Mention Rate (#3, #7, #12)**

Two Recharts `PieChart` donut charts side by side.

Left donut: **Cited 67%** — `innerRadius={40} outerRadius={60}`. Active fill: `var(--accent)`. Inactive: `var(--border)`. Center text: "67%" in 24px JetBrains Mono.

Right donut: **Mentioned 89%** — same dimensions. Active fill: lighter teal (var(--accent) at 60% opacity or a lighter shade). Center text: "89%".

Labels below each donut: "Cited" / "Mentioned" (12px font-weight 500).

Below both donuts (12px, var(--text-secondary), max 2 lines):
"You're mentioned in 89% of tracked queries but only cited (with a link) in 67%. The gap represents opportunities to convert mentions into citations by improving content structure."

```typescript
const VISIBILITY = {
  cited: 0.67,
  mentioned: 0.89,
  totalQueries: 47,
};
```

**B. Citation Sentiment & Context (#13, #14, #15)**

Compact card below the donuts.

Sentiment bars (horizontal, stacked or separate):
```typescript
const SENTIMENT = {
  positive: 0.72,
  neutral: 0.22,
  negative: 0.06,
};
```

Each bar: label (12px) + percentage (12px JetBrains Mono) + horizontal bar. Colors: positive = green, neutral = gray, negative = red.

Below sentiment: context category cards in a 2×3 or 3×2 grid:
```typescript
const CONTEXT_CATEGORIES = [
  { category: "Recommendation", percentage: 42 },
  { category: "Comparison", percentage: 28 },
  { category: "Feature mention", percentage: 18 },
  { category: "Criticism", percentage: 6 },
  { category: "Neutral reference", percentage: 6 },
];
```

Each card: 11px label + 16px JetBrains Mono percentage. `1px solid var(--border)`, 8px padding.

Below: "When AI engines mention you, the context is overwhelmingly positive (72%). Negative mentions are primarily around pricing concerns." (12px, var(--text-secondary))

#### Right: Competitor Leaderboard (#1, #2, #5, #6)

SOV-ranked brand list:

```typescript
const LEADERBOARD = [
  { rank: 1, domain: "bolt.new", name: "Bolt.new", sov: 18.2, citations: 1420, delta: -0.8 },
  { rank: 2, domain: "lovable.dev", name: "Lovable", sov: 12.4, citations: 847, delta: 4.3, isYou: true },
  { rank: 3, domain: "cursor.com", name: "Cursor", sov: 11.8, citations: 921, delta: 1.2 },
  { rank: 4, domain: "replit.com", name: "Replit", sov: 9.1, citations: 710, delta: -2.1 },
  { rank: 5, domain: "v0.dev", name: "V0.dev", sov: 7.3, citations: 571, delta: 0.9 },
  { rank: 6, domain: "emergent.sh", name: "Emergent", sov: 5.2, citations: 406, delta: 3.1 },
];
```

Each row: rank (12px JetBrains Mono) + real favicon (16px) + domain name (13px font-weight 500) + SOV% (13px JetBrains Mono) + citation count (13px JetBrains Mono var(--text-secondary)) + delta (11px, colored).

**Your row:** `background: var(--accent-subtle)`, name in bold, `[YOU]` teal badge.

Clickable rows → show toast "View in Competitive Position →" or link to `/competitive-position`.

**Below leaderboard:** Mini area chart (80px height, full width of right column) showing all competitor SOV lines over 28 days — same data as Competitive Position battle chart but smaller. No axes, just the lines. Gives "at a glance" competitive context.

---

### Section 3: Platform Intelligence Grid (#174, #177, #8, #16) — full width

5-column grid. One column per AI platform. Each column: `1px solid var(--border)`, 12px padding.

```typescript
const PLATFORM_GRID = [
  { platform: "ChatGPT", domain: "openai.com", citations: 312, sov: 14.2, avgRank: 2.1, coverage: 78, sentiment: "Positive" },
  { platform: "Claude", domain: "anthropic.com", citations: 189, sov: 11.8, avgRank: 2.8, coverage: 62, sentiment: "Positive" },
  { platform: "Perplexity", domain: "perplexity.ai", citations: 156, sov: 13.1, avgRank: 1.9, coverage: 71, sentiment: "Positive" },
  { platform: "Google AI", domain: "google.com", citations: 118, sov: 9.4, avgRank: 3.2, coverage: 55, sentiment: "Neutral" },
  { platform: "Gemini", domain: "gemini.google.com", citations: 72, sov: 8.7, avgRank: 3.5, coverage: 48, sentiment: "Positive" },
];
```

Per column:
- Platform favicon (20px, from domain) + name (13px font-weight 600)
- Citations: 20px JetBrains Mono, font-weight 600
- SOV: 13px JetBrains Mono + "%" suffix
- Avg Rank: 13px JetBrains Mono
- Coverage: 13px JetBrains Mono + "%"
- Sentiment: colored pill (Positive=green, Neutral=gray, Negative=red)
- Sparkline: Recharts `AreaChart` (48px height, no axes), 28-day citation trend per platform. Fill: platform color at 10%. Stroke: platform color.

Labels for each metric: 11px, var(--text-secondary), uppercase.

The column with highest SOV gets a `border-top: 2px solid var(--accent)`.

**Generate 28-day sparkline data per platform:**
```typescript
const generatePlatformSparkline = (baseCount: number) => {
  return Array.from({ length: 28 }, (_, i) => ({
    day: i + 1,
    value: Math.max(0, Math.floor(baseCount / 28 * (0.6 + Math.random() * 0.8) + i * 0.3)),
  }));
};
```

---

### Section 4: Citation URL Table (#6, #8, #9, #16, #17) — full width

Every URL of yours that gets cited, ranked by citation count.

| Column | Width | Content |
|--------|-------|---------|
| URL | 25% | Your content URL (truncated, 12px, external link icon ↗) |
| Title | 18% | Page title (13px font-weight 500, ellipsis) |
| Citations | 8% | Total count, 13px JetBrains Mono |
| Platforms | 15% | 5 filled/empty favicon dots (12px each): filled = cited on that platform, empty circle = not |
| Queries | 7% | Number of queries served, JetBrains Mono |
| CPS | 7% | Citation Prediction Score, colored: green ≥0.6, amber 0.45-0.59, red <0.45 |
| First Cited | 10% | Date first detected (12px) |
| Velocity | 7% | Citations/week + arrow (↑↓—), JetBrains Mono |

Sortable. Default: Citations descending. Row: 40px, cursor-pointer, hover `var(--accent-subtle)`.

```typescript
const CITATION_URLS = [
  { url: "lovable.dev/blog/ai-app-builder-comparison", title: "AI App Builder Comparison Guide", citations: 63, platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: true, gemini: false }, queries: 12, cps: 0.713, firstCited: "2026-01-15", velocity: 4.8, velocityTrend: "up" },
  { url: "lovable.dev/blog/lovable-vs-cursor", title: "Lovable vs Cursor: Honest Review", citations: 38, platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: true, gemini: false }, queries: 8, cps: 0.654, firstCited: "2026-01-22", velocity: 3.9, velocityTrend: "up" },
  { url: "lovable.dev/blog/vibe-coding-enterprise", title: "Vibe Coding for Enterprise Teams", citations: 31, platforms: { chatgpt: false, claude: true, perplexity: true, google_ai: true, gemini: false }, queries: 6, cps: 0.649, firstCited: "2026-02-01", velocity: 3.2, velocityTrend: "up" },
  { url: "lovable.dev/blog/bolt-new-alternatives", title: "Bolt.new Alternatives in 2026", citations: 29, platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: false, gemini: false }, queries: 9, cps: 0.521, firstCited: "2026-02-14", velocity: 1.4, velocityTrend: "down" },
  { url: "lovable.dev/blog/security-ai-apps", title: "Security in AI-Generated Apps", citations: 24, platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: false }, queries: 5, cps: 0.482, firstCited: "2026-02-08", velocity: 2.1, velocityTrend: "flat" },
  { url: "lovable.dev/blog/non-tech-founder-guide", title: "Non-Technical Founder's Guide", citations: 22, platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: true }, queries: 7, cps: 0.538, firstCited: "2026-02-20", velocity: 2.9, velocityTrend: "up" },
  { url: "lovable.dev/docs/getting-started", title: "Getting Started Guide", citations: 19, platforms: { chatgpt: true, claude: false, perplexity: false, google_ai: true, gemini: true }, queries: 4, cps: 0.521, firstCited: "2026-01-10", velocity: 1.5, velocityTrend: "flat" },
  { url: "lovable.dev/blog/rbac-ai-apps", title: "RBAC in AI-Generated Applications", citations: 18, platforms: { chatgpt: false, claude: false, perplexity: true, google_ai: false, gemini: false }, queries: 3, cps: 0.459, firstCited: "2026-02-25", velocity: 0.8, velocityTrend: "down" },
  { url: "lovable.dev/docs/api-reference", title: "API Reference Documentation", citations: 14, platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: false, gemini: false }, queries: 2, cps: 0.612, firstCited: "2026-01-18", velocity: 1.2, velocityTrend: "flat" },
  { url: "lovable.dev/blog/soc2-compliance", title: "SOC 2 for AI Dev Platforms", citations: 8, platforms: { chatgpt: false, claude: false, perplexity: false, google_ai: true, gemini: false }, queries: 2, cps: 0.385, firstCited: "2026-03-05", velocity: 0.5, velocityTrend: "down" },
];
```

---

### Side Drawer — Citation URL Detail (50% viewport width)

Opens on table row click. Backdrop: `rgba(0,0,0,0.15)`. Close button top-right.

**Drawer header:**
```
"AI App Builder Comparison Guide"
lovable.dev/blog/ai-app-builder-comparison ↗
First cited: Jan 15, 2026  |  Total citations: 63
```

Title: 16px font-weight 600. URL: 12px var(--text-secondary) + ↗ icon. Metadata: 11px var(--text-secondary).

**Drawer sections (each with 14px uppercase header, border-top separator):**

**A. CITATION TIMELINE**
Mini Recharts AreaChart. Full drawer width. 120px height. Daily citations. Fill: var(--accent) at 10%. Stroke: var(--accent).

**B. PLATFORM BREAKDOWN**
5 cards in a row. Each: platform favicon (16px) + name (11px) + citation count (16px JetBrains Mono) + trend arrow + "Cited ✓" / "Not cited ✗" (10px). Card: `1px solid var(--border)`.

**C. QUERIES SERVED (#20)**
List of queries this URL answers. Each row: query text (12px) + platform favicon showing where this URL is cited for this query + position (1st/2nd/3rd cited source, 11px JetBrains Mono).

```typescript
const QUERIES_SERVED = [
  { query: "best AI app builder comparison", platform: "ChatGPT", position: 1 },
  { query: "lovable vs bolt.new vs cursor", platform: "Perplexity", position: 1 },
  { query: "AI app builder features 2026", platform: "Google AI", position: 2 },
  { query: "no-code app builder review", platform: "ChatGPT", position: 3 },
  // ... etc based on queries count
];
```

**D. CITATION CONTEXT (#14)**
2-3 example snippets showing how AI engines reference this URL. Each: platform favicon + platform name + the AI response text with highlighted portion where your URL is cited. Highlighted: `background: rgba(108, 184, 210, 0.15)`.

```typescript
const CITATION_EXAMPLES = [
  {
    platform: "ChatGPT",
    text: "For a comprehensive comparison of AI app builders, **Lovable's comparison guide** covers the key differences between Bolt.new, Cursor, and Replit across pricing, features, and deployment capabilities.",
  },
  {
    platform: "Perplexity",
    text: "According to **Lovable's analysis**, the main differentiators between AI app builders are: deployment flexibility, database integration, and code export options. [Source: lovable.dev]",
  },
];
```

**E. COMPETING URLS**
Other URLs (competitor and your own) cited for the same queries. Shows overlap and potential cannibalization.

```typescript
const COMPETING_URLS = [
  { url: "bolt.new/blog/ai-app-security", domain: "bolt.new", sharedQueries: 3, citations: 81 },
  { url: "lovable.dev/blog/lovable-vs-cursor", domain: "lovable.dev", sharedQueries: 4, citations: 38, isOwn: true },
  { url: "cursor.com/docs/enterprise-features", domain: "cursor.com", sharedQueries: 2, citations: 74 },
];
```

Your own URLs: highlighted with `[YOUR PAGE]` badge. Competitor URLs: real favicon + domain.

---

### Section 5: Revenue Proxy Indicators (#187-192) — full width

Full-width card. Title: "AI Referral Potential". Subtitle: "Leading indicators — actual attribution requires CRM integration".

Three metric cards in a row (grid-cols-3):

```typescript
const REVENUE_PROXY = [
  { label: "Est. AI Referrals", value: "~3,200/mo", sub: "based on citation volume × industry benchmarks", trend: "+12% vs last month" },
  { label: "Citation-to-Visit Rate", value: "8.4%", sub: "estimated CTR from AI citations", trend: "industry avg: 6.2%" },
  { label: "High-Intent Queries", value: "14 of 47", sub: "queries with buying intent signals", trend: "you're cited in 9 of 14" },
];
```

Each card: `1px solid var(--border)`, 12px padding. Value: 20px JetBrains Mono. Label: 11px uppercase. Sub: 11px var(--text-secondary). Trend: 11px, colored.

**Below cards:** Note card with subtle background (`var(--surface)`), `1px solid var(--border)`, 12px text:
"These are estimates based on industry benchmarks. Connect Google Analytics or your CRM to see actual attribution data. [Set up attribution →]"

The link is a placeholder — shows toast "Attribution setup coming soon" on click.

---

## Metrics Coverage Checklist

### Citation Core (#1-16) — 16 metrics:

- [x] #1 Share of Voice → KPI strip "Share of Voice" (12.4%) + Leaderboard SOV column
- [x] #2 SOV per Platform → Platform Grid SOV per column
- [x] #3 Citation Presence Rate → KPI strip "Citation Presence" (67%) + Cited donut
- [x] #4 Avg Citation Position → KPI strip "Avg Citation Position" (2.3) + Platform Grid rank
- [x] #5 Total Tracked Queries → Visibility section (47 queries context)
- [x] #6 Citation Count per URL → Citation URL Table "Citations" column + KPI "Total Citations"
- [x] #7 Brand Mention Count → KPI strip "Brand Mentions" (1,203) + Mentioned donut
- [x] #8 Citation URL → Citation URL Table (10 rows with full URLs)
- [x] #9 Citation Momentum → Hero chart (daily stacked bars + SOV line)
- [x] #10 SPA Score → Hero chart composite (SOV trend as proxy)
- [x] #11 SOV Trend → Hero chart SOV line slope + KPI trend
- [x] #12 Mention vs Citation Gap → Cited vs Mentioned donuts (67% vs 89%, gap explained)
- [x] #13 Citation Sentiment → Sentiment bars (72% positive, 22% neutral, 6% negative)
- [x] #14 Citation Context Category → Context category cards (5 categories) + Drawer Section D
- [x] #15 Brand Search Lift → Sentiment section insight text
- [x] #16 New Citations Detected → Citation URL table "First Cited" column

### Citation Dynamics (#17-27) — 11 metrics:

- [x] #17 Citation Velocity → Citation URL table "Velocity" column
- [x] #18 SOV Change Rate → KPI strip trend (↑ from 8.1%) + Hero chart slope
- [x] #19 New Query Appearances → Citation URL table "First Cited" (recent dates = new appearances)
- [x] #20 Citation Depth → Side drawer "Queries Served" (how many queries each URL answers)
- [x] #21 Citation Breadth → Platform Grid "Coverage" % per platform
- [x] #22 Citation Consistency → Platform Grid (cross-platform presence comparison)
- [x] #23 Platform Agreement → Platform Grid (comparing rankings across platforms)
- [x] #24 Citation Freshness → Citation URL table "First Cited" dates
- [x] #25 Citation Growth Rate → Hero chart (visible upward trend in stacked bars)
- [x] #26 Seasonal Patterns → Hero chart (visible in daily data fluctuations)
- [x] #27 Day-over-Day Change → Hero chart tooltip (compare adjacent days)

### Platform Intelligence subset (#174, #177):

- [x] #174 Platform Preference → Platform Grid per-platform metrics
- [x] #177 Platform-Specific SOV → Platform Grid SOV per column

### Revenue Proxy (#187-192) — 6 metrics:

- [x] #187 Estimated AI Referral Volume → KPI strip "Est. AI Referrals" + Revenue section card 1
- [x] #188 Citation-to-Visit Rate → Revenue section card 2 (8.4%)
- [x] #189 High-Intent Query Share → Revenue section card 3 (14 of 47)
- [x] #190 Revenue-Adjacent Citations → Revenue section (high-intent queries you're cited in)
- [x] #191 AI Referral Growth → Revenue section card 1 trend (+12%)
- [x] #192 Attribution Gap Indicator → Revenue section CRM note ("Connect GA or CRM")

---

## Brand System Rules

- CSS variables for ALL UI colors — never hardcode hex
- Platform brand colors for chart segments are acceptable as constants
- 1px borders on every card — no borderless, no shadows, no gradients
- JetBrains Mono for ALL data values. Space Grotesk for ALL text.
- Real brand logos via Google Favicon API everywhere — never colored circles
- Do NOT set `crossOrigin="anonymous"` on favicon images
- Light + dark mode via CSS variables

---

## Verification

```bash
npm run dev      # page loads at /analytics
npx tsc --noEmit # 0 type errors
```

1. Page padding tight — 24px max, 16px between sections
2. Filter bar full-width toolbar — no rounded corners, border-bottom, 44px
3. KPI strip: 6 cards, 28px JetBrains Mono values, colored trends
4. Hero chart: 300px, stacked platform bars + SOV line, 28 days, inline legend with favicons
5. Left column: Cited donut (67%) + Mentioned donut (89%) with gap explanation
6. Left column: Sentiment bars + context category cards
7. Right column: 6-brand SOV leaderboard, your row highlighted with [YOU] badge
8. Right column: mini competitive trend chart below leaderboard
9. Platform Grid: 5 columns, real favicons, sparklines, per-platform metrics
10. Highest-SOV platform column has accent top border
11. Citation URL table: 10 rows, all 8 columns, sortable
12. Platform dots in table: real 12px favicons filled/empty
13. Side drawer opens on URL click — 5 sections populated
14. Drawer: citation timeline, platform breakdown, queries served, citation context examples, competing URLs
15. Revenue proxy: 3 cards + CRM attribution note
16. All 40 metrics from checklist verified present
17. All favicons loading — Network tab 0 404s
18. Works in both light and dark mode
19. `npm run build` succeeds

---

## Completion Criteria

- [ ] Page loads at `/analytics` — old page fully replaced, no console errors
- [ ] Filter bar: full-width toolbar with date + platform + cluster
- [ ] KPI strip: 6 cards with correct values and trends
- [ ] Citation Momentum: ComposedChart, 300px, stacked bars + SOV line, 28 days
- [ ] Cited/Mentioned donuts: 67% and 89% with center text and gap explanation
- [ ] Sentiment bars: 3 bars (positive/neutral/negative) with correct percentages
- [ ] Context categories: 5 cards with percentages
- [ ] Competitor leaderboard: 6 brands, real favicons, your row highlighted
- [ ] Mini competitive trend chart below leaderboard
- [ ] Platform Grid: 5 columns with favicon, 5 metrics each, sparklines
- [ ] Citation URL table: 10 rows, 8 columns, sortable, row click opens drawer
- [ ] Side drawer: 5 sections (timeline, platforms, queries, context, competing)
- [ ] Revenue proxy: 3 cards with values + CRM attribution note
- [ ] All 40 metrics verified present per checklist
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts, real logos
- [ ] Density: no gap > 16px, no padding > 16px, no page margin > 24px
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds