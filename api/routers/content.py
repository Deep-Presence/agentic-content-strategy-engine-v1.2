"""Content generation pipeline API endpoints."""
from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_event_bus, get_task_store
from api.schemas.common import (
    ContentApprovalRequest,
    ContentApprovalResponse,
    ContentStartRequest,
    PipelineRunResponse,
    TaskResponse,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.runner import run_content_pipeline_task
from api.tasks.store import TaskStore
from core.models.content_generation import ContentGenerationInput

router = APIRouter(prefix="/api/v1/content", tags=["content"])


def _derive_slug(company_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")


@router.post("/start", status_code=202)
async def start_content(
    request: ContentStartRequest,
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
) -> PipelineRunResponse:
    try:
        input_data = ContentGenerationInput(**(request.input_data or {}))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input_data: {exc}")

    slug = _derive_slug(input_data.company_name)
    task = task_store.create_task("content", slug)

    asyncio.create_task(
        run_content_pipeline_task(
            task_id=task.task_id,
            input_data=input_data,
            task_store=task_store,
            event_bus=event_bus,
        )
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="content",
        company_slug=task.company_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
def get_content_status(
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
def approve_content(
    run_id: str,
    request: ContentApprovalRequest,
    task_store: TaskStore = Depends(get_task_store),
) -> ContentApprovalResponse:
    task = task_store.get_task(run_id)
    if task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Task {run_id} is not pending approval (current: {task.status.value})",
        )

    task_store.submit_approval(
        run_id,
        decision=request.decision,
        revision_note=request.editor_notes,
    )

    return ContentApprovalResponse(
        run_id=run_id,
        brief_id=request.brief_id,
        decision=request.decision,
        editor_notes=request.editor_notes,
    )
