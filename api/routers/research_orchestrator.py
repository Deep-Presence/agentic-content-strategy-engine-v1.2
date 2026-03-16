"""Research Orchestrator API endpoints — KB → AP → VSG DAG.

Provides a single endpoint to launch all three research pipelines in order.
HITL approvals are handled through existing per-pipeline endpoints:
  - KB: POST /api/v1/knowledge-base/{run_id}/approve
  - AP briefs: POST /api/v1/audience-persona/{run_id}/approve/briefs
  - AP profiles: POST /api/v1/audience-persona/{run_id}/approve/profiles
  - VSG authors: POST /api/v1/voice-style-guide/{run_id}/approve/authors

All using the same run_id returned by POST /start.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_task_store
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.research_orchestrator import ResearchOrchestratorStartRequest
from api.tasks.event_bus import EventBus
from api.tasks.runner import run_research_orchestrator_task
from core.audit import log_pipeline_launch
from core.auth.utils.domain import derive_slug
from core.services.task_store import TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research-orchestrator"])


def _derive_slug(company_name: str) -> str:
    return derive_slug(company_name) or company_name.lower()


@router.post("/start", status_code=202)
async def start_research_orchestrator(
    body: ResearchOrchestratorStartRequest,
    response: Response,
    http_request: Request,
    _user=Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service=Depends(get_auth_service),
) -> PipelineRunResponse:
    """Launch the Research Orchestrator (KB → AP → VSG).

    Returns a task_id (run_id) for SSE streaming and HITL approval.
    """
    # Tenant isolation
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    slug = _derive_slug(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    task = task_store.create_task(
        "research_orchestrator", slug, product_slug=body.product_slug,
    )

    handle = asyncio.create_task(
        run_research_orchestrator_task(
            task_id=task.task_id,
            request=body,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
            artifacts_root=artifacts_root,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="research_orchestrator",
        company_slug=slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "effective_slug": effective_slug,
        },
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="research_orchestrator",
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
def get_research_orchestrator_status(
    run_id: str,
    request: Request,
    _user=Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> TaskResponse:
    """Get the status of a research orchestrator run."""
    task = task_store.get_task(run_id)

    # Tenant isolation — prevent cross-tenant status reads
    user_company_slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not user_company_slug or task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

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
