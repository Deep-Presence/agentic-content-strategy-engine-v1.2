# Content Strategy Engine

An AI-powered content strategy platform that researches companies, builds audience personas, generates writing style guides, and identifies citation gaps across AI search platforms — all through autonomous agent pipelines with human-in-the-loop approval flows.

Built for **Deep Presence** — helping B2B companies become the cited answer in AI-generated search results.

---

## Architecture Overview

The system runs **three sequential pipelines**, each producing structured Markdown artifacts that feed into the next:

```
Pipeline 1: Research Artifacts    Pipeline 2: Gap Analysis    Pipeline 3: Content Generation
─────────────────────────────    ────────────────────────    ──────────────────────────────
Company Context Research         Embed company assets        Planner Agent
        │                        Generate queries            Sub-Agentic Systems
        ▼                        Search AI platforms          (Planner-Manager → Workers)
Audience Persona Research        Enrich citations            Evaluator Agent
        │                        Embed all content           Citation Probability Score
        ▼                        Semantic analysis           Publish
Writing Style Guide Research     Visualize
                                 Generate report
        ✅ Done                        ✅ Done                    🔜 Next
```

### Pipeline 1 — Research Artifacts

Three sequential research stages, each powered by a DeepAgent (Gemini) with Perplexity Deep Research for web intelligence:

| Stage | Agent | Output |
|-------|-------|--------|
| Company Context | Gemini Flash | `artifacts/company_context/{slug}.md` |
| Audience Personas | Gemini Flash | `artifacts/personas/{slug}__persona-icp.md`, `-2.md`, `-3.md` |
| Writing Style Guide | Gemini Flash | `artifacts/style_guides/{slug}.md` |

Each stage uses a **LangGraph state machine** with a human-in-the-loop approval flow:

```
Agent → Approval Gate → Route
                          ├─ approve → Write & Mirror → END
                          ├─ revise  → Agent (with revision note)
                          └─ reject  → END
```

### Pipeline 2 — Gap Analysis

An 8-step pipeline that analyzes how well a company is cited across AI search platforms:

1. **Embed Assets** — Vectorize company context, personas, and style guide
2. **Generate Queries** — Create search queries a target persona would ask
3. **Search Platforms** — Query ChatGPT, Claude, Perplexity, and Google AI Overview
4. **Enrich Citations** — Crawl and extract content from cited sources
5. **Embed Content** — Vectorize all search results and citations
6. **Analyze** — Compute semantic proximity and structural gap analysis
7. **Visualize** — Generate UMAP scatter plots and gap heatmaps
8. **Generate Report** — Produce actionable gap report with recommendations

### Pipeline 3 — Content Generation (Planned)

A multi-agent content creation system that uses research artifacts + gap analysis to produce citation-optimized content.

---

## Project Structure

```
content-strategy-engine/
├── core/                              # All business logic
│   ├── config/
│   │   └── settings.py                # Pydantic BaseSettings (all env vars)
│   ├── models/                        # Pydantic v2 schemas
│   │   ├── artifacts.py               # CompanyResearchInput
│   │   ├── personas.py                # PersonaResearchInput
│   │   ├── style_guide.py             # StyleGuideResearchInput
│   │   ├── gap_analysis.py            # GapAnalysisInput, SemanticUnit, GapReport
│   │   └── reddit_hil.py              # RedditMonitorInput, RedditThread
│   ├── research/                      # Pipeline 1: Research Artifacts
│   │   ├── agents/                    # DeepAgent definitions
│   │   │   ├── base.py                # Shared backend factory + CompositeBackend
│   │   │   ├── company_research_agent.py
│   │   │   ├── persona_agent.py
│   │   │   └── style_guide_agent.py
│   │   ├── graphs/                    # LangGraph state machines
│   │   │   ├── company_research.py
│   │   │   ├── persona_research.py
│   │   │   ├── style_guide.py
│   │   │   └── pipeline.py            # Combined 3-stage orchestrator
│   │   └── tools/
│   │       └── perplexity_client.py   # Perplexity sonar-deep-research wrapper
│   ├── gap_analysis/                  # Pipeline 2: Gap Analysis
│   │   ├── pipeline.py                # 8-step orchestrator
│   │   ├── engines/                   # LLM backends (Claude, Gemini, OpenAI, Perplexity)
│   │   └── steps/                     # s1 through s8
│   ├── reddit_hil/                    # Reddit Human-in-the-Loop Monitor
│   │   ├── graph.py                   # LangGraph for monitoring
│   │   ├── reddit_client.py           # PRAW wrapper
│   │   └── webhooks.py                # Slack/Discord notifications
│   ├── content_engine/                # Pipeline 3 (planned)
│   ├── storage/
│   │   ├── supabase_client.py         # Supabase client singleton
│   │   ├── supabase_mirror.py         # Optional artifact mirroring to DB
│   │   └── backends/
│   │       └── base.py                # Abstract StorageBackend interface
│   └── shared_tools/                  # Cross-pipeline utilities
├── scripts/                           # CLI entry points
│   ├── run_company_research.py
│   ├── run_persona_research.py
│   ├── run_style_guide_research.py
│   ├── run_pipeline.py                # Full 3-stage pipeline
│   └── run_gap_analysis.py
├── artifacts/                         # Persisted agent outputs (source of truth)
│   ├── company_context/               # {slug}.md, {slug}.draft.md
│   ├── personas/                      # {slug}__persona-icp.md, -2.md, -3.md
│   ├── style_guides/                  # {slug}.md
│   ├── gap_analysis/                  # Per-company subdirs with step outputs
│   └── _logs/
├── tests/
├── docs/
├── supabase/                          # Supabase config & migrations
└── flow-diagrams/                     # Architecture visualizations
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- API keys (see [Configuration](#configuration))

### Installation

```bash
cd content-strategy-engine

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for gap analysis web crawling)
playwright install chromium
```

### Environment Setup

Create a `.env.local` file at the project root:

```bash
# Required — Research Pipeline
PERPLEXITY_API_KEY=pplx-...
GOOGLE_API_KEY_COMPANY_DEEPAGENT=AIza...
GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT=AIza...
GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT=AIza...

# Required — Gap Analysis
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY_GAP_ANALYSIS=AIza...

# Optional — Supabase mirroring
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Optional — Reddit monitoring
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=deep-presence-bot/1.0

# Optional — Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## Usage

### Run the Full Research Pipeline

Runs all three stages sequentially (company → persona → style guide):

```bash
python scripts/run_pipeline.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --persona \
  --style \
  --auto-approve
```

Without `--auto-approve`, each stage pauses at the approval gate for human review.

### Run Individual Research Stages

**Company Context Research:**

```bash
python scripts/run_company_research.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --overwrite
```

**Audience Persona Research:**

```bash
python scripts/run_persona_research.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --max-personas 3 \
  --auto-approve
```

**Writing Style Guide Research:**

```bash
python scripts/run_style_guide_research.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --auto-approve
```

### Run Gap Analysis

Requires research artifacts to exist first:

```bash
python scripts/run_gap_analysis.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --company-context-path /artifacts/company_context/ramp.md \
  --persona-path /artifacts/personas/ramp__persona-icp.md \
  --platforms perplexity,openai,gemini,claude \
  --max-queries 150
```

Skip specific steps with `--skip-step`:

```bash
python scripts/run_gap_analysis.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --skip-step 7 --skip-step 8
```

---

## Configuration

All configuration is managed through environment variables via Pydantic `BaseSettings` in `core/config/settings.py`. Variables are loaded from `.env.local` at the project root.

### API Keys

| Variable | Required For | Description |
|----------|-------------|-------------|
| `PERPLEXITY_API_KEY` | Research | Perplexity Deep Research (sonar-deep-research) |
| `GOOGLE_API_KEY_COMPANY_DEEPAGENT` | Research | Gemini for company context agent |
| `GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT` | Research | Gemini for persona agent |
| `GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT` | Research | Gemini for style guide agent |
| `OPENAI_API_KEY` | Gap Analysis | Embeddings (text-embedding-3-small) + search |
| `ANTHROPIC_API_KEY` | Gap Analysis | Claude search platform |
| `GOOGLE_API_KEY_GAP_ANALYSIS` | Gap Analysis | Gemini search platform |

### Model Defaults

| Setting | Default | Purpose |
|---------|---------|---------|
| `GOOGLE_GEMINI_MODEL_COMPANY_DEEPAGENT` | `gemini-3-flash-preview` | Company research model |
| `GOOGLE_PERSONA_DEEPAGENTS_MODEL` | `gemini-3-flash-preview` | Persona research model |
| `GOOGLE_STYLE_GUIDE_DEEPAGENTS_MODEL` | `gemini-3-flash-preview` | Style guide research model |
| `PERPLEXITY_DEEP_RESEARCH_MODEL` | `sonar-deep-research` | Web research model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `AEO_AGENT_INVOKE_TIMEOUT_S` | `900` | Agent invoke timeout (seconds) |

### Optional Services

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Artifact mirroring to database |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase authentication |
| `REDDIT_CLIENT_ID` / `SECRET` / `USER_AGENT` | Reddit thread monitoring |
| `SLACK_WEBHOOK_URL` | Slack notifications |
| `DISCORD_WEBHOOK_URL` | Discord notifications |

---

## Artifact System

All agent outputs are persisted as Markdown files in the `artifacts/` directory. This is the **source of truth** — database mirroring is optional and secondary.

### Artifact Lifecycle

1. **Draft** — Agent writes `{slug}.draft.md` during research
2. **Review** — Human reviews draft at the approval gate (approve / revise / reject)
3. **Promote** — On approval, draft is promoted to `{slug}.md`
4. **Mirror** — Optionally mirrored to Supabase with version tracking

### Iterative Updates

Research agents use **patch-style updates** when an artifact already exists. They read the existing file, update specific sections, and preserve the rest. Section headers are stable anchors — agents never rename them.

### Cross-Stage Context

Later stages automatically receive earlier artifacts as context:

- **Persona agent** reads the company context artifact
- **Style guide agent** reads both company context and persona artifacts
- **Gap analysis** reads all three research artifacts

---

## Storage Architecture

### Backend Routing

The `CompositeBackend` in `core/research/agents/base.py` routes file operations:

| Path Prefix | Backend | Resolves To |
|-------------|---------|-------------|
| `/artifacts/` | `FilesystemBackend` | `artifacts/` directory on disk |
| `/memories/` | `StoreBackend` | In-memory agent memory |
| Everything else | `StateBackend` | Per-thread scratchpad |

### Storage Abstraction

The `StorageBackend` interface (`core/storage/backends/base.py`) supports swappable backends:

- **Local filesystem** — Default for development
- **Cloud storage** — S3 / GCS / Supabase Storage (production, planned)

### Database Mirroring

When Supabase credentials are configured, approved artifacts are automatically mirrored to the database with:

- Version increment on each update
- SHA256 content hash for deduplication
- Structured metadata (company, domain, artifact type)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Agent Framework | DeepAgents + LangGraph |
| LLM (Research) | Google Gemini 3 Flash |
| LLM (Gap Analysis) | Claude, Gemini, GPT-4, Perplexity |
| Web Research | Perplexity sonar-deep-research |
| Embeddings | OpenAI text-embedding-3-small |
| Data Validation | Pydantic v2 |
| Visualization | Plotly, UMAP, scikit-learn |
| Web Crawling | Playwright + BeautifulSoup |
| Database | Supabase (PostgreSQL + pgvector) |
| Reddit | PRAW |

---

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Import Verification

```bash
python -c "from core.config.settings import settings; print('Settings OK')"
python -c "from core.research.graphs.pipeline import run_pipeline; print('Pipeline OK')"
python -c "from core.gap_analysis.pipeline import run_gap_analysis; print('Gap Analysis OK')"
```

### Code Standards

- Type hints on all function signatures
- Pydantic v2 strict models with validators
- `system_prompt=` (not `system_message=`) for `create_deep_agent()`
- `ThreadPoolExecutor` isolation for all `agent.invoke()` calls
- Structured JSON logging with stage/event/timestamp
- Config-relative paths only — no hardcoded absolute paths

---

## License

Proprietary — Deep Presence, Inc.
