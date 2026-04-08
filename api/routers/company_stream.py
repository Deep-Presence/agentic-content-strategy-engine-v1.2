"""Company-wide SSE stream endpoint.

Multiplexes all pipeline state changes and notifications for a company
into a single EventSource connection. The frontend uses this to:
  (a) trigger re-polls when card state changes (``state_changed`` events)
  (b) display in-app notifications (``notification`` events)

Authentication flows through the BFF cookie proxy — the ASGI
AuthMiddleware validates the Bearer token injected by the BFF.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.auth.dependencies import require_auth
from core.events.company_event_bus import company_event_bus, CompanyEvent
from core.models.organization import UserProfile
from core.shared_tools.structured_logging import bind_context, clear_context

router = APIRouter(prefix="/api/v1/companies", tags=["company-stream"])

_HEARTBEAT_INTERVAL_S = 30


@router.get("/{company_slug}/stream")
async def company_stream(
    company_slug: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
) -> StreamingResponse:
    """SSE stream for all pipeline events within a company.

    Events:
      - ``state_changed``: one or more cards changed status (carries IDs + hint)
      - ``notification``: user-facing notification (HITL review, completion, error)
    """
    # Tenant isolation: verify the user belongs to the requested company
    auth_company_slug = getattr(request.state, "company_slug", None)
    if company_slug != auth_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    raw_corr = request.headers.get("X-Correlation-ID", "")
    correlation_id = raw_corr[:128] if raw_corr else str(uuid.uuid4())
    bind_context(
        correlation_id=correlation_id,
        user_id=getattr(request.state, "user_id", None),
        company_slug=company_slug,
    )

    queue = company_event_bus.subscribe(company_slug)

    async def event_generator() -> AsyncIterator[str]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_HEARTBEAT_INTERVAL_S,
                    )
                    yield (
                        f"event: {event.event_type}\n"
                        f"data: {json.dumps(event.data)}\n\n"
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            company_event_bus.unsubscribe(company_slug, queue)
            clear_context()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
