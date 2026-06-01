"""Shared helpers for router endpoints."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request

from core.auth.utils.domain import derive_slug
from core.models.organization import UserProfile
from core.models.workspace import Workspace, WorkspaceMembership
from core.services.workspace_protocol import WorkspaceServiceProtocol
from api.tasks.models import PipelineTask
from core.services.task_store import TaskStoreProtocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkspaceRequestScope:
    """Resolved workspace tenant scope for API route handlers."""

    workspace: Workspace
    membership: WorkspaceMembership
    workspace_slug: str
    workspace_id: str
    company_id: str
    product_slug: Optional[str]
    effective_slug: str


def _workspace_slug_from_effective_slug(effective_slug: str) -> str:
    return effective_slug.split("__", 1)[0]


def _http_from_workspace_error(slug: str, exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in {"workspace_not_found", "access_denied", "insufficient_role"}:
        return HTTPException(status_code=403, detail="Access denied")
    return HTTPException(status_code=400, detail=code)


async def resolve_workspace_scope(
    request: Request,
    user: UserProfile,
    workspace_service: WorkspaceServiceProtocol,
    *,
    workspace_slug: Optional[str] = None,
    company_name: Optional[str] = None,
    effective_slug: Optional[str] = None,
    product_slug: Optional[str] = None,
    min_roles: Optional[tuple[str, ...]] = None,
) -> WorkspaceRequestScope:
    """Resolve and authorize the requested workspace.

    New clients should send ``workspace_slug``. Legacy clients still work by
    deriving the slug from ``company_name`` or, as a final fallback, the token's
    legacy company slug.
    """
    requested_slug = (workspace_slug or "").strip()
    if not requested_slug and effective_slug:
        requested_slug = _workspace_slug_from_effective_slug(effective_slug)
    if not requested_slug and company_name:
        requested_slug = derive_slug(company_name)
    if not requested_slug:
        requested_slug = getattr(request.state, "company_slug", None) or ""
    if not requested_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        workspace, membership = await workspace_service.assert_workspace_access(
            requested_slug,
            user,
            min_roles=min_roles,
        )
    except ValueError as exc:
        raise _http_from_workspace_error(requested_slug, exc) from exc

    resolved_effective = effective_slug or (
        f"{workspace.slug}__{product_slug}" if product_slug else workspace.slug
    )
    return WorkspaceRequestScope(
        workspace=workspace,
        membership=membership,
        workspace_slug=workspace.slug,
        workspace_id=workspace.id,
        company_id=workspace.company_id,
        product_slug=product_slug,
        effective_slug=resolved_effective,
    )


async def assert_task_workspace_access(
    task: PipelineTask,
    user: UserProfile,
    workspace_service: WorkspaceServiceProtocol,
    *,
    min_roles: Optional[tuple[str, ...]] = None,
) -> tuple[Workspace, WorkspaceMembership]:
    """Authorize access to a task using its workspace slug."""
    workspace_slug = task.company_slug
    if not workspace_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        return await workspace_service.assert_workspace_access(
            workspace_slug,
            user,
            min_roles=min_roles,
        )
    except ValueError as exc:
        raise _http_from_workspace_error(workspace_slug, exc) from exc


def authoritative_company_fields(
    scope: WorkspaceRequestScope,
    *,
    company_name: Optional[str] = None,
    domain: Optional[str] = None,
) -> dict[str, str]:
    """Prefer workspace metadata over stale client-supplied company fields."""
    resolved_name = (scope.workspace.name or "").strip() or company_name or scope.workspace_slug
    resolved_domain = (scope.workspace.primary_domain or "").strip() or domain or ""
    fields: dict[str, str] = {"company_name": resolved_name}
    if resolved_domain:
        fields["domain"] = resolved_domain
    return fields


async def assert_slug_workspace_access(
    slug: str,
    user: UserProfile,
    workspace_service: WorkspaceServiceProtocol,
    *,
    min_roles: Optional[tuple[str, ...]] = None,
) -> tuple[Workspace, WorkspaceMembership]:
    """Authorize an effective slug by checking access to its workspace slug."""
    workspace_slug = _workspace_slug_from_effective_slug(slug)
    if not workspace_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        return await workspace_service.assert_workspace_access(
            workspace_slug,
            user,
            min_roles=min_roles,
        )
    except ValueError as exc:
        raise _http_from_workspace_error(workspace_slug, exc) from exc


async def create_task_durable(
    task_store: TaskStoreProtocol,
    pipeline: str,
    company_slug: str,
    product_slug: Optional[str] = None,
    allow_parallel: bool = False,
    workspace_id: Optional[str] = None,
) -> PipelineTask:
    """Create task + await DB persistence. Rolls back on failure (HTTP 503).

    Wraps ``task_store.create_task()`` + ``task_store.ensure_created()``
    into a single durable operation. If the DB INSERT fails, cleans up
    the in-memory state and raises HTTP 503.
    """
    task = task_store.create_task(
        pipeline,
        company_slug,
        product_slug,
        allow_parallel,
        workspace_id=workspace_id,
    )
    try:
        await task_store.ensure_created(task.task_id)
    except Exception:
        logger.exception(
            "Task persistence failed for %s:%s — rolling back",
            pipeline, company_slug,
        )
        if hasattr(task_store, "rollback_create"):
            task_store.rollback_create(task.task_id)
        raise HTTPException(
            status_code=503,
            detail="Task persistence failed — retry later",
        )
    return task
