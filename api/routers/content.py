"""Content generation pipeline API endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from api.auth.store import AuthStore
from api.dependencies import get_auth_store, get_event_bus, get_task_store
from api.schemas.common import (
    ContentApprovalRequest,
    ContentApprovalResponse,
    ContentStartRequest,
    PipelineRunResponse,
    TaskResponse,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.runner import _derive_slug, _resolve_scope, run_content_pipeline_task
from api.tasks.store import TaskStore
from core.models.content_generation import ContentGenerationInput

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("/start", status_code=202)
async def start_content(
    request: ContentStartRequest,
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    auth_store: AuthStore = Depends(get_auth_store),
) -> PipelineRunResponse:
    company_slug = _derive_slug(request.company_name)
    product_slug = request.product_slug
    scope = _resolve_scope(company_slug, product_slug, auth_store)

    # Auto-compute gap_slug from effective_slug when product_slug set but gap_slug not
    gap_slug = request.gap_slug or scope.effective_slug

    input_data = ContentGenerationInput(
        company_name=request.company_name,
        domain=request.domain,
        max_briefs=request.max_briefs,
        auto_approve=request.auto_approve,
        max_concurrent_workers=request.max_concurrent_workers,
        max_revision_cycles=request.max_revision_cycles,
        skip_stages=request.skip_stages,
        company_slug=scope.effective_slug,  # scopes artifact output dir correctly
        product_slug=scope.product_slug,
        product_name=scope.product_name,
        product_description=scope.product_description,
    )
    task = task_store.create_task("content", company_slug, product_slug=product_slug)

    handle = asyncio.create_task(
        run_content_pipeline_task(
            task_id=task.task_id,
            input_data=input_data,
            task_store=task_store,
            event_bus=event_bus,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="content",
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
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

    # Validate brief_id matches current approval payload
    payload_brief = (task.approval_payload or {}).get("brief_id")
    if payload_brief and request.brief_id != payload_brief:
        raise HTTPException(
            status_code=409,
            detail=f"brief_id mismatch: expected {payload_brief}, got {request.brief_id}",
        )

    stage = (task.approval_payload or {}).get("stage", "content_review")
    if request.brief_id:
        stage = f"{stage}:{request.brief_id}"
    task_store.submit_approval(
        run_id,
        decision=request.decision,
        revision_note=request.editor_notes,
        stage=stage,
    )

    return ContentApprovalResponse(
        run_id=run_id,
        brief_id=request.brief_id,
        decision=request.decision,
        editor_notes=request.editor_notes,
    )
