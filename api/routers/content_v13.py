"""Content generation pipeline v1.3 API endpoints.

Exposes the v1.3 pipeline at /api/v1/content/v13/ with three
HITL approval endpoints (topics, briefs, content).

Follows the same patterns as the existing content.py router
(auth, tenant isolation, task store, event bus).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_auth_service, get_event_bus, get_task_store
from api.schemas.content_v13 import (
    ApprovalResponseV13,
    BriefApprovalRequest,
    ContentApprovalRequestV13,
    ContentStartRequestV13,
    PipelineRunResponseV13,
    TopicApprovalRequest,
    TopicContentStartRequest,
    TopicContentStatusItem,
    TopicContentStatusResponse,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.runner import (
    _derive_slug,
    _resolve_scope_async,
    run_content_v13_pipeline_task,
    run_td_content_pipeline_task,
)
from core.auth.service import AuthServiceProtocol
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation_v13 import ContentGenerationInputV13, EntryMode
from core.models.organization import UserProfile
from core.audit import log_hitl_decision, log_pipeline_launch
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content/v13", tags=["content-v13"])

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")


# ---------------------------------------------------------------------------
# Approval Window Validation (C2 fix)
# ---------------------------------------------------------------------------


def _validate_approval_window(
    task: PipelineTask,
    expected_stage: str,
    expected_brief_id: Optional[str] = None,
) -> None:
    """Validate that a task is in the correct HITL window for approval.

    Raises ``HTTPException(409)`` if the task is not awaiting approval,
    is at the wrong HITL stage, or the brief ID doesn't match.

    Args:
        task: The pipeline task to validate.
        expected_stage: Machine-name stage ID from the interrupt value
            (``"topic_approval"``, ``"brief_approval"``, ``"content_review"``).
        expected_brief_id: For brief/content endpoints, the brief_id from
            the request body that must match the current checkpoint's brief_id.
    """
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

    if expected_brief_id:
        current_brief_id = payload.get("brief_id", "")
        if current_brief_id and expected_brief_id != current_brief_id:
            raise HTTPException(
                status_code=409,
                detail=f"Brief ID mismatch (expected: {current_brief_id}, got: {expected_brief_id})",
            )


# ---------------------------------------------------------------------------
# POST /start — Launch v1.3 pipeline
# ---------------------------------------------------------------------------


@router.post("/start", status_code=202)
async def start_content_v13(
    body: ContentStartRequestV13,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponseV13:
    """Launch the v1.3 content generation pipeline."""
    # Tenant isolation
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    company_slug = _derive_slug(body.company_name)
    if not user_company_slug or company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Cannot start pipeline for another company")

    scope = await _resolve_scope_async(company_slug, body.product_slug, auth_service)

    # Build input
    gap_slug = body.gap_slug or scope.effective_slug
    artifacts_root = http_request.app.state.artifacts_root

    # H5: Validate gap_slug before using it in a filesystem path
    if body.gap_slug and not _SLUG_PATTERN.match(body.gap_slug):
        raise HTTPException(status_code=400, detail="Invalid gap_slug format")
    analysis_json_path = artifacts_root / "gap_analysis" / gap_slug / "analysis.json"
    if not analysis_json_path.is_relative_to(artifacts_root):
        raise HTTPException(status_code=400, detail="Invalid gap_slug: path traversal detected")

    input_data = ContentGenerationInputV13(
        company_name=body.company_name,
        domain=body.domain,
        company_slug=scope.effective_slug,
        entry_mode=EntryMode(body.entry_mode),
        max_topics=body.max_topics,
        manual_prompt=body.manual_prompt,
        manual_description=body.manual_description,
        manual_cluster=body.manual_cluster,
        product_slug=body.product_slug,
        product_name=body.product_name or scope.product_name,
        product_description=body.product_description or scope.product_description,
        auto_approve=body.auto_approve,
        max_concurrent_workers=body.max_concurrent_workers,
        max_revision_cycles=body.max_revision_cycles,
        skip_stages=body.skip_stages,
        # Resolve artifact paths
        company_context_path=str(artifacts_root / "company_context" / f"{scope.effective_slug}.md"),
        style_guide_path=str(artifacts_root / "style_guides" / f"{scope.effective_slug}.md"),
        analysis_json_path=str(analysis_json_path),
    )

    # Create task (this also acquires the slug lock)
    task = task_store.create_task(
        pipeline="content_v13",
        company_slug=company_slug,
        product_slug=body.product_slug,
    )

    # H2: Route through runner to enforce semaphore, handle registration, and slug lock cleanup
    handle = asyncio.create_task(
        run_content_v13_pipeline_task(task.task_id, input_data, task_store, event_bus)
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="content_v13",
        company_slug=company_slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "entry_mode": body.entry_mode,
            "max_topics": body.max_topics,
            "effective_slug": scope.effective_slug,
        },
    )

    return PipelineRunResponseV13(
        run_id=task.task_id,
        status="started",
        entry_mode=body.entry_mode,
    )


# ---------------------------------------------------------------------------
# GET /status — Poll pipeline status
# ---------------------------------------------------------------------------


@router.get("/{run_id}/status")
async def get_status_v13(
    run_id: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> dict:
    """Get v1.3 pipeline status."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "current_step": task.current_step,
        "progress_pct": task.progress_pct,
        "error": task.error,
        "result": task.result,
        "approval_payload": task.approval_payload,
    }


# ---------------------------------------------------------------------------
# POST /approve/topics — HITL-1 Topic Approval
# ---------------------------------------------------------------------------


@router.post("/{run_id}/approve/topics")
async def approve_topics(
    run_id: str,
    body: TopicApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseV13:
    """Submit topic approval decision for HITL Checkpoint 1."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    # C2 FIX: Stage-aware validation (fast-fail guard)
    _validate_approval_window(task, "topic_approval")

    # Extract nonce for atomic validation inside submit_approval
    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    approval_data = {
        "topic_decision": body.decision,
        "approved_topic_ranks": body.approved_topic_ranks,
        "topic_feedback": body.feedback or "",
    }

    # Queue approval_data directly — run_hitl_checkpoint reads from queue (C1 fix).
    # Nonce validation inside submit_approval prevents TOCTOU and replay.
    try:
        task_store.submit_approval(
            run_id, decision=body.decision, revision_note=body.feedback,
            stage="topic_approval", approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="content_v13",
            stage="topic_approval",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc))

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="content_v13",
        stage="topic_approval",
        decision=body.decision,
        company_slug=user_company_slug,
        detail={"approved_ranks_count": len(body.approved_topic_ranks or []), "has_feedback": bool(body.feedback)},
    )

    return ApprovalResponseV13(
        status="accepted",
        stage="topic_approval",
        message=f"Topic {body.decision} submitted",
    )


# ---------------------------------------------------------------------------
# POST /approve/briefs — HITL-2 Brief Approval
# ---------------------------------------------------------------------------


@router.post("/{run_id}/approve/briefs")
async def approve_brief(
    run_id: str,
    body: BriefApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseV13:
    """Submit brief approval decision for HITL Checkpoint 2."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    # C2 FIX: Stage-aware validation with brief_id match (fast-fail guard)
    _validate_approval_window(task, "brief_approval", body.brief_id)

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    approval_data = {
        "brief_decision": body.decision,
        "brief_feedback": body.feedback or "",
        "brief_id": body.brief_id,
    }

    try:
        task_store.submit_approval(
            run_id, decision=body.decision, revision_note=body.feedback,
            stage="brief_approval", approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="content_v13",
            stage="brief_approval",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc))

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="content_v13",
        stage="brief_approval",
        decision=body.decision,
        company_slug=user_company_slug,
        detail={"brief_id": body.brief_id, "has_feedback": bool(body.feedback)},
    )

    return ApprovalResponseV13(
        status="accepted",
        stage="brief_approval",
        brief_id=body.brief_id,
        message=f"Brief {body.brief_id} {body.decision} submitted",
    )


# ---------------------------------------------------------------------------
# POST /approve/content — HITL-3 Final Content Review
# ---------------------------------------------------------------------------


@router.post("/{run_id}/approve/content")
async def approve_content(
    run_id: str,
    body: ContentApprovalRequestV13,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseV13:
    """Submit content approval decision for HITL Checkpoint 3."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    # C2 FIX: Stage-aware validation with brief_id match (fast-fail guard)
    _validate_approval_window(task, "content_review", body.brief_id)

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    raw_notes = body.editor_notes or ""
    # Defense-in-depth: truncate editor_notes before embedding in graph state.
    # Schema max_length=5000 is the primary guard; this protects if that check
    # is ever bypassed (e.g., internal callers, future middleware changes).
    truncated_notes = truncate_to_token_limit(raw_notes, max_tokens=1000, label="editor_notes")
    approval_data = {
        "content_decision": body.decision,
        "editor_notes": truncated_notes,
        "rethink": body.rethink,
        "brief_id": body.brief_id,
    }

    try:
        task_store.submit_approval(
            run_id, decision=body.decision, revision_note=body.editor_notes,
            stage="content_review", approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="content_v13",
            stage="content_review",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc))

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="content_v13",
        stage="content_review",
        decision=body.decision,
        company_slug=user_company_slug,
        detail={"brief_id": body.brief_id, "rethink": body.rethink, "has_editor_notes": bool(body.editor_notes)},
    )

    return ApprovalResponseV13(
        status="accepted",
        stage="content_review",
        brief_id=body.brief_id,
        message=f"Content {body.brief_id} {body.decision} submitted",
    )


# ---------------------------------------------------------------------------
# POST /from-topics — Launch TD → GA → CE pipeline
# ---------------------------------------------------------------------------


@router.post("/from-topics", status_code=202)
async def start_from_topics(
    body: TopicContentStartRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponseV13:
    """Launch the TD → GA → CE pipeline for approved topic assignments."""
    # Tenant isolation
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    company_slug = _derive_slug(body.company_name)
    if not user_company_slug or company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Cannot start pipeline for another company")

    # Validate effective_slug format
    if not _SLUG_PATTERN.match(body.effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")

    # Create task
    task = task_store.create_task(
        pipeline="td_content",
        company_slug=company_slug,
        product_slug=body.product_slug,
    )

    handle = asyncio.create_task(
        run_td_content_pipeline_task(
            task_id=task.task_id,
            effective_slug=body.effective_slug,
            topic_assignment_ids=body.topic_assignment_ids,
            company_name=body.company_name,
            domain=body.domain,
            task_store=task_store,
            event_bus=event_bus,
            product_slug=body.product_slug,
            product_name=body.product_name,
            product_description=body.product_description,
            auto_approve=body.auto_approve,
            platforms=body.platforms,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="td_content",
        company_slug=company_slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "effective_slug": body.effective_slug,
        },
    )

    return PipelineRunResponseV13(
        run_id=task.task_id,
        status="started",
        entry_mode="topic_discovery",
        message=f"TD→Content pipeline started for {len(body.topic_assignment_ids)} topics",
    )


# ---------------------------------------------------------------------------
# GET /topic-content-status — Per-assignment status
# ---------------------------------------------------------------------------


@router.get("/{effective_slug}/topic-content-status")
async def get_topic_content_status(
    effective_slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
) -> TopicContentStatusResponse:
    """Get per-assignment content status for a TD-driven content run."""
    if not _SLUG_PATTERN.match(effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")

    # Tenant isolation: effective_slug must start with the user's company slug
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or not effective_slug.startswith(user_company_slug):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        from core.topic_discovery.storage import TopicDiscoveryStorage

        artifacts_root = http_request.app.state.artifacts_root
        td_storage = TopicDiscoveryStorage(
            artifacts_root=artifacts_root, slug=effective_slug,
        )
        matrix = td_storage.get_latest_matrix()
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "topic-content-status lookup failed for %s: %s", effective_slug, exc,
        )
        matrix = None

    if matrix is None:
        return TopicContentStatusResponse(effective_slug=effective_slug)

    items = []
    for a in matrix.assignments:
        items.append(TopicContentStatusItem(
            topic_assignment_id=a.id,
            topic_text=a.topic_text,
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
        ))

    return TopicContentStatusResponse(
        effective_slug=effective_slug,
        total_assignments=len(items),
        items=items,
    )
