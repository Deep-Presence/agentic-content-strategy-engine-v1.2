# Agent — Brand Presence Page (REBUILD)

> **Read CLAUDE.md and brand-system.md first, then this file.**
> **DELETE everything at the home route and rebuild from scratch.**
> This page MUST visually match Citation Intelligence in density, font sizes, spacing, and component patterns. Open `/analytics` (Citation Intelligence) in another tab and use it as your visual reference while building.

---

## Mission

Build the Brand Presence page at `/` (home route). This is the executive overview — the first page a user sees. It shows a proprietary Presence Score (0-100) with an interactive chart, competitive leaderboard, insight cards, platform intelligence, and citation URLs.

**DELETE** whatever currently exists at the home route. Full rebuild.

---

## CRITICAL RULE: Match Citation Intelligence Visually

Open the Citation Intelligence page (`/analytics`) and study it. Your Brand Presence page MUST match:
- Same KPI card sizing and spacing
- Same font sizes for ALL equivalent elements
- Same card border style (1px solid, same border color)
- Same section gap (16px between sections)
- Same page padding (24px horizontal)
- Same filter bar height and styling
- Same table styling for Citation URLs

If you build something and it doesn't look like it belongs on the same platform as Citation Intelligence, you've failed. Check your work against `/analytics` before committing.

---

## FILES

```
src/app/(dashboard)/page.tsx
src/app/(dashboard)/_components/brand-presence/
```

Also modify the sidebar component to add the Deep Presence logo and workspace selector.

---

## SIDEBAR MODIFICATIONS

### Add Logo + Workspace Selector

Find the sidebar component. Add these elements AT THE VERY TOP, before any navigation items:

```tsx
{/* Logo */}
<div style={{ padding: "16px 16px 8px", display: "flex", alignItems: "center", gap: 8 }}>
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="var(--accent)" />
    <text x="12" y="16" textAnchor="middle" fill="#fff" fontSize="11" fontWeight="700" fontFamily="JetBrains Mono">DP</text>
  </svg>
  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>Deep Presence</span>
</div>

{/* Workspace selector */}
<div style={{ padding: "0 16px 12px" }}>
  <button style={{
    display: "flex", alignItems: "center", gap: 6, width: "100%",
    padding: "6px 10px", borderRadius: 6,
    border: "1px solid var(--border)", background: "var(--surface)",
    color: "var(--text-primary)", fontSize: 13, cursor: "pointer",
  }}>
    <img src="https://www.google.com/s2/favicons?domain=insighthealth.com&sz=28" width={14} height={14} style={{ borderRadius: 2 }} />
    <span style={{ flex: 1, textAlign: "left" }}>Insight Health</span>
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 5l3 3 3-3" stroke="var(--text-secondary)" strokeWidth="1.5" /></svg>
  </button>
</div>

{/* Divider */}
<div style={{ height: 1, background: "var(--border)", margin: "0 16px 12px" }} />
```

Then "Brand Presence" nav item below the divider.

### Remove 1W/1M/3M/6M Time Range Toggles

The global date filter in the filter bar handles date ranges. Remove the time range toggle buttons from the chart area entirely. The chart ALWAYS shows the date range selected in the global filter.

---

## PAGE LAYOUT (Top to Bottom)

### 1. Page Header

```
Brand Presence
Your brand's visibility and authority across AI engines
```

Title: 22px font-weight 600. Subtitle: 13px var(--text-secondary). Same as Citation Intelligence header.

### 2. Global Filter Bar

**Copy the exact filter bar pattern from Citation Intelligence.** Same height (44px), same styling, same border.

```
📅 Mar 1, 2026 – Mar 28, 2026  |  All Platforms ▾  |  All Clusters ▾
```

- Height: 44px
- Full width
- `border: 1px solid var(--border)`, border-radius matching Citation Intelligence
- Date text: 13px font-weight 500, with calendar icon
- Filter dropdowns: 13px, with chevron
- Vertical dividers between filters: 1px, 16px height, var(--border)
- NO background color (transparent)
- This filter bar MUST look identical to Citation Intelligence's filter bar

### 3. KPI Strip (4 Cards)

**Match the KPI strip from Citation Intelligence exactly** — same card height, same padding, same font sizes.

```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ PRESENCE SCORE   │ SHARE OF VOICE  │ CITATION RATE   │ AVG POSITION    │
│ 58               │ 12.4%           │ 67%             │ 2.3             │
│ +11 this month   │ ↑ from 8.1%     │ ↑ from 52%      │ ↑ from 3.1      │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

Each card:
- `1px solid var(--border)`, border-radius 6px, padding 16px
- Label: 10px uppercase, letter-spacing 0.05em, var(--text-secondary), font-weight 600
- Value: 28px JetBrains Mono font-weight 700, var(--text-primary)
- Delta: 12px, green if positive, red if negative. Use small SVG up/down arrow before the text (NOT text arrows like ↑)

The Presence Score card should have a subtle accent left border (2px solid var(--accent)) to distinguish it as the primary metric.

**Clicking any KPI card changes the chart below to show that metric's trend.** Active card gets a subtle tinted background (var(--accent-subtle) for Presence Score, etc).

### 4. Chart + Competitive Leaderboard (Side by Side)

**Use the same dual-layout as Citation Intelligence** — chart on left (flex: 1), leaderboard on right (fixed width).

`display: grid; grid-template-columns: 1fr 280px; gap: 16px;`

#### Chart (Left)

Use Recharts (already in the project). Build a `ComposedChart` with:

- **Area** component: smooth monotone curve, gradient fill below the line
  - Gradient: `<linearGradient>` from accent color at 20% opacity (top) to 2% opacity (bottom)
  - Line: 2.5px stroke width, accent color, `type="monotone"`
- **CartesianGrid**: horizontal only, `strokeDasharray="3 3"`, var(--border) color, 0.3 opacity
- **XAxis**: 5 tick marks, 11px font, var(--text-secondary)
- **YAxis**: hidden (the KPI card above serves as the current value)
- **Tooltip**: custom tooltip that updates the HERO DISPLAY above the chart
- **ResponsiveContainer**: width 100%, height 300px

**Hero display above the chart:**

Between the KPI strip and the chart, show a live-updating display:

```
58                              Presence Score
```

Left: the current value at 48px JetBrains Mono font-weight 700. Right: the metric name at 14px var(--text-secondary).

**On chart hover:** The 48px number updates to show the value at the hovered date. The metric name changes to show the date. When hover ends, reverts to current value.

This hero display is INSIDE the chart container (above the Recharts chart), not floating separately on the page.

**View toggles:** Small pills INSIDE the chart container, above the chart area:

```
[Presence Score]  [Share of Voice]  [Citations]  [Mentions]  [Avg Position]
```

12px text. Active: accent color text + accent-subtle background. Inactive: var(--text-secondary).

Clicking a toggle changes:
- The Area chart data
- The hero display value and label
- The leaderboard values and title
- The active KPI card highlight

**Competitor ghost lines** (SOV view only): dashed lines, 1px, 0.3 opacity, for each competitor. Toggle button below chart: "Show competitors" / "Hide competitors".

#### Leaderboard (Right, 280px)

**Match the Competitor Leaderboard from Citation Intelligence exactly.** Same card style, same row height, same font sizes.

```
PRESENCE SCORE RANKING                    ← 10px uppercase, var(--text-secondary)

1  [favicon] Bolt.new          77         ← rank: 11px mono, name: 13px, value: 14px mono bold
2  [favicon] Cursor             71
3  [favicon] Lovable    YOU    58         ← highlighted row: accent bg, accent left border
4  [favicon] V0.dev            57
5  [favicon] Replit            56
6  [favicon] Emergent          43
```

**YOUR row:** accent-subtle background, 2px accent left border, name in accent color. "YOU" badge: 9px, accent background, white text, 2px border-radius.

**On chart hover:** Leaderboard values update to show that date's data. If rankings shift, animate the reorder (CSS transition on transform).

**Leaderboard title and values MUST match the active view:**
- Presence Score → integer scores (0-100), title "PRESENCE SCORE RANKING"
- Share of Voice → percentages, title "SHARE OF VOICE RANKING"
- Citations → counts, title "CITATION COUNT RANKING"
- Mentions → counts, title "MENTION COUNT RANKING"
- Avg Position → position values (sort ascending, lower = better), title "POSITION RANKING"

### 5. Insight Cards (4 Cards)

`display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;`

Gap between chart section and insight cards: 16px.

Each card: `1px solid var(--border)`, 6px border-radius, 14px padding, var(--surface) background.

**EVERY card is clickable.** On hover: border color lightens, background shifts to var(--hover). Active state (when affecting chart): `border-top: 2px solid {color}`, tinted background.

#### Card 1: Cited vs Mentioned

```
CITED VS MENTIONED                  ← 10px uppercase, var(--text-secondary)

40%    60%                          ← 24px JetBrains Mono font-weight 700
Cited  Mentioned                    ← 11px var(--text-secondary)

[amber block] 20% gap — 10 queries  ← amber-subtle bg, amber text, 11px
mention without citing
```

Click → chart switches to overlay Citations trend + Mentions trend. Click the "20% gap" block → opens slide-in drawer listing the 10 queries.

#### Card 2: Platform Breakdown

```
PLATFORM BREAKDOWN

[chatgpt favicon] ChatGPT    ██████████  36.1%
[claude favicon]  Claude      ██████      21.2%
[perplexity fav]  Perplexity  █████       18.5%
[google favicon]  Google AI   ████        13.3%
[gemini favicon]  Gemini      ███         10.8%
```

Each row: favicon 14px + name 12px + horizontal bar (6px height, platform color) + percentage (JetBrains Mono 12px). Click a platform → chart filters to that platform's data.

#### Card 3: Top Cited Content

```
TOP CITED CONTENT

#1  AI App Builder Comparison Guide     63
#2  Lovable vs Cursor: Honest Review    38
#3  Vibe Coding for Enterprise Teams    31
```

Rank: 10px mono dim. Title: 12px, truncated. Count: JetBrains Mono 13px green font-weight 600. Click a row → opens slide-in drawer with URL detail.

#### Card 4: Citation Sentiment

```
CITATION SENTIMENT

Positive  ████████████████████  76%
Neutral   █████                 19%
Negative  ██                     5%

Overwhelmingly positive. Negative around pricing.
```

Bars: 5px height, green/gray/red. Labels: 11px. Percentages: JetBrains Mono 12px. Click → chart shows sentiment trend.

### 6. Platform Intelligence Grid

Section header: "Platform Intelligence" — 16px font-weight 600, 24px top margin.

`display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px;`

**Match the existing Platform Intelligence cards from the current build** — they look decent. Keep the same structure:

Each card: `1px solid var(--border)`, 6px border-radius, 14px padding.

```
[favicon] ChatGPT    TOP              ← 13px font-weight 600
274                                   ← 26px JetBrains Mono font-weight 700
citations                             ← 11px var(--text-secondary)

SOV           36.1%                   ← 12px label + 13px mono value
Avg Rank      2.1
Coverage      78%
Sentiment     Positive

[sparkline]                           ← 28px height, platform color

✓ Best reach (36.8%)                  ← 11px green
✗ Low security coverage               ← 11px amber
```

Top platform: `border-top: 2px solid {platform color}`, "TOP" badge in platform color.

**Click any platform card → opens a slide-in drawer** (50% width, slides from right) with detailed platform intelligence: expanded citation trend, top queries on that platform, top URLs, competitor performance, strengths/weaknesses.

### 7. Citation URLs Table

Section header: "Citation URLs" — 16px font-weight 600. Subtitle: "Every URL cited by AI platforms, ranked by citation count" — 12px var(--text-secondary).

**Match Citation Intelligence's URL table exactly** — same column widths, same font sizes, same hover states.

Table: `1px solid var(--border)`, 6px border-radius, overflow hidden.

Header row: var(--surface) background, 11px uppercase headers, var(--text-secondary).

```
URL             TITLE              CITATIONS ↓   PLATFORMS   CPS      VELOCITY
```

Body rows: 13px text, 48px row height, `border-bottom: 1px solid var(--border)`. Hover: var(--hover) background.

- URL: 13px accent color, truncated, clickable
- Title: 13px var(--text-primary), truncated
- Citations: 14px JetBrains Mono font-weight 600
- Platforms: small favicons (14px) for each platform that cites this URL
- CPS: JetBrains Mono 13px, color-coded (green >= 0.6, amber >= 0.45, red < 0.45)
- Velocity: JetBrains Mono 13px, green if >= 3.0

**Click any row → opens side drawer** (50% width) with URL detail: citation trend chart, platform breakdown bars, queries that cite this URL, content signals (word count, headers, FAQ, tables).

8 mock URLs, same data as the current build.

---

## SLIDE-IN DRAWER COMPONENT

Build a reusable SlideDrawer component used across the page:

```typescript
interface SlideDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  width?: string; // default "50%"
  children: React.ReactNode;
}
```

- Slides from right with animation: `transform: translateX(100%) → translateX(0)`, 200ms ease
- Backdrop: `rgba(0,0,0,0.2)`, click to close
- Close on Escape key
- Header: title (16px font-weight 600) + subtitle (12px dim) + close button (X)
- Content area: scrollable, 20px padding

---

## MOCK DATA

Generate 28 days of data. Use the EXACT same data structure and trends from the current build — don't change the data, just improve the rendering.

Competitors (same as current):
```
Bolt.new:  SOV 18.5% → 17.1% (declining), Presence Score ~77
Cursor:    SOV 11.5% → 11.8% (stable), Presence Score ~71
Lovable:   SOV 8.1% → 12.4% (growing), Presence Score ~58
V0.dev:    SOV 7.1% → 7.4% (stable), Presence Score ~57
Replit:    SOV 9.5% → 8.8% (declining), Presence Score ~56
Emergent:  SOV 5.0% → 5.3% (growing), Presence Score ~43
```

Presence Score formula:
```
sovScore = min(sov / 25 * 100, 100)
citationRate = citations / (citations + mentions) * 100
positionScore = max(0, (5 - position) / 4 * 100)
sentimentScore = positive%
coverageScore = (platformsWithCitations / 5) * 100

presenceScore = round(
  sovScore * 0.35 +
  citationRate * 0.25 +
  positionScore * 0.20 +
  sentimentScore * 0.10 +
  coverageScore * 0.10
)
```

---

## ANIMATIONS

```css
@keyframes fadeUp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
@keyframes slideInRight { from { transform:translateX(100%); } to { transform:translateX(0); } }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
```

- KPI cards: fadeUp with 40ms stagger
- Insight cards: fadeUp with 50ms stagger
- Platform cards: fadeUp with 50ms stagger
- Table rows: fadeUp with 25ms stagger
- Slide drawer: slideInRight 200ms
- Backdrop: fadeIn 150ms
- All hover transitions: 150ms

---

## VERIFICATION CHECKLIST

Before committing, open Brand Presence and Citation Intelligence side by side. Verify:

```bash
npm run dev
npx tsc --noEmit
```

1. KPI strip: 4 cards, same height/padding/font sizes as Citation Intelligence KPIs
2. Filter bar: 44px, same styling as Citation Intelligence filter bar
3. Chart: Recharts Area with gradient fill, 300px height, smooth monotone curve
4. Hero display: 48px number INSIDE the chart container, updates on hover
5. View toggles: 5 pills inside chart container, switching changes chart + leaderboard + KPI highlight
6. NO 1W/1M/3M/6M buttons anywhere on the page
7. Leaderboard: 280px, matching Competitor Leaderboard from Citation Intelligence
8. Leaderboard title + values match active view toggle
9. Leaderboard updates on chart hover
10. 4 insight cards: all clickable with hover states and active states
11. Cited vs Mentioned: click changes chart, gap block opens drawer
12. Platform Breakdown: each platform row clickable, filters chart
13. Top Content: each row clickable, opens drawer
14. Sentiment: clickable, changes chart to sentiment trend
15. Platform Intelligence: 5 cards with sparklines, each clickable → opens drawer
16. Citation URLs: table with 8 rows, each clickable → opens drawer
17. Slide drawers: slide from right, have backdrop, close on Escape
18. Sidebar: Deep Presence logo SVG + "Deep Presence" text at top
19. Sidebar: Workspace selector below logo (Insight Health with favicon)
20. Sidebar: Divider between workspace and Brand Presence nav item
21. Font sizes: nothing below 11px, all matching the spec above
22. All favicons loading (Google Favicon API, no crossOrigin)
23. All animations smooth
24. Page looks like it belongs on the same platform as Citation Intelligence
25. `npm run build` succeeds
```

---

## COMPLETION CRITERIA

- [ ] Page loads at `/` with no console errors
- [ ] Sidebar has DP logo + workspace selector + divider
- [ ] KPI strip: 4 cards matching Citation Intelligence density
- [ ] Clicking KPI card highlights it and changes chart
- [ ] Filter bar: 44px, matching Citation Intelligence
- [ ] Chart: Recharts Area with gradient, 300px, monotone
- [ ] Hero display inside chart container: 48px, hover-updating
- [ ] View toggles inside chart: 5 options, all working
- [ ] No 1W/1M/3M/6M buttons on the page
- [ ] Leaderboard: 280px, values match active view
- [ ] Leaderboard updates on hover
- [ ] All 4 insight cards clickable with visual feedback
- [ ] Platform Intelligence cards clickable → slide drawer
- [ ] Citation URL rows clickable → slide drawer
- [ ] Slide drawers working (slide animation, backdrop, Escape close)
- [ ] All font sizes match spec
- [ ] Visual consistency with Citation Intelligence
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds
