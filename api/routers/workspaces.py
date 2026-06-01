"""Workspace tenant API routes."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import require_auth, require_workspace_member
from api.dependencies import (
    get_artifacts_root,
    get_auth_service,
    get_storage_backend,
    get_task_store,
    get_workspace_service,
)
from api.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceMembersResponse,
    WorkspaceProfileResponse,
    WorkspaceUpdateRequest,
)
from core.auth.service import AuthServiceProtocol
from core.models.organization import UserProfile
from core.services.task_store import TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _to_detail(
    workspace: object, *, role: str
) -> WorkspaceDetailResponse:
    from core.models.workspace import Workspace

    assert isinstance(workspace, Workspace)
    return WorkspaceDetailResponse(
        id=workspace.id,
        slug=workspace.slug,
        name=workspace.name,
        primary_domain=workspace.primary_domain,
        additional_domains=workspace.additional_domains,
        industry=workspace.industry,
        color=workspace.color,
        logo_url=workspace.logo_url,
        avatar_key=workspace.avatar_key,
        description=workspace.description,
        settings_json=workspace.settings_json,
        role=role,
        is_archived=workspace.is_archived,
    )


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> WorkspaceListResponse:
    workspaces = await workspace_service.list_workspaces_for_user(user.id)
    return WorkspaceListResponse(workspaces=workspaces)


@router.post("", response_model=WorkspaceDetailResponse, status_code=201)
async def create_workspace(
    body: WorkspaceCreateRequest,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> WorkspaceDetailResponse:
    if body.slug and not _SLUG_PATTERN.match(body.slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    try:
        workspace = await workspace_service.create_workspace(
            user=user,
            name=body.name,
            primary_domain=body.primary_domain,
            slug=body.slug,
            industry=body.industry,
            color=body.color,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_detail(workspace, role="owner")


@router.get("/{workspace_slug}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_slug: str,
    access: tuple[UserProfile, object, object] = Depends(require_workspace_member),
) -> WorkspaceDetailResponse:
    _user, workspace, membership = access
    return _to_detail(workspace, role=membership.role)


@router.put("/{workspace_slug}", response_model=WorkspaceDetailResponse)
async def update_workspace(
    workspace_slug: str,
    body: WorkspaceUpdateRequest,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> WorkspaceDetailResponse:
    if not _SLUG_PATTERN.match(workspace_slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    try:
        workspace = await workspace_service.update_workspace(
            workspace_slug,
            user,
            **body.model_dump(exclude_unset=True),
        )
        membership = await workspace_service.get_active_membership(workspace_slug, user.id)
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        if code in ("access_denied", "insufficient_role"):
            raise HTTPException(status_code=403, detail="Access denied") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return _to_detail(workspace, role=membership.role if membership else "member")


@router.delete("/{workspace_slug}", response_model=WorkspaceDetailResponse)
async def archive_workspace(
    workspace_slug: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> WorkspaceDetailResponse:
    try:
        workspace = await workspace_service.archive_workspace(workspace_slug, user)
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        if code in ("access_denied", "insufficient_role"):
            raise HTTPException(status_code=403, detail="Access denied") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return _to_detail(workspace, role="owner")


@router.get("/{workspace_slug}/members", response_model=WorkspaceMembersResponse)
async def list_workspace_members(
    workspace_slug: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> WorkspaceMembersResponse:
    try:
        members = await workspace_service.list_members(workspace_slug, user)
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        if code == "access_denied":
            raise HTTPException(status_code=403, detail="Access denied") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return WorkspaceMembersResponse(members=members)


@router.get("/{workspace_slug}/profile", response_model=WorkspaceProfileResponse)
async def get_workspace_profile(
    workspace_slug: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    artifacts_root=Depends(get_artifacts_root),
    storage_backend=Depends(get_storage_backend),
) -> WorkspaceProfileResponse:
    try:
        profile = await workspace_service.get_profile(
            workspace_slug,
            user,
            auth_service=auth_service,
            artifacts_root=artifacts_root,
            storage_backend=storage_backend,
            task_store=task_store,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        if code == "access_denied":
            raise HTTPException(status_code=403, detail="Access denied") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return WorkspaceProfileResponse.model_validate(profile.model_dump(mode="json"))
