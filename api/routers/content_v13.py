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
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import require_auth
from api.dependencies import (
    get_auth_service,
    get_event_bus,
    get_model_config_service,
    get_task_store,
    get_workspace_service,
)
from api.schemas.content_v13 import (
    ApprovalResponseV13,
    BriefApprovalRequest,
    ContentDraftRequestV13,
    ContentDraftResponseV13,
    ContentDraftSaveResponseV13,
    ContentApprovalRequestV13,
    ContentStartRequestV13,
    PipelineRunResponseV13,
    TopicApprovalRequest,
    TopicContentProductionRequest,
    TopicContentStartRequest,
    TopicRunListResponseV13,
    TopicRunEventListResponseV13,
    TopicRunEventV13,
    TopicRunSummaryV13,
    TopicContentStatusItem,
    TopicContentStatusResponse,
)
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.runner import (
    _resolve_scope_async,
    dispatch_queued_td_content_runs,
    run_content_v13_pipeline_task,
    run_td_content_pipeline_task,
    run_td_gap_analysis_task,
)
from api.routers._helpers import (
    assert_slug_workspace_access,
    assert_task_workspace_access,
    create_task_durable,
    resolve_workspace_scope,
)
from api.routers._model_config_preflight import preflight_model_config_or_409
from core.auth.service import AuthServiceProtocol
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation_v13 import ContentGenerationInputV13, EntryMode
from core.models.organization import UserProfile
from core.audit import log_hitl_decision, log_pipeline_launch
from core.model_config.agent_catalog import required_agents_for_pipeline
from core.model_config.service import ModelConfigService
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content/v13", tags=["content-v13"])

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")
_TD_PRODUCTION_QUEUE_CONFLICT_STATES = frozenset({"content_queued", "briefing"})
_CONTENT_AGENT_KEYS = [
    definition.agent_key
    for definition in required_agents_for_pipeline("content")
]


# ---------------------------------------------------------------------------
# Approval Window Validation (C2 fix)
# ---------------------------------------------------------------------------


async def _try_create_td_batch_records(
    request: Request,
    *,
    company_slug: str,
    effective_slug: str,
    workspace_id: str | None,
    topic_assignment_ids: list[str],
    pipeline_task_id: str,
    product_slug: str | None,
    source_mode: str,
    initial_status: str,
    initial_stage: str,
    ga_run_id: str | None = None,
) -> tuple[str | None, list[TopicRunSummaryV13]]:
    """Best-effort durable batch/topic-run creation for TD-entry flows."""
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        return None, []

    try:
        from core.services.content_engine_topic_runs import ContentEngineTopicRunService

        service = ContentEngineTopicRunService(session_factory)
        batch, snapshots = await service.create_td_batch(
            company_slug=company_slug,
            effective_slug=effective_slug,
            workspace_id=workspace_id,
            topic_assignment_ids=topic_assignment_ids,
            pipeline_task_id=pipeline_task_id,
            product_slug=product_slug,
            source_mode=source_mode,
            initial_status=initial_status,
            initial_stage=initial_stage,
            ga_run_id=ga_run_id,
            metadata_json={"effective_slug": effective_slug},
        )
        return str(batch.id), [
            TopicRunSummaryV13(
                topic_run_id=s.topic_run_id,
                batch_run_id=s.batch_run_id,
                topic_assignment_id=s.topic_assignment_id,
                display_id=s.display_id,
                topic_text=s.topic_text,
                brief_id=s.brief_id,
                ga_run_id=s.ga_run_id,
                pipeline_task_id=s.pipeline_task_id,
                status=s.status,
                stage=s.stage,
                seq=s.seq,
                content_piece_id=s.content_piece_id,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in snapshots
        ]
    except Exception:
        logger.warning(
            "Failed to create durable TD batch/topic runs for task=%s slug=%s",
            pipeline_task_id,
            effective_slug,
            exc_info=True,
        )
        return None, []


async def _preflight_content_model_config(
    model_config_service: ModelConfigService,
    workspace_id: str,
) -> None:
    """Fail closed before launching content agents without workspace BYOK config."""
    await preflight_model_config_or_409(
        model_config_service,
        workspace_id,
        _CONTENT_AGENT_KEYS,
        message="Configure an active OpenRouter key before launching content generation.",
    )


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


def _uses_td_durable_continuation(task: PipelineTask) -> bool:
    payload = task.approval_payload or {}
    return bool(
        task.pipeline == "td_content"
        and isinstance(payload.get("continuation"), dict)
    )


def _review_draft_storage_key(*, effective_slug: str, brief_id: str) -> str:
    return f"content/{effective_slug}/content/{brief_id}/review_draft.md"


async def _load_review_draft_content(
    *,
    app,
    effective_slug: str,
    brief_id: str,
) -> str | None:
    storage = getattr(app.state, "storage_backend", None)
    if storage is None:
        from core.storage import get_storage_backend

        storage = get_storage_backend(getattr(app.state, "artifacts_root", None))
    return storage.read(_review_draft_storage_key(effective_slug=effective_slug, brief_id=brief_id))


async def _save_review_draft_content(
    *,
    app,
    effective_slug: str,
    brief_id: str,
    content_markdown: str,
) -> str:
    storage = getattr(app.state, "storage_backend", None)
    if storage is None:
        from core.storage import get_storage_backend

        storage = get_storage_backend(getattr(app.state, "artifacts_root", None))
    return storage.write(
        _review_draft_storage_key(effective_slug=effective_slug, brief_id=brief_id),
        content_markdown,
    )


# ---------------------------------------------------------------------------
# POST /start — Launch v1.3 pipeline
# ---------------------------------------------------------------------------


@router.post("/start", status_code=202)
async def start_content_v13(
    body: ContentStartRequestV13,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> PipelineRunResponseV13:
    """Launch the v1.3 content generation pipeline."""
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    company_slug = workspace_scope.workspace_slug
    await _preflight_content_model_config(
        model_config_service,
        workspace_scope.workspace_id,
    )

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
        gap_query_id=body.gap_query_id,
        brief_id_hint=body.brief_id_hint,
        product_slug=body.product_slug,
        product_name=body.product_name or scope.product_name,
        product_description=body.product_description or scope.product_description,
        auto_approve=body.auto_approve,
        max_concurrent_workers=body.max_concurrent_workers,
        max_revision_cycles=body.max_revision_cycles,
        skip_stages=body.skip_stages,
        # H5-fix: company_context_path, style_guide_path, and persona_paths
        # are now resolved by the runner via resolve_artifacts() fallback chain.
        # Only analysis_json_path stays here (uses gap_slug, not standard fallback).
        analysis_json_path=str(analysis_json_path),
    )

    # Manual mode can run in parallel (each brief is namespaced by brief_id).
    # Autonomous and topic_discovery modes need exclusive artifact directory access.
    is_manual = input_data.entry_mode == EntryMode.MANUAL
    task = await create_task_durable(
        task_store,
        pipeline="content_v13",
        company_slug=company_slug,
        product_slug=body.product_slug,
        allow_parallel=is_manual,
        workspace_id=workspace_scope.workspace_id,
    )

    # H2: Route through runner to enforce semaphore, handle registration, and slug lock cleanup
    handle = asyncio.create_task(
        run_content_v13_pipeline_task(
            task.task_id, input_data, task_store, event_bus, artifacts_root,
            is_parallel=is_manual,
        )
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
        workspace_id=workspace_scope.workspace_id,
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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> dict:
    """Get v1.3 pipeline status."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_workspace_access(task, _user, workspace_service)
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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponseV13:
    """Submit topic approval decision for HITL Checkpoint 1."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponseV13:
    """Submit brief approval decision for HITL Checkpoint 2."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

    # C2 FIX: Stage-aware validation with brief_id match (fast-fail guard)
    _validate_approval_window(task, "brief_approval", body.brief_id)

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    approval_data = {
        "brief_decision": body.decision,
        "brief_feedback": body.feedback or "",
        "brief_id": body.brief_id,
    }

    if _uses_td_durable_continuation(task):
        session_factory = getattr(http_request.app.state, "db_session_factory", None)
        if session_factory is None:
            raise HTTPException(
                status_code=503,
                detail="TD continuation dispatcher is unavailable",
            )
        from core.services.content_engine_topic_runs import (
            ContentEngineTopicRunService,
            TopicRunResumeConflictError,
            TopicRunResumeNotFoundError,
        )

        try:
            task_store.validate_approval_submission(
                run_id,
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

        service = ContentEngineTopicRunService(session_factory)
        try:
            await service.queue_topic_run_resume(
                effective_slug=task.effective_slug or user_company_slug,
                pipeline_task_id=run_id,
                approval_data=approval_data,
            )
        except TopicRunResumeNotFoundError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            )
        except TopicRunResumeConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception:
            logger.warning(
                "Failed to queue TD brief approval continuation for %s",
                run_id,
                exc_info=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Failed to queue TD brief approval continuation",
            )

        task_store.record_approval_submission(
            run_id,
            decision=body.decision,
            revision_note=body.feedback,
            stage="brief_approval",
        )
        try:
            await dispatch_queued_td_content_runs(
                company_slug=user_company_slug,
                task_store=task_store,
                event_bus=http_request.app.state.event_bus,
                session_factory=session_factory,
            )
        except Exception:
            logger.warning(
                "Failed to dispatch queued TD brief approval continuation for %s",
                run_id,
                exc_info=True,
            )
    else:
        try:
            task_store.submit_approval(
                run_id, decision=body.decision, revision_note=body.feedback,
                stage="brief_approval", approval_data=approval_data,
                expected_nonce=nonce,
                delivery_mode="queue",
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
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ApprovalResponseV13:
    """Submit content approval decision for HITL Checkpoint 3."""
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

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
    if body.content_markdown is not None:
        approval_data["content_markdown"] = body.content_markdown

    if body.content_markdown is not None:
        try:
            await _save_review_draft_content(
                app=http_request.app,
                effective_slug=task.effective_slug or user_company_slug,
                brief_id=body.brief_id,
                content_markdown=body.content_markdown,
            )
        except Exception:
            logger.warning(
                "Failed to save review draft content for %s",
                run_id,
                exc_info=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Failed to save review draft content",
            )

    if _uses_td_durable_continuation(task):
        session_factory = getattr(http_request.app.state, "db_session_factory", None)
        if session_factory is None:
            raise HTTPException(
                status_code=503,
                detail="TD continuation dispatcher is unavailable",
            )
        from core.services.content_engine_topic_runs import (
            ContentEngineTopicRunService,
            TopicRunResumeConflictError,
            TopicRunResumeNotFoundError,
        )

        try:
            task_store.validate_approval_submission(
                run_id,
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

        service = ContentEngineTopicRunService(session_factory)
        try:
            await service.queue_topic_run_resume(
                effective_slug=task.effective_slug or user_company_slug,
                pipeline_task_id=run_id,
                approval_data=approval_data,
            )
        except TopicRunResumeNotFoundError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            )
        except TopicRunResumeConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception:
            logger.warning(
                "Failed to queue TD content approval continuation for %s",
                run_id,
                exc_info=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Failed to queue TD content approval continuation",
            )

        task_store.record_approval_submission(
            run_id,
            decision=body.decision,
            revision_note=body.editor_notes,
            stage="content_review",
        )
        try:
            await dispatch_queued_td_content_runs(
                company_slug=user_company_slug,
                task_store=task_store,
                event_bus=http_request.app.state.event_bus,
                session_factory=session_factory,
            )
        except Exception:
            logger.warning(
                "Failed to dispatch queued TD content approval continuation for %s",
                run_id,
                exc_info=True,
            )
    else:
        try:
            task_store.submit_approval(
                run_id, decision=body.decision, revision_note=body.editor_notes,
                stage="content_review", approval_data=approval_data,
                expected_nonce=nonce,
                delivery_mode="queue",
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


@router.get("/{run_id}/draft/content")
async def get_review_draft_content(
    run_id: str,
    brief_id: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ContentDraftResponseV13:
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {run_id}")
    await assert_task_workspace_access(task, _user, workspace_service)
    user_company_slug = task.company_slug

    content_markdown = await _load_review_draft_content(
        app=http_request.app,
        effective_slug=task.effective_slug or user_company_slug,
        brief_id=brief_id,
    )
    if content_markdown is None:
        raise HTTPException(status_code=404, detail="Review draft not found")

    return ContentDraftResponseV13(
        brief_id=brief_id,
        content_markdown=content_markdown,
    )


@router.put("/{run_id}/draft/content")
async def save_review_draft_content(
    run_id: str,
    body: ContentDraftRequestV13,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> ContentDraftSaveResponseV13:
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {run_id}")
    await assert_task_workspace_access(
        task,
        _user,
        workspace_service,
        min_roles=("owner", "admin", "member"),
    )
    user_company_slug = task.company_slug

    try:
        storage_key = await _save_review_draft_content(
            app=http_request.app,
            effective_slug=task.effective_slug or user_company_slug,
            brief_id=body.brief_id,
            content_markdown=body.content_markdown,
        )
    except Exception:
        logger.warning(
            "Failed to persist review draft content for %s",
            run_id,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail="Failed to save review draft content")

    return ContentDraftSaveResponseV13(
        status="saved",
        brief_id=body.brief_id,
        storage_key=storage_key,
    )


# ---------------------------------------------------------------------------
# POST /from-topics — Launch TD → GA → CE pipeline
# ---------------------------------------------------------------------------


@router.post("/from-topics", status_code=202)
async def start_from_topics(
    body: TopicContentStartRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> PipelineRunResponseV13:
    """Launch the TD → GA → CE pipeline for approved topic assignments."""
    # Validate effective_slug format
    if not _SLUG_PATTERN.match(body.effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        effective_slug=body.effective_slug,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    company_slug = workspace_scope.workspace_slug
    await _preflight_content_model_config(
        model_config_service,
        workspace_scope.workspace_id,
    )

    # Create task
    task = await create_task_durable(
        task_store,
        pipeline="td_content",
        company_slug=company_slug,
        product_slug=body.product_slug,
        workspace_id=workspace_scope.workspace_id,
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
        workspace_id=workspace_scope.workspace_id,
        status="started",
        entry_mode="topic_discovery",
        message=f"TD→Content pipeline started for {len(body.topic_assignment_ids)} topics",
    )


# ---------------------------------------------------------------------------
# POST /from-topics/gap-analysis — Launch TD → GA-only pipeline (Phase 1)
# ---------------------------------------------------------------------------


@router.post("/from-topics/gap-analysis", status_code=202)
async def start_from_topics_gap_analysis(
    body: TopicContentStartRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> PipelineRunResponseV13:
    """Launch the TD → GA-only pipeline (Phase 1) for approved topic assignments.

    Runs topic-scoped Gap Analysis without starting Content Engine.
    The user can review GA results and then launch production (Phase 2).
    """
    # Validate effective_slug format
    if not _SLUG_PATTERN.match(body.effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        effective_slug=body.effective_slug,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    company_slug = workspace_scope.workspace_slug

    # Create task
    task = await create_task_durable(
        task_store,
        pipeline="td_gap_analysis",
        company_slug=company_slug,
        product_slug=body.product_slug,
        allow_parallel=True,
        workspace_id=workspace_scope.workspace_id,
    )

    batch_run_id, topic_runs = await _try_create_td_batch_records(
        http_request,
        company_slug=company_slug,
        effective_slug=body.effective_slug,
        workspace_id=workspace_scope.workspace_id,
        topic_assignment_ids=body.topic_assignment_ids,
        pipeline_task_id=task.task_id,
        product_slug=body.product_slug,
        source_mode="td_entry_gap_analysis",
        initial_status="gap_analysis_pending",
        initial_stage="gap_analysis_pending",
        ga_run_id=None,
    )

    handle = asyncio.create_task(
        run_td_gap_analysis_task(
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
            platforms=body.platforms,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="td_gap_analysis",
        company_slug=company_slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "effective_slug": body.effective_slug,
        },
    )

    return PipelineRunResponseV13(
        run_id=task.task_id,
        workspace_id=workspace_scope.workspace_id,
        status="started",
        entry_mode="topic_discovery_ga",
        message=f"TD→GA pipeline started for {len(body.topic_assignment_ids)} topics",
        batch_run_id=batch_run_id,
        topic_runs=topic_runs,
    )


# ---------------------------------------------------------------------------
# POST /from-topics/start-production — Launch Content Production (Phase 2)
# ---------------------------------------------------------------------------


@router.post("/from-topics/start-production", status_code=202)
async def start_from_topics_production(
    body: TopicContentProductionRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> PipelineRunResponseV13:
    """Launch Content Engine production from pre-computed GA results (Phase 2).

    Validates that the GA run's analysis.json exists before starting.
    """
    # Validate effective_slug format
    if not _SLUG_PATTERN.match(body.effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")
    workspace_scope = await resolve_workspace_scope(
        http_request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        effective_slug=body.effective_slug,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    company_slug = workspace_scope.workspace_slug
    await _preflight_content_model_config(
        model_config_service,
        workspace_scope.workspace_id,
    )

    # Validate that the GA run analysis.json exists
    from core.storage import get_storage_backend
    storage = get_storage_backend()
    analysis_key = f"gap_analysis/{body.effective_slug}/topic_scoped/{body.ga_run_id}/analysis.json"
    if not storage.exists(analysis_key):
        raise HTTPException(
            status_code=404,
            detail=f"GA run {body.ga_run_id} analysis not found. Gap analysis may not have completed.",
        )

    try:
        from core.redis import get_redis_or_none
        from core.content_engine.state_redis import read_ga_phase_cards_async

        redis_client = get_redis_or_none()
        if redis_client is not None:
            queued_cards = await read_ga_phase_cards_async(redis_client, body.effective_slug)
            conflicts = [
                card.get("display_id") or card.get("topic_assignment_id") or ""
                for card in queued_cards
                if card.get("topic_assignment_id") in body.topic_assignment_ids
                and card.get("status") in _TD_PRODUCTION_QUEUE_CONFLICT_STATES
                and (
                    not card.get("ga_run_id")
                    or card.get("ga_run_id") == body.ga_run_id
                )
            ]
            if conflicts:
                conflict_list = ", ".join(conflicts)
                raise HTTPException(
                    status_code=409,
                    detail=f"Content production is already queued or running for: {conflict_list}",
                )
    except HTTPException:
        raise
    except Exception:
        logger.warning(
            "Failed to preflight queued production state for %s",
            body.effective_slug,
            exc_info=True,
        )

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(
            status_code=503,
            detail="TD content dispatcher is unavailable",
        )

    from core.services.content_engine_topic_runs import ContentEngineTopicRunService

    service = ContentEngineTopicRunService(session_factory)
    try:
        queued_snapshots = await service.queue_topic_runs_for_dispatch(
            effective_slug=body.effective_slug,
            topic_assignment_ids=body.topic_assignment_ids,
            ga_run_id=body.ga_run_id,
            match_ga_run_id=body.ga_run_id,
            launch_context={
                "company_name": body.company_name,
                "domain": body.domain,
                "product_slug": body.product_slug,
                "product_name": body.product_name,
                "product_description": body.product_description,
                "auto_approve": body.auto_approve,
            },
        )
    except Exception:
        logger.warning(
            "Failed to queue durable TD topic runs for %s",
            body.effective_slug,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Failed to queue TD content production",
        )

    if not queued_snapshots:
        raise HTTPException(
            status_code=409,
            detail="No matching topic runs were queued for TD content production",
        )

    try:
        from core.orchestration.td_content_orchestrator import _emit_company_event, _update_ga_phase_status

        _update_ga_phase_status(
            body.effective_slug,
            body.topic_assignment_ids,
            "content_queued",
        )
        _emit_company_event(
            body.effective_slug,
            "state_changed",
            {"changed": body.topic_assignment_ids, "hint": "content_queued"},
        )
    except Exception:
        logger.warning(
            "Failed to persist queued GA-phase state for %s",
            body.effective_slug,
            exc_info=True,
        )

    topic_run_items = [
        TopicRunSummaryV13(
            topic_run_id=s.topic_run_id,
            batch_run_id=s.batch_run_id,
            topic_assignment_id=s.topic_assignment_id,
            display_id=s.display_id,
            topic_text=s.topic_text,
            brief_id=s.brief_id,
            ga_run_id=s.ga_run_id,
            pipeline_task_id=s.pipeline_task_id,
            status=s.status,
            stage=s.stage,
            seq=s.seq,
            content_piece_id=s.content_piece_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in queued_snapshots
    ]
    dispatched = []
    try:
        dispatched = await dispatch_queued_td_content_runs(
            company_slug=company_slug,
            task_store=task_store,
            event_bus=event_bus,
            session_factory=session_factory,
        )
        if dispatched:
            snapshots = await service.list_topic_runs_by_assignment_ids(
                effective_slug=body.effective_slug,
                topic_assignment_ids=body.topic_assignment_ids,
                ga_run_id=body.ga_run_id,
            )
            topic_run_items = [
                TopicRunSummaryV13(
                    topic_run_id=s.topic_run_id,
                    batch_run_id=s.batch_run_id,
                    topic_assignment_id=s.topic_assignment_id,
                    display_id=s.display_id,
                    topic_text=s.topic_text,
                    brief_id=s.brief_id,
                    ga_run_id=s.ga_run_id,
                    pipeline_task_id=s.pipeline_task_id,
                    status=s.status,
                    stage=s.stage,
                    seq=s.seq,
                    content_piece_id=s.content_piece_id,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in snapshots
            ]
    except Exception:
        logger.warning(
            "Failed to dispatch queued TD topic runs for %s",
            body.effective_slug,
            exc_info=True,
        )
    for dispatched_item in dispatched:
        await log_pipeline_launch(
            user_id=_user.id,
            pipeline="td_content",
            company_slug=company_slug,
            task_id=dispatched_item["task_id"],
            detail={
                "product_slug": body.product_slug,
                "effective_slug": body.effective_slug,
                "ga_run_id": body.ga_run_id,
                "topic_assignment_id": dispatched_item["topic_assignment_id"],
            },
        )

    return PipelineRunResponseV13(
        run_id=(topic_run_items[0].pipeline_task_id if topic_run_items else None) or "",
        workspace_id=workspace_scope.workspace_id,
        status="started",
        entry_mode="topic_discovery",
        message=f"TD→Content production queued for {len(body.topic_assignment_ids)} topics (GA: {body.ga_run_id[:8]}...)",
        topic_runs=topic_run_items,
    )


# ---------------------------------------------------------------------------
# GET /topic-content-status — Per-assignment status
# ---------------------------------------------------------------------------


@router.get("/{effective_slug}/topic-content-status")
async def get_topic_content_status(
    effective_slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TopicContentStatusResponse:
    """Get per-assignment content status for a TD-driven content run."""
    if not _SLUG_PATTERN.match(effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")

    await assert_slug_workspace_access(effective_slug, _user, workspace_service)

    from core.topic_discovery.db_ops import db_read_latest_matrix

    sf = getattr(http_request.app.state, "db_session_factory", None)
    matrix = None
    if sf is not None:
        try:
            matrix = await db_read_latest_matrix(sf, effective_slug)
        except Exception as exc:
            logger.warning(
                "topic-content-status DB lookup failed for %s: %s", effective_slug, exc,
            )

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


@router.get("/{effective_slug}/topic-runs")
async def get_topic_runs(
    effective_slug: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TopicRunListResponseV13:
    """List durable TD-entry topic runs for Content Studio hydration."""
    if not _SLUG_PATTERN.match(effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")

    await assert_slug_workspace_access(effective_slug, _user, workspace_service)

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    if session_factory is None:
        return TopicRunListResponseV13(effective_slug=effective_slug)

    try:
        from core.services.content_engine_topic_runs import ContentEngineTopicRunService

        service = ContentEngineTopicRunService(session_factory)
        items = await service.list_topic_runs(effective_slug=effective_slug)
    except Exception:
        logger.warning("Failed to list topic runs for %s", effective_slug, exc_info=True)
        items = []

    return TopicRunListResponseV13(
        effective_slug=effective_slug,
        total=len(items),
        items=[
            TopicRunSummaryV13(
                topic_run_id=item.topic_run_id,
                batch_run_id=item.batch_run_id,
                topic_assignment_id=item.topic_assignment_id,
                display_id=item.display_id,
                topic_text=item.topic_text,
                brief_id=item.brief_id,
                ga_run_id=item.ga_run_id,
                pipeline_task_id=item.pipeline_task_id,
                status=item.status,
                stage=item.stage,
                seq=item.seq,
                content_piece_id=item.content_piece_id,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
    )


@router.get("/{effective_slug}/topic-runs/{topic_run_id}/events")
async def get_topic_run_events(
    effective_slug: str,
    topic_run_id: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> TopicRunEventListResponseV13:
    """List durable append-only execution events for one TD-entry topic run."""
    if not _SLUG_PATTERN.match(effective_slug):
        raise HTTPException(status_code=400, detail="Invalid effective_slug format")
    try:
        uuid.UUID(topic_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid topic_run_id format") from exc

    await assert_slug_workspace_access(effective_slug, _user, workspace_service)

    session_factory = getattr(http_request.app.state, "db_session_factory", None)
    if session_factory is None:
        return TopicRunEventListResponseV13(
            effective_slug=effective_slug,
            topic_run_id=topic_run_id,
        )

    try:
        from core.services.content_engine_topic_runs import ContentEngineTopicRunService

        service = ContentEngineTopicRunService(session_factory)
        topic_run, items = await service.list_topic_run_events(
            effective_slug=effective_slug,
            topic_run_id=topic_run_id,
        )
    except Exception:
        logger.warning(
            "Failed to list topic run events for %s/%s",
            effective_slug,
            topic_run_id,
            exc_info=True,
        )
        topic_run, items = None, []

    if topic_run is None:
        return TopicRunEventListResponseV13(
            effective_slug=effective_slug,
            topic_run_id=topic_run_id,
        )

    return TopicRunEventListResponseV13(
        effective_slug=effective_slug,
        topic_run_id=topic_run.topic_run_id,
        topic_assignment_id=topic_run.topic_assignment_id,
        display_id=topic_run.display_id,
        topic_text=topic_run.topic_text,
        brief_id=topic_run.brief_id,
        total=len(items),
        items=[
            TopicRunEventV13(
                topic_event_id=item.topic_event_id,
                topic_run_id=item.topic_run_id,
                topic_assignment_id=item.topic_assignment_id,
                display_id=item.display_id,
                brief_id=item.brief_id,
                event_type=item.event_type,
                stage=item.stage,
                status=item.status,
                seq=item.seq,
                content_piece_id=item.content_piece_id,
                pipeline_task_id=item.pipeline_task_id,
                payload_json=item.payload_json,
                created_at=item.created_at,
            )
            for item in items
        ],
    )
