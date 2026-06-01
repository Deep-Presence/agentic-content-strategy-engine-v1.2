"""Task management API endpoints.

All endpoints require authentication. Users can only see and manage
tasks for workspaces they belong to (resolved via workspace membership).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth.dependencies import (
    get_workspace_read_slug,
    get_workspace_write_slug,
    require_auth,
)
from api.dependencies import get_auth_service, get_event_bus, get_task_store, get_workspace_service
from api.routers._helpers import assert_task_workspace_access
from core.auth.service import AuthServiceProtocol
from api.schemas.common import CancelResponse, TaskListResponse, TaskResponse, TaskSummary
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import TaskStatus
from core.services.task_store import TaskStoreProtocol
from core.models.organization import UserProfile
from core.services.workspace_protocol import WorkspaceServiceProtocol

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

_CANCELLABLE_STATES = {TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL}


@router.get("")
def list_tasks(
    pipeline: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    product_slug: Optional[str] = Query(None),
    workspace_slug: str = Depends(get_workspace_read_slug),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    _user: UserProfile = Depends(require_auth),
) -> TaskListResponse:
    tasks = task_store.list_tasks(
        pipeline=pipeline,
        status=status,
        company_slug=workspace_slug,
        product_slug=product_slug,
    )
    summaries = [
        TaskSummary(
            run_id=t.task_id,
            pipeline=t.pipeline,
            status=t.status.value,
            company_slug=t.company_slug,
            product_slug=t.product_slug,
            effective_slug=t.effective_slug,
            current_step=t.current_step,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tasks
    ]
    return TaskListResponse(tasks=summaries, total=len(summaries))


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    task_store: TaskStoreProtocol = Depends(get_task_store),
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TaskResponse:
    task = task_store.get_task(task_id)
    await assert_task_workspace_access(task, user, workspace_service)

    return TaskResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        current_step=task.current_step,
        progress_pct=task.progress_pct,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
        approval_payload=task.approval_payload,
    )


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    _write_slug: str = Depends(get_workspace_write_slug),
) -> CancelResponse:
    task = task_store.get_task(task_id)
    await assert_task_workspace_access(
        task, user, workspace_service, min_roles=("owner", "admin", "member")
    )

    if task.status not in _CANCELLABLE_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel task in {task.status.value} state",
        )

    task_store.cancel_task_handle(task_id)

    task_store.update_task(task_id, status=TaskStatus.CANCELLED)
    await task_store.flush_terminal(task_id)
    effective = task.effective_slug or task.company_slug
    task_store.release_slug_lock(f"{task.pipeline}:{effective}")

    event_bus.publish(task_id, "cancelled", {"reason": "user_cancelled"})

    return CancelResponse(run_id=task_id, status="cancelled")


@router.post("/{task_id}/stream-token")
async def create_stream_token(
    task_id: str,
    request: Request,
    task_store: TaskStoreProtocol = Depends(get_task_store),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> dict:
    """Create a stream token for SSE EventSource clients."""
    task = task_store.get_task(task_id)
    await assert_task_workspace_access(task, user, workspace_service)

    user_id = getattr(request.state, "user_id", None)
    token = auth_service.create_stream_token(user_id, task.company_slug)
    return {"stream_token": token, "expires_in": 3600}
