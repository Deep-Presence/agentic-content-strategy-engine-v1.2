"""Content generation pipeline API endpoints."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import require_auth
from api.dependencies import get_auth_service, get_event_bus, get_task_store, get_workspace_service
from core.auth.service import AuthServiceProtocol
from api.schemas.common import (
    ContentApprovalRequest,
    ContentApprovalResponse,
    ContentStartRequest,
    PipelineRunResponse,
    TaskResponse,
)
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import TaskStatus
from api.routers._helpers import assert_task_workspace_access, create_task_durable, resolve_workspace_scope
from api.tasks.runner import _resolve_scope_async, run_content_pipeline_task
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol
from core.models.content_generation import ContentGenerationInput
from core.models.organization import UserProfile
from core.services.workspace_protocol import WorkspaceServiceProtocol

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("/start", status_code=202)
async def start_content(
    body: ContentStartRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponse:
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    company_slug = workspace_scope.workspace_slug
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
    task = await create_task_durable(
        task_store,
        "content",
        company_slug,
        product_slug=product_slug,
        workspace_id=workspace_scope.workspace_id,
    )

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
        workspace_id=task.workspace_id,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
async def get_content_status(
    run_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TaskResponse:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(task, _user, workspace_service)
    return TaskResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        workspace_id=task.workspace_id,
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
async def approve_content(
    run_id: str,
    body: ContentApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ContentApprovalResponse:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
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
    try:
        task_store.submit_approval(
            run_id,
            decision=body.decision,
            revision_note=body.editor_notes,
            stage=stage,
        )
    except ApprovalWindowError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # ApprovalDeliveryError is handled by global exception handler → 503

    return ContentApprovalResponse(
        run_id=run_id,
        brief_id=body.brief_id,
        decision=body.decision,
        editor_notes=body.editor_notes,
    )
