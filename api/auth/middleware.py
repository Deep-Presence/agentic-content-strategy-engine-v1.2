"""JWT auth middleware — grace mode for v0.

Extracts user identity from Authorization header and injects
into request.state. In grace mode (v0), unauthenticated requests
are allowed through — the middleware sets request.state.user = None.

When auth is enforced (post-Supabase), unauthenticated requests
will receive 401.
"""
from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class AuthMiddleware(BaseHTTPMiddleware):
    """Grace-mode auth middleware.

    - If valid token: sets request.state.user_id, .company_slug
    - If no/invalid token: sets both to None (allows through)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request.state.user_id = None
        request.state.company_slug = None

        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            auth_store = getattr(request.app.state, "auth_store", None)
            if auth_store:
                payload = auth_store.verify_token(token)
                if payload:
                    request.state.user_id = payload.get("user_id")
                    request.state.company_slug = payload.get("company_slug")

        return await call_next(request)


def get_current_user_id(request: Request) -> Optional[str]:
    """Extract user_id from request state. Returns None if not authenticated."""
    return getattr(request.state, "user_id", None)


def get_current_company_slug(request: Request) -> Optional[str]:
    """Extract company_slug from request state. Returns None if not authenticated."""
    return getattr(request.state, "company_slug", None)
