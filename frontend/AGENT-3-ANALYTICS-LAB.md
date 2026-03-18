# Agent 3 — Analytics + Deep Embedding Lab

> **Read CLAUDE.md first, then this file.** Runs parallel after Agent 1.

## Prerequisites Check

```bash
ls src/components/ui/index.ts && ls src/types/index.ts && ls src/data/gap-report.ts
ls data/artifacts/gap_analysis/lovable/gap_report.md    # Real data exists
npm run dev                                              # Starts clean
```

## Files You Own

```
src/app/(dashboard)/analytics/page.tsx
src/app/(dashboard)/analytics/lab/page.tsx
src/app/(dashboard)/analytics/_components/
```

## Data Sources — ALL Real, ALL Available Locally

| Data | Source File | Type |
|------|-----------|------|
| 99 queries + 25 gap briefs | `data/artifacts/gap_analysis/lovable/gap_report.md` | `Query[]` |
| 9 cluster specs | `data/artifacts/gap_analysis/lovable/generation_spec.md` | `Cluster[]` |
| Site audit (8 dimensions) | `data/artifacts/site_audit/lovable/039d53f8.../report.md` | `SiteAudit` |
| t-SNE projections | `data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_tsne.json` | `EmbeddingPoint[]` |
| UMAP projections | `data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_umap.json` | `EmbeddingPoint[]` |
| Enriched citations | `data/artifacts/gap_analysis/lovable/enriched_citations.json` | Full structural signals |
| Company embeddings | `data/artifacts/gap_analysis/lovable/company_embeddings.json` | Company content vectors |

**Import JSON files directly. Never generate synthetic data.**

---

## Step 1: Analytics Top Metrics + Tab System

**Top metrics bar** (always visible): 5 `KPIRow` cells:
- SOV %: 12.4% (+2.1%) | Citation Presence: 38.7% | SPA: 1.130 | Queries: 99 | Published: 7

**VS Code-style tab system** using `TabBar` component. Default open: Performance, Citations. Available: Performance, Share of Voice, Citations, Competitors, Brand Health.

**Global filter bar** below tabs: Cluster (9 options), Platform (5: ChatGPT/Claude/Perplexity/Google AI Overview/Gemini), Date Range, Classification.

### ✅ Verify Before Proceeding

Visit `/analytics`. Top metrics should show real numbers (SPA 1.130, 99 queries). Tab bar should render with clickable tabs. Filter dropdowns should open. If metrics show 0 or undefined, the data parser is broken — check `src/data/gap-report.ts`.

---

## Step 2: Build 5 Tab Contents

**Performance tab:** Recharts `ComposedChart` — content published (bars) + citations gained (line). Published content table below.

**Share of Voice tab:** Recharts stacked `AreaChart` (your SOV vs competitors over time). Competitor breakdown table.

**Citations tab:** Query-level table with ALL 99 queries from real data. Columns: Query Text, Cluster badge, Classification badge, Company Cited (✓/✗), Gap Score, Platform dots. **Click row → drill-down panel slides from right** (Framer Motion, 360px) showing structural comparison.

### Example: Citations Table Row

```tsx
<tr className="hover:bg-accent-subtle cursor-pointer" onClick={() => openDrillDown(query)}>
  <td className="p-[6px_10px] text-[12px] border-b border-border-subtle truncate max-w-[300px]">
    {query.text}
  </td>
  <td className="p-[6px_10px]">
    <Badge variant="info">{query.cluster}</Badge>
  </td>
  <td className="p-[6px_10px]">
    <Badge variant={query.classification === 'significant_gap' ? 'error' : query.classification === 'company_wins' ? 'success' : 'neutral'}>
      {query.classification.replace('_', ' ')}
    </Badge>
  </td>
  <td className="p-[6px_10px] text-center">
    {query.companyCited ? '✓' : '—'}
  </td>
  <td className="p-[6px_10px] text-[12px] font-mono">{query.gap.toFixed(4)}</td>
</tr>
```

### Example: Drill-Down Structural Comparison

```tsx
// Inside the slide-in panel
<div className="space-y-4">
  <h3 className="text-h3">Structural Comparison</h3>
  {/* Your page vs cited pages — horizontal bars */}
  {['words', 'headers', 'lists', 'citations'].map(metric => (
    <div key={metric} className="space-y-1">
      <span className="text-[10px] uppercase tracking-[0.06em] text-text-tertiary">{metric}</span>
      <div className="flex gap-2 items-center">
        <div className="h-[6px] bg-accent rounded-sm" style={{ width: `${yourPercent}%` }} />
        <div className="h-[6px] bg-text-tertiary/30 rounded-sm" style={{ width: `${citedPercent}%` }} />
      </div>
    </div>
  ))}
  <Button variant="primary" className="w-full mt-4">Add to Content Cycle</Button>
</div>
```

**Competitors tab:** Citation share bar chart. Head-to-head table. Extract domains from gap report exemplar URLs (netlify.com, gitguardian.com, sonarsource.com, etc.).

**Brand Health tab:** `ScoreGauge` for AEO score (38.7/100). Recharts `RadarChart` for 8 dimensions (use real scores: Crawlability 100, Performance 100, On-Page SEO 94, Extractability 95, Schema 98, E-E-A-T 100, Freshness 100, Security 100). Bot access table. Top findings from audit.

### ✅ Verify Before Proceeding

Click each tab. Performance shows chart. Citations shows 99 rows of real data. Click a row — drill-down slides in with real exemplar data. Brand Health shows gauge at 38.7 and radar chart. If data is missing, check parsers.

---

## Step 3: Deep Embedding Lab (4 Views)

**CRITICAL:** Every Plotly component must use dynamic import:
```tsx
import dynamic from 'next/dynamic';
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });
```

**View 1 — Space Overview:**
- Full Plotly scatter. Points: company=`#5BA4C4`, citations=`rgba(91,164,196,0.5)`, queries=`#DC7B18`
- t-SNE ↔ UMAP toggle switches dataset
- 9 cluster regions (labeled)
- Hover: title, URL, similarity, cluster

**View 2 — Cluster Deep-Dive:**
- Cluster selector → filtered scatter. Gap lines between your content and citations.
- Right sidebar: cluster stats from generation_spec.md (query count, avg word count, FAQ rate, etc.)

**View 3 — Query Microscope:**
- Query selector → your points vs cited points with connection lines
- Structural comparison panel
- "Why they're cited and you're not" analysis

**View 4 — Simulation:**
- Paste URL/draft → predicted embedding position
- Select queries → CPS predictions for 5 platforms
- Structural sliders → real-time CPS recalc

**Topical Authority Overlay:** Toggle on any view. Heatmap showing content vs citation concentration.

### ✅ Verify Before Proceeding

Visit `/analytics/lab`. The scatter plot should render WITHOUT SSR errors. Points should be visible and colored. Hover should show tooltips. Toggle t-SNE/UMAP — data should change. If you see "window is not defined", the dynamic import is missing.

---

## Troubleshooting

### "window is not defined" (Plotly SSR)
**Fix:** `dynamic(() => import('react-plotly.js'), { ssr: false })`. This MUST be at the component level, not inside a render function.

### Plotly Chart Too Small or Invisible
**Fix:** Wrap in a div with explicit height: `<div style={{ height: '500px', width: '100%' }}><Plot ... /></div>`. Set `layout.autosize = true` and `config.responsive = true`.

### Recharts Not Rendering
**Fix:** Recharts needs explicit `<ResponsiveContainer width="100%" height={300}>` wrapper. Without it, charts render at 0px height.

### Large JSON Import Slow
**Symptom:** Page takes 5+ seconds to load because embedding JSONs are multi-MB.
**Fix:** Use Next.js `getStaticProps` or load data on the client with `useEffect` + loading skeleton. Don't import 24MB JSON at module scope.

### Filter State Resets on Tab Switch
**Fix:** Lift filter state to the analytics page level (parent), not inside each tab. Pass filter values as props to tab content components.

### Drill-Down Panel Doesn't Close
**Fix:** Add click-outside handler and Escape key listener. Use `useEffect` with `document.addEventListener('keydown', ...)`.

---

## Completion Criteria

- [ ] Analytics loads with real data in top metrics (SPA 1.130, 99 queries)
- [ ] All 5 tabs render with content
- [ ] Filter bar works across tabs
- [ ] Citations tab: 99 real queries visible
- [ ] Citations drill-down: slides in with structural comparison
- [ ] Brand Health: AEO gauge at 38.7, radar with 8 real dimension scores
- [ ] Embedding Lab: no SSR errors
- [ ] Scatter plot renders with colored points
- [ ] t-SNE/UMAP toggle works
- [ ] All 4 Lab views functional
- [ ] Light mode default, dark mode works
- [ ] `npx tsc --noEmit` — 0 errors
