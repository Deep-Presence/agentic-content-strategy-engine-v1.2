"""Pure ASGI auth middleware — default-deny on protected routes.

Replaces the previous BaseHTTPMiddleware grace-mode implementation.
Middleware handles *authentication* (identity extraction).
FastAPI dependencies handle *authorization* (role + tenant checks).

Token extraction:
  - ``Authorization: Bearer {token}`` header (all endpoints)
  - ``?stream_token={token}`` query param (SSE /events only — Codex C4)

Public routes (no auth required):
  /health, /readiness, /docs, /redoc, /openapi.json,
  /api/v1/auth/register, /api/v1/auth/login
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.parse import parse_qs

from starlette.types import ASGIApp, Receive, Scope, Send

from core.auth.utils.tokens import verify_token as _verify_token_util

logger = logging.getLogger(__name__)

# ── Public route configuration ─────────────────────────────

_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/readiness",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/join",
})

_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/docs/",
    "/redoc/",
)


def _is_public(path: str) -> bool:
    """Return True if the path should be accessible without auth."""
    if path in _PUBLIC_PATHS:
        return True
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# ── Token extraction ───────────────────────────────────────

def _extract_token_from_headers(headers: list[tuple[bytes, bytes]]) -> Optional[str]:
    """Extract Bearer token from raw ASGI headers."""
    for name, value in headers:
        if name == b"authorization":
            decoded = value.decode("latin-1")
            if decoded.startswith("Bearer "):
                return decoded[7:]
    return None


def _extract_stream_token_from_query(query_string: bytes) -> Optional[str]:
    """Extract stream_token from query string for SSE endpoints."""
    if not query_string:
        return None
    params = parse_qs(query_string.decode("latin-1"))
    tokens = params.get("stream_token")
    return tokens[0] if tokens else None


def _extract_token(scope: Scope) -> Optional[str]:
    """Extract auth token from the request — header first, then query param for SSE."""
    headers = scope.get("headers", [])
    token = _extract_token_from_headers(headers)
    if token:
        return token

    # Fallback: stream_token query param for SSE EventSource endpoints
    path = scope.get("path", "")
    if path.endswith("/events"):
        return _extract_stream_token_from_query(scope.get("query_string", b""))

    return None


# ── 401 response sender ───────────────────────────────────

async def _send_401(send: Send, detail: str, code: str) -> None:
    """Send a raw ASGI 401 JSON response."""
    body = json.dumps({"detail": detail, "code": code}).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", b"application/json"),
            (b"www-authenticate", b"Bearer"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


# ── Middleware ─────────────────────────────────────────────

class AuthMiddleware:
    """Pure ASGI middleware — default-deny on protected routes.

    Public routes pass through without auth.
    Protected routes require a valid Bearer token (or stream_token for SSE).
    Sets ``scope["state"]["user_id"]`` and ``scope["state"]["company_slug"]``
    for downstream dependencies.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # Ensure state dict exists
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["user_id"] = None
        scope["state"]["company_slug"] = None

        # Public paths — allow through without auth
        if _is_public(path):
            await self.app(scope, receive, send)
            return

        # Extract token
        token = _extract_token(scope)
        if not token:
            await _send_401(send, "Missing authentication token", "missing_token")
            return

        # Verify token via extracted utility (no AuthStore dependency)
        secret_key = self._get_secret_key(scope)
        if not secret_key:
            logger.error("secret_key not available on app.state")
            await _send_401(send, "Authentication service unavailable", "auth_unavailable")
            return

        payload = _verify_token_util(secret_key, token)
        if not payload:
            await _send_401(send, "Invalid or expired token", "invalid_token")
            return

        # Stream tokens can only be used for SSE endpoints (Codex C4)
        if payload.get("stream_only") and not path.endswith("/events"):
            await _send_401(send, "Stream token cannot be used here", "invalid_token")
            return

        # Populate request state for downstream dependencies
        scope["state"]["user_id"] = payload.get("user_id")
        scope["state"]["company_slug"] = payload.get("company_slug")

        await self.app(scope, receive, send)

    @staticmethod
    def _get_secret_key(scope: Scope) -> Optional[str]:
        """Safely retrieve secret_key from app state."""
        app = scope.get("app")
        if app and hasattr(app, "state"):
            return getattr(app.state, "secret_key", None)
        return None


# ── Helper functions (backward compat) ─────────────────────

def get_current_user_id(request: Any) -> Optional[str]:
    """Extract user_id from request state. Returns None if not authenticated."""
    return getattr(request.state, "user_id", None)


def get_current_company_slug(request: Any) -> Optional[str]:
    """Extract company_slug from request state. Returns None if not authenticated."""
    return getattr(request.state, "company_slug", None)
