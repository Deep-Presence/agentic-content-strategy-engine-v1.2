"""Content generation pipeline API endpoints."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_auth_service, get_event_bus, get_task_store
from core.auth.service import AuthServiceProtocol
from api.schemas.common import (
    ContentApprovalRequest,
    ContentApprovalResponse,
    ContentStartRequest,
    PipelineRunResponse,
    TaskResponse,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.runner import _derive_slug, _resolve_scope_async, run_content_pipeline_task
from api.tasks.store import TaskStore
from core.models.content_generation import ContentGenerationInput
from core.models.organization import UserProfile

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("/start", status_code=202)
async def start_content(
    body: ContentStartRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    # Tenant isolation: slug must match authenticated user's company
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    company_slug = _derive_slug(body.company_name)
    if not user_company_slug or company_slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    product_slug = body.product_slug
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Auto-compute gap_slug from effective_slug when product_slug set but gap_slug not
    gap_slug = body.gap_slug or scope.effective_slug

    input_data = ContentGenerationInput(
        company_name=body.company_name,
        domain=body.domain,
        max_briefs=body.max_briefs,
        auto_approve=body.auto_approve,
        max_concurrent_workers=body.max_concurrent_workers,
        max_revision_cycles=body.max_revision_cycles,
        skip_stages=body.skip_stages,
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
    request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStore = Depends(get_task_store),
) -> TaskResponse:
    task = task_store.get_task(run_id)
    # Task ownership check
    user_company_slug = getattr(request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
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
    body: ContentApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStore = Depends(get_task_store),
) -> ContentApprovalResponse:
    task = task_store.get_task(run_id)
    # Task ownership check
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    if task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Task {run_id} is not pending approval (current: {task.status.value})",
        )

    # Validate brief_id matches current approval payload
    payload_brief = (task.approval_payload or {}).get("brief_id")
    if payload_brief and body.brief_id != payload_brief:
        raise HTTPException(
            status_code=409,
            detail=f"brief_id mismatch: expected {payload_brief}, got {body.brief_id}",
        )

    stage = (task.approval_payload or {}).get("stage", "content_review")
    if body.brief_id:
        stage = f"{stage}:{body.brief_id}"
    task_store.submit_approval(
        run_id,
        decision=body.decision,
        revision_note=body.editor_notes,
        stage=stage,
    )

    return ContentApprovalResponse(
        run_id=run_id,
        brief_id=body.brief_id,
        decision=body.decision,
        editor_notes=body.editor_notes,
    )
