"""Onboarding Pipeline Orchestrator API endpoints.

POST /start — superuser only, tenant-isolated, launches 3-phase onboarding.
GET /{run_id}/status — tenant-isolated status check.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_task_store, get_workspace_service
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.onboarding import OnboardingStartRequest
from api.tasks.event_bus import EventBusProtocol
from api.routers._helpers import (
    assert_task_workspace_access,
    create_task_durable,
    resolve_workspace_scope,
)
from api.tasks.runner import run_onboarding_task
from core.audit import log_pipeline_launch
from core.services.task_store import TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post("/start", status_code=202)
async def start_onboarding(
    body: OnboardingStartRequest,
    response: Response,
    http_request: Request,
    _user=Depends(require_role("superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service=Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponse:
    """Launch the onboarding pipeline orchestrator.

    Requires superuser role. company_name/domain resolved from workspace scope.
    """
    scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        min_roles=("owner", "admin", "member"),
    )
    company_slug = scope.workspace_slug

    # Look up company details from auth_service
    company = await auth_service.get_company_by_slug(company_slug)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company_name = company.name
    company_domain = company.domain

    # Persist industry if provided
    if body.industry:
        try:
            await auth_service.update_company(company_slug, industry=body.industry)
        except Exception:
            logger.warning("Failed to persist industry for %s", company_slug)

    task = await create_task_durable(
        task_store,
        "onboarding",
        company_slug,
        workspace_id=scope.workspace_id,
    )

    handle = asyncio.create_task(
        run_onboarding_task(
            task_id=task.task_id,
            request=body,
            company_name=company_name,
            company_domain=company_domain or "",
            company_slug=company_slug,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
            artifacts_root=artifacts_root,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="onboarding",
        company_slug=company_slug,
        task_id=task.task_id,
        detail={
            "company_name": company_name,
        },
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="onboarding",
        company_slug=task.company_slug,
        workspace_id=scope.workspace_id,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
async def get_onboarding_status(
    run_id: str,
    request: Request,
    _user=Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TaskResponse:
    """Get the status of an onboarding run."""
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(task, _user, workspace_service)

    return TaskResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        current_step=task.current_step,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
    )
