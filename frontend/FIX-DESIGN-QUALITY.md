# PLATFORM DESIGN FIX — Page by Page, Section by Section

> **Read CLAUDE.md and brand-system.md first.**
> This file fixes specific visual problems on specific pages. Every instruction references an exact section.
> Work through pages in order: Brand Summary → Citation Intelligence → Competitive Position.
> After each page, run `npm run dev` and visually verify before moving to the next page.

---

# PAGE 1: BRAND SUMMARY (route: `/`)

## 1.1 — Page Title Area

**Current:** "Brand Summary" at 22px with subtitle below. A breadcrumb "Brand Presence" appears in the top bar above.
**Fix:** The top bar says "Brand Presence" but the page says "Brand Summary." Find the breadcrumb/top-bar component and rename it to "Brand Summary" to match the page title. Increase page title to 26px.

## 1.2 — KPI Strip (4 cards: SOV, Avg Position, Total Citations, Content Velocity)

**Current:** The 4 cards show navigation hints like "→ Competitive Position" as text at the bottom.
**Fix on each card:**
- Remove the text "→ Competitive Position" / "→ Citation Intelligence" etc from the bottom of each card
- Add a 12px lucide-react `ChevronRight` icon in the top-right corner of the card, color `var(--text-muted)`
- On card hover: border changes to `var(--accent)`, background shifts to `var(--hover)`, chevron turns accent-colored, card moves `translateY(-1px)` with `transition: all 150ms`
- Entire card wrapped in Next.js `<Link>` — clicking anywhere navigates
- Increase main value font from 28px to 32px
- Delta line ("+5.1 this period"): replace text character "↑" with lucide `TrendingUp` icon (12px green) or `TrendingDown` (12px red)

## 1.3 — Presence Score Hero Section

**Current:** Shows "58 Presence Score +11 this month" with trajectory below, then view toggles.
**Fix:**
- Increase "58" to **56px** JetBrains Mono font-weight 700 — this is THE number on the page, it must dominate
- "+11" delta: increase to 18px JetBrains Mono green (currently too small)
- Trajectory "45 Jan → 52 Feb → 58 Mar → 74 Apr": replace text "→" arrows with 10px lucide `ChevronRight` icons in `var(--text-muted)`. Each month: score in 16px JetBrains Mono font-weight 600, month label in 11px var(--text-secondary) below the score. Horizontal layout.
- "Gaining 7.2 points per month on average": move below trajectory, 12px green text
- "˅ Breakdown" button top-right: add `border: 1px solid var(--border)`, `padding: 4px 10px`, `border-radius: 4px`. On hover: accent border

## 1.4 — Chart Hover Behavior

**Current:** Hovering shows just "50 Mar 4" — bare number and date, no context.
**Fix:** On hover show:
- The hovered value at 56px (same size as default hero)
- Date below in 13px var(--text-secondary): "Mar 4, 2026"
- Delta from current: "(−8 from current)" in 12px, red if lower, green if higher
- When NOT hovering: revert to current value with "+11 this month" delta
- Transitions: instant (no animation delay on number changes)

## 1.5 — Leaderboard (Right Side of Chart)

**Current:** Shows "PRESENCE SCORE RANKING" with "1 [favicon] Bolt.new 77". Having rank number (1) AND score (77) creates confusion.
**Fix — restructure completely:**

Remove rank numbers entirely. Visual order = rank. Each row:
- Favicon (14px) + name (13px) + horizontal bar (4px height, proportional to score) + score (JetBrains Mono 13px font-weight 600)
- Bars: `var(--text-muted)` at 30% opacity for competitors, `var(--accent)` for you
- YOUR row: `background: var(--accent-subtle)`, `border-left: 3px solid var(--accent)`, name in accent color, "YOU" badge (8px text, accent bg, white text)
- Row height: 36px for breathing room
- On chart hover: scores update to that date's values, rankings may reorder with `transition: transform 200ms`
- Header changes with active view: "SOV RANKING" for Share of Voice, "CITATION COUNT RANKING" for Citations, etc.

## 1.6 — Insight Cards (Content Velocity, Platform Breakdown, Top Cited, Sentiment)

**Fix:**
- Add `32px` gap between chart section and these cards
- Add full-width `1px solid var(--border)` divider with 24px margin above and below
- **Platform Breakdown card:** horizontal bars are too short — the bar container should use `flex: 1` to span full available width
- **Citation Sentiment card:** minimum bar width of 20px so even 5% Negative is visible

## 1.7 — Platform Intelligence Section

**Fix:**
- Add full-width divider before this section
- Increase padding inside each card from 12px to 16px
- "TOP" badge on ChatGPT: `background: #10A37F`, white text, top-right of header

## 1.8 — Platform Detail Drawer (ChatGPT/Claude/etc)

**Current:** Extremely sparse — just 4 stat boxes, a 7-day list of numbers, and 2 bullet points.
**Fix — restructure completely to match the Citation Intelligence platform drawer depth:**

**Drawer header:**
```
[favicon 20px] ChatGPT — Detailed Intelligence
274 citations across 12 tracked queries
ChatGPT is your strongest platform — 36.8% of all citations come from here.
```
Title 18px font-weight 600, subtitle 12px, narrative 13px var(--text-secondary)

**Stat strip (single horizontal line, not separate boxes):**
```
274 citations · 36.1% SOV · #2.1 avg rank · 78% coverage
```
13px, JetBrains Mono for values, middle dots between items

**Citation trend:** Recharts AreaChart, 140px height, platform color fill with gradient, 28 days, 4-5 date labels. Replaces the wasteful "Daily Citations (Last 7 Days)" list.

**Two-column summary card:**
```
WHAT'S WORKING                         WHERE TO IMPROVE
✓ Best reach — 36.8% of citations      ✗ Low security query coverage
✓ Strong branded query ranking          ✗ Not citing your API docs
✓ 78% coverage of tracked queries      ✗ No FAQ sections on cited pages
```
Two columns, bordered card, green left / amber-red right, 12px text

**Top queries on this platform (table):**
```
"AI app builder comparison"       14 citations    You: #1
"lovable vs cursor"                9 citations    You: #2
"enterprise AI app builder"        5 citations    Not cited ✗
```
Query 13px, citations JetBrains Mono 12px, rank green or "Not cited ✗" red. Top 5-8 queries.

**Top cited URLs on this platform:**
```
/blog/ai-app-builder-comparison      23 citations
/blog/lovable-vs-cursor              12 citations
```
URL 12px accent, citations JetBrains Mono 12px. Top 3-5.

**Structural preferences:**
```
WHAT CHATGPT PREFERS
FAQ sections:       72% of cited content    You: 20% ✗
Word count:         avg 2,200 words         You: 1,800 ⚠
Comparison tables:  65% of cited content    You: 30% ✗
External citations: 84% of cited content    You: 78% ✓

Your score for ChatGPT: 45/100
```
Signal 12px, preference 12px, your score 12px colored. Overall score 18px JetBrains Mono accent.

---

# PAGE 2: CITATION INTELLIGENCE (route: `/analytics`)

## 2.1 — KPI Strip

**Fix:**
- Total Citations "847": increase to 36px, add `border-left: 3px solid var(--accent)`
- **Delete ALL description lines** under KPI values: "across 5 engines", "of mentions that include a link", "mention without citing", "when cited, your rank" — all gone. Labels are self-explanatory.
- Keep only delta lines ("+124 this period", "↑ from 52%")
- Replace text "↑" arrows with lucide `TrendingUp`/`TrendingDown` icons (12px)
- "11 queries" in Mention-to-Cite Gap card: make clickable (underline, accent color), opens uncited queries drawer

## 2.2 — Citation Momentum Chart

**Chart:** Stacked bars look good. Keep.
**SOV overlay line:** Reduce opacity to 0.25, line width to 1px (currently fights with bars).
**Event markers below chart:** Max 3 events shown. Each on its own line: `[6px dot] Mar 5 Published: Vibe Coding Guide`. 12px text, 8px vertical gap between events.

## 2.3 — Competitor Leaderboard (right of chart)

**Fix — remove sparklines, remove rank numbers:**
- Delete sparkline graphs entirely — they convey nothing at that size
- Remove rank numbers (1,2,3) — visual order = rank
- Each row: favicon (14px) + domain (13px) + SOV (JetBrains Mono 13px font-weight 600) + citation count (JetBrains Mono 12px var(--text-secondary)) + delta with lucide `TrendingUp`/`TrendingDown` icon (12px colored)
- YOUR row: accent-subtle bg, 3px accent left border, "YOU" badge
- Row height: 36px

## 2.4 — Visibility Pipeline

**Fix (minor):**
- Add 32px gap and divider above
- Replace "→" in "View 11 queries that mention without citing →" with lucide `ChevronDown` (12px) that rotates on expand

## 2.5 — "How AI Engines Talk About You"

**Fix:**
- Remove italic styling from descriptions. Change to: 11px var(--text-secondary), normal weight, no quotation marks, no em-dash formatting. Plain text like: `AI engines actively recommend your product`
- Sentiment trend chart: reduce height to 80px (secondary information)
- Summary paragraph: wrap in card with `background: var(--surface)`, `1px solid var(--border)`, `14px padding`

## 2.6 — Platform Intelligence Grid

**Fix:**
- Add 32px gap and divider above
- On card click: open the detailed drawer (this already works well from screenshot 9 — the Claude drawer has citation trend, top queries, URLs, structural preferences, and overall score)
- **Copy this drawer implementation to Brand Summary's platform cards** — Brand Summary currently shows the sparse version

## 2.7 — Citation URLs Table

**Fix:**
- Add 32px gap and divider above
- Platforms column: replace 14px engine favicons with 6px colored dots (engine brand colors). Filled = cited, hollow = not cited. More scannable.
- Sort icon: replace text "↓" with lucide `ArrowDown` SVG (12px)

---

# PAGE 3: COMPETITIVE POSITION (route: `/competitive-position`)

## 3.1 — KPI Strip

**Fix:**
- Growth direction "+3.2 points this month": increase to 13px
- Win Rate amber color: use stronger `#D97706` instead of `#F5A623`

## 3.2 — Position Narrative Card

**Current is excellent.** Keep exactly as-is.

## 3.3 — Head-to-Head Chart

**Fix:**
- Your line: increase to 3px width. Competitor lines: 1.5px at 0.6 opacity. Your line must visually dominate.
- Event markers: max 3 events, each on own line with 8px gap

## 3.4 — Win Rate Section

**Fix:**
- Add 32px gap and divider above
- One-line interpretations: reduce to 10px `var(--text-muted)` (should be more subtle than bar labels)

## 3.5 — Where You're Winning and Losing

**Current is one of the best sections on the platform.** Keep structure.
**Fix:**
- "WHITE SPACE" badge: increase to 11px, `background: var(--red)`, white text, font-weight 700
- "Enter this territory →" button: remove "→", add lucide `ArrowRight` icon (12px). Style: accent outline button. On hover: `background: var(--accent-subtle)`

## 3.6 — Cluster Detail Drawer

**Current is well-structured.**
**Fix:**
- "Recommended Strategy" card: increase padding to 16px, text to 13px
- Gap scores (e.g., "Gap: 26.7%"): style as `color: var(--red); font-family: 'JetBrains Mono'; font-weight: 600`

## 3.7 — Citations at Risk

**Fix:**
- Add 32px gap and divider above
- "Defend →" buttons: remove "→", add lucide `Shield` icon (12px) before "Defend"
- "Create content →" buttons: remove "→", add lucide `Plus` icon (12px) before "Create"

## 3.8 — Who's Taking Your Citations

**Fix:**
- Verify Mind Share and Authority tiers exist below Direct Competitors. If missing, add from agent spec.
- Below Authority tier: add insight card — `background: var(--surface)`, `border-left: 3px solid var(--accent)`, 14px padding, 13px text explaining to focus on how-to content not reference material.

---

# GLOBAL FIXES (ALL pages)

## G.1 — Section Dividers

Add `1px solid var(--border)` full-width line between major sections. 24px margin above and below.

Sections to separate:
- **Brand Summary:** KPIs | Chart+Leaderboard | Insight Cards | Platform Intelligence
- **Citation Intelligence:** KPIs | Chart+Leaderboard | Visibility Pipeline | Sentiment | Platform Intelligence | Citation URLs
- **Competitive Position:** KPIs | Narrative+Chart | Win Rate | Winning/Losing | Citations at Risk | Who's Taking

## G.2 — Delete Redundant Subtitles

These subtitles restate the header. Delete them:
- "When competing for the same query, how often are you cited instead?" → DELETE
- "Your position in each topic cluster" → DELETE
- "Sentiment breakdown of how your brand is referenced across AI platforms" → DELETE
- "Daily citation volume by platform with SOV trend" → DELETE
- "Every URL cited by AI platforms, ranked by citation count" → SHORTEN to "Ranked by citation count"

## G.3 — Color Intensity

In CSS variables, increase subtle backgrounds:
```css
--accent-subtle: rgba(108, 184, 210, 0.12);  /* from 0.08 */
--green-subtle: rgba(52, 178, 123, 0.12);
--amber-subtle: rgba(245, 166, 35, 0.12);
--red-subtle: rgba(229, 72, 77, 0.12);
--purple-subtle: rgba(157, 140, 224, 0.12);
```

Ensure status colors use full values: green `#34B27B`, amber `#D97706`, red `#E5484D`.

## G.4 — Tooltip Styling (all charts)

```css
background: #1e1e1e;
border: 1px solid #333;
border-radius: 6px;
padding: 10px 14px;
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
font-size: 12px;
max-width: 260px;
```

## G.5 — Interactive Card Hover States

Every clickable card:
```css
cursor: pointer;
transition: all 150ms ease;
```
On hover:
```css
border-color: rgba(108, 184, 210, 0.4);
background: var(--hover);
transform: translateY(-1px);
```

## G.6 — Replace ALL Text Arrows

Search entire codebase for text arrow characters: `→`, `←`, `↑`, `↓`, `▾`, `▸`, `▼`, `▲`
Replace every instance with the corresponding lucide-react SVG icon:
- `→` in buttons → lucide `ArrowRight` or `ChevronRight` (12px)
- `↑`/`↓` in deltas → lucide `TrendingUp`/`TrendingDown` (12px)
- `▾` in dropdowns → lucide `ChevronDown` (12px)
- `▸`/`▾` in expand/collapse → lucide `ChevronRight` that rotates 90° on expand

---

# VERIFICATION

```bash
npm run dev
npx tsc --noEmit
npm run build
```

**Brand Summary:**
- [ ] Presence Score 56px dominates page
- [ ] Leaderboard: no rank numbers, has mini bars, no confusion
- [ ] Chart hover shows value + date + delta from current
- [ ] KPI cards: chevron icon top-right, no text navigation hints, full-card click
- [ ] Trajectory: SVG chevrons between numbers, not text arrows
- [ ] Platform drawer: narrative + stat strip + chart + two-column summary + queries + URLs + preferences + score
- [ ] Top bar breadcrumb says "Brand Summary" not "Brand Presence"
- [ ] Section dividers between all major sections

**Citation Intelligence:**
- [ ] Total Citations 36px with accent left border
- [ ] All KPI description lines deleted
- [ ] Leaderboard: no sparklines, no rank numbers
- [ ] SOV line at 0.25 opacity
- [ ] Sentiment descriptions NOT italic, plain 11px text
- [ ] Section dividers between all sections
- [ ] Redundant subtitles deleted

**Competitive Position:**
- [ ] Your chart line 3px, competitors 1.5px at 0.6 opacity
- [ ] Win rate interpretations at 10px text-muted
- [ ] WHITE SPACE badges prominent red
- [ ] All buttons use lucide icons not text arrows
- [ ] Section dividers between all sections

**Global:**
- [ ] 32px gaps + dividers between all major sections
- [ ] Color subtle backgrounds at 0.12
- [ ] All tooltips have consistent styling with shadow
- [ ] All clickable cards have translateY(-1px) hover
- [ ] Zero text arrow characters anywhere in codebase
- [ ] `npm run build` succeeds