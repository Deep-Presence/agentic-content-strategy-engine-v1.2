"""Company settings endpoints — team management, profile editing, pipeline defaults.

All endpoints are scoped under /api/v1/companies/{slug}/settings/.
"""
from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth.dependencies import require_role, require_tenant
from api.dependencies import get_auth_service
from api.schemas.settings import (
    CompanyProfileSettingsResponse,
    PipelineDefaultsResponse,
    TeamListResponse,
    TeamMemberResponse,
    UpdateCompanyProfileRequest,
    UpdatePipelineDefaultsRequest,
    UpdateUserRequest,
)
from core.auth.service import AuthServiceProtocol
from core.models.organization import Company, UserProfile

router = APIRouter(
    prefix="/api/v1/companies/{slug}/settings",
    tags=["settings"],
)


# ── Helpers ───────────────────────────────────────────────


async def _require_superuser_tenant(
    slug: str,
    request: Request,
    user: UserProfile = Depends(require_role("superuser")),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> Tuple[UserProfile, Company]:
    """Verify the user is a superuser and belongs to the company."""
    # Lightweight tenant check
    company_slug = getattr(request.state, "company_slug", None)
    if not company_slug or slug != company_slug:
        raise HTTPException(status_code=403, detail="Access denied")

    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    return user, company


# ── Phase 1A: Team Management ─────────────────────────────


@router.get("/team", response_model=TeamListResponse)
async def list_team(
    slug: str,
    _user: UserProfile = Depends(require_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> TeamListResponse:
    """List all team members for this company."""
    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    users = await auth_service.list_users_for_company(company.id)
    members = [
        TeamMemberResponse(
            id=u.id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]
    return TeamListResponse(members=members, total=len(members))


@router.put("/team/{user_id}", response_model=TeamMemberResponse)
async def update_team_member(
    slug: str,
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    su_company: Tuple[UserProfile, Company] = Depends(_require_superuser_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> TeamMemberResponse:
    """Update a team member's role, name, or active status.

    Only superusers can perform this operation.
    """
    su_user, company = su_company

    # Verify target user belongs to this company
    target = await auth_service.get_user_by_id(user_id)
    if not target or target.get("company_id") != company.id:
        raise HTTPException(status_code=404, detail="User not found in this company")

    update_fields = body.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = await auth_service.update_user(
            user_id,
            requesting_user_id=su_user.id,
            **update_fields,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TeamMemberResponse(
        id=updated.id,
        email=updated.email,
        first_name=updated.first_name,
        last_name=updated.last_name,
        role=updated.role,
        is_active=updated.is_active,
        created_at=updated.created_at,
    )


# ── Phase 1B: Company Profile ─────────────────────────────


@router.get("/profile", response_model=CompanyProfileSettingsResponse)
async def get_profile(
    slug: str,
    _user: UserProfile = Depends(require_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> CompanyProfileSettingsResponse:
    """Get company profile settings."""
    company = await auth_service.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{slug}' not found")

    return CompanyProfileSettingsResponse(
        slug=company.slug,
        name=company.name,
        domain=company.domain,
        additional_domains=company.additional_domains,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.put("/profile", response_model=CompanyProfileSettingsResponse)
async def update_profile(
    slug: str,
    body: UpdateCompanyProfileRequest,
    su_company: Tuple[UserProfile, Company] = Depends(_require_superuser_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> CompanyProfileSettingsResponse:
    """Update company profile settings. Superuser only."""
    _, company = su_company

    update_fields = body.model_dump(exclude_none=True)
    if update_fields:
        try:
            company = await auth_service.update_company(slug, **update_fields)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return CompanyProfileSettingsResponse(
        slug=company.slug,
        name=company.name,
        domain=company.domain,
        additional_domains=company.additional_domains,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


# ── Phase 1C: Pipeline Defaults ───────────────────────────


@router.get("/pipeline-defaults", response_model=PipelineDefaultsResponse)
async def get_pipeline_defaults(
    slug: str,
    _user: UserProfile = Depends(require_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineDefaultsResponse:
    """Get per-company pipeline default overrides."""
    defaults = await auth_service.get_pipeline_defaults(slug)
    return PipelineDefaultsResponse(**defaults.model_dump())


@router.put("/pipeline-defaults", response_model=PipelineDefaultsResponse)
async def update_pipeline_defaults(
    slug: str,
    body: UpdatePipelineDefaultsRequest,
    su_company: Tuple[UserProfile, Company] = Depends(_require_superuser_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> PipelineDefaultsResponse:
    """Update per-company pipeline defaults. Superuser only."""
    update_fields = body.model_dump(exclude_none=True)
    defaults = await auth_service.update_pipeline_defaults(slug, **update_fields)
    return PipelineDefaultsResponse(**defaults.model_dump())
