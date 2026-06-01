"""FastAPI auth dependencies — authentication, role, and tenant authorization.

Dependency chain (Codex I1):
  require_auth → require_role → require_company_access / require_workspace_access

Middleware handles authentication (identity extraction + default-deny).
Dependencies handle authorization (permissions + tenant scoping).
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from fastapi import Depends, HTTPException, Request

from api.dependencies import get_auth_service, get_workspace_service
from core.auth.service import AuthServiceProtocol
from core.models.organization import Company, UserProfile
from core.models.workspace import Workspace, WorkspaceMembership
from core.services.workspace_protocol import WorkspaceServiceProtocol

_WRITE_MEMBERSHIP_ROLES = frozenset({"owner", "admin", "member"})


async def require_auth(
    request: Request,
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> UserProfile:
    """Return the authenticated user or raise 401.

    Reads ``request.state.user_id`` (set by ASGI AuthMiddleware),
    resolves the full user profile from the service, and checks
    ``is_active``.  Every protected endpoint should depend on this.
    """
    user_id: Optional[str] = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = await auth_service.get_user_by_id(user_id)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Build UserProfile without password_hash
    profile = UserProfile.model_validate(
        {k: v for k, v in user_data.items() if k != "password_hash"}
    )

    if not profile.is_active:
        raise HTTPException(
            status_code=401,
            detail="Account deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return profile


def require_role(*allowed_roles: str) -> Callable[..., UserProfile]:
    """Dependency factory: returns a dependency that checks the user role.

    Usage::

        user = Depends(require_role("member", "superuser"))
    """

    async def _check_role(
        user: UserProfile = Depends(require_auth),
    ) -> UserProfile:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}",
            )
        return user

    return _check_role


async def require_tenant(
    slug: str,
    request: Request,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> UserProfile:
    """Lightweight tenant check for data-read endpoints.

    Verifies active workspace membership for the URL slug. Legacy
    single-company users still pass via company_id fallback in the service.
    """
    try:
        await workspace_service.assert_workspace_access(slug, user)
    except ValueError as exc:
        if str(exc) == "workspace_not_found":
            raise HTTPException(status_code=404, detail=f"Workspace '{slug}' not found")
        raise HTTPException(status_code=403, detail="Access denied")
    return user


async def require_workspace_member(
    workspace_slug: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> Tuple[UserProfile, Workspace, WorkspaceMembership]:
    """Verify the user has active membership in the requested workspace."""
    try:
        workspace, membership = await workspace_service.assert_workspace_access(
            workspace_slug, user
        )
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(
                status_code=404, detail=f"Workspace '{workspace_slug}' not found"
            )
        raise HTTPException(status_code=403, detail="Access denied")
    return user, workspace, membership


async def require_company_access(
    slug: str,
    user: UserProfile = Depends(require_auth),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> Tuple[UserProfile, Company]:
    """Verify the authenticated user belongs to the company identified by *slug*.

    Uses workspace membership as the authorization boundary while still
    returning the legacy Company object for existing write endpoints.
    """
    try:
        await workspace_service.assert_workspace_access(slug, user)
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")
        raise HTTPException(status_code=403, detail="Access denied")

    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    return user, company


async def require_company_member(
    slug: str,
    user: UserProfile = Depends(require_auth),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
) -> Tuple[UserProfile, Company]:
    """Like ``require_company_access`` but also requires workspace write access.

    Authorizes via workspace membership roles (owner, admin, member). Legacy
    JWT ``user.role`` is not used when an active membership row exists.
    """
    try:
        _workspace, membership = await workspace_service.assert_workspace_access(
            slug, user, min_roles=tuple(_WRITE_MEMBERSHIP_ROLES)
        )
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")
        raise HTTPException(status_code=403, detail="Access denied")

    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    return user, company
