"""Research pipeline API endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_task_store
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from api.schemas.common import (
    ApprovalRequest,
    ApprovalResponse,
    PipelineRunResponse,
    ResearchStartRequest,
    TaskResponse,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.runner import run_research_pipeline_task
from core.services.task_store import TaskStoreProtocol
from core.models.organization import UserProfile

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _derive_slug(company_name: str) -> str:
    return derive_slug(company_name)


# Stage → artifact existence check. Draft personas (.draft.md) are excluded.
_STAGE_CHECKS = {
    "company": lambda root, slug: (root / "company_context" / f"{slug}.md").exists(),
    "persona": lambda root, slug: any(
        f
        for f in (root / "personas").glob(f"{slug}__persona-*.md")
        if not f.name.endswith(".draft.md")
    ),
    "style_guide": lambda root, slug: (root / "style_guides" / f"{slug}.md").exists(),
}


def _research_stages_exist(
    artifacts_root: Path,
    effective_slug: str,
    company_slug: str,
    stages: List[str],
) -> bool:
    """True only if ALL requested stages have approved artifacts.

    Checks effective_slug first (product-level), then falls back to company_slug.
    """
    slugs = [s for s in [effective_slug, company_slug] if s]
    return all(
        any(_STAGE_CHECKS[stage](artifacts_root, lookup) for lookup in slugs)
        for stage in stages
    )


def _get_latest_research_run(
    task_store: TaskStoreProtocol, slug: str, product_slug: Optional[str]
) -> Optional[PipelineTask]:
    """Return the most-recent completed research task for this exact scope."""
    tasks = [
        t
        for t in task_store.list_tasks(pipeline="research", company_slug=slug)
        if t.product_slug == product_slug and t.status.value == "completed"
    ]
    return max(tasks, key=lambda t: t.created_at) if tasks else None


@router.post(
    "/start",
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "All requested stages already exist"}},
)
async def start_research(
    body: ResearchStartRequest,
    response: Response,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    # Tenant isolation: slug must match authenticated user's company
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    slug = _derive_slug(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug
    requested_stages = list(body.stages) if body.stages else ["company", "persona", "style_guide"]

    if not body.force_rerun and _research_stages_exist(
        artifacts_root, effective_slug, slug, requested_stages
    ):
        last_task = _get_latest_research_run(task_store, slug, body.product_slug)
        response.status_code = 200
        return PipelineRunResponse(
            run_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            pipeline="research",
            company_slug=slug,
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=last_task.created_at if last_task else datetime.now(timezone.utc),
            already_exists=True,
            message=(
                f"Stages {requested_stages} already have approved artifacts. "
                "Pass force_rerun=true to re-run."
            ),
        )

    task = task_store.create_task("research", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_research_pipeline_task(
            task_id=task.task_id,
            request=body,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="research",
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
def get_research_status(
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


@router.post("/{run_id}/approve")
def approve_research(
    run_id: str,
    body: ApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponse:
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

    stage = (task.approval_payload or {}).get("stage")
    task_store.submit_approval(
        run_id,
        decision=body.decision,
        revision_note=body.revision_note,
        stage=stage,
    )

    return ApprovalResponse(
        run_id=run_id,
        decision=body.decision,
        revision_note=body.revision_note,
    )
