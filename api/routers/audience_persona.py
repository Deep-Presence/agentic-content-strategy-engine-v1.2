"""Audience Persona pipeline API endpoints."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_artifacts_root, get_auth_service, get_event_bus, get_persona_data_service, get_task_store
from api.schemas.audience_persona import (
    ApprovalResponseAP,
    AudiencePersonaStartRequest,
    ManualPersonaBriefRequest,
    PersonaBriefApprovalRequest,
    PersonaListItem,
    PersonaListResponse,
    PersonaProfileApprovalRequest,
    StandaloneApproveRequest,
)
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.runner import run_audience_persona_pipeline_task, run_single_persona_generator_task
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.audience_persona import PersonaBrief
from core.models.organization import UserProfile
from core.research.audience_persona.storage import PersonaStorage
from core.audit import log_hitl_decision, log_pipeline_launch
from core.services.task_store import ApprovalWindowError, TaskStoreProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audience-persona", tags=["audience-persona"])

# Regex for safe slug/persona_id path params
_SAFE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


# ── Helpers ───────────────────────────────────────────────────────────


def _derive_slug_local(company_name: str) -> str:
    return derive_slug(company_name)


def _slugify_persona_name(name: str) -> str:
    """Convert a persona name to a slug-safe persona_id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return slug or "persona"


def _validate_approval_window(
    task: PipelineTask,
    expected_stage: str,
) -> None:
    """Validate that a task is in the correct HITL window for approval.

    Raises HTTPException(409) if the task is not awaiting approval
    or is at the wrong HITL stage.
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


def _ap_should_guard(
    artifacts_root: Path,
    effective_slug: str,
    slug: str,
    *,
    backend: Optional[Any] = None,
) -> tuple[bool, Optional[str]]:
    """Check whether the AP guard should block a new run.

    Returns (should_guard, message).

    Guard only blocks when approved personas (fresh|stale) exist AND
    the KB hasn't been updated since the last AP run.
    """
    storage = PersonaStorage(artifacts_root, effective_slug, backend=backend)
    manifest = storage.read_manifest()

    # Count approved personas (only fresh|stale count)
    approved_count = sum(
        1 for entry in manifest.personas.values()
        if entry.status in ("fresh", "stale")
    )
    if approved_count == 0:
        return False, None

    # Check KB staleness: if KB synthesis_version > AP's kb_synthesis_version → run
    from core.research.knowledge_base.storage import KBStorage
    kb_storage = KBStorage(artifacts_root, effective_slug, backend=backend)
    kb_manifest = kb_storage.read_manifest()
    kb_synth_version = kb_manifest.synthesis_version
    ap_synth_version = manifest.kb_synthesis_version or 0
    if kb_synth_version > ap_synth_version:
        return False, None

    return True, (
        f"Audience personas already exist ({approved_count} approved). "
        "Pass force_rerun=true to re-run."
    )


# ── Endpoint 1: POST /start ──────────────────────────────────────────


@router.post(
    "/start",
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "Personas already exist"}},
)
async def start_audience_persona(
    body: AudiencePersonaStartRequest,
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

    # Guard: check if approved personas already exist
    _storage_backend = getattr(http_request.app.state, "storage_backend", None)
    if not body.force_rerun:
        should_guard, message = _ap_should_guard(artifacts_root, effective_slug, slug, backend=_storage_backend)
        if should_guard:
            response.status_code = 200
            await log_pipeline_launch(
                user_id=_user.id,
                pipeline="audience_persona",
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
                pipeline="audience_persona",
                company_slug=slug,
                product_slug=body.product_slug,
                effective_slug=effective_slug,
                status="already_exists",
                created_at=datetime.now(timezone.utc),
                already_exists=True,
                message=message or "",
            )

    task = task_store.create_task("audience_persona", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_audience_persona_pipeline_task(
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
        pipeline="audience_persona",
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
        pipeline="audience_persona",
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


# ── Endpoint 2: GET /{run_id}/status ─────────────────────────────────


@router.get("/{run_id}/status")
def get_audience_persona_status(
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


# ── Endpoint 3: POST /{run_id}/approve/briefs (HITL-1) ──────────────


@router.post("/{run_id}/approve/briefs")
async def approve_briefs(
    run_id: str,
    body: PersonaBriefApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseAP:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_approval_window(task, "persona_brief_review")

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    approval_data = {
        "batch_decision": body.batch_decision,
        "brief_reviews": [r.model_dump(mode="json") for r in body.brief_reviews],
        "added_briefs": [b.model_dump(mode="json") for b in body.added_briefs],
    }

    try:
        task_store.submit_approval(
            run_id,
            decision=body.batch_decision,
            stage="persona_brief_review",
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="audience_persona",
            stage="persona_brief_review",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="audience_persona",
        stage="persona_brief_review",
        decision=body.batch_decision,
        company_slug=user_company_slug,
        detail={"brief_count": len(body.brief_reviews), "added_count": len(body.added_briefs)},
    )

    return ApprovalResponseAP(
        status="accepted",
        stage="persona_brief_review",
        message=f"Brief approval submitted: {body.batch_decision}",
    )


# ── Endpoint 4: POST /{run_id}/approve/profiles (HITL-2) ────────────


@router.post("/{run_id}/approve/profiles")
async def approve_profiles(
    run_id: str,
    body: PersonaProfileApprovalRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> ApprovalResponseAP:
    task = task_store.get_task(run_id)
    user_company_slug = getattr(http_request.state, "company_slug", None)
    if task.company_slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_approval_window(task, "persona_profile_review")

    nonce = (task.approval_payload or {}).get("checkpoint_nonce")

    approval_data = {
        "profile_reviews": [r.model_dump(mode="json") for r in body.profile_reviews],
    }

    try:
        task_store.submit_approval(
            run_id,
            decision="profile_review",
            stage="persona_profile_review",
            approval_data=approval_data,
            expected_nonce=nonce,
        )
    except ApprovalWindowError as exc:
        await log_hitl_decision(
            user_id=_user.id,
            run_id=run_id,
            pipeline="audience_persona",
            stage="persona_profile_review",
            decision="rejected",
            company_slug=user_company_slug,
            detail={"reason": str(exc)},
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_hitl_decision(
        user_id=_user.id,
        run_id=run_id,
        pipeline="audience_persona",
        stage="persona_profile_review",
        decision="profile_review",
        company_slug=user_company_slug,
        detail={"profile_count": len(body.profile_reviews)},
    )

    return ApprovalResponseAP(
        status="accepted",
        stage="persona_profile_review",
        message="Profile approval submitted",
    )


# ── Endpoint 5: POST /{slug}/add-persona (standalone) ────────────────


@router.post("/{slug}/add-persona", status_code=202)
async def add_persona(
    slug: str,
    body: ManualPersonaBriefRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> Dict[str, Any]:
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    if not _SAFE_SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")

    # Generate persona_id from slugified name
    persona_id = _slugify_persona_name(body.persona_name)

    # Collision check — append suffix if needed
    storage = PersonaStorage(artifacts_root, slug)
    existing_ids = set(storage.list_persona_ids())
    if persona_id in existing_ids:
        import uuid as _uuid
        persona_id = f"{persona_id}-{_uuid.uuid4().hex[:6]}"

    # Write brief to storage
    brief = PersonaBrief(
        brief_id=f"pb-manual-{persona_id}",
        persona_name=body.persona_name,
        tagline=body.tagline,
        description=body.description,
        rationale=body.rationale,
        source="manual",
    )
    storage.write_brief(persona_id, brief)

    # Managed task lifecycle
    task = task_store.create_task("audience_persona", slug)

    handle = asyncio.create_task(
        run_single_persona_generator_task(
            task_id=task.task_id,
            persona_id=persona_id,
            slug=slug,
            task_store=task_store,
            event_bus=event_bus,
            artifacts_root=artifacts_root,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return {
        "persona_id": persona_id,
        "task_id": task.task_id,
    }


# ── Endpoint 6: POST /{slug}/personas/{persona_id}/approve ───────────


@router.post("/{slug}/personas/{persona_id}/approve")
async def standalone_approve_persona(
    slug: str,
    persona_id: str,
    body: StandaloneApproveRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> Dict[str, str]:
    user_company_slug: Optional[str] = getattr(http_request.state, "company_slug", None)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    storage = PersonaStorage(artifacts_root, slug)
    manifest = storage.read_manifest()

    entry = manifest.personas.get(persona_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

    if entry.status != "pending_review":
        raise HTTPException(
            status_code=409,
            detail=f"Persona '{persona_id}' is not pending review (current: {entry.status})",
        )

    new_status = "fresh" if body.decision == "approve" else "archived"
    storage.mark_persona_status(persona_id, new_status)

    await log_hitl_decision(
        user_id=_user.id,
        run_id=persona_id,
        pipeline="audience_persona",
        stage="standalone_persona_approval",
        decision=body.decision,
        company_slug=slug,
    )

    return {"persona_id": persona_id, "status": new_status}


# ── Endpoint 7: GET /{slug}/personas (list) ──────────────────────────


@router.get("/{slug}/personas")
async def list_personas(
    slug: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    persona_svc=Depends(get_persona_data_service),
) -> PersonaListResponse:
    user_company_slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    personas = await persona_svc.list_personas(slug)
    items = [PersonaListItem.model_validate(p) for p in personas]
    return PersonaListResponse(slug=slug, personas=items, total=len(items))
