"""Brand Brain + Run History endpoints.

- GET /api/v1/companies/{slug}/research/artifacts
- GET /api/v1/companies/{slug}/runs

All endpoints require authentication and company membership.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.auth.dependencies import require_tenant
from api.dependencies import get_brand_data_service
from api.schemas.brand_data import (
    ResearchArtifactsResponse,
    RunHistoryResponse,
)
from core.services.brand_data import BrandDataServiceProtocol

router = APIRouter(
    prefix="/api/v1/companies/{slug}",
    tags=["brand-data"],
)


@router.get("/research/artifacts", response_model=ResearchArtifactsResponse)
async def get_brand_research_artifacts(
    slug: str,
    brand_service: BrandDataServiceProtocol = Depends(get_brand_data_service),
    _access=Depends(require_tenant),
) -> ResearchArtifactsResponse:
    """Research artifacts (company context, personas, style guide) with content."""
    return await brand_service.get_research_artifacts(slug)


@router.get("/runs", response_model=RunHistoryResponse)
async def get_company_runs(
    slug: str,
    brand_service: BrandDataServiceProtocol = Depends(get_brand_data_service),
    pipeline: Optional[str] = Query(None, description="Filter by pipeline type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    _access=Depends(require_tenant),
) -> RunHistoryResponse:
    """Run history across all pipelines for a company."""
    return await brand_service.get_run_history(
        slug, pipeline=pipeline, status=status, limit=limit,
    )
