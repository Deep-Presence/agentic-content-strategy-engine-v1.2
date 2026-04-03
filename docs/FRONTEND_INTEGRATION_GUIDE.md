# Frontend Integration Guide — Backend API Reference

> **Audience:** Frontend team, integration engineers, and anyone mapping the new frontend v2.2 to the existing backend.
>
> **Last Updated:** 2026-04-02
>
> **Base URL:** `http://localhost:8000` (dev) | Set via `NEXT_PUBLIC_API_URL`

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Authentication](#2-authentication)
3. [SSE Event Streaming (Real-Time Pipeline Progress)](#3-sse-event-streaming)
4. [Task Lifecycle](#4-task-lifecycle)
5. [HITL (Human-in-the-Loop) Approval Flows](#5-hitl-approval-flows)
6. [API Endpoints — Complete Reference](#6-api-endpoints)
   - [Auth](#61-auth)
   - [Health](#62-health)
   - [Companies & Products](#63-companies--products)
   - [Site Audit](#64-site-audit)
   - [Knowledge Base](#65-knowledge-base)
   - [Knowledge Documents](#66-knowledge-documents)
   - [Audience Personas](#67-audience-personas)
   - [Voice Style Guide](#68-voice-style-guide)
   - [Research Orchestrator](#69-research-orchestrator)
   - [Gap Analysis](#610-gap-analysis)
   - [Gap Data (Dashboard)](#611-gap-data-dashboard)
   - [Content Engine v1.3](#612-content-engine-v13)
   - [Content Data (Dashboard)](#613-content-data-dashboard)
   - [Topic Discovery](#614-topic-discovery)
   - [Onboarding](#615-onboarding)
   - [CPS (Citation Probability Scoring)](#616-cps)
   - [Daily Tracker](#617-daily-tracker)
   - [CMS Integration](#618-cms-integration)
   - [Tasks](#619-tasks)
   - [Events (SSE)](#620-events-sse)
   - [Artifacts](#621-artifacts)
   - [Brand Data](#622-brand-data)
   - [Settings](#623-settings)
7. [Request/Response Schemas — Complete Reference](#7-schemas)
8. [Pipeline Data Availability Matrix](#8-pipeline-data-availability-matrix)
9. [Integration Readiness Assessment](#9-integration-readiness-assessment)
10. [Error Handling](#10-error-handling)
11. [CORS & Infrastructure](#11-cors--infrastructure)

---

## 1. Quick Start

### Making Your First Request

```javascript
// 1. Login
const res = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@acme.com', password: 'password123' })
});
const { access_token, user, company } = await res.json();

// 2. Use token for all subsequent requests
const headers = { 'Authorization': `Bearer ${access_token}` };

// 3. Fetch gap analysis summary
const summary = await fetch(`/api/v1/companies/${company.slug}/gap-analysis/summary`, { headers });

// 4. Start a pipeline
const run = await fetch('/api/v1/gap-analysis/start', {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ company_name: company.name, domain: company.domain })
});
const { run_id } = await run.json();

// 5. Stream real-time progress
const tokenRes = await fetch(`/api/v1/tasks/${run_id}/stream-token`, { headers });
const { stream_token } = await tokenRes.json();
const es = new EventSource(`/api/v1/tasks/${run_id}/events?stream_token=${stream_token}`);
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Bearer Token** | 24-hour JWT-like token from login. Send as `Authorization: Bearer {token}` |
| **Stream Token** | 60-minute SSE-only token. Pass as `?stream_token=xxx` for EventSource |
| **Company Slug** | URL-safe company identifier (e.g., `acme-corp`). Auto-derived from company name |
| **Product Slug** | Optional sub-entity. Pattern: `^[a-z0-9][a-z0-9-]*$` |
| **Effective Slug** | `{company_slug}__{product_slug}` (double underscore). Used for artifact namespacing |
| **Run ID** | UUID identifying a pipeline execution. Used for status polling and SSE |
| **Task ID** | Same as Run ID. Used interchangeably |
| **HITL** | Human-in-the-Loop checkpoint. Pipeline pauses for user approval |
| **Pipeline** | Async background job (gap analysis, content generation, etc.) |

---

## 2. Authentication

### 2.1 Token Format

- **Access Token:** `{base64_payload}.{hmac_signature}` (24-hour TTL)
- **Stream Token:** Same format with `stream_only: true` flag (60-minute TTL, SSE endpoints only)

### 2.2 Auth Endpoints

#### POST `/api/v1/auth/register` (Public)
Creates a new company + superuser account.

```json
// Request
{
  "first_name": "string",
  "last_name": "string",
  "email": "user@example.com",
  "password": "string (min 8 chars)",
  "company_name": "string",
  "company_domain": "example.com"
}

// Response (201)
{
  "access_token": "string",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "string",
    "last_name": "string",
    "role": "superuser",
    "company_id": "uuid",
    "is_active": true
  },
  "company": {
    "id": "uuid",
    "slug": "company-slug",
    "name": "Company Name",
    "domain": "example.com"
  }
}
```

Error: `409 domain_taken` if domain already registered.

#### POST `/api/v1/auth/login` (Public)

```json
// Request
{ "email": "user@example.com", "password": "string" }

// Response (200) — same shape as register
```

#### GET `/api/v1/auth/me` (Protected)

```json
// Response (200)
{
  "user": { /* same as login */ },
  "company": { /* same as login */ }
}
```

#### POST `/api/v1/auth/invite` (Protected, superuser only)

```json
// Request
{ "role": "member|viewer" }

// Response (201)
{ "invite_code": "16-char hex", "company_slug": "string", "role": "member|viewer" }
```

#### POST `/api/v1/auth/join` (Public)

```json
// Request
{
  "invite_code": "string",
  "first_name": "string",
  "last_name": "string",
  "email": "user@example.com",
  "password": "string"
}

// Response (201) — same shape as login
```

### 2.3 Roles & Permissions

| Role | Can Start Pipelines | Can Approve HITL | Can Manage Team | Can View Data |
|------|:---:|:---:|:---:|:---:|
| **superuser** | Yes | Yes | Yes | Yes |
| **member** | Yes | Yes | No | Yes |
| **viewer** | No | No | No | Yes |

### 2.4 Token Usage

```
Regular endpoints:   Authorization: Bearer {access_token}
SSE EventSource:     /api/v1/tasks/{id}/events?stream_token={stream_token}
```

Stream tokens are created via `POST /api/v1/tasks/{task_id}/stream-token` (requires access token).

### 2.5 Tenant Isolation

Every authenticated request is scoped to the user's company. Users can **never** see data from other companies. The middleware extracts `company_slug` from the token and enforces it on every request.

---

## 3. SSE Event Streaming

### 3.1 Connecting

```javascript
// Step 1: Get a stream token (requires access_token)
const { stream_token } = await apiPost(`/api/v1/tasks/${taskId}/stream-token`);

// Step 2: Open EventSource with query param
const es = new EventSource(
  `/api/v1/tasks/${taskId}/events?stream_token=${stream_token}`
);

// Step 3: Listen to typed events
es.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`${data.progress_pct}% — ${data.current_step}`);
});

es.addEventListener('pending_approval', (e) => {
  const data = JSON.parse(e.data);
  // Show HITL approval UI with data.payload
});

es.addEventListener('completed', (e) => {
  const data = JSON.parse(e.data);
  es.close(); // Close on terminal event
});

es.addEventListener('failed', (e) => {
  const data = JSON.parse(e.data);
  console.error(data.error);
  es.close();
});
```

### 3.2 Event Types

| Event | Status | Description | Data Shape |
|-------|--------|-------------|------------|
| `pipeline_start` | RUNNING | Pipeline initialized | `{ pipeline: string }` |
| `step_started` | RUNNING | Step began | `{ step: string, progress_pct: float }` |
| `progress` | RUNNING | Progress update | `{ progress_pct: float, current_step: string }` |
| `stage_started` | RUNNING | Content stage began | `{ stage: string, brief_id: string }` |
| `stage_complete` | RUNNING | Content stage done | `{ stage: string, brief_id: string }` |
| `worker_progress` | RUNNING | Worker update | `{ brief_id: string, stage: string }` |
| `worker_failed` | RUNNING | Worker error (non-fatal) | `{ brief_id: string, error: string }` |
| `brief_completed` | RUNNING | Brief finished | `{ brief_id: string, title: string }` |
| `brief_rejected` | RUNNING | Brief rejected | `{ brief_id: string, reason: string }` |
| `cps_scoring_complete` | RUNNING | CPS scores ready | `{ brief_id: string, score: float }` |
| `pending_approval` | PENDING_APPROVAL | HITL checkpoint | `{ stage: string, payload: object }` |
| `approval_received` | RUNNING | Approval processed | `{ stage: string, decision: string }` |
| `completed` | COMPLETED | Pipeline succeeded | `{ pipeline: string, result: object }` |
| `failed` | FAILED | Pipeline failed | `{ error: string }` |
| `cancelled` | CANCELLED | User cancelled | `{ reason: "user_cancelled" }` |
| `log` | RUNNING | Informational log | `{ message: string, level: string }` |
| `onboarding_*` | RUNNING | Onboarding sub-events | `{ phase: string, sub_pipeline: string }` |

**Terminal events:** `completed`, `failed`, `cancelled` — close the EventSource after receiving these.

### 3.3 Reconnection with Last-Event-ID

Each SSE event has a numeric `id`. If the connection drops:

```javascript
// Store the last event ID
let lastEventId = null;
es.onmessage = (e) => { lastEventId = e.lastEventId; };

// On reconnect, the browser automatically sends Last-Event-ID header
// The backend replays all events after that ID from Redis Streams
```

### 3.4 Heartbeat

The server sends a heartbeat comment (`: heartbeat\n\n`) every 15 seconds to keep the connection alive. This is invisible to EventSource listeners — it only prevents proxy timeouts.

---

## 4. Task Lifecycle

### 4.1 Task States

```
START
  |
  v
RUNNING -------> PENDING_APPROVAL ---> RUNNING ---> COMPLETED
  |                                                    ^
  +----> FAILED ----------------------------------------+
  |
  +----> CANCELLED
```

| Status | Description |
|--------|-------------|
| `running` | Pipeline is executing |
| `pending_approval` | Waiting for HITL decision |
| `completed` | Pipeline finished successfully |
| `failed` | Pipeline errored out |
| `cancelled` | User cancelled the pipeline |

### 4.2 Task Data Model

```json
// GET /api/v1/tasks/{task_id}
{
  "run_id": "uuid",
  "pipeline": "gap_analysis|content|knowledge_base|site_audit|...",
  "company_slug": "string",
  "product_slug": "optional string",
  "effective_slug": "string",
  "status": "running|pending_approval|completed|failed|cancelled",
  "current_step": "optional string",
  "progress_pct": 0.0-100.0,
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601",
  "result": null,           // populated on completion
  "error": null,             // populated on failure
  "approval_payload": null   // populated when pending_approval
}
```

### 4.3 Task Listing

```
GET /api/v1/tasks?pipeline=gap_analysis&status=running&product_slug=premium

Response:
{
  "tasks": [ { TaskSummary... } ],
  "total": 5
}
```

Tasks are automatically filtered to the authenticated user's company.

### 4.4 Pipeline Concurrency

Maximum 3 concurrent pipelines (configurable). If exceeded, the pipeline waits in a queue. Frontend receives the `run_id` immediately — SSE events begin when the pipeline actually starts.

---

## 5. HITL Approval Flows

### 5.1 General Pattern

1. Pipeline publishes SSE event: `event: pending_approval`
2. Frontend displays approval UI using `data.payload`
3. Frontend sends approval decision via the pipeline-specific approval endpoint
4. Pipeline resumes based on decision

### 5.2 Pipeline-Specific HITL Stages

#### Knowledge Base (3 checkpoints)
| Checkpoint | SSE Stage | Approval Endpoint | Decisions |
|------------|-----------|-------------------|-----------|
| 1 | `kb_checkpoint_1` | `POST /api/v1/knowledge-base/{run_id}/approve` | approve, revise, reject |
| 2 | `kb_checkpoint_2` | Same endpoint | approve, revise, reject |
| 3 | `kb_checkpoint_3` | Same endpoint | approve, revise, reject |

```json
// Approval Request
{ "decision": "approve|revise|reject", "revision_note": "optional feedback" }
```

#### Audience Persona (2 checkpoints)
| Checkpoint | SSE Stage | Approval Endpoint | Decisions |
|------------|-----------|-------------------|-----------|
| Brief Review | `persona_brief_review` | `POST /api/v1/audience-persona/{run_id}/approve/briefs` | approve_all, partial, reject_all |
| Profile Review | `persona_profile_review` | `POST /api/v1/audience-persona/{run_id}/approve/profiles` | approve, revise, reject (per profile) |

```json
// Brief Approval (batch)
{
  "batch_decision": "approve_all|partial|reject_all",
  "brief_reviews": [
    { "brief_id": "string", "decision": "approve|modify|reject", "modified_brief": null }
  ],
  "added_briefs": [
    { "persona_name": "string", "tagline": "", "description": "", "rationale": [] }
  ]
}

// Profile Approval (batch)
{
  "profile_reviews": [
    { "persona_id": "string", "decision": "approve|revise|reject", "revision_note": "" }
  ]
}
```

#### Voice Style Guide (1 checkpoint)
| Checkpoint | SSE Stage | Approval Endpoint | Decisions |
|------------|-----------|-------------------|-----------|
| Author Review | `vsg_author_review` | `POST /api/v1/voice-style-guide/{run_id}/approve/authors` | approve_all, partial, reject_all |

```json
{
  "batch_decision": "approve_all|partial|reject_all",
  "author_reviews": [
    { "author_id": "string", "decision": "approve|modify|reject", "modified_author": null }
  ]
}
```

#### Content Engine v1.3 (3 checkpoints)
| Checkpoint | SSE Stage | Approval Endpoint | Decisions |
|------------|-----------|-------------------|-----------|
| Topic Approval | `topic_approval` | `POST /api/v1/content/v13/{run_id}/approve/topics` | approve, modify, reject, retry |
| Brief Approval | `brief_approval` | `POST /api/v1/content/v13/{run_id}/approve/briefs` | approve, feedback, reject (per brief) |
| Content Review | `content_review` | `POST /api/v1/content/v13/{run_id}/approve/content` | approve, edit, reject (per brief) |

```json
// Topic Approval
{
  "decision": "approve|modify|reject|retry",
  "approved_topic_ranks": [1, 2, 5],
  "feedback": "optional string"
}

// Brief Approval (per-brief)
{
  "brief_id": "brief-1",
  "decision": "approve|feedback|reject",
  "feedback": "optional string"
}

// Content Review (per-brief)
{
  "brief_id": "brief-1",
  "decision": "approve|edit|reject",
  "editor_notes": "optional string (max 5000 chars)",
  "rethink": false  // triggers full re-draft if true
}
```

#### Topic Discovery (3 checkpoints)
| Checkpoint | SSE Stage | Approval Endpoint | Decisions |
|------------|-----------|-------------------|-----------|
| Taxonomy | `td_taxonomy_review` | `POST /api/v1/topic-discovery/{run_id}/approve/taxonomy` | approve, modify, retry |
| Subdomain Selection | `td_subdomain_selection` | `POST /api/v1/topic-discovery/{run_id}/approve/subdomains` | select, select_top_n |
| Matrix | `td_matrix_review` | `POST /api/v1/topic-discovery/{run_id}/approve/matrix` | approve, modify |

```json
// Taxonomy Approval
{
  "batch_decision": "approve|modify|retry",
  "user_edits": [
    { "op": "add|delete|rename|reparent", "node_id": "", "name": "", "new_name": "" }
  ],
  "user_feedback": "optional string"
}

// Subdomain Selection
{
  "batch_decision": "select|select_top_n",
  "selected_subdomain_ids": ["uuid1", "uuid2"],
  "top_n": 10,
  "persona_filter": "optional persona_id"
}

// Matrix Approval
{
  "batch_decision": "approve|modify",
  "user_edits": [
    {
      "op": "adjust_priority|remove|add",
      "assignment_id": "uuid",
      "new_priority": 0.85,
      "topic_text": "string",
      "subdomain_name": "string",
      "buyer_stage": "tofu|mofu|bofu",
      "intent_type": "informational|commercial|navigational|transactional"
    }
  ]
}
```

### 5.3 HITL Timeout Behavior

If no approval is received:
- **Default behavior:** Pipeline auto-rejects (fail-safe)
- **Not auto-approve** — this is a deliberate safety decision
- Frontend should prompt users when `pending_approval` events arrive

---

## 6. API Endpoints

### 6.1 Auth
**Prefix:** `/api/v1/auth`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/register` | Public | `RegisterRequest` | `LoginResponse` (201) | Creates company + superuser |
| POST | `/login` | Public | `LoginRequest` | `LoginResponse` | |
| GET | `/me` | Bearer | — | `MeResponse` | |
| POST | `/invite` | Superuser | `InviteRequest` | `InviteResponse` (201) | |
| POST | `/join` | Public | `JoinRequest` | `LoginResponse` (201) | Redeem invite code |

### 6.2 Health
**Prefix:** `/` (root)

| Method | Path | Auth | Response | Notes |
|--------|------|------|----------|-------|
| GET | `/health` | Public | `{ status, database, pgvector, redis }` | |
| GET | `/readiness` | Public | `{ ready: bool, missing_keys: [] }` | Checks required API keys |

### 6.3 Companies & Products
**Prefix:** `/api/v1/companies`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| GET | `/{slug}` | Tenant | — | `CompanyProfileResponse` | Full company profile with artifacts & latest runs |
| POST | `/{slug}/products` | Member+ | `ProductCreateRequest` | `ProductDetailResponse` (201) | |
| GET | `/{slug}/products/{product_slug}` | Tenant | — | `ProductDetailResponse` | |
| PUT | `/{slug}/products/{product_slug}` | Member+ | `ProductUpdateRequest` | `ProductDetailResponse` | |
| DELETE | `/{slug}/products/{product_slug}` | Member+ | — | `{ deleted: true }` | |

### 6.4 Site Audit
**Prefix:** `/api/v1/site-audit`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `SiteAuditStartRequest` | `PipelineRunResponse` (202) | Returns 200 if audit exists |
| GET | `/status/{run_id}` | Bearer | — | `TaskResponse` | |
| GET | `/companies/{slug}/audits` | Tenant | — | `[AuditSummaryResponse]` | Query: `limit` |
| GET | `/companies/{slug}/audits/{audit_id}` | Tenant | — | `AuditDetailResponse` | Full audit with dimension scores |
| GET | `/companies/{slug}/audits/{audit_id}/findings` | Tenant | — | `AuditFindingsResponse` | Query: `severity`, `dimension`, `page`, `page_size` |
| GET | `/companies/{slug}/audits/{audit_id}/pages` | Tenant | — | `AuditPageResultsResponse` | Query: `page`, `page_size` |

### 6.5 Knowledge Base
**Prefix:** `/api/v1/knowledge-base`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `KnowledgeBaseStartRequest` | `PipelineRunResponse` (202) | Guard: returns 200 if artifacts exist |
| GET | `/{slug}/health` | Bearer | — | `KBHealthResponse` | Query: `threshold_override` |
| POST | `/{slug}/refresh-stale` | Member+ | `KBRefreshStaleRequest` | `PipelineRunResponse` (202) | Returns 200 if all fresh |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |
| POST | `/{run_id}/approve` | Member+ | `ApprovalRequest` | `ApprovalResponse` | HITL |

### 6.6 Knowledge Documents
**Prefix:** `/api/v1/companies/{slug}/knowledge-docs`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/` | Member+ | `multipart/form-data` (file) | `KnowledgeDocResponse` (201) | PDF, MD, TXT, DOCX |
| GET | `/` | Tenant | — | `KnowledgeDocListResponse` | Query: `product_slug` |
| GET | `/{doc_id}` | Tenant | — | `KnowledgeDocResponse` | |
| DELETE | `/{doc_id}` | Member+ | — | 204 No Content | |
| GET | `/{doc_id}/download` | Tenant | — | File binary | Original content-type |

### 6.7 Audience Personas
**Prefix:** `/api/v1/audience-persona`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `AudiencePersonaStartRequest` | `PipelineRunResponse` (202) | Guard: 200 if personas exist |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |
| POST | `/{run_id}/approve/briefs` | Member+ | `PersonaBriefApprovalRequest` | `ApprovalResponseAP` | HITL-1 |
| POST | `/{run_id}/approve/profiles` | Member+ | `PersonaProfileApprovalRequest` | `ApprovalResponseAP` | HITL-2 |
| POST | `/{slug}/add-persona` | Member+ | `ManualPersonaBriefRequest` | `{ persona_id, task_id }` (202) | Manual add |
| POST | `/{slug}/personas/{persona_id}/approve` | Member+ | `StandaloneApproveRequest` | `{ persona_id, status }` | |
| GET | `/{slug}/personas` | Bearer | — | `PersonaListResponse` | |

### 6.8 Voice Style Guide
**Prefix:** `/api/v1/voice-style-guide`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `VoiceStyleGuideStartRequest` | `PipelineRunResponse` (202) | Guard: 200 if guide fresh |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |
| POST | `/{run_id}/approve/authors` | Member+ | `AuthorApprovalRequest` | `ApprovalResponseVSG` | HITL |
| GET | `/{slug}/guide` | Bearer | — | `{ slug, guide_md, version, word_count, last_updated, source_authors[] }` | |

### 6.9 Research Orchestrator
**Prefix:** `/api/v1/research`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `ResearchOrchestratorStartRequest` | `PipelineRunResponse` (202) | Runs KB -> AP -> VSG |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |

### 6.10 Gap Analysis
**Prefix:** `/api/v1/gap-analysis`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `GapAnalysisStartRequest` | `PipelineRunResponse` (202) | Guard: 200 if artifacts exist |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |

### 6.11 Gap Data (Dashboard)
**Prefix:** `/api/v1/companies/{slug}/gap-analysis`

All endpoints: Auth = Tenant, Query param: `product_slug` (optional)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/summary` | `GapSummaryResponse` | SPA score, classifications, clusters |
| GET | `/queries` | `QueryListResponse` | Paginated. Query: `cluster`, `classification`, `search`, `sort_by`, `sort_dir`, `page`, `page_size` |
| GET | `/clusters` | `ClusterListResponse` | Cluster specs with centroid distances |
| GET | `/signals` | `SignalAveragesResponse` | Structural signal averages & correlations |
| GET | `/platforms` | `PlatformListResponse` | Per-platform citation breakdown |
| GET | `/heatmap` | `HeatmapResponse` | Gap score heatmap by cluster |
| GET | `/embeddings` | `EmbeddingProjectionResponse` | Query: `method` (umap\|tsne) |
| GET | `/trend` | `SPATrendResponse` | SPA score across runs |

### 6.12 Content Engine v1.3
**Prefix:** `/api/v1/content/v13`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `ContentStartRequestV13` | `PipelineRunResponseV13` (202) | Entry modes: autonomous, manual |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |
| POST | `/{run_id}/approve/topics` | Member+ | `TopicApprovalRequest` | `ApprovalResponseV13` | HITL-1 |
| POST | `/{run_id}/approve/briefs` | Member+ | `BriefApprovalRequest` | `ApprovalResponseV13` | HITL-2 |
| POST | `/{run_id}/approve/content` | Member+ | `ContentApprovalRequestV13` | `ApprovalResponseV13` | HITL-3 |
| POST | `/from-topics` | Member+ | `TopicContentStartRequest` | `PipelineRunResponseV13` (202) | TD -> Content pipeline |
| GET | `/{effective_slug}/topic-content-status` | Bearer | — | `TopicContentStatusResponse` | |

### 6.13 Content Data (Dashboard)
**Prefix:** `/api/v1/companies/{slug}/content`

All endpoints: Auth = Tenant, Query param: `product_slug` (optional)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/briefs` | `ContentBriefListResponse` | All briefs with statuses |
| POST | `/briefs` | `ContentBriefListItem` (201) | Add manual brief. Body: `AddBriefRequest` |
| GET | `/briefs/{brief_id}` | `ContentBriefDetailResponse` | Full brief detail with eval history |
| GET | `/briefs/{brief_id}/{stage}` | `StageContentResponse` | Stages: `outline`, `draft`, `enriched`, `formatted`, `eval_history`, `final` |

### 6.14 Topic Discovery
**Prefix:** `/api/v1/topic-discovery`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Member+ | `TopicDiscoveryStartRequest` | `PipelineRunResponse` (202) | |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |
| POST | `/{run_id}/approve/taxonomy` | Member+ | `TaxonomyApprovalRequest` | `ApprovalResponseTD` | HITL-1 |
| POST | `/{run_id}/approve/subdomains` | Member+ | `SubdomainSelectionRequest` | `ApprovalResponseTD` | HITL-1b |
| POST | `/{run_id}/approve/matrix` | Member+ | `MatrixApprovalRequest` | `ApprovalResponseTD` | HITL-2 |
| GET | `/{slug}/taxonomy` | Bearer | — | `TaxonomyReadResponse` | |
| GET | `/{slug}/matrix` | Bearer | — | `MatrixReadResponse` | |
| GET | `/{slug}/scored-subdomains` | Bearer | — | `ScoredSubdomainsResponse` | |
| GET | `/{slug}/personas` | Bearer | — | `PersonaAffinityResponse` | Query: `persona_id` |
| POST | `/expand` | Member+ | `TopicExpansionStartRequest` | `PipelineRunResponse` (202) | Requires discovery complete |
| GET | `/{slug}/expansion-status` | Bearer | — | `ExpansionStatusResponse` | |

### 6.15 Onboarding
**Prefix:** `/api/v1/onboarding`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/start` | Superuser | `OnboardingStartRequest` | `PipelineRunResponse` (202) | 3-phase orchestrator |
| GET | `/{run_id}/status` | Bearer | — | `TaskResponse` | |

### 6.16 CPS
**Prefix:** `/api/v1/cps`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/score` | Bearer | `CPSScoreRequest` | `CPSScoreResponse` | Returns 503 if model unavailable |

### 6.17 Daily Tracker
**Prefix:** `/api/v1/daily-tracker`

**Prompt Library:**

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| POST | `/prompts` | Member+ | `CreatePromptRequest` | `TrackedPrompt` (201) |
| GET | `/prompts` | Bearer | — | `PromptListResponse` |
| GET | `/prompts/{prompt_id}` | Bearer | — | `TrackedPrompt` |
| PUT | `/prompts/{prompt_id}` | Member+ | `UpdatePromptRequest` | `TrackedPrompt` |
| DELETE | `/prompts/{prompt_id}` | Member+ | — | 204 |
| PATCH | `/prompts/{prompt_id}/toggle` | Member+ | `{ active: bool }` | `TrackedPrompt` |
| POST | `/prompts/import` | Member+ | `{ slug: string }` | `[TrackedPrompt]` (201) |
| POST | `/prompts/bulk` | Member+ | `{ prompts: [] }` | `[TrackedPrompt]` (201) |

**Runs:**

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| POST | `/runs` | Member+ | `TriggerRunRequest` | `PipelineRunResponse` (202) |
| GET | `/runs/{run_id}` | Bearer | — | `RunStatusResponse` |
| GET | `/runs` | Bearer | — | `RunListResponse` |

**Analytics:**

| Method | Path | Auth | Query | Response |
|--------|------|------|-------|----------|
| GET | `/analytics/visibility` | Bearer | `run_id` | `VisibilityMetrics` |
| GET | `/analytics/mention-trend` | Bearer | `days (1-365)` | `[TrendDataPoint]` |
| GET | `/analytics/sov` | Bearer | `run_id` | `{ [brand]: float }` |
| GET | `/analytics/citations` | Bearer | `run_id` | `{ [brand]: object }` |
| GET | `/analytics/competitors` | Bearer | `run_id` | `[CompetitorMetrics]` |

### 6.18 CMS Integration
**Prefix:** `/api/v1/cms`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| POST | `/connect` | Member+ | `CMSConnectRequest` | `CMSConnectResponse` | Validates + stores credentials |
| GET | `/connection` | Bearer | — | `CMSConnectionInfoResponse \| null` | Cached in Redis |
| DELETE | `/connection` | Member+ | — | `{ disconnected: bool }` | |
| POST | `/sync` | Member+ | — | `{ run_id, pipeline, status }` (202) | Background sync |
| GET | `/synced-posts` | Bearer | — | `[CMSSyncedPostSummary]` | Query: `stale_only`, `limit`, `offset` |
| GET | `/stale-actions` | Bearer | — | `[StaleContentAction]` | Home dashboard cards |
| POST | `/stale-to-triage` | Member+ | `{ cms_synced_post_id }` | `StaleToTriageResponse` | Queue stale post for refresh |
| POST | `/publish` | Member+ | `CMSPublishRequest` | `CMSPublishResponse` | Publish brief to CMS |
| POST | `/refresh/{cms_post_id}` | Member+ | `CMSRefreshRequest` | `CMSPublishResponse` | Update existing post |
| GET | `/publish-history` | Bearer | — | `[CMSPublishHistoryItem]` | Query: `limit`, `offset` |
| GET | `/categories` | Bearer | — | `[CMSCategoryItem]` | CMS categories for publish UI |

### 6.19 Tasks
**Prefix:** `/api/v1/tasks`

| Method | Path | Auth | Body | Response | Notes |
|--------|------|------|------|----------|-------|
| GET | `/` | Bearer | — | `TaskListResponse` | Query: `pipeline`, `status`, `product_slug` |
| GET | `/{task_id}` | Bearer | — | `TaskResponse` | |
| POST | `/{task_id}/cancel` | Member+ | — | `CancelResponse` | Only running/pending tasks |
| POST | `/{task_id}/stream-token` | Bearer | — | `{ stream_token, expires_in: 3600 }` | |

### 6.20 Events (SSE)
**Prefix:** `/api/v1/tasks`

| Method | Path | Auth | Response | Notes |
|--------|------|------|----------|-------|
| GET | `/{task_id}/events` | Bearer or `?stream_token=xxx` | `text/event-stream` | See Section 3 |

### 6.21 Artifacts
**Prefix:** `/api/v1/artifacts`

| Method | Path | Auth | Response | Notes |
|--------|------|------|----------|-------|
| GET | `/companies` | Bearer | `{ companies: [string] }` | List visible company slugs |
| GET | `/{artifact_type}/{slug}` | Bearer | `{ artifact_type, slug, files: [{name, size}] }` | Types: company_context, personas, style_guides, gap_analysis, content, knowledge_base |
| GET | `/{artifact_type}/{slug}/{filename:path}` | Bearer | JSON/HTML/Text | File content |

### 6.22 Brand Data
**Prefix:** `/api/v1/companies/{slug}`

| Method | Path | Auth | Response | Notes |
|--------|------|------|----------|-------|
| GET | `/research/artifacts` | Tenant | `ResearchArtifactsResponse` | Company context, personas, style guide |
| GET | `/runs` | Tenant | `RunHistoryResponse` | Query: `pipeline`, `status`, `limit` |

### 6.23 Settings
**Prefix:** `/api/v1/companies/{slug}/settings`

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| GET | `/team` | Tenant | — | `TeamListResponse` |
| PUT | `/team/{user_id}` | Superuser | `UpdateUserRequest` | `TeamMemberResponse` |
| GET | `/profile` | Tenant | — | `CompanyProfileSettingsResponse` |
| PUT | `/profile` | Superuser | `UpdateCompanyProfileRequest` | `CompanyProfileSettingsResponse` |
| GET | `/pipeline-defaults` | Tenant | — | `PipelineDefaultsResponse` |
| PUT | `/pipeline-defaults` | Superuser | `UpdatePipelineDefaultsRequest` | `PipelineDefaultsResponse` |

---

## 7. Schemas

### 7.1 Common Schemas

#### PipelineRunResponse (returned by all pipeline `/start` endpoints)
```typescript
{
  run_id: string             // UUID — use for status polling and SSE
  pipeline: string           // "gap_analysis" | "content" | "knowledge_base" | etc.
  company_slug: string
  product_slug?: string
  effective_slug?: string    // "{company_slug}__{product_slug}"
  status: string             // "running" | "completed" | etc.
  created_at: string         // ISO 8601
  already_exists: boolean    // true if guard prevented re-run (200 response)
  message?: string
}
```

#### TaskResponse (returned by all `/{run_id}/status` endpoints)
```typescript
{
  run_id: string
  pipeline: string
  company_slug: string
  product_slug?: string
  effective_slug?: string
  status: "running" | "pending_approval" | "completed" | "failed" | "cancelled"
  current_step?: string
  progress_pct?: number      // 0-100
  created_at: string
  updated_at: string
  result?: object            // populated on completion
  error?: string             // populated on failure
  approval_payload?: object  // populated when pending_approval
}
```

#### ErrorResponse
```typescript
{
  detail: string
  error_code?: string        // machine-readable code (e.g., "domain_taken")
}
```

### 7.2 Gap Analysis Schemas

#### GapSummaryResponse
```typescript
{
  spa_score: {
    t_stat: number
    p_value: number
    effect: string           // "large_negative" | "small_negative" | "negligible" | etc.
    mean_citation_similarity: number
    mean_company_similarity: number
    median_citation_similarity: number
    median_company_similarity: number
  }
  proximity_stats: {
    citation_similarity_mean: number
    citation_similarity_median: number
    company_similarity_mean: number
    company_similarity_median: number
  }
  classification_counts: {
    significant_gap: number
    gap_to_close: number
    roughly_equal: number
    company_wins: number
  }
  cluster_performance: [{
    cluster_id?: string
    cluster_name: string
    query_count: number
    citation_count: number
    avg_gap: number
    avg_citation_sim: number
    avg_company_sim: number
    structural_rates: { [signal: string]: number }
  }]
  total_queries: number
  total_citations: number
  company_cited_count: number
  average_gap: number
  executive_summary: string
  recommendations: [{ [key: string]: any }]
}
```

#### QueryRow (inside QueryListResponse)
```typescript
{
  query_id: string
  query_text: string
  cluster_id?: string
  cluster_name?: string
  gap_score: number
  classification: "significant_gap" | "gap_to_close" | "roughly_equal" | "company_wins"
  company_sim: number
  citation_sim: number
  target_words: { min: number, max: number }
  reading_level: { min: number, max: number }
  headers: number
  patterns: string[]
  top_domain?: string
  top_exemplar_sim: number
  platform_citations: { [platform: string]: number }
  company_cited: boolean
  company_cited_platforms: string[]
  content_brief?: {
    target_word_count: { min: number, max: number }
    target_reading_level: { min: number, max: number }
    recommended_header_count: number
    header_hierarchy: { [level: string]: number }
    content_patterns: string[]
    dominant_authority?: string
    dominant_content_type?: string
    exemplars_analyzed: number
  }
  top_exemplars: [{
    similarity: number
    domain?: string
    url: string
    snippet?: string
    authority_type?: string
    content_type?: string
  }]
}
```

#### QueryListResponse
```typescript
{
  queries: QueryRow[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
```

#### ClusterSpecResponse (inside ClusterListResponse)
```typescript
{
  cluster_id?: string
  cluster_name: string
  query_count: number
  citations_analyzed: number
  centroid_distance?: number
  word_count_range: { min: number, max: number }
  required_elements: string[]
  structural_rates: { [signal: string]: number }
  avg_word_count: number
  faq_rate: number
  table_rate: number
  key_takeaways_rate: number
  dominant_content_type?: string
  dominant_authority_type?: string
  exemplar_themes: string[]
}
```

#### SignalAveragesResponse
```typescript
{
  signals: [{
    signal: string
    category: string
    citation_avg: number
    company_avg: number
    unit: string
    recommendation: string
  }]
  correlations: [{
    signal: string
    correlation: number
    category: string
  }]
  cluster_patterns: [{
    cluster_id: string
    cluster_name: string
    faq: number
    definition_opening: number
    key_takeaways: number
    comparison_table: number
    step_by_step: number
    research_refs: number
    expert_quotes: number
  }]
  cluster_fingerprints: { [cluster: string]: { [signal: string]: number } }
}
```

#### PlatformListResponse
```typescript
{
  platforms: [{
    name: string                           // "perplexity" | "openai" | "gemini" | "claude"
    total_citations: number
    unique_domains: number
    avg_citation_sim: number
    most_cited_domain?: string
    best_cluster?: string
    worst_cluster?: string
    per_cluster: { [cluster: string]: number }
  }]
  agreement: { [platform: string]: { [platform: string]: number } }
  citation_exclusivity: { [platform: string]: { [platform: string]: number } }
}
```

#### HeatmapResponse
```typescript
{
  clusters: [{
    cluster_name: string
    cluster_id?: string
    queries: [{
      query_id: string
      query_text: string
      gap_score: number
      classification: string
    }]
    avg_gap: number
  }]
  min_gap: number
  max_gap: number
}
```

#### EmbeddingProjectionResponse
```typescript
{
  method: "umap" | "tsne"
  point_count: number
  points: [{
    x: number
    y: number
    type: string           // "query" | "citation" | "company"
    id: string             // "q-0", "c-14", "co-3"
    label: string
    cluster: string
    cluster_id: string
    query_id?: string
    similarity?: number
    gap_score?: number
  }]
}
```

#### SPATrendResponse
```typescript
{
  trend: [{
    run_id: string
    run: string            // short date label ("Mar 15")
    timestamp: string      // ISO 8601
    spa_score: number
    citation_advantage: number
    company_advantage: number
    total_queries: number
    total_citations: number
  }]
}
```

### 7.3 Site Audit Schemas

#### AuditSummaryResponse
```typescript
{
  audit_id: string
  domain: string
  overall_score: number    // 0-100
  grade: string            // A, B, C, D, F
  pages_crawled: number
  total_findings: number
  status: "pending" | "running" | "completed" | "failed"
  started_at: string
  completed_at: string
}
```

#### AuditDetailResponse
```typescript
{
  audit_id: string
  domain: string
  overall_score: number
  grade: string
  pages_crawled: number
  pages_discovered: number
  duration_seconds: number
  dimension_scores: [{
    dimension: string      // crawlability, on_page_seo, security, eeat, freshness, performance, schema_markup, extractability
    score: number
    weight: number
    weighted_score: number
    finding_count: number
    critical_count: number
    high_count: number
    medium_count: number
    low_count: number
    info_count: number
  }]
  ai_bot_access: {
    gptbot_allowed: boolean
    claudebot_allowed: boolean
    perplexitybot_allowed: boolean
    google_extended_allowed: boolean
    ccbot_allowed: boolean
    has_llms_txt: boolean
    robots_txt_exists: boolean
  }
  sitemap_health: {
    has_sitemap: boolean
    sitemap_url_count: number
    sitemap_urls: string[]
    sitemap_errors: string[]
    has_sitemap_index: boolean
  }
  total_findings: number
  findings_by_severity: { [severity: string]: number }
  findings_by_dimension: { [dimension: string]: number }
  avg_snippet_readiness: number
  pages_with_schema: number
  avg_question_heading_ratio: number
  status: string
  error_message?: string
  started_at: string
  completed_at: string
}
```

#### AuditFindingResponse (inside AuditFindingsResponse)
```typescript
{
  finding_type: string
  dimension: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  message: string
  recommendation: string
  url: string
  details: { [key: string]: any }
}
```

#### PageResultResponse (inside AuditPageResultsResponse)
```typescript
{
  url: string
  status_code: number
  crawl_depth: number
  title: string
  word_count: number
  reading_level: number
  has_https: boolean
  is_noindex: boolean
  schema_result: {
    has_schema: boolean
    schema_types: string[]
    validation_errors: string[]
    inferred_page_type: string
  }
  aeo: {
    snippet_readiness_score: number
    question_heading_ratio: number
    quick_answer_hook_count: number
    self_contained_paragraph_ratio: number
    avg_paragraph_word_count: number
    content_patterns: { [pattern: string]: boolean }
  }
  finding_count: number
}
```

### 7.4 Content Schemas

#### ContentBriefListItem
```typescript
{
  id: string                 // brief_id (e.g., "brief-1")
  title: string
  status: "suggested" | "briefing" | "brief_review" | "approved" | "review" | "completed" | "rejected"
  content_type: "blog" | "faq" | "pillar_page" | "comparison" | "how_to"
  cluster: string
  target_word_count: number
  citability_score?: number  // 0-100
  cycle_id?: string
  task_id?: string           // HITL approval task_id
  created_at: string
  updated_at: string
  gap_context?: {
    gap_score: number
    classification: string
    company_similarity: number
    citation_similarity: number
    company_cited: boolean
    company_best_url: string
    why_picked: string[]
    success_indicators: [{ [key: string]: string }]
    exemplars: [{ [key: string]: any }]
  }
  published_url: string
  published_at?: string
}
```

#### ContentBriefDetailResponse
```typescript
{
  id: string
  title: string
  status: string
  content_type: string
  cluster: string
  target_word_count: { min: number, max: number }
  structural_targets: { [key: string]: any }
  key_topics: string[]
  key_angles: string[]
  priority_score: number
  citability_score?: number
  eval_history: [{
    cycle: number
    dimensions: [{
      dimension: string
      passed: boolean
      score: number
      feedback: string
    }]
    overall_passed: boolean
    overall_score: number
  }]
  final_passed: boolean
  exemplars: [{
    url: string
    word_count: number
    authority_type: string
    content_type: string
    snippet: string
  }]
  available_stages: string[] // ["outline", "draft", "enriched", "formatted", "final"]
}
```

#### StageContentResponse
```typescript
{
  brief_id: string
  stage: string
  content_type: "text/markdown" | "application/json"
  content: string | object   // markdown string or JSON object
}
```

### 7.5 Topic Discovery Schemas

#### TaxonomyReadResponse
```typescript
{
  slug: string
  taxonomy: object           // hierarchical tree structure
  version: number
  total_subdomains: number
  coverage_score: number
}
```

#### MatrixReadResponse
```typescript
{
  slug: string
  matrix: object             // topic assignment matrix
  version: number
  total_assignments: number
}
```

#### ScoredSubdomainsResponse
```typescript
{
  slug: string
  scored_subdomains: object
  version: number
  total_scored: number
  signals_used: string[]
}
```

#### PersonaAffinityResponse
```typescript
{
  slug: string
  persona_entries: object
  total_personas: number
  total_subdomains: number
}
```

#### ExpansionStatusResponse
```typescript
{
  slug: string
  effective_slug: string
  total_subdomains: number
  expanded: number
  not_expanded: number
  expanded_ids: string[]
  available_for_expansion: [{ [key: string]: any }]
}
```

### 7.6 Brand Data Schemas

#### ResearchArtifactsResponse
```typescript
{
  company_context: {
    content?: string         // markdown
    status: "none" | "draft" | "approved"
    updated_at?: string
  }
  personas: [{
    id: string               // "persona-icp"
    name: string
    type: "icp" | "secondary"
    content: string          // markdown
    status: "draft" | "approved"
    updated_at?: string
  }]
  style_guide: {
    content?: string         // markdown
    status: "none" | "draft" | "approved"
    updated_at?: string
  }
}
```

#### RunHistoryResponse
```typescript
{
  runs: [{
    id: string
    pipeline: string
    company: string          // display name
    company_slug: string
    status: string
    started: string          // ISO 8601
    duration: string         // human-readable ("3h 46m")
    queries: number
    citations: number
    spa_score: number
    steps_completed: number
    total_steps: number
  }]
  total: number
}
```

### 7.7 Company Schemas

#### CompanyProfileResponse
```typescript
{
  slug: string
  name: string
  domain: string
  products: [{
    slug: string
    name: string
    domain?: string
    description?: string
    has_research: boolean
    has_gap_analysis: boolean
    has_content: boolean
  }]
  has_research: boolean
  has_gap_analysis: boolean
  has_content: boolean
  research_summary: {
    company_context?: string
    company_context_status: "none" | "draft" | "approved"
    personas: string[]
    style_guide?: string
    style_guide_status: "none" | "draft" | "approved"
  }
  latest_runs: {
    [pipeline: string]: {
      run_id: string
      status: string
      created_at: string
      completed_at?: string
      summary?: object
    } | null
  }
}
```

### 7.8 CMS Schemas

#### CMSConnectRequest
```typescript
{
  provider: string           // "wordpress" (more adapters coming)
  site_url: string
  username: string
  api_key: string            // WordPress application password
}
```

#### CMSConnectionInfoResponse
```typescript
{
  provider: string
  site_url: string
  site_name: string
  cms_version: string
  user_display_name: string
  is_active: boolean
  last_sync_at?: string
  sync_post_count: number
}
```

#### CMSSyncedPostSummary
```typescript
{
  id: string                 // UUID
  cms_post_id: string
  title: string
  slug: string
  url: string
  word_count: number
  published_at?: string
  modified_at?: string
  is_stale: boolean
  staleness_days: number
  categories: string[]
  queued_for_refresh: boolean
}
```

#### CMSPublishRequest
```typescript
{
  brief_id: string
  effective_slug?: string
  product_slug?: string
  status: "draft" | "publish"
  slug_override?: string
  categories: string[]
}
```

#### CMSPublishResponse
```typescript
{
  cms_post_id: string
  url: string
  slug: string
  title: string
  status: string
  word_count: number
}
```

### 7.9 Settings Schemas

#### TeamMemberResponse
```typescript
{
  id: string
  email: string
  first_name: string
  last_name: string
  role: "superuser" | "member" | "viewer"
  is_active: boolean
  created_at: string
}
```

#### CompanyProfileSettingsResponse
```typescript
{
  slug: string
  name: string
  domain: string
  additional_domains: string[]
  industry?: string
  created_at: string
  updated_at: string
}
```

#### PipelineDefaultsResponse
```typescript
{
  max_crawl_pages?: number
  max_crawl_depth?: number
  max_queries?: number
  platforms?: string[]
  max_personas?: number
  auto_approve_research: boolean
  max_briefs?: number
  max_revision_cycles?: number
  auto_approve_content: boolean
  updated_at?: string
}
```

### 7.10 Knowledge Base Schemas

#### KBHealthResponse
```typescript
{
  slug: string
  overall_score: number      // 0-1
  doc_health: {
    [doc_type: string]: {    // company_overview, customer_reviews, competitor_registry, weakness_analysis, brand_perception
      doc_type: string
      status: "fresh" | "stale" | "missing"
      current_version: number
      last_updated?: string
      age_days: number
      staleness_threshold_days: number
      stale_reason?: string
      dependencies: string[]
    }
  }
  synthesis_version: number
  synthesis_last_updated?: string
  synthesis_needs_refresh: boolean
  stale_docs: string[]
  missing_docs: string[]
  last_full_refresh?: string
}
```

### 7.11 CPS Schemas

#### CPSScoreRequest
```typescript
{
  content_markdown: string   // min 50 chars
  target_queries: string[]   // 1-10 queries
  content_url: string        // default: "https://example.com"
}
```

#### CPSScoreResponse
```typescript
{
  cps_score: number
  per_engine: { [engine: string]: number }
  per_query: [{ [key: string]: any }]
  model_version: string
  feature_config: string
  target_weight: number
}
```

### 7.12 Pipeline Start Request Schemas

#### GapAnalysisStartRequest
```typescript
{
  company_name: string       // required
  domain: string             // required
  product_slug?: string
  seed_urls: string[]        // default: []
  force_rerun: boolean       // default: false — set true to bypass guard
  skip_steps: number[]       // default: []
  max_queries: number        // default: 150, range: 10-500
  platforms: string[]        // default: ["perplexity", "openai", "gemini", "claude"]
  language: string           // default: "en"
  region?: string
  additional_constraints?: string
  max_crawl_pages?: number
  max_crawl_depth?: number
}
```

#### KnowledgeBaseStartRequest
```typescript
{
  company_name: string
  domain: string
  product_slug?: string
  seed_urls: string[]
  force_rerun: boolean
  mode: "full" | "refresh" | "single"  // default: "full"
  refresh_docs?: string[]   // doc types to refresh
  single_doc?: string       // single doc type
  auto_approve_checkpoints: number[]  // [1, 2, 3] — which checkpoints to auto-approve
  express_mode: boolean     // default: false
  language: string
  region?: string
  internal_sources: string[]
  additional_constraints?: string
  staleness_threshold_days: number  // default: 30
}
```

#### ContentStartRequestV13
```typescript
{
  company_name: string
  domain: string
  entry_mode: "autonomous" | "manual"  // default: "autonomous"
  // Autonomous mode fields:
  max_topics: number         // default: 6, range: 1-15
  gap_slug?: string
  // Manual mode fields:
  manual_prompt?: string     // max 2000 chars
  manual_description?: string
  manual_cluster?: string
  gap_query_id?: string
  brief_id_hint?: string    // pattern: ^brief-\d{1,4}$
  // Common fields:
  product_slug?: string
  product_name?: string
  product_description?: string
  auto_approve: boolean      // default: false
  max_concurrent_workers: number  // default: 3, range: 1-10
  max_revision_cycles: number     // default: 2, range: 0-5
  skip_stages: number[]
}
```

#### OnboardingStartRequest
```typescript
{
  industry?: string          // max 200 chars
  seed_personas: string[]    // max 7
  seed_urls: string[]        // max 10
  max_pages: number          // default: 200, range: 10-500
  max_depth: number          // default: 4, range: 1-10
  max_personas: number       // default: 5, range: 3-7
  max_authors: number        // default: 3, range: 2-3
  max_queries: number        // default: 75, range: 10-500
  platforms: string[]        // default: ["perplexity", "openai", "gemini", "claude"]
  language: string           // default: "en"
  region?: string
  force_rerun: boolean       // default: false
}
```

---

## 8. Pipeline Data Availability Matrix

This matrix shows what the backend **already provides** and what the frontend can display.

### Data Dashboard Endpoints (Read-Only, No Pipeline Run Required)

| Frontend Page | Backend Endpoint(s) | Data Available | Readiness |
|---------------|---------------------|----------------|-----------|
| **Home / Command Center** | `GET /companies/{slug}` | Company profile, products, latest runs, research status | **Ready** |
| | `GET /companies/{slug}/runs` | Run history across all pipelines | **Ready** |
| | `GET /cms/stale-actions` | Stale content action cards | **Ready** |
| **Analytics — Summary** | `GET /.../gap-analysis/summary` | SPA score, gap classifications, cluster performance | **Ready** |
| **Analytics — Queries** | `GET /.../gap-analysis/queries` | Paginated query table with filters, sorting | **Ready** |
| **Analytics — Clusters** | `GET /.../gap-analysis/clusters` | Cluster specs, performance metrics | **Ready** |
| **Analytics — Signals** | `GET /.../gap-analysis/signals` | Structural signal averages, correlations | **Ready** |
| **Analytics — Platforms** | `GET /.../gap-analysis/platforms` | Per-platform citation breakdown, agreement | **Ready** |
| **Analytics — Heatmap** | `GET /.../gap-analysis/heatmap` | Gap score heatmap by cluster | **Ready** |
| **Analytics — Trend** | `GET /.../gap-analysis/trend` | SPA score trend across runs | **Ready** |
| **Analytics Lab — Embeddings** | `GET /.../gap-analysis/embeddings` | 2D projections (UMAP/t-SNE) | **Ready** |
| **Content Studio — Brief List** | `GET /.../content/briefs` | All briefs with statuses, citability scores | **Ready** |
| **Content Studio — Brief Detail** | `GET /.../content/briefs/{id}` | Full brief with eval history, structural targets | **Ready** |
| **Content Studio — Stage View** | `GET /.../content/briefs/{id}/{stage}` | Content at each pipeline stage | **Ready** |
| **Content Planner — Taxonomy** | `GET /topic-discovery/{slug}/taxonomy` | Hierarchical topic tree | **Ready** |
| **Content Planner — Matrix** | `GET /topic-discovery/{slug}/matrix` | Topic assignment matrix | **Ready** |
| **Content Planner — Subdomains** | `GET /topic-discovery/{slug}/scored-subdomains` | Scored subdomain list | **Ready** |
| **Content Planner — Persona Affinity** | `GET /topic-discovery/{slug}/personas` | Persona-topic mapping | **Ready** |
| **Content Planner — Expansion** | `GET /topic-discovery/{slug}/expansion-status` | Expansion progress | **Ready** |
| **Artifacts — Company Context** | `GET /.../research/artifacts` | Company context markdown | **Ready** |
| **Artifacts — Personas** | `GET /audience-persona/{slug}/personas` | Persona list with metadata | **Ready** |
| **Artifacts — Voice Guide** | `GET /voice-style-guide/{slug}/guide` | Voice style guide markdown | **Ready** |
| **Artifacts — KB Health** | `GET /knowledge-base/{slug}/health` | Doc health, staleness, scores | **Ready** |
| **Artifacts — Knowledge Docs** | `GET /.../knowledge-docs` | Uploaded documents | **Ready** |
| **Site Audit — List** | `GET /site-audit/companies/{slug}/audits` | Audit summaries | **Ready** |
| **Site Audit — Detail** | `GET /site-audit/companies/{slug}/audits/{id}` | Full audit with dimensions | **Ready** |
| **Site Audit — Findings** | `GET /site-audit/companies/{slug}/audits/{id}/findings` | Paginated findings | **Ready** |
| **Site Audit — Pages** | `GET /site-audit/companies/{slug}/audits/{id}/pages` | Per-page results | **Ready** |
| **CMS — Connection** | `GET /cms/connection` | CMS connection status | **Ready** |
| **CMS — Synced Posts** | `GET /cms/synced-posts` | Synced posts with staleness | **Ready** |
| **CMS — Publish History** | `GET /cms/publish-history` | Publish audit trail | **Ready** |
| **CMS — Categories** | `GET /cms/categories` | CMS categories for publish UI | **Ready** |
| **Daily Tracker — Prompts** | `GET /daily-tracker/prompts` | Tracked prompts | **Ready** |
| **Daily Tracker — Runs** | `GET /daily-tracker/runs` | Daily run list | **Ready** |
| **Daily Tracker — Analytics** | `GET /daily-tracker/analytics/*` | Visibility, mentions, SOV, citations | **Ready** |
| **Settings — Team** | `GET /.../settings/team` | Team members | **Ready** |
| **Settings — Profile** | `GET /.../settings/profile` | Company profile | **Ready** |
| **Settings — Pipeline Defaults** | `GET /.../settings/pipeline-defaults` | Pipeline configuration | **Ready** |
| **Attribution Dashboard** | — | — | **Not Yet** (Phase 2) |

### Pipeline Actions (Write Operations)

| Action | Backend Endpoint | Readiness |
|--------|------------------|-----------|
| Start onboarding | `POST /onboarding/start` | **Ready** |
| Start site audit | `POST /site-audit/start` | **Ready** |
| Start knowledge base | `POST /knowledge-base/start` | **Ready** |
| Start audience persona | `POST /audience-persona/start` | **Ready** |
| Start voice style guide | `POST /voice-style-guide/start` | **Ready** |
| Start research orchestrator (KB+AP+VSG) | `POST /research/start` | **Ready** |
| Start gap analysis | `POST /gap-analysis/start` | **Ready** |
| Start content engine | `POST /content/v13/start` | **Ready** |
| Start topic discovery | `POST /topic-discovery/start` | **Ready** |
| Start topic expansion | `POST /topic-discovery/expand` | **Ready** |
| Start content from topics | `POST /content/v13/from-topics` | **Ready** |
| Start daily tracker run | `POST /daily-tracker/runs` | **Ready** |
| Cancel pipeline | `POST /tasks/{id}/cancel` | **Ready** |
| HITL approvals (all pipelines) | Various `/approve/*` endpoints | **Ready** |
| Add manual brief | `POST /.../content/briefs` | **Ready** |
| Add manual persona | `POST /audience-persona/{slug}/add-persona` | **Ready** |
| CMS connect/disconnect/sync/publish | Various `/cms/*` endpoints | **Ready** |
| Upload knowledge doc | `POST /.../knowledge-docs` | **Ready** |
| CPS scoring | `POST /cps/score` | **Ready** |
| Manage products | CRUD on `/companies/{slug}/products` | **Ready** |
| Manage team | `PUT /.../settings/team/{userId}` | **Ready** |
| Update company profile | `PUT /.../settings/profile` | **Ready** |
| Update pipeline defaults | `PUT /.../settings/pipeline-defaults` | **Ready** |

---

## 9. Integration Readiness Assessment

### What's Immediately Usable (No Backend Changes Needed)

1. **All data dashboard endpoints** — Gap analysis, content studio, topic discovery, site audit, brand artifacts, daily tracker, CMS
2. **All pipeline start + HITL approval endpoints** — Every pipeline is fully operational
3. **SSE real-time streaming** — Complete with reconnection, heartbeat, and Last-Event-ID replay
4. **Auth flow** — Login, register, invite, join, token management
5. **Settings management** — Team, profile, pipeline defaults
6. **CMS integration** — Connect, sync, publish, refresh, stale detection
7. **Product management** — CRUD operations
8. **Knowledge doc management** — Upload, list, download, delete
9. **Task management** — List, status, cancel, stream tokens

### What Needs Frontend-Side Work (Backend Ready)

| Feature | Backend Status | Frontend Work Needed |
|---------|---------------|---------------------|
| Kanban board with real-time status | Backend provides `pipeline_state.json` + SSE events | Map brief statuses to Kanban columns |
| Content editor with stage tabs | Backend serves all stages via `/briefs/{id}/{stage}` | Render markdown + JSON preview |
| Eval history visualization | Backend provides `eval_history` with per-dimension scores | Chart/table component |
| Taxonomy tree visualization | Backend serves hierarchical JSON | Tree component with edit capability |
| Embedding scatter plots | Backend serves 2D coordinates | D3/Plotly scatter plot |
| Gap heatmap | Backend serves cluster-grouped gap scores | Heatmap visualization |
| HITL approval dialogs | Backend provides `approval_payload` via SSE | Modal/dialog components for each pipeline |
| SPA trend chart | Backend serves trend data points | Line chart |
| Audit dimension radar/bar chart | Backend serves dimension scores | Radar or bar chart |
| CMS publish workflow | Backend has full publish + category API | Publish dialog with category selector |

### What's Not Available Yet (Backend Work Required)

| Feature | Status | Notes |
|---------|--------|-------|
| **Attribution Dashboard** | Phase 2 | GA4 integration DB layer done, service/adapter/router pending |
| **Real-time collaboration** | Not planned | Single-user per company currently |
| **Webhook notifications** | Not available | SSE only — no push notifications |
| **File export (PDF/CSV)** | Not available | Frontend must implement client-side export |
| **Search across all entities** | Not available | Must search per-entity (queries, briefs, prompts separately) |
| **Activity feed / audit log** | Partial | Run history exists, but no granular activity feed |
| **Content versioning / diff** | Not available | Only latest version per stage stored |

---

## 10. Error Handling

### HTTP Status Codes

| Code | When | Action |
|------|------|--------|
| 200 | Success | Display data |
| 201 | Resource created | Display confirmation |
| 202 | Pipeline accepted | Start SSE monitoring |
| 204 | Deleted | Remove from UI |
| 400 | Invalid input | Show validation errors from `detail` |
| 401 | Token expired/invalid | Redirect to `/login` |
| 403 | Access denied | Show "Access denied" (tenant isolation failure) |
| 404 | Not found | Show "Not found" |
| 409 | Conflict | Show conflict message. Common: pipeline already running, domain taken, approval window closed |
| 503 | Service unavailable | Retry with backoff. CPS model or DB unavailable |

### Error Response Shape

```json
{
  "detail": "Human-readable error message",
  "error_code": "machine_readable_code"
}
```

### Guard Conditions (200 with `already_exists: true`)

Several pipeline start endpoints return **200** instead of **202** when artifacts already exist:
- Gap Analysis: previous results exist
- Knowledge Base: synthesis exists
- Audience Persona: personas exist and KB hasn't been updated
- Voice Style Guide: guide is fresh
- Topic Discovery: taxonomy exists
- Site Audit: audit exists for domain

To force a re-run, set `force_rerun: true` in the request body.

---

## 11. CORS & Infrastructure

### CORS Configuration

```
Default origins: ["http://localhost:3000", "http://localhost:3001"]
Production: Set API_CORS_ORIGINS env var (JSON array)
Methods: All
Headers: All
Credentials: Allowed
```

### Response Headers

```
X-Request-ID: {uuid}                    // Unique per request
X-Correlation-ID: {uuid or forwarded}   // Trace across services
```

### Next.js Proxy Configuration

The frontend uses Next.js rewrites to proxy API calls:

```javascript
// next.config.mjs
rewrites: [
  { source: '/api/:path*', destination: `${API_URL}/api/:path*` },
  { source: '/health', destination: `${API_URL}/health` },
  { source: '/readiness', destination: `${API_URL}/readiness` }
]
```

### Concurrency

- Maximum 3 concurrent pipelines (configurable via `API_MAX_CONCURRENT_PIPELINES`)
- Excess pipeline requests queue via semaphore
- Frontend receives `run_id` immediately; SSE events begin when pipeline actually starts

---

## Appendix A: Enum Reference

### Pipeline Names
`gap_analysis`, `knowledge_base`, `audience_persona`, `voice_style_guide`, `topic_discovery`, `content`, `site_audit`, `onboarding`, `research`, `daily_tracker`, `cms_sync`, `td_content`

### Task Statuses
`running`, `pending_approval`, `completed`, `failed`, `cancelled`

### User Roles
`superuser`, `member`, `viewer`

### Gap Classifications
`significant_gap`, `gap_to_close`, `roughly_equal`, `company_wins`

### Content Types
`blog`, `faq`, `pillar_page`, `comparison`, `how_to`

### Brief Statuses
`suggested`, `briefing`, `brief_review`, `approved`, `outlining`, `drafting`, `linking`, `enriching`, `evaluating`, `revising`, `review`, `pending_content_approval`, `completed`, `published`, `rejected`, `failed`

### Buyer Stages
`tofu` (Top of Funnel), `mofu` (Middle of Funnel), `bofu` (Bottom of Funnel)

### Intent Types
`informational`, `commercial`, `navigational`, `transactional`

### Search Platforms
`perplexity`, `openai`, `gemini`, `claude`

### Audit Dimensions
`crawlability`, `on_page_seo`, `security`, `eeat`, `freshness`, `performance`, `schema_markup`, `extractability`

### KB Document Types
`company_overview`, `customer_reviews`, `competitor_registry`, `weakness_analysis`, `brand_perception`

### Artifact Status
`none`, `draft`, `approved`

### Persona Status
`fresh`, `stale`, `missing`, `archived`

---

## Appendix B: Frontend Existing Integration Code

The frontend already has a well-structured API layer in place:

| Layer | Location | Notes |
|-------|----------|-------|
| API Client | `frontend/src/lib/api/client.ts` | Type-safe fetch wrapper with JWT injection, auto-401 redirect |
| Endpoints | `frontend/src/lib/api/endpoints.ts` | Centralized URL builders for all endpoints |
| Types | `frontend/src/lib/api/types.ts` | TypeScript response types matching backend schemas |
| Transforms | `frontend/src/lib/api/transforms.ts` | snake_case -> camelCase converters |
| SWR Hooks | `frontend/src/lib/hooks/` | 9 domain-specific hooks with caching configs |
| SSE Hook | `frontend/src/lib/hooks/useTaskStream.ts` | EventSource with auto-reconnection |
| Auth Store | `frontend/src/stores/auth.ts` | Zustand store with localStorage persistence |

**SWR Cache Settings:**
- Gap analysis: 60s cache, no stale revalidation (data rarely changes)
- Content briefs: 5s refresh (real-time during pipeline runs)
- Site audit: standard SWR defaults
- CMS: standard SWR defaults

**Auth Token Storage:**
- `localStorage.dp_token` — access token
- `localStorage.dp_user` — user JSON
- `localStorage.dp_company` — company JSON
