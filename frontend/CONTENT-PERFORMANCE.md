# Agent — Content Performance Page (v3 — Production)

> **Read CLAUDE.md and brand-system.md first, then this file.** This builds/rebuilds the `/content-performance` page.

---

## Mission

Build the Content Performance page — the page that answers **"Which of my content is earning citations, and which isn't?"** Per-content-piece analysis with structural signal intelligence. Absorbs 38 metrics: Content Performance (#99-116, 18 metrics) + Structural Signals (#79-98, 20 metrics).

---

## Files You Own

```
src/app/(dashboard)/content-performance/page.tsx
src/app/(dashboard)/content-performance/_components/
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
Section headers: 15px, font-weight 600
Section subtitles: 12px, var(--text-secondary)
Table headers: 11px, uppercase, letter-spacing 0.05em, var(--text-secondary)
Table body: 13px
Table data values: 13px, JetBrains Mono
Chart axis labels: 11px
Correlation coefficient (r value): 12px, JetBrains Mono, var(--text-secondary)
Impact badges: 10px, uppercase, font-weight 600
Drawer section headers: 14px, uppercase, font-weight 600
```

### Global Filter Bar

```tsx
<div className="flex items-center gap-3 px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <DateRangePicker /> {/* Feb 28, 2026 – Mar 27, 2026 */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <ClusterFilter /> {/* All ▾ */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <LifecycleStageFilter /> {/* All ▾ */}
  <button className="ml-auto text-xs" style={{ color: 'var(--text-secondary)' }}>× Clear</button>
</div>
```

Full-width toolbar. No rounded corners. Height 44px. 0 gap below page title.

---

## Page Structure

### KPI Strip (6 cards, single row)

| KPI | Value | Trend | Sub | Metric # |
|-----|-------|-------|-----|----------|
| Published | 7 | +3 this week | pieces total | — |
| Total Citations | 225 | +38 this period | across all content | #99 |
| Avg CPS | 0.574 | ↑ from 0.48 | citation prediction score | #101 |
| Utilization | 71% | ↑ from 62% | 5/7 pieces cited | #104 |
| Stale Alerts | 2 | — | velocity below threshold | #115 |
| AI Referral Est. | ~2,400/mo | — | estimated from citations | #114 |

Cards: `1px solid var(--border)`, 12px padding, no shadow. JetBrains Mono 28px values.

---

### Section 1: Two-column charts (55% left / 45% right)

**Left: Citation Velocity by Content (#100, #108, #115)**

Recharts `BarChart`. Height: **280px**. One bar per content piece (7 bars).

Bar color by lifecycle stage:
- Growing: `var(--accent)` / `#6CB8D2`
- Peaking: `#F5A623` (amber)
- Stable: `var(--text-secondary)` at 40% opacity (gray)
- Declining: `#E87C3F` (orange)
- Stale: `#E5484D` (red)

**X-axis:** Rotate labels 45° → `<XAxis angle={-45} textAnchor="end" tick={{ fontSize: 11 }} />`. Truncate titles to 18 chars + "…". Add `marginBottom: 60` to chart container.

Horizontal `ReferenceLine` at y=1.0: dashed red (`stroke="#E5484D" strokeDasharray="4 4"`). Label at right end: "Stale threshold" (10px, red).

**Tooltip on hover:** full content title, citations/week value, lifecycle stage, cluster name.

```typescript
const VELOCITY_DATA = [
  { title: "AI App Builder Comparison Guide", velocity: 4.8, lifecycle: "peaking", cluster: "Branded Evaluation" },
  { title: "Lovable vs Cursor: Honest Review", velocity: 3.9, lifecycle: "growing", cluster: "Branded Evaluation" },
  { title: "Vibe Coding for Enterprise Teams", velocity: 3.2, lifecycle: "growing", cluster: "Category Comparison" },
  { title: "Non-Technical Founder's Guide", velocity: 2.9, lifecycle: "growing", cluster: "Problem/Awareness" },
  { title: "Security in AI-Generated Apps", velocity: 2.1, lifecycle: "stable", cluster: "Boundary" },
  { title: "Bolt.new Alternatives in 2026", velocity: 1.4, lifecycle: "declining", cluster: "Branded Evaluation" },
  { title: "RBAC in AI-Generated Applications", velocity: 0.8, lifecycle: "stale", cluster: "Boundary" },
];
```

**Right: CPS Predicted vs Actual (#101, #102, #103, #105, #106)**

Recharts `ScatterChart`. Height: **280px**.

Diagonal reference line (y=x): `stroke="var(--text-secondary)" strokeOpacity={0.3} strokeDasharray="4 4"`. Label "Perfect prediction" at top-right end (10px, italic, var(--text-secondary)).

Dot size: 8px min → 20px max, scaled by citation count. Color: `#34B27B` (green) above diagonal (overperformer), `#E5484D` (red) below (underperformer).

**Tooltip on hover:** content title, predicted CPS, actual CPS, citation count.

**Top 3-4 most deviant dots:** 10px label with first 15 chars of title, offset with thin leader line (1px `var(--text-secondary)` at 30%).

Annotations: "Overperformer" (10px, var(--text-secondary)) in top-left area. "Underperformer" in bottom-right.

```typescript
const CPS_SCATTER = [
  { title: "AI App Builder Comparison Guide", predicted: 0.68, actual: 0.85, citations: 63 },
  { title: "Lovable vs Cursor: Honest Review", predicted: 0.62, actual: 0.75, citations: 38 },
  { title: "Vibe Coding for Enterprise Teams", predicted: 0.55, actual: 0.65, citations: 24 },
  { title: "Security in AI-Generated Apps", predicted: 0.60, actual: 0.45, citations: 31 },
  { title: "Non-Technical Founder's Guide", predicted: 0.48, actual: 0.55, citations: 22 },
  { title: "Bolt.new Alternatives in 2026", predicted: 0.58, actual: 0.42, citations: 29 },
  { title: "RBAC in AI-Generated Applications", predicted: 0.52, actual: 0.35, citations: 18 },
];
```

---

### Section 2: Structural Alignment — Diverging Bar Chart (#79-98)

**Full-width card.** Title: "What Structure Gets Cited? Your Content vs What AI Engines Prefer". Subtitle: "Structural signals sorted by Pearson correlation coefficient with citation likelihood".

**Layout: Horizontal diverging bar chart.** For each signal, ONE bar centered on zero:
- Left side (negative gap): how far below cited average you are → red/amber fill
- Right side (positive gap): how far above → green fill
- Zero line in center = matches cited average exactly

```
Signal                   r       ←— Your Gap vs Cited Avg —→                   Impact
FAQ Section            0.82   ████████████████████████|                          CRITICAL
                                        -58%
Comparison Table       0.79   ███████████████████████ |                          CRITICAL
                                        -55%
Word Count 2000+       0.74   ███████████████████████ |                          HIGH
                                    -47%
Headers per 500w ≥ 3   0.71   ██████████████████████  |                          HIGH
                                    -36%
Ordered Lists          0.68   █████████████████████   |                          HIGH
                                   -37%
Schema (FAQ/HowTo)     0.65   ████████████████████████|                          HIGH
                                       -53%
External Citations     0.62   ██████████████████████  |                          MEDIUM
                                   -46%
Key Takeaways          0.58   ████████████████        |                          MEDIUM
                                  -33%
Reading Grade 8-12     0.54               |██                                    LOW
                                     -6%
Stats/Data Points      0.51   ██████████████████      |                          MEDIUM
                                   -36%
Definition Opening     0.47   ████████                |                          LOW
                                -12%
Code Blocks            0.42                     |████████                        LOW
                                           +17%
```

**Toggle button:** "Show top 12" (default) / "Show all 20 signals" — expands to include remaining 8 lower-correlation signals.

Signal name: 13px font-weight 500. `r = 0.82`: 12px JetBrains Mono, var(--text-secondary).

Impact badges as pills: CRITICAL = `background: #E5484D`, white text. HIGH = `background: #F5A623`, dark text. MEDIUM = `background: var(--accent)`, white text. LOW = `background: var(--text-secondary)` at 20%, dark text. 10px uppercase.

**Hover tooltip:** "FAQ Section — Cited avg: 78% | Yours: 20% | Gap: -58%"

```typescript
const STRUCTURAL_SIGNALS = [
  { signal: "FAQ Section", r: 0.82, citedAvg: 78, yours: 20, impact: "critical" },
  { signal: "Comparison Table", r: 0.79, citedAvg: 85, yours: 30, impact: "critical" },
  { signal: "Word Count 2000+", r: 0.74, citedAvg: 92, yours: 45, impact: "high" },
  { signal: "Headers per 500w ≥ 3", r: 0.71, citedAvg: 80, yours: 44, impact: "high" },
  { signal: "Ordered Lists", r: 0.68, citedAvg: 72, yours: 35, impact: "high" },
  { signal: "Schema (FAQ/HowTo)", r: 0.65, citedAvg: 68, yours: 15, impact: "high" },
  { signal: "External Citations", r: 0.62, citedAvg: 84, yours: 38, impact: "medium" },
  { signal: "Key Takeaways", r: 0.58, citedAvg: 55, yours: 22, impact: "medium" },
  { signal: "Reading Grade 8-12", r: 0.54, citedAvg: 88, yours: 82, impact: "low" },
  { signal: "Stats/Data Points", r: 0.51, citedAvg: 64, yours: 28, impact: "medium" },
  { signal: "Definition Opening", r: 0.47, citedAvg: 52, yours: 40, impact: "low" },
  { signal: "Code Blocks", r: 0.42, citedAvg: 38, yours: 55, impact: "low" },
  // Additional 8 signals for "Show all 20":
  { signal: "Step-by-Step Guide", r: 0.39, citedAvg: 45, yours: 30, impact: "low" },
  { signal: "Expert Quotes", r: 0.36, citedAvg: 32, yours: 10, impact: "low" },
  { signal: "Research References", r: 0.34, citedAvg: 48, yours: 25, impact: "low" },
  { signal: "Infographics/Images", r: 0.31, citedAvg: 55, yours: 40, impact: "low" },
  { signal: "Table of Contents", r: 0.28, citedAvg: 62, yours: 50, impact: "low" },
  { signal: "Meta Description", r: 0.25, citedAvg: 95, yours: 90, impact: "low" },
  { signal: "Canonical URL", r: 0.22, citedAvg: 98, yours: 100, impact: "low" },
  { signal: "Mobile Responsive", r: 0.18, citedAvg: 99, yours: 100, impact: "low" },
];
```

---

### Section 3: Content Performance Table (full width) — CRITICAL

**Do NOT skip this section.** This is the core of the page.

| Column | Width | Content |
|--------|-------|---------|
| Title | 20% | Content title, single line ellipsis, 13px font-weight 500, clickable |
| Cluster | 10% | Colored badge pill (11px) |
| Citations | 7% | Total count, 13px JetBrains Mono |
| CPS | 7% | 3-decimal, colored: green ≥0.6, amber 0.45-0.59, red <0.45, 13px JetBrains Mono |
| Velocity | 8% | Citations/week + arrow (↑ up, ↓ down, — flat), 13px JetBrains Mono |
| Structural | 7% | 0-100 score + mini inline bar (40px wide, colored fill proportional to score) |
| Freshness | 8% | Badge: "Fresh" (green pill, ≤30d), "Aging" (amber pill, 31-60d), "Stale" (red pill, >60d) |
| Lifecycle | 8% | Badge: Growing ↑ (teal), Peaking ◆ (amber), Stable — (gray), Declining ↓ (orange), Stale ⚠ (red) |
| Platforms | 12% | 5 dots for ChatGPT/Claude/Perplexity/Google/Gemini — filled real favicon (12px) if cited, empty circle (12px, var(--border)) if not |
| Cannibal. | 6% | Count in JetBrains Mono or "—" if 0 |
| | 4% | → chevron (var(--text-secondary)) |

Row height: 40px. Row styling:
- Stale lifecycle: `background: rgba(229, 72, 77, 0.04)`
- Declining lifecycle: `background: rgba(245, 166, 35, 0.04)`
- Hover: `background: var(--accent-subtle)`
- Cursor: pointer (every row opens drawer)

Sortable column headers. Default: Citations descending.

```typescript
const CONTENT_PIECES = [
  {
    id: "c1", title: "AI App Builder Comparison Guide", cluster: "Branded Evaluation", clusterColor: "#5BA4C4",
    citations: 63, cps: 0.713, velocity: 4.8, velocityTrend: "up", structuralScore: 72,
    freshnessDays: 80, lifecycle: "peaking",
    platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 1, publishedAt: "2026-01-08", url: "lovable.dev/blog/ai-app-builder-comparison",
    queriesCovered: 12, exemplarSimilarity: 0.72, briefCompliance: 88,
  },
  {
    id: "c2", title: "Lovable vs Cursor: Honest Review", cluster: "Branded Evaluation", clusterColor: "#5BA4C4",
    citations: 38, cps: 0.654, velocity: 3.9, velocityTrend: "up", structuralScore: 65,
    freshnessDays: 77, lifecycle: "growing",
    platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 1, publishedAt: "2026-01-11", url: "lovable.dev/blog/lovable-vs-cursor",
    queriesCovered: 8, exemplarSimilarity: 0.68, briefCompliance: 82,
  },
  {
    id: "c3", title: "Security in AI-Generated Applications", cluster: "Boundary", clusterColor: "#DC7B18",
    citations: 31, cps: 0.482, velocity: 2.1, velocityTrend: "flat", structuralScore: 48,
    freshnessDays: 73, lifecycle: "stable",
    platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: false },
    cannibalization: 0, publishedAt: "2026-01-14", url: "lovable.dev/blog/security-ai-apps",
    queriesCovered: 5, exemplarSimilarity: 0.55, briefCompliance: 64,
  },
  {
    id: "c4", title: "Vibe Coding for Enterprise Teams", cluster: "Category Comparison", clusterColor: "#34B27B",
    citations: 24, cps: 0.649, velocity: 3.2, velocityTrend: "up", structuralScore: 68,
    freshnessDays: 70, lifecycle: "growing",
    platforms: { chatgpt: false, claude: true, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 0, publishedAt: "2026-01-17", url: "lovable.dev/blog/vibe-coding-enterprise",
    queriesCovered: 6, exemplarSimilarity: 0.65, briefCompliance: 78,
  },
  {
    id: "c5", title: "Bolt.new Alternatives in 2026", cluster: "Branded Evaluation", clusterColor: "#5BA4C4",
    citations: 29, cps: 0.521, velocity: 1.4, velocityTrend: "down", structuralScore: 55,
    freshnessDays: 67, lifecycle: "declining",
    platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: false, gemini: false },
    cannibalization: 2, publishedAt: "2026-01-20", url: "lovable.dev/blog/bolt-new-alternatives",
    queriesCovered: 9, exemplarSimilarity: 0.58, briefCompliance: 71,
  },
  {
    id: "c6", title: "RBAC in AI-Generated Applications", cluster: "Boundary", clusterColor: "#DC7B18",
    citations: 18, cps: 0.459, velocity: 0.8, velocityTrend: "down", structuralScore: 35,
    freshnessDays: 64, lifecycle: "stale",
    platforms: { chatgpt: false, claude: false, perplexity: true, google_ai: false, gemini: false },
    cannibalization: 0, publishedAt: "2026-01-23", url: "lovable.dev/blog/rbac-ai-apps",
    queriesCovered: 3, exemplarSimilarity: 0.48, briefCompliance: 55,
  },
  {
    id: "c7", title: "Non-Technical Founder's Guide to AI App Builders", cluster: "Problem/Awareness", clusterColor: "#8B7EC8",
    citations: 22, cps: 0.538, velocity: 2.9, velocityTrend: "up", structuralScore: 60,
    freshnessDays: 61, lifecycle: "growing",
    platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: true },
    cannibalization: 0, publishedAt: "2026-01-26", url: "lovable.dev/blog/non-tech-founder-guide",
    queriesCovered: 7, exemplarSimilarity: 0.62, briefCompliance: 84,
  },
];
```

---

### Side Drawer — Content Deep Dive (50% viewport width) — CRITICAL

**Do NOT skip this section.** Opens on table row click. Backdrop: `rgba(0,0,0,0.15)`. Close button: top-right, 32px hit target.

**Drawer header:**
```
"AI App Builder Comparison Guide"
lovable.dev/blog/ai-app-builder-comparison ↗     Published: Jan 8, 2026
```
Title: 16px font-weight 600. URL: 12px var(--text-secondary), external link icon. Published date: 12px var(--text-secondary).

Each drawer section separated by `border-top: 1px solid var(--border)`, with 14px uppercase section header and 12px top padding.

#### Section A: CITATION TIMELINE (#100)

Mini Recharts `AreaChart`. Full drawer width. Height: 120px. Daily citations over the date range.

Fill: `var(--accent)` at 10% opacity. Stroke: `var(--accent)` 2px. No grid lines. X-axis: dates (11px). Y-axis: citation count (11px JetBrains Mono). Tooltip on hover: date + citation count.

```typescript
// Generate 28 days of citation data for this piece
const generateCitationTimeline = (totalCitations: number) => {
  return Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    citations: Math.max(0, Math.floor(totalCitations / 28 * (0.5 + Math.random()))),
  }));
};
```

#### Section B: PLATFORM DISTRIBUTION (#109)

5 small cards in a row (grid-cols-5). Each card: `1px solid var(--border)`, 12px padding.

Content per card:
- Platform favicon (16px) from real domain
- Platform name (11px)
- Citation count on this platform (16px JetBrains Mono, font-weight 600)
- "Cited ✓" (green, 10px) or "Not cited ✗" (gray, 10px)

```typescript
const PLATFORM_DOMAINS = {
  chatgpt: "openai.com",
  claude: "anthropic.com",
  perplexity: "perplexity.ai",
  google_ai: "google.com",
  gemini: "gemini.google.com",
};

// Example for c1 (AI App Builder Comparison Guide):
const PLATFORM_DIST = [
  { platform: "ChatGPT", domain: "openai.com", citations: 22, cited: true },
  { platform: "Claude", domain: "anthropic.com", citations: 15, cited: true },
  { platform: "Perplexity", domain: "perplexity.ai", citations: 14, cited: true },
  { platform: "Google AI", domain: "google.com", citations: 12, cited: true },
  { platform: "Gemini", domain: "gemini.google.com", citations: 0, cited: false },
];
```

#### Section C: STRUCTURAL COMPLIANCE (#112, #91, #92, #116)

Table comparing your content's structure against cited averages for the same queries:

| Signal | Cited Avg | Yours | Gap | Status |
|--------|-----------|-------|-----|--------|
| Word Count | 2,017 | 1,450 | -567 | ⚠ Below |
| Headers | 14 | 8 | -6 | ⚠ Below |
| FAQ Sections | 42% | 0% | -42% | ❌ Missing |
| Comparison Tables | 41% | 100% | +59% | ✅ Above |
| External Citations | 94% | 80% | -14% | ⚠ Below |
| Reading Level | 10.2 | 11.5 | +1.3 | ✅ Match |
| Key Takeaways | 38% | 0% | -38% | ❌ Missing |
| Lists (ordered) | 65% | 40% | -25% | ⚠ Below |

Status icons: ✅ (yours ≥ cited avg) green, ⚠ (within 30%) amber, ❌ (>30% below) red. Gap values: red if negative and large, green if positive.

#### Section D: QUERY COVERAGE (#110)

List of queries this content piece serves. Each row:
- Query text (12px)
- Gap score badge (JetBrains Mono, colored: green ≤0.2, amber 0.2-0.5, red >0.5)
- Classification badge (pill): "significant_gap" (red), "moderate_gap" (amber), "aligned" (green), "company_leads" (teal)

```typescript
const QUERIES_COVERED = [
  { query: "best AI app builder comparison", gapScore: 0.15, classification: "aligned" },
  { query: "lovable vs bolt.new vs cursor", gapScore: 0.08, classification: "company_leads" },
  { query: "AI app builder features comparison", gapScore: 0.32, classification: "moderate_gap" },
  { query: "no-code app builder review 2026", gapScore: 0.28, classification: "moderate_gap" },
  // ... more queries based on queriesCovered count
];
```

#### Section E: CANNIBALIZATION RISK (#113)

If `cannibalization > 0`:
```
⚠ This page competes with 1 other page for the same citations:

"Lovable vs Cursor: Honest Review" — similarity: 0.87
Recommendation: Differentiate by focusing on different comparison angles.
The overlap is primarily in the "AI App Builder Evaluation" cluster.
```

If `cannibalization === 0`:
```
✅ No cannibalization detected — this content has unique query coverage.
```

Show competing page URL (12px, clickable), similarity score (JetBrains Mono), recommendation text (12px var(--text-secondary)).

#### Section F: BRIEF COMPLIANCE (#116)

If a content brief exists for this piece:

```
Word Count:  Target 2,000  |  Actual 1,450  |  ⚠ 72% of target
             [███████████████░░░░░]

Required Elements:
  ✅ Comparison table present
  ✅ External citations (8 sources)
  ❌ FAQ section missing
  ❌ Key takeaways missing
  ✅ Headers per 500w ≥ 3
  ⚠  Reading level 11.5 (target: 8-10)

Brief Compliance Score: 88%
```

Mini progress bar for word count (40px height, full drawer width). Checklist with ✅/❌/⚠ for each required element.

#### Section G: FRESHNESS (#107)

```
Content Age: 80 days (published Jan 8, 2026)
Cited Exemplar Avg Age: 45 days

⚠ Your content is 35 days older than the average cited piece
   for these queries. Consider refreshing with updated data
   and recent developments.

Freshness Score: 62/100
```

Show content age vs exemplar avg as two bars side by side. Color: green if younger than exemplars, amber if within 30 days, red if >30 days older.

---

## Metrics Coverage Checklist

### Content Performance (#99-116) — 18 metrics:

- [x] #99 Citation Count per Content Piece → Table "Citations" column + KPI strip "Total Citations"
- [x] #100 Citation Velocity per Piece → Velocity bar chart + Table "Velocity" column + Drawer Section A timeline
- [x] #101 CPS (Citation Prediction Score) → CPS scatter chart + Table "CPS" column + KPI strip "Avg CPS"
- [x] #102 CPS Accuracy → CPS scatter (distance from diagonal = accuracy)
- [x] #103 CPS Predicted vs Actual → CPS scatter chart (x=predicted, y=actual)
- [x] #104 Content Utilization Rate → KPI strip "Utilization" (71%, 5/7 pieces cited)
- [x] #105 Underperformers → CPS scatter (red dots below diagonal)
- [x] #106 Overperformers → CPS scatter (green dots above diagonal)
- [x] #107 Content Freshness Score → Table "Freshness" column + Drawer Section G
- [x] #108 Content Lifecycle Stage → Table "Lifecycle" column + Velocity chart bar colors
- [x] #109 Platform Citation Distribution → Table "Platforms" column (5 favicon dots) + Drawer Section B
- [x] #110 Query Coverage per Piece → Drawer Section D (query list with gap scores)
- [x] #111 Content-to-Exemplar Similarity → Drawer Section C (structural comparison against cited content)
- [x] #112 Content Structural Score → Table "Structural" column + Drawer Section C
- [x] #113 Content Cannibalization Risk → Table "Cannibal." column + Drawer Section E
- [x] #114 Content ROI Proxy → KPI strip "AI Referral Est." (~2,400/mo)
- [x] #115 Stale Content Alert → KPI strip "Stale Alerts" + Velocity chart stale threshold + Table row styling
- [x] #116 Content Brief Compliance → Drawer Section F (compliance score + checklist)

### Structural Signals (#79-98) — 20 metrics:

- [x] #79 FAQ Presence Rate → Structural Alignment diverging bar (r=0.82, gap=-58%)
- [x] #80 Comparison Table Rate → Structural Alignment (r=0.79, gap=-55%)
- [x] #81 Key Takeaways Rate → Structural Alignment (r=0.58, gap=-33%)
- [x] #82 Header Density → Structural Alignment (r=0.71, gap=-36%)
- [x] #83 Ordered List Usage → Structural Alignment (r=0.68, gap=-37%)
- [x] #84 Stats/Data Points Rate → Structural Alignment (r=0.51, gap=-36%)
- [x] #85 Citation/Reference Rate → Structural Alignment (r=0.62, gap=-46%)
- [x] #86 Word Count → Structural Alignment (r=0.74, gap=-47%)
- [x] #87 Paragraph Density → Structural Alignment (included in "Show all 20" toggle)
- [x] #88 Word Count Sweet Spot → Drawer Section C (word count comparison)
- [x] #89 Header Density Correlation → Structural Alignment (r coefficient displayed)
- [x] #90 Reading Level → Structural Alignment (r=0.54, gap=-6%) + Drawer Section C
- [x] #91 Structural Alignment Score → Table "Structural" column (0-100 score)
- [x] #92 Structural Gap per Signal → Structural Alignment gap values + Drawer Section C
- [x] #93 Required Elements per Cluster → Drawer Section F (required elements checklist)
- [x] #94 Dominant Content Type → Structural Alignment (implied in signal ordering)
- [x] #95 Dominant Authority Type → Structural Alignment (implied in citation patterns)
- [x] #96 Content Pattern Presence → Drawer Section C (pattern checklist)
- [x] #97 Header Hierarchy → Drawer Section C (headers count comparison)
- [x] #98 Schema Markup Impact → Structural Alignment (r=0.65, Schema FAQ/HowTo)

---

## Brand System Rules

- CSS variables for all colors — never hardcode hex for UI
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

1. Page padding tight — 24px max horizontal, 16px between sections
2. Filter bar full-width toolbar, no rounded corners, 44px height
3. KPI strip: 6 cards, 28px JetBrains Mono values, correct trends
4. Velocity chart: 280px height, 7 bars with lifecycle colors, rotated labels readable, stale threshold line labeled
5. CPS scatter: 280px, dots sized by citations, colored by over/under, top deviators labeled, diagonal annotated
6. Structural alignment: diverging bar format, 12 signals by default, toggle to 20, impact pills, hover tooltips
7. **Content table: 7 rows with ALL 11 columns** — verify each column renders correctly
8. **Side drawer: opens on any row click** — verify all 7 sections (A through G) populated with data
9. Platform dots in table: real 12px favicons for cited platforms, empty circles for not cited
10. Stale/declining rows have subtle background coloring
11. Sorting works on column header clicks
12. All font sizes match standardization table
13. All favicons loading (Network tab: 0 favicon 404s)
14. Works in both light and dark mode
15. `npm run build` — succeeds

---

## Completion Criteria

- [ ] Page loads at `/content-performance` with no console errors
- [ ] Filter bar: full-width toolbar with date + cluster + lifecycle filters
- [ ] KPI strip: 6 cards with correct values (Utilization = 71% not 100%)
- [ ] Velocity bar chart: 280px, 7 bars, lifecycle colors, rotated x-labels, stale threshold
- [ ] CPS scatter: 280px, sized dots, over/under coloring, diagonal line, labeled top deviators
- [ ] Structural Alignment: diverging bar chart with 12 signals, toggle to 20, r values, impact pills
- [ ] Content table: 7 rows, ALL 11 columns present and populated
- [ ] Table sorting works on all sortable columns
- [ ] Stale/declining rows have subtle background tinting
- [ ] Platform dots: real favicons for cited, empty circles for not cited
- [ ] Side drawer opens on row click — 50% viewport width
- [ ] Drawer Section A: citation timeline AreaChart (120px)
- [ ] Drawer Section B: 5 platform cards with favicon + count + cited status
- [ ] Drawer Section C: structural compliance table with 8 signals, status icons
- [ ] Drawer Section D: query coverage list with gap scores and classification badges
- [ ] Drawer Section E: cannibalization risk with competing pages or "none detected"
- [ ] Drawer Section F: brief compliance with word count bar + element checklist
- [ ] Drawer Section G: freshness assessment with age comparison
- [ ] All 38 metrics from checklist verified present
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts, real logos
- [ ] Density: no gap > 16px, no padding > 16px, no page margin > 24px
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds