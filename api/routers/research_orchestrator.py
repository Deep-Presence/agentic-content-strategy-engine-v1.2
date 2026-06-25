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
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_model_config_service, get_task_store, get_workspace_service
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.research_orchestrator import ResearchOrchestratorStartRequest
from api.tasks.event_bus import EventBusProtocol
from api.routers._helpers import (
    assert_task_workspace_access,
    authoritative_company_fields,
    create_task_durable,
    resolve_workspace_scope,
)
from api.routers._model_config_preflight import preflight_model_config_or_409
from api.tasks.runner import run_research_orchestrator_task
from core.audit import log_pipeline_launch
from core.auth.utils.domain import derive_slug
from core.model_config.agent_catalog import required_agents_for_pipeline
from core.model_config.service import ModelConfigService
from core.services.task_store import TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research-orchestrator"])

_RESEARCH_PIPELINE_AGENT_KEYS = {
    "kb": [
        definition.agent_key
        for definition in required_agents_for_pipeline("research_kb")
    ],
    "ap": [
        definition.agent_key
        for definition in required_agents_for_pipeline("research_ap")
    ],
    "vsg": [
        definition.agent_key
        for definition in required_agents_for_pipeline("research_vsg")
    ],
}


def _derive_slug(company_name: str) -> str:
    return derive_slug(company_name) or company_name.lower()


def _agent_keys_for_research_pipelines(pipelines: list[str]) -> list[str]:
    keys: list[str] = []
    for pipeline in pipelines:
        keys.extend(_RESEARCH_PIPELINE_AGENT_KEYS[pipeline])
    return list(dict.fromkeys(keys))


@router.post("/start", status_code=202)
async def start_research_orchestrator(
    body: ResearchOrchestratorStartRequest,
    response: Response,
    http_request: Request,
    _user=Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service=Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> PipelineRunResponse:
    """Launch the Research Orchestrator (KB → AP → VSG).

    Returns a task_id (run_id) for SSE streaming and HITL approval.
    """
    scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    if body.workspace_slug.strip():
        body = body.model_copy(
            update=authoritative_company_fields(
                scope,
                company_name=body.company_name,
                domain=body.domain,
            )
        )
    slug = scope.workspace_slug
    effective_slug = scope.effective_slug

    await preflight_model_config_or_409(
        model_config_service,
        scope.workspace_id,
        _agent_keys_for_research_pipelines(body.pipelines),
        message="Configure an active OpenRouter key before launching Research Orchestrator.",
    )

    task = await create_task_durable(
        task_store,
        "research_orchestrator",
        slug,
        product_slug=body.product_slug,
        workspace_id=scope.workspace_id,
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
        workspace_id=scope.workspace_id,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{run_id}/status")
async def get_research_orchestrator_status(
    run_id: str,
    request: Request,
    _user=Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TaskResponse:
    """Get the status of a research orchestrator run."""
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
