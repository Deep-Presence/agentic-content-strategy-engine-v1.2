# Agent 1: Deep Signal Analysis

> **Wait for Agent 0 to complete.** Run `git pull` before starting. You depend on the design system, API client, types, and layout shell.

---

## Your Mission

Build the **Deep Signal Analysis** section — the 8-step intelligence pipeline that analyzes how AI platforms cite content and identifies gaps. This is the renamed "Gap Analysis" with a premium, technical feel.

---

## Files You Own

```
src/app/(dashboard)/signal-analysis/
├── page.tsx                          # Results overview (default landing)
├── run/page.tsx                      # Trigger new pipeline run
├── [runId]/page.tsx                  # Run detail with 8-step progress
├── briefs/page.tsx                   # All gap briefs list
├── briefs/[briefId]/page.tsx         # Individual gap brief detail
├── loading.tsx                       # Skeleton loading states
└── components/
    ├── pipeline-trigger-form.tsx     # Form to start a new run
    ├── step-progress.tsx             # 8-step visual progress tracker
    ├── results-overview.tsx          # SPA score + cluster summary
    ├── gap-brief-table.tsx           # Sortable table of all briefs
    ├── gap-brief-detail.tsx          # Full brief with exemplars
    ├── cluster-card.tsx              # Individual cluster summary card
    └── spa-score-display.tsx         # Large SPA score visualization

src/components/pipeline/
├── pipeline-progress.tsx             # Reusable 8-step SSE progress component
├── gap-brief-card.tsx                # Compact brief card for lists
├── spa-score-card.tsx                # Compact SPA score for dashboard
└── cluster-breakdown.tsx             # Cluster grid overview

src/stores/pipeline-store.ts          # Zustand store for signal analysis state
```

## Files You Must NOT Touch

Everything in `src/components/ui/`, `src/lib/`, `src/types/`, `src/app/(dashboard)/layout.tsx`, and any other agent's directories.

---

## Page Specifications

### 1. Results Overview — `/signal-analysis` (Landing Page)

**Purpose:** Show the latest completed analysis results for the current company.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Page Header: "Deep Signal Analysis"                      │
│ Subtitle: "AI Citation Intelligence for {company}"       │
│ Actions: [Run New Analysis] button                       │
├─────────────────────────────────────────────────────────┤
│ SPA Score Card (full-width hero)                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │  SPA Score: 0.1847                                   │ │
│ │  t-stat: 12.4 | p-value: < 0.001                    │ │
│ │  Citation Advantage: 68% | Company Advantage: 32%    │ │
│ │  "AI platforms cite competitors 68% more than you"   │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Cluster Breakdown (3-col grid of ClusterCards)           │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│ │ Mechanism  │ │ Boundary   │ │ Category   │           │
│ │ C1 · 8 q   │ │ C2 · 8 q   │ │ Comparison │           │
│ │ FAQ: 32%   │ │ FAQ: 23%   │ │ C3 · 8 q   │           │
│ │ Gap: 0.18  │ │ Gap: 0.15  │ │ FAQ: 36%   │           │
│ └────────────┘ └────────────┘ └────────────┘           │
│ ... (all 9 clusters)                                     │
├─────────────────────────────────────────────────────────┤
│ Top Gap Briefs (table, top 25, sorted by gap severity)  │
│ ┌─────┬──────────────────┬─────────┬───────┬──────────┐│
│ │ #   │ Query             │ Cluster │ Gap   │ Action   ││
│ │ 1   │ How do no-code... │ Cat.Cmp │ 0.244 │ View →   ││
│ │ 2   │ What is a design..│ Defn    │ 0.231 │ View →   ││
│ └─────┴──────────────────┴─────────┴───────┴──────────┘│
│ "Open in Embedding Lab →" link at bottom                 │
└─────────────────────────────────────────────────────────┘
```

**Data Source:**
- `GET /api/v1/artifacts/gap_analysis/{slug}/gap_report.json` — Full report
- `GET /api/v1/artifacts/gap_analysis/{slug}/generation_spec.json` — Cluster specs

**Implementation Notes:**
- Use Webflow as default company (slug: "webflow")
- Color-code gap scores: significant_gap (red), gap_to_close (orange), roughly_equal (gray), company_wins (green)
- Each cluster card shows: name, query count, top structural rates, avg gap score, dominant content type
- Table rows are clickable → navigate to brief detail
- "Open in Embedding Lab" link at bottom of each section → `/embedding-lab?company={slug}`

### 2. Run New Analysis — `/signal-analysis/run`

**Purpose:** Trigger a new Deep Signal Analysis pipeline.

**Layout:**
- Form with fields:
  - Company Name (text input, required)
  - Domain (text input, required)
  - Seed URLs (multi-input, add/remove URLs)
  - Skip Steps (checkbox group: steps 1-8, for re-running partial analyses)
- "Start Analysis" button (primary, terracotta)
- Cancel link

**On Submit:**
- Call `POST /api/v1/gap-analysis/start` with the form data
- On 202: Navigate to `/signal-analysis/{run_id}` to show progress
- On 409: Show toast "Pipeline already running for this company" with link to existing run

### 3. Run Detail + Progress — `/signal-analysis/[runId]`

**Purpose:** Show real-time progress of a running analysis, or completed results.

**If status === 'running':**
```
┌────────────────────────────────────────────────────────┐
│ Deep Signal Analysis — Running                          │
│ Company: Webflow | Started: 2 minutes ago               │
├────────────────────────────────────────────────────────┤
│ 8-Step Pipeline Progress                                │
│                                                          │
│ ✅ S1: Embed Assets         — Completed (45s)           │
│ ✅ S2: Generate Queries     — Completed (1m 23s)        │
│ 🔄 S3: Search AI Platforms  — In Progress...            │
│ ○  S4: Enrich Citations     — Waiting                   │
│ ○  S5: Embed Content        — Waiting                   │
│ ○  S6: Analyze Gaps         — Waiting                   │
│ ○  S7: Visualize            — Waiting                   │
│ ○  S8: Generate Report      — Waiting                   │
│                                                          │
│ [Cancel Run]                                             │
└────────────────────────────────────────────────────────┘
```

**SSE Implementation:**
- Connect to `GET /api/v1/tasks/{runId}/events` using the `useEventStream` hook from lib/hooks
- Each step event updates the step status in real-time
- Show elapsed time per step
- On "completed": auto-navigate to results overview
- On "failed": show error message with retry button

**If status === 'completed':**
Show the same results overview content, but scoped to this specific run.

**If status === 'pending_approval':**
This shouldn't happen for gap analysis (no HITL), but handle gracefully.

### 4. Gap Brief Detail — `/signal-analysis/briefs/[briefId]`

**Purpose:** Deep dive into a single gap brief showing the full content brief, target specs, and citation exemplars.

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ ← Back to Briefs                                         │
│ Query: "How do no-code website builders compare to..."   │
│ Cluster: Category Comparison (C3) | Gap: 0.244           │
├──────────────────────────┬──────────────────────────────┤
│ Content Brief             │ Top Citation Exemplars        │
│                           │                               │
│ Target Word Count:        │ 1. thenewstack.io (0.809)    │
│   1090–1110              │    "How to Choose Between..."  │
│ Reading Level: 12.0–14.6 │    📊 45-Signal Card          │
│ Headers: 12–15           │    [Open in Lab →]            │
│ H2: 3, H3: 9            │                               │
│ Patterns: Step-by-Step   │ 2. beecommerce.pl (0.782)    │
│ Authority: commercial    │    "In the realm of web..."   │
│ Content Type: blog       │    📊 45-Signal Card          │
│                           │                               │
│ Best Company Match:       │ 3. beecommerce.pl (0.782)    │
│ unit_246 (sim: 0.492)    │    "In the realm of web..."   │
│ "We are a full-service.."│    📊 45-Signal Card          │
├──────────────────────────┴──────────────────────────────┤
│ Actions:                                                  │
│ [Create Content Brief →] [Open in Embedding Lab →]       │
└─────────────────────────────────────────────────────────┘
```

**45-Signal Card (expandable):**
Each citation exemplar has a collapsible card showing ALL 45 structural signals organized by category:
- Category A: Text Composition (word count, sentence count, reading level, etc.)
- Category B: Structural Elements (headers, lists, tables, code blocks)
- Category C: Content Patterns (FAQ, definition, key takeaways, comparison tables)
- Category D: Factual Density (data points, citation density, named entities)

Display as a 4-column grid of small stat boxes, color-coded by category.

**"Create Content Brief" button:** Navigates to `/content-pipeline?create=true&query={query_id}&cluster={cluster}` (Agent 3 handles that page)

---

## Component Specifications

### `step-progress.tsx`
The 8-step progress visualization. This is a **key differentiating UX moment**.

Design: Vertical stepper with connecting lines.
- Each step: circle icon (numbered or status icon) + label + description + elapsed time
- States: waiting (gray circle, dashed line), active (terracotta pulsing circle, solid line), completed (green checkmark), failed (red X)
- Animate transitions between states
- The connecting line between steps fills with color as steps complete

### `spa-score-display.tsx`
Large, prominent SPA score display.
- Score number in Source Serif 4, large (text-display)
- Donut/radial chart showing citation advantage vs company advantage
- Use Recharts PieChart with two segments
- Color: terracotta for citation advantage, sage for company advantage
- Below: t-statistic, p-value, interpretation text

### `cluster-card.tsx`
Card for each cluster in the grid.
- Header: cluster name (Source Serif 4) + cluster ID badge
- Stats: query count, avg gap score, avg word count
- Mini bar chart: structural rates (headers, lists, stats, citations) as horizontal bars
- Bottom: dominant content type + authority type badges
- Click → filters the brief table to this cluster

### `gap-brief-table.tsx`
Sortable table with columns: #, Query, Cluster, Gap Score, Classification, Best Company Sim, Avg Citation Sim, Actions.
- Sortable by any column
- Filterable by cluster (dropdown)
- Filterable by classification (tabs: All, Significant Gap, Gap to Close, Equal, Company Wins)
- Rows clickable → navigate to brief detail
- Gap score cell: color-coded badge

---

## Zustand Store

**`src/stores/pipeline-store.ts`:**
```typescript
interface PipelineState {
  // Current analysis run
  activeRunId: string | null;
  activeRunStatus: TaskStatus | null;
  completedSteps: GapAnalysisStep[];
  currentStep: GapAnalysisStep | null;

  // Results
  gapReport: GapReport | null;
  clusterSpecs: ClusterSpec[];
  gapBriefs: GapBrief[];

  // Actions
  setActiveRun: (runId: string, status: TaskStatus) => void;
  updateStep: (step: GapAnalysisStep, status: 'completed' | 'active') => void;
  setResults: (report: GapReport, specs: ClusterSpec[], briefs: GapBrief[]) => void;
  reset: () => void;
}
```

---

## API Endpoints You Use

| Endpoint | Where Used |
|----------|-----------|
| `POST /api/v1/gap-analysis/start` | Run page — trigger pipeline |
| `GET /api/v1/gap-analysis/{run_id}/status` | Run detail — poll status |
| `GET /api/v1/tasks/{task_id}/events` | Run detail — SSE progress |
| `POST /api/v1/tasks/{task_id}/cancel` | Run detail — cancel button |
| `GET /api/v1/artifacts/gap_analysis/{slug}` | Results — list files |
| `GET /api/v1/artifacts/gap_analysis/{slug}/gap_report.json` | Results — load report |
| `GET /api/v1/artifacts/gap_analysis/{slug}/generation_spec.json` | Results — load cluster specs |
| `GET /api/v1/artifacts/gap_analysis/{slug}/gap_analysis_complete.json` | Brief detail — full data |

---

## Acceptance Criteria

- [ ] `/signal-analysis` renders with Webflow data showing SPA score, 9 clusters, top 25 briefs
- [ ] `/signal-analysis/run` form submits correctly (or shows graceful error if backend not running)
- [ ] `/signal-analysis/{runId}` shows 8-step progress with SSE updates
- [ ] Steps animate from waiting → active → completed in real-time
- [ ] Cluster cards are clickable and filter the brief table
- [ ] Brief detail page shows full content brief + citation exemplars with 45-signal cards
- [ ] "Open in Embedding Lab" links point to correct routes
- [ ] All components use the shared design system (Button, Card, Badge, Table from components/ui/)
- [ ] Brand styling is correct: cream backgrounds, Source Serif headings, terracotta accents for this section? NO — this section uses OCEAN BLUE accent (see brand.skill.md Phase Color Mapping)
