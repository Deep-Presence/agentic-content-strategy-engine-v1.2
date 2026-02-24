# Agent 3: Content Pipeline

> **Wait for Agent 0 to complete.** Run `git pull` before starting. You depend on the design system, API client, types, and layout shell.

---

## Your Mission

Build the **Content Pipeline** — a Linear-style content management system with multiple views, weekly cycles, a Tiptap rich text editor with diff toggle, HITL approval flow, and Citability Score integration. This is the production hub where content goes from gap brief → published article.

**Design Philosophy:** Linear's speed and keyboard-first feel, adapted to content workflows. Clean, dense information. Status-driven. No clutter.

---

## Files You Own

```
src/app/(dashboard)/content-pipeline/
├── page.tsx                              # Main view with Board/Table/Calendar/Cycles/Roadmap switcher
├── cycles/page.tsx                       # Cycles (weekly sprints) view
├── roadmap/page.tsx                      # Roadmap timeline view
├── analytics/page.tsx                    # Content analytics dashboard
├── [briefId]/page.tsx                    # Brief detail: Tiptap editor + Intel Panel + HITL
├── loading.tsx                           # Skeleton loading states
└── components/
    ├── view-switcher.tsx                 # Board / Table / Calendar / Cycles / Roadmap tabs
    ├── board-view.tsx                    # Kanban board (drag columns)
    ├── table-view.tsx                    # Sortable table view
    ├── calendar-view.tsx                 # Calendar grid view
    ├── cycle-card.tsx                    # Individual cycle card
    ├── cycle-list.tsx                    # List of cycles with progress
    ├── roadmap-timeline.tsx              # Horizontal timeline
    ├── brief-card.tsx                    # Content brief card (used in board + lists)
    ├── brief-status-badge.tsx            # Status indicator with color
    ├── citability-score-badge.tsx        # Citability score display
    ├── content-type-badge.tsx            # Blog/Guide/Case Study/Product Page badge
    ├── create-brief-dialog.tsx           # Dialog to create new brief
    ├── pipeline-trigger-bar.tsx          # Bar to trigger content generation
    ├── eval-scores-panel.tsx             # Evaluator scores display (4 dimensions)
    ├── analytics-charts.tsx              # Content analytics charts
    └── filter-bar.tsx                    # Filters for status, type, cluster, cycle

src/components/editor/
├── tiptap-editor.tsx                     # Full Tiptap rich text editor
├── diff-toggle.tsx                       # Red/green diff view component
├── intel-panel.tsx                       # Right sidebar: target signals, gap score, exemplars, eval scores
└── approval-bar.tsx                      # Bottom bar: Approve / Edit+Note / Reject buttons

src/stores/content-store.ts              # Zustand store for content pipeline state
```

## Files You Must NOT Touch

Everything in `src/components/ui/`, `src/lib/`, `src/types/`, `src/app/(dashboard)/layout.tsx`, and any other agent's directories.

---

## Content Brief Status Flow

```
Suggested → Approved → Research → Drafting → Enriching → Formatting → Evaluating → Review → Published
                                                                          ↓
                                                                    Draft Saved (rejected)
```

Each status maps to a column in Kanban view and a color:

| Status | Color | Description |
|--------|-------|-------------|
| `suggested` | `cream-500` (gray) | Generated from gap analysis, awaiting approval |
| `approved` | `ocean-400` (blue) | Approved for production, queued |
| `research` | `ocean-400` (blue) | Agent researching content |
| `drafting` | `ocean-400` (blue) | Agent writing draft |
| `enriching` | `ocean-400` (blue) | Perplexity enriching with facts |
| `formatting` | `ocean-400` (blue) | Haiku formatting final version |
| `evaluating` | `terracotta-400` (orange) | Evaluator-optimizer loop running |
| `review` | `terracotta-400` (orange) | Waiting for human review (HITL) |
| `published` | `sage-400` (green) | Approved and published |
| `draft_saved` | `cream-600` (gray) | Rejected, saved as draft |

---

## Page Specifications

### 1. Main Pipeline View — `/content-pipeline`

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Page Header: "Content Pipeline"                                  │
│ Actions: [+ New Brief] [⚡ Generate from Gaps] [Filter ▼]      │
├─────────────────────────────────────────────────────────────────┤
│ View Switcher: [Board] [Table] [Calendar] [Cycles] [Roadmap]   │
├─────────────────────────────────────────────────────────────────┤
│ Filter Bar: Status ▼ | Type ▼ | Cluster ▼ | Cycle ▼ | Search  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│                    Active View Content                            │
│                    (remaining height, scrollable)                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### View A: Board (Kanban) — Default View

Horizontal scrolling Kanban board with columns for each status.

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Suggested   │ │   Research   │ │  Evaluating  │ │   Review     │
│  (3 items)   │ │  (2 items)   │ │  (1 item)    │ │  (2 items)   │
├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │
│ │ Brief #1 │ │ │ │ Brief #4 │ │ │ │ Brief #6 │ │ │ │ Brief #7 │ │
│ │ Blog     │ │ │ │ Guide    │ │ │ │ Blog     │ │ │ │ Case Sty │ │
│ │ C3: Cat  │ │ │ │ C1: Mech │ │ │ │ C5: Defn │ │ │ │ C7: Best │ │
│ │ CS: 72%  │ │ │ │ CS: 85%  │ │ │ │ CS: —    │ │ │ │ CS: 91%  │ │
│ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │
│ ┌──────────┐ │ │ ┌──────────┐ │ │              │ │ ┌──────────┐ │
│ │ Brief #2 │ │ │ │ Brief #5 │ │ │              │ │ │ Brief #8 │ │
│ └──────────┘ │ │ └──────────┘ │ │              │ │ └──────────┘ │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

**Kanban Implementation:**
- Columns scroll horizontally
- Each column: header with status name + count badge
- Cards are compact but informative (see Brief Card spec below)
- Drag-and-drop between columns is a STRETCH GOAL (nice to have, not required for MVP)
- Column groups: collapse "Research + Drafting + Enriching + Formatting" into single "In Progress" column for cleaner view
- Column order: Suggested → Approved → In Progress → Evaluating → Review → Published

### View B: Table

Sortable, filterable table with columns:
| Column | Width | Type |
|--------|-------|------|
| Title | flex | Text, clickable → brief detail |
| Status | 120px | StatusBadge |
| Type | 100px | ContentTypeBadge |
| Cluster | 140px | Text |
| Citability Score | 100px | Score badge (color-coded) |
| Word Count | 80px | Number |
| Cycle | 120px | Text or "—" |
| Updated | 100px | Relative date |

Sort by any column. Click row → navigate to brief detail.

### View C: Calendar

Monthly calendar grid. Each day cell shows content briefs due/published on that date.
- Brief cards appear as small colored dots or mini-cards in day cells
- Color = status
- Click day → see briefs for that day
- Navigate months with arrows

**For MVP:** Use a simple grid layout (7 columns × 5-6 rows). Don't use a heavy calendar library.

### View D: Cycles (Weekly Sprints)

Accessible from both the tab on main page and `/content-pipeline/cycles`.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Active Cycle: Week of Feb 24                                     │
│ Progress: ████████░░░░░░░░░░ 4/10 briefs (40%)                 │
│ [Add Brief to Cycle] [Complete Cycle]                            │
├─────────────────────────────────────────────────────────────────┤
│ Cycle Briefs:                                                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ✅ "How no-code builders compare to headless CMS"  Published│ │
│ │ ✅ "What is a design system in website tools"       Published│ │
│ │ 🔄 "Best platforms with enterprise SSO"             Review   │ │
│ │ 🔄 "No-code vs low-code for marketing sites"       Drafting │ │
│ │ ○  "Website performance core web vitals"            Approved │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Past Cycles:                                                      │
│ Week of Feb 17 — 8/8 (100%) ✅                                   │
│ Week of Feb 10 — 6/8 (75%) — 2 rolled over                      │
└─────────────────────────────────────────────────────────────────┘
```

**Cycle Logic:**
- Each cycle = 1 week (Monday-Sunday)
- Briefs not completed auto-rollover to next cycle
- Show cycle velocity (briefs/week trend)

### View E: Roadmap

Horizontal timeline showing content planned across weeks/months.
- X-axis: time (weeks)
- Y-axis: content types or clusters
- Bars represent briefs, colored by status
- Drag to adjust timeline (STRETCH GOAL)

**For MVP:** Simple horizontal bar chart using Recharts or a custom flex layout with week columns.

---

### 2. Brief Detail — `/content-pipeline/[briefId]`

**This is the most complex page. It's the HITL review experience.**

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│ ← Back to Pipeline                                                │
│ "How do no-code builders compare to headless CMS and Next.js?"   │
│ Status: Review | Cluster: C3 | Type: Blog | Citability: 85%     │
├─────────────────────────────────┬────────────────────────────────┤
│ Content Editor (Left, ~60%)     │ Intel Panel (Right, ~40%)      │
│                                  │                                 │
│ ┌──────────────────────────────┐│ ┌──────────────────────────┐   │
│ │  [Diff Toggle: OFF]          ││ │ Target Signals            │   │
│ │                              ││ │ Word Count: 1090-1110    │   │
│ │  Tiptap Rich Text Editor     ││ │ Reading Level: 12.0-14.6 │   │
│ │  with full formatting        ││ │ Headers: 12-15           │   │
│ │  toolbar                     ││ │ H2: 3, H3: 9            │   │
│ │                              ││ │ Patterns: Step-by-Step   │   │
│ │  Content renders here        ││ ├──────────────────────────┤   │
│ │  with markdown support       ││ │ Gap Score: 0.244          │   │
│ │                              ││ │ Classification: Sig. Gap  │   │
│ │                              ││ ├──────────────────────────┤   │
│ │                              ││ │ Eval Scores               │   │
│ │                              ││ │ Structural: 0.85 ✅       │   │
│ │                              ││ │ Semantic: 0.72 ✅         │   │
│ │                              ││ │ Style: 0.78 ✅            │   │
│ │                              ││ │ Factual: 0.81 ✅          │   │
│ │                              ││ ├──────────────────────────┤   │
│ │                              ││ │ Top Citation Exemplars    │   │
│ │                              ││ │ 1. thenewstack.io (0.81) │   │
│ │                              ││ │ 2. beecommerce.pl (0.78) │   │
│ │                              ││ │ [View in Lab →]           │   │
│ │                              ││ └──────────────────────────┘   │
│ └──────────────────────────────┘│                                 │
├─────────────────────────────────┴────────────────────────────────┤
│ Approval Bar                                                      │
│ [✓ Approve & Publish] [✎ Edit + Note] [✕ Reject → Save Draft]  │
└──────────────────────────────────────────────────────────────────┘
```

### Tiptap Editor Component

**`src/components/editor/tiptap-editor.tsx`:**

Full-featured Tiptap editor with:
- Formatting toolbar: Bold, Italic, Strikethrough, Code, H1-H4, Bullet List, Ordered List, Blockquote, Code Block, Horizontal Rule, Link
- Content loads from the brief's `final.md` artifact (fetched via API)
- Editable when status === 'review'
- Read-only when status === 'published'
- Changes tracked locally (not saved to backend until approval)

**Extensions to include:**
```typescript
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';
import Color from '@tiptap/extension-color';
import TextStyle from '@tiptap/extension-text-style';
```

### Diff Toggle Component

**`src/components/editor/diff-toggle.tsx`:**

A toggle button in the top-right of the editor area.

- **OFF (default):** Clean content view — just the formatted text
- **ON:** Inline diff comparing current stage to previous stage
  - **Red text with strikethrough** = removed from previous version
  - **Green text with highlight** = added in current version
  - Shows changes made by the evaluator-optimizer loop

**Implementation:**
1. Fetch two artifacts: current (`formatted.md` or `final.md`) and previous (`draft.md` or `enriched.md`)
2. Compute diff using a simple line-by-line comparison (or word-level for better granularity)
3. Render diff inline in the Tiptap editor using custom marks/decorations
4. Use `@tiptap/extension-highlight` with green background for additions
5. Use `@tiptap/extension-color` with red + strikethrough for deletions

**Simplification for MVP:** If real-time diff is too complex, show a split view instead — left = previous, right = current, with changed lines highlighted. Mark with `// TODO: upgrade to inline diff`.

### Intel Panel Component

**`src/components/editor/intel-panel.tsx`:**

Right sidebar showing intelligence context for the brief under review.

**Sections (scrollable):**

1. **Target Signals** — From the ContentBrief (word count range, reading level, header count, hierarchy, content patterns, authority type)

2. **Current Metrics** — Live metrics computed from the current content:
   - Current word count (vs target range — green if in range, red if outside)
   - Current header count
   - Current reading level estimate

3. **Gap Score** — Score + classification + interpretation text

4. **Evaluator Scores** — 4 dimensions from the evaluator-optimizer loop:
   - Structural Score (threshold ≥ 0.8)
   - Semantic Proximity (threshold ≥ 0.65)
   - Style Alignment (threshold ≥ 0.7)
   - Factual Grounding (threshold ≥ 0.7)
   - Each shows: score value, pass/fail indicator, threshold line

5. **Revision History** — If the content went through revision cycles, show:
   - Cycle 1: scores → failed (which dimensions) → revised
   - Cycle 2: scores → passed → ready for review

6. **Top Citation Exemplars** — Top 3 from the gap brief, with similarity score, domain, snippet

7. **Actions:**
   - "Open in Embedding Lab →" link
   - "View Gap Brief →" link
   - "Regenerate" button (triggers re-run of content workers for this brief)

### Approval Bar Component

**`src/components/editor/approval-bar.tsx`:**

Fixed bottom bar with three actions:

1. **✓ Approve & Publish** (primary button, sage green)
   - Calls `POST /api/v1/content/{run_id}/approve` with `{ brief_id, decision: "approve" }`
   - Navigates back to pipeline with success toast

2. **✎ Edit + Note** (secondary button)
   - Opens a text area for editor notes
   - Calls `POST /api/v1/content/{run_id}/approve` with `{ brief_id, decision: "edit", editor_notes }`
   - Brief goes back to workers for revision

3. **✕ Reject → Save Draft** (danger button)
   - Confirmation dialog: "Are you sure? This will save the content as a draft."
   - Calls `POST /api/v1/content/{run_id}/approve` with `{ brief_id, decision: "reject" }`
   - Brief status changes to `draft_saved`

---

### 3. Content Analytics — `/content-pipeline/analytics`

**Purpose:** Metrics and trends about content production.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Page Header: "Content Analytics"                                 │
├──────────┬──────────┬──────────┬──────────┐                     │
│ Published│ In Prog  │ Avg CS   │ Velocity │                     │
│   42     │   8      │  78%     │ 6.5/wk   │                     │
├──────────┴──────────┴──────────┴──────────┘                     │
├─────────────────────────────────────────────────────────────────┤
│ Content Type Breakdown (Donut Chart)                             │
│ Blogs: 65% | Guides: 20% | Case Studies: 10% | Product: 5%    │
├─────────────────────────────────────────────────────────────────┤
│ Citability Score Trend (Line Chart — last 8 weeks)              │
├─────────────────────────────────────────────────────────────────┤
│ Cycle Velocity (Bar Chart — briefs completed per week)          │
├─────────────────────────────────────────────────────────────────┤
│ Cluster Coverage Map                                             │
│ Heat grid showing which clusters have the most/least content    │
└─────────────────────────────────────────────────────────────────┘
```

Use Recharts for all analytics charts. Use the shared Card component for each section.

---

## Brief Card Component

**`content-pipeline/components/brief-card.tsx`:**

Used in Kanban board, table rows, and cycle lists.

```
┌────────────────────────────────────────┐
│ 📝 How do no-code builders compare...  │
│                                          │
│ [Blog] [C3: Category Comparison]        │
│                                          │
│ CS: ████████░░ 85%    1090 words        │
│                                          │
│ Updated 2 hours ago                      │
└────────────────────────────────────────┘
```

- Title: truncated to 2 lines max
- Type badge: content type with color
- Cluster badge: cluster name
- Citability Score: horizontal progress bar with percentage
  - Below threshold (< 70%): terracotta/orange, shows "⚠️ Low score — consider rerun"
  - Above threshold (≥ 70%): sage green
- Target word count from content brief
- Relative timestamp

### Citability Score Badge

**`content-pipeline/components/citability-score-badge.tsx`:**

The Citability Score is the Citation Prediction Model score — a percentage representing the probability that AI search engines will cite this content.

```typescript
interface CitabilityScoreBadgeProps {
  score: number;          // 0-100
  threshold?: number;     // default 70
  size?: 'sm' | 'md' | 'lg';
  showBar?: boolean;      // show progress bar
}
```

Color logic:
- 0-49: `error` (red) — "Low — needs significant improvement"
- 50-69: `warning` (orange) — "Below threshold — consider adjustments"
- 70-84: `sage-400` (green) — "Good — ready for review"
- 85-100: `sage-500` (dark green) — "Excellent — high citation probability"

---

## Pipeline Trigger Bar

**`content-pipeline/components/pipeline-trigger-bar.tsx`:**

When the user clicks "⚡ Generate from Gaps" in the page header:

1. Show a slide-over panel:
   - Company: {current company} (auto-filled)
   - Gap Slug: {current company slug}
   - Max Briefs: number input (default: 10)
   - Max Workers: number input (default: 3)
   - Auto-Approve: checkbox (default: false)
   - Skip Stages: checkbox group (1-4)
2. Submit → `POST /api/v1/content/start`
3. On 202: Show toast with "Content generation started" + link to pipeline view
4. SSE events will update brief statuses in real-time

---

## Zustand Store

**`src/stores/content-store.ts`:**
```typescript
interface ContentState {
  // View state
  activeView: 'board' | 'table' | 'calendar' | 'cycles' | 'roadmap';
  setActiveView: (view: ContentState['activeView']) => void;

  // Filters
  statusFilter: ContentBriefStatus | 'all';
  typeFilter: ContentType | 'all';
  clusterFilter: string | 'all';
  cycleFilter: string | 'all';
  searchQuery: string;
  setFilter: (key: string, value: string) => void;

  // Data
  briefs: ContentBriefItem[];
  setBriefs: (briefs: ContentBriefItem[]) => void;
  updateBrief: (id: string, updates: Partial<ContentBriefItem>) => void;

  // Cycles
  activeCycle: Cycle | null;
  pastCycles: Cycle[];
  setCycles: (active: Cycle | null, past: Cycle[]) => void;

  // Active brief (for editor)
  activeBriefId: string | null;
  setActiveBrief: (id: string | null) => void;
}
```

---

## API Endpoints You Use

| Endpoint | Where Used |
|----------|-----------|
| `POST /api/v1/content/start` | Trigger generation |
| `GET /api/v1/content/{run_id}/status` | Poll generation progress |
| `POST /api/v1/content/{run_id}/approve` | HITL approval |
| `GET /api/v1/tasks/{task_id}/events` | SSE progress stream |
| `GET /api/v1/artifacts/content/{slug}` | List content files |
| `GET /api/v1/artifacts/content/{slug}/briefs.json` | Load brief list |
| `GET /api/v1/artifacts/content/{slug}/content/brief-{N}/final.md` | Load brief content |
| `GET /api/v1/artifacts/content/{slug}/content/brief-{N}/eval_history.json` | Load eval scores |
| `GET /api/v1/artifacts/content/{slug}/content/brief-{N}/formatted.md` | Load formatted (for diff) |
| `GET /api/v1/artifacts/content/{slug}/content/brief-{N}/draft.md` | Load draft (for diff) |
| `GET /api/v1/artifacts/gap_analysis/{slug}/gap_report.json` | Gap data for intel panel |
| `GET /api/v1/tasks?status=pending_approval` | Find briefs needing review |

---

## Acceptance Criteria

- [ ] `/content-pipeline` renders with view switcher (Board is default)
- [ ] Kanban board shows columns with brief cards
- [ ] Table view renders sortable columns
- [ ] Calendar view shows a month grid with brief indicators
- [ ] Cycles view shows active cycle with progress + past cycles
- [ ] View switcher changes view without page reload
- [ ] Filter bar filters briefs by status, type, cluster
- [ ] Brief detail page renders with Tiptap editor (left) + Intel panel (right)
- [ ] Diff toggle switches between clean and diff view (MVP: split view is acceptable)
- [ ] Approval bar with 3 buttons calls correct API endpoints
- [ ] Citability Score badge renders with correct color coding
- [ ] Analytics page shows 4 metric cards + charts
- [ ] "Generate from Gaps" triggers content pipeline
- [ ] All components use sage-green accent for this section (see brand Phase Color Mapping)
- [ ] No TypeScript errors
