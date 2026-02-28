"""Site audit pipeline API endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from api.auth.dependencies import require_auth, require_role, require_tenant
from api.dependencies import (
    get_artifacts_root,
    get_auth_service,
    get_event_bus,
    get_site_audit_data_service,
    get_task_store,
)
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.site_audit import (
    AuditDetailResponse,
    AuditFindingsResponse,
    AuditPageResultsResponse,
    AuditSummaryResponse,
    SiteAuditStartRequest,
)
from api.tasks.event_bus import EventBus
from api.tasks.models import PipelineTask
from api.tasks.runner import run_site_audit_task
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.organization import UserProfile
from core.services.site_audit_data import SiteAuditDataServiceProtocol
from core.services.task_store import TaskStoreProtocol

router = APIRouter(prefix="/api/v1/site-audit", tags=["site-audit"])


def _derive_slug(company_name: str) -> str:
    """Derive a URL slug from a company name."""
    return derive_slug(company_name)


def _site_audit_artifacts_exist(
    artifacts_root: Path, effective_slug: str, domain: str
) -> bool:
    """True if a completed audit_result.json exists for this slug + domain.

    Checks the site_audit/{effective_slug}/ directory for any sub-directory
    that contains a completed audit_result.json whose domain matches.
    """
    d = artifacts_root / "site_audit" / effective_slug
    if not d.exists():
        return False
    for sub in d.iterdir():
        if not sub.is_dir():
            continue
        result_file = sub / "audit_result.json"
        if result_file.exists():
            import json

            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                if (
                    data.get("status") == "completed"
                    and data.get("domain") == domain
                ):
                    return True
            except Exception:
                continue
    return False


def _get_latest_audit_run(
    task_store: TaskStoreProtocol,
    slug: str,
    product_slug: Optional[str],
) -> Optional[PipelineTask]:
    """Return the most-recent completed site_audit task for this scope."""
    tasks = [
        t
        for t in task_store.list_tasks(pipeline="site_audit", company_slug=slug)
        if t.product_slug == product_slug and t.status.value == "completed"
    ]
    return max(tasks, key=lambda t: t.created_at) if tasks else None


@router.post(
    "/start",
    response_model=PipelineRunResponse,
    status_code=202,
    responses={200: {"model": PipelineRunResponse, "description": "Audit already exists"}},
)
async def start_site_audit(
    body: SiteAuditStartRequest,
    response: Response,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBus = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineRunResponse:
    """Start the site audit pipeline for a company domain.

    Args:
        body: Audit configuration including company_name, domain, and options.
        response: FastAPI response object (used to set 200 status for guard).
        request: FastAPI request (used to extract company_slug from middleware state).
        _user: Authenticated user with member or superuser role.
        task_store: Task persistence store.
        event_bus: SSE event bus.
        artifacts_root: Filesystem artifacts root.
        auth_service: Auth service for tenant and product lookups.

    Returns:
        202 PipelineRunResponse when a new audit is launched.
        200 PipelineRunResponse with already_exists=True when guard fires.

    Raises:
        HTTPException(403): When the request is for a different tenant.
        HTTPException(409): When a site_audit run is already in progress for this slug.
    """
    # Tenant isolation: slug derived from company_name must match the token's company_slug
    user_company_slug: Optional[str] = getattr(request.state, "company_slug", None)
    slug = _derive_slug(body.company_name)
    if not user_company_slug or slug != user_company_slug:
        raise HTTPException(
            status_code=403,
            detail="Cannot start pipeline for another company",
        )

    effective_slug = f"{slug}__{body.product_slug}" if body.product_slug else slug

    # Force-rerun guard: return 200 when a completed audit already exists
    if not body.force_rerun and _site_audit_artifacts_exist(
        artifacts_root, effective_slug, body.domain
    ):
        last_task = _get_latest_audit_run(task_store, slug, body.product_slug)
        response.status_code = 200
        return PipelineRunResponse(
            run_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            pipeline="site_audit",
            company_slug=slug,
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=last_task.created_at if last_task else datetime.now(timezone.utc),
            already_exists=True,
            message="Audit already exists. Pass force_rerun=true to re-run.",
        )

    # Slug lock: create_task raises TaskConflictError (→ 409) if already running
    task = task_store.create_task("site_audit", slug, product_slug=body.product_slug)

    handle = asyncio.create_task(
        run_site_audit_task(
            task_id=task.task_id,
            request=body,
            artifacts_root=artifacts_root,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=auth_service,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        product_slug=task.product_slug,
        effective_slug=task.effective_slug,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/status/{run_id}", response_model=TaskResponse)
async def get_site_audit_status(
    run_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    task_store: TaskStoreProtocol = Depends(get_task_store),
) -> TaskResponse:
    """Poll the status of a running or completed site audit task.

    Args:
        run_id: The task UUID returned by POST /start.
        request: FastAPI request (used to extract company_slug).
        _user: Authenticated user.
        task_store: Task persistence store.

    Returns:
        TaskResponse with current status, progress, and result.

    Raises:
        HTTPException(404): When the task_id does not exist.
        HTTPException(403): When the task belongs to a different tenant.
    """
    task = task_store.get_task(run_id)
    user_company_slug: Optional[str] = getattr(request.state, "company_slug", None)
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
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
        approval_payload=task.approval_payload,
    )


@router.get("/companies/{slug}/audits", response_model=list[AuditSummaryResponse])
async def list_audits(
    slug: str,
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    audit_service: SiteAuditDataServiceProtocol = Depends(get_site_audit_data_service),
    _access: UserProfile = Depends(require_tenant),
) -> list[AuditSummaryResponse]:
    """List all site audits for a company, most recent first.

    Args:
        slug: Company URL slug (verified against authenticated user's tenant).
        limit: Maximum number of audits to return (default 20, max 100).
        audit_service: Site audit data service.
        _access: Tenant access check (verified that slug matches user's company).

    Returns:
        List of AuditSummaryResponse items, newest first.
    """
    audits = await audit_service.list_audits(slug, limit=limit)
    return [AuditSummaryResponse.model_validate(a) for a in audits]


@router.get("/companies/{slug}/audits/{audit_id}", response_model=AuditDetailResponse)
async def get_audit_detail(
    slug: str,
    audit_id: str,
    audit_service: SiteAuditDataServiceProtocol = Depends(get_site_audit_data_service),
    _access: UserProfile = Depends(require_tenant),
) -> AuditDetailResponse:
    """Get full detail for a single site audit run.

    Args:
        slug: Company URL slug.
        audit_id: Audit run identifier (UUID string).
        audit_service: Site audit data service.
        _access: Tenant access check.

    Returns:
        AuditDetailResponse with scores, dimension breakdown, and metadata.

    Raises:
        HTTPException(404): When the audit does not exist on disk.
    """
    data = await audit_service.get_audit_detail(slug, audit_id)
    return AuditDetailResponse.model_validate(data)


@router.get(
    "/companies/{slug}/audits/{audit_id}/findings",
    response_model=AuditFindingsResponse,
)
async def get_audit_findings(
    slug: str,
    audit_id: str,
    severity: Optional[str] = Query(
        None,
        description="Filter by severity: critical, high, medium, low, info",
    ),
    dimension: Optional[str] = Query(
        None,
        description=(
            "Filter by dimension: crawlability, performance, on_page_seo, "
            "extractability, schema_markup, eeat, freshness, security"
        ),
    ),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    audit_service: SiteAuditDataServiceProtocol = Depends(get_site_audit_data_service),
    _access: UserProfile = Depends(require_tenant),
) -> AuditFindingsResponse:
    """Get paginated findings for a site audit, with optional severity/dimension filters.

    Args:
        slug: Company URL slug.
        audit_id: Audit run identifier.
        severity: Optional severity filter.
        dimension: Optional dimension filter.
        page: 1-based page number.
        page_size: Findings per page (max 200).
        audit_service: Site audit data service.
        _access: Tenant access check.

    Returns:
        AuditFindingsResponse with paginated findings.

    Raises:
        HTTPException(404): When the audit does not exist on disk.
    """
    data = await audit_service.get_findings(
        slug,
        audit_id,
        severity=severity,
        dimension=dimension,
        page=page,
        page_size=page_size,
    )
    return AuditFindingsResponse.model_validate(data)


@router.get(
    "/companies/{slug}/audits/{audit_id}/pages",
    response_model=AuditPageResultsResponse,
)
async def get_audit_pages(
    slug: str,
    audit_id: str,
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    audit_service: SiteAuditDataServiceProtocol = Depends(get_site_audit_data_service),
    _access: UserProfile = Depends(require_tenant),
) -> AuditPageResultsResponse:
    """Get paginated per-page results for a site audit.

    Args:
        slug: Company URL slug.
        audit_id: Audit run identifier.
        page: 1-based page number.
        page_size: Pages per response page (max 200).
        audit_service: Site audit data service.
        _access: Tenant access check.

    Returns:
        AuditPageResultsResponse with paginated per-page results.

    Raises:
        HTTPException(404): When the audit does not exist on disk.
    """
    data = await audit_service.get_page_results(
        slug,
        audit_id,
        page=page,
        page_size=page_size,
    )
    return AuditPageResultsResponse.model_validate(data)
