"""Company profile endpoint.

Returns company profile with products, research artifact status,
gap analysis/content availability, and latest pipeline runs.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import require_company_member, require_tenant
from api.dependencies import get_artifacts_root, get_auth_store, get_task_store
from api.schemas.company import (
    CompanyProfileResponse,
    LatestRunSummary,
    ProductCreateRequest,
    ProductDetailResponse,
    ProductSummary,
    ProductUpdateRequest,
    ResearchArtifactSummary,
)
from api.auth.store import AuthStore
from api.tasks.store import TaskStore
from core.models.organization import Company, Product, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _detect_artifact_status(artifacts_root: Path, type_name: str, slug: str) -> str:
    """Check if an artifact exists: 'approved', 'draft', or 'none'.

    For flat types (company_context, style_guides): looks for {slug}.md or {slug}.draft.md.
    """
    type_dir = artifacts_root / type_name
    if not type_dir.is_dir():
        return "none"

    approved = type_dir / f"{slug}.md"
    draft = type_dir / f"{slug}.draft.md"

    if approved.is_file():
        return "approved"
    elif draft.is_file():
        return "draft"
    return "none"


def _detect_personas(artifacts_root: Path, slug: str) -> List[str]:
    """Find all persona files for a company slug."""
    personas_dir = artifacts_root / "personas"
    if not personas_dir.is_dir():
        return []

    persona_files = []
    for f in sorted(personas_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.name.endswith(".draft.md"):
            continue
        stem = f.stem
        # Match {slug}__persona-*.md
        if stem.startswith(f"{slug}__persona"):
            persona_files.append(f.name)
    return persona_files


def _has_nested_artifacts(artifacts_root: Path, type_name: str, slug: str) -> bool:
    """Check if nested artifact directory exists and has files."""
    slug_dir = artifacts_root / type_name / slug
    if not slug_dir.is_dir():
        return False
    # Check for any non-hidden files
    for f in slug_dir.iterdir():
        if f.is_file() and not f.name.startswith("."):
            return True
    return False


def _build_research_summary(
    artifacts_root: Path, slug: str
) -> ResearchArtifactSummary:
    """Scan filesystem for research artifacts belonging to this company."""
    cc_status = _detect_artifact_status(artifacts_root, "company_context", slug)
    sg_status = _detect_artifact_status(artifacts_root, "style_guides", slug)
    personas = _detect_personas(artifacts_root, slug)

    # Determine the file path for company_context if it exists
    cc_file = None
    if cc_status == "approved":
        cc_file = f"{slug}.md"
    elif cc_status == "draft":
        cc_file = f"{slug}.draft.md"

    sg_file = None
    if sg_status == "approved":
        sg_file = f"{slug}.md"
    elif sg_status == "draft":
        sg_file = f"{slug}.draft.md"

    return ResearchArtifactSummary(
        company_context=cc_file,
        company_context_status=cc_status,
        personas=personas,
        style_guide=sg_file,
        style_guide_status=sg_status,
    )


def _get_latest_runs(
    task_store: TaskStore, slug: str
) -> Dict[str, Optional[LatestRunSummary]]:
    """Find the most recent task per pipeline type for this company."""
    latest: Dict[str, Optional[LatestRunSummary]] = {
        "research": None,
        "gap_analysis": None,
        "content": None,
    }

    all_tasks = task_store.list_tasks()
    # Filter to this company and group by pipeline
    for task in all_tasks:
        if task.company_slug != slug:
            continue
        pipeline = task.pipeline
        if pipeline not in latest:
            continue

        current = latest[pipeline]
        if current is None or task.created_at > current.created_at:
            latest[pipeline] = LatestRunSummary(
                run_id=task.task_id,
                status=task.status.value,
                created_at=task.created_at,
                completed_at=(
                    task.updated_at
                    if task.status.value in ("completed", "failed", "cancelled")
                    else None
                ),
                summary=task.result,
            )

    return latest


@router.get("/{slug}", response_model=CompanyProfileResponse)
def get_company_profile(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    auth_store: AuthStore = Depends(get_auth_store),
    task_store: TaskStore = Depends(get_task_store),
    _user: UserProfile = Depends(require_tenant),
) -> CompanyProfileResponse:
    """Get company profile with artifacts, products, and latest runs.

    Requires authentication and company membership.
    """
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")

    # Try auth store first for company metadata
    company = auth_store.get_company_by_slug(slug)

    # Check filesystem for artifacts
    has_research = (
        _detect_artifact_status(artifacts_root, "company_context", slug) != "none"
        or len(_detect_personas(artifacts_root, slug)) > 0
        or _detect_artifact_status(artifacts_root, "style_guides", slug) != "none"
    )
    has_gap_analysis = _has_nested_artifacts(artifacts_root, "gap_analysis", slug)
    has_content = _has_nested_artifacts(artifacts_root, "content", slug)

    # If no company in auth store AND no artifacts, 404
    if company is None and not has_research and not has_gap_analysis and not has_content:
        raise HTTPException(
            status_code=404,
            detail=f"Company '{slug}' not found",
        )

    # Build sub-components
    research_summary = _build_research_summary(artifacts_root, slug)
    latest_runs = _get_latest_runs(task_store, slug)

    # Build product summaries from auth store
    products: List[ProductSummary] = []
    if company and company.products:
        for p in company.products:
            effective = f"{slug}__{p.slug}"
            products.append(
                ProductSummary(
                    slug=p.slug,
                    name=p.name,
                    domain=p.domain,
                    description=p.description,
                    has_research=(
                        _detect_artifact_status(artifacts_root, "company_context", effective) != "none"
                    ),
                    has_gap_analysis=_has_nested_artifacts(artifacts_root, "gap_analysis", effective),
                    has_content=_has_nested_artifacts(artifacts_root, "content", effective),
                )
            )

    return CompanyProfileResponse(
        slug=slug,
        name=company.name if company else slug.replace("-", " ").title(),
        domain=company.domain if company else "",
        products=products,
        has_research=has_research,
        has_gap_analysis=has_gap_analysis,
        has_content=has_content,
        research_summary=research_summary,
        latest_runs=latest_runs,
    )


# ── Product CRUD endpoints ─────────────────────────────────


@router.post("/{slug}/products", response_model=ProductDetailResponse, status_code=201)
def create_product(
    slug: str,
    body: ProductCreateRequest,
    auth: tuple[UserProfile, Company] = Depends(require_company_member),
    auth_store: AuthStore = Depends(get_auth_store),
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
        auth_store.add_product(slug, product)
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
def get_product(
    slug: str,
    product_slug: str,
    _user: UserProfile = Depends(require_tenant),
    auth_store: AuthStore = Depends(get_auth_store),
) -> ProductDetailResponse:
    """Get a specific product by slug. Requires company membership."""
    product = auth_store.get_product(slug, product_slug)
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
def update_product(
    slug: str,
    product_slug: str,
    body: ProductUpdateRequest,
    auth: tuple[UserProfile, Company] = Depends(require_company_member),
    auth_store: AuthStore = Depends(get_auth_store),
) -> ProductDetailResponse:
    """Update a product's fields. Requires member+ role and company membership."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        product = auth_store.update_product(slug, product_slug, **updates)
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
def delete_product(
    slug: str,
    product_slug: str,
    auth: tuple[UserProfile, Company] = Depends(require_company_member),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    """Delete a product. Requires member+ role and company membership."""
    removed = auth_store.remove_product(slug, product_slug)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product_slug}' not found in company '{slug}'",
        )
    return {"deleted": True}
