# Fix — Citation Intelligence Page: Interactive Depth & Visual Intelligence

> **Read CLAUDE.md and brand-system.md first.** This is a targeted enhancement of the existing `/analytics` page. The structure is correct — this fix makes it feel like a $20K/month intelligence briefing instead of a dashboard of metrics.

---

## 1. HERO CHART — Citation Momentum (Major Enhancement)

### A. Click-to-drill tooltips with cause attribution

The current tooltip shows numbers. It needs to show **why** the numbers changed.

Replace the basic Recharts tooltip with a custom tooltip component:

```tsx
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload) return null;
  const total = payload.reduce((sum, p) => sum + (p.value || 0), 0);
  const sov = payload.find(p => p.dataKey === 'sov')?.value;
  
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', padding: '12px', borderRadius: '4px', maxWidth: '280px' }}>
      <div style={{ fontSize: '13px', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: '20px', fontFamily: 'JetBrains Mono', fontWeight: 600, marginTop: '4px' }}>
        {total} citations
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
        SOV: {sov?.toFixed(1)}%
      </div>
      <div style={{ borderTop: '1px solid var(--border)', marginTop: '8px', paddingTop: '8px' }}>
        {payload.filter(p => p.dataKey !== 'sov').map(p => (
          <div key={p.dataKey} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', marginTop: '4px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: p.fill || p.color }} />
              {p.dataKey}
            </span>
            <span style={{ fontFamily: 'JetBrains Mono' }}>{p.value}</span>
          </div>
        ))}
      </div>
      {/* Cause attribution — what drove this day's numbers */}
      <div style={{ borderTop: '1px solid var(--border)', marginTop: '8px', paddingTop: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>
        {/* This is mock — in production, derived from actual events */}
        Click for detailed breakdown →
      </div>
    </div>
  );
};
```

### B. Event milestone markers on the SOV line

Add `ReferenceDot` markers on the SOV line at key event dates. These show **what you did** and **what happened** overlaid on the trend.

```typescript
const CHART_EVENTS = [
  { date: "Mar 5", sov: 9.2, type: "published", label: "Published: Vibe Coding Guide", color: "#34B27B" },
  { date: "Mar 12", sov: 10.8, type: "gained", label: "+3 new ChatGPT citations", color: "#6CB8D2" },
  { date: "Mar 18", sov: 11.4, type: "lost", label: "Lost 'vibe coding meaning' to cursor.com", color: "#E5484D" },
  { date: "Mar 23", sov: 12.1, type: "gained", label: "Perplexity started citing Enterprise guide", color: "#6CB8D2" },
];
```

Render each event as a `ReferenceDot` on the SOV line:
- **Published events:** green dot (8px) with a small upward triangle marker
- **Gained events:** teal dot (8px)
- **Lost events:** red dot (8px) with a small downward triangle marker

On hover over any event dot, show a tooltip with the event label. Use Recharts `customized` prop or a `ReferenceDot` with a custom shape.

Below the chart, add a small **event legend strip** (full width, 28px height):
```
📗 Mar 5: Published Vibe Coding Guide    📈 Mar 12: +3 ChatGPT citations    🔴 Mar 18: Lost to cursor.com    📈 Mar 23: Perplexity new citation
```
Each event: 10px text, colored dot prefix, horizontally scrollable if too many. This strip provides at-a-glance narrative context without cluttering the chart.

### C. Competitive ghost line on hover

When the user hovers anywhere on the chart area, show a dashed gray line representing **bolt.new's SOV** (the #1 competitor) behind your SOV line. This gives constant competitive context.

Implementation: always render the competitor line but with `strokeOpacity={0}` by default. On chart `onMouseEnter`, set opacity to 0.3. On `onMouseLeave`, set back to 0.

```typescript
// Add bolt.new SOV to the data
const enhancedData = momentumData.map((d, i) => ({
  ...d,
  competitorSov: 18.2 - (i * 0.04) + (Math.random() * 0.5 - 0.25), // bolt.new declining
}));
```

Render as:
```tsx
<Line 
  dataKey="competitorSov" 
  stroke="var(--text-secondary)" 
  strokeDasharray="4 4" 
  strokeWidth={1.5}
  strokeOpacity={isHovered ? 0.35 : 0} 
  dot={false}
  name="bolt.new SOV"
  style={{ transition: 'stroke-opacity 200ms' }}
/>
```

Add a subtle label at the right end of the ghost line when visible: "bolt.new" in 10px var(--text-secondary).

### D. Click a bar to see that day's breakdown

When the user clicks any bar in the chart, open a **mini slide-down panel** (not a full drawer — just a 200px expandable area below the chart) showing:

```
Mar 15, 2026 — 38 total citations (+5 vs previous day)

Platform breakdown:
ChatGPT    14 citations    (+2)    Top: "AI App Builder Comparison" cited for 3 new queries
Claude      9 citations    (+1)    Top: "Vibe Coding Enterprise" first citation on Claude
Perplexity  8 citations    (—)     No change
Google AI   5 citations    (+1)    Top: "Getting Started Guide" moved from position 3→2
Gemini      2 citations    (+1)    Top: "Non-Technical Founder's Guide" first Gemini citation
```

Each platform row: real favicon (14px) + name + count (JetBrains Mono) + delta (colored) + top event (12px var(--text-secondary)).

Click the panel's "×" or click another bar to dismiss/switch. This replaces the need for a full drawer on the hero chart.

---

## 2. CITED vs MENTIONED DONUTS — Make Actionable

### A. Add the gap as a clickable CTA

Between or below the two donuts, add a prominent **gap indicator**:

```tsx
<div style={{ 
  display: 'flex', alignItems: 'center', gap: '8px',
  padding: '8px 12px', borderRadius: '6px',
  background: 'rgba(245, 166, 35, 0.08)', 
  border: '1px solid rgba(245, 166, 35, 0.2)',
  cursor: 'pointer',
  marginTop: '12px'
}}>
  <span style={{ fontSize: '20px', fontFamily: 'JetBrains Mono', fontWeight: 600, color: '#F5A623' }}>22%</span>
  <div>
    <div style={{ fontSize: '12px', fontWeight: 500 }}>Mention-to-Citation Gap</div>
    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>10 queries mention you without citing — View queries →</div>
  </div>
</div>
```

On click: navigate to `/prompt-tracking` with a filter pre-set (or show a toast "View in Prompt Tracking → mentioned but not cited queries"). This turns a passive stat into an action.

### B. Add a mini breakdown inside each donut

The donut center currently just shows the percentage. Add a second line inside each:

- Cited donut center: "67%" (24px) + "31 of 47" (10px var(--text-secondary)) — shows raw numbers
- Mentioned donut center: "89%" (24px) + "42 of 47" (10px var(--text-secondary))

This grounds the percentages in real counts.

---

## 3. PLATFORM INTELLIGENCE GRID — Differentiation

### A. Add "Your strength" and "Your weakness" per platform

Below the sparkline in each platform column, add two compact lines:

```typescript
const PLATFORM_INSIGHTS = {
  ChatGPT: {
    strength: "Best rank (2.1) — they cite you highest",
    weakness: "Low coverage in security queries",
    strengthColor: "#34B27B",
  },
  Claude: {
    strength: "Fastest growing — +18% citations this month",
    weakness: "Not citing your comparison guides",
    strengthColor: "#34B27B",
  },
  Perplexity: {
    strength: "Highest rank (1.9) — you're their #1 pick",
    weakness: "Only 71% coverage, missing enterprise queries",
    strengthColor: "#34B27B",
  },
  "Google AI": {
    strength: "Strong schema recognition — your structured content wins",
    weakness: "Lowest SOV (9.4%) — underrepresented here",
    strengthColor: "#F5A623",
  },
  Gemini: {
    strength: "Growing — first citations this month on 3 pages",
    weakness: "Lowest coverage (48%) and citations (72)",
    strengthColor: "#F5A623",
  },
};
```

Per column, below the sparkline:
```
✅ Best rank (2.1) — they cite you highest
⚠ Low coverage in security queries
```

Strength line: 10px, green prefix icon. Weakness line: 10px, amber prefix icon. Max 1 line each, ellipsis if long.

### B. Make sparklines more useful

Current sparklines are decorative. Fix:
- Increase height from ~48px to **64px**
- Add a hover interaction: on hover, show a small tooltip with the exact day + value
- Add a thin horizontal reference line at the sparkline's average value (1px dashed var(--border))
- If the trend is declining, tint the sparkline fill slightly red instead of the platform color

### C. Highlight the top-performing platform visually

The platform with highest SOV already gets a `border-top: 2px solid var(--accent)`. Also add:
- A small "🏆 Top platform" label (10px, var(--accent)) in the top-right corner of that column
- The citation count in that column should be slightly larger (24px instead of 20px)

---

## 4. CITATION URLs TABLE — Enhancements

### A. Add a click-to-expand inline row (before the full drawer)

When a user clicks a row, before opening a full drawer, expand the row inline to show a **quick preview** (like an accordion):

```
lovable.dev/blog/ai-app-builder-comparison ↗     63 citations
├── ChatGPT: 22 citations (cited for 8 queries)
├── Claude: 15 citations (cited for 6 queries)  
├── Perplexity: 14 citations (cited for 5 queries)
├── Google AI: 12 citations (cited for 4 queries)
└── Gemini: 0 citations
                                        [Open full analysis →]
```

The expanded row: 160px additional height below the original row, showing per-platform breakdown with real favicons. The "Open full analysis →" link opens the full side drawer. This gives a quick-glance without committing to a full drawer interaction.

### B. Add row status indicators

At the left edge of each row (before the URL column), add a thin 3px colored left border:
- Green: velocity trending up (growing)
- Gray: velocity flat (stable)
- Red: velocity trending down (declining)

This gives an at-a-glance health indicator for each URL without reading the velocity column.

### C. Platform dots should be interactive

Currently the 5 platform dots (filled/empty favicons) are static. Make them interactive:
- Hover over a filled favicon → tooltip: "Cited on ChatGPT — 22 times, avg position 1.8"
- Hover over an empty circle → tooltip: "Not cited on Gemini — consider optimizing for this platform"

---

## 5. COMPETITOR LEADERBOARD — Enhancements

### A. Add a delta spark indicator

Next to each competitor's SOV delta (+4.3%, -0.8%, etc.), add a tiny inline sparkline or trend arrow that shows direction over the last 7 days, not just the period delta. This distinguishes "declining slowly" from "fell off a cliff yesterday."

Implementation: 3 small arrows or a 24×12px micro-sparkline next to the delta number.

### B. Make your row more prominent

Currently your row has `var(--accent-subtle)` background and a [YOU] badge. Also add:
- Your SOV number in **bold** (font-weight 600) while others are normal weight
- A thin left border on your row: `border-left: 3px solid var(--accent)`

### C. Clickable competitor rows

Each competitor row should be clickable → navigate to `/competitive-position`. Add `cursor: pointer` and hover state. On click: navigate or show toast "View bolt.new in Competitive Position →".

---

## 6. AI REFERRAL POTENTIAL — Enhancement

### A. Make the cards more visual

Currently the three cards show numbers + text. Add a small visual element to each:

**Card 1 (Est. AI Referrals ~3,200/mo):** Add a mini bar chart (40px height, 7 bars) showing weekly referral estimates for the last 7 weeks. Shows growth trajectory.

**Card 2 (Citation-to-Visit Rate 8.4%):** Add a comparison indicator: a small inline bar showing your 8.4% vs industry avg 6.2%. Two bars side by side, yours in accent, industry in gray.

**Card 3 (High-Intent Queries 14 of 47):** Add a mini donut (32px) showing 14/47 fill. Inside: nothing (too small for text). The fill communicates "you're covering about a third."

---

## WHAT NOT TO CHANGE

```
✅ Page title, subtitle, filter bar — keep as-is
✅ KPI strip values and layout — keep as-is
✅ Section order: KPIs → Hero chart → Visibility + Leaderboard → Platform Grid → URL Table → Revenue
✅ Side drawer structure and sections — keep as-is
✅ All 40 metric mappings — keep as-is
✅ Font sizes and spacing standards — keep as-is
```

---

## Verification After Fixes

```bash
npm run dev
npx tsc --noEmit
```

1. Hero chart: custom tooltip shows per-platform breakdown with cause text
2. Hero chart: event milestone dots visible on SOV line (at least 4 events)
3. Hero chart: event legend strip below chart with event descriptions
4. Hero chart: competitor ghost line appears on hover (dashed, 35% opacity)
5. Hero chart: click any bar → mini panel expands below with day breakdown
6. Donuts: 22% gap indicator visible between/below donuts, styled as amber CTA
7. Donuts: center text shows percentage + raw count (e.g., "31 of 47")
8. Platform grid: strength/weakness lines visible below each sparkline
9. Platform grid: sparklines 64px height with average reference line
10. Platform grid: top platform has "🏆 Top platform" label
11. Citation URLs table: click row → inline expansion with platform breakdown
12. Citation URLs table: colored left border (green/gray/red) per row health
13. Citation URLs table: platform dots show tooltip on hover
14. Competitor leaderboard: your row has bold SOV + left accent border
15. Competitor leaderboard: rows are clickable with hover state
16. Revenue cards: mini visuals added (bar chart, comparison bars, mini donut)
17. All existing functionality preserved — no regressions
18. `npm run build` succeeds