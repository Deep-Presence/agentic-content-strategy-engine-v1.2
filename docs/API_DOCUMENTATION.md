# Content Strategy Engine — API Documentation

> **For frontend engineers.** Everything you need to build the dashboard UI.
>
> **Base URL:** `http://localhost:8000`
> **API Prefix:** `/api/v1`
> **Interactive Docs:** `http://localhost:8000/docs` (Swagger) · `http://localhost:8000/redoc`

---

## 1. Quick Reference

### Pipeline Operations

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/health` | Health check | 200 |
| `GET` | `/readiness` | API key readiness check | 200 |
| `POST` | `/api/v1/gap-analysis/start` | Launch gap analysis pipeline | 202 |
| `GET` | `/api/v1/gap-analysis/{run_id}/status` | Get gap analysis status | 200 |
| `POST` | `/api/v1/research/start` | Launch research pipeline | 202 |
| `GET` | `/api/v1/research/{run_id}/status` | Get research status | 200 |
| `POST` | `/api/v1/research/{run_id}/approve` | Submit HITL approval (research) | 200 |
| `POST` | `/api/v1/content/start` | Launch content generation pipeline | 202 |
| `GET` | `/api/v1/content/{run_id}/status` | Get content generation status | 200 |
| `POST` | `/api/v1/content/{run_id}/approve` | Submit HITL approval (content) | 200 |
| `GET` | `/api/v1/tasks` | List all tasks (with filters) | 200 |
| `GET` | `/api/v1/tasks/{task_id}` | Get task detail | 200 |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | Cancel a running task | 200 |
| `GET` | `/api/v1/tasks/{task_id}/events` | Stream real-time events (SSE) | 200 |
| `GET` | `/api/v1/artifacts/companies` | List all company slugs | 200 |
| `GET` | `/api/v1/artifacts/{type}/{slug}` | List artifact files | 200 |
| `GET` | `/api/v1/artifacts/{type}/{slug}/{filename}` | Get artifact file content | 200 |

### Authentication

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `POST` | `/api/v1/auth/register` | Register new user + company | 201 |
| `POST` | `/api/v1/auth/login` | Login with email + password | 200 |
| `GET` | `/api/v1/auth/me` | Get current user (requires Bearer token) | 200 |

### Company Profile

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/companies/{slug}` | Get company profile with artifacts & runs | 200 |

### Gap Analysis Data (Signal Analysis Dashboard)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/companies/{slug}/gap-analysis/summary` | Executive overview (SPA, classifications, clusters) | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/queries` | Paginated query list (filterable, sortable) | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/clusters` | Cluster specs with structural rates | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/signals` | Structural signal averages & correlations | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/platforms` | Per-platform citation breakdown | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/heatmap` | Gap score heatmap by cluster | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/embeddings` | 2D embedding projections (UMAP/t-SNE) | 200 |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/trend` | SPA score trend across runs | 200 |

### Content Data (Content Pipeline Workspace)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/companies/{slug}/content/briefs` | List all content briefs with statuses | 200 |
| `GET` | `/api/v1/companies/{slug}/content/briefs/{brief_id}` | Full brief detail with eval history | 200 |
| `GET` | `/api/v1/companies/{slug}/content/briefs/{brief_id}/{stage}` | Stage-specific file content | 200 |

### Brand Data (Research & Runs)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/companies/{slug}/research/artifacts` | Research artifacts with full content | 200 |
| `GET` | `/api/v1/companies/{slug}/runs` | Run history across all pipelines | 200 |

---

## 2. Getting Started

### Running the Server

```bash
cd content-strategy-engine
python scripts/run_server.py
```

This starts uvicorn on `http://localhost:8000` with hot-reload. Alternatively:

```bash
uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:3001"]` | Allowed CORS origins (JSON list) |
| `API_API_PREFIX` | `/api/v1` | URL prefix for all routes |
| `API_MAX_CONCURRENT_PIPELINES` | `3` | Max concurrent pipeline runs |

Example:
```bash
export API_CORS_ORIGINS='["http://localhost:3000", "https://app.deeppresence.com"]'
export API_MAX_CONCURRENT_PIPELINES=5
```

### Verify the Server

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "ok"}

# Readiness check (verifies API keys are set)
curl http://localhost:8000/readiness
# → {"ready": true, "missing_keys": []}
```

If `ready` is `false`, the `missing_keys` array tells you which API keys need to be set (`openai_api_key`, `anthropic_api_key`, `perplexity_api_key`).

---

## 3. Core Concepts

### Pipelines

The system has 3 pipelines:

| Pipeline | What it does | Has HITL? |
|----------|-------------|-----------|
| **research** | AI agents research a company, build persona profiles, and create writing style guides | Yes — approve/revise/reject each stage |
| **gap_analysis** | Crawls company site, generates search queries, queries 4 AI platforms, analyzes citation gaps | No |
| **content** | Uses research + gap analysis outputs to auto-generate optimized content pieces | Yes — approve/edit/reject each brief |

### Async Task Model

All pipeline starts return `202 Accepted` with a `run_id`. The pipeline runs in the background. You then either:
- **Stream events** via SSE (`GET /api/v1/tasks/{run_id}/events`) — real-time updates
- **Poll status** via `GET /api/v1/{pipeline}/{run_id}/status` — simpler, request/response

### Task Lifecycle

```
                          ┌─────────────────────┐
                          │      running         │
                          └──────┬──────┬────────┘
                   HITL needed   │      │  error
                          ┌──────▼──┐  ┌▼─────────┐
                          │ pending  │  │  failed   │
                          │_approval │  └───────────┘
                          └──────┬───┘
                  approve/revise │
                          ┌──────▼──────┐
                          │   running    │◄── (may loop back to pending_approval)
                          └──────┬──────┘
                                 │ done
                          ┌──────▼──────┐
                          │  completed   │
                          └─────────────┘
```

Possible statuses: `running` · `pending_approval` · `completed` · `failed` · `cancelled` · `failed_restart`

### Slug Locks

Only one pipeline can run per company at a time. If you try to start a second gap analysis for "ramp" while one is already running, you get `409 Conflict`. The lock is released when the task completes, fails, or is cancelled.

### Concurrency Limit

A global semaphore limits total concurrent pipeline runs (default: 3). Tasks exceeding this limit queue until a slot opens.

---

## 4. Authentication & CORS

### Authentication

The API uses **JWT Bearer tokens** for authentication. Auth state is backed by a JSON file store (`api/auth/store.py`).

**Middleware:** `AuthMiddleware` runs on every request. It parses the `Authorization: Bearer {token}` header and sets `request.state.user_id` and `request.state.company_slug`. Endpoints that don't require auth simply ignore these values.

### CORS

Configured via `API_CORS_ORIGINS` env var. Defaults to `localhost:3000` and `localhost:3001`. Set this to your frontend's origin in production.

---

## 5. Auth Endpoints

### Register

```
POST /api/v1/auth/register
```

Creates a new user with company deduplication. If `company_domain` matches an existing company's root domain, the user joins that company as `member`. Otherwise, a new company is created and the user becomes `superuser`. Subdomains are normalized to root domain.

**Request Body:**

```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@acme.com",
  "password": "securepass123",
  "company_name": "Acme Corp",
  "company_domain": "acme.com"
}
```

**Fields:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `first_name` | string | Yes | — | User's first name |
| `last_name` | string | Yes | — | User's last name |
| `email` | string | Yes | Valid email | User's email (must be unique) |
| `password` | string | Yes | 8–128 chars | Password |
| `company_name` | string | Yes | — | Company display name |
| `company_domain` | string | Yes | — | Company domain (e.g., `acme.com`) |

**Response (201):**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "user-abc123",
    "email": "john@acme.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "superuser",
    "company_id": "company-def456",
    "is_active": true
  },
  "company": {
    "id": "company-def456",
    "slug": "acme-corp",
    "name": "Acme Corp",
    "domain": "acme.com"
  }
}
```

**Error (409):** Email already registered or domain conflict.

### Login

```
POST /api/v1/auth/login
```

Authenticate with email + password. Returns access token, user info, and company info.

**Request Body:**

```json
{
  "email": "john@acme.com",
  "password": "securepass123"
}
```

**Response (200):** Same `LoginResponse` shape as register.

**Error (401):** Invalid email or password.

### Get Current User

```
GET /api/v1/auth/me
```

Return current user info from the auth token.

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response (200):**

```json
{
  "user": {
    "id": "user-abc123",
    "email": "john@acme.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "superuser",
    "company_id": "company-def456",
    "is_active": true
  },
  "company": {
    "id": "company-def456",
    "slug": "acme-corp",
    "name": "Acme Corp",
    "domain": "acme.com"
  }
}
```

**Error (401):** No token, invalid token, or user not found.

---

## 6. Company Profile

### Get Company Profile

```
GET /api/v1/companies/{slug}
```

Returns company profile with research artifact status, gap analysis/content availability, products, and latest pipeline runs.

**Path Parameters:**
- `slug` — Company slug. Must match `^[a-z0-9][a-z0-9-]*$`.

**Response (200):**

```json
{
  "slug": "ramp",
  "name": "Ramp",
  "domain": "ramp.com",
  "products": [
    {
      "slug": "expense-management",
      "name": "Expense Management",
      "has_research": false,
      "has_gap_analysis": false,
      "has_content": false
    }
  ],
  "has_research": true,
  "has_gap_analysis": true,
  "has_content": false,
  "research_summary": {
    "company_context": "ramp.md",
    "company_context_status": "approved",
    "personas": ["ramp__persona-icp.md", "ramp__persona-secondary-1.md"],
    "style_guide": "ramp.md",
    "style_guide_status": "approved"
  },
  "latest_runs": {
    "research": {
      "run_id": "660e8400-...",
      "status": "completed",
      "created_at": "2026-02-20T10:00:00Z",
      "completed_at": "2026-02-20T10:15:00Z",
      "summary": { "...": "..." }
    },
    "gap_analysis": {
      "run_id": "550e8400-...",
      "status": "completed",
      "created_at": "2026-02-22T11:00:00Z",
      "completed_at": "2026-02-22T14:46:00Z",
      "summary": null
    },
    "content": null
  }
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | URL-safe company identifier |
| `name` | string | Display name (from auth store, or title-cased slug) |
| `domain` | string | Company domain (empty if not registered) |
| `products` | ProductSummary[] | Products from auth store (product-level artifacts not yet implemented) |
| `has_research` | bool | Whether any research artifacts exist |
| `has_gap_analysis` | bool | Whether gap analysis output directory has files |
| `has_content` | bool | Whether content output directory has files |
| `research_summary` | object | Artifact file names and statuses (`"none"` · `"draft"` · `"approved"`) |
| `latest_runs` | object | Most recent task per pipeline type (`null` if no runs) |

**Error (400):** Invalid slug format (doesn't match regex).

**Error (404):** Company not found in auth store AND no artifacts exist on filesystem.

---

## 7. Gap Analysis (Pipeline Operations)

### Start Gap Analysis

```
POST /api/v1/gap-analysis/start
```

**Request Body (simplified):**

The frontend only needs `company_name` and `domain`. The backend auto-resolves research artifact paths (company context, personas, style guide) from the filesystem based on the company slug.

```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "seed_urls": ["https://ramp.com/blog", "https://ramp.com/resources"],
  "skip_steps": [],
  "max_queries": 150,
  "platforms": ["perplexity", "openai", "gemini", "claude"],
  "language": "en",
  "region": "US",
  "max_crawl_pages": 200,
  "max_crawl_depth": 3
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `seed_urls` | string[] | No | `[]` | URLs to crawl |
| `skip_steps` | int[] | No | `[]` | Step numbers (1-8) to skip |
| `max_queries` | int | No | `150` | Max queries (10-500) |
| `platforms` | string[] | No | `["perplexity","openai","gemini","claude"]` | AI platforms to search |
| `language` | string | No | `"en"` | Language code |
| `region` | string | No | `null` | Region filter |
| `additional_constraints` | string | No | `null` | Extra instructions for the pipeline |
| `max_crawl_pages` | int | No | `null` | Override crawl page limit |
| `max_crawl_depth` | int | No | `null` | Override crawl depth |

**`skip_steps`:** Array of step numbers (1-8) to skip. Useful for resuming a partial run. Steps: 1=embed assets, 2=generate queries, 3=search platforms, 4=enrich citations, 5=embed content, 6=analyze, 7=visualize, 8=generate report.

> **Note:** The backend automatically derives `company_slug` from `company_name`, then resolves `company_context_path`, `persona_paths`, and `style_guide_path` from the artifacts directory. Only approved (non-draft) artifacts are used. The `resolved_artifacts` field in the completion result shows which artifacts were found.

**Response (202):**

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline": "gap_analysis",
  "company_slug": "ramp",
  "status": "running",
  "created_at": "2026-02-16T12:34:56.789123+00:00"
}
```

### Get Gap Analysis Status

```
GET /api/v1/gap-analysis/{run_id}/status
```

**Response (200):**

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline": "gap_analysis",
  "company_slug": "ramp",
  "status": "completed",
  "current_step": null,
  "progress_pct": null,
  "created_at": "2026-02-16T12:34:56.789123+00:00",
  "updated_at": "2026-02-16T13:45:00.123456+00:00",
  "result": {
    "report_md": "# Gap Analysis Report: Ramp\n\n## Executive Summary...",
    "report_json": { "...": "..." },
    "visualization_paths": [
      "visualizations/gap_heatmap.html",
      "visualizations/umap.html",
      "visualizations/radar.html"
    ],
    "produced_artifacts": [
      {"type": "gap_analysis", "slug": "ramp"}
    ]
  },
  "error": null,
  "approval_payload": null
}
```

**`result` (on completion):**

| Field | Type | Description |
|-------|------|-------------|
| `report_md` | string | First 500 chars of the markdown report |
| `report_json` | object | Full structured JSON report |
| `visualization_paths` | string[] | Relative paths to HTML visualizations |
| `resolved_artifacts` | object | Research artifacts that were auto-resolved from the filesystem |
| `produced_artifacts` | array | Artifact types produced — use with `GET /artifacts/{type}/{slug}` |

**`resolved_artifacts` shape:**

```json
{
  "company_context_path": "/artifacts/company_context/ramp.md",
  "persona_paths": ["/artifacts/personas/ramp__persona-icp.md"],
  "style_guide_path": "/artifacts/style_guides/ramp.md"
}
```

Fields are `null` / `[]` if no approved artifact was found for that type. Only finalized artifacts (`.md`) are resolved; draft artifacts (`.draft.md`) are excluded.

**`error` (on failure):** String with the exception message.

---

## 8. Research Pipeline (Pipeline Operations)

The research pipeline runs up to 3 sequential stages: **company** → **persona** → **style guide**. Each stage can pause for human approval.

### Start Research

```
POST /api/v1/research/start
```

**Request Body (simplified):**

The frontend only needs `company_name` and `domain`. The backend constructs per-stage inputs and chains artifact paths (company_context_path, persona_paths) automatically between stages.

```json
{
  "company_name": "Stripe",
  "domain": "stripe.com",
  "seed_urls": ["https://stripe.com/blog"],
  "stages": ["company", "persona", "style_guide"],
  "auto_approve": false,
  "language": "en",
  "region": "us",
  "max_personas": 3
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `seed_urls` | string[] | No | `[https://{domain}/]` | URLs for the research agent to study |
| `stages` | string[] | No | `["company","persona","style_guide"]` | Which stages to run (order is always company → persona → style_guide) |
| `auto_approve` | bool | No | `false` | Skip HITL gates — auto-approve all stages |
| `language` | string | No | `"en"` | Language code |
| `region` | string | No | `null` | Region context |
| `max_personas` | int | No | `3` | 1-3 (1 ICP + up to 2 secondary) |
| `internal_sources` | string[] | No | `[]` | Paths to internal transcripts/notes |
| `additional_constraints` | string | No | `null` | Extra instructions for the research agents |

> **Note:** The backend automatically derives `company_slug` from `company_name`, constructs `company_context_path` after the company stage completes, and passes `persona_paths` to the style guide stage. The frontend never needs to know about artifact paths.

**Response (202):** Same shape as gap analysis `PipelineRunResponse`.

### Get Research Status

```
GET /api/v1/research/{run_id}/status
```

**Response (200):** Same `TaskResponse` shape as gap analysis.

When `status` is `"pending_approval"`, the `approval_payload` tells you which stage needs approval:

```json
{
  "status": "pending_approval",
  "current_step": "company",
  "approval_payload": {
    "stage": "company",
    "status": "pending_approval",
    "draft_path": "/artifacts/company_context/stripe.draft.md",
    "artifact_md": "# Company Context: Stripe\n\n**Domain:** stripe.com\n\n## Origin Story\n..."
  }
}
```

The `artifact_md` field contains the full draft content to display to the user for review.

### Submit Research Approval

```
POST /api/v1/research/{run_id}/approve
```

**Request Body:**

```json
{
  "decision": "approve",
  "revision_note": null
}
```

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `decision` | string | Yes | `"approve"` · `"revise"` · `"reject"` | Approval decision |
| `revision_note` | string | No | — | Feedback for the agent (required if `"revise"`) |

**Response (200):**

```json
{
  "run_id": "660e8400-...",
  "decision": "approve",
  "revision_note": null
}
```

**What happens after each decision:**
- **`approve`** — Stage output is finalized, pipeline moves to the next stage (or completes)
- **`revise`** — Agent re-runs with the `revision_note` as feedback, then returns to `pending_approval` again
- **`reject`** — Pipeline stops, task status becomes `completed`

---

## 9. Content Generation (Pipeline Operations)

### Start Content Generation

```
POST /api/v1/content/start
```

**Request Body:**

```json
{
  "input_data": {
    "company_name": "Ramp",
    "domain": "ramp.com",
    "company_context_path": "/artifacts/company_context/ramp.md",
    "persona_paths": ["/artifacts/personas/ramp__persona-icp.md"],
    "style_guide_path": "/artifacts/style_guides/ramp.md",
    "gap_report_json_path": "/artifacts/gap_analysis/ramp/gap_report.json",
    "generation_spec_json_path": "/artifacts/gap_analysis/ramp/generation_spec.json",
    "analysis_json_path": "/artifacts/gap_analysis/ramp/analysis.json",
    "max_briefs": 10,
    "max_concurrent_workers": 3,
    "max_revision_cycles": 2,
    "auto_approve": false,
    "skip_stages": []
  }
}
```

**`input_data` fields (ContentGenerationInput):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `company_context_path` | string | No | — | Path to company context artifact |
| `persona_paths` | string[] | No | `[]` | Paths to persona artifacts |
| `style_guide_path` | string | No | — | Path to style guide artifact |
| `gap_report_json_path` | string | No | — | Path to gap report JSON |
| `generation_spec_json_path` | string | No | — | Path to generation spec JSON |
| `analysis_json_path` | string | No | — | Path to analysis JSON |
| `max_briefs` | int | No | `10` | Max content pieces to generate |
| `max_concurrent_workers` | int | No | `3` | Parallel content workers |
| `max_revision_cycles` | int | No | `2` | Max auto-revision cycles before HITL |
| `auto_approve` | bool | No | `false` | Skip HITL review gates |
| `skip_stages` | int[] | No | `[]` | Stage numbers to skip (1-4) |

**Response (202):** Same `PipelineRunResponse` shape.

### Get Content Status

```
GET /api/v1/content/{run_id}/status
```

**Response (200):** Same `TaskResponse` shape.

On completion, the `result` field contains:

```json
{
  "result": {
    "company_slug": "ramp",
    "total_briefs": 5,
    "total_approved": 4,
    "total_rejected": 1,
    "pieces": [
      { "brief_id": "brief-001", "title": "How to Automate Expense Reports", "status": "approved" },
      { "brief_id": "brief-002", "title": "Ramp vs Brex: A Complete Comparison", "status": "approved" },
      { "brief_id": "brief-003", "title": "Why Finance Teams Need Real-Time Spend Visibility", "status": "rejected" }
    ],
    "produced_artifacts": [
      { "type": "content", "slug": "ramp" }
    ]
  }
}
```

### Submit Content Approval

```
POST /api/v1/content/{run_id}/approve
```

**Request Body:**

```json
{
  "brief_id": "brief-001",
  "decision": "approve",
  "editor_notes": null
}
```

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `brief_id` | string | Yes | — | Which content brief to approve |
| `decision` | string | Yes | `"approve"` · `"edit"` · `"reject"` | Approval decision |
| `editor_notes` | string | No | — | Feedback for the agent (use with `"edit"`) |

**Response (200):**

```json
{
  "run_id": "770e8400-...",
  "brief_id": "brief-001",
  "decision": "approve",
  "editor_notes": null
}
```

---

## 10. Task Management

### List Tasks

```
GET /api/v1/tasks
GET /api/v1/tasks?pipeline=research
GET /api/v1/tasks?status=running
GET /api/v1/tasks?pipeline=gap_analysis&status=completed
```

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `pipeline` | string | Filter by pipeline: `research` · `gap_analysis` · `content` |
| `status` | string | Filter by status: `running` · `pending_approval` · `completed` · `failed` · `cancelled` |

**Response (200):**

```json
{
  "tasks": [
    {
      "run_id": "550e8400-...",
      "pipeline": "gap_analysis",
      "status": "completed",
      "company_slug": "ramp",
      "current_step": null,
      "created_at": "2026-02-16T12:34:56.789123+00:00",
      "updated_at": "2026-02-16T13:45:00.123456+00:00"
    },
    {
      "run_id": "660e8400-...",
      "pipeline": "research",
      "status": "pending_approval",
      "company_slug": "stripe",
      "current_step": "persona",
      "created_at": "2026-02-16T14:00:00.000000+00:00",
      "updated_at": "2026-02-16T14:05:30.000000+00:00"
    }
  ]
}
```

### Get Task Detail

```
GET /api/v1/tasks/{task_id}
```

**Response (200):** Full `TaskResponse` (same shape as pipeline-specific status endpoints).

### Cancel Task

```
POST /api/v1/tasks/{task_id}/cancel
```

Only tasks with status `running` or `pending_approval` can be cancelled.

**Response (200):**

```json
{
  "run_id": "550e8400-...",
  "status": "cancelled"
}
```

**Error (409):** Task is not in a cancellable state.

```json
{
  "detail": "Cannot cancel task in completed state"
}
```

---

## 11. Artifacts (File Serving)

Artifacts are the files produced by each pipeline. The API serves them directly from the filesystem.

### List Companies

```
GET /api/v1/artifacts/companies
```

**Response (200):**

```json
{
  "companies": ["carta", "ramp", "stripe"]
}
```

### List Artifact Files

```
GET /api/v1/artifacts/{artifact_type}/{slug}
```

**Valid artifact types:** `company_context` · `personas` · `style_guides` · `gap_analysis` · `content`

**Response (200):**

```json
{
  "artifact_type": "gap_analysis",
  "slug": "ramp",
  "files": [
    { "name": "gap_report.md", "size": 12345 },
    { "name": "gap_report.json", "size": 5678 },
    { "name": "generation_spec.json", "size": 3456 },
    { "name": "visualizations/gap_heatmap.html", "size": 234567 },
    { "name": "visualizations/umap.html", "size": 345678 },
    { "name": "visualizations/radar.html", "size": 123456 }
  ]
}
```

### Get Artifact Content

```
GET /api/v1/artifacts/{artifact_type}/{slug}/{filename}
```

The response content type depends on the file extension:

| Extension | Content-Type | Description |
|-----------|-------------|-------------|
| `.json` | `application/json` | Parsed JSON |
| `.html` | `text/html` | HTML (visualizations, etc.) |
| `.md`, others | `text/plain` | Plain text (markdown, etc.) |

**Examples:**

```bash
# Get markdown report
curl http://localhost:8000/api/v1/artifacts/gap_analysis/ramp/gap_report.md

# Get JSON report (returns parsed JSON)
curl http://localhost:8000/api/v1/artifacts/gap_analysis/ramp/gap_report.json

# Get HTML visualization (embed in iframe)
curl http://localhost:8000/api/v1/artifacts/gap_analysis/ramp/visualizations/gap_heatmap.html

# Get company context
curl http://localhost:8000/api/v1/artifacts/company_context/ramp/ramp.md

# Get persona
curl http://localhost:8000/api/v1/artifacts/personas/ramp/ramp__persona-icp.md
```

---

## 12. Gap Analysis Data (Read-Only)

These endpoints serve pre-computed gap analysis artifacts for the **Signal Analysis dashboard**. All data is read from `artifacts/gap_analysis/{slug}/` JSON files with mtime-based caching.

> **Slug validation:** All endpoints validate `slug` against `^[a-z0-9][a-z0-9-]*$`. Returns `400` for invalid slugs.

### Summary

```
GET /api/v1/companies/{slug}/gap-analysis/summary
```

Executive overview: SPA score, proximity stats, gap classifications, cluster performance, and recommendations.

**Response (200):**

```json
{
  "spa_score": {
    "t_stat": -3.45,
    "p_value": 0.002,
    "effect": "significant_gap",
    "mean_citation_similarity": 0.78,
    "mean_company_similarity": 0.52,
    "median_citation_similarity": 0.81,
    "median_company_similarity": 0.54
  },
  "proximity_stats": {
    "citation_similarity_mean": 0.78,
    "citation_similarity_median": 0.81,
    "company_similarity_mean": 0.52,
    "company_similarity_median": 0.54
  },
  "classification_counts": {
    "significant_gap": 24,
    "gap_to_close": 18,
    "roughly_equal": 12,
    "company_wins": 6
  },
  "cluster_performance": [
    {
      "cluster_id": "c1",
      "cluster_name": "Product Features",
      "query_count": 15,
      "citation_count": 45,
      "avg_gap": 0.28,
      "avg_citation_sim": 0.82,
      "avg_company_sim": 0.58,
      "structural_rates": { "has_faq": 0.62, "has_comparison_table": 0.44 }
    }
  ],
  "total_queries": 60,
  "total_citations": 210,
  "average_gap": 0.26,
  "executive_summary": "Ramp has a 26 point gap...",
  "recommendations": [
    { "type": "content_pattern", "cluster": "Product Features", "pattern": "comparison_table", "adoption": 0.44 }
  ]
}
```

**Error (404):** No gap analysis data found for slug.

### Queries

```
GET /api/v1/companies/{slug}/gap-analysis/queries
```

Paginated, filterable query list for the **Query Intelligence** tab.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `cluster` | string | `null` | Filter by cluster name or ID |
| `classification` | string | `null` | Filter: `significant_gap` · `gap_to_close` · `roughly_equal` · `company_wins` |
| `search` | string | `null` | Substring search on query text |
| `sort_by` | string | `gap_score` | Sort field (`gap_score` · `company_sim` · `citation_sim` · `query_text`) |
| `sort_dir` | string | `desc` | Sort direction: `asc` or `desc` |
| `page` | int | `1` | Page number (1-indexed, min: 1) |
| `page_size` | int | `15` | Items per page (min: 1, max: 100) |

**Response (200):**

```json
{
  "queries": [
    {
      "query_id": "q-0",
      "query_text": "how to automate expense reports",
      "cluster_id": "c1",
      "cluster_name": "Product Features",
      "gap_score": 0.32,
      "classification": "significant_gap",
      "company_sim": 0.45,
      "citation_sim": 0.78,
      "target_words": { "min": 800, "max": 1200 },
      "reading_level": { "min": 7.2, "max": 9.5 },
      "headers": 4,
      "patterns": ["faq", "comparison_table"],
      "top_domain": "competitor.com",
      "top_exemplar_sim": 0.82,
      "platform_citations": { "chatgpt": 3, "claude": 2, "perplexity": 4, "gemini": 2 },
      "content_brief": {
        "target_word_count": { "min": 800, "max": 1200 },
        "target_reading_level": { "min": 7.2, "max": 9.5 },
        "recommended_header_count": 4,
        "header_hierarchy": { "h1": 1, "h2": 2, "h3": 3 },
        "content_patterns": ["faq", "comparison_table"],
        "dominant_authority": "vendor",
        "dominant_content_type": "guide",
        "exemplars_analyzed": 12
      },
      "top_exemplars": [
        {
          "similarity": 0.82,
          "domain": "competitor.com",
          "url": "https://competitor.com/features",
          "snippet": "Our product offers five key features...",
          "authority_type": "vendor",
          "content_type": "guide"
        }
      ]
    }
  ],
  "total": 60,
  "page": 1,
  "page_size": 15,
  "total_pages": 4
}
```

### Clusters

```
GET /api/v1/companies/{slug}/gap-analysis/clusters
```

Cluster specifications with centroid distances, structural rates, and exemplar themes. Used for the **Content Briefs** tab.

**Response (200):**

```json
{
  "clusters": [
    {
      "cluster_id": "c1",
      "cluster_name": "Product Features",
      "query_count": 15,
      "citations_analyzed": 45,
      "centroid_distance": 0.28,
      "min_similarity_threshold": 0.70,
      "word_count_range": { "min": 800, "max": 1400 },
      "required_elements": ["introduction", "key_takeaways", "comparison_table"],
      "structural_rates": { "has_faq": 0.62, "has_comparison_table": 0.44 },
      "avg_word_count": 1050.5,
      "faq_rate": 0.62,
      "table_rate": 0.44,
      "key_takeaways_rate": 0.51,
      "dominant_content_type": "guide",
      "dominant_authority_type": "vendor",
      "exemplar_themes": ["comparison", "use_cases", "implementation"]
    }
  ]
}
```

### Signals

```
GET /api/v1/companies/{slug}/gap-analysis/signals
```

Structural signal analysis: citation vs. company averages, correlations with citation similarity, and per-cluster content pattern adoption rates. Used for the **Structural Signals** tab.

**Response (200):**

```json
{
  "signals": [
    {
      "signal": "header_count",
      "category": "structure",
      "citation_avg": 4.2,
      "company_avg": 2.8,
      "unit": "count",
      "recommendation": "Increase header count from 2-3 to 4-5"
    }
  ],
  "correlations": [
    { "signal": "header_count", "correlation": 0.68, "category": "structure" }
  ],
  "cluster_patterns": [
    {
      "cluster_id": "c1",
      "cluster_name": "Product Features",
      "faq": 0.62,
      "definition_opening": 0.44,
      "key_takeaways": 0.51,
      "comparison_table": 0.44,
      "step_by_step": 0.33,
      "research_refs": 0.22,
      "expert_quotes": 0.18
    }
  ],
  "cluster_fingerprints": {
    "c1": { "has_faq": 0.62, "has_comparison_table": 0.44, "has_step_by_step": 0.33 }
  }
}
```

### Platforms

```
GET /api/v1/companies/{slug}/gap-analysis/platforms
```

Per-platform citation breakdown with agreement matrix and citation exclusivity. Used for the **Platform Intelligence** tab.

**Response (200):**

```json
{
  "platforms": [
    {
      "name": "ChatGPT",
      "total_citations": 48,
      "unique_domains": 12,
      "avg_citation_sim": 0.79,
      "most_cited_domain": "competitor.com",
      "best_cluster": "c1",
      "worst_cluster": "c3",
      "per_cluster": { "c1": 18, "c2": 15, "c3": 12 }
    }
  ],
  "agreement": {
    "c1": { "ChatGPT": 0.85, "Claude": 0.78, "Perplexity": 0.81, "Gemini": 0.72 }
  },
  "citation_exclusivity": {
    "c1": { "ChatGPT_only": 3, "Claude_only": 2, "exclusive_to_one": 5, "cited_by_all_4": 8 }
  }
}
```

### Heatmap

```
GET /api/v1/companies/{slug}/gap-analysis/heatmap
```

Gap score heatmap grouped by cluster. Clusters sorted by average gap (descending), queries within clusters sorted by gap score (descending).

**Response (200):**

```json
{
  "clusters": [
    {
      "cluster_name": "Product Features",
      "cluster_id": "c1",
      "queries": [
        { "query_id": "q-0", "query_text": "how to automate expense reports", "gap_score": 0.32, "classification": "significant_gap" },
        { "query_id": "q-1", "query_text": "product feature comparison", "gap_score": 0.28, "classification": "significant_gap" }
      ],
      "avg_gap": 0.30
    }
  ],
  "min_gap": 0.02,
  "max_gap": 0.45
}
```

`min_gap` and `max_gap` are global across all queries — use for heatmap scale normalization.

### Embeddings

```
GET /api/v1/companies/{slug}/gap-analysis/embeddings
```

2D embedding projections for scatter plot visualization. Shows spatial relationships between queries, citations, and company content.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | `umap` | Projection method: `umap` or `tsne` |

**Response (200):**

```json
{
  "method": "umap",
  "point_count": 156,
  "points": [
    {
      "x": 0.32, "y": -0.18,
      "type": "query",
      "id": "q-0",
      "label": "how to automate expense reports",
      "cluster": "Product Features",
      "cluster_id": "c1",
      "query_id": "q-0",
      "similarity": null,
      "gap_score": 0.32
    },
    {
      "x": 0.48, "y": 0.22,
      "type": "citation",
      "id": "c-14",
      "label": "competitor.com/features",
      "cluster": "Product Features",
      "cluster_id": "c1",
      "query_id": "q-0",
      "similarity": 0.82,
      "gap_score": null
    },
    {
      "x": 0.24, "y": -0.32,
      "type": "company",
      "id": "co-3",
      "label": "ramp.com/blog/features",
      "cluster": "Product Features",
      "cluster_id": "c1",
      "query_id": null,
      "similarity": 0.45,
      "gap_score": null
    }
  ]
}
```

**Point types:** `query` · `citation` · `company`. Color by cluster, size/shape by type.

### Trend

```
GET /api/v1/companies/{slug}/gap-analysis/trend
```

SPA score trend across completed gap analysis runs. Shows improvement over time.

**Response (200):**

```json
{
  "trend": [
    {
      "run_id": "550e8400-...",
      "run": "Feb 18",
      "timestamp": "2026-02-18T14:30:00Z",
      "spa_score": -2.8,
      "citation_advantage": 0.24,
      "company_advantage": -0.28,
      "total_queries": 60,
      "total_citations": 210
    },
    {
      "run_id": "660e8400-...",
      "run": "Feb 22",
      "timestamp": "2026-02-22T10:15:00Z",
      "spa_score": -1.9,
      "citation_advantage": 0.18,
      "company_advantage": -0.22,
      "total_queries": 62,
      "total_citations": 215
    }
  ]
}
```

`spa_score` is the t-statistic: negative = citations win, positive = company wins. `run` is a short date label for the x-axis. Sorted by timestamp ascending.

---

## 13. Content Data (Read-Only)

These endpoints serve content pipeline artifacts for the **Content Pipeline workspace**. All data is read from `artifacts/content/{slug}/` files.

### List Briefs

```
GET /api/v1/companies/{slug}/content/briefs
```

List all content briefs with inferred statuses and evaluation scores.

**Response (200):**

```json
{
  "briefs": [
    {
      "id": "brief-0",
      "title": "How to Automate Expense Reports",
      "status": "approved",
      "content_type": "blog",
      "cluster": "Product Features",
      "target_word_count": 1200,
      "citability_score": 82.5,
      "cycle_id": "cycle-1",
      "created_at": "2026-02-20T10:00:00Z",
      "updated_at": "2026-02-22T15:30:00Z"
    }
  ],
  "total": 5
}
```

**Status values:** `suggested` (brief created, no stages completed) · `approved` (passed evaluation, has final content) · `published` (marked as published in run_metadata).

`citability_score` is derived from eval `overall_score` (0–100 scale), `null` if no evaluation exists.

### Get Brief Detail

```
GET /api/v1/companies/{slug}/content/briefs/{brief_id}
```

Full detail for a single content brief, including evaluation history, exemplars, and available stages.

**Path Parameters:**
- `brief_id` — Format `brief-{N}` (e.g., `brief-0`, `brief-12`)

**Response (200):**

```json
{
  "id": "brief-0",
  "title": "How to Automate Expense Reports",
  "status": "approved",
  "content_type": "blog",
  "cluster": "Product Features",
  "target_word_count": { "min": 800, "max": 1400 },
  "structural_targets": { "has_faq": true, "has_comparison_table": true, "header_count": 4 },
  "key_topics": ["expense automation", "receipt scanning", "policy compliance"],
  "key_angles": ["vendor_perspective", "use_cases", "comparison"],
  "priority_score": 0.92,
  "citability_score": 82.5,
  "eval_history": [
    {
      "cycle": 1,
      "dimensions": [
        { "dimension": "structural", "passed": true, "score": 0.88, "feedback": "Good header hierarchy" },
        { "dimension": "semantic", "passed": true, "score": 0.85, "feedback": "Strong topical alignment" },
        { "dimension": "style", "passed": true, "score": 0.79, "feedback": "Matches style guide" },
        { "dimension": "factual", "passed": true, "score": 0.81, "feedback": "No factual errors" }
      ],
      "overall_passed": true,
      "overall_score": 0.825
    }
  ],
  "final_passed": true,
  "exemplars": [
    {
      "url": "https://competitor.com/features",
      "word_count": 1250,
      "authority_type": "vendor",
      "content_type": "guide",
      "snippet": "Our platform offers five core features..."
    }
  ],
  "available_stages": ["outline", "draft", "enriched", "formatted", "eval_history", "final"]
}
```

**Error (400):** Invalid `brief_id` format. **Error (404):** Brief not found.

### Get Stage Content

```
GET /api/v1/companies/{slug}/content/briefs/{brief_id}/{stage}
```

Get stage-specific file content for a brief.

**Path Parameters:**
- `brief_id` — Format `brief-{N}`
- `stage` — One of: `outline` · `draft` · `enriched` · `formatted` · `eval_history` · `final`

**Response (200) — Markdown stages** (draft, enriched, formatted, final):

```json
{
  "brief_id": "brief-0",
  "stage": "final",
  "content_type": "text/markdown",
  "content": "# How to Automate Expense Reports\n\n## Introduction\n..."
}
```

**Response (200) — JSON stages** (outline, eval_history):

```json
{
  "brief_id": "brief-0",
  "stage": "outline",
  "content_type": "application/json",
  "content": {
    "title": "How to Automate Expense Reports",
    "sections": [
      { "heading": "Introduction", "key_points": ["Problem statement", "Solution overview"] }
    ]
  }
}
```

**Error (400):** Invalid `stage` name. **Error (404):** Stage file not found.

---

## 14. Brand Data (Read-Only)

Research artifacts and pipeline run history endpoints.

### Research Artifacts

```
GET /api/v1/companies/{slug}/research/artifacts
```

Returns all research artifacts (company context, personas, style guide) with full content and status.

**Response (200):**

```json
{
  "company_context": {
    "content": "# Ramp Company Context\n\nRamp is a corporate spend management platform...",
    "status": "approved",
    "updated_at": "2026-02-20T10:00:00Z"
  },
  "personas": [
    {
      "id": "persona-icp",
      "name": "Persona Icp",
      "type": "icp",
      "content": "# ICP Persona\n\nTarget: Fortune 500 CFOs...",
      "status": "approved",
      "updated_at": "2026-02-20T10:05:00Z"
    },
    {
      "id": "persona-secondary-1",
      "name": "Persona Secondary 1",
      "type": "secondary",
      "content": "# Secondary Persona\n\nTarget: Finance Managers...",
      "status": "approved",
      "updated_at": "2026-02-20T10:10:00Z"
    }
  ],
  "style_guide": {
    "content": "# Ramp Writing Style Guide\n\nTone: Professional yet approachable...",
    "status": "approved",
    "updated_at": "2026-02-20T10:15:00Z"
  }
}
```

**Status values:** `none` · `draft` · `approved`

**Notes:**
- Persona `id` is extracted from filename (e.g., `persona-icp` from `ramp__persona-icp.md`)
- Persona `type` is `icp` if filename contains "icp", else `secondary`
- Approved artifacts (`.md`) take priority over drafts (`.draft.md`)
- Only files matching `{slug}__persona-*.md` are included
- `content` is `null` if file cannot be read

### Run History

```
GET /api/v1/companies/{slug}/runs
```

Run history across all pipelines for a company. Supports filtering by pipeline type and status.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pipeline` | string | `null` | Filter: `research` · `gap_analysis` · `content` |
| `status` | string | `null` | Filter: `running` · `completed` · `failed` (see status mapping below) |
| `limit` | int | `50` | Max results (min: 1, max: 200) |

**Status mapping (backend → frontend):**
- `pending_approval` → `running`
- `cancelled` → `failed`
- All other statuses passed through as-is

Filtering by `status=running` will also match `pending_approval` tasks.

**Response (200):**

```json
{
  "runs": [
    {
      "id": "550e8400-...",
      "pipeline": "gap_analysis",
      "company": "Ramp",
      "company_slug": "ramp",
      "status": "completed",
      "started": "2026-02-22T10:00:00Z",
      "duration": "3h 46m",
      "queries": 60,
      "citations": 210,
      "spa_score": -2.8,
      "steps_completed": 8,
      "total_steps": 8
    },
    {
      "id": "660e8400-...",
      "pipeline": "research",
      "company": "Ramp",
      "company_slug": "ramp",
      "status": "completed",
      "started": "2026-02-20T14:00:00Z",
      "duration": "52m",
      "queries": 0,
      "citations": 0,
      "spa_score": 0.0,
      "steps_completed": 3,
      "total_steps": 3
    }
  ],
  "total": 2
}
```

**Notes:**
- `duration` is human-readable (e.g., `"3h 46m"`, `"52m"`, `"10s"`)
- `queries`, `citations`, `spa_score` are populated from gap_analysis results; `0` for other pipelines
- `total_steps`: 8 for gap_analysis, 3 for research, 4 for content
- Sorted by `started` descending (newest first)

---

## 15. Server-Sent Events (SSE)

### Endpoint

```
GET /api/v1/tasks/{task_id}/events
```

**Headers:**
- `Accept: text/event-stream`
- `Last-Event-ID: {id}` — optional, for reconnection (replays events after this ID)

**Response Headers:**
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no`

### Wire Format

Each event is SSE-formatted:

```
id: 1
event: pipeline_start
data: {"pipeline": "research"}

id: 2
event: stage_start
data: {"stage": "company"}

id: 3
event: pending_approval
data: {"stage": "company", "status": "pending_approval", "draft_path": "...", "artifact_md": "..."}

id: 4
event: approval_received
data: {"stage": "company", "decision": "approve"}

id: 5
event: stage_complete
data: {"stage": "company"}

id: 6
event: stage_start
data: {"stage": "persona"}

...

id: 10
event: completed
data: {"pipeline": "research"}

```

### Event Types

| Event | Data | When |
|-------|------|------|
| `pipeline_start` | `{ "pipeline": "research\|gap_analysis\|content" }` | Pipeline execution begins |
| `stage_start` | `{ "stage": "company\|persona\|style" }` | Research stage begins |
| `pending_approval` | `{ "stage": "...", ...interrupt_payload }` | Waiting for human decision |
| `approval_received` | `{ "stage": "...", "decision": "..." }` | Human decision submitted |
| `stage_complete` | `{ "stage": "..." }` | Research stage finished |
| `completed` | `{ "pipeline": "..." }` | Pipeline finished successfully |
| `failed` | `{ "error": "exception message" }` | Pipeline encountered an error |
| `cancelled` | `{}` | Task was cancelled |

### Terminal Events

The stream **automatically closes** after emitting one of: `completed`, `failed`, `cancelled`. You do not need to manually close the connection.

### JavaScript Integration

```typescript
function streamPipelineEvents(
  taskId: string,
  onEvent: (type: string, data: any) => void,
  onDone: () => void,
  lastEventId?: number
): EventSource {
  const url = `http://localhost:8000/api/v1/tasks/${taskId}/events`;
  const eventSource = new EventSource(url);

  // Listen for all named events
  const eventTypes = [
    'pipeline_start', 'stage_start', 'pending_approval',
    'approval_received', 'stage_complete',
    'completed', 'failed', 'cancelled'
  ];

  for (const type of eventTypes) {
    eventSource.addEventListener(type, (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      onEvent(type, data);

      // Terminal events — close the connection
      if (['completed', 'failed', 'cancelled'].includes(type)) {
        eventSource.close();
        onDone();
      }
    });
  }

  eventSource.onerror = () => {
    // Browser will auto-reconnect with Last-Event-ID header
    console.warn('SSE connection error, reconnecting...');
  };

  return eventSource;
}

// Usage
const es = streamPipelineEvents(
  runId,
  (type, data) => {
    switch (type) {
      case 'pending_approval':
        showApprovalDialog(data);
        break;
      case 'completed':
        showResults(data);
        break;
      case 'failed':
        showError(data.error);
        break;
    }
  },
  () => console.log('Stream ended')
);
```

### Reconnection with Last-Event-ID

The browser's `EventSource` automatically sends `Last-Event-ID` on reconnection. The server replays all events after that ID, so you never miss events. The bounded history holds the last 100 events per task.

For manual reconnection (e.g., with `fetch`):

```typescript
async function reconnectStream(taskId: string, lastEventId: number) {
  const response = await fetch(
    `http://localhost:8000/api/v1/tasks/${taskId}/events`,
    { headers: { 'Last-Event-ID': lastEventId.toString() } }
  );
  // Parse SSE stream from response.body...
}
```

---

## 16. Human-in-the-Loop (HITL) Approval Flow

### Research Pipeline HITL

The research pipeline has up to 3 approval gates — one per stage (company, persona, style guide). Each stage follows this flow:

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as API Server
    participant Agent as AI Agent

    FE->>API: POST /research/start
    API-->>FE: 202 { run_id }
    FE->>API: GET /tasks/{run_id}/events (SSE)

    Agent->>Agent: Research company...
    API-->>FE: SSE: stage_start {stage: "company"}
    Agent->>Agent: Write draft artifact
    API-->>FE: SSE: pending_approval {stage, artifact_md, draft_path}

    Note over FE: Display draft to user for review

    FE->>API: POST /research/{run_id}/approve {decision: "revise", revision_note: "Add more on pricing"}
    API-->>FE: 200 { run_id, decision }
    API-->>FE: SSE: approval_received {stage, decision: "revise"}

    Agent->>Agent: Revise with feedback...
    API-->>FE: SSE: pending_approval {stage, artifact_md, draft_path}

    Note over FE: Display revised draft

    FE->>API: POST /research/{run_id}/approve {decision: "approve"}
    API-->>FE: SSE: approval_received {stage, decision: "approve"}
    API-->>FE: SSE: stage_complete {stage: "company"}
    API-->>FE: SSE: stage_start {stage: "persona"}

    Note over FE: Repeat approval flow for persona and style_guide stages

    API-->>FE: SSE: completed {pipeline: "research"}
```

**Key points:**
- Each "revise" decision loops the agent back — it re-researches with your feedback, then asks for approval again
- "reject" stops the pipeline immediately
- "approve" finalizes the stage and moves to the next one
- The `approval_payload` in the status response contains the draft content (`artifact_md`) for display
- Set `auto_approve: true` in the start request to skip all approval gates

### Content Pipeline HITL

Content generation produces multiple content pieces. Each piece goes through HITL review individually:

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as API Server

    FE->>API: POST /content/start
    API-->>FE: 202 { run_id }
    FE->>API: GET /tasks/{run_id}/events (SSE)

    API-->>FE: SSE: pipeline_start
    API-->>FE: SSE: pending_approval {brief_id, title, content_preview, eval_summary}

    Note over FE: Display content piece for review

    FE->>API: POST /content/{run_id}/approve {brief_id: "brief-001", decision: "approve"}
    API-->>FE: SSE: approval_received {brief_id, decision}

    Note over FE: Next piece...

    API-->>FE: SSE: pending_approval {brief_id: "brief-002", ...}
    FE->>API: POST /content/{run_id}/approve {brief_id: "brief-002", decision: "edit", editor_notes: "Shorten the intro"}

    API-->>FE: SSE: completed {pipeline: "content"}
```

**Content approval decisions:**
- **`approve`** — Content is finalized as-is
- **`edit`** — Agent applies your `editor_notes` feedback, then returns for approval again
- **`reject`** — Content piece is discarded

### Detecting HITL State

Two ways to detect when approval is needed:

**1. Via SSE (real-time):**
Listen for `pending_approval` events in your SSE stream.

**2. Via polling:**
Poll the status endpoint. When `status === "pending_approval"`, read `approval_payload` for the draft content:

```typescript
async function pollForApproval(runId: string, pipeline: string) {
  const response = await fetch(
    `http://localhost:8000/api/v1/${pipeline}/${runId}/status`
  );
  const task = await response.json();

  if (task.status === 'pending_approval') {
    // task.approval_payload contains draft content
    // task.current_step tells you which stage
    showApprovalUI(task.approval_payload, task.current_step);
  }
}
```

---

## 17. Integration Patterns

### Pattern 1: Launch Pipeline + Stream Progress

The most common pattern — start a pipeline and show real-time progress:

```typescript
async function launchAndStream(pipeline: 'research' | 'gap_analysis' | 'content', body: any) {
  // 1. Start the pipeline
  const startRes = await fetch(`http://localhost:8000/api/v1/${pipeline.replace('_', '-')}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (startRes.status === 409) {
    const err = await startRes.json();
    alert(`Conflict: ${err.detail}`);
    return;
  }

  const { run_id } = await startRes.json();

  // 2. Stream events
  const es = new EventSource(
    `http://localhost:8000/api/v1/tasks/${run_id}/events`
  );

  es.addEventListener('pipeline_start', () => setStatus('Running...'));
  es.addEventListener('stage_start', (e) => {
    const { stage } = JSON.parse(e.data);
    setStatus(`Running ${stage}...`);
  });
  es.addEventListener('pending_approval', (e) => {
    const data = JSON.parse(e.data);
    showApprovalDialog(run_id, pipeline, data);
  });
  es.addEventListener('completed', () => {
    es.close();
    setStatus('Done!');
    loadResults(run_id, pipeline);
  });
  es.addEventListener('failed', (e) => {
    es.close();
    const { error } = JSON.parse(e.data);
    setStatus(`Failed: ${error}`);
  });

  return run_id;
}
```

### Pattern 2: Poll-Based Status Checking

Simpler alternative if you don't want SSE:

```typescript
async function pollStatus(runId: string, pipeline: string, intervalMs = 3000) {
  const url = pipeline === 'gap_analysis'
    ? `http://localhost:8000/api/v1/gap-analysis/${runId}/status`
    : `http://localhost:8000/api/v1/${pipeline}/${runId}/status`;

  const poll = setInterval(async () => {
    const res = await fetch(url);
    const task = await res.json();

    updateUI(task);

    if (['completed', 'failed', 'cancelled'].includes(task.status)) {
      clearInterval(poll);
    }
  }, intervalMs);
}
```

### Pattern 3: HITL Approval Workflow

Complete approval flow with revision support:

```typescript
async function handleApproval(
  runId: string,
  pipeline: 'research' | 'content',
  approvalData: any
) {
  // Show the draft content to the user
  const userDecision = await showReviewModal({
    stage: approvalData.stage || approvalData.brief_id,
    content: approvalData.artifact_md || approvalData.content_preview,
  });
  // userDecision = { decision: 'approve' | 'revise' | 'reject', note?: string }

  const endpoint = `http://localhost:8000/api/v1/${pipeline}/${runId}/approve`;

  let body: any;
  if (pipeline === 'research') {
    body = {
      decision: userDecision.decision,
      revision_note: userDecision.note || null,
    };
  } else {
    body = {
      brief_id: approvalData.brief_id,
      decision: userDecision.decision === 'revise' ? 'edit' : userDecision.decision,
      editor_notes: userDecision.note || null,
    };
  }

  await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
```

### Pattern 4: Artifact Browsing

List companies, then their artifacts, then display content:

```typescript
async function browseArtifacts() {
  // 1. Get all companies
  const companiesRes = await fetch('http://localhost:8000/api/v1/artifacts/companies');
  const { companies } = await companiesRes.json();
  // companies = ["carta", "ramp", "stripe"]

  // 2. List artifact types for a company
  const types = ['company_context', 'personas', 'style_guides', 'gap_analysis', 'content'];
  for (const type of types) {
    const res = await fetch(`http://localhost:8000/api/v1/artifacts/${type}/${selectedCompany}`);
    if (res.ok) {
      const { files } = await res.json();
      renderFileList(type, files);
    }
  }

  // 3. Get file content
  const contentRes = await fetch(
    `http://localhost:8000/api/v1/artifacts/gap_analysis/ramp/gap_report.json`
  );
  const reportData = await contentRes.json();
  renderReport(reportData);

  // 4. Embed HTML visualizations in an iframe
  // <iframe src="http://localhost:8000/api/v1/artifacts/gap_analysis/ramp/visualizations/gap_heatmap.html" />
}
```

### Pattern 5: Task Dashboard

List, filter, and manage all tasks:

```typescript
async function loadDashboard() {
  // All tasks
  const allRes = await fetch('http://localhost:8000/api/v1/tasks');
  const { tasks } = await allRes.json();

  // Filter running tasks
  const runningRes = await fetch('http://localhost:8000/api/v1/tasks?status=running');
  const running = await runningRes.json();

  // Tasks needing approval
  const pendingRes = await fetch('http://localhost:8000/api/v1/tasks?status=pending_approval');
  const pending = await pendingRes.json();

  // Cancel a task
  async function cancelTask(taskId: string) {
    const res = await fetch(`http://localhost:8000/api/v1/tasks/${taskId}/cancel`, {
      method: 'POST',
    });
    if (res.status === 409) {
      const err = await res.json();
      alert(err.detail); // "Cannot cancel task in completed state"
    }
  }
}
```

---

## 18. Error Handling

### Error Response Shape

All errors return JSON with a `detail` field. Custom exception handlers also include an `error_code` field:

```json
{
  "detail": "Human-readable error message",
  "error_code": "machine_readable_code"
}
```

> **Note:** `error_code` is only present on responses from custom exception handlers (`task_not_found`, `task_conflict`, `pipeline_error`). Standard HTTP errors (400, 409 from endpoints, 422 validation) return only `detail`.

### Error Codes

| HTTP Status | Error Code | Cause | Frontend Action |
|-------------|-----------|-------|----------------|
| **400** | — | Path traversal in artifact path | Show "Invalid file path" |
| **404** | `task_not_found` | Task ID doesn't exist | Show "Task not found" |
| **404** | — | Artifact/file not found | Show "File not found" |
| **409** | `task_conflict` | Concurrent run for same company | Show "A pipeline is already running for this company" |
| **409** | — | Task not in expected state (e.g., cancel completed task, approve non-pending task) | Show the `detail` message |
| **422** | — | Invalid request body or artifact type | Show validation error from `detail` |
| **500** | `pipeline_error` | Unhandled pipeline exception | Show "Pipeline error: {detail}" |

### Common Scenarios

**Starting a pipeline when one is already running:**
```
POST /api/v1/gap-analysis/start → 409
{
  "detail": "A pipeline is already running for company 'ramp' (task_id=550e8400-...)",
  "error_code": "task_conflict"
}
```
Action: Show the existing task ID so the user can monitor or cancel it.

**Approving a task that's not pending:**
```
POST /api/v1/research/{run_id}/approve → 409
{
  "detail": "Task 550e8400-... is not pending approval (current: running)"
}
```
Action: Refresh the task status — the state may have changed.

**Task not found:**
```
GET /api/v1/tasks/{bad_id} → 404
{
  "detail": "Task not found: bad-uuid",
  "error_code": "task_not_found"
}
```

**API keys not configured:**
```
GET /readiness → 200
{
  "ready": false,
  "missing_keys": ["anthropic_api_key", "perplexity_api_key"]
}
```
Action: Show a setup banner listing missing keys.

---

## 19. Data Models Reference

### Response Models

#### PipelineRunResponse
Returned by all `POST /start` endpoints (202).

```typescript
interface PipelineRunResponse {
  run_id: string;          // UUID
  pipeline: string;        // "research" | "gap_analysis" | "content"
  company_slug: string;    // URL-safe company identifier (e.g. "ramp")
  status: string;          // "running"
  created_at: string;      // ISO 8601 datetime
}
```

#### TaskResponse
Returned by all `GET /status` and `GET /tasks/{id}` endpoints.

```typescript
interface TaskResponse {
  run_id: string;
  pipeline: string;
  company_slug: string;                  // URL-safe company identifier
  status: TaskStatus;
  current_step: string | null;           // e.g. "company", "s3_search_platforms"
  progress_pct: number | null;           // 0-100
  created_at: string;                    // ISO 8601
  updated_at: string;                    // ISO 8601
  result: Record<string, any> | null;    // Pipeline-specific result on completion
  error: string | null;                  // Error message on failure
  approval_payload: Record<string, any> | null;  // HITL context when pending
}
```

#### TaskListResponse

```typescript
interface TaskListResponse {
  tasks: TaskSummary[];
}

interface TaskSummary {
  run_id: string;
  pipeline: string;
  status: TaskStatus;
  company_slug: string;
  current_step: string | null;
  created_at: string;
  updated_at: string;
}
```

#### ApprovalResponse

```typescript
interface ApprovalResponse {
  run_id: string;
  decision: string;
  revision_note: string | null;
}
```

#### ContentApprovalResponse

```typescript
interface ContentApprovalResponse {
  run_id: string;
  brief_id: string;
  decision: string;
  editor_notes: string | null;
}
```

#### CancelResponse

```typescript
interface CancelResponse {
  run_id: string;
  status: string;  // "cancelled"
}
```

#### ErrorResponse

```typescript
interface ErrorResponse {
  detail: string;
  error_code?: string;  // "task_not_found" | "task_conflict" | "pipeline_error"
}
```

#### ProducedArtifact

Included in every pipeline's `result.produced_artifacts` array on completion. Tells the frontend which `GET /artifacts/{type}/{slug}` calls to make.

```typescript
interface ProducedArtifact {
  type: string;   // "company_context" | "personas" | "style_guides" | "gap_analysis" | "content"
  slug: string;   // Company slug (e.g. "ramp")
}
```

**Which pipeline produces what:**

| Pipeline | `produced_artifacts` |
|----------|---------------------|
| **research** | `company_context`, `personas`, `style_guides` (depends on `stages` requested) |
| **gap_analysis** | `gap_analysis` |
| **content** | `content` |

### Auth Models

#### RegisterRequest

```typescript
interface RegisterRequest {
  first_name: string;
  last_name: string;
  email: string;                               // EmailStr validated
  password: string;                            // 8–128 chars
  company_name: string;
  company_domain: string;
}
```

#### LoginRequest

```typescript
interface LoginRequest {
  email: string;                               // EmailStr validated
  password: string;                            // 8–128 chars
}
```

#### LoginResponse

```typescript
interface LoginResponse {
  access_token: string;                        // JWT token
  token_type: string;                          // "bearer"
  user: UserResponse;
  company: CompanyResponse;
}
```

#### UserResponse

```typescript
interface UserResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;                                // "superuser" | "admin" | "member"
  company_id: string;
  is_active: boolean;
}
```

#### CompanyResponse

```typescript
interface CompanyResponse {
  id: string;
  slug: string;
  name: string;
  domain: string;
}
```

#### MeResponse

```typescript
interface MeResponse {
  user: UserResponse;
  company: CompanyResponse;
}
```

### Company Profile Models

#### CompanyProfileResponse

```typescript
interface CompanyProfileResponse {
  slug: string;
  name: string;
  domain: string;
  products: ProductSummary[];
  has_research: boolean;
  has_gap_analysis: boolean;
  has_content: boolean;
  research_summary: ResearchArtifactSummary;
  latest_runs: Record<string, LatestRunSummary | null>;
}

interface ProductSummary {
  slug: string;
  name: string;
  has_research: boolean;
  has_gap_analysis: boolean;
  has_content: boolean;
}

interface ResearchArtifactSummary {
  company_context: string | null;              // Filename or null
  company_context_status: string;              // "none" | "draft" | "approved"
  personas: string[];                          // Filenames
  style_guide: string | null;
  style_guide_status: string;
}

interface LatestRunSummary {
  run_id: string;
  status: string;
  created_at: string;                          // ISO 8601
  completed_at: string | null;
  summary: Record<string, any> | null;
}
```

### Gap Analysis Data Models

#### GapSummaryResponse

```typescript
interface GapSummaryResponse {
  spa_score: SPAScore;
  proximity_stats: ProximityStats;
  classification_counts: GapClassificationCounts;
  cluster_performance: ClusterPerformanceRow[];
  total_queries: number;
  total_citations: number;
  average_gap: number;
  executive_summary: string;
  recommendations: Record<string, any>[];
}

interface SPAScore {
  t_stat: number;
  p_value: number;
  effect: string;                              // "significant_gap" | "gap_to_close" | "roughly_equal" | "company_wins"
  mean_citation_similarity: number;
  mean_company_similarity: number;
  median_citation_similarity: number;
  median_company_similarity: number;
}

interface ProximityStats {
  citation_similarity_mean: number;
  citation_similarity_median: number;
  company_similarity_mean: number;
  company_similarity_median: number;
}

interface GapClassificationCounts {
  significant_gap: number;
  gap_to_close: number;
  roughly_equal: number;
  company_wins: number;
}

interface ClusterPerformanceRow {
  cluster_id: string | null;
  cluster_name: string;
  query_count: number;
  citation_count: number;
  avg_gap: number;
  avg_citation_sim: number;
  avg_company_sim: number;
  structural_rates: Record<string, number>;
}
```

#### QueryListResponse

```typescript
interface QueryListResponse {
  queries: QueryRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface QueryRow {
  query_id: string;
  query_text: string;
  cluster_id: string | null;
  cluster_name: string | null;
  gap_score: number;
  classification: string;
  company_sim: number;
  citation_sim: number;
  target_words: { min: number; max: number };
  reading_level: { min: number; max: number };
  headers: number;
  patterns: string[];
  top_domain: string | null;
  top_exemplar_sim: number;
  platform_citations: Record<string, number>;
  content_brief: QueryContentBrief | null;
  top_exemplars: QueryExemplar[];
}

interface QueryContentBrief {
  target_word_count: { min: number; max: number };
  target_reading_level: { min: number; max: number };
  recommended_header_count: number;
  header_hierarchy: Record<string, number>;
  content_patterns: string[];
  dominant_authority: string | null;
  dominant_content_type: string | null;
  exemplars_analyzed: number;
}

interface QueryExemplar {
  similarity: number;
  domain: string | null;
  url: string;
  snippet: string | null;
  authority_type: string | null;
  content_type: string | null;
}
```

#### ClusterListResponse

```typescript
interface ClusterListResponse {
  clusters: ClusterSpecResponse[];
}

interface ClusterSpecResponse {
  cluster_id: string | null;
  cluster_name: string;
  query_count: number;
  citations_analyzed: number;
  centroid_distance: number | null;
  min_similarity_threshold: number | null;
  word_count_range: { min: number; max: number };
  required_elements: string[];
  structural_rates: Record<string, number>;
  avg_word_count: number;
  faq_rate: number;
  table_rate: number;
  key_takeaways_rate: number;
  dominant_content_type: string | null;
  dominant_authority_type: string | null;
  exemplar_themes: string[];
}
```

#### SignalAveragesResponse

```typescript
interface SignalAveragesResponse {
  signals: SignalAverageRow[];
  correlations: SignalCorrelationRow[];
  cluster_patterns: ClusterPatternRow[];
  cluster_fingerprints: Record<string, Record<string, number>>;
}

interface SignalAverageRow {
  signal: string;
  category: string;
  citation_avg: number;
  company_avg: number;
  unit: string;
  recommendation: string;
}

interface SignalCorrelationRow {
  signal: string;
  correlation: number;
  category: string;
}

interface ClusterPatternRow {
  cluster_id: string;
  cluster_name: string;
  faq: number;
  definition_opening: number;
  key_takeaways: number;
  comparison_table: number;
  step_by_step: number;
  research_refs: number;
  expert_quotes: number;
}
```

#### PlatformListResponse

```typescript
interface PlatformListResponse {
  platforms: PlatformSummaryResponse[];
  agreement: Record<string, Record<string, number>>;
  citation_exclusivity: Record<string, Record<string, number>>;
}

interface PlatformSummaryResponse {
  name: string;
  total_citations: number;
  unique_domains: number;
  avg_citation_sim: number;
  most_cited_domain: string | null;
  best_cluster: string | null;
  worst_cluster: string | null;
  per_cluster: Record<string, number>;
}
```

#### HeatmapResponse

```typescript
interface HeatmapResponse {
  clusters: HeatmapCluster[];
  min_gap: number;
  max_gap: number;
}

interface HeatmapCluster {
  cluster_name: string;
  cluster_id: string | null;
  queries: HeatmapQuery[];
  avg_gap: number;
}

interface HeatmapQuery {
  query_id: string;
  query_text: string;
  gap_score: number;
  classification: string;
}
```

#### EmbeddingProjectionResponse

```typescript
interface EmbeddingProjectionResponse {
  method: string;                              // "umap" | "tsne"
  point_count: number;
  points: EmbeddingPoint[];
}

interface EmbeddingPoint {
  x: number;
  y: number;
  type: string;                                // "query" | "citation" | "company"
  id: string;
  label: string;
  cluster: string;
  cluster_id: string;
  query_id: string | null;
  similarity: number | null;
  gap_score: number | null;
}
```

#### SPATrendResponse

```typescript
interface SPATrendResponse {
  trend: SPATrendPoint[];
}

interface SPATrendPoint {
  run_id: string;
  run: string;                                 // Short date label: "Feb 18"
  timestamp: string;                           // ISO 8601
  spa_score: number;                           // t-statistic
  citation_advantage: number;
  company_advantage: number;
  total_queries: number;
  total_citations: number;
}
```

### Content Data Models

#### ContentBriefListResponse

```typescript
interface ContentBriefListResponse {
  briefs: ContentBriefListItem[];
  total: number;
}

interface ContentBriefListItem {
  id: string;                                  // brief_id (e.g., "brief-0")
  title: string;
  status: string;                              // "suggested" | "approved" | "published"
  content_type: string;                        // "blog" | "guide" | etc.
  cluster: string;
  target_word_count: number;
  citability_score: number | null;             // 0–100
  cycle_id: string | null;
  created_at: string;                          // ISO 8601
  updated_at: string;
}
```

#### ContentBriefDetailResponse

```typescript
interface ContentBriefDetailResponse {
  id: string;
  title: string;
  status: string;
  content_type: string;
  cluster: string;
  target_word_count: { min: number; max: number };
  structural_targets: Record<string, any>;
  key_topics: string[];
  key_angles: string[];
  priority_score: number;
  citability_score: number | null;
  eval_history: EvalCycle[];
  final_passed: boolean;
  exemplars: BriefExemplar[];
  available_stages: string[];                  // e.g., ["outline", "draft", "final"]
}

interface EvalCycle {
  cycle: number;
  dimensions: EvalDimension[];
  overall_passed: boolean;
  overall_score: number;                       // 0–1
}

interface EvalDimension {
  dimension: string;                           // "structural" | "semantic" | "style" | "factual"
  passed: boolean;
  score: number;                               // 0–1
  feedback: string;
}

interface BriefExemplar {
  url: string;
  word_count: number;
  authority_type: string;
  content_type: string;
  snippet: string;
}
```

#### StageContentResponse

```typescript
interface StageContentResponse {
  brief_id: string;
  stage: string;                               // "outline" | "draft" | "enriched" | "formatted" | "eval_history" | "final"
  content_type: string;                        // "text/markdown" | "application/json"
  content: string | Record<string, any>;       // String for markdown, object for JSON
}
```

### Brand Data Models

#### ResearchArtifactsResponse

```typescript
interface ResearchArtifactsResponse {
  company_context: ArtifactContent;
  personas: PersonaArtifact[];
  style_guide: ArtifactContent;
}

interface ArtifactContent {
  content: string | null;
  status: string;                              // "none" | "draft" | "approved"
  updated_at: string | null;                   // ISO 8601
}

interface PersonaArtifact {
  id: string;                                  // e.g., "persona-icp"
  name: string;                                // e.g., "Persona Icp"
  type: string;                                // "icp" | "secondary"
  content: string;
  status: string;                              // "draft" | "approved"
  updated_at: string | null;
}
```

#### RunHistoryResponse

```typescript
interface RunHistoryResponse {
  runs: RunHistoryItem[];
  total: number;
}

interface RunHistoryItem {
  id: string;                                  // Task ID
  pipeline: string;                            // "gap_analysis" | "research" | "content"
  company: string;                             // Display name
  company_slug: string;
  status: string;                              // Mapped: "running" | "completed" | "failed"
  started: string;                             // ISO 8601
  duration: string;                            // Human-readable: "3h 46m"
  queries: number;                             // Gap analysis only (0 for others)
  citations: number;
  spa_score: number;
  steps_completed: number;
  total_steps: number;                         // 8=gap, 3=research, 4=content
}
```

### Enums

#### TaskStatus

```typescript
type TaskStatus =
  | 'running'
  | 'pending_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'failed_restart';    // Orphan recovery — task was running when server restarted
```

### Request Models

#### GapAnalysisStartRequest (simplified)

```typescript
interface GapAnalysisStartRequest {
  company_name: string;                      // Required
  domain: string;                            // Required
  seed_urls?: string[];                      // Default: []
  skip_steps?: number[];                     // Default: []
  max_queries?: number;                      // Default: 150 (10-500)
  platforms?: string[];                      // Default: ["perplexity","openai","gemini","claude"]
  language?: string;                         // Default: "en"
  region?: string;
  additional_constraints?: string;
  max_crawl_pages?: number;
  max_crawl_depth?: number;
}
```

> The backend constructs `GapAnalysisInput` internally: derives `company_slug` from `company_name`, and auto-resolves `company_context_path`, `persona_paths`, and `style_guide_path` from the artifacts directory.

#### ResearchStartRequest (simplified)

```typescript
interface ResearchStartRequest {
  company_name: string;                      // Required
  domain: string;                            // Required
  seed_urls?: string[];                      // Default: [https://{domain}/]
  stages?: ('company' | 'persona' | 'style_guide')[];  // Default: all three
  auto_approve?: boolean;                    // Default: false
  language?: string;                         // Default: "en"
  region?: string;
  max_personas?: number;                     // Default: 3 (1-3)
  internal_sources?: string[];               // Default: []
  additional_constraints?: string;
}
```

> The backend constructs per-stage inputs (CompanyResearchInput, PersonaResearchInput, StyleGuideResearchInput) internally and chains artifact paths between stages automatically.

#### ContentStartRequest

```typescript
interface ContentStartRequest {
  input_data: ContentGenerationInput;
}
```

#### ApprovalRequest

```typescript
interface ApprovalRequest {
  decision: 'approve' | 'revise' | 'reject';
  revision_note?: string | null;
}
```

#### ContentApprovalRequest

```typescript
interface ContentApprovalRequest {
  brief_id: string;
  decision: 'approve' | 'edit' | 'reject';
  editor_notes?: string | null;
}
```

### Pipeline Input Models

#### GapAnalysisInput (internal — constructed by backend)

```typescript
// Frontend does NOT send this directly. The backend constructs it
// from the simplified GapAnalysisStartRequest fields and auto-resolved
// artifact paths from the filesystem.
interface GapAnalysisInput {
  company_name: string;
  company_slug?: string;                     // Derived from company_name
  domain?: string;
  seed_urls?: string[];                      // Default: []
  company_context_path?: string;             // Auto-resolved from artifacts/company_context/{slug}.md
  persona_paths?: string[];                  // Auto-resolved from artifacts/personas/{slug}__persona-*.md
  style_guide_path?: string;                 // Auto-resolved from artifacts/style_guides/{slug}.md
  max_queries?: number;                      // Default: 150 (10-500)
  platforms?: string[];                      // Default: ["perplexity","openai","gemini","claude"]
  language?: string;                         // Default: "en"
  region?: string;
  additional_constraints?: string;
  max_crawl_pages?: number;
  max_crawl_depth?: number;
}
```

#### CompanyResearchInput (internal — constructed by backend)

```typescript
// Frontend does NOT send this directly. The backend constructs it
// from the simplified ResearchStartRequest fields.
interface CompanyResearchInput {
  company_name: string;
  domain?: string;
  seed_urls?: string[];
  internal_sources?: string[];
  language?: string;
  region?: string;
  additional_constraints?: string;
}
```

#### PersonaResearchInput (internal — constructed by backend)

```typescript
// Backend auto-populates company_context_path from the company stage output.
interface PersonaResearchInput {
  company_name: string;
  domain?: string;
  company_slug?: string;
  company_context_path?: string;             // Auto-linked from company stage
  max_personas?: number;
  language?: string;
  region?: string;
}
```

#### StyleGuideResearchInput (internal — constructed by backend)

```typescript
// Backend auto-populates company_context_path and persona_paths from prior stages.
interface StyleGuideResearchInput {
  company_name: string;
  domain?: string;
  company_slug?: string;
  company_context_path?: string;             // Auto-linked from company stage
  persona_paths?: string[];                  // Auto-linked from persona stage
  language?: string;
  region?: string;
}
```

#### ContentGenerationInput

```typescript
interface ContentGenerationInput {
  company_name: string;                      // Required
  domain: string;                            // Required
  company_context_path?: string;
  persona_paths?: string[];                  // Default: []
  style_guide_path?: string;
  gap_report_json_path?: string;
  generation_spec_json_path?: string;
  analysis_json_path?: string;
  max_briefs?: number;                       // Default: 10
  max_concurrent_workers?: number;           // Default: 3
  max_revision_cycles?: number;              // Default: 2
  auto_approve?: boolean;                    // Default: false
  skip_stages?: number[];                    // Default: []
}
```

---

## 20. Artifact Directory Structure

```
artifacts/
├── company_context/                     ← Flat layout
│   ├── ramp.md                          ← Finalized company context
│   ├── ramp.draft.md                    ← Draft (before approval)
│   ├── carta.md
│   └── stripe.md
│
├── personas/                            ← Flat layout
│   ├── ramp__persona-icp.md             ← ICP persona
│   ├── ramp__persona-secondary-1.md     ← Secondary persona #1
│   ├── ramp__persona-secondary-2.md     ← Secondary persona #2
│   ├── carta__persona-icp.md
│   └── stripe__persona-icp.md
│
├── style_guides/                        ← Flat layout
│   ├── ramp.md
│   ├── carta.md
│   └── stripe.md
│
├── gap_analysis/                        ← Nested layout
│   └── ramp/
│       ├── company_embeddings.json      ← Embedded company content
│       ├── site_discovery/
│       │   ├── discovered_pages.json
│       │   ├── site_tree.json
│       │   └── discovery_summary.json
│       ├── queries.json                 ← Generated search queries
│       ├── platform_results/
│       │   ├── openai_results.jsonl
│       │   ├── claude_results.jsonl
│       │   ├── gemini_results.jsonl
│       │   └── perplexity_results.jsonl
│       ├── enriched_citations.json      ← Crawled + enriched cited pages
│       ├── embeddings/
│       │   ├── queries_with_embeddings.json
│       │   └── citations_with_embeddings.json
│       ├── analysis.json                ← Semantic proximity analysis
│       ├── visualizations/
│       │   ├── gap_heatmap.html         ← Embed in iframe
│       │   ├── umap.html
│       │   ├── radar.html
│       │   └── treemap.html
│       ├── gap_report.md                ← Human-readable report
│       ├── gap_report.json              ← Structured report data
│       ├── generation_spec.md           ← Content generation spec
│       └── generation_spec.json
│
├── content/                             ← Nested layout
│   └── ramp/
│       ├── briefs.json                  ← All content briefs
│       ├── run_metadata.json
│       └── content/
│           ├── brief-001/
│           │   ├── outline.json
│           │   ├── draft.md
│           │   ├── enriched.md
│           │   ├── formatted.md
│           │   ├── eval_history.json
│           │   └── final.md             ← Approved final content
│           └── brief-002/
│               └── ...
│
└── _jobs/                               ← Task persistence (internal)
    ├── 550e8400-....json
    └── 660e8400-....json
```

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Company context | `{slug}.md` | `ramp.md` |
| Company context draft | `{slug}.draft.md` | `ramp.draft.md` |
| Persona (ICP) | `{slug}__persona-icp.md` | `ramp__persona-icp.md` |
| Persona (secondary) | `{slug}__persona-secondary-{n}.md` | `ramp__persona-secondary-1.md` |
| Style guide | `{slug}.md` | `ramp.md` |
| Gap analysis | `{slug}/{file}` | `ramp/gap_report.json` |
| Content | `{slug}/content/brief-{id}/{file}` | `ramp/content/brief-001/final.md` |

### Which Pipeline Produces What

| Pipeline | Artifacts | Key Files for Display |
|----------|-----------|----------------------|
| **Research** | company_context, personas, style_guides | `{slug}.md` — rendered markdown |
| **Gap Analysis** | gap_analysis/{slug}/ | `gap_report.json` — structured data, `visualizations/*.html` — embed in iframes |
| **Content** | content/{slug}/ | `briefs.json` — brief list, `content/brief-{id}/final.md` — approved content |
