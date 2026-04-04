"""Topic Discovery pipeline API endpoints."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_task_store, get_td_data_service
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.topic_discovery import (
    ApprovalResponseTD,
    AssignmentListResponse,
    AssignmentStatusUpdateRequest,
    AssignmentStatusUpdateResponse,
    CreateCustomAssignmentRequest,
    DiscoverySummaryResponse,
    ExpansionStatusResponse,
    MatrixApprovalRequest,
    MatrixReadResponse,
    PersonaAffinityResponse,
    ScoredSubdomainsResponse,
    SubdomainSelectionRequest,
    TaxonomyApprovalRequest,
    TaxonomyReadResponse,
    TopicDiscoveryStartRequest,
    TopicExpansionStartRequest,
)
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import PipelineTask, TaskStatus
from api.routers._helpers import create_task_durable
from api.tasks.runner import run_topic_discovery_pipeline_task, run_topic_expansion_pipeline_task
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.organization import UserProfile
from core.audit import log_hitl_decision, log_pipeline_launch
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol
from core.topic_discovery.storage import TopicDiscoveryStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/topic-discovery", tags=["topic-discovery"])


# ── Helpers ───────────────────────────────────────────────────────────


def _derive_slug_local(company_name: str) -> str:
    return derive_slug(company_name)


def _validate_approval_window(
    task: PipelineTask,
    expected_stage: str,
) -> None:
    """Validate that a task is in the correct HITL window for approval."""
    if task.status != TaskStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Task is not awaiting approval (current status: {task.status.value})",
        )

    payload = task.approval_payload or {}
    current_stage = payload.get("stage", "")
    if current_stage != expected_stage:
        raise HTTPException(
            status_code=409,
            detail=f"Wrong approval stage (current: {current_stage}, expected: {expected_stage})",
        )


def _td_should_guard(
    artifacts_root: Path,
    effective_slug: str,
    *,
    backend: Optional[Any] = None,
) -> tuple[bool, Optional[str]]:
    """Check whether the TD guard should block a new run.

    Guard blocks when an approved taxonomy + matrix already exist.
    """
    kw = {"backend": backend} if backend else {}
    storage = TopicDiscoveryStorage(artifacts_root, effective_slug, **kw)
    manifest = storage.read_manifest()

    if manifest.taxonomy_version > 0:
        from core.models.topic_discovery import TopicDiscoveryStatus

        if manifest.status in (TopicDiscoveryStatus.discovery_complete, TopicDiscoveryStatus.approved):
            return True, (
                f"Topic discovery already complete (taxonomy v{manifest.taxonomy_version}, "
                f"status={manifest.status.value}). Pass force_rerun=true to re-run."
            )
    return False, None


# ── Endpoint 1: POST /start ──────────────────────────────────────────


@router.post(
    "/start",
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "Already exists"}},
)
async def start_topic_discovery(
    body: TopicDiscoveryStartRequest,
    response: Response,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    # Tenant isolation
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    slug = _derive_slug_local(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug
    _sb = getattr(http_request.app.state, "storage_backend", None)

    # Guard: check if discovery already exists
    if not body.force_rerun:
        should_guard, message = _td_should_guard(artifacts_root, effective_slug, backend=_sb)
        if should_guard:
            response.status_code = 200
            await log_pipeline_launch(
                user_id=_user.id,
                pipeline="topic_discovery",
                company_slug=slug,
                task_id=f"existing-{effective_slug}",
                detail={
                    "outcome": "already_exists",
                    "product_slug": body.product_slug,
                    "effective_slug": effective_slug,
                },
            )
            return PipelineRunResponse(
                run_id=f"existing-{effective_slug}",
                pipeline="topic_discovery",
                company_slug=slug,
                product_slug=body.product_slug,
                effective_slug=effective_slug,
                status="already_exists",
                created_at=datetime.now(timezone.utc),
                already_exists=True,
                message=message or "",
            )

    task = await create_task_durable(task_store, "topic_discovery", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_topic_discovery_pipeline_task(
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
        pipeline="topic_discovery",
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
        pipeline="topic_discovery",
        company_slug=slug,
        product_slug=body.product_slug,
        effective_slug=effective_slug,
        status="started",
        created_at=task.created_at,
    )


# ── Endpoint 2: GET /{run_id}/status ─────────────────────────────────


@router.get("/{run_id}/status")
async def get_topic_discovery_status(
    run_id: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> TaskResponse:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return TaskResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        current_step=task.current_step,
        progress_pct=task.progress_pct,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at,
        approval_payload=task.approval_payload,
    )


# ── Endpoint 3: POST /{run_id}/approve/taxonomy ──────────────────────


@router.post("/{run_id}/approve/taxonomy")
async def approve_taxonomy(
    run_id: str,
    body: TaxonomyApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseTD:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_approval_window(task, "td_taxonomy_review")

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")
    if not nonce:
        raise HTTPException(
            status_code=409, detail="No active approval checkpoint"
        )

    approval_data = {
        "batch_decision": body.batch_decision,
        "user_edits": [e.model_dump(mode="json") for e in body.user_edits],
        "user_feedback": body.user_feedback or "",
    }

    try:
        task_store.submit_approval(
            run_id,
            decision=body.batch_decision,
            stage="td_taxonomy_review",
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="topic_discovery",
            stage="td_taxonomy_review",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="topic_discovery",
        stage="td_taxonomy_review",
        decision=body.batch_decision,
        company_slug=user_company_slug,
        detail={"edit_count": len(body.user_edits), "has_feedback": bool(body.user_feedback)},
    )

    return ApprovalResponseTD(
        status="accepted",
        stage="td_taxonomy_review",
        message=f"Taxonomy review submitted: {body.batch_decision}",
    )


# ── Endpoint 3b: POST /{run_id}/approve/subdomains ────────────────


@router.post("/{run_id}/approve/subdomains")
async def approve_subdomains(
    run_id: str,
    body: SubdomainSelectionRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseTD:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_approval_window(task, "td_subdomain_selection")

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")
    if not nonce:
        raise HTTPException(
            status_code=409, detail="No active approval checkpoint"
        )

    approval_data = {
        "batch_decision": body.batch_decision,
        "selected_subdomain_ids": body.selected_subdomain_ids,
        "top_n": body.top_n,
        "persona_filter": body.persona_filter,
    }

    try:
        task_store.submit_approval(
            run_id,
            decision=body.batch_decision,
            stage="td_subdomain_selection",
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="topic_discovery",
            stage="td_subdomain_selection",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="topic_discovery",
        stage="td_subdomain_selection",
        decision=body.batch_decision,
        company_slug=user_company_slug,
        detail={"selected_count": len(body.selected_subdomain_ids or []), "top_n": body.top_n},
    )

    return ApprovalResponseTD(
        status="accepted",
        stage="td_subdomain_selection",
        message=f"Subdomain selection submitted: {body.batch_decision}",
    )


# ── Endpoint 4: POST /{run_id}/approve/matrix ────────────────────────


@router.post("/{run_id}/approve/matrix")
async def approve_matrix(
    run_id: str,
    body: MatrixApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseTD:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_approval_window(task, "td_matrix_review")

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")
    if not nonce:
        raise HTTPException(
            status_code=409, detail="No active approval checkpoint"
        )

    approval_data = {
        "batch_decision": body.batch_decision,
        "user_edits": [e.model_dump(mode="json") for e in body.user_edits],
    }

    try:
        task_store.submit_approval(
            run_id,
            decision=body.batch_decision,
            stage="td_matrix_review",
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="topic_discovery",
            stage="td_matrix_review",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="topic_discovery",
        stage="td_matrix_review",
        decision=body.batch_decision,
        company_slug=user_company_slug,
        detail={"has_feedback": bool(getattr(body, "user_feedback", None))},
    )

    return ApprovalResponseTD(
        status="accepted",
        stage="td_matrix_review",
        message=f"Matrix review submitted: {body.batch_decision}",
    )


# ── Endpoint 5: GET /{slug}/taxonomy ─────────────────────────────────


@router.get("/{slug}/taxonomy")
async def get_latest_taxonomy(
    slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    td_svc=Depends(get_td_data_service),
) -> TaxonomyReadResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    taxonomy = await td_svc.get_taxonomy(slug)
    if taxonomy is None:
        raise HTTPException(status_code=404, detail="No taxonomy found")

    return TaxonomyReadResponse(
        slug=slug,
        taxonomy=taxonomy,
        version=taxonomy.get("version", 0),
        total_subdomains=taxonomy.get("total_subdomains", 0),
        coverage_score=taxonomy.get("coverage_score", 0.0),
    )


# ── Endpoint 6: GET /{slug}/matrix ───────────────────────────────────


@router.get("/{slug}/matrix")
async def get_latest_matrix(
    slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    td_svc=Depends(get_td_data_service),
) -> MatrixReadResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    matrix = await td_svc.get_matrix(slug)
    if matrix is None:
        raise HTTPException(status_code=404, detail="No matrix found")

    return MatrixReadResponse(
        slug=slug,
        matrix=matrix,
        version=matrix.get("version", 0),
        total_assignments=matrix.get("total_assignments", 0),
    )


# ── Endpoint 7: GET /{slug}/scored-subdomains ─────────────────────


@router.get("/{slug}/scored-subdomains")
async def get_scored_subdomains(
    slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    td_svc=Depends(get_td_data_service),
) -> ScoredSubdomainsResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    scored = await td_svc.get_scored_subdomains(slug)
    if scored is None:
        raise HTTPException(status_code=404, detail="No scored subdomains found")

    return ScoredSubdomainsResponse(
        slug=slug,
        scored_subdomains=scored,
        version=scored.get("version", 0),
        total_scored=scored.get("total_scored", 0),
        signals_used=scored.get("signals_used", []),
    )


# ── Endpoint 8: GET /{slug}/personas ──────────────────────────────


@router.get("/{slug}/personas")
async def get_persona_affinity(
    slug: str,
    http_request: Request,
    persona_id: Optional[str] = None,
    _user: UserProfile = Depends(require_auth),
    td_svc=Depends(get_td_data_service),
) -> PersonaAffinityResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    affinity = await td_svc.get_persona_affinity(slug, persona_id=persona_id)
    if affinity is None:
        raise HTTPException(status_code=404, detail="No persona affinity data found")

    return PersonaAffinityResponse(
        slug=slug,
        persona_entries=affinity.get("persona_entries", {}),
        total_personas=affinity.get("total_personas", 0),
        total_subdomains=affinity.get("total_subdomains", 0),
    )


# ── Endpoint 9: POST /expand ────────────────────────────────────────


@router.post(
    "/expand",
    status_code=202,
)
async def start_topic_expansion(
    body: TopicExpansionStartRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    # Tenant isolation
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    slug = _derive_slug_local(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    # Pre-check: discovery must have completed
    _sb = getattr(http_request.app.state, "storage_backend", None)
    kw = {"backend": _sb} if _sb else {}
    storage = TopicDiscoveryStorage(artifacts_root, effective_slug, **kw)
    manifest = storage.read_manifest()
    if manifest.taxonomy_version == 0:
        raise HTTPException(
            status_code=409,
            detail="Topic discovery has not been completed yet. Run Pipeline A first.",
        )

    task = await create_task_durable(task_store, "topic_expansion", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_topic_expansion_pipeline_task(
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
        pipeline="topic_expansion",
        company_slug=slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "effective_slug": effective_slug,
        },
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline="topic_expansion",
        company_slug=slug,
        product_slug=body.product_slug,
        effective_slug=effective_slug,
        status="started",
        created_at=task.created_at,
    )


# ── Endpoint 10: GET /{slug}/expansion-status ────────────────────────


def _collect_subdomain_nodes(
    nodes: list,
) -> list:
    """Recursively collect all leaf and non-leaf subdomain nodes."""
    result: List[Dict[str, Any]] = []
    for node in nodes:
        result.append(node)
        if hasattr(node, "children") and node.children:
            result.extend(_collect_subdomain_nodes(node.children))
    return result


@router.get("/{slug}/expansion-status")
async def get_expansion_status(
    slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> ExpansionStatusResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    _sb = getattr(http_request.app.state, "storage_backend", None)
    kw = {"backend": _sb} if _sb else {}
    storage = TopicDiscoveryStorage(artifacts_root, slug, **kw)
    taxonomy = storage.get_latest_taxonomy()
    if taxonomy is None:
        raise HTTPException(status_code=404, detail="No taxonomy found")

    all_nodes = _collect_subdomain_nodes(taxonomy.root_nodes)
    expanded_ids: List[str] = []
    available: List[Dict[str, Any]] = []

    for node in all_nodes:
        if node.expansion_status == "expanded":
            expanded_ids.append(node.id)
        elif node.expansion_status in ("not_expanded", "failed"):
            available.append({
                "id": node.id,
                "name": node.name,
                "priority_score": node.priority_score,
                "expansion_status": node.expansion_status,
            })

    # Sort available by priority descending
    available.sort(key=lambda x: x["priority_score"], reverse=True)

    effective_slug = slug
    return ExpansionStatusResponse(
        slug=slug,
        effective_slug=effective_slug,
        total_subdomains=len(all_nodes),
        expanded=len(expanded_ids),
        not_expanded=len(available),
        expanded_ids=expanded_ids,
        available_for_expansion=available,
    )


# ── Endpoint 11: GET /{slug}/summary ──────────────────────────────────


@router.get("/{slug}/summary")
async def get_discovery_summary(
    slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    td_svc=Depends(get_td_data_service),
) -> DiscoverySummaryResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    summary = await td_svc.get_discovery_summary(slug)
    if summary is None:
        raise HTTPException(status_code=404, detail="No discovery found")

    return DiscoverySummaryResponse(**summary)


# ── Endpoint 12: GET /{slug}/assignments ──────────────────────────────


@router.get("/{slug}/assignments")
async def list_assignments(
    slug: str,
    http_request: Request,
    buyer_stage: Optional[str] = None,
    intent_type: Optional[str] = None,
    persona_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    _user: UserProfile = Depends(require_auth),
    td_svc=Depends(get_td_data_service),
) -> AssignmentListResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await td_svc.list_assignments(
        slug,
        buyer_stage=buyer_stage,
        intent_type=intent_type,
        persona_id=persona_id,
        status=status,
        page=page,
        page_size=page_size,
    )

    return AssignmentListResponse(slug=slug, **result)


# ── Endpoint 13: PATCH /{slug}/assignments/{assignment_id} ───────────


@router.patch("/{slug}/assignments/{assignment_id}")
async def update_assignment_status(
    slug: str,
    assignment_id: str,
    body: AssignmentStatusUpdateRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    td_svc=Depends(get_td_data_service),
) -> AssignmentStatusUpdateResponse:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await td_svc.update_assignment_status(slug, assignment_id, body.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    return AssignmentStatusUpdateResponse(
        assignment_id=assignment_id,
        status=body.status,
        message=f"Assignment status updated to {body.status}",
    )


# ── Endpoint 14: POST /{slug}/assignments ─────────────────────────────


@router.post("/{slug}/assignments", status_code=201)
async def create_custom_assignment(
    slug: str,
    body: CreateCustomAssignmentRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    td_svc=Depends(get_td_data_service),
) -> Dict[str, Any]:
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or (
        slug != user_company_slug
        and not slug.startswith(f"{user_company_slug}__")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = await td_svc.create_assignment(
            slug,
            assignment_data={
                "topic_text": body.topic_text,
                "subdomain_id": body.subdomain_id or "",
                "subdomain_name": body.subdomain_name or "",
                "buyer_stage": body.buyer_stage.value,
                "intent_type": body.intent_type.value,
                "persona_id": body.persona_id or "",
                "persona_name": body.persona_name or "",
                "priority_score": body.priority_score,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return result
