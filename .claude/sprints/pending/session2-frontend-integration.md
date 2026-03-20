# Session 2: Frontend-Backend Integration (Phases 6-10)

## Context

Session 1 completed Phases 1-5 of the frontend-backend integration. The foundation layer, auth flow, onboarding with SSE streaming, home dashboard, and brand artifacts are all wired to real API endpoints. This document describes exactly what remains for Session 2.

## What Was Done in Session 1

### Files Created
| File | Purpose |
|------|---------|
| `frontend/src/lib/api/client.ts` | Typed fetch wrapper with JWT injection, 401 handling |
| `frontend/src/lib/api/endpoints.ts` | URL builder constants for ALL backend endpoints |
| `frontend/src/stores/auth.ts` | Zustand auth store (token, user, company, login/register/join/logout) |
| `frontend/src/lib/hooks/useTaskStream.ts` | SSE hook for real-time pipeline progress |
| `frontend/src/__tests__/api-client.test.ts` | API client unit tests (8 tests) |
| `frontend/src/__tests__/auth-store.test.ts` | Auth store unit tests (11 tests) |
| `frontend/src/__tests__/use-task-stream.test.ts` | SSE hook unit tests (7 tests) |
| `frontend/src/__tests__/setup.ts` | Vitest setup file |
| `frontend/vitest.config.ts` | Vitest configuration with path aliases |
| `frontend/.env.local` | Backend URL env var |

### Files Modified
| File | Changes |
|------|---------|
| `frontend/next.config.mjs` | Added rewrites proxy for `/api/*` → backend |
| `frontend/src/stores/workspace.ts` | Removed hardcoded "Lovable", initializes from auth |
| `frontend/src/app/(auth)/login/page.tsx` | Real API login + onboarding detection |
| `frontend/src/app/(auth)/register/page.tsx` | Real API register → redirect to /onboarding |
| `frontend/src/app/(auth)/join/page.tsx` | Real API join + onboarding detection |
| `frontend/src/app/(dashboard)/layout.tsx` | Auth guard: validate JWT on mount, redirect if invalid |
| `frontend/src/app/onboarding/page.tsx` | Wired to POST /onboarding/start, passes taskId to ScreenPipeline |
| `frontend/src/app/onboarding/_components/ScreenInput.tsx` | Pre-fills company name/domain from auth store |
| `frontend/src/app/onboarding/_components/ScreenPipeline.tsx` | Real SSE via useTaskStream (removed all timers/hardcoded messages) |
| `frontend/src/app/(dashboard)/page.tsx` | KPIs from gap-analysis/summary, content/briefs, site-audit, tasks |
| `frontend/src/app/(dashboard)/_components/home/ActiveTasks.tsx` | Fetches from GET /tasks?status=running |
| `frontend/src/app/(dashboard)/_components/home/HITLReviews.tsx` | Fetches from GET /tasks?status=pending_approval |
| `frontend/src/app/(dashboard)/_components/home/RecentActivity.tsx` | Fetches from GET /companies/{slug}/runs |
| `frontend/src/app/(dashboard)/artifacts/page.tsx` | Fetches KB docs from artifacts API, personas/voice from research API |
| `api/routers/artifacts.py` | Added "knowledge_base" to VALID_TYPES |

### API Client Usage Pattern
```typescript
import { apiGet, apiPost, ApiError } from '@/lib/api/client';
import { GAP_DATA, TASKS } from '@/lib/api/endpoints';
import { useAuthStore } from '@/stores/auth';

// Get company slug from auth store
const company = useAuthStore((s) => s.company);
const slug = company?.slug;

// Fetch data
const data = await apiGet<ResponseType>(GAP_DATA.summary(slug));

// The client auto-injects Bearer token from localStorage('dp_token')
// On 401, it clears auth and redirects to /login
```

### Auth Store Access
```typescript
const { user, company } = useAuthStore();
// company.slug — use for all tenant-scoped API calls
// user.first_name — display name
// user.role — "superuser" | "member" | "viewer"
```

### Gotchas Discovered
1. **Next.js rewrites proxy** handles CORS in dev — frontend calls `/api/v1/...` which Next.js proxies to `localhost:8000`
2. **Backend returns snake_case** — frontend works with snake_case directly (no camelCase mapping needed)
3. **PlainTextResponse for .md files** — the artifacts endpoint returns markdown as plain text, not JSON. `apiGet` tries `res.json()` which will fail. Need to handle `.md` content differently or use `fetch` directly for those.
4. **VoiceGuide type** has strict register name union: `'tactical' | 'analytical' | 'empathy'`
5. **KBDocument type** requires `id` field
6. **Stream tokens** expire in 5 minutes — the SSE hook should handle reconnection for long-running pipelines

---

## Phase 6: Analytics (Signal Analysis)

### Files to Modify

**`frontend/src/app/(dashboard)/analytics/page.tsx`**
- Remove all imports from `@/data/gap-report`
- Convert from server component to `'use client'`
- Fetch data from API on mount using `useAuthStore` for slug

**`frontend/src/app/(dashboard)/analytics/_components/PerformanceTab.tsx`**
- Replace `gapReport` prop data with API fetch
- Endpoint: `GET /companies/{slug}/gap-analysis/summary`
- Maps: `spa_score`, `classification_counts`, `cluster_performance`, `total_queries`, `total_citations`

**`frontend/src/app/(dashboard)/analytics/_components/ShareOfVoiceTab.tsx`**
- Endpoint: `GET /companies/{slug}/gap-analysis/platforms`
- Maps: `platforms` array (total_citations, per_cluster, avg_citation_sim)

**`frontend/src/app/(dashboard)/analytics/_components/CitationsTab.tsx`** (if exists)
- Endpoint: `GET /companies/{slug}/gap-analysis/queries?page=1&page_size=15`
- Support pagination with `page` and `page_size` query params

**`frontend/src/app/(dashboard)/analytics/_components/CompetitorsTab.tsx`**
- Endpoint: `GET /companies/{slug}/gap-analysis/clusters`
- Maps: `clusters` array with structural rates, exemplar themes

**`frontend/src/app/(dashboard)/analytics/_components/BrandHealthTab.tsx`**
- Remove import of `audit_result.json`
- Endpoint: `GET /site-audit/companies/{slug}/audits` → get latest → `GET /{audit_id}`
- Maps: 8 dimensions with scores

**`frontend/src/app/(dashboard)/analytics/lab/page.tsx`**
- Remove all JSON file imports
- Endpoint: `GET /companies/{slug}/gap-analysis/embeddings?method=umap` (and `tsne`)
- Endpoint: `GET /companies/{slug}/gap-analysis/heatmap`
- Pass data to Plotly components

**`frontend/src/app/(dashboard)/analytics/lab/_components/SpaceOverview.tsx`**
- Accept embedding points as props from parent

**`frontend/src/app/(dashboard)/analytics/lab/_components/ClusterDeepDive.tsx`**
- Accept embedding points + cluster data as props

### Endpoint-to-Tab Mapping
| Tab | Endpoint | Response Schema |
|-----|----------|----------------|
| Performance | `GET /gap-analysis/summary` | `GapSummaryResponse` |
| SOV | `GET /gap-analysis/platforms` | `PlatformListResponse` |
| Citations | `GET /gap-analysis/queries` | `QueryListResponse` (paginated) |
| Competitors | `GET /gap-analysis/clusters` | `ClusterListResponse` |
| Brand Health | `GET /site-audit/companies/{slug}/audits` | audit list → detail |
| Embedding Lab | `GET /gap-analysis/embeddings` | `EmbeddingProjectionResponse` |
| Heatmap | `GET /gap-analysis/heatmap` | `HeatmapResponse` |
| SPA Trend | `GET /gap-analysis/trend` | `SPATrendResponse` |
| Signals | `GET /gap-analysis/signals` | `SignalAveragesResponse` |

### Verification
- All 5 analytics tabs render with real API data
- Embedding lab scatter plot renders from API data
- Brand health shows real audit scores
- Empty states show when no data exists

---

## Phase 7: Content Studio

### Files to Modify

**`frontend/src/app/(dashboard)/content/_components/content-data.ts`**
- DELETE this file entirely (imports from JSON files)
- Replace with API fetching in the page/parent component

**`frontend/src/app/(dashboard)/content/page.tsx`**
- Fetch briefs: `GET /companies/{slug}/content/briefs`
- Map backend status to kanban columns:
  - `suggested` → Triage
  - `approved` → Brief
  - `generating` → Generating
  - `review` → Review
  - `published` → Published

**Content Detail Panel**
- Fetch detail: `GET /companies/{slug}/content/briefs/{id}`
- Response has: title, status, content_type, cluster, target_word_count, structural_targets, eval_history

**Content Editor/Stage View**
- Fetch stage: `GET /companies/{slug}/content/briefs/{id}/{stage}`
- Stages: outline, draft, enriched, formatted, final
- Returns markdown or JSON depending on stage

### Verification
- Kanban board shows real briefs from API
- Brief detail panel shows real metadata
- Stage content (outline, draft, etc.) renders correctly

---

## Phase 8: Content Planner

### Files to Modify

**`frontend/src/app/(dashboard)/planner/_components/topic-data.ts`**
- DELETE this file (hardcoded taxonomy)

**`frontend/src/app/(dashboard)/planner/page.tsx`**
- Fetch taxonomy: `GET /topic-discovery/{slug}/taxonomy`
- Fetch scored subdomains: `GET /topic-discovery/{slug}/scored-subdomains`
- Fetch persona affinity: `GET /topic-discovery/{slug}/personas`

**`frontend/src/app/(dashboard)/planner/_components/TaxonomyTree.tsx`**
- Accept taxonomy data as props from API
- Map backend taxonomy format to tree structure

**`frontend/src/app/(dashboard)/planner/_components/SubdomainDetail.tsx`**
- Accept scored subdomain data as props

### Verification
- Taxonomy tree renders from API data
- Subdomain detail shows real scores
- Empty state when no taxonomy exists

---

## Phase 9: Settings

### Files to Modify

**`frontend/src/app/(dashboard)/settings/page.tsx`**
- Wire up 3 tabs to real API endpoints

**Team Tab**
- Fetch: `GET /companies/{slug}/settings/team`
- Update: `PUT /companies/{slug}/settings/team/{userId}`
- Create invite: `POST /api/v1/auth/invite`
- Response: `TeamListResponse` with members array

**Profile Tab**
- Fetch: `GET /companies/{slug}/settings/profile`
- Update: `PUT /companies/{slug}/settings/profile`
- Response: `CompanyProfileSettingsResponse`

**Pipeline Defaults Tab**
- Fetch: `GET /companies/{slug}/settings/pipeline-defaults`
- Update: `PUT /companies/{slug}/settings/pipeline-defaults`
- Response: `PipelineDefaultsResponse`

### Verification
- Team list shows real members
- Profile edits persist
- Pipeline defaults load and save

---

## Phase 10: Cleanup

### Files to Delete
```
frontend/src/data/gap-report.ts
frontend/src/data/knowledge-base.ts
frontend/src/data/personas.ts
frontend/src/data/voice-guide.ts
frontend/src/data/content-briefs.ts
frontend/src/data/embeddings.ts
frontend/src/data/site-audit.ts
frontend/src/data/topics.ts
```

### Files to Modify
- **Attribution page** (`frontend/src/app/(dashboard)/attribution/page.tsx`): Show "Connect your analytics" empty state. No backend endpoint exists for attribution yet.
- Remove any remaining `fs` imports from frontend
- Remove `data/artifacts` symlink if present
- Verify `npm run build` succeeds with no errors

### Verification
- No filesystem reads remain in frontend
- `npx tsc --noEmit` passes (ignore pre-existing unrelated errors)
- `npm run build` succeeds
- All pages load from API only
