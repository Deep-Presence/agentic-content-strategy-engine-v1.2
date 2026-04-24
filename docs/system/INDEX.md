# Content Strategy Engine — System Documentation Index

> **Last Updated:** 2026-04-24
> **Total Documentation Files:** 39/39 (All phases complete)
> **Last Bulk Update:** 15 files updated to cover TD-entry parallelism, cannibalization revamp, and scalability changes (commits a9b85f5..HEAD)

## Phase 1: Architecture & Infrastructure

| # | Document | Description |
|---|----------|-------------|
| 00 | [Architecture Overview](00-ARCHITECTURE-OVERVIEW.md) | System-wide architecture, pipelines, tech stack, data flow, security model |
| 01 | [Core Config](01-CORE-CONFIG.md) | Pydantic Settings — 113 fields, env vars, computed properties |
| 02 | [Core Models](02-CORE-MODELS.md) | Pydantic models — 16 files, 100+ models, 30+ enums |
| 03 | [Core DB](03-CORE-DB.md) | SQLAlchemy ORM — 28 tables, 33 repos, 41 migrations, pgvector. **Updated:** migrations 0038-0041 (content_engine_runs, scheduler state, freshness, cannibalization), async pool 15/20 |
| 04 | [Core Auth](04-CORE-AUTH.md) | Auth service protocol, DbAuthService, tokens, passwords |
| 05 | [Core Events](05-CORE-EVENTS.md) | CompanyEventBus — **Updated:** Redis Streams backing, `topic_run_changed` event, per-topic fanout for TD-entry parallelism, `Last-Event-ID` replay |
| 06 | [Core Storage](06-CORE-STORAGE.md) | StorageBackend ABC — Local, R2, Cached backends, Supabase mirror |
| 07 | [Core Redis](07-CORE-REDIS.md) | Redis infrastructure — **Updated:** semaphore `renew()`/`suspend()`/`resume()`, per-company CE pool, `force_clear()` startup purge, SCAN-based cache delete |
| 08 | [Core Shared Tools](08-CORE-SHARED-TOOLS.md) | Embeddings, vector store, cost tracker, tracing, logging, OpenRouter |

## Phase 2: Service Layer

| # | Document | Description |
|---|----------|-------------|
| 09 | [Core Services](09-CORE-SERVICES.md) | **Updated:** NEW `ContentEngineTopicRunService` (898 lines, durable TD-entry state, scheduler state machine), `DbTaskStore` per-company CE pool + suspend/resume, `CMSService` SEO metadata + auto-prompt, `ContentPerformanceService` structural score + freshness benchmark, scalability themes |

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
| 14 | [Pipeline: Gap Analysis](14-PIPELINE-GAP-ANALYSIS.md) | Pipeline 2 — **Updated:** S4 freshness date extraction, migration 0040, cited-exemplar freshness benchmark feeding Content Performance |
| 15 | [Pipeline: Content Engine](15-PIPELINE-CONTENT-ENGINE.md) | Pipeline 3 v1.3 — **Updated:** TWO execution models (legacy manual vs TD-entry parallel), deep parallelism design (durable state tables, per-company CE pool, slot suspend/resume, scheduler state machine, startup reconciliation, claimed-resume, per-card SSE fanout) |
| 16 | [Pipeline: Topic Discovery](16-PIPELINE-TOPIC-DISCOVERY.md) | Pipeline 4 — **Updated:** NEW cannibalization detection subsystem (Phase 1 planner scoring + Phase 2 fanout-aware overlap evidence, zero-LLM design, weighted scoring formula, two-surface persistence, delta scope resolver, async runner) |

## Phase 5: Pipeline Documentation — Orchestration & Auxiliary

| # | Document | Description |
|---|----------|-------------|
| 17 | [Pipeline: Onboarding](17-PIPELINE-ONBOARDING.md) | Pipeline 5 — 3-phase meta-orchestrator, 6 sub-pipelines |
| 18 | [Core Orchestration](18-CORE-ORCHESTRATION.md) | **Updated:** batch_run + N topic_run creation, dispatcher handoff, Step 2a snap-back guard, zero-pieces revert, error path Redis phase reversion, orchestrator no longer holds slug lock |
| 19 | [CPS Model](19-CORE-CPS-MODEL.md) | Neural citation predictor — 3-stream encoder, dual heads |
| 20 | [Daily Tracker](20-CORE-DAILY-TRACKER.md) | Mediator pattern — platform runner, mention detection, 4 metrics |
| 21 | [Reddit HIL](21-CORE-REDDIT-HIL.md) | LangGraph pipeline — PRAW, keyword scoring, Gemini drafts |
| 22 | [Core CMS](22-CORE-CMS.md) | **Updated:** Yoast SEO field mapping, auto-sync on first connect, auto-prompt generation chain, cache invalidation strategy, tz-aware datetime fix |
| 23 | [Core Analytics](23-CORE-ANALYTICS.md) | **Updated:** GA4 adapter hardening (retry, error taxonomy, pagePath), AI referral batch CASE/WHEN, per-page aggregation queries for Content Performance |
| 24 | [Content Inventory](24-CORE-CONTENT-INVENTORY.md) | **Updated:** `enrich_thin_pages()`, content-to-prompt pipeline integration (6 endpoints), security hardening, unpublished pages staging |
| 25 | [Audit Logging](25-CORE-AUDIT-LOGGING.md) | Dual-mode audit, sensitive data masking |

## Phase 6: API Layer

| # | Document | Description |
|---|----------|-------------|
| 26 | [API Overview](26-API-OVERVIEW.md) | App factory, middleware chain, DI container, exception handlers |
| 27 | [API Auth](27-API-AUTH.md) | Pure ASGI middleware, RBAC dependencies, stream tokens |
| 28 | [API Routers](28-API-ROUTERS.md) | **Updated:** `content_v13.py` deep-dive (15 endpoints), TD-entry Phase 1/2 split, durable continuation approval flow, company SSE, content_performance readiness + freshness, CMS auto-sync |
| 29 | [API Schemas](29-API-SCHEMAS.md) | **Updated:** `TopicRunSummaryV13`, `TopicContentProductionRequest`, `FreshnessAssessment`, `ContentPerformanceReadinessResponse`, `ContentPublishMetadata`, `CMSCategoryItem`, `DisconnectResponse` |
| 30 | [API Services](30-API-SERVICES.md) | API-level data reshaping, Redis caching, path validation |
| 31 | [API Tasks](31-API-TASKS.md) | **Updated:** TD-entry dispatcher (`dispatch_queued_td_content_runs`), per-topic CE runner, HITL slot release, claimed-resume, startup reconciliation, F18 Redis GA-phase reversion fix, error path guarantees |

## Phase 7: Frontend

| # | Document | Description |
|---|----------|-------------|
| 32 | [Frontend Overview](32-FRONTEND-OVERVIEW.md) | BFF proxy, 5 Zustand stores, 28 components, design system |
| 33 | [Frontend Dashboard Pages](33-FRONTEND-DASHBOARD-PAGES.md) | **Updated:** Content Studio topic-run-centric kanban (3-layer SSE strategy, version-aware merge, per-card activity feed, Tiptap editor), Content Performance (unpublished staging, freshness benchmarks, CMS sync), Planner (cannibalization badges + evidence panel, batch dispatch), Settings (GA4 3-state connect flow) |
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
| How does **TD-entry parallel CE** work? | [15](15-PIPELINE-CONTENT-ENGINE.md) (architecture) + [31](31-API-TASKS.md) (dispatcher) + [09](09-CORE-SERVICES.md) (durable state service) + [03](03-CORE-DB.md) (tables) |
| How does **cannibalization detection** work? | [16](16-PIPELINE-TOPIC-DISCOVERY.md) (scoring + evidence) + [03](03-CORE-DB.md) (migration 0041) + [33](33-FRONTEND-DASHBOARD-PAGES.md) (planner UI) |
| How does **freshness benchmarking** work? | [14](14-PIPELINE-GAP-ANALYSIS.md) (S4 extraction) + [03](03-CORE-DB.md) (migration 0040) + [23](23-CORE-ANALYTICS.md) (GA4 per-page) + [33](33-FRONTEND-DASHBOARD-PAGES.md) (drawer) |
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
| How does the CMS integration work? | [22-CORE-CMS.md](22-CORE-CMS.md) |
| How does GA4 analytics work? | [23-CORE-ANALYTICS.md](23-CORE-ANALYTICS.md) |
| How do I deploy? | [37-SCRIPTS-AND-TOOLING.md](37-SCRIPTS-AND-TOOLING.md) |

---

## Recent Update Summary (2026-04-24)

15 files updated to reflect changes from commits `a9b85f5..HEAD` (13 commits, ~22K insertions, ~150 files changed). Key themes:

### TD-Entry Parallel Content Engine Execution
- **What:** Multiple topic assignments now flow through gap analysis and the Content Engine in parallel, each with its own durable `topic_run` row, scheduler state, and per-card SSE events.
- **Where:** [15](15-PIPELINE-CONTENT-ENGINE.md) (pipeline design), [31](31-API-TASKS.md) (dispatcher + runner), [09](09-CORE-SERVICES.md) (`ContentEngineTopicRunService`), [03](03-CORE-DB.md) (migrations 0038/0039), [07](07-CORE-REDIS.md) (per-company CE semaphore pool), [18](18-CORE-ORCHESTRATION.md) (orchestrator handoff), [28](28-API-ROUTERS.md) (Phase 1/2 endpoints), [05](05-CORE-EVENTS.md) (topic_run_changed events), [33](33-FRONTEND-DASHBOARD-PAGES.md) (kanban 3-layer update strategy).

### Cannibalization Detection Subsystem
- **What:** Zero-LLM scoring pipeline using pgvector + SQL + Python that detects when a proposed topic overlaps with existing published content, with Phase 1 planner scoring and Phase 2 fanout-aware overlap evidence.
- **Where:** [16](16-PIPELINE-TOPIC-DISCOVERY.md) (algorithm + persistence), [03](03-CORE-DB.md) (migration 0041), [33](33-FRONTEND-DASHBOARD-PAGES.md) (planner badges + evidence drawer).

### Content Performance & Freshness Benchmarking
- **What:** Cited-exemplar freshness dates extracted from gap analysis S4, GA4 per-page aggregation queries, structural composite scores, unpublished pages staging.
- **Where:** [14](14-PIPELINE-GAP-ANALYSIS.md) (S4 freshness), [23](23-CORE-ANALYTICS.md) (GA4 hardening), [24](24-CORE-CONTENT-INVENTORY.md) (thin-page enrichment), [33](33-FRONTEND-DASHBOARD-PAGES.md) (Content Performance page).

### CMS & Analytics Hardening
- **What:** WordPress SEO metadata roundtrip (Yoast), auto-sync on first connect, auto-prompt generation chain, GA4 retry + error taxonomy, AI referral batch classification.
- **Where:** [22](22-CORE-CMS.md), [23](23-CORE-ANALYTICS.md), [29](29-API-SCHEMAS.md).
