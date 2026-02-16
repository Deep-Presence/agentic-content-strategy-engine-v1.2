"""Research pipeline API endpoints."""
from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_event_bus, get_task_store
from api.schemas.common import (
    ApprovalRequest,
    ApprovalResponse,
    PipelineRunResponse,
    ResearchStartRequest,
    TaskResponse,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.runner import run_research_pipeline_task
from api.tasks.store import TaskStore

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _derive_slug(company_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")


@router.post("/start", status_code=202)
async def start_research(
    request: ResearchStartRequest,
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
) -> PipelineRunResponse:
    slug = _derive_slug(request.company_name)
    task = task_store.create_task("research", slug)

    asyncio.create_task(
        run_research_pipeline_task(
            task_id=task.task_id,
            request=request,
            task_store=task_store,
            event_bus=event_bus,
        )
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="research",
        company_slug=task.company_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
def get_research_status(
    run_id: str,
    task_store: TaskStore = Depends(get_task_store),
) -> TaskResponse:
    task = task_store.get_task(run_id)
    return TaskResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        status=task.status.value,
        current_step=task.current_step,
        progress_pct=task.progress_pct,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
        approval_payload=task.approval_payload,
    )


@router.post("/{run_id}/approve")
def approve_research(
    run_id: str,
    request: ApprovalRequest,
    task_store: TaskStore = Depends(get_task_store),
) -> ApprovalResponse:
    task = task_store.get_task(run_id)
    if task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Task {run_id} is not pending approval (current: {task.status.value})",
        )

    task_store.submit_approval(
        run_id,
        decision=request.decision,
        revision_note=request.revision_note,
    )

    return ApprovalResponse(
        run_id=run_id,
        decision=request.decision,
        revision_note=request.revision_note,
    )
