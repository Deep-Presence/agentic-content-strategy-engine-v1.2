"""Knowledge Base pipeline API endpoints."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_kb_data_service, get_task_store, get_workspace_service
from api.schemas.common import (
    ApprovalRequest,
    ApprovalResponse,
    KBDocHealthResponse,
    KBHealthResponse,
    KBRefreshStaleRequest,
    KnowledgeBaseStartRequest,
    PipelineRunResponse,
    TaskResponse,
)
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import PipelineTask, TaskStatus
from api.routers._helpers import (
    assert_slug_workspace_access,
    assert_task_workspace_access,
    create_task_durable,
    resolve_workspace_scope,
)
from api.tasks.runner import run_kb_pipeline_task
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.knowledge_base import KB_DEPENDENCY_GRAPH, KBDocType
from core.models.organization import UserProfile
from core.research.knowledge_base.storage import KBStorage
from core.audit import log_hitl_decision, log_pipeline_launch
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])

# Checkpoint → doc types mapping for revision note translation (CX-3)
_CHECKPOINT_DOC_TYPES: Dict[str, List[str]] = {
    "kb_checkpoint_1": ["company_overview", "customer_reviews", "competitor_registry"],
    "kb_checkpoint_2": ["weakness_analysis", "brand_perception"],
}


def _derive_slug(company_name: str) -> str:
    return derive_slug(company_name)


def _kb_artifacts_exist(
    artifacts_root: Path,
    effective_slug: str,
    backend: Optional[Any] = None,
) -> bool:
    """Check if a completed KB run exists (manifest with synthesis_version > 0)."""
    storage = KBStorage(artifacts_root, effective_slug, backend=backend)
    manifest = storage.read_manifest()
    return manifest.synthesis_version > 0


def _get_latest_kb_run(
    task_store: TaskStoreProtocol, slug: str, product_slug: Optional[str],
) -> Optional[PipelineTask]:
    """Return the most-recent completed KB task for this exact scope."""
    tasks = [
        t
        for t in task_store.list_tasks(pipeline="knowledge_base", company_slug=slug)
        if t.product_slug == product_slug and t.status.value == "completed"
    ]
    return max(tasks, key=lambda t: t.created_at) if tasks else None


@router.post(
    "/start",
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "KB artifacts already exist"}},
)
async def start_knowledge_base(
    body: KnowledgeBaseStartRequest,
    response: Response,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponse:
    scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    slug = scope.workspace_slug
    effective_slug = scope.effective_slug

    # Guard: skip if already completed and not force_rerun
    _sb = getattr(http_request.app.state, "storage_backend", None)
    if not body.force_rerun and _kb_artifacts_exist(artifacts_root, effective_slug, backend=_sb):
        last_task = _get_latest_kb_run(task_store, slug, body.product_slug)
        response.status_code = 200
        await log_pipeline_launch(
            user_id=_user.id,
            pipeline="knowledge_base",
            company_slug=slug,
            task_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            detail={
                "outcome": "already_exists",
                "product_slug": body.product_slug,
                "mode": body.mode,
                "effective_slug": effective_slug,
            },
        )
        return PipelineRunResponse(
            run_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            pipeline="knowledge_base",
            company_slug=slug,
            workspace_id=scope.workspace_id,
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=last_task.created_at if last_task else datetime.now(timezone.utc),
            already_exists=True,
            message=(
                "Knowledge base artifacts already exist. "
                "Pass force_rerun=true to re-run."
            ),
        )

    task = await create_task_durable(
        task_store,
        "knowledge_base",
        slug,
        product_slug=body.product_slug,
        workspace_id=scope.workspace_id,
    )

    handle = asyncio.create_task(
        run_kb_pipeline_task(
            task_id=task.task_id,
            request=body,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="knowledge_base",
        company_slug=slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "mode": body.mode,
            "force_rerun": body.force_rerun,
            "effective_slug": effective_slug,
        },
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="knowledge_base",
        company_slug=task.company_slug,
        workspace_id=scope.workspace_id,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/{slug}/health")
async def get_knowledge_base_health(
    slug: str,
    request: Request,
    threshold_override: Optional[int] = Query(None, ge=1, le=365),
    _user: UserProfile = Depends(require_auth),
    kb_svc=Depends(get_kb_data_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> KBHealthResponse:
    """Get health report for a knowledge base — staleness, missing docs, score."""
    await assert_slug_workspace_access(slug, _user, workspace_service)

    report_dict = await kb_svc.get_health(slug, threshold_override=threshold_override)
    return KBHealthResponse.model_validate(report_dict)


@router.post(
    "/{slug}/refresh-stale",
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "All docs are fresh"}},
)
async def refresh_stale_knowledge_base(
    slug: str,
    body: KBRefreshStaleRequest,
    response: Response,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponse:
    """Refresh only stale/missing KB docs. Returns 200 if everything is fresh."""
    _workspace, _membership = await assert_slug_workspace_access(
        slug,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    workspace_id = str(_workspace.id)

    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug
    _sb = getattr(http_request.app.state, "storage_backend", None)
    storage = KBStorage(artifacts_root, effective_slug, backend=_sb) if _sb else KBStorage(artifacts_root, effective_slug)
    report = storage.get_staleness_report(
        threshold_override=body.staleness_threshold_override,
    )

    stale_types = report.stale_docs + report.missing_docs
    if not stale_types:
        response.status_code = 200
        return PipelineRunResponse(
            run_id=f"fresh-{effective_slug}",
            pipeline="knowledge_base",
            company_slug=slug,
            workspace_id=workspace_id,
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=datetime.now(timezone.utc),
            already_exists=True,
            message="All documents are fresh",
        )

    # Topological sort stale docs using DAG
    sorted_stale = _topological_sort_stale(stale_types)

    task = await create_task_durable(
        task_store,
        "knowledge_base",
        slug,
        product_slug=body.product_slug,
        workspace_id=workspace_id,
    )

    # Build a KnowledgeBaseStartRequest-compatible body for the runner
    from api.schemas.common import KnowledgeBaseStartRequest as KBStartReq

    start_req = KBStartReq(
        company_name=slug,
        domain=body.domain,
        product_slug=body.product_slug,
        force_rerun=True,
        mode="refresh",
        refresh_docs=sorted_stale,
        auto_approve_checkpoints=body.auto_approve_checkpoints,
    )

    handle = asyncio.create_task(
        run_kb_pipeline_task(
            task_id=task.task_id,
            request=start_req,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="knowledge_base",
        company_slug=task.company_slug,
        workspace_id=workspace_id,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


def _topological_sort_stale(stale_doc_values: List[str]) -> List[str]:
    """Topologically sort stale doc type values using KB_DEPENDENCY_GRAPH."""
    stale_set = set(stale_doc_values)
    sorted_result: List[str] = []
    visited: set[str] = set()

    def _visit(dt_val: str) -> None:
        if dt_val in visited:
            return
        visited.add(dt_val)
        try:
            dt = KBDocType(dt_val)
        except ValueError:
            return
        for dep in KB_DEPENDENCY_GRAPH.get(dt, []):
            if dep.value in stale_set:
                _visit(dep.value)
        sorted_result.append(dt_val)

    for val in stale_doc_values:
        _visit(val)
    return sorted_result


@router.get("/{run_id}/status")
async def get_knowledge_base_status(
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
async def approve_knowledge_base(
    run_id: str,
    body: ApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponse:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    task_company_slug = task.company_slug
    if task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Task {run_id} is not pending approval (current: {task.status.value})",
        )

    stage = (task.approval_payload or {}).get("stage")
    nonce = (task.approval_payload or {}).get("checkpoint_nonce")
    approval_data: Optional[Dict[str, Any]] = None

    # CX-3: Translate singular revision_note → per-doc-type revision_notes dict
    if body.decision == "revise" and body.revision_note and stage in _CHECKPOINT_DOC_TYPES:
        doc_types = _CHECKPOINT_DOC_TYPES[stage]
        approval_data = {
            "decision": body.decision,
            "revision_notes": {dt: body.revision_note for dt in doc_types},
        }

    try:
        task_store.submit_approval(
            run_id,
            decision=body.decision,
            revision_note=body.revision_note,
            stage=stage,
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="knowledge_base",
            stage=stage,
            decision="rejected",
            company_slug=task_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="knowledge_base",
        stage=stage,
        decision=body.decision,
        company_slug=task_company_slug,
        detail={"revision_note_provided": bool(body.revision_note)},
    )

    return ApprovalResponse(
        run_id=run_id,
        decision=body.decision,
        revision_note=body.revision_note,
    )
