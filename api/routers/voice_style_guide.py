"""Voice Style Guide pipeline API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_task_store, get_vsg_data_service
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.voice_style_guide import (
    ApprovalResponseVSG,
    AuthorApprovalRequest,
    VoiceStyleGuideStartRequest,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus
from api.routers._helpers import create_task_durable
from api.tasks.runner import run_voice_style_guide_pipeline_task
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.organization import UserProfile
from core.research.voice_style_guide.storage import VoiceStyleGuideStorage
from core.audit import log_hitl_decision, log_pipeline_launch
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice-style-guide", tags=["voice-style-guide"])


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


def _vsg_should_guard(
    artifacts_root: Path,
    effective_slug: str,
) -> tuple[bool, Optional[str]]:
    """Check whether the VSG guard should block a new run.

    Guard blocks when a fresh voice style guide already exists.
    """
    storage = VoiceStyleGuideStorage(artifacts_root, effective_slug)
    manifest = storage.read_manifest()

    if manifest.guide.current_version > 0 and manifest.guide.status == "fresh":
        return True, (
            f"Voice style guide already exists (v{manifest.guide.current_version}). "
            "Pass force_rerun=true to re-run."
        )
    return False, None


# ── Endpoint 1: POST /start ──────────────────────────────────────────


@router.post(
    "/start",
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "Guide already exists"}},
)
async def start_voice_style_guide(
    body: VoiceStyleGuideStartRequest,
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
    slug = _derive_slug_local(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )
    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    # Guard: check if guide already exists
    if not body.force_rerun:
        should_guard, message = _vsg_should_guard(artifacts_root, effective_slug)
        if should_guard:
            response.status_code = 200
            await log_pipeline_launch(
                user_id=_user.id,
                pipeline="voice_style_guide",
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
                pipeline="voice_style_guide",
                company_slug=slug,
                product_slug=body.product_slug,
                effective_slug=effective_slug,
                status="already_exists",
                created_at=datetime.now(timezone.utc),
                already_exists=True,
                message=message or "",
            )

    task = await create_task_durable(task_store, "voice_style_guide", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_voice_style_guide_pipeline_task(
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
        pipeline="voice_style_guide",
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
        pipeline="voice_style_guide",
        company_slug=slug,
        product_slug=body.product_slug,
        effective_slug=effective_slug,
        status="started",
        created_at=task.created_at,
    )


# ── Endpoint 2: GET /{run_id}/status ─────────────────────────────────


@router.get("/{run_id}/status")
async def get_voice_style_guide_status(
    run_id: str,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> TaskResponse:
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
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


# ── Endpoint 3: POST /{run_id}/approve/authors ──────────────────────


@router.post("/{run_id}/approve/authors")
async def approve_authors(
    run_id: str,
    body: AuthorApprovalRequest,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseVSG:
    task = task_store.get_task(run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _validate_approval_window(task, "vsg_author_review")

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    approval_data = {
        "batch_decision": body.batch_decision,
        "author_reviews": [r.model_dump(mode="json") for r in body.author_reviews],
    }

    try:
        task_store.submit_approval(
            run_id,
            decision=body.batch_decision,
            stage="vsg_author_review",
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="voice_style_guide",
            stage="vsg_author_review",
            decision="rejected",
            company_slug=task.company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="voice_style_guide",
        stage="vsg_author_review",
        decision=body.batch_decision,
        company_slug=task.company_slug,
        detail={"author_count": len(body.author_reviews)},
    )

    return ApprovalResponseVSG(
        status="accepted",
        stage="vsg_author_review",
        message=f"Author review submitted: {body.batch_decision}",
    )


# ── Endpoint 4: GET /{slug}/guide ────────────────────────────────────


@router.get("/{slug}/guide")
async def get_latest_guide(
    slug: str,
    _user: UserProfile = Depends(require_auth),
    vsg_svc=Depends(get_vsg_data_service),
) -> Dict[str, Any]:
    result = await vsg_svc.get_guide(slug)
    if result is None:
        raise HTTPException(status_code=404, detail="No voice style guide found")

    return {
        "slug": slug,
        "guide_md": result["content_md"],
        "version": result.get("version", 0),
        "word_count": result.get("word_count", 0),
        "last_updated": result.get("last_updated"),
        "source_authors": result.get("source_authors", []),
    }
