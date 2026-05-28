"""Content-to-Prompt API endpoints.

Generates AI visibility tracking prompts from content inventory pages,
deduplicates against existing prompts, and links them for per-page analytics.

Auth: All endpoints require authentication + tenant isolation.
Write operations require ``member`` or ``superuser`` role.

6 endpoints:
  POST   /generate             Generate prompts for specified pages (async)
  GET    /pages/{id}/prompts   List prompts linked to a page
  GET    /pages/{id}/metrics   Per-page aggregated visibility metrics
  GET    /pending              List pending (unapproved) prompts
  POST   /approve              Bulk approve pending prompts
  POST   /regenerate/{id}      Re-generate prompts for a changed page (async)
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_auth_service
from api.schemas.content_to_prompt import (
    ApprovePromptsRequest,
    ApprovePromptsResponse,
    GeneratePromptsRequest,
    GeneratePromptsResponse,
    LinkedPromptItem,
    PageMetricsResponse,
    PagePromptsResponse,
    PendingPromptItem,
    PendingPromptsResponse,
)
from core.auth.service import AuthServiceProtocol
from core.models.organization import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content-to-prompt", tags=["content-to-prompt"])


# ── Helpers ───────────────────────────────────────────────────────────


def _get_company_slug(request: Request) -> str:
    slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return slug


async def _resolve_company_uuid(
    request: Request,
    auth_service: AuthServiceProtocol,
) -> _uuid.UUID:
    """Resolve company UUID from auth context. Raises 404 if not found."""
    slug = _get_company_slug(request)
    company = await auth_service.get_company_by_slug(slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company.id


async def _get_repos(request: Request) -> dict[str, Any]:
    """Build repositories from DB session factory.  Raises 503 if no DB."""
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        raise HTTPException(
            status_code=503,
            detail="Content-to-Prompt requires database — set DATABASE_URL",
        )

    session = sf()

    from core.db.repositories.content_inventory_prompt_repo import (
        ContentInventoryPromptRepository,
    )
    from core.db.repositories.content_inventory_repo import ContentInventoryRepository
    from core.db.repositories.daily_tracker_repo import TrackedPromptRepository

    return {
        "session": session,
        "link_repo": ContentInventoryPromptRepository(session),
        "prompt_repo": TrackedPromptRepository(session),
        "inventory_repo": ContentInventoryRepository(session),
    }


# ── POST /generate ────────────────────────────────────────────────────


@router.post(
    "/generate",
    response_model=GeneratePromptsResponse,
    status_code=202,
)
async def generate_prompts(
    body: GeneratePromptsRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> GeneratePromptsResponse:
    """Generate AI visibility prompts for specified content inventory pages.

    Validates page ownership via company_uuid before generation.
    """
    company_slug = _get_company_slug(request)
    company_uuid = await _resolve_company_uuid(request, auth_service)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        from core.daily_tracker.content_to_prompt import ContentToPromptService
        from core.daily_tracker.content_to_prompt_orchestrator import (
            ContentToPromptOrchestrator,
        )

        generator = ContentToPromptService()
        orchestrator = ContentToPromptOrchestrator(
            generator=generator,
            prompt_repo=repos["prompt_repo"],
            link_repo=repos["link_repo"],
            inventory_repo=repos["inventory_repo"],
        )

        page_ids = [_uuid.UUID(pid) for pid in body.page_ids]
        auto_approve = body.auto_approve if body.auto_approve is not None else True

        result = await orchestrator.run_for_pages(
            company_id=company_slug,
            company_uuid=company_uuid,
            page_ids=page_ids,
            brand_name=body.brand_name or company_slug,
            brand_category=body.brand_category or "",
            competitors=body.competitors,
            k=body.k,
            auto_approve=auto_approve,
        )

        await session.commit()

        return GeneratePromptsResponse(
            generation_run_id=result.generation_run_id,
            pages_processed=result.pages_processed,
            pages_succeeded=result.pages_succeeded,
            pages_failed=result.pages_failed,
            prompts_created=result.prompts_created,
            prompts_deduplicated=result.prompts_deduplicated,
            errors=result.errors,
        )
    except Exception as exc:
        await session.rollback()
        logger.exception("Content-to-prompt generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await session.close()


# ── POST /generate-new ─────────────────────────────────────────────────


@router.post(
    "/generate-new",
    response_model=GeneratePromptsResponse,
    status_code=202,
)
async def generate_prompts_for_new_pages(
    request: Request,
    k: int = 6,
    auto_approve: bool = True,
    brand_name: str | None = None,
    brand_category: str | None = None,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> GeneratePromptsResponse:
    """Generate prompts for all content inventory pages that have NO prompts yet.

    Automatically finds pages without linked prompts and generates k prompts
    for each.  Called after CMS sync to process only newly added pages.
    Returns empty result if all pages already have prompts.
    """
    company_slug = _get_company_slug(request)
    company_uuid = await _resolve_company_uuid(request, auth_service)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        # Find pages without any linked prompts
        new_page_ids = await repos["link_repo"].get_pages_without_prompts(
            company_uuid, limit=500,
        )

        if not new_page_ids:
            return GeneratePromptsResponse(
                generation_run_id="",
                pages_processed=0,
            )

        from core.daily_tracker.content_to_prompt import ContentToPromptService
        from core.daily_tracker.content_to_prompt_orchestrator import (
            ContentToPromptOrchestrator,
        )

        generator = ContentToPromptService()
        orchestrator = ContentToPromptOrchestrator(
            generator=generator,
            prompt_repo=repos["prompt_repo"],
            link_repo=repos["link_repo"],
            inventory_repo=repos["inventory_repo"],
        )

        result = await orchestrator.run_for_pages(
            company_id=company_slug,
            company_uuid=company_uuid,
            page_ids=new_page_ids,
            brand_name=brand_name or company_slug,
            brand_category=brand_category or "",
            k=k,
            auto_approve=auto_approve,
        )

        await session.commit()

        return GeneratePromptsResponse(
            generation_run_id=result.generation_run_id,
            pages_processed=result.pages_processed,
            pages_succeeded=result.pages_succeeded,
            pages_failed=result.pages_failed,
            prompts_created=result.prompts_created,
            prompts_deduplicated=result.prompts_deduplicated,
            errors=result.errors,
        )
    except Exception as exc:
        await session.rollback()
        logger.exception("Content-to-prompt generate-new failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await session.close()


# ── GET /pages/{id}/prompts ───────────────────────────────────────────


@router.get("/pages/{inventory_id}/prompts", response_model=PagePromptsResponse)
async def get_page_prompts(
    inventory_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PagePromptsResponse:
    """List all tracked prompts linked to a content inventory page."""
    company_uuid = await _resolve_company_uuid(request, auth_service)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        inv_uuid = _uuid.UUID(inventory_id)

        # Tenant isolation: verify page belongs to company
        page = await repos["inventory_repo"].get_by_id(inv_uuid)
        if page is None or page.company_id != company_uuid:
            raise HTTPException(status_code=404, detail="Page not found")

        links = await repos["link_repo"].get_prompts_for_page(inv_uuid)

        items: list[LinkedPromptItem] = []
        for link in links:
            prompt = await repos["prompt_repo"].get_by_id(link.tracked_prompt_id)
            if prompt is None:
                continue
            items.append(LinkedPromptItem(
                link_id=str(link.id),
                prompt_id=str(link.tracked_prompt_id),
                text=prompt.text or "",
                buyer_stage=link.buyer_stage,
                intent_type=link.intent_type,
                is_branded=link.is_branded,
                approved=link.approved,
                is_user_edited=link.is_user_edited,
                active=prompt.active,
                category=prompt.category,
                source=prompt.source or "",
                created_at=prompt.created_at,
            ))

        return PagePromptsResponse(
            inventory_id=inventory_id,
            prompts=items,
            total=len(items),
        )
    finally:
        await session.close()


# ── GET /pages/{id}/metrics ──────────────────────────────────────────


@router.get("/pages/{inventory_id}/metrics", response_model=PageMetricsResponse)
async def get_page_metrics(
    inventory_id: str,
    request: Request,
    days: int = 30,
    _user: UserProfile = Depends(require_auth),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PageMetricsResponse:
    """Get aggregated visibility metrics for a content inventory page."""
    company_uuid = await _resolve_company_uuid(request, auth_service)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        inv_uuid = _uuid.UUID(inventory_id)

        # Tenant isolation
        page = await repos["inventory_repo"].get_by_id(inv_uuid)
        if page is None or page.company_id != company_uuid:
            raise HTTPException(status_code=404, detail="Page not found")

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        metrics = await repos["link_repo"].get_page_metrics(
            inv_uuid, start, now,
        )

        return PageMetricsResponse(
            inventory_id=inventory_id,
            total_prompts=metrics["total_prompts"],
            active_prompts=metrics["active_prompts"],
            mention_rate=metrics["mention_rate"],
            citation_rate=metrics["citation_rate"],
            total_responses=metrics["total_responses"],
            by_buyer_stage=metrics["by_buyer_stage"],
        )
    finally:
        await session.close()


# ── GET /pending ─────────────────────────────────────────────────────


@router.get("/pending", response_model=PendingPromptsResponse)
async def get_pending_prompts(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    _user: UserProfile = Depends(require_auth),
) -> PendingPromptsResponse:
    """List prompts pending approval (auto_approve=False)."""
    company_slug = _get_company_slug(request)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        links = await repos["link_repo"].get_pending_by_slug(
            company_slug, limit=limit, offset=offset,
        )

        items: list[PendingPromptItem] = []
        for link in links:
            prompt = await repos["prompt_repo"].get_by_id(link.tracked_prompt_id)
            inv = await repos["inventory_repo"].get_by_id(link.content_inventory_id)
            items.append(PendingPromptItem(
                link_id=str(link.id),
                inventory_id=str(link.content_inventory_id),
                prompt_id=str(link.tracked_prompt_id),
                prompt_text=prompt.text if prompt else "",
                buyer_stage=link.buyer_stage,
                intent_type=link.intent_type,
                is_branded=link.is_branded,
                page_title=inv.title if inv else "",
                page_url=inv.url if inv else "",
            ))

        return PendingPromptsResponse(pending=items, total=len(items))
    finally:
        await session.close()


# ── POST /approve ────────────────────────────────────────────────────


@router.post("/approve", response_model=ApprovePromptsResponse)
async def approve_prompts(
    body: ApprovePromptsRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
) -> ApprovePromptsResponse:
    """Bulk approve pending prompts. Activates the linked tracked_prompts.

    Tenant isolation: validates each link belongs to the requesting
    company's content inventory before approving.
    """
    company_slug = _get_company_slug(request)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        link_ids = [_uuid.UUID(lid) for lid in body.link_ids]

        # Tenant isolation: verify all links belong to this company
        validated_ids: list[_uuid.UUID] = []
        prompt_ids_to_activate: list[_uuid.UUID] = []

        for lid in link_ids:
            link = await repos["link_repo"].get_by_id(lid)
            if link is None:
                continue
            # Check ownership via content_inventory.effective_slug
            inv = await repos["inventory_repo"].get_by_id(link.content_inventory_id)
            if inv is None or inv.effective_slug != company_slug:
                continue
            validated_ids.append(lid)
            prompt_ids_to_activate.append(link.tracked_prompt_id)

        approved = await repos["link_repo"].approve_links(validated_ids)

        # Activate the corresponding tracked prompts
        for prompt_id in prompt_ids_to_activate:
            await repos["prompt_repo"].update(prompt_id, active=True)

        await session.commit()
        return ApprovePromptsResponse(approved_count=approved)
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await session.close()


# ── POST /regenerate/{id} ────────────────────────────────────────────


@router.post(
    "/regenerate/{inventory_id}",
    response_model=GeneratePromptsResponse,
    status_code=202,
)
async def regenerate_prompts(
    inventory_id: str,
    request: Request,
    k: int = 6,
    brand_name: str | None = None,
    brand_category: str | None = None,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> GeneratePromptsResponse:
    """Re-generate prompts for a content inventory page.

    Validates page ownership. Deletes old non-user-edited links,
    deactivates orphaned prompts, and generates fresh prompts.
    """
    company_slug = _get_company_slug(request)
    company_uuid = await _resolve_company_uuid(request, auth_service)
    repos = await _get_repos(request)
    session = repos["session"]

    try:
        from core.daily_tracker.content_to_prompt import ContentToPromptService
        from core.daily_tracker.content_to_prompt_orchestrator import (
            ContentToPromptOrchestrator,
        )

        # Tenant isolation: verify page belongs to company
        inv_uuid = _uuid.UUID(inventory_id)
        page = await repos["inventory_repo"].get_by_id(inv_uuid)
        if page is None or page.company_id != company_uuid:
            raise HTTPException(status_code=404, detail="Page not found")

        generator = ContentToPromptService()
        orchestrator = ContentToPromptOrchestrator(
            generator=generator,
            prompt_repo=repos["prompt_repo"],
            link_repo=repos["link_repo"],
            inventory_repo=repos["inventory_repo"],
        )

        result = await orchestrator.regenerate_for_page(
            company_id=company_slug,
            company_uuid=company_uuid,
            page_id=inv_uuid,
            brand_name=brand_name or company_slug,
            brand_category=brand_category or "",
            k=k,
        )

        await session.commit()

        return GeneratePromptsResponse(
            generation_run_id=result.generation_run_id,
            pages_processed=result.pages_processed,
            pages_succeeded=result.pages_succeeded,
            pages_failed=result.pages_failed,
            prompts_created=result.prompts_created,
            prompts_deduplicated=result.prompts_deduplicated,
            errors=result.errors,
        )
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        logger.exception("Content-to-prompt regeneration failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await session.close()
