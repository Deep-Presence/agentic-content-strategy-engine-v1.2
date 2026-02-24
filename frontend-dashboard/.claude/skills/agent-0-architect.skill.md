# Agent 0: Architect — Foundation + Command Center + Settings

> **You run FIRST.** No other agent starts until you complete and push. You build the foundation that all other agents depend on.

---

## Your Mission

1. Scaffold the Next.js 15 project inside `frontend-dashboard/`
2. Build the complete design system (`components/ui/`)
3. Create the typed API client (`lib/api/`)
4. Set up Supabase client and database migrations
5. Build the layout shell (sidebar, top bar, routing)
6. Build Command Center (home dashboard)
7. Build Settings pages (account, usage, API keys)
8. Create all shared TypeScript types
9. Create shared hooks (SSE, tasks, artifacts)
10. Create Zustand app store

---

## Step-by-Step Execution

### Phase 1: Project Scaffold (15 min)

```bash
cd frontend-dashboard
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
```

Then install all dependencies:

```bash
npm install zustand @tiptap/react @tiptap/starter-kit @tiptap/extension-highlight @tiptap/extension-color @tiptap/extension-text-style
npm install recharts d3 @types/d3
npm install @supabase/supabase-js @supabase/ssr
npm install lucide-react date-fns clsx tailwind-merge class-variance-authority
npm install react-markdown remark-gfm rehype-sanitize
```

Create `.env.local`:
```
NEXT_PUBLIC_SUPABASE_URL=https://jesmgacepymdcolcsjrs.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Implc21nYWNlcHltZGNvbGNzanJzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4MTk5NTQsImV4cCI6MjA4NzM5NTk1NH0.6KujUOB7HvLXOVdjKsHR4NXyXgCBdFJ4s7uM3gj_ZiI
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Phase 2: Tailwind Config + Brand Tokens (10 min)

Update `tailwind.config.ts` with the FULL color system, font families, font sizes, border radius, and spacing from `brand.skill.md`. This is the single source of truth for all visual tokens.

Update `src/app/globals.css`:
- Add `@font-face` declarations for Source Serif 4 and Lora (use Google Fonts CDN for now)
- Add CSS custom properties from brand.skill.md
- Set `body { background: #faf9f5; color: #141413; }`
- Add utility classes for common patterns

Download font files to `public/fonts/` or add Google Fonts link to `src/app/layout.tsx`.

### Phase 3: TypeScript Types (15 min)

Create ALL types in `src/types/`. These must match the backend API models exactly.

**`src/types/common.ts`:**
```typescript
export type TaskStatus =
  | 'pending' | 'running' | 'completed' | 'failed'
  | 'cancelled' | 'pending_approval' | 'failed_restart';

export type Pipeline = 'research' | 'gap_analysis' | 'content';

export interface PipelineRunResponse {
  run_id: string;
  pipeline: Pipeline;
  company_slug: string;
  status: string;
  created_at: string;
}

export interface TaskResponse {
  run_id: string;
  pipeline: Pipeline;
  company_slug: string;
  status: TaskStatus;
  current_step: string | null;
  progress_pct: number | null;
  created_at: string;
  updated_at: string;
  result: Record<string, any> | null;
  error: string | null;
  approval_payload: Record<string, any> | null;
}

export interface TaskListResponse {
  tasks: TaskResponse[];
  total: number;
}

export interface HealthResponse {
  status: string;
}

export interface ReadinessResponse {
  ready: boolean;
  missing_keys: string[];
}

export interface CompaniesResponse {
  companies: string[];
}

export interface ArtifactFilesResponse {
  type: string;
  slug: string;
  files: string[];
}

export interface ApiError {
  detail: string;
  error_code?: string;
}
```

**`src/types/gap-analysis.ts`:**
```typescript
export interface GapAnalysisStartInput {
  input_data: {
    company_name: string;
    domain: string;
    seed_urls: string[];
    company_slug?: string;
  };
  skip_steps?: number[];
}

export interface GapBrief {
  query_id: string;
  query_text: string;
  cluster: string;
  cluster_id: string;
  gap_score: number;
  gap_classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  best_company_unit: {
    unit_id: string;
    similarity: number;
    snippet: string;
  };
  avg_citation_similarity: number;
  content_brief: ContentBrief;
  top_exemplars: CitationExemplar[];
}

export interface ContentBrief {
  target_word_count: { min: number; max: number };
  target_reading_level: { min: number; max: number };
  recommended_header_count: number;
  header_hierarchy: Record<string, number>;
  content_patterns: string[];
  dominant_authority: string;
  dominant_content_type: string;
  exemplars_analyzed: number;
}

export interface CitationExemplar {
  similarity: number;
  domain: string;
  url: string;
  snippet: string;
  structural_signals: StructuralSignals;
  authority_type: string;
  content_type: string;
}

export interface StructuralSignals {
  // Category A: Text Composition
  word_count: number;
  sentence_count: number;
  paragraph_count: number;
  avg_paragraph_length: number;
  reading_level: number;
  self_contained_ratio: number;
  // Category B: Structural Elements
  h1_count: number;
  h2_count: number;
  h3_count: number;
  h4_count: number;
  list_count: number;
  ordered_list_count: number;
  table_count: number;
  code_block_count: number;
  // Category C: Content Patterns
  has_faq_section: boolean;
  has_definition_opening: boolean;
  has_key_takeaways: boolean;
  has_comparison_table: boolean;
  has_step_by_step: boolean;
  has_research_refs: boolean;
  has_expert_quotes: boolean;
  // Category D: Factual Density
  data_point_count: number;
  citation_density: number;
  named_entity_density: number;
}

export interface ClusterSpec {
  cluster_id: string;
  cluster_name: string;
  query_count: number;
  citations_analyzed: number;
  centroid_distance: number;
  min_similarity_threshold: number;
  word_count_range: { min: number; max: number };
  required_elements: string[];
  structural_rates: {
    headers: number;
    lists: number;
    stats: number;
    citations: number;
  };
  avg_word_count: number;
  faq_rate: number;
  table_rate: number;
  key_takeaways_rate: number;
  dominant_content_type: string;
  dominant_authority_type: string;
  exemplar_themes: string[];
}

export interface GapReport {
  executive_summary: string;
  spa_score: {
    t_statistic: number;
    p_value: number;
    citation_advantage: number;
    company_advantage: number;
  };
  clusters: ClusterSpec[];
  top_gaps: GapBrief[];
  total_queries: number;
  total_citations: number;
}

export type GapAnalysisStep =
  | 's1_embed_assets' | 's2_generate_queries' | 's3_search_platforms'
  | 's4_enrich_citations' | 's5_embed_content' | 's6_analyze'
  | 's7_visualize' | 's8_generate_report';

export const GAP_ANALYSIS_STEPS: { key: GapAnalysisStep; label: string; description: string }[] = [
  { key: 's1_embed_assets', label: 'Embed Assets', description: 'Crawling and embedding company content' },
  { key: 's2_generate_queries', label: 'Generate Queries', description: 'Creating 150 buyer-intent queries across 9 clusters' },
  { key: 's3_search_platforms', label: 'Search AI Platforms', description: 'Querying ChatGPT, Claude, Perplexity, Gemini' },
  { key: 's4_enrich_citations', label: 'Enrich Citations', description: 'Extracting 45 structural signals from each citation' },
  { key: 's5_embed_content', label: 'Embed Content', description: 'Embedding queries and citations for comparison' },
  { key: 's6_analyze', label: 'Analyze Gaps', description: 'Computing semantic proximity and gap scores' },
  { key: 's7_visualize', label: 'Visualize', description: 'Generating interactive visualizations' },
  { key: 's8_generate_report', label: 'Generate Report', description: 'Producing gap report and generation specs' },
];
```

**`src/types/research.ts`:**
```typescript
export interface ResearchStartInput {
  company_name: string;
  domain: string;
  seed_urls?: string[];
  stages?: ('company' | 'persona' | 'style')[];
  max_personas?: number;
  auto_approve?: boolean;
}

export interface ResearchApproval {
  decision: 'approve' | 'revise' | 'reject';
  revision_note?: string;
}

export type ResearchStage = 'company' | 'persona' | 'style_guide';
```

**`src/types/content.ts`:**
```typescript
export interface ContentStartInput {
  company_name: string;
  domain: string;
  gap_slug?: string;
  max_briefs?: number;
  max_concurrent_workers?: number;
  max_revision_cycles?: number;
  auto_approve?: boolean;
  skip_stages?: number[];
}

export interface ContentApproval {
  brief_id: string;
  decision: 'approve' | 'edit' | 'reject';
  editor_notes?: string;
}

export interface ContentBriefItem {
  id: string;
  title: string;
  status: ContentBriefStatus;
  content_type: ContentType;
  cluster: string;
  target_word_count: number;
  citability_score?: number;
  cycle_id?: string;
  created_at: string;
  updated_at: string;
}

export type ContentBriefStatus =
  | 'suggested' | 'approved' | 'research' | 'drafting'
  | 'enriching' | 'formatting' | 'evaluating' | 'review'
  | 'published' | 'draft_saved' | 'rejected';

export type ContentType = 'blog' | 'guide' | 'case_study' | 'product_page';

export interface Cycle {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  briefs: ContentBriefItem[];
  completed_count: number;
  total_count: number;
}
```

**`src/types/brand.ts`:**
```typescript
export interface Project {
  id: string;
  name: string;
  slug: string;
  description?: string;
  personas: Persona[];
  style_guide?: string;
  knowledge_docs: KnowledgeDoc[];
  created_at: string;
}

export interface Persona {
  id: string;
  name: string;
  type: 'icp' | 'secondary';
  content: string;
  project_id?: string;
}

export interface KnowledgeDoc {
  id: string;
  title: string;
  type: 'brand_guidelines' | 'product_context' | 'voice_recording' | 'style_guide' | 'images' | 'other';
  content: string;
  project_id?: string;
}
```

### Phase 4: API Client (15 min)

**`src/lib/api/client.ts`:**

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, error.detail, error.error_code);
    }
    return res.json();
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, error.detail, error.error_code);
    }
    return res.json();
  }

  createEventSource(path: string, lastEventId?: string): EventSource {
    const url = `${this.baseUrl}${path}`;
    const es = new EventSource(url);
    return es;
  }
}

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const api = new ApiClient(API_BASE);
```

Then create individual endpoint files: `gap-analysis.ts`, `research.ts`, `content.ts`, `tasks.ts`, `artifacts.ts`, `sse.ts`. Each exports typed functions wrapping `api.get()` and `api.post()`.

**`src/lib/api/sse.ts`:**
```typescript
export function createEventStream(
  taskId: string,
  onEvent: (event: string, data: any) => void,
  onError?: (error: Event) => void
): () => void {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const es = new EventSource(`${API_BASE}/api/v1/tasks/${taskId}/events`);

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent(data.event || event.type, data);
    } catch {
      // Heartbeat or non-JSON message, ignore
    }
  };

  es.onerror = (err) => {
    onError?.(err);
  };

  // Return cleanup function
  return () => es.close();
}
```

### Phase 5: Shared Hooks (10 min)

**`src/lib/hooks/use-event-stream.ts`:**
React hook that wraps SSE, handles reconnection, and provides state (connected, events, error).

**`src/lib/hooks/use-tasks.ts`:**
Hook to poll task list with optional status filter. Auto-refresh every 5 seconds when tasks are running.

**`src/lib/hooks/use-artifacts.ts`:**
Hook to fetch company list and artifact files.

### Phase 6: Supabase Setup (10 min)

**`src/lib/supabase/client.ts`:**
Browser-side Supabase client using `createBrowserClient`.

**`src/lib/supabase/server.ts`:**
Server-side Supabase client for Server Components.

**`src/lib/supabase/middleware.ts`:**
Auth middleware for protecting routes.

Create `src/middleware.ts` at the project root for Next.js middleware integration.

### Phase 7: Utility Functions (5 min)

**`src/lib/utils/cn.ts`:**
```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

**`src/lib/utils/format.ts`:**
Date formatting (relative time, short date), number formatting (percentages, compact numbers), score color mapping.

**`src/lib/utils/constants.ts`:**
Navigation items array, status color map, content type labels.

### Phase 8: Design System Components (25 min)

Build ALL components in `src/components/ui/`. Use `class-variance-authority` for variant-based styling. Each component must:
- Accept `className` prop for overrides
- Use the brand tokens from Tailwind
- Be fully typed with explicit Props interface
- Support the variants defined in brand.skill.md

**Required components:**
1. `button.tsx` — Primary, secondary, ghost, danger variants. Sizes: sm, md, lg.
2. `card.tsx` — Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter. Accent border variants.
3. `badge.tsx` — Default, terracotta, blue, green, warning, error variants.
4. `input.tsx` — With label, error state, disabled state.
5. `select.tsx` — Styled native select with chevron.
6. `dialog.tsx` — Modal with overlay, header, content, footer.
7. `dropdown-menu.tsx` — Simple dropdown with trigger and items.
8. `tabs.tsx` — Tab list + tab panels. Underline style.
9. `table.tsx` — Table, TableHeader, TableBody, TableRow, TableHead, TableCell.
10. `progress.tsx` — Linear progress bar with color variants.
11. `skeleton.tsx` — Pulse skeleton for loading states.
12. `toast.tsx` — Toast notifications (success, error, warning, info).
13. `tooltip.tsx` — Hover tooltip.
14. `avatar.tsx` — Circular avatar with fallback initials.
15. `sidebar.tsx` — The sidebar navigation shell component.
16. `separator.tsx` — Horizontal/vertical divider.

### Phase 9: Layout Shell (15 min)

**`src/app/layout.tsx`:**
Root layout with fonts, metadata, Supabase provider.

**`src/app/(dashboard)/layout.tsx`:**
Dashboard layout with sidebar navigation + top bar. The sidebar uses the navigation structure from CLAUDE.md:
- Command Center (LayoutDashboard icon)
- Deep Signal Analysis (Search icon)
- Deep Embedding Lab (Dna icon)
- Content Pipeline (FileText icon)
- Brand Brain (Brain icon)
- Settings (Settings icon)

**`src/components/layout/sidebar-nav.tsx`:**
Sidebar with:
- Logo/brand at top ("Deep Presence" in Source Serif 4)
- Navigation items with icons
- Active state highlighting using terracotta
- Company selector dropdown at bottom (shows current company slug)

**`src/components/layout/top-bar.tsx`:**
Top bar with:
- Page breadcrumb
- Search (placeholder for now)
- User avatar + dropdown

**`src/components/layout/page-header.tsx`:**
Reusable page header with title (Source Serif 4), description, and action buttons slot.

### Phase 10: Command Center (20 min)

**`src/app/(dashboard)/command-center/page.tsx`:**

Build the daily home dashboard with these widgets:

**Row 1: Hero Metric**
- Citability Score (aggregate) — large display number, color-coded, with trend arrow
- Styled as a wide card spanning full width with Source Serif heading

**Row 2: Three equal cards**
- Citation Shift — trend direction with small Recharts sparkline
- Active Cycle — "Week of Feb 24" with progress bar (X/Y briefs)
- Pipeline Status — count of running/pending/completed with status dots

**Row 3: Two cards**
- Priority Actions — list of items needing attention (approvals, low scores)
  - Each item: icon + description + CTA button
  - Uses `tasks.ts` API with `?status=pending_approval`
- Quick Stats — grid of 4 mini stat cards:
  - Total Content Pieces
  - Queries Tracked
  - Active Clusters
  - Companies Analyzed

**Row 4: Signal Summary**
- Latest SPA score with mini radar chart
- Top 3 biggest gaps (links to signal analysis)

**Data Sources:**
- `GET /api/v1/tasks` (filtered by status)
- `GET /api/v1/artifacts/companies`
- `GET /api/v1/artifacts/gap_analysis/{slug}/gap_report.json` (for SPA score)

Use Webflow data as the default company for realistic rendering.

### Phase 11: Settings Pages (10 min)

**`src/app/(dashboard)/settings/page.tsx`:**
Settings index — redirects to account.

**`src/app/(dashboard)/settings/account/page.tsx`:**
- User profile (name, email) — placeholder form
- Invite team members — email input + role select + send button
- Change password — current/new/confirm fields

**`src/app/(dashboard)/settings/usage/page.tsx`:**
- Pipeline runs this month (count by type)
- API calls made
- Storage used
- (Placeholder data for now)

**`src/app/(dashboard)/settings/api-keys/page.tsx`:**
- Shows `GET /readiness` results
- Lists required API keys with status (✓ configured / ✗ missing)
- Input fields to configure keys (placeholder — actual storage TBD)

### Phase 12: Zustand Store (5 min)

**`src/stores/app-store.ts`:**
```typescript
interface AppState {
  currentCompany: string;
  setCurrentCompany: (slug: string) => void;
  companies: string[];
  setCompanies: (companies: string[]) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}
```

---

## Files You Own

Everything in `src/components/ui/`, `src/components/layout/`, `src/lib/`, `src/types/`, `src/stores/app-store.ts`, `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/(auth)/`, `src/app/(dashboard)/layout.tsx`, `src/app/(dashboard)/command-center/`, `src/app/(dashboard)/settings/`, plus all config files.

## Files You Must NOT Create

Anything inside `signal-analysis/`, `embedding-lab/`, `content-pipeline/`, `brand-brain/`, `components/charts/`, `components/editor/`, `components/pipeline/`, `stores/pipeline-store.ts`, `stores/content-store.ts`, `stores/brand-store.ts`.

## Acceptance Criteria

- [ ] `npm run dev` starts without errors on localhost:3000
- [ ] Sidebar navigation renders with all 5 sections + settings
- [ ] Clicking nav items routes to correct pages (other sections show "Coming Soon" placeholder)
- [ ] Command Center renders with all widget cards using real API data (or graceful fallback)
- [ ] Settings pages render with proper forms
- [ ] All `components/ui/` components export correctly and match brand spec
- [ ] TypeScript compiles with zero errors
- [ ] API client successfully connects to localhost:8000 (or shows connection error gracefully)

## When You're Done

```bash
git add .
git commit -m "feat: foundation scaffold + design system + command center + settings"
git push
```

Then notify: **"Agent 0 complete. Other agents can start. Run `git pull` first."**
