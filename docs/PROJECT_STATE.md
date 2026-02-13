# AEO-Optimizer Content Engine -- Project State

> Last updated: 2026-02-12

## 1. What This Project Is

The **AEO-Optimizer Content Engine** is a multi-agent system that automates company research, audience persona generation, writing style-guide creation, content gap analysis, and Reddit engagement monitoring. It uses LangGraph for workflow orchestration, DeepAgents for agentic tool-use, and multiple LLM providers (Google Gemini, Anthropic Claude, OpenAI, Perplexity) to produce structured Markdown artifacts.

The system is designed around a **filesystem-first, DB-mirror** architecture: artifacts live on disk as the source of truth and are optionally mirrored to Supabase for versioning and centralized access.

---

## 2. Directory Structure

```
aeo-optimizer/
├── .env.local                          # Production-like env vars (API keys)
├── .env.test.local                     # Test env vars
├── requirements.in                     # Top-level pinned dependencies
├── venv/                               # Python 3.12 virtual environment
│
├── content-engine/                     # *** PRIMARY MODULE ***
│   ├── README.md
│   ├── requirements.txt                # Python dependencies
│   │
│   ├── artifacts/                      # Persisted agent outputs (source of truth)
│   │   ├── company_context/            # {slug}.md, {slug}.draft.md
│   │   ├── personas/                   # {slug}__persona-icp.md, -2.md, -3.md
│   │   ├── style_guides/              # {slug}.md
│   │   ├── gap_analysis/              # {slug}/ (per-company subdirs)
│   │   ├── _logs/                     # Runtime logs
│   │   │   └── reddit_monitor/        # {slug}__seen.json (dedup cache)
│   │   └── _shared/                   # Shared templates (empty)
│   │
│   ├── scripts/                        # CLI entry points
│   │   ├── run_company_research.py
│   │   ├── run_persona_research.py
│   │   ├── run_gap_analysis.py
│   │   └── run_pipeline.py            # Full 3-stage orchestrator
│   │
│   ├── src/
│   │   ├── settings.py                # Pydantic BaseSettings (all env vars)
│   │   │
│   │   ├── agents/                    # DeepAgent definitions
│   │   │   ├── company_research_agent.py
│   │   │   ├── persona_agent.py
│   │   │   └── style_guide_agent.py
│   │   │
│   │   ├── graphs/                    # LangGraph state machines
│   │   │   ├── company_research.py
│   │   │   ├── persona_research.py
│   │   │   ├── style_guide.py
│   │   │   ├── reddit_hil_monitor.py
│   │   │   └── pipeline.py           # Master orchestrator
│   │   │
│   │   ├── models/                    # Pydantic schemas
│   │   │   ├── artifacts.py           # CompanyResearchInput, CompanyContextArtifact
│   │   │   ├── personas.py            # PersonaResearchInput, PersonaArtifact
│   │   │   ├── style_guide.py         # StyleGuideResearchInput, WritingStyleGuideArtifact
│   │   │   ├── reddit_hil.py          # RedditMonitorInput, RedditThread, DraftNotification
│   │   │   └── gap_analysis.py        # GapAnalysisInput, SemanticUnit, GapReport, etc.
│   │   │
│   │   ├── tools/                     # External service wrappers
│   │   │   ├── perplexity_client.py   # Perplexity Deep Research (sonar-deep-research)
│   │   │   ├── reddit_client.py       # PRAW read-only Reddit client
│   │   │   └── webhooks.py            # Slack + Discord notifications
│   │   │
│   │   ├── storage/                   # Persistence adapters
│   │   │   ├── supabase_client.py     # Supabase connection singleton
│   │   │   └── supabase_artifact_mirror.py  # Mirror artifacts to Supabase
│   │   │
│   │   ├── gap_analysis/              # 8-step gap analysis pipeline
│   │   │   ├── pipeline.py            # Main orchestrator
│   │   │   ├── engines/               # LLM backends (Claude, Gemini, OpenAI, Perplexity)
│   │   │   └── steps/                 # s1_embed_assets .. s8_generate_report
│   │   │
│   │   └── cli/
│   │       └── reddit_hil.py          # Reddit HIL CLI entry point
│   │
│   ├── data/                          # Raw/processed data (currently empty)
│   │   ├── raw/
│   │   ├── processed/
│   │   └── tmp/
│   │
│   └── tests/                         # Test suite (currently empty)
│
├── supabase/                           # Supabase config + migrations
│   ├── config.toml
│   └── migrations/
│       ├── 20250206120000_initial_schema.sql
│       ├── 20251209105957_remote_schema.sql
│       ├── 20251227120000_artifact_versions.sql
│       └── 20260207120000_rls_enums_hnsw.sql
│
├── flow-diagram/                       # Architecture visualizations (Excalidraw, SVG)
├── misc/                               # Reference docs, PDFs, artifact guides
├── similarweb-scraper/                 # SimilarWeb scraper utility (Python/Selenium)
├── mcp_excalidraw/                     # MCP Excalidraw server (TypeScript/React)
└── chat_transcript/                    # Conversation logs
```

---

## 3. System Architecture

```
                            ┌──────────────────────────────────────────┐
                            │              PIPELINE                     │
                            │  (src/graphs/pipeline.py)                │
                            └──────┬───────────┬───────────┬───────────┘
                                   │           │           │
                          ┌────────▼──┐  ┌─────▼─────┐  ┌─▼──────────┐
                          │  Company   │  │  Persona  │  │ Style Guide│
                          │  Research  │  │  Research  │  │  Research  │
                          │  Graph     │─►│  Graph     │─►│  Graph     │
                          └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
                                │               │               │
                          ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
                          │  DeepAgent │  │  DeepAgent │  │  DeepAgent │
                          │  (Gemini)  │  │  (Gemini)  │  │  (Claude)  │
                          └──┬─────┬───┘  └──┬─────┬───┘  └──┬─────┬───┘
                             │     │         │     │         │     │
                      ┌──────▼┐ ┌──▼───┐     │     │         │     │
                      │Perplex│ │Local │     │     │         │     │
                      │Search │ │Files │     │     │         │     │
                      └───────┘ └──────┘     │     │         │     │
                                             │     │         │     │
              ┌──────────────────────────────────────────────────────────┐
              │                   ARTIFACT FILESYSTEM                    │
              │   /artifacts/company_context/  personas/  style_guides/  │
              └──────────────────────────┬───────────────────────────────┘
                                         │ (optional mirror)
                                 ┌───────▼───────┐
                                 │   SUPABASE     │
                                 │  (versioned)   │
                                 └───────────────┘

              ┌──────────────────────────────────────────────────────────┐
              │              STANDALONE SYSTEMS                          │
              │                                                          │
              │  Reddit HIL Monitor     Gap Analysis Pipeline            │
              │  (LangGraph)            (8-step, non-graph)             │
              │  fetch → rank → draft   embed → query → search →        │
              │  → Slack/Discord        enrich → embed → analyze →      │
              │                         visualize → report               │
              └──────────────────────────────────────────────────────────┘
```

### Data Flow Between Stages

1. **Company Research** runs first (standalone). Produces `/artifacts/company_context/{slug}.md`.
2. **Persona Research** reads the company context artifact. Produces `/artifacts/personas/{slug}__persona-*.md`.
3. **Style Guide** reads both company context + persona artifacts. Produces `/artifacts/style_guides/{slug}.md`.
4. **Reddit HIL Monitor** reads all three artifact types. Produces draft replies + webhook notifications.
5. **Gap Analysis** reads company context + personas. Produces reports + visualizations.

---

## 4. Agents

### 4.1 Company Research Agent

| Property | Value |
|----------|-------|
| File | `src/agents/company_research_agent.py` |
| LLM | Google Gemini (`gemini-3-flash-preview`) |
| Tools | `internet_search` (Perplexity), `read_local_text` |
| Backend | CompositeBackend: `/artifacts/` → FilesystemBackend, `/memories/` → StoreBackend, default → StateBackend |
| Output | Company Context Markdown artifact |

**What it researches:** Origin story, founding team, funding, product evolution, competitors, market position, target audience, customer quotes/reviews, pain points, and use cases.

### 4.2 Persona Research Agent

| Property | Value |
|----------|-------|
| File | `src/agents/persona_agent.py` |
| LLM | Google Gemini (`gemini-3-flash-preview`) |
| Tools | `internet_search` (Perplexity) |
| Backend | Shared from company_research_agent |
| Output | Up to 3 persona Markdown artifacts (ICP + 2 secondary) |

**Persona sections:** Persona Summary, Role & Context, Day-in-the-Life Mechanics, KPIs / What Success Means, Pain Points & Blockers, Buying Triggers, Trust Builders & Objections, Annoyances, Messaging Angles, Quotes, Sources.

### 4.3 Style Guide Agent

| Property | Value |
|----------|-------|
| File | `src/agents/style_guide_agent.py` |
| LLM | Claude Sonnet (`claude-sonnet-4-5-20250929`) via `deepagents_model` setting |
| Tools | `internet_search` (Perplexity) |
| Backend | Shared from company_research_agent |
| Output | Writing Style Guide Markdown artifact |

**Style guide sections:** Voice & Tone, Channel Variations, Show vs Tell, Sentence & Language Choices, Jargon / Terminology Rules, Audience Resonance, Product Positioning & Messaging Pillars, Do / Don't, Formatting & Structure, Sample Snippets, Sources.

### Key Pattern: All Agents

- Built with `deepagents.create_deep_agent(model, tools, system_prompt, backend, store)`
- Singleton pattern: lazy-initialized via `get_*_agent()` functions
- Return JSON `{ "written_paths": [...], "notes": "..." }` (persona + style guide) or raw Markdown (company)
- Support patch updates: if artifact exists, edit sections rather than rewrite

---

## 5. LangGraph Workflows

All three research graphs follow the same pattern:

```
agent → [write_temp_draft →] approval_gate → route → approve → write_and_mirror → END
                                                    → revise  → agent (loop)
                                                    → reject  → END
```

### 5.1 Company Research Graph (`src/graphs/company_research.py`)

| Node | Function | Purpose |
|------|----------|---------|
| `agent` | `_run_agent` | Invoke DeepAgent with ThreadPoolExecutor + timeout (900s) |
| `write_temp_draft` | `_write_temp_draft` | Write `.draft.md` to `/artifacts/company_context/` |
| `approval_gate` | `_approval_gate` | `interrupt()` for human review, or auto-approve |
| `route` | `_route` | Pass-through for conditional edges |
| `write_and_mirror` | `_write_and_mirror` | Write permanent `.md` + mirror to Supabase |

**State:**
```python
{
    "input": CompanyResearchInput,
    "auto_approve": bool,
    "revision_note": str | None,
    "artifact_md": str,
    "draft_path": str,
    "approval_decision": "approve" | "revise" | "reject",
    "output_path": str,
    "mirrored": bool,
}
```

### 5.2 Persona Research Graph (`src/graphs/persona_research.py`)

Same structure minus `write_temp_draft` (agent writes drafts directly). Handles multiple artifacts (ICP + secondary personas). Promotes `.draft.md` → `.md` on approval.

### 5.3 Style Guide Graph (`src/graphs/style_guide.py`)

Same structure as persona graph. Single artifact per company.

### 5.4 Reddit HIL Monitor Graph (`src/graphs/reddit_hil_monitor.py`)

Linear pipeline (no approval gate):

```
load_artifacts → fetch_candidates → dedupe_cache → rank_filter → draft_reply → notify → END
```

| Node | Purpose |
|------|---------|
| `load_artifacts` | Read company context, ICP persona, style guide from disk |
| `fetch_candidates` | Fetch recent threads from subreddits via PRAW |
| `dedupe_cache` | Filter out already-processed thread IDs |
| `rank_filter` | Extract persona keywords, heuristic scoring, select top-K |
| `draft_reply` | LLM (Gemini) ranks + drafts replies for top threads |
| `notify` | Send Slack/Discord webhooks, update seen cache |

### 5.5 Pipeline Orchestrator (`src/graphs/pipeline.py`)

Sequential orchestration:

```python
run_pipeline(company_input, persona_input?, style_input?, auto_approve=False)
```

1. `run_company_stage()` → extract `company_output_path`
2. `run_persona_stage()` → inject `company_context_path`, extract `persona_paths`
3. `run_style_stage()` → inject `company_context_path` + `persona_paths`

Each stage catches `GraphInterrupt` and returns `{"status": "interrupt", "stage": name, "values": payload}` so the caller can present approval UI and resume.

---

## 6. Gap Analysis Pipeline

**File:** `src/gap_analysis/pipeline.py`

A separate 8-step sequential pipeline (not LangGraph). Each step saves intermediate artifacts to `/artifacts/gap_analysis/{slug}/` and can be skipped with `--skip-step`.

| Step | File | What it does |
|------|------|--------------|
| 1 | `s1_embed_assets.py` | Embed company context + personas into semantic units |
| 2 | `s2_generate_queries.py` | Generate search queries clustered by intent/persona |
| 3 | `s3_search_platforms.py` | Search Perplexity, Google, OpenAI, etc. |
| 4 | `s4_enrich_citations.py` | Enrich citations with metadata + relevance |
| 5 | `s5_embed_content.py` | Embed queries + citations for vector comparison |
| 6 | `s6_analyze.py` | Compute SPA (Semantic Proximity Analysis), gap scores |
| 7 | `s7_visualize.py` | Generate charts and heatmaps |
| 8 | `s8_generate_report.py` | Produce final gap report (Markdown + JSON) |

**LLM Engines:** Supports Claude, Gemini, OpenAI, and Perplexity backends (`src/gap_analysis/engines/`).

---

## 7. Tools & Integrations

### 7.1 Perplexity Client (`src/tools/perplexity_client.py`)

- Model: `sonar-deep-research` (autonomous multi-step retrieval + synthesis)
- Function: `research(query)` → returns text with inline citations `[1]`, `[2]`, etc.
- Used by all three research agents for web search

### 7.2 Reddit Client (`src/tools/reddit_client.py`)

- Library: PRAW (read-only mode enforced)
- Function: `fetch_new_threads(subreddit, limit=25)` → `List[RedditThread]`
- Safety: Verifies `reddit.read_only == True` before any API calls

### 7.3 Webhooks (`src/tools/webhooks.py`)

- `send_slack(webhook_url, thread_url, ...)` → Slack Block Kit formatted messages
- `send_discord(webhook_url, ...)` → Discord embed messages
- Handles text chunking for payload size limits

---

## 8. Storage Architecture

### Filesystem (Source of Truth)

```
artifacts/
├── company_context/{slug}.md          # Final company context
├── company_context/{slug}.draft.md    # Draft (pending approval)
├── personas/{slug}__persona-icp.md    # ICP persona
├── personas/{slug}__persona-2.md      # Secondary persona 2
├── personas/{slug}__persona-3.md      # Secondary persona 3
├── style_guides/{slug}.md             # Writing style guide
├── gap_analysis/{slug}/               # Gap analysis outputs
│   ├── company_embeddings.json
│   ├── queries.json
│   ├── platform_results/
│   ├── enriched_citations.json
│   ├── embeddings/
│   ├── analysis.json
│   ├── visualizations/
│   ├── gap_report.md / .json
│   └── generation_spec.md / .json
└── _logs/reddit_monitor/{slug}__seen.json  # Dedup cache
```

### Supabase (Optional Versioned Mirror)

- **Tables:** `public.artifacts`, `public.artifact_versions`
- Each write increments version number with SHA256 hash + timestamp
- Mirror functions: `mirror_company_context_if_configured()`, `mirror_persona_if_configured()`, `mirror_styleguide_if_configured()`
- No-op if `company_id` or Supabase credentials aren't set

### DeepAgents Backend Abstraction

The agents use a `CompositeBackend` that routes virtual paths:

| Virtual Path | Backend | Storage |
|---|---|---|
| `/artifacts/*` | `FilesystemBackend` | Disk (`content-engine/artifacts/`) |
| `/memories/*` | `StoreBackend` | `InMemoryStore` (per-process) |
| Everything else | `StateBackend` | Thread-local scratchpad |

---

## 9. Configuration

All configuration is centralized in `src/settings.py` using Pydantic `BaseSettings`. Environment variables are loaded from `.env.local` files at both the repo root and `content-engine/` directory.

### Required API Keys

| Variable | Service | Used By |
|----------|---------|---------|
| `PERPLEXITY_API_KEY` | Perplexity | All research agents (web search) |
| `GOOGLE_API_KEY_COMPANY_DEEPAGENT` | Google Gemini | Company research agent |
| `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT` | Google Gemini | Persona research agent |
| `GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT` | Google Gemini | Style guide agent |
| `OPENAI_API_KEY` | OpenAI | Gap analysis embeddings |

### Optional API Keys

| Variable | Service | Used By |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Anthropic Claude | Style guide (default model), gap analysis |
| `GOOGLE_API_KEY_GAP_ANALYSIS` | Google Gemini | Gap analysis engine |
| `GOOGLE_API_KEY_REDDIT_HIL` | Google Gemini | Reddit HIL monitor |
| `REDDIT_CLIENT_ID` | Reddit (PRAW) | Reddit HIL monitor |
| `REDDIT_CLIENT_SECRET` | Reddit (PRAW) | Reddit HIL monitor |
| `REDDIT_USER_AGENT` | Reddit (PRAW) | Reddit HIL monitor |
| `SUPABASE_URL` | Supabase | Artifact mirroring |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Artifact mirroring |
| `SLACK_WEBHOOK_URL` | Slack | Reddit notifications |
| `DISCORD_WEBHOOK_URL` | Discord | Reddit notifications |
| `BRAVE_SEARCH_API_KEY` | Brave Search | Alternative search |

### Model Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_GEMINI_MODEL_COMPANY_DEEPAGENT` | `gemini-3-flash-preview` | Company agent LLM |
| `GOOGLE_PERSONA_DEEPAGENTS_MODEL` | `gemini-3-flash-preview` | Persona agent LLM |
| `GOOGLE_STYLE_GUIDE_DEEPAGENTS_MODEL` | `gemini-3-flash-preview` | Style guide agent LLM |
| `DEEPAGENTS_MODEL` | `claude-sonnet-4-5-20250929` | Default DeepAgents model |
| `PERPLEXITY_DEEP_RESEARCH_MODEL` | `sonar-deep-research` | Perplexity research model |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | OpenAI embedding model |
| `AEO_AGENT_INVOKE_TIMEOUT_S` | `900` (15 min) | Agent invocation timeout |

---

## 10. Running the Project

All commands assume you're in the `content-engine/` directory with the virtual environment activated.

### Company Research (standalone)

```bash
python scripts/run_company_research.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --seed-url "https://ramp.com" \
  --overwrite
```

### Persona Research (standalone, requires company context artifact)

```bash
python scripts/run_persona_research.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --company-context-path "/artifacts/company_context/ramp.md" \
  --auto-approve
```

### Full Pipeline (company -> persona -> style guide)

```bash
python scripts/run_pipeline.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --persona \
  --style \
  --auto-approve
```

### Gap Analysis

```bash
python scripts/run_gap_analysis.py \
  --company-name "Ramp" \
  --domain "ramp.com" \
  --company-context-path "/artifacts/company_context/ramp.md" \
  --persona-path "/artifacts/personas/ramp__persona-icp.md"
```

### Reddit HIL Monitor

```bash
python -m src.cli.reddit_hil \
  --company-name "Ramp" \
  --company-slug ramp \
  --subreddits marketing,startups \
  --dry-run
```

---

## 11. Current State & Known Issues

### What's Working

- Company research agent: end-to-end functional (Gemini + Perplexity deep research)
- Persona research agent: functional after `system_message` → `system_prompt` fix and `ThreadPoolExecutor` isolation fix
- Artifact filesystem: drafts and permanent artifacts written correctly
- Supabase mirroring: implemented, optional
- Gap analysis: 8-step pipeline implemented with skip-step support
- Reddit HIL: graph + CLI implemented, webhooks for Slack/Discord

### What's In Progress / Known Issues

- **Style guide agent** has the same two bugs the persona agent had:
  - Uses `system_message=` instead of `system_prompt=` in `create_deep_agent()` call (line 64)
  - Missing `ThreadPoolExecutor` isolation for `agent.invoke()` (line 118) — will hit the same `StoreBackend` runtime error
- **Tests:** `tests/` directory is empty — no automated tests yet
- **No API server:** No REST/WebSocket server; graphs invoked only via CLI scripts or direct Python API
- **InMemoryStore:** The store backend is in-memory only — memories are lost between process restarts
- **Debug log paths:** Hardcoded to `/Users/aryankeshri/Documents/aeo-optimizer/.cursor/debug.log` in company_research_agent.py and company_research.py

### Git Status (as of session start)

**Branch:** `main`

**Modified (uncommitted):**
- `src/graphs/company_research.py`
- `src/graphs/persona_research.py`
- `src/graphs/pipeline.py`
- `src/graphs/style_guide.py`

**Untracked artifacts:**
- `artifacts/company_context/ramp-business-corporation.draft.md`
- `artifacts/company_context/ramp-business-corporation.md`

**Recent commits:**
- `d79eb2c` — added gap-analysis flow
- `f20377c` — init: reddit_workflow setup
- `7f81ba9` — completed research agent phase
- `25dbc20` — persona_deepagent_implementation
- `be946a6` — company-context-research-agent + artifact handling

---

## 12. External Dependencies Summary

### Core Frameworks
- `deepagents` — Agentic framework (tool use, memory, filesystem backend)
- `langgraph` 0.6.11 — Graph-based orchestration with interrupts
- `langchain-google-genai` — Google Gemini integration
- `pydantic` + `pydantic-settings` — Data validation and config

### LLM Providers
- `perplexity` SDK — Deep research
- `anthropic` — Claude
- `openai` — Embeddings + chat
- `langchain-google-genai` — Gemini

### Data & Storage
- `supabase` — Artifact versioning
- `praw` — Reddit API

### Analysis & Visualization
- `numpy`, `scikit-learn`, `scipy` — Numerical computing
- `plotly` — Charts
- `umap-learn` — Dimensionality reduction
- `beautifulsoup4` — HTML parsing
- `playwright` — Browser automation (gap analysis crawling)
