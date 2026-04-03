# Agent — Brand Presence Page (Production Build)

> **Read CLAUDE.md and brand-system.md first, then this file.** This is a NEW PAGE build at `/` (home route). Also includes a sidebar rename.

---

## Mission

Build the **Brand Presence** page — the executive overview and default landing page of Deep Presence. This is the first thing a CMO sees when they open the app. It answers one question: "How is my brand doing across AI engines?"

The page follows the Robinhood pattern:
- **One hero number** — the Presence Score — massive, unmissable
- **One adaptive chart** — shows how the score moved over time. Hover updates the hero number live
- **One competitive leaderboard** — always visible beside the chart, updates on hover
- **Insight cards below** — each card is a lens that changes what the chart shows
- **No tabs.** One page, one scroll, infinite depth through interaction

---

## Files You Own

```
src/app/(dashboard)/page.tsx              ← Brand Presence (home route)
src/app/(dashboard)/_components/          ← shared components if needed
```

Also modify:
```
src/components/sidebar.tsx (or equivalent) ← rename section + add new item
```

---

## SIDEBAR CHANGES

### Rename "PRESENCE" section to "INTELLIGENCE"

Find the sidebar section currently labeled "PRESENCE" (containing Citation Intelligence, Competitive Position, Prompt Tracking) and rename it to "INTELLIGENCE".

### Add "Brand Presence" as top-level sidebar item

Add "Brand Presence" ABOVE the INTELLIGENCE section. It should be the first item in the sidebar, before any section headers. It links to `/` (home route).

```
Brand Presence          ← NEW (links to /, always visible, not inside a section)
─────────
INTELLIGENCE            ← RENAMED from "PRESENCE"
  Citation Intelligence
  Competitive Position
  Prompt Tracking
SIGNALS
  Content Performance
  Technical Readiness
  Embedding Lab
CONTENT
  Content Planner
  Content Studio
KNOWLEDGE
  Brand Hub
  Documents
```

"Brand Presence" should have a slightly different visual weight — perhaps a small icon or slightly larger font than the section items, since it's the primary landing page.

---

## MANDATORY LAYOUT STANDARDS

Apply the same standards from other agent files:

```
Page horizontal padding: max 24px
Section gaps: 16px
Card internal padding: 12px
Font sizes: match brand-system.md exactly
1px borders on all cards
JetBrains Mono for ALL data values
Space Grotesk for ALL text
Real brand logos via Google Favicon API
Do NOT set crossOrigin="anonymous" on favicon images
CSS variables for all colors
```

---

## PAGE STRUCTURE (Top to Bottom)

### 1. Page Header

```
Brand Presence
Your brand's visibility and authority across AI engines
```

Title: 22px font-weight 600. Subtitle: 13px var(--text-secondary).

### 2. Global Filter Bar

Full-width, 40px height, border-bottom only. Left-aligned:

```
📅 Mar 1, 2026 – Mar 28, 2026  |  All Platforms ▾  |  All Clusters ▾
```

Date range: clickable, opens two-month calendar popup (same pattern as other pages). Platform filter: dropdown with All / ChatGPT / Claude / Perplexity / Google AI / Gemini. Cluster filter: dropdown with All + list of topic clusters.

These filters affect ALL data on the page — chart, leaderboard, insight cards, everything.

### 3. Presence Score Hero

This is the centerpiece. The Presence Score is a proprietary composite metric (0-100) combining:
- Share of Voice (weight: 35%)
- Citation Rate (weight: 25%)
- Average Position (weight: 20%, inverted — lower position = higher score)
- Sentiment (weight: 10%)
- Platform Coverage (weight: 10%)

Display:

```
74
Presence Score  ·  +6 this month
```

The number: **52px** JetBrains Mono, font-weight 700. Color: var(--text-primary). 
Below: "Presence Score" in 13px var(--text-secondary), then " · +6 this month" in green (or red if declining).

**On chart hover:** The 52px number updates in real-time to show the Presence Score at that specific date. The delta text changes to show the date: "Mar 15, 2026". When the user stops hovering, it reverts to the current value and delta.

This hover-to-update interaction is the signature UX of the page. It must be smooth — no flickering, no lag. Use React state, not DOM manipulation.

### 4. View Toggles + Time Range

Directly below the hero, two rows of controls:

**View toggles** (left-aligned): Small pill buttons that change what the chart displays.

```
[Presence Score]  [Share of Voice]  [Citations]  [Mentions]  [Avg Position]
```

Active toggle: colored background tint matching the view's accent color, colored text. Inactive: transparent, var(--text-secondary).

Each view changes:
- The chart data and line color
- The hero number format
- The hero delta
- The leaderboard values (where applicable)

View definitions:
- **Presence Score** (default): composite 0-100 score, teal accent, hero shows "74"
- **Share of Voice**: percentage, teal accent, hero shows "12.4%", delta "+4.3pp"
- **Citations**: count, green accent, hero shows "847", delta "+124 this period"
- **Mentions**: count, purple accent, hero shows "1,203", delta "+89 this period"
- **Avg Position**: number (lower is better), amber accent, hero shows "2.3", delta "improved by 0.8"

**Time range** (right-aligned): `1W  1M  3M  6M` — small buttons. Active: surface background, primary text. Inactive: transparent, muted text.

### 5. Chart + Competitive Leaderboard (Side by Side)

Use CSS Grid: `grid-template-columns: 1fr 240px` with 16px gap.

#### Chart (Left)

A smooth area chart with gradient fill. Border: `1px solid var(--border)`, border-radius 6px, padding 12px 16px.

**Chart specifications:**
- Smooth bezier curve (use cubic bezier control points, not straight lines between points)
- Gradient fill below the line: from `{color} at 25% opacity` to `{color} at 2% opacity`
- Line width: 2.5px, rounded caps and joins
- Subtle grid lines: 3 horizontal lines at 25%, 50%, 75%, stroke 0.5px var(--border)
- X-axis labels: show 5 evenly spaced dates, 10px var(--text-secondary)
- Key data points: small dots (3px radius) at start, 33%, 66%, and end of the chart
- Hover interaction: vertical dashed line follows cursor, solid dot (5px) on the line, value label above the dot

**Competitor ghost lines** (SOV view only):
- Dashed lines (strokeDasharray: "4 4", opacity 0.3) for each competitor
- Toggle button below chart: "Show competitors" / "Hide competitors"
- When visible, show a legend: dashed line + competitor name for each

**Chart must use SVG, not a charting library.** Build the chart as an inline SVG component with calculated paths. This gives full control over the hover interaction, gradient fills, and animation.

Data: generate 28 days of realistic data for each metric. The Presence Score should trend upward from ~68 to ~74 with natural variation. SOV from ~8% to ~12.4%. Citations from ~22/day to ~32/day. Use sine waves + random noise for realistic patterns.

#### Competitive Leaderboard (Right)

Border: `1px solid var(--border)`, border-radius 6px, padding 12px 14px.

Header: "Share of Voice Ranking" (or "{View Label} Ranking" when view changes) — 11px uppercase var(--text-secondary).

Ranked list of brands:

```
1  [favicon] Bolt.new          18.2%
2  [favicon] Lovable    YOU    12.4%    ← highlighted
3  [favicon] Cursor             11.8%
4  [favicon] Replit              9.1%
5  [favicon] V0.dev              7.3%
```

Each row: rank (JetBrains Mono 11px), favicon (14px), name (12px), value (JetBrains Mono 13px font-weight 600).

"YOU" row: accent subtle background, 2px accent left border, accent-colored text. "YOU" badge: tiny pill with accent background, white text, 9px.

**Live update on hover:** When the user hovers on the chart, leaderboard values update to reflect that date's data. Rankings may shift — animate the reorder smoothly. This is the killer feature — watching rankings shift as you scrub through time.

Mock competitors and their SOV trends:
```typescript
const COMPETITORS = [
  { domain: "bolt.new", name: "Bolt.new", sovStart: 18.5, sovEnd: 17.1, trend: "declining" },
  { domain: "cursor.com", name: "Cursor", sovStart: 11.5, sovEnd: 11.8, trend: "stable" },
  { domain: "replit.com", name: "Replit", sovStart: 9.5, sovEnd: 8.8, trend: "declining" },
  { domain: "v0.dev", name: "V0.dev", sovStart: 7.1, sovEnd: 7.4, trend: "stable" },
  { domain: "emergent.sh", name: "Emergent", sovStart: 5.0, sovEnd: 5.3, trend: "growing" },
];
```

Your SOV: starts at 8.1%, ends at 12.4% (growing). This means during the scrub, the user can see themselves overtake Replit and close the gap on Cursor.

### 6. Insight Cards (4 cards, horizontal)

`grid-template-columns: repeat(4, 1fr)`, gap 10px.

Each card: `1px solid var(--border)`, border-radius 6px, padding 12px 14px, background var(--surface). On hover: border lightens, background shifts to hover color. **Active state** (when clicked and affecting chart): `border-top: 2px solid {accent color}`, tinted background.

**Card 1: "Cited vs Mentioned"**

```
CITED VS MENTIONED

67%        89%
Cited      Mentioned

[amber bar] 22% gap — 11 queries mention without citing
```

Two large numbers (22px JetBrains Mono). The 22% gap as an amber-tinted bar below with explanatory text. Clicking this card toggles the chart between Citations and Mentions views.

**Card 2: "Platform Breakdown"**

Five horizontal bars showing each platform's share:

```
PLATFORM BREAKDOWN

[favicon] ChatGPT      ███████████████  36.8%
[favicon] Claude        ████████         21.2%
[favicon] Perplexity    ███████          18.4%
[favicon] Google AI     █████            13.5%
[favicon] Gemini        ████             10.1%
```

Each bar: 6px height, platform's brand color, proportional width. Favicon (14px) + name (12px) + bar + percentage (JetBrains Mono 12px). Clicking a platform could filter the chart to that platform's data.

**Card 3: "Top Cited Content"**

```
TOP CITED CONTENT

#1  AI App Builder Comparison Guide          63
#2  Lovable vs Cursor: Honest Review         38
#3  Vibe Coding for Enterprise Teams         31
```

Three rows: rank (10px mono muted), title (11px, truncated), citation count (JetBrains Mono 12px green). Clicking navigates to Citation Intelligence → Citation URLs section.

**Card 4: "Citation Sentiment"**

```
CITATION SENTIMENT

Positive  ████████████████████████  72%
Neutral   ████████                  22%
Negative  ██                         6%

Overwhelmingly positive. Negative around pricing.
```

Three horizontal bars with colors: green (positive), gray (neutral), red (negative). Small explanatory text below. 10px labels, 5px bar height, JetBrains Mono 11px percentages.

### 7. Platform Intelligence Grid

Below insight cards. Section header: "Platform Intelligence" — 15px font-weight 600.

5 cards in a row (`grid-template-columns: repeat(5, 1fr)`, gap 8px).

Each platform card:
```
┌──────────────────────────┐
│ [favicon] ChatGPT   TOP  │
│                          │
│ 312                      │  ← 24px JetBrains Mono
│ citations                │
│                          │
│ SOV           14.2%      │
│ Avg Rank      2.1        │
│ Coverage      78%        │
│ Sentiment     Positive   │
│                          │
│ [sparkline chart]        │  ← 24px height mini sparkline
│                          │
│ ✓ Best rank (2.1)        │  ← green, 10px
│ ✗ Low security coverage  │  ← amber, 10px
└──────────────────────────┘
```

Border: `1px solid var(--border)`, border-radius 6px, padding 12px. Top platform gets `border-top: 2px solid {platform color}` and "TOP" label.

Sparkline: simple SVG line chart, 24px height, platform's brand color, showing citation trend over the time period.

Insights at bottom: one positive (green ✓) and one area-for-improvement (amber) per platform. 10px text.

### 8. Citation URLs Table

Section header: "Citation URLs" — 15px font-weight 600. Subtitle: "Every URL cited by AI platforms, ranked by citation count" — 12px var(--text-secondary).

Table with `1px solid var(--border)`, border-radius 6px.

Columns:
```
URL | TITLE | CITATIONS ↓ | PLATFORMS | CPS | VELOCITY
```

- URL: 12px accent color, truncated with ellipsis, clickable
- Title: 12px, truncated
- Citations: JetBrains Mono 13px font-weight 600
- Platforms: small favicon icons for each platform that cites this URL
- CPS (Citations Per Source): JetBrains Mono 13px, color-coded (green ≥ 0.6, amber ≥ 0.45, red < 0.45)
- Velocity: JetBrains Mono 13px, green if ≥ 3.0

Row click: opens side drawer with URL detail (citations over time, which queries cite it, platform breakdown, content analysis).

Mock data: 8-10 URLs with realistic citation counts ranging from 8 to 63.

---

## ANIMATIONS

```css
@keyframes fadeUp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
```

- Stagger fadeUp on table rows (25ms per row)
- fadeUp on insight cards (50ms per card)
- fadeUp on platform grid cards (50ms per card)
- Smooth transition (150ms) on all hover states
- Chart hover: no animation delay — instant update on hero number
- Leaderboard reorder: use CSS transition on transform/position for smooth rank changes
- View toggle: chart line should transition smoothly (or fade) when switching views

---

## MOCK DATA

Generate 28 days of data with these requirements:

```typescript
interface DayData {
  date: string;           // "Mar 1"
  presenceScore: number;  // 0-100, trending 68 → 74
  sov: number;            // %, trending 8.1 → 12.4
  citations: number;      // daily count, 22 → 32 range
  mentions: number;       // daily count, 35 → 48 range
  position: number;       // 3.1 → 2.3, lower is better
  // Per-platform citation counts
  chatgpt: number;
  claude: number;
  perplexity: number;
  google: number;
  gemini: number;
  // Sentiment
  positive: number;       // percentage
  neutral: number;
  // Competitor SOV
  boltSov: number;        // 18.5 → 17.1 (declining)
  cursorSov: number;      // 11.5 → 11.8 (stable)
  replitSov: number;      // 9.5 → 8.8 (declining)
  v0Sov: number;          // 7.1 → 7.4 (stable)
  emergentSov: number;    // 5.0 → 5.3 (growing)
}
```

Use sine waves + random noise for realistic daily variation. The overall trends should be clear when hovering through time.

Citation URLs mock data:
```typescript
const URLS = [
  { url: "lovable.dev/blog/ai-app-builder-comparison", title: "AI App Builder Comparison Guide", citations: 63, platforms: ["chatgpt","claude","perplexity","google"], cps: 0.713, velocity: 4.8, firstCited: "Jan 14, 2026" },
  { url: "lovable.dev/blog/lovable-vs-cursor", title: "Lovable vs Cursor: Honest Review", citations: 38, platforms: ["chatgpt","perplexity","google"], cps: 0.654, velocity: 3.9, firstCited: "Jan 21, 2026" },
  { url: "lovable.dev/blog/vibe-coding-enterprise", title: "Vibe Coding for Enterprise Teams", citations: 31, platforms: ["claude","perplexity","google"], cps: 0.649, velocity: 3.2, firstCited: "Jan 31, 2026" },
  { url: "lovable.dev/blog/bolt-new-alternatives", title: "Bolt.new Alternatives in 2026", citations: 29, platforms: ["chatgpt","perplexity"], cps: 0.521, velocity: 1.4, firstCited: "Feb 13, 2026" },
  { url: "lovable.dev/blog/security-ai-apps", title: "Security in AI-Generated Apps", citations: 24, platforms: ["claude","chatgpt"], cps: 0.482, velocity: 2.1, firstCited: "Feb 7, 2026" },
  { url: "lovable.dev/blog/non-tech-founder-guide", title: "Non-Technical Founder's Guide", citations: 22, platforms: ["chatgpt","claude","perplexity"], cps: 0.538, velocity: 2.9, firstCited: "Feb 19, 2026" },
  { url: "lovable.dev/docs/getting-started", title: "Getting Started Guide", citations: 19, platforms: ["chatgpt","claude"], cps: 0.521, velocity: 1.5, firstCited: "Jan 9, 2026" },
  { url: "lovable.dev/blog/rbac-ai-apps", title: "RBAC in AI-Generated Applications", citations: 18, platforms: ["claude","perplexity"], cps: 0.459, velocity: 0.8, firstCited: "Feb 24, 2026" },
];
```

---

## PRESENCE SCORE CALCULATION

The Presence Score is a weighted composite of 5 metrics, normalized to 0-100:

```typescript
function calculatePresenceScore(data: DayData): number {
  const sovScore = Math.min(data.sov / 25 * 100, 100);        // 25% SOV = 100
  const citationRate = (data.citations / (data.citations + data.mentions)) * 100;
  const positionScore = Math.max(0, (5 - data.position) / 4 * 100);  // position 1 = 100, position 5 = 0
  const sentimentScore = data.positive;                         // already 0-100
  const platformCount = [data.chatgpt, data.claude, data.perplexity, data.google, data.gemini].filter(v => v > 0).length;
  const coverageScore = (platformCount / 5) * 100;

  return Math.round(
    sovScore * 0.35 +
    citationRate * 0.25 +
    positionScore * 0.20 +
    sentimentScore * 0.10 +
    coverageScore * 0.10
  );
}
```

Show this formula somewhere accessible — maybe a small info icon next to "Presence Score" that shows a tooltip explaining the components and weights.

---

## CHART IMPLEMENTATION

Build the chart as a custom SVG component. Do NOT use Recharts or any charting library.

```typescript
interface ChartProps {
  data: DayData[];
  dataKey: string;
  color: string;
  suffix?: string;
  hoverIdx: number | null;
  onHover: (idx: number | null) => void;
}
```

Requirements:
- Smooth bezier curves between data points (use cubic bezier control points)
- Gradient fill: `<linearGradient>` from color at 25% opacity to 2% opacity
- Hover: vertical dashed line + solid dot + value label
- X-axis: 5 evenly spaced date labels
- Responsive: use viewBox and 100% width
- Competitor ghost lines: dashed, low opacity, toggleable
- Transitions: when switching views, the line should have a subtle css transition

---

## VERIFICATION

```bash
npm run dev
npx tsc --noEmit
```

1. Page loads at `/` (home route) as Brand Presence
2. Sidebar: "Brand Presence" appears at top, PRESENCE renamed to INTELLIGENCE
3. Hero number: 52px Presence Score that updates on chart hover
4. View toggles: Presence Score / SOV / Citations / Mentions / Avg Position all work
5. Time range: 1W / 1M / 3M / 6M toggles
6. Chart: smooth bezier area chart with gradient fill
7. Chart hover: vertical line, dot, value label, hero updates live
8. Competitor ghost lines: visible on SOV view, toggleable
9. Leaderboard: 5 brands ranked, "YOU" highlighted, updates on hover
10. Leaderboard reorder: rankings shift when hovering to dates where positions changed
11. Insight card 1: Cited vs Mentioned with 22% gap indicator
12. Insight card 2: Platform bars with favicons and percentages
13. Insight card 3: Top 3 cited URLs with citation counts
14. Insight card 4: Sentiment bars with explanatory text
15. Platform Intelligence: 5 cards with sparklines and insights
16. Citation URLs table: 8 rows, sortable by citations, hover states
17. All favicons loading (Google Favicon API)
18. All animations: fadeUp stagger, hover transitions, chart interaction
19. Global filters: date, platform, cluster
20. All text sizes match brand-system.md
21. CSS variables for all colors
22. `npm run build` succeeds

---

## COMPLETION CRITERIA

- [ ] Brand Presence page loads at `/` with no console errors
- [ ] Sidebar updated: Brand Presence at top, PRESENCE → INTELLIGENCE
- [ ] Presence Score hero: 52px, updates on hover, reverts on mouse leave
- [ ] 5 view toggles working: Presence Score, SOV, Citations, Mentions, Position
- [ ] SVG area chart: bezier curves, gradient fill, hover interaction
- [ ] Competitor ghost lines on SOV view with toggle
- [ ] Competitive leaderboard: live-updating rankings on hover
- [ ] 4 insight cards: Cited/Mentioned, Platforms, Top Content, Sentiment
- [ ] Platform Intelligence: 5 cards with sparklines and per-platform insights
- [ ] Citation URLs table: 8 rows, all columns, hover states
- [ ] Global filter bar: date, platform, cluster
- [ ] All animations smooth and non-janky
- [ ] All brand logos via Google Favicon API
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds