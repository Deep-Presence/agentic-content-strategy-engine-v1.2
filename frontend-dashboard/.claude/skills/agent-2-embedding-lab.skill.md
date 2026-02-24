# Agent 2: Deep Embedding Lab

> **Wait for Agent 0 to complete.** Run `git pull` before starting. You depend on the design system, API client, types, and layout shell.

---

## Your Mission

Build the **Deep Embedding Lab** — an immersive, tab-based visualization workspace where technical users explore embedding data, citation patterns, and gap analysis results through interactive D3.js and Recharts charts. This is the platform's primary competitive moat — no other tool visualizes embedding data this way.

---

## Files You Own

```
src/app/(dashboard)/embedding-lab/
├── page.tsx                          # Main workspace with tab navigation
├── loading.tsx                       # Skeleton loading states
└── components/
    ├── lab-workspace.tsx             # Tab container + shared controls
    ├── company-selector.tsx          # Company + run selector for the lab
    ├── chart-toolbar.tsx             # Shared controls (zoom, filter, export)
    ├── embedding-scatter.tsx         # UMAP/t-SNE scatter plot (main view)
    ├── cluster-radar-chart.tsx       # Multi-cluster radar overlay
    ├── gap-heatmap-chart.tsx         # Query × Cluster heatmap
    ├── citation-treemap-chart.tsx    # Domain distribution treemap
    ├── similarity-histogram.tsx      # Distribution histogram
    ├── cluster-boxplot-chart.tsx     # Company vs Citation per cluster
    ├── signal-inspector-panel.tsx    # 45-signal detail card (slide-over)
    ├── company-vs-citation.tsx       # Side-by-side comparison view
    ├── citation-source-explorer.tsx  # Platform filter view (ChatGPT vs Claude vs Perplexity vs Gemini)
    ├── query-drill-down.tsx          # Click-to-drill detail for any query
    └── chart-legend.tsx              # Shared legend component

src/components/charts/
├── umap-scatter.tsx                  # Reusable UMAP scatter (D3-based)
├── tsne-scatter.tsx                  # Reusable t-SNE scatter (D3-based)
├── cluster-radar.tsx                 # Reusable radar chart (Recharts)
├── gap-heatmap.tsx                   # Reusable heatmap (D3-based)
├── citation-treemap.tsx              # Reusable treemap (D3-based)
├── similarity-histogram.tsx          # Reusable histogram (Recharts)
├── cluster-boxplot.tsx               # Reusable boxplot (D3-based)
├── signal-inspector.tsx              # 45-signal visual card (pure React)
├── company-vs-citation.tsx           # Comparison chart (Recharts)
└── citation-explorer.tsx             # Platform breakdown (Recharts)
```

**Architecture Note:** Components in `src/components/charts/` are generic, reusable chart components that other agents can import. Components in `embedding-lab/components/` are lab-specific compositions that wire data + interactions to those charts.

## Files You Must NOT Touch

Everything in `src/components/ui/`, `src/lib/`, `src/types/`, `src/app/(dashboard)/layout.tsx`, and any other agent's directories.

---

## Page Specification

### Main Workspace — `/embedding-lab`

**Purpose:** A full-screen, immersive workspace with tab-based navigation between different visualization modes. Think of it like a Jupyter notebook's visual output pane, but designed for non-data-scientists.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│ Page Header: "Deep Embedding Lab"                                 │
│ Subtitle: "Explore citation patterns and content gaps"            │
│ Controls: [Company: Webflow ▼] [Run: Latest ▼] [Export ▼]       │
├──────────────────────────────────────────────────────────────────┤
│ Tab Bar:                                                          │
│ [ Embedding Space ] [ Clusters ] [ Gap Map ] [ Citations ]       │
│ [ Signals ] [ Platform Breakdown ]                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│                    Active Tab Content                              │
│                    (full remaining height)                         │
│                                                                    │
│                                                                    │
│                                                                    │
│                                                                    │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

**CRITICAL: This page must feel like a data exploration workspace, not a static dashboard.** Every chart must be interactive — hover for details, click to drill down, brush to filter.

---

## Tab Specifications

### Tab 1: Embedding Space

**Content:** Large UMAP or t-SNE scatter plot showing all embeddings in 2D space.

**Three types of points:**
- 🔵 Query embeddings (blue circles)
- 🟠 Citation embeddings (terracotta triangles)
- 🟢 Company content embeddings (green squares)

**Controls:**
- Toggle UMAP / t-SNE (radio buttons)
- Color by: Cluster, Embedding Type, Gap Score (dropdown)
- Filter by cluster (multi-select checkboxes)
- Search: type a query to highlight its embeddings

**Interactions:**
- Hover any point → tooltip with: type, text snippet (first 100 chars), similarity score, cluster
- Click a query point → opens `query-drill-down` panel on right side showing:
  - Full query text
  - Gap score + classification
  - Top 3 citation exemplars (similarity score, domain, snippet)
  - Best company match (similarity, unit ID, snippet)
  - Link to full brief detail (`/signal-analysis/briefs/{id}`)
- Brush/lasso to select region → shows stats for selected points
- Zoom + pan (mouse wheel + drag)

**D3 Implementation Notes:**
- Use `d3-zoom` for zoom/pan behavior
- Use `d3-brush` for selection
- Render points as SVG circles/triangles/squares
- For large datasets (1000+ points), use canvas rendering with SVG overlay for interactions
- Animate point transitions when switching between UMAP and t-SNE

**Data Source:**
- The backend generates Plotly HTML files, but we are NOT embedding iframes
- Instead, fetch the raw data from `GET /api/v1/artifacts/gap_analysis/{slug}/gap_analysis_complete.json`
- This contains all embeddings, query-citation mappings, and gap scores
- If the complete JSON is too large, fall back to loading individual files:
  - `analysis.json` for gap scores and mappings
  - `generation_spec.json` for cluster data

**Fallback for MVP:** If D3 scatter is complex, start with Recharts ScatterChart. It won't have brush/zoom but will show the data correctly. Mark it with a `// TODO: upgrade to D3` comment.

### Tab 2: Clusters

**Content:** Cluster comparison view using radar charts.

**Layout:**
```
┌───────────────────────────┬────────────────────────────────┐
│ Cluster Selector           │ Radar Chart Overlay             │
│ ☑ Mechanism (C1)          │                                  │
│ ☑ Boundary (C2)           │     ┌──────────┐                │
│ ☐ Category Comparison     │    /  headers   \               │
│ ☐ Decision Criteria       │   /              \              │
│ ☑ Definition (C5)         │  │ faq    lists   │             │
│ ☐ Problem/Awareness       │   \              /              │
│ ...                        │    \   stats   /               │
│                            │     └──────────┘                │
│ [Select All] [Clear]      │  (overlaid lines for each       │
│                            │   selected cluster)             │
├───────────────────────────┼────────────────────────────────┤
│ Cluster Detail Table       │                                 │
│ ┌────────┬──────┬───────┐ │ Exemplar Themes Word Cloud      │
│ │Cluster │ Avg  │ FAQ   │ │ (top 10 TF-IDF themes per       │
│ │        │ WC   │ Rate  │ │  selected cluster)              │
│ │ C1     │ 1740 │ 32%   │ │                                 │
│ │ C2     │ 1596 │ 23%   │ │                                 │
│ └────────┴──────┴───────┘ │                                 │
└───────────────────────────┴────────────────────────────────┘
```

**Radar chart axes (from generation_spec):**
- headers rate
- lists rate
- stats rate
- citations rate
- FAQ rate
- table rate
- key takeaways rate

**Each cluster is a different colored line overlay.** Select 2-4 clusters to compare them visually.

Use `Recharts RadarChart` with `PolarGrid`, `PolarAngleAxis`, `Radar` components. Each selected cluster = one `<Radar>` element with distinct color (use the brand color palette cycling through terracotta, ocean, sage, warning, etc.).

### Tab 3: Gap Map

**Content:** Heatmap showing gap scores across queries and clusters.

**X-axis:** Clusters (C1–C9)
**Y-axis:** Top 25 queries (sorted by gap score)
**Cell color:** Gap score intensity (white = 0, deep terracotta = max gap)
**Cell hover:** Query text, cluster name, gap score, classification

**Implementation:** D3 heatmap with color scale.

```typescript
// Color scale
const colorScale = d3.scaleSequential(d3.interpolateOranges)
  .domain([0, maxGapScore]);
```

Alternative if D3 heatmap is too complex for MVP: Use Recharts with a grid of colored cells, or a simple HTML table with background-color styling.

**Click a cell → drill down panel** showing that query's full brief for that cluster context.

### Tab 4: Citations

**Content:** Two sub-views for exploring citation sources.

**Sub-view A: Citation Treemap**
Interactive treemap showing domain distribution of all citations.
- Size = number of citations from that domain
- Color = average similarity score (light = low, dark = high)
- Click a domain → filter to show only that domain's citations in a list below
- Group by: Domain (default), Authority Type, Content Type

Use D3 treemap layout. Each rect is clickable and hoverable.

**Sub-view B: Citation Source Explorer (Platform Breakdown)**
Compare citation patterns across the 4 AI platforms: ChatGPT, Claude, Perplexity, Gemini.
- Horizontal bar chart: number of unique citations per platform
- Overlap Venn-style indicator: how many citations are shared across platforms
- Filter: select a platform → show its unique citations in a list

Use Recharts BarChart for the platform comparison.

### Tab 5: Signals

**Content:** The 45-Signal Inspector — a deep dive into citation structural signals.

**Layout:**
- Left panel: List of citation exemplars (sortable by similarity, filterable by cluster)
- Right panel: Selected exemplar's full 45-signal breakdown

**45-Signal Breakdown Display:**
Organized into 4 visual sections (cards), each with a background tint:

**Category A — Text Composition (terracotta tint):**
```
Word Count: 1,090    Sentence Count: 45    Paragraphs: 26
Avg Paragraph Length: 42 words    Reading Level: 12.3 (Flesch-Kincaid)
Self-Contained Ratio: 0.85
```

**Category B — Structural Elements (ocean blue tint):**
```
H1: 1  H2: 5  H3: 8  H4: 2    Lists: 12  Ordered: 3
Tables: 1    Code Blocks: 0    Bullets/List: 4.2
```

**Category C — Content Patterns (sage green tint):**
```
✅ FAQ Section    ❌ Definition Opening    ✅ Key Takeaways
❌ Comparison Table    ✅ Step-by-Step    ❌ Research Refs
❌ Expert Quotes
```
(Checkmark = true, X = false, color green/red respectively)

**Category D — Factual Density (gray tint):**
```
Data Points: 3    Citation Density: 0.42    Named Entity Density: 0.18
```

Each signal should have a subtle comparison indicator: how this exemplar compares to the cluster average (above/below/at average, shown as ↑/↓/= with green/red/gray).

### Tab 6: Platform Breakdown

**Content:** Detailed comparison of how each AI platform responds to queries.

**Layout:**
- Top: 4 platform cards in a row (ChatGPT, Claude, Perplexity, Gemini)
  - Each shows: total citations, unique citations, avg similarity, top domain
- Middle: Select a query → see all 4 platform responses side-by-side
- Bottom: Platform agreement chart (Recharts grouped bar) — for each query, how similar are the citations across platforms?

---

## Shared Chart Components (`src/components/charts/`)

These are reusable, typed chart components. They receive data as props and handle rendering only. No API calls inside chart components.

### `umap-scatter.tsx`
```typescript
interface UmapScatterProps {
  points: Array<{
    x: number;
    y: number;
    type: 'query' | 'citation' | 'company';
    id: string;
    label: string;
    cluster?: string;
    similarity?: number;
    gapScore?: number;
  }>;
  colorBy: 'type' | 'cluster' | 'gap_score';
  selectedCluster?: string;
  highlightedIds?: string[];
  onPointClick?: (point: any) => void;
  onPointHover?: (point: any) => void;
  onBrushSelect?: (points: any[]) => void;
  width?: number;
  height?: number;
}
```

### `cluster-radar.tsx`
```typescript
interface ClusterRadarProps {
  clusters: Array<{
    name: string;
    color: string;
    metrics: {
      headers: number;
      lists: number;
      stats: number;
      citations: number;
      faq: number;
      tables: number;
      key_takeaways: number;
    };
  }>;
  size?: number;
}
```

### `gap-heatmap.tsx`
```typescript
interface GapHeatmapProps {
  data: Array<{
    query_id: string;
    query_text: string;
    cluster: string;
    gap_score: number;
    classification: string;
  }>;
  clusters: string[];
  onCellClick?: (queryId: string, cluster: string) => void;
  width?: number;
  height?: number;
}
```

### `signal-inspector.tsx`
```typescript
interface SignalInspectorProps {
  signals: StructuralSignals;  // from types/gap-analysis.ts
  clusterAverages?: Partial<StructuralSignals>;  // for comparison
  compact?: boolean;  // compact mode for inline use
}
```

---

## Data Loading Strategy

The Embedding Lab works with large JSON files. Use this loading strategy:

1. **On page mount:** Fetch `generation_spec.json` (small, ~5KB) for cluster data
2. **On page mount:** Fetch `gap_report.json` (medium, ~50KB) for gap briefs
3. **On "Embedding Space" tab activation:** Fetch `gap_analysis_complete.json` (large, ~1.5MB) for full embeddings
4. **Cache in Zustand** so switching tabs doesn't re-fetch
5. **Show skeleton loaders** while data loads
6. **Show "No data available" state** if files don't exist (company hasn't run analysis)

```typescript
// In embedding-lab/page.tsx
'use client';
import { useEffect, useState } from 'react';
import { artifacts } from '@/lib/api/artifacts';
import { useAppStore } from '@/stores/app-store';

export default function EmbeddingLabPage() {
  const currentCompany = useAppStore(s => s.currentCompany);
  const [genSpec, setGenSpec] = useState(null);
  const [gapReport, setGapReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [spec, report] = await Promise.all([
          artifacts.getFileContent('gap_analysis', currentCompany, 'generation_spec.json'),
          artifacts.getFileContent('gap_analysis', currentCompany, 'gap_report.json'),
        ]);
        setGenSpec(spec);
        setGapReport(report);
      } catch (e) {
        // No data available
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [currentCompany]);

  // ... render tabs
}
```

---

## Real Data Reference (Webflow)

Use this real data from the Webflow analysis to build realistic charts:

**9 Clusters with structural rates:**
| Cluster | ID | Queries | Avg WC | FAQ Rate | Table Rate | Headers | Lists | Stats | Citations |
|---------|----|---------|--------|----------|------------|---------|-------|-------|-----------|
| Mechanism | C1 | 8 | 1740 | 0.32 | 0.21 | 0.90 | 0.80 | 0.62 | 0.96 |
| Boundary | C2 | 8 | 1596 | 0.23 | 0.29 | 0.96 | 0.78 | 0.75 | 0.98 |
| Category Comparison | C3 | 8 | 1858 | 0.36 | 0.39 | 0.96 | 0.87 | 0.75 | 0.96 |
| Decision Criteria | C4 | 8 | 2055 | 0.27 | 0.24 | 0.91 | 0.77 | 0.71 | 0.95 |
| Definition | C5 | 8 | 1690 | 0.24 | 0.12 | 0.92 | 0.80 | 0.68 | 0.93 |
| Problem/Awareness | C6 | 8 | 1685 | 0.23 | 0.13 | 0.95 | 0.84 | 0.73 | 0.95 |
| Best-of/Consideration | C7 | 8 | 1748 | 0.28 | 0.29 | 0.91 | 0.84 | 0.71 | 0.95 |
| Branded Evaluation | C8 | 8 | 1821 | 0.38 | 0.40 | 0.92 | 0.80 | 0.77 | 0.97 |
| Feature Verification | C9 | 8 | 1423 | 0.22 | 0.20 | 0.86 | 0.80 | 0.56 | 0.99 |

**Use this data for hardcoded fallback** when the API isn't available. Create a `embedding-lab/data/webflow-sample.ts` file with this data so the UI always renders something meaningful.

---

## Acceptance Criteria

- [ ] `/embedding-lab` renders the 6-tab workspace
- [ ] Tab switching works without page reload
- [ ] At least 3 tabs render functional interactive charts (Embedding Space, Clusters, Gap Map are highest priority)
- [ ] Cluster radar shows overlapping lines for selected clusters
- [ ] Heatmap renders with correct color coding
- [ ] Signal inspector shows all 45 signals organized by category
- [ ] Charts use brand colors (ocean blue primary for this section)
- [ ] Hover tooltips work on all chart elements
- [ ] Loading skeletons display while data fetches
- [ ] Empty states show when no company data exists
- [ ] All chart components in `src/components/charts/` export clean typed interfaces
- [ ] No TypeScript errors
