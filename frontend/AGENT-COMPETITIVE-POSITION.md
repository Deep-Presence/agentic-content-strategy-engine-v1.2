# Agent — Competitive Position Page (v3 — Production)

> **Read CLAUDE.md and brand-system.md first, then this file.** This builds/rebuilds the `/competitive-position` page.

---

## Mission

Build the Competitive Position page — the page that answers **"Am I winning or losing, and against whom?"** This page absorbs 19 metrics from two categories: Competitive Intelligence (#28-40) and Citation Drift & Risk (#181-186).

---

## Files You Own

```
src/app/(dashboard)/competitive-position/page.tsx
src/app/(dashboard)/competitive-position/_components/
```

**Never touch** shared UI components, other pages, stores, or layout files. Import from `@/components/ui` only.

---

## MANDATORY LAYOUT STANDARDS (Apply to every element on this page)

### Density & Spacing

The page must feel **dense and information-rich** — like a Bloomberg terminal, not a marketing landing page.

```
Page-level horizontal padding: max 24px (1.5rem) — NO max-w-7xl or container wrappers
Section gaps: 16px between sections (NOT 24/32/40)
Card internal padding: 12px-16px (NOT 24px)
KPI card internal padding: 12px
Chart container padding: 12px
Table cell padding: 6px vertical, 8px horizontal
Table row height: 40px
```

If you write `p-6`, `p-8`, `gap-6`, `gap-8`, `space-y-6`, `space-y-8` — stop. Use `p-3`, `p-4`, `gap-3`, `gap-4`, `space-y-3`, `space-y-4`. Remove any `max-w-7xl mx-auto` or `container` class.

### Font Sizes (non-negotiable — apply exactly)

```
Page title: 22px, font-weight 600, Space Grotesk
Page subtitle: 13px, var(--text-secondary)
KPI numbers: 28px, JetBrains Mono, font-weight 600
KPI labels: 11px, uppercase, letter-spacing 0.05em, var(--text-secondary)
KPI trend/sub text: 12px
Section headers: 15px, font-weight 600
Section subtitles: 12px, var(--text-secondary)
Table headers: 11px, uppercase, letter-spacing 0.05em, var(--text-secondary)
Table body text: 13px
Table data values: 13px, JetBrains Mono
Chart axis labels: 11px
Chart legend text: 11px
Status badges/pill text: 10px, uppercase, font-weight 600
```

### Global Filter Bar

Full-width toolbar. Not a card. No rounded corners. No background color. Sits directly below page title with **0 gap**.

```tsx
<div className="flex items-center gap-3 px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <DateRangePicker /> {/* Mar 1, 2026 – Mar 28, 2026 */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} /> {/* vertical divider */}
  <ClusterFilter /> {/* All Clusters ▾ */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <PlatformFilter /> {/* All Platforms ▾ */}
  <button className="ml-auto text-xs" style={{ color: 'var(--text-secondary)' }}>× Clear</button>
</div>
```

Height: 44px. Separated by `border-b` only. Date picker always leftmost. "× Clear" always rightmost.

---

## Page Structure

### KPI Strip (6 cards, single row, full width)

| KPI | Value | Trend | Sub |
|-----|-------|-------|-----|
| Gap to #1 | -5.8pp | was -7.9pp 30d ago | vs bolt.new |
| Gap Trend | Closing | ↑ +2.1pp/30d | 8-week direction |
| Avg Win Rate | 39% | ↑ from 34% | vs top 5 competitors |
| At-Risk Citations | 4 | +2 this period | queries drifting |
| Early Warnings | 2 | — | pre-drift signals |
| Recapture Opps | 3 | — | lost but recoverable |

Use existing `MetricCard` or `KPIRow` from shared UI if available, otherwise create inline. Cards: `1px solid var(--border)`, 12px padding, no shadow, no gradient. JetBrains Mono for values. 11px uppercase overline labels.

---

### Section 1: Head-to-Head Daily Battle (full width)

**Chart type:** Recharts `LineChart` with daily data points. Height: **300px** minimum.

Your line: 3px stroke, `var(--accent)`, filled dots. Competitor lines: 1.5px, dashed, distinct colors.

**Legend:** Inline with section title — right-aligned on the same line as "Head-to-Head Daily Battle". Each legend item: small colored line sample (16px wide) + competitor domain + real favicon (12px). Your line (lovable.dev) listed first with bold label and teal color.

Hover tooltip: exact date, SOV % per competitor for that day.

**Mock data:**

```typescript
const generateBattleData = () => {
  const data = [];
  const startDate = new Date('2026-02-28');
  for (let i = 0; i < 28; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    data.push({
      date: date.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' }),
      'lovable.dev': 8.1 + (i * 0.16) + (Math.random() * 1.2 - 0.6),
      'bolt.new': 18.2 - (i * 0.04) + (Math.random() * 1.0 - 0.5),
      'cursor.com': 11.8 + (i * 0.02) + (Math.random() * 0.8 - 0.4),
      'replit.com': 9.1 - (i * 0.03) + (Math.random() * 0.6 - 0.3),
      'v0.dev': 7.0 + (i * 0.05) + (Math.random() * 0.7 - 0.35),
    });
  }
  return data;
};
```

The chart tells a story: lovable.dev is the fastest-growing line, closing the gap to bolt.new.

---

### Section 2: Two-column layout (55% left / 45% right)

**Left: Head-to-Head Win Rate (#31)**

Horizontal bar chart. When you and a competitor are both eligible for a query, what % of the time are you cited instead?

Bar height: **24px** each. Background track behind each bar: `var(--border)` at 20% opacity. Color: green (≥50%), accent (30-49%), red (<30%).

Real competitor favicon (16px) via `https://www.google.com/s2/favicons?domain={domain}&sz=20`. Do NOT set `crossOrigin` attribute.

```typescript
const WIN_RATES = [
  { domain: "v0.dev", rate: 0.68 },
  { domain: "replit.com", rate: 0.52 },
  { domain: "cursor.com", rate: 0.38 },
  { domain: "bolt.new", rate: 0.22 },
  { domain: "emergent.sh", rate: 0.15 },
];
```

**Right: Gap to #1 Trend (#28, #29)**

Recharts `AreaChart`. Height: **200px** minimum. Gap closing over 8 weeks. Reference line at y=0 (the goal). Area filled with error-subtle color below zero.

```typescript
const GAP_TREND = [
  { week: "Jan 26", gap: -7.9 },
  { week: "Feb 2", gap: -7.5 },
  { week: "Feb 9", gap: -7.1 },
  { week: "Feb 16", gap: -6.8 },
  { week: "Feb 23", gap: -6.5 },
  { week: "Mar 2", gap: -6.2 },
  { week: "Mar 9", gap: -6.0 },
  { week: "Mar 16", gap: -5.8 },
];
```

---

### Section 3: Competitor SOV by Cluster (#32, #37)

Table with inline dual-bar visualization. Sort by your authority descending (strongest first).

Columns: CLUSTER | AUTHORITY (dual bars) | #1 COMPETITOR | ACTION

Dual bars: each bar at least **120px** wide. Numeric scores displayed directly on the bars (white text if bar long enough, else to the right).

**Action tags as pill badges with colored backgrounds:**
- DEFEND: `background: #34B27B`, white text
- CLOSE GAP: `background: var(--accent)`, white text
- INVEST: `background: #F5A623`, dark text
- PRIORITY: `background: #E5484D`, white text

All pills: 10px uppercase font-weight 600, `padding: 2px 8px`, border-radius 4px.

```typescript
const CLUSTER_SOV = [
  { cluster: "Branded Evaluation", you: 72, comp: 68, compDomain: "bolt.new", action: "defend" },
  { cluster: "Category Comparison", you: 58, comp: 71, compDomain: "cursor.com", action: "close_gap" },
  { cluster: "Mechanism", you: 45, comp: 67, compDomain: "emergent.sh", action: "invest" },
  { cluster: "Boundary", you: 38, comp: 62, compDomain: "snyk.io", action: "invest" },
  { cluster: "Definition", you: 34, comp: 55, compDomain: "designrev.com", action: "invest" },
  { cluster: "Feature Verification", you: 31, comp: 48, compDomain: "knack.com", action: "invest" },
  { cluster: "Decision Criteria", you: 28, comp: 52, compDomain: "alloy.app", action: "priority" },
  { cluster: "Problem/Awareness", you: 25, comp: 45, compDomain: "dev.to", action: "priority" },
  { cluster: "Best-of/Consideration", you: 18, comp: 58, compDomain: "rocket.new", action: "priority" },
];
```

---

### Section 4: Citation Drift Tracker (#181-186) — full width table

The early warning system. Columns:

| Query | Drift Score | Took Over | Lost On | Status | Action |
|-------|-------------|-----------|---------|--------|--------|

**Row styling by status:**
- LOST rows: `background: rgba(229, 72, 77, 0.06)`
- AT RISK rows: `background: rgba(245, 166, 35, 0.06)`
- STABLE / NEVER HAD: default background

**Status badges as pill badges:** LOST = red bg/white text, AT RISK = amber bg/dark text, STABLE = green bg/white text, NEVER HAD = gray bg/white text. 10px uppercase.

**Action column:** Small text links (NOT full buttons), `text-xs font-weight-500`:
- LOST: "Recapture →" in red
- AT RISK: "Defend →" in amber
- Both show toast "Added to content queue" on click

All rows: `cursor-pointer`, hover `var(--accent-subtle)`.

Default sort: LOST first → AT_RISK → STABLE → NEVER_HAD. Within each group, by drift score descending.

"Took Over" and "Lost On" columns: real favicon (14px) + domain/platform name. `—` for empty.

```typescript
const DRIFT_DATA = [
  { query: "vibe coding meaning", drift: 0.22, tookOver: "cursor.com", lostOn: "ChatGPT", status: "lost" },
  { query: "AI code generation security risks", drift: 0.18, tookOver: "snyk.io", lostOn: "Claude", status: "lost" },
  { query: "enterprise AI app builder features", drift: 0.15, tookOver: "retool.com", lostOn: "Gemini", status: "lost" },
  { query: "no-code AI app security audit", drift: 0.11, tookOver: null, lostOn: null, status: "at_risk" },
  { query: "how to deploy AI-generated app to prod", drift: 0.08, tookOver: null, lostOn: null, status: "at_risk" },
  { query: "prompt-to-app platform comparison", drift: 0.05, tookOver: null, lostOn: null, status: "at_risk" },
  { query: "bolt.new vs lovable comparison", drift: 0.03, tookOver: null, lostOn: null, status: "stable" },
  { query: "best AI app builder for startups", drift: 0.01, tookOver: null, lostOn: null, status: "stable" },
  { query: "AI app builder data privacy", drift: 0.19, tookOver: "owasp.org", lostOn: null, status: "never_had" },
  { query: "RBAC in AI-generated applications", drift: 0.12, tookOver: "auth0.com", lostOn: null, status: "never_had" },
];
```

---

### Section 5: Most-Cited Competitor URLs (#39)

Specific competitor pages cited most across AI platforms.

| URL | Domain | Influence | Cited On | Your Overlap | Action |

- **Domain:** real favicon (16px) + domain text
- **Cited On:** real platform favicons (16px each, 4px gap). Fetch from: openai.com, anthropic.com, perplexity.ai, google.com, gemini.google.com
- **Your Overlap:** fraction "2/6" + mini progress bar (40px wide, 4px height, teal fill proportional to ratio)
- **Action:** "Analyze →" text link in accent color

```typescript
const PLATFORM_DOMAINS = {
  chatgpt: "openai.com",
  claude: "anthropic.com",
  perplexity: "perplexity.ai",
  google_ai: "google.com",
  gemini: "gemini.google.com",
};

const MOST_CITED_URLS = [
  { url: "bolt.new/blog/ai-app-security", domain: "bolt.new", influence: 81, platforms: ["chatgpt", "perplexity"], overlap: "2/6", overlapRatio: 0.33 },
  { url: "cursor.com/docs/enterprise-features", domain: "cursor.com", influence: 74, platforms: ["claude", "chatgpt", "perplexity"], overlap: "1/5", overlapRatio: 0.20 },
  { url: "owasp.org/ai-security-guide", domain: "owasp.org", influence: 72, platforms: ["chatgpt", "claude", "perplexity"], overlap: "0/3", overlapRatio: 0.00 },
  { url: "snyk.io/learn/ai-code-security", domain: "snyk.io", influence: 68, platforms: ["chatgpt", "claude", "google_ai"], overlap: "0/4", overlapRatio: 0.00 },
  { url: "replit.com/blog/vibe-coding-guide", domain: "replit.com", influence: 65, platforms: ["perplexity", "gemini"], overlap: "3/7", overlapRatio: 0.43 },
  { url: "auth0.com/blog/rbac-best-practices", domain: "auth0.com", influence: 62, platforms: ["chatgpt", "claude"], overlap: "0/3", overlapRatio: 0.00 },
  { url: "dev.to/t/ai-app-builders", domain: "dev.to", influence: 59, platforms: ["perplexity"], overlap: "1/4", overlapRatio: 0.25 },
  { url: "retool.com/blog/ai-app-builder-comparison", domain: "retool.com", influence: 55, platforms: ["google_ai", "chatgpt"], overlap: "2/5", overlapRatio: 0.40 },
];
```

---

### Side Drawer (50% viewport width, slides from right)

Backdrop overlay: `background: rgba(0,0,0,0.15)`. Close button: top-right, 32px hit target.

Drawer header: 16px font-weight 600 title, 12px domain URL below in var(--text-secondary).

Each drawer section: 14px uppercase section header, `border-top: 1px solid var(--border)` separator, 12px top padding.

#### Trigger: Click any competitor name → Competitor Drawer

**Section 1 — SOV by Cluster**
Their authority vs yours per cluster. Mini horizontal dual bars (same layout as Section 3 but filtered to this competitor). Show only clusters where this competitor appears.

**Section 2 — Top Cited URLs**
Their most-cited pages for queries where you both compete. Table: URL | Citations | Platforms (favicon dots). Max 5 rows.

**Section 3 — Structural Comparison**
Average structural signals of their cited content vs yours. Table:

| Signal | Their Avg | Your Avg | Gap |
|--------|-----------|----------|-----|
| Word Count | 2,450 | 1,380 | -1,070 |
| Headers per 500w | 4.2 | 2.1 | -2.1 |
| FAQ Sections | 68% | 20% | -48% |
| Comparison Tables | 55% | 30% | -25% |
| External Citations | 82% | 38% | -44% |
| Reading Level | 9.8 | 11.2 | +1.4 |

Color code gaps: red if you're significantly behind, green if you're ahead.

**Section 4 — Citation Trajectory**
Mini Recharts LineChart (120px height, full drawer width) showing their citation count over 28 days. Single line in their brand color. Hover tooltip with exact daily count.

**Section 5 — Threat Assessment**
Competitor Threat Score (#184). Text summary:
- "bolt.new published 4 new content pieces in your clusters this month"
- "2 of those target clusters where you currently DEFEND"
- Threat level badge: HIGH / MEDIUM / LOW

#### Trigger: Click any query in drift tracker → Query Drawer

**Section 1 — Query Text**
Full query displayed at 16px font-weight 600.

**Section 2 — Your Content**
The closest content piece you have for this query. Show: URL (with external link icon), similarity score (0-1 in JetBrains Mono), structural scores (word count, headers, FAQ, tables). If no content piece is close, show "No matching content found" in red.

**Section 3 — What Replaced You**
Competitor URL that took the citation. Show: URL, their similarity score, their structural scores. Side-by-side comparison with your content.

**Section 4 — Structural Gap**
What they have that you don't. List of missing structural elements:
- "❌ Missing FAQ section (they have 3 FAQs)"
- "❌ Word count 1,200 vs their 2,800"
- "✅ You have comparison tables (they don't)"
- "❌ Missing external citations (they cite 8 sources)"

**Section 5 — Action**
"Create content brief →" button (accent background, white text). On click: shows toast "Content brief created — view in Content Planner".

---

## Metrics Coverage Checklist

Ensure ALL 19 metrics are represented. Verify each one exists on the page:

- [x] #28 Gap to #1 → KPI strip "Gap to #1" card + Gap Trend chart y-values
- [x] #29 Gap Trend → KPI strip "Gap Trend" card + Gap Trend chart slope
- [x] #30 Competitive Citation Overlap → Most-Cited URLs "Your Overlap" column
- [x] #31 Head-to-Head Win Rate → Win Rate horizontal bars
- [x] #32 Competitor SOV per Cluster → SOV by Cluster table (your score column)
- [x] #33 Competitor Citation Count by Platform → Side drawer + Most-Cited URLs "Cited On" column
- [x] #34 Competitor Content Velocity → Side drawer Threat Assessment (new pieces published)
- [x] #35 Citation Displacement Events → Drift Tracker LOST rows (count = displacement events)
- [x] #36 Competitive Structural Gap → Side drawer Structural Comparison table
- [x] #37 Competitor Authority Score per Cluster → SOV by Cluster table (competitor score column)
- [x] #38 Competitor Page Structure Analysis → Side drawer Structural Comparison details
- [x] #39 Most-Cited Competitor URLs → Most-Cited URLs table (all 8 rows)
- [x] #40 Competitor Citation Trajectory → Head-to-Head chart (competitor lines) + Side drawer mini chart
- [x] #181 Citation Drift Score per Query → Drift Tracker "Drift Score" column
- [x] #182 At-Risk Citations → KPI strip "At-Risk Citations" card + Drift Tracker AT_RISK rows
- [x] #183 Lost Citations with Cause → Drift Tracker LOST rows with "Took Over" + "Lost On" columns
- [x] #184 Competitor Threat Score → KPI strip "Early Warnings" card + Side drawer Threat Assessment
- [x] #185 Citation Recapture Opportunities → KPI strip "Recapture Opps" card + Drift Tracker "Recapture →" button
- [x] #186 Early Warning Signals → KPI strip "Early Warnings" card + Drift Tracker AT_RISK status rows

---

## Brand System Rules

- All colors from CSS variables (`var(--accent)`, `var(--text-primary)`, `var(--border)`, etc.) — never hardcode hex values for UI elements
- Platform brand colors for competitor chart lines are acceptable as constants since they represent external brands
- All cards: `border: 1px solid var(--border)` — no borderless cards, no shadows, no gradients
- JetBrains Mono for ALL data values (numbers, scores, percentages, rates)
- Space Grotesk for ALL text (labels, headers, body, descriptions)
- Real brand logos everywhere — `https://www.google.com/s2/favicons?domain={domain}&sz={size}`. Never colored circles with initials. Do NOT set `crossOrigin="anonymous"` on favicon images.
- Supports both light and dark mode via CSS variables
- Max font-weight: 600 (never use 700/800/900 except gauge scores)

---

## Verification

```bash
npm run dev     # page renders at /competitive-position without errors
npx tsc --noEmit  # 0 type errors
```

1. Page padding is tight — 24px max horizontal, 16px between sections, no floating cards
2. Filter bar spans full width as toolbar — no rounded corners, border-bottom only, 44px height
3. All font sizes match the standardization table exactly (spot-check: KPI numbers = 28px, table headers = 11px uppercase)
4. KPI strip: 6 cards visible, JetBrains Mono values, trend text colored correctly
5. Head-to-Head chart: 300px height, 5 lines, your line bold teal, inline legend with favicons
6. Win Rate bars: 24px height, background track visible, favicons loading (check Network tab for 404s)
7. SOV by Cluster: 9 rows, dual bars 120px+ wide, pill-style action badges with colored backgrounds
8. Drift Tracker: 10 rows sorted by status priority, status pill badges, LOST/AT_RISK rows have subtle background tint
9. Most-Cited URLs: 8 rows, platform favicons loading, overlap mini progress bar visible
10. Side drawer opens on competitor click — shows 5 sections with data
11. Side drawer opens on query click — shows 5 sections with structural gap detail
12. All favicons loading — verify in Network tab, no 404s
13. Works in both light and dark mode (toggle and check)
14. `npm run build` — succeeds with 0 errors

---

## Completion Criteria

- [ ] Page loads at `/competitive-position` with no console errors
- [ ] Global filter bar: full-width toolbar with date + cluster + platform filters
- [ ] KPI strip: 6 cards with correct values, trends, and sub-text
- [ ] Head-to-Head battle chart: 300px, daily data, 28 days, 5 lines, inline legend with favicons
- [ ] Win Rate: 5 horizontal bars, 24px height, real favicons, colored by threshold
- [ ] Gap to #1 Trend: area chart, 200px, 8 weeks, reference line at zero
- [ ] SOV by Cluster: 9 rows, dual bars with scores, pill action badges
- [ ] Drift Tracker: 10 rows, status pills, row background tinting, action links
- [ ] Most-Cited URLs: 8 rows, platform favicon indicators, overlap progress bars
- [ ] Competitor drawer: opens on click, 5 sections populated with mock data
- [ ] Query drawer: opens on click, 5 sections including structural gap list
- [ ] All 19 metrics from checklist are represented (verify each one)
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts, real logos
- [ ] Density: no section gap > 16px, no card padding > 16px, no page padding > 24px
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds