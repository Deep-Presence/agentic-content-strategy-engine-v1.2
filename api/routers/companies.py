"""Company profile endpoint.

Returns company profile with products, research artifact status,
gap analysis/content availability, and latest pipeline runs.

Legacy alias: delegates to WorkspaceProfileService and maps the response
shape for backward-compatible clients.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import require_auth, require_company_member, require_tenant
from api.dependencies import (
    get_artifacts_root,
    get_auth_service,
    get_storage_backend,
    get_task_store,
    get_workspace_service,
)
from api.schemas.company import (
    CompanyProfileResponse,
    LatestRunSummary,
    ProductCreateRequest,
    ProductDetailResponse,
    ProductSummary,
    ProductUpdateRequest,
    ResearchArtifactSummary,
)
from core.auth.service import AuthServiceProtocol
from core.models.organization import Company, Product, UserProfile
from core.models.workspace import WorkspaceProfile
from core.services.task_store import TaskStoreProtocol
from core.services.workspace_protocol import WorkspaceServiceProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def workspace_profile_to_company_response(
    profile: WorkspaceProfile,
) -> CompanyProfileResponse:
    """Map workspace profile to legacy company profile response."""
    products = [
        ProductSummary(
            slug=p.slug,
            name=p.name,
            domain=p.domain,
            description=p.description,
            has_research=p.has_research,
            has_gap_analysis=p.has_gap_analysis,
            has_content=p.has_content,
        )
        for p in profile.products
    ]
    latest_runs: Dict[str, Optional[LatestRunSummary]] = {
        key: None for key in ("research", "gap_analysis", "content")
    }
    for key, value in profile.latest_runs.items():
        if key in latest_runs and value is not None:
            latest_runs[key] = LatestRunSummary(**value.model_dump(mode="json"))
    return CompanyProfileResponse(
        slug=profile.slug,
        name=profile.name,
        domain=profile.primary_domain,
        products=products,
        has_research=profile.has_research,
        has_gap_analysis=profile.has_gap_analysis,
        has_content=profile.has_content,
        research_summary=ResearchArtifactSummary(
            **profile.research_summary.model_dump(mode="json")
        ),
        latest_runs=latest_runs,
    )


@router.get("/{slug}", response_model=CompanyProfileResponse)
async def get_company_profile(
    slug: str,
    artifacts_root=Depends(get_artifacts_root),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    user: UserProfile = Depends(require_auth),
    storage_backend=Depends(get_storage_backend),
) -> CompanyProfileResponse:
    """Get company profile with artifacts, products, and latest runs.

    Legacy alias for ``GET /api/v1/workspaces/{slug}/profile``.
    """
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")

    try:
        profile = await workspace_service.get_profile(
            slug,
            user,
            auth_service=auth_service,
            artifacts_root=artifacts_root,
            storage_backend=storage_backend,
            task_store=task_store,
        )
    except ValueError as exc:
        code = str(exc)
        if code in ("workspace_not_found", "access_denied"):
            raise HTTPException(status_code=403, detail="Access denied") from exc
        raise HTTPException(status_code=400, detail=code) from exc

    return workspace_profile_to_company_response(profile)


# ── Product CRUD endpoints ─────────────────────────────────


@router.post("/{slug}/products", response_model=ProductDetailResponse, status_code=201)
async def create_product(
    slug: str,
    body: ProductCreateRequest,
    auth: tuple[UserProfile, Company] = Depends(require_company_member),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ProductDetailResponse:
    """Create a new product under a company.

    Requires member+ role and company membership.
    """
    if not _SLUG_PATTERN.match(body.slug):
        raise HTTPException(
            status_code=422,
            detail="Product slug must match ^[a-z0-9][a-z0-9-]*$",
        )

    _, company = auth

    product = Product(
        company_id=company.id,
        slug=body.slug,
        name=body.name,
        domain=body.domain,
        description=body.description,
    )

    try:
        await auth_service.add_product(slug, product)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return ProductDetailResponse(
        id=product.id,
        slug=product.slug,
        name=product.name,
        domain=product.domain,
        description=product.description,
        company_id=product.company_id,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/{slug}/products/{product_slug}", response_model=ProductDetailResponse)
async def get_product(
    slug: str,
    product_slug: str,
    _user: UserProfile = Depends(require_tenant),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ProductDetailResponse:
    """Get a specific product by slug. Requires company membership."""
    product = await auth_service.get_product(slug, product_slug)
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product_slug}' not found in company '{slug}'",
        )

    return ProductDetailResponse(
        id=product.id,
        slug=product.slug,
        name=product.name,
        domain=product.domain,
        description=product.description,
        company_id=product.company_id,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.put("/{slug}/products/{product_slug}", response_model=ProductDetailResponse)
async def update_product(
    slug: str,
    product_slug: str,
    body: ProductUpdateRequest,
    auth: tuple[UserProfile, Company] = Depends(require_company_member),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ProductDetailResponse:
    """Update a product's fields. Requires member+ role and company membership."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        product = await auth_service.update_product(slug, product_slug, **updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ProductDetailResponse(
        id=product.id,
        slug=product.slug,
        name=product.name,
        domain=product.domain,
        description=product.description,
        company_id=product.company_id,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.delete("/{slug}/products/{product_slug}")
async def delete_product(
    slug: str,
    product_slug: str,
    auth: tuple[UserProfile, Company] = Depends(require_company_member),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> dict:
    """Delete a product. Requires member+ role and company membership."""
    removed = await auth_service.remove_product(slug, product_slug)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product_slug}' not found in company '{slug}'",
        )
    return {"deleted": True}
