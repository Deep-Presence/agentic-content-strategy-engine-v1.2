# API Routers

> **Location:** `api/routers/`
> **Owner:** API
> **Dependencies:** All services, task store, event bus
> **Dependents:** Frontend (via BFF proxy)
> **Last Updated:** 2026-04-09

## Overview

31 router files defining 150+ endpoints organized by domain. All pipeline launch endpoints return 202 Accepted with a task_id for SSE tracking. Data endpoints return domain-specific response schemas.

## Route Inventory

### Infrastructure (18 routes)

| Router | Method | Path | Description |
|--------|--------|------|-------------|
| health | GET | `/health` | Liveness check |
| health | GET | `/readiness` | Dependency health |
| auth | POST | `/auth/register` | Create account + company |
| auth | POST | `/auth/login` | Get access token |
| auth | GET | `/auth/me` | Current user profile |
| auth | POST | `/auth/invite` | Generate invite code |
| auth | POST | `/auth/join` | Redeem invite |
| tasks | GET | `/tasks` | List tasks (filtered by company) |
| tasks | GET | `/tasks/{id}` | Task detail |
| tasks | POST | `/tasks/{id}/cancel` | Cancel running task |
| tasks | POST | `/tasks/{id}/stream-token` | Get SSE stream token |
| events | GET | `/tasks/{id}/events` | SSE event stream |
| company_stream | GET | `/companies/{slug}/stream` | Company-wide SSE |
| companies | GET | `/companies/{slug}` | Company profile |
| companies | POST/GET/PUT/DELETE | `/companies/{slug}/products/*` | Product CRUD |
| settings | GET/PUT | `/settings/team/*` | Team management |
| settings | GET/PUT | `/settings/profile` | Company profile |
| settings | GET/PUT | `/settings/pipeline-defaults` | Pipeline defaults |

### Pipeline Launch (42 routes)

| Router | Endpoints | Key Routes |
|--------|-----------|------------|
| gap_analysis | 2 | `POST /start`, `GET /{id}/status` |
| content_v13 | 8 | `POST /start`, 3 approve endpoints, `POST /from-topics` (3 variants) |
| knowledge_base | 3 | `POST /`, `GET /{id}/status`, `POST /{id}/approve` |
| audience_persona | 7 | `POST /`, approve briefs/profiles, add persona |
| voice_style_guide | 4 | `POST /`, approve authors |
| topic_discovery | 14 | `POST /`, approve taxonomy/subdomains/matrix, expansion, CRUD |
| site_audit | 6 | `POST /`, status, list/detail/findings/readiness |
| onboarding | 2 | `POST /start`, `GET /{id}/status` |
| research_orchestrator | 2 | `POST /start`, `GET /{id}/status` |

### Data Read/Write (60+ routes)

| Router | Endpoints | Description |
|--------|-----------|-------------|
| gap_data | 10 | Summary, queries, clusters, signals, platforms, heatmap, embeddings, trend, profiles, gaps |
| content_data | 4 | Briefs list/detail, stage content, add brief |
| brand_data | 2 | Research artifacts, run history |
| content_inventory | 7 | List, stats, detail, import, embeddings, delete |
| content_performance | 4 | Table, velocity, similar, detail |
| content_to_prompt | 7 | Generate, list by page, metrics, pending, approve |
| daily_tracker | 14 | Prompt CRUD, fanout management, import/bulk |
| cms | 11 | Connect, sync, publish, refresh, stale actions, categories |
| analytics | 8 | OAuth flow, connection, properties, sync |
| artifacts | 4 | List, download, upload |
| knowledge_docs | 5 | Upload, list, detail, delete, download |
| cps | 1 | Score prediction |

## Common Patterns

- **Pipeline launch:** `POST → create_task_durable() → asyncio.create_task(runner) → 202`
- **Approval:** `POST /{id}/approve → task_store.submit_approval() → pipeline resumes`
- **Data read:** `GET → service.get_*() → schema.model_validate() → 200`
- **Tenant isolation:** All data routes use `require_tenant(slug)` or `require_company_access(slug)`
