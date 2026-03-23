# Content Strategy Engine

**Deep Presence** helps B2B companies become the cited answer in AI-generated search results — across ChatGPT, Perplexity, Claude, and Gemini.

This is the core engine: six autonomous pipelines that research your company, audit your site, identify citation gaps, generate optimized content, and track your visibility over time — all with human-in-the-loop approval at every critical stage.

---

## Pipelines

| # | Pipeline | What it does |
|---|----------|--------------|
| 0 | **Site Audit** | Deterministic 6-step crawler. Scores pages across 8 dimensions (schema, AEO readiness, penalties). No LLM needed. |
| 1 | **Research Artifacts** | Gemini + Perplexity agents produce company context, audience personas, and style guides. LangGraph HITL approval. |
| 1b | **Knowledge Base** | 6-agent DAG (company overview, products, reviews, competitors, trends, news). 3 HITL checkpoints. Staleness tracking + delta synthesis. |
| 2 | **Gap Analysis** | 8-step pipeline: embed assets → generate queries → search 4 AI platforms → extract citations → analyze semantic gaps → visualize → report. |
| 3 | **Content Engine** | 6-stage async pipeline: Strategic Planner → Brief Builder → Workers (Outline → Draft → Fact Enrich → Format → Link) → Evaluator-Optimizer (E-E-A-T + style + factual) → HITL Review. |
| — | **Daily Tracker** | Scheduled monitoring: platform runner → mention detection → 4 metrics (mention rate, citation rate, share of voice, trend). |

Each pipeline produces structured Markdown artifacts in `artifacts/`, the filesystem source of truth. Database storage is optional and additive.

---

## Quick Start

### Prerequisites

- Python 3.12+
- API keys (see [Environment Variables](#environment-variables))

### 1. Clone & install

```bash
git clone <repo-url>
cd content-strategy-engine

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Required for gap analysis web crawling
playwright install chromium
```

### 2. Configure environment

Create `.env.local` at the project root:

```bash
# --- Required (core pipelines) ---
OPENAI_API_KEY=sk-...                           # Embeddings + gap analysis search
ANTHROPIC_API_KEY=sk-ant-...                     # Content engine + gap analysis search
PERPLEXITY_API_KEY=pplx-...                      # Deep research + fact enrichment

# Google Gemini — one key per pipeline (rate-limit isolation)
GOOGLE_API_KEY_GAP_ANALYSIS=AIza...              # Gap analysis: Gemini search engine
GOOGLE_API_KEY_AUDIENCE_PERSONA=AIza...          # Audience persona pipeline
GOOGLE_API_KEY_REDDIT_HIL=AIza...                # Reddit HIL monitor

# --- Optional ---
LANGSMITH_API_KEY=ls-...                         # Tracing (LangSmith)
DATABASE_URL=postgresql+asyncpg://localhost:5432/deep_presence  # PostgreSQL (enables DB mode)

# Reddit monitoring
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=deep-presence-bot/1.0

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 3. Start the API server

```bash
python scripts/run_server.py
# → http://localhost:8000
# → Docs at http://localhost:8000/docs
```

### 4. Verify

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## API Reference

All pipeline endpoints are async — they return a `task_id` immediately. Stream progress via SSE at `/api/v1/tasks/{task_id}/events`.

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/readiness` | API key readiness |
| POST | `/api/v1/auth/register` | Register a new company |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/site-audit/start` | Launch site audit |
| POST | `/api/v1/knowledge-base/start` | Launch knowledge base pipeline |
| POST | `/api/v1/audience-persona/start` | Launch audience persona pipeline |
| POST | `/api/v1/voice-style-guide/start` | Launch voice style guide pipeline |
| POST | `/api/v1/gap-analysis/start` | Launch gap analysis |
| POST | `/api/v1/content/start` | Launch content generation (v1.3) |
| POST | `/api/v1/content/{run_id}/approve` | HITL: approve/revise content brief |
| POST | `/api/v1/daily-tracker/start` | Launch daily tracker run |
| GET | `/api/v1/tasks` | List tasks (filter by pipeline/status) |
| GET | `/api/v1/tasks/{task_id}/events` | SSE event stream |

Full reference: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

---

## Running Pipelines via CLI

### Research pipelines (Knowledge Base → Audience Persona → Voice Style Guide)

```bash
# Knowledge Base (company research — 6-agent DAG)
python scripts/run_kb.py --company-name "Ramp" --domain ramp.com --auto-approve

# Audience Personas (2-agent pipeline)
python scripts/run_audience_persona.py --company-name "Ramp" --domain ramp.com --auto-approve

# Voice Style Guide (3-agent pipeline)
python scripts/run_voice_style_guide.py --company-name "Ramp" --domain ramp.com --auto-approve
```

### Gap analysis

```bash
python scripts/run_gap_analysis.py \
  --company-name "Ramp" \
  --domain ramp.com \
  --company-context-path artifacts/company_context/ramp.md \
  --persona-path artifacts/personas/ramp__persona-icp.md \
  --platforms perplexity,openai,gemini,claude \
  --max-queries 150
```

---

## Project Structure

```
content-strategy-engine/
├── core/                       # All business logic
│   ├── config/settings.py      # Pydantic Settings (all env vars)
│   ├── models/                 # Pydantic v2 models (13 files)
│   ├── site_audit/             # Pipeline 0: deterministic audit
│   ├── research/               # Pipeline 1: agents, graphs, prompts, tools
│   │   └── knowledge_base/     # Pipeline 1b: 6-agent DAG + HITL
│   ├── gap_analysis/           # Pipeline 2: 8-step analysis
│   ├── content_engine/         # Pipeline 3: v1.3 async pipeline
│   ├── cps_model/              # Citation Prediction Score model
│   ├── daily_tracker/          # Platform monitoring + metrics
│   ├── reddit_hil/             # Reddit monitor + webhooks
│   ├── auth/                   # Auth utils
│   ├── db/                     # SQLAlchemy ORM + Alembic migrations
│   ├── services/               # Service layer (JSON + DB dual-mode)
│   ├── storage/                # StorageBackend ABC
│   └── shared_tools/           # Embedding clients, ChromaDB
├── api/                        # FastAPI REST API
│   ├── app.py                  # App factory
│   ├── auth/                   # ASGI middleware, RBAC
│   ├── routers/                # 19 router modules
│   ├── schemas/                # Request/response models
│   ├── services/               # Data services (dual-mode)
│   └── tasks/                  # TaskStore, EventBus (SSE)
├── scripts/                    # CLI entry points
├── artifacts/                  # Persisted outputs (source of truth)
├── tests/                      # Test suite
├── docs/                       # System & API documentation
└── supabase/migrations/        # Database migrations
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.12, asyncio |
| API | FastAPI + Uvicorn |
| Data validation | Pydantic v2 |
| State machines | LangGraph (HITL flows) |
| LLM routing | LiteLLM (content engine), raw SDK clients elsewhere |
| LLMs | Claude Sonnet 4.5, Gemini 3 Flash, GPT-5.2, Perplexity Sonar Pro |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Vector store | ChromaDB (local) |
| Web crawling | Playwright + trafilatura + BeautifulSoup |
| Analysis | scipy, numpy, scikit-learn |
| Visualization | Plotly |
| Tracing | LangSmith |
| Database | PostgreSQL + SQLAlchemy 2.0 + Alembic (optional) |
| Auth | JWT + ASGI middleware + RBAC |

---

## Development

### Running tests

```bash
# Full suite
pytest tests/ -v

# Specific module
pytest tests/content_engine/ -v
pytest tests/integration/ -v

# With coverage
pytest tests/ --cov=core --cov-report=term-missing
```

### Smoke Tests (Deployment Validation)

Smoke tests run against a **live deployed instance** to catch issues that unit tests miss: environment config, auth flow, SSE streaming, network connectivity. They live in `tests/smoke/` and are auto-skipped unless `SMOKE_TEST_URL` is set.

```bash
# Against local dev server
SMOKE_TEST_URL=http://localhost:8000 pytest tests/smoke/ -v

# Against staging/production
SMOKE_TEST_URL=https://api.staging.example.com pytest tests/smoke/ -v

# With authentication (enables login + protected endpoint tests)
SMOKE_TEST_URL=https://api.staging.example.com \
  SMOKE_TEST_EMAIL=test@example.com \
  SMOKE_TEST_PASSWORD=your-password \
  pytest tests/smoke/ -v
```

**What smoke tests verify:**
- `/health` and `/readiness` return 200 with expected shape
- Unauthenticated requests to protected endpoints get 401
- Login flow returns a valid access token
- Authenticated task list returns 200
- SSE event stream endpoint responds correctly

**When to run:** after every deployment, before tagging a release, or when debugging deployment-specific issues that unit tests don't catch.

### Database setup (optional)

The engine runs filesystem-first by default. To enable PostgreSQL:

```bash
# Set DATABASE_URL in .env.local
DATABASE_URL=postgresql+asyncpg://localhost:5432/deep_presence

# Run migrations
alembic upgrade head
```

### Import check

```bash
python -c "from core.config.settings import settings; print('Settings OK')"
python -c "from api.app import create_app; print('App OK')"
```

---

## License

Proprietary — Deep Presence, Inc.
