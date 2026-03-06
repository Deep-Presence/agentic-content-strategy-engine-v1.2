# Frontend Dashboard — Architecture Overview

> **Last Updated:** 2026-02-25
> **Location:** `frontend-dashboard/`
> **Stack:** Next.js 16.1 · React 19 · Tailwind CSS 4 · Zustand 5 · Supabase SSR · D3 · Recharts · TipTap

---

## Table of Contents

1. [Identity & Isolation](#1-identity--isolation)
2. [Tech Stack](#2-tech-stack)
3. [Directory Structure](#3-directory-structure)
4. [Integration Map](#4-integration-map)
5. [Backend API Integration](#5-backend-api-integration)
6. [Supabase Integration](#6-supabase-integration)
7. [Page Routes](#7-page-routes)
8. [State Management (Zustand)](#8-state-management-zustand)
9. [Custom Hooks](#9-custom-hooks)
10. [SSE Real-Time Data Flow](#10-sse-real-time-data-flow)
11. [TypeScript Types](#11-typescript-types)
12. [Design System](#12-design-system)
13. [Mock Data Strategy](#13-mock-data-strategy)
14. [Authentication](#14-authentication)
15. [Constants & Utilities](#15-constants--utilities)
16. [Current Limitations](#16-current-limitations)

---

## 1. Identity & Isolation

The frontend is a **completely self-contained Next.js 16.1 project** at `frontend-dashboard/`. It has its own `package.json`, `node_modules/`, and `tsconfig.json`. It shares **zero files** with the Python backend.

### Hard Isolation Rules

- The **only interface** between `frontend-dashboard/` and the rest of the project is the **HTTP API** (`http://localhost:8000/api/v1/*`).
- No Python imports, no shared types, no filesystem paths, no build-time coupling.
- Never import from or reference `core/`, `api/`, or `artifacts/` directly.
- `frontend-dashboard/` is deletable with `rm -rf frontend-dashboard/` — the rest of the project remains 100% functional.

---

## 2. Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | **Next.js 16.1 + React 19** | App Router, Server Components, streaming |
| Styling | **Tailwind CSS 4** | Utility-first, custom theme tokens via CSS vars |
| Components | **shadcn/ui** | Unstyled primitives restyled to warm editorial theme |
| State | **Zustand 5.0** | Lightweight, 4 stores, works with SSE push updates |
| Auth | **@supabase/ssr 0.8** | Server-side session management (not enforced yet) |
| Charts | **D3 7.9 + Recharts 3.7** | UMAP/t-SNE/heatmaps (D3), bar/line charts (Recharts) |
| Editor | **TipTap 3.20** | Rich text editing for brand artifacts |
| Markdown | **react-markdown + rehype-sanitize + remark-gfm** | Artifact rendering with XSS prevention |
| Icons | **Lucide React** | Clean, consistent iconography |
| HTTP | **Native fetch + EventSource** | No axios — SSE streaming via EventSource API |
| Fonts | **Source Serif 4 (headings) + Lora (body) + SF Mono (code)** | Serif-forward editorial design |

### Dependencies (18 total)

```
next 16.1.6, react 19.2.3, zustand 5.0.11
@supabase/supabase-js 2.97.0, @supabase/ssr 0.8.0
@tiptap/react 3.20.0, @tiptap/starter-kit 3.20.0
recharts 3.7.0, d3 7.9.0, @types/d3 7.4.3
tailwindcss 4, date-fns 4.1.0, lucide-react 0.575.0
react-markdown 10.1.0, rehype-sanitize 6.0.0, remark-gfm 4.0.1
clsx 2.1.1, tailwind-merge 3.5.0, class-variance-authority 0.7.1
```

### Scripts

```bash
cd frontend-dashboard
npm run dev         # Start dev server (port 3000)
npm run build       # Production build
npm start           # Start production server
npm run lint        # ESLint check
```

---

## 3. Directory Structure

```
frontend-dashboard/
├── package.json                           # 18 deps, 6 devDeps
├── tsconfig.json                          # Strict mode, @/* path alias
├── next.config.ts                         # Empty (defaults)
├── postcss.config.mjs                     # Tailwind v4 via PostCSS
├── .env.local                             # Supabase + API URL config
│
├── src/
│   ├── app/                               # Next.js App Router
│   │   ├── layout.tsx                     # Root layout (ToastProvider)
│   │   ├── page.tsx                       # Redirect → /command-center
│   │   ├── globals.css                    # Tailwind v4 theme + CSS custom props
│   │   │
│   │   ├── (auth)/
│   │   │   ├── layout.tsx
│   │   │   └── login/page.tsx             # Placeholder login form
│   │   │
│   │   └── (dashboard)/                   # All main routes
│   │       ├── layout.tsx                 # Sidebar + TopBar + company fetch
│   │       ├── command-center/page.tsx    # Mission Control
│   │       ├── signal-analysis/           # 6-tab gap analysis workspace
│   │       │   ├── page.tsx               # Main tabbed view
│   │       │   ├── run/page.tsx           # Launch new gap analysis
│   │       │   ├── [runId]/page.tsx       # View run results
│   │       │   ├── briefs/page.tsx
│   │       │   ├── components/            # 20+ chart/UI components
│   │       │   ├── data/sample-data.ts
│   │       │   └── loading.tsx
│   │       ├── embedding-lab/             # Interactive visualizations
│   │       │   ├── page.tsx
│   │       │   ├── components/            # 10+ D3/Recharts components
│   │       │   ├── data/webflow-sample.ts
│   │       │   └── loading.tsx
│   │       ├── content-pipeline/          # Content management
│   │       │   ├── page.tsx               # Board/Table/Calendar view
│   │       │   ├── [briefId]/page.tsx     # Brief detail
│   │       │   ├── analytics/page.tsx
│   │       │   ├── cycles/page.tsx
│   │       │   ├── roadmap/page.tsx
│   │       │   ├── components/            # 15+ board/table/list components
│   │       │   └── loading.tsx
│   │       ├── brand-brain/               # Research artifacts
│   │       │   ├── page.tsx               # Projects overview
│   │       │   ├── projects/[projectId]/page.tsx
│   │       │   ├── personas/page.tsx
│   │       │   ├── knowledge/page.tsx
│   │       │   ├── style-guide/page.tsx
│   │       │   ├── components/            # 15+ editors + viewers
│   │       │   ├── data/mock-artifacts.ts
│   │       │   └── loading.tsx
│   │       ├── settings/
│   │       │   ├── page.tsx
│   │       │   ├── account/page.tsx
│   │       │   ├── api-keys/page.tsx
│   │       │   └── usage/page.tsx
│   │       └── loading.tsx
│   │
│   ├── components/                        # Reusable components
│   │   ├── ui/                            # shadcn/ui primitives (restyled)
│   │   │   ├── button.tsx, card.tsx, dialog.tsx, dropdown-menu.tsx
│   │   │   ├── input.tsx, select.tsx, sidebar.tsx, tabs.tsx
│   │   │   ├── toast.tsx, tooltip.tsx, badge.tsx, avatar.tsx
│   │   │   ├── progress.tsx, separator.tsx, skeleton.tsx, table.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── sidebar-nav.tsx            # Main navigation (6 routes)
│   │   │   ├── top-bar.tsx                # Page title + search + notifications
│   │   │   └── page-header.tsx
│   │   │
│   │   ├── charts/                        # D3 + Recharts visualizations
│   │   │   ├── umap-scatter.tsx, tsne-scatter.tsx
│   │   │   ├── gap-heatmap.tsx, cluster-radar.tsx, cluster-boxplot.tsx
│   │   │   ├── citation-treemap.tsx, signal-inspector.tsx
│   │   │   ├── similarity-histogram.tsx, company-vs-citation.tsx
│   │   │   └── citation-explorer.tsx
│   │   │
│   │   ├── editor/
│   │   │   ├── tiptap-editor.tsx          # Rich text editor
│   │   │   ├── approval-bar.tsx           # HITL approve/reject controls
│   │   │   ├── diff-toggle.tsx
│   │   │   └── intel-panel.tsx
│   │   │
│   │   └── pipeline/
│   │       ├── pipeline-progress.tsx
│   │       ├── spa-score-card.tsx
│   │       ├── cluster-breakdown.tsx
│   │       └── gap-brief-card.tsx
│   │
│   ├── lib/
│   │   ├── api/                           # HTTP clients (→ backend)
│   │   │   ├── client.ts                  # Base ApiClient (GET/POST)
│   │   │   ├── sse.ts                     # EventSource wrapper
│   │   │   ├── gap-analysis.ts            # Gap analysis endpoints
│   │   │   ├── research.ts               # Research pipeline endpoints
│   │   │   ├── content.ts                # Content generation endpoints
│   │   │   ├── tasks.ts                  # Task polling/cancellation
│   │   │   └── artifacts.ts              # Artifact file retrieval
│   │   │
│   │   ├── supabase/                      # Auth (configured, not enforced)
│   │   │   ├── client.ts                  # Browser Supabase client
│   │   │   ├── server.ts                  # Server-side Supabase client
│   │   │   └── middleware.ts              # Session refresh
│   │   │
│   │   ├── hooks/
│   │   │   ├── use-event-stream.ts        # SSE listener with reconnect
│   │   │   ├── use-tasks.ts               # Task polling (5s interval)
│   │   │   ├── use-artifacts.ts           # Artifact file/content loading
│   │   │   └── use-count-up.ts            # Number animation
│   │   │
│   │   ├── utils/
│   │   │   ├── constants.ts               # NAV_ITEMS, STATUS_COLORS
│   │   │   ├── format.ts                  # Date/number formatters
│   │   │   └── cn.ts                      # className merge utility
│   │   │
│   │   └── data/
│   │       └── webflow-fixtures.ts        # Large mock data for demos
│   │
│   ├── stores/                            # Zustand state management
│   │   ├── app-store.ts                   # Company selector, sidebar
│   │   ├── pipeline-store.ts              # Gap analysis run state
│   │   ├── content-store.ts               # Content filters + briefs
│   │   └── brand-store.ts                 # Research artifacts + projects
│   │
│   ├── types/                             # TypeScript interfaces
│   │   ├── api.ts                         # Re-exports all types
│   │   ├── common.ts                      # TaskStatus, Pipeline, responses
│   │   ├── gap-analysis.ts                # GapReport, GapBrief, ClusterSpec
│   │   ├── research.ts                    # ResearchStartInput, approval
│   │   ├── content.ts                     # ContentBriefItem, Cycle
│   │   └── brand.ts                       # Project, Persona, KnowledgeDoc
│   │
│   └── middleware.ts                      # Supabase session middleware
```

---

## 4. Integration Map

```
┌──────────────────────────────────────────────────────────────────┐
│                      Frontend Dashboard                          │
│                    (Next.js 16 + React 19)                       │
│                                                                  │
│  ┌───────────┐  ┌────────────┐  ┌───────────┐  ┌────────────┐  │
│  │ App Store │  │  Pipeline  │  │  Content  │  │   Brand    │  │
│  │ (Zustand) │  │   Store    │  │   Store   │  │   Store    │  │
│  └─────┬─────┘  └─────┬──────┘  └─────┬─────┘  └─────┬──────┘  │
│        │               │               │               │         │
│  ┌─────┴───────────────┴───────────────┴───────────────┴──────┐  │
│  │                src/lib/api/ (HTTP Clients)                  │  │
│  │  client.ts · gap-analysis.ts · research.ts · content.ts    │  │
│  │  tasks.ts · artifacts.ts · sse.ts                          │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────┼───────────────────────────────────┐  │
│  │   src/lib/supabase/    │  (Auth — NOT ACTIVE)              │  │
│  │   client.ts · server.ts · middleware.ts                    │  │
│  └────────────────────────┼───────────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────────┘
                            │ HTTP + SSE
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│               FastAPI Backend (localhost:8000)                    │
│                                                                  │
│  /api/v1/gap-analysis/*    → Gap Analysis Pipeline (s1-s8)       │
│  /api/v1/research/*        → Research Pipeline (LangGraph HITL)  │
│  /api/v1/content/*         → Content Engine (4-stage)            │
│  /api/v1/tasks/*/events    → SSE Streaming (real-time progress)  │
│  /api/v1/artifacts/*       → File Serving (MD, JSON, HTML)       │
│  /health, /readiness       → Health Checks                       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Python Core                                                     │
│  ├── LLM APIs (OpenAI, Anthropic, Google, Perplexity)           │
│  ├── ChromaDB (local vector storage)                            │
│  ├── Local Filesystem (artifacts/ — source of truth)            │
│  ├── Supabase Mirror (optional DB sync)                         │
│  └── Langfuse Tracing (LLM observability)                       │
└──────────────────────────────────────────────────────────────────┘
```

**Key point:** The frontend is a **pure HTTP consumer**. It never touches the database, filesystem, or LLM APIs directly.

---

## 5. Backend API Integration

### API Client Architecture

All communication lives in `src/lib/api/`:

#### Base Client (`client.ts`)

```typescript
class ApiClient {
  private baseUrl: string  // from NEXT_PUBLIC_API_URL

  async get<T>(path: string): Promise<T>
  async post<T>(path: string, body?: unknown): Promise<T>
  getBaseUrl(): string
}

export const api = new ApiClient(process.env.NEXT_PUBLIC_API_URL)
```

Throws `ApiError(status, message, code?)` on non-2xx responses.

#### Gap Analysis (`gap-analysis.ts`)

```typescript
export const gapAnalysis = {
  start(input: GapAnalysisStartInput): Promise<PipelineRunResponse>
  getStatus(runId: string): Promise<PipelineRunResponse>
}
```

#### Research (`research.ts`)

```typescript
export const research = {
  start(input: ResearchStartInput): Promise<PipelineRunResponse>
  getStatus(runId: string): Promise<PipelineRunResponse>
  approve(runId: string, approval: ResearchApproval): Promise<{ status: string }>
}
```

#### Content (`content.ts`)

```typescript
export const content = {
  start(input: ContentStartInput): Promise<PipelineRunResponse>
  getStatus(runId: string): Promise<PipelineRunResponse>
  approve(runId: string, approval: ContentApproval): Promise<{ status: string }>
}
```

#### Tasks (`tasks.ts`)

```typescript
export const tasks = {
  list(params?: { status?: string }): Promise<TaskListResponse>
  get(taskId: string): Promise<TaskResponse>
  cancel(taskId: string): Promise<{ status: string }>
}
```

#### Artifacts (`artifacts.ts`)

```typescript
export const artifacts = {
  listCompanies(): Promise<CompaniesResponse>
  listFiles(type: ArtifactType, slug: string): Promise<ArtifactFilesResponse>
  getContent<T>(type: ArtifactType, slug: string, filename: string): Promise<T>
}
```

#### SSE Streaming (`sse.ts`)

```typescript
export function createEventStream(
  taskId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError?: (error: Event) => void
): () => void  // Returns cleanup function
```

Creates `EventSource` to `{API_BASE}/api/v1/tasks/{taskId}/events`. Parses JSON event payloads and heartbeats. Returns a cleanup function to close the connection.

### Full Endpoint Map

| Method | Path | Frontend Client | Purpose |
|--------|------|----------------|---------|
| `GET` | `/health` | — | Health check |
| `GET` | `/readiness` | — | API key readiness |
| `POST` | `/api/v1/gap-analysis/start` | `gapAnalysis.start()` | Launch gap analysis (202) |
| `GET` | `/api/v1/gap-analysis/{run_id}/status` | `gapAnalysis.getStatus()` | Poll status |
| `POST` | `/api/v1/research/start` | `research.start()` | Launch research pipeline (202) |
| `GET` | `/api/v1/research/{run_id}/status` | `research.getStatus()` | Poll research status |
| `POST` | `/api/v1/research/{run_id}/approve` | `research.approve()` | HITL approval |
| `POST` | `/api/v1/content/start` | `content.start()` | Launch content gen (202) |
| `GET` | `/api/v1/content/{run_id}/status` | `content.getStatus()` | Poll content status |
| `POST` | `/api/v1/content/{run_id}/approve` | `content.approve()` | Per-brief HITL approval |
| `GET` | `/api/v1/tasks/{task_id}/events` | `createEventStream()` | SSE streaming |
| `GET` | `/api/v1/tasks` | `tasks.list()` | List all tasks |
| `GET` | `/api/v1/tasks/{task_id}` | `tasks.get()` | Get task detail |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | `tasks.cancel()` | Cancel running task |
| `GET` | `/api/v1/artifacts/companies` | `artifacts.listCompanies()` | List company slugs |
| `GET` | `/api/v1/artifacts/{type}/{slug}` | `artifacts.listFiles()` | List artifact files |
| `GET` | `/api/v1/artifacts/{type}/{slug}/{filename}` | `artifacts.getContent()` | Get file content |

---

## 6. Supabase Integration

Three files in `src/lib/supabase/`:

| File | Purpose | Current Status |
|------|---------|----------------|
| `client.ts` | Browser-side `createBrowserClient()` | **Configured, not used** |
| `server.ts` | Server Components `createServerClient()` | **Configured, not used** |
| `middleware.ts` | Session token refresh per request | **Wired in middleware.ts, runs but no-op** |

### Environment Variables

```env
NEXT_PUBLIC_SUPABASE_URL=https://xojlzytyekwksqdmvwmc.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Current Role

- **Auth infrastructure is ready** but **not enforced**
- No routes are protected — everything is publicly accessible
- Login page (`/login`) is a placeholder with no form submission
- The frontend does **NOT** read/write data to Supabase tables directly
- All data flows exclusively through the backend REST API
- Supabase Realtime subscriptions are **not implemented**

### Future Role

- User authentication (email/password, OAuth)
- Route protection via middleware session checks
- Potentially: realtime collaboration via Supabase Realtime channels

---

## 7. Page Routes

### Route Map

```
/                              → Redirects to /command-center
├── /command-center            → Mission Control (executive dashboard)
├── /signal-analysis           → Deep Signal Analysis (6-tab workspace)
│   ├── /signal-analysis/run   → Launch new gap analysis form
│   ├── /signal-analysis/[runId] → View specific run results
│   └── /signal-analysis/briefs  → Content briefs from gap analysis
├── /embedding-lab             → Interactive D3/Recharts visualization workspace
├── /content-pipeline          → Content management (board/table/calendar)
│   ├── /content-pipeline/[briefId]  → Brief detail view
│   ├── /content-pipeline/analytics  → Performance analytics
│   ├── /content-pipeline/cycles     → Content cycles management
│   └── /content-pipeline/roadmap    → Timeline roadmap view
├── /brand-brain               → Research artifacts overview
│   ├── /brand-brain/projects/[projectId] → Project detail
│   ├── /brand-brain/personas  → Persona card list + editor
│   ├── /brand-brain/knowledge → Knowledge docs management
│   └── /brand-brain/style-guide → Style guide viewer/editor
├── /settings                  → Settings hub
│   ├── /settings/account      → Account info (placeholder)
│   ├── /settings/api-keys     → API key management
│   └── /settings/usage        → Usage/quota display
└── /login                     → Placeholder auth page
```

### Page Details

#### Command Center (`/command-center`)

Executive overview dashboard with:
1. Hero Health Bar — Citability score, SPA score, published content count
2. 12-week Visibility Trend chart + Pipeline Status panel
3. 4-platform performance grid (ChatGPT, Claude, Perplexity, Gemini) with sparklines
4. Cluster health matrix heatmap
5. Priority Actions + Activity Feed (side-by-side)
6. Content Performance Row (citability/velocity trends)
7. Competitive Snapshot (8 top competitors by similarity)
8. Quick Links footer

**Data source:** `WEBFLOW_GAP_REPORT` fixture (mock data).

#### Deep Signal Analysis (`/signal-analysis`)

6-tab analytical workspace:

| Tab | Content |
|-----|---------|
| **Overview** | SPA score, gap classifications, cluster heatmap, citation advantage, platform donuts |
| **Query Intelligence** | Master table of 150 queries + distribution charts |
| **Structural Signals** | Signal categories, importance ranking, fingerprints, content patterns |
| **Platform Intelligence** | Cross-platform comparison, agreement matrix, trend chart |
| **Content Briefs** | Priority matrix, brief cards, cluster recommendations |
| **Run History** | Past gap analysis runs table |

Launch form at `/signal-analysis/run` POSTs to `/api/v1/gap-analysis/start`.

#### Embedding Lab (`/embedding-lab`)

Interactive visualization workspace with:
- UMAP/t-SNE scatter plots (semantic space)
- Gap heatmap
- Cluster radar chart + boxplot
- Citation treemap + source explorer
- Signal inspector
- Similarity histogram
- Company vs citation comparison

#### Content Pipeline (`/content-pipeline`)

Content management with multiple views:
- **Board view** — Kanban-style drag columns
- **Table view** — Sortable/filterable data table
- **Calendar view** — Timeline calendar
- **Cycles view** — Sprint-like content cycles
- **Roadmap view** — Timeline roadmap

Filters: status, content type, cluster, cycle, search query.

#### Brand Brain (`/brand-brain`)

Research artifacts management:
- **Projects** — CRUD project entities
- **Personas** — Persona card list + TipTap editor
- **Knowledge** — Knowledge docs (brand guidelines, product context, etc.)
- **Style Guide** — Style guide viewer/editor
- **Research trigger** — Launch research pipeline + HITL approval inline

---

## 8. State Management (Zustand)

### App Store (`stores/app-store.ts`)

```typescript
{
  currentCompany: string              // Selected company slug
  setCurrentCompany: (slug) => void
  companies: string[]                 // Available companies
  setCompanies: (companies) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
}
```

### Pipeline Store (`stores/pipeline-store.ts`)

```typescript
{
  // Active run
  activeRunId: string | null
  activeRunStatus: TaskStatus | null

  // Steps tracking (8 gap analysis steps)
  steps: StepState[]                  // { key, status, startedAt?, completedAt? }
  currentStep: GapAnalysisStep | null

  // Results
  gapReport: GapReport | null
  clusterSpecs: ClusterSpec[]
  gapBriefs: GapBrief[]

  // Filtering & sorting
  selectedCluster: string | null
  briefClassificationFilter: string
  briefSortField: string
  briefSortDirection: 'asc' | 'desc'

  // Actions
  setActiveRun(runId, status)
  updateStep(step, status)
  setResults(report, specs, briefs)
  setSelectedCluster(cluster)
  setBriefClassificationFilter(filter)
  setBriefSort(field, direction)
  reset()
}
```

### Content Store (`stores/content-store.ts`)

```typescript
{
  // View mode
  activeView: 'board' | 'table' | 'calendar' | 'cycles' | 'roadmap'
  setActiveView(view)

  // Filters
  statusFilter: ContentBriefStatus | 'all'
  typeFilter: ContentType | 'all'
  clusterFilter: string | 'all'
  cycleFilter: string | 'all'
  searchQuery: string
  setFilter(key, value)

  // Data
  briefs: ContentBriefItem[]
  setBriefs(briefs)
  updateBrief(id, updates)

  // Cycles
  activeCycle: Cycle | null
  pastCycles: Cycle[]
  setCycles(active, past)

  // UI
  activeBriefId: string | null
  setActiveBrief(id)
}
```

### Brand Store (`stores/brand-store.ts`)

```typescript
{
  // Artifacts
  companyContext: string | null
  companyContextStatus: 'none' | 'draft' | 'approved'
  personas: Persona[]
  styleGuide: string | null
  styleGuideStatus: 'none' | 'draft' | 'approved'

  // Knowledge
  knowledgeDocs: KnowledgeDoc[]

  // Projects
  projects: Project[]

  // Research pipeline
  activeResearchRunId: string | null
  activeResearchStatus: TaskStatus | null
  activeResearchStage: ResearchStage | null
  approvalPayload: Record<string, unknown> | null

  // Actions
  setCompanyContext(content, status)
  setPersonas(personas)
  addPersona / removePersona
  setStyleGuide(content, status)
  setKnowledgeDocs / addKnowledgeDoc / updateKnowledgeDoc / removeKnowledgeDoc
  setProjects / addProject / removeProject
  setResearchRun(runId, status, stage)
  setApprovalPayload(payload)
  clearResearchRun()
  reset()
}
```

---

## 9. Custom Hooks

### `useEventStream` — SSE Listener

```typescript
useEventStream(taskId: string | null, options?: {
  onEvent?: (event: string, data: Record<string, unknown>) => void
  autoConnect?: boolean
})

Returns: {
  connected: boolean
  events: Array<{ event, data, timestamp }>
  lastEvent: string | null
  error: string | null
  connect: () => void
  disconnect: () => void
}
```

- Auto-connects when `taskId` changes (if `autoConnect = true`)
- Reconnects on error with manual controls
- Maintains full event history

### `useTasks` — Task Polling

```typescript
useTasks(options?: {
  status?: string
  pollInterval?: number   // Default: 5000ms
  autoRefresh?: boolean   // Default: true
})

Returns: {
  tasks: TaskResponse[]
  total: number
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}
```

- Polls every 5s if tasks are running
- Auto-stops polling when no running tasks
- Cleanup on unmount

### `useArtifactFiles` / `useArtifactContent` — Artifact Loading

```typescript
useArtifactFiles(type: ArtifactType, slug: string)
→ { files: string[], loading, error }

useArtifactContent<T>(type: ArtifactType, slug: string, filename: string)
→ { data: T | null, loading, error }
```

- Skips fetch if slug is empty
- Cancellation cleanup for unmounted components

### `useCountUp` — Number Animation

- Animates numbers from 0 to target value
- Used in hero metric cards on Command Center

---

## 10. SSE Real-Time Data Flow

```
User clicks "Run Gap Analysis"
        │
        ├── POST /api/v1/gap-analysis/start
        │   └── Backend returns { run_id } (202 Accepted)
        │
        ├── useEventStream(run_id) opens EventSource connection
        │   │
        │   │   Backend SSE Events:
        │   ├── pipeline_start      → Show progress bar, set status "running"
        │   ├── stage_start         → Update step indicator to active
        │   ├── stage_complete      → Mark step as done (checkmark)
        │   ├── pending_approval    → Show HITL approval controls
        │   ├── approval_received   → Collapse approval UI, continue
        │   ├── completed           → Fill progress to 100%, fetch results
        │   ├── failed              → Show error message
        │   └── cancelled           → Show cancelled state
        │
        └── On "completed"
            ├── GET /api/v1/artifacts/gap_analysis/{slug}/ → List result files
            ├── GET /api/v1/artifacts/gap_analysis/{slug}/gap_report.json
            ├── Render charts, briefs, cluster specs
            └── Close EventSource connection
```

### SSE Connection Details

- **Endpoint:** `GET /api/v1/tasks/{task_id}/events`
- **Protocol:** Server-Sent Events (EventSource API)
- **Heartbeat:** 15s keepalive from backend
- **Reconnect:** `Last-Event-ID` header for resume
- **Cleanup:** Hook closes EventSource on component unmount

---

## 11. TypeScript Types

All types are in `src/types/` and re-exported via `src/types/api.ts`.

### Common Types (`common.ts`)

```typescript
type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'
                | 'cancelled' | 'pending_approval' | 'failed_restart'

type Pipeline = 'research' | 'gap_analysis' | 'content'

interface TaskResponse {
  run_id: string
  pipeline: Pipeline
  company_slug: string
  status: TaskStatus
  current_step: string | null
  progress_pct: number | null
  created_at: string
  updated_at: string
  result: Record<string, unknown> | null
  error: string | null
  approval_payload: Record<string, unknown> | null
}

interface PipelineRunResponse {
  run_id: string
  pipeline: Pipeline
  company_slug: string
  status: string
  created_at: string
}

interface TaskListResponse { tasks: TaskResponse[]; total: number }
interface CompaniesResponse { companies: string[] }
interface ArtifactFilesResponse { type: string; slug: string; files: string[] }
```

### Gap Analysis Types (`gap-analysis.ts`)

```typescript
interface GapAnalysisStartInput {
  input_data: {
    company_name: string
    domain: string
    seed_urls: string[]
    company_slug?: string
  }
  skip_steps?: number[]
}

interface GapReport {
  executive_summary: string
  spa_score: { t_statistic, p_value, citation_advantage, company_advantage }
  clusters: ClusterSpec[]
  top_gaps: GapBrief[]
  total_queries: number
  total_citations: number
}

interface GapBrief {
  query_id, query_text, cluster, cluster_id: string
  gap_score: number
  gap_classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins'
  best_company_unit: { unit_id, similarity, snippet }
  avg_citation_similarity: number
  content_brief: ContentBrief
  top_exemplars: CitationExemplar[]
}

interface ClusterSpec {
  cluster_id, cluster_name: string
  query_count, citations_analyzed: number
  word_count_range: { min, max }
  required_elements: string[]
  structural_rates: { headers, lists, stats, citations }
  dominant_content_type, dominant_authority_type: string
  exemplar_themes: string[]
}

type GapAnalysisStep = 's1_embed_assets' | 's2_generate_queries' | 's3_search_platforms'
                     | 's4_enrich_citations' | 's5_embed_content' | 's6_analyze'
                     | 's7_visualize' | 's8_generate_report'
```

### Research Types (`research.ts`)

```typescript
interface ResearchStartInput {
  company_name: string
  domain: string
  seed_urls?: string[]
  stages?: ('company' | 'persona' | 'style')[]
  max_personas?: number
  auto_approve?: boolean
}

interface ResearchApproval {
  decision: 'approve' | 'revise' | 'reject'
  revision_note?: string
}

type ResearchStage = 'company' | 'persona' | 'style_guide'
```

### Content Types (`content.ts`)

```typescript
interface ContentStartInput {
  company_name: string
  domain: string
  gap_slug?: string
  max_briefs?: number
  auto_approve?: boolean
}

interface ContentApproval {
  brief_id: string
  decision: 'approve' | 'edit' | 'reject'
  editor_notes?: string
}

type ContentBriefStatus = 'suggested' | 'approved' | 'research' | 'drafting'
                        | 'enriching' | 'formatting' | 'evaluating' | 'review'
                        | 'published' | 'draft_saved' | 'rejected'

type ContentType = 'blog' | 'guide' | 'case_study' | 'product_page'
```

### Brand Types (`brand.ts`)

```typescript
interface Project { id, name, slug, description?, personas, style_guide?, knowledge_docs, created_at }
interface Persona { id, name, type: 'icp' | 'secondary', content, project_id? }
interface KnowledgeDoc { id, title, type, content, project_id? }
```

---

## 12. Design System

### Design Identity: "Warm Editorial"

Inspired by **claude.ai + hex.tech + Notion** — warm, editorial, serif-forward with terracotta accents on a cream canvas. Feels like a premium design tool that reads like a beautifully typeset document.

### Color Palette

#### Cream (Neutral Base)
| Token | Hex | Usage |
|-------|-----|-------|
| `cream-50` | `#fefdfb` | Lightest background |
| `cream-100` | `#faf9f5` | Primary background |
| `cream-200` | `#f5f3ee` | Card backgrounds |
| `cream-300` | `#efeee8` | Subtle borders |
| `cream-400` | `#e8e6dc` | Muted borders |
| `cream-500` | `#d4d1c7` | Disabled text |
| `cream-600` | `#b0aea5` | Placeholder text |
| `cream-700` | `#8a8780` | Tertiary text |
| `cream-800` | `#6b6960` | Secondary text |
| `cream-900` | `#4a4840` | Primary text |
| `cream-950` | `#141413` | Near-black text |

#### Terracotta (Primary Accent)
| Token | Hex | Usage |
|-------|-----|-------|
| `terracotta-50` | `#fdf3ec` | Light tinted background |
| `terracotta-400` | `#d97757` | **Primary action color** (CTAs, active states) |
| `terracotta-500` | `#c4593a` | Hover state |
| `terracotta-600+` | darker | Pressed states |

#### Semantic Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `sage-400` | `#788c5d` | Success / approved / completed |
| `ocean-400` | `#6a9bcc` | Info / running / informational |
| `warning` | `#e8926d` | Warning states |
| `error` | `#c44040` | Error / failed states |

### Status Badge Colors

```typescript
STATUS_COLORS = {
  pending:          'bg-cream-400 text-cream-800'
  running:          'bg-ocean-50 text-ocean-500'
  completed:        'bg-sage-50 text-sage-500'
  failed:           'bg-error/10 text-error'
  cancelled:        'bg-cream-300 text-cream-700'
  pending_approval: 'bg-terracotta-50 text-terracotta-500'
}
```

### Typography

| Level | Font | Size |
|-------|------|------|
| Display | Source Serif 4 | 2.25rem |
| Heading 1 | Source Serif 4 | 1.75rem |
| Heading 2 | Source Serif 4 | 1.375rem |
| Heading 3 | Source Serif 4 | 1.125rem |
| Body | Lora | 0.875rem |
| Body Large | Lora | 0.9375rem |
| Body Small | Lora | 0.8125rem |
| Caption | Lora | 0.75rem |
| Code | SF Mono / Fira Code | 0.875rem |

### Design Principles

1. **Serif everywhere** — Source Serif 4 for headings, Lora for body. Mono only for code/IDs.
2. **Warm, never cold** — No pure `#fff` or `#000`. Everything has a warm undertone.
3. **Terracotta is the accent only** — CTAs, active states, progress bars. Never for large backgrounds.
4. **Borders over shadows** — `border-cream-300` (1px) for separation. Shadows only on floating elements.
5. **Generous whitespace** — Minimum 24px padding on containers, 16px gaps.

### Shadows

```
sm:  0 1px 2px rgba(20,20,19, 0.04)
md:  0 2px 8px rgba(20,20,19, 0.06)
lg:  0 4px 16px rgba(20,20,19, 0.08)
xl:  0 8px 32px rgba(20,20,19, 0.10)
```

---

## 13. Mock Data Strategy

A large fixtures file at `src/lib/data/webflow-fixtures.ts` provides comprehensive mock data for a "Webflow" company demo:

- `WEBFLOW_GAP_REPORT` — Full gap analysis report
- `WEBFLOW_PIPELINE_BRIEFS` — Content pipeline briefs
- `WEBFLOW_TASKS` — Sample task list
- `WEBFLOW_CLUSTERS` — Cluster specs
- `WEBFLOW_TOP_GAPS` — Top gap briefs

### Fallback Behavior

When the backend API is unavailable:
1. Pages catch fetch errors gracefully
2. Fall back to fixture data for rendering
3. Enables fully offline development and demos

### Usage

```typescript
// In page components:
const data = apiAvailable ? await gapAnalysis.getStatus(runId) : WEBFLOW_GAP_REPORT
```

---

## 14. Authentication

### Current State

| Aspect | Status |
|--------|--------|
| Supabase client configured | Yes |
| Login page exists | Yes (placeholder, no submission) |
| Route protection | None |
| Auth middleware | Runs but doesn't block |
| Backend auth checks | None |
| User sessions | Not tracked |

### Middleware Flow (No-Op Currently)

```
Request → middleware.ts → updateSession()
           │
           ├── Creates Supabase server client
           ├── Calls getUser() (refreshes token if exists)
           ├── Updates cookies if needed
           └── Passes request through (no blocking)
```

### Matcher Config

```typescript
// Runs on all routes EXCEPT:
// _next/static, _next/image, favicon.ico, fonts/, *.svg|png|jpg|jpeg|gif|webp
```

---

## 15. Constants & Utilities

### Navigation Items (`constants.ts`)

```typescript
NAV_ITEMS = [
  { label: 'Mission Control',       href: '/command-center',    icon: LayoutDashboard },
  { label: 'Deep Signal Analysis',  href: '/signal-analysis',   icon: Search,     section: 'Intelligence' },
  { label: 'Deep Embedding Lab',    href: '/embedding-lab',     icon: Dna,        section: 'Intelligence' },
  { label: 'Content Pipeline',      href: '/content-pipeline',  icon: FileText,   section: 'Content' },
  { label: 'Brand Brain',           href: '/brand-brain',       icon: Brain,      section: 'Content' },
  { label: 'Settings',              href: '/settings',          icon: Settings,   section: 'System' },
]
```

### Label Maps

```typescript
CONTENT_TYPE_LABELS = { blog, guide, case_study, product_page }
PIPELINE_LABELS     = { research, gap_analysis, content }
```

### Formatting Utilities (`format.ts`)

```typescript
relativeTime(dateString): string         // "2 hours ago"
shortDate(dateString): string            // "Feb 25, 2026"
shortDateTime(dateString): string        // "Feb 25, 10:30 AM"
formatPercent(value, decimals?): string  // "85.5%"
formatCompactNumber(value): string       // "1.2M", "5.3K"
scoreColor(score): string               // Returns text-error/warning/sage-400
scoreBgColor(score): string             // Returns bg-error/warning/sage-50
```

### Class Name Utility (`cn.ts`)

```typescript
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

---

## 16. Current Limitations

| # | Limitation | Severity |
|---|-----------|----------|
| 1 | **Auth is placeholder** — No login enforcement, all routes public | High |
| 2 | **No persistence** — Zustand state lost on page reload (no localStorage) | Medium |
| 3 | **Fixtures may be stale** — Mock data doesn't auto-update with backend changes | Low |
| 4 | **No dark mode** — Only warm cream/terracotta light theme | Low |
| 5 | **No frontend tests** — No unit/integration test suite | Medium |
| 6 | **Limited accessibility** — No ARIA labels, limited keyboard navigation | Medium |
| 7 | **Single-company focus** — Dashboard layout assumes one active company at a time | Low |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-02-25 | Initial architecture document created |
