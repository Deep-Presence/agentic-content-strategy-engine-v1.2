# Frontend ↔ Backend Integration Mapping

> **Purpose:** Maps every dummy data source in the revamped frontend to its corresponding backend API endpoint(s) in the content-strategy-engine monolith (port 8000) and log-ingestion-service (port 8001).
>
> **How to read this:** Each section covers one frontend route. For each piece of data the frontend currently consumes from hardcoded mocks or `data/artifacts/` files, the table shows the backend endpoint that will replace it.

---

## Architecture Overview

```
┌─────────────────────┐         ┌──────────────────────────────────┐
│   Revamped Frontend │ ──────> │  Monolith (port 8000)            │
│   (Next.js 14)      │         │  /api/v1/*                       │
│                     │         │  - Auth, Pipelines, Data, SSE    │
│   Currently uses:   │         └──────────────────────────────────┘
│   - Hardcoded mocks │
│   - data/artifacts/ │ ──────> ┌──────────────────────────────────┐
│     (fs.readFile)   │         │  Log Ingestion Service (8001)    │
│                     │         │  /v1/dashboard/*                 │
└─────────────────────┘         │  - AI Crawler analytics          │
                                └──────────────────────────────────┘
```

**Auth pattern:** All endpoints (except `/register`, `/login`, `/join`) require `Authorization: Bearer {jwt_token}`. SSE endpoints also accept `?stream_token={token}`.

**Tenant isolation:** Every data endpoint scopes by `company_slug` from the JWT. Product-level data uses `product_slug` query param.

---

## Table of Contents

1. [Auth Pages (`/login`, `/register`, `/join`)](#1-auth-pages)
2. [Onboarding (`/onboarding`)](#2-onboarding)
3. [Home / Brand Summary (`/`)](#3-home--brand-summary)
4. [Citation Intelligence (`/analytics`)](#4-citation-intelligence)
5. [Competitive Position (`/competitive-position`)](#5-competitive-position)
6. [Prompt Tracking (`/prompt-tracking`)](#6-prompt-tracking)
7. [Content Performance (`/content-performance`)](#7-content-performance)
8. [Technical Readiness (`/technical-readiness`)](#8-technical-readiness)
9. [Embedding Lab (`/embedding-lab`)](#9-embedding-lab)
10. [Content Planner (`/planner`)](#10-content-planner)
11. [Content Studio (`/content-studio`)](#11-content-studio)
12. [Brand Hub / Artifacts (`/artifacts`)](#12-brand-hub--artifacts)
13. [Settings (`/settings`)](#13-settings)
14. [Attribution (`/attribution`)](#14-attribution)
15. [Cross-Cutting: SSE Task Streaming](#15-cross-cutting-sse-task-streaming)
16. [Gaps & New Backend Work Needed](#16-gaps--new-backend-work-needed)

---

## 1. Auth Pages

**Routes:** `/login`, `/register`, `/join`

**Current frontend:** Pure form UIs. `useState` for fields, `router.push()` on submit. No API calls.

| Frontend Action | Backend Endpoint | Method | Request Body | Response |
|---|---|---|---|---|
| Login form submit | `/api/v1/auth/login` | POST | `{ email, password }` | `{ access_token, token_type, user, company }` |
| Register form submit | `/api/v1/auth/register` | POST | `{ first_name, last_name, email, password, company_name, company_domain }` | `{ access_token, token_type, user, company }` |
| Join with invite code | `/api/v1/auth/join` | POST | `{ invite_code, first_name, last_name, email, password }` | `{ access_token, token_type, user, company }` |
| Get current user (on app load) | `/api/v1/auth/me` | GET | — | `{ user, company }` |

**Integration notes:**
- Store `access_token` in httpOnly cookie or secure storage
- After login/register, redirect to `/` (home) or `/onboarding` if first-time
- Company `slug` from login response is used in all subsequent API calls

---

## 2. Onboarding

**Route:** `/onboarding`

**Current frontend:** 4-screen wizard (Input → Briefing → Pipeline → Complete). Hardcoded pipeline step labels. Simulated progress.

| Frontend Data | Backend Endpoint | Method | Notes |
|---|---|---|---|
| Start onboarding pipeline | `/api/v1/onboarding/start` | POST | Body: `{ industry?, seed_personas[], seed_urls[], max_pages, max_depth, ... }`. `company_name` and `domain` are resolved from JWT. Returns `{ run_id }` |
| Pipeline progress (real-time) | `/api/v1/tasks/{run_id}/events` | GET (SSE) | Stream events: `pipeline_start`, `stage_start`, `stage_complete`, `pending_approval`, `completed`, `failed` |
| Pipeline status (poll fallback) | `/api/v1/tasks/{run_id}` | GET | Returns `{ status, current_step, progress_pct, result, error }` |

**Integration notes:**
- The onboarding pipeline runs: Research (KB → AP → VSG) → Gap Analysis → Site Audit sequentially
- Frontend should connect to SSE stream for real-time progress updates
- Each `stage_start` event maps to a step in the progress UI
- On `completed` event, redirect to home dashboard

---

## 3. Home / Brand Summary

**Route:** `/`

**Current frontend data sources:**

| Mock Data (in `_components/brand-presence/mock-data.ts`) | Backend Endpoint | Method | Response Fields Used |
|---|---|---|---|
| `generateDayData()` — 28 days of time-series: `presenceScore`, `sov`, `citations`, `mentions`, `position` per day | `/api/v1/daily-tracker/analytics/mention-trend` | GET | `?days=28` → `TrendDataPoint[]` with daily mention/citation counts |
| Per-platform breakdown (`chatgpt`, `claude`, `perplexity`, `google`, `gemini`) | `/api/v1/daily-tracker/analytics/visibility` | GET | `VisibilityMetrics` with per-platform breakdown |
| `COMPETITORS[]` — 14 competitors with SOV, citations | `/api/v1/daily-tracker/analytics/competitors` | GET | `CompetitorMetrics[]` — per-competitor SOV and citations |
| Share of Voice values | `/api/v1/daily-tracker/analytics/sov` | GET | `{ brand: float, ...competitors }` |
| `CITATION_URLS[]` — 8 URLs with citation counts, CPS, velocity | `/api/v1/daily-tracker/analytics/citations` | GET | `{ rate, domain_breakdown }` |
| `PLATFORMS[]` — 5 platforms with stats | `/api/v1/companies/{slug}/gap-analysis/platforms` | GET | `PlatformListResponse { platforms[] }` |
| `TRAJECTORY` — monthly scores | **Not yet available** | — | Needs new aggregation endpoint (see [Gaps](#16-gaps--new-backend-work-needed)) |
| `SCORE_BREAKDOWN` — weighted score components | `/api/v1/companies/{slug}/gap-analysis/summary` | GET | `spa_score`, breakdown in `GapSummaryResponse` |

**Integration notes:**
- The home page is a composite view. It pulls from multiple endpoints.
- The Daily Tracker analytics endpoints are the primary data source for time-series.
- The "Presence Score" concept maps to the backend's SPA (Semantic Proximity Analysis) score.
- Consider a BFF (Backend-for-Frontend) aggregation endpoint or fetch in parallel on the client.

---

## 4. Citation Intelligence

**Route:** `/analytics`

**Current frontend data sources (all in `_components/data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `KPIS` — `totalCitations: 847`, `citationRate: 67`, `uncitedQueries: 11`, `avgPosition: 2.3` | `/api/v1/companies/{slug}/gap-analysis/summary` | GET | `{ total_citations, company_cited_count, average_gap }`. Citation rate = `company_cited_count / total_queries`. Uncited = `total_queries - company_cited_count`. |
| `generateMomentumData()` — 28 days per-platform citations | `/api/v1/daily-tracker/analytics/mention-trend` | GET | `?days=28` → daily per-platform citation counts |
| `LEADERBOARD[]` — 8 competitors with SOV, citations, delta | `/api/v1/daily-tracker/analytics/competitors` | GET | `CompetitorMetrics[]` with SOV and citation data |
| `UNCITED_QUERIES[]` — 11 queries with engines and actions | `/api/v1/companies/{slug}/gap-analysis/queries` | GET | `?classification=uncited&sort_by=gap&sort_dir=desc` → `QueryListResponse` |
| `VISIBILITY` — `totalQueries: 47`, `cited: 31`, etc. | `/api/v1/companies/{slug}/gap-analysis/summary` | GET | `{ total_queries, company_cited_count, classification_counts }` |
| `SENTIMENT_CATEGORIES[]` — sentiment breakdown | **Not yet available** | — | Needs sentiment analysis endpoint (see [Gaps](#16-gaps--new-backend-work-needed)) |
| `PLATFORMS[]` — per-platform intel with sparklines | `/api/v1/companies/{slug}/gap-analysis/platforms` | GET | `PlatformListResponse` with per-platform citation stats |
| `CITATION_URLS[]` — 10 URLs with per-platform counts, CPS | `/api/v1/companies/{slug}/gap-analysis/signals` | GET | `SignalAveragesResponse` — structural signals and correlations |
| URL drawer detail — structural signals, improvements | `/api/v1/companies/{slug}/gap-analysis/signals` | GET | Per-URL signal data from `signals[]` and `correlations[]` |

**Integration notes:**
- Most citation intelligence data comes from the gap analysis data endpoints
- The "momentum" time-series requires the Daily Tracker to have run multiple times
- Sentiment analysis is a gap — the backend doesn't currently compute sentiment from AI responses

---

## 5. Competitive Position

**Route:** `/competitive-position`

**Current frontend data sources (all in `_components/data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `YOUR_DATA` — rank, SOV, citations, winRate | `/api/v1/companies/{slug}/gap-analysis/summary` | GET | `spa_score`, SOV from `cluster_performance[]`, citation counts |
| `COMPETITORS[]` — 6 competitors with SOV, trend, winRate | `/api/v1/daily-tracker/analytics/competitors` | GET | `CompetitorMetrics[]` |
| `CLUSTER_RANKINGS[]` — 9 clusters with your rank vs leader | `/api/v1/companies/{slug}/gap-analysis/clusters` | GET | `ClusterListResponse { clusters[] }` — each has `your_share`, `leader`, `gap` |
| `CITATIONS_AT_RISK[]` — lost/at-risk citations | `/api/v1/companies/{slug}/gap-analysis/queries` | GET | `?classification=at_risk` or `?classification=lost` |
| `SOV_TREND` — 28-day SOV for you + competitors | `/api/v1/companies/{slug}/gap-analysis/trend` | GET | `SPATrendResponse { trend: SPATrendPoint[] }` — daily SPA scores |
| `COMPETITOR_DETAILS` — per-competitor queries won/lost | `/api/v1/companies/{slug}/gap-analysis/queries` | GET | Filter by competitor domain, analyze win/loss |
| `CLUSTER_DETAILS` — per-cluster dominators | `/api/v1/companies/{slug}/gap-analysis/clusters` | GET | Cluster detail with competitor breakdown |
| `MINDSHARE[]` / `AUTHORITY[]` — external sources | `/api/v1/companies/{slug}/gap-analysis/signals` | GET | Mindshare/authority signals in `SignalAveragesResponse` |

**Integration notes:**
- Competitive position is primarily derived from gap analysis query-level data
- The "win rate" concept = percentage of queries where your citation rank is higher than competitor X
- Backend may need a dedicated competitive comparison endpoint for efficiency

---

## 6. Prompt Tracking

**Route:** `/prompt-tracking`

**Current frontend data sources (all in `_components/prompt-data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `PROMPTS[]` — 15 tracked prompts with mention/citation rates | `/api/v1/daily-tracker/prompts` | GET | `PromptListResponse { prompts[], total }` |
| `TOPICS` — unique topics derived from prompts | `/api/v1/daily-tracker/prompts` | GET | `?category={topic}` — group by category |
| Per-prompt competitor mentions | `/api/v1/daily-tracker/analytics/competitors` | GET | `?run_id={latest}` → per-competitor mention data |
| Per-prompt platform mention rates | `/api/v1/daily-tracker/analytics/visibility` | GET | `?run_id={latest}` → per-platform visibility |
| Query fanouts per prompt | **Derived from gap analysis** | — | Each tracked prompt maps to gap analysis queries |
| `getAnswerHistory()` — 28 rows of AI answers per platform | **Not yet available** | — | Needs answer snapshot storage endpoint (see [Gaps](#16-gaps--new-backend-work-needed)) |
| `FULL_ANSWERS` — full AI answer text per platform | **Not yet available** | — | Raw AI responses not currently stored/served |

**Integration notes:**
- Prompt tracking uses the Daily Tracker pipeline and its analytics endpoints
- Prompts are managed (CRUD) via `/api/v1/daily-tracker/prompts/*`
- Runs are triggered via `/api/v1/daily-tracker/runs` POST
- Answer history (storing full AI responses over time) is a backend gap
- The "query fanout" concept links tracked prompts to gap analysis queries

---

## 7. Content Performance

**Route:** `/content-performance`

**Current frontend data sources (all in `_components/data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `CONTENT_PIECES[]` — 7 pieces with citations, CPS, velocity | `/api/v1/companies/{slug}/content/briefs` | GET | `ContentBriefListResponse { briefs[] }` — each has `citability_score`, status |
| Per-piece structural scores | `/api/v1/cps/score` | POST | `CPSScoreResponse { cps_score, per_engine[], per_query[] }` — compute for each content piece |
| `STRUCTURAL_SIGNALS[]` — 20 signals with correlation | `/api/v1/companies/{slug}/gap-analysis/signals` | GET | `SignalAveragesResponse { signals[], correlations[] }` |
| `CPS_SCATTER[]` — predicted vs actual CPS | Combination of CPS score endpoint + gap analysis | — | Predicted from `/cps/score`, actual from citation tracking |
| `QUERY_COVERAGE` — queries covered per piece | `/api/v1/companies/{slug}/gap-analysis/queries` | GET | Cross-reference content pieces with gap queries |
| `CANNIBALIZATION_ENTRIES` — overlapping content | **Not yet available** | — | Needs content overlap/cannibalization detection (see [Gaps](#16-gaps--new-backend-work-needed)) |
| `BRIEF_COMPLIANCE` — word count targets, elements | `/api/v1/companies/{slug}/content/briefs/{brief_id}` | GET | `ContentBriefDetailResponse { target_word_count, structural_targets }` |
| Traffic data (`~2,400/mo` hardcoded) | **GA4 integration (in progress)** | — | `/api/v1/ga4/traffic` (not yet implemented) |

**Integration notes:**
- Content performance combines content pipeline data with gap analysis signals
- The CPS (Citation Signal Predictor) endpoint provides per-content scoring
- Traffic data requires the GA4 integration (DB layer done, service/router pending per memory)
- Content cannibalization detection is a backend gap

---

## 8. Technical Readiness

**Route:** `/technical-readiness`

**Current frontend data sources (all in `_components/tech-readiness-data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `GAP_DATA.siteHealth.score` — overall site health | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}` | GET | `AuditDetailResponse { overall_score, grade }` |
| `PRIORITY_FIXES[]` — 7 ranked fixes | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}/findings` | GET | `?severity=critical&page_size=10` → `AuditFindingsResponse { findings[] }` |
| `DIMENSIONS[]` — 8 dimensions with scores | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}` | GET | `dimension_scores[]` in `AuditDetailResponse` |
| `BOT_ACCESS[]` — 5 AI bots with status, lastCrawl | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}` | GET | `ai_bot_access` in `AuditDetailResponse` |
| `CRITICAL_FILES[]` — robots.txt, llms.txt, Sitemap | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}` | GET | Part of audit findings |
| `ENGINE_PREFERENCES` — per-engine signal preferences | `/api/v1/companies/{slug}/gap-analysis/signals` | GET | `cluster_fingerprints` in `SignalAveragesResponse` |
| `BOT_CRAWL_DATA` — 28 days bot crawl activity | `/v1/dashboard/crawlers` **(log-ingestion-service, port 8001)** | GET | `list[CrawlerSummary]` with per-bot request counts |
| Bot crawl daily breakdown | `/v1/dashboard/crawlers/{bot_id}` **(port 8001)** | GET | `{ daily_activity[] }` with per-day crawl counts |
| `SNIPPET_DISTRIBUTION[]` — snippet readiness | **Not yet available** | — | Needs snippet readiness analysis (see [Gaps](#16-gaps--new-backend-work-needed)) |
| `AFFECTED_PAGES[]` — pages with issues | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}/pages` | GET | `AuditPageResultsResponse { pages[] }` |

**Integration notes:**
- This page pulls from TWO backend services:
  1. **Monolith (8000):** Site audit results and gap analysis signals
  2. **Log-ingestion-service (8001):** Real-time AI crawler activity data
- To get the latest audit, first call `/audits?limit=1` to get the most recent `audit_id`
- Bot crawl data from the log-ingestion-service is the ONLY data from port 8001 used by the frontend

---

## 9. Embedding Lab

**Route:** `/embedding-lab`

**Current frontend data sources (all in `_components/data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `CLUSTERS[]` — 9 clusters with per-engine breakdown | `/api/v1/companies/{slug}/gap-analysis/clusters` | GET | `ClusterListResponse { clusters[] }` |
| `GAP_QUERIES[]` — queries sorted by opportunity | `/api/v1/companies/{slug}/gap-analysis/queries` | GET | `?sort_by=gap&sort_dir=desc` → `QueryListResponse` |
| `ENGINE_DATA[]` — 5 engines with citation stats | `/api/v1/companies/{slug}/gap-analysis/platforms` | GET | `PlatformListResponse { platforms[] }` |
| `EMBEDDING_POINTS[]` — UMAP/t-SNE scatter coordinates | `/api/v1/companies/{slug}/gap-analysis/embeddings` | GET | `?method=umap` or `?method=tsne` → `EmbeddingProjectionResponse { points[] }` |
| Territory/danger zone summary stats | `/api/v1/companies/{slug}/gap-analysis/summary` | GET | `GapSummaryResponse { cluster_performance[] }` |

**Integration notes:**
- The embedding lab is primarily a visualization of gap analysis data
- The `/embeddings` endpoint provides pre-computed UMAP/t-SNE projections
- Note: `src/data/embeddings.ts` exists with a file-based loader but is NOT used by the current page — the page uses its own hardcoded mock data instead
- The D3 territory map visualization consumes the same cluster/query data

---

## 10. Content Planner

**Route:** `/planner`

**Current frontend data sources (all in `_components/planner-data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `ASSIGNMENTS[]` — ~15 content assignments with priority scores | `/api/v1/topic-discovery/{slug}/matrix` | GET | `MatrixReadResponse { matrix }` — topic assignments with scores |
| `CLUSTERS[]` — cluster hierarchy with subclusters | `/api/v1/topic-discovery/{slug}/taxonomy` | GET | `TaxonomyReadResponse { taxonomy }` — full cluster/subdomain hierarchy |
| Persona affinity scores per assignment | `/api/v1/topic-discovery/{slug}/personas` | GET | `PersonaAffinityResponse { persona_entries[] }` |
| `INITIATIVES[]` — strategic initiatives | **User-created in frontend** | — | No backend equivalent — this is editorial workflow |
| Scored subdomains for prioritization | `/api/v1/topic-discovery/{slug}/scored-subdomains` | GET | `ScoredSubdomainsResponse { scored_subdomains[] }` — priority-ranked |
| Start content from selected topics | `/api/v1/content/v13/from-topics` | POST | `{ topic_assignment_ids[] }` → starts content pipeline |

**Integration notes:**
- The planner maps to Topic Discovery pipeline outputs
- Note: `src/data/topics.ts` exists with a file-based loader for `gap_report.json` but is NOT used
- The "approve/reject/modify" actions on topics use the Topic Discovery HITL endpoints
- Starting content production from selected topics uses the Content Engine v1.3 `from-topics` endpoint

---

## 11. Content Studio

**Route:** `/content-studio`

**Current frontend data sources (all in `_components/mock-data.ts`):**

| Mock Data | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|
| `INITIAL_CARDS[]` — 8 content cards in queue/human/agent columns | `/api/v1/companies/{slug}/content/briefs` | GET | `ContentBriefListResponse { briefs[] }` — each has `status` that maps to column |
| Card detail — brief content (sections, sources, reasons) | `/api/v1/companies/{slug}/content/briefs/{brief_id}` | GET | `ContentBriefDetailResponse` with full brief data |
| Card detail — article content (full markdown, word counts) | `/api/v1/companies/{slug}/content/briefs/{brief_id}/{stage}` | GET | `?stage=draft` or `enriched` or `final` → `StageContentResponse { content }` |
| `MOCK_CYCLE` / `PAST_CYCLES` — cycle metadata | **Not yet available** | — | Needs content cycle/sprint management (see [Gaps](#16-gaps--new-backend-work-needed)) |
| Agent progress (pct, currentTask, wordsCurrent) | `/api/v1/tasks/{run_id}/events` | GET (SSE) | Real-time `stage_start`, `stage_complete` events with progress |
| Pipeline status polling | `/api/v1/content/v13/{run_id}/status` | GET | `{ status, current_step, progress_pct }` |
| Start content production | `/api/v1/content/v13/start` | POST | `{ company_name, domain, entry_mode, ... }` → `{ run_id }` |
| Approve brief | `/api/v1/content/v13/{run_id}/approve/briefs` | POST | `{ brief_id, decision: "approve" }` |
| Approve article | `/api/v1/content/v13/{run_id}/approve/content` | POST | `{ brief_id, decision: "approve" }` |
| Send back for revision | `/api/v1/content/v13/{run_id}/approve/content` | POST | `{ brief_id, decision: "edit", editor_notes }` |
| CPS prediction scores | `/api/v1/cps/score` | POST | Score content before publish |
| Publish to CMS | `/api/v1/cms/publish` | POST | `{ brief_id, status: "publish", collection_id? }` → `{ cms_post_id, url }` (Webflow: pass `collection_id` when multiple collections enabled) |
| CMS connection (Content Studio) | `/api/v1/cms/connection` | GET | `{ provider, provider_config, sync_post_count, ... }` |
| Article metadata (slug, meta, tags) | `/api/v1/companies/{slug}/content/briefs/{brief_id}` | GET | Brief detail includes content metadata |

**Column ↔ Status mapping:**

| Frontend Column | Backend Status | Pipeline State |
|---|---|---|
| Queue | Brief has no active `run_id` | Not started |
| Agent Work | `running` | Pipeline active (planning/writing/evaluating) |
| Your Review | `pending_approval` | Awaiting HITL decision |
| Published | `completed` + CMS published | Done |

**Integration notes:**
- The content studio is the most complex integration — it combines content pipeline management, real-time SSE progress, HITL approvals, and CMS publishing
- Each card's "stage" maps to the content v1.3 pipeline stages: `topic_selection → brief_generation → brief_review → writing → evaluation → content_review`
- The "cycle" concept (weekly content sprints) doesn't exist in the backend yet

---

## 12. Brand Hub / Artifacts

**Route:** `/artifacts`

**Current frontend data sources — this is the ONLY page reading real files:**

| File-Based Loader | File(s) Read | Backend Endpoint | Method | Response Mapping |
|---|---|---|---|---|
| `getKnowledgeBase()` | `data/artifacts/knowledge_base/lovable/*/v1.md` (5 docs) | `/api/v1/artifacts/knowledge_base/{slug}/{filename}` | GET | Returns markdown content per doc |
| — (alternative) | — | `/api/v1/companies/{slug}/research/artifacts` | GET | `ResearchArtifactsResponse { company_context, personas[], style_guide }` — bundled |
| `getVoiceGuide()` | `data/artifacts/voice_style_guide/lovable/guide/v1.md` | `/api/v1/voice-style-guide/{slug}/guide` | GET | `{ guide_md, version, word_count, source_authors[] }` |
| `getPersonas()` | `data/artifacts/audience_personas/lovable/*/v1.md` | `/api/v1/audience-persona/{slug}/personas` | GET | `PersonaListResponse { personas[] }` — each has profile data |

**Knowledge Base documents:**

| Current File Path | KB Doc Type | Backend Retrieval |
|---|---|---|
| `knowledge_base/lovable/company_overview/v1.md` | Company Overview | `/api/v1/artifacts/knowledge_base/{slug}/company_overview/v1.md` |
| `knowledge_base/lovable/brand_perception/v1.md` | Brand Perception | Same pattern with `brand_perception` |
| `knowledge_base/lovable/competitor_registry/v1.md` | Competitor Registry | Same pattern with `competitor_registry` |
| `knowledge_base/lovable/customer_reviews/v1.md` | Customer Reviews | Same pattern with `customer_reviews` |
| `knowledge_base/lovable/weakness_analysis/v1.md` | Weakness Analysis | Same pattern with `weakness_analysis` |

**Knowledge Base health & refresh:**

| Frontend Action | Backend Endpoint | Method |
|---|---|---|
| Check KB freshness | `/api/v1/knowledge-base/{slug}/health` | GET |
| Refresh stale docs | `/api/v1/knowledge-base/{slug}/refresh-stale` | POST |
| Upload custom doc | `/api/v1/companies/{slug}/knowledge-docs` | POST (multipart) |
| List uploaded docs | `/api/v1/companies/{slug}/knowledge-docs` | GET |

**Integration notes:**
- This page currently uses `fs.readFileSync()` (server-side) — must switch to API calls
- The artifacts endpoint serves files from blob storage (R2), not filesystem
- The `/research/artifacts` bundled endpoint is the most efficient for initial load
- Individual doc refresh uses the Knowledge Base pipeline with `mode: "single"`

---

## 13. Settings

**Route:** `/settings`

**Current frontend:** 5 tabs, all hardcoded mock data.

### Team Tab

| Mock Data | Backend Endpoint | Method | Response |
|---|---|---|---|
| 4 hardcoded team members | `/api/v1/companies/{slug}/settings/team` | GET | `TeamListResponse { members[] }` |
| Update member role | `/api/v1/companies/{slug}/settings/team/{user_id}` | PUT | `{ role: "editor" }` |
| Generate invite code | `/api/v1/auth/invite` | POST | `{ invite_code, company_slug, role }` |

### Models Tab

| Mock Data | Backend Endpoint | Method | Response |
|---|---|---|---|
| 4 model configs with token usage | **Not yet available** | — | Model configuration not exposed via API (see [Gaps](#16-gaps--new-backend-work-needed)) |

### Integrations Tab

| Mock Data | Backend Endpoint | Method | Response |
|---|---|---|---|
| 7 integrations (CMS + GA4) | `/api/v1/cms/connection` | GET | `CMSConnectionInfoResponse` (WordPress or Webflow) |
| Connect WordPress | `/api/v1/cms/connect` | POST | `{ provider: "wordpress", site_url, username, api_key }` |
| Connect Webflow (step 1) | `/api/v1/cms/connect` | POST | `{ provider: "webflow", site_url, api_key }` (Site API Token) |
| Webflow collections | `/api/v1/cms/webflow/collections` | GET | Collection list for configure wizard |
| Webflow field schema | `/api/v1/cms/webflow/collections/{id}/fields` | GET | Fields + `suggested_mapping` |
| Webflow configure + sync | `/api/v1/cms/webflow/configure` | POST | `{ site_id, collections[], default_collection_id, trigger_sync: true }` |
| GA4 connection | **GA4 integration (in progress)** | — | DB layer done, endpoints pending |

### Billing Tab

| Mock Data | Backend Endpoint | Method | Response |
|---|---|---|---|
| Usage meters, plan tiers | **Not yet available** | — | Needs billing/usage API (see [Gaps](#16-gaps--new-backend-work-needed)) |

### Notifications Tab

| Mock Data | Backend Endpoint | Method | Response |
|---|---|---|---|
| 8 notification preferences | **Not yet available** | — | Needs notification preferences API |

### Company Profile (implicit)

| Mock Data | Backend Endpoint | Method | Response |
|---|---|---|---|
| Company name, domain | `/api/v1/companies/{slug}/settings/profile` | GET | `CompanyProfileSettingsResponse` |
| Update profile | `/api/v1/companies/{slug}/settings/profile` | PUT | `{ name?, domain?, industry? }` |
| Pipeline defaults | `/api/v1/companies/{slug}/settings/pipeline-defaults` | GET | `PipelineDefaultsResponse` |

---

## 14. Attribution

**Route:** `/attribution`

**Current frontend:** All hardcoded mock data with a demo banner. This is the most integration-dependent page.

| Mock Data | Backend Endpoint | Method | Notes |
|---|---|---|---|
| `kpis` — AI-sourced traffic, demo requests, pipeline, revenue | **GA4 integration (in progress)** | — | Traffic from GA4, conversions from CRM integration |
| `funnelStepsAll[]` — 6-step attribution funnel | **Not yet available** | — | Needs full attribution pipeline |
| `platformData` — per-platform impressions→revenue | **Not yet available** | — | Combines Daily Tracker + GA4 + CRM data |
| `roiTableData[]` — content ROI with per-platform breakdown | **Not yet available** | — | Needs content-level attribution tracking |
| `trendData[]` — 12-week traffic trend | **GA4 integration** | — | `ga4_traffic_data` table exists, API pending |

**Integration notes:**
- Attribution is the LEAST backend-ready page
- Requires: GA4 integration (in progress), CRM integration (not started), and a new attribution computation pipeline
- The frontend correctly shows a "Demo data" banner
- Partial data may be available from Daily Tracker + GA4 once those integrations are complete

---

## 15. Cross-Cutting: SSE Task Streaming

The SSE system is used across multiple pages for real-time pipeline progress.

**Endpoint:** `GET /api/v1/tasks/{run_id}/events`

**Auth:** Bearer token OR `?stream_token={token}` (5-min expiry, obtained via `POST /api/v1/tasks/{task_id}/stream-token`)

**Event flow:**
```
pipeline_start → stage_start → stage_complete → ... → pending_approval → approval_received → ... → completed
```

**Pages that need SSE:**

| Page | When SSE is Used |
|---|---|
| `/onboarding` | Full onboarding pipeline progress |
| `/content-studio` | Content generation progress (planning → writing → evaluation) |
| `/planner` | Topic discovery pipeline progress |
| `/artifacts` | Knowledge base refresh, persona generation, voice guide generation |
| Any page triggering a pipeline | Site audit, gap analysis re-run, etc. |

**Frontend implementation pattern:**
```typescript
// 1. Get stream token
const { stream_token } = await fetch(`/api/v1/tasks/${runId}/stream-token`, { method: 'POST' });

// 2. Connect SSE
const es = new EventSource(`/api/v1/tasks/${runId}/events?stream_token=${stream_token}`);

// 3. Handle events
es.addEventListener('stage_start', (e) => updateProgress(JSON.parse(e.data)));
es.addEventListener('pending_approval', (e) => showApprovalUI(JSON.parse(e.data)));
es.addEventListener('completed', (e) => { showResults(JSON.parse(e.data)); es.close(); });
es.addEventListener('failed', (e) => { showError(JSON.parse(e.data)); es.close(); });
```

---

## 16. Gaps & New Backend Work Needed

These are data points the frontend needs that the backend does NOT currently provide:

| Gap | Frontend Page(s) | Proposed Solution | Priority |
|---|---|---|---|
| **Sentiment analysis** — sentiment of AI responses toward brand | Citation Intelligence, Home | Add sentiment scoring to gap analysis or daily tracker pipeline | Medium |
| **Answer history storage** — full AI response text over time | Prompt Tracking | Store raw AI responses in daily tracker runs, add retrieval endpoint | High |
| **Content cycles/sprints** — weekly content batching | Content Studio | Add cycle management to content pipeline (create/archive cycles, assign briefs to cycles) | Medium |
| **Content cannibalization detection** — overlapping content | Content Performance | Add content overlap analysis to CPS or gap analysis | Low |
| **Snippet readiness distribution** — readiness histogram | Technical Readiness | Extend site audit with snippet/featured-snippet readiness scoring | Low |
| **Attribution pipeline** — full funnel from citation to revenue | Attribution | New pipeline combining Daily Tracker + GA4 + CRM data | High (but complex) |
| **GA4 analytics endpoints** — traffic, conversions, AI referrals | Attribution, Content Performance | Complete GA4 integration (DB done, service/router pending) | High |
| **Model configuration API** — LLM model settings | Settings | Expose model config via settings endpoint | Low |
| **Billing/usage API** — usage meters, plan management | Settings | New billing service or Stripe integration | Medium |
| **Notification preferences API** — email/in-app toggles | Settings | Add notification settings to user preferences | Low |
| **Presence score trajectory** — monthly aggregated scores | Home | Add monthly aggregation to SPA trend or daily tracker | Low |
| **CRM integration** — Salesforce/HubSpot connection | Settings, Attribution | New CRM adapter following CMS integration pattern | High |

---

## Unused `src/data/` Loaders (Dead Code)

These loader files exist in the frontend but are NOT imported by any page. They were likely built for the V0 frontend:

| File | Reads From | Status |
|---|---|---|
| `src/data/gap-report.ts` | `data/artifacts/gap_analysis/lovable/gap_report.json` | Dead code — replaced by hardcoded mocks in `/analytics` |
| `src/data/topics.ts` | Derives from `gap-report.ts` | Dead code — replaced by hardcoded mocks in `/planner` |
| `src/data/embeddings.ts` | `data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_*.json` | Dead code — replaced by hardcoded mocks in `/embedding-lab` |
| `src/data/site-audit.ts` | `data/artifacts/site_audit/lovable/*/audit_result.json` | Dead code — replaced by hardcoded mocks in `/technical-readiness` |
| `src/data/content-briefs.ts` | `data/artifacts/content/carta/briefs.json` + markdown files | Dead code — replaced by hardcoded mocks in `/content-studio` |

These can be deleted during integration or repurposed as API client utilities.

---

## Integration Priority Order

Based on data readiness and user impact:

1. **Auth** (`/login`, `/register`, `/join`) — Backend fully ready
2. **Brand Hub** (`/artifacts`) — Backend fully ready (just switch fs.read → API calls)
3. **Embedding Lab** (`/embedding-lab`) — Backend fully ready
4. **Citation Intelligence** (`/analytics`) — Backend mostly ready (gap analysis endpoints)
5. **Competitive Position** (`/competitive-position`) — Backend mostly ready
6. **Technical Readiness** (`/technical-readiness`) — Backend mostly ready (site audit + log service)
7. **Content Planner** (`/planner`) — Backend mostly ready (topic discovery endpoints)
8. **Content Studio** (`/content-studio`) — Backend ready for core flow, needs cycle management
9. **Content Performance** (`/content-performance`) — Partially ready, needs GA4
10. **Prompt Tracking** (`/prompt-tracking`) — Partially ready, needs answer history
11. **Home Dashboard** (`/`) — Composite view, needs multiple endpoints working
12. **Settings** (`/settings`) — Partially ready (team, profile, CMS)
13. **Onboarding** (`/onboarding`) — Backend fully ready (pipeline + SSE)
14. **Attribution** (`/attribution`) — Least ready, needs GA4 + CRM + attribution pipeline
