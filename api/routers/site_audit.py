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
    get_workspace_service,
)
from api.schemas.common import PipelineRunResponse, TaskResponse
from api.schemas.site_audit import (
    AuditDetailResponse,
    AuditFindingsResponse,
    AuditPageResultsResponse,
    AuditSummaryResponse,
    SiteAuditStartRequest,
)
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import PipelineTask
from api.routers._helpers import (
    assert_task_workspace_access,
    create_task_durable,
    resolve_workspace_scope,
)
from api.tasks.runner import run_site_audit_task
from core.audit import log_pipeline_launch
from core.auth.service import AuthServiceProtocol
from core.auth.utils.domain import derive_slug
from core.models.organization import UserProfile
from core.services.site_audit_data import SiteAuditDataServiceProtocol
from core.services.task_store import TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

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
                    data.get("status") in ("completed", "degraded")
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
    domain: Optional[str] = None,
) -> Optional[PipelineTask]:
    """Return the most-recent completed site_audit task for this scope.

    When *domain* is given, only tasks whose ``result.domain`` matches
    are considered — prevents returning a run_id for the wrong domain
    when the same slug has audits for multiple domains.
    """
    tasks = [
        t
        for t in task_store.list_tasks(pipeline="site_audit", company_slug=slug)
        if t.product_slug == product_slug
        and t.status.value == "completed"
        and (domain is None or (t.result or {}).get("domain") == domain)
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
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
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
    scope = await resolve_workspace_scope(
        request,
        _user,
        workspace_service,
        workspace_slug=body.workspace_slug,
        company_name=body.company_name,
        product_slug=body.product_slug,
        min_roles=("owner", "admin", "member"),
    )
    slug = scope.workspace_slug
    effective_slug = scope.effective_slug

    # Force-rerun guard: return 200 when a completed audit already exists
    # Filesystem check is sufficient — pipeline writes FS first, DB second
    if not body.force_rerun and _site_audit_artifacts_exist(
        artifacts_root, effective_slug, body.domain
    ):
        last_task = _get_latest_audit_run(task_store, slug, body.product_slug, domain=body.domain)
        response.status_code = 200
        await log_pipeline_launch(
            user_id=_user.id,
            pipeline="site_audit",
            company_slug=slug,
            task_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            detail={
                "outcome": "already_exists",
                "product_slug": body.product_slug,
                "effective_slug": effective_slug,
            },
        )
        return PipelineRunResponse(
            run_id=last_task.task_id if last_task else f"existing-{effective_slug}",
            pipeline="site_audit",
            company_slug=slug,
            workspace_id=scope.workspace_id,
            product_slug=body.product_slug,
            effective_slug=effective_slug,
            status="already_exists",
            created_at=last_task.created_at if last_task else datetime.now(timezone.utc),
            already_exists=True,
            message="Audit already exists. Pass force_rerun=true to re-run.",
        )

    # Slug lock: create_task raises TaskConflictError (→ 409) if already running
    task = await create_task_durable(
        task_store,
        "site_audit",
        slug,
        product_slug=body.product_slug,
        workspace_id=scope.workspace_id,
    )

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

    await log_pipeline_launch(
        user_id=_user.id,
        pipeline="site_audit",
        company_slug=slug,
        task_id=task.task_id,
        detail={
            "product_slug": body.product_slug,
            "domain": body.domain,
            "effective_slug": effective_slug,
        },
    )

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        workspace_id=scope.workspace_id,
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
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
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
    await assert_task_workspace_access(task, _user, workspace_service)
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
