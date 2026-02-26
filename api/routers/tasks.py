"""Task management API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_event_bus, get_task_store
from api.schemas.common import CancelResponse, TaskListResponse, TaskResponse, TaskSummary
from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

_CANCELLABLE_STATES = {TaskStatus.RUNNING, TaskStatus.PENDING_APPROVAL}


@router.get("")
def list_tasks(
    pipeline: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    company_slug: Optional[str] = Query(None),
    product_slug: Optional[str] = Query(None),
    task_store: TaskStore = Depends(get_task_store),
) -> TaskListResponse:
    tasks = task_store.list_tasks(
        pipeline=pipeline,
        status=status,
        company_slug=company_slug,
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
def get_task(
    task_id: str,
    task_store: TaskStore = Depends(get_task_store),
) -> TaskResponse:
    task = task_store.get_task(task_id)
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
def cancel_task(
    task_id: str,
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
) -> CancelResponse:
    task = task_store.get_task(task_id)
    if task.status not in _CANCELLABLE_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel task in {task.status.value} state",
        )

    # Cancel the background asyncio.Task if running
    task_store.cancel_task_handle(task_id)

    task_store.update_task(task_id, status=TaskStatus.CANCELLED)
    # Use effective_slug (may be company__product) for correct lock release
    effective = task.effective_slug or task.company_slug
    task_store.release_slug_lock(effective)

    # Publish SSE cancelled event so frontend receives it
    event_bus.publish(task_id, "cancelled", {"reason": "user_cancelled"})

    return CancelResponse(run_id=task_id, status="cancelled")
