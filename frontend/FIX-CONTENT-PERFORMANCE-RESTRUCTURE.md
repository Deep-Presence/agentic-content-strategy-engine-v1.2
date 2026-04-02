# Fix — Content Performance Page: Restructure to Table-First

> **Read CLAUDE.md and brand-system.md first.** This is a targeted restructure of the existing `/content-performance` page. The page currently buries the content table below two chart sections and a massive structural signals list. The table IS the page — everything else is secondary.

---

## THE PROBLEM

Look at how Prompt Tracking works: the table is the entire page. You see all 15 prompts immediately. Click a row → deep drawer. That's the pattern Content Performance needs to follow.

Right now Content Performance has:
1. KPI strip (good — keep)
2. Two charts taking up half the viewport (wrong — these should be in a tab)
3. A 12-row structural signals diverging bar list (wrong — this should be in a tab or the drawer)
4. The actual content table (buried at the bottom — this should be the FIRST thing after KPIs)

**The fix: Make the content table the primary view. Move charts and structural signals into a secondary tab.**

---

## NEW PAGE STRUCTURE

### Keep: Page title + subtitle + filter bar + KPI strip

These stay exactly as they are. No changes needed. The filter bar is already correct (full-width toolbar).

### Add: Tab bar below KPI strip

Two tabs, same pattern as Prompt Tracking's Prompt/Topic toggle:

```tsx
<div className="flex items-center px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <div className="flex gap-4">
    <button style={activeTab === 'pages' ? { borderBottom: '2px solid var(--accent)', fontWeight: 600, paddingBottom: '6px' } : { color: 'var(--text-secondary)' }}
            className="text-sm">
      Pages
    </button>
    <button style={activeTab === 'insights' ? { borderBottom: '2px solid var(--accent)', fontWeight: 600, paddingBottom: '6px' } : { color: 'var(--text-secondary)' }}
            className="text-sm">
      Insights
    </button>
  </div>
  <div className="ml-auto flex items-center gap-3">
    <input type="text" placeholder="Search content..." className="text-xs px-3 py-1.5 rounded"
           style={{ border: '1px solid var(--border)', background: 'transparent', width: '200px' }} />
  </div>
</div>
```

**"Pages" tab (default):** The content table — full width, immediately visible, the primary experience.

**"Insights" tab:** The charts (Citation Velocity, CPS Scatter) and the Structural Alignment diverging bars. This is secondary analysis the user navigates to intentionally.

---

## PAGES TAB — The Content Table (Restructured)

This table is now the star of the page. It needs to be richer than before — more columns, more data per row, more like the Prompt Tracking table in density and information.

### Table Columns

| Column | Width | Content |
|--------|-------|---------|
| Page | 22% | Content title (13px font-weight 500, single line ellipsis). Below title in 11px var(--text-secondary): truncated URL like `lovable.dev/blog/ai-app-bu...` |
| Cluster | 8% | Colored badge pill (11px) |
| Citations | 6% | Total count, JetBrains Mono. Color: green ≥40, amber 20-39, default <20 |
| CPS | 6% | 3-decimal score, JetBrains Mono. Color: green ≥0.6, amber 0.45-0.59, red <0.45 |
| Velocity | 6% | Citations/week + trend arrow (↑↓—), JetBrains Mono |
| Traffic | 7% | Monthly pageviews from GA, JetBrains Mono. Format: "2.4K" / "890" / "12.1K". Show "—" if no GA connected |
| Structural | 6% | Score 0-100 + mini inline bar (36px wide, colored: green ≥70, amber 40-69, red <40) |
| Freshness | 7% | Badge: "Fresh" (green, ≤30d), "Aging" (amber, 31-60d), "Stale" (red, >60d) |
| Lifecycle | 7% | Badge with icon: ↑ Growing (teal), ◆ Peaking (amber), — Stable (gray), ↓ Declining (orange), ⚠ Stale (red) |
| Platforms | 10% | 5 filled/empty dots — filled = real favicon (12px), empty = circle outline. For: ChatGPT, Claude, Perplexity, Google AI, Gemini |
| Cannibal. | 5% | Count or "—" |
| AI Referrals | 7% | Estimated monthly referrals from AI citations, JetBrains Mono. Format: "247" / "1.2K" |
| | 3% | → chevron |

### Row Styling

```
Row height: 44px (slightly taller than Prompt Tracking to accommodate URL subtitle)
Hover: var(--accent-subtle)
Cursor: pointer
Stale lifecycle rows: background: rgba(229, 72, 77, 0.04)
Declining lifecycle rows: background: rgba(245, 166, 35, 0.04)
```

### Sorting

All columns with ↕ icon are sortable. Default: Citations descending. Click column header to toggle asc/desc.

### Mock Data (7 content pieces — updated with traffic + referral data)

```typescript
const CONTENT_PIECES = [
  {
    id: "c1",
    title: "AI App Builder Comparison Guide",
    url: "lovable.dev/blog/ai-app-builder-comparison",
    cluster: "Branded Evaluation", clusterColor: "#5BA4C4",
    citations: 63, cps: 0.713, velocity: 4.8, velocityTrend: "up",
    traffic: 12100, // monthly pageviews
    structuralScore: 72,
    freshnessDays: 80, lifecycle: "peaking",
    platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 1,
    aiReferrals: 247, // estimated monthly from AI citations
    publishedAt: "2026-01-08",
    queriesCovered: 12, exemplarSimilarity: 0.72, briefCompliance: 88,
  },
  {
    id: "c2",
    title: "Lovable vs Cursor: Honest Review",
    url: "lovable.dev/blog/lovable-vs-cursor",
    cluster: "Branded Evaluation", clusterColor: "#5BA4C4",
    citations: 38, cps: 0.654, velocity: 3.9, velocityTrend: "up",
    traffic: 8400,
    structuralScore: 65,
    freshnessDays: 77, lifecycle: "growing",
    platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 1,
    aiReferrals: 124,
    publishedAt: "2026-01-11",
    queriesCovered: 8, exemplarSimilarity: 0.68, briefCompliance: 82,
  },
  {
    id: "c3",
    title: "Security in AI-Generated Applications",
    url: "lovable.dev/blog/security-ai-apps",
    cluster: "Boundary", clusterColor: "#DC7B18",
    citations: 31, cps: 0.482, velocity: 2.1, velocityTrend: "flat",
    traffic: 3200,
    structuralScore: 48,
    freshnessDays: 73, lifecycle: "stable",
    platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: false },
    cannibalization: 0,
    aiReferrals: 56,
    publishedAt: "2026-01-14",
    queriesCovered: 5, exemplarSimilarity: 0.55, briefCompliance: 64,
  },
  {
    id: "c4",
    title: "Vibe Coding for Enterprise Teams",
    url: "lovable.dev/blog/vibe-coding-enterprise",
    cluster: "Category Comparison", clusterColor: "#34B27B",
    citations: 24, cps: 0.649, velocity: 3.2, velocityTrend: "up",
    traffic: 5600,
    structuralScore: 68,
    freshnessDays: 70, lifecycle: "growing",
    platforms: { chatgpt: false, claude: true, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 0,
    aiReferrals: 123,
    publishedAt: "2026-01-17",
    queriesCovered: 6, exemplarSimilarity: 0.65, briefCompliance: 78,
  },
  {
    id: "c5",
    title: "Bolt.new Alternatives in 2026",
    url: "lovable.dev/blog/bolt-new-alternatives",
    cluster: "Branded Evaluation", clusterColor: "#5BA4C4",
    citations: 29, cps: 0.521, velocity: 1.4, velocityTrend: "down",
    traffic: 4100,
    structuralScore: 55,
    freshnessDays: 67, lifecycle: "declining",
    platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: false, gemini: false },
    cannibalization: 2,
    aiReferrals: 89,
    publishedAt: "2026-01-20",
    queriesCovered: 9, exemplarSimilarity: 0.58, briefCompliance: 71,
  },
  {
    id: "c6",
    title: "RBAC in AI-Generated Applications",
    url: "lovable.dev/blog/rbac-ai-apps",
    cluster: "Boundary", clusterColor: "#DC7B18",
    citations: 18, cps: 0.459, velocity: 0.8, velocityTrend: "down",
    traffic: 1900,
    structuralScore: 35,
    freshnessDays: 64, lifecycle: "stale",
    platforms: { chatgpt: false, claude: false, perplexity: true, google_ai: false, gemini: false },
    cannibalization: 0,
    aiReferrals: 183,
    publishedAt: "2026-01-23",
    queriesCovered: 3, exemplarSimilarity: 0.48, briefCompliance: 55,
  },
  {
    id: "c7",
    title: "Non-Technical Founder's Guide to AI App Builders",
    url: "lovable.dev/blog/non-tech-founder-guide",
    cluster: "Problem/Awareness", clusterColor: "#8B7EC8",
    citations: 22, cps: 0.538, velocity: 2.9, velocityTrend: "up",
    traffic: 6800,
    structuralScore: 60,
    freshnessDays: 61, lifecycle: "growing",
    platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: true },
    cannibalization: 0,
    aiReferrals: 177,
    publishedAt: "2026-01-26",
    queriesCovered: 7, exemplarSimilarity: 0.62, briefCompliance: 84,
  },
];
```

### Footer

"7 published pieces" — 11px, var(--text-secondary), left-aligned below table. Same pattern as Prompt Tracking's "15 of 15 prompts".

---

## SIDE DRAWER — Content Deep Dive (50% viewport width)

Opens on any table row click. This is the deep dive — like Prompt Tracking's drawer but for content analysis.

**Drawer header:**
```
AI App Builder Comparison Guide
lovable.dev/blog/ai-app-builder-comparison ↗     Published: Jan 8, 2026
```
Title: 16px font-weight 600. URL: 12px var(--text-secondary) + ↗ external link icon.

**Drawer sections (each with 14px uppercase header, border-top separator):**

### A. CITATION TIMELINE
Mini Recharts AreaChart. Full drawer width. 120px height. Daily citations over the selected date range. Fill: var(--accent) at 10%. Stroke: var(--accent) 2px.

### B. TRAFFIC vs CITATIONS
Two-line overlay chart (140px height). Left y-axis: pageviews (gray area fill). Right y-axis: citations (accent line). Shows correlation between traffic and citations. If traffic data unavailable, show a muted card: "Connect Google Analytics to see traffic data alongside citations. [Connect GA →]"

### C. PLATFORM DISTRIBUTION
5 small cards in a row. Each: platform favicon (16px) + name (11px) + citation count (16px JetBrains Mono) + "Cited ✓" (green 10px) or "Not cited ✗" (gray 10px). Card: 1px border, 12px padding.

### D. STRUCTURAL COMPLIANCE
Table comparing your content's structure vs what gets cited for the same queries:

| Signal | Cited Avg | Yours | Gap | Status |
|--------|-----------|-------|-----|--------|
| Word Count | 2,017 | 2,450 | +433 | ✅ Above |
| Headers | 14 | 16 | +2 | ✅ Above |
| FAQ Sections | 42% | 100% | +58% | ✅ Above |
| Comparison Tables | 41% | 100% | +59% | ✅ Above |
| External Citations | 94% | 80% | -14% | ⚠ Below |
| Reading Level | 10.2 | 11.5 | +1.3 | ✅ Above |
| Key Takeaways | 38% | 100% | +62% | ✅ Above |
| Lists (ordered) | 65% | 80% | +15% | ✅ Above |

Status: ✅ = yours ≥ cited avg (green). ⚠ = within 30% (amber). ❌ = >30% below (red).

### E. QUERY COVERAGE
List of queries this content serves. Each row: query text (12px) + gap score (JetBrains Mono, colored) + classification badge (pill: ALIGNED green, COMPANY LEADS teal, MODERATE GAP amber, SIGNIFICANT GAP red).

### F. CANNIBALIZATION RISK
If cannibalization > 0: show competing page(s) with cosine similarity + recommendation.
If 0: "✅ No cannibalization detected"

### G. BRIEF COMPLIANCE
Word count target vs actual (mini bar), required elements checklist (✅/❌ for each), reading level match, overall compliance score.

### H. FRESHNESS ASSESSMENT
Content age vs average age of cited exemplars. Shows whether content needs refresh.

### I. TRAFFIC SOURCES (Google Analytics)
If GA connected: breakdown of traffic sources for this page — Organic Search, Direct, AI Referral (estimated), Social, Referral. As horizontal bars or a simple table.
If not connected: "Connect Google Analytics for traffic source breakdown. [Connect GA →]"

---

## INSIGHTS TAB — Charts & Analysis

When the user clicks the "Insights" tab, show the charts that are currently taking up the main view:

### Citation Velocity by Content
The existing bar chart (keep as-is from current implementation — it's fine). Height: 280px. Lifecycle-colored bars with stale threshold line.

### CPS: Predicted vs Actual
The existing scatter chart (keep as-is). Height: 280px. Green overperformers, red underperformers.

### Structural Alignment Overview
The existing diverging bar chart (keep as-is). 12 signals by default, toggle to 20. This is good — it just doesn't belong as the primary view.

### Content Lifecycle Distribution
NEW — Add a simple visualization showing how many pieces are in each lifecycle stage:
```
Growing: 3 pieces  ████████████████████
Peaking: 1 piece   ██████
Stable:  1 piece   ██████
Declining: 1 piece ██████
Stale:   1 piece   ██████
```

---

## WHAT TO MOVE / DELETE / KEEP

```
KEEP AS-IS:
✅ Page title, subtitle, filter bar — no changes
✅ KPI strip — no changes (but fix Utilization to 71%, not 100%)
✅ Citation Velocity chart — move to Insights tab
✅ CPS Scatter chart — move to Insights tab
✅ Structural Alignment diverging bars — move to Insights tab
✅ Side drawer sections A, C, D, E, F, G — keep and improve

ADD:
➕ Pages/Insights tab toggle (below KPI strip)
➕ Search input on tab bar (right-aligned)
➕ Traffic column in table (monthly pageviews)
➕ AI Referrals column in table (estimated monthly)
➕ URL subtitle below title in each table row
➕ Drawer Section B: Traffic vs Citations overlay chart
➕ Drawer Section I: Traffic Sources breakdown
➕ Content Lifecycle Distribution chart in Insights tab
➕ "7 published pieces" footer below table

RESTRUCTURE:
🔄 Content table: move from bottom to be the primary view under "Pages" tab
🔄 Charts: move from primary view to "Insights" tab

FIX:
🔧 KPI "Utilization": change from 100% to 71% (5/7 pieces cited)
```

---

## Verification After Restructure

```bash
npm run dev
npx tsc --noEmit
```

1. "Pages" tab is default — content table visible immediately after KPI strip
2. Table shows 7 rows with ALL columns including Traffic and AI Referrals
3. Each row shows title + URL subtitle (two lines per row, 44px height)
4. Platform dots use real favicons (12px)
5. Stale/declining rows have subtle background tinting
6. Sorting works on all sortable columns
7. Click any row → drawer opens with all 9 sections (A through I)
8. Drawer Section B: Traffic vs Citations chart or GA connect prompt
9. Drawer Section I: Traffic sources or GA connect prompt
10. "Insights" tab: shows all three existing charts + lifecycle distribution
11. Charts in Insights tab render correctly (not broken by the move)
12. "7 published pieces" footer visible below table
13. Filter bar still works (date, cluster, lifecycle)
14. KPI Utilization shows 71% not 100%
15. `npm run build` succeeds