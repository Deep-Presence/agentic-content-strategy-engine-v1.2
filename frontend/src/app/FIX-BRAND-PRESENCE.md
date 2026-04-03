# Fix — Brand Presence Page: Polish & Drill-Down

> **Read CLAUDE.md and brand-system.md first.** This fixes the existing Brand Presence page at `/`. Do NOT rebuild — patch and improve what exists.

---

## FIX 1: Chart — Make It Feel Premium

The current chart is too thin and basic. It needs to feel like a Robinhood portfolio chart.

**Gradient fill:** The area below the line MUST have a smooth gradient fill. Use an SVG `<linearGradient>` — top at 25% opacity of the line color, bottom at 2% opacity. This creates the signature "filled area" look. If using Recharts `<Area>`, set `fill="url(#gradient)"` with a proper `<defs>` gradient. If using custom SVG, ensure the gradient is present.

**Line smoothness:** Use `type="monotone"` on Recharts Area/Line, or cubic bezier control points on custom SVG paths. The line should curve smoothly, never angular.

**Line weight:** 2.5px stroke width. Not 1px, not 3px. 2.5px is the Robinhood sweet spot.

**Chart height:** Increase to at least 280px. The current chart is too short — it should be the visual centerpiece of the page.

**Hover crosshair:** The vertical dashed line on hover should be subtle — 0.5px width, `var(--text-secondary)` color, `strokeDasharray="4 4"`. The dot on the line should be 6px radius, filled with the line color, with a 2px white (or bg-colored) stroke to make it pop.

**X-axis labels:** Show 5 evenly spaced dates. Font: 11px, var(--text-secondary). No Y-axis labels — the hero number serves as the Y value.

**Chart container:** `1px solid var(--border)`, 8px border-radius, 16px padding. NO background color — just the border framing the chart against the page background.

---

## FIX 2: Hero Number — Tighter Connection to Chart

The hero number should feel physically connected to the chart, not floating in space.

**Reduce gap between hero number and chart** — max 12px between the delta text and the view toggles, max 8px between view toggles and chart top edge. The number→toggles→chart should feel like one unified component.

**Hero number size:** 56px JetBrains Mono, font-weight 700. Not larger. The current 58px-ish is fine but make sure it's exactly consistent.

**Delta styling:** The "+11 this month" should be 14px, green for positive, red for negative. Add a small up/down SVG arrow icon (not text arrow) before the number.

**On hover:** The hero number transition should be instant (no CSS transition on the number itself — transitions cause lag). The date text that replaces the delta should be the same 14px, var(--text-secondary).

**"?" info icon** next to "Presence Score": On hover/click, show a tooltip explaining the formula: "Presence Score combines Share of Voice (35%), Citation Rate (25%), Average Position (20%), Sentiment (10%), and Platform Coverage (10%) into a single 0-100 metric." Use a small (14px) circle with "?" in it, var(--text-secondary).

---

## FIX 3: Leaderboard Data — Fix Mismatch

The leaderboard currently shows percentage values (17.7%, 12.8%) even when "Presence Score" is selected. This is wrong.

**When Presence Score is selected:** Leaderboard should show scores (0-100) for each competitor. Calculate a rough presence score for competitors using the same formula. Title: "PRESENCE SCORE RANKING".

**When Share of Voice is selected:** Show SOV percentages. Title: "SHARE OF VOICE RANKING".

**When Citations is selected:** Show citation counts. Title: "CITATION COUNT RANKING".

**When Mentions is selected:** Show mention counts. Title: "MENTION COUNT RANKING".

**When Avg Position is selected:** Show position values (lower is better). Title: "POSITION RANKING". Sort ascending (position 1.2 ranks above 2.3).

The leaderboard title and values MUST match the active view toggle.

---

## FIX 4: Insight Cards — Add Drill-Down Interactions

Each insight card must be interactive. Currently they look static.

**Cited vs Mentioned card:**
- Click the card → chart switches to show two overlaid lines (cited % trend + mentioned % trend). View toggle highlights "Citations".
- The "20% gap — 10 queries mention without citing" text should be clickable → opens a slide-in panel (right side, 400px) listing the 10 specific queries with their mention vs citation status across each platform.
- Active state: card gets `border-top: 2px solid var(--purple)`, subtle purple background tint.

**Platform Breakdown card:**
- Each platform row is clickable → click "ChatGPT" and the chart filters to show ChatGPT-only citation data. The leaderboard updates to show ChatGPT-specific rankings.
- Active platform gets highlighted row (platform color tint).
- Click again to deselect (return to all platforms).

**Top Cited Content card:**
- Each URL row is clickable → navigates to Citation Intelligence page with that URL's detail drawer open. OR opens an inline slide-in panel showing: citation trend for that URL, which platforms cite it, which queries reference it, citation velocity.
- The citation count should be clickable with hover underline.

**Citation Sentiment card:**
- Click the card → chart switches to show sentiment trend over time (positive % as green area, neutral as gray, negative as red area, stacked).
- Below the bars, the text "Overwhelmingly positive. Negative around pricing." should be more specific: "76% of citations are positive recommendations. Negative mentions primarily around pricing transparency and enterprise tier costs."

**Visual feedback on all cards:**
- Hover: border lightens, subtle shadow or background shift, 150ms transition
- Active (affecting chart): `border-top: 2px solid {accent color}`, tinted background, card title color changes to accent
- Cursor: pointer on all cards

---

## FIX 5: Platform Intelligence — Add Drill-Down

Each platform card should be clickable. On click, open a **slide-in detail panel** (right side, 50% width) showing:

```
ChatGPT — Detailed Intelligence
─────────────────────────────────
274 citations · 36.1% SOV · Avg Rank 2.2 · 78% Coverage

Citation trend chart (sparkline expanded to full chart, 30 days)

Top queries on this platform:
  "AI app builder comparison"     cited 14 times
  "lovable vs cursor"             cited 9 times
  "best no-code builder"          cited 7 times

Top cited URLs on this platform:
  /blog/ai-app-builder-comparison     23 citations
  /blog/lovable-vs-cursor             12 citations

Competitor performance on this platform:
  1. bolt.new    42.3%
  2. You         36.1%
  3. cursor.com  28.4%

Strengths: Best reach (36.8%), highest total citations
Weaknesses: Low coverage in security queries, inconsistent ranking for enterprise topics
```

This panel slides in with `slideRight 200ms ease`. Close button returns to the main view.

---

## FIX 6: Citation URLs Table — Add Row Drill-Down

Each row in the Citation URLs table should be clickable. On click, open a **side drawer** (right side, 50% width) showing:

```
lovable.dev/blog/ai-app-builder-comparison
AI App Builder Comparison Guide
─────────────────────────────────
63 citations · CPS 0.713 · Velocity 4.8 · First cited Jan 14, 2026

Citation trend (30-day line chart)

Platform breakdown:
  ChatGPT    23 citations    [████████]
  Claude     15 citations    [████]
  Perplexity 14 citations    [████]
  Google AI  11 citations    [███]

Queries that cite this URL (8):
  "AI app builder comparison"         ChatGPT, Claude, Perplexity
  "best AI app builder 2026"          ChatGPT, Google AI
  "lovable vs bolt.new vs cursor"     Claude, Perplexity
  ...

Content signals:
  Word count: 3,200 · Headers: 14 · FAQ sections: 2 · Tables: 3
```

---

## FIX 7: Font Sizes — Match Other Pages

Compare with Citation Intelligence (screenshot 4) and ensure consistency:

```
Page title: 22px font-weight 600 (match Citation Intelligence)
Page subtitle: 13px var(--text-secondary)
Hero number: 56px JetBrains Mono font-weight 700
Hero delta: 14px
View toggle text: 13px (active: font-weight 600 + color, inactive: font-weight 400 + muted)
Time range buttons: 12px
Chart x-axis labels: 11px
Leaderboard title: 10px uppercase
Leaderboard names: 13px
Leaderboard values: 14px JetBrains Mono font-weight 600
Insight card titles: 11px uppercase
Insight card values: 22px JetBrains Mono font-weight 700
Insight card body text: 12px
Platform card names: 13px font-weight 600
Platform card citation numbers: 26px JetBrains Mono font-weight 700
Platform card metric labels: 12px
Platform card metric values: 13px JetBrains Mono
Platform card insight text: 11px
Citation URLs table headers: 11px uppercase
Citation URLs table body: 13px
Section headers ("Platform Intelligence", "Citation URLs"): 16px font-weight 600
```

Go through EVERY text element and ensure it matches. If anything is smaller than 11px, increase it.

---

## FIX 8: Global Filter Bar — Make It Prominent

The date filter is too subtle. Standardize across all pages:

**Filter bar height:** 44px. Full width. `border-bottom: 1px solid var(--border)`. No background color.

**Date selector:** Should be clearly clickable — show the calendar icon (📅) + date range text at 13px font-weight 500. On hover: text turns accent color. On click: opens two-month calendar popup.

**Platform and Cluster filters:** 13px, dropdown style with subtle border. Clear visual separation (vertical dividers, 1px, 16px height) between each filter.

**Make the filter bar feel like it belongs** — right now it looks like an afterthought. It should be the second most prominent element after the hero number.

---

## FIX 9: Sidebar — Add Logo + Workspace

Restructure the top of the sidebar:

```
┌─────────────────────┐
│ [DP logo]  Deep      │  ← product logo (20px icon) + "Deep Presence" (14px font-weight 600)
│            Presence   │     or just the logo + abbreviated name
│                      │
│ [🏢] Insight Health ▾│  ← workspace selector (13px, dropdown)
├─────────────────────┤
│                      │
│ Brand Presence       │  ← top nav item, 16px below the divider
│                      │
│ INTELLIGENCE         │
│   Citation intelli...│
│   Competitive pos... │
│   Prompt tracking    │
│                      │
│ SIGNALS              │
│   ...                │
```

**Logo:** Use a simple icon or the "DP" monogram. 20px × 20px, accent color. If no logo asset exists, create a simple SVG: rounded square with "DP" text inside.

**Workspace selector:** Shows current workspace name with a dropdown chevron. 13px. On click: dropdown showing available workspaces (for now, just "Insight Health" with a checkmark).

**Divider:** 1px horizontal line below the workspace selector, `var(--border)` color, with 12px vertical padding above and below.

**Brand Presence positioning:** Move it 16px below the divider. It's currently too tight against the top of the sidebar.

---

## FIX 10: Insight Cards — Tighten Layout

The four insight cards should feel like a unified strip, not four separate floating boxes.

**Equal heights:** All four cards must be the same height. Use `align-items: stretch` on the grid container.

**Remove gap between chart and cards:** The insight cards should sit directly below the chart+leaderboard section with only 12px gap. They're contextual controls for the chart, not a separate section.

**Card internal spacing:** 12px padding. Title at top, content below, no excessive vertical gaps inside the card.

---

## Verification

1. Chart has gradient fill below the line
2. Chart line is smooth (monotone/bezier), 2.5px weight
3. Chart height is at least 280px
4. Hero number updates on hover (verify it's working, not just built)
5. Leaderboard values match the active view toggle
6. Leaderboard title changes with view toggle
7. All 4 insight cards have hover states and are clickable
8. Clicking "Cited vs Mentioned" changes the chart view
9. Platform Breakdown rows are individually clickable
10. Top Cited Content rows are clickable
11. Platform Intelligence cards open detail panel on click
12. Citation URLs rows open side drawer on click
13. Font sizes match the spec above — nothing below 11px
14. Global filter bar is 44px, prominent, with 13px text
15. Sidebar has logo + workspace selector + proper spacing
16. `npm run build` succeeds