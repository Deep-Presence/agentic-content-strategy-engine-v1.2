# API Overview

> **Location:** `api/`
> **Owner:** API
> **Dependencies:** FastAPI, Uvicorn, `core/` modules, Redis, PostgreSQL
> **Dependents:** Frontend (BFF proxy), external clients
> **Last Updated:** 2026-04-09

## Overview

The API layer is a FastAPI application exposing 31 routers with 150+ endpoints. It uses pure ASGI middleware for authentication (SSE-safe, no buffering), RBAC dependencies for authorization, and a session-managed DI container for service construction. Background pipelines run via `asyncio.create_task()` with `DbTaskStore` for lifecycle management and `RedisEventBus` for SSE streaming.

## Architecture

```
Request Flow:
CORSMiddleware → AuthMiddleware (pure ASGI) → RequestLoggingMiddleware → Router
                     │                              │
              Set scope.state.user_id        Bind structlog context
              Set scope.state.company_slug   Log request duration
```

## App Factory (`app.py`)

### Startup Sequence (lifespan)
1. Structured logging initialization
2. Redis health check → `app.state.redis`
3. EventBus creation → `RedisEventBus` (requires healthy Redis)
4. TaskStore creation → `DbTaskStore(session_factory, redis_client)`
5. Storage backend → Local or R2, wrapped with `CachedStorageBackend`
6. Auth store initialization
7. DB session factory + health checks (PostgreSQL + pgvector)
8. Audit sink → `DbAuditSink` or `NoOpAuditSink`

### Exception Handlers
| Exception | HTTP Status | Error Code |
|-----------|------------|------------|
| `TaskNotFoundError` | 404 | `task_not_found` |
| `TaskConflictError` | 409 | `task_conflict` |
| `PipelineError` | 500 | `pipeline_error` |
| `ApprovalDeliveryError` | 503 | `approval_delivery_failed` |

### `app.state` Properties
`redis`, `redis_healthy`, `event_bus`, `task_store`, `artifacts_root`, `storage_backend`, `auth_store`, `secret_key`, `db_session_factory`, `db_healthy`, `pgvector_available`

## Middleware Chain

1. **CORSMiddleware** — handles OPTIONS preflight, configurable origins
2. **AuthMiddleware** — pure ASGI (no BaseHTTPMiddleware buffering). Extracts token from Bearer header or `?stream_token` query param. Sets `scope["state"]` with user_id/company_slug. Stream tokens restricted to `/events` endpoints only.
3. **RequestLoggingMiddleware** — binds request_id, correlation_id, user_id. Propagates via X-Correlation-ID, X-Request-ID headers. Skips SSE endpoints.

## Auth Dependencies (`auth/dependencies.py`)

```
require_auth(request) → UserProfile
    ↓
require_role("member", "superuser") → UserProfile
    ↓
require_tenant(slug) → UserProfile                     (lightweight slug check)
require_company_access(slug) → (UserProfile, Company)  (full lookup)
require_company_member(slug) → (UserProfile, Company)  (role + company)
```

## DI Container (`dependencies.py`)

Session-managed async generators for per-request DB service construction:
- `get_auth_service()` → `DbAuthService` or `JsonAuthService`
- `get_gap_data_service()` → `DbGapDataService` or `JsonGapDataService`
- `get_content_data_service()`, `get_kb_data_service()`, `get_persona_data_service()`, `get_vsg_data_service()`, `get_site_audit_data_service()`, `get_topic_discovery_data_service()`

Plus direct accessors: `get_task_store()`, `get_event_bus()`, `get_storage_backend()`, `get_redis()`

## Configuration (`config.py`)

```python
class ApiSettings(BaseSettings):
    cors_origins: List[str] = ["http://localhost:3000"]
    api_prefix: str = "/api/v1"
    max_concurrent_pipelines: int = 3
```
