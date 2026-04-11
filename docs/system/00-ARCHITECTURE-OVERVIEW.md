# Architecture Overview

> **Location:** Root (`content-strategy-engine/`)
> **Owner:** Full Stack
> **Last Updated:** 2026-04-09

## Overview

The Content Strategy Engine is the core product of **Deep Presence** — a platform that helps B2B companies get cited in AI search results (Perplexity, ChatGPT, Claude, Gemini). The system analyzes a company's web presence, identifies gaps in AI visibility, generates optimized content, and tracks citation performance across AI platforms.

The application is a full-stack system with a Python backend (FastAPI + async pipelines), a Next.js 14 frontend, PostgreSQL for persistence, and Redis for real-time coordination. It orchestrates eight distinct pipelines, two monitoring systems, and a neural ranking model — all exposed through a RESTful API with SSE streaming.

## System Architecture

```
                                    ┌─────────────────────────────┐
                                    │     Next.js 14 Frontend     │
                                    │   (App Router, Zustand, BFF)│
                                    └─────────────┬───────────────┘
                                                  │ httpOnly cookie
                                                  │ Same-origin /api/v1/...
                                    ┌─────────────▼───────────────┐
                                    │    BFF Proxy Layer           │
                                    │  (Cookie → Bearer token)    │
                                    └─────────────┬───────────────┘
                                                  │ Bearer token
                                    ┌─────────────▼───────────────┐
                                    │     FastAPI Backend          │
                                    │  (ASGI Middleware, RBAC)     │
                                    │  31 routers, 21 schemas      │
                                    └──┬──────┬──────┬──────┬─────┘
                                       │      │      │      │
                          ┌────────────▼─┐  ┌─▼────┐ │   ┌──▼──────────┐
                          │  PostgreSQL  │  │Redis │ │   │ Cloudflare  │
                          │  (pgvector)  │  │      │ │   │ R2 Storage  │
                          └──────────────┘  └──────┘ │   └─────────────┘
                                                     │
                                    ┌────────────────▼────────────────┐
                                    │      Core Pipeline Engine       │
                                    │  8 pipelines + 2 monitors       │
                                    │  LangGraph HITL, LiteLLM,       │
                                    │  asyncio background tasks        │
                                    └────────────────┬────────────────┘
                                                     │
                              ┌──────────┬───────────┼───────────┬──────────┐
                              │          │           │           │          │
                         ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐
                         │OpenAI  │ │Anthropic│ │Google  │ │Perplx  │ │LangSmith│
                         │(embed) │ │(Claude) │ │(Gemini)│ │(Sonar) │ │(trace) │
                         └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

## Pipelines

The system orchestrates eight pipelines, two monitors, and a neural model:

| # | Pipeline | Purpose | LLM Providers | HITL |
|---|----------|---------|---------------|------|
| 0 | **Site Audit** | Deterministic 6-step crawler + SEO analysis | None (no LLM) | No |
| 1a | **Knowledge Base** | 6-agent DAG for company research | Perplexity, Anthropic | 3 checkpoints |
| 1b | **Audience Persona** | 2-agent persona discovery + generation | Gemini, Perplexity | 2 checkpoints |
| 1c | **Voice Style Guide** | 3-agent author discovery + voice synthesis | Anthropic, Perplexity | 1 checkpoint |
| 2 | **Gap Analysis** | 8-step competitive gap discovery + embedding | OpenAI, Anthropic, Google, Perplexity | No |
| 3 | **Content Engine v1.3** | 6-stage content generation + evaluation | Anthropic, Perplexity (via LiteLLM) | 2 checkpoints |
| 4 | **Topic Discovery** | Multi-source topic generation + CPS ranking | Anthropic, Perplexity (via LiteLLM) | 2 checkpoints |
| 5 | **Onboarding** | Company/product/persona setup orchestrator | Delegates to P1a/1b/1c | Inherited |
| - | **Daily Tracker** | AI platform monitoring + mention detection | Claude (fanout gen) | No |
| - | **Reddit HIL** | Subreddit monitoring + reply drafting | Gemini | Slack/Discord |
| - | **CPS Model** | Citation Signal Predictor (neural ranking) | None (neural net) | No |

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Language | Python 3.12, asyncio |
| Framework | FastAPI + Uvicorn |
| Data Validation | Pydantic v2 (strict models) |
| Database | PostgreSQL + SQLAlchemy 2.0 (async) |
| Vector Storage | pgvector (1536-dim, HNSW indexes) |
| Cache/Coordination | Redis (Streams, Sorted Sets, Hashes, Lists) |
| Object Storage | Cloudflare R2 (S3-compatible) via `StorageBackend` ABC |
| State Machines | LangGraph (HITL interrupt model) |
| LLM Abstraction | LiteLLM (content engine + topic discovery) |
| LLM Routing | OpenRouter (unified API gateway) |
| Tracing | LangSmith (sole backend) |
| Logging | structlog (correlation IDs, JSON/console) |
| Content Extraction | trafilatura + BeautifulSoup |
| Analysis | scipy, numpy, scikit-learn, Plotly |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | Next.js 14 (App Router), React 18 |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS + CSS custom properties |
| State | Zustand (5 stores) |
| Auth | BFF proxy (httpOnly cookies, CSP nonces) |
| Charts | Recharts, D3, Plotly |
| Editor | BlockNote (rich text) |
| Drag & Drop | @dnd-kit |
| Icons | lucide-react |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Database | PostgreSQL (required) |
| Cache | Redis (required) |
| Object Storage | Cloudflare R2 (production) / Local filesystem (dev) |
| Deployment | Docker, Railway |
| CI | GitHub Actions |

## Key Architectural Patterns

### 1. Protocol-Based Service Layer
```
AuthServiceProtocol ──► DbAuthService (production, PostgreSQL)
GapDataServiceProtocol ──► DbGapDataService / JsonGapDataService
ContentDataServiceProtocol ──► DbContentDataService / JsonContentDataService
```
Services implement runtime-checkable Protocols. DI switch in `api/dependencies.py` selects implementation based on `DATABASE_URL` presence. Filesystem-first, DB-additive — JSON artifacts always written first.

### 2. BFF Proxy Pattern (Frontend)
```
Browser ──[httpOnly cookie]──► Next.js BFF ──[Bearer token]──► FastAPI Backend
```
No backend URL or auth token ever exposed to browser. CSP nonces for script injection protection.

### 3. Pipeline Execution
```
API Router ──► asyncio.create_task() ──► Pipeline Runner
                                            │
                                    ┌───────▼───────┐
                                    │  DbTaskStore   │
                                    │  (Redis locks) │
                                    │  (Semaphore)   │
                                    └───────┬───────┘
                                            │
                                    ┌───────▼───────┐
                                    │ RedisEventBus  │
                                    │ (SSE Streams)  │
                                    └───────────────┘
```
Background pipelines managed by `DbTaskStore` with Redis distributed locks (prevent duplicate runs per slug), Redis distributed semaphore (max 3 concurrent), and `RedisEventBus` for SSE streaming to frontend.

### 4. Dual-Write State
Pipeline state written to both Redis Hash and filesystem simultaneously. Redis for hot reads (sub-ms), filesystem for durability and fallback.

### 5. HITL Interrupt Model
LangGraph `interrupt()` pauses graph execution. State persisted to Redis via `RedisSaver`. Frontend polls for `pending_approval` status, submits approval via API, `BRPOP` unblocks the waiting pipeline.

### 6. Company-Wide SSE
`CompanyEventBus` (in-memory pub/sub) broadcasts state changes to all subscribers for a company slug. Frontend `useCompanyStream` hook debounces and triggers re-polls.

## Data Flow Overview

```
Company Onboarding (P5)
    │
    ├──► Knowledge Base (P1a) ──► company_context/{slug}.md
    ├──► Audience Persona (P1b) ──► audience_personas/{slug}/
    └──► Voice Style Guide (P1c) ──► style_guides/{slug}.md
              │
              ▼
Site Audit (P0) ──► site_audit/{slug}/
              │
              ▼
Gap Analysis (P2) ──► gap_analysis/{slug}/
    │                      │
    │                      ▼
    │              Topic Discovery (P4) ──► topic_discovery/{slug}/
    │                      │
    │                      ▼
    └──────────► Content Engine (P3) ──► content/{slug}/
                           │
                           ▼
                  Daily Tracker ──► daily_tracker/{slug}/
                           │
                           ▼
                  CMS Publish ──► WordPress/Webflow
```

## Directory Layout

```
content-strategy-engine/
├── core/               ← ALL business logic (23 modules)
│   ├── config/         ← Pydantic Settings (113 params)
│   ├── models/         ← Pydantic models (16 files, 100+ models)
│   ├── db/             ← SQLAlchemy ORM (25 tables, 30 repos, 37 migrations)
│   ├── auth/           ← Auth service protocol + DB implementation
│   ├── events/         ← CompanyEventBus (in-memory pub/sub)
│   ├── storage/        ← StorageBackend ABC (Local, R2, Cached)
│   ├── services/       ← 33 service files (Protocol → Json → Db pattern)
│   ├── shared_tools/   ← Embedding clients, cost tracker, tracing, logging
│   ├── site_audit/     ← Pipeline 0 (deterministic, 6 steps)
│   ├── research/       ← Pipelines 1a/1b/1c (KB, AP, VSG)
│   ├── gap_analysis/   ← Pipeline 2 (8 steps, 4 search engines)
│   ├── content_engine/ ← Pipeline 3 v1.3 (6 stages, LiteLLM)
│   ├── topic_discovery/← Pipeline 4 (multi-source, CPS scoring)
│   ├── onboarding/     ← Pipeline 5 (orchestrator)
│   ├── orchestration/  ← Cross-pipeline orchestrators
│   ├── cps_model/      ← Citation Signal Predictor (neural net)
│   ├── daily_tracker/  ← Platform monitoring + metrics
│   ├── reddit_hil/     ← Reddit monitoring + LangGraph
│   ├── cms/            ← CMS adapter pattern (WordPress)
│   ├── analytics/      ← GA4 integration
│   ├── content_inventory/ ← Content registry + cannibalization
│   ├── audit/          ← Structured logging, correlation IDs
│   ├── redis.py        ← Async + sync Redis client singletons
│   ├── redis_semaphore.py ← Distributed pipeline concurrency
│   ├── cache.py        ← Redis cache utilities
│   └── checkpointer.py ← LangGraph RedisSaver factory
├── api/                ← FastAPI REST API
│   ├── app.py          ← App factory, middleware, lifespan
│   ├── auth/           ← ASGI middleware, RBAC dependencies
│   ├── routers/        ← 31 route handlers
│   ├── schemas/        ← 21 request/response model files
│   ├── services/       ← API-level data services
│   └── tasks/          ← DbTaskStore, RedisEventBus, runner
├── frontend/           ← Next.js 14 dashboard
│   ├── src/app/        ← 12 dashboard pages + auth + onboarding
│   ├── src/components/ ← 27 shared UI components
│   ├── src/stores/     ← 5 Zustand stores
│   └── src/lib/        ← API client, auth, BFF proxy
├── tests/              ← ~2100+ tests
├── scripts/            ← CLI entry points
├── artifacts/          ← Persisted pipeline outputs
└── docs/               ← System documentation
```

## Security Model

1. **Default-deny ASGI middleware** — all routes require auth unless explicitly public
2. **RBAC** — superuser, member, viewer roles enforced via FastAPI dependencies
3. **Tenant isolation** — company_slug scoping on all data access
4. **BFF proxy** — no tokens in browser, httpOnly cookies only
5. **CSP nonces** — per-request Content Security Policy
6. **Fernet encryption** — CMS credentials encrypted at rest
7. **HMAC-SHA256** — OAuth state tokens for GA4
8. **Distributed locks** — prevent concurrent pipeline runs on same slug
9. **Stream tokens** — 5-minute TTL, SSE-only scope

## Configuration

All configuration via environment variables, loaded by Pydantic Settings with multi-file `.env` support. Key required variables:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection (required, app fails fast without it) |
| `REDIS_URL` | Redis connection (required for EventBus, locks, semaphore, cache) |
| `OPENROUTER_API_KEY` | Unified LLM routing via OpenRouter |
| `ANTHROPIC_API_KEY` | Direct Anthropic API calls (KB brand perception) |
| `OPENAI_API_KEY` | OpenAI embeddings (text-embedding-3-small) |
| `LANGSMITH_API_KEY` | LangSmith tracing (optional but recommended) |
| `JWT_SECRET_KEY` | Token signing (auto-generated in dev) |

See [01-CORE-CONFIG.md](01-CORE-CONFIG.md) for the complete 113-field settings reference.
