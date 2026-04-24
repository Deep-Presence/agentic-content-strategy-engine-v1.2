# Frontend Dashboard Pages

> **Location:** `frontend/src/app/(dashboard)/`
> **Owner:** Frontend
> **Dependencies:** API client, Zustand stores, UI components, company-wide SSE
> **Last Updated:** 2026-04-15

## Overview

12 dashboard pages under the `(dashboard)` route group, sharing a common layout with sidebar + topbar. Each page follows a pattern of `_lib/` (types, API, parsers, adapters), `_hooks/` (data fetching), and `_components/` (page-specific UI).

Content Studio, Content Performance, and Planner have been rebuilt around the **TD-entry parallel execution model**: multiple topics can flow through gap analysis and the Content Engine in parallel, and the UI updates each card independently via a mix of company-wide SSE, per-topic SSE, and adaptive polling. See `docs/TD_ENTRY_PARALLEL_EXECUTION_PLAN.md` and [05-CORE-EVENTS.md](05-CORE-EVENTS.md) for the backend side.

## Page Inventory

| Route | Page Name | Backend Pipeline | Status |
|-------|-----------|-----------------|--------|
| `/` | Brand Presence | KB + Daily Tracker | Mock data |
| `/analytics` | Citation Intelligence | Daily Tracker | Mock data |
| `/competitive-position` | Competitive Position | Gap Analysis | Real API |
| `/prompt-tracking` | Prompt Tracking | Daily Tracker | Real API |
| `/content-performance` | Content Performance | Content Engine + GA4 + CMS | Real API |
| `/technical-readiness` | Technical SEO Audit | Site Audit | Real API |
| `/embedding-lab` | Deep Embedding Lab | Gap Analysis | Real API |
| `/planner` | Content Planner | Topic Discovery | Real API |
| `/content-studio` | Content Studio | Content Engine (TD-entry parallel) | Real API |
| `/artifacts` | Brand Hub | KB + VSG + AP + Gap | Real API |
| `/attribution` | Attribution & Revenue | Demo (no backend) | Mock data |
| `/settings` | Settings | Auth + CMS + GA4 | Partial (Team + Integrations) |

---

## Content Studio — `/content-studio`

The largest frontend surface. Now **topic-run-centric**: each kanban card corresponds to a durable `topic_run` record, and many cards progress concurrently.

### File Structure

```
content-studio/
├── page.tsx                              ← Top-level board + FullPageView router
├── _components/
│   ├── ColumnBoard.tsx                   ← Kanban columns
│   ├── ContentCardItem.tsx               ← Card with agent progress + GA phase hints
│   ├── FullPageView.tsx                  ← Detail view (brief/review/publish modes)
│   ├── LeftSidebar.tsx                   ← Brief, exemplars, activity feed
│   ├── RightSidebar.tsx                  ← Metrics: compliance, E-E-A-T, CPS, publish
│   ├── ArticleEditor.tsx                 ← Tiptap editor with comment marks
│   └── types.ts                          ← ContentCard, BriefPipelineStatus, etc.
├── _hooks/
│   ├── useContentBriefs.ts               ← Core state: briefs + topic-run overlay + adaptive polling
│   ├── useCompanyStream.ts               ← Company-wide SSE
│   ├── useTopicRunEvents.ts              ← Per-topic events (on-demand)
│   ├── useCardActivity.ts                ← Topic-run events → activity feed
│   └── useBriefDetail.ts                 ← Brief detail + article loader (with error surface)
└── _lib/
    ├── types.ts                          ← API types + SSE event shapes + TopicRunSummaryAPI
    ├── api.ts                            ← Briefs, topic-runs, approvals, CMS publish
    ├── adapters.ts                       ← Backend → ContentCard, eval → UI metrics
    ├── topic-run-store.ts                ← Normalized store (version-aware merge, overlay)
    ├── card-activity.ts                  ← TopicRunEvent → CardActivityItem
    └── status-adapter.ts                 ← Status → column, label, HITL actions
```

### Topic Runs as Source of Truth

`topic-run-store.ts` holds topic run state with version-aware merge:

- `mergeTopicRunSnapshots()` — replaces entry only if `seq` is higher or `updated_at` is newer.
- `overlayTopicRunOnCard()` — merges topic run onto `ContentCard`: copies `displayId`, `topicRunId`, `batchRunId`, `status`, `updatedAt`. Local card wins only if its `updatedAt` is strictly newer.

### Real-Time Strategy: Three-Layer Update Model

1. **Company-wide SSE — `useCompanyStream`**: one `EventSource` per company. Three event types: `topic_run_changed` (immediate merge), `state_changed` (300ms debounce, optimistic flip), `notification` (HITL/completion/error). `onReconnect → refetch()`.

2. **Per-topic SSE — `useTopicRunEvents`**: lazy, only when user opens a card. Fetches topic-run events for the detail drawer's activity feed.

3. **Adaptive polling — `useContentBriefs`**: 5s when active topics, 60s idle, paused when empty. Also hits `/topic-runs` per effective slug to refresh the topic-run store.

### Version-Aware Merge + Optimistic Grace

- `updateCard(id, { status })` stamps `optimisticRef` with `Date.now()`.
- For `OPTIMISTIC_GRACE_MS = 15_000` after optimistic update, polls cannot overwrite that card's status.
- `agentProgress` preserved across merges.

### Per-Card Activity Feed

`useCardActivity` fetches `topic-runs/{id}/events` and adapts via `card-activity.ts`. Keyed on `display_id` for stable human-readable identity.

### Tiptap Article Editor

`ArticleEditor.tsx` uses Tiptap (StarterKit + Underline + TextAlign + Link + custom `CommentMark`). Prosemirror markdown serializer for round-trip between editor state and persisted markdown.

### Detail View — FullPageView

Orchestrates three sidebars for selected card. RightSidebar guards against NaN from empty arrays/zero targets via clamped percentages. `useBriefDetail` surfaces article load failures instead of spinning.

### Action Semantics & Resume

- `start_production` — calls `/from-topics/start-production` with single `topic_assignment_id` and cached `ga_run_id`. Writes back `pipeline_task_id` so approved TD cards reuse paused task identity.
- `activeTaskId` in `page.tsx` is scoped to kanban, not company. Prefers GA-phase card.

### Known Issues

- Single-process SSE (multi-worker needs Redis Pub/Sub).
- No SSE `id:` field (no `Last-Event-ID` replay).
- Worker-step SSE sparse.
- Toast notifications not wired yet.

---

## Content Performance — `/content-performance`

Three data streams: published-page analytics (GA4 + structural signals), unpublished-pages staging from Content Studio briefs, and CMS-sync action.

### File Structure

```
content-performance/
├── page.tsx                              ← Tabbed layout (Pages / Unpublished / Insights)
├── _components/
│   ├── ContentTable.tsx                  ← Published pages with traffic, velocity, structural score
│   ├── UnpublishedPagesTable.tsx         ← NEW — completed-but-unpublished briefs
│   ├── ContentDrawer.tsx                 ← 50vw detail drawer
│   ├── VelocityChart.tsx                 ← Daily pageviews/AI referrals chart
│   └── CPSScatterChart.tsx               ← Citation vs velocity scatter
└── _lib/
    ├── types.ts                          ← FreshnessAssessmentAPI, ContentPerformanceReadinessAPI
    ├── api.ts                            ← Content detail, table, velocity, readiness, CMS sync, GA4
    └── adapters.ts                       ← API row → ContentPiece, structural signal formatting
```

### Key Features

- **SEO + structural metadata** on ContentDrawer: `structural_signals`, `structural_score` (0–100), `platforms`, `queries_covered`.
- **Freshness benchmarking**: `FreshnessAssessmentAPI` with `content_age_days`, `cited_exemplar_avg/median_age_days`, `freshness_score`, `freshness_status/reason`.
- **Unpublished staging**: `UnpublishedPagesTable` renders completed briefs with `published_url=None`. Shares `FullPageView` with Content Studio.
- **CMS sync action**: 3-step flow — sync → poll → generate prompts.
- **Analytics readiness banner**: maps `state` enum to user-facing titles.
- **Drawer DB error handling** (commit `678589f`): surfaces 500s instead of silent hang.

---

## Content Planner — `/planner`

Entry point into TD-entry parallel flow: operators select topic assignments and "Approve & Send to Studio" dispatches a batch.

### File Structure

```
planner/
├── page.tsx                              ← Queue / Explorer / Rejected views
├── _components/
│   ├── PriorityQueue.tsx                 ← Sortable table with cannibalization badges
│   ├── DetailDrawer.tsx                  ← 50vw drawer with cannibalization evidence
│   ├── ClusterExplorer.tsx               ← Cluster-grouped grid
│   └── planner-data.ts                   ← Types: Assignment, CannibalizationMatchItem
└── _lib/
    ├── api.ts                            ← Topic list, assignment status, GA launch
    └── adapters.ts                       ← API → Assignment, cannibalization field mapping
```

### Cannibalization Surface (Phase 1 + Phase 2)

`Assignment` carries six cannibalization fields:
- `cannibalizationRisk`: 0–1 overlap score
- `cannibalizationMatches`: array with `inventoryId`, `url`, `title`, `similarity`, `riskScore`, `signals`
- `cannibalizationRiskLevel`: `none` / `low` / `medium` / `high`
- `cannibalizationRecommendedAction`, `cannibalizationReasons`

**PriorityQueue.tsx** — `getCannibalizationBadge()` renders "High Risk" (red, >= 0.90) or "Overlap" (amber, >= 0.80) inline.

**DetailDrawer.tsx** — Cannibalization Risk section (line 323): overlap gauge, recommended action, composite risk score, reasons list, per-match details with similarity scores. Border/background adapts to risk level.

### Launching TD-Entry Parallel Batches

`handleApprove` in `page.tsx:82`:
1. `approveAssignments(ids)` — marks as approved in DB.
2. `startFromTopicsPipeline(...)` — POSTs to `/from-topics/gap-analysis`.
3. On 409 → toast "wait". On failure → `revertAssignments(ids)`.

### Known Issues

- `displayId` still computed frontend-side (backend universal display IDs planned).
- Cannibalization evidence depends on content inventory being populated.

---

## Settings — `/settings`

7-tab page; only Team and Integrations wired to real APIs.

### Recent Changes

- **GA4 Connect Flow** — 3-state component (`not_connected`, `property_required`, `connected`). OAuth round-trip, property selection, disconnect with `purgeData` toggle.
- **Integrations hook** — `buildBackfillRequest(days)` for GA4, `waitForTaskCompletion(taskId)` poll, OAuth callback handling (`?ga4=connected`).
- **New types**: `GA4ConnectionResponseAPI`, `GA4PropertyItemAPI`, `GA4SyncRequestAPI`, `TaskStatusAPI`.

### Known Issues

- Billing, Models, Notifications, Profile tabs still dummy.
- GA4 OAuth callback fails silently if user not authed.

---

## Cross-References

- **Backend parallel execution plan:** `docs/TD_ENTRY_PARALLEL_EXECUTION_PLAN.md`
- **CompanyEventBus + SSE:** [05-CORE-EVENTS.md](05-CORE-EVENTS.md)
- **API routers:** [28-API-ROUTERS.md](28-API-ROUTERS.md)
- **Content Engine pipeline:** [15-PIPELINE-CONTENT-ENGINE.md](15-PIPELINE-CONTENT-ENGINE.md)
- **Topic Discovery + cannibalization:** [16-PIPELINE-TOPIC-DISCOVERY.md](16-PIPELINE-TOPIC-DISCOVERY.md)
- **Frontend BFF proxy + auth:** `frontend/CLAUDE.md`
