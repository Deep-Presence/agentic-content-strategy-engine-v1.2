"""Knowledge Base pipeline API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_kb_data_service, get_task_store
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
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.runner import run_kb_pipeline_task
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.knowledge_base import KB_DEPENDENCY_GRAPH, KBDocType
from core.models.organization import UserProfile
from core.research.knowledge_base.storage import KBStorage
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["knowledge-base"])

# Checkpoint → doc types mapping for revision note translation (CX-3)
_CHECKPOINT_DOC_TYPES: Dict[str, List[str]] = {
    "kb_checkpoint_1": ["company_overview", "customer_reviews", "competitor_registry"],
    "kb_checkpoint_2": ["weakness_analysis", "brand_perception"],
}


def _derive_slug(company_name: str) -> str:
    return derive_slug(company_name)


def _kb_artifacts_exist(artifacts_root: Path, effective_slug: str) -> bool:
    """Check if a completed KB run exists (manifest with synthesis_version > 0)."""
    manifest_path = artifacts_root / "knowledge_base" / effective_slug / "_manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text())
        return manifest.get("synthesis_version", 0) > 0
    except (json.JSONDecodeError, OSError):
        return False


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
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    # Tenant isolation
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    slug = _derive_slug(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    # Guard: skip if already completed and not force_rerun
    if not body.force_rerun and _kb_artifacts_exist(artifacts_root, effective_slug):
        last_task = _get_latest_kb_run(task_store, slug, body.product_slug)
        response.status_code = 200
        return PipelineRunResponse(
            run_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            pipeline="knowledge_base",
            company_slug=slug,
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

    task = task_store.create_task("knowledge_base", slug, product_slug=body.product_slug)

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

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="knowledge_base",
        company_slug=task.company_slug,
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
) -> KBHealthResponse:
    """Get health report for a knowledge base — staleness, missing docs, score."""
    user_company_slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

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
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    """Refresh only stale/missing KB docs. Returns 200 if everything is fresh."""
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug
    storage = KBStorage(artifacts_root, effective_slug)
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
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=datetime.now(timezone.utc),
            already_exists=True,
            message="All documents are fresh",
        )

    # Topological sort stale docs using DAG
    sorted_stale = _topological_sort_stale(stale_types)

    task = task_store.create_task("knowledge_base", slug, product_slug=body.product_slug)

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
def get_knowledge_base_status(
    run_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> TaskResponse:
    task = task_store.get_task(run_id)
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
def approve_knowledge_base(
    run_id: str,
    body: ApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponse:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
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
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ApprovalResponse(
        run_id=run_id,
        decision=body.decision,
        revision_note=body.revision_note,
    )
