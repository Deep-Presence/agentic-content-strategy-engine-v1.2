# Content Strategy Engine — Comprehensive System Documentation

> **Project:** Deep Presence Content Strategy Engine (formerly AEO-Optimizer)
> **Owner:** Aryan (CTO & Co-founder, Deep Presence)
> **Stack:** Python 3.12 · LangGraph · DeepAgents · FastAPI (planned) · SQLAlchemy (planned) · Pydantic v2
> **Document Date:** 2026-02-15
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
7. [Pipeline 3: Content Generation Engine (Planned)](#7-pipeline-3-content-generation-engine-planned)
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
21. [Appendix A: Model & API Key Matrix](#appendix-a-model--api-key-matrix)
22. [Appendix B: Artifact Naming Conventions](#appendix-b-artifact-naming-conventions)
23. [Appendix C: Code Standards & Conventions](#appendix-c-code-standards--conventions)

---

## 1. Executive Summary

The **Content Strategy Engine** is a multi-agent AI platform that automates the end-to-end workflow of content strategy for B2B companies. It operates across three sequential pipelines:

1. **Research Artifacts Pipeline** (implemented) — Uses LLM agents with web research tools to produce company context documents, audience persona profiles, and writing style guides. Each artifact goes through a human-in-the-loop approval flow (approve / revise / reject) before being finalized.

2. **Gap Analysis Pipeline** (implemented) — An 8-step data pipeline that embeds a company's web content, generates buyer-intent search queries, searches four AI platforms (ChatGPT, Claude, Perplexity, Google AI Overview), enriches the citations those platforms return, embeds everything into a shared vector space, computes semantic proximity analysis (SPA), generates interactive visualizations, and produces a gap report with actionable content recommendations.

3. **Content Generation Engine** (planned) — Will consume the outputs of Pipelines 1 and 2 to automatically generate optimized content pieces that close the identified citation gaps.

Additionally, a **Reddit Human-in-the-Loop Monitor** (implemented) monitors subreddits for threads matching a company's ICP persona, drafts contextual replies, and sends notifications via Slack/Discord.

The system is designed as a **CLI-first platform** (no API server yet), with all business logic in a `core/` Python package. Artifacts are persisted to the local filesystem as the source of truth, with optional versioned mirroring to Supabase. The codebase is structured for eventual deployment behind a FastAPI server with a frontend.

**Current production clients analyzed:** Ramp (corporate spend management) and Carta (equity management platform).

---

## 2. What This System Does — The Business Problem

### The Problem: AI Search Engine Optimization (AEO)

Traditional SEO optimizes for Google's link-based ranking. But the rise of AI-powered search (ChatGPT, Claude, Perplexity, Google AI Overview) introduces a new challenge: **AI Engine Optimization (AEO)**. When a user asks an AI assistant "What's the best spend management tool?", the AI synthesizes an answer by citing various sources. If your company's content isn't structured in a way that AI models can understand and cite, you become invisible in AI-assisted discovery.

### The Solution: Deep Presence Content Strategy Engine

This system answers three questions:
1. **"Who are we, who are our customers, and how should we write?"** → Research Artifacts Pipeline
2. **"Where are we being cited vs. where are we invisible in AI search?"** → Gap Analysis Pipeline
3. **"What content should we create to fill those gaps?"** → Content Generation Engine (planned)

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
    Content Generation (planned)
    (Create optimized content that AI models will cite)
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
│  ┌──────────────────┐   ┌───────────────────┐   ┌─────────────────────┐  │
│  │   Pipeline 1:    │   │   Pipeline 2:     │   │   Pipeline 3:       │  │
│  │   Research       │──▶│   Gap Analysis    │──▶│   Content Generation│  │
│  │   Artifacts      │   │   (8-step)        │   │   (planned)         │  │
│  └────────┬─────────┘   └────────┬──────────┘   └─────────────────────┘  │
│           │                      │                                       │
│           ▼                      ▼                                       │
│  ┌─────────────────────────────────────────┐                             │
│  │           Artifact Storage               │                            │
│  │  Filesystem (SoT) ◀──▶ Supabase Mirror  │                             │
│  │  ChromaDB (vectors)                      │                            │
│  └─────────────────────────────────────────┘                             │
│                                                                          │
│  ┌─────────────────┐                                                     │
│  │  Reddit HIL     │  (Independent monitoring system)                    │
│  │  Monitor        │                                                     │
│  └─────────────────┘                                                     │
│                                                                          │
│  External Services:                                                      │
│  • Perplexity (sonar-deep-research)  • Google Gemini (3-flash-preview)   │
│  • OpenAI (text-embedding-3-large)   • Anthropic Claude (sonnet-4.5)     │
│  • Reddit (PRAW read-only)           • Slack / Discord (webhooks)        │
│  • Supabase (PostgREST + Storage)    • ChromaDB (local vector DB)        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.12+ | All business logic |
| **Agent Framework** | DeepAgents | LLM agent creation with tool-use, backends, memory |
| **Orchestration** | LangGraph v0.2+ | State machine graphs with interrupt-based human-in-the-loop |
| **Data Validation** | Pydantic v2 | Input/output schemas, settings management |
| **Web Research** | Perplexity SDK (sonar-deep-research) | Deep web research with citations |
| **LLM Providers** | Google Gemini, Anthropic Claude, OpenAI GPT | Agent reasoning, query gen, reports |
| **Embeddings** | OpenAI text-embedding-3-large (3072-dim) | Semantic similarity in gap analysis |
| **Vector Store** | ChromaDB (local, persistent) | Embedding storage and retrieval |
| **Database** | Supabase (PostgreSQL 17 + pgvector) | Optional artifact mirroring, versioning |
| **Visualization** | Plotly | Interactive HTML charts (UMAP, t-SNE, heatmaps) |
| **Dimensionality Reduction** | UMAP, t-SNE (scikit-learn) | Embedding space visualization |
| **Web Crawling** | Playwright, httpx, BeautifulSoup4 | Site crawling and HTML extraction |
| **Reddit** | PRAW (read-only) | Subreddit monitoring |
| **Notifications** | Slack Block Kit, Discord Webhooks | Alert delivery |

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
│   ├── content_engine/                    # Pipeline 3: Content Generation (FUTURE — empty)
│   │   └── __init__.py
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
│       ├── embedding_client.py            # embed_texts() — OpenAI text-embedding-3-large wrapper (42 lines)
│       └── chroma_client.py               # ChromaDB persistent client with company/citation collections (184 lines)
│
├── scripts/                               # CLI entry points (all use argparse)
│   ├── run_company_research.py            # Standalone company research (74 lines)
│   ├── run_persona_research.py            # Standalone persona research (80 lines)
│   ├── run_style_guide_research.py        # Standalone style guide research (83 lines)
│   ├── run_pipeline.py                    # Combined 3-stage research pipeline (132 lines)
│   ├── run_gap_analysis.py                # Full 8-step gap analysis (74 lines)
│   ├── run_gap_step.py                    # Individual gap step runner for debugging (340 lines)
│   ├── resolve_vertexai_redirects.py      # Utility: resolve Vertex AI redirect URLs (140 lines)
│   └── strip_embeddings_from_json.py      # Utility: remove embedding vectors from JSON (67 lines)
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
├── tests/                                 # ⚠️ EMPTY — No tests implemented
│   ├── conftest.py                        # 1-line stub: `# pytest configuration & shared fixtures`
│   ├── research/                          # Empty
│   ├── gap_analysis/                      # Empty
│   └── content_engine/                    # Empty
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
- Embeds all texts using OpenAI `text-embedding-3-large` (3072 dimensions)
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

**Purpose:** For each unique citation URL found in Step 3, fetch the actual HTML page, extract content paragraphs, and classify the content's structural and authority signals.

**Process:**
1. **De-duplication:** One citation per unique URL (collapsed across all engines and queries)
2. **HTML Fetching:** Async HTTP GET with 20-second timeout, follows redirects
3. **Content Extraction:** BeautifulSoup parsing of p, li, h2, h3 tags
4. **Structural Signal Extraction:**

| Signal | Measurement |
|--------|-------------|
| `word_count` | Total words in extracted content |
| `paragraph_count` | Number of content paragraphs |
| `header_count` | Number of H2/H3 headers |
| `list_item_count` | Number of list items |
| `stat_count` | Count of numbers/statistics in text |
| `citation_count` | Count of outbound links |
| `authority_type` | `.gov` → government, `.edu` → academic, `.org` → nonprofit, else commercial |
| `content_type` | Inferred: blog, guide, faq, docs, research, case_study |

**Output:** `enriched_citations.json` — List of `EnrichedCitation` with paragraphs and structural signals.

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
- On batch failure: retry one-by-one with zero-vector fallback (3072-dim zero vector)

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
Top-3 cited pages per query with: similarity score, domain, URL, snippet, structural signals, authority type.

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

**Purpose:** Produce the final gap analysis report (Markdown + JSON) and generation specifications.

**2-Phase Generation:**

**Phase A: Programmatic Reports**
- `gap_report.md` — Summary + top-10 gap briefs with SPA score, proximity stats, per-gap details (cluster, company unit, citation similarities, interpretation, exemplars) + full gaps appendix table
- `generation_spec.md` — Per-cluster content generation specs (query count, word count range, required elements, authority signals, structural rates, min similarity threshold)
- JSON versions of both

**Phase B: LLM-Generated Summary**
- Calls OpenAI (GPT-5.2) with focused prompt
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
```

**Key Artifact Dependencies:**
- S2 requires: `company_context_path` (reads company artifact from disk)
- S2 requires: `persona_paths` (reads persona artifacts from disk)
- S2 requires: `style_guide_path` (reads style guide from disk)
- S2 requires: query taxonomy file (`b2b_queries_180.json` — hardcoded path)
- S5 requires: ChromaDB collection from S1 (for company embedding IDs)
- S6 requires: ChromaDB collections from S1 + S5 (for embedding vectors)

---

## 7. Pipeline 3: Content Generation Engine (Planned)

**Status:** Not yet implemented. Only an empty `core/content_engine/__init__.py` exists.

**Planned Architecture (from CLAUDE.md):**

```
Planner Agent
    ↓
  Identifies topics/prompts from research + gap analysis
    ↓
  Spawns Sub-Agentic Systems (one per content brief)
    ↓
  Each sub-system:
    ┌─────────────────────┐
    │  Planner-Manager     │
    │    ↓                 │
    │  Worker Agents       │  (research, write, cite)
    │    ↓                 │
    │  Evaluator Agent     │  (quality + citation probability)
    │    ↓                 │
    │  Citation Score Check│
    └─────────────────────┘
    ↓
  Publish (if score passes threshold)
```

**Expected Input:**
- `generation_spec.json` from Pipeline 2 (cluster content specs)
- Research artifacts from Pipeline 1 (company context, personas, style guide)
- Gap report from Pipeline 2 (prioritized content recommendations)

**Expected Output:**
- Optimized content pieces stored in `/artifacts/content/`
- Each piece evaluated against citation probability thresholds

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
StructuralSignals:   word_count, paragraph_count, header_count, list_item_count,
                     stat_count, citation_count, has_headers, has_lists, has_numbers,
                     authority_type, content_type
EnrichedCitation:    url, domain, title, query_id, cluster_name, engine,
                     paragraphs, best_paragraphs, structural_signals
```

**Analysis Models:**
```
SpaResult:           cluster_id, cluster_name, t_stat, p_value,
                     mean_citation_sim, mean_company_sim, effect
CentroidResult:      cluster_id, cluster_name, query_centroid, citation_centroid, distance
QueryGap:            query_id, cluster_name, query_text, best_company_unit,
                     best_company_similarity, avg_citation_similarity, gap, interpretation,
                     top_cited_exemplars
ClusterContentSpec:  cluster_id, cluster_name, query_count, word_count_range,
                     min_similarity_threshold, required_elements, authority_signals,
                     structural_rates, total_citations_analyzed
AnalysisResult:      proximity_stats, spa_results, centroids, gaps, citation_patterns,
                     decision_metrics, cluster_specs
GapReport:           report_md, report_json, generation_spec_md, generation_spec_json,
                     visualization_paths
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
| `OPENAI_API_KEY` | — | Embeddings (text-embedding-3-large) + query gen + reports |
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
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model |
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

### Current State: ZERO TEST COVERAGE

```
tests/
├── conftest.py              # 1-line stub: `# pytest configuration & shared fixtures`
├── research/                # Empty
├── gap_analysis/            # Empty
└── content_engine/          # Empty
```

There are **no test files** in the entire project.

### Required Test Coverage (per CLAUDE.md)

#### Research Pipeline Tests
- [ ] Company research agent invocation (mock Perplexity + Gemini)
- [ ] Persona research agent invocation (mock APIs, verify 1-3 persona creation)
- [ ] Style guide research agent invocation (mock APIs)
- [ ] Full 3-stage pipeline orchestration (company → persona → style)
- [ ] Approval flow: approve / revise / reject paths (all 3 branches)
- [ ] Artifact file I/O: draft creation, promotion to final
- [ ] Cross-stage context passing (company path feeds into persona input)
- [ ] `--auto-approve` flag bypasses interrupt
- [ ] `--overwrite` flag behavior
- [ ] Supabase mirroring (mock Supabase client)

#### Gap Analysis Tests
- [ ] All 8 steps independently (mock API calls, verify outputs)
- [ ] Step-to-step data flow and dependency validation
- [ ] ChromaDB embedding hydration
- [ ] Platform search result aggregation (mock all 4 engines)
- [ ] Citation enrichment (mock HTTP fetches)
- [ ] SPA computation correctness (synthetic data)
- [ ] Visualization generation (verify HTML output)
- [ ] Report generation (verify Markdown structure)
- [ ] Skip-step functionality
- [ ] Platform subset selection

#### Reddit HIL Tests
- [ ] PRAW read-only enforcement
- [ ] Thread ranking and filtering
- [ ] Keyword extraction from persona
- [ ] LLM drafting (mock Gemini)
- [ ] Webhook delivery (mock Slack/Discord)
- [ ] Dedup cache persistence

#### CLI Script Tests
- [ ] Argument parsing and validation
- [ ] Default value behavior
- [ ] Exit codes and error handling

#### Required Fixtures
- [ ] Sample HTML content (for parsing tests)
- [ ] Mock API responses (Perplexity, Gemini, Claude, OpenAI)
- [ ] Sample artifact Markdown files
- [ ] Sample JSON fixtures (queries, embeddings, citations, analysis)
- [ ] Mock Supabase client
- [ ] Mock ChromaDB client
- [ ] Temporary directory fixtures

---

## 16. Dependency Graph

### Python Package Dependencies

```
pydantic v2.5+
├── BaseModel (all 30+ schemas)
├── Field validators
├── HttpUrl type
└── model_copy() for cross-stage wiring

pydantic-settings v2.0+
└── BaseSettings (core/config/settings.py)

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
├── numpy, scipy, scikit-learn → Statistics + cosine similarity
├── umap-learn → UMAP dimensionality reduction
├── plotly → Interactive HTML visualizations
├── beautifulsoup4 → HTML content extraction
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
core/models/* ← Used by graphs, agents, pipeline, mirror
        ↓
core/shared_tools/* ← Used by gap analysis steps
        ↓
core/storage/* ← Used by research graphs (mirror after approval)
        ↓
core/research/agents/* ← Used by research graphs
        ↓
core/research/graphs/* ← Used by scripts
core/gap_analysis/* ← Used by scripts
core/reddit_hil/* ← Used by CLI
        ↓
scripts/* ← User entry points
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

---

## 18. Known Vulnerabilities, Flaws & Technical Debt

### Critical Issues

#### 1. ZERO TEST COVERAGE
**Severity:** Critical
**Description:** The entire codebase has no automated tests. The `tests/` directory contains only an empty `conftest.py` stub.
**Impact:** No regression protection. Any refactoring or feature addition could silently break existing functionality. No CI/CD quality gate.
**Recommendation:** Implement tests in priority order: (1) approval flow branches, (2) cross-stage context passing, (3) gap analysis data flow, (4) CLI argument parsing.

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
**Description:** Zero-vector fallback uses hardcoded 3072 dimensions (for text-embedding-3-large). If the embedding model changes, this silently produces wrong-dimension vectors.
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

### Data Quality & Operational Concerns

#### 11. Vertex AI Redirect URLs
**Description:** The Gemini search engine sometimes returns Vertex AI Search redirect URLs (`vertexaisearch.cloud.google.com/...`) instead of direct URLs. A utility script exists to resolve these, but it's a manual post-processing step.
**Location:** `scripts/resolve_vertexai_redirects.py`
**Impact:** Enriched citations may contain unresolvable URLs until manually fixed.
**Recommendation:** Integrate redirect resolution into Step 4 (enrich citations) automatically.

#### 12. PDF Detection Fragility
**Description:** PDF detection in Step 4 uses basic string matching (`"%PDF-"` signature). Could miss some PDFs or false-positive on text containing the PDF signature.
**Location:** `core/gap_analysis/steps/s4_enrich_citations.py`
**Impact:** Some binary content may slip through to embedding, producing garbage vectors.
**Recommendation:** Use Content-Type headers and more robust binary detection.

#### 13. ChromaDB Not Production-Ready for Multi-Tenant
**Description:** ChromaDB runs locally with file-based persistence. Not suitable for multi-user production deployment.
**Impact:** Single-machine limitation. No concurrent access from multiple processes.
**Recommendation:** Migrate to pgvector (Supabase) for production. ChromaDB remains appropriate for local development.

#### 14. Hardcoded Default Paths in Utility Scripts
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
| Reddit HIL Monitor | ✅ Functional | Medium — tested with Ramp |
| Supabase Schema | ✅ Production | High — 4 migrations, RLS, HNSW |
| Supabase Mirror | ✅ Functional | Medium — works but no SQLAlchemy ORM |
| CLI Scripts | ✅ Functional | Medium — works but no error handling |

### What's Planned (Future Scope)

| Priority | Component | Description | Dependencies |
|----------|-----------|-------------|--------------|
| 1 | **Content Generation Engine** | Planner → Sub-Agents → Evaluator → Publish | Pipeline 1 + 2 outputs |
| 2 | **FastAPI Backend** | REST API + WebSocket pipeline events | All core modules |
| 3 | **SQLAlchemy ORM** | Replace raw Supabase client with ORM | Supabase schema |
| 4 | **Frontend** | Web UI for artifact review, gap visualization, pipeline management | FastAPI backend |
| 5 | **Comprehensive Tests** | pytest + pytest-asyncio, mock all APIs | Existing codebase |
| 6 | **Persistent Agent Store** | Replace InMemoryStore with durable storage | DeepAgents integration |
| 7 | **Cloud Storage Backends** | S3/GCS/Supabase Storage implementations | StorageBackend interface |
| 8 | **Structured Logging** | JSON logging with correlation IDs | logging_config.py |
| 9 | **CI/CD Pipeline** | Automated tests, linting, deployment | Tests + Docker |

### Content Generation Engine — Planned Design

```
Input:
  ├── generation_spec.json (from Pipeline 2 — per-cluster content specs)
  ├── gap_report.json (prioritized content recommendations)
  ├── Research artifacts (company context, personas, style guide)
  └── Cluster content specs (word count, structure, authority signals)

Architecture:
  ┌───────────────────┐
  │  Planner Agent     │  Analyzes gap report + generation specs
  │  (strategic)       │  Identifies top-priority content pieces
  └────────┬──────────┘
           │ spawns N sub-systems (one per content brief)
           ▼
  ┌───────────────────┐
  │  Sub-Agent System  │ × N
  │  ┌──────────────┐ │
  │  │Planner-Manager│ │  Plans content structure + research needs
  │  └──────┬───────┘ │
  │         ▼         │
  │  ┌──────────────┐ │
  │  │Worker Agents  │ │  Research + write sections + add citations
  │  └──────┬───────┘ │
  │         ▼         │
  │  ┌──────────────┐ │
  │  │Evaluator     │ │  Quality check + citation probability score
  │  └──────┬───────┘ │
  │         ▼         │
  │  Citation Score    │  Must exceed threshold (from cluster_spec)
  │  Check → Pass/Fail │
  └───────────────────┘
           │
           ▼
  ┌───────────────────┐
  │  Publisher          │  Write to artifacts/content/{slug}/
  └───────────────────┘
```

---

## Appendix A: Model & API Key Matrix

| Component | Model | API Key Variable | Default Model |
|-----------|-------|------------------|---------------|
| Company Research Agent | Gemini | `GOOGLE_API_KEY_COMPANY_DEEPAGENT` | `gemini-3-flash-preview` |
| Persona Research Agent | Gemini | `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT` | `gemini-3-flash-preview` |
| Style Guide Research Agent | Gemini | `GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT` | `gemini-3-flash-preview` |
| DeepAgents (default) | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Perplexity Research | Sonar | `PERPLEXITY_API_KEY` | `sonar-deep-research` |
| Embeddings | OpenAI | `OPENAI_API_KEY` | `text-embedding-3-large` |
| Gap: Query Generation | OpenAI | `OPENAI_API_KEY` | `gpt-5.2-2025-12-11` |
| Gap: Report Generation | OpenAI | `OPENAI_API_KEY` | `gpt-5.2-2025-12-11` |
| Gap: OpenAI Search Engine | OpenAI | `OPENAI_API_KEY` | `gpt-5.2-2025-12-11` |
| Gap: Claude Search Engine | Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` |
| Gap: Gemini Search Engine | Gemini | `GOOGLE_API_KEY_GAP_ANALYSIS` | `gemini-3-flash-preview` |
| Gap: Perplexity Search Engine | Sonar | `PERPLEXITY_API_KEY` | `sonar-pro` |
| Reddit HIL Monitor | Gemini | `GOOGLE_API_KEY_REDDIT_HIL` | `gemini-3-flash-preview` |

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
```

---

*End of Comprehensive System Documentation*
*Generated: 2026-02-15*
*Total codebase files analyzed: ~60+*
*Total lines of documentation: ~1800+*
