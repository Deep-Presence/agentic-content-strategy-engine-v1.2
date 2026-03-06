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
| `POST` | `/api/v1/content/v13/start` | Launch content v1.3 pipeline | 202 |
| `GET` | `/api/v1/content/v13/{run_id}/status` | Get content v1.3 status | 200 |
| `POST` | `/api/v1/content/v13/{run_id}/approve/topics` | HITL-1 topic approval (v1.3) | 200 |
| `POST` | `/api/v1/content/v13/{run_id}/approve/briefs` | HITL-2 brief approval (v1.3) | 200 |
| `POST` | `/api/v1/content/v13/{run_id}/approve/content` | HITL-3 content review (v1.3) | 200 |
| `POST` | `/api/v1/site-audit/start` | Launch site audit pipeline | 202 |
| `GET` | `/api/v1/site-audit/status/{run_id}` | Get site audit status | 200 |
| `POST` | `/api/v1/knowledge-base/start` | Launch knowledge base pipeline | 202 |
| `GET` | `/api/v1/knowledge-base/{run_id}/status` | Get knowledge base status | 200 |
| `POST` | `/api/v1/knowledge-base/{run_id}/approve` | Submit HITL approval (KB) | 200 |
| `GET` | `/api/v1/knowledge-base/{slug}/health` | KB health & staleness report | 200 |
| `POST` | `/api/v1/knowledge-base/{slug}/refresh-stale` | Refresh only stale KB docs | 202 |
| `POST` | `/api/v1/audience-persona/start` | Launch audience persona pipeline | 202 |
| `GET` | `/api/v1/audience-persona/{run_id}/status` | Get audience persona status | 200 |
| `POST` | `/api/v1/audience-persona/{run_id}/approve/briefs` | HITL-1 brief approval (AP) | 200 |
| `POST` | `/api/v1/audience-persona/{run_id}/approve/profiles` | HITL-2 profile approval (AP) | 200 |
| `POST` | `/api/v1/audience-persona/{slug}/add-persona` | Add standalone persona | 202 |
| `POST` | `/api/v1/audience-persona/{slug}/personas/{persona_id}/approve` | Approve/reject standalone persona | 200 |
| `GET` | `/api/v1/audience-persona/{slug}/personas` | List all personas | 200 |
| `POST` | `/api/v1/cps/score` | Score content for citation probability | 200 |
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

### Site Audit Data

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/site-audit/companies/{slug}/audits` | List all audits for a company | 200 |
| `GET` | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}` | Full audit detail with scores | 200 |
| `GET` | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}/findings` | Paginated findings (filterable) | 200 |
| `GET` | `/api/v1/site-audit/companies/{slug}/audits/{audit_id}/pages` | Paginated per-page results | 200 |

### Knowledge Documents

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `POST` | `/api/v1/companies/{slug}/knowledge-docs` | Upload a knowledge document | 201 |
| `GET` | `/api/v1/companies/{slug}/knowledge-docs` | List knowledge documents | 200 |
| `GET` | `/api/v1/companies/{slug}/knowledge-docs/{doc_id}` | Get document metadata | 200 |
| `DELETE` | `/api/v1/companies/{slug}/knowledge-docs/{doc_id}` | Delete a document | 204 |
| `GET` | `/api/v1/companies/{slug}/knowledge-docs/{doc_id}/download` | Download document file | 200 |

### Company Settings

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `GET` | `/api/v1/companies/{slug}/settings/team` | List team members | 200 |
| `PUT` | `/api/v1/companies/{slug}/settings/team/{user_id}` | Update team member (superuser) | 200 |
| `GET` | `/api/v1/companies/{slug}/settings/profile` | Get company profile settings | 200 |
| `PUT` | `/api/v1/companies/{slug}/settings/profile` | Update company profile (superuser) | 200 |
| `GET` | `/api/v1/companies/{slug}/settings/pipeline-defaults` | Get pipeline default overrides | 200 |
| `PUT` | `/api/v1/companies/{slug}/settings/pipeline-defaults` | Update pipeline defaults (superuser) | 200 |

### Daily Tracker

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| `POST` | `/api/v1/daily-tracker/prompts` | Create a tracked prompt | 201 |
| `GET` | `/api/v1/daily-tracker/prompts` | List tracked prompts (filterable) | 200 |
| `GET` | `/api/v1/daily-tracker/prompts/{prompt_id}` | Get a specific prompt | 200 |
| `PUT` | `/api/v1/daily-tracker/prompts/{prompt_id}` | Update a prompt | 200 |
| `DELETE` | `/api/v1/daily-tracker/prompts/{prompt_id}` | Delete a prompt | 204 |
| `PATCH` | `/api/v1/daily-tracker/prompts/{prompt_id}/toggle` | Toggle active status | 200 |
| `POST` | `/api/v1/daily-tracker/prompts/import` | Import from gap analysis queries | 201 |
| `POST` | `/api/v1/daily-tracker/prompts/bulk` | Bulk create prompts | 201 |
| `POST` | `/api/v1/daily-tracker/runs` | Trigger a daily tracking run | 202 |
| `GET` | `/api/v1/daily-tracker/runs/{run_id}` | Get run status | 200 |
| `GET` | `/api/v1/daily-tracker/runs` | List runs for company | 200 |
| `GET` | `/api/v1/daily-tracker/analytics/visibility` | Overall visibility metrics | 200 |
| `GET` | `/api/v1/daily-tracker/analytics/mention-trend` | Mention rate over time | 200 |
| `GET` | `/api/v1/daily-tracker/analytics/sov` | Share of voice vs competitors | 200 |
| `GET` | `/api/v1/daily-tracker/analytics/citations` | Citation rates | 200 |
| `GET` | `/api/v1/daily-tracker/analytics/competitors` | Per-competitor metrics | 200 |

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

The system has 6 pipelines:

| Pipeline | What it does | Has HITL? |
|----------|-------------|-----------|
| **site_audit** | Deterministic crawl + 8-dimension page analysis (no LLM) | No |
| **research** | AI agents research a company, build persona profiles, and create writing style guides | Yes — approve/revise/reject each stage |
| **knowledge_base** | 6-agent DAG builds company knowledge (overview, reviews, competitors, etc.) | Yes — 3 HITL checkpoints |
| **gap_analysis** | Crawls company site, generates search queries, queries 4 AI platforms, analyzes citation gaps | No |
| **content** | Uses research + gap analysis outputs to auto-generate optimized content pieces | Yes — approve/edit/reject each brief |
| **content_v13** | v1.3 pipeline: Strategic Planner → Brief Builder → Workers → Evaluator → HITL | Yes — 3 HITL checkpoints (topics, briefs, content) |

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

### Already-Exists Guard

Site audit and knowledge base pipelines support an **already-exists guard**. If a completed run already exists for the company/product scope, the start endpoint returns `200` instead of `202` with `already_exists: true`. Pass `force_rerun: true` in the request to bypass this guard.

### Slug Locks

Only one pipeline can run per company at a time. If you try to start a second gap analysis for "ramp" while one is already running, you get `409 Conflict`. The lock is released when the task completes, fails, or is cancelled.

### Product Scoping

Pipelines support optional **product-level scoping** via `product_slug`. When set, the effective slug becomes `{company_slug}__{product_slug}` (double underscore). Artifacts are stored in product-scoped directories.

### Concurrency Limit

A global semaphore limits total concurrent pipeline runs (default: 3). Tasks exceeding this limit queue until a slot opens.

---

## 4. Authentication & CORS

### Authentication

The API uses **JWT Bearer tokens** for authentication. Auth state is backed by a JSON file store (`api/auth/store.py`).

**Middleware:** `AuthMiddleware` runs on every request. It parses the `Authorization: Bearer {token}` header and sets `request.state.user_id` and `request.state.company_slug`. Endpoints that don't require auth simply ignore these values.

**Roles:** `superuser` · `admin` · `member` · `viewer`. Most pipeline endpoints require `member` or `superuser`. Settings endpoints require `superuser`. Read-only endpoints require any authenticated user.

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

**Error (400):** Invalid slug format (doesn't match regex).

**Error (404):** Company not found in auth store AND no artifacts exist on filesystem.

---

## 7. Site Audit Pipeline

### Start Site Audit

```
POST /api/v1/site-audit/start
```

Launch the deterministic 6-step site audit pipeline. No LLM required. Crawls the domain, analyzes each page across 8 dimensions (crawlability, performance, on-page SEO, extractability, schema markup, E-E-A-T, freshness, security), and produces a scored report.

**Auth:** Requires `member` or `superuser` role. Tenant-isolated (slug must match authenticated user's company).

**Request Body:**

```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "product_slug": null,
  "max_pages": 200,
  "max_depth": 4,
  "check_core_web_vitals": true,
  "check_schema_validation": true,
  "check_ai_bot_access": true,
  "force_rerun": false
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name (derives slug) |
| `domain` | string | Yes | — | Domain to audit |
| `product_slug` | string | No | `null` | Product scope |
| `max_pages` | int | No | `200` | Max pages to crawl (1–2000) |
| `max_depth` | int | No | `4` | Max crawl depth (1–10) |
| `check_core_web_vitals` | bool | No | `true` | Check Core Web Vitals signals |
| `check_schema_validation` | bool | No | `true` | Validate JSON-LD schema markup |
| `check_ai_bot_access` | bool | No | `true` | Check AI-bot access in robots.txt |
| `force_rerun` | bool | No | `false` | Bypass already-exists guard |

**Response (202):** `PipelineRunResponse` with `pipeline: "site_audit"`.

**Response (200):** When audit already exists and `force_rerun` is false. Returns `already_exists: true` and a `message`.

### Get Site Audit Status

```
GET /api/v1/site-audit/status/{run_id}
```

**Auth:** Requires authentication. Tenant-isolated.

**Response (200):** Standard `TaskResponse`.

### List Audits

```
GET /api/v1/site-audit/companies/{slug}/audits
```

List all completed site audits for a company, most recent first.

**Auth:** Requires tenant access.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Max results (1–100) |

**Response (200):**

```json
[
  {
    "audit_id": "abc-123",
    "domain": "ramp.com",
    "overall_score": 72.5,
    "grade": "C",
    "pages_crawled": 150,
    "total_findings": 45,
    "status": "completed",
    "started_at": "2026-03-01T10:00:00Z",
    "completed_at": "2026-03-01T10:15:00Z"
  }
]
```

### Get Audit Detail

```
GET /api/v1/site-audit/companies/{slug}/audits/{audit_id}
```

Full detail for a single audit run including per-dimension scores, AI bot access summary, sitemap health, and finding breakdowns.

**Auth:** Requires tenant access.

**Response (200):**

```json
{
  "audit_id": "abc-123",
  "domain": "ramp.com",
  "overall_score": 72.5,
  "grade": "C",
  "pages_crawled": 150,
  "pages_discovered": 200,
  "duration_seconds": 45.2,
  "dimension_scores": [
    {
      "dimension": "crawlability",
      "score": 85.0,
      "weight": 0.15,
      "weighted_score": 12.75,
      "finding_count": 3,
      "critical_count": 0,
      "high_count": 1,
      "medium_count": 2,
      "low_count": 0,
      "info_count": 0
    }
  ],
  "ai_bot_access": {
    "gptbot_allowed": true,
    "claudebot_allowed": true,
    "perplexitybot_allowed": true,
    "google_extended_allowed": true,
    "ccbot_allowed": true,
    "has_llms_txt": false,
    "robots_txt_exists": true
  },
  "sitemap_health": {
    "has_sitemap": true,
    "sitemap_url_count": 180,
    "sitemap_urls": ["https://ramp.com/sitemap.xml"],
    "sitemap_errors": [],
    "has_sitemap_index": false
  },
  "total_findings": 45,
  "findings_by_severity": { "critical": 2, "high": 8, "medium": 20, "low": 10, "info": 5 },
  "findings_by_dimension": { "crawlability": 3, "on_page_seo": 12, "schema_markup": 8 },
  "avg_snippet_readiness": 0.65,
  "pages_with_schema": 42,
  "avg_question_heading_ratio": 0.12,
  "status": "completed",
  "error_message": null,
  "started_at": "2026-03-01T10:00:00Z",
  "completed_at": "2026-03-01T10:15:00Z"
}
```

### Get Audit Findings

```
GET /api/v1/site-audit/companies/{slug}/audits/{audit_id}/findings
```

Paginated findings with optional severity/dimension filters.

**Auth:** Requires tenant access.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `severity` | string | `null` | Filter: `critical` · `high` · `medium` · `low` · `info` |
| `dimension` | string | `null` | Filter: `crawlability` · `performance` · `on_page_seo` · `extractability` · `schema_markup` · `eeat` · `freshness` · `security` |
| `page` | int | `1` | 1-based page number |
| `page_size` | int | `50` | Items per page (1–200) |

**Response (200):**

```json
{
  "findings": [
    {
      "finding_type": "missing_meta_description",
      "dimension": "on_page_seo",
      "severity": "medium",
      "message": "Page is missing a meta description",
      "recommendation": "Add a unique meta description of 150-160 characters",
      "url": "https://ramp.com/pricing",
      "details": {}
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

### Get Audit Pages

```
GET /api/v1/site-audit/companies/{slug}/audits/{audit_id}/pages
```

Paginated per-page audit results with AEO readiness and schema detection.

**Auth:** Requires tenant access.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | `1` | 1-based page number |
| `page_size` | int | `50` | Items per page (1–200) |

**Response (200):**

```json
{
  "pages": [
    {
      "url": "https://ramp.com/blog/expense-reports",
      "status_code": 200,
      "crawl_depth": 2,
      "title": "How to Automate Expense Reports",
      "word_count": 1250,
      "reading_level": 8.2,
      "has_https": true,
      "is_noindex": false,
      "schema": {
        "has_schema": true,
        "schema_types": ["Article", "FAQPage"],
        "validation_errors": [],
        "inferred_page_type": "article"
      },
      "aeo": {
        "snippet_readiness_score": 0.78,
        "question_heading_ratio": 0.25,
        "quick_answer_hook_count": 3,
        "self_contained_paragraph_ratio": 0.6,
        "avg_paragraph_word_count": 45.0,
        "content_patterns": { "has_faq": true, "has_definition": false }
      },
      "finding_count": 2
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

---

## 8. Gap Analysis (Pipeline Operations)

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
  "max_crawl_depth": 3,
  "force_rerun": false
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `product_slug` | string | No | `null` | Product scope |
| `seed_urls` | string[] | No | `[]` | URLs to crawl |
| `force_rerun` | bool | No | `false` | Bypass already-exists guard |
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

---

## 9. Research Pipeline (Pipeline Operations)

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
  "max_personas": 3,
  "force_rerun": false
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `product_slug` | string | No | `null` | Product scope |
| `seed_urls` | string[] | No | `[https://{domain}/]` | URLs for the research agent to study |
| `force_rerun` | bool | No | `false` | Bypass already-exists guard |
| `stages` | string[] | No | `["company","persona","style_guide"]` | Which stages to run |
| `auto_approve` | bool | No | `false` | Skip HITL gates |
| `language` | string | No | `"en"` | Language code |
| `region` | string | No | `null` | Region context |
| `max_personas` | int | No | `3` | 1-3 (1 ICP + up to 2 secondary) |
| `internal_sources` | string[] | No | `[]` | Paths to internal transcripts/notes |
| `additional_constraints` | string | No | `null` | Extra instructions for the research agents |

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

**What happens after each decision:**
- **`approve`** — Stage output is finalized, pipeline moves to the next stage (or completes)
- **`revise`** — Agent re-runs with the `revision_note` as feedback, then returns to `pending_approval` again
- **`reject`** — Pipeline stops, task status becomes `completed`

---

## 10. Knowledge Base Pipeline

The knowledge base pipeline runs a 6-agent DAG with 3 HITL checkpoints:

- **Phase 1** (parallel): Company Overview, Customer Reviews, Competitor Registry
- **HITL Checkpoint 1:** Review P1 outputs
- **Phase 2** (sequential): Weakness Analysis, Brand Perception
- **HITL Checkpoint 2:** Review P2 outputs
- **Phase 3:** Synthesis
- **HITL Checkpoint 3:** Review final synthesis

### Start Knowledge Base

```
POST /api/v1/knowledge-base/start
```

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

**Request Body:**

```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "product_slug": null,
  "mode": "full",
  "auto_approve_checkpoints": [],
  "language": "en",
  "staleness_threshold_days": 30,
  "force_rerun": false
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `product_slug` | string | No | `null` | Product scope |
| `seed_urls` | string[] | No | `[]` | URLs for agent research |
| `force_rerun` | bool | No | `false` | Bypass already-exists guard |
| `mode` | string | No | `"full"` | `"full"` · `"refresh"` · `"single"` |
| `refresh_docs` | string[] | No | `null` | Doc types to refresh (mode=refresh) |
| `single_doc` | string | No | `null` | Single doc type to run (mode=single) |
| `auto_approve_checkpoints` | int[] | No | `[]` | Checkpoint numbers to auto-approve (1, 2, 3) |
| `language` | string | No | `"en"` | Language code |
| `region` | string | No | `null` | Region context |
| `internal_sources` | string[] | No | `[]` | Internal source paths |
| `additional_constraints` | string | No | `null` | Extra instructions |
| `staleness_threshold_days` | int | No | `30` | Staleness threshold (1–365) |

**Valid `refresh_docs` / `single_doc` values:** `"company_overview"` · `"customer_reviews"` · `"competitor_registry"` · `"weakness_analysis"` · `"brand_perception"`

**Response (202):** `PipelineRunResponse` with `pipeline: "knowledge_base"`.

**Response (200):** When artifacts already exist and `force_rerun` is false.

### Get Knowledge Base Status

```
GET /api/v1/knowledge-base/{run_id}/status
```

**Auth:** Requires authentication. Tenant-isolated.

**Response (200):** Standard `TaskResponse`. When `status` is `"pending_approval"`, the `approval_payload` contains the checkpoint stage and draft documents for review.

### Submit Knowledge Base Approval

```
POST /api/v1/knowledge-base/{run_id}/approve
```

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

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
| `revision_note` | string | No | — | Feedback for the agent(s) (required if `"revise"`) |

When revising, the `revision_note` is applied to all doc types in the current checkpoint (e.g., checkpoint 1 applies to company_overview, customer_reviews, and competitor_registry).

### Get Knowledge Base Health

```
GET /api/v1/knowledge-base/{slug}/health
```

Returns a health report for the knowledge base — staleness, missing docs, overall score.

**Auth:** Requires authentication. Tenant-isolated.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold_override` | int | `null` | Override staleness threshold (1–365 days) |

**Response (200):**

```json
{
  "slug": "ramp",
  "overall_score": 0.85,
  "doc_health": {
    "company_overview": {
      "doc_type": "company_overview",
      "status": "fresh",
      "current_version": 2,
      "last_updated": "2026-03-01T10:00:00Z",
      "age_days": 5,
      "staleness_threshold_days": 90,
      "stale_reason": null,
      "dependencies": []
    },
    "customer_reviews": {
      "doc_type": "customer_reviews",
      "status": "stale",
      "current_version": 1,
      "last_updated": "2026-01-15T10:00:00Z",
      "age_days": 50,
      "staleness_threshold_days": 30,
      "stale_reason": "age_exceeded",
      "dependencies": ["company_overview"]
    }
  },
  "synthesis_version": 1,
  "synthesis_last_updated": "2026-03-01T10:15:00Z",
  "synthesis_needs_refresh": false,
  "stale_docs": ["customer_reviews"],
  "missing_docs": [],
  "last_full_refresh": "2026-03-01T10:00:00Z"
}
```

### Refresh Stale Knowledge Base

```
POST /api/v1/knowledge-base/{slug}/refresh-stale
```

Refresh only stale/missing KB docs. Returns `200` if everything is fresh.

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

**Request Body:**

```json
{
  "domain": "ramp.com",
  "product_slug": null,
  "staleness_threshold_override": null,
  "auto_approve_checkpoints": [],
  "include_synthesis": true
}
```

**Response (202):** `PipelineRunResponse` when stale docs found and refresh launched.

**Response (200):** When all documents are fresh. Returns `already_exists: true` with `message: "All documents are fresh"`.

---

## 11. Content Generation (Pipeline Operations)

### Start Content Generation

```
POST /api/v1/content/start
```

**Request Body:**

```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "max_briefs": 5,
  "auto_approve": false,
  "max_concurrent_workers": 3,
  "max_revision_cycles": 2,
  "skip_stages": []
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `product_slug` | string | No | `null` | Product scope |
| `max_briefs` | int | No | `5` | Max content pieces (1–20) |
| `auto_approve` | bool | No | `false` | Skip HITL review gates |
| `gap_slug` | string | No | `null` | Gap analysis slug to use |
| `max_concurrent_workers` | int | No | `3` | Parallel content workers (1–10) |
| `max_revision_cycles` | int | No | `2` | Max revision cycles (0–5) |
| `skip_stages` | int[] | No | `[]` | Stage numbers to skip |

**Response (202):** `PipelineRunResponse`.

### Get Content Status

```
GET /api/v1/content/{run_id}/status
```

**Response (200):** Standard `TaskResponse`.

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

---

## 12. Content Generation v1.3 Pipeline

The v1.3 pipeline features 3 HITL checkpoints with a Strategic Planner → Brief Builder → Workers → Evaluator architecture.

### Start Content v1.3

```
POST /api/v1/content/v13/start
```

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

**Request Body:**

```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "entry_mode": "autonomous",
  "max_topics": 6,
  "gap_slug": null,
  "auto_approve": false,
  "max_concurrent_workers": 3,
  "max_revision_cycles": 2,
  "skip_stages": []
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company_name` | string | Yes | — | Company name |
| `domain` | string | Yes | — | Company domain |
| `entry_mode` | string | No | `"autonomous"` | `"autonomous"` (from gap analysis) or `"manual"` |
| `max_topics` | int | No | `6` | Max topics to select (1–15) |
| `gap_slug` | string | No | `null` | Gap analysis slug for autonomous mode |
| `manual_prompt` | string | No | `null` | Manual topic query (max 2000 chars) |
| `manual_description` | string | No | `null` | Manual topic description (max 2000 chars) |
| `manual_cluster` | string | No | `null` | Manual cluster name |
| `product_slug` | string | No | `null` | Product scope |
| `product_name` | string | No | `null` | Product name override |
| `product_description` | string | No | `null` | Product description override |
| `auto_approve` | bool | No | `false` | Skip all HITL gates |
| `max_concurrent_workers` | int | No | `3` | Parallel workers (1–10) |
| `max_revision_cycles` | int | No | `2` | Max revision cycles (0–5) |
| `skip_stages` | int[] | No | `[]` | Stage numbers to skip |

**Response (202):**

```json
{
  "run_id": "770e8400-...",
  "status": "started",
  "entry_mode": "autonomous"
}
```

### Get Content v1.3 Status

```
GET /api/v1/content/v13/{run_id}/status
```

**Auth:** Requires authentication. Tenant-isolated.

**Response (200):**

```json
{
  "task_id": "770e8400-...",
  "status": "pending_approval",
  "current_step": "topic_approval",
  "progress_pct": 25.0,
  "error": null,
  "result": null,
  "approval_payload": {
    "stage": "topic_approval",
    "topics": [...]
  }
}
```

### HITL-1: Approve Topics

```
POST /api/v1/content/v13/{run_id}/approve/topics
```

Submit topic approval after Strategic Planner selects topics.

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

**Request Body:**

```json
{
  "decision": "approve",
  "approved_topic_ranks": [0, 1, 2],
  "added_query_ids": [],
  "removed_query_ids": [],
  "feedback": null
}
```

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `decision` | string | Yes | `"approve"` · `"modify"` · `"reject"` · `"retry"` | Topic decision |
| `approved_topic_ranks` | int[] | No | `[]` | Ranks of approved topics (non-negative) |
| `added_query_ids` | string[] | No | `[]` | Additional query IDs to include (for modify) |
| `removed_query_ids` | string[] | No | `[]` | Query IDs to exclude (for modify) |
| `feedback` | string | No | `null` | Guidance for retry |

**Response (200):**

```json
{
  "status": "accepted",
  "stage": "topic_approval",
  "message": "Topic approve submitted"
}
```

### HITL-2: Approve Brief

```
POST /api/v1/content/v13/{run_id}/approve/briefs
```

Submit brief approval after Brief Builder creates a content blueprint.

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

**Request Body:**

```json
{
  "brief_id": "brief-0",
  "decision": "approve",
  "feedback": null
}
```

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `brief_id` | string | Yes | — | Brief identifier |
| `decision` | string | Yes | `"approve"` · `"feedback"` · `"reject"` | Brief decision |
| `feedback` | string | No | `null` | Feedback for the agent |

### HITL-3: Approve Content

```
POST /api/v1/content/v13/{run_id}/approve/content
```

Submit final content review after Workers + Evaluator produce the content.

**Auth:** Requires `member` or `superuser` role. Tenant-isolated.

**Request Body:**

```json
{
  "brief_id": "brief-0",
  "decision": "approve",
  "editor_notes": null,
  "rethink": false
}
```

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `brief_id` | string | Yes | — | Brief identifier |
| `decision` | string | Yes | `"approve"` · `"edit"` · `"reject"` | Content decision |
| `editor_notes` | string | No | `null` | Editing feedback (max 5000 chars) |
| `rethink` | bool | No | `false` | If true on reject, trigger major direction change |

**CPS Score in Review:** The HITL-3 review state includes a CPS (Citation Signal Predictor) score in `eval_summary.cps` when available. This predicts how likely the content is to be cited by AI answer engines (0.0–1.0). The CPS score is informational and does not gate approval.

```json
{
  "eval_summary": {
    "overall_score": 0.85,
    "overall_passed": true,
    "dimensions": { ... },
    "cps": {
      "cps_score": 0.72,
      "per_engine": {
        "chatgpt_search": 0.75,
        "claude_search": 0.68,
        "gemini_search": 0.71,
        "perplexity": 0.74
      },
      "per_query": [{"query": "best CRM software", "cps_score": 0.72}],
      "model_version": "v1",
      "feature_config": "option_b_full31",
      "target_weight": 0.5
    }
  }
}
```

---

## 13. Task Management

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
| `pipeline` | string | Filter by pipeline: `research` · `gap_analysis` · `content` · `content_v13` · `site_audit` · `knowledge_base` |
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
      "product_slug": null,
      "effective_slug": "ramp",
      "current_step": null,
      "created_at": "2026-02-16T12:34:56.789123+00:00",
      "updated_at": "2026-02-16T13:45:00.123456+00:00"
    }
  ],
  "total": 1
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

---

## 14. Artifacts (File Serving)

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
    { "name": "gap_report.json", "size": 5678 }
  ]
}
```

### Get Artifact Content

```
GET /api/v1/artifacts/{artifact_type}/{slug}/{filename}
```

| Extension | Content-Type | Description |
|-----------|-------------|-------------|
| `.json` | `application/json` | Parsed JSON |
| `.html` | `text/html` | HTML (visualizations, etc.) |
| `.md`, others | `text/plain` | Plain text (markdown, etc.) |

---

## 15. Gap Analysis Data (Read-Only)

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
| `page` | int | `1` | Page number (1-indexed) |
| `page_size` | int | `15` | Items per page (1–100) |

**Response (200):** Paginated query list with `queries`, `total`, `page`, `page_size`, `total_pages`.

### Clusters

```
GET /api/v1/companies/{slug}/gap-analysis/clusters
```

Cluster specifications with centroid distances, structural rates, and exemplar themes.

### Signals

```
GET /api/v1/companies/{slug}/gap-analysis/signals
```

Structural signal analysis: citation vs. company averages, correlations, and per-cluster content pattern adoption rates.

### Platforms

```
GET /api/v1/companies/{slug}/gap-analysis/platforms
```

Per-platform citation breakdown with agreement matrix and citation exclusivity.

### Heatmap

```
GET /api/v1/companies/{slug}/gap-analysis/heatmap
```

Gap score heatmap grouped by cluster. `min_gap` and `max_gap` for scale normalization.

### Embeddings

```
GET /api/v1/companies/{slug}/gap-analysis/embeddings
```

2D embedding projections for scatter plot visualization.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | `umap` | Projection method: `umap` or `tsne` |

### Trend

```
GET /api/v1/companies/{slug}/gap-analysis/trend
```

SPA score trend across completed gap analysis runs.

---

## 16. Content Data (Read-Only)

These endpoints serve content pipeline artifacts for the **Content Pipeline workspace**.

### List Briefs

```
GET /api/v1/companies/{slug}/content/briefs
```

### Get Brief Detail

```
GET /api/v1/companies/{slug}/content/briefs/{brief_id}
```

### Get Stage Content

```
GET /api/v1/companies/{slug}/content/briefs/{brief_id}/{stage}
```

**Valid stages:** `outline` · `draft` · `enriched` · `formatted` · `eval_history` · `final`

---

## 17. Brand Data (Read-Only)

### Research Artifacts

```
GET /api/v1/companies/{slug}/research/artifacts
```

Returns all research artifacts (company context, personas, style guide) with full content and status.

### Run History

```
GET /api/v1/companies/{slug}/runs
```

Run history across all pipelines for a company.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pipeline` | string | `null` | Filter: `research` · `gap_analysis` · `content` |
| `status` | string | `null` | Filter: `running` · `completed` · `failed` |
| `limit` | int | `50` | Max results (1–200) |

---

## 18. Knowledge Documents

Upload and manage internal knowledge documents (product one-pagers, competitive analyses, etc.) that get embedded alongside public site content.

### Upload Document

```
POST /api/v1/companies/{slug}/knowledge-docs
```

Upload a knowledge document file (PDF, Markdown, TXT, DOCX).

**Auth:** Requires company member access.

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | The document file to upload |

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `product_slug` | string | `null` | Product scope |

**Response (201):**

```json
{
  "id": "doc-abc123",
  "filename": "competitive-analysis.pdf",
  "content_type": "application/pdf",
  "file_size_bytes": 245000,
  "word_count": 3200,
  "uploaded_at": "2026-03-01T10:00:00Z",
  "is_embedded": false,
  "last_embedded_at": null
}
```

### List Documents

```
GET /api/v1/companies/{slug}/knowledge-docs
```

**Auth:** Requires tenant access.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `product_slug` | string | `null` | Product scope |

**Response (200):**

```json
{
  "documents": [
    {
      "id": "doc-abc123",
      "filename": "competitive-analysis.pdf",
      "content_type": "application/pdf",
      "file_size_bytes": 245000,
      "word_count": 3200,
      "uploaded_at": "2026-03-01T10:00:00Z",
      "is_embedded": true,
      "last_embedded_at": "2026-03-01T10:05:00Z"
    }
  ],
  "total": 1
}
```

### Get Document Metadata

```
GET /api/v1/companies/{slug}/knowledge-docs/{doc_id}
```

**Auth:** Requires tenant access.

**Response (200):** Single `KnowledgeDocResponse`.

### Delete Document

```
DELETE /api/v1/companies/{slug}/knowledge-docs/{doc_id}
```

**Auth:** Requires company member access.

**Response (204):** No content.

### Download Document

```
GET /api/v1/companies/{slug}/knowledge-docs/{doc_id}/download
```

**Auth:** Requires tenant access.

**Response:** File download with original filename.

---

## 19. Company Settings

All settings endpoints are scoped under `/api/v1/companies/{slug}/settings/`.

### List Team Members

```
GET /api/v1/companies/{slug}/settings/team
```

**Auth:** Requires tenant access.

**Response (200):**

```json
{
  "members": [
    {
      "id": "user-abc123",
      "email": "john@acme.com",
      "first_name": "John",
      "last_name": "Doe",
      "role": "superuser",
      "is_active": true,
      "created_at": "2026-01-15T10:00:00Z"
    }
  ],
  "total": 1
}
```

### Update Team Member

```
PUT /api/v1/companies/{slug}/settings/team/{user_id}
```

**Auth:** Requires `superuser` role.

**Request Body:**

```json
{
  "role": "member",
  "first_name": null,
  "last_name": null,
  "is_active": true
}
```

All fields are optional — only non-null fields are applied.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `role` | string | `"superuser"` · `"member"` · `"viewer"` | User role |
| `first_name` | string | — | First name |
| `last_name` | string | — | Last name |
| `is_active` | bool | — | Active status |

**Response (200):** Updated `TeamMemberResponse`.

### Get Company Profile Settings

```
GET /api/v1/companies/{slug}/settings/profile
```

**Auth:** Requires tenant access.

**Response (200):**

```json
{
  "slug": "acme-corp",
  "name": "Acme Corp",
  "domain": "acme.com",
  "additional_domains": [],
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

### Update Company Profile Settings

```
PUT /api/v1/companies/{slug}/settings/profile
```

**Auth:** Requires `superuser` role.

**Request Body:**

```json
{
  "name": "Acme Corporation",
  "domain": "acme.com",
  "additional_domains": ["blog.acme.com"]
}
```

All fields are optional — only non-null fields are applied.

### Get Pipeline Defaults

```
GET /api/v1/companies/{slug}/settings/pipeline-defaults
```

**Auth:** Requires tenant access.

**Response (200):**

```json
{
  "max_crawl_pages": null,
  "max_crawl_depth": null,
  "max_queries": null,
  "platforms": null,
  "max_personas": null,
  "auto_approve_research": false,
  "max_briefs": null,
  "max_revision_cycles": null,
  "auto_approve_content": false,
  "updated_at": null
}
```

`null` values mean the system default is used.

### Update Pipeline Defaults

```
PUT /api/v1/companies/{slug}/settings/pipeline-defaults
```

**Auth:** Requires `superuser` role.

**Request Body:**

```json
{
  "max_crawl_pages": 300,
  "max_queries": 200,
  "platforms": ["perplexity", "openai", "claude"],
  "auto_approve_research": true
}
```

All fields are optional — only non-null fields are applied.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `max_crawl_pages` | int | 1–5000 | Gap analysis crawl limit |
| `max_crawl_depth` | int | 1–10 | Gap analysis crawl depth |
| `max_queries` | int | 1–500 | Gap analysis query limit |
| `platforms` | string[] | — | AI platforms to search |
| `max_personas` | int | 1–10 | Research persona limit |
| `auto_approve_research` | bool | — | Auto-approve research stages |
| `max_briefs` | int | 1–50 | Content brief limit |
| `max_revision_cycles` | int | 0–5 | Content revision limit |
| `auto_approve_content` | bool | — | Auto-approve content pieces |

---

## 20. Daily Tracker

The Daily Tracker monitors AI platform mentions and citations over time. It includes a prompt library, run management, and analytics.

### Prompt Library

#### Create Prompt

```
POST /api/v1/daily-tracker/prompts
```

**Auth:** Requires `member` or `superuser` role.

**Request Body:**

```json
{
  "text": "best expense management software for startups",
  "category": "product",
  "tags": ["expense", "startup"]
}
```

**Response (201):** `TrackedPrompt` object.

**Error (409):** Duplicate prompt text.

#### List Prompts

```
GET /api/v1/daily-tracker/prompts
```

**Auth:** Requires authentication.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | `null` | Filter by category |
| `source` | string | `null` | Filter by source |
| `active` | bool | `null` | Filter by active status |
| `search` | string | `null` | Substring search on prompt text |
| `tags` | string[] | `null` | Filter by tags |
| `limit` | int | `50` | Max results (1–200) |
| `offset` | int | `0` | Offset for pagination |

**Response (200):**

```json
{
  "prompts": [
    {
      "id": "prompt-abc",
      "text": "best expense management software",
      "category": "product",
      "tags": ["expense"],
      "active": true,
      "source": "manual",
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### Get Prompt

```
GET /api/v1/daily-tracker/prompts/{prompt_id}
```

#### Update Prompt

```
PUT /api/v1/daily-tracker/prompts/{prompt_id}
```

**Request Body:** All fields optional.

```json
{
  "text": "updated prompt text",
  "category": "competitor",
  "tags": ["updated"],
  "active": false
}
```

#### Delete Prompt

```
DELETE /api/v1/daily-tracker/prompts/{prompt_id}
```

**Response (204):** No content.

#### Toggle Prompt Active Status

```
PATCH /api/v1/daily-tracker/prompts/{prompt_id}/toggle
```

**Request Body:**

```json
{ "active": false }
```

#### Import Prompts from Gap Analysis

```
POST /api/v1/daily-tracker/prompts/import
```

Import prompts from a gap analysis run's `queries.json`.

**Request Body:**

```json
{ "slug": "ramp" }
```

**Response (201):** Array of created `TrackedPrompt` objects.

#### Bulk Create Prompts

```
POST /api/v1/daily-tracker/prompts/bulk
```

Duplicates are skipped.

**Request Body:**

```json
{
  "prompts": [
    { "text": "prompt one", "category": "product", "tags": [] },
    { "text": "prompt two", "category": null, "tags": ["tag1"] }
  ]
}
```

**Response (201):** Array of created `TrackedPrompt` objects.

### Run Management

#### Trigger Daily Run

```
POST /api/v1/daily-tracker/runs
```

**Auth:** Requires `member` or `superuser` role.

**Request Body:**

```json
{
  "engines": ["perplexity", "openai"],
  "prompt_ids": null,
  "brand": "Ramp",
  "competitors": ["Brex", "Divvy"],
  "concurrency": 6
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `engines` | string[] | `null` | Platforms to query (null = all) |
| `prompt_ids` | string[] | `null` | Specific prompts (null = all active) |
| `brand` | string | `null` | Brand name to track |
| `competitors` | string[] | `null` | Competitor names |
| `concurrency` | int | `6` | Parallel requests (1–20) |

**Response (202):**

```json
{
  "run_id": "run-abc",
  "company_id": "ramp",
  "status": "completed",
  "prompt_count": 50,
  "engine_count": 2,
  "started_at": "2026-03-01T10:00:00Z",
  "completed_at": "2026-03-01T10:05:00Z",
  "error": null
}
```

#### Get Run Status

```
GET /api/v1/daily-tracker/runs/{run_id}
```

#### List Runs

```
GET /api/v1/daily-tracker/runs
```

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Max results (1–100) |
| `offset` | int | `0` | Offset |

> **Note:** In v1, run listing returns empty as runs are transient. Full DB persistence is deferred.

### Analytics

#### Visibility Metrics

```
GET /api/v1/daily-tracker/analytics/visibility
```

Overall visibility metrics (mention rate, citation rate, share of voice).

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | string | `null` | Specific run (null = latest) |

#### Mention Trend

```
GET /api/v1/daily-tracker/analytics/mention-trend
```

Mention rate over time.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | int | `30` | Lookback period (1–365) |

#### Share of Voice

```
GET /api/v1/daily-tracker/analytics/sov
```

Share of voice vs competitors. Returns `{ "brand": 0.45, "competitor1": 0.30, ... }`.

#### Citation Rates

```
GET /api/v1/daily-tracker/analytics/citations
```

Citation rates with domain breakdown.

#### Competitor Metrics

```
GET /api/v1/daily-tracker/analytics/competitors
```

Per-competitor visibility metrics.

---

## 21. Audience Persona Pipeline

### Start Audience Persona Pipeline

```
POST /api/v1/audience-persona/start
```

**Auth:** `member` or `superuser` (Bearer token required)

**Request Body:**
```json
{
  "company_name": "Ramp",
  "domain": "ramp.com",
  "product_slug": null,
  "max_personas": 5,
  "auto_approve_checkpoints": [],
  "force_rerun": false,
  "language": "en",
  "region": null,
  "additional_constraints": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | string | Yes | Company name (derives slug) |
| `domain` | string | Yes | Company domain |
| `product_slug` | string | No | Product scope (creates `{slug}__{product}` effective slug) |
| `max_personas` | int | No | 3-7 personas to generate (default: 5) |
| `auto_approve_checkpoints` | int[] | No | Checkpoint numbers to auto-approve: `[1]` = briefs, `[2]` = profiles, `[1,2]` = both |
| `force_rerun` | bool | No | Override pipeline guard (default: false) |
| `language` | string | No | Output language (default: "en") |
| `region` | string | No | Geographic focus |
| `additional_constraints` | string | No | Custom guidance for persona generation |

**Response (202 — Pipeline Launched):**
```json
{
  "run_id": "550e8400-...",
  "pipeline": "audience_persona",
  "company_slug": "ramp",
  "product_slug": null,
  "effective_slug": "ramp",
  "status": "running",
  "created_at": "2026-03-06T..."
}
```

**Response (200 — Already Exists):**
When approved personas already exist and KB hasn't been updated since last AP run:
```json
{
  "run_id": "existing-ramp",
  "pipeline": "audience_persona",
  "company_slug": "ramp",
  "status": "already_exists",
  "already_exists": true,
  "message": "Audience personas already exist (3 approved). Pass force_rerun=true to re-run."
}
```

### Get Audience Persona Status

```
GET /api/v1/audience-persona/{run_id}/status
```

**Auth:** Any authenticated user

**Response:** Standard `TaskResponse` with `approval_payload` containing HITL stage details.

### HITL-1: Brief Approval

```
POST /api/v1/audience-persona/{run_id}/approve/briefs
```

**Auth:** `member` or `superuser`

Called when the pipeline pauses at HITL-1 (persona brief review). The `approval_payload` in the task status will contain the suggested briefs.

**Request Body:**
```json
{
  "batch_decision": "partial",
  "brief_reviews": [
    {
      "brief_id": "pb-abc12345",
      "decision": "approve"
    },
    {
      "brief_id": "pb-def67890",
      "decision": "modify",
      "modified_brief": {
        "persona_name": "VP of Engineering",
        "tagline": "Technical decision-maker",
        "description": "Updated description...",
        "rationale": ["Updated rationale"]
      }
    },
    {
      "brief_id": "pb-ghi11111",
      "decision": "reject"
    }
  ],
  "added_briefs": [
    {
      "persona_name": "Startup Founder",
      "tagline": "Early-stage bootstrapper",
      "description": "A manually added persona...",
      "rationale": ["Custom reason"]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `batch_decision` | `"approve_all" \| "partial" \| "reject_all"` | Batch decision for all briefs |
| `brief_reviews` | array | Per-brief decisions (required for `partial`) |
| `brief_reviews[].decision` | `"approve" \| "modify" \| "reject"` | Decision for this brief |
| `brief_reviews[].modified_brief` | object | Modified brief data (required for `modify`) |
| `added_briefs` | array | Manually added persona briefs |

**Response:**
```json
{
  "status": "accepted",
  "stage": "persona_brief_review",
  "message": "Brief approval submitted: partial"
}
```

### HITL-2: Profile Approval

```
POST /api/v1/audience-persona/{run_id}/approve/profiles
```

**Auth:** `member` or `superuser`

Called when the pipeline pauses at HITL-2 (profile review). The `approval_payload` in the task status will contain profile summaries with content previews.

**Request Body:**
```json
{
  "profile_reviews": [
    {
      "persona_id": "vp-engineering",
      "decision": "approve"
    },
    {
      "persona_id": "startup-founder",
      "decision": "revise",
      "revision_note": "Add more detail about pain points with expense management."
    },
    {
      "persona_id": "finance-director",
      "decision": "reject"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `profile_reviews` | array | Per-profile decisions (min 1 required) |
| `profile_reviews[].persona_id` | string | Persona ID (lowercase alphanumeric + hyphens) |
| `profile_reviews[].decision` | `"approve" \| "revise" \| "reject"` | Decision for this profile |
| `profile_reviews[].revision_note` | string | Feedback for revision (required for `revise`) |

**Response:**
```json
{
  "status": "accepted",
  "stage": "persona_profile_review",
  "message": "Profile approval submitted"
}
```

### Add Standalone Persona

```
POST /api/v1/audience-persona/{slug}/add-persona
```

**Auth:** `member` or `superuser`

Generates a single persona profile outside the pipeline flow. Creates a brief, runs Agent 2 (Perplexity deep research), and stores the result. The profile will need standalone approval afterwards.

**Request Body:**
```json
{
  "persona_name": "CFO at Series B Startup",
  "tagline": "Budget-conscious finance leader",
  "description": "A hands-on CFO at a fast-growing startup...",
  "rationale": ["High-value segment", "Underserved by current content"]
}
```

**Response (202):**
```json
{
  "persona_id": "cfo-at-series-b-startup",
  "task_id": "550e8400-..."
}
```

### Approve/Reject Standalone Persona

```
POST /api/v1/audience-persona/{slug}/personas/{persona_id}/approve
```

**Auth:** `member` or `superuser`

Approves or rejects a persona in `pending_review` status (e.g., after standalone add-persona generation).

**Request Body:**
```json
{
  "decision": "approve"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `decision` | `"approve" \| "reject"` | Approve sets status to `fresh`, reject sets to `archived` |

**Response:**
```json
{
  "persona_id": "cfo-at-series-b-startup",
  "status": "fresh"
}
```

### List Personas

```
GET /api/v1/audience-persona/{slug}/personas
```

**Auth:** Any authenticated user

Returns all personas for a company with their current status, version, and word count.

**Response:**
```json
{
  "slug": "ramp",
  "personas": [
    {
      "persona_id": "vp-engineering",
      "persona_name": "VP of Engineering",
      "tagline": "Technical decision-maker",
      "kind": "icp",
      "status": "fresh",
      "current_version": 2,
      "last_updated": "2026-03-06T...",
      "created_by": "agent",
      "word_count": 3200
    }
  ],
  "total": 3
}
```

| Status | Meaning |
|--------|---------|
| `fresh` | Approved and current |
| `stale` | Approved but outdated (>60 days or KB updated) |
| `pending_review` | Generated, awaiting approval |
| `archived` | Rejected or superseded |
| `missing` | Expected but not yet generated |

---

## 22. CPS Scoring (Citation Signal Predictor)

### Score Content

```
POST /api/v1/cps/score
```

**Auth:** Any authenticated user (Bearer token required)

Scores markdown content for citation probability across 4 AI answer engines. Returns a CPS score (0.0–1.0) indicating how likely the content is to be cited when AI engines answer the given queries. Requires PyTorch and the model checkpoint to be available on the server.

**Request Body:**
```json
{
  "content_markdown": "# Best CRM Software for Small Business\n\nWhen choosing a CRM...",
  "target_queries": [
    "best CRM software",
    "CRM for small business"
  ],
  "content_url": "https://example.com/crm-guide"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content_markdown` | string | Yes | Markdown content to score (min 50 chars) |
| `target_queries` | string[] | Yes | 1-10 search queries to score against |
| `content_url` | string | No | URL for authority feature extraction (default: `https://example.com`) |

**Response (200):**
```json
{
  "cps_score": 0.72,
  "per_engine": {
    "chatgpt_search": 0.75,
    "claude_search": 0.68,
    "gemini_search": 0.71,
    "perplexity": 0.74
  },
  "per_query": [
    {"query": "best CRM software", "cps_score": 0.73},
    {"query": "CRM for small business", "cps_score": 0.71}
  ],
  "model_version": "v1",
  "feature_config": "option_a_top11",
  "target_weight": 0.5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cps_score` | float | Overall citation probability (0.0–1.0) — average across all engines |
| `per_engine` | object | Per-engine scores: `chatgpt_search`, `claude_search`, `gemini_search`, `perplexity` |
| `per_query` | array | Per-query average scores across all engines |
| `model_version` | string | Model version identifier |
| `feature_config` | string | Feature selection config used (e.g., `option_a_top11`, `option_b_full31`) |
| `target_weight` | float | Contrastive vs regression signal weight |

**Score Interpretation:**

| CPS Score | Interpretation |
|-----------|----------------|
| 0.0 – 0.2 | Very unlikely to be cited |
| 0.2 – 0.4 | Low citation probability |
| 0.4 – 0.6 | Moderate citation probability |
| 0.6 – 0.8 | High citation probability |
| 0.8 – 1.0 | Very high citation probability |

**Error Responses:**
- `503` — CPS scoring unavailable (torch not installed, model checkpoint missing, or CPS disabled in settings)
- `500` — CPS scoring failed during inference

**Notes:**
- CPS scoring is also integrated into Content Engine v1.3 as Stage 4.5 (between evaluator and HITL-3). The standalone endpoint is for ad-hoc scoring outside the pipeline.
- Settings: `cps_enabled` (bool, default `true`), `cps_target_weight` (float, default `0.5`)
- The model extracts 30 features: 12 structural (HTML), 9 citability (text), 9 authority (URL)

---

## 23. Server-Sent Events (SSE)

### Endpoint

```
GET /api/v1/tasks/{task_id}/events
```

**Headers:**
- `Accept: text/event-stream`
- `Last-Event-ID: {id}` — optional, for reconnection (replays events after this ID)

### Event Types

| Event | Data | When |
|-------|------|------|
| `pipeline_start` | `{ "pipeline": "..." }` | Pipeline execution begins |
| `stage_start` | `{ "stage": "..." }` | Research/KB stage begins |
| `pending_approval` | `{ "stage": "...", ...interrupt_payload }` | Waiting for human decision |
| `approval_received` | `{ "stage": "...", "decision": "..." }` | Human decision submitted |
| `stage_complete` | `{ "stage": "..." }` | Stage finished |
| `completed` | `{ "pipeline": "..." }` | Pipeline finished successfully |
| `failed` | `{ "error": "exception message" }` | Pipeline encountered an error |
| `cancelled` | `{}` | Task was cancelled |
| `ap_phase_start` | `{ "phase": 0-3, "agents": [...] }` | Audience Persona phase begins |
| `ap_agent_complete` | `{ "agent": "...", "persona_name": "...", ... }` | AP agent finished |
| `ap_phase_complete` | `{ "phase": 0-3 }` | AP phase finished |

### Terminal Events

The stream **automatically closes** after emitting one of: `completed`, `failed`, `cancelled`.

### Reconnection

The browser's `EventSource` automatically sends `Last-Event-ID` on reconnection. The server replays all events after that ID (bounded to last 100 events per task).

---

## 24. Error Handling

### Error Response Shape

```json
{
  "detail": "Human-readable error message",
  "error_code": "machine_readable_code"
}
```

> `error_code` is only present on responses from custom exception handlers (`task_not_found`, `task_conflict`, `pipeline_error`).

### Error Codes

| HTTP Status | Error Code | Cause | Frontend Action |
|-------------|-----------|-------|----------------|
| **400** | — | Path traversal / invalid slug / invalid request | Show validation error |
| **403** | — | Tenant isolation violation | Show "Access denied" |
| **404** | `task_not_found` | Task ID doesn't exist | Show "Task not found" |
| **404** | — | Artifact/file/document not found | Show "Not found" |
| **409** | `task_conflict` | Concurrent run for same company | Show "A pipeline is already running" |
| **409** | — | Wrong state for action (cancel completed, approve non-pending) | Show the `detail` message |
| **422** | — | Invalid request body | Show validation error from `detail` |
| **500** | `pipeline_error` | Unhandled pipeline exception | Show "Pipeline error: {detail}" |

---

## 25. Data Models Reference

### Common Response Models

#### PipelineRunResponse
Returned by all `POST /start` endpoints (202) and already-exists guards (200).

```typescript
interface PipelineRunResponse {
  run_id: string;
  pipeline: string;
  company_slug: string;
  product_slug: string | null;
  effective_slug: string | null;
  status: string;
  created_at: string;            // ISO 8601
  already_exists: boolean;       // true when guard fires (200 response)
  message: string | null;        // Human-readable message (e.g., "Audit already exists...")
}
```

#### TaskResponse
Returned by all `GET /status` and `GET /tasks/{id}` endpoints.

```typescript
interface TaskResponse {
  run_id: string;
  pipeline: string;
  company_slug: string;
  product_slug: string | null;
  effective_slug: string | null;
  status: TaskStatus;
  current_step: string | null;
  progress_pct: number | null;
  created_at: string;
  updated_at: string;
  result: Record<string, any> | null;
  error: string | null;
  approval_payload: Record<string, any> | null;
}
```

#### TaskListResponse

```typescript
interface TaskListResponse {
  tasks: TaskSummary[];
  total: number;
}

interface TaskSummary {
  run_id: string;
  pipeline: string;
  status: TaskStatus;
  company_slug: string;
  product_slug: string | null;
  effective_slug: string | null;
  current_step: string | null;
  created_at: string;
  updated_at: string;
}
```

#### TaskStatus

```typescript
type TaskStatus =
  | 'running'
  | 'pending_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'failed_restart';
```

### Auth Models

```typescript
interface RegisterRequest {
  first_name: string;
  last_name: string;
  email: string;
  password: string;           // 8–128 chars
  company_name: string;
  company_domain: string;
}

interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;         // "bearer"
  user: UserResponse;
  company: CompanyResponse;
}

interface UserResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;               // "superuser" | "admin" | "member" | "viewer"
  company_id: string;
  is_active: boolean;
}

interface CompanyResponse {
  id: string;
  slug: string;
  name: string;
  domain: string;
}
```

### Site Audit Models

```typescript
interface SiteAuditStartRequest {
  company_name: string;
  domain: string;
  product_slug?: string;
  max_pages?: number;              // 1–2000, default 200
  max_depth?: number;              // 1–10, default 4
  check_core_web_vitals?: boolean; // default true
  check_schema_validation?: boolean;
  check_ai_bot_access?: boolean;
  force_rerun?: boolean;
}

interface AuditSummaryResponse {
  audit_id: string;
  domain: string;
  overall_score: number;
  grade: string;
  pages_crawled: number;
  total_findings: number;
  status: string;
  started_at: string;
  completed_at: string;
}

interface AuditDetailResponse {
  audit_id: string;
  domain: string;
  overall_score: number;
  grade: string;
  pages_crawled: number;
  pages_discovered: number;
  duration_seconds: number;
  dimension_scores: DimensionScoreResponse[];
  ai_bot_access: AIBotAccessResponse;
  sitemap_health: SitemapHealthResponse;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  findings_by_dimension: Record<string, number>;
  avg_snippet_readiness: number;
  pages_with_schema: number;
  avg_question_heading_ratio: number;
  status: string;
  error_message: string | null;
  started_at: string;
  completed_at: string;
}

interface DimensionScoreResponse {
  dimension: string;
  score: number;
  weight: number;
  weighted_score: number;
  finding_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
}
```

### Knowledge Base Models

```typescript
interface KnowledgeBaseStartRequest {
  company_name: string;
  domain: string;
  product_slug?: string;
  seed_urls?: string[];
  force_rerun?: boolean;
  mode?: 'full' | 'refresh' | 'single';
  refresh_docs?: string[];         // Doc type values
  single_doc?: string;             // Single doc type
  auto_approve_checkpoints?: number[];  // [1, 2, 3]
  language?: string;
  region?: string;
  internal_sources?: string[];
  additional_constraints?: string;
  staleness_threshold_days?: number;   // 1–365, default 30
}

interface KBHealthResponse {
  slug: string;
  overall_score: number;
  doc_health: Record<string, KBDocHealthResponse>;
  synthesis_version: number;
  synthesis_last_updated: string | null;
  synthesis_needs_refresh: boolean;
  stale_docs: string[];
  missing_docs: string[];
  last_full_refresh: string | null;
}

interface KBDocHealthResponse {
  doc_type: string;
  status: string;
  current_version: number;
  last_updated: string | null;
  age_days: number;
  staleness_threshold_days: number;
  stale_reason: string | null;
  dependencies: string[];
}
```

### Content v1.3 Models

```typescript
interface ContentStartRequestV13 {
  company_name: string;
  domain: string;
  entry_mode?: 'autonomous' | 'manual';
  max_topics?: number;
  gap_slug?: string;
  manual_prompt?: string;
  manual_description?: string;
  manual_cluster?: string;
  product_slug?: string;
  product_name?: string;
  product_description?: string;
  auto_approve?: boolean;
  max_concurrent_workers?: number;
  max_revision_cycles?: number;
  skip_stages?: number[];
}

interface PipelineRunResponseV13 {
  run_id: string;
  status: string;
  entry_mode: string;
  message: string | null;
}

interface TopicApprovalRequest {
  decision: 'approve' | 'modify' | 'reject' | 'retry';
  approved_topic_ranks: number[];   // Non-negative integers
  added_query_ids: string[];
  removed_query_ids: string[];
  feedback: string | null;
}

interface BriefApprovalRequest {
  brief_id: string;
  decision: 'approve' | 'feedback' | 'reject';
  feedback: string | null;
}

interface ContentApprovalRequestV13 {
  brief_id: string;
  decision: 'approve' | 'edit' | 'reject';
  editor_notes: string | null;     // Max 5000 chars
  rethink: boolean;                // Trigger re-brief on reject
}

interface ApprovalResponseV13 {
  status: string;
  stage: string;
  brief_id: string | null;
  message: string | null;
}
```

### Knowledge Document Models

```typescript
interface KnowledgeDocResponse {
  id: string;
  filename: string;
  content_type: string;
  file_size_bytes: number;
  word_count: number;
  uploaded_at: string;
  is_embedded: boolean;
  last_embedded_at: string | null;
}

interface KnowledgeDocListResponse {
  documents: KnowledgeDocResponse[];
  total: number;
}
```

### Settings Models

```typescript
interface TeamMemberResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface TeamListResponse {
  members: TeamMemberResponse[];
  total: number;
}

interface CompanyProfileSettingsResponse {
  slug: string;
  name: string;
  domain: string;
  additional_domains: string[];
  created_at: string;
  updated_at: string;
}

interface PipelineDefaultsResponse {
  max_crawl_pages: number | null;
  max_crawl_depth: number | null;
  max_queries: number | null;
  platforms: string[] | null;
  max_personas: number | null;
  auto_approve_research: boolean;
  max_briefs: number | null;
  max_revision_cycles: number | null;
  auto_approve_content: boolean;
  updated_at: string | null;
}
```

### Audience Persona Models

```typescript
interface AudiencePersonaStartRequest {
  company_name: string;
  domain: string;
  product_slug?: string;
  max_personas?: number;              // 3-7, default 5
  auto_approve_checkpoints?: number[]; // [1]=briefs, [2]=profiles
  force_rerun?: boolean;
  language?: string;
  region?: string;
  additional_constraints?: string;
}

interface PersonaBriefApprovalRequest {
  batch_decision: 'approve_all' | 'partial' | 'reject_all';
  brief_reviews?: BriefReviewItem[];
  added_briefs?: ManualBriefItem[];
}

interface BriefReviewItem {
  brief_id: string;
  decision: 'approve' | 'modify' | 'reject';
  modified_brief?: ManualBriefItem;
}

interface ManualBriefItem {
  persona_name: string;
  tagline?: string;
  description?: string;
  rationale?: string[];
}

interface PersonaProfileApprovalRequest {
  profile_reviews: ProfileReviewItem[];
}

interface ProfileReviewItem {
  persona_id: string;                 // ^[a-z0-9][a-z0-9-]*$
  decision: 'approve' | 'revise' | 'reject';
  revision_note?: string;
}

interface PersonaListItem {
  persona_id: string;
  persona_name: string;
  tagline: string;
  kind: 'icp' | 'secondary';
  status: 'fresh' | 'stale' | 'missing' | 'pending_review' | 'archived';
  current_version: number;
  last_updated: string | null;
  created_by: 'agent' | 'manual' | 'hybrid';
  word_count: number;
}

interface PersonaListResponse {
  slug: string;
  personas: PersonaListItem[];
  total: number;
}
```

### CPS Scoring Models

```typescript
interface CPSScoreRequest {
  content_markdown: string;           // Min 50 chars
  target_queries: string[];           // 1-10 queries
  content_url?: string;               // Default: "https://example.com"
}

interface CPSScoreResponse {
  cps_score: number;                  // 0.0-1.0 overall
  per_engine: {
    chatgpt_search: number;
    claude_search: number;
    gemini_search: number;
    perplexity: number;
  };
  per_query: Array<{
    query: string;
    cps_score: number;
  }>;
  model_version: string;
  feature_config: string;
  target_weight: number;
}
```

---

## 26. Artifact Directory Structure

```
artifacts/
├── company_context/                     ← Flat layout
│   ├── ramp.md                          ← Finalized company context
│   ├── ramp.draft.md                    ← Draft (before approval)
│   └── ramp__expense-mgmt.md           ← Product-scoped artifact
│
├── personas/                            ← Flat layout
│   ├── ramp__persona-icp.md             ← ICP persona
│   ├── ramp__persona-secondary-1.md     ← Secondary persona #1
│   └── ramp__persona-secondary-2.md
│
├── style_guides/                        ← Flat layout
│   └── ramp.md
│
├── gap_analysis/                        ← Nested layout
│   └── ramp/
│       ├── company_embeddings.json
│       ├── site_discovery/
│       ├── queries.json
│       ├── platform_results/
│       ├── enriched_citations.json
│       ├── embeddings/
│       ├── analysis.json
│       ├── visualizations/*.html
│       ├── gap_report.md
│       ├── gap_report.json
│       └── generation_spec.json
│
├── content/                             ← Nested layout
│   └── ramp/
│       ├── briefs.json
│       ├── run_metadata.json
│       └── content/
│           └── brief-001/
│               ├── outline.json
│               ├── draft.md
│               ├── enriched.md
│               ├── formatted.md
│               ├── eval_history.json
│               └── final.md
│
├── knowledge_base/                      ← Nested layout
│   └── ramp/
│       ├── _manifest.json
│       ├── company_overview.md
│       ├── customer_reviews.md
│       ├── competitor_registry.md
│       ├── weakness_analysis.md
│       ├── brand_perception.md
│       └── synthesis.md
│
├── audience_personas/                   ← Versioned personas
│   └── ramp/
│       ├── _manifest.json               ← PersonaManifest (slug, personas{}, kb_synthesis_version)
│       ├── vp-engineering/
│       │   ├── brief.json               ← PersonaBrief (suggester output)
│       │   ├── v1.md                    ← Profile version 1
│       │   ├── v1.json                  ← Structured sidecar (optional)
│       │   └── v2.md                    ← Profile version 2 (revision)
│       └── startup-founder/
│           ├── brief.json
│           └── v1.md
│
├── knowledge_docs/                      ← Uploaded documents
│   └── ramp/
│       ├── _index.json
│       └── doc-abc123.pdf
│
├── site_audit/                          ← Nested layout
│   └── ramp/
│       └── {audit_id}/
│           ├── audit_result.json
│           └── page_results/
│
└── _jobs/                               ← Task persistence (internal)
    └── 550e8400-....json
```

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Company context | `{slug}.md` | `ramp.md` |
| Company context draft | `{slug}.draft.md` | `ramp.draft.md` |
| Product-scoped | `{slug}__{product}.md` | `ramp__expense-mgmt.md` |
| Persona (ICP) [v1] | `{slug}__persona-icp.md` | `ramp__persona-icp.md` |
| Persona (secondary) [v1] | `{slug}__persona-secondary-{n}.md` | `ramp__persona-secondary-1.md` |
| Audience Persona [v2] | `{slug}/{persona_id}/v{N}.md` | `ramp/vp-engineering/v1.md` |
| Audience Persona brief | `{slug}/{persona_id}/brief.json` | `ramp/vp-engineering/brief.json` |
| Audience Persona manifest | `{slug}/_manifest.json` | `ramp/_manifest.json` |
| Style guide | `{slug}.md` | `ramp.md` |
| Gap analysis | `{slug}/{file}` | `ramp/gap_report.json` |
| Content | `{slug}/content/brief-{id}/{file}` | `ramp/content/brief-001/final.md` |
| Knowledge base | `{slug}/{doc_type}.md` | `ramp/company_overview.md` |
| Site audit | `{slug}/{audit_id}/audit_result.json` | `ramp/abc-123/audit_result.json` |

### Which Pipeline Produces What

| Pipeline | Artifacts | Key Files for Display |
|----------|-----------|----------------------|
| **Site Audit** | site_audit/{slug}/ | `audit_result.json` — scored results |
| **Research** | company_context, personas, style_guides | `{slug}.md` — rendered markdown |
| **Knowledge Base** | knowledge_base/{slug}/ | `*.md` docs + `_manifest.json` |
| **Gap Analysis** | gap_analysis/{slug}/ | `gap_report.json` — structured data, `visualizations/*.html` |
| **Content** | content/{slug}/ | `briefs.json` — brief list, `content/brief-{id}/final.md` |
| **Content v1.3** | content/{slug}/ | Same as content pipeline |
| **Audience Persona** | audience_personas/{slug}/ | `_manifest.json` — manifest, `{persona_id}/v{N}.md` — profiles |
