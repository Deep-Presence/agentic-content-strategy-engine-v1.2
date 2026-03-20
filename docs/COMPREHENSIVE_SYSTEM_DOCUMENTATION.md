# Content Strategy Engine — Comprehensive System Documentation

> **Project:** Deep Presence Content Strategy Engine (formerly AEO-Optimizer)
> **Owner:** Aryan (CTO & Co-founder, Deep Presence)
> **Stack:** Python 3.12 · LangGraph · FastAPI · Pydantic v2 · LangSmith · LiteLLM
> **Document Date:** 2026-03-15 (updated: Structured Logging Foundation — structlog, correlation IDs, context propagation)
> **Document Scope:** Exhaustive technical documentation covering architecture, implementation, decisions, vulnerabilities, and roadmap.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What This System Does — The Business Problem](#2-what-this-system-does--the-business-problem)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Directory Structure — Complete File Map](#4-directory-structure--complete-file-map)
4a. [Pipeline 0: Site Audit](#4a-pipeline-0-site-audit)
   - 4a.1 [Overview & Architecture](#4a1-overview--architecture)
   - 4a.2 [Step 1 — Discover (s1_discover.py)](#4a2-step-1--discover-s1_discoverpy)
   - 4a.3 [Step 2 — Analyze Pages (s2_analyze_pages.py)](#4a3-step-2--analyze-pages-s2_analyze_pagespy)
   - 4a.4 [Step 3 — Check Schema (s3_check_schema.py)](#4a4-step-3--check-schema-s3_check_schemapy)
   - 4a.5 [Step 4 — Check AEO (s4_check_aeo.py)](#4a5-step-4--check-aeo-s4_check_aeopy)
   - 4a.6 [Step 5 — Aggregate (s5_aggregate.py)](#4a6-step-5--aggregate-s5_aggregatepy)
   - 4a.7 [Step 6 — Report (s6_report.py)](#4a7-step-6--report-s6_reportpy)
   - 4a.8 [Check Modules](#4a8-check-modules)
   - 4a.9 [Scoring Algorithm](#4a9-scoring-algorithm)
   - 4a.10 [Configuration](#4a10-configuration)
   - 4a.11 [Pydantic Models](#4a11-pydantic-models)
   - 4a.12 [Pipeline Orchestration Details](#4a12-pipeline-orchestration-details)
   - 4a.13 [API Endpoints](#4a13-api-endpoints)
   - 4a.14 [P3 Bug Fixes & Improvements](#4a14-p3-bug-fixes--improvements)
4b. [Daily LLM Visibility Tracker](#4b-daily-llm-visibility-tracker)
   - 4b.1 [Overview & Architecture](#4b1-overview--architecture)
   - 4b.2 [Module Architecture — Design Patterns](#4b2-module-architecture--design-patterns)
   - 4b.3 [Protocol Interfaces](#4b3-protocol-interfaces)
   - 4b.4 [Orchestrator (Mediator)](#4b4-orchestrator-mediator)
   - 4b.5 [Prompt Library Service](#4b5-prompt-library-service)
   - 4b.6 [Platform Runner Service (Adapter)](#4b6-platform-runner-service-adapter)
   - 4b.7 [Mention Detector](#4b7-mention-detector)
   - 4b.8 [Analytics Engine & Metric Calculators](#4b8-analytics-engine--metric-calculators)
   - 4b.9 [API Endpoints (16 Total)](#4b9-api-endpoints-16-total)
   - 4b.10 [DI Wiring](#4b10-di-wiring)
   - 4b.11 [Pydantic Models](#4b11-pydantic-models)
   - 4b.12 [ORM & Database](#4b12-orm--database)
5. [Pipeline 1: Research Artifacts (REMOVED — old DeepAgents pipeline)](#5-pipeline-1-research-artifacts)
5c. [Knowledge Base Pipeline (Pipeline 1a)](#5c-knowledge-base-pipeline-research-v2)
   - 5c.1 [Architecture — 3-Layer Knowledge Base](#5c1-architecture--3-layer-knowledge-base)
   - 5c.2 [DAG Execution & 3 HITL Checkpoints](#5c2-dag-execution--3-hitl-checkpoints)
   - 5c.3 [6 Specialist Agents](#5c3-6-specialist-agents)
   - 5c.4 [Prompt System — 6 Prompt Files with Hub Fallback](#5c4-prompt-system--6-prompt-files-with-hub-fallback)
   - 5c.5 [KBStorage — Versioned Filesystem Store](#5c5-kbstorage--versioned-filesystem-store)
   - 5c.6 [Staleness Tracking & Propagation](#5c6-staleness-tracking--propagation)
   - 5c.7 [Delta Synthesis Mode](#5c7-delta-synthesis-mode)
   - 5c.8 [read_file Tool](#5c8-read_file-tool)
   - 5c.9 [HITL Mini-Graphs](#5c9-hitl-mini-graphs)
   - 5c.10 [Health & Refresh-Stale API Endpoints](#5c10-health--refresh-stale-api-endpoints)
   - 5c.11 [Pydantic Models (17 Models)](#5c11-pydantic-models-17-models)
   - 5c.12 [LangSmith Tracing Integration](#5c12-langsmith-tracing-integration)
   - 5c.13 [Test Coverage (260 tests)](#5c13-test-coverage-260-tests)
5d. [Audience Persona Pipeline (Pipeline 1b)](#5d-audience-persona-pipeline-research-v3)
   - 5d.1 [Architecture — 2-Agent Pipeline with 2 HITL Checkpoints](#5d1-architecture--2-agent-pipeline-with-2-hitl-checkpoints)
   - 5d.2 [Agent 1 — Persona Suggester (Gemini Flash)](#5d2-agent-1--persona-suggester-gemini-flash)
   - 5d.3 [Agent 2 — Profile Generator (Perplexity Deep Research)](#5d3-agent-2--profile-generator-perplexity-deep-research)
   - 5d.4 [HITL-1: Brief Approval Graph](#5d4-hitl-1-brief-approval-graph)
   - 5d.5 [HITL-2: Profile Review Graph](#5d5-hitl-2-profile-review-graph)
   - 5d.6 [PersonaStorage — Versioned Filesystem Store](#5d6-personastorage--versioned-filesystem-store)
   - 5d.7 [Pydantic Models (9 Models)](#5d7-pydantic-models-9-models)
   - 5d.8 [API Endpoints (7 Total)](#5d8-api-endpoints-7-total)
   - 5d.9 [Test Coverage (232 tests)](#5d9-test-coverage-232-tests)
5f. [Research Orchestrator — KB → AP → VSG DAG](#5f-research-orchestrator--kb--ap--vsg-dag)
   - 5f.1 [Architecture & Flow](#5f1-architecture--flow)
   - 5f.2 [Skip Logic](#5f2-skip-logic)
   - 5f.3 [HITL Pass-Through](#5f3-hitl-pass-through)
   - 5f.4 [API Endpoints](#5f4-api-endpoints)
   - 5f.5 [Test Coverage (67 tests)](#5f5-test-coverage-67-tests)
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
   - 7.1 [LiteLLM Client — Unified LLM Abstraction](#71-litellm-client--unified-llm-abstraction)
   - 7.2 [LangSmith Prompt Registry — Hub-with-Local-Fallback](#72-langsmith-prompt-registry--hub-with-local-fallback)
   - 7.3 [LangSmith Tracing Architecture (Replaces Langfuse)](#73-langsmith-tracing-architecture-replaces-langfuse)
   - 7.4 [Stage 0 — Two-Phase Context Loading (ContextRouter)](#74-stage-0--two-phase-context-loading-contextrouter)
   - 7.5 [Stage 1 — Strategic Planner (Agent 1)](#75-stage-1--strategic-planner-agent-1)
   - 7.6 [Stage 2 — Brief Builder (Agent 2)](#76-stage-2--brief-builder-agent-2)
   - 7.7 [Stage 3 — Content Workers (Orchestrator-Workers)](#77-stage-3--content-workers-orchestrator-workers)
   - 7.8 [Stage 4 — Evaluator-Optimizer Loop](#78-stage-4--evaluator-optimizer-loop)
   - 7.9 [Stage 5 — Human Review (LangGraph HITL)](#79-stage-5--human-review-langgraph-hitl)
   - 7.10 [v1.0 Architecture (Preserved)](#710-v10-architecture-preserved)
   - 7.11 [Entry Modes](#711-entry-modes)
   - 7.12 [Pydantic Models — v1.3 (12 models)](#712-pydantic-models--v13-12-models)
   - 7.13 [Artifact Structure](#713-artifact-structure)
   - 7.14 [Utility Modules](#714-utility-modules)
   - 7.15 [Input Sources](#715-input-sources)
8. [Reddit Human-in-the-Loop Monitor](#8-reddit-human-in-the-loop-monitor)
9. [Storage Architecture](#9-storage-architecture)
   - 9.1 [Filesystem Layer (Source of Truth)](#91-filesystem-layer-source-of-truth)
   - 9.2 [DeepAgents Backend Routing (REMOVED)](#92-deepagents-backend-routing-removed)
   - 9.3 [pgvector Vector Store](#93-pgvector-vector-store)
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
22. [Front-Back Integration Sprint — Exhaustive 4-Phase Detail](#22-front-back-integration-sprint--exhaustive-4-phase-detail)
    - 22.1 [Sprint Context](#221-sprint-context)
    - 22.2 [Phase 1 — Foundation](#222-phase-1--foundation-2026-02-25-423-tests)
    - 22.3 [Phase 2 — Gap Analysis Data Endpoints](#223-phase-2--gap-analysis-data-endpoints-2026-02-25-484-tests)
    - 22.4 [Code Review C1-C4 Fixes](#224-code-review-c1-c4-fixes-2026-02-25-500-tests)
    - 22.5 [Phase 3 — Content Briefs + Embedding Projections](#225-phase-3--content-briefs--embedding-projections-2026-02-25-585-tests)
    - 22.6 [Phase 4 — Brand Brain + Run History](#226-phase-4--brand-brain--run-history-2026-02-26-766-tests)
    - 22.7 [Sprint Architecture — How the 4 Phases Connect](#227-sprint-architecture--how-the-4-phases-connect)
    - 22.8 [What's Next](#228-whats-next)
23. [Product-Level Pipeline Execution Sprint](#23-product-level-pipeline-execution-sprint--exhaustive-5-phase-detail)
24. [Route Protection & Authorization Sprint](#24-route-protection--authorization-sprint--exhaustive-implementation-detail)
    - 24.1 [Problem Statement](#241-problem-statement)
    - 24.2 [Architecture — Separation of Concerns](#242-architecture--separation-of-concerns)
    - 24.3 [Pure ASGI Middleware — Why Not BaseHTTPMiddleware](#243-pure-asgi-middleware--why-not-basehttpmiddleware)
    - 24.4 [Default-Deny & Public Route Whitelist](#244-default-deny--public-route-whitelist)
    - 24.5 [Token Extraction — Dual-Mode (Header + Query Param)](#245-token-extraction--dual-mode-header--query-param)
    - 24.6 [Auth Dependency Chain](#246-auth-dependency-chain)
    - 24.7 [Auth Dependency Usage — Complete Router Map](#247-auth-dependency-usage--complete-router-map)
    - 24.8 [Registration Hardening (Codex C1)](#248-registration-hardening--closing-the-cross-tenant-attack-codex-c1)
    - 24.9 [Invite Flow](#249-invite-flow--joining-existing-companies)
    - 24.10 [Pipeline Tenant Isolation (Codex C2)](#2410-pipeline-tenant-isolation-codex-c2)
    - 24.11 [Task & SSE Tenant Isolation (Codex C3)](#2411-task--sse-tenant-isolation-codex-c3)
    - 24.12 [JWT Secret Key Enforcement (Codex W8)](#2412-jwt-secret-key-enforcement-codex-w8)
    - 24.13 [Login Timing Fix (Codex W7)](#2413-login-timing-fix-codex-w7)
    - 24.14 [Threading Model — RLock and Mutable Field Allowlists](#2414-threading-model--rlock-and-mutable-field-allowlists)
    - 24.15 [Middleware Ordering](#2415-middleware-ordering)
    - 24.16 [Test Migration Strategy](#2416-test-migration-strategy)
    - 24.17 [New Auth Enforcement Tests](#2417-new-auth-enforcement-tests)
    - 24.18 [Codex Review Findings — Full Disposition](#2418-codex-review-findings--full-disposition)
    - 24.19 [Files Changed Summary](#2419-files-changed-summary)
    - 24.20 [Deferred Items](#2420-deferred-items)
25. [Settings Pages API & Knowledge Doc Upload Sprint](#25-settings-pages-api--knowledge-doc-upload-sprint--exhaustive-implementation-detail)
    - 25.1 [Sprint Context & Problem Statement](#251-sprint-context--problem-statement)
    - 25.2 [Feature 1A — User Management](#252-feature-1a--user-management)
    - 25.3 [Feature 1B — Company Profile Editing](#253-feature-1b--company-profile-editing)
    - 25.4 [Feature 1C — Pipeline Defaults](#254-feature-1c--pipeline-defaults)
    - 25.5 [Feature 2A — Knowledge Doc Upload & Storage](#255-feature-2a--knowledge-doc-upload--storage)
    - 25.6 [Feature 2B — S1 Pipeline Integration](#256-feature-2b--s1-pipeline-integration)
    - 25.7 [Feature 2C — Embedded Status Tracking](#257-feature-2c--embedded-status-tracking)
    - 25.8 [Shared Modules Extracted (Review Fixes C2/C3)](#258-shared-modules-extracted-review-fixes-c2c3)
    - 25.9 [Review Fixes Summary](#259-review-fixes-summary)
    - 25.10 [Runner Integration — Pipeline Defaults Wiring](#2510-runner-integration--pipeline-defaults-wiring)
    - 25.11 [New Endpoints Summary](#2511-new-endpoints-summary)
    - 25.12 [Files Changed Summary](#2512-files-changed-summary)
    - 25.13 [Deferred Items](#2513-deferred-items)
26. [SQLAlchemy & Service Layer Migration — 3-Phase Database Architecture](#26-sqlalchemy--service-layer-migration--3-phase-database-architecture)
    - 26.1 [Migration Overview & Strategy](#261-migration-overview--strategy)
    - 26.2 [Phase 1 — SQLAlchemy ORM Infrastructure (D-DB-1)](#262-phase-1--sqlalchemy-orm-infrastructure-d-db-1)
    - 26.3 [Phase 1 — ORM Tables (31 Total)](#263-phase-1--orm-tables-31-total)
    - 26.4 [Phase 1 — Repository Pattern](#264-phase-1--repository-pattern)
    - 26.5 [Phase 1 — Alembic Migrations](#265-phase-1--alembic-migrations)
    - 26.6 [Phase 1 — Engine & Session Factory](#266-phase-1--engine--session-factory)
    - 26.7 [Phase 2 — Auth Migration: Three-Layer Decomposition (D-AUTH-2)](#267-phase-2--auth-migration-three-layer-decomposition-d-auth-2)
    - 26.8 [Phase 2 — AuthServiceProtocol](#268-phase-2--authserviceprotocol)
    - 26.9 [Phase 2 — JsonAuthService & DbAuthService](#269-phase-2--jsonauthservice--dbauthorservice)
    - 26.10 [Phase 2 — Auth Utilities (Pure Functions)](#2610-phase-2--auth-utilities-pure-functions)
    - 26.11 [Phase 2 — Middleware Decoupling](#2611-phase-2--middleware-decoupling)
    - 26.12 [Phase 3 — Service Layer Migration: Three Data Protocols (D-SVC-1)](#2612-phase-3--service-layer-migration-three-data-protocols-d-svc-1)
    - 26.13 [Phase 3 — GapDataServiceProtocol & Implementations](#2613-phase-3--gapdataserviceprotocol--implementations)
    - 26.14 [Phase 3 — BrandDataServiceProtocol & ContentDataServiceProtocol](#2614-phase-3--branddataserviceprotocol--contentdataserviceprotocol)
    - 26.15 [Phase 3 — Signal & Platform Repositories (SQL Analytics)](#2615-phase-3--signal--platform-repositories-sql-analytics)
    - 26.16 [Phase 3 — TaskStoreProtocol & DbTaskStore (D-TASKSTORE-1)](#2616-phase-3--taskstoreprotocol--dbtaskstore-d-taskstore-1)
    - 26.17 [DI Wiring — How the Switch Works](#2617-di-wiring--how-the-switch-works)
    - 26.18 [Backfill Script (JSON to DB Migration)](#2618-backfill-script-json-to-db-migration)
    - 26.19 [Cross-Cutting Patterns](#2619-cross-cutting-patterns)
    - 26.20 [Architecture Diagram](#2620-architecture-diagram)
    - 26.21 [Testing Strategy](#2621-testing-strategy)
    - 26.22 [Files Changed Summary](#2622-files-changed-summary)
    - 26.23 [Deferred Items](#2623-deferred-items)
27. [Appendix A: Model & API Key Matrix](#appendix-a-model--api-key-matrix)
28. [Appendix B: Artifact Naming Conventions](#appendix-b-artifact-naming-conventions)
29. [Appendix C: Code Standards & Conventions](#appendix-c-code-standards--conventions)

---

## 1. Executive Summary

The **Content Strategy Engine** is a multi-agent AI platform that automates the end-to-end workflow of content strategy for B2B companies. It operates across four pipelines:

0. **Site Audit Pipeline** (implemented) — A 6-step deterministic pipeline that audits website AI-readiness across 8 dimensions (crawlability, performance, on-page SEO, content extractability/AEO, schema markup, E-E-A-T, freshness, security). Scores each dimension 0–100 using penalty-based deductions, computes a weighted overall score, assigns a letter grade (A–F), and generates actionable Markdown + JSON reports. 100% deterministic — no LLM calls.

1. **Research Artifacts Pipeline** (implemented) — Uses LLM agents with web research tools to produce company context documents, audience persona profiles, and writing style guides. Each artifact goes through a human-in-the-loop approval flow (approve / revise / reject) before being finalized. **Knowledge Base v2** (implemented 2026-03-05/06) replaces the monolithic agent with 5 specialist research agents, a versioned knowledge base (L2 docs), DAG-ordered execution with 3 HITL checkpoints, delta synthesis mode, staleness tracking with propagation, and health/refresh-stale API endpoints. 260 tests. **Audience Persona Pipeline v2** (implemented 2026-03-06) is a 2-agent architecture: Agent 1 (Gemini Flash) suggests 3–7 persona briefs → HITL-1 per-brief approval → Agent 2 (Perplexity deep research) generates full persona profiles in parallel → HITL-2 per-profile review. PersonaStorage versioned filesystem, KB staleness integration, 7 API endpoints, 232 tests.

2. **Gap Analysis Pipeline** (implemented) — An 8-step data pipeline that embeds a company's web content, generates buyer-intent search queries, searches four AI platforms (ChatGPT, Claude, Perplexity, Google AI Overview), enriches the citations those platforms return, embeds everything into a shared vector space, computes semantic proximity analysis (SPA), generates interactive visualizations, and produces a gap report with actionable content recommendations.

3. **Content Generation Engine v1.3** (implemented) — A 6-stage async pipeline that consumes the outputs of Pipelines 1 and 2 to automatically generate optimized content pieces that close the identified citation gaps. Two-phase context loading (ContextRouter), Strategic Planner (topic selection), Brief Builder (parallel blueprint generation), Orchestrator-Workers (5-agent chain: Outliner → Drafter → Fact Enricher → Formatter → Linker), Evaluator-Optimizer loop (E-E-A-T + Style + Factual judges, max 2 revisions), **Stage 4.5 CPS Scoring** (Citation Signal Predictor — predicts AI engine citation probability 0.0–1.0 per piece), and LangGraph HITL for human review. LiteLLM abstraction for all LLM calls, LangSmith tracing (Langfuse fully removed). **Standalone CPS endpoint** (`POST /api/v1/cps/score`) available for ad-hoc scoring.

Additionally, a **Reddit Human-in-the-Loop Monitor** (implemented) monitors subreddits for threads matching a company's ICP persona, drafts contextual replies, and sends notifications via Slack/Discord.

The system exposes both a **CLI** and a **FastAPI REST API** (implemented 2026-02-16, expanded 2026-02-25/26). All business logic lives in a `core/` Python package. The API layer (`api/`) wraps all three pipelines with async task runners, SSE event streaming for real-time progress, and HITL approval endpoints. A **front-back integration sprint** (2026-02-25/26) added 16 company-scoped data retrieval endpoints across 4 phases — authentication, gap analysis data, content brief data, and brand brain/run history — with a 3-module service layer, 50+ response models, and 343 new tests. Task state is persisted via a JSON-backed TaskStore. Artifacts are persisted to the local filesystem as the source of truth, with optional versioned mirroring to Supabase. LLM observability is provided by **LangSmith** tracing across all pipelines — content engine, knowledge base, and research agents (Langfuse was fully removed 2026-03-02).

A **Settings Pages API** sprint (2026-02-27) added 11 new endpoints across 3 features — team management, company profile editing, and pipeline defaults — plus a full **Knowledge Document Upload** system (5 endpoints, multipart file upload, text extraction, s1 pipeline integration, embedded status tracking). Shared modules (`core/shared_tools/text_extraction.py`, `core/shared_tools/knowledge_doc_metadata.py`) ensure consistent text extraction and thread-safe metadata coordination between the API service layer and the gap analysis pipeline.

A **3-phase database migration** (2026-02-27/28) established a hybrid filesystem + PostgreSQL architecture: Phase 1 created 31 ORM tables, 16 repositories, and 4 Alembic migrations using pure SQLAlchemy 2.0. Phase 2 decomposed authentication into a three-layer architecture (pure utilities → service protocol → dual Json/Db implementations). Phase 3 applied the same protocol pattern across all data services (gap, brand, content, TaskStore) with SQL analytics repositories replacing Python-based JSON parsing for heavy aggregations. All phases use a single opt-in switch (`DATABASE_URL`) with automatic fallback to JSON-backed services.

**~2568 tests, 1 pre-existing failure (PB-39).** Full coverage across all pipelines (including site audit, Knowledge Base, and Audience Persona), API endpoints, data retrieval layers, settings management, knowledge document upload, auth services, DB repositories, service layer protocols, and CPS model. Knowledge Base module: 260 tests. Audience Persona module: 232 tests. CPS model: 44 tests (7 skipped without torch).

**Current production clients analyzed:** Ramp (corporate spend management), Carta (equity management platform), and Mynd.

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
│  │           Artifact Storage               │  │  LangSmith           │  │
│  │  Filesystem (SoT) ◀──▶ Supabase Mirror  │  │  (LLM Observability) │  │
│  │  pgvector (vectors)                       │  └───────────────────────┘  │
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
│  • Supabase (PostgREST + Storage)    • pgvector (PostgreSQL vectors)     │
└──────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.12+ | All business logic |
| **API Framework** | FastAPI + Uvicorn | REST API with async task runners, SSE, HITL endpoints |
| **Agent Framework** | Raw SDK clients + LangGraph | LLM agent creation with tool-use and HITL |
| **Orchestration** | LangGraph v0.2+ | State machine graphs with interrupt-based human-in-the-loop |
| **Data Validation** | Pydantic v2 | Input/output schemas, settings management |
| **Web Research** | Perplexity SDK (sonar-deep-research) | Deep web research with citations |
| **LLM Providers** | Google Gemini, Anthropic Claude, OpenAI GPT | Agent reasoning, query gen, reports |
| **Embeddings** | OpenAI text-embedding-3-small (1536-dim) | Semantic similarity in gap analysis |
| **Vector Store** | pgvector (PostgreSQL extension) | Embedding storage and retrieval via `DATABASE_URL` |
| **Database** | Supabase (PostgreSQL 17 + pgvector) | Optional artifact mirroring, versioning |
| **Visualization** | Plotly | Interactive HTML charts (UMAP, t-SNE, heatmaps) |
| **Dimensionality Reduction** | UMAP, t-SNE (scikit-learn) | Embedding space visualization |
| **Web Crawling** | Playwright, httpx, BeautifulSoup4 | Site crawling and HTML extraction |
| **Reddit** | PRAW (read-only) | Subreddit monitoring |
| **Notifications** | Slack Block Kit, Discord Webhooks | Alert delivery |
| **LLM Abstraction** | LiteLLM | Unified LLM call interface with auto-prefix routing (content engine) |
| **Observability** | LangSmith (sole backend) | LLM tracing, scoring, prompt registry (Langfuse fully removed 2026-03-02) |

---

## 4. Directory Structure — Complete File Map

```
content-strategy-engine/
├── CLAUDE.md                              # Project memory for Claude Code (development instructions)
├── README.md                              # User-facing documentation + quick start
├── pyproject.toml                         # Project metadata + dependency declaration
├── requirements.txt                       # Flat dependency list (for pip install)
├── alembic.ini                            # Alembic config — script_location=core/db/migrations (DB URL from settings)
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
│   │   ├── audience_persona.py           # PersonaBrief, PersonaManifest, PersonaProfileEntry,
│   │   │                                  #   PersonaAgentResult, AudiencePersonaInput, AudiencePersonaOutput (9 models)
│   │   ├── personas.py                    # PersonaResearchInput, PersonaArtifact (with to_markdown()) [v1 legacy]
│   │   ├── style_guide.py                # StyleGuideResearchInput, WritingStyleGuideArtifact
│   │   ├── gap_analysis.py               # 20+ models: GapAnalysisInput, SemanticUnit, QueryCluster,
│   │   │                                  #   GeneratedQuery, CitationRef, PlatformResult, StructuralSignals,
│   │   │                                  #   EnrichedCitation, SpaResult, CentroidResult, QueryGap,
│   │   │                                  #   ClusterContentSpec, AnalysisResult, GapReport,
│   │   │                                  #   DiscoveredPage, SiteTreeNode, SiteDiscoveryResult
│   │   ├── site_audit.py                 # SiteAuditInput, AuditFinding, PageAuditResult, DimensionScore, SiteAuditResult,
│   │   │                                  #   SchemaDetectionResult, AEOReadinessResult, AIBotAccessResult, SitemapHealthResult
│   │   ├── knowledge_base.py             # 17 KB models (KBManifest, KBDocVersion, etc.)
│   │   ├── knowledge_docs.py             # KnowledgeDocument metadata model (upload tracking)
│   │   ├── organization.py               # CompanyPipelineDefaults model (per-company pipeline overrides)
│   │   └── reddit_hil.py                 # RedditMonitorInput, RedditThread, DraftNotification
│   │
│   ├── site_audit/                        # Pipeline 0: Site Audit (6-step, deterministic)
│   │   ├── __init__.py
│   │   ├── config.py                      # AuditConfig frozen dataclass, DEFAULT_AUDIT_CONFIG, dimension weights
│   │   ├── pipeline.py                    # Main orchestrator: run_site_audit()
│   │   ├── scoring.py                     # Penalty-based scoring, grade computation
│   │   ├── checks/                        # Pure-function check modules (no I/O)
│   │   │   ├── crawlability.py            # robots.txt, sitemap, canonical, redirect checks
│   │   │   ├── on_page_seo.py             # Title, meta desc, headings, alt text, internal links
│   │   │   ├── eeat_signals.py            # Author info, citations, original research, recency
│   │   │   ├── security.py                # HTTPS, mixed content, CSP headers
│   │   │   ├── extractability.py          # Question headings, hooks, self-contained paragraphs
│   │   │   ├── schema_checks.py           # JSON-LD parsing, type validation, @graph handling
│   │   │   └── performance.py             # SSR content check + Core Web Vitals (async)
│   │   └── steps/                         # Individual pipeline steps
│   │       ├── s1_discover.py             # AsyncSiteCrawler — 4-phase BFS + AI bot detection
│   │       ├── s2_analyze_pages.py        # Per-page parallel analysis with semaphore
│   │       ├── s3_check_schema.py         # JSON-LD detection with @graph, type validation
│   │       ├── s4_check_aeo.py            # AEO readiness scoring (0-100 composite)
│   │       ├── s5_aggregate.py            # Dimension scoring, overall score, grade, top findings
│   │       └── s6_report.py               # Markdown + JSON report generation
│   │
│   ├── research/                          # Pipeline 1: Research Pipelines (KB + AP + VSG)
│   │   ├── __init__.py
│   │   ├── knowledge_base/                # Pipeline 1a: 6-agent DAG, HITL, storage
│   │   │   ├── storage.py, agents.py, pipeline.py, graph.py, tools.py
│   │   ├── audience_persona/              # Pipeline 1b: 2-agent pipeline with 2 HITL checkpoints
│   │   │   ├── agents.py                  # Agent 1 (Gemini Flash suggester) + Agent 2 (Perplexity generator)
│   │   │   ├── graph.py                   # 2 LangGraph HITL sub-graphs (brief review + profile review)
│   │   │   ├── pipeline.py               # 4-phase orchestrator (preflight → suggest → generate → finalize)
│   │   │   └── storage.py                 # PersonaStorage: versioned filesystem (manifest + brief + v{N}.md)
│   │   ├── voice_style_guide/             # Pipeline 1c: 3-agent pipeline with 1 HITL checkpoint
│   │   │   ├── agents.py, graph.py, pipeline.py, storage.py
│   │   ├── prompts/                       # Prompt files for research agents
│   │   │   ├── persona_suggester.py       # System + user prompts for AP Agent 1
│   │   │   ├── persona_generator.py       # System + user prompts for AP Agent 2
│   │   │   └── ...                        # KB agent prompts (6 files)
│   │   └── tools/                         # Research-specific tools
│   │       ├── __init__.py
│   │       └── perplexity_client.py       # sonar-deep-research wrapper with citation formatting
│   │
│   ├── cps_model/                         # Citation Signal Predictor Model
│   │   ├── __init__.py
│   │   ├── config.py                      # TrainingConfig (Pydantic): loss, optimizer, encoder, predictor configs
│   │   ├── scorer.py                      # CPSScorer: inference wrapper, from_checkpoint(), score_async()
│   │   ├── best_model.pt                  # Trained model checkpoint (gitignored in prod)
│   │   ├── scaler_params.npz             # Feature standardization params
│   │   ├── model/
│   │   │   ├── __init__.py
│   │   │   ├── fusion_encoder.py          # FusionEncoder: 3-stream (semantic + sidecar + engine)
│   │   │   ├── citation_predictor.py      # CitationPredictor: shared trunk + 4 per-engine heads
│   │   │   └── feature_selector.py        # Feature selection configs (option_a/option_b)
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── base.py                    # BaseExtractor ABC
│   │       ├── structural.py              # 12 HTML structure features (headers, lists, tables, etc.)
│   │       ├── citability.py              # 9 text citability features (factual density, reading level, etc.)
│   │       └── authority.py               # 9 URL authority features (domain, HTTPS, citations, etc.)
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
│   │   ├── tracing.py                     # LangSmith tracing (unified, shared across all pipelines)
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
│   ├── storage/                           # Persistence layer (filesystem + Supabase mirror)
│   │   ├── __init__.py
│   │   ├── backends/
│   │   │   ├── __init__.py
│   │   │   └── base.py                    # Abstract StorageBackend interface (read/write/exists/delete/list_dir)
│   │   ├── supabase_client.py             # Singleton Supabase client factory (lru_cache)
│   │   └── supabase_mirror.py             # Versioned mirroring: mirror_*_if_configured() functions (339 lines)
│   │
│   ├── db/                                # Database layer — SQLAlchemy 2.0 + asyncpg + Alembic (Phase 1)
│   │   ├── __init__.py                    # Exports: Base, UUIDPKMixin, TimestampMixin, get_engine, get_session_factory, reset_engine
│   │   ├── base.py                        # DeclarativeBase + UUIDPKMixin (native PgUUID) + TimestampMixin
│   │   ├── engine.py                      # Lazy engine init + async session factory (no import-time DB connection)
│   │   ├── enums.py                       # 12 Postgres enum types (UserRole, PipelineType, PipelineStatus, etc.)
│   │   ├── dependencies.py               # FastAPI DI: get_db_session(), get_*_repo() (not wired to routes in Phase 1)
│   │   ├── models/                        # ORM models — 31 tables across 10 files
│   │   │   ├── __init__.py                # Imports all model modules (triggers metadata registration)
│   │   │   ├── organization.py            # CompanyModel, ProductModel, UserModel, InviteModel, PipelineDefaultsModel
│   │   │   ├── pipelines.py               # PipelineRunModel (self-ref FK), PipelineStageLogModel
│   │   │   ├── cache.py                   # PlatformResultCacheModel, UrlEnrichmentCacheModel, UrlStructuralSignalsModel (45 cols)
│   │   │   ├── gap_analysis.py            # RunQueryModel, RunCitationModel, QueryGapModel, QueryExemplarModel, ClusterSpecModel, SpaResultModel, CentroidResultModel
│   │   │   ├── embeddings.py              # SemanticUnitModel, QueryEmbeddingModel, ParagraphEmbeddingModel, RunParagraphScoreModel (pgvector)
│   │   │   ├── content.py                 # ContentPieceModel, ResearchArtifactModel
│   │   │   ├── tracking.py                # TrackingSnapshotModel (partial unique indexes), ContentMentionTrackingModel, ContentPieceTrackingModel
│   │   │   ├── site_audit.py              # SiteAuditModel, AuditFindingModel
│   │   │   ├── topic_discovery.py         # TopicDiscoveryModel, DiscoveredTopicModel
│   │   │   └── knowledge_docs.py          # KnowledgeDocumentModel
│   │   ├── repositories/                  # Generic base + 8 domain repos (flush-only contract)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # SQLAlchemyRepository[ModelT] — generic CRUD (get_by_id, create, update, delete, list_all)
│   │   │   ├── company_repo.py            # get_by_slug, get_by_domain, list_active
│   │   │   ├── auth_repo.py               # get_by_email, list_by_company, count_superusers, deactivate
│   │   │   ├── pipeline_repo.py           # create_run, update_status, list_by_company, add_stage_log, get_active_runs
│   │   │   ├── cache_repo.py              # get_fresh_platform_result/url_enrichment (TTL), upsert (ON CONFLICT)
│   │   │   ├── gap_analysis_repo.py       # bulk_insert_query_gaps, get_gaps_by_run, update_gap, get_cluster_specs
│   │   │   ├── embedding_repo.py          # store_embedding, similarity_search (pgvector cosine_distance)
│   │   │   ├── tracking_repo.py           # create_snapshot, get_snapshot, add_mention, get_trend
│   │   │   └── content_repo.py            # create_piece, update_status, list_by_run, get_by_gap_query
│   │   └── migrations/                    # Alembic migration framework
│   │       ├── env.py                     # Reads settings.database_url_sync (computed property), imports models for metadata
│   │       ├── script.py.mako             # Migration template
│   │       └── versions/
│   │           ├── 0001_initial_schema.py # Hand-written: pgvector ext, 12 enums, 31 tables, FKs, partial indexes
│   │           └── 0002_hnsw_indexes.py   # HNSW vector indexes (separate for deployment control)
│   │
│   └── shared_tools/                      # Cross-pipeline utilities
│       ├── __init__.py
│       ├── embedding_client.py            # embed_texts() — OpenAI text-embedding-3-small wrapper (42 lines)
│       ├── async_embedding_client.py      # async_embed_texts() — Async variant with batching
│       ├── vector_store.py                # pgvector-backed vector store (async, requires DATABASE_URL)
│       ├── text_extraction.py             # extract_text() — canonical text extraction for .md/.txt/.pdf/.docx
│       └── knowledge_doc_metadata.py      # Shared metadata lock + I/O for knowledge document _metadata.json
│
├── api/                                   # *** FastAPI REST API LAYER ***
│   ├── __init__.py
│   ├── app.py                             # App factory (lifespan, middleware, 14 routers)
│   ├── config.py                          # ApiSettings (CORS, port, max concurrency)
│   ├── dependencies.py                    # Dependency injection (get_task_store, get_event_bus, get_artifacts_root, get_auth_store)
│   ├── exceptions.py                      # Global exception handlers (TaskNotFound, TaskConflict, PipelineError)
│   ├── auth/                              # Authentication layer (Phase 1 — pre-Supabase)
│   │   ├── __init__.py
│   │   ├── models.py                      # LoginRequest, RegisterRequest, TokenResponse, UserResponse (EmailStr, password validation)
│   │   ├── store.py                       # AuthStore: JSON-file-backed CRUD, PBKDF2 hashing, HMAC tokens, domain normalization,
│   │   │                                  #   update_user(), get/update_pipeline_defaults(), invite management
│   │   ├── middleware.py                  # AuthMiddleware: default-deny pure ASGI middleware
│   │   └── dependencies.py               # require_auth, require_role, require_tenant, require_company_access, require_company_member
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py                      # GET /health, /readiness
│   │   ├── auth.py                        # POST /login, POST /register, GET /me, POST /invite, POST /join
│   │   ├── companies.py                   # GET /api/v1/companies/{slug} — company profile (Phase 1)
│   │   ├── gap_analysis.py                # POST /start, GET /{run_id}/status (pipeline execution)
│   │   ├── gap_data.py                    # 8 GET endpoints: summary, queries, clusters, signals, platforms, heatmap, embeddings, trend
│   │   ├── content.py                     # POST /start, GET /status, POST /approve (pipeline execution)
│   │   ├── content_data.py                # 3 GET endpoints: briefs, briefs/{id}, briefs/{id}/{stage}
│   │   ├── brand_data.py                  # 2 GET endpoints: research/artifacts, runs
│   │   ├── knowledge_base.py              # POST /start, GET /status, POST /approve (KB pipeline)
│   │   ├── audience_persona.py            # POST /start, POST /approve (AP pipeline)
│   │   ├── voice_style_guide.py           # POST /start, POST /approve (VSG pipeline)
│   │   ├── events.py                      # GET /tasks/{task_id}/events (SSE streaming)
│   │   ├── artifacts.py                   # GET /artifacts/companies, /{type}/{slug}
│   │   ├── tasks.py                       # GET /tasks (+ total + company_slug filter), /{task_id}, POST /{task_id}/cancel
│   │   ├── settings.py                    # 6 endpoints: GET/PUT team, profile, pipeline-defaults (Settings Pages API)
│   │   └── knowledge_docs.py             # 5 endpoints: POST upload, GET list/detail/download, DELETE (Knowledge Docs)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py                      # Shared request/response models (GapAnalysisStartInput, KnowledgeBaseStartRequest, etc.)
│   │   ├── company.py                     # CompanyProfileResponse, ProductSummary, ResearchArtifactSummary (Phase 1)
│   │   ├── gap_data.py                    # 20+ models: GapSummaryResponse, QueryRow, ClusterSpecResponse, etc. (Phase 2)
│   │   ├── content_data.py                # 12 models: ContentBriefListItem, EvalCycle, EmbeddingPoint, etc. (Phase 3)
│   │   ├── brand_data.py                  # 8 models: ArtifactContent, PersonaArtifact, RunHistoryItem, SPATrendPoint, etc. (Phase 4)
│   │   ├── settings.py                    # TeamMemberResponse, UpdateUserRequest, CompanySettingsResponse, PipelineDefaultsResponse
│   │   └── knowledge_docs.py             # KnowledgeDocResponse, KnowledgeDocListResponse
│   ├── services/                          # Service layer — business logic for data endpoints
│   │   ├── gap_data_service.py            # 13+ functions: mtime cache, Pearson corr, Jaccard sim, TF-IDF, signal avg (Phase 2)
│   │   ├── content_data_service.py        # 2-phase status inference, citability score, eval history (Phase 3)
│   │   ├── brand_data_service.py          # Artifact detection, persona scanning, run history, SPA trend, status mapping (Phase 4)
│   │   └── knowledge_doc_service.py       # Upload, list, get, delete, text extraction for knowledge documents
│   └── tasks/
│       ├── __init__.py
│       ├── models.py                      # PipelineTask, TaskStatus (6 states), ApprovalRecord
│       ├── store.py                       # TaskStore (JSON-backed + in-memory + slug locks + approval queues + task handles)
│       ├── event_bus.py                   # EventBus (pub/sub for SSE, event history, 15s heartbeat)
│       └── runner.py                      # Background task wrappers for all 3 pipelines + HITL interrupt/resume
│
├── scripts/                               # CLI entry points (all use argparse)
│   ├── run_kb.py                          # Knowledge base pipeline (6-agent DAG)
│   ├── run_audience_persona.py            # Audience persona pipeline (2-agent)
│   ├── run_voice_style_guide.py           # Voice style guide pipeline (3-agent)
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
│   ├── knowledge_docs/                    # Uploaded knowledge documents per company/product
│   │   └── {effective_slug}/              # e.g., ramp/ or ramp__corporate-card/
│   │       ├── _metadata.json             # List[KnowledgeDocument] — sidecar metadata
│   │       ├── {uuid}_{original_name}.md  # Stored files with UUID collision-safe prefix
│   │       ├── {uuid}_{original_name}.pdf
│   │       └── ...
│   ├── _auth/                             # Auth system persistence (JSON-file backed)
│   │   ├── companies.json                 # Company registry
│   │   ├── users.json                     # User registry
│   │   └── settings/                      # Per-company pipeline defaults
│   │       └── {company_slug}.json        # CompanyPipelineDefaults
│   ├── chroma_db/                         # (LEGACY) — vector storage now in PostgreSQL via pgvector
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
│   ├── conftest.py                        # Shared fixtures (mock clients)
│   ├── shared_tools/                      # Async embedding + pgvector store tests
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

## 4a. Pipeline 0: Site Audit

### 4a.1 Overview & Architecture

The Site Audit pipeline is a **100% deterministic** (no LLM calls) 6-step pipeline that audits a website's AI-readiness across 8 dimensions. It runs before the Gap Analysis pipeline and produces a comprehensive audit report with dimension scores, an overall grade, and actionable findings. **793 tests** cover the entire module.

**8 Audit Dimensions** (with weights summing to 1.0):

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| `crawlability` | 0.20 | robots.txt accessibility, sitemap quality, canonical tags, redirect chains, crawl-delay |
| `performance` | 0.10 | SSR content presence, Core Web Vitals (graceful degradation via PageSpeed Insights API) |
| `on_page_seo` | 0.15 | Title tags, meta descriptions, heading hierarchy, alt text, internal links, boilerplate detection |
| `extractability` | 0.20 | AEO readiness — question headings, hooks, self-contained paragraphs, content patterns |
| `schema_markup` | 0.10 | JSON-LD presence, 7 schema type validators, coverage across pages |
| `eeat` | 0.15 | Author attribution, content freshness (dateutil parsing with DoS guard) |
| `freshness` | 0.05 | Content recency signals (publish date, modified date, age thresholds) |
| `security` | 0.05 | HTTPS enforcement, mixed content detection |

**Pipeline flow:**

```
s1_discover → s2_analyze_pages → s3_check_schema → s4_check_aeo → s5_aggregate → s6_report
```

**Failure modes:**
- **s1 failure = hard fail** — returns `SiteAuditResult(status="failed")` immediately (no pages to analyse)
- Steps 2–4 degrade gracefully — failures are caught, logged, and the step number is appended to `failed_steps`
- If any steps fail, the pipeline sets `status="degraded"`, zeros out affected dimension scores via `_STEP_DIMENSION_MAP`, and recomputes the overall score conservatively
- Step 6 (report) failure does not affect the result — the `SiteAuditResult` is already complete

**Step-to-dimension mapping** (`_STEP_DIMENSION_MAP` in `pipeline.py`):
```python
{
    2: ["crawlability", "on_page_seo", "security", "eeat", "freshness", "performance"],
    3: ["schema_markup"],
    4: ["extractability"],
}
```

**Entry point:** `core/site_audit/pipeline.py` → `run_site_audit(input_data, config, on_progress, skip_steps, output_dir)`

**Key parameters:**
- `input_data: SiteAuditInput` — domain, max_pages, max_depth, optional feature flags
- `config: AuditConfig = DEFAULT_AUDIT_CONFIG` — scoring thresholds and concurrency limits
- `on_progress: Optional[Callable[[str], None]]` — callback for SSE streaming progress
- `skip_steps: Optional[list[int]]` — step numbers to skip (e.g. `[3, 4]` to reuse cached results)
- `output_dir: Optional[Path]` — defaults to `artifacts/site_audit/{effective_slug}/{audit_id}`

**Effective slug derivation:** `{company_slug}__{product_slug}` (double underscore) when both are present, else `company_slug` only.

### 4a.2 Step 1 — Discover (s1_discover.py)

**File:** `core/site_audit/steps/s1_discover.py`
**Class:** `AsyncSiteCrawler`
**Output:** `S1DiscoveryOutput` dataclass

**S1DiscoveryOutput fields:**
- `pages_with_html: list[tuple[str, str]]` — (url, html) pairs for successfully fetched pages
- `ai_bot_access: AIBotAccessResult` — AI crawler accessibility summary
- `sitemap_health: SitemapHealthResult` — sitemap coverage and health
- `crawl_depth_map: dict[str, int]` — `{normalized_url: BFS_depth}` for every discovered URL
- `redirect_map: dict[str, str]` — `{original_url: final_url}` for redirected requests
- `status_code_map: dict[str, int]` — `{url: http_status_code}` for every fetched URL
- `robots_txt_raw: str` — raw robots.txt content
- `discovered_urls: set[str]` — all normalized URLs found (superset of pages_with_html)

**4-phase URL discovery:**

1. **robots.txt** — Fetch `/robots.txt`, parse User-Agent directives via `urllib.robotparser.RobotFileParser`, extract sitemap URLs, detect AI bot policies, check for `llms.txt`, parse `Crawl-delay` directive
2. **Sitemaps** — Recursive XML sitemap parsing using `defusedxml.ElementTree` (security-hardened). Handles sitemap index files (recursive expansion). Probes common paths (`/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml`, `/sitemap-index.xml`) if robots.txt lists none. Maximum XML body size: `_MAX_XML_BYTES = 10 MB`
3. **RSS/Atom feeds** — Feed discovery and URL extraction from `<link>` tags
4. **BFS crawl** — Breadth-first HTML link extraction using `httpx.AsyncClient` with `asyncio.Semaphore` concurrency control

**URL Normalisation:**
- `normalize_url(url)`: strips fragments, normalises scheme/host to lowercase, removes default ports (80/443), unquotes then re-quotes path
- `canonical_url(url)`: applies all normalizations from `normalize_url()` PLUS sorts query parameters for order-invariant deduplication. This prevents duplicate crawls of URLs like `?a=1&b=2` vs `?b=2&a=1`
- `is_same_domain(url, domain)`: www-stripped netloc comparison

**BFS deduplication:** Uses `canonical_url()` as the dedup key (stored in `_visited` set and `_depth_map`). The normalised form is used for actual fetching. Depth map always keeps the minimum depth for each canonical URL.

**Skip extensions:** A frozenset `_SKIP_EXTENSIONS` of 30+ file extensions (`.pdf`, `.jpg`, `.css`, `.js`, etc.) that are skipped without fetching.

**AI Bot Detection:** Checks 5 bots against robots.txt directives:
- `GPTBot` (OpenAI), `ClaudeBot` (Anthropic), `PerplexityBot`, `Google-Extended`, `CCBot` (Common Crawl)
- Produces `AIBotAccessResult` with per-bot boolean fields and `has_llms_txt`, `robots_txt_exists`, `crawl_delay_seconds`

**Crawl-delay parsing** (`_parse_crawl_delay()`):
- Extracts the first `Crawl-delay:` value from robots.txt using regex `r"(?:^|\n)\s*Crawl-delay:\s*(\d+\.?\d*)"` (case-insensitive)
- Caps at `_MAX_CRAWL_DELAY = 300.0` seconds to prevent unbounded values
- Returns `float | None` (None if no directive found)
- Pipeline generates findings for excessive crawl-delay: `>30s` = medium severity, `>10s` = info severity

**Sitemap Health:** Produces `SitemapHealthResult` with `has_sitemap`, `sitemap_url_count`, `sitemap_urls`, `sitemap_errors`, `has_sitemap_index`.

**Test isolation:** `_transport` parameter on `AsyncSiteCrawler.__init__()` accepts `httpx.MockTransport` for zero-network test runs. Default user-agent: `"DeepPresence-SiteAudit/1.0"`.

### 4a.3 Step 2 — Analyse Pages (s2_analyze_pages.py)

**File:** `core/site_audit/steps/s2_analyze_pages.py`
**Functions:** `analyze_single_page()` (sync, pure CPU) + `analyze_all_pages()` (async with `asyncio.Semaphore`)

`analyze_all_pages()` fans out page analysis via `asyncio.gather()` with a configurable semaphore (`config.page_analysis_concurrency`, default 30). Each page is analysed by `analyze_single_page()` which is synchronous and pure CPU (no I/O).

**Per-page signal extraction** (all via BeautifulSoup + trafilatura + textstat):
- **Title**: `<title>` text and length
- **Meta description**: fallback chain `name="description"` → `property="og:description"` → `name="twitter:description"`
- **Headings**: all H1–H6 tags collected with level and text, heading hierarchy validation
- **Images**: total count, with-alt count, without-alt count
- **Links**: internal vs external link counts (domain-relative classification)
- **Content**: word count via trafilatura text extraction, reading level via textstat
- **Technical SEO**: canonical tag presence and URL, noindex/nofollow meta robots, SSR detection
- **Security**: HTTPS check, mixed content detection (HTTP resources in HTTPS pages)
- **Freshness/authority**: publish date (from `article:published_time`, `datePublished`, `og:updated_time`), modified date, author name/presence
- **Author detection**: scans elements matching CSS class patterns `("author", "byline", "post-author", "entry-author", "article-author", "writer")`

**Check function dispatch** per page:
1. `check_status_code(url, status_code)` → crawlability
2. `check_crawl_depth(url, depth)` → crawlability
3. `check_canonical(url, has_canonical, canonical_url)` → crawlability
4. `check_noindex(url, is_noindex)` → crawlability
5. `check_title(url, title, title_length, config)` → on_page_seo
6. `check_meta_description(url, meta_desc, meta_length, config)` → on_page_seo
7. `check_h1(url, h1_count, h1_text)` → on_page_seo
8. `check_heading_hierarchy(url, headings)` → on_page_seo
9. `check_images(url, total, without_alt)` → on_page_seo
10. `check_internal_links(url, count)` → on_page_seo
11. `check_author(url, has_author)` → eeat
12. `check_freshness(url, publish_date, modified_date, page_type)` → freshness
13. `check_https(url)` → security
14. `check_mixed_content(url, has_mixed_content)` → security
15. `check_ssr_content(html, url)` → performance

Produces `PageAuditResult` per page with all findings, signal values, and sub-results attached.

### 4a.4 Step 3 — Check Schema (s3_check_schema.py)

**File:** `core/site_audit/steps/s3_check_schema.py`
**Functions:** `detect_schema(html, url) -> SchemaDetectionResult` + `generate_schema_findings(url, result) -> list[AuditFinding]`
**Skipped when:** `check_schema_validation=False` on input OR step 3 in `skip_steps`

**Detection pipeline:**
1. Parse all `<script type="application/ld+json">` blocks via `parse_jsonld_blocks()` — matches type with regex `r"^application/ld\+json\s*(;.*)?$"` (case-insensitive, handles charset suffix). Uses `tag.string` with fallback to `tag.get_text()` for multi-node script content
2. Handle `@graph` containers (explodes nested items into flat list), JSON arrays, and standalone objects
3. Extract and normalise `@type` values via `identify_schema_types()` — strips `http://schema.org/` and `https://schema.org/` URI prefixes, deduplicates while preserving order
4. Run type-specific validation via `validate_schema_block()` dispatch — per-block `try/except` isolation
5. Infer page type from URL via `infer_page_type(url, html)` — heuristic path matching

**7 Schema Type Validators** (in `checks/schema_checks.py`):

| Validator | Schema Type | Required Fields | Recommended Fields |
|-----------|-------------|-----------------|-------------------|
| `validate_article_schema()` | Article, BlogPosting | headline, author (with name), datePublished | image, dateModified |
| `validate_faq_schema()` | FAQPage | mainEntity array with @type:Question, name, acceptedAnswer.text | — |
| `validate_howto_schema()` | HowTo | name, step array (each with text or itemListElement) | — |
| `validate_organization_schema()` | Organization | name, url | logo |
| `validate_breadcrumb_schema()` | BreadcrumbList | itemListElement array with position, name (supports nested `item.name`) | — |
| `validate_product_schema()` | Product | name, offers OR price+priceCurrency | description, image, brand, sku |
| `validate_speakable_schema()` | Speakable, SpeakableSpecification | cssSelector OR xpath | name |

**Known schema types** (recognised by the `KNOWN_SCHEMA_TYPES` frozenset): Organization, Article, BlogPosting, FAQPage, HowTo, Product, BreadcrumbList, LocalBusiness, Person, WebSite, WebPage, Speakable, SpeakableSpecification.

**Finding generation** (`generate_schema_findings()`):
- Homepage without Organization schema → **medium**
- Article page without Article/BlogPosting schema → **high**
- FAQ page without FAQPage schema → **high**
- Product page without Product schema → **medium**
- Any page without BreadcrumbList schema → **low**
- Schema present with validation errors → **medium** per error

**Page type inference** (`infer_page_type()`):
- URL path heuristics applied in priority order: `/blog/`, `/posts/`, `/articles/` → `"article"`; `/product/`, `/shop/` → `"product"`; `/faq/`, `/help/` → `"faq"`; `/about/` → `"about"`; `/pricing/` → `"pricing"`; root path → `"homepage"`; default → `"page"`
- Also checks trailing and leading path segments for match

### 4a.5 Step 4 — Check AEO (s4_check_aeo.py)

**File:** `core/site_audit/steps/s4_check_aeo.py`
**Function:** `analyze_aeo_readiness(html, url, config) -> tuple[AEOReadinessResult, list[AuditFinding]]`

This is the **differentiator** — traditional SEO tools don't check any of this. It scores how well content is structured for AI extraction as answer snippets.

**AEO Snippet Readiness Score** (0–100), composite formula:

```
score = question_heading_ratio      × 25
      + quick_answer_hook_ratio     × 25
      + self_contained_para_ratio   × 20
      + paragraph_length_score      × 15
      + content_pattern_score       (0–15, uncapped input)
```

Score is clamped to `[0.0, 100.0]`.

**Component 1 — Question Heading Classification** (`classify_heading_as_question()` in `extractability.py`):

Three rules applied in priority order:
1. **Question mark + start word**: heading ends with `?` AND starts with a recognised question word (21 words including what/how/why/when/where/who/which/can/does/is/are/should/will/do/have/has/could/would/might/may/did/was/were). Uses `\b` word boundary to prevent prefix false positives ("Whoever" is NOT a question).
2. **Comparison patterns**: heading contains vs, versus, compared to, difference between, pros and cons, comparison (regex patterns, no trailing `?` required).
3. **Wh-word headings without `?`**: core wh-words only (what/how/why/when/where/who/which), minimum 4 words to filter fragments like "How" or "What Now".

**Component 2 — Quick Answer Hook Detection** (`detect_quick_answer_hook()` in `extractability.py`):

After each question heading, searches up to 5 siblings for `<p>` elements (including `<p>` nested inside `<div>`/`<section>`/`<article>` containers). Word count must fall within `[config.aeo_quick_answer_min_words, config.aeo_quick_answer_max_words]` (default 15–150). Search stops at the next heading element (h1–h6) to prevent matching unrelated paragraphs. Skips non-content tags (`img`, `figure`, `picture`, `script`, `style`, `noscript`).

**Component 3 — Self-Contained Paragraph Detection** (`is_self_contained_paragraph()` in `extractability.py`):

A paragraph is self-contained if:
- Word count in range 20–80 words
- Does NOT start with a continuity marker (case-insensitive, word boundary): however, additionally, furthermore, moreover, in addition, as mentioned, as noted, as discussed, that said, on the other hand, meanwhile, nevertheless, consequently, therefore

Only meaningful paragraphs (≥5 words) are evaluated. The ratio is `self_contained_count / meaningful_paragraph_count`.

**Component 4 — Paragraph Length Score** (`_compute_paragraph_length_score()`):

Returns a score in [0.0, 1.0]:
- 1.0 if `avg_word_count` is within `[ideal_min, ideal_max]` (default 20–80)
- Linear decay to 0.0 below range (at 0 words) or above range (at 2× ideal_max)
- Guards against invalid config: `ideal_min <= 0` → `ideal_min = 1`

**Component 5 — Content Pattern Score** (`_compute_content_pattern_score()`):

| Pattern | Points | Detector |
|---------|--------|----------|
| FAQ section | +4 | `detect_faq_section()` — heading contains "FAQ"/"Frequently Asked Questions", `<dl>` presence, or 3+ question+answer pairs |
| Definition opening | +3 | `detect_definition_opening()` — first paragraph matches "{Topic} is/are {definitional continuation}" or "{Topic} refers to..." with continuation word validation and non-topic-starter rejection |
| Key takeaways | +3 | `detect_key_takeaways()` — heading with "Key Takeaways"/"Summary"/"TL;DR" followed by `<ul>`/`<ol>` |
| Comparison table | +2 | `detect_comparison_table()` — `<table>` with 3+ rows, 2+ columns, comparison header terms |
| Numbered steps | +2 | `detect_numbered_steps()` — `<ol>` with 3+ items, or 2+ headings matching "Step N:" pattern |
| Table of contents | +1 | `detect_toc()` — CSS selector for id/class containing "toc"/"table-of-contents"/"contents" (case-insensitive), or `<nav>` with 3+ internal anchor links |

Total capped at 15 points.

**Definition opening detection** (`detect_definition_opening()`):
- Matches `{topic (1–5 words)} is/are {continuation}` or `{topic} refers to {anything}`
- After `is/are`, requires a definitional continuation word: articles (a/an/the), definitional verbs (defined/known/considered/described), quantifiers (one/any/not), adverbs (essentially/basically/generally/typically/commonly/often/primarily/specifically/usually/simply), or passive purpose verbs (used/designed/built/meant/intended)
- Also accepts hyphenated compound terms (e.g., "machine-readable") as definitional
- Rejects paragraphs starting with continuity markers or non-topic starters (there/it/our/we/you/they/my/your/his/her/its)

**AEO Findings generated:**
- `low_question_heading_ratio`: ratio < `config.aeo_min_question_heading_ratio` (default 0.3) → **medium**
- `poor_aeo_readiness`: score < 30 → **high**
- `moderate_aeo_readiness`: score 30–59 → **medium**
- `no_self_contained_paragraphs`: ratio = 0 with meaningful paragraphs present → **medium**
- `faq_page_missing_faq_structure`: URL inferred as FAQ page but no FAQ section detected → **medium**

### 4a.6 Step 5 — Aggregate (s5_aggregate.py)

**File:** `core/site_audit/steps/s5_aggregate.py`
**Function:** `aggregate_results(page_results, ai_bot_access, sitemap_health, domain, audit_id, config) -> SiteAuditResult`

1. **Collect findings**: flatten all `AuditFinding` objects from all `PageAuditResult.findings`
2. **Compute dimension scores**: `compute_all_dimension_scores(findings, config, pages_crawled)` — page-normalised scoring (see 4a.9)
3. **Compute overall score**: `compute_overall_score(dimension_scores)` — weighted sum, clamped to [0, 100]
4. **Assign grade**: `compute_grade(overall_score, config)` — threshold lookup
5. **Compute breakdowns**: `findings_by_severity` and `findings_by_dimension` via `collections.Counter`
6. **Compute AEO stats**: average snippet readiness score, average question heading ratio across all pages
7. **Schema coverage**: count of pages where `schema_result.has_schema` is True
8. **Top findings**: `_compute_top_findings(findings, max_count=10)` — sorted by severity (critical first), deduplicated by `finding_type`, each with occurrence count

### 4a.7 Step 6 — Report (s6_report.py)

**File:** `core/site_audit/steps/s6_report.py`
**Functions:** `generate_markdown_report(result) -> str` + `generate_report(result, output_dir) -> tuple[Path, Path]`

`generate_report()` is async, creates `output_dir` if needed, writes two files:

**report.md** — 7-section Markdown executive summary:
1. **Header**: overall score, grade with emoji (A=🟢, B=🔵, C=🟡, D=🟠, F=🔴), pages crawled/discovered, total findings, duration
2. **Dimension Scores**: pipe-delimited table with dimension label, raw score, weight, weighted score, finding count
3. **AI Bot Access**: table of 5 bots with allowed/blocked status, robots.txt and llms.txt presence
4. **Sitemap Health**: sitemap found, URL count, sitemap index, errors
5. **AEO Readiness**: average snippet readiness, schema coverage ratio, average question heading ratio
6. **Top Findings**: numbered list with severity badge, message, dimension, affected page count, recommendation
7. **Findings by Severity**: bullet list of non-zero severity counts

**audit_result.json** — Full `SiteAuditResult` serialized via `model_dump(mode="json")` with `json.dumps(indent=2, default=str)`.

### 4a.8 Check Modules — Detailed Reference

All in `core/site_audit/checks/` — pure functions returning `list[AuditFinding]`, zero I/O.

**crawlability.py** — 4 check functions:

| Function | Finding Types | Severities |
|----------|--------------|------------|
| `check_status_code(url, status_code)` | `timeout_or_connection_error` (code=0), `server_error` (5xx), `client_error` (4xx), `redirect` (3xx) | high, critical, high, info |
| `check_crawl_depth(url, depth, max_recommended=3)` | `excessive_crawl_depth` (>5), `deep_crawl_depth` (>3) | high, medium |
| `check_canonical(url, has_canonical, canonical_url)` | `missing_canonical`, `canonical_mismatch` (canonical != page URL) | medium, high |
| `check_noindex(url, is_noindex)` | `noindex_page` | info |

**on_page_seo.py** — 6 check functions:

| Function | Finding Types | Severities |
|----------|--------------|------------|
| `check_title(url, title, title_length, config)` | `missing_title`, `boilerplate_title`, `title_too_short`, `title_too_long` | critical, high, high, high |
| `check_meta_description(url, meta_desc, meta_length, config)` | `missing_meta_description`, `meta_description_too_short`, `meta_description_too_long` | high, medium, medium |
| `check_h1(url, h1_count, h1_text)` | `missing_h1`, `multiple_h1` | critical, high |
| `check_heading_hierarchy(url, headings)` | `heading_hierarchy_skip` (lists all skip violations) | medium |
| `check_images(url, total, without_alt)` | `images_missing_alt_majority` (>50%), `images_missing_alt` | high, medium |
| `check_internal_links(url, count)` | `no_internal_links` | medium |

Boilerplate title detection: frozenset `{"home", "untitled", "untitled document", "page", "new page", "index", "welcome"}`. Title length thresholds: `config.title_min_length` (default 30) to `config.title_max_length` (default 60). Meta description thresholds: `config.meta_min_length` (default 120) to `config.meta_max_length` (default 160).

**eeat_signals.py** — 2 check functions:

| Function | Finding Types | Severities |
|----------|--------------|------------|
| `check_author(url, has_author)` | `missing_author` | medium |
| `check_freshness(url, publish_date, modified_date, page_type)` | `missing_date_metadata` (articles only), `stale_content_2y` (>730 days), `stale_content_1y` (>365 days) | low, medium, low |

**Date parsing** (`_parse_date_robust()`):
1. Reject strings > `_MAX_DATE_STR_LENGTH = 100` chars (DoS prevention for fuzzy parser)
2. Try `dateutil.parser.isoparse()` first (ISO 8601 with timezones, Z suffix, fractional seconds — fastest, strictest)
3. Fallback to `dateutil.parser.parse(fuzzy=False)` for human-readable dates
4. Normalise timezone-naive results to UTC via `replace(tzinfo=timezone.utc)`
5. Catches `ValueError`, `TypeError`, `OverflowError`

**security.py** — 2 check functions:

| Function | Finding Types | Severities |
|----------|--------------|------------|
| `check_https(url)` | `not_https` | critical |
| `check_mixed_content(url, has_mixed_content)` | `mixed_content` | high |

**performance.py** — 2 functions:

| Function | Type | Finding Types | Severities |
|----------|------|--------------|------------|
| `check_ssr_content(html, url)` | sync, pure | `possible_csr_page` (< 100 visible words after stripping script/style/noscript/head) | high |
| `fetch_core_web_vitals(url, api_key)` | async, I/O | CWV metric findings (LCP, INP, FID, CLS) | high/medium based on thresholds |

CWV "good" thresholds: LCP ≤ 2500ms, FID ≤ 100ms, INP ≤ 200ms, CLS ≤ 0.1. `fetch_core_web_vitals()` returns `None` (graceful degradation) when API key is absent or request fails.

**extractability.py** — 10 functions (see §4a.5 for detailed descriptions):

Core functions: `classify_heading_as_question()`, `detect_quick_answer_hook()`, `is_self_contained_paragraph()`. Content pattern detectors: `detect_faq_section()`, `detect_definition_opening()`, `detect_key_takeaways()`, `detect_comparison_table()`, `detect_numbered_steps()`, `detect_toc()`. Helpers: `_get_visible_text()`, `_count_words()`.

**schema_checks.py** — 12 functions:

Core functions: `parse_jsonld_blocks()`, `identify_schema_types()`, `validate_schema_block()`, `infer_page_type()`. Type validators: `validate_article_schema()`, `validate_faq_schema()`, `validate_howto_schema()`, `validate_organization_schema()`, `validate_breadcrumb_schema()`, `validate_product_schema()`, `validate_speakable_schema()`. Helpers: `_normalize_schema_type()`.

### 4a.9 Scoring Algorithm

**File:** `core/site_audit/scoring.py`

**Page-normalised penalty-based scoring** (ensures large and small sites with the same issue rate receive comparable scores):

1. **Separate findings**: site-level findings (`url=""`) from page-level findings (`url` set)
2. **Site-level penalty**: sum of `config.penalty_for(severity)` for all site-level findings (applied once)
3. **Page-level penalty**:
   - Group page-level findings by URL
   - Per-page: deduplicate by `finding_type` keeping the max severity penalty per type
   - Compute per-page penalty sum
   - Mean across ALL crawled pages (unaffected pages contribute 0): `mean_page_penalty = sum(page_penalties) / max(1, pages_crawled)`
4. **Total penalty**: `site_penalty + mean_page_penalty`
5. **Raw score**: `clamp(100.0 - total_penalty, 0.0, 100.0)`
6. **Weighted score**: `raw_score × dimension_weight`

**Overall score:** `sum(ds.weighted_score for ds in dimension_scores)`, clamped to [0, 100], rounded to 2 decimal places.

**Grade thresholds:** A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 40, F < 40

**Default severity penalties:**
```python
{"critical": 10.0, "high": 5.0, "medium": 2.0, "low": 1.0, "info": 0.0}
```

**Functions:**
```python
def compute_dimension_score(dimension, findings, config=DEFAULT_AUDIT_CONFIG, pages_crawled=1) -> DimensionScore
def compute_all_dimension_scores(findings, config=DEFAULT_AUDIT_CONFIG, pages_crawled=1) -> list[DimensionScore]
def compute_overall_score(dimension_scores) -> float
def compute_grade(overall_score, config=DEFAULT_AUDIT_CONFIG) -> str
```

`DimensionScore` output includes: dimension, score, weight, weighted_score, finding_count, and per-severity counts (critical_count, high_count, medium_count, low_count, info_count).

### 4a.10 Configuration

**File:** `core/site_audit/config.py`

`AuditConfig` — frozen dataclass (`@dataclass(frozen=True)`, thread-safe):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dimension_weights` | `dict[str, float]` | 8 dimensions summing to 1.0 | Relative weight per dimension |
| `grade_thresholds` | `dict[str, float]` | `{"A": 90.0, "B": 75.0, "C": 60.0, "D": 40.0}` | Minimum score per grade |
| `severity_penalties` | `dict[str, float]` | `{"critical": 10.0, ...}` | Score deduction per finding |
| `title_min_length` | `int` | 30 | Minimum `<title>` length (chars) |
| `title_max_length` | `int` | 60 | Maximum `<title>` length (chars) |
| `meta_min_length` | `int` | 120 | Minimum meta description length |
| `meta_max_length` | `int` | 160 | Maximum meta description length |
| `page_analysis_concurrency` | `int` | 30 | Max concurrent page-analysis tasks |
| `request_timeout` | `float` | 15.0 | Per-request HTTP timeout (seconds) |
| `max_redirects` | `int` | 5 | Max redirect hops before marking broken |
| `aeo_min_question_heading_ratio` | `float` | 0.3 | Minimum fraction of question headings |
| `aeo_ideal_paragraph_word_count_min` | `int` | 20 | Lower bound of ideal paragraph range |
| `aeo_ideal_paragraph_word_count_max` | `int` | 80 | Upper bound of ideal paragraph range |
| `aeo_quick_answer_min_words` | `int` | 15 | Min words for quick-answer hook |
| `aeo_quick_answer_max_words` | `int` | 150 | Max words for quick-answer hook |

**Post-init validation** (`__post_init__`, 8 invariant checks):
1. Dimension weights must sum to 1.0 (tolerance ±0.01)
2. Required grades A/B/C/D must be present
3. Grade thresholds must be monotonically decreasing (A ≥ B ≥ C ≥ D)
4. `title_min_length ≤ title_max_length`
5. `meta_min_length ≤ meta_max_length`
6. All severity penalties ≥ 0
7. `aeo_min_question_heading_ratio` in [0.0, 1.0]
8. `aeo_ideal_paragraph_word_count_min ≤ aeo_ideal_paragraph_word_count_max`

**Module-level assertion**: `DEFAULT_DIMENSION_WEIGHTS` sum checked at import time (tolerance 1e-9).

**Methods:**
- `weight_sum() -> float` — returns sum of dimension weights (useful for testing)
- `grade_for_score(score) -> str` — derive letter grade from score
- `penalty_for(severity) -> float` — get deduction for severity string (0.0 for unrecognised)

`DEFAULT_AUDIT_CONFIG: AuditConfig = AuditConfig()` — module-level singleton used by all pipeline functions.

### 4a.11 Pydantic Models

**File:** `core/models/site_audit.py`

**Enums:**
- `AuditDimension(str, Enum)`: crawlability, performance, on_page_seo, extractability, schema_markup, eeat, freshness, security
- `AuditCheckSeverity(str, Enum)`: critical, high, medium, low, info

**Input model:**
- `SiteAuditInput`: company_name (required), domain (required), company_slug (auto-derived via `model_validator(mode="before")`), product_slug (validated: `^[a-z0-9][a-z0-9-]*$`), max_pages=200, max_depth=4, check_core_web_vitals=True, check_schema_validation=True, check_ai_bot_access=True

**Per-finding model:**
- `AuditFinding`: finding_type, dimension, severity, message, recommendation, url (empty=site-level), details (dict)

**Per-page sub-results:**
- `SchemaDetectionResult`: has_schema, schema_types (list), raw_jsonld_blocks (list), validation_errors (list), inferred_page_type
- `AEOReadinessResult`: snippet_readiness_score (0–100), question_heading_ratio, quick_answer_hook_count, self_contained_paragraph_ratio, avg_paragraph_word_count, content_patterns (dict[str, bool])

**Per-page comprehensive result:**
- `PageAuditResult`: 30+ fields grouped by HTTP metadata, on-page SEO, images, links, content, technical SEO, security, freshness/authority. Includes `schema_result: SchemaDetectionResult` (aliased as `"schema"`), `aeo: AEOReadinessResult`, `findings: list[AuditFinding]`. Config: `populate_by_name = True`.

**Site-level aggregated results:**
- `AIBotAccessResult`: 5 per-bot boolean fields (gptbot_allowed, claudebot_allowed, perplexitybot_allowed, google_extended_allowed, ccbot_allowed), has_llms_txt, robots_txt_exists, crawl_delay_seconds (float | None)
- `SitemapHealthResult`: has_sitemap, sitemap_url_count, sitemap_urls (list), sitemap_errors (list), has_sitemap_index
- `DimensionScore`: dimension, score (0–100), weight, weighted_score, finding_count, per-severity counts (critical/high/medium/low/info)
- `SiteAuditResult`: 26 fields — audit_id, domain, overall_score, grade, pages_crawled, pages_discovered, duration_seconds, dimension_scores, ai_bot_access, sitemap_health, page_results, total_findings, findings_by_severity, findings_by_dimension, top_findings, avg_snippet_readiness, pages_with_schema, avg_question_heading_ratio, started_at, completed_at, status (pending/running/completed/failed/degraded), error_message, failed_steps (list[int]), degraded_dimensions (list[str])

All fields have defaults for backward compatibility with existing JSON artefacts.

### 4a.12 Pipeline Orchestration Details

**File:** `core/site_audit/pipeline.py`

`run_site_audit()` orchestrates all 6 steps sequentially:
- Generates `audit_id` (UUID), records `started_at` and wall-clock `t0`
- Each step is independently skippable via `skip_steps`
- Progress callbacks via `_emit(on_progress, message)` — safely catches callback exceptions
- Steps 3–4 run per-page in the pipeline loop: iterate over `page_results`, fetch HTML from `html_map`, run detection, extend page findings. Per-page failures are counted; if ALL pages fail for a step, the step is marked as failed
- After step 5, checks for failed steps: computes degraded dimensions, zeros their scores, recomputes overall score and grade
- After aggregation, generates crawl-delay findings from `ai_bot_access.crawl_delay_seconds`
- Step 6 writes report to `output_dir` (async)
- Finalises `completed_at`, `duration_seconds`, logs completion

### 4a.13 API Endpoints

**Router:** `api/routers/site_audit.py` (registered at `/api/v1/site-audit/` and `/api/v1/companies/{slug}/audits/`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/site-audit/start` | Launch site audit (202 Accepted) |
| `GET` | `/api/v1/site-audit/{run_id}/status` | Poll audit status |
| `GET` | `/api/v1/companies/{slug}/audits` | List audits for company |
| `GET` | `/api/v1/companies/{slug}/audits/{audit_id}` | Get audit detail |
| `GET` | `/api/v1/companies/{slug}/audits/{audit_id}/findings` | Get audit findings |
| `GET` | `/api/v1/companies/{slug}/audits/{audit_id}/pages` | Get page-level results |

**Service:** `SiteAuditDataServiceProtocol` (runtime_checkable Protocol) + `JsonSiteAuditDataService` (filesystem-backed, FIFO cache)

**Repository:** `SiteAuditRepository` in `core/db/repositories/site_audit_repo.py` (flush-only contract)

### 4a.14 P3 Bug Fixes & Improvements (Sprint: site-audit-p3-bugfixes)

82 tests added (793 total site audit tests). Key fixes:

1. **Config validation** (`config.py`): Added `__post_init__` with 8 invariant checks — weight sum, required grades, monotonic grade thresholds, title/meta length bounds, non-negative penalties, AEO ratio range, AEO paragraph word count bounds. Prevents invalid configurations from silently producing wrong scores.

2. **dateutil parsing** (`eeat_signals.py`): Replaced naive `datetime.fromisoformat()` with robust `_parse_date_robust()` — ISO 8601 first via `dateutil.parser.isoparse()`, then `dateutil.parser.parse(fuzzy=False)` fallback. Added `_MAX_DATE_STR_LENGTH = 100` guard against DoS via fuzzy parser. Catches `OverflowError` in addition to `ValueError`/`TypeError`. Normalises timezone-naive datetimes to UTC.

3. **Canonical URL deduplication** (`s1_discover.py`): Added `canonical_url()` function that applies all `normalize_url()` transformations PLUS sorts query parameters via `parse_qsl()`/`urlencode(sorted(...))`. BFS enqueue, visited set, and link extraction all use `canonical_url()` as the dedup key, preventing duplicate crawls of URLs differing only in query parameter order.

4. **Crawl-delay handling** (`s1_discover.py` + `pipeline.py`): Added `_parse_crawl_delay()` with regex extraction, `_MAX_CRAWL_DELAY = 300.0` cap, and `float | None` return. Added `crawl_delay_seconds` field to `AIBotAccessResult`. Pipeline generates crawl-delay findings: `>30s` = medium severity (`crawl_delay_excessive`), `>10s` = info severity (`crawl_delay_high`).

5. **Schema validators** (`schema_checks.py`): Added `validate_product_schema()` (name + offers/price validation, 4 recommended field warnings), `validate_speakable_schema()` (cssSelector/xpath requirement), and enhanced `validate_breadcrumb_schema()` to handle nested `item.name` in addition to direct `name` field. Added Product and Speakable/SpeakableSpecification to `KNOWN_SCHEMA_TYPES` and `validate_schema_block()` dispatch.

6. **AEO improvements** (`extractability.py` + `s4_check_aeo.py`): Extended question heading detection with wh-word headings without trailing `?` (core wh-words only, ≥4 words). Added comparison pattern detection (vs, versus, compared to, difference between, pros and cons). Enhanced definition opening detector with continuation word validation, non-topic-starter rejection, and hyphenated compound term support. Made quick-answer hook configurable via `config.aeo_quick_answer_min_words`/`max_words` (default 15–150). Added heading-bounded search (stops at next h1–h6). Added container search (div/section/article inner `<p>` scanning).

---

## 4b. Daily LLM Visibility Tracker

### 4b.1 Overview & Architecture

The Daily LLM Visibility Tracker monitors brand visibility across AI platforms (ChatGPT, Claude, Gemini, Perplexity). It runs tracked prompts against each platform daily, detects brand mentions and citations in responses, and computes analytics (mention rate, share of voice, citation rate, trends).

**Key characteristics:**
- Reuses existing gap analysis search engines via an **adapter pattern** — zero code duplication
- All metric computation is **100% deterministic** — no LLM calls in the analytics path
- The only LLM calls happen in the platform runner (via existing gap engines)
- Modular architecture with Mediator and Strategy patterns

**Location:** `core/daily_tracker/` (business logic), `api/routers/daily_tracker.py` (API), `core/models/daily_tracker.py` (Pydantic), `core/db/models/daily_tracker.py` (ORM)

### 4b.2 Module Architecture — Design Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **Mediator** | `DailyTrackerOrchestrator` | Modules never talk to each other directly. Adding a new module (e.g., notifications) requires changes only in the orchestrator. |
| **Strategy** | `MetricCalculator` ABC + registry | Each metric is a subclass. New metrics never modify existing calculator code (Open/Closed Principle). |
| **Adapter** | `PlatformRunnerService` | Wraps existing gap analysis `SearchEngine` implementations. Imports `from core.gap_analysis.engines.openai_engine import OpenAIEngine` etc. |
| **Protocol** | 5 `@runtime_checkable` Protocols | Decouples interfaces from implementations. Enables test mocking and future DB-backed swaps. |

### 4b.3 Protocol Interfaces

All protocols are `@runtime_checkable` and defined in `core/daily_tracker/protocols.py`:

| Protocol | Methods | Implementor |
|----------|---------|-------------|
| `PromptLibraryServiceProtocol` | `create_prompt`, `get_prompt`, `list_prompts`, `update_prompt`, `delete_prompt`, `toggle_prompt`, `import_from_gap_analysis`, `bulk_create` | `PromptLibraryService` |
| `PlatformRunnerServiceProtocol` | `run_prompts` | `PlatformRunnerService` |
| `MentionDetectorProtocol` | `detect_mentions` | `MentionDetector` |
| `AnalyticsServiceProtocol` | `compute_visibility_metrics`, `compute_mention_rate_trend`, `compute_share_of_voice`, `compute_citation_rate`, `get_competitor_metrics` | `AnalyticsService` |
| `DailyTrackerOrchestratorProtocol` | `execute_daily_run`, `get_run_status` | `DailyTrackerOrchestrator` |

### 4b.4 Orchestrator (Mediator)

**File:** `core/daily_tracker/orchestrator.py`

The orchestrator coordinates the full daily run pipeline without modules talking directly to each other.

**Pipeline flow:**
1. **Fetch prompts** — specific IDs via `get_prompt()` or all active via `list_prompts(company_id, filters=None)`
2. **Run prompts across platforms** — delegates to `PlatformRunnerService.run_prompts()` which returns `DailyRunResult` with `PlatformResponse` objects
3. **Detect mentions** — for each response, calls `MentionDetector.detect_mentions(text, brand, competitors)` (sync, regex-based)
4. **Assemble result** — builds `DailyRunResult` with enriched responses and `_mention_analyses` attached as index-aligned list

**Key design decisions:**
- **Stateless** — does not cache run results or own DB dependencies. The API layer handles persistence.
- **Error isolation** — catches all exceptions and returns `RunStatus.FAILED` with error message (never re-raises).
- **`_mention_analyses`** attached as a separate attribute (not part of `PlatformResponse`) to avoid modifying models owned by other modules.

### 4b.5 Prompt Library Service

**File:** `core/daily_tracker/prompt_library.py`

CRUD operations for tracked prompts. Each prompt belongs to a company, has text/category/tags, an active flag, and a source (`manual`, `gap_analysis`, `custom`).

**Key operations:**
- `create_prompt(company_id, text, category, tags)` — dedup by text within company
- `import_from_gap_analysis(company_id, slug)` — reads `artifacts/gap_analysis/{slug}/queries.json`, imports as tracked prompts
- `bulk_create(company_id, prompt_dicts)` — skips duplicates

### 4b.6 Platform Runner Service (Adapter)

**File:** `core/daily_tracker/platform_runner.py`

Adapter pattern wrapping existing gap analysis search engines. Imports engines directly:
```python
from core.gap_analysis.engines.openai_engine import OpenAIEngine
from core.gap_analysis.engines.claude_engine import ClaudeEngine
from core.gap_analysis.engines.gemini_engine import GeminiEngine
from core.gap_analysis.engines.perplexity_engine import PerplexityEngine
```

Converts `TrackedPrompt` → engine-compatible format, runs with semaphore concurrency control, and assembles `DailyRunResult` with `PlatformResponse` objects.

### 4b.7 Mention Detector

**File:** `core/daily_tracker/mention_detector.py`

Regex-based brand mention detection. 100% deterministic, no LLM calls, sub-millisecond latency.

Returns `MentionAnalysis` with:
- `brand_mentioned: bool`, `brand_mention_count: int`
- `competitor_mentions: dict[str, int]`
- `citations: list[str]` (extracted URLs)
- `citation_rank: int | None` (position of first brand citation)

### 4b.8 Analytics Engine & Metric Calculators

**File:** `core/daily_tracker/analytics_engine.py`

Uses the **Strategy pattern** via `MetricCalculator` ABC (`core/daily_tracker/metrics/base.py`).

**4 metric calculators** (registered in `METRIC_REGISTRY`):
| Calculator | File | Output |
|------------|------|--------|
| `MentionRateCalculator` | `metrics/mention_rate.py` | `VisibilityMetrics.mention_rate` |
| `ShareOfVoiceCalculator` | `metrics/share_of_voice.py` | `dict[str, float]` brand vs competitors |
| `CitationRateCalculator` | `metrics/citation_rate.py` | Citation rate with domain breakdown |
| `TrendCalculator` | `metrics/trend.py` | `list[TrendDataPoint]` over time |

**Data provider:** `AnalyticsService` uses a `ResponseDataProvider` protocol (defined in `analytics_engine.py`) decoupled from DB repos. The DI layer bridges via `_DbResponseDataProvider` adapter in `api/dependencies.py`.

### 4b.9 API Endpoints (16 Total)

**Router:** `api/routers/daily_tracker.py` — prefix `/api/v1/daily-tracker`

#### Prompt Library (8 endpoints)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/prompts` | member/superuser | Create tracked prompt (201) |
| `GET` | `/prompts` | any auth | List with filters (category, source, active, search, tags) |
| `GET` | `/prompts/{prompt_id}` | any auth | Get specific prompt |
| `PUT` | `/prompts/{prompt_id}` | member/superuser | Update prompt fields |
| `DELETE` | `/prompts/{prompt_id}` | member/superuser | Delete prompt (204) |
| `PATCH` | `/prompts/{prompt_id}/toggle` | member/superuser | Toggle active/inactive |
| `POST` | `/prompts/import` | member/superuser | Import from gap analysis queries (201) |
| `POST` | `/prompts/bulk` | member/superuser | Bulk create prompts (201) |

#### Run Management (3 endpoints)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/runs` | member/superuser | Trigger daily run (202) |
| `GET` | `/runs/{run_id}` | any auth | Get run status |
| `GET` | `/runs` | any auth | List runs for company |

#### Analytics (5 endpoints)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/analytics/visibility` | any auth | Overall visibility metrics |
| `GET` | `/analytics/mention-trend` | any auth | Mention rate over time (`?days=30`) |
| `GET` | `/analytics/sov` | any auth | Share of voice vs competitors |
| `GET` | `/analytics/citations` | any auth | Citation rates with domain breakdown |
| `GET` | `/analytics/competitors` | any auth | Per-competitor metrics |

**Tenant isolation:** All endpoints use `_get_company_id(request)` which extracts `company_slug` from `request.state` (set by auth middleware).

### 4b.10 DI Wiring

**File:** `api/dependencies.py` (APPEND ONLY — 3 factory functions added)

| Factory | Returns | Fallback |
|---------|---------|----------|
| `get_prompt_library_service(request)` | `PromptLibraryService` | Checks `app.state.prompt_library_service` override, then builds from `db_session_factory`. 503 if neither available. |
| `get_analytics_service(request)` | `AnalyticsService` | Checks `app.state.analytics_service` override, then builds with `_DbResponseDataProvider`. 503 if no DB. |
| `get_daily_tracker_orchestrator(request)` | `DailyTrackerOrchestrator` | Wires `PromptLibraryService` + `PlatformRunnerService` + `MentionDetector`. 503 if no DB. |

**`_DbResponseDataProvider`** — adapter class in `api/dependencies.py` bridging `DailyRunResponseRepository` to the `ResponseDataProvider` protocol used by `AnalyticsService`.

**Test injection:** Tests set `app.state.prompt_library_service`, `app.state.analytics_service`, `app.state.orchestrator` to mock objects. DI functions check these first before building real services.

### 4b.11 Pydantic Models

**File:** `core/models/daily_tracker.py`

| Model | Purpose |
|-------|---------|
| `TrackedPrompt` | Prompt with company_id, text, category, tags, active, source |
| `PromptSource` | Enum: `manual`, `gap_analysis`, `custom` |
| `PromptLibraryFilter` | Filter for list queries (category, tags, active, source, search) |
| `DailyRunConfig` | Run configuration (engines, prompts, concurrency) |
| `PlatformResponse` | Single response: prompt_id, engine, response_text, latency_ms |
| `MentionAnalysis` | Detection result: brand_mentioned, counts, citations, rank |
| `DailyRunResult` | Full run result: run_id, status, responses, timestamps |
| `RunStatus` | Enum: `pending`, `running`, `completed`, `failed` |
| `VisibilityMetrics` | Aggregate metrics: mention_rate, citation_rate, avg_position |
| `TrendDataPoint` | Time-series point: date, mention_rate, citation_rate |
| `CompetitorMetrics` | Per-competitor: name, mention_rate, avg_position |

### 4b.12 ORM & Database

**File:** `core/db/models/daily_tracker.py`

3 ORM tables:
| Table | Purpose |
|-------|---------|
| `TrackedPromptModel` | Persists tracked prompts with company_id, text, metadata |
| `DailyRunModel` | Run records with status, timestamps, config |
| `DailyRunResponseModel` | Individual responses with mention analysis results |

**Repositories** (`core/db/repositories/daily_tracker_repo.py`):
- `TrackedPromptRepository` — CRUD + filtering
- `DailyRunRepository` — Run lifecycle
- `DailyRunResponseRepository` — Response storage + analytics queries

**Migration:** `core/db/migrations/versions/0005_daily_tracker.py`

---

## 5. Pipeline 1: Research Artifacts (REMOVED)

> **This section documents the old DeepAgents-based research pipeline which has been fully removed.**
> It was replaced by three new pipelines: Knowledge Base (§5c), Audience Persona (§5d), and Voice Style Guide (§5e).
> The old code, models (`core/models/artifacts.py`, `core/models/style_guide.py`), agents (`core/research/agents/`),
> graphs (`core/research/graphs/`), API router (`api/routers/research.py`), and CLI scripts were deleted.
> The `deepagents` dependency was also removed.

<details>
<summary>Historical reference (collapsed — old pipeline architecture)</summary>

### Overview (Historical)

The Research Artifacts Pipeline produced three foundational documents that fed into all downstream systems. Each stage used a DeepAgent (LLM with tools) orchestrated by a LangGraph state machine with human-in-the-loop approval.

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

</details>

---

## 5c. Knowledge Base Pipeline (Pipeline 1a)

The Knowledge Base replaces the monolithic Research Artifacts pipeline (§5) with a **3-layer architecture** of specialist research agents, versioned documents, and synthesized Company Profiles. Built across Phases 1-5 (2026-03-05/06) with **260 tests** (214 core + 46 API).

**Files:** `core/models/knowledge_base.py` (17 Pydantic models, 288 lines), `core/research/knowledge_base/` (5 modules: storage, agents, pipeline, graph, tools), `core/research/prompts/*.py` (6 prompt files), `api/routers/knowledge_base.py`, `api/schemas/common.py`

### 5c.1 Architecture -- 3-Layer Knowledge Base

```
Layer 1 (Raw Inputs):     Ephemeral -- Perplexity/Claude research outputs (not persisted)
                          Raw LLM outputs from each specialist agent
Layer 2 (Knowledge Base): 5 typed, versioned docs:
                            company_overview    -- Company positioning, products, market
                            customer_reviews    -- User sentiment, themes, quotes
                            competitor_registry -- Competitive landscape, market map
                            weakness_analysis   -- Competitor weaknesses + opportunities
                            brand_perception    -- Market position, strengths, challenges
Layer 3 (Company Profile): Synthesized artifact at artifacts/company_context/{slug}.md
                           Single comprehensive document combining all L2 intelligence
                           Promoted ONLY after HITL-3 approve
```

**Design principle:** Layer 1 is ephemeral (never persisted). Layer 2 is versioned and immutable (each version is a snapshot). Layer 3 is the single source of truth consumed by downstream pipelines (Gap Analysis, Content Engine).

### 5c.2 DAG Execution & 3 HITL Checkpoints

**Pipeline entry:**
```python
async def run_knowledge_base_pipeline(
    input_data: KnowledgeBaseInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> KnowledgeBaseOutput
```

**File:** `core/research/knowledge_base/pipeline.py` (~639 lines)

**DAG execution order:**
```
Phase 1 (parallel):   company_overview + customer_reviews
                      (both are root nodes -- no dependencies)
Phase 2 (sequential): competitor_scanner
                      (needs company_overview_md from Phase 1)
-- HITL-1: review 3 docs (company_overview, customer_reviews, competitor_registry) --
Phase 3 (parallel):   weakness_analyst + brand_perception
                      (weakness needs overview + competitor; brand needs overview + reviews + competitor)
-- HITL-2: review 2 docs (weakness_analysis, brand_perception) --
Phase 4 (sequential): synthesis agent
                      (reads ALL L2 docs -> produces L3 Company Profile)
-- HITL-3: review synthesis --
DONE -> promote company_context/{slug}.md (ONLY on HITL-3 approve)
```

**3 execution modes** (resolved by `_resolve_mode(input_data, storage)`):

| Mode | Trigger | Agents Run | HITL | Synthesis |
|------|---------|------------|------|-----------|
| `full` | No `refresh_docs` specified | All 5 L2 agents | All 3 checkpoints | Full synthesis |
| `refresh` | `refresh_docs` has 2+ types | Only specified agents | All 3 checkpoints | Delta synthesis (if prior exists) |
| `single` | `refresh_docs` has exactly 1 type | One agent only | Skipped | Skipped |

**Mode resolution logic:**
```python
def _resolve_mode(input_data, storage) -> Tuple[str, List[KBDocType]]:
    if input_data.refresh_docs:
        if len(input_data.refresh_docs) == 1:
            return "single", list(input_data.refresh_docs)
        return "refresh", list(input_data.refresh_docs)
    return "full", list(L2_DOC_TYPES)
```

**Slug resolution** (`_resolve_slug(input_data)`): Uses `input_data.company_slug` if set, otherwise derives from `company_name` via lowercasing + regex cleanup (remove non-alphanumeric, replace spaces with hyphens).

**HITL pattern: Pipeline-with-inline-HITL** (not a monolithic graph). The pipeline owns DAG execution and calls HITL checkpoints as inline async pauses. Two LangGraph mini-graphs (`build_kb_doc_review_graph`, `build_kb_synthesis_review_graph`) handle the pause/resume mechanics. `run_kb_hitl_checkpoint()` is the async helper that invokes a graph, detects `__interrupt__` in the result dict (LangGraph >=1.0 model), waits for human input via TaskStore, and resumes the graph.

**Auto-approve:** `input_data.auto_approve_checkpoints: List[int]` specifies which checkpoints (1, 2, 3) should be auto-approved. The auto_approve flag is passed into the HITL state dict.

**HITL decision handling (all 3 checkpoints):**

| Decision | Action |
|----------|--------|
| `approve` | Continue to next phase |
| `revise` | Re-run affected agents with `revision_note` appended to prompt. `revision_notes` is a dict mapping `doc_type.value -> note_text`. Each revised agent receives `revision_note=note` parameter. |
| `reject` | Build partial `KnowledgeBaseOutput` and return immediately. Pipeline terminates cleanly with whatever results exist. |

**Revision flow detail:**
1. Pipeline receives `revision_notes: Dict[str, str]` from HITL result
2. For each `doc_type_str, note` in revision_notes:
   - Validate `doc_type_str` is a valid `KBDocType` (skip with warning if not)
   - Validate doc_type is in the current checkpoint scope (skip if not)
   - Call `_run_single_agent(input_data, dt, storage, results, trace_span, revision_note=note)`
   - Re-write version to storage if no error
   - Add to `changed_doc_types` if not already present

**Staleness propagation:** After all agents complete (before synthesis), the pipeline calls `storage.propagate_staleness(changed_doc_types)` to mark downstream docs as stale via reverse DAG BFS.

**SSE events emitted:**
- `pipeline_start` — at pipeline beginning
- `kb_phase_start` — at each phase (1-4) with agent list
- `kb_agent_complete` — after each agent with word_count, has_error
- `kb_phase_complete` — after each phase
- `completed` / `failed` — terminal events

**Task store updates:** `current_step` updated at each phase transition (`initializing`, `phase_1`, `phase_2`, `phase_3`, `phase_4_synthesis`).

### 5c.3 6 Specialist Agents

**File:** `core/research/knowledge_base/agents.py` (~526 lines)

**Three tiers** based on research capability:

**Tier 1 -- Perplexity Deep Research (Agents 1-4):**

All four share a common runner `_run_perplexity_agent()` that:
1. Creates a LangSmith span via `create_span()`
2. Calls `perplexity_client.research(query=full_prompt)` via `asyncio.to_thread()` + `asyncio.wait_for(timeout_s)`
3. Logs generation to LangSmith
4. Returns `KBAgentResult` with content_md, word_count, execution_time_s
5. Catches `asyncio.TimeoutError` and general exceptions -> returns `KBAgentResult(error=...)`

Each agent function builds its prompt by combining system prompt (from `get_*_system_prompt()`) + user prompt (from `build_*_user_prompt()`) with a `\n\n` separator:

| Agent | Function | Upstream Dependencies | Default Timeout |
|-------|----------|----------------------|-----------------|
| Company Overview | `run_company_overview_agent(input_data, parent_span, timeout_s=300, revision_note)` | None (root) | 300s |
| Customer Reviews | `run_customer_reviews_agent(input_data, parent_span, timeout_s=300, revision_note)` | None (root) | 300s |
| Competitor Scanner | `run_competitor_scanner_agent(input_data, company_overview_md, parent_span, timeout_s=300, revision_note)` | `company_overview_md` | 300s |
| Weakness Analyst | `run_weakness_analyst_agent(input_data, company_overview_md, competitor_registry_md, parent_span, timeout_s=300, revision_note)` | `company_overview_md`, `competitor_registry_md` | 300s |

**Tier 2 -- Anthropic SDK + Native Web Search (Agent 5: Brand Perception):**

```python
async def run_brand_perception_agent(
    input_data: KnowledgeBaseInput,
    upstream_docs: Dict[str, str],     # Up to 4 upstream L2 docs
    parent_span, timeout_s=300.0,
    max_web_searches=10,               # Server-side web search cap
    revision_note=None,
) -> KBAgentResult
```

Uses `anthropic.AsyncAnthropic` with the `web_search_20250305` server-side tool:
```python
tool_spec = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": max_web_searches,
}
```

**Pause-turn loop handling:** Anthropic's server-side web_search tool can trigger `pause_turn` when the model hits its internal iteration limit. The agent handles this with a bounded continuation loop:
```python
_MAX_PAUSE_TURNS = 5
while response.stop_reason == "pause_turn":
    pause_turns += 1
    if pause_turns >= _MAX_PAUSE_TURNS:
        break  # Accept partial result
    messages.append({"role": "assistant", "content": response.content})
    response = await client.messages.create(...)
```
If `pause_turns >= _MAX_PAUSE_TURNS`, the result is marked `is_partial=True`.

**Text extraction:** `_extract_text_with_citations(response)` filters response content blocks, keeping only `type="text"` blocks (filtering out `server_tool_use`, etc.), and joins with `\n\n`.

**Model:** `settings.research_kb_brand_perception_model` (configurable, default Claude model)
**Max tokens:** 8192 per call

**Tier 3 -- LangGraph Synthesis Agent (Agent 6):**

```python
async def run_synthesis_agent(
    input_data: KnowledgeBaseInput,
    kb_base_dir: Path,                          # Root for read_file tool
    available_docs: Dict[str, str],             # doc_type.value -> file path
    missing_docs: List[str],                    # Missing doc_type.value strings
    parent_span, timeout_s=600.0,
    revision_note=None,
    delta_mode: bool = False,                   # Incremental synthesis
    changed_docs: Optional[Dict[str, str]] = None,
    previous_synthesis_path: Optional[str] = None,
) -> KBAgentResult
```

**Architecture:** Uses `langgraph.prebuilt.create_react_agent` with a LangChain chat model + a custom `read_file` tool. The synthesis agent can read any file within the KB directory via the tool.

**Partial failure policy (CX-14):** Requires minimum 3 of 5 L2 docs to proceed. If fewer than 3 available, returns error immediately.

**Delta mode validation:** If `delta_mode=True` but `previous_synthesis_path` is None, returns error.

**Model building:** `_build_model(settings.research_kb_synthesis_model)` handles three format strings:
- `"anthropic:claude-opus-4-6"` (colon separator)
- `"anthropic/claude-opus-4-6"` (slash separator)
- `"gpt-4o"` (bare model name -- provider inferred)

Injects API keys from settings (not relying on env vars) for Anthropic, OpenAI, and Google providers.

**Synthesis output extraction:** `_extract_synthesis_output(messages)` iterates messages in reverse, finds the last AI message, and extracts text from either string content or list-of-dicts content blocks.

### 5c.4 Prompt System -- 6 Prompt Files with Hub Fallback

**Files:** `core/research/prompts/` (6 files: `company_overview.py`, `customer_reviews.py`, `competitor_scanner.py`, `weakness_analyst.py`, `brand_perception.py`, `synthesis.py`)

Each prompt file follows the **Hub-with-local-fallback pattern:**
- `get_*_system_prompt() -> str` -- calls `get_prompt(HUB_NAME, LOCAL_FALLBACK)` from the prompt registry
- `build_*_user_prompt(input_data, ..., revision_note=None) -> str` -- constructs the user message

**Revision note injection:** All `build_*_user_prompt()` functions accept an optional `revision_note: str`. When provided, a section is appended:
```
## Reviewer Feedback
{revision_note}
```

**Upstream context injection:** Agents that depend on upstream docs receive the full markdown of those docs in their user prompt. For example:
- `build_competitor_scanner_user_prompt(input_data, company_overview_md, revision_note)` -- includes company overview
- `build_weakness_analyst_user_prompt(input_data, company_overview_md, competitor_registry_md, revision_note)` -- includes overview + competitor data
- `build_brand_perception_user_prompt(input_data, upstream_docs, revision_note)` -- includes up to 4 upstream docs

**Synthesis prompts (special):**
- `get_synthesis_system_prompt()` -- Full synthesis: combine all L2 docs into comprehensive Company Profile
- `get_delta_synthesis_system_prompt()` -- Delta synthesis: update existing profile based on changed docs only
- `build_synthesis_user_prompt(input_data, available_docs, missing_docs, revision_note)` -- Lists file paths for `read_file` tool
- `build_delta_synthesis_user_prompt(input_data, previous_synthesis_path, changed_docs, unchanged_docs, missing_docs, revision_note)` -- Provides previous synthesis path + changed-only file paths

### 5c.5 KBStorage -- Versioned Filesystem Store

**File:** `core/research/knowledge_base/storage.py` (~509 lines)

**Class:** `KBStorage(artifacts_root: Path, slug: str)`

**Filesystem layout:**
```
artifacts/knowledge_base/{slug}/
    _manifest.json                  # KBManifest (versions, timestamps, synthesis metadata)
    company_overview/
        v1.md                       # Version 1 markdown
        v1.json                     # Version 1 structured JSON sidecar (optional)
        v2.md                       # Version 2 (after revision)
    customer_reviews/
        v1.md, v1.json
    competitor_registry/
        v1.md, v1.json
    weakness_analysis/
        v1.md, v1.json
    brand_perception/
        v1.md, v1.json
    synthesis/
        v1.md                       # Synthesis versions (no JSON sidecar)
```

**Manifest operations:**
- `read_manifest() -> KBManifest` -- Returns blank manifest if file doesn't exist or is corrupt
- `write_manifest(manifest)` -- **Atomic write** via `tempfile.mkstemp()` + `os.replace()`. Creates temp file in same directory, writes content, then atomic rename. Cleans up temp file on failure via `os.unlink()` in except block.

**Version operations:**
- `write_version(doc_type, content_md, content_json=None) -> int`:
  1. Reads manifest to determine next version number (`entry.current_version + 1`, or 1 if new)
  2. Creates doc type directory (`mkdir(parents=True, exist_ok=True)`)
  3. Writes `v{N}.md` file
  4. Writes `v{N}.json` sidecar if `content_json` provided
  5. Computes SHA-256 hash and word count
  6. Updates manifest entry with: doc_type, current_version, last_updated (UTC now), staleness_days (from `KB_DEFAULT_STALENESS_DAYS`), status="fresh", dependencies (from `KB_DEPENDENCY_GRAPH`)
  7. Persists manifest **last** (atomicity -- if write fails, manifest is unchanged)
  8. Returns version number

- `read_version(doc_type, version) -> Optional[KBDocVersion]` -- Reads markdown + optional JSON sidecar, computes SHA-256
- `get_latest_version(doc_type) -> Optional[KBDocVersion]` -- Reads current_version from manifest, then reads that version
- `get_all_latest() -> Dict[KBDocType, Optional[KBDocVersion]]` -- Reads latest of every L2 doc type

**Synthesis operations:**
- `write_synthesis(content_md) -> int` -- Writes `synthesis/v{N}.md`, updates manifest `synthesis_version` and `synthesis_last_updated`
- `read_synthesis(version=None) -> Optional[KBDocVersion]` -- Reads synthesis by version (latest if None)

**Staleness checking:**
- `check_staleness(doc_type, threshold_days=30) -> bool` -- Returns True if doc is missing, has no `last_updated`, or age exceeds threshold

### 5c.6 Staleness Tracking & Propagation

**DAG dependency graph** (`KB_DEPENDENCY_GRAPH` constant in `core/models/knowledge_base.py`):
```python
KB_DEPENDENCY_GRAPH: Dict[KBDocType, List[KBDocType]] = {
    COMPANY_OVERVIEW: [],                                      # Root node
    CUSTOMER_REVIEWS: [],                                      # Root node
    COMPETITOR_REGISTRY: [COMPANY_OVERVIEW],                   # Depends on overview
    WEAKNESS_ANALYSIS: [COMPANY_OVERVIEW, COMPETITOR_REGISTRY],# Depends on 2
    BRAND_PERCEPTION: [COMPANY_OVERVIEW, CUSTOMER_REVIEWS,     # Depends on 3
                       COMPETITOR_REGISTRY],
}
```

**Note:** `weakness_analysis` and `brand_perception` run in parallel (Phase 3), but `brand_perception` uses the *previous* version of `weakness_analysis` from storage. Listed as a data dependency for staleness purposes.

**Per-doc staleness thresholds** (`KB_DEFAULT_STALENESS_DAYS`):

| Doc Type | Threshold | Rationale |
|----------|-----------|-----------|
| `company_overview` | 90 days | Company fundamentals change slowly |
| `customer_reviews` | 30 days | Reviews appear frequently |
| `competitor_registry` | 90 days | Market structure is stable |
| `weakness_analysis` | 60 days | Competitive dynamics shift moderately |
| `brand_perception` | 45 days | Brand perception shifts with reviews + news |

**`get_staleness_report(threshold_override=None) -> KBHealthReport`:**

For each L2 doc type, determines health status:
1. **Missing:** No manifest entry or `current_version == 0`
2. **Age-based staleness:** `(now - last_updated).days > threshold`
3. **Upstream-changed staleness:** Any upstream dependency's `last_updated` is newer than this doc's `last_updated`

Synthesis freshness: needs refresh if any L2 doc was updated after `synthesis_last_updated`, or if synthesis has never been run (version == 0) and any L2 docs exist.

**Score formula:** `base_score = (fresh_count / 5) * 100`. If synthesis needs refresh and base_score > 0, deduct 10 points (clamped to 0).

**`propagate_staleness(refreshed_doc_types: List[KBDocType]) -> List[KBDocType]`:**

Builds reverse DAG (for each doc type, which doc types depend on it), then runs **BFS from refreshed docs** to find all downstream docs. Marks each downstream doc's `entry.status = "stale"` in the manifest. Returns list of newly-stale doc types.

**`get_changed_since_synthesis() -> List[KBDocType]`:**

Returns L2 doc types whose `last_updated` is after `synthesis_last_updated`. If no synthesis exists (version == 0), returns all L2 docs that have at least one version.

### 5c.7 Delta Synthesis Mode

When `mode == "refresh"` and a previous synthesis exists, the synthesis agent runs in **delta mode** instead of full synthesis:

**Trigger conditions (in pipeline.py):**
```python
use_delta = mode == "refresh" and storage.read_synthesis() is not None
```

**Delta mode inputs:**
- `previous_synthesis_path`: Relative path like `"synthesis/v2.md"` -- the synthesis agent reads this via `read_file` tool
- `changed_docs`: Dict mapping only changed doc types to their file paths
- `unchanged_docs`: Automatically computed as `available_docs - changed_docs`

**Delta synthesis prompts** (`core/research/prompts/synthesis.py`):
- `get_delta_synthesis_system_prompt()` -- Instructs the agent to: read the previous Company Profile, identify sections affected by changed research, update those sections while preserving unchanged content
- `build_delta_synthesis_user_prompt()` -- Provides: previous synthesis file path, changed doc file paths, unchanged doc file paths (for reference), missing docs list

**Fallback:** If no prior synthesis exists (`storage.read_synthesis() is None`), falls back to full synthesis mode even in refresh mode.

### 5c.8 read_file Tool

**File:** `core/research/knowledge_base/tools.py`

```python
def make_read_file_tool(base_dir: Path) -> BaseTool:
    """Create a LangChain tool for reading files from the KB directory."""
```

Creates a `@tool`-decorated function that accepts a relative file path and reads it from `base_dir`. Used by the synthesis agent to read L2 documents and previous synthesis versions. The tool is scoped to the KB base directory for security.

### 5c.9 HITL Mini-Graphs

**File:** `core/research/knowledge_base/graph.py`

Two LangGraph mini-graphs (not the full pipeline graph -- these handle pause/resume only):

**1. `build_kb_doc_review_graph()`** -- Used for HITL-1 and HITL-2
- State: `doc_summaries`, `checkpoint`, `auto_approve`, `decision`, `revision_notes`
- Nodes: `present_docs` -> `approval_gate` (interrupt) -> `route_decision`
- If `auto_approve=True`, skips interrupt and returns `decision="approve"`

**2. `build_kb_synthesis_review_graph()`** -- Used for HITL-3
- State: `synthesis_preview`, `synthesis_word_count`, `checkpoint`, `auto_approve`, `decision`, `revision_note`
- Same pattern as doc review but with synthesis-specific fields

**`run_kb_hitl_checkpoint()`** -- Async helper:
1. Invokes the graph with initial state
2. Checks for `__interrupt__` in result (LangGraph >=1.0 interrupt model)
3. If interrupted, emits SSE event, updates TaskStore status to `pending_approval`
4. Waits for human input (TaskStore approval)
5. Resumes graph with human decision
6. Returns final state dict

### 5c.10 Health & Refresh-Stale API Endpoints

**Router:** `api/routers/knowledge_base.py`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/knowledge-base/start` | Start KB pipeline (202/200) | member/superuser + tenant |
| `GET` | `/api/v1/knowledge-base/{slug}/health` | Staleness report + score | auth + tenant |
| `POST` | `/api/v1/knowledge-base/{slug}/refresh-stale` | Refresh only stale docs (202/200) | member/superuser + tenant |
| `GET` | `/api/v1/knowledge-base/{run_id}/status` | Poll run status | auth + tenant |
| `POST` | `/api/v1/knowledge-base/{run_id}/approve` | HITL approval | member/superuser + tenant |

**Route ordering:** Static routes (`/{slug}/health`, `/{slug}/refresh-stale`) are registered **BEFORE** dynamic routes (`/{run_id}/status`, `/{run_id}/approve`) to avoid FastAPI path collision. Without this ordering, `health` would be interpreted as a `run_id`.

**Health endpoint detail:**
- Instantiates `KBStorage(artifacts_root, slug)`, calls `get_staleness_report(threshold_override)`
- Returns `KBHealthResponse` with:
  - `per_doc: Dict[str, KBDocHealthResponse]` -- status, version, age_days, threshold, stale_reason, dependencies
  - `overall_score: float` -- 0-100
  - `synthesis_version: int`, `synthesis_last_updated: Optional[datetime]`
  - `synthesis_needs_refresh: bool`
  - `stale_docs: List[str]`, `missing_docs: List[str]`
- Optional query param: `?threshold_override=N` (applies globally to all doc types)

**Refresh-stale endpoint detail:**
1. Gets staleness report
2. If no stale or missing docs: returns HTTP 200 with `{"message": "All documents are fresh"}`
3. If stale docs exist: launches background pipeline with `refresh_docs` set to stale doc types (topologically sorted for DAG-order execution), returns HTTP 202

**Write-before-approve fix (Codex CRITICAL):** Synthesis is written to `storage.write_synthesis()` (versioned KB internal) immediately after the synthesis agent completes. However, the promoted file `company_context/{slug}.md` is **only written inside the HITL-3 approve branch**. If HITL-3 rejects, the KB synthesis version exists but is not promoted to the public-facing company context. This ensures rejected synthesis never leaks to downstream consumers.

### 5c.11 Pydantic Models (17 Models)

**File:** `core/models/knowledge_base.py` (288 lines)

**Enums and constants:**
- `KBDocType(str, Enum)` -- 6 values: `COMPANY_OVERVIEW`, `CUSTOMER_REVIEWS`, `COMPETITOR_REGISTRY`, `WEAKNESS_ANALYSIS`, `BRAND_PERCEPTION`, `SYNTHESIS`
- `L2_DOC_TYPES: tuple[KBDocType, ...]` -- The 5 L2 types (excludes synthesis)
- `KB_DEPENDENCY_GRAPH: Dict[KBDocType, List[KBDocType]]` -- DAG edges
- `KB_DEFAULT_STALENESS_DAYS: Dict[KBDocType, int]` -- Per-type thresholds

**Storage models:**

| Model | Fields | Purpose |
|-------|--------|---------|
| `KBDocVersion` | version, created_at, created_by, content_md, content_json, word_count, source_count, sha256 | Single version snapshot |
| `KBDocEntry` | doc_type, current_version, last_updated, staleness_days, status (fresh/stale/missing), dependencies | Manifest entry per doc type |
| `KBManifest` | slug, company_name, created_at, last_full_refresh, documents (Dict), synthesis_version, synthesis_last_updated | Top-level manifest |

**Health models:**

| Model | Fields | Purpose |
|-------|--------|---------|
| `KBDocHealth` | doc_type, status, current_version, last_updated, age_days, staleness_threshold_days, dependencies, stale_reason | Per-doc health status |
| `KBHealthReport` | slug, overall_score, doc_health (Dict), synthesis_version, synthesis_last_updated, synthesis_needs_refresh, stale_docs, missing_docs, last_full_refresh | Full health report |

**Agent I/O models:**

| Model | Fields | Purpose |
|-------|--------|---------|
| `KBAgentResult` | doc_type, version, content_md, content_json, sources, word_count, execution_time_s, error, is_partial | Result from any agent |
| `KnowledgeBaseInput` | company_name, domain, company_slug, company_id, product_slug, product_name, seed_urls, internal_sources, language, region, additional_constraints, refresh_docs, staleness_threshold_days, auto_approve_checkpoints | Pipeline input |
| `KnowledgeBaseOutput` | slug, company_name, manifest, agent_results, synthesis_md, company_profile_path, knowledge_base_dir, total_execution_time_s, changed_docs | Pipeline output |

**Per-agent structured output models:**

| Model | Fields | Purpose |
|-------|--------|---------|
| `CustomerReview` | quote, source_platform, source_url, reviewer_role, sentiment (Literal), themes, date | Single review |
| `CustomerReviewsStructured` | total_reviews_analyzed, reviews, sentiment_distribution, top_positive_themes, top_negative_themes, notable_quotes | Agent 2 output |
| `CompetitorProfile` | name, domain, relevance (Literal), relevance_score, key_differentiators, market_position | Single competitor |
| `CompetitorRegistryStructured` | direct_competitors, mindshare_competitors, market_map | Agent 3 output |
| `CompetitorWeakness` | competitor_name, weakness_category, description, severity (Literal), evidence, opportunity_for_us | Single weakness |
| `WeaknessAnalysisStructured` | per_competitor, systemic_industry_problems, strategic_opportunities | Agent 4 output |
| `BrandPerceptionStructured` | market_position, brand_positioning, key_differentiators, strengths_liked_by_users, challenges_and_pain_points, strategic_recommendations | Agent 5 output |

All fields have defaults for backward compatibility.

**API schemas** (`api/schemas/common.py`):
- `KnowledgeBaseStartRequest` -- company_name, domain, refresh_docs, auto_approve_checkpoints
- `KBDocHealthResponse` -- status, version, age_days, threshold, stale_reason, dependencies
- `KBHealthResponse` -- per_doc, overall_score, synthesis_version, synthesis_last_updated, synthesis_needs_refresh, stale_docs, missing_docs
- `KBRefreshStaleRequest` -- threshold_override

### 5c.12 LangSmith Tracing Integration

The KB pipeline uses the shared tracing module (`core/shared_tools/tracing.py`):

- `create_research_trace(slug)` -- Creates root trace under `research_kb_project` LangSmith project
- Each agent creates a span: `agent/company-overview`, `agent/customer-reviews`, etc.
- Each agent logs a generation with `log_generation()` (prompt truncated to 2000 chars)
- Pipeline creates a root span: `kb-pipeline/{slug}` with mode and target_docs metadata
- `flush()` called at pipeline end

### 5c.13 Test Coverage (260 tests)

| File | Tests | Scope |
|------|-------|-------|
| `test_models_kb.py` | 17 | Model validation, DAG constants, serialization, all 17 models |
| `test_storage.py` | 44 | Manifest CRUD, versioning, atomic writes, staleness report, propagation, changed_since_synthesis |
| `test_tools.py` | 8 | read_file tool scoping, file reading, error handling |
| `test_prompts.py` | 27 | 6 prompt builders + revision notes + delta prompts + Hub fallback |
| `test_agents.py` | 44 | 6 agent functions, timeout handling, error paths, delta mode, pause_turn loop |
| `test_graph_kb.py` | 22 | 2 HITL sub-graphs, auto-approve, interrupt/resume cycle |
| `test_pipeline_kb.py` | 40 | DAG execution order, 3 modes (full/refresh/single), HITL decision handling, delta synthesis, revision flows |
| `test_knowledge_base.py` (API) | 46 | Start (202/200/403/401/422), status, approve, health (per-doc + overall), refresh-stale (200 if fresh, 202 if stale) |
| **Total** | **260** | |

---

## 5d. Audience Persona Pipeline (Research v3)

### 5d.1 Architecture — 2-Agent Pipeline with 2 HITL Checkpoints

**Files:** `core/research/audience_persona/pipeline.py` (orchestrator), `agents.py`, `graph.py`, `storage.py`

The Audience Persona pipeline is a 2-agent architecture that replaces the monolithic persona research agent (§5.2) with a more structured approach. It produces detailed buyer persona profiles grounded in the company's Knowledge Base outputs.

**Execution Flow:**
```
Phase 0: Preflight — validate KB outputs, load company context + reviews + knowledge docs
    ↓
Phase 1: Agent 1 (Gemini Flash) — Persona Suggester → 3-7 PersonaBriefs
    ↓
── HITL-1: Per-brief approval (approve / modify / reject + manual add) ──
    ↓
Phase 2: Agent 2 (Perplexity deep research) — Parallel Profile Generators
    ↓
── HITL-2: Per-profile review (approve / revise / reject) ──
    ↓
Phase 3: Finalize — update manifest, record KB synthesis version, emit completed
```

**Key Design Decisions:**
- **Preflight check** validates Knowledge Base outputs exist before starting (company context required, customer reviews optional)
- **KB staleness integration**: manifest records `kb_synthesis_version` — pipeline guard blocks re-runs unless KB has been updated
- **Frozen ID map**: `_build_id_map()` creates deterministic `brief_id → persona_id` mapping with collision suffixing before parallel generation
- **Semaphore-controlled concurrency**: `settings.audience_persona_max_concurrent_generators` limits parallel profile generators
- **Storage lock**: `asyncio.Lock()` serializes filesystem writes during parallel generation

### 5d.2 Agent 1 — Persona Suggester (Gemini Flash)

**File:** `core/research/audience_persona/agents.py` → `run_persona_suggester()`

**LLM:** Google Gemini Flash (`gemini-3-flash-preview`) via raw `google.genai` SDK
**API Key:** `GOOGLE_API_KEY_AUDIENCE_PERSONA` (fallback: `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT`)

**Input Context:**
- Company context markdown (max 15K chars, from KB or company_context artifact)
- Customer reviews markdown (max 10K chars, from KB)
- Knowledge documents text (max 50K chars, from uploaded docs)
- Additional constraints (optional user-provided guidance)

**Output:** JSON array of 3–7 `PersonaBrief` objects with fields: `persona_name`, `tagline`, `description`, `rationale[]`

**Error Handling:**
- Response MIME type forced to `application/json`
- Tolerant JSON parsing: strips code fences, finds `[...]` boundaries
- Validates each brief (empty names rejected, duplicate names deduplicated)
- Retry once on validation failure with repair prompt
- Returns empty list on complete failure (never raises)

### 5d.3 Agent 2 — Profile Generator (Perplexity Deep Research)

**File:** `core/research/audience_persona/agents.py` → `run_persona_profile_generator()`

**LLM:** Perplexity `sonar-deep-research` via `perplexity_client.research()`
**Timeout:** 300s per persona

**Input:** System + user prompt built from `PersonaBrief` + company context + reviews + knowledge docs
**Output:** `PersonaAgentResult` with full persona profile markdown + optional structured JSON sidecar

**Revision Support:** When `revision_note` is provided (from HITL-2 revise decision), the prompt includes `## Reviewer Feedback` section appended to the user prompt.

**Error Handling:** Each generator runs independently — failures produce `PersonaAgentResult(error=...)` without blocking other generators.

### 5d.4 HITL-1: Brief Approval Graph

**File:** `core/research/audience_persona/graph.py` → `build_ap_brief_review_graph()`

**State Schema:** `APBriefReviewState(TypedDict)` — `briefs`, `checkpoint`, `auto_approve`, `batch_decision`, `brief_reviews`, `added_briefs`, `approved_briefs`

**Graph Nodes:** `present` → `gate` (interrupt) → route → END

**Approval Decisions:**
| Batch Decision | Behavior |
|----------------|----------|
| `approve_all` | All original briefs approved |
| `reject_all` | No briefs approved — pipeline ends gracefully |
| `partial` | Per-brief decisions: approve / modify / reject |

**Partial Mode Rules (fail-closed):**
- Unknown `brief_id`s silently skipped
- Duplicate `brief_id`s: first-wins
- Unreviewed briefs: rejected
- Modified briefs require non-empty `persona_name`
- Manually added briefs get unique IDs, `source="manual"`

### 5d.5 HITL-2: Profile Review Graph

**File:** `core/research/audience_persona/graph.py` → `build_ap_profile_review_graph()`

**State Schema:** `APProfileReviewState(TypedDict)` — `profile_summaries`, `checkpoint`, `auto_approve`, `profile_reviews`, `approved_profiles`, `revision_requests`, `rejected_profiles`

**Per-Profile Decisions:**
| Decision | Action |
|----------|--------|
| `approve` | Profile marked as `fresh` in manifest |
| `revise` | Re-run profile generator with `## Reviewer Feedback` appended |
| `reject` | Profile marked as `archived` in manifest |

**Fail-open policy:** Unreviewed profiles are approved (profiles already generated — safer to keep than discard).

### 5d.6 PersonaStorage — Versioned Filesystem Store

**File:** `core/research/audience_persona/storage.py`

**Layout:**
```
artifacts/audience_personas/{slug}/
    _manifest.json                    # PersonaManifest: slug, personas{}, kb_synthesis_version
    {persona_id}/
        brief.json                     # PersonaBrief (suggester output or manual entry)
        v1.md                          # Profile version 1 (markdown)
        v1.json                        # Structured sidecar (optional)
        v2.md                          # Profile version 2 (revision)
        ...
```

**Key Methods:**
| Method | Description |
|--------|-------------|
| `write_version()` | Writes new version file + updates manifest (SHA-256, word count, timestamps) |
| `read_version(persona_id, version)` | Read specific version (md + optional json) |
| `get_latest_version(persona_id)` | Read latest version from manifest |
| `list_active_persona_ids()` | Return IDs with status `fresh`/`stale`/`pending_review` |
| `list_persona_paths()` | Return paths to latest `.md` files (for content engine integration) |
| `check_staleness(persona_id, threshold_days)` | Default 60 days |
| `check_kb_staleness(kb_synthesis_version)` | Compare manifest's KB version vs current |
| `mark_persona_status(persona_id, status)` | Update persona status in manifest |

**Atomicity:** Manifest writes use `tempfile.mkstemp()` + `os.replace()` for crash safety. Version files are written before manifest update.

### 5d.7 Pydantic Models (9 Models)

**File:** `core/models/audience_persona.py`

| Model | Fields | Purpose |
|-------|--------|---------|
| `PersonaBriefDecision` | Enum: approve, modify, reject | HITL-1 per-brief decision |
| `PersonaProfileDecision` | Enum: approve, revise, reject | HITL-2 per-profile decision |
| `PersonaBrief` | brief_id, persona_name, tagline, description, rationale[], source | Agent 1 output / manual entry |
| `PersonaBriefReview` | brief_id, decision, modified_brief? | HITL-1 review item |
| `PersonaProfileEntry` | persona_id, persona_name, tagline, kind (icp/secondary), current_version, status, sha256, word_count | Manifest entry |
| `PersonaManifest` | slug, company_name, personas{}, kb_synthesis_version, kb_synthesis_updated_at | Top-level manifest |
| `PersonaAgentResult` | brief_id, persona_name, content_md, content_json?, word_count, execution_time_s, error? | Agent 2 result |
| `AudiencePersonaInput` | company_name, domain?, max_personas (3-7), auto_approve_checkpoints[], language, region? | Pipeline input |
| `AudiencePersonaOutput` | slug, manifest, briefs_suggested, briefs_approved, profiles_generated, persona_results{} | Pipeline output |

### 5d.8 API Endpoints (7 Total)

**Router:** `api/routers/audience_persona.py` — prefix `/api/v1/audience-persona`
**Schemas:** `api/schemas/audience_persona.py`

| # | Method | Path | Description | Auth |
|---|--------|------|-------------|------|
| 1 | `POST` | `/start` | Launch AP pipeline (202) or skip if exists (200) | member/superuser |
| 2 | `GET` | `/{run_id}/status` | Get pipeline status | any auth |
| 3 | `POST` | `/{run_id}/approve/briefs` | HITL-1 brief approval | member/superuser |
| 4 | `POST` | `/{run_id}/approve/profiles` | HITL-2 profile approval | member/superuser |
| 5 | `POST` | `/{slug}/add-persona` | Standalone persona generation (202) | member/superuser |
| 6 | `POST` | `/{slug}/personas/{persona_id}/approve` | Standalone approve/reject | member/superuser |
| 7 | `GET` | `/{slug}/personas` | List all personas for a company | any auth |

**Pipeline Guard:** If approved personas already exist AND KB hasn't been updated since last AP run, returns HTTP 200 with `already_exists=true`. Override with `force_rerun=true`.

**Tenant Isolation:** All endpoints verify `company_slug` matches authenticated user's company.

### 5d.9 Test Coverage (232 tests)

| File | Tests | Scope |
|------|-------|-------|
| `tests/research/audience_persona/test_models_ap.py` | 30 | 9 Pydantic models, defaults, enums |
| `tests/research/audience_persona/test_storage_ap.py` | 32 | PersonaStorage: manifest CRUD, versioning, staleness |
| `tests/research/audience_persona/test_agents_ap.py` | 30 | Suggester + generator, retry logic, knowledge docs |
| `tests/research/audience_persona/test_graph_ap.py` | 30 | 2 HITL graphs, auto-approve, interrupt/resume |
| `tests/research/audience_persona/test_pipeline_ap.py` | 45 | Full pipeline: preflight, ID map, parallel gen, HITL flow |
| `tests/research/audience_persona/test_prompts_ap.py` | 20 | Prompt builders, revision notes |
| `tests/api/test_audience_persona_router.py` | 45 | 7 endpoints: start, status, approve, add-persona, list |
| **Total** | **232** | |

---

## 5f. Research Orchestrator — KB → AP → VSG DAG

The Research Orchestrator provides a **single API call** (`POST /api/v1/research/start`) that runs all three research pipelines in sequence: Knowledge Base → Audience Persona → Voice Style Guide. It handles dependency ordering, HITL pass-through, skip logic for fresh artifacts, auto-approve distribution, and error propagation.

**Location:** `core/research/orchestrator.py` (core logic), `api/routers/research_orchestrator.py` (API)

### 5f.1 Architecture & Flow

```
POST /api/v1/research/start
    → run_research_orchestrator_task() (runner.py — acquires semaphore + slug lock ONCE)
        → run_research_orchestrator() (orchestrator.py)
            1. Resolve slugs (company_slug, effective_slug)
            2. Emit "pipeline_start" SSE event
            3. For each pipeline in [kb, ap, vsg]:
               a. Check skip logic (_should_skip_*)
               b. If skip → emit "orchestrator_stage_skipped", record SubPipelineResult(skipped)
               c. If run  → emit "orchestrator_stage_start"
                          → build sub-pipeline Input
                          → await run_{pipeline}_pipeline(...)
                          → emit "orchestrator_stage_complete"
               d. On error → emit "orchestrator_stage_failed", STOP downstream
            4. Emit "completed" event
            5. Return ResearchOrchestratorOutput
```

**Key design decisions:**
- Sub-pipelines called **directly** (not via runner wrappers) — no double-lock or double-semaphore
- Orchestrator's `run_id` passed to sub-pipelines for valid FK in DB artifact persistence
- `OrchestratorStatus` enum: `completed`, `completed_partial` (some skipped), `failed` (a pipeline errored)
- Failed orchestrator status maps to `TaskStatus.FAILED` at the task level

### 5f.2 Skip Logic

Each pipeline has a skip check that evaluates artifact freshness:

| Pipeline | Skip Condition | Mechanism |
|----------|----------------|-----------|
| KB | `synthesis_version > 0` AND no stale docs AND not `force_rerun` | `KBStorage.read_manifest()` |
| AP | Approved personas exist AND `kb_synthesis_version` matches current KB | `PersonaStorage.read_manifest()` + `KBStorage.read_manifest()` |
| VSG | Guide `current_version > 0` AND `status == "fresh"` AND AP unchanged | `VoiceStyleGuideStorage.read_manifest()` |

`force_rerun=true` bypasses all skip logic. `skip_fresh=false` in the API request disables freshness skipping.

### 5f.3 HITL Pass-Through

The orchestrator shares its `task_id` with all sub-pipelines. When a sub-pipeline (e.g., KB) hits a HITL checkpoint:

1. KB calls `task_store.wait_for_approval(task_id)` — suspends the KB coroutine
2. The orchestrator's `await` on KB naturally suspends
3. User approves via existing per-pipeline endpoint (e.g., `POST /api/v1/knowledge-base/{run_id}/approve`)
4. KB resumes, completes, returns output
5. Orchestrator proceeds to next pipeline

**No new approval endpoints** — all approvals use existing per-pipeline endpoints with the same `run_id`.

### 5f.4 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/research/start` | Launch orchestrator (202). Returns `run_id`. |
| `GET` | `/api/v1/research/{run_id}/status` | Get orchestrator status (tenant-isolated). |

**Request body (`POST /start`):**
```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "product_slug": "expense",
  "pipelines": ["kb", "ap", "vsg"],
  "auto_approve": {"kb": [1,2,3], "ap": [1,2], "vsg": [1]},
  "force_rerun": false,
  "skip_fresh": true,
  "max_personas": 5,
  "max_authors": 3
}
```

### 5f.5 Test Coverage (67 tests)

| Category | Count | Description |
|----------|-------|-------------|
| Model tests | 19 | AutoApproveConfig, PipelineSkipConfig, SubPipelineStatus/Result, OrchestratorStatus, Input/Output |
| Skip logic | 10 | Skip/no-skip for KB/AP/VSG with force_rerun and config overrides |
| Input construction | 3 | _build_kb/ap/vsg_input helpers |
| Full orchestration | 5 | All-run, selective, all-skipped, mixed skip/run |
| Error propagation | 3 | KB fail → AP/VSG skip, AP fail → VSG skip, VSG fail recorded |
| SSE events | 3 | Stage events, skipped events, failed events |
| Auto-approve | 3 | Per-pipeline checkpoint distribution |
| Null-safe helpers | 1 | Runs without event_bus |
| Slug resolution | 3 | Company-only, with product, explicit slug |
| API router | 17 | Start success/auth/tenant/validation, status/cross-tenant/not-found |
| **Total** | **67** | |

---

## 6. Pipeline 2: Gap Analysis

### Overview

The Gap Analysis Pipeline is an 8-step sequential data pipeline (not LangGraph-based) that identifies where a company's content is weak relative to what AI search engines cite. It operates in embedding space, comparing the company's web content against the sources that ChatGPT, Claude, Perplexity, and Google AI Overview cite when answering buyer-intent queries.

**Entry Point:** `run_gap_analysis(input_data: GapAnalysisInput, skip_steps: List[int] = [])` in `core/gap_analysis/pipeline.py`

**All outputs stored in:** `/artifacts/gap_analysis/{company_slug}/`

**Skip Logic:** Each step can be independently skipped via `skip_steps` parameter. Skipped steps load from cached JSON/pgvector instead of rerunning. This enables fast re-analysis without re-crawling or re-searching.

---

### 6.1 Step 1 — Embed Company Assets

**File:** `core/gap_analysis/steps/s1_embed_assets.py`

**Purpose:** Crawl the company's entire website, extract semantic units (meaningful text chunks), embed them using OpenAI, and store in pgvector.

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
- Stores raw embeddings in pgvector (indexed by company slug)
- Saves lightweight JSON with `embedding_id` only (no raw vectors in JSON — saves disk space)

**Knowledge Document Integration (Phase 2B — added 2026-02-27):**

After website discovery and chunking, s1 checks for uploaded knowledge documents:
1. Resolves `knowledge_doc_dir` from `GapAnalysisInput` — path to `artifacts/knowledge_docs/{effective_slug}/`
2. If the directory exists and contains `_metadata.json`, loads all tracked documents
3. Extracts text from each file using `core/shared_tools/text_extraction.py` (supports `.md`, `.txt`, `.pdf` via pdfplumber, `.docx` via python-docx)
4. Chunks extracted text using the same `_chunk_paragraphs()` function (min_words=80, max_words=220)
5. Creates `SemanticUnit` objects with `discovery_source="knowledge_doc"` and `url=None`
6. Merges knowledge doc units with website units → embeds all → stores in pgvector
7. After embedding, calls `mark_documents_embedded()` from `core/shared_tools/knowledge_doc_metadata.py` to set `is_embedded=True` and `last_embedded_at` on all processed documents

**Shared module coordination:** Both the upload service (`api/services/knowledge_doc_service.py`) and s1's mark-as-embedded share the **same** `metadata_lock` from `core/shared_tools/knowledge_doc_metadata.py`. This prevents race conditions when a user uploads a document while a pipeline is marking documents as embedded.

**Backward compat:** `knowledge_doc_dir` defaults to `None` in `GapAnalysisInput`. Existing pipelines that don't have knowledge docs produce identical results.

**Runner resolves path with fallback:**
```
artifacts/knowledge_docs/{effective_slug}/  →  fallback to  →  artifacts/knowledge_docs/{company_slug}/
```

**Company Page Structural Analysis (added 2026-03-07):**

After `build_semantic_units()`, s1 computes structural signals for each crawled company page by reusing s4's `compute_structural_signals(html)` public wrapper. This enables the content engine to compare company page structure against top-cited exemplars (e.g., "your page has 3 headers, competitors have 8").

- Iterates `pages_with_html` (URL, HTML pairs retained from crawl)
- Calls `compute_structural_signals(html)` per page → returns `(paragraphs, StructuralSignals)`
- Builds `CompanyPageAnalysis` objects: `url`, `title`, `structural_signals`, `word_count`, `paragraph_count`
- Saves to `company_page_analysis.json`
- Errors per page logged at DEBUG level but don't fail the pipeline

**Outputs:**
| File | Content |
|------|---------|
| `company_embeddings.json` | List of SemanticUnit with embedding_ids (no raw vectors) — includes both website and knowledge doc units |
| `company_page_analysis.json` | List of CompanyPageAnalysis with ~45 structural signals per page (added 2026-03-07) |
| `site_discovery/discovered_pages.json` | All discovered URLs with metadata |
| `site_discovery/site_tree.json` | Hierarchical site structure |
| `site_discovery/discovery_summary.json` | Discovery statistics |
| pgvector table: `persona_embeddings` (company-scoped) | Raw embeddings for similarity queries |

**Skip Logic:** If step 1 already ran, loads embeddings from JSON and hydrates from pgvector if needed.

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

**Public API (added 2026-03-07):** `compute_structural_signals(html: str) -> Tuple[List[str], StructuralSignals]` — Public wrapper around `_extract_paragraphs()` for reuse by s1 (company page analysis). Takes raw HTML, returns paragraphs list and full StructuralSignals.

**Self-citation flag propagation:** `is_company_citation` flag from `CitationRef` (set by pipeline's `_flag_company_citations()` between s3 and s4) is carried through dedup into `EnrichedCitation.is_company_citation`.

**Output:** `enriched_citations.json` — List of `EnrichedCitation` with paragraphs, ~45 structural signals, and `is_company_citation` flag.

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
- Upsert deduplicated embeddings to pgvector citations table

**Outputs:**
| File | Content |
|------|---------|
| `embeddings/queries_with_embeddings.json` | GeneratedQuery objects with embedding vectors |
| `embeddings/citations_with_embeddings.json` | EnrichedCitation objects with best_paragraphs |
| pgvector table: `cps_training_snippets` (company-scoped) | Citation paragraph embeddings |

---

### 6.6 Step 6 — Semantic & Structural Analysis (SPA)

**File:** `core/gap_analysis/steps/s6_analyze.py`

**Purpose:** The core analytical step. Computes semantic proximity, gap measurements, statistical tests, centroid distances, and content specifications per cluster.

**Analysis Components:**

**1. Query-Citation Similarity**
For each query, find top-N (N=5) citations by best-paragraph similarity, compute average citation similarity.

**2. Query-Company Similarity**
For each query, find best-matching company semantic unit. Track best similarity + unit metadata (ID, text snippet, and URL).

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

**9. Company URL Passthrough (added 2026-03-07)**
Each `QueryGap` now includes `best_company_url` — the actual URL of the best-matching company page. Previously only `best_company_unit` (ID) and `best_company_unit_text` (200-char snippet) were stored. The URL enables the content engine to recommend "optimize this page" vs "create new page."

**10. Self-Citation Detection (added 2026-03-07)**
Accepts optional `company_citation_map: Dict[str, List[str]]` (query_id → list of engines that cited the company). Sets `company_cited: bool` and `company_cited_platforms: List[str]` on each `QueryGap`. Built from `_flag_company_citations()` and `_build_company_citation_map()` in `pipeline.py`, which run BEFORE s4 dedup to preserve multi-engine information.

**11. Company Structural Signals (added 2026-03-07)**
Accepts optional `page_analysis_lookup: Dict[str, CompanyPageAnalysis]` (URL → page analysis). Looks up the best company unit's URL in the lookup and attaches `best_company_structural_signals` (dict of ~45 signals) to each `QueryGap`. Enables structural comparison between company pages and top-cited exemplars.

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
- `gap_report.md` — Summary + **top 25 gap briefs** (up from 10) with inline ContentBrief sections showing: target word count, reading level, recommended headers, content patterns (FAQ rate, table rate, key takeaways), dominant authority/content types. Per-gap sections include company page URL (if available), self-citation status (which AI platforms cite the company), and company page structural summary (word count, headers, lists, paragraphs). Remaining gaps (after 25) go in appendix table.
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
  ├── S1: domain, seed_urls ──────────────────────▶ company_embeddings.json + pgvector
  │                                                   + company_page_analysis.json
  │                                                   │
  ├── S2: company_context_path, persona_paths ────▶ queries.json
  │                                                   │
  ├── S3: queries.json + platforms ────────────────▶ platform_results/{engine}.jsonl
  │   └── _flag_company_citations(domain)              (is_company_citation flagged)
  │   └── _build_company_citation_map()                (query_id → [engines])
  │                                                   │
  ├── S4: platform_results ────────────────────────▶ enriched_citations.json
  │                                                   │
  ├── S5: queries + citations ─────────────────────▶ embeddings/*.json + pgvector
  │                                                   │
  ├── S6: company_units + queries + citations ─────▶ analysis.json
  │       + company_citation_map                       (best_company_url,
  │       + page_analysis_lookup                        company_cited, structural_signals)
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
- S5 requires: pgvector embeddings from S1 (for company embedding IDs)
- S6 requires: pgvector embeddings from S1 + S5 (for embedding vectors)

---

## 7. Pipeline 3: Content Generation Engine

**Status:** Implemented (v1.0 + v1.3). **437 content engine tests** (57 v1.0 + 257 v1.3 core + 28 v1.0 API + 28 v1.3 API + 38 LangSmith migration + 12 persistence + 17 prompt registry). All passing.

**v1.0 Architecture:** 4-stage async pipeline using two Anthropic agent patterns:
- **Orchestrator-Workers** — parallel content production with semaphore-controlled concurrency
- **Evaluator-Optimizer** — 4-dimension quality gate with automated revision cycles

**v1.3 Architecture:** 6-stage pipeline with two-phase context loading, 2 new agents (Strategic Planner + Brief Builder), 3 HITL checkpoints, LiteLLM abstraction for all LLM calls, LangSmith tracing (Langfuse fully removed), E-E-A-T evaluation, and dual feedback loops. Both v1.0 and v1.3 coexist via separate API endpoints (`/api/v1/content/` for v1.0, `/api/v1/content-v13/` for v1.3).

**Key Architectural Change — Langfuse to LangSmith Migration (2026-03-02):**
Langfuse was **fully removed** from the codebase and replaced with LangSmith as the sole tracing backend. The migration introduced `core/shared_tools/tracing.py` as a unified tracing module shared across all pipelines (content engine, research/KB, etc.). The old `core/content_engine/tracing.py` (Langfuse-based) was deleted. `core/content_engine/tracing_v13.py` is now a **re-export shim** that re-exports all functions from `core/shared_tools/tracing`, maintaining backward compatibility with all existing import sites.

```
v1.3 Pipeline Flow:
+------------------------------------------------------------------------+
|  [Stage 0] Two-Phase Context Loading (ContextRouter)                    |
|    Phase 1: extract_scorecard() -> PlannerScorecard (~11K tokens)        |
|    Phase 2: extract_worker_context() -> per-topic full context           |
+--------------------+---------------------------------------------------+
                     v
+------------------------------------------------------------------------+
|  [Stage 1] Strategic Planner Agent (LiteLLM)                            |
|    Input: scorecard + company context + style guide                     |
|    Output: StrategicPlannerOutput -> List[TopicSelection]                |
|    -> HITL-1: Topic Approval (approve/modify/reject/retry)              |
+--------------------+---------------------------------------------------+
                     v
+------------------------------------------------------------------------+
|  [Stage 2] Brief Builder Agent (LiteLLM, parallel per topic)            |
|    Input: TopicSelection + WorkerQueryContext                            |
|    Output: List[ContentBlueprint] (extends ContentBrief)                |
|    -> HITL-2: Brief Approval (approve/feedback/reject per blueprint)     |
+--------------------+---------------------------------------------------+
                     v
+------------------------------------------------------------------------+
|  [Stage 3] Content Workers (v1.3 chain)                                 |
|    Outliner -> Drafter -> Linker -> Fact Checker (verify-only)           |
|  [Stage 4] Evaluator-Optimizer (4+1 dimensions, dual feedback)          |
|    + E-E-A-T (5th judge), section_level -> drafter+fact_checker         |
|    + major_change (semantic < 0.5) -> auto re-brief                     |
|  [Stage 5] HITL-3 Content Review (bounded retry loops)                  |
|    edit (max 2) -> drafter -> re-evaluate -> re-present                 |
|    reject (max 2) -> re-brief -> re-dispatch -> re-evaluate -> re-present|
+------------------------------------------------------------------------+

Entry Modes:
  AUTONOMOUS: Full pipeline (stages 0-5), reads gap_analysis output
  MANUAL: User prompt -> inline WorkerQueryContext -> stages 2-5
```

**v1.3 File Map (14 new files):**
| File | Purpose | Lines |
|------|---------|-------|
| `core/content_engine/context_router.py` | Two-phase context extraction (scorecard + worker context) — pure data transform, no LLM, no I/O | ~338 |
| `core/content_engine/strategic_planner.py` | Agent 1: Topic selection with ranking and metadata via LiteLLM | ~129 |
| `core/content_engine/brief_builder.py` | Agent 2: Parallel blueprint generation per topic via LiteLLM | ~236 |
| `core/content_engine/llm_client.py` | LiteLLM wrapper: auto-prefix routing, retry with jittered backoff, LangSmith callbacks | ~235 |
| `core/content_engine/pipeline_v13.py` | 6-stage orchestrator with skip_stages support and entry mode routing | ~500+ |
| `core/content_engine/graph_v13.py` | 3 LangGraph HITL checkpoints (topic/brief/content) | ~400+ |
| `core/content_engine/tracing_v13.py` | Re-export shim — delegates to `core/shared_tools/tracing` | ~36 |
| `core/content_engine/prompt_registry.py` | LangSmith Hub prompt fetching with thread-safe TTL cache + local fallback | ~146 |
| `core/content_engine/evaluator/eeat_judge.py` | E-E-A-T evaluation dimension (LLM-as-Judge) | ~120 |
| `core/content_engine/prompts/strategic_planner_prompts.py` | Planner system + user prompt templates | ~100+ |
| `core/content_engine/prompts/brief_builder_prompts.py` | Brief builder system + user prompt templates | ~100+ |
| `core/content_engine/prompts/eeat_judge_prompts.py` | E-E-A-T judge prompt templates | ~80 |
| `core/models/content_generation_v13.py` | v1.3 Pydantic models (12 models, 271 lines) | ~271 |
| `api/routers/content_v13.py` | 5 API endpoints (start, status, 3 approvals) | ~200+ |

**v1.3 DB Persistence:** Two new functions in `core/content_engine/persistence.py`:
- `persist_v13_planner_output()` — writes to `PipelineRunModel.config["v13_planner"]` JSONB
- `persist_v13_brief_approval()` — writes to `PipelineRunModel.config["v13_briefs"]` JSONB

### 7.1 LiteLLM Client — Unified LLM Abstraction

**File:** `core/content_engine/llm_client.py`

All LLM calls in the v1.3 pipeline route through this module, replacing direct SDK calls (Anthropic `AsyncAnthropic`, httpx to Perplexity, etc.) with a single `llm_call()` function.

**`_ensure_litellm_model(model: str) -> str`** — Auto-detects provider and prefixes model strings:

| Model Prefix | Provider | Example |
|--------------|----------|---------|
| `claude-` | `anthropic/` | `claude-sonnet-4-5-20250929` → `anthropic/claude-sonnet-4-5-20250929` |
| `sonar` | `perplexity/` | `sonar-pro` → `perplexity/sonar-pro` |
| `gpt-`, `o1`, `o3` | `openai/` | `gpt-5.2-2025-12-11` → `openai/gpt-5.2-2025-12-11` |
| `gemini-` | `google/` | `gemini-3-flash-preview` → `google/gemini-3-flash-preview` |
| Already has `/` | unchanged | `anthropic/claude-sonnet-4-5-20250929` → unchanged |
| Unknown | unchanged | passed through to LiteLLM for routing |

```python
async def llm_call(
    *,
    model: str,                                    # LiteLLM model string
    system: str,                                   # System prompt
    user: str,                                     # User prompt
    max_tokens: int = 4096,                        # Max output tokens
    temperature: float = 0.0,                      # Sampling temperature
    response_format: Optional[Type[BaseModel]] = None,  # Pydantic model for structured output
    metadata: Optional[Dict[str, Any]] = None,     # Metadata (appears in LangSmith traces)
    max_retries: int = 3,                          # Retry attempts on transient failures
    base_delay: float = 1.0,                       # Base delay for exponential backoff
) -> LLMResponse
```

**Retry strategy:** Jittered exponential backoff: `delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)`. All exceptions caught — final exception re-raised after exhausting retries.

**LangSmith callback integration:**
```python
def configure_litellm_callbacks() -> None:
    """Called once at pipeline startup."""
    litellm.success_callback = ["langsmith"]
    litellm.failure_callback = ["langsmith"]
```
LiteLLM auto-detects LangSmith when `LANGSMITH_API_KEY` env var is set. Configured via `configure_litellm_callbacks()` at pipeline startup.

**LLMResponse model:**
```python
class LLMResponse(BaseModel):
    content: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""
```

**Lazy import:** `litellm` is imported at module load but wrapped in try/except — tests can mock without installing the full package. If not installed, `llm_call()` raises `RuntimeError`.

**Embedding pass-through:** `embed_texts(texts)` delegates to `core/shared_tools/async_embedding_client.async_embed_texts()`, keeping embedding calls consistent across v1.0 and v1.3.

### 7.2 LangSmith Prompt Registry — Hub-with-Local-Fallback

**File:** `core/content_engine/prompt_registry.py`

Thread-safe, TTL-cached prompt fetching from LangSmith Hub with automatic local fallback.

**Architecture:**
```
get_prompt(hub_name, local_fallback, tag)
    |
    +-- Hub disabled (settings.langsmith_use_hub=False)? -> return local_fallback
    |
    +-- Cache hit (within 5-min TTL)? -> return cached text
    |
    +-- Cache miss -> acquire _LOCK (threading.Lock)
         |
         +-- Double-check cache (another thread may have populated)
         |
         +-- Pull from Hub: Client.pull_prompt_commit("name:tag")
         |    |
         |    +-- Extract text via _extract_text_from_manifest()
         |    |     Path 1: messages[0].kwargs.content
         |    |     Path 2: messages[0].kwargs.prompt.kwargs.template
         |    |     Path 3: messages[0].kwargs.template
         |    |
         |    +-- Success? -> cache and return
         |    +-- Failure? -> return local_fallback (don't cache failures)
```

**Process-global state:**
- `_CACHE: Dict[str, tuple[str, float]]` — key is `"{hub_name}:{tag}"`, value is `(text, fetched_at_epoch)`
- `_CACHE_TTL = 300` (5 minutes)
- `_LOCK = threading.Lock()` — ensures single-flight Hub pulls under contention

**Configuration:**
- `LANGSMITH_API_KEY` — required for Hub pulls
- `settings.langsmith_use_hub = True` to enable (default: `False` — local prompts authoritative)
- `settings.langsmith_hub_tag = "production"` for version pinning

**Async wrapper:** `aget_prompt()` runs `get_prompt()` in thread pool via `asyncio.to_thread()`.

**Usage pattern in prompt files:**
```python
from core.content_engine.prompt_registry import get_prompt
_HUB_NAME = "outliner-system"
def get_outliner_system_prompt() -> str:
    return get_prompt(_HUB_NAME, OUTLINER_SYSTEM_PROMPT)
```

### 7.3 LangSmith Tracing Architecture (Replaces Langfuse)

**File:** `core/shared_tools/tracing.py` (primary), `core/content_engine/tracing_v13.py` (re-export shim)

**Migration:** Langfuse was **fully removed** (2026-03-02). LangSmith is now the sole tracing backend. The shared module lives in `core/shared_tools/tracing.py` and is used by both the content engine and the knowledge base pipeline. The old `tracing_v13.py` is a re-export shim for backward compatibility.

**LangSmith integration uses `RunTree`** from `langsmith.run_trees`:
- Each `RunTree` represents a trace or span
- Parent-child hierarchy via `parent.create_child()`
- `run_type` values: `"chain"` (pipeline/stage spans), `"llm"` (generation logging)
- `post()` sends the run to LangSmith, `patch()` updates it, `end()` finalizes it

**Context-var span propagation:**
LangGraph graph nodes are sync functions whose state dicts are serialized by MemorySaver (msgpack). Putting a RunTree into state crashes with `TypeError: Type is not msgpack serializable`. Instead, `contextvars.ContextVar` propagates the current span out-of-band:
```python
_current_span: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar("langsmith_current_span", default=None)
set_current_span(span)   # Set in async context before graph invocation
get_current_span()       # Read in sync graph nodes
```

**Backward-compatible kwargs:** Every public function accepts OLD Langfuse kwargs (`input=`, `parent_span=`, `level=`, `status_message=`, `model_parameters=`, `user_id=`, `metadata=` on `end_span`) as keyword-only arguments. These are silently absorbed or mapped to LangSmith equivalents, so callers migrated by a simple import swap continue to work without callsite changes.

**Trace hierarchy:**
```
Project: content-engine (configurable via LANGSMITH_PROJECT)
  Session ID: content-{slug}-{timestamp}
    Root RunTree: content-pipeline/{slug}  (run_type="chain")
      +-- Stage Span: strategic-planner     (run_type="chain")
      |     +-- Generation: select_topics   (run_type="llm")
      +-- Stage Span: brief-builder-parallel
      |     +-- Span: brief-builder/brief-001
      |     |     +-- Generation: build_brief
      |     +-- Span: brief-builder/brief-002
      +-- Stage Span: workers
      |     +-- Span: Worker #1 -> outliner/drafter/linker/fact_checker
      +-- Stage Span: evaluator
      |     +-- Span: evaluator/brief-001 -> eval dimensions
      +-- Stage Span: review
            +-- Score: human_decision
```

**Helper functions (all in `core/shared_tools/tracing.py`):**

| Function | Purpose |
|----------|---------|
| `create_session(company_slug)` | Generate session ID: `"content-{slug}-{timestamp}"` |
| `create_pipeline_trace(session_id, slug, ...)` | Create root RunTree with project name |
| `create_trace(session_id, name, ...)` | Create standalone RunTree |
| `create_research_trace(slug, ...)` | Create root trace for KB pipeline (uses `research_kb_project` setting) |
| `create_span(parent, name, ...)` | Create child span under parent via `parent.create_child()` |
| `end_span(span, output=, error=)` | Finalize span: `span.end()` + `span.patch()` |
| `log_generation(parent, name, model, ...)` | Log LLM call as child span with `run_type="llm"` |
| `log_score(parent, name, value, comment)` | Log score via `client.create_feedback()` |
| `update_trace_output(trace, output)` | End root trace with final output |
| `flush()` | No-op (LangSmith uses sync HTTP calls via post/patch) |
| `set_current_span(span)` | Set span in contextvars |
| `get_current_span()` | Get span from contextvars |

**`log_score()` type handling:**
- `float` → passed as `score` directly
- `bool` → converted to `1.0` / `0.0`
- `str` → stored in `comment` field (LangSmith feedback requires numeric score)

**`log_generation()` truncation:** Input and output texts are truncated to 5000 chars before sending to prevent oversized payloads.

**`end_span()` Langfuse compat:** If `level="ERROR"` and `error` is None, maps `status_message` to the error field.

**Singleton client:** Cached `Client` instance initialized lazily with `api_key` and optional `workspace_id` from settings.

**Graceful degradation:** All functions check `_is_enabled()` (requires `langsmith` package + `LANGSMITH_API_KEY` setting). All functions wrap operations in try/except and return None on failure — tracing unavailability never crashes the pipeline.

### 7.4 Stage 0 — Two-Phase Context Loading (ContextRouter)

**File:** `core/content_engine/context_router.py`

A **pure data transformation module** — no LLM calls, no I/O, no imports from prompts/ or pipeline modules. Implements the key insight that different agents need different amounts of context:

**Phase 1 — Scorecard Extraction (`extract_scorecard()`):**

```python
def extract_scorecard(
    analysis_json: Dict[str, Any],      # Full AnalysisResult from analysis.json
    company_context_md: str = "",        # First ~600 chars used
    product_focus: Optional[str] = None,
) -> PlannerScorecard
```

Iterates over `analysis_json["gaps"]` and `analysis_json["cluster_specs"]` to produce:
- **Per-query scorecards** (`QueryScorecard`): ~50 tokens each. Fields: `query_id`, `query_text`, `cluster_name`, `gap`, `best_company_similarity`, `avg_citation_similarity`, `interpretation`, `exemplar_count`, `has_brief`, `company_cited` (whether company is already cited by AI platforms for this query).
- **Per-cluster summaries** (`ClusterSummary`): ~60 tokens each. Aggregated from query scorecards by `cluster_name`. Fields: `cluster_name`, `query_count`, `avg_gap`, `max_gap`, `significant_gap_count`, `dominant_content_type`, `dominant_authority_type`.
- **Company summary**: First ~600 chars of `company_context_md`.
- **Product focus**: Optional product description for product-level runs.

Total budget: ~11K tokens (200 queries x 50 = 10K + 15 clusters x 60 = 900 + company summary).

**Phase 2 — Full Context Extraction (`extract_worker_context()`):**

```python
def extract_worker_context(
    analysis_json: Dict[str, Any],
    approved_query_ids: List[str],      # Only 4-6 approved queries, not 200
) -> Dict[str, WorkerQueryContext]
```

Filters the gaps list to approved IDs only, pulls **complete** QueryGap data including `top_cited_exemplars` with `structural_signals`, and matches to `ClusterContentSpec` by `cluster_name`. Returns `WorkerQueryContext` per approved query with: `query_gap` (full dict), `cluster_spec`, `exemplars`, `gap_content_brief`, `company_best_text`, `company_best_url` (source page URL for optimize-vs-create decisions).

**Formatting functions:**
- `format_scorecard_as_markdown(scorecard)` — Renders cluster overview + per-query table as markdown. Tables are more token-efficient than JSON for tabular data (no repeated keys). Query text truncated to 80 chars. Includes `Cited` column showing self-citation status per query.
- `format_worker_context_as_markdown(context)` — Renders gap analysis, company content (with source URL), company page structural signals vs exemplar comparison, self-citation status, brief targets, exemplars with structural signals, and cluster spec as structured markdown sections.

### 7.5 Stage 1 — Strategic Planner (Agent 1)

**File:** `core/content_engine/strategic_planner.py`
**Prompts:** `core/content_engine/prompts/strategic_planner_prompts.py`

The Strategic Planner performs **triage only** — it does NOT produce content briefs (unlike v1.0). It selects the top-K highest-impact content opportunities from the full query scorecard.

```python
async def select_topics(
    scorecard: PlannerScorecard,
    *,
    max_topics: int = 6,             # Number of topics to select
    user_feedback: str = "",          # From HITL-1 retry
    parent_span: Optional[Any] = None,
) -> StrategicPlannerOutput
```

**Flow:**
1. Format scorecard as markdown tables via `format_scorecard_as_markdown()`
2. Build user prompt via `build_strategic_planner_user_prompt(scorecard_markdown, max_topics, user_feedback)`
3. Truncate to 100K tokens via `truncate_to_token_limit()`
4. Call LLM via `llm_call()` (model: `settings.content_engine_v13_planner_model`, temperature 0.0)
5. Parse response via `safe_parse()` into `StrategicPlannerOutput`
6. Enrich `selection_metadata` with model, token counts
7. Log generation to LangSmith

**Output — `StrategicPlannerOutput`:**
- `selections: List[TopicSelection]` — ranked 4-6 content opportunities
- `selection_metadata: Dict[str, Any]` — model info, token counts

**`TopicSelection` model:**
- `rank: int` — priority order
- `query_ids: List[str]` — which queries this topic consolidates
- `query_texts: List[str]` — human-readable query texts
- `cluster_name: str` — which cluster this topic belongs to
- `rationale: str` — WHY this topic was chosen (must cite gap evidence)
- `consolidation_note: str` — how related queries were merged
- `estimated_impact: Literal["high", "medium", "low"]`

### 7.6 Stage 2 — Brief Builder (Agent 2)

**File:** `core/content_engine/brief_builder.py`
**Prompts:** `core/content_engine/prompts/brief_builder_prompts.py`

The content architect agent. For each approved topic, receives **full** gap analysis detail (exemplar structural signals, content briefs, cluster specs) and produces a detailed `ContentBlueprint`.

```python
async def build_brief(
    context: WorkerQueryContext,
    topic_selection: TopicSelection,
    *,
    company_context_md: str = "",
    persona_mds: Optional[List[str]] = None,
    style_guide_md: str = "",
    brief_id: str = "brief-001",
    parent_span: Optional[Any] = None,
) -> ContentBlueprint
```

**Flow:**
1. Format full context as markdown via `format_worker_context_as_markdown()`
2. Build user prompt via `build_brief_builder_user_prompt()` with context, company, personas, style, topic rationale, query IDs/texts, brief_id
3. Truncate to 150K tokens (Sonnet 4.5 has 200K context window)
4. Call LLM via `llm_call()` (model: `settings.content_engine_v13_brief_builder_model`, max_tokens=8192, temperature 0.0)
5. Parse response via `safe_parse()` into `ContentBlueprint`
6. Set `blueprint.brief_id = brief_id` and `blueprint.gap_context = context`
7. Log generation to LangSmith

**Parallel execution:**

```python
async def build_briefs_parallel(
    contexts: Dict[str, WorkerQueryContext],
    topics: List[TopicSelection],
    *,
    max_concurrent: int = 3,
    brief_id_overrides: Optional[List[str]] = None,  # For re-briefs
    ...
) -> List[ContentBlueprint]
```

Uses `asyncio.Semaphore(max_concurrent)` + `asyncio.create_task()` + `asyncio.gather()`. Each topic runs its own Brief Builder instance concurrently. Follows the same pattern as `workers/dispatcher.py`.

**`brief_id_overrides`:** Index-aligned with topics. Used for re-briefs to prevent collision with original `brief-001`. If shorter than topics, remaining topics get default `brief-{N:03d}` IDs.

**Primary query selection:** Each topic may consolidate multiple queries. The first query's full context (`topic.query_ids[0]`) is used as the primary input to the Brief Builder. If no context found for the primary query, the brief is skipped with a warning.

**`ContentBlueprint` model** (extends `ContentBrief`):
```python
class ContentBlueprint(ContentBrief):
    sections: List[BlueprintSection] = []      # Section-level outline
    territory_queries: List[str] = []          # Related queries covered
    reading_hierarchy: Dict[str, int] = {}     # H2/H3/H4 structure
    must_hit_checklist: List[str] = []         # Non-negotiable items
    user_feedback: str = ""                    # From HITL-2
    gap_context: Optional[WorkerQueryContext]  # Full gap data
    gap_reasoning: List[str] = []              # 3 points on gap overcoming
    tone_voice_description: str = ""           # Voice guidance
    target_persona: str = ""                   # Target audience
    buyer_stage: str = ""                      # Journey stage
    intent_stage: str = ""                     # Search intent
```

**`BlueprintSection` model:**
```python
class BlueprintSection(BaseModel):
    heading: str = ""
    level: int = 2                             # H2, H3, etc.
    key_points: List[str] = []
    target_word_count: int = 300
    structural_elements: List[str] = []        # Required elements
    must_include: List[str] = []               # Non-negotiable items
```

### 7.7 Stage 3 — Content Workers (Orchestrator-Workers)

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

**Worker Chain — v1.0 (4 steps per brief):**

| Step | File | Model | Function | Output |
|------|------|-------|----------|--------|
| 1. Outline | `workers/outliner.py` | Sonnet 4.5 | `generate_outline()` | `ContentOutline` |
| 2. Draft | `workers/drafter.py` | Sonnet 4.5 | `generate_draft()` | `ContentDraft` |
| 3. Enrich | `workers/fact_enricher.py` | Perplexity sonar-pro | `enrich_with_facts()` | `EnrichedDraft` |
| 4. Format | `workers/formatter.py` | Haiku 4.5 | `format_content()` | `FormattedContent` |

**Worker Chain — v1.3 (4 steps per brief, different chain):**

| Step | File | Model | Function | Output |
|------|------|-------|----------|--------|
| 1. Outline | `workers/outliner.py` | Sonnet 4.5 via LiteLLM | `generate_outline()` | `ContentOutline` |
| 2. Draft | `workers/drafter.py` | Sonnet 4.5 via LiteLLM | `generate_draft()` | `ContentDraft` |
| 3. Link | `workers/linker.py` | Perplexity sonar-pro via LiteLLM | `link_content()` | `LinkedDraft` |
| 4. Fact Check | `workers/fact_enricher.py` | Perplexity sonar-pro via LiteLLM | `enrich_with_facts()` | `EnrichedDraft` |

v1.3 replaces the Formatter step with a **Linker agent** that resolves `[INTERNAL-LINK]`, `[EXTERNAL-LINK]`, and `[STAT:]` placeholders. Structural counts are computed inline via `_count_structural_elements()`. The Fact Checker is rewritten from "enrich" to **"verify-only"** (no new content added).

**Each step:**
- Has its own prompt file in `core/content_engine/prompts/`
- Logs a tracing span via LangSmith
- Persists intermediate artifact to disk (v1.0: `outline.json`, `draft.md`, `enriched.md`, `formatted.md`; v1.3: `outline.json`, `draft.md`, `linked.md`, `fact_checked.md`)

**Linker (v1.3 only):** Uses Perplexity sonar-pro via LiteLLM to resolve link/stat placeholders. Accepts site pages from s1 discovery for internal link resolution. Gracefully skips if `PERPLEXITY_API_KEY` not set. Returns `LinkedDraft` with link/stat counts.

**Fact Enricher (v1.0):** Uses httpx to call Perplexity API directly (raw SDK). Gracefully skips if `PERPLEXITY_API_KEY` not set (returns draft unchanged). Detects added citations via regex.

**Fact Checker (v1.3):** Verify-only mode — replaces `[STAT:]` placeholders, verifies existing claims, flags unverifiable claims. Does NOT add new content. Uses LiteLLM.

**Formatter (v1.0 only):** Uses `_count_structural_elements(markdown)` for word count, header count, list count, stat count, and citation count using regex patterns. Uses Haiku 4.5 via raw Anthropic SDK.

**Drafter `revise_draft()`:** Used during evaluator revision cycles and HITL-3 edit feedback to incorporate feedback. Both v1.0 and v1.3 use this method.

### 7.8 Stage 4 — Evaluator-Optimizer Loop

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
    use_eeat: bool = False,           # v1.3: enable E-E-A-T dimension
    use_targeted_revision: bool = False,  # v1.3: dual feedback routing
) -> tuple[FormattedContent, RevisionHistory, FeedbackRoute]
```

Returns a 3-tuple: final content, revision history, and feedback route (`"pass"`, `"section_level"`, or `"major_change"`).

**4+1 Evaluation Dimensions (run in parallel via `asyncio.gather`):**

| Dimension | File | Type | Model | Threshold |
|-----------|------|------|-------|-----------|
| Structural | `evaluator/structural.py` | Deterministic (Python) | None | >= 0.8 |
| Semantic | `evaluator/semantic.py` | Embedding proximity | OpenAI text-embedding-3-small | >= 0.65 |
| Style | `evaluator/style_judge.py` | LLM-as-Judge | Haiku 4.5 | >= 0.7 |
| Factual | `evaluator/factual_judge.py` | LLM-as-Judge | Sonnet 4.5 | >= 0.7 |
| E-E-A-T | `evaluator/eeat_judge.py` | LLM-as-Judge | Sonnet 4.5 | >= 0.7 | (v1.3 only)

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

**E-E-A-T Judge (v1.3 only):** Evaluates Experience, Expertise, Authoritativeness, and Trustworthiness signals. Returns JSON with `score` (0-1) and `feedback`. Uses Sonnet 4.5 as the judge model.

**Revision Logic (v1.0 — `use_targeted_revision=False`):**
1. If any dimension fails -> compile feedback from all failed dimensions
2. Re-run: `revise_draft()` -> `enrich_with_facts()` -> `format_content()` (skip Outliner)
3. Re-evaluate all 4 dimensions
4. If still failing after `max_cycles` -> flag for HITL with eval results attached
5. Early exit when `max_revision_cycles=0` (skip evaluator entirely)

**Revision Logic (v1.3 — `use_targeted_revision=True`, dual feedback routing):**

`FeedbackRoute` enum (`core/models/content_generation_v13.py`):
```python
class FeedbackRoute(str, Enum):
    PASS = "pass"                # All dimensions passed
    SECTION_LEVEL = "section_level"  # Targeted fix
    MAJOR_CHANGE = "major_change"    # Fundamental re-brief
```

`classify_feedback(dimensions)` routes based on failure severity:
- **`"pass"`** — all dimensions passed, no revision needed
- **`"section_level"`** — targeted fix: run only needed workers (drafter + fact_checker)
- **`"major_change"`** — semantic score < 0.5, content direction fundamentally wrong -> flag for re-brief

`_get_targeted_revision_plan(dimensions)` determines workers:
| Failed Dimension(s) | Workers Run |
|---------------------|-------------|
| structural, style, semantic, or eeat | `["drafter", "fact_checker"]` |
| factual only | `["fact_checker"]` |
| drafter + any combo | `["drafter", "fact_checker"]` (always re-verify after drafter revises) |

`_run_targeted_revision()` chain: drafter (if needed) -> fact_checker (if needed) -> inline `_count_structural_elements()` (no formatter step).

**Early-stop:** If score improvement < 0.02 between revision cycles, stop revising and flag as `"section_level"`.

### 7.8.1 Stage 4.5 — CPS Scoring (Citation Signal Predictor)

**Files:** `core/cps_model/scorer.py`, `core/content_engine/pipeline_v13.py` (Stage 4.5 block)

After evaluator approval and before HITL-3 review, every content piece is scored by the CPS model to predict how likely it is to be cited by AI answer engines.

**Architecture:**
- **CPS Model** (~600K params): FusionEncoder (3-stream: semantic projection 1536→256, structural sidecar MLP, engine conditioning 4→16) → CitationPredictor (shared trunk + 4 per-engine heads)
- **Feature Extraction**: 12 structural (HTML), 9 citability (text), 9 authority (URL) = 30 features, delegated to `core/cps_model/extractors/`
- **Embeddings**: OpenAI `text-embedding-3-small` (1536-dim) via `async_embed_texts()`
- **Output**: CPS score 0.0–1.0 per engine (ChatGPT, Claude, Gemini, Perplexity) + weighted average

**Pipeline Integration:**
```
Stage 4 (Evaluator) → Stage 4.5 (CPS) → Stage 5 (HITL-3)
```

- `_score_cps_batch()` scores all evaluated pieces via `asyncio.gather()` with per-piece error handling
- CPS results stored in `eval_summary["cps"]` (Dict[str, Any]) — no Pydantic model changes
- CPS is **informational only** — does not gate approval/rejection
- Graceful degradation: if `torch` is not installed or model checkpoint is missing, scoring is silently skipped

**Return Schema:**
```json
{
  "cps_score": 0.72,
  "per_engine": {"chatgpt_search": 0.75, "claude_search": 0.68, "gemini_search": 0.71, "perplexity": 0.74},
  "per_query": [{"query": "best CRM software", "cps_score": 0.72}],
  "model_version": "v1",
  "feature_config": "option_b_full31",
  "target_weight": 0.5
}
```

**Settings:** `cps_enabled` (bool, default True), `cps_target_weight` (float, default 0.5)

**Tests:** 44 tests in `tests/cps_model/` (scorer + extractors) + `tests/content_engine/test_cps_integration.py` (pipeline integration)

### 7.9 Stage 5 — Human Review (LangGraph HITL)

**File:** `core/content_engine/graph.py` (v1.0), `core/content_engine/graph_v13.py` + `pipeline_v13.py` Stage 5 (v1.3)

**v1.0 Graph HITL:**
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

**Graph nodes:** `present_content` -> `approval_gate` (interrupt) -> `route` -> `finalize` / `apply_edits` / END

**Resume tokens:** `{"approval_decision": "approve"|"edit"|"reject", "editor_notes": "..."}`

**`auto_approve` flag** skips interrupt (same pattern as research pipeline). Approved content saved to `final.md`.

**v1.3 — Three HITL Checkpoints (graph_v13.py):**

| Checkpoint | Graph | When | Decisions |
|------------|-------|------|-----------|
| HITL-1 | `build_topic_approval_graph()` | After Strategic Planner | approve / modify / reject / retry |
| HITL-2 | `build_brief_approval_graph()` | After Brief Builder | approve / feedback / reject (per blueprint) |
| HITL-3 | `build_content_review_graph_v13()` | After Evaluator-Optimizer | approve / edit / reject (per piece) |

All three use `run_hitl_checkpoint()` — an async helper that manages LangGraph interrupt/resume cycles via MemorySaver.

**v1.3 HITL-3 Feedback Loops (pipeline_v13.py Stage 5):**

| Decision | Action | Max Attempts | Constants |
|----------|--------|--------------|-----------|
| `"approve"` | Write `final.md`, status=APPROVED | -- | -- |
| `"edit"` | Route to drafter with `[HUMAN REVIEW]` feedback -> fact checker -> re-evaluate -> re-present | 2 | `_MAX_EDIT_ATTEMPTS = 2` |
| `"reject"` | Route to brief builder for re-brief -> re-dispatch workers -> re-evaluate -> re-present | 2 | `_MAX_REBRIEFS = 2` |

**Edit flow** (`_apply_human_edits()`):
1. `revise_draft(feedback=f"[HUMAN REVIEW]\n{editor_notes}")` — drafter incorporates human notes
2. `enrich_with_facts()` — re-verify facts on revised content
3. `_count_structural_elements()` — compute counts inline (no formatter step)
4. Return `FormattedContent` -> loop back to HITL-3 for re-approval

**Reject/Major-change flow** (`_rebrief_and_rerun()`):
1. Create new `TopicSelection` with `rationale=f"Re-brief after rejection: {user_comment[:200]}"`
2. Extract worker contexts from blueprint's `gap_context`
3. `build_briefs_parallel()` — re-brief with original contexts
4. `dispatch_workers_v13()` — full worker chain on new brief
5. `evaluate_and_optimize()` — full evaluation
6. Return 3-tuple -> loop back to HITL-3 for approval

**Evaluator `major_change` signal:** When `evaluate_and_optimize()` returns `feedback_route="major_change"` (semantic < 0.5), the pipeline automatically triggers `_rebrief_and_rerun()` before presenting at HITL-3, counting against the re-brief limit.

**Permanent rejection:** After exhausting edit or re-brief attempts, content is marked `ContentStatus.REJECTED` with no further retries.

### 7.10 v1.0 Architecture (Preserved)

```
+----------------------------------------------------------------------+
|  [1/4] Strategic Planner (Sonnet 4.5)                                 |
|    Input: gap report + generation spec + company context + personas   |
|    Output: List[ContentBrief] -- prioritized content assignments      |
+------------------+---------------------------------------------------+
                   | spawns N worker chains (asyncio.Semaphore)
                   v
+----------------------------------------------------------------------+
|  [2/4] Content Workers (parallel)                                     |
|    Per brief: Outliner (Sonnet) -> Drafter (Sonnet) ->                |
|               Fact Enricher (Perplexity sonar-pro) ->                 |
|               Formatter (Haiku 4.5)                                   |
|    Output: List[FormattedContent]                                     |
+------------------+---------------------------------------------------+
                   v
+----------------------------------------------------------------------+
|  [3/4] Evaluator-Optimizer Loop (max 2 revision cycles)               |
|    4 dimensions in parallel: Structural (code) + Semantic (embed)     |
|                               + Style (Haiku judge) + Factual         |
|                                 (Sonnet judge)                        |
|    Failed -> compile feedback -> revise -> re-evaluate                |
|    Output: List[FormattedContent] + RevisionHistory                   |
+------------------+---------------------------------------------------+
                   v
+----------------------------------------------------------------------+
|  [4/4] Human Review (LangGraph HITL)                                  |
|    interrupt() -> approve / edit / reject per piece                    |
|    auto_approve flag skips interrupt                                   |
|    Output: List[ContentPiece] with status + final markdown            |
+----------------------------------------------------------------------+
```

**v1.0 Entry Point:** `core/content_engine/pipeline.py` -> `run_content_generation(input_data)`
**v1.0 CLI:** `scripts/run_content_engine.py`

**v1.0 Planner** (`core/content_engine/planner.py`):
- Model: Sonnet 4.5 via `AsyncAnthropic` (raw SDK)
- Single LLM call with structured JSON output
- Context window guard: `truncate_to_token_limit()`
- JSON parsing: `safe_parse()` with code fence extraction and trailing comma cleanup
- Output: `PlannerOutput` with `List[ContentBrief]`

### 7.11 Entry Modes

**`EntryMode` enum:**
- `AUTONOMOUS` — Full pipeline (stages 0-5), reads gap_analysis output automatically
- `MANUAL` — User provides a topic prompt -> inline `WorkerQueryContext` -> stages 2-5 only

**`ContentGenerationInputV13`** (extends `ContentGenerationInput`):
```python
class ContentGenerationInputV13(ContentGenerationInput):
    entry_mode: EntryMode = EntryMode.AUTONOMOUS
    max_topics: int = 6                              # Topics for autonomous planner
    manual_prompt: Optional[str] = None              # Manual mode
    manual_description: Optional[str] = None
    manual_cluster: Optional[str] = None
```

### 7.12 Pydantic Models — v1.3 (12 models)

**File:** `core/models/content_generation_v13.py` (271 lines)

| Model | Purpose |
|-------|---------|
| `QueryScorecard` | Lightweight per-query summary (~50 tokens each) |
| `ClusterSummary` | Per-cluster aggregate (~60 tokens each) |
| `PlannerScorecard` | Complete scorecard for Agent 1 (~11K tokens total) |
| `TopicSelection` | Single topic selected by Agent 1 |
| `StrategicPlannerOutput` | Agent 1 output (selections + metadata) |
| `WorkerQueryContext` | Full gap context for one approved query |
| `BlueprintSection` | Section-level outline within blueprint |
| `ContentBlueprint` | Extended `ContentBrief` from Agent 2 |
| `EntryMode` | Enum: `AUTONOMOUS` / `MANUAL` |
| `ManualPromptInput` | User input for manual mode |
| `ContentGenerationInputV13` | Extended pipeline input |
| `FeedbackRoute` | Enum: `PASS` / `SECTION_LEVEL` / `MAJOR_CHANGE` |
| `LLMResponse` | Standardized LiteLLM response wrapper |

All fields have defaults for backward compatibility with existing JSON artifacts.

### 7.13 Artifact Structure

**v1.0:**
```
artifacts/content/{company-slug}/
  briefs.json                    # PlannerOutput (all briefs)
  content/
    brief-{N}/
      outline.json               # ContentOutline
      draft.md                   # Raw draft markdown
      enriched.md                # Fact-enriched markdown
      formatted.md               # Style-formatted markdown
      eval_history.json          # RevisionHistory
      final.md                   # Approved content
  run_metadata.json              # ContentGenerationOutput
```

**v1.3:**
```
artifacts/content/{company-slug}/
  planner_output.json            # StrategicPlannerOutput (topics)
  blueprints.json                # List[ContentBlueprint] (briefs)
  content/
    brief-{N}/
      outline.json               # ContentOutline (with voice_tone_description)
      draft.md                   # Raw draft with link placeholders
      linked.md                  # After Linker: resolved links
      fact_checked.md            # After Fact Checker: verified claims
      eval_history.json          # RevisionHistory
      final.md                   # Approved content
  run_metadata.json              # ContentGenerationOutput
```

### 7.14 Utility Modules

**File:** `core/content_engine/utils.py`

| Function | Purpose |
|----------|---------|
| `safe_parse(text, model_cls)` | Extract JSON from LLM response (code fences, trailing commas) -> Pydantic model |
| `_retry_async_anthropic(fn, max_retries, base_delay)` | Provider-agnostic retry with jittered exponential backoff (Anthropic + OpenAI errors) |
| `_estimate_tokens(text)` | Approximate token count (chars / 3.5) |
| `truncate_to_token_limit(text, max_tokens, label)` | Pre-flight context window guard -- truncates by paragraph |

### 7.15 Input Sources

**v1.0 Input:**
- `generation_spec.json` from Pipeline 2 (cluster content specs)
- `gap_report.json` from Pipeline 2 (prioritized content recommendations)
- Research artifacts from Pipeline 1 (company context, personas, style guide)
- `analysis.json` from Pipeline 2 (semantic analysis data)

**v1.3 Input (AUTONOMOUS mode):**
- `analysis.json` from Pipeline 2 (semantic analysis data — used by ContextRouter)
- Research artifacts from Pipeline 1/1b (company context, personas, style guide)
- Gap analysis output drives topic selection through scorecard extraction

**v1.3 Input (MANUAL mode):**
- User-provided `manual_prompt`, `manual_description`, `manual_cluster`
- Research artifacts from Pipeline 1/1b

**Output (both versions):**
- Content pieces in `artifacts/content/{slug}/content/brief-{N}/final.md`
- Run metadata in `artifacts/content/{slug}/run_metadata.json`
- Per-brief intermediate artifacts (outline, draft, linked/enriched, eval_history)

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
- Reads artifact files from `artifacts/` directory
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

### 9.2 DeepAgents Backend Routing (REMOVED)

> The DeepAgents `CompositeBackend` and `base.py` were part of the old research pipeline, which has been fully removed.
> The new research pipelines (KB, AP, VSG) use direct filesystem storage via their own `Storage` classes
> (`KBStorage`, `PersonaStorage`, `VSGStorage`), each with versioned document management and manifest tracking.

### 9.3 pgvector Vector Store

**File:** `core/shared_tools/vector_store.py`

**Purpose:** PostgreSQL-backed vector storage for gap analysis embeddings. Requires `DATABASE_URL` to be set.

**Tables:**
- `persona_embeddings` — Company asset embeddings (from S1), `Vector(1536)` with HNSW index
- `cps_training_snippets` — Citation paragraph embeddings (from S5)
- `cps_training_queries` — Query embeddings for training data

**Configuration:**
```python
# Requires DATABASE_URL environment variable (PostgreSQL with pgvector extension)
# HNSW indexes created via Alembic migration 0002_hnsw_indexes.py
```

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `upsert_embeddings(slug, ids, texts, embeddings, metadatas)` | Batch upsert to `persona_embeddings` |
| `get_embeddings_by_ids(slug, ids)` | Retrieve specific embeddings by ID |
| `get_all_embeddings(slug)` | Retrieve all embeddings for a company |
| `collection_exists(slug)` | Check if embeddings exist for company |
| `delete_company_embeddings(slug)` | Delete for re-runs (idempotent) |
| `upsert_citation_embeddings(slug, ids, docs, embeddings, metadatas)` | Citation-specific upsert to `cps_training_snippets` |

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

**Current Status:** Interface defined but no concrete backend classes implemented yet. The new research pipelines use their own versioned storage classes (`KBStorage`, `PersonaStorage`, `VSGStorage`).

### 9.6 Knowledge Document Storage (Added 2026-02-27)

**Location:** `artifacts/knowledge_docs/{effective_slug}/`

**Storage Layout:**
```
artifacts/knowledge_docs/
├── ramp/                               # Company-level docs
│   ├── _metadata.json                  # List[KnowledgeDocument] — sidecar tracking
│   ├── {uuid}_positioning-doc.md       # UUID-prefixed collision-safe filename
│   └── {uuid}_competitive-analysis.pdf
├── ramp__corporate-card/               # Product-level docs
│   ├── _metadata.json
│   └── {uuid}_product-brief.docx
└── carta/
    └── _metadata.json
```

**`_metadata.json` format:** JSON array of `KnowledgeDocument` objects (from `core/models/knowledge_docs.py`):
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "positioning-doc.md",
    "stored_filename": "550e8400-e29b-41d4-a716-446655440000_positioning-doc.md",
    "content_type": "text/markdown",
    "file_size_bytes": 2048,
    "word_count": 350,
    "uploaded_at": "2026-02-27T10:00:00Z",
    "uploaded_by": "user-uuid",
    "company_slug": "ramp",
    "product_slug": null,
    "effective_slug": "ramp",
    "is_embedded": true,
    "last_embedded_at": "2026-02-27T12:00:00Z"
  }
]
```

**Supported formats:** `.md`, `.txt`, `.pdf`, `.docx` (10MB per file default limit)

**Thread safety:** All metadata reads/writes go through `core/shared_tools/knowledge_doc_metadata.py` which provides a single process-wide `metadata_lock` (threading.Lock). Atomic writes via temp file + `os.replace()`. Both the upload service and s1 pipeline step share this lock.

**Pipeline integration:** Knowledge docs are auto-included in s1's embedding phase. After embedding, `is_embedded` and `last_embedded_at` are updated in `_metadata.json`.

### 9.7 Pipeline Defaults Storage (Added 2026-02-27)

**Location:** `artifacts/_auth/settings/{company_slug}.json`

**Format:** `CompanyPipelineDefaults` model (from `core/models/organization.py`):
```json
{
  "max_crawl_pages": 300,
  "max_crawl_depth": 3,
  "max_queries": null,
  "platforms": null,
  "max_personas": null,
  "auto_approve_research": false,
  "max_briefs": null,
  "max_revision_cycles": null,
  "auto_approve_content": false
}
```

**Merge strategy:** Request-level values always take precedence. Company defaults fill in `None`/unset fields. Global settings are the final fallback.

### 9.8 SQLAlchemy Database Layer (Phase 1 — Added 2026-02-27)

**Package:** `core/db/` — SQLAlchemy 2.0 Declarative + asyncpg + Alembic

**Architecture:** Pure SQLAlchemy 2.0 (NOT SQLModel). Three-tier model architecture: core Pydantic models (contracts between pipeline steps), API schemas (request/response), ORM models (database persistence). Repository layer handles conversion between ORM and Pydantic models.

**Key Design Decisions:**
- **Lazy engine initialization:** `get_engine()` creates the engine on first call, NOT at import time. Existing pipeline scripts without `DATABASE_URL` are completely unaffected.
- **Native Postgres UUID PKs:** `PgUUID(as_uuid=True)` — 16 bytes vs 36 bytes for String(36). Repo layer handles `str ↔ uuid.UUID` conversion.
- **Flush-only repository contract:** Repos call `session.add()` + `session.flush()` only. The DI session generator (`get_db_session()`) owns `commit()` on success and `rollback()` on error. This enables savepoint-based test isolation AND multi-repo atomic transactions.
- **Computed `database_url_sync`:** Derived from `database_url` by replacing `+asyncpg` with standard `postgresql://`. Single source of truth prevents sync/async URL drift.

**Schema:** 31 ORM tables across 10 model files:
- **Organization (5):** companies, products, users, invites, company_pipeline_defaults
- **Pipeline (2):** pipeline_runs (self-ref FK, partial index on active runs), pipeline_stage_logs
- **Cache (3):** platform_result_cache, url_enrichment_cache, url_structural_signals (45 individual typed columns)
- **Gap Analysis (7):** run_queries, run_citations (composite FK), query_gaps, query_exemplars, cluster_specs, spa_results, centroid_results
- **Embeddings (4):** semantic_units, query_embeddings, paragraph_embeddings, run_paragraph_scores — all with pgvector `Vector(1536)` + HNSW indexes
- **Content (2):** content_pieces, research_artifacts
- **Tracking (3):** tracking_snapshots (partial unique indexes for NULL handling), content_mention_tracking, content_piece_tracking
- **Site Audit (2):** site_audits, audit_findings
- **Topic Discovery (2):** topic_discoveries, discovered_topics
- **Knowledge Docs (1):** knowledge_documents

**Enum Types (12):** UserRole, PipelineType, PipelineStatus, StageStatus, SearchEngine, GapClassification, ArtifactType, ArtifactStatus, ContentPieceStatus, FindingSeverity, TrackingStatus

**Repositories (8 domain + 1 generic base):**
- Generic `SQLAlchemyRepository[ModelT]` with `get_by_id`, `create`, `update`, `delete`, `list_all`
- Domain repos extend with specific methods (e.g., `cache_repo.get_fresh_platform_result()` with TTL check, `embedding_repo.similarity_search()` with pgvector cosine_distance)

**Alembic Migrations:**
- `0001_initial_schema.py` — Hand-written (not autogenerated). Creates pgvector extension, 12 enums, 31 tables, FKs with ON DELETE policies (CASCADE/SET NULL/RESTRICT), partial indexes.
- `0002_hnsw_indexes.py` — HNSW vector indexes separated for deployment control (index creation can lock tables on large datasets).

**Phase 1 Status:** Infrastructure complete. Fully wired into routers via Phase 2 (auth) and Phase 3 (data services, TaskStore). See §26 for comprehensive 3-phase migration documentation.

**Dependencies:** `sqlalchemy[asyncio]>=2.0.30`, `asyncpg>=0.29`, `psycopg2-binary>=2.9` (sync driver for Alembic), `alembic>=1.13`, `pgvector>=0.3`

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

**Knowledge Document Model (`core/models/knowledge_docs.py`) — added 2026-02-27:**
```
KnowledgeDocument:   id (UUID str), filename (original), stored_filename (uuid_name on disk),
                     content_type (MIME), file_size_bytes (default 0), word_count (default 0),
                     uploaded_at (datetime, default factory), uploaded_by (Optional[str]),
                     company_slug (default ""), product_slug (Optional[str]),
                     effective_slug (default ""), is_embedded (bool, default False),
                     last_embedded_at (Optional[datetime])
```

**Organization Model (`core/models/organization.py`) — added 2026-02-27:**
```
CompanyPipelineDefaults: max_crawl_pages (Optional[int]), max_crawl_depth (Optional[int]),
                         max_queries (Optional[int]), platforms (Optional[List[str]]),
                         max_personas (Optional[int]), auto_approve_research (bool = False),
                         max_briefs (Optional[int]), max_revision_cycles (Optional[int]),
                         auto_approve_content (bool = False)
```

**Site Discovery Models:**
```
DiscoverySource:     Enum (SITEMAP, SITEMAP_INDEX, ROBOTS_TXT, BFS_CRAWL, CANONICAL,
                           HREFLANG, RSS_FEED, SEED_URL, REDIRECT, KNOWLEDGE_DOC)
DiscoveredPage:      url, title, h1, meta_description, status_code, discovery_source,
                     depth, parent_url, canonical_url, word_count, has_content
SiteTreeNode:        url, title, path_segment, children, page_count_below
SiteDiscoveryResult: domain, base_url, total_pages, pages, site_tree, crawl_duration
```

**Pipeline Models:**
```
GapAnalysisInput:    company_name, domain, seed_urls, max_queries (default 150),
                     platforms (default: all 4), max_crawl_pages (500), max_crawl_depth (4),
                     knowledge_doc_dir (Optional[str], default None) — resolved by runner
SemanticUnit:        unit_id, url (Optional — None for knowledge docs), title, text,
                     embedding, embedding_id, char/word_count,
                     discovery_source (Optional[str] — "knowledge_doc" for uploaded docs)
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
ContentOutline:    brief_id, title, sections: List[OutlineSection], total_target_words,
                   voice_tone_description: str = ""  (v1.3: forwarded from brief to drafter)
ContentDraft:      brief_id, title, markdown, word_count
EnrichedDraft:     brief_id, title, markdown, word_count, facts_added: List[Dict]
LinkedDraft:       brief_id, title, markdown, word_count,   (v1.3: output of Linker worker)
                   internal_links_added (int), external_links_added (int), stats_resolved (int)
FormattedContent:  brief_id, title, markdown, word_count, header_count, list_count,
                   stat_count, citation_count
```

**Stage 3 Models:**
```
DimensionResult:   dimension ("structural"|"semantic"|"style"|"factual"|"eeat"),
                   passed, score (0-1), feedback, details: Dict
EvalResult:        brief_id, cycle, dimensions: List[DimensionResult],
                   overall_passed, overall_score
RevisionHistory:   brief_id, cycles: List[EvalResult], final_passed
FeedbackRoute:     Literal["pass", "section_level", "major_change"]  (v1.3: evaluator return signal)
```

**Stage 4 Models:**
```
ContentStatus:     Enum: PENDING, APPROVED, EDITED, REJECTED
ContentPiece:      brief_id, title, status (ContentStatus), final_markdown,
                   eval_summary: Dict, human_notes, artifact_path
ContentGenerationOutput: company_slug, total_briefs, total_approved, total_rejected,
                        pieces: List[ContentPiece], run_metadata: Dict
```

### Content Engine v1.3 Models (`core/models/content_generation_v13.py`)

```
TopicSelection:    topic_title, content_format, target_cluster, target_queries,
                   rationale (gap-based reasoning), priority_score,
                   funnel_stage, estimated_word_count
StrategicPlannerOutput: topics: List[TopicSelection], planning_metadata: Dict
ContentBlueprint   (extends ContentBrief):
                   gap_context: Dict, gap_reasoning: List[str] = [],
                   tone_voice_description: str = "", target_persona: str = "",
                   buyer_stage: str = "", intent_stage: str = ""
ContentGenerationInputV13: company_name, domain, analysis_json_path (str),
                   company_context_path, persona_paths, style_guide_path,
                   max_briefs (10), max_concurrent_workers (3),
                   max_revision_cycles (2), auto_approve (False),
                   skip_stages ([]), user_prompt (Optional, for MANUAL mode)
WorkerQueryContext: query_id, cluster_name, query_text, gap, interpretation,
                   content_brief (GapContentBrief), exemplars
PlannerScorecard:  total_queries, coverage_summary, top_gaps: List[Dict]
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
| `DATABASE_URL` | — | PostgreSQL connection URL (required for pgvector vector storage) |
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

#### Observability (LangSmith — Sole Backend)

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGSMITH_API_KEY` | — | LangSmith API key (required for tracing and Hub prompts) |
| `LANGSMITH_PROJECT` | — | LangSmith project name for trace grouping |
| `LANGSMITH_WORKSPACE_ID` | — | Optional workspace ID for multi-workspace setups |
| `LANGSMITH_USE_HUB` | `false` | Enable LangSmith Hub prompt pulling (prompt registry) |
| `LANGSMITH_HUB_TAG` | `production` | Version tag for Hub prompt pinning |

> **Note:** Langfuse environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) are no longer used. Langfuse was fully removed 2026-03-02.

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
database_url_sync:          Derived from DATABASE_URL (replaces +asyncpg with postgresql://)
```

#### Optional — Database (PostgreSQL + SQLAlchemy) — Added 2026-02-27

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `None` | PostgreSQL async URL (`postgresql+asyncpg://...`). DB layer is opt-in — `None` means no DB. |
| `DATABASE_ECHO` | `false` | Enable SQLAlchemy SQL logging |
| `DATABASE_POOL_SIZE` | `5` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | `10` | Max overflow connections beyond pool size |
| `PLATFORM_CACHE_TTL_DAYS` | `7` | Re-search platforms after N days (cache repo TTL) |
| `URL_ENRICHMENT_CACHE_TTL_DAYS` | `14` | Re-scrape URLs after N days (cache repo TTL) |
| `TEST_DATABASE_URL` | — | Test database URL. If not set, all 44 DB tests auto-skip. |

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
├── conftest.py                           # Shared fixtures (mock clients)
├── shared_tools/
│   ├── test_async_embedding_client.py    # Async embedding client tests
│   └── test_vector_store.py             # pgvector store tests
├── gap_analysis/
│   └── steps/
│       ├── test_s1_embed_assets.py       # Site discovery + embedding tests
│       ├── test_s2_generate_queries.py   # Query generation tests
│       ├── test_s4_enrich_citations.py   # Citation enrichment tests (11 tests — ALL PASSING)
│       ├── test_s4_main_content.py       # Main content extraction tests (5 tests)
│       ├── test_s4_structural_signals.py # Expanded structural signals tests (16 tests)
│       ├── test_s5_embed_content.py      # Content embedding tests
│       ├── test_s6_analyze.py            # GapContentBrief + ClusterContentSpec tests (8 tests)
│       ├── test_s7_projections.py        # UMAP/t-SNE projection export tests (12 tests)
│       └── test_s8_generate_report.py    # Report generation tests (11 tests incl. Phase 3)
├── gap_analysis/
│   └── test_pipeline.py                  # Gap analysis pipeline orchestrator tests
├── research/                             # 109 tests — ALL PASSING (added 2026-02-26)
│   ├── conftest.py                       # 9 fixture categories (singleton reset, MockDeepAgent, isolated_artifacts, mock mirrors)
│   ├── agents/
│   │   ├── test_base.py                  # 10 tests — InMemoryStore, CompositeBackend, FilesystemBackend, singletons
│   │   ├── test_company_research_agent.py # 13 tests — internet_search, read_local_text, build/get agent, _extract_final_markdown
│   │   ├── test_persona_agent.py          # 11 tests — build/get agent, run_persona_agent (JSON parse, disk fallback, slug derivation)
│   │   └── test_style_guide_agent.py      # 9 tests — build/get agent, run_style_guide_agent (default paths, revision note)
│   ├── tools/
│   │   └── test_perplexity_client.py      # 11 tests — _client() validation, research(), search(), error handling (401/429)
│   └── graphs/
│       ├── test_company_graph.py          # 16 tests — full HITL (auto-approve, interrupt, approve/reject/revise) + helpers
│       ├── test_persona_graph.py          # 13 tests — multi-file draft promotion, all 3 approval paths, cleanup
│       ├── test_style_graph.py            # 10 tests — backend write fallback, all 3 approval paths, empty draft handling
│       └── test_pipeline.py              # 16 tests — stage sequencing, context passing, interrupt early-exit, optional stages
├── api/                                   # 305+ tests — ALL PASSING
│   ├── conftest.py                        # Fixtures: client, app, task_store, artifacts_root, auth_store
│   ├── test_health.py                     # Health + readiness endpoints
│   ├── test_gap_analysis.py               # Start pipeline, status polling, skip_steps
│   ├── test_research.py                   # Start pipeline, HITL approval flow
│   ├── test_content.py                    # Start pipeline, HITL per-brief approval
│   ├── test_events.py                     # SSE streaming, Last-Event-ID, terminal events
│   ├── test_artifacts.py                  # Company listing, artifact retrieval
│   ├── test_tasks.py                      # Task CRUD, filtering, cancellation
│   ├── test_store.py                      # TaskStore persistence, slug locks, approval events
│   ├── test_event_bus.py                  # Pub/sub, history replay, subscriber lifecycle
│   ├── test_runner.py                     # Background task wrappers, graph interrupt/resume
│   ├── test_auth_endpoints.py             # POST login, GET /me, token validation (Phase 1)
│   ├── test_auth_store.py                 # AuthStore CRUD, hashing, token sign/verify (Phase 1)
│   ├── test_companies.py                  # GET /companies/{slug}, artifact scanning (Phase 1)
│   ├── test_registration.py               # 25 tests — domain normalization, company dedup, roles (Phase 1)
│   ├── test_tasks_extended.py             # company_slug filter, total field (Phase 1)
│   ├── test_gap_data.py                   # 67 tests — all 8 gap data endpoints + ?product_slug= variants (Phase 2+3+5)
│   ├── test_content_data.py               # 79 tests — brief list/detail/stage + ?product_slug= variants (Phase 3+5)
│   ├── test_brand_data.py                 # 57 tests — artifacts, personas, run history, SPA trend, status mapping (Phase 4)
│   ├── test_products.py                   # 35 tests — product CRUD, slug validation, ownership checks (product-pipeline P1)
│   ├── test_task_store_product.py         # 16 tests — effective_slug locking, company+product coexistence (product-pipeline P2)
│   ├── test_gap_analysis_product.py       # 36 tests — RunScope, _resolve_scope, fallback chain, lock conflicts (product-pipeline P3)
│   ├── test_gap_analysis.py (guard)      # +7 new: TestStartGapAnalysisGuard — dual-sentinel, force_rerun, existing-prefix run_id, product-level dir
│   ├── test_research.py (guard)          # +5 new: TestStartResearchGuard — all-stages, partial stages, draft exclusion, force_rerun
│   ├── test_auth_enforcement.py          # 42 tests — auth enforcement: middleware, RBAC, tenant isolation, stream tokens
│   ├── test_settings_team.py             # 16 tests — team management: list, update role, deactivate, guards
│   ├── test_settings_profile.py          # 11 tests — company profile: get, update, auth checks
│   ├── test_settings_pipeline.py         # 12 tests — pipeline defaults: get, update, merge with runner
│   ├── test_knowledge_docs.py            # 19 tests — upload, list, get, delete, download, oversized, bad extension
│   └── test_s1_knowledge_docs.py         # (in gap_analysis/) 15 tests — s1 integration: load, chunk, embed, mark status
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
├── core/test_site_audit/                # 585 tests — Site Audit Module (Pipeline 0) (added 2026-02-28)
│   ├── __init__.py
│   ├── test_models.py                    # 52 tests — Pydantic model validation, enum coverage, defaults
│   ├── test_config.py                    # 42 tests — AuditConfig, weights sum, grade thresholds, penalties, pipeline signature
│   ├── test_crawler.py                   # 60 tests — AsyncSiteCrawler 4-phase discovery, AI bot detection, MockTransport
│   ├── test_checks.py                    # 86 tests — crawlability, on_page_seo, eeat_signals, security check modules
│   ├── test_schema.py                    # 76 tests — JSON-LD parsing, @graph handling, type validation, findings
│   ├── test_aeo.py                       # 125 tests — AEO readiness scoring, extractability, question headings, hooks
│   ├── test_steps.py                     # 59 tests — s2_analyze_pages, s3_check_schema, s4_check_aeo integration
│   ├── test_repo.py                      # 24 tests — SiteAuditRepository flush-only contract
│   └── test_integration.py              # 61 tests — scoring, aggregation, report generation, pipeline wiring
├── db/                                   # 44 tests — auto-skip without TEST_DATABASE_URL (added 2026-02-27)
│   ├── __init__.py
│   ├── conftest.py                       # Async fixtures, savepoint isolation with restart logic, sample_company/user/pipeline_run
│   ├── test_models.py                    # 12 tests — table creation, constraint enforcement, enum types
│   ├── test_organization_repo.py         # 5 tests — company CRUD, get_by_slug, get_by_domain, list_active
│   ├── test_auth_repo.py                # 4 tests — user CRUD, get_by_email, list_by_company
│   ├── test_pipeline_repo.py            # 6 tests — pipeline run CRUD, stage logs, status transitions
│   ├── test_cache_repo.py               # 6 tests — platform/URL enrichment cache, TTL hit/miss, upsert
│   ├── test_gap_analysis_repo.py        # 6 tests — bulk insert query gaps, update, cluster specs
│   └── test_embedding_repo.py           # 5 tests — pgvector store, similarity search, generic embedding
```

**Test counts:** ~1978 total tests (~1843 passed + 135 skipped), 1 pre-existing failure (PB-39). **Site Audit sprint added 636 tests** (585 core + 51 API) — models: 52, config: 42, crawler: 60, checks: 86, schema: 76, AEO: 125, steps: 59, repo: 24, integration: 61, API: 51. Research pipeline coverage added 2026-02-26 (+109 tests). Front-back integration sprint added 343 tests across 4 phases. Product-level pipeline sprint added 114 tests across 5 phases. Pipeline guard sprint added 12 tests. Route protection sprint added 44 tests. Settings + Knowledge Docs sprint added 77 tests. SQLAlchemy migration sprint added 44 DB tests — auto-skip without `TEST_DATABASE_URL`. S4 mock regression fixed in Phase -1 of structural signal overhaul.

### API Test Coverage (526+ tests — 126 base + 179 front-back + 114 product-level + 12 pipeline-guard + 44 route-protection + 51 site-audit)

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

### Front-Back Sprint API Tests (179 new tests — added 2026-02-25/26)

| Test File | Count | What's Tested |
|-----------|-------|---------------|
| `test_auth_endpoints.py` | ~10 | POST /login (email+password→token), GET /me (Bearer token→user+company), invalid credentials, expired tokens |
| `test_auth_store.py` | ~15 | AuthStore CRUD, PBKDF2 password hashing, HMAC token sign/verify, company lookup, user deactivation |
| `test_registration.py` | 25 | Domain normalization (multi-part TLDs, subdomains, port stripping), company dedup by root domain, first-user=superuser, subdomain preservation in additional_domains, email validation, password min/max length |
| `test_companies.py` | ~12 | Company profile endpoint, artifact scanning, task history, product list, missing company 404 |
| `test_tasks_extended.py` | ~5 | `company_slug` filter, `total` field in TaskListResponse |
| `test_gap_data.py` | 67 | All 8 gap data endpoints + `?product_slug=` variants (effective slug, missing product dir, all 8 pass no 422), old+new format backward compat, pagination, filtering, sorting, slug validation, Pearson correlation, Jaccard similarity, empty state |
| `test_content_data.py` | 79 | Brief list/detail/stage + `?product_slug=` variants (effective slug, independent dirs, missing dir 200 empty, brief detail, stage content, company dir without product_slug), 2-phase status inference, eval history, citability score, path traversal protection |
| `test_brand_data.py` | 57 | Research artifact detection (approved/draft/none), persona scanning with prefix filter (CX-4), run history with status mapping (running/pending_approval/failed/cancelled), duration formatting, SPA trend computation, NaN guards, gap metric extraction, step inference, limit param |

### Product-Level Pipeline Sprint Tests (114 new tests — added 2026-02-26)

| Test File | Count | What's Tested |
|-----------|-------|---------------|
| `test_products.py` | 35 | Product CRUD endpoints: create (valid, invalid slug, duplicate, 404 company), get (200, 404), update (name/domain/description, 404), delete (200, 404), ownership check (product.company_id == user.company_id), slug format validation (`^[a-z0-9][a-z0-9-]*$`) |
| `test_task_store_product.py` | 16 | `create_task(product_slug=...)` uses effective_slug for lock, company-level and product-level locks coexist (both 202), same-product second run conflicts (409), `list_tasks(product_slug=...)` filter, effective_slug stored on task, cancel uses task.effective_slug for teardown |
| `test_gap_analysis_product.py` | 36 | `_derive_slug()` unit tests, `_resolve_scope()` unit tests (found/not found/no product), `resolve_artifacts()` fallback chain (effective → company → None for context/personas/style), gap analysis start with product_slug (202), company+product coexistence (both 202), same-product conflict (409), `GapAnalysisInput`/`ContentGenerationInput`/`CompanyResearchInput` product fields |
| `test_s2_product_context.py` | 15 | `_PRODUCT_CONTEXT_BLOCK` constant has all format slots, `_build_seed_prompt()` with product context present/absent, `generate_queries()` prompt capture: contains product block when product_slug+product_name set, no block for company-level, `build_planner_user_prompt()` injects product section after `## Company` |

### Route Protection Sprint Tests (44 new tests — added 2026-02-27)

| Test File | Count | What's Tested |
|-----------|-------|---------------|
| `test_auth_enforcement.py` | 42 | Middleware enforcement (public routes, 401 without token, expired/malformed tokens, valid token), deactivated user 401, role-based access (viewer blocked from pipelines/products/invites, member/superuser allowed), tenant isolation (cross-company profile/pipeline/task/gap-data/content-data/artifact access → 403, task auto-filter by company), stream tokens (creation, task ownership, expiry behavior), registration hardening (isolated company, domain-taken 409, invite flow, invite requires superuser), login constant-time behavior |
| `test_registration.py` | 2 | Invite flow join + invite code single-use (added alongside Phase 3 hardening) |

### Content Engine Test Coverage — v1.0 (57/57 passing)

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

### Content Engine Test Coverage — v1.3 (257/257 passing, added 2026-03-02)

| Test File | Count | What's Tested |
|-----------|-------|---------------|
| `test_context_router.py` | 25 | `extract_scorecard()`, `extract_worker_context()`, markdown formatting, edge cases |
| `test_llm_client.py` | 12 | `_ensure_litellm_model()` prefix mapping (8 providers), `llm_call()` success/retry/error |
| `test_v13_models.py` | 10 | JSON roundtrip for all v1.3 models, `ContentBlueprint` extends `ContentBrief`, enums, defaults |
| `test_strategic_planner.py` | 15 | `select_topics()` with mocked `llm_call`, ranking, metadata, feedback, max_topics, JSON fallback |
| `test_brief_builder.py` | 20 | `build_brief()`, `build_briefs_parallel()`, concurrency, error propagation, unique IDs |
| `test_eeat_judge.py` | 10 | `evaluate_eeat()` → `DimensionResult`, score thresholds, markdown fences, JSON fallback |
| `test_tracing_v13.py` | 8 | Session ID format, graceful degradation, span create/end, flush |
| `test_evaluator_v13.py` | 8 | `classify_feedback()` (pass/section_level/major_change), `_get_targeted_revision_plan()` routing |
| `test_graph_v13.py` | 49 | 3 HITL graphs (topic/brief/content), node functions, routing, `run_hitl_checkpoint()` loop |
| `test_pipeline_v13.py` | 14 | Autonomous + manual modes, skip stages, topic/brief rejection, artifact persistence |
| `test_v13_persistence.py` | 12 | `persist_v13_planner_output()`, `persist_v13_brief_approval()`, noop guards, DB error handling |
| `test_content_v13.py` (API) | 28 | 5 endpoints: start (202/403/401/422), status, 3 approval endpoints with validation |

**Bugs found via TDD:** 5 router bugs caught by integration tests (effective_slug→product_slug, missing pipeline Literal, wrong field names, submit_approval signature mismatch, approval_payload flow).

### Research Pipeline Test Coverage (109/109 passing — added 2026-02-26)

| Test File | Count | What's Tested |
|-----------|-------|---------------|
| `test_base.py` | 10 | InMemoryStore singleton, CompositeBackend routes, FilesystemBackend, get_backend caching |
| `test_company_research_agent.py` | 13 | internet_search → Perplexity, read_local_text (truncation, missing file), agent build/cache, _extract_final_markdown (dict, BaseMessage, tool calls, list blocks) |
| `test_persona_agent.py` | 11 | Agent build/cache, run_persona_agent: JSON parse, non-JSON fallback, disk fallback, slug derivation, revision note, draft vs final paths |
| `test_style_guide_agent.py` | 9 | Agent build/cache, run_style_guide_agent: JSON parse, non-JSON fallback, disk fallback, default persona paths, revision note, single file output |
| `test_perplexity_client.py` | 11 | _client() API key validation, research() with/without citations, empty choices, content=None, 401/429 error handling, search() delegation |
| `test_company_graph.py` | 16 | Full HITL: auto-approve (write artifact, delete draft, set output_path+mirrored), interrupt (pending_approval payload), resume approve/reject/revise, _write_temp_draft, _cleanup_drafts, _overwrite_virtual_path, _extract_final_markdown list blocks |
| `test_persona_graph.py` | 13 | Multi-file draft promotion (single + multiple), empty draft skipped, HITL interrupt/resume all 3 paths, _cleanup_drafts (multiple, missing, no-drafts-on-disk) |
| `test_style_graph.py` | 10 | Draft promotion, backend write fallback ("already exists"), HITL interrupt/resume all 3 paths, cleanup on reject, empty draft skipped |
| `test_pipeline.py` | 16 | _has_interrupt/_get_interrupt_value helpers, full pipeline auto-approve, company-only, interrupt at each stage, context passing (company→persona, persona→style), optional stage skip, individual stage delegation |

### Remaining Test Gaps

#### Gap Analysis Tests (partial coverage)
- [ ] Steps s3, s7 integration tests
- [ ] Step-to-step data flow validation
- [ ] Platform subset selection

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
├── pgvector + SQLAlchemy → PostgreSQL vector storage (replaces ChromaDB)
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

Database (added 2026-02-27):
├── sqlalchemy[asyncio] v2.0.30+ → ORM, async engine, session factory (core/db/)
├── asyncpg v0.29+ → PostgreSQL async driver (used by create_async_engine)
├── psycopg2-binary v2.9+ → PostgreSQL sync driver (required by Alembic for migrations)
├── alembic v1.13+ → Database migration framework (core/db/migrations/)
└── pgvector v0.3+ → PostgreSQL vector extension bindings (Vector(1536) column type)
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

### Decision 5: pgvector for Vector Storage

**Choice:** Use pgvector (PostgreSQL extension) for embedding storage during gap analysis. Migrated from ChromaDB.

**Rationale:**
- Multi-tenant production-ready (row-level company scoping)
- Persistent across process restarts
- Fast cosine similarity queries via HNSW indexes
- Unified storage layer — same PostgreSQL instance as other application data
- Tables: `persona_embeddings`, `cps_training_snippets`, `cps_training_queries`

**Requirement:** `DATABASE_URL` must be set. pgvector extension enabled via Alembic migration.

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

### Decision 11: LangSmith for Observability (Langfuse Removed)

**Choice:** LangSmith as the sole tracing backend across all pipelines (content engine, knowledge base, research agents).

**Original choice (2026-02-15):** Langfuse was initially chosen for its open-source self-hosting option and Session → Trace → Span → Generation hierarchy. Migrated from Langfuse v2 to v3 API (2026-02-16).

**Migration to LangSmith (2026-03-02):** Langfuse was **fully removed**. LangSmith replaced it as the sole tracing backend. Rationale:
- Native integration with LangGraph ecosystem (LangGraph Studio, prompt registry)
- `RunTree` from `langsmith.run_trees` provides parent-child span hierarchy
- LangSmith Hub prompt registry enables version-pinned prompt management
- LiteLLM `success_callback = ["langsmith"]` provides automatic LLM call tracing
- `contextvars.ContextVar` pattern solves LangGraph sync-node span propagation (RunTree can't be serialized by MemorySaver's msgpack)
- Shared module `core/shared_tools/tracing.py` (~507 lines) used by ALL pipelines
- Backward-compatible Langfuse kwargs absorbed silently — migration was import-swap only

**Tradeoff:** No self-hosting option (cloud-only). Requires `LANGSMITH_API_KEY`. See §7.3 for full architecture.

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

### Decision 13: Pipeline Guard — HTTP 200 Skip for Existing Artifacts (D-GUARD-1)

**Choice:** When `force_rerun=false` (default) and complete artifacts already exist for the requested `effective_slug`, return HTTP 200 with `already_exists=true` instead of launching a new background task.

**Rationale:**
- Each pipeline run costs $10–60 in LLM+embedding costs
- User 2 joining an already-analyzed company can accidentally trigger a duplicate run
- Returning 200 (not 409) is semantically correct — it is not a conflict, the resource already exists
- Guard fires **before** `task_store.create_task()` so no slug conflict is created
- Frontend using `already_exists=true` can skip polling and go straight to displaying existing data

**Implementation Details:**
- **Gap analysis:** Dual-sentinel artifact detection (`gap_analysis_complete.json` OR `analysis.json`) — mirrors `gap_data_service.py` sentinel logic to ensure consistency
- **Research:** Stage-aware guard — only fires if **all requested stages** have approved artifacts. `.draft.md` personas are excluded (draft ≠ approved)
- **`run_id` fallback:** When no completed task record found, returns `f"existing-{effective_slug}"` (stable, non-empty, clearly pre-existing) — not pollable for status, returns 404 which is acceptable
- **`datetime.now(timezone.utc)`** used throughout (not deprecated `datetime.utcnow()`)
- **`responses={200: {...}}`** added to both route decorators for correct OpenAPI documentation

**Alternatives Rejected:**
- Returning 409 Conflict — semantically wrong. Duplicate run prevention is a success case, not an error.
- Always-launch-and-deduplicate — would still create task and lock, causing 409 if concurrent requests race.
- Cache-aside at service layer (not router) — guard needs `artifacts_root` + `task_store` access; router is the right boundary.

**Tradeoff:** Clients must pass `force_rerun=true` to refresh data for an existing company. Frontends should surface this as a "Re-run analysis" button rather than a default.

**Outcome:** 12 tests added. 900 total tests passing.

**Approved by:** Aryan

### Decision 14: SQLAlchemy 2.0 + Alembic Database Layer (D-DB-1)

**Choice:** Pure SQLAlchemy 2.0 Declarative with native PgUUID PKs, hand-written Alembic migrations, flush-only repository pattern, and lazy engine initialization.

**Rationale:**
- SQLAlchemy 2.0 wins 6-0 scorecard vs SQLModel across pgvector `Vector(1536)`, 12+ Postgres enums, JSONB `server_default`, `ARRAY(Text)`, self-referential FK, and Alembic autogenerate
- We maintain 3 separate model layers (core Pydantic, API schemas, ORM) — SQLModel's dual class provides zero benefit
- Hand-written first migration avoids known autogenerate footguns with pgvector/enums/partial indexes
- Flush-only repos enable savepoint test isolation AND multi-repo atomic transactions within single requests
- Lazy engine init prevents import-time DB connections (existing pipeline scripts without `DATABASE_URL` are unaffected)
- Native `PgUUID(as_uuid=True)` is 16 bytes vs 36 bytes for String(36), faster indexing on Postgres
- `database_url_sync` computed from `database_url` prevents sync/async URL drift (single source of truth)

**Alternatives Rejected:**
- SQLModel (escape hatches required for pgvector, enums, JSONB; dual class unnecessary in our architecture)
- String(36) PKs (storage/performance penalty, non-native Postgres type)
- Autogenerated first migration (known issues with pgvector extensions, enum creation order, partial indexes, opclass syntax)
- Combined HNSW+schema migration (index creation locks tables on large datasets)
- Repos owning commit() (breaks savepoint test isolation, prevents multi-repo atomicity)

**Codex Review:** gpt-5.3-codex with extra-high reasoning. 10 CRITICAL, 8 WARNING, 6 ARCHITECTURAL, 10 MISSING, 8 IMPROVEMENT findings. All CRITICALs and relevant WARNINGs incorporated. Plan at `.claude/plans/fluffy-herding-oasis.md`.

**Outcome:** 44 new files, 31 ORM tables, 44 DB tests (auto-skip without `TEST_DATABASE_URL`). Zero changes to existing code. 1028 existing tests pass unchanged.

**Approved by:** Aryan

---

## 18. Known Vulnerabilities, Flaws & Technical Debt

### Critical Issues

#### 1. PARTIAL TEST COVERAGE (Significantly Improved)
**Severity:** Low (downgraded from Critical — 2026-02-15, improved through 2026-03-06)
**Description:** ~2568 total tests, 1 pre-existing failure (PB-39). **Site audit module: 793 tests.** **Knowledge Base: 260 tests.** **Audience Persona: 232 tests.** **Content engine: 437 tests** (v1.0 + v1.3). **CPS model: 44 tests** (7 skipped without torch). Research pipeline: 109 tests. API layer: 526+ tests. Gap analysis: comprehensive coverage. Database layer: 44 tests (auto-skip without `TEST_DATABASE_URL`). Reddit HIL still has zero tests.
**Impact:** All major pipelines (including site audit, knowledge base, audience persona, CPS model), all API endpoints, settings management, knowledge document upload, and database layer have regression protection. Only Reddit HIL remains unprotected.
**Recommendation:** Add tests for Reddit HIL (webhook delivery, PRAW mocking). Run DB tests with `TEST_DATABASE_URL` in CI to validate full PostgreSQL integration.

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

#### 7. ~~No Structured Logging~~ ✅ RESOLVED (Sprint v17)
**Severity:** ~~Medium~~ → **Resolved**
**Description:** Structured logging foundation implemented via `structlog`. Central config in `core/shared_tools/structured_logging.py`. JSON output in prod, colored console in dev. Context propagation via `structlog.contextvars` (correlation_id, user_id, company_slug, task_id, pipeline_name). All 115 existing `logging.getLogger(__name__)` call sites work unchanged via structlog's `ProcessorFormatter` stdlib bridge.
**Files:** `core/shared_tools/structured_logging.py` (new), `core/config/settings.py` (3 new fields: `log_level`, `log_format`, `log_include_caller`), `api/app.py` (middleware rewrite), `api/tasks/runner.py` (14 functions), 5 scripts, 2 print() eliminations.
**Tests:** 22 new tests (17 structured logging + 5 middleware).

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

#### 10. Old Research Pipeline Removed (2026-03-08)
**Severity:** ~~Medium~~ Resolved
**Description:** The old DeepAgents-based research pipeline (company research, persona research, style guide research) has been fully removed. All code in `core/research/agents/`, `core/research/graphs/`, `core/models/artifacts.py`, `core/models/style_guide.py`, `api/routers/research.py`, and associated scripts/tests deleted. The `deepagents` dependency removed from `pyproject.toml` and `requirements.txt`. Replaced by three new pipelines: Knowledge Base (§5c), Audience Persona (§5d), and Voice Style Guide (§5e).

#### 11. Langfuse Removed — Replaced by LangSmith (2026-03-02)
**Severity:** ~~High~~ Resolved
**Description:** Originally written for Langfuse v2 API, then migrated to Langfuse v3 (2026-02-16). Langfuse was **fully removed** on 2026-03-02 and replaced by LangSmith as the sole tracing backend. The unified module `core/shared_tools/tracing.py` uses `RunTree` from `langsmith.run_trees` and is shared across all pipelines. Old `core/content_engine/tracing_v13.py` is a re-export shim for backward compatibility. See §7.3 for full architecture.
**Location:** `core/shared_tools/tracing.py` (unified), `core/content_engine/tracing_v13.py` (shim)

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

#### 16. (RESOLVED) ChromaDB Migrated to pgvector
**Description:** ChromaDB has been replaced by pgvector (PostgreSQL extension). Vector storage now uses tables `persona_embeddings`, `cps_training_snippets`, and `cps_training_queries` with HNSW indexes. `DATABASE_URL` is required.

#### 17. Hardcoded Default Paths in Utility Scripts
**Description:** `resolve_vertexai_redirects.py` defaults input to Ramp's enriched citations path. `strip_embeddings_from_json.py` defaults to Ramp's embeddings path.
**Impact:** Confusing defaults if used with other companies.
**Recommendation:** Remove defaults or make them configurable via settings.

### Front-Back Integration Sprint — Deferred Issues (2026-02-25/26)

> **Full list:** `.claude/sprints/v1/review-findings-deferred.md`

#### 18. `update_company()` Allows Overwriting Protected Fields (C5)
**Severity:** Critical (deferred)
**Location:** `api/auth/store.py:183`
**Description:** No allowlist on `setattr` — caller can overwrite `id`, `created_at`, `slug` via `**kwargs`.
**Fix:** Add allowlist of mutable fields (`name`, `domain`, `additional_domains`, `products`).

#### 19. Module-Level Cache Thread Safety (C6)
**Severity:** Critical (deferred)
**Location:** `api/services/gap_data_service.py`, `api/services/content_data_service.py`, `api/services/brand_data_service.py`
**Description:** FastAPI runs sync endpoints in a thread pool. The compound operation (check length, delete oldest, insert) on `_CACHE` dict is not atomic under concurrent load.
**Fix:** Add `threading.Lock` around cache mutations, or switch to `cachetools.TTLCache`.

#### 20. `_PATTERN_FLAGS` has_comparison_table Mismatch (C7)
**Severity:** Medium (deferred)
**Location:** `api/services/gap_data_service.py:190`
**Description:** `_PATTERN_FLAGS` includes `has_comparison_table` which doesn't exist on `GapContentBrief` — real field is `has_tables`. Test fixtures mask this.
**Fix:** Replace `("has_comparison_table", "Tables")` with `("has_tables", "Tables")`.

#### 21. Symlink Path Traversal Bypass (CX-1)
**Severity:** Critical (deferred)
**Location:** `api/services/content_data_service.py:408-411`
**Description:** Content stage reader uses `str.startswith()` for path validation, which is bypassable via symlinks. Needs `Path.is_relative_to()`.

#### 22. Sort by String Field Crash (CX-3)
**Severity:** Medium (deferred)
**Location:** `api/services/gap_data_service.py:761`
**Description:** `sort_by=query_text` with missing values → `getattr(...) or 0` mixes str/int types → `TypeError`.

#### 23. Null `overall_score` Crash (CX-4)
**Severity:** Medium (deferred)
**Location:** `api/services/content_data_service.py:205-206`
**Description:** `{'cycles': [{'overall_score': None}]}` → `None * 100` → `TypeError`.

#### 24. NaN in Enriched Citations (CX-6)
**Severity:** Medium (deferred)
**Location:** `api/services/gap_data_service.py:278-287`
**Description:** `structural_signals: {"word_count": NaN}` propagates through averages → `json.dumps(NaN)` → `ValueError` (500).

#### 25. No Rate Limiting on /register (W8)
**Severity:** Medium (deferred)
**Location:** `api/routers/auth.py`
**Description:** No rate limiter on registration endpoint. Vulnerable to abuse before real usage.

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
| **Site Audit (Pipeline 0)** | ✅ Implemented | **High — 6-step deterministic audit, 8 dimensions, penalty-based scoring, 793 tests** |
| Company Research Agent | ✅ Production | High — used for Ramp, Carta, Mynd |
| Persona Research Agent | ✅ Production | High — ICP personas approved for Ramp, Carta |
| Style Guide Research Agent | ✅ Functional | Medium — bugs fixed, awaiting approvals |
| Research Pipeline Orchestrator | ✅ Functional | High — cross-stage wiring works, 109 tests |
| Gap Analysis (8 steps) | ✅ Production | High — complete for Ramp, Carta |
| Content Generation Engine v1.3 | ✅ Implemented | **High — 6-stage pipeline, LiteLLM, E-E-A-T eval, 3 HITL, LangSmith tracing, 437 tests** |
| **FastAPI REST API (core)** | ✅ Implemented | **High — 126 tests, SSE, HITL, all 4 pipelines** |
| **API Data Endpoints (front-back)** | ✅ Implemented | **High — 16 endpoints, 179 tests, 4-phase sprint complete** |
| **Product-Level Pipeline Execution** | ✅ Implemented | **High — product CRUD, effective_slug locking, per-product artifact dirs, product prompts, 114 tests** |
| **Auth System (v0)** | ✅ Implemented | **High — default-deny ASGI middleware, RBAC, tenant isolation, invite flow, 952 tests** |
| **Settings Pages API** | ✅ Implemented | **High — team management, company profile, pipeline defaults, 39 tests** |
| **Knowledge Doc Upload** | ✅ Implemented | **High — multipart upload, text extraction, s1 integration, embedded status, 37 tests** |
| Reddit HIL Monitor | ✅ Functional | Medium — tested with Ramp |
| Supabase Schema | ✅ Production | High — 4 migrations, RLS, HNSW |
| Supabase Mirror | ✅ Functional | Medium — works but no SQLAlchemy ORM |
| CLI Scripts | ✅ Functional | Medium — works but no error handling |
| LangSmith Tracing (sole backend) | ✅ Implemented | **High — all pipelines traced, prompt registry, shared module (Langfuse removed)** |
| **Knowledge Base (Pipeline 1b)** | ✅ Implemented | **High — 6-agent DAG, 3 HITL checkpoints, staleness tracking, delta synthesis, 260 tests** |

### Completed Sprints

| Sprint | Branch | Completed | Tests Added | Key Deliverables |
|--------|--------|-----------|-------------|------------------|
| `v3-async` | `feat/async-pipeline` | 2026-02-15 | 58 | Async pipeline, Playwright CF bypass, BFS fix |
| `content-engine-v1` | `feat/content-engine` | 2026-02-15 | 57 | 4-stage content generation pipeline |
| `v3-signals` | `feat/structural-signals` | 2026-02-18 | 75 | 45 structural signals, dual-soup, 3-tier output |
| `api-v1` | `feat/api` | 2026-02-19 | 126 | FastAPI, SSE, HITL, TaskStore, EventBus |
| **`front-back-integration`** | **`feat/front-back`** | **2026-02-26** | **343** | **16 data endpoints, auth, company model, service layer, 4 phases** |
| **`product-level-pipeline`** | **`feat/front-back`** | **2026-02-26** | **114** | **Product CRUD, effective_slug locking, pipeline wiring, product prompts, ?product_slug= on all 11 data endpoints** |
| `review-action-items` | `feat/front-back` | 2026-02-26 | 6 | 9 security/correctness fixes from Codex review → 888 total |
| `pipeline-guard` | `feat/front-back` | 2026-02-27 | 12 | force_rerun guard on /gap-analysis/start + /research/start → 900 total |
| `route-protection` | `feat/front-back` | 2026-02-27 | 44 | Default-deny ASGI middleware, RBAC, tenant isolation, invite flow, stream tokens → 944 total |
| `security-fixes` | `feat/front-back` | 2026-02-27 | 8 | 5 CRITICAL review fixes (artifact IDOR, SSE auth, login is_active, invite race) → 952 total |
| **`settings-knowledge-docs`** | **`feat/front-back`** | **2026-02-27** | **77** | **Settings Pages API (team/profile/pipeline-defaults) + Knowledge Doc Upload (CRUD + s1 integration + embedded status) + 6 review fixes → 1029 total** |
| `sqlalchemy-migration` | `feat/front-back` | 2026-02-27 | 44 | SQLAlchemy 2.0 Phase 1 — 31 ORM tables, Alembic, 8 domain repos, DI → 1073 total |
| `auth-migration-phase2` | `feat/front-back` | 2026-02-28 | 96 | AuthServiceProtocol, Json/Db dual impl, middleware decoupling → 1168 total |
| `service-layer-phase3` | `feat/front-back` | 2026-02-28 | 46 | 3 data service protocols, dual implementations, backfill → 1213 total |
| `cleanup-taskstore-migration` | `feat/front-back` | 2026-02-28 | 129 | TaskStoreProtocol, DbTaskStore, Phase 4 persistence hooks → 1342 total |
| **`site-audit`** | **`feat/front-back`** | **2026-02-28** | **636** | **Pipeline 0: 6-step deterministic audit, 8 dimensions, async BFS crawler, AEO readiness, penalty-based scoring, API layer → ~1978 total** |
| **`content-engine-v13`** | **`feat/content-engine-v13`** | **2026-03-02** | **~437** | **v1.3 pipeline (6 stages, LiteLLM, E-E-A-T, 3 HITL, linker agent), LangSmith migration (Langfuse removed)** |
| **`site-audit-p3-bugfixes`** | **`fix/site-audit-p3`** | **2026-03-04** | **82** | **P3 bug fixes: config validation, dateutil parsing, canonical URL, crawl-delay, schema validators, AEO improvements → 793 site audit tests** |
| **`knowledge-base-v1-v5`** | **`research-agent-v1.2.0`** | **2026-03-06** | **260** | **KB Phases 1-5: 17 models, KBStorage, 6 agents, DAG orchestrator, 3 HITL, API router, staleness tracking, delta synthesis → ~2479 total** |

### What's Planned (Future Scope)

| Priority | Component | Description | Dependencies |
|----------|-----------|-------------|--------------|
| 1 | **Frontend-Backend Integration** | Wire frontend to live endpoints, remove ~2100 lines of fixture data | ✅ Backend complete (front-back sprint) |
| 2 | **Content Engine v1.1** | HITL timeout, --offline flag, cost budget cap | Content Engine v1.0 |
| 3 | **Production Hardening** | Fix deferred issues (C5-C7, CX-1 through CX-10), thread-safe caches, rate limiting | front-back sprint |
| 4 | **~~Product-Level Pipeline Execution~~** | ~~Model supports it (Company → Products), execution deferred~~ — **DONE in product-level-pipeline sprint** | ✅ Complete |
| 5 | **Supabase Migration** | Replace JSON AuthStore with Supabase, migrate task persistence | Auth system, Supabase schema |
| 6 | **~~SQLAlchemy ORM~~** | ~~Replace raw Supabase client with ORM~~ — **DONE in sqlalchemy-migration + service-layer-phase3 sprints** | ✅ Complete |
| 6 | **Reddit HIL Tests** | Only untested module (PRAW mocking, webhook delivery) | Existing codebase |
| 7 | **DB Integration for New Research Pipelines** | Add PostgreSQL persistence for KB/AP/VSG | SQLAlchemy + Alembic |
| 8 | **Cloud Storage Backends** | S3/GCS/Supabase Storage implementations | StorageBackend interface |
| 9 | ~~**Structured Logging**~~ | ✅ **DONE** — structlog foundation, JSON/console modes, correlation IDs, context propagation | `core/shared_tools/structured_logging.py` |
| 10 | **CI/CD Pipeline** | Automated tests, linting, deployment | Tests + Docker |
| 11 | **Redis/PG TaskStore** | Replace JSON-file TaskStore for multi-server | FastAPI backend |

---

## 21. REST API Layer (FastAPI)

**Status:** Implemented (2026-02-16), expanded with data endpoints (2026-02-25/26), expanded with product-level support (2026-02-26), pipeline guard added (2026-02-27), production-grade route protection added (2026-02-27), **Settings Pages API + Knowledge Doc Upload added (2026-02-27)**. 1029 tests passing, 1 pre-existing failure (PB-39). All 3 pipelines wrapped + 16 company-scoped data retrieval endpoints + product CRUD endpoints + `?product_slug=` on all 11 data endpoints. `force_rerun` guard on `/gap-analysis/start`. Default-deny ASGI middleware with RBAC, tenant isolation, invite flow, and stream tokens. **14 routers total** including settings (6 endpoints) and knowledge-docs (5 endpoints). Per-company pipeline defaults wired into the gap analysis runner.

**Architecture Decision:** D-API-1 — `asyncio.create_task()` (not Celery), JSON-file TaskStore, SSE for progress, `MemorySaver` checkpointer for HITL. See §17 Decision 12 for full rationale. Data endpoints added in D-FB-1 through D-FB-5.

### 21.1 Application Factory & Lifecycle

**File:** `api/app.py`

```python
def create_app() -> FastAPI:
```

**Startup (lifespan context manager):**
1. **Initialize structured logging** — `configure_logging()` from `core.shared_tools.structured_logging` (structlog + stdlib bridge, JSON or console mode based on `LOG_FORMAT` env var)
2. Initialize `EventBus` (in-memory pub/sub for SSE)
3. Initialize `TaskStore` (JSON-file-backed persistence + semaphore)
4. Scan disk for orphan tasks — marks stale "running" tasks as `FAILED_RESTART`
5. Store shared state in `app.state` (accessed via dependency injection)

**Middleware (applied in order — FastAPI adds in reverse, so last-added = outermost):**
1. `CORSMiddleware` — outermost. Handles OPTIONS preflight before auth. Configurable origins (default: `localhost:3000`, `localhost:3001`), credentials enabled.
2. `AuthMiddleware` — **pure ASGI middleware** (not BaseHTTPMiddleware — safe for SSE streaming, Codex W1). **Default-deny** posture: blocks unauthenticated requests to protected routes with 401 JSON. Reads `Authorization: Bearer {token}` header (or `?stream_token=` query param for SSE). If valid, injects `scope["state"]["user_id"]` and `scope["state"]["company_slug"]`. Public path whitelist: `/health`, `/readiness`, `/docs`, `/redoc`, `/openapi.json`, `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/join`.
3. `RequestLoggingMiddleware` — Structured request logging via `structlog.contextvars`. Generates/extracts `X-Correlation-ID` header, binds context (correlation_id, method, path, user_id, company_slug), logs `"request_completed"` with `status_code` and `duration_ms` as structured fields. Returns early for `/events` paths (SSE safe). Clears context after each request.

**Exception Handlers:**
| Exception | HTTP Status | Error Code |
|-----------|-------------|------------|
| `TaskNotFoundError` | 404 | `task_not_found` |
| `TaskConflictError` | 409 | `task_conflict` |
| `PipelineError` | 500 | `pipeline_error` |

**Routers (mounted in order):** health, auth, companies, gap_analysis, gap_data, events, artifacts, content, content_v13, cps, content_data, brand_data, settings, knowledge_base, knowledge_docs, audience_persona, voice_style_guide, site_audit, daily_tracker, tasks

---

### 21.2 API Endpoints Reference

#### Health & Readiness
```
GET  /health                                    → {"status": "ok"}
GET  /readiness                                 → {"ready": bool, "missing_keys": [...]}
```

#### Gap Analysis Pipeline
```
POST /api/v1/gap-analysis/start                 → 202 Accepted (new run) | 200 OK (already_exists)
GET  /api/v1/gap-analysis/{run_id}/status       → TaskResponse
```

**Request Body (`/gap-analysis/start`):**
```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "product_slug": "corp-card",
  "seed_urls": ["https://ramp.com"],
  "skip_steps": [1, 2],
  "force_rerun": false
}
```
- `company_name` (required): Company display name
- `domain` (required): Company domain
- `product_slug` (optional): Product slug for product-scoped run; validated via regex (lowercase, no path chars, no leading hyphen)
- `seed_urls` (optional): Additional URLs to crawl
- `skip_steps` (optional): Step numbers to skip (1–8)
- `force_rerun` (optional, default `false`): When `false`, if artifacts already exist for this `effective_slug` the endpoint returns HTTP 200 with `already_exists=true` (no new task created). Pass `true` to force a fresh run.

**Already-Exists Response (HTTP 200):**
```json
{
  "run_id": "task-abc123",
  "pipeline": "gap_analysis",
  "company_slug": "ramp",
  "product_slug": "corp-card",
  "effective_slug": "ramp__corp-card",
  "status": "already_exists",
  "already_exists": true,
  "message": "Artifacts already exist. Pass force_rerun=true to re-run.",
  "created_at": "2026-02-26T10:00:00Z"
}
```
- `run_id` is the last completed task's ID (for reference), or `"existing-{effective_slug}"` if no task record exists.
- **Artifact detection (dual-sentinel):** checks `artifacts/gap_analysis/{effective_slug}/gap_analysis_complete.json` OR `analysis.json`. Mirrors the same logic used by `gap_data_service.py`.

#### Research Pipeline
```
POST /api/v1/research/start                     → 202 Accepted (new run) | 200 OK (already_exists)
GET  /api/v1/research/{run_id}/status           → TaskResponse
POST /api/v1/research/{run_id}/approve          → ApprovalResponse
```

**Request Body (`/research/start`):**
```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "product_slug": "corp-card",
  "stages": ["company", "persona", "style_guide"],
  "auto_approve": false,
  "max_personas": 3,
  "force_rerun": false
}
```
- `company_name` (required), `domain` (required)
- `product_slug` (optional): Product-scoped run
- `stages` (optional, default all three): Subset of `["company", "persona", "style_guide"]` to run. **The guard only fires if ALL requested stages have approved artifacts.**
- `auto_approve` (optional, default `false`): Skip HITL review
- `max_personas` (optional, default 3): Max persona files to generate
- `force_rerun` (optional, default `false`): When `false`, if all requested stages already have approved artifacts the endpoint returns HTTP 200 with `already_exists=true`. Pass `true` to force a fresh run.

**Guard logic (stage-aware):**
- `company` stage: checks `artifacts/company_context/{slug}.md`
- `persona` stage: checks `artifacts/personas/{slug}__persona-*.md` (excludes `.draft.md` files — drafts are NOT considered approved)
- `style_guide` stage: checks `artifacts/style_guides/{slug}.md`
- Dual-scope: checks `{effective_slug}` first, falls back to bare `{company_slug}` (product runs reuse company-level artifacts if not overridden)

**Already-Exists Response (HTTP 200):** Same shape as gap analysis already-exists response above, with:
```json
{
  "status": "already_exists",
  "already_exists": true,
  "message": "Stages ['company', 'persona', 'style_guide'] already have approved artifacts. Pass force_rerun=true to re-run."
}
```

**Approval Request (`/research/{run_id}/approve`):**
```json
{ "decision": "approve|revise|reject", "revision_note": "optional feedback" }
```

#### Content Generation Pipeline (v1.0)
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

#### Content Generation Pipeline v1.3 (added 2026-03-02)
```
POST /api/v1/content/v13/start                          → 202 Accepted: PipelineRunResponseV13
GET  /api/v1/content/v13/{run_id}/status                → TaskResponse (dict)
POST /api/v1/content/v13/{run_id}/approve/topics        → ApprovalResponseV13
POST /api/v1/content/v13/{run_id}/approve/briefs        → ApprovalResponseV13
POST /api/v1/content/v13/{run_id}/approve/content       → ApprovalResponseV13
```

**Content v1.3 Start Request:**
```json
{
  "company_name": "Ramp", "domain": "ramp.com",
  "entry_mode": "autonomous",
  "max_topics": 5, "auto_approve": false,
  "skip_stages": [], "max_revision_cycles": 2,
  "manual_prompt": null, "manual_description": null
}
```
- `entry_mode` (optional, default "autonomous"): `"autonomous"` | `"manual"`
- `max_topics` (optional, default 5): Maximum topics for Strategic Planner
- `auto_approve` (optional, default false): Skip all 3 HITL checkpoints
- `skip_stages` (optional): List of stage numbers to skip
- `manual_prompt` (required for manual mode): User's topic prompt

**Three HITL Approval Endpoints:**
- Topic Approval: `{ "decision": "approve|modify|reject|retry", "approved_topic_ranks": [0,1,2], "feedback": "..." }`
- Brief Approval: `{ "brief_id": "brief-001", "decision": "approve|feedback|reject", "feedback": "..." }`
- Content Review: `{ "brief_id": "brief-001", "decision": "approve|edit|reject", "editor_notes": "...", "rethink": false }`

**Approval flow:** Router stores full approval dict on `task.approval_payload` via `update_task()`, then calls `submit_approval(decision=string)` to unblock the pipeline. `run_hitl_checkpoint()` reads `task.approval_payload` for `Command(resume=...)` graph resumption.

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

#### Daily LLM Visibility Tracker (`api/routers/daily_tracker.py`)
```
POST /api/v1/daily-tracker/prompts                      → TrackedPrompt (201)
GET  /api/v1/daily-tracker/prompts                      → PromptListResponse
GET  /api/v1/daily-tracker/prompts/{prompt_id}          → TrackedPrompt
PUT  /api/v1/daily-tracker/prompts/{prompt_id}          → TrackedPrompt
DELETE /api/v1/daily-tracker/prompts/{prompt_id}        → 204
PATCH /api/v1/daily-tracker/prompts/{prompt_id}/toggle  → TrackedPrompt
POST /api/v1/daily-tracker/prompts/import               → list[TrackedPrompt] (201)
POST /api/v1/daily-tracker/prompts/bulk                 → list[TrackedPrompt] (201)
POST /api/v1/daily-tracker/runs                         → RunStatusResponse (202)
GET  /api/v1/daily-tracker/runs/{run_id}                → RunStatusResponse
GET  /api/v1/daily-tracker/runs                         → RunListResponse
GET  /api/v1/daily-tracker/analytics/visibility         → VisibilityMetrics
GET  /api/v1/daily-tracker/analytics/mention-trend      → list[TrendDataPoint]
GET  /api/v1/daily-tracker/analytics/sov                → dict[str, float]
GET  /api/v1/daily-tracker/analytics/citations          → dict[str, object]
GET  /api/v1/daily-tracker/analytics/competitors        → list[CompetitorMetrics]
```

**Auth:** All endpoints require authentication. Write operations (POST/PUT/DELETE/PATCH) require `member` or `superuser` role. Read operations (GET) require any authenticated user.

**Tenant isolation:** `_get_company_id(request)` extracts `company_slug` from `request.state` (set by auth middleware). All queries are scoped to the authenticated company.

**DI:** Services injected via `get_prompt_library_service`, `get_analytics_service`, `get_daily_tracker_orchestrator` (defined in `api/dependencies.py`). Tests inject mocks via `app.state.*` overrides.

#### Artifact Retrieval
```
GET  /api/v1/artifacts/companies                → {"companies": ["ramp", "carta"]}
GET  /api/v1/artifacts/{type}/{slug}            → {"artifact_type", "slug", "files": [...]}
GET  /api/v1/artifacts/{type}/{slug}/{filename} → File content (JSON/HTML/MD)
```
**Artifact types:** `company_context`, `personas`, `style_guides`, `gap_analysis`, `content`

**Slug validation:** Slugs must match `^[a-z0-9][a-z0-9-]*$` (lowercase alphanumeric + hyphens, starting with alphanumeric). Invalid slugs return 400. Additionally, resolved paths are checked for containment within the artifacts root to prevent path traversal.

#### Authentication (`api/routers/auth.py`, `api/auth/`)

```
POST /api/v1/auth/register                     → LoginResponse (201) — public
POST /api/v1/auth/login                        → LoginResponse — public
GET  /api/v1/auth/me                           → MeResponse (requires Bearer token)
POST /api/v1/auth/invite                       → InviteResponse (201) — requires superuser role
POST /api/v1/auth/join                         → LoginResponse (201) — public (requires valid invite code)
```

**Registration (`/register`):**
```json
{
  "email": "aryan@ramp.com",
  "password": "securepass123",
  "first_name": "Aryan",
  "last_name": "Keshri",
  "company_name": "Ramp",
  "company_domain": "ramp.com"
}
```
- `email`: Validated via `EmailStr` (requires `email-validator` package)
- `password`: `min_length=8, max_length=128` enforced at API model level
- **Domain normalization:** `normalize_domain()` strips protocol/www/path/port, handles multi-part TLDs (frozenset of 15: `.co.uk`, `.com.au`, `.co.jp`, etc.), returns `(root_domain, subdomain_or_none)`.
- **Isolated company creation (Codex C1):** Registration ALWAYS creates a new company — the first user becomes `superuser`. Domain auto-join was removed to prevent cross-tenant account takeover. If the domain already has a company, returns **409** with message: "A company with this domain already exists. Ask your admin for an invite code."
- **Subdomain normalization:** `app.ramp.com` normalizes to `ramp.com` — triggers domain-taken 409 if `ramp.com` company exists.

**Login (`/login`):**
```json
{ "email": "aryan@ramp.com", "password": "securepass123" }
```
Returns `{ "access_token": "...", "user": {...}, "company": {...} }`. Token is HMAC-SHA256 signed, base64-encoded, containing `user_id + company_slug + expires_at`.
- **Timing oracle prevention (Codex W7):** When user not found, a constant-time dummy hash verification (`AuthStore._DUMMY_HASH`) runs before returning 401, preventing timing-based user enumeration.

**Me (`/me`):** Requires `Authorization: Bearer {token}` header. Returns current user profile + company info. Handles `company_id` fallback lookup since `UserProfile` doesn't store `company_slug` directly.

**Invite (`/invite`):** Requires `superuser` role. Creates a single-use invite code (16-char hex) for the user's company. Accepts `role` parameter (`member` or `viewer`, default `member`).

**Join (`/join`):** Public endpoint. Accepts an invite code + user details. Creates the user in the invite's company with the specified role. Invite code is consumed after use — cannot be redeemed twice.

**Auth Dependencies (`api/auth/dependencies.py`):**
- `require_auth(request, auth_store) → UserProfile`: Looks up user by `request.state.user_id`, checks `is_active`, returns 401 if any check fails
- `require_role(*roles) → Callable`: Factory returning dependency that calls `require_auth`, then checks `user.role ∈ roles`, returns 403 if not
- `require_tenant(slug, request) → UserProfile`: Lightweight slug comparison — URL `{slug}` must match token's `company_slug`, returns 403 if mismatch
- `require_company_access(slug, request, auth_store) → UserProfile`: Store-based tenant check — looks up company, verifies `user.company_id == company.id`
- `require_company_member(slug, request, auth_store) → UserProfile`: Combined role check (member/superuser) + store-based tenant check for write endpoints

**AuthStore (`api/auth/store.py`):**
- JSON-file backed: `artifacts/_auth/companies.json`, `artifacts/_auth/users.json`
- Password hashing: PBKDF2-HMAC-SHA256, 260000 iterations
- Token signing: HMAC-SHA256 with `JWT_SECRET_KEY` env var
- **JWT_SECRET_KEY enforcement (Codex W8):** `RuntimeError` on startup if env var not set in non-dev/test environments. Auto-generated random key in dev/test only.
- Thread-safe: `threading.RLock` on all mutating methods + atomic file writes via temp + `os.replace()`
- Stream tokens: `create_stream_token(user_id, company_slug)` generates 5-minute tokens with `stream_only: true` flag
- Invite management: `create_invite(company_slug, role)` / `redeem_invite(code, ...)` — single-use codes stored in memory

#### Company Profile (Phase 1 — `api/routers/companies.py`)

```
GET  /api/v1/companies/{slug}                  → CompanyProfileResponse
```

Returns company profile with:
- Products list (with `has_research`, `has_gap_analysis`, `has_content` flags)
- Research artifact summary (which artifacts exist, draft/approved status)
- Latest pipeline runs (most recent run per pipeline type)
- Artifact presence scanning: checks `artifacts/{type}/{slug}*` filesystem paths

**Response model (`api/schemas/company.py`):**
```python
class CompanyProfileResponse(BaseModel):
    slug: str
    name: str
    domain: str
    products: List[ProductSummary] = []
    has_research: bool = False
    has_gap_analysis: bool = False
    has_content: bool = False
    research_summary: ResearchArtifactSummary = ...
    latest_runs: Dict[str, Optional[LatestRunSummary]] = {}
```

#### Gap Analysis Data (Phase 2 — `api/routers/gap_data.py`, `api/services/gap_data_service.py`)

All endpoints read from `artifacts/gap_analysis/{slug}/` JSON files. Service layer uses mtime-based caching (max 10 entries, FIFO eviction).

**Backward compatibility:** Supports both `gap_analysis_complete.json` (new combined format) and `analysis.json` + `gap_report.json` (old Ramp format with 11 structural signals). Detection: try `gap_analysis_complete.json` first, fallback to separate files.

```
GET  /api/v1/companies/{slug}/gap-analysis/summary     → GapSummaryResponse
GET  /api/v1/companies/{slug}/gap-analysis/queries      → QueryListResponse
GET  /api/v1/companies/{slug}/gap-analysis/clusters     → ClusterListResponse
GET  /api/v1/companies/{slug}/gap-analysis/signals      → SignalAveragesResponse
GET  /api/v1/companies/{slug}/gap-analysis/platforms     → PlatformListResponse
GET  /api/v1/companies/{slug}/gap-analysis/heatmap      → HeatmapResponse
GET  /api/v1/companies/{slug}/gap-analysis/embeddings   → EmbeddingProjectionResponse
GET  /api/v1/companies/{slug}/gap-analysis/trend        → SPATrendResponse
```

**`/summary` — Overview tab data:**
- SPA score (t_stat, p_value, effect, mean similarities)
- Proximity stats (citation vs company similarity means/medians)
- Classification counts (significant_gap, gap_to_close, roughly_equal, company_wins)
- Per-cluster performance rows (avg_gap, avg_citation_sim, structural rates)
- Executive summary text + recommendations list

**`/queries` — Query Intelligence tab (paginated):**
- Query params: `cluster`, `classification`, `search` (filters), `sort_by`, `sort_dir`, `page`, `page_size`
- Returns: query_id, query_text, cluster assignment, gap_score, classification, similarities, content brief, top exemplars, platform citations
- Content brief includes: target_word_count range, reading_level range, recommended_header_count, header_hierarchy, content_patterns, dominant_authority/content_type

**`/clusters` — Content Briefs tab:**
- Cluster specs with centroid distances (merged from analysis result centroids)
- Structural rates per cluster (from enriched citations)
- TF-IDF exemplar themes, dominant content/authority types
- Word count ranges, FAQ/table/key-takeaways adoption rates

**`/signals` — Structural Signals tab:**
- Signal averages: citation_avg vs company_avg for ~45 structural signals, grouped by category
- Signal correlations: Pearson correlation of each signal with citation similarity (sorted by absolute value)
- Cluster patterns: per-cluster content pattern adoption rates (FAQ, definition_opening, key_takeaways, comparison_table, step_by_step, research_refs, expert_quotes)
- Cluster fingerprints: structural rate dicts per cluster for radar charts

**`/platforms` — Platform Intelligence tab:**
- Per-platform: total_citations, unique_domains, avg_citation_sim, most_cited_domain, best/worst cluster, per_cluster breakdown
- Platform engine name mapping: `openai→chatgpt`, `claude→claude`, `gemini→gemini`, `perplexity→perplexity` (frontend uses lowercase keys)
- Agreement matrix: pairwise Jaccard similarity of domain sets between platforms
- Citation exclusivity: unique/shared/total domain counts per platform pair

**`/heatmap` — Heatmap tab:**
- Cluster groups each containing their queries with gap scores and classifications
- Global min_gap and max_gap for color scale normalization

**`/embeddings` — Embedding Lab scatter plot:**
- Query param: `method` (`umap` or `tsne`)
- Returns 2D projections from `embedding_projections_{method}.json` (computed in s7_visualize.py)
- Each point: x, y, type (query/citation/company), id, label, cluster, cluster_id, similarity, gap_score

**`/trend` — SPA Score Trend (Phase 4 addition to gap_data router):**
- Data source: `TaskStore.list_tasks(pipeline="gap_analysis", status="completed", company_slug=slug)`
- Returns `SPATrendPoint` array sorted ascending by timestamp (oldest first for chart x-axis)
- Each point: run_id, run label (e.g., "Feb 18"), timestamp (ISO8601), spa_score (from t_stat), citation_advantage, company_advantage, total_queries, total_citations
- NaN guard: `_safe_float()` converts NaN/Inf/None to 0.0

**Service layer (`api/services/gap_data_service.py`) — key functions:**
- `_load_gap_data()` — mtime-cached JSON loading with old/new format fallback
- `_load_enriched_citations()` — mtime-cached, typically 5-20MB per company
- `_pearson()` — Pearson correlation with `product <= 0` guard for floating-point imprecision
- `_jaccard()` — set intersection / union for domain agreement
- `_signal_averages()` — ~45 signals across 4 categories (formatting, structural, authority, content)
- `_signal_correlations()` — Pearson of each signal against citation similarity
- `_cluster_patterns()` — content pattern adoption rates from enriched citations

**Response models (`api/schemas/gap_data.py`) — 20+ models:**
- `GapSummaryResponse`, `SPAScore`, `ProximityStats`, `GapClassificationCounts`, `ClusterPerformanceRow`
- `QueryRow`, `QueryContentBrief`, `QueryExemplar`, `QueryListResponse`
- `ClusterSpecResponse`, `ClusterListResponse`
- `SignalAverageRow`, `SignalCorrelationRow`, `ClusterPatternRow`, `SignalAveragesResponse`
- `PlatformSummaryResponse`, `PlatformListResponse`
- `HeatmapQuery`, `HeatmapCluster`, `HeatmapResponse`

#### Content Data (Phase 3 — `api/routers/content_data.py`, `api/services/content_data_service.py`)

All endpoints read from `artifacts/content/{slug}/` directory. Service layer uses mtime-based caching (same pattern as gap_data).

```
GET  /api/v1/companies/{slug}/content/briefs                    → ContentBriefListResponse
GET  /api/v1/companies/{slug}/content/briefs/{brief_id}         → ContentBriefDetailResponse
GET  /api/v1/companies/{slug}/content/briefs/{brief_id}/{stage} → StageContentResponse
```

**`/briefs` — Content Pipeline board/table view:**
- Lists all briefs for a company with computed status and citability scores
- **Status inference (2-phase):**
  1. **Authoritative:** Check `run_metadata.json` → `pieces` array (post-HITL status like `approved`, `rejected`, `edit`)
  2. **File-based fallback:** Scan brief directory for stage files, check `eval_history.json` (`final_passed=True` → `review`, `False` → `evaluating`), presence of `formatted.md` → `formatting`, `draft.md` → `drafting`, `outline.json` → `outlining`
  3. `approved` kept distinct from `published` (frontend has separate board columns)
- **content_format → content_type mapping:** `long_form_article→blog`, `comparison_guide→comparison`, `how_to_guide→how-to`, `listicle→listicle`, etc.
- **Citability score:** Derived from `eval_history.json` — last cycle's `overall_score × 100`

**`/briefs/{brief_id}` — Brief detail view:**
- Full brief metadata + eval_history (cycles with per-dimension scores) + exemplars + available_stages list
- `available_stages`: scans `brief-{N}/` directory for `outline.json`, `draft.md`, `enriched.md`, `formatted.md`, `eval_history.json`

**`/briefs/{brief_id}/{stage}` — Stage-specific content:**
- Stage must be in `available_stages` (returns 404 otherwise)
- JSON stages (`outline`, `eval_history`): parsed and returned as dict in `content` field
- Markdown stages (`draft`, `enriched`, `formatted`): returned as string in `content` field
- `content_type`: `application/json` for JSON stages, `text/markdown` for markdown stages

**Embedding projections (Phase 3 addition to gap_data router):**
- `GET /api/v1/companies/{slug}/gap-analysis/embeddings`
- Pipeline change: `s7_visualize.py` now exports `embedding_projections_umap.json` and `embedding_projections_tsne.json` alongside HTML plots
- Embeds are computed once and reused for both HTML plots and JSON exports (no drift)

**Response models (`api/schemas/content_data.py`) — 12 models:**
- `ContentBriefListItem`, `ContentBriefListResponse`
- `EvalDimension`, `EvalCycle`, `BriefExemplar`
- `ContentBriefDetailResponse`
- `StageContentResponse`
- `EmbeddingPoint`, `EmbeddingProjectionResponse` (shared with gap_data router)

#### Brand Brain + Run History (Phase 4 — `api/routers/brand_data.py`, `api/services/brand_data_service.py`)

```
GET  /api/v1/companies/{slug}/research/artifacts  → ResearchArtifactsResponse
GET  /api/v1/companies/{slug}/runs                → RunHistoryResponse
```

**`/research/artifacts` — Brand Brain research artifacts viewer:**
- Reads full markdown content of research artifacts from filesystem
- **3 artifact types:** company_context (`artifacts/company_context/{slug}.md`), personas (`artifacts/personas/{slug}__persona-*.md`), style_guide (`artifacts/style_guides/{slug}.md`)
- **Artifact detection priority:** `.md` (approved, status="approved") > `.draft.md` (draft, status="draft") > neither (status="none", content=null)
- **Persona scanning:** Only `{slug}__persona-*.md` files are accepted (Codex CX-4 hardening — rejects `{slug}__notes.md` etc.)
- **Persona metadata extraction from filename:** `{slug}__persona-icp.md` → `id="persona-icp"`, `name="Persona Icp"`, `type="icp"` (vs `type="secondary"` for non-ICP)
- **updated_at:** File mtime converted to ISO8601

**`/runs` — Run History across all pipelines:**
- Data source: `TaskStore.list_tasks(company_slug=slug)` — no filesystem reads needed, task result dict already contains all metrics
- Query params: `pipeline` (filter: gap_analysis, research, content), `status` (filter: running, completed, failed), `limit` (default 50, max 200)
- **Status mapping:** Backend has 6 statuses, frontend expects 3:
  - `running` → `running`, `pending_approval` → `running`
  - `completed` → `completed`
  - `failed` → `failed`, `cancelled` → `failed`, `failed_restart` → `failed`
- **Status filter operates on mapped values:** `?status=running` catches both `running` AND `pending_approval` tasks
- **Duration computation:** `updated_at - created_at` for terminal tasks → `"3h 46m"`, `"23m"`, `"<1m"`, or `""` for running tasks
- **Gap metrics extraction from `task.result.report_json`:**
  - `spa_score` ← `spa_results[0].t_stat`
  - `queries` ← `decision_metrics.total_queries`
  - `citations` ← `decision_metrics.total_citations`
- **Steps completed inference via `_infer_steps_completed()`:**
  - Gap: `_GAP_STEP_MAP` = `{s1_embed_assets: 1, ..., s8_generate_report: 8}`
  - Research: `_RESEARCH_STEP_MAP` = `{company: 1, persona: 2, style_guide: 3}`
  - Content: parses `"stage N"` string → int
  - Completed tasks → total_steps (8 for gap, 3 for research, 4 for content)
- Sorted by `created_at` descending (most recent first)

**Response models (`api/schemas/brand_data.py`) — 8 models:**
- `ArtifactContent` (content, status, updated_at)
- `PersonaArtifact` (id, name, type, content, status, updated_at)
- `ResearchArtifactsResponse` (company_context, personas, style_guide)
- `RunHistoryItem` (id, pipeline, company, status, started, duration, queries, citations, spa_score, steps_completed, total_steps)
- `RunHistoryResponse` (runs, total)
- `SPATrendPoint` (run_id, run, timestamp, spa_score, citation_advantage, company_advantage, total_queries, total_citations)
- `SPATrendResponse` (trend)

#### Service Layer Architecture (Phase 2-4 — `api/services/`)

All three service modules follow the same architectural pattern:

**Caching:**
```python
_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}  # (cache_key) → (mtime_ns, data)
_CACHE_MAX_ENTRIES = 10  # FIFO eviction when full
```
- Check file mtime before serving cached data
- Known thread-safety issue: non-atomic read-modify-write race under concurrent load (C6 deferred)

**Slug validation:** All services validate slug format via `_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")`. Invalid slugs raise `HTTPException(400)`.

**Path traversal protection:** `Path.is_relative_to(base)` — NOT `str.startswith()` (which is bypassable via symlinks).

**Error philosophy:** Return empty/default data for missing artifacts (200 with empty lists), not 500. Log warnings for corrupted files. This enables graceful degradation when pipeline is mid-run.

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

## 25. Settings Pages API & Knowledge Doc Upload Sprint — Exhaustive Implementation Detail

**Sprint:** `settings-knowledge-docs` (2026-02-27)
**Branch:** `feat/front-back`
**Tests added:** 77 new tests (+ 6 review fixes applied) → 1029 total (1 pre-existing failure)
**Problem:** Non-technical users need dashboard UI to manage company settings, team members, and pipeline defaults. Clients have internal context (positioning docs, messaging frameworks, competitive analyses) that the pipeline can't access because s1 only crawls public URLs.

### 25.1 Sprint Context & Problem Statement

Two features needed before YC demo readiness:

1. **Settings Pages API** — Backend endpoints for managing team members, company profile, and per-company pipeline defaults (currently all configured via `.env.local` or CLI)
2. **Knowledge Doc Upload** — Allow clients to upload internal documents (.md, .txt, .pdf, .docx) that get embedded alongside site content in the gap analysis pipeline

**Deferred:** API key configuration (Phase 1D) — pre-YC, we run pipelines on behalf of clients with our own keys.

### 25.2 Feature 1A — User Management

**New/modified files:** `api/auth/store.py` (add `update_user()`), `api/schemas/settings.py` (NEW), `api/routers/settings.py` (NEW), `tests/api/test_settings_team.py` (NEW — 16 tests)

**AuthStore changes:**
- `_USER_MUTABLE_FIELDS = frozenset({"role", "first_name", "last_name", "is_active"})` — allowlist pattern matching existing `_COMPANY_MUTABLE_FIELDS`
- `update_user(user_id, **kwargs) → UserProfile` — uses `_lock`, validates field names against allowlist, returns updated user
- Guards: cannot deactivate self, cannot demote last superuser

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/companies/{slug}/settings/team` | tenant | List team members |
| PUT | `/companies/{slug}/settings/team/{user_id}` | superuser+tenant | Update role/status |

**Response model (`TeamMemberResponse`):** user_id, email, first_name, last_name, role, is_active, created_at

### 25.3 Feature 1B — Company Profile Editing

**New/modified files:** `api/schemas/settings.py` (extended), `api/routers/settings.py` (extended), `tests/api/test_settings_profile.py` (NEW — 11 tests)

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/companies/{slug}/settings/profile` | tenant | Get company profile for editing |
| PUT | `/companies/{slug}/settings/profile` | superuser+tenant | Update name, domain, additional_domains |

Delegates to existing `auth_store.update_company()` with `_COMPANY_MUTABLE_FIELDS` allowlist.

### 25.4 Feature 1C — Pipeline Defaults

**New/modified files:** `core/models/organization.py` (NEW), `api/auth/store.py` (add `get/update_pipeline_defaults()`), `api/schemas/settings.py` (extended), `api/routers/settings.py` (extended), `api/tasks/runner.py` (merge defaults), `tests/api/test_settings_pipeline.py` (NEW — 12 tests)

**Model (`CompanyPipelineDefaults` in `core/models/organization.py`):**
```python
class CompanyPipelineDefaults(BaseModel):
    max_crawl_pages: Optional[int] = None
    max_crawl_depth: Optional[int] = None
    max_queries: Optional[int] = None
    platforms: Optional[List[str]] = None
    max_personas: Optional[int] = None
    auto_approve_research: bool = False
    max_briefs: Optional[int] = None
    max_revision_cycles: Optional[int] = None
    auto_approve_content: bool = False
```

**Storage:** `artifacts/_auth/settings/{company_slug}.json` — same file-backed pattern as auth store.

**Runner integration (W3 fix):** When constructing `GapAnalysisInput`, company defaults fill in `None` fields:
```python
_defaults = auth_store.get_pipeline_defaults(scope.company_slug)
max_crawl_pages = request.max_crawl_pages or (_defaults.max_crawl_pages if _defaults else None)
```
Only applies to Optional fields (`max_crawl_pages`, `max_crawl_depth`) where `None` clearly means "not set". Non-optional fields like `max_queries` (default 150) pass through directly since we can't distinguish "user sent default" from "user wants default".

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/companies/{slug}/settings/pipeline-defaults` | tenant | Get pipeline defaults |
| PUT | `/companies/{slug}/settings/pipeline-defaults` | superuser+tenant | Update pipeline defaults |

### 25.5 Feature 2A — Knowledge Doc Upload & Storage

**New/modified files:** `core/models/knowledge_docs.py` (NEW), `api/services/knowledge_doc_service.py` (NEW), `api/schemas/knowledge_docs.py` (NEW), `api/routers/knowledge_docs.py` (NEW), `api/app.py` (register router), `tests/api/test_knowledge_docs.py` (NEW — 19 tests)

**Storage layout:**
```
artifacts/knowledge_docs/{effective_slug}/
├── _metadata.json                   # List[KnowledgeDocument]
├── {uuid}_{original_name}.md
├── {uuid}_{original_name}.txt
└── {uuid}_{original_name}.pdf
```

**`KnowledgeDocument` model (`core/models/knowledge_docs.py`):**
- `id`: UUID string
- `filename`: original filename (sanitized)
- `stored_filename`: `{uuid}_{sanitized_name}` on disk
- `content_type`: MIME type from extension mapping
- `file_size_bytes`, `word_count`: computed on upload
- `uploaded_at`, `uploaded_by`, `company_slug`, `product_slug`, `effective_slug`
- `is_embedded: bool = False`, `last_embedded_at: Optional[datetime] = None`

**Supported formats:** `.md`, `.txt`, `.pdf` (pdfplumber), `.docx` (python-docx)
**Size limit:** 10MB per file (configurable via `DEFAULT_MAX_UPLOAD_BYTES`)

**Validation chain:**
1. Filename sanitization (`_sanitize_filename()` — strips paths, removes suspicious chars)
2. Extension whitelist check
3. Size limit check (after reading content)
4. Path traversal check (`stored_path.resolve().is_relative_to(doc_dir.resolve())`)

**Endpoints:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/companies/{slug}/knowledge-docs` | member+tenant | Upload file (multipart) |
| GET | `/companies/{slug}/knowledge-docs` | tenant | List docs (with `?product_slug=`) |
| GET | `/companies/{slug}/knowledge-docs/{doc_id}` | tenant | Get doc metadata |
| DELETE | `/companies/{slug}/knowledge-docs/{doc_id}` | member+tenant | Delete doc + file |
| GET | `/companies/{slug}/knowledge-docs/{doc_id}/download` | tenant | Stream file (FileResponse) |

**Cross-product search:** GET detail, DELETE, and download endpoints use `_find_across_product_slugs()` helper — a generic `TypeVar+Callable` helper that first checks the company slug, then scans all `{slug}__*` product subdirectories. This ensures a doc uploaded to `ramp__corporate-card` can be found when queried via the `ramp` company endpoint.

**New dependencies:** `pdfplumber>=0.10`, `python-docx>=1.0`

### 25.6 Feature 2B — S1 Pipeline Integration

**Modified files:** `core/models/gap_analysis.py` (add `DiscoverySource.KNOWLEDGE_DOC`, `knowledge_doc_dir` on `GapAnalysisInput`), `core/gap_analysis/steps/s1_embed_assets.py` (load + chunk + embed knowledge docs), `api/tasks/runner.py` (resolve `knowledge_doc_dir` path), `tests/gap_analysis/steps/test_s1_knowledge_docs.py` (NEW — 15 tests)

**Integration point in `embed_company_assets()`:**
1. After site discovery + chunking → existing SemanticUnits
2. If `knowledge_doc_dir` is set → load docs from `_metadata.json` → extract text → chunk via `_chunk_paragraphs()` → create SemanticUnits with `discovery_source="knowledge_doc"` and `url=None`
3. Merge both lists → embed all → store in pgvector

**Text extraction:** Uses canonical `extract_text()` from `core/shared_tools/text_extraction.py` (supports .md, .txt, .pdf via pdfplumber, .docx via python-docx).

**Runner resolves path with product fallback:**
```
artifacts/knowledge_docs/{effective_slug}/  →  fallback  →  artifacts/knowledge_docs/{company_slug}/
```

**Backward compat:** `knowledge_doc_dir` defaults to `None`. Existing pipelines produce identical results.

### 25.7 Feature 2C — Embedded Status Tracking

**Modified files:** `core/gap_analysis/steps/s1_embed_assets.py` (call mark function after embedding), `core/shared_tools/knowledge_doc_metadata.py` (shared `mark_documents_embedded()`)

After embedding completes in s1, calls `mark_documents_embedded(knowledge_doc_dir)` which:
1. Acquires `metadata_lock`
2. Re-reads `_metadata.json` inside lock (TOCTOU safe)
3. Sets `is_embedded=True` and `last_embedded_at=now()` on all documents
4. Writes atomically via tmp file + `os.replace()`

### 25.8 Shared Modules Extracted (Review Fixes C2/C3)

**C2 Fix — `core/shared_tools/text_extraction.py` (NEW):**
Canonical `extract_text(file_path: Path) -> str` function. Both `api/services/knowledge_doc_service.py` (upload) and `core/gap_analysis/steps/s1_embed_assets.py` (embed) import from here. Eliminates 25 lines of duplicated PDF/DOCX extraction code.

**C3 Fix — `core/shared_tools/knowledge_doc_metadata.py` (NEW):**
Single process-wide `metadata_lock = threading.Lock()`. Provides `load_metadata()`, `save_metadata()`, `slug_dir()`, `metadata_path()`, and `mark_documents_embedded()`. Both the service (upload/delete) and s1 (mark-as-embedded) use the **same** lock instance, preventing race conditions when uploading during a pipeline run.

Architecture constraint: `core/` cannot import from `api/`, so shared code lives in `core/shared_tools/`.

### 25.9 Review Fixes Summary

| Fix | Category | What | Detail |
|-----|----------|------|--------|
| C1 | DRY | Extracted `_find_across_product_slugs()` | Generic TypeVar+Callable helper; fixed delete missing `subdir.name == slug` check |
| C2 | Dedup | Created `core/shared_tools/text_extraction.py` | Canonical text extraction shared by service + s1 |
| C3 | Race condition | Created `core/shared_tools/knowledge_doc_metadata.py` | Same metadata_lock shared by service + s1 |
| W1 | Dead code | Removed dead import in `settings.py` | `from api.auth.dependencies import require_tenant as _rt` |
| W3 | Missing wiring | Pipeline defaults → runner | `max_crawl_pages`/`max_crawl_depth` now use company defaults as fallback |
| W5 | Type safety | Added type annotation to `_doc_to_response` | `doc: KnowledgeDocument` parameter annotation |

### 25.10 Runner Integration — Pipeline Defaults Wiring

In `api/tasks/runner.py::run_gap_pipeline_task()`:
```python
_defaults = auth_store.get_pipeline_defaults(scope.company_slug) if auth_store else None

input_data = GapAnalysisInput(
    ...
    max_crawl_pages=(
        request.max_crawl_pages
        or (_defaults.max_crawl_pages if _defaults else None)
    ),
    max_crawl_depth=(
        request.max_crawl_depth
        or (_defaults.max_crawl_depth if _defaults else None)
    ),
    knowledge_doc_dir=str(knowledge_doc_dir) if knowledge_doc_dir else None,
    ...
)
```

Knowledge doc dir resolution: checks `artifacts/knowledge_docs/{effective_slug}/`, falls back to `artifacts/knowledge_docs/{company_slug}/`.

### 25.11 New Endpoints Summary

| # | Method | Path | Auth | Feature |
|---|--------|------|------|---------|
| 1 | GET | `/companies/{slug}/settings/team` | tenant | 1A |
| 2 | PUT | `/companies/{slug}/settings/team/{user_id}` | superuser+tenant | 1A |
| 3 | GET | `/companies/{slug}/settings/profile` | tenant | 1B |
| 4 | PUT | `/companies/{slug}/settings/profile` | superuser+tenant | 1B |
| 5 | GET | `/companies/{slug}/settings/pipeline-defaults` | tenant | 1C |
| 6 | PUT | `/companies/{slug}/settings/pipeline-defaults` | superuser+tenant | 1C |
| 7 | POST | `/companies/{slug}/knowledge-docs` | member+tenant | 2A |
| 8 | GET | `/companies/{slug}/knowledge-docs` | tenant | 2A |
| 9 | GET | `/companies/{slug}/knowledge-docs/{doc_id}` | tenant | 2A |
| 10 | DELETE | `/companies/{slug}/knowledge-docs/{doc_id}` | member+tenant | 2A |
| 11 | GET | `/companies/{slug}/knowledge-docs/{doc_id}/download` | tenant | 2A |

### 25.12 Files Changed Summary

| File | Action | Lines |
|------|--------|-------|
| `core/models/knowledge_docs.py` | NEW | ~35 |
| `core/models/organization.py` | NEW | ~25 |
| `core/models/gap_analysis.py` | Modified | +3 (DiscoverySource.KNOWLEDGE_DOC, knowledge_doc_dir field) |
| `core/shared_tools/text_extraction.py` | NEW | ~47 |
| `core/shared_tools/knowledge_doc_metadata.py` | NEW | ~97 |
| `core/gap_analysis/steps/s1_embed_assets.py` | Modified | ~40 lines (knowledge doc loading + shared imports) |
| `api/auth/store.py` | Modified | +60 (update_user, get/update_pipeline_defaults) |
| `api/routers/settings.py` | NEW | ~150 |
| `api/routers/knowledge_docs.py` | NEW | ~180 |
| `api/schemas/settings.py` | NEW | ~70 |
| `api/schemas/knowledge_docs.py` | NEW | ~30 |
| `api/services/knowledge_doc_service.py` | NEW | ~206 |
| `api/app.py` | Modified | +2 (register routers) |
| `api/tasks/runner.py` | Modified | +15 (pipeline defaults + knowledge_doc_dir) |
| `tests/api/test_settings_team.py` | NEW | 16 tests |
| `tests/api/test_settings_profile.py` | NEW | 11 tests |
| `tests/api/test_settings_pipeline.py` | NEW | 12 tests |
| `tests/api/test_knowledge_docs.py` | NEW | 19 tests |
| `tests/gap_analysis/steps/test_s1_knowledge_docs.py` | NEW | 15 tests |

### 25.13 Deferred Items

| Item | Priority | Description |
|------|----------|-------------|
| Phase 1D — API Key Configuration | Future sprint | Encrypted per-company keys, RuntimeConfig passthrough, masked reads |
| W2: `update_pipeline_defaults` ignores unknown kwargs | Low | Silently ignores via Pydantic — no error for typos |
| W4: `_save_metadata` doesn't create parent dir | Low | Relies on upload creating it first |
| W6: No pagination on list endpoints | Medium | Settings team list and knowledge docs list return all items |
| I1-I5: Minor code quality items | Low | See backlog PB-40 through PB-44 |

---

## 26. SQLAlchemy & Service Layer Migration — 3-Phase Database Architecture

> **Completed:** 2026-02-27 (Phase 1), 2026-02-28 (Phases 2 & 3)
> **Total New Tests:** 235 (44 + 96 + 46 + 49)
> **Total Test Count After:** 1262 (1127 passed + 135 skipped)
> **Key Decision IDs:** D-DB-1, D-AUTH-2, D-SVC-1, D-TASKSTORE-1

### 26.1 Migration Overview & Strategy

The migration converts the content strategy engine from a **pure filesystem** persistence model to a **hybrid filesystem + PostgreSQL** architecture in three sequential phases. Each phase follows the same proven pattern: **Protocol → JsonService (backward compat) → DbService (opt-in)**. The filesystem remains the source of truth for large artifacts; the database provides queryable metadata, aggregations, and structured relational data.

**Why three phases (not one big migration):**
1. Phase 1 establishes infrastructure (ORM, repos, migrations) with zero production impact.
2. Phase 2 migrates the most critical service (auth) as a proof-of-concept for the dual-mode pattern.
3. Phase 3 applies the proven pattern across all remaining services and adds the TaskStore.

**Zero-breakage guarantee:** At every phase, existing tests pass unchanged. The `DATABASE_URL` environment variable acts as the single opt-in switch. Without it, the system behaves identically to pre-migration.

**Directory structure added:**
```
core/
├── auth/                           ← Phase 2: Auth service layer
│   ├── __init__.py
│   ├── service.py                  ← AuthServiceProtocol
│   ├── json_service.py             ← JsonAuthService (wraps AuthStore)
│   ├── db_service.py               ← DbAuthService (uses SQL repos)
│   └── utils/                      ← Pure functions, zero I/O
│       ├── __init__.py
│       ├── passwords.py            ← hash_password, verify_password, DUMMY_HASH
│       ├── tokens.py               ← create_access_token, verify_token, get_secret_key
│       └── domain.py               ← normalize_domain, derive_slug, field allowlists
├── db/                             ← Phase 1: ORM infrastructure
│   ├── __init__.py
│   ├── base.py                     ← DeclarativeBase + UUIDPKMixin + TimestampMixin
│   ├── engine.py                   ← Lazy async engine + session factory
│   ├── enums.py                    ← 12 Postgres enum types
│   ├── dependencies.py             ← FastAPI DI helpers (get_db_session, etc.)
│   ├── models/                     ← 12 ORM model files (31 tables total)
│   │   ├── organization.py         ← CompanyModel, ProductModel, UserModel, InviteModel, PipelineDefaultsModel
│   │   ├── gap_analysis.py         ← RunQueryModel, RunCitationModel, QueryGapModel, QueryExemplarModel, ClusterSpecModel, SpaResultModel, CentroidResultModel
│   │   ├── embeddings.py           ← RunQueryEmbeddingModel, RunCitationEmbeddingModel, RunParagraphScoreModel
│   │   ├── content.py              ← ContentBriefModel, ContentPieceModel, PieceStageModel
│   │   ├── cache.py                ← UrlEnrichmentCacheModel, UrlStructuralSignalsModel
│   │   ├── pipelines.py            ← PipelineRunModel, StageRunModel
│   │   ├── knowledge_docs.py       ← KnowledgeDocModel, KnowledgeDocMetadataModel
│   │   ├── site_audit.py           ← SiteAuditFindingModel
│   │   ├── topic_discovery.py      ← TopicModel
│   │   ├── tracking.py             ← TrackingModel
│   │   └── api_tasks.py            ← ApiTaskModel (Phase 3 — DB-backed TaskStore)
│   ├── migrations/
│   │   ├── env.py                  ← Alembic environment configuration
│   │   └── versions/
│   │       ├── 0001_initial_schema.py       ← All enums + 31 tables
│   │       ├── 0002_hnsw_indexes.py         ← pgvector HNSW indexes (separated for deploy control)
│   │       ├── 0003_fix_gap_enum_add_indexes.py  ← GapClassification fix + strategic indexes
│   │       └── 0004_api_tasks.py            ← ApiTaskModel table
│   └── repositories/               ← 16 repository files
│       ├── base.py                 ← SQLAlchemyRepository[ModelT] generic base
│       ├── auth_repo.py            ← Phase 2: AuthRepository
│       ├── company_repo.py         ← CompanyRepository
│       ├── product_repo.py         ← Phase 2: ProductRepository
│       ├── invite_repo.py          ← Phase 2: InviteRepository
│       ├── pipeline_defaults_repo.py  ← Phase 2: PipelineDefaultsRepository
│       ├── pipeline_repo.py        ← Enhanced Phase 3: get_latest_completed, list_runs_by_slug
│       ├── gap_analysis_repo.py    ← Enhanced Phase 3: paginated queries, classification counts, SPA results
│       ├── content_repo.py         ← Enhanced Phase 3: list_pieces_by_run, get_piece_detail
│       ├── embedding_repo.py       ← EmbeddingRepository (pgvector similarity search)
│       ├── cache_repo.py           ← UrlEnrichmentCacheRepository (TTL-based)
│       ├── signal_repo.py          ← Phase 3: SignalRepository (SQL aggregations on 45 signals)
│       ├── platform_repo.py        ← Phase 3: PlatformRepository (platform coverage analytics)
│       ├── task_repo.py            ← Phase 3: TaskRepository (api_tasks CRUD)
│       ├── knowledge_doc_repo.py   ← KnowledgeDocRepository
│       └── tracking_repo.py        ← TrackingRepository
├── services/                       ← Phase 3: Service layer protocols + implementations
│   ├── __init__.py
│   ├── gap_data.py                 ← GapDataServiceProtocol (7 async methods)
│   ├── json_gap_data.py            ← JsonGapDataService (wraps filesystem)
│   ├── db_gap_data.py              ← DbGapDataService (SQL queries)
│   ├── brand_data.py               ← BrandDataServiceProtocol (2 async methods)
│   ├── json_brand_data.py          ← JsonBrandDataService
│   ├── db_brand_data.py            ← DbBrandDataService
│   ├── content_data.py             ← ContentDataServiceProtocol (3 async methods)
│   ├── json_content_data.py        ← JsonContentDataService
│   ├── db_content_data.py          ← DbContentDataService
│   ├── task_store.py               ← TaskStoreProtocol (10 methods) + exception re-exports
│   └── db_task_store.py            ← DbTaskStore (write-through with in-memory cache)
```

---

### 26.2 Phase 1 — SQLAlchemy ORM Infrastructure (D-DB-1)

**Sprint:** `sqlalchemy-migration` · **Date:** 2026-02-27 · **Tests:** +44 DB tests · **Files:** 44 new, 3 modified

Phase 1 establishes the complete PostgreSQL database layer — ORM models, repositories, Alembic migrations, and the engine factory — without wiring any of it into existing routes or services. This is a pure infrastructure phase: all new code is additive, and no existing behavior changes.

**ORM Choice: Pure SQLAlchemy 2.0 Declarative (NOT SQLModel)**

SQLAlchemy won a 6-0 scorecard against SQLModel across the six features that matter most in this codebase:

| Feature | SQLAlchemy 2.0 | SQLModel | Winner |
|---------|---------------|----------|--------|
| pgvector `Vector(1536)` | Native column type | Requires escape hatch | SQLAlchemy |
| 12+ Postgres enums | Native `Enum(PgEnum)` | Limited enum support | SQLAlchemy |
| JSONB with `server_default` | Native `mapped_column(JSONB, server_default=...)` | Partial support | SQLAlchemy |
| `ARRAY(Text)` columns | Native `mapped_column(ARRAY(Text))` | Not supported | SQLAlchemy |
| Self-referential FK | Standard FK pattern | Requires workarounds | SQLAlchemy |
| Alembic autogenerate | Full support | Partial/buggy | SQLAlchemy |

**Rationale:** We already maintain 3 model layers (core Pydantic, API schemas, ORM) with explicit repo conversions. SQLModel's dual Pydantic+ORM class provides zero benefit in this architecture — it would add complexity (escape hatches for pgvector, enums, JSONB) without reducing any.

**Three-Tier Storage Model:**
- **Tier 1 (Normalized Postgres tables):** Citation metadata, structural signals, query gaps, cluster specs, SPA results, pipeline runs, auth data. Every operation filters/joins/aggregates individual rows — relational is the correct abstraction.
- **Tier 2 (pgvector columns):** Embedding vectors for similarity search. `Vector(1536)` with HNSW indexes. Tables: `persona_embeddings`, `cps_training_snippets`, `cps_training_queries`.
- **Tier 3 (Filesystem/S3):** Large blobs — raw paragraphs, platform response JSONLs, Plotly HTML visualizations, pipeline JSON archives. Too large for Postgres rows (enriched_citations.json exceeds 20MB for some clients).

---

### 26.3 Phase 1 — ORM Tables (31 Total)

All models use two mixins from `core/db/base.py`:

```python
class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**Organization & Auth (5 tables):**

| Table | Key Columns | Indexes | Notes |
|-------|-------------|---------|-------|
| `companies` | `slug (unique)`, `name`, `domain`, `additional_domains (ARRAY)`, `is_archived` | `slug`, `domain` | Root entity. 1:many → products, users, invites |
| `products` | `company_id (FK)`, `slug`, `name`, `domain`, `description` | `(company_id, slug)` unique | Represents a product line within a company |
| `users` | `company_id (FK)`, `email (unique)`, `password_hash`, `role (Enum)`, `first_name`, `last_name`, `is_active` | `email`, `company_id` | PBKDF2 hashed passwords |
| `invites` | `company_id (FK)`, `code (unique)`, `role (Enum)`, `created_by (FK)`, `redeemed_by (FK nullable)`, `expires_at` | `code` | Immutable post-creation (no `updated_at`) |
| `company_pipeline_defaults` | `company_id (FK unique)`, `defaults_json (JSONB)` | `company_id` | 1:1 with companies |

**Pipeline Infrastructure (2 tables):**

| Table | Key Columns | Indexes | Notes |
|-------|-------------|---------|-------|
| `pipeline_runs` | `company_id (FK)`, `product_id (FK nullable)`, `pipeline_type (Enum)`, `status (Enum)`, `effective_slug`, `config_json (JSONB)`, `result_json (JSONB)`, `completed_at` | `effective_slug`, `(company_id, pipeline_type)`, partial `(status)` for active runs | Self-referential FK: `parent_run_id` for sub-steps |
| `pipeline_stage_logs` | `run_id (FK)`, `stage_name`, `status (Enum)`, `started_at`, `completed_at`, `error_message` | `run_id` | Per-step progress tracking |

**Gap Analysis Data (7 tables):**

| Table | Key Columns | Indexes | Notes |
|-------|-------------|---------|-------|
| `run_queries` | `run_id (FK)`, `query_id`, `cluster_name`, `query_text`, `buyer_stage`, `persona_tag` | `(run_id, query_id)` unique, `(run_id, cluster_name)` | Insertion order matters (FK target for citations) |
| `run_citations` | `run_id (FK)`, `query_id (FK composite)`, `engine (Enum)`, `url`, `domain`, `snippet`, `title`, `citation_rank`, `url_enrichment_id (FK nullable)` | `(run_id, query_id)`, `(run_id, engine)`, `url_enrichment_id` | Composite FK: `(run_id, query_id)` → `run_queries` |
| `query_gaps` | `run_id (FK)`, `query_id`, `query_text`, `cluster_name`, `gap (Float)`, `classification (Enum)`, `avg_citation_similarity`, `best_company_similarity`, `best_company_unit_text`, `content_brief (JSONB)`, `targeted_by_content_id (FK nullable)` | `(run_id, query_id)` unique, `(run_id, classification)`, `(run_id, cluster_name)` | Links to content_pieces for gap-closing |
| `query_exemplars` | `query_gap_id (FK)`, `url`, `domain`, `similarity (Float)`, `snippet`, `authority_type`, `rank`, `url_enrichment_id (FK nullable)` | `query_gap_id` | Cascade-deletes with parent query_gap |
| `cluster_specs` | `run_id (FK)`, `cluster_name`, `query_count`, `total_citations_analyzed`, word count stats, boolean pattern rates, `dominant_content_type`, `structural_rates (JSONB)`, `exemplar_themes (ARRAY)` | `(run_id, cluster_name)` unique | Aggregate structural profile per cluster |
| `spa_results` | `run_id (FK)`, `cluster_name`, `t_stat`, `p_value`, `mean_citation_similarity`, `mean_company_similarity`, `effect` | `(run_id, cluster_name)` unique | t-test statistics per cluster |
| `centroid_results` | `run_id (FK)`, `cluster_name`, `distance (Float)` | `(run_id, cluster_name)` unique | Company-to-citation centroid distance |

**Cache (3 tables):**

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `url_enrichment_cache` | `url_hash (unique)`, `url`, `domain`, `title`, `main_content_text`, `content_type`, `status_code`, `fetched_at`, `expires_at` | Query-agnostic — cached by URL, shared across runs |
| `url_structural_signals` | `url_enrichment_id (FK 1:1)`, 45 individual typed columns across 4 categories | **Normalized columns, NOT JSONB** — enables SQL WHERE/GROUP BY/AVG on each signal |
| `platform_result_cache` | `query_hash`, `engine (Enum)`, `result_json (JSONB)`, `expires_at` | TTL-based caching of platform search results |

**Structural signals columns (45 in `url_structural_signals`):**

| Category | Columns (sample) | Type |
|----------|-------------------|------|
| Readability (6) | `word_count`, `paragraph_count`, `avg_sentence_length`, `reading_level`, `vocabulary_diversity`, `readability_score` | Integer/Float |
| Structure (15) | `header_count`, `h2_count`, `h3_count`, `ordered_list_count`, `unordered_list_count`, `table_count`, `code_block_count`, `image_count`, `has_faq_section`, `has_table_of_contents`, `has_key_takeaways` | Integer/Boolean |
| Content Richness (12) | `definition_count`, `statistic_count`, `data_visualization_count`, `callout_count`, `has_expert_quotes`, `citation_density`, `internal_link_count`, `external_link_count` | Integer/Float/Boolean |
| Authority (12) | `is_official_doc`, `has_author_bio`, `has_publish_date`, `has_schema_markup`, `domain_authority_tier`, `content_freshness_tier`, `has_canonical_url` | Boolean/String |

**Embeddings (3 tables):**

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `run_query_embeddings` | `run_id (FK)`, `query_id`, `embedding (Vector(1536))` | pgvector with HNSW index |
| `run_citation_embeddings` | `run_id (FK)`, `citation_id (FK)`, `embedding (Vector(1536))` | pgvector with HNSW index |
| `run_paragraph_scores` | `run_id (FK)`, `citation_id (FK)`, `paragraph_index`, `rank`, `text`, `similarity (Float)` | Top-k paragraph selection results |

**Other Tables (11):**

| Domain | Tables | Notes |
|--------|--------|-------|
| Content Engine | `content_pieces`, `research_artifacts` | Content pipeline outputs |
| Tracking | `tracking_snapshots`, `content_mention_tracking`, `content_piece_tracking` | Daily metric tracking with partial unique indexes |
| Site Audit | `site_audits`, `audit_findings` | Site crawl findings |
| Topic Discovery | `topic_discoveries`, `discovered_topics` | Topic research results |
| Knowledge Docs | `knowledge_documents` | Uploaded reference documents |
| Task Store | `api_tasks` | Phase 3 addition — mirrors JSON TaskStore |

**Postgres Enum Types (12):**

| Enum | Values |
|------|--------|
| `UserRole` | superuser, member, viewer |
| `PipelineType` | research, gap_analysis, content, content_refresh, site_audit, topic_discovery |
| `PipelineStatus` | pending, running, completed, failed, cancelled |
| `StageStatus` | pending, running, completed, failed, skipped, cached |
| `SearchEngine` | openai, claude, gemini, perplexity |
| `GapClassification` | significant_gap, gap_to_close, roughly_equal, company_wins, no_data |
| `ArtifactType` | company_context, persona, style_guide |
| `ArtifactStatus` | draft, approved, archived |
| `ContentPieceStatus` | planned, drafting, review, approved, published, archived |
| `FindingSeverity` | critical, high, medium, low, info |
| `TrackingStatus` | pending, completed, failed |

---

### 26.4 Phase 1 — Repository Pattern

**Generic Base:** `core/db/repositories/base.py`

```python
class SQLAlchemyRepository(Generic[ModelT]):
    model: ClassVar[type[ModelT]]  # Set by each concrete repo

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID | str) -> ModelT | None
    async def create(self, **kwargs) -> ModelT
    async def update(self, id: UUID | str, **kwargs) -> ModelT | None
    async def delete(self, id: UUID | str) -> bool
    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelT]
```

**Transaction Ownership Contract — Critical Design:**
- Repos call `session.add()` + `session.flush()` **only**
- Repos **NEVER** call `session.commit()` or `session.rollback()`
- The DI session generator owns the transaction lifecycle

**Why flush-only:**
1. **Savepoint-based test isolation** — each test wraps in a transaction that rolls back. If repos committed, rollback wouldn't work.
2. **Multi-repo atomic transactions** — multiple repos can operate within one session, and a single commit makes all changes atomic.
3. **Clean separation** — repos are pure data access, the application layer decides when to commit.

**Domain Repositories (8 initial + 8 added in Phases 2-3):**

| Repository | Phase | Key Methods |
|------------|-------|-------------|
| `CompanyRepository` | 1 | `get_by_slug`, `get_by_domain`, `slug_exists`, `list_active` |
| `EmbeddingRepository` | 1 | `bulk_upsert`, `similarity_search` (pgvector cosine_distance) |
| `CacheRepository` | 1 | `get_fresh_platform_result` (TTL check), `get_signals_by_url` |
| `GapAnalysisRepository` | 1+3 | Phase 1: basic CRUD. Phase 3: `get_gaps_paginated`, `get_classification_counts`, `get_spa_results`, `get_centroid_results`, `count_gaps_by_run`, `get_cluster_specs` |
| `PipelineRunRepository` | 1+3 | Phase 1: basic CRUD. Phase 3: `get_latest_completed(slug, pipeline_type)`, `list_runs_by_slug` |
| `ContentRepository` | 1+3 | Phase 1: basic CRUD. Phase 3: `list_pieces_by_run`, `get_piece_detail` |
| `AuthRepository` | 2 | `get_by_email`, `get_by_id`, `create_user`, `update_user`, `get_by_company` |
| `InviteRepository` | 2 | `get_by_code`, `mark_redeemed`, `list_by_company` |
| `ProductRepository` | 2 | `get_by_slugs(company_id, product_slug)`, `list_by_company` |
| `PipelineDefaultsRepository` | 2 | `get_by_company`, `upsert_by_company` |
| `SignalRepository` | 3 | `get_signal_averages`, `get_signal_correlations`, `get_cluster_patterns` — all SQL aggregation (see §26.15) |
| `PlatformRepository` | 3 | `get_platform_summaries`, `get_platform_url_sets`, `get_citation_exclusivity` — SQL analytics (see §26.15) |
| `TaskRepository` | 3 | `get_by_task_id`, `create_task`, `update_by_task_id`, `list_tasks`, `find_active_by_slug`, `mark_orphans_failed` |

---

### 26.5 Phase 1 — Alembic Migrations

All migrations are **hand-written** (not autogenerated). Autogenerate has known issues with pgvector extensions, Postgres enum creation, partial indexes, and composite FKs.

**Migration 0001: `0001_initial_schema.py`**
- Creates `pgvector` extension: `op.execute('CREATE EXTENSION IF NOT EXISTS vector')`
- Creates all 12 Postgres enum types via `op.execute('CREATE TYPE ...')`
- Creates 31 tables with FKs, indexes, and ON DELETE policies (CASCADE/SET NULL/RESTRICT)
- Insertion order respects FK dependencies: `companies` → `products` → `users` → `invites` → pipeline tables → gap analysis tables → etc.
- Partial indexes for performance (e.g., active pipeline runs only)

**Migration 0002: `0002_hnsw_indexes.py`**
- Creates HNSW vector indexes on embedding columns for fast similarity search
- **Separated from 0001** because HNSW index creation locks tables — in production with existing data, this can take minutes and must be deployed independently

**Migration 0003: `0003_fix_gap_enum_add_indexes.py`**
- Fixes `GapClassification` enum values to match the API schema: `significant_gap`, `gap_to_close`, `roughly_equal`, `company_wins`, `no_data` (previously had mismatched strings like `closure_opportunity`)
- Adds strategic indexes identified during Phase 3 service implementation

**Migration 0004: `0004_api_tasks.py`**
- Creates `api_tasks` table for DB-backed TaskStore (Phase 3)
- 4 indexes: `task_id` (unique), `effective_slug`, `status`, `(company_slug, pipeline)` composite

---

### 26.6 Phase 1 — Engine & Session Factory

**`core/db/engine.py`:**

```python
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None
_lock = threading.Lock()

def get_engine() -> AsyncEngine:
    """Lazy singleton — creates engine on first call, NOT at import time."""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:  # Double-checked locking
                _engine = create_async_engine(
                    settings.database_url,
                    pool_pre_ping=True,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    pool_recycle=3600,
                )
    return _engine

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns session factory. Sessions expire_on_commit=False."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False
        )
    return _session_factory
```

**Key design decisions:**
- **Lazy initialization:** Engine created on first call to `get_engine()`, NOT at import time. Existing pipeline scripts without `DATABASE_URL` are completely unaffected — they never call `get_engine()`.
- **Double-checked locking:** Thread-safe singleton creation. Only one engine is ever created per process.
- **`expire_on_commit=False`:** Prevents SQLAlchemy from expiring attributes after commit, which would cause lazy-load queries. All data is eagerly loaded in repos.
- **Computed `database_url_sync`:** Derived from `database_url` by replacing `+asyncpg` with standard `postgresql://`. Single source of truth prevents sync/async URL drift. Used by Alembic (which requires sync connections).

**Configuration in `core/config/settings.py`:**
```python
database_url: Optional[str] = None              # postgresql+asyncpg://...
database_echo: bool = False                      # SQL logging
database_pool_size: int = 5
database_max_overflow: int = 10

@property
def database_url_sync(self) -> Optional[str]:
    """Sync variant for Alembic."""
    if self.database_url:
        return self.database_url.replace("+asyncpg", "")
    return None
```

---

### 26.7 Phase 2 — Auth Migration: Three-Layer Decomposition (D-AUTH-2)

**Sprint:** `auth-migration-phase2` · **Date:** 2026-02-28 · **Tests:** +96 · **Files:** 18 new, 32 modified

Phase 2 proves the dual-mode service pattern by migrating authentication — the most critical and widely-used service. The existing `AuthStore` (JSON-file backed, synchronous) is wrapped in `JsonAuthService` for backward compatibility, while `DbAuthService` provides the SQL-backed implementation for production.

**Three-Layer Architecture:**

```
Layer 1 — Pure Utilities (core/auth/utils/)
    Zero I/O, zero side effects, importable anywhere
    ├── passwords.py   → hash_password(), verify_password(), DUMMY_HASH
    ├── tokens.py      → create_access_token(), verify_token(), get_secret_key()
    └── domain.py      → normalize_domain(), derive_slug(), mutable field frozensets

Layer 2 — Service Interface + Implementations
    ├── core/auth/service.py       → AuthServiceProtocol (runtime_checkable Protocol)
    ├── core/auth/json_service.py  → JsonAuthService (wraps AuthStore)
    └── core/auth/db_service.py    → DbAuthService (uses SQL repos)

Layer 3 — DI + Middleware
    ├── api/dependencies.py        → get_auth_service() DI function
    └── api/auth/middleware.py     → Decoupled from AuthStore; uses utilities only
```

**Why three layers (not two):**
1. **Utilities** are needed by middleware, which runs outside FastAPI's DI system. If utilities lived inside the service, middleware would depend on the service implementation.
2. **Protocol** enables transparent swap. Routers program to `AuthServiceProtocol`, not `JsonAuthService` or `DbAuthService`.
3. **DI** picks the implementation based on `DATABASE_URL` availability. Tests override via `dependency_overrides`.

---

### 26.8 Phase 2 — AuthServiceProtocol

**`core/auth/service.py`:**

```python
@runtime_checkable
class AuthServiceProtocol(Protocol):
    # ── Company operations (async) ──
    async def get_company_by_slug(self, slug: str) -> Optional[Company]: ...
    async def get_company_by_id(self, company_id: str) -> Optional[Company]: ...
    async def get_company_by_domain(self, raw_domain: str) -> Optional[Company]: ...
    async def list_companies(self) -> List[Company]: ...
    async def create_company(self, slug, name, domain, products=None, additional_domains=None) -> Company: ...
    async def update_company(self, slug: str, **kwargs) -> Company: ...

    # ── Product operations (async) ──
    async def get_product(self, company_slug: str, product_slug: str) -> Optional[Product]: ...
    async def add_product(self, company_slug: str, product: Product) -> Product: ...
    async def update_product(self, company_slug: str, product_slug: str, **kwargs) -> Product: ...
    async def remove_product(self, company_slug: str, product_slug: str) -> bool: ...

    # ── User operations (async) ──
    async def get_user_by_email(self, email: str) -> Optional[Dict]: ...
    async def get_user_by_id(self, user_id: str) -> Optional[Dict]: ...
    async def list_users_for_company(self, company_id: str) -> List[UserProfile]: ...
    async def create_user(self, company_id, email, password, first_name, last_name, role) -> UserProfile: ...
    async def update_user(self, user_id, requesting_user_id, **kwargs) -> UserProfile: ...

    # ── Registration + Invites (async) ──
    async def register_user(self, first_name, last_name, email, password, company_name, company_domain) -> Tuple[UserProfile, Company]: ...
    async def create_invite(self, company_slug: str, role: str) -> str: ...
    async def redeem_invite(self, invite_code, first_name, last_name, email, password) -> Tuple[UserProfile, Company]: ...

    # ── Pipeline Defaults (async) ──
    async def get_pipeline_defaults(self, company_slug: str) -> CompanyPipelineDefaults: ...
    async def update_pipeline_defaults(self, company_slug: str, **kwargs) -> CompanyPipelineDefaults: ...

    # ── Tokens (sync — pure computation, no I/O) ──
    def create_access_token(self, user_id: str, company_slug: str, expires_hours: int = 24) -> str: ...
    def create_stream_token(self, user_id: str, company_slug: str, expires_minutes: int = 5) -> str: ...
    def verify_token(self, token: str) -> Optional[Dict]: ...
```

**~25 async methods + 3 sync token methods.** Token methods are sync because they are pure HMAC computation with no I/O.

---

### 26.9 Phase 2 — JsonAuthService & DbAuthService

**`core/auth/json_service.py` — JsonAuthService:**

Wraps the existing synchronous `AuthStore` (`api/auth/store.py`).

```python
class JsonAuthService:
    def __init__(self, store: AuthStore) -> None:
        self._store = store

    # Read ops: sync (in-memory dict, near-instant)
    async def get_company_by_slug(self, slug: str) -> Optional[Company]:
        return self._store.get_company(slug)  # Direct sync call — no thread needed

    # Write ops: threaded to avoid blocking event loop
    async def register_user(self, ...) -> Tuple[UserProfile, Company]:
        return await asyncio.to_thread(self._store.register_user, ...)

    # Token ops: delegated to utilities
    def create_access_token(self, user_id, company_slug, expires_hours=24) -> str:
        return create_access_token(self._store._secret_key, user_id, company_slug, expires_hours)
```

**Key pattern:** Read ops are synchronous (AuthStore holds data in-memory dicts, O(1) lookup). Write ops use `asyncio.to_thread()` because AuthStore holds an `RLock` for thread safety and writes to disk. Token ops delegate to `core/auth/utils/tokens.py` utilities.

**`core/auth/db_service.py` — DbAuthService:**

Takes 5 repositories + `secret_key` as constructor arguments.

```python
class DbAuthService:
    def __init__(
        self,
        company_repo: CompanyRepository,
        auth_repo: AuthRepository,
        invite_repo: InviteRepository,
        product_repo: ProductRepository,
        pipeline_defaults_repo: PipelineDefaultsRepository,
        secret_key: str,
    ) -> None: ...
```

**Key business logic ported from AuthStore:**
- **Registration:** Domain dedup via `company_repo.get_by_domain()`, slug collision avoidance, atomic company + superuser creation
- **Invite create:** Generate random code, validate company exists, set TTL
- **Invite redeem:** Lookup code, validate not expired/redeemed, create user, mark redeemed — all in one session
- **User update guards:** Self-deactivation prevention, last-superuser protection

**ORM ↔ Pydantic conversion methods:**
- `_orm_to_company(CompanyModel) → Company`: Recursively converts products list
- `_orm_to_user_dict(UserModel) → Dict`: Includes `password_hash` (for login verification)
- `_orm_to_user_profile(UserModel) → UserProfile`: Excludes `password_hash` (for API responses)

---

### 26.10 Phase 2 — Auth Utilities (Pure Functions)

**`core/auth/utils/passwords.py`:**

| Function | Purpose |
|----------|---------|
| `hash_password(password: str) → str` | PBKDF2-HMAC-SHA256 with random 16-byte salt. Returns `"{salt_hex}:{hash_hex}"` |
| `verify_password(password: str, stored_hash: str) → bool` | Constant-time comparison via `hmac.compare_digest()` |
| `DUMMY_HASH` | `"0" * 32 + ":" + "0" * 64` — used for login timing-oracle prevention (always verify even for non-existent users) |

**`core/auth/utils/tokens.py`:**

| Function | Purpose |
|----------|---------|
| `create_access_token(secret_key, user_id, company_slug, expires_hours=24) → str` | Payload: `{user_id, company_slug, exp}`. Format: `base64_payload.hmac_signature` |
| `create_stream_token(secret_key, user_id, company_slug, expires_minutes=5) → str` | Same format, adds `stream_only: true` flag. 5min TTL for SSE EventSource |
| `verify_token(secret_key, token) → Optional[Dict]` | Validates HMAC signature + expiration. Returns payload or None |
| `get_secret_key() → str` | `JWT_SECRET_KEY` env var → auto-generate in dev/test → `RuntimeError` in production |

**`core/auth/utils/domain.py`:**

| Function | Purpose |
|----------|---------|
| `normalize_domain(raw: str) → Tuple[str, Optional[str]]` | Strips protocol/www/path/port, handles multi-part TLDs (.co.uk, .com.au). Returns `(root_domain, subdomain_or_none)` |
| `derive_slug(name: str) → str` | Kebab-case from company name: `regex r"[^a-z0-9]+" → "-"` |
| `COMPANY_MUTABLE_FIELDS` | `frozenset({"name", "domain", "additional_domains"})` — prevents `**kwargs` overwriting immutable identity fields |
| `PRODUCT_MUTABLE_FIELDS` | `frozenset({"name", "domain", "description"})` |
| `USER_MUTABLE_FIELDS` | `frozenset({"role", "first_name", "last_name", "is_active"})` |

---

### 26.11 Phase 2 — Middleware Decoupling

**Before Phase 2:** The ASGI auth middleware imported `AuthStore` and called `store.verify_token()` directly. This coupled middleware to the JSON storage implementation.

**After Phase 2:** Middleware uses pure utilities + `app.state.secret_key`.

```python
# api/app.py lifespan — expose secret key for middleware
app.state.secret_key = get_secret_key()

# api/auth/middleware.py — uses verify_token utility directly
from core.auth.utils.tokens import verify_token

class AuthMiddleware:
    async def __call__(self, scope, receive, send):
        token = extract_token(scope)
        if token:
            payload = verify_token(scope["app"].state.secret_key, token)
            if payload:
                scope["state"]["user_id"] = payload["user_id"]
                scope["state"]["company_slug"] = payload["company_slug"]
```

**Why this matters:** Middleware runs for every request, including WebSocket upgrades and SSE streams. It must be lightweight and cannot depend on service-layer abstractions that require DI resolution.

**Router migration:** All 8 routers converted from `def → async def`, all `auth_store: AuthStore` parameters replaced with `auth_service: AuthServiceProtocol = Depends(get_auth_service)`, all calls `await`ed.

---

### 26.12 Phase 3 — Service Layer Migration: Three Data Protocols (D-SVC-1)

**Sprint:** `service-layer-phase3` · **Date:** 2026-02-28 · **Tests:** +46 (9 passed + 37 skipped) · **Files:** 16 new, 14 modified

Following the proven auth migration pattern, Phase 3 applies the same Protocol → JsonService → DbService pattern to all three data service domains. Each domain gets its own narrow protocol because they have different dependencies and different query patterns.

**Why three separate protocols (not one monolithic `DataServiceProtocol`):**
- Gap data needs `SignalRepository` + `PlatformRepository` — brand/content don't
- Brand data needs `PipelineRunRepository` — gap data uses it differently (via run resolution)
- Content data needs `ContentRepository` — gap/brand don't
- Narrow interfaces are more testable and less coupled

---

### 26.13 Phase 3 — GapDataServiceProtocol & Implementations

**`core/services/gap_data.py`:**

```python
@runtime_checkable
class GapDataServiceProtocol(Protocol):
    async def get_summary(self, effective_slug: str) -> GapSummaryResponse: ...
    async def get_queries(self, effective_slug: str, cluster=None, classification=None,
                         search=None, sort_by="gap_score", sort_dir="desc",
                         page=1, page_size=15) -> QueryListResponse: ...
    async def get_clusters(self, effective_slug: str) -> ClusterListResponse: ...
    async def get_signals(self, effective_slug: str) -> SignalAveragesResponse: ...
    async def get_platforms(self, effective_slug: str) -> PlatformListResponse: ...
    async def get_heatmap(self, effective_slug: str) -> HeatmapResponse: ...
    async def get_embedding_projection(self, effective_slug: str, method: str = "umap") -> EmbeddingProjectionResponse: ...
```

**`core/services/json_gap_data.py` — JsonGapDataService:**
- Wraps existing `api/services/gap_data_service.py` module-level functions via `asyncio.to_thread()`
- Preserves mtime-based caching (max 10 entries, FIFO eviction)
- Preserves Python-based computations (Pearson correlations, Jaccard similarity, signal averages)
- Zero behavior change from pre-migration

**`core/services/db_gap_data.py` — DbGapDataService:**
- Takes 4 repositories + `artifacts_root`:
  - `GapAnalysisRepository` — gap queries, classification counts, SPA results
  - `PipelineRunRepository` — run resolution (`effective_slug → run_id`)
  - `SignalRepository` — SQL aggregations on 45 structural signals
  - `PlatformRepository` — platform coverage analytics
  - `artifacts_root: Path` — embedding projections remain filesystem-backed

**Run Resolution Pattern (used by all Db services):**
```python
async def _resolve_run_id(self, effective_slug: str) -> UUID:
    """Convert effective_slug to run_id by finding the latest completed gap analysis run."""
    run = await self._pipeline_repo.get_latest_completed(effective_slug, PipelineType.gap_analysis)
    if run is None:
        raise HTTPException(404, f"No completed gap analysis for {effective_slug}")
    return run.id
```

**Key DbGapDataService methods:**

| Method | SQL Operations |
|--------|---------------|
| `get_summary` | Run resolution → SPA results + classification counts + cluster specs + centroid results + gap counts (all via SQL) → computed cluster performance |
| `get_queries` | Paginated `query_gaps` query with filter/sort/offset → eager-load exemplars via relationship |
| `get_signals` | `signal_repo.get_signal_averages(run_id)` → SQL `AVG(col)` for 45 signals. `signal_repo.get_signal_correlations(run_id)` → SQL `corr(signal, similarity)` for 15 key signals |
| `get_platforms` | `platform_repo.get_platform_summaries` → per-engine citation counts. `get_platform_url_sets` → URL sets for Jaccard computation (done in Python per Codex W4) |
| `get_embedding_projection` | **Delegates to filesystem** via `asyncio.to_thread()` — embedding projections are pre-computed Plotly HTML blobs |

---

### 26.14 Phase 3 — BrandDataServiceProtocol & ContentDataServiceProtocol

**`core/services/brand_data.py` — BrandDataServiceProtocol:**

```python
@runtime_checkable
class BrandDataServiceProtocol(Protocol):
    async def get_research_artifacts(self, slug: str) -> ResearchArtifactsResponse: ...
    async def get_run_history(self, slug: str, pipeline: Optional[str] = None,
                             status: Optional[str] = None, limit: int = 50) -> RunHistoryResponse: ...
```

- `JsonBrandDataService`: Wraps `api/services/brand_data_service.py` — reads artifact files from filesystem, queries TaskStore for run history
- `DbBrandDataService`: Uses `PipelineRunRepository.list_runs_by_slug()` for run history. Research artifact content still read from filesystem (artifacts are source of truth)

**`core/services/content_data.py` — ContentDataServiceProtocol:**

```python
@runtime_checkable
class ContentDataServiceProtocol(Protocol):
    async def get_briefs(self, effective_slug: str) -> BriefListResponse: ...
    async def get_brief_detail(self, effective_slug: str, brief_id: str) -> BriefDetailResponse: ...
    async def get_brief_stage_content(self, effective_slug: str, brief_id: str, stage: str) -> StageContentResponse: ...
```

- `JsonContentDataService`: Wraps `api/services/content_data_service.py` — reads `briefs.json`, `run_metadata.json`, and stage files from filesystem
- `DbContentDataService`: Uses `ContentRepository.list_pieces_by_run()` and `get_piece_detail()` for structured queries. Stage content (markdown files) still read from filesystem.

**Filesystem delegation pattern (applies to all Db services):**
Even when the DB is the primary data source, certain data remains filesystem-backed:
- Embedding projection HTML files (pre-rendered Plotly)
- Research artifact markdown files (company context, personas, style guides)
- Content stage files (outline.md, draft.md, enriched.md, formatted.md)

These are read via `asyncio.to_thread(Path.read_text)` in the Db service implementations.

---

### 26.15 Phase 3 — Signal & Platform Repositories (SQL Analytics)

These repositories replace Python-based computations that previously parsed 20MB+ JSON files on every request.

**`core/db/repositories/signal_repo.py` — SignalRepository:**

**`get_signal_averages(run_id: UUID) → dict[str, float]`:**
```sql
SELECT
    COALESCE(AVG(word_count), 0.0) as word_count,
    COALESCE(AVG(paragraph_count), 0.0) as paragraph_count,
    -- ... 45 signals total
    -- Boolean signals computed as rates:
    COALESCE(AVG(CASE WHEN has_faq_section THEN 1 ELSE 0 END), 0.0) as has_faq_section
FROM url_structural_signals uss
JOIN run_citations rc ON uss.url_enrichment_id = rc.url_enrichment_id
WHERE rc.run_id = :run_id
```
Returns a dict keyed by signal name with float values. `COALESCE/NULLIF` for NULL safety per Codex W2.

**`get_signal_correlations(run_id: UUID) → dict[str, float]`:**
```sql
SELECT
    COALESCE(corr(word_count, similarity), 0.0) as word_count,
    COALESCE(corr(reading_level, similarity), 0.0) as reading_level,
    -- ... 15 key signals
FROM url_structural_signals uss
JOIN run_citations rc ON uss.url_enrichment_id = rc.url_enrichment_id
JOIN run_paragraph_scores rps ON rps.citation_id = rc.id AND rps.rank = 1
WHERE rc.run_id = :run_id
```
Joins with `run_paragraph_scores` (rank=1 = best paragraph) to correlate structural signals with semantic similarity. Pearson correlation via SQL `corr()`.

**`get_cluster_patterns(run_id: UUID) → Sequence[dict]`:**
```sql
SELECT
    rq.cluster_name,
    COUNT(*) as total,
    SUM(CASE WHEN uss.has_faq_section THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as faq_rate,
    -- ... boolean pattern rates
FROM run_citations rc
JOIN run_queries rq ON rc.query_id = rq.query_id AND rc.run_id = rq.run_id
JOIN url_structural_signals uss ON uss.url_enrichment_id = rc.url_enrichment_id
WHERE rc.run_id = :run_id
GROUP BY rq.cluster_name
```

**`core/db/repositories/platform_repo.py` — PlatformRepository:**

**`get_platform_summaries(run_id: UUID) → Sequence[dict]`:**
```sql
SELECT engine, COUNT(*) as citation_count, COUNT(DISTINCT url) as unique_urls
FROM run_citations WHERE run_id = :run_id
GROUP BY engine
```

**`get_platform_url_sets(run_id: UUID) → dict[str, set[str]]`:**
Queries `DISTINCT (engine, url)` and groups into Python sets. Used downstream for **Jaccard similarity** computation in Python (not SQL). Per Codex W4: "Jaccard computation involves set operations that are fragile in SQL — keep it in Python where it's easily tested."

**`get_citation_exclusivity(run_id: UUID) → dict[str, int]`:**
```sql
WITH url_engine_counts AS (
    SELECT url, COUNT(DISTINCT engine) as engine_count
    FROM run_citations WHERE run_id = :run_id
    GROUP BY url
)
SELECT rc.engine, COUNT(*) as exclusive_count
FROM run_citations rc
JOIN url_engine_counts uec ON rc.url = uec.url
WHERE uec.engine_count = 1 AND rc.run_id = :run_id
GROUP BY rc.engine
```

---

### 26.16 Phase 3 — TaskStoreProtocol & DbTaskStore (D-TASKSTORE-1)

**Sprint:** `cleanup-taskstore-migration` · **Date:** 2026-02-28 · **Tests:** +49 · **Files:** 5 new, 7 migrated

**`core/services/task_store.py` — TaskStoreProtocol:**

```python
@runtime_checkable
class TaskStoreProtocol(Protocol):
    @property
    def semaphore(self) -> asyncio.Semaphore: ...

    # CRUD
    def create_task(self, pipeline: str, company_slug: str, product_slug: Optional[str] = None) -> PipelineTask: ...
    def get_task(self, task_id: str) -> PipelineTask: ...
    def update_task(self, task_id: str, **kwargs) -> PipelineTask: ...
    def list_tasks(self, pipeline=None, status=None, company_slug=None, product_slug=None) -> List[PipelineTask]: ...

    # Slug locks
    def acquire_slug_lock(self, slug: str) -> None: ...
    def release_slug_lock(self, slug: str) -> None: ...

    # Task handle tracking (for cancellation)
    def register_task_handle(self, task_id: str, handle: asyncio.Task) -> None: ...
    def cancel_task_handle(self, task_id: str) -> bool: ...
    def remove_task_handle(self, task_id: str) -> None: ...

    # HITL approval
    async def wait_for_approval(self, task_id: str, timeout: float = 86400) -> Dict: ...
    def submit_approval(self, task_id: str, decision: str, revision_note: Optional[str] = None, stage: Optional[str] = None) -> None: ...
```

Re-exports `TaskConflictError` and `TaskNotFoundError` for consumer convenience.

**`core/services/db_task_store.py` — DbTaskStore:**

**Architecture: Write-through in-memory cache with DB persistence.**

```
┌──────────────────────┐
│   In-Memory Cache     │  ← Fast sync reads (dict lookup)
│   _tasks: Dict        │
│   _slug_locks: Dict   │  ← Process-local (NOT persisted)
│   _approval_queues    │  ← Process-local (NOT persisted)
│   _task_handles       │  ← Process-local (NOT persisted)
│   semaphore           │  ← Process-local (NOT persisted)
└─────────┬────────────┘
          │ write-through
          ▼
┌──────────────────────┐
│   PostgreSQL          │  ← Durable state (survives restarts)
│   api_tasks table     │
│   JSONB: result,      │
│   approval_history    │
└──────────────────────┘
```

**Why write-through (not write-behind):**
- State transitions (`status`, `result`, `error`) are critical — must be durable immediately
- Non-critical updates (`progress_pct`) can be fire-and-forget
- Write-behind would lose state if the process crashes mid-pipeline (Codex CX-13 finding)

**`api_tasks` ORM Model (`core/db/models/api_tasks.py`):**

```python
class ApiTaskModel(Base):
    __tablename__ = "api_tasks"

    task_id:            Mapped[str]            = mapped_column(String, primary_key=True)
    company_slug:       Mapped[str]            = mapped_column(String, index=True)
    pipeline:           Mapped[str]            = mapped_column(String)
    status:             Mapped[str]            = mapped_column(String)  # Plain string, NOT PG enum
    effective_slug:     Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    product_slug:       Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    progress_pct:       Mapped[float]          = mapped_column(Float, default=0.0)
    result:             Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error:              Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    approval_payload:   Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    approval_history:   Mapped[list]           = mapped_column(JSONB, default=list)
    created_at:         Mapped[datetime]       = mapped_column(DateTime(timezone=True))
    updated_at:         Mapped[datetime]       = mapped_column(DateTime(timezone=True))
```

**Why plain String status (not PG enum):** `TaskStatus` includes values like `pending_approval` and `failed_restart` which are not part of the standard pipeline status enum. PG enums are immutable — adding new values requires `ALTER TYPE ... ADD VALUE` in a migration. Plain String avoids this friction.

**Startup Recovery:**
```python
async def recover_from_db(self) -> int:
    """Load non-terminal tasks, mark orphans as failed_restart."""
    # 1. Load all tasks from DB → self._tasks cache
    # 2. Find tasks with status 'running' or 'pending_approval' (orphaned)
    # 3. Mark orphans as status='failed_restart', updated_at=now()
    # 4. Return count of recovered orphans
```

**Session factory:** Per-operation (NOT request-scoped). DbTaskStore is a long-lived singleton, not tied to HTTP request lifecycles.

---

### 26.17 DI Wiring — How the Switch Works

**`api/dependencies.py`:**

```python
def get_auth_service(request: Request) -> AuthServiceProtocol:
    """Returns DbAuthService if DATABASE_URL, else JsonAuthService."""
    service = getattr(request.app.state, "auth_service", None)
    if service is not None:
        return service
    return JsonAuthService(request.app.state.auth_store)

def get_gap_data_service(request: Request) -> GapDataServiceProtocol:
    """Returns DbGapDataService if pre-built in lifespan, else JsonGapDataService."""
    service = getattr(request.app.state, "gap_data_service", None)
    if service is not None:
        return service
    return JsonGapDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )

def get_brand_data_service(request: Request) -> BrandDataServiceProtocol:
    service = getattr(request.app.state, "brand_data_service", None)
    if service is not None:
        return service
    return JsonBrandDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )

def get_content_data_service(request: Request) -> ContentDataServiceProtocol:
    service = getattr(request.app.state, "content_data_service", None)
    if service is not None:
        return service
    return JsonContentDataService(artifacts_root=request.app.state.artifacts_root)

def get_task_store(request: Request) -> TaskStoreProtocol:
    return request.app.state.task_store
```

**`api/app.py` lifespan (simplified):**

```python
async def lifespan(app: FastAPI):
    # Phase 1: Always initialize JSON-backed services
    app.state.auth_store = AuthStore(...)
    app.state.task_store = TaskStore(...)
    app.state.secret_key = get_secret_key()

    # Phase 2-3: Attempt DB services if DATABASE_URL is set
    if settings.database_url:
        try:
            session_factory = get_session_factory()
            app.state.db_session_factory = session_factory

            # Auth service (Phase 2)
            async with session_factory() as session:
                app.state.auth_service = DbAuthService(
                    CompanyRepository(session), AuthRepository(session), ...
                )

            # TaskStore (Phase 3)
            db_task_store = DbTaskStore(session_factory)
            recovered = await db_task_store.recover_from_db()
            app.state.task_store = db_task_store

            # Data services (Phase 3)
            app.state.gap_data_service = DbGapDataService(...)
            app.state.brand_data_service = DbBrandDataService(...)
            app.state.content_data_service = DbContentDataService(...)
        except Exception:
            logger.warning("DB init failed — falling back to JSON services")

    yield  # App is running

    # Cleanup
```

**The switch is transparent to routers.** Routers receive a protocol-typed service via `Depends()` and call methods on it. They never know whether they're talking to JSON or DB.

---

### 26.18 Backfill Script (JSON to DB Migration)

**`scripts/backfill_gap_data.py`:**

Migrates existing JSON gap analysis artifacts to the database for testing with real data without implementing Phase 4 pipeline write hooks.

```bash
python scripts/backfill_gap_data.py --company-slug ramp [--product-slug corporate-card] [--dry-run]
```

**Logic:**
1. Find latest completed gap analysis directory for `{effective_slug}`
2. Load `gap_analysis_complete.json` (or fall back to `analysis.json` + `gap_report.json`)
3. Parse queries, citations, structural signals, gaps, cluster specs, SPA results
4. Insert into DB respecting FK ordering: `pipeline_runs` → `run_queries` → `run_citations` + `url_structural_signals` → `query_gaps` + `query_exemplars` + `cluster_specs` + `spa_results` + `centroid_results`
5. **Idempotent:** Checks existing rows by composite key before inserting. Safe to re-run.
6. `--dry-run` flag: Prints what would be inserted without executing

---

### 26.19 Cross-Cutting Patterns

**Pattern 1: The Service Protocol Pattern**

```python
# 1. Define protocol (runtime_checkable for isinstance checks in tests)
@runtime_checkable
class SomeServiceProtocol(Protocol):
    async def method1(self, ...) -> ReturnType: ...

# 2. JSON implementation (wraps existing code, backward compat)
class JsonSomeService:
    async def method1(self, ...):
        return await asyncio.to_thread(existing_module.method1, ...)

# 3. DB implementation (uses SQL repos)
class DbSomeService:
    def __init__(self, repo: SomeRepository, ...): ...
    async def method1(self, ...):
        return await self._repo.method1(...)

# 4. DI switch (transparent to consumers)
def get_some_service(request: Request) -> SomeServiceProtocol:
    return getattr(request.app.state, "some_service", None) or JsonSomeService(...)
```

**Applied identically 5 times:** Auth, Gap Data, Brand Data, Content Data, TaskStore.

**Pattern 2: Run Resolution**

All Db data services resolve `effective_slug → run_id` before querying:
```python
run = await self._pipeline_repo.get_latest_completed(effective_slug, pipeline_type)
```
This finds the most recent completed pipeline run for a given company/product slug. If none exists, returns 404.

**Pattern 3: Filesystem Delegation in Db Services**

Even in DB mode, certain data remains filesystem-backed:
```python
# DbGapDataService.get_embedding_projection()
projection_path = self._artifacts_root / "gap_analysis" / effective_slug / "visualizations" / f"{method}_projection.html"
content = await asyncio.to_thread(projection_path.read_text)
```
This ensures large blobs (HTML visualizations, markdown artifacts, content stage files) stay on fast filesystem I/O rather than being stored as Postgres LOBs.

**Pattern 4: Effective Slug**

```
Company level:    "{company_slug}"                  → "ramp"
Product level:    "{company_slug}__{product_slug}"  → "ramp__corporate-card"
```

Used consistently across artifact directories, lock keys, pipeline run records, and all service methods. Double-underscore separator is unambiguous since individual slugs use `[a-z0-9-]` only.

---

### 26.20 Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Routers (all async def)                      │
│    auth · companies · gap_data · content_data · brand_data             │
│    settings · knowledge_docs · tasks · events · artifacts              │
│    gap_analysis · research · content                                   │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ Depends()
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│              DI Functions (api/dependencies.py)                         │
│                                                                        │
│  get_auth_service() ─────→ AuthServiceProtocol                         │
│  get_gap_data_service() ─→ GapDataServiceProtocol                      │
│  get_brand_data_service()→ BrandDataServiceProtocol                    │
│  get_content_data_service()→ContentDataServiceProtocol                 │
│  get_task_store() ───────→ TaskStoreProtocol                           │
│                                                                        │
│  Switch: if app.state.{service} exists → return it (DB)                │
│          else → construct Json*Service (filesystem fallback)           │
└──────────────┬──────────────────────────────┬──────────────────────────┘
               │                              │
    ┌──────────▼──────────┐        ┌──────────▼──────────┐
    │   Json Services      │        │   Db Services        │
    │   (Default)          │        │   (Opt-in)           │
    ├──────────────────────┤        ├──────────────────────┤
    │ JsonAuthService      │        │ DbAuthService        │
    │ JsonGapDataService   │        │ DbGapDataService     │
    │ JsonBrandDataService │        │ DbBrandDataService   │
    │ JsonContentDataSvc   │        │ DbContentDataService │
    │ TaskStore (JSON)     │        │ DbTaskStore          │
    └─────────┬────────────┘        └─────────┬────────────┘
              │                               │
              │ asyncio.to_thread()            │ async session
              ▼                               ▼
    ┌──────────────────┐          ┌────────────────────────┐
    │ Filesystem        │          │ 16 Repositories         │
    │ (api/services/,   │          ├────────────────────────┤
    │  api/auth/store,  │          │ CompanyRepository       │
    │  artifacts/)      │          │ AuthRepository          │
    └──────────────────┘          │ ProductRepository       │
                                  │ InviteRepository        │
                                  │ PipelineDefaultsRepo    │
                                  │ PipelineRunRepository   │
                                  │ GapAnalysisRepository   │
                                  │ ContentRepository       │
                                  │ EmbeddingRepository     │
                                  │ CacheRepository         │
                                  │ SignalRepository        │
                                  │ PlatformRepository      │
                                  │ TaskRepository          │
                                  │ KnowledgeDocRepository  │
                                  │ TrackingRepository      │
                                  │ SiteAuditRepository     │
                                  └───────────┬────────────┘
                                              │ flush-only
                                              ▼
                                  ┌────────────────────────┐
                                  │ PostgreSQL + pgvector    │
                                  │ 31 tables · 12 enums    │
                                  │ 4 Alembic migrations     │
                                  │ HNSW vector indexes      │
                                  └────────────────────────┘
```

---

### 26.21 Testing Strategy

**Phase 1 Tests (44):**
- Located in `tests/db/` — auto-skip without `TEST_DATABASE_URL`
- Savepoint-based isolation: each test wraps in a transaction that rolls back
- `after_transaction_end` listener restarts nested transaction for proper isolation
- Tests cover: model creation, repo CRUD, composite FK ordering, migration schema verification

**Phase 2 Tests (96):**
- Auth utility unit tests: password hashing, token creation/verification, domain normalization
- JsonAuthService tests: verify all protocol methods via wrapped AuthStore
- DbAuthService tests: full integration with DB (auto-skip without `TEST_DATABASE_URL`)
- Router async migration tests: verify all endpoints return correct responses after sync→async conversion

**Phase 3 Tests (46 = 9 passed + 37 skipped):**
- **Protocol conformance tests (9, always pass):** Verify both Json and Db implementations satisfy `isinstance(service, SomeServiceProtocol)` — catches interface drift
- **DB service tests (37, auto-skip):** Signal repo aggregations, platform repo analytics, gap data service end-to-end, TaskStore write-through + recovery

**Phase 3 TaskStore Tests (49):**
- DbTaskStore CRUD: create, update, list, get
- Write-through verification: changes appear in DB after sync update
- Orphan recovery: running/pending_approval tasks marked as `failed_restart` on startup
- Slug lock isolation: concurrent creates for same slug fail correctly
- Approval flow: wait_for_approval + submit_approval round-trip

**Test fixture pattern:**
```python
# Each tests/db/ file needs its own pytestmark (conftest pytestmark doesn't propagate)
pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Requires TEST_DATABASE_URL"
)
```

**Backward compatibility guarantee:**
All 1127 existing tests (non-DB) pass unchanged — they use JSON-backed services via `dependency_overrides` in conftest.py.

---

### 26.22 Files Changed Summary

| Phase | New Files | Modified Files | Key Additions |
|-------|-----------|----------------|---------------|
| **Phase 1** | 44 | 3 | 31 ORM models, 8 repos, 2 migrations, engine factory, base classes, enums, 44 tests |
| **Phase 2** | 18 | 32 | AuthServiceProtocol, 2 service implementations, 3 utility modules, 3 new repos, middleware decoupled, 8 routers async, 96 tests |
| **Phase 3 (Services)** | 16 | 14 | 3 protocols, 6 service implementations, 2 new repos (signal, platform), 3 enhanced repos, backfill script, 46 tests |
| **Phase 3 (TaskStore)** | 5 | 7 | TaskStoreProtocol, DbTaskStore, ApiTaskModel ORM, TaskRepository, migration 0004, 49 tests |
| **Total** | **83** | **56** | **235 new tests** |

---

### 26.23 Deferred Items

| Item | Description | Why Deferred |
|------|-------------|-------------|
| Phase 4 — Pipeline Write Hooks | Populate DB tables during pipeline execution (s1-s8 write to DB as they run) | Requires modifying each pipeline step — separate sprint |
| Multi-Instance Scaling | Redis pub/sub or PG LISTEN/NOTIFY for SSE events, task cancellation, approval queues across workers | Process-local primitives (semaphore, slug_locks, queues) are sufficient for single-instance |
| API Key Encryption (Phase 1D) | Encrypted per-company API keys in DB | Pre-YC — running on our own keys |
| Content-Gap Integration | Gap analysis auto-refreshes when new content is published | Complex cross-pipeline coordination — design preserved in `.claude/plans/cozy-twirling-mochi.md` |
| CHECK Constraints | DB-level validation on numeric fields (word_count >= 0, similarity 0-1) | Codex recommendation — low risk without them since Pydantic validates at app level |
| Unit-of-Work Abstraction | Formalize the session commit pattern across multi-repo operations | Codex architectural recommendation — current pattern works but isn't explicitly named |
| PB-28/29: Stream Token Hardening | Single-use + task-scoped stream tokens | v0 5-min TTL is acceptable |

---

## Appendix A: Model & API Key Matrix

| Component | Model | API Key Variable | Default Model |
|-----------|-------|------------------|---------------|
| KB Agents (Perplexity) | Sonar | `PERPLEXITY_API_KEY` | `sonar-deep-research` |
| KB Brand Perception | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| KB Synthesis | Gemini | `GOOGLE_API_KEY` | `gemini-3-flash-preview` |
| AP Agent 1 (Suggester) | Gemini | `GOOGLE_API_KEY_AUDIENCE_PERSONA` | `gemini-3-flash-preview` |
| AP Agent 2 (Generator) | Perplexity | `PERPLEXITY_API_KEY` | `sonar-deep-research` |
| VSG Agents | Gemini/Perplexity/Claude | Various | `gemini-3-flash-preview` / `sonar-deep-research` / `claude-sonnet-4-5-20250929` |
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
| Content Engine: Tracing | LangSmith | `LANGSMITH_API_KEY` | — |
| Knowledge Base: 4 Perplexity Agents | Sonar | `PERPLEXITY_API_KEY` | `sonar-deep-research` |
| Knowledge Base: Brand Perception | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` (with web_search tool) |
| Knowledge Base: Synthesis | Gemini | `GOOGLE_API_KEY` | `gemini-3-flash-preview` (LangGraph react agent) |

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

### Research Pipeline Patterns (KB / AP / VSG)
- Raw SDK clients for all LLM calls (no DeepAgents or LangChain wrappers)
- Each pipeline has its own Storage class (`KBStorage`, `PersonaStorage`, `VSGStorage`) with versioned docs + manifests
- LangGraph mini-graphs for HITL pause/resume within each pipeline
- `auto_approve` flag to skip HITL interrupts in CLI scripts

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
from core.models.personas import PersonaResearchInput, PersonaArtifact
from core.research.knowledge_base.pipeline import run_kb_pipeline
from core.research.audience_persona.pipeline import run_ap_pipeline
from core.research.voice_style_guide.pipeline import run_vsg_pipeline
from core.gap_analysis.pipeline import run_gap_analysis
from core.shared_tools.embedding_client import embed_texts
from core.shared_tools.vector_store import upsert_embeddings
from core.content_engine.pipeline import run_content_generation
from core.models.content_generation import ContentGenerationInput, ContentBrief, FormattedContent
```

---

## 22. Front-Back Integration Sprint — Exhaustive 4-Phase Detail

> **Sprint:** `front-back-integration` | **Branch:** `feat/front-back` | **Duration:** 2026-02-25 to 2026-02-26
> **Goal:** Complete all backend data retrieval endpoints required by the frontend dashboard — eliminate ~2,100 lines of hardcoded fixture data across 4 mock files.
> **Final result:** 16 new GET endpoints, 50+ Pydantic response models, 3 service modules, 766 tests passing.

### 22.1 Sprint Context

The frontend dashboard (Next.js 15, 26 routes) was fully built with sophisticated UI but consumed hardcoded fixture data. The backend had 17 working endpoints covering pipeline **execution** (start/monitor/approve) but lacked **data retrieval** endpoints for viewing results, metrics, and analytics. This sprint bridges the two.

**Key constraints from Aryan:**
1. Company → Product → Employee data model (each employee belongs to one company)
2. No Supabase/database — filesystem artifacts are source of truth
3. Frontend renders its own charts from raw JSON (not iframes)
4. Pre-compute UMAP/t-SNE projections in s7 as JSON for fast reads
5. Fix frontend types to match backend (not the other way around)
6. Company-level endpoints only for now (product-level deferred)
7. All Pydantic fields must have defaults (backward compat with existing JSON artifacts)
8. Password min_length=8, max_length=128 enforced in API request models

**Dependency graph:**
```
Phase 1 (Foundation) ──┬──→ Phase 2 (Gap Data) ──→ Phase 3 (Content + Embeddings)
                       └──→ Phase 4 (Brand + History)
```

### 22.2 Phase 1 — Foundation (2026-02-25, 423 tests)

**Goal:** Core data models, company-scoped endpoint, auth skeleton, fix API mismatches with frontend types.

#### Data Model Decisions

**Company model (`core/models/organization.py`):**
```python
class Company(BaseModel):
    id: str = ""                           # UUID4, generated on creation
    slug: str = ""                         # kebab-case, used for artifact directories
    name: str = ""                         # Display name
    domain: str = ""                       # Primary root domain (normalized)
    additional_domains: List[str] = []     # Subdomains from registration
    products: List[Product] = []           # Company products (populated later)
    created_at: datetime                   # Auto-set
    updated_at: datetime                   # Auto-set

class UserProfile(BaseModel):
    id: str = ""                           # UUID4
    company_id: str = ""                   # FK → Company.id
    email: str = ""
    first_name: str = ""                   # Split from single name field (D-FB-1)
    last_name: str = ""
    role: str = "member"                   # "superuser" | "member" | "viewer"
    is_active: bool = True
```

**Why `first_name`/`last_name` instead of `name`:** Standard for user profiles, enables personalized UI ("Hi Aryan" vs "Hi Aryan Keshri"), matches SaaS conventions. Decision D-FB-1.

#### Auth Architecture (pre-Supabase)

**AuthStore (`api/auth/store.py`):**
- JSON-file persistence: `artifacts/_auth/companies.json`, `artifacts/_auth/users.json`
- Password hashing: PBKDF2-HMAC-SHA256 with 260,000 iterations (not bcrypt — avoids C dependency, PBKDF2 is sufficient for v0)
- Token format: HMAC-SHA256 signed, base64-encoded payload `{user_id}:{company_slug}:{expires_timestamp}`
- `JWT_SECRET_KEY` env var — **required** in non-dev/test environments (`RuntimeError` on startup if missing, Codex W8). Auto-generated in dev/test.
- Thread-safe: `threading.RLock` on all mutating methods, atomic file writes via temp + `os.replace()`
- Mutable field allowlists: `_COMPANY_MUTABLE_FIELDS`, `_PRODUCT_MUTABLE_FIELDS` prevent overwriting immutable fields (id, slug, created_at) via update methods

**Registration flow (hardened — Codex C1):**
1. Check for duplicate email → `ValueError("already exists")` if found
2. `normalize_domain(company_domain)` → strips protocol/www/path/port, handles multi-part TLDs (frozenset of 15)
3. Lookup existing company by root domain
4. If match: `ValueError("domain_taken")` → 409 with invite message (no auto-join)
5. If no match: create company + user as `superuser`
6. Generate token, return user + company data

**Invite flow (Codex C1):**
1. Superuser calls `POST /auth/invite` → `create_invite(company_slug, role="member")` → 16-char hex code
2. New user calls `POST /auth/join` with invite code + user details
3. `redeem_invite()` validates code, creates user in the company with the invite's role
4. Invite code is consumed (single-use) — `ValueError("Invalid or expired")` on re-use

**AuthMiddleware (`api/auth/middleware.py`) — Pure ASGI, Default-Deny:**
- **Pure ASGI** implementation (not `BaseHTTPMiddleware`) — safe for SSE streaming (Codex W1)
- **Default-deny** posture: unauthenticated requests to protected routes get 401 JSON immediately
- Public path whitelist: `/health`, `/readiness`, `/docs*`, `/redoc*`, `/openapi.json`, `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/join`
- Token extraction: `Authorization: Bearer {token}` header, or `?stream_token={token}` query param for SSE endpoints
- Stream token validation: tokens with `stream_only: true` rejected for non-SSE endpoints
- Sets `scope["state"]["user_id"]` and `scope["state"]["company_slug"]` on valid auth

**Auth Dependencies (`api/auth/dependencies.py`):**
- `require_auth` → full UserProfile lookup + `is_active` check
- `require_role(*roles)` → factory, calls `require_auth` first, then role check
- `require_tenant(slug)` → lightweight slug comparison (no store lookup)
- `require_company_access(slug)` → store-based tenant check (`user.company_id == company.id`)
- `require_company_member(slug)` → combined role (member/superuser) + store-based tenant check

**Route Protection Summary:**
| Route Category | Auth Level |
|---|---|
| Health, docs, register, login, join | Public (no auth) |
| Company profile, data endpoints, artifacts | `require_auth` + `require_tenant` |
| Pipeline /start, /approve | `require_role("member", "superuser")` + tenant validation |
| Task cancel, stream-token | `require_auth` + task ownership check |
| Invite creation | `require_role("superuser")` |
| Product CRUD | `require_role("member", "superuser")` + company access check |

#### Frontend Type Alignment

Fixed 6 frontend type files to match backend:
- Flattened `GapAnalysisStartInput` (removed nested `input_data`)
- Renamed `style` → `style_guide` in research types
- Added `gap_slug`, `max_concurrent_workers`, `max_revision_cycles`, `skip_stages` to `ContentStartRequest`
- Added `total` field to task list response

#### Files Created/Modified
- **Created:** `core/models/organization.py`, `api/auth/` package (4 files), `api/routers/auth.py`, `api/routers/companies.py`, `api/schemas/company.py`
- **Modified:** `api/app.py`, `api/schemas/common.py`, `api/routers/tasks.py`, `api/tasks/store.py`, `api/routers/content.py`, `api/dependencies.py`, 6 frontend files
- **Tests:** 62 new tests across `test_companies.py`, `test_auth_store.py`, `test_tasks_extended.py`, `test_registration.py`

### 22.3 Phase 2 — Gap Analysis Data Endpoints (2026-02-25, 484 tests)

**Goal:** 6 GET endpoints serving pre-computed gap analysis artifacts for the Signal Analysis dashboard.

#### Data Flow: Pipeline Artifacts → Service Layer → Response Models → Frontend

```
artifacts/gap_analysis/{slug}/
├── gap_analysis_complete.json  ──→  gap_data_service.py  ──→  GapSummaryResponse      ──→ Overview tab
│   (or analysis.json + gap_report.json for old format)       QueryListResponse        ──→ Query Intel tab
│                                                              ClusterListResponse      ──→ Content Briefs tab
│                                                              HeatmapResponse          ──→ Heatmap tab
├── enriched_citations.json     ──→  gap_data_service.py  ──→  SignalAveragesResponse   ──→ Structural Signals tab
└── platform_results/*.jsonl    ──→  gap_data_service.py  ──→  PlatformListResponse     ──→ Platform Intel tab
```

#### Backward Compatibility Strategy

Two artifact formats exist:
1. **New format** (`gap_analysis_complete.json`): Combined file with all SPA results, query gaps, cluster specs, content briefs. Used by Carta, Mynd.
2. **Old format** (`analysis.json` + `gap_report.json` + `generation_spec.json`): Separate files with 11 structural signals (not 45). Used by Ramp.

Detection: try `gap_analysis_complete.json` first, fallback to separate files. Old format maps 11 legacy signal names to new schema. Test suite covers both formats.

#### Service Layer Design — `api/services/gap_data_service.py`

**Caching pattern:**
```python
_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}  # (slug, "data"|"citations") → (mtime_ns, parsed_json)
_CACHE_MAX_ENTRIES = 10
```
File mtime checked before serving cached data. If mtime changed → re-read from disk. FIFO eviction when cache is full.

**Key computation functions:**
- `_pearson(x_vals, y_vals)`: Pearson correlation with `product <= 0` guard for floating-point imprecision (F7 fix)
- `_jaccard(set_a, set_b)`: Set intersection / union for domain agreement matrix
- `_signal_averages()`: Iterates enriched citations, groups ~45 structural signals by category (formatting, structural, authority, content), computes per-signal averages
- `_signal_correlations()`: Pearson correlation of each structural signal against citation similarity — ranks by absolute correlation to identify most impactful signals
- `_cluster_patterns()`: Per-cluster content pattern adoption rates (FAQ, definition_opening, key_takeaways, etc.) from enriched citation structural signals

**Platform engine name mapping:**
```python
_ENGINE_MAP = {"openai": "chatgpt", "claude": "claude", "gemini": "gemini", "perplexity": "perplexity"}
```
Frontend uses lowercase keys. Backend stores engine names as-is from pipeline.

#### Response Models — 20+ Pydantic models in `api/schemas/gap_data.py`

All fields have defaults. Models directly match frontend TypeScript interfaces in `frontend-dashboard/src/types/gap-analysis.ts`.

#### Files Created/Modified
- **Created:** `api/routers/gap_data.py`, `api/schemas/gap_data.py`, `api/services/gap_data_service.py`, `tests/api/test_gap_data.py`
- **Modified:** `api/app.py` (router registration), `api/dependencies.py` (get_artifacts_root)
- **Tests:** 61 new tests covering all 6 endpoints + slug validation + old/new format compat

### 22.4 Code Review C1-C4 Fixes (2026-02-25, 500 tests)

Between Phase 2 and Phase 3, a comprehensive code review identified 27 issues. 4 critical issues were fixed immediately; 23 were deferred.

| Fix | Issue | Change |
|-----|-------|--------|
| C1 | Missing login/me endpoints | Added `POST /login` and `GET /me` to auth router |
| C2 | AuthMiddleware not registered | Added to middleware stack between RequestLogging and CORS |
| C3 | No email/password validation | Added `EmailStr` (requires `email-validator`), `Field(min_length=8, max_length=128)` on passwords |
| C4 | Auth data not gitignored | Added `artifacts/_auth/` and `artifacts/_jobs/` to `.gitignore` |

C3 fix broke 25 existing tests (short passwords in fixtures) — all updated to meet 8-char minimum. Only API-level tests affected; store-level tests bypass API validation (F8 failure logged).

### 22.5 Phase 3 — Content Briefs + Embedding Projections (2026-02-25, 585 tests)

**Goal:** 4 GET endpoints for content pipeline data + 2D embedding projections for scatter plots.

#### Data Flow: Content Artifacts → Service Layer → Response Models → Frontend

```
artifacts/content/{slug}/
├── briefs.json                           ──→  ContentBriefListResponse    ──→ Content Pipeline board
├── run_metadata.json (pieces array)      ──→  (status inference phase 1)
└── content/brief-{N}/                    ──→  ContentBriefDetailResponse  ──→ Brief detail view
    ├── outline.json                      ──→  StageContentResponse       ──→ Stage content
    ├── draft.md                          ──→  StageContentResponse
    ├── enriched.md                       ──→  StageContentResponse
    ├── formatted.md                      ──→  StageContentResponse
    └── eval_history.json                 ──→  (citability score, eval cycles)

artifacts/gap_analysis/{slug}/
└── visualizations/
    ├── embedding_projections_umap.json   ──→  EmbeddingProjectionResponse ──→ Embedding Lab
    └── embedding_projections_tsne.json   ──→  EmbeddingProjectionResponse
```

#### Status Inference — The Most Complex Logic

Content brief status is inferred through a 2-phase process because briefs go through multiple stages:

**Phase 1 — Authoritative (post-HITL):** Check `run_metadata.json` → `pieces` array. Each piece has a `status` field set by the HITL approval flow: `approved`, `rejected`, `edit`. This is the ground truth after human review.

**Phase 2 — File-based fallback:** If no `run_metadata.json` or brief not in `pieces` array, scan the brief directory:
1. `eval_history.json` exists with `final_passed=True` → status `review` (awaiting human review)
2. `eval_history.json` exists with `final_passed=False` → status `evaluating` (still in eval-optimize loop)
3. `formatted.md` exists → status `formatting`
4. `draft.md` exists → status `drafting`
5. `outline.json` exists → status `outlining`
6. Nothing → status `suggested`

**Key design choice:** `approved` is kept distinct from `published` — frontend has separate board columns for these states.

#### Pipeline Change — s7_visualize.py

Added JSON export of 2D embedding projections alongside existing HTML Plotly plots:
- `_save_embedding_projections(coords, metadata, output_path)`: saves `embedding_projections_{method}.json`
- Coordinates computed once, reused for both HTML plot generation and JSON export — prevents coordinate drift between the interactive visualization and the API data
- New functions: `_plot_typed_from_coords()`, `_plot_clustered_from_coords()` accept pre-computed coordinates
- 12 new tests in `tests/gap_analysis/steps/test_s7_projections.py`

#### content_format → content_type Mapping

Backend uses `ContentBrief.content_format` (from planner). Frontend expects a different vocabulary:
```python
_FORMAT_MAP = {
    "long_form_article": "blog", "comparison_guide": "comparison",
    "how_to_guide": "how-to", "listicle": "listicle",
    "case_study": "case-study", "whitepaper": "whitepaper",
    "thought_leadership": "thought-leadership",
}
```

#### Files Created/Modified
- **Created:** `api/routers/content_data.py`, `api/schemas/content_data.py`, `api/services/content_data_service.py`, `tests/api/test_content_data.py`, `tests/gap_analysis/steps/test_s7_projections.py`
- **Modified:** `api/services/gap_data_service.py` (added `get_embedding_projection()`), `api/routers/gap_data.py` (added `/embeddings`), `api/app.py`, `core/gap_analysis/steps/s7_visualize.py`
- **Tests:** 73 API tests + 12 s7 projection tests = 85 new

### 22.6 Phase 4 — Brand Brain + Run History (2026-02-26, 766 tests)

**Goal:** 3 endpoints for Brand Brain research viewer, run history, and SPA trend chart.

#### Data Flow: Mixed Sources → Service Layer → Response Models → Frontend

```
TaskStore (in-memory + JSON files)
├── list_tasks(company_slug=slug)         ──→  RunHistoryResponse       ──→ Run History tab
└── list_tasks(pipeline="gap_analysis",   ──→  SPATrendResponse         ──→ Command Center trend
         status="completed")

artifacts/
├── company_context/{slug}.md             ──→  ResearchArtifactsResponse ──→ Brand Brain viewer
├── personas/{slug}__persona-*.md         ──→  (personas array)
└── style_guides/{slug}.md                ──→  (style_guide artifact)
```

#### Status Mapping — Backend 6 → Frontend 3

The frontend expects only 3 status values. The service maps:
```python
_STATUS_MAP = {
    "running": "running",
    "pending_approval": "running",        # Still in-progress from frontend perspective
    "completed": "completed",
    "failed": "failed",
    "cancelled": "failed",               # Terminal failure states grouped
    "failed_restart": "failed",
}
```

**Critical detail:** Status filtering operates on mapped values, not raw values. So `?status=running` returns both `running` AND `pending_approval` tasks. This was Codex finding #1 (HIGH) — the original implementation filtered on raw status before mapping.

#### Persona File Matching — Codex CX-4 Hardening

Original implementation matched `{slug}__*.md` — too broad. Could match `webflow__notes.md` as a persona.

Fixed to only match `{slug}__persona-*.md`:
```python
suffix = f.name[len(prefix):]  # e.g., "persona-icp.md" or "notes.md"
if not suffix.startswith("persona-"):
    continue  # Skip non-persona files
```

#### Duration Computation

For terminal tasks (completed/failed/cancelled/failed_restart):
```python
delta = updated_at - created_at
hours = total_seconds // 3600
minutes = (total_seconds % 3600) // 60
# "3h 46m", "23m", "<1m", or "" for running
```

**Test challenge:** `TaskStore.update_task()` auto-sets `updated_at = datetime.now(timezone.utc)` AFTER applying kwargs. Tests must patch timestamps directly on the stored task object AFTER calling `update_task()`:
```python
stored = task_store._tasks[task.task_id]
stored.created_at = custom_created_at
stored.updated_at = custom_updated_at
```

#### Gap Metrics Extraction from TaskStore

Run history for gap_analysis tasks extracts metrics from `task.result`:
```
task.result["report_json"]["spa_results"][0]["t_stat"]              → spa_score
task.result["report_json"]["decision_metrics"]["total_queries"]     → queries
task.result["report_json"]["decision_metrics"]["total_citations"]   → citations
task.result["report_json"]["spa_results"][0]["mean_citation_similarity"] - ["mean_company_similarity"] → citation_advantage
```

All numeric extraction uses `_safe_float()` which returns 0.0 for NaN/Inf/None/non-numeric values.

#### Codex Reviews

**Plan review (gpt-5.3-codex):** 11 findings, 2 incorporated:
- INCORPORATE: Status mapping (backend→frontend) — adopted in `_STATUS_MAP`
- INCORPORATE: `limit` query parameter for run history — added with `ge=1, le=200, default=50`

**Code review (gpt-5.3-codex):** 6 findings, 3 incorporated:
1. (HIGH) Status filter inconsistency → Fixed: filter on mapped values
2. (MEDIUM) Steps inference mismatch → Deferred (gap runner doesn't set current_step during execution)
3. (HIGH/Security) Unauthenticated endpoints → Deferred (auth grace mode by design)
4. (MEDIUM) Persona file matching too broad → Fixed: `persona-` prefix check
5. (MEDIUM/Security) Symlink traversal → Deferred (server-controlled artifacts)
6. (LOW) Test gaps for mapped-status filter → Fixed: 3 new tests added

#### Files Created/Modified
- **Created:** `api/schemas/brand_data.py`, `api/services/brand_data_service.py`, `api/routers/brand_data.py`, `tests/api/test_brand_data.py`
- **Modified:** `api/routers/gap_data.py` (added `/trend`), `api/app.py` (registered brand_data router)
- **Tests:** 57 TDD tests

### 22.7 Sprint Architecture — How the 4 Phases Connect

**Shared infrastructure (from Phase 1 → used by all phases):**
- `api/dependencies.py`: `get_artifacts_root()`, `get_task_store()`, `get_auth_store()` — DI providers used across all routers
- `_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")` — slug validation regex, duplicated in each service (not extracted to shared utility — I3 deferred issue)
- Company model defines the entity that all data endpoints are scoped to

**Service layer pattern (Phases 2-4):**
All three service modules (`gap_data_service.py`, `content_data_service.py`, `brand_data_service.py`) follow the same architecture:
1. Module-level `_CACHE` dict with `(slug, key)` → `(mtime_ns, data)` entries
2. FIFO eviction at 10 entries (not LRU — I7 deferred issue)
3. Slug validation via regex + `HTTPException(400)`
4. Path traversal protection via `Path.is_relative_to()` (not `str.startswith()`)
5. Return empty/default data for missing artifacts (graceful degradation)
6. No async — sync functions run in FastAPI's thread pool

**Response model pattern (all phases):**
- All fields have defaults (backward compat with existing JSON artifacts)
- Models in `api/schemas/` directly mirror frontend TypeScript interfaces
- `Field(default_factory=list)` for list fields, `Field(default_factory=ModelName)` for nested models
- Optional fields use `Optional[T] = None`

**URL routing pattern:**
- Pipeline execution: `/api/v1/{pipeline}/start`, `/{pipeline}/{run_id}/status` (existing, flat)
- Data retrieval: `/api/v1/companies/{slug}/{domain}/...` (new, company-scoped)
- Gap data: `/api/v1/companies/{slug}/gap-analysis/` (8 endpoints on gap_data router)
- Content data: `/api/v1/companies/{slug}/content/` (3 endpoints on content_data router)
- Brand data: `/api/v1/companies/{slug}/` (2 endpoints on brand_data router)
- SPA trend: `/api/v1/companies/{slug}/gap-analysis/trend` (on gap_data router, logic in brand_data_service)

**Why SPA trend lives on gap_data router but uses brand_data_service:**
The `/trend` endpoint is semantically gap-analysis data (SPA scores over time) so the URL prefix `/gap-analysis/` is correct. But the data source is `TaskStore` (not filesystem artifacts), and the computation logic is in `brand_data_service.py` alongside other TaskStore-based functions. This avoids coupling `gap_data_service.py` (file-based) to `TaskStore` (in-memory).

### 22.8 What's Next

With all 4 phases complete, the backend is ready for the frontend to consume:

1. **Wire frontend to live endpoints** — Replace ~2,100 lines of fixture data with API calls
2. **Fix deferred issues** — 23 issues tracked in `.claude/sprints/v1/review-findings-deferred.md` (C5-C7, W1-W9, I1-I8, CX-1 through CX-10)
3. **Supabase migration** — Replace JSON AuthStore with Supabase Auth, migrate task persistence to PostgreSQL
4. ~~**Product-level endpoints** — Model supports it (Company → Products), execution deferred~~ → **COMPLETE** (see §23)
5. **Incremental embedding update** — After content approval, update gap analysis embeddings without full re-run

---

## 23. Product-Level Pipeline Execution Sprint — Exhaustive 5-Phase Detail

### 23.1 Sprint Context

**Branch:** `feat/front-back` (continued from front-back sprint)
**Tests:** 882 total (114 new, up from 768)
**Goal:** Each product (e.g., Ramp Corporate Card, Ramp Travel, Ramp Reimbursements) can run its own independent pipeline with product-specific artifact directories, lock keys, and LLM prompt context. Company-level runs are entirely unaffected.

**The core problem:** Platform currently runs all pipelines at company level — one run per company, artifacts at `artifacts/gap_analysis/{company_slug}/`. Ramp has multiple distinct products that compete in different AI-search citation contexts. Product-specific queries + product-specific context = better citation gap analysis per product.

**Pre-implementation review:** Codex gpt-5.3-codex reviewed the plan (high reasoning). 6 CRITICAL + 7 WARNING + 4 INFO findings — all CRITICAL and WARNING findings incorporated. Key findings: lock teardown mismatch (4 paths), cross-tenant auth, artifact inheritance ordering, prompt guard condition.

### 23.2 Key Design Decisions

#### D1 — Effective Slug Pattern

Artifact directory slug = `{company_slug}__{product_slug}` (double underscore). Example: `ramp__ramp-corporate-card`.

```python
def _effective_slug(company_slug: str, product_slug: Optional[str]) -> str:
    return f"{company_slug}__{product_slug}" if product_slug else company_slug
```

Double underscore is unambiguous since individual slugs use `[a-z0-9-]` only — no underscores allowed in individual slugs. `_SLUG_PATTERN` in all 3 service files updated to `^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$`.

#### D2 — Research Artifact Inheritance (Fallback Chain)

Product-level runs share company-level research artifacts. Fallback chain (stops at first match):
1. `artifacts/company_context/{effective_slug}.md` — product-specific research
2. `artifacts/company_context/{company_slug}.md` — shared company research
3. `None` — pipeline runs without context

Same chain for personas and style guides. Artifacts snapshotted at run start.

#### D3 — effective_slug Stored on PipelineTask

`PipelineTask.effective_slug: Optional[str] = None` eliminates repeated derivation in all 4 teardown paths:
- `runner.py gap finally` → `release_slug_lock(task.effective_slug or task.company_slug)`
- `runner.py content finally` → same
- `runner.py research finally` → same
- `tasks.py cancel endpoint` → same

Company-level lock (`"ramp"`) and product-level lock (`"ramp__ramp-corporate-card"`) are **independent** — simultaneous runs allowed.

#### D4 — RunScope Dataclass (Central Resolver)

```python
@dataclass
class RunScope:
    company_slug: str
    product_slug: Optional[str]
    effective_slug: str           # artifact dirs + lock key
    product_name: Optional[str]
    product_description: Optional[str]
    product_domain: Optional[str]

def _resolve_scope(company_slug: str, product_slug: Optional[str], auth_store: AuthStore) -> RunScope:
    ...  # Looks up product from auth_store, builds scope
```

Used by all 3 pipeline runners at startup. Replaces scattered `if product_slug:` lookups.

#### D5 — Prompt Injection Guard

Product context injected into prompts only when `product_slug AND product_name` both non-null. Empty string `""` for company-level runs — zero prompt drift.

```python
# s2_generate_queries.py
product_context: Optional[str] = None
if input_data.product_slug and input_data.product_name:
    product_context = _PRODUCT_CONTEXT_BLOCK.format(...)

# planner.py
product_context_md = ""
if input_data.product_slug and input_data.product_name:
    product_context_md = _PRODUCT_FOCUS_BLOCK.format(...)
```

### 23.3 Phase 1 — Product CRUD (35 tests)

**Goal:** Products can be created, read, updated, deleted. Company profile shows real product artifact status.

#### New models in `core/models/organization.py`

`Product` model added in prior front-back sprint (already existed). Used here.

#### `api/auth/store.py` additions

```python
def add_product(company_slug: str, product: Product) -> Product
def get_product(company_slug: str, product_slug: str) -> Optional[Product]
def update_product(company_slug: str, product_slug: str, **kwargs) -> Product
def remove_product(company_slug: str, product_slug: str) -> bool
```

Slug validation: `re.match(r'^[a-z0-9][a-z0-9-]*$', slug)` — 409 on duplicate, 422 on invalid format, 404 if company not found.

#### `api/routers/companies.py` additions

```
POST   /api/v1/companies/{slug}/products              → create product
GET    /api/v1/companies/{slug}/products/{product_slug} → get product
PUT    /api/v1/companies/{slug}/products/{product_slug} → update product
DELETE /api/v1/companies/{slug}/products/{product_slug} → delete product
```

Every endpoint verifies `product.company_id == company.id` (cross-tenant ownership check — Codex CRITICAL finding).

#### `api/schemas/company.py` additions

- `ProductCreateRequest` — `name: str`, `slug: str`, `domain: Optional[str] = None`, `description: Optional[str] = None`
- `ProductUpdateRequest` — all optional
- `ProductDetailResponse` — full product with `id`, `slug`, `name`, `domain`, `description`, `company_id`, `created_at`, `updated_at`

#### `api/tasks/models.py` additions

```python
class PipelineTask(BaseModel):
    product_slug: Optional[str] = None      # NEW — which product (if any)
    effective_slug: Optional[str] = None    # NEW — lock key + artifact dir slug
```

### 23.4 Phase 2 — Task Infrastructure (16 tests)

**Goal:** Tasks carry product_slug; locks use effective_slug; company+product runs coexist.

#### `api/tasks/store.py` changes

```python
def create_task(
    self,
    pipeline: str,
    company_slug: str,
    product_slug: Optional[str] = None,    # NEW
) -> PipelineTask:
    effective = f"{company_slug}__{product_slug}" if product_slug else company_slug
    self.acquire_slug_lock(effective)       # Lock on effective slug, not bare slug
    task = PipelineTask(
        ...,
        product_slug=product_slug,
        effective_slug=effective,           # Stored for teardown
    )
```

`list_tasks()` gains `product_slug: Optional[str] = None` filter.

Cancel endpoint fixed to `release_slug_lock(task.effective_slug or task.company_slug)`.

#### `api/schemas/common.py` changes

`PipelineRunResponse`, `TaskResponse`, `TaskSummary` all gain `product_slug: Optional[str] = None` and `effective_slug: Optional[str] = None`.

### 23.5 Phase 3 — Pipeline Execution Wiring (36 tests)

**Goal:** `POST /api/v1/gap-analysis/start` with `product_slug` routes the run to the product artifact directory. Research artifacts inherited from company.

#### Core model additions

```python
# core/models/gap_analysis.py, content_generation.py, artifacts.py
product_slug: Optional[str] = None
product_name: Optional[str] = None
product_description: Optional[str] = None
```

#### `api/tasks/runner.py` changes

Added `RunScope` dataclass and `_resolve_scope()`. Updated all 3 runners:
1. Call `_resolve_scope(company_slug, product_slug, auth_store)` at startup
2. Use `scope.effective_slug` for `create_task()` call (lock key + artifact dir)
3. Use bare `company_slug` for `resolve_artifacts()` call (inheritance from company)
4. Populate `product_slug/name/description` fields on input models
5. Content runner: `gap_slug = request.gap_slug or scope.effective_slug`
6. `finally:` block in all 3 runners now uses `task.effective_slug or task.company_slug`

#### Research artifact fallback chain (implemented in `resolve_artifacts()`)

```
effective_slug.md → company_slug.md → None  (company_context)
effective_slug__persona-*.md → company_slug__persona-*.md → []  (personas)
effective_slug.md → company_slug.md → None  (style_guide)
```

### 23.6 Phase 4 — Product Prompts (15 tests)

**Goal:** S2 generates product-focused queries; content planner generates product-focused briefs.

#### `core/gap_analysis/steps/s2_generate_queries.py`

```python
_PRODUCT_CONTEXT_BLOCK = """\

SPECIFIC PRODUCT SCOPE — This gap analysis targets a single product, not the full company:
  Product name:        {product_name}
  Product domain:      {product_domain}
  Product description: {product_description}

CRITICAL INSTRUCTIONS FOR PRODUCT-SCOPED QUERIES:
- Treat this PRODUCT as the subject, not the parent company's full portfolio
- The "category" for these queries is the product's specific niche
- Apply brand name exclusion rules to the PRODUCT category terms
- Generate queries that capture buyers researching THIS product's specific use case
"""
```

Injected into `_QUERY_GEN_PROMPT` via `{product_context_block}` slot, placed between COMPANY section and QUERY CLUSTER TAXONOMY. Slot defaults to `""` for company-level runs.

#### `core/content_engine/prompts/planner_prompts.py`

```python
_PRODUCT_FOCUS_BLOCK = """\

## Specific Product Focus
**Product:** {product_name}
**Product Domain:** {product_domain}
**Description:** {product_description}

When generating content briefs, focus topics on this specific product's buyer journey
and competitive positioning, not the parent company broadly.
"""
```

Injected after `## Company` section in `build_planner_user_prompt()` when `product_context_md` param is set.

### 23.7 Phase 5 — Data Endpoints (12 tests)

**Goal:** All 11 read endpoints serve product artifacts via `?product_slug=`; service internals unchanged.

#### Router pattern (gap_data.py, content_data.py)

```python
def _effective(slug: str, product_slug: Optional[str]) -> str:
    return f"{slug}__{product_slug}" if product_slug else slug

@router.get("/summary", response_model=GapSummaryResponse)
def get_gap_summary(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> GapSummaryResponse:
    return get_summary(artifacts_root, _effective(slug, product_slug))
```

Applied to all 8 gap-data endpoints and all 3 content-data endpoints. Service functions receive the computed effective slug — no changes to service internals.

#### Slug validation pattern (all 3 service files)

```python
# Before: only bare company slugs
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# After: also accepts effective slugs like ramp__corporate-card
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")
```

### 23.8 Artifact Directory Structure (Complete)

```
artifacts/
├── gap_analysis/
│   ├── ramp/                              # Company-level (existing)
│   │   ├── queries.json
│   │   ├── enriched_citations.json
│   │   ├── analysis.json / gap_analysis_complete.json
│   │   ├── gap_report.md / .json
│   │   ├── generation_spec.md / .json
│   │   └── visualizations/
│   └── ramp__ramp-corporate-card/         # Product-level (new)
│       └── (same structure)
├── content/
│   ├── ramp/
│   └── ramp__ramp-corporate-card/         # Product-level (new)
│       ├── briefs.json
│       ├── run_metadata.json
│       └── content/{brief_id}/
├── company_context/
│   ├── ramp.md                            # Company research (shared)
│   └── ramp__ramp-corporate-card.md       # Product research (optional, not required)
├── personas/
│   └── ramp__persona-icp.md              # Always company-level (shared)
└── style_guides/
    └── ramp.md                           # Always company-level (shared)
```

### 23.9 End-to-End Verification

```bash
# 1. Create product
POST /api/v1/companies/ramp/products
{"name": "Ramp Corporate Card", "slug": "ramp-corporate-card", "domain": "ramp.com/corporate-card"}

# 2. Start product-level gap analysis
POST /api/v1/gap-analysis/start
{"company_name": "Ramp", "domain": "ramp.com", "product_slug": "ramp-corporate-card"}
# → artifacts/gap_analysis/ramp__ramp-corporate-card/ created
# → artifacts/gap_analysis/ramp/ untouched
# → Research artifacts from artifacts/company_context/ramp.md used (fallback)

# 3. Read product data
GET /api/v1/companies/ramp/gap-analysis/summary?product_slug=ramp-corporate-card
# → Returns product-scoped summary

# 4. Concurrent runs don't block each other
POST /api/v1/gap-analysis/start  {"company_name":"Ramp"}                          → 202
POST /api/v1/gap-analysis/start  {"company_name":"Ramp", "product_slug":"ramp-corporate-card"} → 202

# 5. Same product second run conflicts
POST /api/v1/gap-analysis/start  {"company_name":"Ramp", "product_slug":"ramp-corporate-card"} → 202
POST /api/v1/gap-analysis/start  {"company_name":"Ramp", "product_slug":"ramp-corporate-card"} → 409
```

---

## 24. Route Protection & Authorization Sprint — Exhaustive Implementation Detail

> **Sprint:** `route-protection` (2026-02-27)
> **Reviewed by:** Codex gpt-5.3-codex with `xhigh` reasoning effort
> **Findings:** 6 CRITICAL, 10 WARNING, 4 INFO — all CRITICALs incorporated
> **Test impact:** 900 → 944 tests (+44 new), 0 failures
> **Plan file:** `.claude/plans/bright-skipping-cupcake.md`

### 24.1 Problem Statement

Before this sprint, the API operated in **grace mode** — the `AuthMiddleware` parsed JWT tokens and populated `request.state` fields, but **never blocked unauthenticated requests**. Every endpoint was publicly accessible to anyone who discovered the API URL. This created six critical vulnerabilities:

1. **No authentication enforcement** — any HTTP client could read all company data, trigger pipelines, and pollute artifacts
2. **Cross-tenant account takeover via registration** — `register_user()` auto-joined companies by domain without proving ownership (Codex C1)
3. **Tenant scope was client-controlled** — pipeline `/start` derived slugs from the request body `company_name`, allowing one company to target another's artifacts (Codex C2)
4. **Task endpoints were IDOR surfaces** — task_id-addressable with no ownership check (Codex C3)
5. **SSE token leakage** — full bearer tokens in query params for EventSource leak in logs, proxies, and referrer headers (Codex C4)
6. **Deleted/deactivated users remained authorized** — middleware never checked user existence or `is_active` status per request (Codex C6)

### 24.2 Architecture — Separation of Concerns

**Core design principle:** Middleware handles **authentication** (identity extraction). FastAPI dependencies handle **authorization** (permissions + tenant scoping).

**Why this split:**
- Middleware operates at the ASGI protocol level — it runs before FastAPI routing, before dependency injection, before path parameter parsing. This makes it the right place for identity extraction and fail-closed default-deny.
- Authorization depends on route-specific context (which company slug is in the URL, what role is needed, whether this is a read or write operation). FastAPI's `Depends()` system naturally expresses these as composable, type-safe dependencies that receive parsed path parameters.
- Mixing authorization into middleware would require the middleware to understand URL routing patterns, duplicating FastAPI's router logic. Keeping them separate avoids this coupling.

```
Request arrives
  → CORSMiddleware (outermost — handles OPTIONS preflight, never reaches auth)
  → AuthMiddleware (ASGI — extracts identity, blocks if no valid token)
      scope["state"]["user_id"] = "uuid-..."
      scope["state"]["company_slug"] = "ramp"
  → RequestLoggingMiddleware (logs method/path/status/duration)
  → FastAPI Router → Endpoint Function
      → Depends(require_auth)          # looks up UserProfile, checks is_active
      → Depends(require_role("member")) # checks user.role ∈ allowed
      → Depends(require_tenant)         # URL slug == token's company_slug
      → Depends(require_company_access) # UUID comparison via store lookup
```

### 24.3 Pure ASGI Middleware — Why Not BaseHTTPMiddleware

**File:** `api/auth/middleware.py` (192 lines, full rewrite)

**Design choice — pure ASGI over BaseHTTPMiddleware:**

Starlette's `BaseHTTPMiddleware` wraps the response body in an intermediary, consuming the entire response into memory before sending it. This is incompatible with Server-Sent Events (SSE) streaming because:
- SSE relies on a never-ending `StreamingResponse` that sends chunks incrementally
- `BaseHTTPMiddleware` buffers the entire response, preventing the client from receiving events in real-time
- This was identified as Codex W1 (WARNING) during the security review

A pure ASGI middleware operates directly on the ASGI `scope`/`receive`/`send` protocol:
```python
class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
```

This has zero impact on streaming — the middleware either:
1. Sends a 401 response directly via raw ASGI `send()` calls (short-circuits before the app runs)
2. Passes through to `self.app(scope, receive, send)` without intercepting the response stream

**Why `_send_401()` constructs raw ASGI messages:**

When the middleware rejects a request, it must send an HTTP response without delegating to FastAPI. This requires constructing two ASGI messages manually:
```python
async def _send_401(send: Send, detail: str, code: str) -> None:
    body = json.dumps({"detail": detail, "code": code}).encode("utf-8")
    await send({"type": "http.response.start", "status": 401,
                "headers": [(b"content-type", b"application/json"),
                             (b"www-authenticate", b"Bearer"),
                             (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
```

The response includes `WWW-Authenticate: Bearer` (RFC 6750 compliance), a machine-readable `code` field (e.g., `"missing_token"`, `"invalid_token"`, `"auth_unavailable"`), and a human-readable `detail` field.

**Non-HTTP scope types are passed through immediately:**

```python
if scope["type"] not in ("http", "websocket"):
    await self.app(scope, receive, send)
    return
```

ASGI servers may send `lifespan` scope types during startup/shutdown. These must never be blocked by auth.

### 24.4 Default-Deny & Public Route Whitelist

**Design choice — default-deny over default-allow:**

The previous grace-mode middleware defaulted to **allow** — it tried to parse tokens but always passed requests through regardless. This is inherently unsafe because:
- Forgetting to add `Depends(require_auth)` to a new endpoint leaves it wide open
- A single missed endpoint creates a data exfiltration vector
- The blast radius of a mistake is "all company data exposed"

Default-deny inverts this: **every route is blocked unless explicitly whitelisted**. The blast radius of a mistake becomes "one endpoint is inaccessible" (a 401 error) — far safer.

**Public path whitelist:**

```python
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/readiness",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/join",
})

_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/docs/",   # Swagger sub-resources (CSS, JS, schema)
    "/redoc/",  # ReDoc sub-resources
)
```

**Why `frozenset` for paths and `tuple` for prefixes:**
- `frozenset` gives O(1) membership testing for exact path matches
- Prefix matching requires iteration anyway, so `tuple` is sufficient and more memory-efficient than `frozenset` for small collections
- Both are immutable — they cannot be accidentally modified at runtime

**Why `/api/v1/auth/join` is public:**
The invite join endpoint must be accessible to unauthenticated users — they don't have an account yet. The invite code itself acts as the authorization credential (single-use, validated in the handler).

### 24.5 Token Extraction — Dual-Mode (Header + Query Param)

**File:** `api/auth/middleware.py`, functions `_extract_token()`, `_extract_token_from_headers()`, `_extract_stream_token_from_query()`

**Design choice — why two extraction modes:**

The browser `EventSource` API (used for SSE) **cannot set custom headers**. It only supports `GET` requests with URL parameters. This means `Authorization: Bearer {token}` headers are impossible for SSE connections from browser clients.

The naive solution — putting the full bearer token in a query parameter — has serious security implications (Codex C4):
- Query params appear in server access logs
- They are included in HTTP `Referer` headers sent to third-party resources
- They may be cached by CDNs and reverse proxies
- Browser history records the full URL

**Solution — short-lived stream tokens:**

Instead of exposing the bearer token, the system uses a dedicated stream token endpoint:
1. Client calls `POST /api/v1/tasks/{task_id}/stream-token` with their bearer token in the header
2. Server returns a 5-minute stream token with `stream_only: true` in the payload
3. Client opens `EventSource(/api/v1/tasks/{task_id}/events?stream_token=xxx)`
4. Middleware accepts the stream token only for paths ending in `/events`

```python
def _extract_token(scope: Scope) -> Optional[str]:
    headers = scope.get("headers", [])
    token = _extract_token_from_headers(headers)
    if token:
        return token
    # Fallback: stream_token query param for SSE EventSource endpoints
    path = scope.get("path", "")
    if path.endswith("/events"):
        return _extract_stream_token_from_query(scope.get("query_string", b""))
    return None
```

**Why header is checked first:** If both header and query param are present, the header token takes priority. This prevents an attacker from overriding a valid header token with a malicious query param.

**Why query param is only checked for `/events` paths:** If the middleware extracted `stream_token` from any path's query params, an attacker could bypass the header-only requirement for non-SSE endpoints. Restricting query param extraction to `/events` paths ensures stream tokens can only be used where they're needed.

**Stream token scope enforcement in middleware:**
```python
if payload.get("stream_only") and not path.endswith("/events"):
    await _send_401(send, "Stream token cannot be used here", "invalid_token")
    return
```

This is defense-in-depth: even if someone extracts a stream token from network traffic, they cannot use it to call data endpoints.

### 24.6 Auth Dependency Chain

**File:** `api/auth/dependencies.py` (138 lines, new file)

Five composable dependencies providing layered authorization. The dependency chain follows Codex I1's recommendation: `require_auth → require_role → require_company_access`.

#### `require_auth` — Base Identity + Active Check

```python
def require_auth(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> UserProfile:
```

**What it does:**
1. Reads `request.state.user_id` (populated by middleware)
2. Looks up full user record from AuthStore → 401 if not found (Codex C6: deleted users are caught here)
3. Builds `UserProfile` via `model_validate()`, excluding `password_hash`
4. Checks `is_active == True` → 401 `"Account deactivated"` if False

**Why store lookup on every request (Codex C6):**
The middleware only validates the JWT signature and expiry. It does NOT check whether the user still exists or is active. Without `require_auth`'s store lookup, a deleted user's token would remain valid until expiry (up to 24 hours). The per-request lookup ensures deactivated/deleted users are immediately blocked.

**Why `model_validate({k: v for ... if k != "password_hash"})` instead of direct construction:**
The user data in the store is a raw dict (not a Pydantic model) because it includes `password_hash` which `UserProfile` doesn't have. Filtering the dict and using `model_validate()` is the cleanest way to construct a valid `UserProfile` without exposing the hash.

#### `require_role(*allowed_roles)` — RBAC Gate

```python
def require_role(*allowed_roles: str) -> Callable[..., UserProfile]:
    def _check_role(user: UserProfile = Depends(require_auth)) -> UserProfile:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, ...)
        return user
    return _check_role
```

**Why a factory function (not a direct dependency):**
FastAPI's `Depends()` expects a callable. To parameterize which roles are allowed, we need a factory that returns a closure capturing `allowed_roles`. Usage: `Depends(require_role("member", "superuser"))`.

**Why `require_auth` is a dependency of `_check_role` (not called manually):**
This ensures the full auth chain runs automatically — FastAPI's DI system handles the composition. If `require_auth` raises 401, `_check_role` never executes. No duplicate code.

**Role hierarchy:** Three roles exist — `viewer` (read-only), `member` (read + write + pipeline), `superuser` (all + admin). The system does NOT implement hierarchical role inheritance (superuser doesn't automatically pass a `member` check). Instead, endpoints that accept both explicitly list them: `require_role("member", "superuser")`. This is deliberate — it's simpler, more explicit, and avoids bugs where a role hierarchy change has unintended cascading effects.

#### `require_tenant` — Lightweight Slug Comparison

```python
def require_tenant(slug: str, request: Request, _user: UserProfile = Depends(require_auth)) -> UserProfile:
    company_slug = getattr(request.state, "company_slug", None)
    if not company_slug or slug != company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return _user
```

**Why this exists separately from `require_company_access`:**
High-volume read endpoints (gap data — 8 endpoints, content data — 3 endpoints, brand data — 2 endpoints) are called frequently by the frontend. They only need to verify the URL slug matches the authenticated user's company. A full store lookup (`require_company_access`) would add an unnecessary `O(n)` company-by-slug scan on every request.

`require_tenant` compares two strings: the URL path parameter `slug` against `request.state.company_slug` (set by middleware from the token). No store lookup, no UUID comparison. Fast and sufficient for read-only endpoints where the slug is the only tenant identifier in the URL.

**Why it depends on `require_auth` (the `_user` parameter):**
Even though `require_tenant` doesn't use the user profile directly, it needs `require_auth` to run first to ensure the user exists and is active. The underscore prefix (`_user`) signals this is an unused-by-name dependency.

#### `require_company_access` — UUID-Based Tenant Check (Codex I2)

```python
def require_company_access(slug: str, user: UserProfile = Depends(require_auth),
                           auth_store: AuthStore = Depends(get_auth_store)) -> Tuple[UserProfile, Company]:
    company = auth_store.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, ...)
    if user.company_id != company.id:
        raise HTTPException(status_code=403, ...)
    return user, company
```

**Why UUID comparison instead of slug comparison (Codex I2):**
Slugs are derived from company names and could theoretically collide or be reassigned. UUIDs (`company.id`) are immutable, globally unique, and cryptographically random. Comparing `user.company_id != company.id` is the authoritative tenant check. The store lookup is necessary here because we need the Company object to get its UUID.

**Why it returns `Tuple[UserProfile, Company]`:**
Write endpoints typically need both the authenticated user and the target company object (e.g., to create a product under the company). Returning both avoids a second store lookup in the endpoint handler.

#### `require_company_member` — Combined Role + Tenant

```python
def require_company_member(slug: str,
    user: UserProfile = Depends(require_role("member", "superuser")),
    auth_store: AuthStore = Depends(get_auth_store)) -> Tuple[UserProfile, Company]:
```

**Why this exists:**
Write endpoints (create product, update product, delete product) need both RBAC (member+ role) and tenant isolation (user belongs to company). Without this combined dependency, every write endpoint would need two separate `Depends()` calls plus manual company lookup. `require_company_member` composes them into one dependency.

**Dependency chain when `require_company_member` is used:**
```
require_company_member
  └─ require_role("member", "superuser")
       └─ require_auth
            └─ reads request.state.user_id (set by AuthMiddleware)
```

### 24.7 Auth Dependency Usage — Complete Router Map

| Router | Endpoint | Auth Dependency | Why This Level |
|--------|----------|-----------------|----------------|
| **auth** | `POST /register` | None (public) | New users don't have tokens |
| | `POST /login` | None (public) | Obtaining a token |
| | `GET /me` | request.state direct | Lightweight self-lookup |
| | `POST /invite` | `require_role("superuser")` | Only admins can invite |
| | `POST /join` | None (public) | Invite code is the credential |
| **companies** | `GET /{slug}` | `require_tenant` | Read-only, slug comparison sufficient |
| | `POST /{slug}/products` | `require_company_member` | Write: needs role + tenant |
| | `GET /{slug}/products/{p}` | `require_tenant` | Read-only |
| | `PUT /{slug}/products/{p}` | `require_company_member` | Write: needs role + tenant |
| | `DELETE /{slug}/products/{p}` | `require_company_member` | Write: needs role + tenant |
| **gap_analysis** | `POST /start` | `require_role("member", "superuser")` | Pipeline trigger + body-level tenant check |
| | `GET /{run_id}/status` | `require_auth` | Task ownership checked in body |
| **research** | `POST /start` | `require_role("member", "superuser")` | Pipeline trigger + body-level tenant check |
| | `GET /{run_id}/status` | `require_auth` | Task ownership checked in body |
| | `POST /{run_id}/approve` | `require_role("member", "superuser")` | HITL approval is a write action |
| **content** | `POST /start` | `require_role("member", "superuser")` | Pipeline trigger + body-level tenant check |
| | `GET /{run_id}/status` | `require_auth` | Task ownership checked in body |
| | `POST /{run_id}/approve` | `require_role("member", "superuser")` | HITL approval is a write action |
| **gap_data** (8) | All endpoints | `require_tenant` | High-volume reads, slug comparison |
| **content_data** (3) | All endpoints | `require_tenant` | High-volume reads, slug comparison |
| **brand_data** (2) | All endpoints | `require_tenant` | High-volume reads, slug comparison |
| **tasks** | `GET /` | `require_auth` | Auto-filters by company_slug |
| | `GET /{task_id}` | `require_auth` | Task ownership checked in body |
| | `POST /{task_id}/cancel` | `require_role("member", "superuser")` | Destructive action |
| | `POST /{task_id}/stream-token` | `require_auth` | Task ownership checked in body |
| **artifacts** (3) | All endpoints | `require_auth` | Custom `_slug_belongs_to_user()` logic |
| **events** | `GET /{task_id}/events` | AuthMiddleware only | SSE — auth via middleware + stream token |

### 24.8 Registration Hardening — Closing the Cross-Tenant Attack (Codex C1)

**File:** `api/auth/store.py`, method `register_user()`

**The vulnerability:** The previous `register_user()` performed domain auto-join: if a company with domain `ramp.com` already existed, any user registering with `company_domain=ramp.com` was automatically added to that company as a `member`. An attacker could:
1. Discover that `ramp.com` exists (e.g., from public API responses)
2. Register with `company_domain=ramp.com`
3. Gain member-level access to all of Ramp's pipeline data, artifacts, and tasks

**The fix — isolated registration:**

```python
def register_user(self, ..., company_domain: str) -> Tuple[UserProfile, Company]:
    root_domain, subdomain = normalize_domain(company_domain)
    existing = self.get_company_by_domain(root_domain)
    if existing:
        raise ValueError("domain_taken")
    # Always creates a new company — user becomes superuser
```

Now:
- Registration **always creates a new, isolated company**
- The registering user becomes `superuser` of that company
- If the domain is already taken → 409 with message: *"A company with this domain already exists. Ask your admin for an invite code."*
- Joining an existing company requires an **invite code** from a superuser

**Why not allow domain-based join with email verification?**
Email verification is a full feature (sending emails, verification tokens, expiry, retry logic) that would delay the security fix. The invite code pattern provides equivalent security with minimal implementation complexity. Email-based invites can be added later as an enhancement.

**Slug collision handling:**

```python
slug = _derive_slug(company_name)
base_slug = slug
counter = 1
while slug in self._companies:
    slug = f"{base_slug}-{counter}"
    counter += 1
```

If "Ramp" already exists as a company, a second registration for a company named "Ramp" (with a different domain) gets slug `ramp-1`. This prevents slug collisions without requiring unique company names.

### 24.9 Invite Flow — Joining Existing Companies

**Files:** `api/auth/store.py` (methods `create_invite()`, `redeem_invite()`), `api/routers/auth.py` (endpoints)

**Design: simple invite codes (v0)**

```
Superuser → POST /api/v1/auth/invite {"role": "member"}
         ← 201 {"invite_code": "a7b3c9e1f2d4a8b6"}

New user  → POST /api/v1/auth/join {"invite_code": "a7b3c9e1f2d4a8b6", "email": "...", ...}
         ← 201 {"user": {...}, "company": {...}, "token": "..."}
```

**Why 16-character hex codes (not UUIDs or JWTs):**
- 16 hex chars = 64 bits of entropy — sufficient for short-lived invite codes
- Easy to share verbally or via text (no special characters, case-insensitive)
- `secrets.token_hex(8)` is cryptographically secure
- Shorter than UUIDs, more readable, adequate security for the threat model

**Why in-memory storage (not persisted to disk):**
- v0 implementation — invite codes are lost on server restart
- This is acceptable because: (1) invites are rare operations, (2) a superuser can simply create a new code, (3) the full invite system will be replaced by email-based invites with Supabase Auth later
- Persisting invite codes to a JSON file would add complexity for a feature that will be replaced

**Single-use enforcement:**
```python
def redeem_invite(self, invite_code, ...):
    invite = invites.get(invite_code)
    if not invite:
        raise ValueError("Invalid or expired invite code")
    # ... create user ...
    del self._invites[invite_code]  # Single-use
```

The invite code is deleted immediately after redemption. Attempting to reuse it returns "Invalid or expired invite code."

**Role assignment via invite:**
The superuser specifies the role when creating the invite (default: `"member"`). The joining user receives exactly that role — they cannot escalate it. The `create_invite` endpoint requires `require_role("superuser")`, preventing members from creating invites.

### 24.10 Pipeline Tenant Isolation (Codex C2)

**Files:** `api/routers/gap_analysis.py`, `api/routers/research.py`, `api/routers/content.py`

**The vulnerability:** Pipeline `/start` endpoints derived the slug from `body.company_name` via `_derive_slug()`. An authenticated user of company A could POST `{"company_name": "Company B"}` and trigger a pipeline that writes artifacts to company B's directory.

**The fix — body slug validated against token slug:**

```python
@router.post("/start")
async def start_gap_analysis(body: GapAnalysisStartRequest,
    http_request: Request,
    user: UserProfile = Depends(require_role("member", "superuser")),
    auth_store: AuthStore = Depends(get_auth_store), ...):

    company_slug = getattr(http_request.state, "company_slug", None)
    derived_slug = _derive_slug(body.company_name)
    if derived_slug != company_slug:
        raise HTTPException(403, "Cannot start pipeline for another company")
```

**Why the body's `company_name` is still accepted (not removed):**
- Backward compatibility — existing frontend code sends `company_name` in the body
- The body value is used for display purposes and slug derivation verification
- The authoritative slug comes from the JWT token (`request.state.company_slug`)
- The derived slug from the body must MATCH the token slug — otherwise 403

**Why `_derive_slug()` comparison (not direct string comparison on company_name):**
Company names may differ in casing or punctuation ("Ramp" vs "ramp") but derive to the same slug. The slug comparison normalizes this.

**Parameter naming in pipeline routers:**

The `request` parameter name conflicts with FastAPI's auto-injected `Request` when both a Pydantic body model and `Request` are in the function signature. Solution: rename body parameter to `body` and Request to `http_request`:

```python
async def start_pipeline(body: PipelineStartRequest, http_request: Request, ...):
```

### 24.11 Task & SSE Tenant Isolation (Codex C3)

**Files:** `api/routers/tasks.py`, `api/routers/events.py`

**The vulnerability:** Tasks are addressable by `task_id` (a UUID). Any authenticated user who guesses or observes a task ID could view another company's task details, cancel their tasks, or stream their SSE events.

**Auto-filtering on `GET /tasks`:**

```python
@router.get("")
async def list_tasks(request: Request, user: UserProfile = Depends(require_auth), ...):
    company_slug = getattr(request.state, "company_slug", None)
    tasks = task_store.list_tasks(company_slug=company_slug, ...)
```

Users automatically see only their own company's tasks. No filter parameter needed — the company_slug is injected from the token.

**Ownership check on task detail/cancel/stream-token:**

```python
task = task_store.get_task(task_id)
if not task:
    raise HTTPException(404, ...)
company_slug = getattr(request.state, "company_slug", None)
if task.company_slug != company_slug:
    raise HTTPException(403, "Access denied")
```

**Why 403 (not 404) for cross-tenant access:**
Returning 404 would hide the existence of the task — this is sometimes preferred for security. However, the task_id is a random UUID (not guessable), and returning 403 provides better debugging information for legitimate users who might have a stale link. The security benefit of 404-masking is minimal given UUID randomness.

**SSE events endpoint (`GET /{task_id}/events`):**
This endpoint does NOT use `Depends(require_auth)` because it needs to support stream token authentication from query params. The middleware handles authentication (supporting both Bearer header and `?stream_token=` query param). The endpoint itself performs the ownership check:

```python
company_slug = getattr(request.state, "company_slug", None)
if task.company_slug != company_slug:
    raise HTTPException(403, "Access denied")
```

### 24.12 JWT Secret Key Enforcement (Codex W8)

**File:** `api/auth/store.py`, `__init__()` method

**The problem:** If `JWT_SECRET_KEY` is not set, the store generated a random secret. On server restart, a new random secret is generated, immediately invalidating ALL existing tokens. Users would be silently logged out, and any in-progress pipeline tasks with SSE connections would lose their stream tokens.

**The fix:**

```python
secret = os.environ.get("JWT_SECRET_KEY")
if not secret:
    env = os.environ.get("ENVIRONMENT", "development")
    if env not in ("development", "test"):
        raise RuntimeError("JWT_SECRET_KEY must be set in non-development environments")
    secret = secrets.token_hex(32)
```

**Why allow random secrets in dev/test:**
Developers running `python scripts/run_server.py` locally shouldn't need to configure environment variables for a quick test. The random secret is acceptable for single-session development. Test environments also benefit — each test run gets a fresh secret, preventing cross-test contamination.

**Why `RuntimeError` (not a warning):**
A warning could be missed in production logs. A hard crash on startup is impossible to miss and prevents the server from running in an insecure state. This follows the "fail loud, fail early" principle.

**Why `ENVIRONMENT` env var (not a Pydantic Settings field):**
The `ENVIRONMENT` check runs in `AuthStore.__init__()`, which executes before any Pydantic Settings class might be initialized. Using a raw env var avoids a circular dependency.

### 24.13 Login Timing Fix (Codex W7)

**File:** `api/routers/auth.py`, login endpoint

**The vulnerability:** When a user doesn't exist, the login handler returned 401 immediately. When a user exists but the password is wrong, it computed a PBKDF2 hash before returning 401. An attacker could measure response times to determine whether an email is registered — a timing side-channel for user enumeration.

**The fix — constant-time dummy hash:**

```python
user = auth_store.get_user_by_email(body.email)
if not user:
    auth_store.verify_password(body.password, AuthStore._DUMMY_HASH)
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

```python
class AuthStore:
    _DUMMY_HASH: str = "0" * 32 + ":" + "0" * 64
```

**Why `_DUMMY_HASH` is a class variable (not generated per-request):**
Generating a fresh hash per request would add variability. The dummy hash is a fixed string with the same format as real hashes (`salt:hash_hex`). `verify_password()` performs the same PBKDF2 computation (100,000 iterations) regardless of whether the user exists or not.

**Why `hmac.compare_digest()` in `verify_password()`:**
Even after ensuring both code paths compute a hash, the final comparison must be constant-time. Python's `==` operator short-circuits on the first differing byte. `hmac.compare_digest()` always compares all bytes, preventing micro-timing attacks on the comparison itself.

### 24.14 Threading Model — RLock and Mutable Field Allowlists

**File:** `api/auth/store.py`

**Why `threading.RLock()` (not `threading.Lock()`):**

```python
self._lock = threading.RLock()
```

`register_user()` calls `create_user()` internally:
```python
def register_user(self, ...):
    with self._lock:
        # ... create company ...
        user = self.create_user(...)  # Also acquires self._lock
```

`create_user()` also acquires `self._lock`:
```python
def create_user(self, ...):
    with self._lock:
        # ... check email, create profile, save ...
```

With a regular `Lock`, this would deadlock — `register_user` holds the lock when calling `create_user`, which tries to acquire the same lock. `RLock` (reentrant lock) allows the same thread to acquire the lock multiple times, preventing the deadlock.

**Why read-only operations don't acquire the lock:**

```python
def get_company_by_slug(self, slug: str) -> Optional[Company]:
    return self._companies.get(slug)  # No lock
```

The in-memory dicts are only mutated under the lock. Python's GIL ensures dict reads are atomic. For a single-worker deployment (which is the current deployment model — Codex W4 deferred), read-without-lock is safe and avoids unnecessary contention.

**Mutable field allowlists:**

```python
_COMPANY_MUTABLE_FIELDS: frozenset = frozenset({"name", "domain", "additional_domains"})
_PRODUCT_MUTABLE_FIELDS: frozenset = frozenset({"name", "domain", "description"})
```

```python
def update_company(self, slug: str, **kwargs: Any) -> Company:
    for k, v in kwargs.items():
        if k in _COMPANY_MUTABLE_FIELDS:
            setattr(company, k, v)
```

**Why allowlists (not blocklists):**
An allowlist is strictly safer — if a new field is added to the model, it's immutable by default until explicitly added to the allowlist. A blocklist approach (`if k not in {"id", "slug", "created_at"}`) would need to be updated every time a new immutable field is added, and forgetting to add it creates a security hole.

**Which fields are immutable and why:**
- `id` — UUID, permanent identifier, used in foreign key relationships
- `slug` — used in URL paths and artifact directory names, changing it would orphan artifacts
- `created_at` — audit trail, must not be tampered with

### 24.15 Middleware Ordering

**File:** `api/app.py`

```python
app.add_middleware(RequestLoggingMiddleware)  # Added 3rd → innermost
app.add_middleware(AuthMiddleware)             # Added 2nd → middle
app.add_middleware(CORSMiddleware, ...)        # Added 1st → outermost
```

FastAPI (Starlette) wraps middleware in **reverse insertion order** — the last `add_middleware()` call wraps the outermost layer. This means:

**Execution order:** CORSMiddleware → AuthMiddleware → RequestLoggingMiddleware → Router

**Why CORS must be outermost:**
Browser preflight `OPTIONS` requests include `Origin` and `Access-Control-Request-Method` headers. These requests do NOT include `Authorization` headers. If `AuthMiddleware` ran before `CORSMiddleware`, it would reject all preflight requests with 401, breaking CORS entirely. By running CORSMiddleware first, OPTIONS requests are handled and returned before they ever reach AuthMiddleware.

**Why RequestLoggingMiddleware is innermost:**
It logs the final status code of the response. If it ran before AuthMiddleware, it would log 401s from the auth middleware, which is correct. But it also needs to see status codes from the actual router handlers. Being innermost ensures it wraps the closest layer to the business logic.

### 24.16 Test Migration Strategy

**Files:** `tests/api/conftest.py` (205 lines, modified), all `tests/api/test_*.py` files

**The challenge:** 900 existing tests were written for the grace-mode middleware — none included auth tokens. Switching to default-deny would break all of them with 401 errors.

**Solution — `_AuthTestClient` with auto-injection:**

```python
class _AuthTestClient(TestClient):
    def __init__(self, app: FastAPI, default_headers: dict[str, str], **kwargs):
        super().__init__(app, headers=default_headers, **kwargs)
        self._default_auth_headers = default_headers

    def request(self, method: str, url: str, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        if "Authorization" not in headers:
            headers.update(self._default_auth_headers)
        return super().request(method, url, headers=headers, **kwargs)
```

**Why a TestClient subclass (not conftest monkey-patching — Codex W10):**
The original plan considered monkey-patching the `client` fixture's `request` method. This would miss:
- Custom TestClient fixtures in specific test files (e.g., `artifacts_client`, `app_client`)
- The `stream()` method used by SSE tests (which `_AuthTestClient` handles via `httpx.Client(headers=...)`)
- Class-based test clients that override `request()`

The subclass approach is clean, explicit, and handles all request methods automatically via httpx's built-in `headers` propagation.

**Why the `if "Authorization" not in headers` guard:**
Tests that explicitly provide an `Authorization` header (e.g., to test expired tokens, malformed tokens, or cross-tenant access) must not have their header overwritten.

**Four client fixtures for comprehensive testing:**

| Fixture | Role | Purpose |
|---------|------|---------|
| `client` | member @ test-co | Default authenticated client for most tests |
| `public_client` | None (no token) | Testing 401 enforcement |
| `viewer_client` | viewer @ test-co | Testing RBAC (403 on write ops) |
| `superuser_client` | superuser @ test-co | Testing admin operations (invites) |

**Company name alignment in pipeline tests:**

All pipeline tests that POST to `/start` include `company_name` in the body. The tenant isolation check requires `_derive_slug(company_name)` to match the test user's `company_slug` ("test-co"). All test payloads were updated: `"Ramp"` → `"Test Co"`, `"ramp"` → `"test-co"`.

### 24.17 New Auth Enforcement Tests

**File:** `tests/api/test_auth_enforcement.py` (589 lines, 42 tests in 7 classes)

| Class | Tests | What It Validates |
|-------|-------|-------------------|
| `TestMiddlewareEnforcement` | 7 | Public routes pass (health, register, login), protected routes 401 without token, 401 with expired token, 401 with malformed token, 200 with valid token |
| `TestDeactivatedUser` | 2 | `is_active=False` → 401 on task list, 401 on company read. Proves middleware passes valid token but `require_auth` rejects at dependency layer |
| `TestRoleBasedAccess` | 12 | Viewer cannot start any pipeline, cannot cancel, cannot CRUD products, cannot create invites. Viewer CAN read company profile and gap data. Member and superuser CAN start pipelines |
| `TestTenantIsolation` | 10 | Cross-company access denied on: company profile, pipeline start, task detail, task cancel, gap data, content data, artifacts, SSE events. Tasks auto-filtered by company. Artifact company list scoped |
| `TestStreamTokens` | 4 | Stream token endpoint returns token with 300s expiry. Stream token works for SSE. Stream token rejected for non-SSE endpoints. Ownership check on stream token creation |
| `TestRegistrationHardening` | 4 | Duplicate domain → 409. Separate domains → separate companies. Invite requires superuser. Join with valid invite code works |
| `TestLoginBehavior` | 1 | Non-existent user → 401 (timing-safe, not blocked by middleware) |

**Cross-tenant test infrastructure:**

```python
@pytest.fixture
def other_company(auth_store): ...   # "other-co" / "Other Co" / "other.com"
@pytest.fixture
def other_user(auth_store, other_company): ...  # member @ other-co
@pytest.fixture
def other_client(app, auth_store, other_company, other_user): ...  # Authenticated for other-co
@pytest.fixture
def test_co_task(task_store, test_company): ...  # Task owned by test-co
@pytest.fixture
def other_co_task(task_store, other_company): ...  # Task owned by other-co
```

The bidirectional test pattern proves isolation in both directions:
```python
def test_user_cannot_read_other_company_profile(self, client, other_company):
    resp = client.get("/api/v1/companies/other-co")
    assert resp.status_code == 403

def test_other_user_cannot_read_test_co_profile(self, other_client, test_company):
    resp = other_client.get("/api/v1/companies/test-co")
    assert resp.status_code == 403
```

### 24.18 Codex Review Findings — Full Disposition

#### CRITICAL (6) — All Incorporated

| # | Finding | Fix | Implementation Location |
|---|---------|-----|------------------------|
| C1 | Cross-tenant account takeover via domain auto-join | Registration creates isolated companies; invite flow for joining | `store.py:register_user()`, `auth.py:/invite`, `auth.py:/join` |
| C2 | Tenant scope client-controlled in `/start` | Body slug validated against token slug | `gap_analysis.py`, `research.py`, `content.py` — all `/start` handlers |
| C3 | Task IDOR — no ownership check | `task.company_slug == user.company_slug` on all task endpoints | `tasks.py`, `events.py` — all handlers |
| C4 | Bearer token in SSE query param leaks | Short-lived stream tokens (5min, `stream_only` flag) | `store.py:create_stream_token()`, `middleware.py`, `tasks.py:/stream-token` |
| C5 | Grace-mode fail-open in production | Full default-deny rewrite | `middleware.py` — complete rewrite |
| C6 | Deleted users remain authorized | `require_auth` does full store lookup + `is_active` check | `dependencies.py:require_auth()` |

#### WARNING (10) — Incorporated or Deferred

| # | Finding | Disposition |
|---|---------|-------------|
| W1 | `BaseHTTPMiddleware` risky for SSE | **INCORPORATED** — Pure ASGI middleware |
| W2 | Middleware ordering | **INCORPORATED** — CORS outermost, verified |
| W3 | TaskStore race conditions | **DEFERRED** — Pre-existing, single-worker for now |
| W4 | AuthStore single-worker only | **DEFERRED** — Will address with Supabase migration |
| W5 | No token revocation/refresh | **PARTIALLY DEFERRED** — Logout not yet added; refresh tokens deferred |
| W6 | No rate limiting on login/SSE | **DEFERRED** — Backlog item PB-ratelimit |
| W7 | Login timing side-channel | **INCORPORATED** — `_DUMMY_HASH` constant-time verification |
| W8 | Secret key auto-generates | **INCORPORATED** — `RuntimeError` in non-dev environments |
| W9 | `/readiness` discloses API key availability | **DEFERRED** — Low risk for internal API |
| W10 | Test monkey-patching misses custom clients | **INCORPORATED** — `_AuthTestClient` subclass approach |

#### INFO (4) — Noted

| # | Finding | Disposition |
|---|---------|-------------|
| I1 | Standardize dependency chain | **INCORPORATED** — `require_auth → require_role → require_company_access` |
| I2 | Prefer `company_id` over slugs | **INCORPORATED** — UUID comparison in `require_company_access` |
| I3 | Structured audit logs | **DEFERRED** — Backlog |
| I4 | Explicit auth error codes | **INCORPORATED** — `code` field in all 401 responses |

### 24.19 Files Changed Summary

| File | Change | Lines |
|------|--------|-------|
| `api/auth/dependencies.py` | **NEW** — 5 auth dependencies | 138 |
| `api/auth/middleware.py` | **REWRITE** — Pure ASGI, default-deny | 192 |
| `api/auth/store.py` | MODIFY — Registration hardening, invite flow, stream tokens, JWT enforcement, RLock | ~543 |
| `api/routers/auth.py` | MODIFY — Login timing fix, invite/join endpoints, domain_taken 409 | ~256 |
| `api/routers/gap_analysis.py` | MODIFY — Role + tenant deps on /start, auth on /status | ~140 |
| `api/routers/research.py` | MODIFY — Role + tenant deps, param rename | ~180 |
| `api/routers/content.py` | MODIFY — Role + tenant deps, param rename | ~200 |
| `api/routers/tasks.py` | MODIFY — Auth + company filter + stream-token endpoint | ~160 |
| `api/routers/events.py` | MODIFY — Task ownership check | ~110 |
| `api/routers/companies.py` | MODIFY — `require_tenant` / `require_company_member` on all | ~200 |
| `api/routers/gap_data.py` | MODIFY — `require_tenant` on all 8 endpoints | ~350 |
| `api/routers/content_data.py` | MODIFY — `require_tenant` on all 3 endpoints | ~180 |
| `api/routers/brand_data.py` | MODIFY — `require_tenant` on both endpoints | ~150 |
| `api/routers/artifacts.py` | MODIFY — `require_auth` + `_slug_belongs_to_user()` | ~170 |
| `api/app.py` | MODIFY — Middleware ordering, import changes | 123 |
| `tests/api/conftest.py` | MODIFY — `_AuthTestClient`, 4 client fixtures | 205 |
| `tests/api/test_auth_enforcement.py` | **NEW** — 42 auth enforcement tests | 589 |
| Various `tests/api/test_*.py` | MODIFY — Company name alignment, auth fixture usage | ~20 files |

### 24.20 Deferred Items

| Item | Why Deferred | Backlog ID |
|------|-------------|------------|
| Rate limiting on login/SSE | Requires external dependency (slowapi or custom) | PB-ratelimit |
| Token refresh flow | Low priority — 24h expiry is sufficient for MVP | PB-refresh-tokens |
| Redis-backed AuthStore | Single-worker deployment for now | PB-multiworker-auth |
| `/readiness` key disclosure | Low risk for internal API | PB-readiness-disclosure |
| Structured audit logs | Nice-to-have, not blocking | PB-audit-log |
| Email-based invites | Simple invite codes sufficient for v0 | — |
| Logout / token blacklist | Partially implemented (W5), full revocation deferred | — |

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
| 2026-02-26 | §15 | Added Research Pipeline Test Coverage section (109 tests), updated test tree, updated total to 763 | T-research-tests |
| 2026-02-26 | §18 | Downgraded test coverage severity from Medium to Low — only Reddit HIL remains untested | T-research-tests |
| 2026-02-26 | §4 | Added api/auth/, api/services/, api/schemas/ (5 files), api/routers/ (6 new routers) to directory structure | T-fb-phase1-4 |
| 2026-02-26 | §15 | Updated test tree: 766 total, added test_brand_data.py (57), expanded api test section (305+ tests) | T-fb-phase4 |
| 2026-02-26 | §18 | Added 8 deferred issues from front-back sprint code reviews (C5-C7, CX-1/3/4/6, W8) | T-fb-phase1-4 |
| 2026-02-26 | §20 | Updated scope: added front-back sprint to completed sprints, added auth system to built components, updated roadmap priorities | T-fb-phase1-4 |
| 2026-02-26 | §21.1 | Added AuthMiddleware to middleware stack, expanded router list (12 routers) | T-fb-phase1-4 |
| 2026-02-26 | §21.2 | Added 16 new company-scoped endpoints: auth (3), company (1), gap data (8), content data (3), brand data (2), with full request/response docs | T-fb-phase1-4 |
| 2026-02-26 | §21.2 | Added Service Layer Architecture subsection documenting shared caching/validation/error patterns | T-fb-phase1-4 |
| 2026-02-26 | §22 | **NEW SECTION** — Exhaustive Front-Back Integration Sprint documentation: 4-phase detail, data flows, design choices, Codex reviews, architecture connections | T-fb-phase1-4 |
| 2026-02-26 | §15 | Updated test counts: 882 total (up from 766), added product-pipeline sprint test files, updated API test coverage header | T-product-pipeline-all |
| 2026-02-26 | §15 | Added Product-Level Pipeline Sprint Tests table (4 test files, 114 new tests) | T-product-pipeline-all |
| 2026-02-26 | §20 | Added Product-Level Pipeline Execution to What's Built table, added sprint to Completed Sprints, marked item 4 in What's Planned as DONE | T-product-pipeline-all |
| 2026-02-26 | §21 | Updated status header — 882 tests, product_slug support on all data endpoints | T-product-pipeline-all |
| 2026-02-26 | §22.8 | Marked Product-level endpoints item as COMPLETE (→ §23) | T-product-pipeline-all |
| 2026-02-26 | §23 | **NEW SECTION** — Product-Level Pipeline Execution Sprint: 5-phase detail (CRUD, task infra, wiring, prompts, data endpoints), design decisions, artifact structure, E2E verification | T-product-pipeline-all |
| 2026-02-27 | §21 | Updated status header — 900 tests, pipeline guard (`force_rerun`) on start endpoints | T-pipeline-guard |
| 2026-02-27 | §21.2 | Updated gap-analysis start docs: flat-field schema, `force_rerun` field, HTTP 200 already-exists response, dual-sentinel artifact detection logic | T-pipeline-guard |
| 2026-02-27 | §21.2 | Updated research start docs: flat-field schema, `force_rerun` + `stages` fields, stage-aware guard logic, draft exclusion, dual-scope fallback | T-pipeline-guard |
| 2026-02-27 | §15 | Updated test count 882→900 (+12 pipeline-guard tests); updated test tree (guard classes in test_gap_analysis.py + test_research.py); updated API test coverage header | T-pipeline-guard |
| 2026-02-27 | §17 | Added Decision 13: Pipeline Guard — HTTP 200 skip for existing artifacts (D-GUARD-1) | T-pipeline-guard |
| 2026-02-27 | §21 | Updated status header — 944 tests, production-grade route protection (Codex gpt-5.3-codex reviewed) | T-route-protection |
| 2026-02-27 | §21.1 | Rewrote middleware docs: pure ASGI (not BaseHTTPMiddleware), default-deny, public whitelist, stream token support, corrected middleware ordering | T-route-protection |
| 2026-02-27 | §21.2 | Rewrote Authentication section: hardened registration (no domain auto-join), invite flow endpoints, auth dependencies module, stream tokens, JWT_SECRET_KEY enforcement, login timing fix | T-route-protection |
| 2026-02-27 | §21.2 | Rewrote Auth Architecture subsection: replaced grace-mode docs with default-deny ASGI middleware, auth dependency chain, route protection summary table | T-route-protection |
| 2026-02-27 | §15 | Updated test count 900→944 (+44 route-protection tests); added route protection test table | T-route-protection |
| 2026-02-27 | §24 | **NEW SECTION** — Route Protection & Authorization Sprint: exhaustive implementation detail (20 subsections). Pure ASGI middleware architecture, auth dependency chain, registration hardening, invite flow, pipeline tenant isolation, task IDOR fix, stream tokens, JWT enforcement, login timing, threading model, middleware ordering, test migration, 42 new tests, Codex review disposition (6C/10W/4I), files changed, deferred items | T-route-protection |
| 2026-02-27 | TOC | Added §23 Product-Level Pipeline, §24 Route Protection with full subsection links, renumbered Appendices to §25-§27 | T-route-protection |
| 2026-02-27 | §1 | Updated Executive Summary — 1029 tests, settings + knowledge doc description | T-settings-knowledge-docs |
| 2026-02-27 | TOC | Added §25 Settings + Knowledge Docs sprint with 13 subsection links, renumbered Appendices to §26-§28 | T-settings-knowledge-docs |
| 2026-02-27 | §4 | Added knowledge_docs.py, organization.py to models; text_extraction.py, knowledge_doc_metadata.py to shared_tools; settings.py, knowledge_docs.py to routers/schemas/services; knowledge_docs/ and _auth/settings/ to artifacts | T-settings-knowledge-docs |
| 2026-02-27 | §6.1 | Added Knowledge Document Integration subsection — loading, chunking, embedding, shared module coordination, runner path resolution | T-settings-knowledge-docs |
| 2026-02-27 | §9 | Added §9.6 Knowledge Document Storage (layout, _metadata.json format, thread safety) and §9.7 Pipeline Defaults Storage | T-settings-knowledge-docs |
| 2026-02-27 | §10 | Added KnowledgeDocument model, CompanyPipelineDefaults model, DiscoverySource.KNOWLEDGE_DOC, knowledge_doc_dir on GapAnalysisInput, discovery_source on SemanticUnit | T-settings-knowledge-docs |
| 2026-02-27 | §15 | Updated test count 944→1029 (+77 settings/knowledge docs + 8 security fixes); added 6 new test files to tree | T-settings-knowledge-docs |
| 2026-02-27 | §18 | Updated test coverage description to 1029 tests | T-settings-knowledge-docs |
| 2026-02-27 | §20 | Added Settings Pages API + Knowledge Doc Upload to What's Built; added 5 missing sprints to Completed Sprints table | T-settings-knowledge-docs |
| 2026-02-27 | §21 | Updated status header — 1029 tests, 14 routers, settings + knowledge docs endpoints | T-settings-knowledge-docs |
| 2026-02-27 | §25 | **NEW SECTION** — Settings Pages API & Knowledge Doc Upload Sprint: 13 subsections covering team management, company profile, pipeline defaults, file upload, s1 integration, embedded status tracking, shared module extraction, review fixes, runner wiring, endpoint summary, files changed, deferred items | T-settings-knowledge-docs |
| 2026-02-27 | §4 | Added `alembic.ini` to root, `core/db/` tree (31 files: engine, base, enums, dependencies, 10 model files, 9 repo files, migrations), `tests/db/` tree (9 files) | T-sqlalchemy-migration |
| 2026-02-27 | §9 | Added §9.8 SQLAlchemy Database Layer — architecture overview, schema summary (31 tables), design decisions, repo pattern, migration strategy, Phase 1 status | T-sqlalchemy-migration |
| 2026-02-27 | §11 | Added Database environment variables (DATABASE_URL, DATABASE_ECHO, pool settings, cache TTLs, TEST_DATABASE_URL) + computed property database_url_sync | T-sqlalchemy-migration |
| 2026-02-27 | §15 | Updated test count 1029→1073 (+44 DB tests); added tests/db/ tree to directory listing | T-sqlalchemy-migration |
| 2026-02-27 | §16 | Added Database dependency group (sqlalchemy, asyncpg, psycopg2-binary, alembic, pgvector) | T-sqlalchemy-migration |
| 2026-02-27 | §17 | Added Decision 14: SQLAlchemy 2.0 + Alembic Database Layer (D-DB-1) — Codex-reviewed, 6-0 vs SQLModel | T-sqlalchemy-migration |
| 2026-02-27 | §18 | Updated test coverage description to 1073 tests, added DB layer mention, added CI recommendation | T-sqlalchemy-migration |
| 2026-02-28 | §1 | Updated Executive Summary — 1262 tests, 3-phase DB migration description | T-db-migration-docs |
| 2026-02-28 | §9.8 | Updated Phase 1 status — now fully wired via Phases 2+3, cross-ref to §26 | T-db-migration-docs |
| 2026-02-28 | TOC | Added §26 SQLAlchemy & Service Layer Migration with 23 subsection links, renumbered Appendices to §27-§29 | T-db-migration-docs |
| 2026-02-28 | §26 | **NEW SECTION** — SQLAlchemy & Service Layer Migration: 3-phase database architecture. Phase 1: 31 ORM tables, 16 repos, 4 Alembic migrations, flush-only pattern, lazy engine. Phase 2: AuthServiceProtocol, 3-layer decomposition (utilities/protocol/services), JsonAuthService + DbAuthService, middleware decoupling. Phase 3: 3 data service protocols (Gap/Brand/Content), 6 implementations (3 Json + 3 Db), SignalRepository SQL aggregations, PlatformRepository analytics, TaskStoreProtocol + DbTaskStore write-through, DI wiring, backfill script. 23 subsections, architecture diagram, cross-cutting patterns, testing strategy, deferred items. | D-DB-1, D-AUTH-2, D-SVC-1, D-TASKSTORE-1 |
| 2026-02-28 | §1 | Updated Executive Summary — ~1978 tests, added Pipeline 0 (Site Audit) description | T-site-audit-all |
| 2026-02-28 | TOC | Added §4a Pipeline 0: Site Audit with 12 subsection links | T-site-audit-all |
| 2026-02-28 | §4 | Added core/site_audit/ directory tree (16 files: pipeline, config, scoring, 6 steps, 7 checks) + core/models/site_audit.py | T-site-audit-all |
| 2026-02-28 | §4a | **NEW SECTION** — Pipeline 0: Site Audit. 12 subsections covering overview, all 6 steps (s1_discover through s6_report), 7 check modules, scoring algorithm, configuration, Pydantic models (2 enums + 9 models), API endpoints (6 endpoints), service protocol + JSON implementation | T-site-audit-all |
| 2026-02-28 | §15 | Added site audit test tree (585 core + 51 API = 636 tests across 10 files); updated test counts to ~1978 total; updated API test coverage header to 526+ | T-site-audit-all |
| 2026-02-28 | §18 | Updated test coverage description to ~1978 tests with site audit module breakdown | T-site-audit-all |
| 2026-02-28 | §20 | Added Site Audit to What's Built table; added 5 missing completed sprints (sqlalchemy through site-audit); marked SQLAlchemy ORM as DONE in What's Planned | T-site-audit-all |

| 2026-02-28 | TOC | Added §4b Daily LLM Visibility Tracker with 12 subsection links | T-DT-integration |
| 2026-02-28 | §4b | **NEW SECTION** — Daily LLM Visibility Tracker: 12 subsections covering overview, design patterns (Mediator/Strategy/Adapter/Protocol), 5 protocol interfaces, orchestrator pipeline flow, prompt library, platform runner adapter, mention detector, analytics engine with 4 metric calculators, 16 API endpoints (8 prompt CRUD + 3 run management + 5 analytics), DI wiring with 3 factory functions + _DbResponseDataProvider adapter, Pydantic models (11 models), ORM tables (3 tables + 3 repositories + migration 0005) | T-DT-integration |
| 2026-02-28 | §21.2 | Added Daily LLM Visibility Tracker endpoint reference (16 endpoints) with auth and tenant isolation details | T-DT-integration |

| 2026-03-02 | §7 | Updated Content Engine: added v1.3 architecture (6-stage pipeline, 2 new agents, 3 HITL, LiteLLM, LangSmith, E-E-A-T, dual feedback), 14 new files documented, DB persistence (2 functions) | T-v13-E2 |
| 2026-03-02 | §15 | Added Content Engine v1.3 test coverage table: 257 new tests across 12 files (context_router 25, llm_client 12, v13_models 10, strategic_planner 15, brief_builder 20, eeat_judge 10, tracing 8, evaluator 8, graph 49, pipeline 14, persistence 12, API 28). 5 router bugs found via TDD | T-v13-E2 |
| 2026-03-02 | §21 | Added Content Generation Pipeline v1.3 endpoint reference (5 endpoints), entry modes, 3 HITL approval flow, approval_payload pattern | T-v13-E2 |
| 2026-03-02 | §7.2 | Updated v1.3 worker chain: Outliner→Drafter→Linker→Fact Checker; added Linker and Fact Checker (verify-only) descriptions | T-ce-v13-refactor |
| 2026-03-02 | §7.3 | Updated evaluate_and_optimize signature (use_eeat, use_targeted_revision, 3-tuple return); added E-E-A-T dimension; added v1.3 dual feedback routing (classify_feedback, _get_targeted_revision_plan, early-stop logic) | T-ce-v13-refactor |
| 2026-03-02 | §7.4 | Added v1.3 HITL-3 feedback loops: edit→drafter (max 2), reject→re-brief (max 2), major_change→auto re-brief, _apply_human_edits(), _rebrief_and_rerun() | T-ce-v13-refactor |
| 2026-03-02 | §7.6 | Added v1.3 artifact structure (linked.md, fact_checked.md, blueprints.json, planner_output.json) | T-ce-v13-refactor |
| 2026-03-02 | §10 | Added LinkedDraft model, voice_tone_description on ContentOutline, FeedbackRoute literal, "eeat" dimension; added v1.3 models subsection (TopicSelection, ContentBlueprint, ContentGenerationInputV13, WorkerQueryContext, PlannerScorecard) | T-ce-v13-refactor |

| 2026-03-06 | TOC | Added §5c Knowledge Base Pipeline (Research v2) with 9 subsection links | T-kb-phase5-synthesis-living-doc |
| 2026-03-06 | §1 | Updated Executive Summary — ~2479 tests, Knowledge Base v2 description (5 specialist agents, DAG execution, delta synthesis, staleness tracking, 260 tests) | T-kb-phase5-synthesis-living-doc |
| 2026-03-06 | §5c | **NEW SECTION** — Knowledge Base Pipeline: 9 subsections covering 3-layer architecture, DAG execution with 3 HITL checkpoints, 6 specialist agents, KBStorage versioned filesystem, staleness tracking & propagation (Phase 5), delta synthesis mode (Phase 5), health & refresh-stale endpoints (Phase 5), 17 Pydantic models, 260 tests. Codex-reviewed (CRITICAL write-before-approve fix, atomic manifest writes, DAG dependency population). | T-kb-phase5-synthesis-living-doc |
| 2026-03-06 | §7 | **MAJOR REWRITE** — Content Engine V1.3: expanded from 7 subsections to 15 (7.1–7.15). Added LiteLLM client (auto-prefix routing, jittered backoff), LangSmith prompt registry (TTL-cached, double-checked locking), LangSmith tracing architecture (RunTree, contextvars propagation, backward-compat Langfuse kwargs), ContextRouter (two-phase loading, PlannerScorecard, WorkerQueryContext), Strategic Planner (topic selection, 100K token truncation), Brief Builder (parallel blueprints, semaphore, re-brief ID overrides), 5-agent worker chain (Outliner→Drafter→Fact Enricher→Formatter→Linker), Evaluator-Optimizer loop (3 judges, targeted revision, FeedbackRoute dispatch), HITL Stage 5 (per-brief approve/edit/reject/major_change/re-brief), v1.0 preservation, entry modes, 12 Pydantic models, artifact structure, utility modules, input sources | T-v13-docs |
| 2026-03-06 | §5c | **MAJOR REWRITE** — Knowledge Base Pipeline: expanded from 9 subsections to 13 (5c.1–5c.13). Added prompt system (6 prompt files with Hub fallback), read_file tool, HITL mini-graphs (approve/revise/reject interrupt model), LangSmith tracing integration. Expanded agent details: 3-tier architecture (Perplexity/Anthropic+web_search/LangGraph react), brand perception pause_turn loop (_MAX_PAUSE_TURNS=5), synthesis partial failure policy (CX-14, min 3/5 L2 docs), atomic manifest writes (tempfile.mkstemp + os.replace) | T-kb-docs |
| 2026-03-06 | §4a | **MAJOR REWRITE** — Site Audit: expanded from 12 subsections to 14 (4a.1–4a.14). Added P3 bug fix section, pipeline orchestration details, page-normalised scoring algorithm, detailed check function reference tables (21 finding types with severities), AEO composite scoring (5 components with weights), 7 schema validators, config dataclass (14 fields, 8 post-init validators), canonical URL deduplication, crawl-delay parsing/findings, dateutil robust parsing with DoS guard, 793 tests | T-site-audit-docs |
| 2026-03-06 | Header | Updated stack: Langfuse v3 → LangSmith + LiteLLM. Updated document date description | T-docs-xref |
| 2026-03-06 | TOC | Updated §4a (12→14 subsections), §5c (9→13 subsections), §7 (7→15 subsections) | T-docs-xref |
| 2026-03-06 | §1 | Updated executive summary: Content Engine v1.3 description, LangSmith replaces Langfuse, updated test counts | T-docs-xref |
| 2026-03-06 | §3 | Updated architecture diagram: Langfuse v3 → LangSmith, added LiteLLM to tech stack table | T-docs-xref |
| 2026-03-06 | §11 | Updated env vars: Langfuse section replaced with LangSmith (5 vars) | T-docs-xref |
| 2026-03-06 | §17 | Rewrote Decision 11: Langfuse → LangSmith migration rationale, RunTree, contextvars, shared module | T-docs-xref |
| 2026-03-06 | §18 | Updated item 11: Langfuse v2 resolved → Langfuse removed, replaced by LangSmith | T-docs-xref |
| 2026-03-06 | §20 | Updated component maturity table: site audit 793 tests, content engine v1.3 437 tests, LangSmith tracing, KB 260 tests. Added 3 sprint entries (content-engine-v13, site-audit-p3-bugfixes, knowledge-base-v1-v5) | T-docs-xref |
| 2026-03-06 | §A | Updated API key matrix: Langfuse → LangSmith, added 3 KB agent entries | T-docs-xref |

| 2026-03-07 | TOC | Added §5d Audience Persona Pipeline (Research v3) with 9 subsection links | T-ap-docs |
| 2026-03-07 | §1 | Updated Executive Summary — ~2568 tests, Audience Persona v2 description, CPS standalone endpoint, updated pipeline 3 description | T-ap-cps-docs |
| 2026-03-07 | §4 | Added `core/models/audience_persona.py`, `core/research/audience_persona/` (5 files), `core/cps_model/` (9 files), `core/research/prompts/` persona files, `api/routers/audience_persona.py`, `api/routers/cps.py`, `api/schemas/audience_persona.py`, `api/schemas/cps.py` to directory structure | T-ap-cps-docs |
| 2026-03-07 | §5d | **NEW SECTION** — Audience Persona Pipeline (Research v3): 9 subsections covering 2-agent architecture (Gemini Flash suggester + Perplexity generator), 2 HITL checkpoints (brief approval + profile review), PersonaStorage versioned filesystem, KB staleness integration, frozen ID map, 9 Pydantic models, 7 API endpoints, 232 tests | T-ap-phase-d |
| 2026-03-07 | §18 | Updated test coverage: ~2568 tests with AP (232), KB (260), CPS (44), site audit (793), content engine (437) breakdowns | T-ap-cps-docs |

| 2026-03-07 | §6.1 | Added Company Page Structural Analysis subsection — s1 computes ~45 structural signals per company page via s4's `compute_structural_signals()`, saves to `company_page_analysis.json` | D-GCE-2 |
| 2026-03-07 | §6.4 | Added `compute_structural_signals()` public API, self-citation flag propagation through dedup | D-GCE-3 |
| 2026-03-07 | §6.6 | Added items 9-11: company URL passthrough (`best_company_url`), self-citation detection (`company_cited`, `company_cited_platforms`), company structural signals (`best_company_structural_signals`) on QueryGap | D-GCE-1/2/3 |
| 2026-03-07 | §6.8 | Updated gap report to include company page URL, self-citation status, and company page structural summary per gap | D-GCE-1/3 |
| 2026-03-07 | §6.10 | Updated data flow diagram — `company_page_analysis.json` from s1, `_flag_company_citations` + `_build_company_citation_map` between s3/s4, enriched s6 inputs | D-GCE-all |
| 2026-03-07 | §7.4 | Updated context router: `company_cited` in QueryScorecard, `company_best_url` in WorkerQueryContext, `Cited` column in scorecard markdown, structural comparison in worker context markdown | D-GCE-all |
| 2026-03-11 | TOC | Added §5f Research Orchestrator with 5 subsection links | T-research-orchestrator |
| 2026-03-11 | §5f | **NEW SECTION** — Research Orchestrator (KB → AP → VSG DAG): sequential pipeline chaining, skip logic (artifact freshness), HITL pass-through (shared task_id), auto-approve distribution, error propagation, tenant-isolated API endpoints. 67 tests (50 core + 17 API). Codex-reviewed (8 findings, 5 fixed, 2 deferred to backlog). | T-research-orchestrator |

---

*End of Comprehensive System Documentation*
*Generated: 2026-03-07 (updated: Gap Analysis → Content Engine data enrichment — 3 features)*
*Total codebase files analyzed: ~380+*
*Total lines of documentation: ~9300+*
