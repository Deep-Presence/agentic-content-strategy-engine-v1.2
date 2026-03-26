"""Gap analysis pipeline API endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_storage_backend as get_storage_dep, get_task_store
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from api.schemas.common import GapAnalysisStartRequest, PipelineRunResponse, TaskResponse
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask
from api.routers._helpers import create_task_durable
from api.tasks.runner import run_gap_pipeline_task
from core.services.task_store import TaskStoreProtocol
from core.storage.backends.base import StorageBackend
from core.audit import log_pipeline_launch
from core.models.organization import UserProfile

router = APIRouter(prefix="/api/v1/gap-analysis", tags=["gap-analysis"])


def _derive_slug(company_name: str) -> str:
    return derive_slug(company_name)


def _gap_analysis_artifacts_exist(storage: "StorageBackend", effective_slug: str) -> bool:
    """True if s8 or s6 output exists for this slug (dual-sentinel, mirrors gap_data_service)."""
    return (
        storage.exists(f"gap_analysis/{effective_slug}/gap_analysis_complete.json")
        or storage.exists(f"gap_analysis/{effective_slug}/analysis.json")
    )


def _get_latest_gap_run(
    task_store: TaskStoreProtocol, slug: str, product_slug: Optional[str]
) -> Optional[PipelineTask]:
    """Return the most-recent completed gap_analysis task for this exact scope."""
    tasks = [
        t
        for t in task_store.list_tasks(pipeline="gap_analysis", company_slug=slug)
        if t.product_slug == product_slug and t.status.value == "completed"
    ]
    return max(tasks, key=lambda t: t.created_at) if tasks else None


@router.post(
    "/start",
    response_model=PipelineRunResponse,
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "Artifacts already exist"}},
)
async def start_gap_analysis(
    body: GapAnalysisStartRequest,
    response: Response,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    storage_backend: StorageBackend = Depends(get_storage_dep),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    # Tenant isolation: slug must match authenticated user's company
    user_company_slug: Optional[str] = getattr(request.state, "company_slug", None)
    slug = _derive_slug(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    if not body.force_rerun and _gap_analysis_artifacts_exist(storage_backend, effective_slug):
        last_task = _get_latest_gap_run(task_store, slug, body.product_slug)
        response.status_code = 200
        await log_pipeline_launch(
            user_id=_user.id,
            pipeline="gap_analysis",
            company_slug=slug,
            task_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            detail={
                "outcome": "already_exists",
                "product_slug": body.product_slug,
                "effective_slug": effective_slug,
            },
        )
        return PipelineRunResponse(
            run_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            pipeline="gap_analysis",
            company_slug=slug,
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=last_task.created_at if last_task else datetime.now(timezone.utc),
            already_exists=True,
            message="Artifacts already exist. Pass force_rerun=true to re-run.",
        )

    task = await create_task_durable(task_store, "gap_analysis", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_gap_pipeline_task(
            task_id=task.task_id,
            request=body,
            artifacts_root=artifacts_root,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="gap_analysis",
        company_slug=slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "force_rerun": body.force_rerun,
            "effective_slug": effective_slug,
        },
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status", response_model=TaskResponse)
async def get_gap_analysis_status(
    run_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
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
