"""Gap analysis pipeline API endpoints."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, Depends

from api.dependencies import get_artifacts_root, get_event_bus, get_task_store
from api.schemas.common import GapAnalysisStartRequest, PipelineRunResponse, TaskResponse
from api.tasks.event_bus import EventBus
from api.tasks.runner import run_gap_pipeline_task
from api.tasks.store import TaskStore

router = APIRouter(prefix="/api/v1/gap-analysis", tags=["gap-analysis"])


def _derive_slug(company_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")


@router.post("/start", response_model=PipelineRunResponse, status_code=202)
async def start_gap_analysis(
    body: GapAnalysisStartRequest,
    task_store: TaskStore = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> PipelineRunResponse:
    slug = _derive_slug(body.company_name)
    task = task_store.create_task("gap_analysis", slug)

    handle = asyncio.create_task(
        run_gap_pipeline_task(
            task_id=task.task_id,
            request=body,
            artifacts_root=artifacts_root,
            task_store=task_store,
            event_bus=event_bus,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status", response_model=TaskResponse)
async def get_gap_analysis_status(
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
