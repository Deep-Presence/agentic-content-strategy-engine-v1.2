# Content Strategy Engine — Comprehensive System Documentation

> **Project:** Deep Presence Content Strategy Engine (formerly AEO-Optimizer)
> **Owner:** Aryan (CTO & Co-founder, Deep Presence)
> **Stack:** Python 3.12 · LangGraph · DeepAgents · FastAPI · Pydantic v2 · Langfuse v3
> **Document Date:** 2026-02-19
> **Document Scope:** Exhaustive technical documentation covering architecture, implementation, decisions, vulnerabilities, and roadmap.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What This System Does — The Business Problem](#2-what-this-system-does--the-business-problem)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Directory Structure — Complete File Map](#4-directory-structure--complete-file-map)
5. [Pipeline 1: Research Artifacts](#5-pipeline-1-research-artifacts)
   - 5.1 [Company Context Research Agent](#51-company-context-research-agent)
   - 5.2 [Audience Persona Research Agent](#52-audience-persona-research-agent)
   - 5.3 [Writing Style Guide Research Agent](#53-writing-style-guide-research-agent)
   - 5.4 [LangGraph State Machines — The Approval Flow](#54-langgraph-state-machines--the-approval-flow)
   - 5.5 [Combined Pipeline Orchestrator](#55-combined-pipeline-orchestrator)
   - 5.6 [Cross-Stage Context Passing](#56-cross-stage-context-passing)
   - 5.7 [Perplexity Deep Research Integration](#57-perplexity-deep-research-integration)
6. [Pipeline 2: Gap Analysis](#6-pipeline-2-gap-analysis)
   - 6.1 [Step 1 — Embed Company Assets](#61-step-1--embed-company-assets)
   - 6.2 [Step 2 — Generate Queries](#62-step-2--generate-queries)
   - 6.3 [Step 3 — Search Platforms](#63-step-3--search-platforms)
   - 6.4 [Step 4 — Enrich Citations](#64-step-4--enrich-citations)
   - 6.5 [Step 5 — Embed Content](#65-step-5--embed-content)
   - 6.6 [Step 6 — Semantic & Structural Analysis (SPA)](#66-step-6--semantic--structural-analysis-spa)
   - 6.7 [Step 7 — Visualize](#67-step-7--visualize)
   - 6.8 [Step 8 — Generate Report](#68-step-8--generate-report)
   - 6.9 [LLM Engine Abstraction](#69-llm-engine-abstraction)
   - 6.10 [Data Flow Between Steps](#610-data-flow-between-steps)
7. [Pipeline 3: Content Generation Engine](#7-pipeline-3-content-generation-engine)
   - 7.1 [Stage 1 — Strategic Planner](#71-stage-1--strategic-planner)
   - 7.2 [Stage 2 — Content Workers (Orchestrator-Workers)](#72-stage-2--content-workers-orchestrator-workers)
   - 7.3 [Stage 3 — Evaluator-Optimizer Loop](#73-stage-3--evaluator-optimizer-loop)
   - 7.4 [Stage 4 — Human Review (LangGraph HITL)](#74-stage-4--human-review-langgraph-hitl)
   - 7.5 [Langfuse Tracing Architecture](#75-langfuse-tracing-architecture)
   - 7.6 [Artifact Structure](#76-artifact-structure)
   - 7.7 [Utility Modules](#77-utility-modules)
8. [Reddit Human-in-the-Loop Monitor](#8-reddit-human-in-the-loop-monitor)
9. [Storage Architecture](#9-storage-architecture)
   - 9.1 [Filesystem Layer (Source of Truth)](#91-filesystem-layer-source-of-truth)
   - 9.2 [DeepAgents Backend Routing (CompositeBackend)](#92-deepagents-backend-routing-compositebackend)
   - 9.3 [ChromaDB Vector Store](#93-chromadb-vector-store)
   - 9.4 [Supabase Mirror (Optional DB Layer)](#94-supabase-mirror-optional-db-layer)
   - 9.5 [Storage Backend Abstraction (Interface)](#95-storage-backend-abstraction-interface)
10. [Data Models — Complete Pydantic v2 Schema Reference](#10-data-models--complete-pydantic-v2-schema-reference)
11. [Configuration & Environment Variables](#11-configuration--environment-variables)
12. [CLI Entry Points — Scripts Reference](#12-cli-entry-points--scripts-reference)
13. [Database Schema — Supabase Migrations](#13-database-schema--supabase-migrations)
14. [Existing Artifacts — Current State of Outputs](#14-existing-artifacts--current-state-of-outputs)
15. [Testing — Current State & Gaps](#15-testing--current-state--gaps)
16. [Dependency Graph](#16-dependency-graph)
17. [Architectural Decisions & Rationale](#17-architectural-decisions--rationale)
18. [Known Vulnerabilities, Flaws & Technical Debt](#18-known-vulnerabilities-flaws--technical-debt)
19. [Security Considerations](#19-security-considerations)
20. [Scope & Roadmap](#20-scope--roadmap)
21. [REST API Layer (FastAPI)](#21-rest-api-layer-fastapi)
    - 21.1 [Application Factory & Lifecycle](#211-application-factory--lifecycle)
    - 21.2 [API Endpoints Reference](#212-api-endpoints-reference)
    - 21.3 [TaskStore — JSON-Backed Persistence](#213-taskstore--json-backed-persistence)
    - 21.4 [EventBus — SSE Streaming](#214-eventbus--sse-streaming)
    - 21.5 [HITL Approval Flow via API](#215-hitl-approval-flow-via-api)
    - 21.6 [Design Choices & Rationale](#216-design-choices--rationale)
22. [Appendix A: Model & API Key Matrix](#appendix-a-model--api-key-matrix)
23. [Appendix B: Artifact Naming Conventions](#appendix-b-artifact-naming-conventions)
24. [Appendix C: Code Standards & Conventions](#appendix-c-code-standards--conventions)

---

## 1. Executive Summary

The **Content Strategy Engine** is a multi-agent AI platform that automates the end-to-end workflow of content strategy for B2B companies. It operates across three sequential pipelines:

1. **Research Artifacts Pipeline** (implemented) — Uses LLM agents with web research tools to produce company context documents, audience persona profiles, and writing style guides. Each artifact goes through a human-in-the-loop approval flow (approve / revise / reject) before being finalized.

2. **Gap Analysis Pipeline** (implemented) — An 8-step data pipeline that embeds a company's web content, generates buyer-intent search queries, searches four AI platforms (ChatGPT, Claude, Perplexity, Google AI Overview), enriches the citations those platforms return, embeds everything into a shared vector space, computes semantic proximity analysis (SPA), generates interactive visualizations, and produces a gap report with actionable content recommendations.

3. **Content Generation Engine** (implemented) — A 4-stage async pipeline that consumes the outputs of Pipelines 1 and 2 to automatically generate optimized content pieces that close the identified citation gaps. Uses Orchestrator-Workers pattern for parallel content production and Evaluator-Optimizer pattern for automated QA, with LangGraph HITL for human review.

Additionally, a **Reddit Human-in-the-Loop Monitor** (implemented) monitors subreddits for threads matching a company's ICP persona, drafts contextual replies, and sends notifications via Slack/Discord.

The system exposes both a **CLI** and a **FastAPI REST API** (implemented 2026-02-16). All business logic lives in a `core/` Python package. The API layer (`api/`) wraps all three pipelines with async task runners, SSE event streaming for real-time progress, and HITL approval endpoints. Task state is persisted via a JSON-backed TaskStore. Artifacts are persisted to the local filesystem as the source of truth, with optional versioned mirroring to Supabase. LLM observability is provided by Langfuse v3 tracing throughout the content generation pipeline.

**Current production clients analyzed:** Ramp (corporate spend management) and Carta (equity management platform).

---

## 2. What This System Does — The Business Problem

### The Problem: AI Search Engine Optimization (AEO)

Traditional SEO optimizes for Google's link-based ranking. But the rise of AI-powered search (ChatGPT, Claude, Perplexity, Google AI Overview) introduces a new challenge: **AI Engine Optimization (AEO)**. When a user asks an AI assistant "What's the best spend management tool?", the AI synthesizes an answer by citing various sources. If your company's content isn't structured in a way that AI models can understand and cite, you become invisible in AI-assisted discovery.

### The Solution: Deep Presence Content Strategy Engine

This system answers three questions:
1. **"Who are we, who are our customers, and how should we write?"** → Research Artifacts Pipeline
2. **"Where are we being cited vs. where are we invisible in AI search?"** → Gap Analysis Pipeline
3. **"What content should we create to fill those gaps?"** → Content Generation Engine (implemented)

### The Value Chain

```
Company Website + Internal Docs
        ↓
    Research Artifacts
    (Company Context → Persona Profiles → Writing Style Guide)
        ↓
    Gap Analysis
    (Embed company content → Generate buyer queries → Search AI platforms
     → Analyze citation patterns → Identify semantic gaps → Recommend content)
        ↓
    Content Generation Engine
    (4-stage: Planner → Workers → Evaluator → HITL Review)
        ↓
    Publication + Monitoring
    (Publish → Monitor Reddit for opportunities → Repeat)
```

---

## 3. High-Level Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        CONTENT STRATEGY ENGINE                           │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI REST API (api/)                                           │  │
│  │  • POST /api/v1/{pipeline}/start   • GET /tasks/{id}/events (SSE) │  │
│  │  • POST /{pipeline}/{id}/approve   • GET /api/v1/artifacts/...    │  │
│  │  • TaskStore (JSON-backed)         • EventBus (pub/sub SSE)       │  │
│  └────────────────────┬───────────────────────────────────────────────┘  │
│                       │ asyncio.create_task()                            │
│                       ▼                                                  │
│  ┌──────────────────┐   ┌───────────────────┐   ┌─────────────────────┐  │
│  │   Pipeline 1:    │   │   Pipeline 2:     │   │   Pipeline 3:       │  │
│  │   Research       │──▶│   Gap Analysis    │──▶│   Content Generation│  │
│  │   Artifacts      │   │   (8-step)        │   │   (4-stage)         │  │
│  └────────┬─────────┘   └────────┬──────────┘   └──────────┬──────────┘  │
│           │                      │                          │            │
│           ▼                      ▼                          ▼            │
│  ┌─────────────────────────────────────────┐  ┌───────────────────────┐  │
│  │           Artifact Storage               │  │  Langfuse v3         │  │
│  │  Filesystem (SoT) ◀──▶ Supabase Mirror  │  │  (LLM Observability) │  │
│  │  ChromaDB (vectors)                      │  └───────────────────────┘  │
│  └─────────────────────────────────────────┘                             │
│                                                                          │
│  ┌─────────────────┐                                                     │
│  │  Reddit HIL     │  (Independent monitoring system)                    │
│  │  Monitor        │                                                     │
│  └─────────────────┘                                                     │
│                                                                          │
│  External Services:                                                      │
│  • Perplexity (sonar-deep-research)  • Google Gemini (3-flash-preview)   │
│  • OpenAI (text-embedding-3-small)   • Anthropic Claude (sonnet-4.5)     │
│  • Reddit (PRAW read-only)           • Slack / Discord (webhooks)        │
│  • Supabase (PostgREST + Storage)    • ChromaDB (local vector DB)        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.12+ | All business logic |
| **API Framework** | FastAPI + Uvicorn | REST API with async task runners, SSE, HITL endpoints |
| **Agent Framework** | DeepAgents | LLM agent creation with tool-use, backends, memory |
| **Orchestration** | LangGraph v0.2+ | State machine graphs with interrupt-based human-in-the-loop |
| **Data Validation** | Pydantic v2 | Input/output schemas, settings management |
| **Web Research** | Perplexity SDK (sonar-deep-research) | Deep web research with citations |
| **LLM Providers** | Google Gemini, Anthropic Claude, OpenAI GPT | Agent reasoning, query gen, reports |
| **Embeddings** | OpenAI text-embedding-3-small (1536-dim) | Semantic similarity in gap analysis |
| **Vector Store** | ChromaDB (local, persistent) | Embedding storage and retrieval |
| **Database** | Supabase (PostgreSQL 17 + pgvector) | Optional artifact mirroring, versioning |
| **Visualization** | Plotly | Interactive HTML charts (UMAP, t-SNE, heatmaps) |
| **Dimensionality Reduction** | UMAP, t-SNE (scikit-learn) | Embedding space visualization |
| **Web Crawling** | Playwright, httpx, BeautifulSoup4 | Site crawling and HTML extraction |
| **Reddit** | PRAW (read-only) | Subreddit monitoring |
| **Notifications** | Slack Block Kit, Discord Webhooks | Alert delivery |
| **Observability** | Langfuse v3.14+ | LLM tracing, scoring, cost tracking |

---

## 4. Directory Structure — Complete File Map

```
content-strategy-engine/
├── CLAUDE.md                              # Project memory for Claude Code (development instructions)
├── README.md                              # User-facing documentation + quick start
├── pyproject.toml                         # Project metadata + dependency declaration
├── requirements.txt                       # Flat dependency list (for pip install)
├── .env.local                             # API keys + secrets (gitignored)
│
├── core/                                  # *** ALL BUSINESS LOGIC ***
│   ├── __init__.py
│   │
│   ├── config/                            # Centralized configuration
│   │   ├── __init__.py
│   │   └── settings.py                    # Pydantic BaseSettings (125 lines)
│   │                                      #   - Loads from .env / .env.local / .env.test.local
│   │                                      #   - Parent dir fallback discovery
│   │                                      #   - Singleton: `settings = Settings()`
│   │
│   ├── models/                            # Pydantic v2 data schemas (shared across pipelines)
│   │   ├── __init__.py                    # Exports: DraftNotification, RedditMonitorInput, RedditThread
│   │   ├── artifacts.py                   # SourceDoc, FactRow, CompanyResearchInput, CompanyContextArtifact
│   │   ├── personas.py                    # PersonaResearchInput, PersonaArtifact (with to_markdown())
│   │   ├── style_guide.py                # StyleGuideResearchInput, WritingStyleGuideArtifact
│   │   ├── gap_analysis.py               # 20+ models: GapAnalysisInput, SemanticUnit, QueryCluster,
│   │   │                                  #   GeneratedQuery, CitationRef, PlatformResult, StructuralSignals,
│   │   │                                  #   EnrichedCitation, SpaResult, CentroidResult, QueryGap,
│   │   │                                  #   ClusterContentSpec, AnalysisResult, GapReport,
│   │   │                                  #   DiscoveredPage, SiteTreeNode, SiteDiscoveryResult
│   │   └── reddit_hil.py                 # RedditMonitorInput, RedditThread, DraftNotification
│   │
│   ├── research/                          # Pipeline 1: Research Artifacts
│   │   ├── __init__.py
│   │   ├── agents/                        # DeepAgent definitions
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # get_store(), backend_factory(), _dbg(), artifact dir creation
│   │   │   ├── company_research_agent.py  # Gemini + Perplexity, internet_search + read_local_text tools
│   │   │   ├── persona_agent.py           # Gemini + Perplexity, 1-3 persona creation, ThreadPoolExecutor
│   │   │   └── style_guide_agent.py       # Gemini + Perplexity, style guide creation, ThreadPoolExecutor
│   │   ├── graphs/                        # LangGraph state machines
│   │   │   ├── __init__.py
│   │   │   ├── company_research.py        # Standalone company graph (agent→draft→approve→mirror)
│   │   │   ├── persona_research.py        # Standalone persona graph (same pattern)
│   │   │   ├── style_guide.py             # Standalone style guide graph (same pattern)
│   │   │   └── pipeline.py                # Combined 3-stage orchestrator (company→persona→style)
│   │   └── tools/                         # Research-specific tools
│   │       ├── __init__.py
│   │       └── perplexity_client.py       # sonar-deep-research wrapper with citation formatting
│   │
│   ├── gap_analysis/                      # Pipeline 2: Gap Analysis (8-step)
│   │   ├── __init__.py
│   │   ├── pipeline.py                    # Main orchestrator: run_gap_analysis()
│   │   ├── engines/                       # LLM search engine backends
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # SearchEngine ABC (async search interface)
│   │   │   ├── claude.py                  # Claude web-search-2025-03-05 beta
│   │   │   ├── gemini.py                  # Gemini with google_search grounding
│   │   │   ├── openai_engine.py           # OpenAI o1/o3 with web_search tool
│   │   │   └── perplexity.py              # Perplexity sonar SDK
│   │   └── steps/                         # Individual pipeline steps
│   │       ├── __init__.py
│   │       ├── s1_embed_assets.py         # Crawl + chunk + embed company website
│   │       ├── s2_generate_queries.py     # 3-pass query generation (seed→dedup→coverage)
│   │       ├── s3_search_platforms.py     # Concurrent search across 4 engines
│   │       ├── s4_enrich_citations.py     # Fetch + extract + classify citation content
│   │       ├── s5_embed_content.py        # Embed queries + citations, top-k selection
│   │       ├── s6_analyze.py              # SPA, centroids, gaps, cluster specs
│   │       ├── s7_visualize.py            # Plotly HTML visualizations
│   │       └── s8_generate_report.py      # LLM-generated gap report + generation specs
│   │
│   ├── content_engine/                    # Pipeline 3: Content Generation Engine
│   │   ├── __init__.py
│   │   ├── pipeline.py                    # Top-level async orchestrator (4-stage)
│   │   ├── planner.py                     # Stage 1: Strategic Planner (Sonnet 4.5)
│   │   ├── tracing.py                     # Langfuse instrumentation (lazy singleton)
│   │   ├── utils.py                       # safe_parse, retry, token estimation
│   │   ├── graph.py                       # Stage 4: LangGraph HITL review
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── dispatcher.py              # Semaphore-controlled parallel dispatch
│   │   │   ├── outliner.py                # Step 1: Outline generation (Sonnet)
│   │   │   ├── drafter.py                 # Step 2: Content drafting (Sonnet)
│   │   │   ├── fact_enricher.py           # Step 3: Perplexity fact verification
│   │   │   └── formatter.py              # Step 4: Style formatting (Haiku)
│   │   ├── evaluator/
│   │   │   ├── __init__.py
│   │   │   ├── loop.py                    # Eval-optimize orchestrator (max 2 cycles)
│   │   │   ├── structural.py              # 8 deterministic structural checks
│   │   │   ├── semantic.py                # Embedding proximity evaluation
│   │   │   ├── style_judge.py             # LLM-as-judge style evaluation (Haiku)
│   │   │   └── factual_judge.py           # LLM-as-judge factual grounding (Sonnet)
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── planner_prompts.py
│   │       ├── outliner_prompts.py
│   │       ├── drafter_prompts.py
│   │       ├── enricher_prompts.py
│   │       ├── formatter_prompts.py
│   │       ├── style_judge_prompts.py
│   │       └── factual_judge_prompts.py
│   │
│   ├── reddit_hil/                        # Reddit Human-in-the-Loop Monitor
│   │   ├── __init__.py                    # Exports: fetch_new_threads
│   │   ├── graph.py                       # LangGraph: load→fetch→dedupe→rank→draft→notify (464 lines)
│   │   ├── reddit_client.py               # PRAW read-only wrapper (126 lines)
│   │   ├── webhooks.py                    # Slack Block Kit + Discord chunked notifications (125 lines)
│   │   └── cli.py                         # CLI entry point with argparse (96 lines)
│   │
│   ├── storage/                           # Persistence layer
│   │   ├── __init__.py
│   │   ├── backends/
│   │   │   ├── __init__.py
│   │   │   └── base.py                    # Abstract StorageBackend interface (read/write/exists/delete/list_dir)
│   │   ├── supabase_client.py             # Singleton Supabase client factory (lru_cache)
│   │   └── supabase_mirror.py             # Versioned mirroring: mirror_*_if_configured() functions (339 lines)
│   │
│   └── shared_tools/                      # Cross-pipeline utilities
│       ├── __init__.py
│       ├── embedding_client.py            # embed_texts() — OpenAI text-embedding-3-small wrapper (42 lines)
│       ├── async_embedding_client.py      # async_embed_texts() — Async variant with batching
│       ├── async_chroma_client.py         # Async ChromaDB wrappers (asyncio.to_thread)
│       └── chroma_client.py               # ChromaDB persistent client with company/citation collections (184 lines)
│
├── api/                                   # *** FastAPI REST API LAYER ***
│   ├── __init__.py
│   ├── app.py                             # App factory (lifespan, middleware, routers)
│   ├── config.py                          # ApiSettings (CORS, port, max concurrency)
│   ├── dependencies.py                    # Dependency injection (get_task_store, get_event_bus)
│   ├── exceptions.py                      # Global exception handlers (TaskNotFound, TaskConflict, PipelineError)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py                      # GET /health, /readiness
│   │   ├── gap_analysis.py                # POST /start, GET /{run_id}/status
│   │   ├── research.py                    # POST /start, GET /status, POST /approve
│   │   ├── content.py                     # POST /start, GET /status, POST /approve
│   │   ├── events.py                      # GET /tasks/{task_id}/events (SSE streaming)
│   │   ├── artifacts.py                   # GET /artifacts/companies, /{type}/{slug}
│   │   └── tasks.py                       # GET /tasks, /{task_id}, POST /{task_id}/cancel
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── common.py                      # Pydantic request/response models
│   └── tasks/
│       ├── __init__.py
│       ├── models.py                      # PipelineTask, TaskStatus, ApprovalRecord
│       ├── store.py                       # TaskStore (JSON-backed + in-memory + slug locks)
│       ├── event_bus.py                   # EventBus (pub/sub for SSE, event history)
│       └── runner.py                      # Background task wrappers for all 3 pipelines
│
├── scripts/                               # CLI entry points (all use argparse)
│   ├── run_company_research.py            # Standalone company research (74 lines)
│   ├── run_persona_research.py            # Standalone persona research (80 lines)
│   ├── run_style_guide_research.py        # Standalone style guide research (83 lines)
│   ├── run_pipeline.py                    # Combined 3-stage research pipeline (132 lines)
│   ├── run_gap_analysis.py                # Full 8-step gap analysis (74 lines)
│   ├── run_gap_step.py                    # Individual gap step runner for debugging (340 lines)
│   ├── resolve_vertexai_redirects.py      # Utility: resolve Vertex AI redirect URLs (140 lines)
│   ├── strip_embeddings_from_json.py      # Utility: remove embedding vectors from JSON (67 lines)
│   └── run_server.py                     # FastAPI server entry point (uvicorn)
│
├── artifacts/                             # Persisted agent outputs (SOURCE OF TRUTH)
│   ├── company_context/                   # {slug}.md, {slug}.draft.md
│   │   ├── ramp.md                        # ✅ Final (approved)
│   │   ├── ramp.draft.md                  # Draft version
│   │   ├── carta.md                       # ✅ Final (approved)
│   │   ├── carta.draft.md                 # Draft version
│   │   ├── mynd.md                        # ✅ Final (approved)
│   │   ├── ramp-business-corporation.md   # Alternative Ramp analysis
│   │   └── ramp-business-corporation.draft.md
│   ├── personas/
│   │   ├── ramp__persona-icp.md           # ✅ Final — "Controller Catherine"
│   │   ├── ramp__persona-icp.draft.md
│   │   ├── carta__persona-icp.md          # ✅ Final
│   │   └── carta__persona-icp.draft.md
│   ├── style_guides/
│   │   ├── ramp.draft.md                  # ⏳ Awaiting approval
│   │   └── carta.draft.md                 # ⏳ Awaiting approval
│   ├── gap_analysis/
│   │   ├── ramp/                          # Complete gap analysis
│   │   │   ├── analysis.json
│   │   │   ├── gap_report.md / .json
│   │   │   ├── generation_spec.md / .json
│   │   │   ├── queries.json               # 144 queries across 9 clusters
│   │   │   ├── enriched_citations.json    # 2,234 citations
│   │   │   ├── embeddings/                # Vectorized queries + citations
│   │   │   ├── platform_results/          # claude_, gemini_, openai_, perplexity_ .jsonl
│   │   │   ├── visualizations/            # Interactive Plotly HTML charts
│   │   │   └── site_discovery/            # Crawled pages + site tree
│   │   └── carta/                         # Same structure
│   ├── chroma_db/                         # ChromaDB persistent vector store
│   └── _logs/
│       ├── debug.log                      # Agent debug logging
│       └── reddit_monitor/                # Reddit seen-thread cache
│           ├── ramp__seen.json
│           └── carta__seen.json
│
├── supabase/
│   ├── config.toml                        # Supabase local dev config
│   └── migrations/
│       ├── 20250206120000_initial_schema.sql           # Core tables + pgvector
│       ├── 20251209105957_remote_schema.sql            # Placeholder
│       ├── 20251227120000_artifact_versions.sql        # Versioning table + RLS
│       └── 20260207120000_rls_enums_hnsw.sql           # HNSW indexes + 13 enums + 20 RLS policies
│
├── tests/                                 # Test suite (276 tests)
│   ├── conftest.py                        # Shared fixtures (FakeChromaCollection, mock clients)
│   ├── shared_tools/                      # Async embedding + ChromaDB client tests
│   ├── gap_analysis/                      # Pipeline + step tests (s1, s2, s4, s5, s8)
│   ├── content_engine/                    # 57 tests — full coverage
│   ├── api/                               # 126 tests — FastAPI integration tests
│   │   ├── conftest.py                    # TestClient, mock stores, fixtures
│   │   ├── test_health.py
│   │   ├── test_gap_analysis.py
│   │   ├── test_research.py
│   │   ├── test_content.py
│   │   ├── test_events.py
│   │   ├── test_artifacts.py
│   │   ├── test_tasks.py
│   │   ├── test_store.py
│   │   ├── test_event_bus.py
│   │   ├── test_runner.py
│   │   └── ...
│   └── research/                          # Empty
│
├── docs/
│   ├── PROJECT_STATE.md                   # Architecture overview + current state (updated 2026-02-12)
│   └── COMPREHENSIVE_SYSTEM_DOCUMENTATION.md  # THIS FILE
│
└── flow-diagrams/                         # Visual architecture diagrams
    ├── CONTENT-ENGINE-FLOW.excalidraw     # Interactive Excalidraw diagram
    ├── FLOW-CHART.svg / .png              # Architecture flow
    ├── FLOW-DARK.svg / FLOW-DARK-NO-BG.svg
    ├── FLOW-NO-BG.svg / .png
    ├── FLOW-2.svg
    └── gap-analysis-flow.png
```

---

## 5. Pipeline 1: Research Artifacts

### Overview

The Research Artifacts Pipeline produces three foundational documents that feed into all downstream systems. Each stage uses a DeepAgent (LLM with tools) orchestrated by a LangGraph state machine with human-in-the-loop approval.

```
Stage 1: Company Context    Stage 2: Persona Research    Stage 3: Style Guide
    ↓                             ↓                           ↓
  {slug}.md               {slug}__persona-*.md           {slug}_style.md

Dependencies:
  Stage 1: No prior context
  Stage 2: Receives Stage 1 output (company context)
  Stage 3: Receives Stage 1 + Stage 2 outputs (company context + personas)
```

### 5.1 Company Context Research Agent

**File:** `core/research/agents/company_research_agent.py`

**Purpose:** Research everything publicly knowable about a company — its origin story, products, market positioning, competitive landscape, target audience, brand perception, and strategic direction.

**LLM Configuration:**
- **Model:** Google Gemini (`gemini-3-flash-preview` by default)
- **API Key:** `GOOGLE_API_KEY_COMPANY_DEEPAGENT`
- **Timeout:** 900 seconds (15 minutes, configurable via `AEO_AGENT_INVOKE_TIMEOUT_S`)

**Available Tools:**
1. `internet_search(query, max_results=6, include_raw_content=True)` — Calls Perplexity's sonar-deep-research model to perform comprehensive web research. Returns research text with inline `[source_id]` citations and a formatted Sources section.
2. `read_local_text(path, max_chars=8000)` — Reads internal documents (transcripts, pitch decks, notes) from the local filesystem.

**System Prompt Directives:**
The agent is instructed to:
- MUST call `internet_search` at least once before finalizing
- Produce structured Markdown with inline `[source_id]` citations
- Cover specific research areas: origin story, founders, funding, product evolution, market position, competitive landscape, target customers, brand perception, customer quotes, internal insights
- Be thorough but not speculative — clearly flag assumptions

**Agent Creation Pattern:**
```python
agent = create_deep_agent(
    model=ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key),
    tools=[internet_search, read_local_text],
    system_prompt=SYSTEM_PROMPT.strip(),    # MUST use system_prompt=, NOT system_message=
    backend=backend_factory(rt),             # CompositeBackend with routing
    store=get_store(),                       # InMemoryStore (singleton)
)
```

**Invocation (ThreadPoolExecutor Isolation):**
```python
timeout_s = settings.aeo_agent_invoke_timeout_s  # 900s default
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
    fut = ex.submit(agent.invoke, {"messages": [{"role": "user", "content": prompt}]})
    result = fut.result(timeout=timeout_s)
```

**Why ThreadPoolExecutor?** The DeepAgents `StoreBackend` has a known runtime error when `agent.invoke()` runs in the main thread alongside other async operations. Isolating in a dedicated thread prevents this.

**Output:** Full Markdown document written to `/artifacts/company_context/{slug}.draft.md`.

---

### 5.2 Audience Persona Research Agent

**File:** `core/research/agents/persona_agent.py`

**Purpose:** Create 1–3 detailed buyer personas based on the company context. Always produces an ICP (Ideal Customer Profile) persona, plus up to 2 secondary personas.

**LLM Configuration:**
- **Model:** Google Gemini (`gemini-3-flash-preview` by default)
- **API Key:** `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT`

**Available Tools:**
- `internet_search` — Perplexity deep research (same as company agent)

**Context Input:**
The agent receives the company context artifact (from Stage 1) as part of its prompt. This enables the agent to create personas grounded in the actual company's market, products, and target audience.

**Output Structure:**
The agent returns JSON:
```json
{
  "written_paths": [
    "/artifacts/personas/{slug}__persona-icp.md",
    "/artifacts/personas/{slug}__persona-2.md",
    "/artifacts/personas/{slug}__persona-3.md"
  ],
  "notes": "Created 3 personas: Controller Catherine (ICP), VP Finance (secondary), ..."
}
```

**Persona Markdown Structure (Stable Headers for Patching):**
Each persona file contains these sections (headers are stable across revisions to enable targeted section updates):

| Section | Content |
|---------|---------|
| Persona Summary | Name, role, company size, key characteristics |
| Role & Context | Industry, team structure, reporting lines, tools used |
| Day-in-the-Life Mechanics | Morning routine, recurring tasks, time sinks, workflows |
| KPIs / What Success Means | Measurable objectives, career motivations |
| Pain Points & Blockers | Frustrations, inefficiencies, tool limitations |
| Buying Triggers | Events that initiate vendor evaluation |
| Trust Builders & Objections | What builds confidence, common objections |
| Annoyances | Pet peeves in vendor interactions, content, sales |
| Messaging Angles | Compelling value propositions, one-liners |
| Quotes | Synthetic representative quotes |
| Sources | Citations from research |

---

### 5.3 Writing Style Guide Research Agent

**File:** `core/research/agents/style_guide_agent.py`

**Purpose:** Produce a comprehensive writing style guide that captures how the company should communicate across all content channels.

**LLM Configuration:**
- **Model:** Google Gemini (`gemini-3-flash-preview` by default, originally Claude Sonnet)
- **API Key:** `GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT`

**Context Input:**
Receives both company context and persona artifacts, enabling the style guide to be grounded in the company's voice AND tailored to its audience.

**Bug Fixes Applied:**
1. ~~`system_message=`~~ → `system_prompt=` (FIXED — was causing agent creation failure)
2. ~~Missing ThreadPoolExecutor~~ → Added ThreadPoolExecutor isolation (FIXED — was causing StoreBackend runtime error)

**Style Guide Markdown Sections:**

| Section | Content |
|---------|---------|
| Voice & Tone | Brand personality, emotional register, formality level |
| Channel Variations | How tone adapts for blog, email, social, docs, support |
| Show vs Tell (Good/Bad Examples) | Concrete before/after writing samples |
| Sentence & Language Choices | Sentence length, active vs passive, readability targets |
| Jargon / Terminology Rules | Industry terms to use, terms to avoid, acronym guidelines |
| Audience Resonance (from Personas) | How to speak to each persona's pain points and motivations |
| Product Positioning & Messaging Pillars | Core value props, differentiators, competitive framing |
| Do / Don't | Explicit rules (do use specific numbers; don't say "industry-leading") |
| Formatting & Structure | Header hierarchy, list usage, CTA placement, visual guidelines |
| Sample Snippets | Full writing samples in the prescribed style |
| Sources | Citations from research |

---

### 5.4 LangGraph State Machines — The Approval Flow

**Pattern:** All three research stages use an identical LangGraph pattern. The graph manages the lifecycle of an artifact from agent research through human approval to final storage.

```
                    ┌──────────────────────────┐
                    │                          │
                    ▼                          │
               ┌──────────┐                    │
               │  agent   │ ◄─── revision_note │
               │ (DeepAg) │                    │
               └────┬─────┘                    │
                    │                          │
                    ▼                          │
          ┌───────────────────┐                │
          │ write_temp_draft  │                │
          │ (save .draft.md)  │                │
          └────────┬──────────┘                │
                   │                           │
                   ▼                           │
          ┌───────────────────┐                │
          │  approval_gate    │                │
          │  interrupt()      │  ◄── auto_approve skips interrupt
          └────────┬──────────┘                │
                   │                           │
                   ▼                           │
              ┌───────────┐                    │
              │  route    │                    │
              └──┬───┬───┬┘                    │
                 │   │   │                     │
       ┌─────────│   │   │──────┐              │
       │         │   │          │              │
       ▼         │   ▼          ▼              │
   ┌────────┐    │ ┌────────┐  ┌────────┐      │
   │approve │    │ │ reject │  │ revise │──────┘
   └───┬────┘      └───┬────┘  └────────┘
       │         │     │
       ▼         │     ▼
┌──────────────┐ │   ┌──────┐
│write_and_    │ │   │ END  │
│mirror        │ │   └──────┘
│(.md + Supa)  │ │
└──────┬───────┘ │
       │         │
       ▼         │
    ┌──────┐     │
    │ END  │     │
    └──────┘     │
```

**Graph State Dictionary:**

```python
{
    "input":             CompanyResearchInput | PersonaResearchInput | StyleGuideResearchInput,
    "auto_approve":      bool,          # If True, skip human review
    "revision_note":     Optional[str],  # Feedback from human reviewer
    "artifact_md":       str,            # Generated markdown (company graph)
    "agent_result":      Dict,           # JSON result (persona/style graphs)
    "draft_path":        str,            # Path to *.draft.md
    "approval_decision": str,            # "approve" | "revise" | "reject"
    "output_path":       str,            # Final *.md path (after approval)
    "written_paths":     List[str],      # Multiple paths (persona/style)
    "mirrored":          bool | List,    # Supabase mirror result
}
```

**Node Implementations:**

| Node | Company Graph | Persona/Style Graph |
|------|---------------|---------------------|
| `agent` | Invokes agent, extracts markdown via `_extract_final_markdown()` | Calls `run_persona_agent()` / `run_style_guide_agent()`, gets JSON result |
| `write_temp_draft` | Writes markdown to `.draft.md` via backend or direct FS | Agent writes drafts directly via DeepAgents tools (no separate node) |
| `approval_gate` | Calls `interrupt()` with draft_path + artifact_md preview | Calls `interrupt()` with draft_paths from agent_result |
| `write_and_mirror` | Reads draft, writes to permanent `.md`, mirrors to Supabase | Iterates over draft_paths, promotes each to `.md`, mirrors each |

**Key Helper Functions:**

- `_extract_final_markdown(messages)` — Robust extraction of assistant message content from various formats (dict, LangChain BaseMessage, list-type content blocks). Filters out user messages to prevent prompt leakage. Falls back to last assistant message if latest is empty (tool-call messages).

- `_overwrite_virtual_path(vpath, content)` — Converts virtual `/artifacts/...` path to real filesystem path, creates parent directories, writes content.

- `_log_event(event, data)` — Structured JSON logging to console for debugging.

---

### 5.5 Combined Pipeline Orchestrator

**File:** `core/research/graphs/pipeline.py`

**Purpose:** Chains all three research stages sequentially, automatically wiring outputs from earlier stages as inputs to later stages.

**Key Functions:**

```python
def run_pipeline(
    company_input: CompanyResearchInput,
    persona_input: Optional[PersonaResearchInput] = None,
    style_input: Optional[StyleGuideResearchInput] = None,
    auto_approve: bool = False,
) -> Dict:
```

**Orchestration Logic:**

1. **Company Stage** — Runs first. If interrupted (human review needed), returns immediately with `{"stage": "company", "status": "interrupt", ...}`.

2. **Persona Stage** — Runs only if `persona_input` is provided. **Automatically injects** `company_context_path` from the company stage output so the persona agent can read the approved company context.

3. **Style Guide Stage** — Runs only if `style_input` is provided. **Automatically injects** both `company_context_path` and `persona_paths` from previous stage outputs.

4. **Completion** — Returns `{"stage": "complete", "company": {...}, "personas": {...}, "style": {...}}`.

**Cross-Stage Wiring (automatic):**
```python
# After company stage completes:
persona_input = persona_input.model_copy(
    update={"company_context_path": company_output_path}
)

# After persona stage completes:
style_input = style_input.model_copy(
    update={
        "company_context_path": company_output_path,
        "persona_paths": persona_written_paths,
    }
)
```

---

### 5.6 Cross-Stage Context Passing

The pipeline uses Pydantic's `model_copy(update={...})` to inject paths from earlier stages into later stage inputs. This enables:

1. **Company → Persona:** The persona agent reads the company context artifact to understand the business before creating personas.
2. **Company + Persona → Style Guide:** The style guide agent reads both to create a voice that fits the brand AND resonates with the target audience.

**Input Model Relationships:**

```
CompanyResearchInput
  ├── company_name, domain, seed_urls, internal_sources
  └── No prior context needed

PersonaResearchInput
  ├── company_name, domain, max_personas
  └── company_context_path: str  ◄── Injected from Stage 1 output

StyleGuideResearchInput
  ├── company_name, domain
  ├── company_context_path: str  ◄── Injected from Stage 1 output
  └── persona_paths: List[str]   ◄── Injected from Stage 2 output
```

---

### 5.7 Perplexity Deep Research Integration

**File:** `core/research/tools/perplexity_client.py`

**Purpose:** Wraps the Perplexity API's `sonar-deep-research` model to provide comprehensive web research with citation tracking.

**API:**
```python
def research(
    query: str,
    max_results: int = 8,
    search_depth: str = "advanced",
    ...
) -> str:
```

**Behavior:**
- Uses `sonar-deep-research` model (configurable via `PERPLEXITY_DEEP_RESEARCH_MODEL`)
- Returns research text with inline `[1]`, `[2]` citations
- Appends formatted `\n\nSources:\n[1] https://...\n[2] https://...` section
- Lazy client import (avoids top-level dependency failure if `perplexityai` not installed)

**Error Handling:**
- `401` / "Authorization" → Invalid/expired API key (clear error message)
- `429` / "rate limit" → Quota exceeded (suggests checking billing)
- Other exceptions → Re-raised with context

---

## 6. Pipeline 2: Gap Analysis

### Overview

The Gap Analysis Pipeline is an 8-step sequential data pipeline (not LangGraph-based) that identifies where a company's content is weak relative to what AI search engines cite. It operates in embedding space, comparing the company's web content against the sources that ChatGPT, Claude, Perplexity, and Google AI Overview cite when answering buyer-intent queries.

**Entry Point:** `run_gap_analysis(input_data: GapAnalysisInput, skip_steps: List[int] = [])` in `core/gap_analysis/pipeline.py`

**All outputs stored in:** `/artifacts/gap_analysis/{company_slug}/`

**Skip Logic:** Each step can be independently skipped via `skip_steps` parameter. Skipped steps load from cached JSON/ChromaDB instead of rerunning. This enables fast re-analysis without re-crawling or re-searching.

---

### 6.1 Step 1 — Embed Company Assets

**File:** `core/gap_analysis/steps/s1_embed_assets.py`

**Purpose:** Crawl the company's entire website, extract semantic units (meaningful text chunks), embed them using OpenAI, and store in ChromaDB.

**Process (4-phase discovery):**

1. **Phase 1: robots.txt parsing** — Fetches `/robots.txt`, extracts Sitemap directives for Phase 2.

2. **Phase 2: Sitemap parsing** — Recursively parses XML sitemaps (handles sitemap indexes pointing to sub-sitemaps). Extracts all `<url>` entries with `lastmod`, `changefreq`, `priority`.

3. **Phase 3: RSS/Atom feed discovery** — Discovers and parses RSS/Atom feeds for additional URLs.

4. **Phase 4: Enhanced BFS crawl** — Breadth-first crawl starting from seed URLs, with seed-path prioritization. Respects `max_crawl_pages` and `max_crawl_depth` limits.

**URL Processing:**
- Normalization: strips fragments, lowercases scheme/netloc
- Validation: respects robots.txt rules (configurable)
- Filtering: skips non-HTML (PDFs, images, CSS, JS, binary files)

**Semantic Unit Generation:**
- Extracts content paragraphs from HTML (p, li, h2, h3 tags via BeautifulSoup)
- Chunks paragraphs into 80–220 word segments
- Assigns stable `unit_id` (unit_1, unit_2, ...)
- Produces `SemanticUnit` objects with url, title, text, char_count, word_count

**Embedding & Storage:**
- Embeds all texts using OpenAI `text-embedding-3-small` (1536 dimensions)
- Stores raw embeddings in ChromaDB (indexed by company slug)
- Saves lightweight JSON with `embedding_id` only (no raw vectors in JSON — saves disk space)

**Outputs:**
| File | Content |
|------|---------|
| `company_embeddings.json` | List of SemanticUnit with embedding_ids (no raw vectors) |
| `site_discovery/discovered_pages.json` | All discovered URLs with metadata |
| `site_discovery/site_tree.json` | Hierarchical site structure |
| `site_discovery/discovery_summary.json` | Discovery statistics |
| ChromaDB collection: `gap_company_{slug}` | Raw embeddings for similarity queries |

**Skip Logic:** If step 1 already ran, loads embeddings from JSON and hydrates from ChromaDB if needed.

---

### 6.2 Step 2 — Generate Queries

**File:** `core/gap_analysis/steps/s2_generate_queries.py`

**Purpose:** Generate category-level search queries that a real buyer persona would type into an AI search engine.

**3-Pass Generation Process:**

**Pass 1: LLM Seed Generation**
- Loads a query taxonomy (default: `b2b_queries_180.json` with 9 clusters)
- Reads company context + persona + style guide artifacts for grounding
- Calls OpenAI (GPT-5.2 / o1) with a sophisticated prompt

**Query Clusters (Taxonomy):**

| Cluster | ID | Intent | Brand Name Policy |
|---------|----|--------|-------------------|
| Mechanism | C1 | "How does X technology work?" | NO brand names |
| Boundary | C2 | "Where does X not work?" | Permitted for known limitations only |
| Category Comparison | C3 | "X vs Y (categories, not brands)" | NO brand names |
| Decision Criteria | C4 | "What to evaluate when choosing X?" | NO brand names |
| Definition | C5 | "What is X?" | NO brand names |
| Problem/Awareness | C6 | "Why is X a problem?" | NO brand names |
| Best-of/Consideration | C7 | "Best X for Y use case" | NO brand names |
| Branded Evaluation | C8 | "Competitor-name alternatives" | REQUIRED (brand names) |
| Feature Verification | C9 | "Does X support Y?" | NO brand names |

**Pass 2: Semantic Deduplication**
- Embeds all generated query texts
- Greedy selection per cluster with cosine similarity threshold 0.85
- Removes redundant queries that are semantically too similar within the same cluster

**Pass 3: Coverage Validation**
- Ensures minimum queries per cluster (`max_queries / cluster_count`)
- Trims overrepresented clusters (max 30% of total per cluster)
- Generates fill-in queries via LLM for underrepresented clusters

**Output:** `queries.json` — List of `GeneratedQuery` objects with cluster assignment, buyer stage, and persona tag.

---

### 6.3 Step 3 — Search Platforms

**File:** `core/gap_analysis/steps/s3_search_platforms.py`

**Purpose:** Execute every generated query across four AI search platforms and collect their responses with citations.

**Execution:**
- Concurrent async execution (semaphore limit: 6 simultaneous calls)
- Each engine independently searches each query
- Citations (URLs) extracted from each engine's response format

**Engines Used:**

| Engine | Model | API | Citation Extraction Method |
|--------|-------|-----|---------------------------|
| Perplexity | sonar (configurable) | Perplexity SDK | Direct `citations` list in response |
| OpenAI | GPT-5.2 / o1 / o3 | OpenAI REST (responses API) | Parsed from `web_search_call.action.sources` |
| Gemini | gemini-2.0-flash | Google AI REST | `groundingMetadata.groundingChunks[].web.uri` |
| Claude | claude-opus (configurable) | Anthropic REST (beta) | Parsed from content blocks + tool_result |

**Output:** `platform_results/{engine}_results.jsonl` — One JSON object per line per engine.

**Error Handling:** Failed searches return a `PlatformResult` with error message in `response_text` field. Pipeline continues with available results.

---

### 6.4 Step 4 — Enrich Citations

**File:** `core/gap_analysis/steps/s4_enrich_citations.py`

**Purpose:** For each unique citation URL found in Step 3, fetch the actual HTML page, extract main content (isolating from nav/footer/sidebar), extract paragraphs, and compute ~45 structural signals across 4 categories.

**Process:**
1. **De-duplication:** One citation per unique URL (collapsed across all engines and queries)
2. **HTML Fetching:** Async HTTP GET with 20-second timeout, follows redirects
3. **Main Content Extraction** (3-tier fallback via `_extract_main_content()`):
   - **Tier 1:** `trafilatura.extract()` with `output_format='html'` — research-grade content extraction. Used if output > 200 chars.
   - **Tier 2:** Semantic HTML tags — `<article>`, `<main>`, `[role="main"]`, `.post-content`, `.entry-content`
   - **Tier 3:** Full page fallback (original behavior)
4. **Dual-Soup Architecture:** Two separate HTML processing paths:
   - `_extract_main_content()` → clean text for paragraph extraction (trafilatura strips boilerplate)
   - `_extract_structural_html()` → semantic-tag-only scoping (no trafilatura) for structure counting (preserves `<ol>`, `<dl>`, `<table>`, `<details>` that trafilatura flattens)
5. **Structural Signal Extraction (~45 fields across 4 categories):**

**Category A — Text Composition (10 fields):**

| Signal | Measurement |
|--------|-------------|
| `word_count` | Total words in extracted main content |
| `main_content_word_count` | Same (main-content-scoped) |
| `sentence_count` | Sentence count (English-only regex split) |
| `avg_paragraph_length` | Mean paragraph word count |
| `median_paragraph_length` | Median paragraph word count |
| `max_paragraph_word_count` | Longest paragraph word count |
| `avg_sentence_length` | Mean sentence word count |
| `avg_sentence_count_per_paragraph` | Sentences per paragraph |
| `reading_level` | Flesch-Kincaid grade level (via textstat, English only) |
| `self_contained_ratio` | Ratio of paragraphs that are self-contained (20-150 words, non-referential, contain facts) |

**Category B — Structural Elements (13 fields):**

| Signal | Measurement |
|--------|-------------|
| `header_count`, `h1_count`, `h2_count`, `h3_count`, `h4_count` | Per-level header counts |
| `paragraph_count` | Content paragraph count |
| `list_item_count`, `ordered_list_count`, `unordered_list_count` | List metrics |
| `list_block_count`, `bullets_per_list_block`, `min_bullets_per_list` | List block aggregates |
| `table_count`, `definition_list_count`, `blockquote_count`, `code_block_count` | Element counts |

**Category C — Content Patterns (8 fields):**

| Signal | Measurement |
|--------|-------------|
| `has_faq_section` | FAQ heading or `<details>`/`<summary>` detected |
| `has_definition_opening` | "X is a/an..." opening or `<dl>` present |
| `has_key_takeaways` | "Key Takeaways"/"Summary" heading detected |
| `has_toc` | "Table of Contents"/"Contents" heading detected |
| `has_comparison_table` | "Comparison"/"vs" heading or `<table>` present |
| `has_step_by_step` | "Step"/"How to" heading with ordered list detected |
| `has_research_refs` | "According to"/"study"/"research" attribution phrases |
| `has_expert_quotes` | `<blockquote>` or "says/said" + quotes detected |

**Category D — Factual Density (3 fields):**

| Signal | Measurement |
|--------|-------------|
| `data_point_count` | Count of numbers with `%`, `$`, year patterns |
| `citation_density` | Outbound links per 1000 words |
| `named_entity_density` | Capitalized multi-word phrases per 1000 words |

**Original 11 fields** (`word_count`, `paragraph_count`, `header_count`, `list_item_count`, `stat_count`, `citation_count`, `has_headers`, `has_lists`, `has_numbers`, `authority_type`, `content_type`) are preserved at the top of `StructuralSignals` for backward compatibility.

**Dependencies added:** `trafilatura>=1.6.0` (content extraction), `textstat>=0.7.0` (Flesch-Kincaid reading level).

**Output:** `enriched_citations.json` — List of `EnrichedCitation` with paragraphs and ~45 structural signals.

---

### 6.5 Step 5 — Embed Content

**File:** `core/gap_analysis/steps/s5_embed_content.py`

**Purpose:** Embed query texts and citation paragraphs into the same vector space; select the top-k best-matching paragraphs per citation.

**3-Phase Approach:**

**Phase 1: Collect & Sanitize**
- Filter garbage content: binary data, PDF signatures, base64 encoding, tiny paragraphs (<50 chars)
- Truncate long paragraphs to 6,000 characters (safe for OpenAI token limit)
- De-duplicate texts globally (same paragraph from multiple URLs → single embedding)

**Phase 2: Bulk Embed**
- Embed all unique texts via OpenAI in batches of 256
- On batch failure: retry one-by-one with zero-vector fallback (1536-dim zero vector)

**Phase 3: Score & Select**
- Compute cosine similarity between anchor text embedding and paragraph embeddings
- Select top-k (k=3) best-matching paragraphs per citation
- Upsert deduplicated embeddings to ChromaDB citations collection

**Outputs:**
| File | Content |
|------|---------|
| `embeddings/queries_with_embeddings.json` | GeneratedQuery objects with embedding vectors |
| `embeddings/citations_with_embeddings.json` | EnrichedCitation objects with best_paragraphs |
| ChromaDB collection: `gap_citations_{slug}` | Citation paragraph embeddings |

---

### 6.6 Step 6 — Semantic & Structural Analysis (SPA)

**File:** `core/gap_analysis/steps/s6_analyze.py`

**Purpose:** The core analytical step. Computes semantic proximity, gap measurements, statistical tests, centroid distances, and content specifications per cluster.

**Analysis Components:**

**1. Query-Citation Similarity**
For each query, find top-N (N=5) citations by best-paragraph similarity, compute average citation similarity.

**2. Query-Company Similarity**
For each query, find best-matching company semantic unit. Track best similarity + unit metadata.

**3. Gap Calculation**
```
gap = avg_citation_similarity - best_company_similarity
```
| Gap Value | Interpretation |
|-----------|----------------|
| gap ≥ 0.15 | `significant_gap` — Company severely underperforms |
| gap ≥ 0.05 | `gap_to_close` — Company is behind citations |
| -0.05 < gap < 0.05 | `roughly_equal` — Company is competitive |
| gap ≤ -0.05 | `company_wins` — Company outperforms citations |

**4. Citation Exemplars**
Top-3 cited pages per query with: similarity score, domain, URL, snippet, structural signals (~45 fields), authority type. Exemplars are URL-deduped to prevent single-URL bias. `per_paragraph_word_counts` is stripped from exemplar signals to prevent artifact bloat.

**4b. Per-Query Content Briefs (GapContentBrief)**
For each query with ≥1 exemplar, `_compute_content_brief(exemplars)` derives a `GapContentBrief`:
- `target_word_count`, `target_reading_level`, `avg_paragraph_length`, `recommended_header_count` — (min, max) tuples from exemplar ranges
- `header_hierarchy` — median h2/h3/h4 counts across exemplars
- Boolean rates: `has_faq_section`, `has_key_takeaways`, `has_step_by_step`, `has_tables`, etc. — fraction of exemplars exhibiting each pattern
- `target_data_point_density`, `target_citation_density` — median density values
- `dominant_authority_type`, `dominant_content_type` — most common type via Counter
- Attached to `QueryGap.content_brief`

**5. SPA (Semantic Proximity Analysis)**
Per-cluster independent t-test comparing citation similarities vs. company similarities:
- Computes t-statistic, p-value
- Effect interpretation: "citation_advantage" or "company_advantage"

**6. Centroid Analysis**
Per cluster: compute centroid of query embeddings & citation embeddings. Distance = 1 - cosine_similarity(query_centroid, citation_centroid). Measures cluster-level embedding space distance.

**7. Citation Patterns**
Aggregate distributions:
- Domain distribution (Counter — which domains are cited most)
- Authority type distribution (gov, edu, org, commercial)
- Content type distribution (blog, guide, docs, research, etc.)

**8. Cluster Content Specifications**
Per cluster, generates actionable specs for the Content Generation Engine:
- Word count range (min–max from cited exemplars)
- Authority signals distribution
- Structural rates (% with headers, lists, stats, citations)
- Required elements (elements present in ≥80% of top citations)
- Min similarity threshold (mean - 0.5 × std for quality gate)
- **Expanded fields (v3):** `faq_rate`, `table_rate`, `definition_rate`, `code_block_rate`, `key_takeaways_rate` — fraction of citations with each pattern
- `avg_word_count`, `avg_paragraph_word_count`, `avg_sentence_count_per_paragraph` — aggregate text metrics
- `min_bullets_per_list` — minimum list items across citations
- `dominant_content_type`, `dominant_authority_type` — most common types via Counter
- `exemplar_themes` — top terms via TF-IDF (scikit-learn TfidfVectorizer) on exemplar query texts, wrapped in try/except for empty-vocabulary edge case

**Output:** `analysis.json` — Complete `AnalysisResult` object.

---

### 6.7 Step 7 — Visualize

**File:** `core/gap_analysis/steps/s7_visualize.py`

**Purpose:** Generate interactive Plotly HTML visualizations of embedding space and gap analysis results.

**Visualizations Generated:**

| Visualization | Type | Description |
|---------------|------|-------------|
| Embedding Space Explorer | UMAP scatter | All query/citation/company embeddings in 2D |
| t-SNE Embedding Space | t-SNE scatter | Alternative dimensionality reduction |
| Clustered Embedding Space | UMAP/t-SNE colored by cluster | Shows cluster separation |
| Gap Heatmap | Heatmap | Per-query gaps vs. clusters |
| Gap Distribution | Box plot by cluster | Gap spread per cluster |
| Citation Treemap | Treemap | Domain distribution |
| Similarity Histogram | Histogram | Distribution of similarity scores |
| Per-Cluster Boxplot | Boxplot | Company vs. citation similarity per cluster |
| Cluster Radar | Radar chart | Multi-dimensional cluster comparison |

**Output:** `visualizations/` directory with HTML files + `paths.json` mapping.

**Key Implementation Details:**
- `_collect_typed_embeddings()` — Applies top-N/top-K filtering to manage embedding count
- `_reduce_embeddings()` — t-SNE or UMAP dimensionality reduction
- `_compute_proximity_pairs()` — Similarity scores for each query-citation pair

---

### 6.8 Step 8 — Generate Report

**File:** `core/gap_analysis/steps/s8_generate_report.py`

**Purpose:** Produce the final gap analysis report (Markdown + JSON), generation specifications, and full-fidelity analysis JSON.

**3-Tier Output Architecture:**

**Tier 1: `gap_analysis_complete.json` (Full Fidelity)**
- Written by `save_report(report, output_dir, analysis=analysis)` when `analysis` is provided
- Contains: `generated_at` timestamp, full `analysis` (all QueryGaps with GapContentBriefs, all exemplars with enriched signals), all `cluster_specs`, `report_json`, `generation_spec_json`
- Additive — does NOT replace existing 3-file contract. Content engine's 3-file loading is unchanged.

**Tier 2: JSON Files (Machine-Readable)**
- `gap_report.json` — Executive summary + recommendations (unchanged contract)
- `generation_spec.json` — Cluster specs (unchanged contract)

**Tier 3: Markdown Reports (Human-Readable)**

*Phase A: Programmatic Reports*
- `gap_report.md` — Summary + **top 25 gap briefs** (up from 10) with inline ContentBrief sections showing: target word count, reading level, recommended headers, content patterns (FAQ rate, table rate, key takeaways), dominant authority/content types. Remaining gaps (after 25) go in appendix table.
- `generation_spec.md` — Per-cluster content specs with expanded fields: FAQ rate, table rate, avg word count, avg paragraph word count, dominant content/authority types, exemplar themes

*Phase B: LLM-Generated Summary*
- Calls OpenAI (GPT-5.2) with focused prompt including expanded cluster spec context
- Generates: executive summary + top-5 content recommendations
- Each recommendation includes: title idea, target cluster, structural signals to match, impact reasoning
- Prepended to `gap_report.md`

**Outputs:**
| File | Content |
|------|---------|
| `gap_report.md` | Human-readable analysis with executive summary + recommendations |
| `gap_report.json` | Machine-readable version |
| `generation_spec.md` | Content specs per cluster for the generation engine |
| `generation_spec.json` | Machine-readable version |
| `gap_analysis_complete.json` | Full-fidelity JSON with all ContentBriefs + exemplar signals (when analysis provided) |

**Pipeline Integration:** `pipeline.py` passes `analysis` to `save_report()` at line 283.

---

### 6.9 LLM Engine Abstraction

**File:** `core/gap_analysis/engines/base.py`

**Abstract Base Class:**
```python
class SearchEngine(ABC):
    engine_name: str
    model: Optional[str]

    @abstractmethod
    async def search(self, query_text: str, query_id: Optional[str] = None) -> PlatformResult:
        """Execute a search query and return result with citations."""
```

**Implementation Details:**

| Engine | File | API Pattern | Citation Source | Notes |
|--------|------|-------------|----------------|-------|
| Perplexity | `perplexity.py` | Perplexity SDK (sync, wrapped in asyncio.to_thread) | Direct `citations` list | Slowest but most comprehensive |
| OpenAI | `openai_engine.py` | OpenAI REST `client.responses.create()` | Parsed from `web_search_call.action.sources` | Experimental responses API (o1/o3) |
| Gemini | `gemini.py` | Google AI REST | `groundingMetadata.groundingChunks[].web.uri` | May return Vertex AI redirect URLs |
| Claude | `claude.py` | Anthropic REST (beta) | Content blocks + tool_result | Uses `web-search-2025-03-05` beta header |

**Common Patterns:**
- All engines use `asyncio.to_thread()` for sync SDK wrappers
- Error handling: returns error message in `response_text` on exception (never crashes pipeline)
- Citation rank: sequential index (1, 2, 3, ...) in extraction order
- Source attribution: each citation tagged with engine name

---

### 6.10 Data Flow Between Steps

```
GapAnalysisInput
  │
  ├── S1: domain, seed_urls ──────────────────────▶ company_embeddings.json + ChromaDB
  │                                                   │
  ├── S2: company_context_path, persona_paths ────▶ queries.json
  │                                                   │
  ├── S3: queries.json + platforms ────────────────▶ platform_results/{engine}.jsonl
  │                                                   │
  ├── S4: platform_results ────────────────────────▶ enriched_citations.json
  │                                                   │
  ├── S5: queries + citations ─────────────────────▶ embeddings/*.json + ChromaDB
  │                                                   │
  ├── S6: company_units + queries + citations ─────▶ analysis.json
  │                                                   │
  ├── S7: all_data + analysis ─────────────────────▶ visualizations/*.html
  │                                                   │
  └── S8: analysis + queries + citations ──────────▶ gap_report.{md,json}
                                                      generation_spec.{md,json}
                                                      gap_analysis_complete.json
```

**Key Artifact Dependencies:**
- S2 requires: `company_context_path` (reads company artifact from disk)
- S2 requires: `persona_paths` (reads persona artifacts from disk)
- S2 requires: `style_guide_path` (reads style guide from disk)
- S2 requires: query taxonomy file (`b2b_queries_180.json` — hardcoded path)
- S5 requires: ChromaDB collection from S1 (for company embedding IDs)
- S6 requires: ChromaDB collections from S1 + S5 (for embedding vectors)

---

## 7. Pipeline 3: Content Generation Engine

**Status:** Implemented (v1.0). Branch: `feat/content-engine-v1.0.0`. 57/57 tests passing.

**Architecture:** 4-stage async pipeline using two Anthropic agent patterns:
- **Orchestrator-Workers** — parallel content production with semaphore-controlled concurrency
- **Evaluator-Optimizer** — 4-dimension quality gate with automated revision cycles

```
┌──────────────────────────────────────────────────────────────────────┐
│  [1/4] Strategic Planner (Sonnet 4.5)                                │
│    Input: gap report + generation spec + company context + personas  │
│    Output: List[ContentBrief] — prioritized content assignments      │
└──────────────────┬───────────────────────────────────────────────────┘
                   │ spawns N worker chains (asyncio.Semaphore)
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  [2/4] Content Workers (parallel)                                    │
│    Per brief: Outliner (Sonnet) → Drafter (Sonnet) →                 │
│               Fact Enricher (Perplexity sonar-pro) →                 │
│               Formatter (Haiku 4.5)                                  │
│    Output: List[FormattedContent]                                    │
└──────────────────┬───────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  [3/4] Evaluator-Optimizer Loop (max 2 revision cycles)              │
│    4 dimensions in parallel: Structural (code) + Semantic (embed)    │
│                               + Style (Haiku judge) + Factual        │
│                                 (Sonnet judge)                       │
│    Failed → compile feedback → revise → re-evaluate                  │
│    Output: List[FormattedContent] + RevisionHistory                  │
└──────────────────┬───────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  [4/4] Human Review (LangGraph HITL)                                 │
│    interrupt() → approve / edit / reject per piece                   │
│    auto_approve flag skips interrupt                                  │
│    Output: List[ContentPiece] with status + final markdown           │
└──────────────────────────────────────────────────────────────────────┘
```

**Entry Point:** `core/content_engine/pipeline.py` → `run_content_generation(input_data)`
**CLI:** `scripts/run_content_engine.py`

**Input:**
- `generation_spec.json` from Pipeline 2 (cluster content specs)
- `gap_report.json` from Pipeline 2 (prioritized content recommendations)
- Research artifacts from Pipeline 1 (company context, personas, style guide)
- `analysis.json` from Pipeline 2 (semantic analysis data)

**Output:**
- Content pieces in `artifacts/content/{slug}/content/brief-{N}/final.md`
- Run metadata in `artifacts/content/{slug}/run_metadata.json`
- Per-brief artifacts: `outline.json`, `draft.md`, `enriched.md`, `formatted.md`, `eval_history.json`

### 7.1 Stage 1 — Strategic Planner

**File:** `core/content_engine/planner.py`
**Prompts:** `core/content_engine/prompts/planner_prompts.py`

```python
async def plan_content(
    input_data: ContentGenerationInput,
    company_context_md: str,
    style_guide_md: str,
    persona_mds: List[str],
    gap_report_json: dict,
    generation_spec_json: dict,
    analysis_json: dict,
    session_id: str = "",
) -> PlannerOutput
```

- **Model:** Sonnet 4.5 via `AsyncAnthropic` (raw SDK)
- **Pattern:** Single LLM call with structured JSON output
- **Context window guard:** `truncate_to_token_limit()` applied to company context and personas
- **JSON parsing:** `safe_parse()` with code fence extraction and trailing comma cleanup
- **Output:** `PlannerOutput` with `List[ContentBrief]` — each brief includes `word_count_range`, `structural_targets`, `target_queries`, `key_topics`, `key_angles`
- **Tracing:** Langfuse generation logged under `planner` trace

### 7.2 Stage 2 — Content Workers (Orchestrator-Workers)

**Dispatcher:** `core/content_engine/workers/dispatcher.py`

```python
async def dispatch_workers(
    briefs: List[ContentBrief],
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    max_concurrent: int = 3,
    session_id: str = "",
    artifact_dir: Path = Path("."),
) -> List[FormattedContent]
```

Uses `asyncio.Semaphore(max_concurrent)` + `asyncio.gather(return_exceptions=True)`. Failing one worker does NOT cancel the batch.

**Worker Chain (4 steps per brief):**

| Step | File | Model | Function | Output |
|------|------|-------|----------|--------|
| 1. Outline | `workers/outliner.py` | Sonnet 4.5 | `generate_outline()` | `ContentOutline` |
| 2. Draft | `workers/drafter.py` | Sonnet 4.5 | `generate_draft()` | `ContentDraft` |
| 3. Enrich | `workers/fact_enricher.py` | Perplexity sonar-pro | `enrich_with_facts()` | `EnrichedDraft` |
| 4. Format | `workers/formatter.py` | Haiku 4.5 | `format_content()` | `FormattedContent` |

**Each step:**
- Has its own prompt file in `core/content_engine/prompts/`
- Logs a Langfuse span under the worker trace
- Persists intermediate artifact to disk (`outline.json`, `draft.md`, `enriched.md`, `formatted.md`)

**Fact Enricher:** Uses httpx to call Perplexity API directly. Gracefully skips if `PERPLEXITY_API_KEY` not set (returns draft unchanged). Detects added citations via regex.

**Formatter:** Uses `_count_structural_elements(markdown)` for word count, header count, list count, stat count, and citation count using regex patterns.

**Drafter also provides:** `revise_draft()` — used during evaluator revision cycles to incorporate feedback.

**CLI Progress:**
```
  [2/4] Content Workers .......
         Worker #1: Outlining "409A Valuation..."
         Worker #1: Drafting "409A Valuation..."
         Worker #2: Outlining "ASC 718 Explained..."
         Worker #1: DONE (2,847 words, 8 headers, 12 citations)
         Workers complete: 10/10 briefs ............ 142.5s
```

### 7.3 Stage 3 — Evaluator-Optimizer Loop

**Orchestrator:** `core/content_engine/evaluator/loop.py`

```python
async def evaluate_and_optimize(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str,
    style_guide_md: str,
    input_data: ContentGenerationInput,
    max_cycles: int = 2,
    session_id: str = "",
    artifact_dir: Path = Path("."),
) -> tuple[FormattedContent, RevisionHistory]
```

**4 Evaluation Dimensions (run in parallel via `asyncio.gather`):**

| Dimension | File | Type | Model | Threshold |
|-----------|------|------|-------|-----------|
| Structural | `evaluator/structural.py` | Deterministic (Python) | None | >= 0.8 |
| Semantic | `evaluator/semantic.py` | Embedding proximity | OpenAI text-embedding-3-small | >= 0.65 |
| Style | `evaluator/style_judge.py` | LLM-as-Judge | Haiku 4.5 | >= 0.7 |
| Factual | `evaluator/factual_judge.py` | LLM-as-Judge | Sonnet 4.5 | >= 0.7 |

**Structural Evaluator (8 checks):**
1. Word count within `word_count_range`
2. Header count >= `structural_targets.min_headers`
3. List count >= `structural_targets.min_lists`
4. Citation count >= `structural_targets.min_citations`
5. At least 1 statistic present
6. Heading hierarchy valid (no H4 before H2)
7. No empty sections (heading with < 30 chars before next heading)
8. Required elements present (from brief)

Score = passed_checks / total_checks. Passes if >= 0.8.

**Semantic Evaluator:** Embeds content via `async_embed_texts()` (reuses `core/shared_tools/async_embedding_client.py`), computes cosine similarity against target query embeddings.

**Style Judge:** Evaluates tone consistency, terminology alignment, readability, authority signals against the style guide. Returns JSON with `score` (0-1) and `feedback`.

**Factual Judge:** Evaluates claim accuracy, source quality, recency, completeness. Returns JSON with `score` (0-1) and `feedback`.

**Revision Logic:**
1. If any dimension fails → compile feedback from all failed dimensions
2. Re-run: `revise_draft()` → `enrich_with_facts()` → `format_content()` (skip Outliner)
3. Re-evaluate all 4 dimensions
4. If still failing after `max_cycles` → flag for HITL with eval results attached
5. Early exit when `max_revision_cycles=0` (skip evaluator entirely)

### 7.4 Stage 4 — Human Review (LangGraph HITL)

**File:** `core/content_engine/graph.py`

```python
def build_content_review_graph() -> CompiledGraph
async def run_content_review(
    formatted_contents: List[FormattedContent],
    briefs: List[ContentBrief],
    revision_histories: List[RevisionHistory],
    session_id: str = "",
    artifact_dir: Path = Path("."),
) -> List[ContentPiece]
```

**Graph nodes:** `present_content` → `approval_gate` (interrupt) → `route` → `finalize` / `apply_edits` / END

**Resume tokens:** `{"approval_decision": "approve"|"edit"|"reject", "editor_notes": "..."}`

**`auto_approve` flag** skips interrupt (same pattern as research pipeline). Approved content saved to `final.md`.

### 7.5 Langfuse Tracing Architecture

**File:** `core/content_engine/tracing.py`

**SDK Version:** Langfuse v3.14+ (v3 API — **breaking change from v2**, migrated 2026-02-16)

Lazy singleton `Langfuse` client — returns None if not configured (no-op when `LANGFUSE_PUBLIC_KEY` not set). All tracing functions catch exceptions internally and return None, so Langfuse unavailability never crashes the pipeline.

**v2 → v3 Migration (Breaking Changes Applied):**

| v2 API (removed) | v3 API (current) |
|---|---|
| `lf.trace()` | `lf.start_span()` + `span.update_trace(session_id=...)` |
| `target.generation()` | `target.start_generation()` + `gen.end()` |
| `target.span()` | `target.start_span()` |
| `usage=` parameter | `usage_details=` parameter |
| `span.end(**kwargs)` | `span.update(**kwargs)` then `span.end()` |

**Note:** `start_generation()` is already deprecated in 3.14.1 in favor of `start_observation(as_type='generation')`. Current code uses `start_generation()` — monitor for future migration.

**Hierarchy (v3 — Span-based, not Trace-based):**
```
Session: content-gen-{slug}-{timestamp}     (implicit — created when trace references session_id)
  └── Root Span: content-pipeline/{slug}    (acts as trace via update_trace())
        ├── Stage Span: stage/1-planner
        │     └── Span: planner → Generation: plan_content
        ├── Stage Span: stage/2-workers
        │     ├── Span: Worker #1 → outliner/drafter/fact_enricher/formatter
        │     └── Span: Worker #2 → ...
        ├── Stage Span: stage/3-evaluator
        │     └── Span: evaluator/{brief_id} → eval_cycle_0 / revision_cycle_1 / ...
        └── Stage Span: stage/4-review
              └── Span: Review: {title} → Score: human_decision
```

**Key difference from v2:** In v3, there is no `lf.trace()` method. Instead, a root span is created with `lf.start_span()`, then `span.update_trace(session_id=..., tags=..., user_id=...)` promotes it to function as the trace. Child spans and generations nest under this root span.

**Helper functions:** `create_session()`, `create_pipeline_trace()`, `log_generation()`, `create_span()`, `end_span()`, `update_trace_output()`, `log_score()`, `flush()`

### 7.6 Artifact Structure

```
artifacts/content/{company-slug}/
├── briefs.json                    # PlannerOutput (all briefs)
├── content/
│   └── brief-{N}/
│       ├── outline.json           # ContentOutline
│       ├── draft.md               # Raw draft markdown
│       ├── enriched.md            # Fact-enriched markdown
│       ├── formatted.md           # Style-formatted markdown
│       ├── eval_history.json      # RevisionHistory
│       └── final.md               # Approved content
└── run_metadata.json              # ContentGenerationOutput
```

### 7.7 Utility Modules

**File:** `core/content_engine/utils.py`

| Function | Purpose |
|----------|---------|
| `safe_parse(text, model_cls)` | Extract JSON from LLM response (code fences, trailing commas) → Pydantic model |
| `_retry_async_anthropic(fn, max_retries, base_delay)` | Provider-agnostic retry with jittered exponential backoff (Anthropic + OpenAI errors) |
| `_estimate_tokens(text)` | Approximate token count (chars / 3.5) |
| `truncate_to_token_limit(text, max_tokens)` | Pre-flight context window guard — truncates by paragraph |

---

## 8. Reddit Human-in-the-Loop Monitor

**Files:** `core/reddit_hil/` (graph.py, reddit_client.py, webhooks.py, cli.py)

**Purpose:** A standalone monitoring system that finds high-value Reddit threads matching a company's ICP persona, drafts contextual replies using the company's style guide, and notifies the team via Slack/Discord.

### Architecture

```
LangGraph State Machine:
  load_artifacts → fetch_candidates → dedupe_cache → rank_filter → draft_reply → notify → END
```

### Graph Nodes

**1. `load_artifacts`**
- Loads 3 artifact files: company context, ICP persona, style guide
- Uses DeepAgents-style virtual paths (`/artifacts/...`)
- Max 400KB per artifact (prevents token explosion in LLM calls)
- Raises error if any artifact missing

**2. `fetch_candidates`**
- Uses PRAW (read-only mode) to fetch newest threads from configured subreddits
- Default: 25 threads per subreddit
- Returns `List[RedditThread]` (Pydantic model)
- **Safety:** Explicitly asserts `reddit.read_only == True`

**3. `dedupe_cache`**
- Loads previously-seen thread IDs from persistent JSON cache
- Cache path: `artifacts/_logs/reddit_monitor/{company_slug}__seen.json`
- Filters out already-processed threads

**4. `rank_filter`**
- Extracts keywords from persona markdown (up to 80 terms from Pain Points, Buying Triggers, Messaging Angles)
- Heuristic scoring: keyword matches / soft cap
- Pre-filters: no over-18, no stickied, no locked, age < max_age_hours, title length > 18 chars
- Returns top-k shortlisted threads

**5. `draft_reply`**
- Single LLM call (Gemini via LangChain)
- Prompt includes: full company context, persona, style guide, top-k candidate threads
- LLM returns JSON: `[{thread_id, fit_score, why_match, draft_markdown}]`
- Parses JSON, matches back to original threads
- Returns `List[DraftNotification]`

**6. `notify`**
- Sends Slack webhooks (Block Kit with aggressive truncation: 2500 chars/block, max 3 blocks)
- Sends Discord webhooks (chunked to 1800 chars/message, max 3 messages, code-fenced)
- Updates persistent seen-IDs cache
- Dry-run mode: skips webhooks, only caches IDs

### CLI Usage

```bash
python -m core.reddit_hil.cli \
  --company-name "Ramp" \
  --company-slug "ramp" \
  --subreddits "marketing,startups,entrepreneur" \
  --top-k 5 \
  --dry-run
```

---

## 9. Storage Architecture

### Design Principle

> **Filesystem writes first, DB mirrors second. If DB write fails, the filesystem is always the source of truth.**

### 9.1 Filesystem Layer (Source of Truth)

All artifacts live in the `/artifacts/` directory tree. This is the canonical store during local development.

**Artifact Lifecycle:**
```
Agent generates content
    ↓
Write to {slug}.draft.md           ← Draft stage (human review)
    ↓ (human approves)
Promote to {slug}.md               ← Final artifact
    ↓ (if Supabase configured)
Mirror to Supabase                  ← Optional DB snapshot
```

**Naming Conventions:**
- Drafts: `{slug}.draft.md`
- Finals: `{slug}.md`
- Slug derivation: `company_name.lower().replace(" ", "-")`

### 9.2 DeepAgents Backend Routing (CompositeBackend)

**File:** `core/research/agents/base.py`

When DeepAgents write files, the `CompositeBackend` routes writes to the appropriate storage:

| Virtual Path Prefix | Backend | Physical Location |
|---------------------|---------|-------------------|
| `/artifacts/*` | `FilesystemBackend` | `content-strategy-engine/artifacts/` |
| `/memories/*` | `StoreBackend` | In-memory (InMemoryStore singleton) |
| Everything else | `StateBackend` | Per-thread scratchpad (ephemeral) |

**Singleton Pattern:**
```python
_store = None

def get_store():
    global _store
    if _store is None:
        _store = InMemoryStore()
    return _store
```

### 9.3 ChromaDB Vector Store

**File:** `core/shared_tools/chroma_client.py`

**Purpose:** Persistent local vector storage for gap analysis embeddings.

**Collections per company:**
- `gap_company_{slug}` — Company asset embeddings (from S1)
- `gap_citations_{slug}` — Citation paragraph embeddings (from S5)

**Configuration:**
```python
chroma_persist_dir = settings.chroma_persist_dir  # Default: "artifacts/chroma_db"
chroma_collection_prefix = settings.chroma_collection_prefix  # Default: "gap_company"
```

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `get_chroma_client()` | Persistent ChromaDB client (anonymized telemetry disabled) |
| `get_company_collection(slug)` | Get/create company collection (cosine metric) |
| `upsert_embeddings(slug, ids, texts, embeddings, metadatas)` | Batch upsert (chunks of 500) |
| `get_embeddings_by_ids(slug, ids)` | Retrieve specific embeddings by ID |
| `get_all_embeddings(slug)` | Retrieve all embeddings for a company |
| `collection_exists(slug)` | Check if collection has data |
| `delete_company_collection(slug)` | Delete for re-runs (idempotent) |
| `get_citations_collection(slug)` | Separate collection for citation embeddings |
| `upsert_citation_embeddings(slug, ids, docs, embeddings, metadatas)` | Citation-specific upsert |

### 9.4 Supabase Mirror (Optional DB Layer)

**Files:** `core/storage/supabase_client.py`, `core/storage/supabase_mirror.py`

**Client Factory:**
```python
@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = settings.effective_supabase_url
    key = settings.effective_supabase_key
    if not url or not key:
        raise RuntimeError("Supabase env not set...")
    return create_client(url, key)
```

**Mirror Functions (3 artifact types):**

Each type has a `mirror_*_if_configured()` convenience wrapper that is safe to call unconditionally — returns `None` silently if `company_id` or Supabase env vars are missing.

**1. `mirror_company_context_markdown()`**
- Creates/updates row in `artifacts` table (type: `company_context`)
- Appends immutable snapshot to `artifact_versions` table
- Computes SHA256 hash of markdown for integrity

**2. `mirror_persona_markdown()`**
- Same pattern, type: `persona`
- Matches by `(company_id, type='persona', content.path)` — handles multiple personas per company

**3. `mirror_styleguide_markdown()`**
- Same pattern, type: `guidelines`

**Supabase Data Structure:**

```json
// artifacts table row
{
  "id": "a-456",
  "company_id": "c-123",
  "type": "company_context",
  "title": "Acme Corp — Company Context",
  "status": "active",
  "version": 1,
  "content": {
    "format": "md",
    "path": "artifacts/company_context/acme-corp.md",
    "body": "# Company Context: Acme Corp\n...",
    "sha256": "abc123...",
    "domain": "acme.com",
    "mirrored_at": "2026-02-15T10:30:00Z"
  },
  "source": "agent",
  "last_regenerated_by": "agent-1"
}

// artifact_versions table row (immutable)
{
  "artifact_id": "a-456",
  "version_no": 1,
  "body_md": "# Company Context: Acme Corp\n...",
  "metadata": {
    "path": "artifacts/company_context/acme-corp.md",
    "sha256": "abc123...",
    "mirrored_at": "2026-02-15T10:30:00Z"
  }
}
```

### 9.5 Storage Backend Abstraction (Interface)

**File:** `core/storage/backends/base.py`

**Abstract Interface (defined, no concrete implementations yet):**

```python
class StorageBackend(ABC):
    @abstractmethod
    def read(self, path: str) -> Optional[str]: ...

    @abstractmethod
    def write(self, path: str, content: str) -> str: ...

    @abstractmethod
    def exists(self, path: str) -> bool: ...

    @abstractmethod
    def delete(self, path: str) -> bool: ...

    @abstractmethod
    def list_dir(self, prefix: str) -> list[str]: ...
```

**Planned Implementations:**
- `LocalFilesystemBackend` — Local dev (default)
- `S3Backend` / `GCSBackend` — Cloud storage for production
- `SupabaseStorageBackend` — Supabase Storage buckets

**Current Status:** Interface defined but no concrete backend classes implemented yet. The `DeepAgents.FilesystemBackend` is used directly in the research pipeline (separate from this abstraction).

---

## 10. Data Models — Complete Pydantic v2 Schema Reference

### Research Pipeline Models

#### `CompanyResearchInput` (`core/models/artifacts.py`)
```
company_id:             Optional[str]     # Supabase UUID (enables mirroring)
auto_mirror:            bool = False      # Auto-mirror after approval
company_name:           str               # Display name
domain:                 Optional[str]     # e.g., "ramp.com"
seed_urls:              List[HttpUrl]     # Starting URLs for research
internal_sources:       List[str]         # Paths to internal docs
language:               str = "en"
region:                 Optional[str]     # Geographic context
additional_constraints: Optional[str]     # Extra instructions for agent
```

#### `CompanyContextArtifact` (`core/models/artifacts.py`)
```
company_name, domain, origin_story, products_services, market_positioning,
target_audience, brand_perception, competitors, growth_drivers, bottlenecks,
goals_urgency, risks_unknowns, recommendations,
fact_table:     List[FactRow]
open_questions: List[str]
sources:        List[SourceDoc]

Methods:
  to_markdown() → str  # Renders structured Markdown
```

#### `PersonaResearchInput` (`core/models/personas.py`)
```
company_id, company_name, domain, company_slug,
company_context_path:   Optional[str]     # Path to company artifact (injected by pipeline)
internal_sources:       List[str]
max_personas:           int = 3           # 1 ICP + up to 2 secondary
language, region, additional_constraints
```

#### `PersonaArtifact` (`core/models/personas.py`)
```
company_name, persona_name, kind (PersonaKind: "icp" | "secondary"),
role_title, industry_context, summary, role_and_context, day_in_life,
kpis_success, pain_points_blockers, buying_triggers,
trust_builders_objections, annoyances, messaging_angles,
quotes: List[str], sources: List[str]

Methods:
  to_markdown() → str
```

#### `StyleGuideResearchInput` (`core/models/style_guide.py`)
```
company_id, company_name, domain, company_slug,
company_context_path:   Optional[str]     # Injected from Pipeline Stage 1
persona_paths:          List[str]          # Injected from Pipeline Stage 2
internal_sources, language, region, additional_constraints
```

#### `WritingStyleGuideArtifact` (`core/models/style_guide.py`)
```
company_name, domain, voice_tone, channel_variations, show_vs_tell,
sentence_language, jargon_rules, audience_resonance, product_positioning,
do_dont, formatting_structure, sample_snippets, sources: List[str]

Methods:
  to_markdown() → str
```

### Gap Analysis Models (`core/models/gap_analysis.py`)

**Site Discovery Models:**
```
DiscoverySource:     Enum (SITEMAP, SITEMAP_INDEX, ROBOTS_TXT, BFS_CRAWL, CANONICAL,
                           HREFLANG, RSS_FEED, SEED_URL, REDIRECT)
DiscoveredPage:      url, title, h1, meta_description, status_code, discovery_source,
                     depth, parent_url, canonical_url, word_count, has_content
SiteTreeNode:        url, title, path_segment, children, page_count_below
SiteDiscoveryResult: domain, base_url, total_pages, pages, site_tree, crawl_duration
```

**Pipeline Models:**
```
GapAnalysisInput:    company_name, domain, seed_urls, max_queries (default 150),
                     platforms (default: all 4), max_crawl_pages (500), max_crawl_depth (4)
SemanticUnit:        unit_id, url, title, text, embedding, embedding_id, char/word_count
QueryCluster:        cluster_id, cluster_name, intent, citation_behavior, buyer_stage
GeneratedQuery:      query_id, cluster_id, cluster_name, query_text, buyer_stage,
                     persona_tag, embedding
```

**Citation Models:**
```
CitationRef:         url, rank, title, snippet, confidence, source
PlatformResult:      engine, model, query_id, query_text, response_text,
                     citations: List[CitationRef]
CitationExemplar:    similarity, domain, url, snippet, structural_signals, authority_type
StructuralSignals:   ~45 fields across 4 categories (all with defaults for backward compat):
  Original (11):     word_count, paragraph_count, header_count, list_item_count,
                     stat_count, citation_count, has_headers, has_lists, has_numbers,
                     authority_type, content_type
  Cat A - Text (10): main_content_word_count, sentence_count, avg_paragraph_length,
                     median_paragraph_length, max_paragraph_word_count, avg_sentence_length,
                     avg_sentence_count_per_paragraph, reading_level, self_contained_ratio,
                     per_paragraph_word_counts: List[int]
  Cat B - Structure (13): h1_count, h2_count, h3_count, h4_count, ordered_list_count,
                     unordered_list_count, table_count, definition_list_count,
                     blockquote_count, code_block_count, list_block_count,
                     bullets_per_list_block, min_bullets_per_list
  Cat C - Patterns (8): has_faq_section, has_definition_opening, has_key_takeaways,
                     has_toc, has_comparison_table, has_step_by_step,
                     has_research_refs, has_expert_quotes
  Cat D - Density (3): data_point_count, citation_density, named_entity_density
EnrichedCitation:    url, domain, title, query_id, cluster_name, engine,
                     paragraphs, best_paragraphs, structural_signals
```

**Content Brief Models:**
```
GapContentBrief:     target_word_count: Tuple[int,int], target_reading_level: Tuple[float,float],
                     avg_paragraph_length: Tuple[int,int], recommended_header_count: Tuple[int,int],
                     header_hierarchy: Dict[str,int], has_ordered_lists, has_unordered_lists,
                     has_tables, has_faq_section, has_definition_opening, has_key_takeaways,
                     has_step_by_step (all float rates), target_data_point_density,
                     target_citation_density, dominant_authority_type, dominant_content_type,
                     exemplar_count
```

**Analysis Models:**
```
SpaResult:           cluster_id, cluster_name, t_stat, p_value,
                     mean_citation_sim, mean_company_sim, effect
CentroidResult:      cluster_id, cluster_name, query_centroid, citation_centroid, distance
QueryGap:            query_id, cluster_name, query_text, best_company_unit,
                     best_company_similarity, avg_citation_similarity, gap, interpretation,
                     top_cited_exemplars: List[CitationExemplar],
                     content_brief: Optional[GapContentBrief]
ClusterContentSpec:  cluster_id, cluster_name, query_count, word_count_range,
                     min_similarity_threshold, required_elements, authority_signals,
                     structural_rates, total_citations_analyzed,
                     faq_rate, table_rate, definition_rate, code_block_rate,
                     key_takeaways_rate, avg_word_count, avg_paragraph_word_count,
                     avg_sentence_count_per_paragraph, min_bullets_per_list,
                     dominant_content_type, dominant_authority_type,
                     exemplar_themes: List[str]
AnalysisResult:      proximity_stats, spa_results, centroids, gaps, citation_patterns,
                     decision_metrics, cluster_specs
GapReport:           report_md, report_json, generation_spec_md, generation_spec_json,
                     visualization_paths
```

### Content Generation Models (`core/models/content_generation.py`)

**Input Model:**
```
ContentGenerationInput: company_name, domain, company_context_path, persona_paths,
                        style_guide_path, gap_report_json_path, generation_spec_json_path,
                        analysis_json_path, max_briefs (10), max_concurrent_workers (3),
                        max_revision_cycles (2), auto_approve (False), skip_stages ([])
```

**Stage 1 Models:**
```
TargetQuery:       query_text, cluster_name, embedding (optional)
StructuralTargets: header_rate, list_rate, stat_rate, citation_rate,
                   min_headers (3), min_lists (1), min_citations (2)
ContentBrief:      brief_id, title, target_queries, target_cluster, content_format,
                   funnel_stage, channel, priority_score, word_count_range (Tuple[int,int]),
                   structural_targets (StructuralTargets), key_topics, key_angles,
                   competitor_exemplars, semantic_threshold (0.65)
PlannerOutput:     briefs: List[ContentBrief], planning_metadata: Dict
```

**Stage 2 Models:**
```
OutlineSection:    heading, level (2), key_points, target_word_count (300)
ContentOutline:    brief_id, title, sections: List[OutlineSection], total_target_words
ContentDraft:      brief_id, title, markdown, word_count
EnrichedDraft:     brief_id, title, markdown, word_count, facts_added: List[Dict]
FormattedContent:  brief_id, title, markdown, word_count, header_count, list_count,
                   stat_count, citation_count
```

**Stage 3 Models:**
```
DimensionResult:   dimension ("structural"|"semantic"|"style"|"factual"),
                   passed, score (0-1), feedback, details: Dict
EvalResult:        brief_id, cycle, dimensions: List[DimensionResult],
                   overall_passed, overall_score
RevisionHistory:   brief_id, cycles: List[EvalResult], final_passed
```

**Stage 4 Models:**
```
ContentStatus:     Enum: PENDING, APPROVED, EDITED, REJECTED
ContentPiece:      brief_id, title, status (ContentStatus), final_markdown,
                   eval_summary: Dict, human_notes, artifact_path
ContentGenerationOutput: company_slug, total_briefs, total_approved, total_rejected,
                        pieces: List[ContentPiece], run_metadata: Dict
```

### Reddit HIL Models (`core/models/reddit_hil.py`)
```
RedditMonitorInput:  company_name, company_slug, company_context_path, icp_persona_path,
                     style_guide_path, subreddits (default ["marketing"]),
                     max_threads_per_subreddit (25), max_age_hours (72),
                     shortlist_k (15), top_k (3), send_slack, send_discord, dry_run
RedditThread:        id, subreddit, title, url, created_utc, score, num_comments,
                     is_self, selftext, author, locked, stickied, over_18
                     Methods: text_for_matching(max_chars=4000)
DraftNotification:   thread, fit_score (0.0-1.0), why_match, draft_markdown, metadata
```

---

## 11. Configuration & Environment Variables

### Settings Architecture

**File:** `core/config/settings.py`
**Class:** `Settings(BaseSettings)` — Pydantic v2 BaseSettings with multi-file env loading
**Singleton:** `settings = Settings()` — Imported and used globally

**Env File Discovery Chain (in order of precedence):**
1. `{PROJECT_ROOT}/.env`
2. `{PROJECT_ROOT}/.env.local` (overrides)
3. `{PROJECT_ROOT}/.env.test.local` (test overrides)
4. `{PROJECT_ROOT}/../.env` (parent directory fallback)
5. `{PROJECT_ROOT}/../.env.local`
6. `{PROJECT_ROOT}/../.env.test.local`

### Complete Environment Variable Reference

#### Required — Research Pipeline

| Variable | Default | Purpose |
|----------|---------|---------|
| `PERPLEXITY_API_KEY` | — | Web research via sonar-deep-research |
| `GOOGLE_API_KEY_COMPANY_DEEPAGENT` | — | Company research agent (Gemini) |
| `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT` | — | Persona research agent (Gemini) |
| `GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT` | — | Style guide agent (Gemini) |

#### Required — Gap Analysis

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Embeddings (text-embedding-3-small) + query gen + reports |
| `ANTHROPIC_API_KEY` | — | Claude search engine |
| `GOOGLE_API_KEY_GAP_ANALYSIS` | — | Gemini search engine |

#### Model Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_GEMINI_MODEL_COMPANY_DEEPAGENT` | `gemini-3-flash-preview` | Company agent model |
| `GOOGLE_PERSONA_DEEPAGENTS_MODEL` | `gemini-3-flash-preview` | Persona agent model |
| `GOOGLE_STYLE_GUIDE_DEEPAGENTS_MODEL` | `gemini-3-flash-preview` | Style guide agent model |
| `DEEPAGENTS_MODEL` | `claude-sonnet-4-5-20250929` | Default DeepAgent LLM |
| `PERPLEXITY_DEEP_RESEARCH_MODEL` | `sonar-deep-research` | Perplexity model |
| `PERPLEXITY_SEARCH_MODEL` | `sonar-pro` | Perplexity search model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `GAP_ANALYSIS_QUERY_GEN_MODEL` | `gpt-5.2-2025-12-11` | Query generation |
| `GAP_ANALYSIS_REPORT_MODEL` | `gpt-5.2-2025-12-11` | Report generation |
| `GAP_ANALYSIS_OPENAI_ENGINE_MODEL` | `gpt-5.2-2025-12-11` | OpenAI search engine |
| `GAP_ANALYSIS_CLAUDE_ENGINE_MODEL` | `claude-sonnet-4-5-20250929` | Claude search engine |
| `GAP_ANALYSIS_GEMINI_ENGINE_MODEL` | `gemini-3-flash-preview` | Gemini search engine |
| `GOOGLE_GEMINI_MODEL_REDDIT_HIL` | `gemini-3-flash-preview` | Reddit monitor LLM |

#### Pipeline Settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `AEO_AGENT_INVOKE_TIMEOUT_S` | `900` (15 min) | Agent invocation timeout |
| `GAP_ANALYSIS_MAX_CRAWL_PAGES` | `500` | Max pages to crawl in S1 |
| `GAP_ANALYSIS_MAX_CRAWL_DEPTH` | `4` | Max crawl depth in S1 |

#### Storage & Database

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHROMA_PERSIST_DIR` | `artifacts/chroma_db` | ChromaDB storage path |
| `CHROMA_COLLECTION_PREFIX` | `gap_company` | ChromaDB collection naming |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Supabase admin key (preferred) |
| `SUPABASE_ANON_KEY` | — | Supabase anon key (fallback) |
| `SUPABASE_AGENT_ID` | — | Audit trail identifier |

#### Integrations

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDDIT_CLIENT_ID` | — | PRAW authentication |
| `REDDIT_CLIENT_SECRET` | — | PRAW authentication |
| `REDDIT_USER_AGENT` | — | PRAW user agent |
| `SLACK_WEBHOOK_URL` | `""` | Slack notifications |
| `DISCORD_WEBHOOK_URL` | `""` | Discord notifications |
| `BRAVE_SEARCH_API_KEY` | — | Alternative search (unused currently) |
| `GOOGLE_API_KEY_REDDIT_HIL` | — | Reddit monitor Gemini key |

#### Content Generation Engine

| Variable | Default | Purpose |
|----------|---------|---------|
| `CONTENT_ENGINE_PLANNER_MODEL` | `claude-sonnet-4-5-20250929` | Strategic planner model |
| `CONTENT_ENGINE_WORKER_MODEL` | `claude-sonnet-4-5-20250929` | Outliner + drafter model |
| `CONTENT_ENGINE_FORMATTER_MODEL` | `claude-haiku-4-5-20251001` | Formatter model |
| `CONTENT_ENGINE_STYLE_JUDGE_MODEL` | `claude-haiku-4-5-20251001` | Style judge model |
| `CONTENT_ENGINE_FACTUAL_JUDGE_MODEL` | `claude-sonnet-4-5-20250929` | Factual judge model |
| `CONTENT_ENGINE_FACT_ENRICHER_MODEL` | `sonar-pro` | Perplexity fact enricher model |
| `CONTENT_ENGINE_MAX_CONCURRENT_WORKERS` | `3` | Max parallel worker chains |
| `CONTENT_ENGINE_MAX_REVISION_CYCLES` | `2` | Max eval-revise cycles |

#### Observability (Langfuse)

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse project secret key |
| `LANGFUSE_HOST` | `https://us.cloud.langfuse.com` | Langfuse server URL |

#### FastAPI API Server

| Variable | Default | Purpose |
|----------|---------|---------|
| `API_CORS_ORIGINS` | `["http://localhost:3000","http://localhost:3001"]` | Allowed CORS origins (JSON array) |
| `API_PREFIX` | `/api/v1` | API route prefix |
| `API_MAX_CONCURRENT_PIPELINES` | `3` | Global semaphore cap for concurrent pipeline runs |

**Note:** API settings live in `api/config.py` as a separate `ApiSettings(BaseSettings)` class with `env_prefix="API_"`. All overridable via `API_*` environment variables.

#### Computed Properties

```python
effective_supabase_url:     SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL
effective_supabase_anon_key: SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY
effective_supabase_key:     SUPABASE_SERVICE_ROLE_KEY or effective_supabase_anon_key
```

---

## 12. CLI Entry Points — Scripts Reference

### Research Pipeline Scripts

#### `scripts/run_company_research.py` (74 lines)
```bash
python scripts/run_company_research.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --seed-url "https://ramp.com" \
  --seed-url "https://ramp.com/blog" \
  --internal-source "/path/to/transcript.txt" \
  --language en \
  --no-print       # Skip stdout output
  --overwrite       # Overwrite existing artifacts
```

**Pattern:** `build_graph()` → `graph.invoke({"input": inp, "overwrite": args.overwrite})` → print results

#### `scripts/run_persona_research.py` (80 lines)
```bash
python scripts/run_persona_research.py \
  --company-name "Ramp" \
  --company-context-path "/artifacts/company_context/ramp.md" \
  --max-personas 3 \
  --auto-approve    # Skip human review
```

#### `scripts/run_style_guide_research.py` (83 lines)
```bash
python scripts/run_style_guide_research.py \
  --company-name "Ramp" \
  --company-context-path "/artifacts/company_context/ramp.md" \
  --persona-path "/artifacts/personas/ramp__persona-icp.md" \
  --auto-approve
```

#### `scripts/run_pipeline.py` (132 lines)
```bash
python scripts/run_pipeline.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --seed-url "https://ramp.com" \
  --persona               # Enable persona stage
  --style                 # Enable style guide stage (requires --persona)
  --auto-approve          # Auto-approve all drafts
  --max-personas 1        # Default: 1 (not 3) for speed
```

**Special:** Only script that checks for interrupt status and handles resumption.

### Gap Analysis Scripts

#### `scripts/run_gap_analysis.py` (74 lines)
```bash
python scripts/run_gap_analysis.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --company-context-path "/artifacts/company_context/ramp.md" \
  --persona-path "/artifacts/personas/ramp__persona-icp.md" \
  --style-guide-path "/artifacts/style_guides/ramp.md" \
  --seed-url "https://ramp.com" \
  --max-queries 150 \
  --platforms "perplexity,openai,gemini,claude" \
  --skip-step 1 --skip-step 2   # Skip steps 1 and 2 (use cached data)
```

#### `scripts/run_gap_step.py` (340 lines)
Most detailed script — runs individual steps for debugging/iteration:
```bash
python scripts/run_gap_step.py \
  --step 6 \
  --company-slug "ramp" \
  --domain "ramp.com"
```
Provides rich status output: sample URLs, query cluster counts, domain distributions, similarity statistics.

### Utility Scripts

#### `scripts/resolve_vertexai_redirects.py` (140 lines)
Resolves Vertex AI Search redirect URLs in enriched citations:
```bash
python scripts/resolve_vertexai_redirects.py \
  --input artifacts/gap_analysis/ramp/enriched_citations.json \
  --in-place \
  --delay 0.3 \
  --timeout 20
```

#### `scripts/strip_embeddings_from_json.py` (67 lines)
Removes embedding vectors from JSON for smaller file sizes:
```bash
python scripts/strip_embeddings_from_json.py \
  --input artifacts/gap_analysis/ramp/company_embeddings.json
```

### Content Generation Scripts

#### `scripts/run_content_engine.py`
```bash
python scripts/run_content_engine.py \
  --company-name "Carta" --domain carta.com \
  --company-context-path artifacts/company_context/carta.md \
  --persona-path artifacts/personas/carta__persona-icp.md \
  --style-guide-path artifacts/style_guides/carta.md \
  --gap-slug carta \
  --max-briefs 5 --max-workers 3 --max-revisions 2 \
  --auto-approve \
  --skip-stage 3   # Skip evaluator loop
```

**Arguments:**
| Flag | Description |
|------|-------------|
| `--company-name` | Company name (required) |
| `--domain` | Company domain (required) |
| `--company-context-path` | Path to company context markdown |
| `--persona-path` | Path(s) to persona markdown (repeatable) |
| `--style-guide-path` | Path to style guide markdown |
| `--gap-slug` | Company slug for auto-discovering gap analysis artifacts |
| `--gap-report-json` | Path to gap report JSON (overrides --gap-slug) |
| `--generation-spec-json` | Path to generation spec JSON (overrides --gap-slug) |
| `--analysis-json` | Path to analysis JSON (overrides --gap-slug) |
| `--max-briefs` | Maximum content briefs to generate (default: 10) |
| `--max-workers` | Max concurrent worker chains (default: 3) |
| `--max-revisions` | Max evaluator revision cycles (default: 2) |
| `--auto-approve` | Auto-approve all content (skip HITL) |
| `--skip-stage` | Stage numbers to skip (repeatable: 1, 2, 3, 4) |

**Pattern:** Constructs `ContentGenerationInput`, calls `asyncio.run(run_content_generation(input_data))`.

#### `scripts/run_server.py` — FastAPI Server
```bash
python scripts/run_server.py
# or directly via uvicorn:
uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

**Default:** `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

**`--gap-slug` auto-discovery:** When provided, automatically resolves:
- `artifacts/gap_analysis/{slug}/gap_report.json`
- `artifacts/gap_analysis/{slug}/generation_spec.json`
- `artifacts/gap_analysis/{slug}/analysis.json`

**CLI Output:**
```
────────────────────────────────────────────────
  Content Generation Pipeline — carta
────────────────────────────────────────────────

  [1/4] Strategic Planner .................. 32.1s (5 briefs)
  [2/4] Content Workers .................... 142.5s (5/5 briefs)
  [3/4] Evaluator Loop ..................... 89.4s (4/5 passed)
  [4/4] Human Review ....................... 0.0s (auto-approved)

────────────────────────────────────────────────
  Done — 264.0s total | 5 approved, 0 rejected
────────────────────────────────────────────────
```

---

## 13. Database Schema — Supabase Migrations

### Migration History (4 files)

#### Migration 1: `20250206120000_initial_schema.sql`
**Scope:** Core schema creation

**Extensions Enabled:**
- `pgcrypto` — UUID generation
- `vector` — pgvector for embedding similarity

**Tables Created (18):**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | Auth identity | References `auth.users` |
| `companies` | Tenant records | name, slug, domain |
| `company_members` | Team membership | company_id, user_id, role |
| `sites` | Company domains | company_id, domain, status |
| `agents` | Agent registry | name, model, tools, config |
| `site_audits` | Audit runs | site_id, status, findings_count |
| `artifacts` | Living documents | company_id, type, content (JSONB), embedding (vector) |
| `knowledge_chunks` | RAG retrieval | artifact_id, chunk_text, embedding (vector) |
| `workflows` | End-to-end pipeline runs | company_id, type, status, config |
| `agent_runs` | Execution traces | workflow_id, agent_id, input, output |
| `workflow_steps` | Ordered steps | workflow_id, step_number, name |
| `content_assets` | Briefs, drafts, etc. | company_id, type, status |
| `content_versions` | Version history | asset_id, version_no, body |
| `agent_metrics` | KPI per agent run | agent_run_id, metric, value |
| `sandbox_results` | Virtual eval outputs | agent_run_id, result |
| `cms_jobs` | Publishing queue | asset_id, status, scheduled_at |
| `llm_usage_log` | Billing/governance | model, tokens, cost |
| `audit_findings` | Issues from audits | audit_id, type, severity |
| `task_queue` | Relational job queue | type, status, payload |

**Indexes:**
- IVFFlat vector indexes on `artifacts.embedding` and `knowledge_chunks.embedding` (lists=100)
- Standard btree on foreign keys and status columns

#### Migration 2: `20251209105957_remote_schema.sql`
**Status:** Empty placeholder (1 line)

#### Migration 3: `20251227120000_artifact_versions.sql`
**Scope:** Artifact versioning support

- Creates `artifact_versions` table (immutable version snapshots)
- Unique constraint: `(artifact_id, version_no)`
- Helper function: `is_company_member(target_company uuid)` for tenant access checks
- RLS policy: `artifact_versions_all` scoped to parent artifact's company_id

#### Migration 4: `20260207120000_rls_enums_hnsw.sql` (511 lines)
**Scope:** Production-readiness upgrade

**1. Vector Index Upgrade:**
- IVFFlat → HNSW (m=16, ef_construction=64) — Better query performance for production

**2. Strongly-Typed Enums (13 new):**
`user_role`, `user_status`, `member_role`, `member_status`, `site_status`, `audit_status`, `artifact_status`, `workflow_status`, `agent_run_status`, `content_status`, `cms_job_status`, `task_status`, `audit_finding_status`

**3. Column Type Migrations:**
All text status/role columns converted to enum types with safe data validation.

**4. Partial Indexes:**
- Active agent runs: `CREATE INDEX ... WHERE status IN ('pending', 'running')`
- Ready task queue: `CREATE INDEX ... WHERE status = 'ready'`

**5. Row Level Security (20 policies):**
All access scoped through `is_company_member()` — tenant isolation across all tables.

---

## 14. Existing Artifacts — Current State of Outputs

### Ramp (Corporate Spend Management)

| Artifact | Status | Key Details |
|----------|--------|-------------|
| Company Context | ✅ Final (`ramp.md`) | Founded 2019, $32B valuation, 12 product areas, 5+ competitors analyzed |
| ICP Persona | ✅ Final (`ramp__persona-icp.md`) | "Controller Catherine" — Director of Finance/Controller at mid-market tech (200-1,000 employees), 43 sources cited |
| Style Guide | ⏳ Draft (`ramp.draft.md`) | Awaiting human approval |
| Gap Analysis | ✅ Complete | 144 queries, 2,234 citations, 9 clusters analyzed |
| Gap Report | ✅ Generated | SPA: -0.715, avg gap: -0.0046, 5 content recommendations |
| Generation Spec | ✅ Generated | Per-cluster content specs ready for Pipeline 3 |

**Top 5 Content Gaps Identified for Ramp:**
1. "What is procurement intake-to-pay?" (gap: 0.1443)
2. "What is automated GL coding?" (gap: 0.1346)
3. "Best virtual card providers for SaaS renewals" (gap: 0.1311)
4. "Brex alternatives for mid-market spend management" (gap: 0.1241)
5. "What is purchase approval workflow?" (gap: 0.1212)

### Carta (Equity Management Platform)

| Artifact | Status | Key Details |
|----------|--------|-------------|
| Company Context | ✅ Final (`carta.md`) | Founded 2012, $7.4B→$3.5B valuation, 2024 trust crisis documented |
| ICP Persona | ⏳ Draft (`carta__persona-icp.draft.md`) | Awaiting approval |
| Style Guide | ⏳ Draft (`carta.draft.md`) | Awaiting approval |
| Gap Analysis | ✅ Complete | Full pipeline completed with visualizations |

### Mynd

| Artifact | Status |
|----------|--------|
| Company Context | ✅ Final (`mynd.md`) |
| Other stages | Not yet run |

---

## 15. Testing — Current State & Gaps

### Current State

```
tests/
├── conftest.py                           # Shared fixtures (FakeChromaCollection, mock clients)
├── shared_tools/
│   ├── test_async_embedding_client.py    # Async embedding client tests
│   └── test_async_chroma_client.py       # Async ChromaDB client tests
├── gap_analysis/
│   └── steps/
│       ├── test_s1_embed_assets.py       # Site discovery + embedding tests
│       ├── test_s2_generate_queries.py   # Query generation tests
│       ├── test_s4_enrich_citations.py   # Citation enrichment tests (11 tests — ALL PASSING)
│       ├── test_s4_main_content.py       # Main content extraction tests (5 tests)
│       ├── test_s4_structural_signals.py # Expanded structural signals tests (16 tests)
│       ├── test_s5_embed_content.py      # Content embedding tests
│       ├── test_s6_analyze.py            # GapContentBrief + ClusterContentSpec tests (8 tests)
│       └── test_s8_generate_report.py    # Report generation tests (11 tests incl. Phase 3)
├── gap_analysis/
│   └── test_pipeline.py                  # Gap analysis pipeline orchestrator tests
├── research/                             # Empty
└── content_engine/                       # 57 tests — ALL PASSING
    ├── __init__.py
    ├── conftest.py                       # Shared fixtures (sample_brief, mock_anthropic, etc.)
    ├── test_models.py                    # 28 tests — Pydantic model validation
    ├── test_planner.py                   # 2 tests — Strategic planner
    ├── test_outliner.py                  # 1 test — Outline generation
    ├── test_drafter.py                   # 1 test — Draft generation
    ├── test_fact_enricher.py             # 2 tests — Fact enrichment + skip
    ├── test_formatter.py                 # 6 tests — Structural counting + format
    ├── test_dispatcher.py                # 2 tests — Parallel dispatch + failure handling
    ├── test_structural.py                # 8 tests — All structural checks
    ├── test_evaluator.py                 # 2 tests — Full eval loop + revision
    ├── test_graph.py                     # 3 tests — LangGraph HITL
    └── test_integration.py              # 2 tests — Full pipeline + skip stages
```

**Test counts:** 351 total tests. All 351 passing (0 failures). S4 mock regression fixed in Phase -1 of structural signal overhaul.

### API Test Coverage (126/126 passing — added 2026-02-16)

| Test File | What's Tested |
|-----------|---------------|
| `test_health.py` | Health + readiness endpoints, missing API key detection |
| `test_gap_analysis.py` | Start pipeline, status polling, skip_steps |
| `test_research.py` | Start pipeline, HITL approval flow (approve/revise/reject) |
| `test_content.py` | Start pipeline, HITL per-brief approval |
| `test_events.py` | SSE streaming, Last-Event-ID reconnection, terminal events |
| `test_artifacts.py` | Company listing, artifact retrieval by type/slug |
| `test_tasks.py` | Task CRUD, filtering by pipeline/status, cancellation |
| `test_store.py` | TaskStore persistence, slug locks, approval events, startup recovery |
| `test_event_bus.py` | Pub/sub, history replay, subscriber lifecycle |
| `test_runner.py` | Background task wrappers, graph interrupt/resume loop |

### Content Engine Test Coverage (57/57 passing)

| Test File | Count | What's Tested |
|-----------|-------|---------------|
| `test_models.py` | 28 | All 15 Pydantic models — defaults, validation, serialization |
| `test_planner.py` | 2 | Plan content with mocked Anthropic, JSON parsing |
| `test_outliner.py` | 1 | Outline generation with mocked Anthropic |
| `test_drafter.py` | 1 | Draft generation with mocked Anthropic |
| `test_fact_enricher.py` | 2 | Enrichment with mocked Perplexity + skip when no API key |
| `test_formatter.py` | 6 | `_count_structural_elements()` for headers/lists/stats/citations + format |
| `test_dispatcher.py` | 2 | Single brief dispatch + `return_exceptions=True` failure handling |
| `test_structural.py` | 8 | All 8 structural checks individually |
| `test_evaluator.py` | 2 | All-pass scenario + revision-triggered scenario |
| `test_graph.py` | 3 | Graph compilation, auto-approve, `run_content_review()` |
| `test_integration.py` | 2 | Full pipeline (auto-approve) + skip stages |

### Remaining Test Gaps

#### Research Pipeline Tests
- [ ] Company research agent invocation (mock Perplexity + Gemini)
- [ ] Persona research agent invocation (mock APIs, verify 1-3 persona creation)
- [ ] Style guide research agent invocation (mock APIs)
- [ ] Full 3-stage pipeline orchestration (company → persona → style)
- [ ] Approval flow: approve / revise / reject paths (all 3 branches)

#### Gap Analysis Tests (partial coverage)
- [ ] Steps s3, s6, s7 tests
- [ ] Step-to-step data flow validation
- [ ] Platform subset selection
- [ ] Fix 4 known s4 test failures

#### Reddit HIL Tests
- [ ] PRAW read-only enforcement
- [ ] Thread ranking and filtering
- [ ] Webhook delivery (mock Slack/Discord)

#### Content Engine Tests (covered, potential additions)
- [ ] Semantic evaluator with real embeddings
- [ ] Style judge prompt quality
- [ ] Factual judge prompt quality
- [ ] Multi-brief concurrent dispatch stress test
- [ ] LangGraph edit flow (non-auto-approve path)

---

## 16. Dependency Graph

### Python Package Dependencies

```
fastapi v0.115+
├── REST API framework (api/app.py)
├── Dependency injection (api/dependencies.py)
├── StreamingResponse (SSE events)
└── Lifespan context manager (shared state)

uvicorn v0.32+
└── ASGI server for FastAPI (scripts/run_server.py)

python-multipart v0.0.12+
└── Form data parsing (FastAPI dependency)

pydantic v2.5+
├── BaseModel (all 30+ schemas)
├── Field validators
├── HttpUrl type
└── model_copy() for cross-stage wiring

pydantic-settings v2.0+
├── BaseSettings (core/config/settings.py)
└── BaseSettings (api/config.py — API_* prefix)

langgraph v0.2+
├── StateGraph (all research graphs)
├── START, END nodes
├── interrupt() for human-in-the-loop
└── Conditional edges (approve/revise/reject routing)

deepagents
├── create_deep_agent() (agent factory)
├── CompositeBackend (path routing)
├── FilesystemBackend (artifact storage)
├── StoreBackend (agent memory)
├── StateBackend (per-thread scratchpad)
└── InMemoryStore (memory persistence)

LLM Providers:
├── langchain-google-genai → Google Gemini (agents)
├── anthropic SDK → Claude (gap analysis search + style guide)
├── openai SDK → GPT (embeddings, queries, reports)
└── perplexityai SDK → sonar-deep-research (web research)

Data Processing:
├── chromadb v0.5+ → Persistent vector storage (local)
├── numpy, scipy, scikit-learn → Statistics + cosine similarity + TF-IDF themes
├── umap-learn → UMAP dimensionality reduction
├── plotly → Interactive HTML visualizations
├── beautifulsoup4 → HTML structural element extraction
├── trafilatura v1.6+ → Main content extraction (3-tier fallback in S4)
├── textstat v0.7+ → Flesch-Kincaid reading level computation (S4)
└── playwright → Headless browser crawling

Web & HTTP:
├── httpx → Async HTTP client (crawling, citation fetching)
├── requests → Sync HTTP (fallback)
└── python-dotenv → .env file loading

Integrations:
└── praw v7.7+ → Reddit API (read-only)
```

### Internal Dependency Flow

```
core/config/settings.py ← Used by everything
        ↓
core/models/* ← Used by graphs, agents, pipeline, mirror, API schemas
        ↓
core/shared_tools/* ← Used by gap analysis steps + content engine
        ↓
core/storage/* ← Used by research graphs (mirror after approval)
        ↓
core/research/agents/* ← Used by research graphs
        ↓
core/research/graphs/* ← Used by scripts + API runners
core/gap_analysis/* ← Used by scripts + API runners
core/content_engine/* ← Used by scripts + API runners
core/reddit_hil/* ← Used by CLI
        ↓
api/tasks/runner.py ← Wraps core pipelines as background tasks
api/tasks/store.py ← JSON-backed task persistence
api/tasks/event_bus.py ← SSE pub/sub
api/routers/* ← REST endpoints
api/app.py ← FastAPI app factory
        ↓
scripts/* ← CLI entry points
scripts/run_server.py ← API entry point (uvicorn)
```

---

## 17. Architectural Decisions & Rationale

### Decision 1: Filesystem-First Storage

**Choice:** Artifacts are written to the local filesystem as the canonical source of truth. Database mirroring is optional.

**Rationale:**
- Artifacts are Markdown files — naturally file-based
- Enables git versioning of artifacts (though not currently gitignored)
- No database dependency for core operation
- Developers can directly inspect and edit artifacts
- Database becomes an API-layer convenience, not a hard dependency

**Tradeoff:** No multi-user concurrent access to artifacts. Suitable for single-developer or CI/CD usage, but needs API layer for team collaboration.

### Decision 2: LangGraph with `interrupt()` for Human-in-the-Loop

**Choice:** Use LangGraph's `interrupt()` mechanism to pause graph execution and wait for human review.

**Rationale:**
- Clean separation between automated processing and human review
- Graph state persists across interrupts
- Supports both human review (default) and auto-approve (for CI/CD)
- Enables revise loops without losing context

**Tradeoff:** CLI-based approval flow is manual (`graph.invoke()` → inspect draft → resume with decision). Will be smoother with a frontend.

### Decision 3: Separate Google API Keys Per Agent

**Choice:** Each research agent has its own Google API key (`GOOGLE_API_KEY_COMPANY_DEEPAGENT`, `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT`, etc.)

**Rationale:**
- Enables per-agent rate limit tracking
- Allows different billing projects per agent
- Prevents one agent's usage from blocking another
- Supports different API quota allocations

**Tradeoff:** More environment variables to manage. Could be simplified with a single key if rate limits aren't a concern.

### Decision 4: ThreadPoolExecutor for Agent Invocation

**Choice:** All `agent.invoke()` calls are wrapped in `concurrent.futures.ThreadPoolExecutor(max_workers=1)`.

**Rationale:**
- DeepAgents' `StoreBackend` has a known runtime error when accessed from the main thread alongside async operations
- Thread isolation prevents this by running the agent in a dedicated thread
- `max_workers=1` ensures sequential execution within the thread pool

**Tradeoff:** Added complexity. Cannot use `asyncio` directly with agent invocations. Timeout handling requires careful management.

### Decision 5: ChromaDB for Local Vector Storage

**Choice:** Use ChromaDB (persistent, local) for embedding storage during gap analysis.

**Rationale:**
- No external database dependency for development
- Persistent across process restarts
- Fast cosine similarity queries
- Simple API (upsert, query, delete)

**Tradeoff:** Not suitable for multi-tenant production. Should migrate to pgvector (Supabase) for production deployment.

### Decision 6: 4-Engine Search Strategy

**Choice:** Query all four AI search platforms (Perplexity, OpenAI, Gemini, Claude) for gap analysis.

**Rationale:**
- Each platform has different citation biases and source preferences
- Broader citation coverage reduces blind spots
- Enables cross-platform citation pattern analysis
- Identifies which platforms cite the company vs. competitors

**Tradeoff:** 4x API costs. Slower execution (even with concurrency). Platform APIs can change without notice. The `--platforms` flag allows subsetting.

### Decision 7: Query Taxonomy with Brand Name Rules

**Choice:** 9-cluster query taxonomy with explicit rules about when brand names can/cannot appear.

**Rationale:**
- Category-level queries (C1, C3-C7, C9) test whether the company appears when users DON'T search for it by name
- Branded queries (C8) test competitive positioning
- Brand-aware queries (C2) test whether known limitations surface correctly

**Tradeoff:** Fixed taxonomy may not cover all industries equally well. The `b2b_queries_180.json` taxonomy is currently hardcoded.

### Decision 8: Supabase for Multi-Tenant Backend

**Choice:** Supabase (PostgreSQL + PostgREST + pgvector) with Row Level Security for the eventual API layer.

**Rationale:**
- Built-in auth, RLS, real-time subscriptions
- pgvector for production embedding queries
- PostgREST provides instant REST API
- RLS policies enable secure multi-tenant isolation
- Managed service reduces ops burden

**Tradeoff:** Vendor lock-in to Supabase. RLS policies add query overhead. Self-hosted option available but adds ops complexity.

### Decision 9: Orchestrator-Workers + Evaluator-Optimizer for Content Engine

**Choice:** Two-pattern architecture: Orchestrator-Workers for parallel content production (semaphore-controlled), Evaluator-Optimizer for automated QA with 4 evaluation dimensions.

**Rationale:**
- Orchestrator-Workers enables parallel brief processing with controlled concurrency
- Evaluator-Optimizer provides automated quality gate without manual review
- 4 dimensions (structural, semantic, style, factual) cover all quality aspects
- Max 2 revision cycles balance quality vs. cost
- `asyncio.gather(return_exceptions=True)` ensures one failing brief doesn't cancel the batch

**Tradeoff:** Multiple LLM calls per brief (~$0.50-1.00 per brief). Revision cycles add latency. LLM judges may have inconsistent scoring.

### Decision 10: Raw AsyncAnthropic SDK for Content Engine (No LangChain)

**Choice:** Use `AsyncAnthropic` SDK directly for all content engine LLM calls. No LangChain wrappers.

**Rationale:**
- Consistent with gap analysis pattern (raw SDK clients)
- Fine-grained control over structured JSON output parsing
- Direct access to usage metrics for cost tracking
- Simpler debugging (no wrapper abstraction layers)
- Custom retry logic with `_retry_async_anthropic()` handles provider-specific errors

**Tradeoff:** More boilerplate per LLM call. No LangChain ecosystem integrations. Must handle JSON parsing and retry logic manually.

### Decision 11: Langfuse for Observability (Not LangSmith)

**Choice:** Langfuse for tracing and observability of content generation pipeline.

**Rationale:**
- Open-source with self-hosting option
- Session → Trace → Span → Generation hierarchy fits pipeline stages
- Score tracking for eval dimensions
- Cost tracking per generation
- Graceful no-op when not configured (no hard dependency)

**Tradeoff:** Separate from LangGraph ecosystem (which integrates with LangSmith). Requires additional API keys.

**Update (2026-02-16):** Migrated from Langfuse v2 API to v3 API (breaking change). Key difference: v3 removed `lf.trace()` entirely — now uses `lf.start_span()` + `span.update_trace(session_id=...)` to establish the trace. See §7.5 for full migration details.

### Decision 12: FastAPI Integration Architecture (D-API-1)

**Choice:** Same-repo `api/` package. `asyncio.create_task()` for background pipeline execution. JSON-file-backed `TaskStore`. Server-Sent Events (SSE) for real-time progress. `MemorySaver` checkpointer for LangGraph HITL interrupt/resume.

**Rationale:**
- **`asyncio.create_task` (not Celery):** Lightweight, no infra deps. Matches existing async-first patterns. All pipeline code is already async — no serialization boundary needed.
- **JSON-file TaskStore (not SQLite/Redis):** Simple, debuggable, human-readable. Atomic writes via temp-file + `os.replace()`. Sufficient for current scale (single-server, <10 concurrent pipelines).
- **SSE (not WebSocket):** Simpler protocol, auto-reconnect via `Last-Event-ID` header. One-directional (server→client) is sufficient — client actions use REST endpoints. No connection state management needed.
- **MemorySaver checkpointer:** Enables LangGraph graph state persistence across interrupt/resume cycles. Required for HITL approval flow where graph pauses and resumes after human decision.
- **Per-slug locks:** Prevents concurrent pipeline runs for the same company (race condition on shared artifacts).
- **Global semaphore:** Caps total concurrent pipelines (default: 3) to prevent resource exhaustion.

**Alternatives Rejected:**
- Celery + Redis — Over-engineering for current scale. Adds infrastructure dependency and serialization complexity.
- WebSocket for progress — SSE is simpler, auto-reconnects. WebSocket needed only for bidirectional communication.
- SQLite TaskStore — Unnecessary complexity. JSON files are sufficient and more debuggable.

**Outcome:** 6 phases complete. 126 tests passing. All 3 pipelines wrapped with REST endpoints, SSE events, and HITL approval flow.

**Approved by:** Aryan

---

## 18. Known Vulnerabilities, Flaws & Technical Debt

### Critical Issues

#### 1. PARTIAL TEST COVERAGE (Improved Significantly)
**Severity:** Medium (downgraded from Critical — 2026-02-15, improved 2026-02-16, updated 2026-02-19)
**Description:** 351 total tests, all passing. API layer: 126+ passing. Content engine: 57/57 passing. Gap analysis: comprehensive coverage (s1, s2, s4, s5, s6, s8, pipeline). Research pipeline and Reddit HIL have zero tests. S4 test failures fixed (2026-02-18).
**Impact:** API layer, content engine, and gap analysis have full regression protection. Research pipeline and Reddit HIL remain unprotected.
**Recommendation:** Add tests for research pipeline (approval flows) and Reddit HIL (webhook delivery).

#### 2. InMemoryStore — Agent Memory Not Persistent
**Severity:** High
**Description:** The `InMemoryStore` used for agent memories is lost between process restarts. Agent learning and context from previous runs is discarded.
**Location:** `core/research/agents/base.py` (lines 74-79)
**Impact:** Agents start fresh every run. No memory of previous research, revisions, or approved artifacts.
**Recommendation:** Evaluate persistent store options: Redis, PostgreSQL (via Supabase), or custom SQLAlchemy store.

#### 3. Hardcoded Query Taxonomy Path
**Severity:** Medium
**Description:** The query taxonomy file path is hardcoded to `Deep_Presence/research/Citation_Signal_Predictor/cps_model/b2b_queries_180.json` — a path **outside** the content-strategy-engine directory.
**Location:** `core/gap_analysis/steps/s2_generate_queries.py`
**Impact:** Will fail if the external repository structure changes. Not portable.
**Recommendation:** Bundle the taxonomy file within `content-strategy-engine/core/gap_analysis/` or load from config.

#### 4. No Error Handling in CLI Scripts
**Severity:** Medium
**Description:** Most CLI scripts (company research, gap analysis) have no try/except blocks around graph invocation or function calls. Failures produce raw Python tracebacks.
**Location:** All files in `scripts/`
**Impact:** Poor developer experience. No graceful error messages or recovery suggestions.
**Recommendation:** Add try/except with user-friendly error messages and exit codes.

### Moderate Issues

#### 5. Embedding Dimension Hardcoded
**Severity:** Medium
**Description:** Zero-vector fallback uses hardcoded 1536 dimensions (for text-embedding-3-small). If the embedding model changes, this silently produces wrong-dimension vectors.
**Location:** `core/gap_analysis/steps/s5_embed_content.py` (lines 176, 193)
**Recommendation:** Derive dimension from model configuration or first successful embedding.

#### 6. OpenAI Experimental API Usage
**Severity:** Medium
**Description:** Uses `client.responses.create()` which is an experimental OpenAI API (responses API for o1/o3 models). No fallback if API changes.
**Location:** `core/gap_analysis/engines/openai_engine.py`
**Impact:** Could break without warning if OpenAI deprecates or changes the responses API.
**Recommendation:** Add fallback to standard `chat.completions.create()` endpoint.

#### 7. No Structured Logging
**Severity:** Medium
**Description:** CLAUDE.md mandates "structured JSON logging with correlation IDs" but this is not fully implemented. Each graph file has its own `_log_event()` function. No central logging config.
**Location:** `core/config/logging_config.py` — File does not exist.
**Impact:** No unified log format, no correlation IDs for tracing across pipeline stages, difficult to debug production issues.
**Recommendation:** Implement `core/config/logging_config.py` with structured JSON logging, correlation IDs, and centralized configuration.

#### 8. Duplicated Helper Functions
**Severity:** Low
**Description:** `_overwrite_virtual_path()` is duplicated across `company_research.py` and `persona_research.py`. Multiple `_log_event()` implementations across graph files.
**Location:** `core/research/graphs/`
**Impact:** Maintenance burden. Changes must be replicated across files.
**Recommendation:** Extract to shared utility in `core/research/graphs/__init__.py` or a `utils.py` module.

#### 9. StorageBackend Interface Without Implementations
**Severity:** Low (current), High (for production)
**Description:** `core/storage/backends/base.py` defines a clean `StorageBackend` ABC but no concrete implementations (LocalFilesystemBackend, S3Backend, etc.) exist.
**Impact:** Cannot swap storage backends as designed. Currently using DeepAgents' own `FilesystemBackend` directly.
**Recommendation:** Implement `LocalFilesystemBackend` as the default, then cloud backends when needed.

#### 10. Agent Invocation Pattern Inconsistency
**Severity:** Low
**Description:** Company agent uses ThreadPoolExecutor in the graph node (`company_research.py` line 149), while persona/style agents use ThreadPoolExecutor inside the agent function files themselves. Both work but follow different patterns.
**Impact:** Mental overhead when reading code. Inconsistent error handling.
**Recommendation:** Standardize to one pattern (preferably in the agent files, matching persona/style approach).

#### 11. Langfuse v2 API Incompatibility — RESOLVED (2026-02-16)
**Severity:** ~~High~~ Resolved
**Description:** `tracing.py` was written for Langfuse v2 API (`lf.trace()`, `target.generation()`, `target.span()`) but Langfuse 3.14.1 was installed. v3 removed these methods entirely, causing all tracing to silently fail with `'Langfuse' object has no attribute 'trace'`.
**Fix Applied:** Rewrote `tracing.py` to use v3 SDK API. See §7.5 for migration details.
**Location:** `core/content_engine/tracing.py`

#### 12. TaskStore JSON Persistence — Single-Server Limitation
**Severity:** Low (current), Medium (for production)
**Description:** `TaskStore` uses JSON files in `artifacts/_jobs/` for task persistence. Works fine for single-server deployment but does not support multi-server or horizontal scaling.
**Location:** `api/tasks/store.py`
**Impact:** Cannot scale API to multiple servers without shared state.
**Recommendation:** Migrate to Redis or PostgreSQL-backed task store when horizontal scaling is needed.

#### 13. `model_dump(mode='json')` in TaskStore
**Severity:** Low
**Description:** TaskStore persistence uses `model_dump(mode='json')` for Pydantic v2 serialization. Works correctly in current Pydantic v2 but should be verified with future Pydantic upgrades.
**Location:** `api/tasks/store.py`

### Data Quality & Operational Concerns

#### 14. Vertex AI Redirect URLs
**Description:** The Gemini search engine sometimes returns Vertex AI Search redirect URLs (`vertexaisearch.cloud.google.com/...`) instead of direct URLs. A utility script exists to resolve these, but it's a manual post-processing step.
**Location:** `scripts/resolve_vertexai_redirects.py`
**Impact:** Enriched citations may contain unresolvable URLs until manually fixed.
**Recommendation:** Integrate redirect resolution into Step 4 (enrich citations) automatically.

#### 15. PDF Detection Fragility
**Description:** PDF detection in Step 4 uses basic string matching (`"%PDF-"` signature). Could miss some PDFs or false-positive on text containing the PDF signature.
**Location:** `core/gap_analysis/steps/s4_enrich_citations.py`
**Impact:** Some binary content may slip through to embedding, producing garbage vectors.
**Recommendation:** Use Content-Type headers and more robust binary detection.

#### 16. ChromaDB Not Production-Ready for Multi-Tenant
**Description:** ChromaDB runs locally with file-based persistence. Not suitable for multi-user production deployment.
**Impact:** Single-machine limitation. No concurrent access from multiple processes.
**Recommendation:** Migrate to pgvector (Supabase) for production. ChromaDB remains appropriate for local development.

#### 17. Hardcoded Default Paths in Utility Scripts
**Description:** `resolve_vertexai_redirects.py` defaults input to Ramp's enriched citations path. `strip_embeddings_from_json.py` defaults to Ramp's embeddings path.
**Impact:** Confusing defaults if used with other companies.
**Recommendation:** Remove defaults or make them configurable via settings.

---

## 19. Security Considerations

### API Key Management
- All API keys loaded from `.env.local` (gitignored)
- No keys in code or committed files
- Separate keys per agent prevents cross-agent key exposure
- Supabase uses service role key (admin) for mirroring — should be restricted in production

### Reddit Client Safety
- PRAW client explicitly enforces `read_only == True` with assertion
- No write operations possible even if credentials support it
- Prevents accidental posting

### Supabase Row Level Security
- 20 RLS policies enforce tenant isolation via `is_company_member()` function
- All data access scoped to the user's company membership
- Service role key bypasses RLS (used by agent mirroring) — acceptable for server-side operations

### Potential Risks
1. **No input sanitization on CLI arguments** — Company names, slugs, and paths are used directly in file operations and API calls. While these come from trusted CLI input (not external users), a malicious input could traverse directories.
2. **Webhook URLs in environment** — Slack/Discord webhook URLs are secrets. If leaked, anyone can post to those channels.
3. **Large artifact content** — No size limits on artifact content beyond the 400KB cap in Reddit HIL. A malicious or very large website could produce enormous artifacts.
4. **No rate limiting on API calls** — The gap analysis pipeline makes hundreds of API calls. No retry with exponential backoff or circuit breaker pattern.

---

## 20. Scope & Roadmap

### What's Built (Current Scope)

| Component | Status | Maturity |
|-----------|--------|----------|
| Company Research Agent | ✅ Production | High — used for Ramp, Carta, Mynd |
| Persona Research Agent | ✅ Production | High — ICP personas approved for Ramp, Carta |
| Style Guide Research Agent | ✅ Functional | Medium — bugs fixed, awaiting approvals |
| Research Pipeline Orchestrator | ✅ Functional | High — cross-stage wiring works |
| Gap Analysis (8 steps) | ✅ Production | High — complete for Ramp, Carta |
| Content Generation Engine | ✅ Implemented | Medium — 57 tests passing, awaiting live smoke test |
| **FastAPI REST API** | ✅ Implemented | **High — 126 tests, SSE, HITL, all 3 pipelines** |
| Reddit HIL Monitor | ✅ Functional | Medium — tested with Ramp |
| Supabase Schema | ✅ Production | High — 4 migrations, RLS, HNSW |
| Supabase Mirror | ✅ Functional | Medium — works but no SQLAlchemy ORM |
| CLI Scripts | ✅ Functional | Medium — works but no error handling |
| Langfuse Tracing (v3) | ✅ Functional | Medium — content engine traced, v3 API |

### What's Planned (Future Scope)

| Priority | Component | Description | Dependencies |
|----------|-----------|-------------|--------------|
| 1 | **Content Engine v1.1** | HITL timeout, --offline flag, cost budget cap | Content Engine v1.0 |
| 2 | ~~**FastAPI Backend**~~ | ~~REST API + SSE pipeline events~~ | ✅ **Completed 2026-02-16** |
| 3 | **Frontend** | Web UI for artifact review, gap visualization, pipeline management | FastAPI backend (done) |
| 4 | **SQLAlchemy ORM** | Replace raw Supabase client with ORM | Supabase schema |
| 5 | **Comprehensive Tests** | Research pipeline + Reddit HIL tests | Existing codebase |
| 6 | **Persistent Agent Store** | Replace InMemoryStore with durable storage | DeepAgents integration |
| 7 | **Cloud Storage Backends** | S3/GCS/Supabase Storage implementations | StorageBackend interface |
| 8 | **Structured Logging** | JSON logging with correlation IDs | logging_config.py |
| 9 | **CI/CD Pipeline** | Automated tests, linting, deployment | Tests + Docker |
| 10 | **Redis/PG TaskStore** | Replace JSON-file TaskStore for multi-server | FastAPI backend |

---

## 21. REST API Layer (FastAPI)

**Status:** Implemented (2026-02-16). 126/126 tests passing. All 3 pipelines wrapped.

**Architecture Decision:** D-API-1 — `asyncio.create_task()` (not Celery), JSON-file TaskStore, SSE for progress, `MemorySaver` checkpointer for HITL. See §17 Decision 12 for full rationale.

### 21.1 Application Factory & Lifecycle

**File:** `api/app.py`

```python
def create_app() -> FastAPI:
```

**Startup (lifespan context manager):**
1. Initialize `EventBus` (in-memory pub/sub for SSE)
2. Initialize `TaskStore` (JSON-file-backed persistence + semaphore)
3. Scan disk for orphan tasks — marks stale "running" tasks as `FAILED_RESTART`
4. Store shared state in `app.state` (accessed via dependency injection)

**Middleware (applied in order):**
1. `RequestLoggingMiddleware` — logs `METHOD PATH STATUS_CODE DURATION_MS`
2. `CORSMiddleware` — configurable origins (default: `localhost:3000`, `localhost:3001`), credentials enabled

**Exception Handlers:**
| Exception | HTTP Status | Error Code |
|-----------|-------------|------------|
| `TaskNotFoundError` | 404 | `task_not_found` |
| `TaskConflictError` | 409 | `task_conflict` |
| `PipelineError` | 500 | `pipeline_error` |

**Routers (mounted in order):** health, gap_analysis, research, content, events, artifacts, tasks

---

### 21.2 API Endpoints Reference

#### Health & Readiness
```
GET  /health                                    → {"status": "ok"}
GET  /readiness                                 → {"ready": bool, "missing_keys": [...]}
```

#### Gap Analysis Pipeline
```
POST /api/v1/gap-analysis/start                 → 202 Accepted: PipelineRunResponse
GET  /api/v1/gap-analysis/{run_id}/status       → TaskResponse
```

**Request Body (`/gap-analysis/start`):**
```json
{
  "input_data": {
    "company_name": "Ramp",
    "domain": "ramp.com",
    "seed_urls": ["https://ramp.com"],
    "company_slug": "ramp"
  },
  "skip_steps": [1, 2]
}
```

#### Research Pipeline
```
POST /api/v1/research/start                     → 202 Accepted: PipelineRunResponse
GET  /api/v1/research/{run_id}/status           → TaskResponse
POST /api/v1/research/{run_id}/approve          → ApprovalResponse
```

**Request Body (`/research/start`):**
```json
{
  "company": { "company_name": "Ramp", "seed_urls": ["https://ramp.com"], "domain": "ramp.com" },
  "persona": { "company_name": "Ramp", "domain": "ramp.com" },
  "style_guide": { "company_name": "Ramp", "domain": "ramp.com" },
  "auto_approve": false
}
```

**Approval Request (`/research/{run_id}/approve`):**
```json
{ "decision": "approve|revise|reject", "revision_note": "optional feedback" }
```

#### Content Generation Pipeline
```
POST /api/v1/content/start                      → 202 Accepted: PipelineRunResponse
GET  /api/v1/content/{run_id}/status            → TaskResponse
POST /api/v1/content/{run_id}/approve           → ContentApprovalResponse
```

**Content Start Request (typed flat fields):**
```json
{ "company_name": "Ramp", "domain": "ramp.com", "max_briefs": 5, "auto_approve": false }
```
- `company_name` (required): Company display name
- `domain` (required): Company domain
- `max_briefs` (optional, default 5, 1-20): Maximum briefs to generate
- `auto_approve` (optional, default false): Skip HITL review when true — wired through to content engine's `run_content_review()`

**Content Approval (per brief):**
```json
{ "brief_id": "brief-1", "decision": "approve|edit|reject", "editor_notes": "optional" }
```
- `brief_id` is validated against the current `approval_payload.brief_id` — returns 409 on mismatch

#### SSE Event Streaming
```
GET  /api/v1/tasks/{task_id}/events             → text/event-stream (SSE)
     Headers: Last-Event-ID (for reconnection replay)
```

**SSE Event Format:**
```
id: 1
event: pipeline_start
data: {"pipeline": "gap_analysis"}

id: 2
event: stage_start
data: {"stage": "company"}

id: 3
event: pending_approval
data: {"stage": "company", "draft_path": "..."}

id: 4
event: completed
data: {"pipeline": "gap_analysis"}
```

**Event Types:**

| Event | When | Data |
|-------|------|------|
| `pipeline_start` | Pipeline begins | `{pipeline}` |
| `stage_start` | Research stage begins | `{stage}` |
| `stage_complete` | Research stage completes | `{stage}` |
| `pending_approval` | Graph interrupts for HITL | `{stage, ...interrupt_payload}` |
| `approval_received` | Human submits decision | `{stage, decision}` |
| `completed` | Pipeline succeeds | `{pipeline}` |
| `failed` | Pipeline fails | `{error}` |
| `cancelled` | Task cancelled by user | `{}` |

#### Task Management
```
GET  /api/v1/tasks                              → TaskListResponse (?pipeline=&status=)
GET  /api/v1/tasks/{task_id}                    → TaskResponse
POST /api/v1/tasks/{task_id}/cancel             → CancelResponse
```
- **Cancel** now performs real cancellation: calls `asyncio.Task.cancel()` on the background task handle, publishes SSE `cancelled` event, and sets task status to `cancelled`. Runners catch `asyncio.CancelledError` for clean shutdown.

#### Artifact Retrieval
```
GET  /api/v1/artifacts/companies                → {"companies": ["ramp", "carta"]}
GET  /api/v1/artifacts/{type}/{slug}            → {"artifact_type", "slug", "files": [...]}
GET  /api/v1/artifacts/{type}/{slug}/{filename} → File content (JSON/HTML/MD)
```
**Artifact types:** `company_context`, `personas`, `style_guides`, `gap_analysis`, `content`

**Slug validation:** Slugs must match `^[a-z0-9][a-z0-9-]*$` (lowercase alphanumeric + hyphens, starting with alphanumeric). Invalid slugs return 400. Additionally, resolved paths are checked for containment within the artifacts root to prevent path traversal.

---

### 21.3 TaskStore — JSON-Backed Persistence

**File:** `api/tasks/store.py`

**Architecture:**
- **In-Memory Dict:** O(1) lookup for active tasks
- **JSON Files:** Atomic persistence via temp-file + `os.replace()` to `artifacts/_jobs/{task_id}.json`
- **Slug Locks:** Per-company mutexes prevent concurrent pipeline runs for the same company
- **Global Semaphore:** Caps concurrent pipelines (default: 3, via `API_MAX_CONCURRENT_PIPELINES`)
- **Approval Queues:** `asyncio.Queue(maxsize=1)`-based blocking/unblocking for HITL — prevents lost-wakeup race condition (previously used `asyncio.Event` which could miss signals if `set()` was called before `wait()`)
- **Task Handle Tracking:** `Dict[str, asyncio.Task]` stores background task handles, enabling real cancellation via `asyncio.Task.cancel()`

**Task Lifecycle:**
```
create_task() → acquire slug lock → RUNNING
    ↓
register_task_handle() → store asyncio.Task for cancellation support
    ↓
update_task() → RUNNING (progress updates)
    ↓ (if graph interrupts)
update_task() → PENDING_APPROVAL (blocked on wait_for_approval())
    ↓ (human calls /approve)
submit_approval() → Queue.put_nowait() unblocks wait_for_approval()
    ↓
update_task() → RUNNING → ... → COMPLETED | FAILED
    ↓ (or user calls /cancel)
cancel_task_handle() → asyncio.Task.cancel() + CancelledError caught in runner
    ↓
release_slug_lock() + remove_task_handle()
```

**Startup Recovery:** On server restart, `_recover_from_disk()` loads all JSON files. Tasks with status `RUNNING` or `PENDING_APPROVAL` are marked `FAILED_RESTART` (orphan recovery).

**Key Model:**
```python
class PipelineTask(BaseModel):
    task_id: str
    pipeline: Literal["research", "gap_analysis", "content"]
    status: TaskStatus  # running | pending_approval | completed | failed | cancelled | failed_restart
    company_slug: str
    current_step: Optional[str]
    progress_pct: Optional[float]
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    approval_payload: Optional[Dict[str, Any]]
    approval_history: List[ApprovalRecord]
```

---

### 21.4 EventBus — SSE Streaming

**File:** `api/tasks/event_bus.py`

**Architecture:**
- **Per-Task History:** `collections.deque(maxlen=100)` — bounded event buffer per task
- **Per-Task Subscribers:** `List[asyncio.Queue]` — live subscriber queues
- **Auto-Incrementing IDs:** Per-task counter for `Last-Event-ID` reconnection

**Flow:**
1. Background runner calls `event_bus.publish(task_id, event_type, data)`
2. Event stored in history deque + pushed to all active subscriber queues
3. SSE endpoint (`GET /tasks/{id}/events`) creates subscriber, streams events
4. On reconnect with `Last-Event-ID`: replays history starting after that ID, then switches to live
5. **Heartbeat keepalive:** If no event is published for 15 seconds, the stream yields a SSE comment (`: heartbeat\n\n`) to prevent proxy/browser timeouts

**Terminal Events:** `completed`, `failed`, `cancelled` — SSE stream closes after yielding a terminal event.

---

### 21.5 HITL Approval Flow via API

**Research Pipeline (3-stage approval loop):**

```
Client                          API Server                       LangGraph
  │                                │                                │
  │  POST /research/start          │                                │
  │ ─────────────────────────────▶ │  asyncio.create_task()         │
  │  ◀ 202 {run_id}               │ ──────────────────────────────▶ │
  │                                │                                │ graph.invoke()
  │  GET /tasks/{id}/events (SSE)  │                                │
  │ ─────────────────────────────▶ │                                │
  │  ◀ event: pipeline_start       │                                │ ← GraphInterrupt
  │  ◀ event: stage_start          │  ◀──── interrupt payload ──────│
  │  ◀ event: pending_approval     │                                │
  │                                │  wait_for_approval() BLOCKS    │
  │  (User reviews draft)          │                                │
  │                                │                                │
  │  POST /research/{id}/approve   │                                │
  │    {decision: "approve"}       │                                │
  │ ─────────────────────────────▶ │  submit_approval() UNBLOCKS   │
  │                                │ ──────────────────────────────▶ │ Command(resume={...})
  │  ◀ event: approval_received    │                                │
  │  ◀ event: stage_complete       │  ◀──── result ────────────────│
  │  ...next stage...              │                                │
```

**Content Pipeline (per-brief approval):** Same pattern but the approval endpoint accepts `brief_id` to approve individual content pieces.

**Graph Resume Mechanism:**
```python
# Runner detects GraphInterrupt, extracts interrupt payload (guarded)
interrupt_values = snapshot.tasks[0].interrupts[0].value \
    if snapshot.tasks and snapshot.tasks[0].interrupts else {}

# Publishes pending_approval event, blocks on asyncio.Queue
approval = await task_store.wait_for_approval(task_id)

# Resumes graph with human decision
result = await asyncio.to_thread(
    graph.invoke,
    Command(resume={"approval_decision": decision, "revision_note": note}),
    config
)
```

**Research Pipeline Reject Early-Exit:** When a stage receives a `"reject"` decision, the runner stops pipeline progression. For example, if `company` is rejected, `persona` and `style_guide` stages are skipped. `produced_artifacts` is built from actually completed stages, not requested stages.

**Auto-approve:** When `auto_approve: true` in the start request, the graph skips `interrupt()` calls entirely — no HITL pause. For the content pipeline, `auto_approve` is wired through `pipeline.py` → `graph.py` → `run_content_review(auto_approve=True)`.

---

### 21.6 Design Choices & Rationale

| Choice | Why | Alternative Rejected |
|--------|-----|---------------------|
| `asyncio.create_task()` | No infra deps, matches async codebase | Celery + Redis (over-engineering) |
| JSON-file TaskStore | Simple, debuggable, atomic writes | SQLite (unnecessary complexity) |
| SSE (not WebSocket) | Simpler, auto-reconnect via header | WebSocket (bidirectional not needed) |
| Per-slug locks | Prevent artifact race conditions | No locking (data corruption risk) |
| `MemorySaver` checkpointer | LangGraph interrupt/resume persistence | Custom state persistence (reinventing) |
| Startup orphan recovery | Graceful handling of server crashes | Ignore stale tasks (confusing UX) |
| `asyncio.Queue` for approvals | Prevents lost-wakeup race condition; multiple approvals can queue | `asyncio.Event` (set before wait loses signal) |
| Task handle tracking | Enables real `asyncio.Task.cancel()` on user cancel | Soft-delete only (orphan task keeps running) |
| 15s SSE heartbeat | Prevents proxy/browser timeout on quiet streams | No keepalive (client disconnects silently) |
| Slug regex validation | Prevents path traversal in artifact routes | Trust client input (security risk) |
| `rehype-sanitize` in MarkdownViewer | Prevents XSS from untrusted markdown content | Trust API-served markdown (security risk) |

---

## Appendix A: Model & API Key Matrix

| Component | Model | API Key Variable | Default Model |
|-----------|-------|------------------|---------------|
| Company Research Agent | Gemini | `GOOGLE_API_KEY_COMPANY_DEEPAGENT` | `gemini-3-flash-preview` |
| Persona Research Agent | Gemini | `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT` | `gemini-3-flash-preview` |
| Style Guide Research Agent | Gemini | `GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT` | `gemini-3-flash-preview` |
| DeepAgents (default) | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Perplexity Research | Sonar | `PERPLEXITY_API_KEY` | `sonar-deep-research` |
| Embeddings | OpenAI | `OPENAI_API_KEY` | `text-embedding-3-small` |
| Gap: Query Generation | OpenAI | `OPENAI_API_KEY` | `gpt-5.2-2025-12-11` |
| Gap: Report Generation | OpenAI | `OPENAI_API_KEY` | `gpt-5.2-2025-12-11` |
| Gap: OpenAI Search Engine | OpenAI | `OPENAI_API_KEY` | `gpt-5.2-2025-12-11` |
| Gap: Claude Search Engine | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Gap: Gemini Search Engine | Gemini | `GOOGLE_API_KEY_GAP_ANALYSIS` | `gemini-3-flash-preview` |
| Gap: Perplexity Search Engine | Sonar | `PERPLEXITY_API_KEY` | `sonar-pro` |
| Reddit HIL Monitor | Gemini | `GOOGLE_API_KEY_REDDIT_HIL` | `gemini-3-flash-preview` |
| Content Engine: Planner | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Content Engine: Outliner | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Content Engine: Drafter | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Content Engine: Fact Enricher | Perplexity | `PERPLEXITY_API_KEY` | `sonar-pro` |
| Content Engine: Formatter | Claude | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| Content Engine: Style Judge | Claude | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| Content Engine: Factual Judge | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Content Engine: Semantic Eval | OpenAI | `OPENAI_API_KEY` | `text-embedding-3-small` |
| Content Engine: Tracing | Langfuse | `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | — |

---

## Appendix B: Artifact Naming Conventions

### Slug Derivation
```python
slug = company_name.lower().replace(" ", "-")
# "Ramp" → "ramp"
# "Acme Corp" → "acme-corp"
```

### File Naming Patterns

| Artifact Type | Draft | Final |
|---------------|-------|-------|
| Company Context | `artifacts/company_context/{slug}.draft.md` | `artifacts/company_context/{slug}.md` |
| ICP Persona | `artifacts/personas/{slug}__persona-icp.draft.md` | `artifacts/personas/{slug}__persona-icp.md` |
| Secondary Persona 1 | `artifacts/personas/{slug}__persona-2.draft.md` | `artifacts/personas/{slug}__persona-2.md` |
| Secondary Persona 2 | `artifacts/personas/{slug}__persona-3.draft.md` | `artifacts/personas/{slug}__persona-3.md` |
| Style Guide | `artifacts/style_guides/{slug}.draft.md` | `artifacts/style_guides/{slug}.md` |
| Gap Analysis | `artifacts/gap_analysis/{slug}/` (directory) | All step outputs in subdirectory |
| Content Engine | `artifacts/content/{slug}/` (directory) | briefs.json, run_metadata.json, content/brief-{N}/ |

### Gap Analysis Directory Structure
```
artifacts/gap_analysis/{slug}/
├── analysis.json
├── gap_report.md / .json
├── generation_spec.md / .json
├── queries.json
├── enriched_citations.json
├── company_embeddings.json
├── embeddings/
│   ├── queries_with_embeddings.json
│   └── citations_with_embeddings.json
├── platform_results/
│   ├── claude_results.jsonl
│   ├── gemini_results.jsonl
│   ├── openai_results.jsonl
│   └── perplexity_results.jsonl
├── visualizations/
│   ├── *.html (Plotly charts)
│   └── paths.json
└── site_discovery/
    ├── discovered_pages.json
    ├── site_tree.json
    └── discovery_summary.json
```

---

## Appendix C: Code Standards & Conventions

### Python Standards
- **Python 3.12+** required
- **Type hints on ALL function signatures** — no exceptions
- **Pydantic v2 strict models** with validators for feature ranges
- **async/await** for all I/O-bound operations (API calls, file ops, DB)
- **Naming:** Files: `snake_case.py` · Classes: `PascalCase` · Functions/vars: `snake_case` · Constants: `UPPER_SNAKE_CASE`

### DeepAgents Patterns
- Use `system_prompt=` parameter (NOT `system_message=`)
- Wrap ALL `agent.invoke()` calls in `ThreadPoolExecutor(max_workers=1)`
- Agents return JSON: `{"written_paths": [...], "notes": "..."}` for persona/style
- Support patch-style updates for existing artifacts (read → edit sections → write back)

### LangGraph Patterns
- State is a plain dict (not a TypedDict or Pydantic model — flexibility over safety)
- `interrupt()` for human-in-the-loop pausing
- Conditional edges for routing based on `approval_decision`
- `auto_approve` flag to skip interrupts in CI/CD

### Error Handling
- Each pipeline step must be independently recoverable
- Never let one step failure crash the entire pipeline — isolate, log, continue
- Use `skip_steps` to bypass cached steps on re-runs
- Structured logging with correlation IDs (planned, not fully implemented)

### Git Standards
- Feature branches: `feat/research-refactor`, `feat/gap-analysis-integration`
- Descriptive commits: `feat: add persona graph with accept/reject/revise flow`
- Never commit directly to `main`
- PR-ready branches before merge

### Import Convention
```python
from core.config.settings import settings
from core.models.artifacts import CompanyResearchInput, CompanyContextArtifact
from core.models.personas import PersonaResearchInput, PersonaArtifact
from core.research.agents.base import get_backend, get_store
from core.research.graphs.company_research import build_graph
from core.gap_analysis.pipeline import run_gap_analysis
from core.shared_tools.embedding_client import embed_texts
from core.shared_tools.chroma_client import upsert_embeddings
from core.content_engine.pipeline import run_content_generation
from core.models.content_generation import ContentGenerationInput, ContentBrief, FormattedContent
```

---

## Changelog

| Date | Section | Change | Task ID |
|------|---------|--------|---------|
| 2026-02-15 | §7 | Complete rewrite — Content Generation Engine implemented (4-stage pipeline) | T-CG-all |
| 2026-02-15 | §4 | Added content_engine/ directory tree (30+ files) | T-CG-all |
| 2026-02-15 | §10 | Added Content Generation Models (15 Pydantic models) | T-CG-1 |
| 2026-02-15 | §11 | Added Content Engine + Langfuse env vars (11 new settings) | T-CG-3 |
| 2026-02-15 | §12 | Added scripts/run_content_engine.py CLI reference | T-CG-all |
| 2026-02-15 | §15 | Updated test coverage: 150 total tests, 57 content engine tests | T-CG-32/33 |
| 2026-02-15 | §17 | Added Decisions 9-11 (Orchestrator-Workers, Raw SDK, Langfuse) | D-CG-1/2 |
| 2026-02-15 | §18 | Downgraded test coverage from Critical to Medium | T-CG-32/33 |
| 2026-02-15 | §20 | Moved Content Engine to "Built", updated roadmap | T-CG-all |
| 2026-02-15 | §A | Added 9 content engine rows to Model & API Key Matrix | T-CG-all |
| 2026-02-15 | §B | Added content engine artifact naming convention | T-CG-all |
| 2026-02-16 | §1 | Updated Executive Summary — no longer CLI-first, FastAPI implemented | D-API-1 |
| 2026-02-16 | §3 | Added FastAPI + Langfuse to architecture diagram and tech stack table | D-API-1 |
| 2026-02-16 | §4 | Added api/ directory tree (30+ files), updated tests/ tree, added async shared tools | D-API-1 |
| 2026-02-16 | §7.5 | Rewrote Langfuse tracing section — v2→v3 migration details, corrected hierarchy | F2 |
| 2026-02-16 | §11 | Added FastAPI API server env vars (API_CORS_ORIGINS, API_PREFIX, API_MAX_CONCURRENT_PIPELINES) | D-API-1 |
| 2026-02-16 | §12 | Added scripts/run_server.py entry point | D-API-1 |
| 2026-02-16 | §15 | Added API test coverage (126 tests), updated total to 276 | D-API-1 |
| 2026-02-16 | §16 | Added fastapi, uvicorn, python-multipart to dependency graph; updated internal flow | D-API-1 |
| 2026-02-16 | §17 | Added Decision 12: FastAPI integration architecture (D-API-1); updated Decision 11 with v3 note | D-API-1 |
| 2026-02-16 | §18 | Added items 15-17 (Langfuse v2 resolved, TaskStore limitations); updated test coverage severity | D-API-1, F2 |
| 2026-02-16 | §20 | Moved FastAPI from "Planned" to "Built"; added Langfuse tracing to built list | D-API-1 |
| 2026-02-16 | §21 | **NEW SECTION** — Complete REST API Layer documentation (endpoints, TaskStore, SSE, HITL flow) | D-API-1 |
| 2026-02-18 | §6.4 | Rewrote S4 section — 3-tier main content extraction, dual-soup architecture, ~45 structural signals across 4 categories | T-SSO-all |
| 2026-02-18 | §6.6 | Added GapContentBrief computation, expanded ClusterContentSpec (12 new fields), URL dedup, TF-IDF themes | T-SSO-all |
| 2026-02-18 | §6.8 | Rewrote S8 section — 3-tier output architecture, top-25 inline briefs, gap_analysis_complete.json | T-SSO-all |
| 2026-02-18 | §6.10 | Updated data flow diagram — gap_analysis_complete.json added to S8 output | T-SSO-all |
| 2026-02-18 | §10 | Expanded StructuralSignals (11→45 fields), added GapContentBrief model, expanded ClusterContentSpec, CitationExemplar | T-SSO-all |
| 2026-02-18 | §15 | Updated test tree — 4 new test files, 351 total tests (all passing), fixed S4 known failures | T-SSO-all |
| 2026-02-18 | §16 | Added trafilatura v1.6+ and textstat v0.7+ to dependency graph | T-SSO-all |
| 2026-02-19 | §21.3 | TaskStore: asyncio.Event→Queue for approvals; added task handle tracking for cancellation | T-review-fix-1 |
| 2026-02-19 | §21.4 | EventBus: added 15s SSE heartbeat keepalive | T-review-fix-1 |
| 2026-02-19 | §21.2 | Content router: typed ContentStartRequest, brief_id validation; cancel endpoint cancels task + SSE event; slug regex validation on artifacts | T-review-fix-1 |
| 2026-02-19 | §21.5 | HITL: guarded interrupt extraction, research reject early-exit, content auto_approve wired through | T-review-fix-1 |
| 2026-02-19 | §21.6 | Added 5 design choice rows (Queue, task handles, heartbeat, slug validation, rehype-sanitize) | T-review-fix-1 |
| 2026-02-19 | §18 | Updated test count to 351; all S4 failures resolved | T-review-fix-1 |

---

*End of Comprehensive System Documentation*
*Generated: 2026-02-19*
*Total codebase files analyzed: ~120+*
*Total lines of documentation: ~3500+*
