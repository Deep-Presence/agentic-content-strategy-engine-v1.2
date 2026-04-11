# Content Strategy Engine — System Documentation Index

> **Last Updated:** 2026-04-09
> **Total Documentation Files:** 39/39 (All phases complete)

## Phase 1: Architecture & Infrastructure

| # | Document | Description |
|---|----------|-------------|
| 00 | [Architecture Overview](00-ARCHITECTURE-OVERVIEW.md) | System-wide architecture, pipelines, tech stack, data flow, security model |
| 01 | [Core Config](01-CORE-CONFIG.md) | Pydantic Settings — 113 fields, env vars, computed properties |
| 02 | [Core Models](02-CORE-MODELS.md) | Pydantic models — 16 files, 100+ models, 30+ enums |
| 03 | [Core DB](03-CORE-DB.md) | SQLAlchemy ORM — 25 tables, 30 repos, 37 migrations, pgvector |
| 04 | [Core Auth](04-CORE-AUTH.md) | Auth service protocol, DbAuthService, tokens, passwords |
| 05 | [Core Events](05-CORE-EVENTS.md) | CompanyEventBus — in-memory pub/sub, SSE integration |
| 06 | [Core Storage](06-CORE-STORAGE.md) | StorageBackend ABC — Local, R2, Cached backends, Supabase mirror |
| 07 | [Core Redis](07-CORE-REDIS.md) | Redis infrastructure — clients, semaphore, cache, checkpointer, key schema |
| 08 | [Core Shared Tools](08-CORE-SHARED-TOOLS.md) | Embeddings, vector store, cost tracker, tracing, logging, OpenRouter |

## Phase 2: Service Layer

| # | Document | Description |
|---|----------|-------------|
| 09 | [Core Services](09-CORE-SERVICES.md) | 33 service files — Protocol pattern, Json/Db dual-mode, cache helpers |

## Phase 3: Pipeline Documentation — Research

| # | Document | Description |
|---|----------|-------------|
| 10 | [Pipeline: Site Audit](10-PIPELINE-SITE-AUDIT.md) | Pipeline 0 — 6-step deterministic crawler, 8-dimension scoring, AEO |
| 11 | [Pipeline: Knowledge Base](11-PIPELINE-KNOWLEDGE-BASE.md) | Pipeline 1a — 6-agent DAG, 3 HITL, staleness, 4 execution modes |
| 12 | [Pipeline: Audience Persona](12-PIPELINE-AUDIENCE-PERSONA.md) | Pipeline 1b — 2-agent, 2 HITL, persona embeddings |
| 13 | [Pipeline: Voice Style Guide](13-PIPELINE-VOICE-STYLE-GUIDE.md) | Pipeline 1c — 3-agent, 1 HITL, style guide promotion |

## Phase 4: Pipeline Documentation — Analysis & Content

| # | Document | Description |
|---|----------|-------------|
| 14 | [Pipeline: Gap Analysis](14-PIPELINE-GAP-ANALYSIS.md) | Pipeline 2 — 8 steps, 4 search engines, 8,100 lines |
| 15 | [Pipeline: Content Engine](15-PIPELINE-CONTENT-ENGINE.md) | Pipeline 3 v1.3 — 6 stages, 5 evaluators, 3 HITL, 10,000 lines |
| 16 | [Pipeline: Topic Discovery](16-PIPELINE-TOPIC-DISCOVERY.md) | Pipeline 4 — 4 sources, 4-dim scoring, cannibalization, 9,664 lines |

## Phase 5: Pipeline Documentation — Orchestration & Auxiliary

| # | Document | Description |
|---|----------|-------------|
| 17 | [Pipeline: Onboarding](17-PIPELINE-ONBOARDING.md) | Pipeline 5 — 3-phase meta-orchestrator, 6 sub-pipelines |
| 18 | [Core Orchestration](18-CORE-ORCHESTRATION.md) | TD->GA->CE pipeline, 3 entry patterns, Redis GA-phase cards |
| 19 | [CPS Model](19-CORE-CPS-MODEL.md) | Neural citation predictor — 3-stream encoder, dual heads |
| 20 | [Daily Tracker](20-CORE-DAILY-TRACKER.md) | Mediator pattern — platform runner, mention detection, 4 metrics |
| 21 | [Reddit HIL](21-CORE-REDDIT-HIL.md) | LangGraph pipeline — PRAW, keyword scoring, Gemini drafts |
| 22 | [Core CMS](22-CORE-CMS.md) | Adapter pattern — WordPress REST API, Fernet encryption |
| 23 | [Core Analytics](23-CORE-ANALYTICS.md) | GA4 OAuth + sync + AI referral classification |
| 24 | [Content Inventory](24-CORE-CONTENT-INVENTORY.md) | Universal content registry, cannibalization detection |
| 25 | [Audit Logging](25-CORE-AUDIT-LOGGING.md) | Dual-mode audit, sensitive data masking |

## Phase 6: API Layer

| # | Document | Description |
|---|----------|-------------|
| 26 | [API Overview](26-API-OVERVIEW.md) | App factory, middleware chain, DI container, exception handlers |
| 27 | [API Auth](27-API-AUTH.md) | Pure ASGI middleware, RBAC dependencies, stream tokens |
| 28 | [API Routers](28-API-ROUTERS.md) | 31 routers, 150+ endpoints — full route inventory |
| 29 | [API Schemas](29-API-SCHEMAS.md) | 21 schema files — all request/response models |
| 30 | [API Services](30-API-SERVICES.md) | API-level data reshaping, Redis caching, path validation |
| 31 | [API Tasks](31-API-TASKS.md) | DbTaskStore, RedisEventBus, 18 pipeline runners, SSE streaming |

## Phase 7: Frontend

| # | Document | Description |
|---|----------|-------------|
| 32 | [Frontend Overview](32-FRONTEND-OVERVIEW.md) | BFF proxy, 5 Zustand stores, 28 components, design system |
| 33 | [Frontend Dashboard Pages](33-FRONTEND-DASHBOARD-PAGES.md) | All 12 dashboard pages with integration status |
| 34 | [Frontend Components](34-FRONTEND-COMPONENTS.md) | 28 shared UI components + auth components |
| 35 | [Frontend Auth & Onboarding](35-FRONTEND-AUTH-ONBOARDING.md) | Auth flow, cross-tab sync, onboarding wizard |
| 36 | [Frontend BFF & API](36-FRONTEND-BFF-API.md) | BFF proxy routes, cookie management, catch-all proxy |

## Phase 8: Testing, Scripts & Deployment

| # | Document | Description |
|---|----------|-------------|
| 37 | [Scripts & Tooling](37-SCRIPTS-AND-TOOLING.md) | 17 pipeline scripts, Docker, CI/CD |
| 38 | [Testing Guide](38-TESTING-GUIDE.md) | 2,100+ tests, 299 files, fixtures, patterns |

---

## Quick Reference

| Question | Document |
|----------|----------|
| How does pipeline X work? | Files [10](10-PIPELINE-SITE-AUDIT.md)-[18](18-CORE-ORCHESTRATION.md) |
| What does this Pydantic model look like? | [02-CORE-MODELS.md](02-CORE-MODELS.md) |
| What tables are in the DB? | [03-CORE-DB.md](03-CORE-DB.md) |
| How does auth work? | [04-CORE-AUTH.md](04-CORE-AUTH.md) + [27-API-AUTH.md](27-API-AUTH.md) |
| How does Redis fit in? | [07-CORE-REDIS.md](07-CORE-REDIS.md) |
| What LLM providers does this use? | [00-ARCHITECTURE-OVERVIEW.md](00-ARCHITECTURE-OVERVIEW.md) |
| What settings can I configure? | [01-CORE-CONFIG.md](01-CORE-CONFIG.md) |
| What API endpoints exist? | [28-API-ROUTERS.md](28-API-ROUTERS.md) |
| How is the frontend structured? | Files [32](32-FRONTEND-OVERVIEW.md)-[36](36-FRONTEND-BFF-API.md) |
| How do I write tests? | [38-TESTING-GUIDE.md](38-TESTING-GUIDE.md) |
| How do services work? | [09-CORE-SERVICES.md](09-CORE-SERVICES.md) |
| How does SSE streaming work? | [31-API-TASKS.md](31-API-TASKS.md) + [05-CORE-EVENTS.md](05-CORE-EVENTS.md) |
| How does storage work? | [06-CORE-STORAGE.md](06-CORE-STORAGE.md) |
| How do I deploy? | [37-SCRIPTS-AND-TOOLING.md](37-SCRIPTS-AND-TOOLING.md) |
