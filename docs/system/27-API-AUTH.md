# API Auth Layer

> **Location:** `api/auth/`
> **Owner:** API
> **Dependencies:** `core/auth/`, JWT tokens
> **Dependents:** All authenticated endpoints
> **Last Updated:** 2026-04-09

## Overview

The API auth layer provides authentication (identity extraction via pure ASGI middleware) and authorization (role/tenant checks via FastAPI dependencies). It follows a default-deny model where all routes require authentication unless explicitly listed as public.

## File Structure

| File | Purpose |
|------|---------|
| `middleware.py` | Pure ASGI auth middleware (no BaseHTTPMiddleware) |
| `dependencies.py` | FastAPI authorization dependencies |
| `models.py` | Request/response DTOs (Login, Register, Join) |
| `store.py` | JSON-backed auth store (legacy, replaced by DbAuthService) |

## Public Routes (no auth required)

```
/health, /readiness
/docs, /redoc, /openapi.json
/api/v1/auth/register
/api/v1/auth/login
/api/v1/auth/join
/api/v1/analytics/google/callback
/api/v1/analytics/google/sync-all
```

## Token Extraction (priority order)

1. `Authorization: Bearer {token}` header (all endpoints)
2. `?stream_token={token}` query param (SSE `/events` only)

Stream tokens have `stream_only=True` flag — rejected on non-SSE endpoints.

## Auth Flow

```
1. POST /api/v1/auth/login → { access_token, user, company }
2. Token stored in httpOnly cookie by frontend BFF
3. All subsequent requests: BFF reads cookie → injects Bearer header
4. AuthMiddleware extracts → verifies → sets scope.state
5. Dependencies check role/company/tenant as needed
```

## SSE Streaming Auth

```
1. POST /api/v1/tasks/{id}/stream-token → { stream_token } (60-min TTL)
2. GET /api/v1/tasks/{id}/events?stream_token={token} → SSE stream
```
