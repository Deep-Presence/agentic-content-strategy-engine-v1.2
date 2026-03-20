# Frontend-Backend Integration Plan v2 (Phases 6-10)

> **Sprint:** v19 — frontend-backend-integration-session2
> **Date:** 2026-03-18
> **Branch:** `feat/front-back`
> **Approach:** TDD — write Vitest tests FIRST, then implement

---

## Current State Assessment

### Already Integrated (Session 1 — Phases 1-5)
| Page | Status | Method |
|------|--------|--------|
| Auth (login/register/join) | REAL API | `apiPost(AUTH.*)` |
| Onboarding | REAL API + SSE | `apiPost(ONBOARDING.start)` + `useTaskStream()` |
| Home Dashboard | REAL API | `apiGet(GAP_DATA.summary)`, `CONTENT_DATA.briefs`, `SITE_AUDIT.audits`, `TASKS.list` |
| Brand Artifacts | REAL API | `apiGet(BRAND_DATA.researchArtifacts)`, `ARTIFACTS.*` |
| Dashboard Layout | REAL API | Auth guard, JWT validation |

### Remaining (This Session — Phases 6-10)
| Page | Current Source | Target Source |
|------|---------------|---------------|
| Analytics (5 tabs) | `gap-report.ts` → local JSON | `GAP_DATA.*`, `SITE_AUDIT.*` |
| Analytics Lab (4 views) | Dynamic JSON imports | `GAP_DATA.embeddings`, `.heatmap` |
| Content Studio (Kanban) | `content-data.ts` → local JSON | `CONTENT_DATA.briefs`, `.brief`, `.stage` |
| Content Planner | `topic-data.ts` → local JSON | `TOPIC_DISCOVERY.taxonomy`, `.scoredSubdomains`, `.personas` |
| Settings (3 real tabs) | Mock useState | `SETTINGS.team`, `.profile`, `.pipelineDefaults` |
| Attribution | `data.ts` → hardcoded | Empty state (no backend exists) |

### Files to Delete After Integration
```
frontend/src/data/gap-report.ts
frontend/src/data/knowledge-base.ts
frontend/src/data/personas.ts
frontend/src/data/voice-guide.ts
frontend/src/data/content-briefs.ts
frontend/src/data/embeddings.ts
frontend/src/data/site-audit.ts
frontend/src/data/topics.ts
frontend/src/app/(dashboard)/content/_components/content-data.ts
frontend/src/app/(dashboard)/planner/_components/topic-data.ts
```

---

## Phase 6: Analytics (Signal Analysis) — ~12 files

### 6A: TypeScript Response Types
**New file:** `frontend/src/lib/api/types/gap-analysis.ts`

Define TypeScript interfaces matching backend Pydantic models:
```typescript
// Mirrors api/schemas/gap_data.py
interface GapSummaryResponse {
  spa_score: { overall: number; by_cluster: Record<string, number> };
  proximity_stats: { company_avg: number; citation_avg: number; gap_avg: number };
  classification_counts: Record<string, number>;  // significant_gap, gap_to_close, roughly_equal, company_wins
  cluster_performance: ClusterPerformanceRow[];
  total_queries: number;
  total_citations: number;
  average_gap: number;
  executive_summary: string;
  recommendations: Record<string, any>[];
}

interface QueryListResponse {
  queries: QueryRow[];
  total: number; page: number; page_size: number; total_pages: number;
}

interface ClusterListResponse { clusters: ClusterRow[]; total: number; }
interface SignalAveragesResponse { signals: SignalRow[]; dimensions: string[]; }
interface PlatformListResponse { platforms: PlatformRow[]; agreement_matrix: Record<string, Record<string, number>>; }
interface HeatmapResponse { rows: HeatmapRow[]; clusters: string[]; }
interface EmbeddingProjectionResponse { points: EmbeddingPoint[]; method: 'umap' | 'tsne'; metadata: Record<string, any>; }
interface SPATrendResponse { data_points: TrendPoint[]; }
```

**New file:** `frontend/src/lib/api/types/site-audit.ts`
```typescript
// Mirrors api/schemas/site_audit.py
interface AuditDetailResponse {
  audit_id: string; domain: string; overall_score: number; grade: string;
  pages_crawled: number; dimension_scores: DimensionScoreResponse[];
  ai_bot_access: AIBotAccessResponse; total_findings: number;
  findings_by_severity: Record<string, number>;
  findings_by_dimension: Record<string, number>;
}
```

### 6B: Analytics Data Hook
**New file:** `frontend/src/lib/hooks/useAnalyticsData.ts`

Custom hook that fetches all analytics data in parallel:
```typescript
function useAnalyticsData(slug: string | undefined) {
  // Returns { summary, queries, clusters, signals, platforms, heatmap, trend, loading, error }
  // Fetches: GAP_DATA.summary, .clusters, .signals, .platforms, .heatmap, .trend
  // Queries fetched separately with pagination state
}
```

**Test file (write FIRST):** `frontend/src/__tests__/use-analytics-data.test.ts`
- Test: returns loading=true initially
- Test: fetches all endpoints in parallel on mount
- Test: handles partial failures (one endpoint 404, others succeed)
- Test: returns empty state when slug is undefined
- Test: pagination works for queries endpoint

### 6C: Analytics Page Rewrite
**Modify:** `frontend/src/app/(dashboard)/analytics/page.tsx`
- Remove `import { getGapReport } from '@/data/gap-report'`
- Add `'use client'` directive
- Use `useAnalyticsData(slug)` hook
- Pass API data to tab components via props
- Add loading skeleton + error states

### 6D: Tab Components Migration
Each tab receives data as props instead of importing from gap-report:

**Modify:** `PerformanceTab.tsx`
- Props: `{ summary: GapSummaryResponse; trend: SPATrendResponse }`
- Remove all `report.*` references
- Map `summary.spa_score`, `summary.classification_counts`, `summary.cluster_performance`

**Modify:** `ShareOfVoiceTab.tsx`
- Props: `{ platforms: PlatformListResponse }`
- Remove `report.queries` iteration
- Map `platforms.platforms` array → per-platform charts

**Modify:** `CitationsTab.tsx`
- Props: `{ queries: QueryRow[]; pagination: PaginationState; onPageChange: fn }`
- Remove `report.queries` reference
- Support server-side pagination via `GAP_DATA.queries(slug)?page=N&page_size=15`
- Wire search/filter controls to API query params

**Modify:** `CompetitorsTab.tsx`
- Props: `{ clusters: ClusterListResponse }`
- Remove `report.clusters` reference

**Modify:** `BrandHealthTab.tsx`
- Props: `{ audit: AuditDetailResponse | null }`
- Remove `audit_result.json` import
- Fetch from `SITE_AUDIT.audits(slug)` → get latest → `SITE_AUDIT.audit(slug, auditId)`
- Map 8 `dimension_scores` to radar/bar chart

### 6E: Analytics Lab Rewrite
**Modify:** `frontend/src/app/(dashboard)/analytics/lab/page.tsx`
- Remove dynamic JSON imports for embedding projections
- Fetch `GAP_DATA.embeddings(slug)?method=umap` and `?method=tsne`
- Fetch `GAP_DATA.heatmap(slug)` for heatmap view
- Pass data to `SpaceOverview`, `ClusterDeepDive` as props

**Modify:** `SpaceOverview.tsx` — accept `EmbeddingProjectionResponse` as prop
**Modify:** `ClusterDeepDive.tsx` — accept embedding + cluster data as props

### 6F: Analytics Tests
**Test file (write FIRST):** `frontend/src/__tests__/analytics-integration.test.ts`
- Test: analytics page renders loading skeleton before data arrives
- Test: PerformanceTab renders SPA score from API data
- Test: CitationsTab pagination calls API with correct params
- Test: BrandHealthTab fetches latest audit and renders dimension scores
- Test: empty state when no gap data exists
- Test: lab page renders Plotly scatter from embedding API data

### Endpoint-to-Tab Verification Matrix
| Tab | Endpoint | Key Fields Used |
|-----|----------|-----------------|
| Performance | `GAP_DATA.summary` | `spa_score`, `classification_counts`, `cluster_performance` |
| Performance | `GAP_DATA.trend` | `data_points` → line chart |
| SOV | `GAP_DATA.platforms` | `platforms[]` → per-platform citation counts |
| Citations | `GAP_DATA.queries` | `queries[]` with pagination |
| Competitors | `GAP_DATA.clusters` | `clusters[]` with structural rates |
| Brand Health | `SITE_AUDIT.audits` → `.audit` | `dimension_scores[]`, `overall_score`, `grade` |
| Lab: Scatter | `GAP_DATA.embeddings` | `points[]` with x,y,cluster,label |
| Lab: Heatmap | `GAP_DATA.heatmap` | `rows[]` with cluster × signal matrix |

---

## Phase 7: Content Studio — ~8 files

### 7A: Content Types
**New file:** `frontend/src/lib/api/types/content.ts`
```typescript
interface ContentBrief {
  id: string; title: string; status: ContentStatus;
  content_type: string; cluster: string;
  target_word_count: number; citability_score: number | null;
  cycle_id: string | null; created_at: string; updated_at: string;
}
type ContentStatus = 'suggested' | 'approved' | 'in_progress' | 'completed';

interface ContentBriefDetail {
  id: string; title: string; status: string; content_type: string;
  cluster: string; target_word_count: { min: number; max: number };
  structural_targets: Record<string, any>;
  key_topics: string[]; key_angles: string[]; priority_score: number;
  citability_score: number | null;
  eval_history: EvalCycle[];
  final_passed: boolean; exemplars: BriefExemplar[];
  available_stages: string[];
}

interface StageContent {
  brief_id: string; stage: string;
  content_type: 'text/markdown' | 'application/json';
  content: string | Record<string, any>;
}
```

### 7B: Content Data Hook
**New file:** `frontend/src/lib/hooks/useContentBriefs.ts`
```typescript
function useContentBriefs(slug: string | undefined) {
  // Returns { briefs, total, loading, error, refetch }
  // Fetches: CONTENT_DATA.briefs(slug)
}

function useContentBriefDetail(slug: string | undefined, briefId: string | null) {
  // Returns { detail, loading, error }
  // Fetches: CONTENT_DATA.brief(slug, briefId)
}

function useStageContent(slug: string | undefined, briefId: string | null, stage: string | null) {
  // Returns { content, loading, error }
  // Fetches: CONTENT_DATA.stage(slug, briefId, stage)
}
```

**Test file (write FIRST):** `frontend/src/__tests__/use-content-briefs.test.ts`
- Test: fetches briefs on mount
- Test: groups briefs by status for kanban columns
- Test: detail hook fetches on briefId change
- Test: stage content returns markdown string
- Test: handles 404 when no briefs exist

### 7C: Content Page Rewrite
**Modify:** `frontend/src/app/(dashboard)/content/page.tsx`
- Remove `import { boardItems } from './_components/content-data'`
- Use `useContentBriefs(slug)` hook
- Map backend status → kanban columns:
  - `suggested` → "Triage"
  - `approved` → "Brief"
  - `in_progress` → "Generating" / "Review" (check sub-status)
  - `completed` → "Published"
- Pass briefs to `KanbanBoard` component

**DELETE:** `frontend/src/app/(dashboard)/content/_components/content-data.ts`

### 7D: Detail & Stage Views
**Modify:** `DetailView.tsx`
- Use `useContentBriefDetail(slug, selectedBriefId)`
- Render: title, status badge, content_type, cluster, word count, eval history, exemplars

**Modify:** `ContentView.tsx`
- Use `useStageContent(slug, briefId, stage)`
- Render markdown content via `react-markdown`
- Tab selector for available_stages

**Modify:** `ScoringPanel.tsx`
- Accept `eval_history: EvalCycle[]` as prop
- Render E-E-A-T scores, style scores, factual scores per cycle

### 7E: Content Tests
**Test file (write FIRST):** `frontend/src/__tests__/content-integration.test.ts`
- Test: kanban board renders briefs in correct columns by status
- Test: clicking brief opens detail panel with API data
- Test: stage tabs load content from API
- Test: empty kanban shows "no briefs" state

---

## Phase 8: Content Planner (Topic Discovery) — ~5 files

### 8A: Planner Types
**New file:** `frontend/src/lib/api/types/topic-discovery.ts`
```typescript
interface TaxonomyResponse {
  slug: string; taxonomy: TaxonomyNode;
  version: number; total_subdomains: number; coverage_score: number;
}
interface TaxonomyNode {
  name: string; children?: TaxonomyNode[];
  subdomain_id?: string; category?: string;
}
interface ScoredSubdomainsResponse {
  subdomains: ScoredSubdomain[];
}
interface ScoredSubdomain {
  subdomain_id: string; name: string; category: string;
  aeo_score: number; gap_score: number; priority_rank: number;
  cluster_mapping: Record<string, any>;
}
interface PersonaAffinityResponse {
  personas: PersonaAffinity[];
}
```

### 8B: Planner Data Hook
**New file:** `frontend/src/lib/hooks/usePlannerData.ts`
```typescript
function usePlannerData(slug: string | undefined) {
  // Returns { taxonomy, scoredSubdomains, personaAffinity, loading, error }
  // Fetches in parallel:
  //   TOPIC_DISCOVERY.taxonomy(slug)
  //   TOPIC_DISCOVERY.scoredSubdomains(slug)
  //   TOPIC_DISCOVERY.personas(slug)
}
```

**Test file (write FIRST):** `frontend/src/__tests__/use-planner-data.test.ts`
- Test: fetches taxonomy, scored subdomains, persona affinity in parallel
- Test: returns empty taxonomy when 404
- Test: handles partial load (taxonomy exists, personas don't)

### 8C: Planner Page Rewrite
**Modify:** `frontend/src/app/(dashboard)/planner/page.tsx`
- Remove all imports from `./\_components/topic-data`
- Use `usePlannerData(slug)` hook
- Pass taxonomy → `TaxonomyTree`, scoredSubdomains → `SubdomainDetail`

**DELETE:** `frontend/src/app/(dashboard)/planner/_components/topic-data.ts`

### 8D: Component Props Migration
**Modify:** `TaxonomyTree.tsx` — accept `TaxonomyResponse` as prop (was importing from topic-data)
**Modify:** `SubdomainDetail.tsx` — accept `ScoredSubdomain` as prop
**Modify:** `AssignmentsView.tsx` — accept assignments from API (if available via matrix endpoint)
**Modify:** `CoveragePanel.tsx` — accept coverage data from scored subdomains

### 8E: Planner Tests
**Test file (write FIRST):** `frontend/src/__tests__/planner-integration.test.ts`
- Test: taxonomy tree renders from API data
- Test: clicking subdomain shows detail panel
- Test: empty state when no taxonomy exists
- Test: coverage panel shows correct percentages

---

## Phase 9: Settings — ~6 files

### 9A: Settings Types
**New file:** `frontend/src/lib/api/types/settings.ts`
```typescript
interface TeamListResponse {
  members: TeamMember[];
}
interface TeamMember {
  user_id: string; email: string; first_name: string; last_name: string;
  role: 'superuser' | 'member' | 'viewer';
  is_active: boolean; created_at: string;
}
interface CompanyProfileSettingsResponse {
  company_name: string; domain: string; slug: string;
  industry: string; description: string;
  has_research: boolean;
}
interface PipelineDefaultsResponse {
  max_crawl_pages: number; max_crawl_depth: number;
  gap_platforms: string[];
  max_queries: number;
}
```

### 9B: Settings Hooks
**New file:** `frontend/src/lib/hooks/useSettings.ts`
```typescript
function useTeam(slug: string | undefined) {
  // GET SETTINGS.team(slug) → { members, loading, error, refetch }
}
function useUpdateTeamMember(slug: string | undefined) {
  // PUT SETTINGS.teamMember(slug, userId) → { update, loading, error }
}
function useCompanyProfile(slug: string | undefined) {
  // GET/PUT SETTINGS.profile(slug) → { profile, update, loading, error }
}
function usePipelineDefaults(slug: string | undefined) {
  // GET/PUT SETTINGS.pipelineDefaults(slug) → { defaults, update, loading, error }
}
```

**Test file (write FIRST):** `frontend/src/__tests__/use-settings.test.ts`
- Test: useTeam fetches team members
- Test: useUpdateTeamMember sends PUT with role change
- Test: useCompanyProfile fetches and updates
- Test: usePipelineDefaults fetches and updates
- Test: non-superuser cannot update (403 handling)

### 9C: Team Tab
**Modify:** `frontend/src/app/(dashboard)/settings/_components/TeamTab.tsx`
- Remove mock useState members
- Use `useTeam(slug)` hook
- Wire "Invite" button to `apiPost(AUTH.invite)`
- Wire role dropdown to `useUpdateTeamMember`

### 9D: Profile Tab (within settings page or dedicated component)
- Use `useCompanyProfile(slug)` hook
- Wire form submit to PUT endpoint
- Only enable edit for superuser role

### 9E: Pipeline Defaults Tab
- Use `usePipelineDefaults(slug)` hook
- Wire form to PUT endpoint
- Show current defaults (max_crawl_pages, platforms, max_queries)

### 9F: Settings Tests
**Test file (write FIRST):** `frontend/src/__tests__/settings-integration.test.ts`
- Test: TeamTab renders real team members from API
- Test: invite button calls POST /auth/invite
- Test: role change calls PUT with correct payload
- Test: profile form loads and saves
- Test: pipeline defaults form loads and saves
- Test: viewer role sees disabled controls

### Note on Models, Integrations, Billing, Notifications tabs
These 3 tabs have **no backend endpoints** yet. They should:
- Keep current mock UI
- Show "Coming soon" or disabled state where appropriate
- NOT be deleted — they represent future features

---

## Phase 10: Cleanup & Attribution — ~12 files

### 10A: Attribution Page
**Modify:** `frontend/src/app/(dashboard)/attribution/page.tsx`
- Replace mock data with empty state: "Connect your analytics to see attribution data"
- Keep the UI structure but show EmptyState component
- Remove import from `./\_components/data`
- Attribution backend does not exist yet — this is intentional

### 10B: Delete Mock Data Files
```
DELETE: frontend/src/data/gap-report.ts
DELETE: frontend/src/data/knowledge-base.ts
DELETE: frontend/src/data/personas.ts
DELETE: frontend/src/data/voice-guide.ts
DELETE: frontend/src/data/content-briefs.ts
DELETE: frontend/src/data/embeddings.ts
DELETE: frontend/src/data/site-audit.ts
DELETE: frontend/src/data/topics.ts
```

### 10C: Remove Filesystem References
- Verify no `fs` imports remain in frontend
- Remove `/data/artifacts/` symlink if present
- Remove any `import()` calls to local JSON artifact files

### 10D: Add Missing Endpoint Definitions
**Modify:** `frontend/src/lib/api/endpoints.ts`
- Add Topic Discovery approval endpoints:
  - `approveTaxonomy: (runId) => /api/v1/topic-discovery/${runId}/approve/taxonomy`
  - `approveSubdomains: (runId) => /api/v1/topic-discovery/${runId}/approve/subdomains`
  - `approveMatrix: (runId) => /api/v1/topic-discovery/${runId}/approve/matrix`
- Add Settings PUT endpoints (if not already present)

### 10E: Build Verification
```bash
cd frontend && npx tsc --noEmit    # TypeScript check
cd frontend && npm run build        # Next.js production build
cd frontend && npx vitest run       # All tests pass
```

### 10F: Cleanup Tests
**Test file (write FIRST):** `frontend/src/__tests__/no-mock-data.test.ts`
- Test: no imports from `@/data/` in any page component
- Test: no dynamic `import()` of local JSON files
- Test: attribution page renders empty state

---

## Execution Order & Dependencies

```
Phase 6A (types) ──┐
                    ├── Phase 6B (hook + tests) ── Phase 6C-6E (page + tabs + lab)
Phase 6F (tests) ──┘

Phase 7A (types) ──┐
                    ├── Phase 7B (hook + tests) ── Phase 7C-7D (page + views)
Phase 7E (tests) ──┘

Phase 8A (types) ──┐
                    ├── Phase 8B (hook + tests) ── Phase 8C-8D (page + components)
Phase 8E (tests) ──┘

Phase 9A (types) ──┐
                    ├── Phase 9B (hooks + tests) ── Phase 9C-9E (tabs)
Phase 9F (tests) ──┘

Phase 10A-10F (cleanup) ── depends on 6-9 all complete
```

**Critical path:** 6A → 6B → 6C → 6D → 6E (analytics is the most complex phase)

---

## Test Strategy (TDD)

### Layer 1: Hook Tests (unit)
- Mock `fetch` globally via `vi.fn()`
- Test each hook returns correct loading/data/error states
- Test pagination, filtering, error handling
- ~25 tests across 4 hook test files

### Layer 2: Integration Tests (component)
- Render page components with mocked API responses
- Test that data flows from hook → component → UI
- Test loading skeletons, empty states, error states
- ~20 tests across 4 integration test files

### Layer 3: Build Verification
- `tsc --noEmit` passes
- `npm run build` succeeds
- `vitest run` all green

### Estimated Test Count
| Phase | Hook Tests | Integration Tests | Total |
|-------|-----------|-------------------|-------|
| 6 (Analytics) | 8 | 8 | 16 |
| 7 (Content) | 6 | 5 | 11 |
| 8 (Planner) | 4 | 4 | 8 |
| 9 (Settings) | 6 | 6 | 12 |
| 10 (Cleanup) | 0 | 3 | 3 |
| **Total** | **24** | **26** | **~50** |

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Backend response shape mismatch | TypeScript types mirror Pydantic models exactly; any drift caught at compile time |
| Plotly SSR issues in lab | Already handled — dynamic import with `ssr: false` |
| Long-running data fetches | Add loading skeletons in every page/tab |
| Empty data (new company, no runs) | Every component has explicit empty state |
| Pagination complexity (citations) | Server-side pagination already built in backend |
| Settings mutations fail for non-superuser | Check `user.role` before showing edit controls |
| Attribution has no backend | Show empty state with "coming soon" message |

---

## Files Created (New)
```
frontend/src/lib/api/types/gap-analysis.ts
frontend/src/lib/api/types/site-audit.ts
frontend/src/lib/api/types/content.ts
frontend/src/lib/api/types/topic-discovery.ts
frontend/src/lib/api/types/settings.ts
frontend/src/lib/hooks/useAnalyticsData.ts
frontend/src/lib/hooks/useContentBriefs.ts
frontend/src/lib/hooks/usePlannerData.ts
frontend/src/lib/hooks/useSettings.ts
frontend/src/__tests__/use-analytics-data.test.ts
frontend/src/__tests__/use-content-briefs.test.ts
frontend/src/__tests__/use-planner-data.test.ts
frontend/src/__tests__/use-settings.test.ts
frontend/src/__tests__/analytics-integration.test.ts
frontend/src/__tests__/content-integration.test.ts
frontend/src/__tests__/planner-integration.test.ts
frontend/src/__tests__/settings-integration.test.ts
frontend/src/__tests__/no-mock-data.test.ts
```

## Files Modified
```
frontend/src/app/(dashboard)/analytics/page.tsx
frontend/src/app/(dashboard)/analytics/_components/PerformanceTab.tsx
frontend/src/app/(dashboard)/analytics/_components/ShareOfVoiceTab.tsx
frontend/src/app/(dashboard)/analytics/_components/CitationsTab.tsx
frontend/src/app/(dashboard)/analytics/_components/CompetitorsTab.tsx
frontend/src/app/(dashboard)/analytics/_components/BrandHealthTab.tsx
frontend/src/app/(dashboard)/analytics/lab/page.tsx
frontend/src/app/(dashboard)/analytics/lab/_components/SpaceOverview.tsx
frontend/src/app/(dashboard)/analytics/lab/_components/ClusterDeepDive.tsx
frontend/src/app/(dashboard)/content/page.tsx
frontend/src/app/(dashboard)/content/_components/DetailView.tsx
frontend/src/app/(dashboard)/content/_components/ContentView.tsx
frontend/src/app/(dashboard)/content/_components/ScoringPanel.tsx
frontend/src/app/(dashboard)/planner/page.tsx
frontend/src/app/(dashboard)/planner/_components/TaxonomyTree.tsx
frontend/src/app/(dashboard)/planner/_components/SubdomainDetail.tsx
frontend/src/app/(dashboard)/planner/_components/AssignmentsView.tsx
frontend/src/app/(dashboard)/planner/_components/CoveragePanel.tsx
frontend/src/app/(dashboard)/settings/_components/TeamTab.tsx
frontend/src/app/(dashboard)/settings/page.tsx (profile/pipeline tabs)
frontend/src/app/(dashboard)/attribution/page.tsx
frontend/src/lib/api/endpoints.ts
```

## Files Deleted
```
frontend/src/data/gap-report.ts
frontend/src/data/knowledge-base.ts
frontend/src/data/personas.ts
frontend/src/data/voice-guide.ts
frontend/src/data/content-briefs.ts
frontend/src/data/embeddings.ts
frontend/src/data/site-audit.ts
frontend/src/data/topics.ts
frontend/src/app/(dashboard)/content/_components/content-data.ts
frontend/src/app/(dashboard)/planner/_components/topic-data.ts
```
