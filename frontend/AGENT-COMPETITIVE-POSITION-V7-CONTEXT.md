# Competitive Position Page — Full Context Handover

> **For the next Claude Code agent.** This documents everything discussed, decided, built, and still pending for the `/competitive-position` page across 7 iterations in one session.

---

## Current State (v7 — built and running)

The page is at `src/app/(dashboard)/competitive-position/` on branch `new-frontend-v2`.

### Files that exist right now:

```
page.tsx                          — Main page (single scroll, no tabs)
_components/data.ts               — All mock data (competitors, clusters, dimensions, etc.)
_components/brand-logo.tsx         — Favicon fetcher with fallback
_components/slide-drawer.tsx       — Reusable 50vw slide drawer
_components/sparkline.tsx          — Inline SVG sparkline component
_components/kpi-strip.tsx          — 3 plain KPI cards (SOV, Rank, Win Rate)
_components/sov-hero.tsx           — Market Share donut + SOV trend chart + Rising Threats
_components/landscape-grid.tsx     — Full-width stacked landscape (Direct/Mind Share/Authority)
_components/head-to-head.tsx       — Pinnable H2H cards (max 10) + expandable table
_components/cluster-cards.tsx      — Dimension breakdown (Intent/Funnel/Persona) + Cluster cards
_components/activity-feed.tsx      — Timeline + Table toggle with priority badges
_components/drawers.tsx            — CompetitorDrawer + ClusterDrawer
```

### Files that were DELETED (sections removed per user request):

```
territory-table.tsx    — removed (data lives on Embedding Lab page)
citation-watchlist.tsx — removed (data lives on Embedding Lab page)
collapsible.tsx        — removed (no longer needed)
position-table.tsx     — removed (merged into H2H expandable table)
platform-section.tsx   — removed (belongs on Citation Intelligence page)
```

---

## Page Section Order (current v7):

1. **KPI Strip** — 3 plain cards: SOV 12.4%, Rank #2/17, Win Rate 39%. No icons, no colored borders.
2. **Market Share Donut + SOV Trend** — Side by side. Donut shows you vs Direct vs Mind Share vs Authority. SOV chart has click-to-highlight on competitor lines.
3. **Rising Threats** — Compact card with 4 rising competitors (sparklines + deltas).
4. **Competitive Landscape** — Full-width STACKED (not 3-column grid). Each category (Direct, Mind Share, Authority) is its own full-width section with explanatory header. Click any brand → competitor drawer.
5. **Head-to-Head Cards** — Pinnable (max 10). Top 6 pinned by default. Expandable table below for remaining brands. Category badges.
6. **Competitive Breakdown** — Intent/Funnel/Persona toggle. Individual cards per dimension with mini SVG donut charts showing your SOV vs leader.
7. **Cluster Breakdown** — 3-column grid of cluster cards with top competitors. Click → cluster drawer.
8. **Activity Feed** — Timeline + Table view toggle. Priority badges (P1/P2/P3). Click row for detail.

---

## Key User Decisions (from deep interview):

### What metrics to show:
- **SOV** is primary (framed as "market share" in competitive context)
- **Rank** must show total tracked brands (currently 17 in mock, real pipeline tracks 50-70)
- **Win Rate** kept but user was initially skeptical — may need rethinking
- **"Gap to Leader"** was rejected as confusing — removed
- **"Territory Control"** was tried and removed

### What was explicitly rejected/removed:
- ❌ Scatter plots, radar charts, heatmaps, treemaps — ALL rejected
- ❌ Platform Divergence matrix — user hated it ("worst map")
- ❌ Territory Position table — lives on Embedding Lab
- ❌ Citation Watchlist — lives on Embedding Lab
- ❌ Strategy per Category section — removed
- ❌ Detailed Matchups collapsible — removed
- ❌ All em dashes in copy — user considers them "AI slop"
- ❌ Colored icon circles on KPIs — "AI slop"
- ❌ Colored left borders on KPIs — tried and removed
- ❌ Any SOV trend that overlaps with Citation Intelligence page
- ❌ Tabs — user wants single page with sections

### What the user explicitly approved:
- ✅ Head-to-head cards format (confirmed "good")
- ✅ Competitive Landscape (Direct/Mind Share/Authority) — "unique differentiator nobody else offers"
- ✅ Activity Feed concept — chronological competitor moves
- ✅ Cluster cards with top competitors
- ✅ Dimension breakdown (Intent/Funnel/Persona) aligned with Content Planner
- ✅ Market Share donut
- ✅ Pinnable H2H cards (max 10, rest in expandable table)
- ✅ Full-width stacked landscape (not 3-column grid)
- ✅ Individual dimension cards with mini donuts
- ✅ Timeline + Table toggle for activity feed
- ✅ Click-to-highlight on SOV chart lines

### Content Planner alignment:
- The competitive page dimensions mirror the Content Planner's taxonomy:
  - **Intent**: Informational, Commercial, Navigational, Transactional
  - **Funnel Stage**: TOFU, MOFU, BOFU
  - **Persona**: Solo Founder, Product Manager, Agency Owner, Technical Engineer
  - **Clusters**: Match gap_analysis clusters from the pipeline
- Content actions link to Content Planner (recommendations already exist there from pipeline)

### Copy rules:
- Short factual statements only
- No em dashes anywhere
- No narrative suggestions
- No AI-sounding prose
- Example: "bolt.new leads with 18.2%. You have 12.4%."

### Drill-down requirements:
- Every brand, cluster, query, and activity item must be clickable
- Competitor drawer: tabs (Overview, Queries, Compare) — currently only Overview built
- Cluster drawer: must show FULL query list with who's cited on each platform
- Activity feed: click row → side panel with full event detail

---

## What Still Needs Work (user's latest feedback on v7):

The user said "everything looks good from the data standpoint" but needs better organization and polish:

1. **KPI strip** — "don't write unnecessary things." Keep it even simpler.
2. **SOV chart** — needs better color palette, more interactive feel
3. **Rising Threats** — currently takes right amount of space but could be polished
4. **Competitive Landscape** — cards need to be "bigger, easily readable." Drill-down drawer on right needs rich data (full competitor profile with tabs: Overview, Queries, Compare)
5. **Head-to-Head cards** — need to be "more aesthetic from outside and inside." Data not properly organized. Add small graphs.
6. **Competitive Breakdown** — "show graphs, take up enough space." Individual cards per dimension is approved but execution needs polish
7. **Cluster cards** — insights are "vague." Need to highlight insights properly.
8. **Activity Feed** — needs more detail, table form, side panel with multiple data points, priority grading
9. **All drawers** — need richer content. Competitor drawer needs 3 tabs (Overview/Queries/Compare). Currently only basic overview.
10. **No em dashes** — remove ALL em dashes everywhere in the codebase for this page

---

## Data Architecture (in data.ts):

### Core data structures:
- `YOUR_DATA` — SOV, rank, winRate, sparkline, gaps closed/opened
- `COMPETITORS` (6) — domain, SOV, citations, delta, winRate, trend, sparkline, delta7d/14d/28d
- `MINDSHARE` (5) — domain, SOV, citations, label (type)
- `AUTHORITY` (5) — domain, SOV, citations, label (type)
- `ALL_BRANDS` (17) — combined list for market share
- `MARKET_SHARE` — category breakdown (you 12.4%, direct 56.4%, mind share 9.7%, authority 12.9%, others 8.6%)
- `CLUSTER_RANKINGS` (9) — cluster, yourRank, yourShare, leaderDomain, gap, coverage, status
- `CLUSTER_CARDS` (6) — enriched with intent, funnelStage, topBrands, contentGap
- `INTENT_BREAKDOWN` (4) — per-intent competitive data
- `FUNNEL_BREAKDOWN` (3) — per-funnel-stage competitive data
- `PERSONA_BREAKDOWN` (4) — per-persona competitive data
- `SOV_TREND` (28 days) — daily SOV for you + 5 competitors
- `RANK_HISTORY` (28 days) — computed daily ranks
- `CITATIONS` (11) — lost/at_risk/stable/never_had items
- `COMPETITOR_DETAILS` (6) — per-competitor drawer data (queries won/lost, why they win, how to close gap)
- `CLUSTER_DETAILS` (2) — per-cluster drawer data (queries, strategy)
- `PRIORITY_ACTIONS` (8) — aggregated gap-closing actions ranked by impact

### Platform SOV data:
- ChatGPT: 14.2% (#2, +2.1)
- Claude: 8.1% (#5, +0.4)
- Perplexity: 18.6% (#1, +4.8)
- Gemini: 10.3% (#3, -0.2)
- Google AI: 11.2% (#3, +1.1)

---

## Design System Rules (from CLAUDE.md + brand-system.md):

- Font display: Space Grotesk (all non-code text)
- Font mono: JetBrains Mono (all numbers/data values)
- All colors via CSS variables: var(--accent), var(--text-primary), etc.
- **Exception for SVG/Recharts**: Use hardcoded hex (#5BA4C4, #E5484D, etc.) — CSS vars don't resolve in SVG context
- Card borders: 1px solid var(--border), borderRadius 6-8px
- No shadows on cards, no gradients in product UI
- Table headers: 9-10px uppercase, 0.06em letter-spacing
- Table rows: 34-38px height, hover bg var(--accent-subtle)
- Max font-weight: 600
- All brand logos: Google Favicon API with Clearbit fallback
- Do NOT use crossOrigin="anonymous" on favicon images

---

## Build Commands:

```bash
npx tsc --noEmit          # TypeScript check (0 errors on competitive-position)
npm run build             # Production build (succeeds, 19.8 kB bundle)
npm run dev               # Dev server (localhost:3000)
```

---

## Git Status:

- Branch: `new-frontend-v2`
- Last competitive-position commit: `88f41fc` (v6)
- v7 changes are uncommitted (staged files pending)
- Other pages also have uncommitted changes (analytics, embedding-lab, technical-readiness)

---

## Memory Files (user preferences):

- `/Users/shashank/.claude/projects/.../memory/feedback_brand_hub_quality.md` — $20K platform quality standards
- `/Users/shashank/.claude/projects/.../memory/feedback_clear_next_cache.md` — Always kill dev server + rm -rf .next before restart
- `/Users/shashank/.claude/projects/.../memory/feedback_drilldown_architecture.md` — Every metric must drill down, progressive disclosure, don't reduce content

---

## Critical User Quotes:

- "This is a $20K/month platform. It should look really polished."
- "Don't add any em dashes. Remove everything which makes it look like AI slop."
- "Show the drill downs on deeper insights where it's needed."
- "Data storytelling. How do we make sense out of that data?"
- "Mind share and authority — focus more on this kind of data."
- "If you want to represent data in tabs, you can totally do that."
- "3-4 hero sections prominently + expandable detail sections."
- "Head-to-head cards are good." (confirmed)
- "Show 10-20 pinnable competitors, rest in hidden table."
- "Individual cards per dimension" (for Intent/Funnel/Persona breakdown)
- "Full width stacked" (for landscape categories)
- "Click competitor → full profile with tabs (Overview, Queries, Compare)"
- "Short factual statements only. No narrative, no em dashes."
- "Two views: Timeline + Table toggle" (for activity feed)
- "Remove Territory Position and Citation Watchlist completely" (on Embedding Lab)
