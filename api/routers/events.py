"""SSE events streaming endpoint.

Authentication is handled by the ASGI AuthMiddleware which supports
both Bearer tokens and ``?stream_token=`` query params for SSE.
Task ownership is verified before streaming begins.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.dependencies import get_event_bus, get_task_store
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskStore

router = APIRouter(prefix="/api/v1/tasks", tags=["events"])


@router.get("/{task_id}/events")
async def stream_events(
    task_id: str,
    request: Request,
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
) -> StreamingResponse:
    # Validate task exists (raises 404 via exception handler if not)
    task = task_store.get_task(task_id)

    # Tenant isolation: verify the task belongs to the user's company
    company_slug = getattr(request.state, "company_slug", None)
    if company_slug and task.company_slug != company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id: int | None = None
    if last_event_id_str:
        try:
            last_event_id = int(last_event_id_str)
        except ValueError:
            pass  # Ignore malformed Last-Event-ID, replay all

    return StreamingResponse(
        event_bus.stream(task_id, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
