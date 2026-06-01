"""SSE events streaming endpoint.

Authentication is handled by the ASGI AuthMiddleware which supports
both Bearer tokens and ``?stream_token=`` query params for SSE.
``require_auth`` dependency performs is_active check (C3 fix).
Task ownership is verified via workspace membership before streaming.
"""
from __future__ import annotations

import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.auth.dependencies import require_auth
from api.dependencies import get_event_bus, get_task_store, get_workspace_service
from api.routers._helpers import assert_task_workspace_access
from api.tasks.event_bus import EventBusProtocol
from core.models.organization import UserProfile
from core.services.task_store import TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol
from core.shared_tools.structured_logging import bind_context, clear_context

router = APIRouter(prefix="/api/v1/tasks", tags=["events"])


@router.get("/{task_id}/events")
async def stream_events(
    task_id: str,
    request: Request,
    user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> StreamingResponse:
    task = task_store.get_task(task_id)
    await assert_task_workspace_access(task, user, workspace_service)

    company_slug = task.company_slug
    raw_corr = request.headers.get("X-Correlation-ID", "")
    correlation_id = raw_corr[:128] if raw_corr else str(uuid.uuid4())
    bind_context(
        correlation_id=correlation_id,
        user_id=getattr(request.state, "user_id", None),
        company_slug=company_slug,
        task_id=task_id,
        pipeline_name=task.pipeline,
    )

    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id: int | None = None
    if last_event_id_str:
        try:
            last_event_id = int(last_event_id_str)
        except ValueError:
            pass

    def _get_task_status(tid: str) -> str | None:
        try:
            t = task_store.get_task(tid)
            status = t.status.value
            if status == "failed_restart":
                return "failed"
            return status
        except Exception:
            return None

    async def _stream_with_cleanup() -> AsyncIterator[str]:
        try:
            async for event in event_bus.stream(
                task_id,
                last_event_id=last_event_id,
                task_status_fn=_get_task_status,
            ):
                yield event
        finally:
            clear_context()

    return StreamingResponse(
        _stream_with_cleanup(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
