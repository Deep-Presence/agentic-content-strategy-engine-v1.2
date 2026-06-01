"""Topic Discovery pipeline API endpoints."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_task_store, get_td_data_service, get_workspace_service
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.topic_discovery import (
    ApprovalResponseTD,
    AssignmentListResponse,
    AssignmentStatusUpdateRequest,
    AssignmentStatusUpdateResponse,
    CreateCustomAssignmentRequest,
    CreateNodeRequest,
    NodeResponse,
    UpdateNodeRequest,
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
from api.routers._helpers import (
    assert_slug_workspace_access,
    assert_task_workspace_access,
    create_task_durable,
    resolve_workspace_scope,
)
from api.tasks.runner import run_topic_discovery_pipeline_task, run_topic_expansion_pipeline_task
from core.auth.service import AuthServiceProtocol
from core.models.organization import UserProfile
from core.audit import log_hitl_decision, log_pipeline_launch
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/topic-discovery", tags=["topic-discovery"])


# ── Helpers ───────────────────────────────────────────────────────────


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


async def _td_should_guard_db(
    session_factory: Any,
    effective_slug: str,
) -> tuple[bool, Optional[str]]:
    """Check whether the TD guard should block a new run via DB."""
    from core.topic_discovery.db_ops import db_read_manifest

    manifest = await db_read_manifest(session_factory, effective_slug)
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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponse:
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    slug = workspace_scope.workspace_slug
    effective_slug = workspace_scope.effective_slug

    # Guard: check if discovery already exists
    if not body.force_rerun:
        sf = getattr(http_request.app.state, "db_session_factory", None)
        if sf is None:
            raise HTTPException(status_code=503, detail="Database not available")
        should_guard, message = await _td_should_guard_db(sf, effective_slug)
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
                workspace_id=workspace_scope.workspace_id,
                product_slug=body.product_slug,
                effective_slug=effective_slug,
                status="already_exists",
                created_at=datetime.now(timezone.utc),
                already_exists=True,
                message=message or "",
            )

    task = await create_task_durable(
        task_store,
        "topic_discovery",
        slug,
        product_slug=body.product_slug,
        workspace_id=workspace_scope.workspace_id,
    )

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
        workspace_id=task.workspace_id,
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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TaskResponse:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(task, _user, workspace_service)
    return TaskResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        workspace_id=task.workspace_id,
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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponseTD:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponseTD:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponseTD:
    task = task_store.get_task(run_id)
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> TaxonomyReadResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> MatrixReadResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> ScoredSubdomainsResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> PersonaAffinityResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

    affinity = await td_svc.get_persona_affinity(slug, persona_id=persona_id)
    if affinity is None:
        raise HTTPException(status_code=404, detail="No persona affinity data found")

    return PersonaAffinityResponse(
        slug=slug,
        persona_entries=affinity.get("persona_entries", {}),
        persona_metadata=affinity.get("persona_metadata", {}),
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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponse:
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    slug = workspace_scope.workspace_slug
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    # Pre-check: discovery must have completed
    sf = getattr(http_request.app.state, "db_session_factory", None)
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not available")
    from core.topic_discovery.db_ops import db_read_manifest
    manifest = await db_read_manifest(sf, effective_slug)
    if manifest.taxonomy_version == 0:
        raise HTTPException(
            status_code=409,
            detail="Topic discovery has not been completed yet. Run Pipeline A first.",
        )

    # allow_parallel=True: multiple subdomains can expand concurrently.
    # Per-subdomain safety is handled by db_claim_subdomain_for_expansion()
    # (optimistic DB lock), not by the Redis slug lock.
    task = await create_task_durable(
        task_store, "topic_expansion", slug,
        product_slug=body.product_slug,
        allow_parallel=True,
        workspace_id=workspace_scope.workspace_id,
    )

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
        workspace_id=task.workspace_id,
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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ExpansionStatusResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

    sf = getattr(http_request.app.state, "db_session_factory", None)
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not available")
    from core.topic_discovery.db_ops import db_read_taxonomy
    taxonomy = await db_read_taxonomy(sf, slug)
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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> DiscoverySummaryResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> AssignmentListResponse:
    await assert_slug_workspace_access(slug, _user, workspace_service)

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
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> AssignmentStatusUpdateResponse:
    await assert_slug_workspace_access(
        slug,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )

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
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> Dict[str, Any]:
    await assert_slug_workspace_access(
        slug,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )

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


# ═══════════════════════════════════════════════════════════════════════
# Tree CRUD: Node operations (editable tree)
# ═══════════════════════════════════════════════════════════════════���═══


# ── Endpoint 16: PATCH /{slug}/nodes/{node_id} ────────────────────────


@router.patch("/{slug}/nodes/{node_id}")
async def update_node(
    slug: str,
    node_id: str,
    body: UpdateNodeRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> NodeResponse:
    """Update a single taxonomy node's attributes (name, description, parent_id)."""
    await assert_slug_workspace_access(
        slug,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )

    kwargs = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description
    if body.parent_id is not None:
        import uuid as _uuid
        try:
            kwargs["parent_id"] = _uuid.UUID(body.parent_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid parent_id UUID")

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await td_svc.update_node(slug, node_id, **kwargs)
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")

    return NodeResponse(
        id=str(result["id"]),
        name=result.get("name", ""),
        description=result.get("description", ""),
        parent_id=str(result["parent_id"]) if result.get("parent_id") else None,
        depth=result.get("depth", 0),
        expansion_status=result.get("expansion_status", "not_expanded"),
        message="Node updated",
    )


# ── Endpoint 17: DELETE /{slug}/nodes/{node_id} ──────────────────────


@router.delete("/{slug}/nodes/{node_id}")
async def delete_node(
    slug: str,
    node_id: str,
    http_request: Request,
    reparent_children: bool = True,
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> NodeResponse:
    """Delete a single taxonomy node. Children are reparented by default."""
    await assert_slug_workspace_access(
        slug,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )

    deleted = await td_svc.delete_node(slug, node_id, reparent_children=reparent_children)
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")

    return NodeResponse(
        id=node_id,
        name="",
        message="Node deleted" + (" (children reparented)" if reparent_children else ""),
    )


# ── Endpoint 18: POST /{slug}/nodes ──────────────────────────────────


@router.post("/{slug}/nodes", status_code=201)
async def create_node(
    slug: str,
    body: CreateNodeRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    td_svc=Depends(get_td_data_service),
) -> NodeResponse:
    """Add a new taxonomy node (manual addition)."""
    await assert_slug_workspace_access(
        slug,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )

    result = await td_svc.create_node(
        slug,
        name=body.name,
        description=body.description,
        parent_id=body.parent_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Discovery not found for slug")

    return NodeResponse(
        id=str(result["id"]),
        name=result.get("name", ""),
        description=result.get("description", ""),
        parent_id=str(result["parent_id"]) if result.get("parent_id") else None,
        depth=result.get("depth", 0),
        expansion_status="not_expanded",
        message="Node created",
    )
