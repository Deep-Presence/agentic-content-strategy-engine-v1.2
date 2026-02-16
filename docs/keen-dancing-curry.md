# FastAPI Integration Plan — Content Strategy Engine

## Context

The Content Strategy Engine currently runs as CLI scripts (`scripts/run_*.py`) with no HTTP server. We need to expose all 3 pipelines (Research, Gap Analysis, Content Generation) plus CPS Model management and artifact retrieval via a FastAPI REST API. A React/Next.js frontend will consume this API. Pipelines are long-running (10-60 min) with 2 pipelines requiring Human-in-the-Loop (HITL) approval flows.

**Problem:** No way to trigger pipelines, monitor progress, or approve HITL decisions from a web interface.
**Outcome:** A production-ready FastAPI backend that wraps existing `core/` business logic with zero duplication, background task management, real-time progress via SSE, and HITL approval via REST endpoints.

---

## Decision: Same Repository (Monorepo)

**Choice: `api/` package at project root, same repo.**

Why:
- The API is a thin HTTP layer over `core/`. It directly imports `core.gap_analysis.pipeline.run_gap_analysis`, `core.research.graphs.pipeline.run_pipeline`, etc. No cross-repo versioning needed.
- Pydantic models from `core/models/` are reused directly as API schemas — zero duplication, zero drift.
- 2-person team. Cross-repo coordination overhead is unjustifiable.
- Strict import rule: `api/ → core/`, never `core/ → api/`.

---

## Directory Structure

```
content-strategy-engine/
├── api/                                  # NEW — FastAPI application
│   ├── __init__.py
│   ├── app.py                            # FastAPI factory + lifespan
│   ├── config.py                         # CORS origins, API-specific settings
│   ├── dependencies.py                   # FastAPI Depends (task_store, event_bus)
│   ├── exceptions.py                     # Global exception handlers
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── store.py                      # JSON-file-backed TaskStore
│   │   ├── models.py                     # TaskStatus enum, PipelineTask model
│   │   ├── runner.py                     # PipelineRunner (asyncio.create_task + HITL)
│   │   └── event_bus.py                  # In-memory pub/sub for SSE
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py                     # GET /health, /readiness
│   │   ├── research.py                   # /api/v1/research/*
│   │   ├── gap_analysis.py               # /api/v1/gap-analysis/*
│   │   ├── content.py                    # /api/v1/content/*
│   │   ├── cps.py                        # /api/v1/cps/* (CPS model mgmt)
│   │   ├── artifacts.py                  # /api/v1/artifacts/*
│   │   └── events.py                     # /api/v1/tasks/{id}/events (SSE)
│   └── schemas/
│       ├── __init__.py
│       └── common.py                     # PipelineRunResponse, TaskResponse, ErrorResponse
├── tests/
│   ├── api/                              # NEW — API layer tests
│   │   ├── __init__.py
│   │   ├── conftest.py                   # TestClient, mock TaskStore, fixtures
│   │   ├── test_health.py
│   │   ├── test_research.py
│   │   ├── test_gap_analysis.py
│   │   ├── test_content.py
│   │   ├── test_cps.py
│   │   ├── test_artifacts.py
│   │   ├── test_events.py
│   │   └── test_task_store.py
│   └── ... (existing tests unchanged)
├── scripts/
│   └── run_server.py                     # NEW — uvicorn entry point
└── ... (existing files unchanged)
```

---

## API Route Design

### Health & System

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/health` | `{"status": "ok"}` |
| `GET` | `/readiness` | Checks API keys configured, returns `{"ready": bool, "missing_keys": [...]}` |

### Research Pipeline — `/api/v1/research`

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/api/v1/research/start` | `ResearchStartRequest` | `PipelineRunResponse {run_id, status: "running"}` |
| `GET` | `/api/v1/research/{run_id}/status` | — | `TaskResponse` |
| `POST` | `/api/v1/research/{run_id}/approve` | `ApprovalRequest {decision, revision_note?}` | `TaskResponse` |

Here in the future versions, i would want to add api-endpoints of type PUT, for each of the individual research agents.
So, the vision is that, if say, i have run the whole pipeline once, but then i want to improve or add specific aspect or pov to a particular research artifact, i would want to run only that research agent, and i would want the research agent to use the
existing artifact only, and only add new things to it, instead of re-writing everything from scratch. So have a plan about how, we would be doing this, and how we should plan our design to adjust such future adjustments.

**Request schema:**
```python
class ResearchStartRequest(BaseModel):
    company: CompanyResearchInput        # reuse from core.models.artifacts
    persona: Optional[PersonaResearchInput] = None
    style_guide: Optional[StyleGuideResearchInput] = None
    auto_approve: bool = False
```

### Gap Analysis — `/api/v1/gap-analysis`

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/api/v1/gap-analysis/start` | `GapAnalysisStartRequest` | `PipelineRunResponse` |
| `GET` | `/api/v1/gap-analysis/{run_id}/status` | — | `TaskResponse` |

Again over here, in the future versions, there is a chance we would want to add api-endpoints specifically for each of the individual steps of the research agent. so plan accordingly.
For gap-analysis, also make sure the user had the endpoints to view all the visualisations produced by our pipeline in v1. 

**Request schema:**
```python
class GapAnalysisStartRequest(BaseModel):
    input_data: GapAnalysisInput         # reuse from core.models.gap_analysis
    skip_steps: List[int] = []
```

### Content Generation — `/api/v1/content`

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/api/v1/content/start` | `ContentGenerationInput` (from core) | `PipelineRunResponse` |
| `GET` | `/api/v1/content/{run_id}/status` | — | `TaskResponse` |
| `POST` | `/api/v1/content/{run_id}/approve` | `ContentApprovalRequest {brief_id, decision, editor_notes?}` | `TaskResponse` |

### CPS Model — `/api/v1/cps`
Let's not add the end-points for the cps model in our v1.
<!-- | Method | Path | Body | Response |
|--------|------|------|----------|
| `GET` | `/api/v1/cps/taxonomies` | — | List of available taxonomy files |
| `GET` | `/api/v1/cps/taxonomies/{name}` | — | Taxonomy JSON content |
| `POST` | `/api/v1/cps/taxonomies` | `{name, queries: [...]}` | Created taxonomy metadata |
| `PUT` | `/api/v1/cps/taxonomies/{name}` | Updated query list | Updated taxonomy |
| `DELETE` | `/api/v1/cps/taxonomies/{name}` | — | Confirmation | -->

### Artifacts — `/api/v1/artifacts`

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/v1/artifacts/companies` | List of company slugs |
| `GET` | `/api/v1/artifacts/{type}/{slug}` | Artifact listing (files in that dir) |
| `GET` | `/api/v1/artifacts/{type}/{slug}/{filename}` | Raw artifact content (MD/JSON) |

`type` = `company_context` | `personas` | `style_guides` | `gap_analysis` | `content`

Just make sure the user is able to access each of the output or content artifact that our pipelines produce, except for the embeddings one. 

### Task Management (Cross-Pipeline)

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/v1/tasks` | List all tasks (filterable by pipeline, status) |
| `GET` | `/api/v1/tasks/{task_id}` | Task details + progress |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | Cancel a running task |
| `GET` | `/api/v1/tasks/{task_id}/events` | **SSE stream** of pipeline events |

### Common Response Schemas

```python
class PipelineRunResponse(BaseModel):
    run_id: str
    pipeline: str
    status: str              # "running"
    created_at: datetime

class TaskResponse(BaseModel):
    run_id: str
    pipeline: str            # "research" | "gap_analysis" | "content"
    status: str              # "running" | "pending_approval" | "completed" | "failed" | "cancelled"
    current_step: Optional[str] = None
    progress_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    approval_payload: Optional[Dict[str, Any]] = None

class ApprovalRequest(BaseModel):
    decision: Literal["approve", "revise", "reject"]
    revision_note: Optional[str] = None

class ApprovalRecord(BaseModel):
    """Audit trail for HITL decisions (Codex: approval audit)"""
    task_id: str
    stage: str
    decision: str
    revision_note: Optional[str] = None
    decided_at: datetime
    # Future: decided_by: str  (when auth is added)

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
```

---

## Background Task Architecture

**Choice: `asyncio.create_task` + JSON-file-backed TaskStore**

Why not Celery/arq/Redis:
- 5-10 pipeline runs/day — massively overkill
- Pipelines are already async coroutines — they run natively in the FastAPI event loop
- HITL requires bidirectional communication (pipeline waits for approval) — with Celery this needs separate pub/sub; with asyncio we use `asyncio.Event` directly

### TaskStore Design

- **In-memory dict** for fast reads (no file I/O on every `GET /tasks/{id}`)
- **Atomic JSON persistence** on every mutation — write to temp file, then `os.replace()` (atomic on POSIX) to prevent corruption. One file per task under `artifacts/_jobs/`.
- **On startup**: scan `artifacts/_jobs/` to recover completed/failed task history; mark any "running" tasks as `failed_restart` (Codex: orphan recovery)
- **asyncio.Event** for HITL approval gates — background task awaits event, API sets it
- **Global concurrency semaphore** — cap at 3 concurrent pipeline runs to prevent resource exhaustion (Codex: throttling)

### PipelineRunner

Wraps each pipeline execution with:
1. `asyncio.create_task()` for background execution
2. Try/catch for proper status updates on success/failure
3. Event publishing for SSE subscribers
4. HITL approval loop using `asyncio.Event`

For the **research pipeline** (synchronous): wrap with `asyncio.to_thread()` to avoid blocking the event loop.

### Concurrent Run Protection

Per-company-slug lock prevents two simultaneous runs for the same company. Returns `409 Conflict` if attempted.

---

## HITL Integration

The key challenge: LangGraph `interrupt()` pauses execution, and `graph.invoke()` raises `GraphInterrupt`. To resume, the graph must be re-invoked.

### Solution: MemorySaver Checkpointer + Split-Invoke

**Modification needed in `core/`** (backward-compatible):

Add optional `checkpointer` parameter to `build_graph()` functions:
- `core/research/graphs/company_research.py` → `build_graph(checkpointer=None)`
- `core/research/graphs/persona_research.py` → `build_graph(checkpointer=None)`
- `core/research/graphs/style_guide.py` → `build_graph(checkpointer=None)`
- `core/content_engine/graph.py` → `build_content_review_graph(checkpointer=None)`

Currently: `graph.compile()` (no checkpointer)
Changed to: `graph.compile(checkpointer=checkpointer)`

The CLI path continues to pass `None` (unchanged behavior). The API path passes `MemorySaver()` to enable interrupt/resume.

### HITL Flow (Research Pipeline Example)

```
1. POST /api/v1/research/start
   → Creates task, launches asyncio background task
   → Response: {run_id, status: "running"}

2. Background task runs company stage:
   graph = build_company_graph(checkpointer=MemorySaver())
   result = graph.invoke(state, config={"configurable": {"thread_id": run_id}})
   → GraphInterrupt raised
   → Caught, stored in TaskStore: status="pending_approval", approval_payload={draft_path, preview}
   → SSE event: {type: "pending_approval", stage: "company", ...}

3. GET /api/v1/research/{run_id}/status
   → {status: "pending_approval", approval_payload: {stage: "company", draft_path: "..."}}

4. Frontend fetches draft: GET /api/v1/artifacts/company_context/{slug}.draft.md

5. POST /api/v1/research/{run_id}/approve
   {decision: "approve"}
   → TaskStore.submit_approval() → sets asyncio.Event
   → Background task resumes:
     graph.invoke(Command(resume={"approval_decision": "approve"}), config=...)
   → Continues to persona stage (may interrupt again)

6. Eventually: status="completed", result={artifact_paths: [...]}
```

### Gap Analysis: No HITL Needed

Runs straight through 8 steps. Simplest integration — just `asyncio.create_task(run_gap_analysis(input_data, skip_steps))`.

### Content Generation: HITL for Stage 4

Same pattern as research. The `build_content_review_graph()` gets a `checkpointer` parameter. Each content piece can be individually approved/rejected.

---

## Real-Time Progress: SSE (Server-Sent Events)

**Choice: SSE over WebSocket**

Why: Progress is unidirectional (server→client). SSE has native browser `EventSource` API with auto-reconnection. WebSocket is overkill — the only bidirectional need (HITL approval) goes through REST POST.

### Implementation

```python
@router.get("/api/v1/tasks/{task_id}/events")
async def stream_events(task_id: str, request: Request):
    return StreamingResponse(
        event_bus.stream(task_id),  # async generator
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### Event Types

Each event includes an auto-incrementing `id` field for `Last-Event-ID` reconnection support (Codex: SSE reliability).

```json
{"id": "1", "type": "step_start",        "step": 1, "name": "Embed Company Assets"}
{"id": "2", "type": "step_complete",     "step": 1, "elapsed_s": 120.5}
{"id": "3", "type": "progress",          "step": 3, "detail": "Searching perplexity (1/4)"}
{"id": "4", "type": "pending_approval",  "stage": "company", "payload": {...}}
{"id": "5", "type": "approval_received", "decision": "approve"}
{"id": "6", "type": "completed",         "result": {...}}
{"id": "7", "type": "failed",            "error": "..."}
```

### SSE Reconnection Support

EventBus keeps a bounded event history (last 100 events per task). If client reconnects with `Last-Event-ID` header, replay missed events before streaming live. This handles network blips without requiring WebSocket complexity.

### Integration with Existing Pipelines

For v1: The API-side runner wraps each pipeline step and publishes events between step boundaries. This avoids modifying `core/` pipeline orchestrators.

For v2: Add optional `on_progress: Callable` callback to `run_gap_analysis()` and `run_content_generation()` signatures (backward-compatible with default `None`).

---

## CPS Model Endpoints

The CPS model taxonomy is currently at an external path: `Deep_Presence/research/Citation_Signal_Predictor/cps_model/b2b_queries_180.json`.

**Plan:**
1. Create `artifacts/cps_taxonomies/` directory as the API-managed taxonomy store
2. On first startup, copy the default taxonomy from the external path (if it exists)
3. API endpoints manage CRUD for taxonomy files
4. Gap analysis s2 (`generate_queries`) will be updated to accept a `taxonomy_path` parameter (currently hardcoded) — configurable via the API

This decouples the CPS model from the external filesystem path (resolving known tech debt item #3 in CLAUDE.md).

---

## Error Handling

### Global Exception Handlers

```python
# api/exceptions.py
- ValidationError → 422 with field-level errors
- TaskNotFoundError → 404
- TaskConflictError → 409 (e.g., approving a non-pending task)
- PipelineError → 500 with error message (no stack trace)
- Generic Exception → 500 with generic message
```

### Per-Pipeline Errors

- Caught in PipelineRunner wrapper, stored as `PipelineTask.error`
- API never exposes stack traces — only error message strings
- Structured logging with `logging.getLogger(__name__)` in each router

---

## Testing Strategy (TDD)

### Principle: Tests first, then implementation. Test the HTTP contract, mock the pipelines.

### Test Files (mirrors `api/`)

| Test File | What It Tests |
|-----------|---------------|
| `tests/api/test_task_store.py` | TaskStore CRUD, persistence, reload from disk |
| `tests/api/test_health.py` | Health/readiness endpoints |
| `tests/api/test_gap_analysis.py` | Start pipeline, check status, SSE events |
| `tests/api/test_research.py` | Start, HITL approval flow, multi-stage resume |
| `tests/api/test_content.py` | Start, per-brief HITL approval |
| `tests/api/test_cps.py` | Taxonomy CRUD operations |
| `tests/api/test_artifacts.py` | Artifact listing and retrieval |
| `tests/api/test_events.py` | SSE stream behavior, keepalive, disconnect |

### Test Patterns

```python
# conftest.py
@pytest.fixture
def task_store(tmp_path):
    return TaskStore(base_dir=tmp_path)

@pytest.fixture
def app(task_store):
    app = create_app()
    app.state.task_store = task_store
    return app

@pytest.fixture
def client(app):
    return TestClient(app)
```

- Mock all pipeline functions (`run_gap_analysis`, `run_pipeline`, `run_content_generation`)
- Use `pytest.mark.asyncio` for async tests
- Use `httpx.AsyncClient` for SSE stream tests
- Use `tmp_path` fixture for isolated artifact directories

---

## New Dependencies

```
# api/
fastapi>=0.115,<1.0
uvicorn[standard]>=0.32,<1.0
python-multipart>=0.0.12           # Form data support
```

**NOT adding:** celery, redis, arq, websockets, sqlalchemy

---

## Core Modifications Required (Backward-Compatible)

These are minimal changes to `core/` to support the API layer:

| File | Change | Backward Compatible? |
|------|--------|---------------------|
| `core/research/graphs/company_research.py` | `build_graph(checkpointer=None)` → `graph.compile(checkpointer=checkpointer)` | Yes — `None` = current behavior |
| `core/research/graphs/persona_research.py` | Same | Yes |
| `core/research/graphs/style_guide.py` | Same | Yes |
| `core/content_engine/graph.py` | `build_content_review_graph(checkpointer=None)` | Yes |
| `core/gap_analysis/steps/s2_generate_queries.py` | Accept `taxonomy_path` parameter (default = current hardcoded path) | Yes |

---

## Implementation Order (TDD)

### Phase 1: Foundation (Tasks 1-5)

1. **TaskStore + models** — JSON-file-backed task persistence with full unit tests
2. **EventBus** — In-memory pub/sub for SSE with tests
3. **FastAPI app factory** — Lifespan, CORS, exception handlers
4. **Health endpoints** — `/health`, `/readiness`
5. **`scripts/run_server.py`** — Uvicorn entry point

### Phase 2: Gap Analysis API (Tasks 6-8) — simplest pipeline, no HITL

6. **`POST /api/v1/gap-analysis/start`** — Launch background task, return run_id
7. **`GET /api/v1/gap-analysis/{run_id}/status`** — Task lookup
8. **`GET /api/v1/tasks/{task_id}/events`** — SSE stream with step progress

### Phase 3: Artifacts & CPS (Tasks 9-11)

9. **Artifact listing/retrieval endpoints** — Read from filesystem
10. **CPS taxonomy CRUD** — `artifacts/cps_taxonomies/` management
11. **Update s2 to accept taxonomy_path param** — Decouple from hardcoded path

### Phase 4: Research Pipeline API + HITL (Tasks 12-15)

12. **Modify `build_graph()` functions** — Add `checkpointer` parameter
13. **PipelineRunner with HITL support** — asyncio.Event approval gates
14. **Research start + status endpoints**
15. **Research approval endpoint** — Resume from interrupt

### Phase 5: Content Generation API + HITL (Tasks 16-18)

16. **Content generation start endpoint**
17. **Content HITL approval** — Per-brief approve/edit/reject
18. **Task listing + cancellation endpoints**

### Phase 6: Polish (Tasks 19-21)

19. **CORS configuration** for React/Next.js frontend
20. **Request logging middleware**
21. **Update `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md`** + `_memory/`

---

## Verification Plan

1. **Unit tests:** `pytest tests/api/ -v` — all TaskStore, router, and schema tests pass
2. **Integration test:** Start server with `python scripts/run_server.py`, hit `/health`, start a gap analysis run with mocked pipeline, verify SSE events stream correctly
3. **HITL test:** Start a research pipeline run, verify it pauses at `pending_approval`, submit approval via POST, verify pipeline resumes and completes
4. **Artifact test:** Run a pipeline, verify artifacts are accessible via `/api/v1/artifacts/` endpoints
5. **CPS test:** Upload a taxonomy, verify it's stored and retrievable
6. **Existing tests:** `pytest tests/ -v` — confirm all existing 90+ tests still pass (no core regressions)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| In-memory TaskStore loses running tasks on crash | Atomic JSON persistence recovers history; artifacts on disk are source of truth |
| LangGraph MemorySaver is in-memory only | Sufficient for single-instance local dev; upgrade to PostgresSaver for production |
| Research pipeline is synchronous (blocks event loop) | Wrapped in `asyncio.to_thread()` |
| Two concurrent runs for same company slug | Per-slug lock, 409 Conflict response |
| Large artifact responses (embeddings) | API schemas exclude embedding vectors; use streaming for large files |
| JSON file corruption on crash during write | Atomic write: temp file + `os.replace()` (POSIX atomic) |
| Resource exhaustion from too many concurrent runs | Global semaphore caps at 3 concurrent pipelines |

---

## Codex Review Summary

Codex (o4-mini) reviewed this plan. Key findings addressed:

| Codex Finding | Our Response |
|---------------|-------------|
| JSON write corruption risk | Added atomic write pattern (temp + os.replace) |
| No orphan task recovery | Added startup scan to mark stale "running" tasks as failed_restart |
| No approval audit trail | Added ApprovalRecord model with timestamps |
| SSE reconnection gaps | Added Last-Event-ID support with bounded event history replay |
| No concurrency throttling | Added global semaphore (max 3 concurrent pipeline runs) |
| Missing auth/security | Deferred to Phase 7 (not needed for local dev — frontend integration will drive this) |
| Celery/Redis/Temporal suggested | Rejected for current scale (5-10 runs/day, single instance). Noted as upgrade path. |
| Tight coupling of core models to API | Request bodies reuse core models (intentional — single source of truth). Response schemas are separate thin projections. |

### Production Upgrade Path (When Needed)

When scaling beyond single-instance local dev:
1. TaskStore → PostgreSQL-backed with SQLAlchemy async
2. MemorySaver → PostgresSaver for LangGraph checkpoint persistence
3. EventBus → Redis pub/sub for multi-instance SSE
4. Add JWT auth middleware
5. Add rate limiting
6. Containerize with Docker + health check probes
