"""FastAPI auth dependencies — authentication, role, and tenant authorization.

Dependency chain (Codex I1):
  require_auth → require_role → require_company_access

Middleware handles authentication (identity extraction + default-deny).
Dependencies handle authorization (permissions + tenant scoping).
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from fastapi import Depends, HTTPException, Request

from api.dependencies import get_auth_service
from core.auth.service import AuthServiceProtocol
from core.models.organization import Company, UserProfile


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
    _user: UserProfile = Depends(require_auth),
) -> UserProfile:
    """Lightweight tenant check for data-read endpoints.

    Compares the URL ``slug`` against the authenticated user's
    ``company_slug`` from the token (set by middleware).
    No store lookup needed — suitable for high-volume read endpoints.
    Returns the authenticated user profile.
    """
    company_slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not company_slug or slug != company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return _user


async def require_company_access(
    slug: str,
    user: UserProfile = Depends(require_auth),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> Tuple[UserProfile, Company]:
    """Verify the authenticated user belongs to the company identified by *slug*.

    Uses ``company_id`` (UUID) for comparison, not slug strings (Codex I2).
    Returns ``(user, company)`` for convenience.
    Suitable for endpoints that need the Company object (write operations).
    """
    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    if user.company_id != company.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return user, company


async def require_company_member(
    slug: str,
    user: UserProfile = Depends(require_role("member", "superuser")),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> Tuple[UserProfile, Company]:
    """Like ``require_company_access`` but also requires member+ role.

    Combines role check and tenant check in one dependency for write endpoints.
    """
    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    if user.company_id != company.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return user, company
