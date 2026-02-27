"""Gap analysis pipeline API endpoints."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.auth.store import AuthStore
from api.dependencies import get_artifacts_root, get_auth_store, get_event_bus, get_task_store
from api.schemas.common import GapAnalysisStartRequest, PipelineRunResponse, TaskResponse
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask
from api.tasks.runner import run_gap_pipeline_task
from api.tasks.store import TaskStore
from core.models.organization import UserProfile

router = APIRouter(prefix="/api/v1/gap-analysis", tags=["gap-analysis"])


def _derive_slug(company_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")


def _gap_analysis_artifacts_exist(artifacts_root: Path, effective_slug: str) -> bool:
    """True if s8 or s6 output exists for this slug (dual-sentinel, mirrors gap_data_service)."""
    d = artifacts_root / "gap_analysis" / effective_slug
    return (d / "gap_analysis_complete.json").exists() or (d / "analysis.json").exists()


def _get_latest_gap_run(
    task_store: TaskStore, slug: str, product_slug: Optional[str]
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
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_store: AuthStore = Depends(get_auth_store),
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

    if not body.force_rerun and _gap_analysis_artifacts_exist(artifacts_root, effective_slug):
        last_task = _get_latest_gap_run(task_store, slug, body.product_slug)
        response.status_code = 200
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

    task = task_store.create_task("gap_analysis", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_gap_pipeline_task(
            task_id=task.task_id,
            request=body,
            artifacts_root=artifacts_root,
            task_store=task_store,
            event_bus=event_bus,
            auth_store=auth_store,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

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
