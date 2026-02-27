"""Gap analysis data retrieval endpoints.

Serves pre-computed pipeline artifacts for the Signal Analysis dashboard.
All endpoints require authentication and company membership.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from api.auth.dependencies import require_tenant
from api.dependencies import get_gap_data_service
from api.schemas.brand_data import SPATrendResponse
from api.schemas.content_data import EmbeddingProjectionResponse
from api.schemas.gap_data import (
    ClusterListResponse,
    GapSummaryResponse,
    HeatmapResponse,
    PlatformListResponse,
    QueryListResponse,
    SignalAveragesResponse,
)
from core.services.gap_data import GapDataServiceProtocol

router = APIRouter(
    prefix="/api/v1/companies/{slug}/gap-analysis",
    tags=["gap-data"],
)


def _effective(slug: str, product_slug: Optional[str]) -> str:
    """Compute effective artifact directory slug."""
    return f"{slug}__{product_slug}" if product_slug else slug


@router.get("/summary", response_model=GapSummaryResponse)
async def get_gap_summary(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> GapSummaryResponse:
    """Executive overview: SPA score, proximity stats, classifications, clusters."""
    return await gap_service.get_summary(_effective(slug, product_slug))


@router.get("/queries", response_model=QueryListResponse)
async def get_gap_queries(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    cluster: Optional[str] = Query(None, description="Filter by cluster name or ID"),
    classification: Optional[str] = Query(None, description="Filter by gap classification"),
    search: Optional[str] = Query(None, description="Search query text"),
    sort_by: str = Query("gap_score", description="Sort field"),
    sort_dir: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(15, ge=1, le=100, description="Items per page"),
    _access=Depends(require_tenant),
) -> QueryListResponse:
    """Paginated, filterable query list for the Query Intelligence tab."""
    return await gap_service.get_queries(
        _effective(slug, product_slug),
        cluster=cluster,
        classification=classification,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/clusters", response_model=ClusterListResponse)
async def get_gap_clusters(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> ClusterListResponse:
    """Cluster specifications with centroid distances and structural rates."""
    return await gap_service.get_clusters(_effective(slug, product_slug))


@router.get("/signals", response_model=SignalAveragesResponse)
async def get_gap_signals(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> SignalAveragesResponse:
    """Structural signal averages, correlations, and cluster patterns."""
    return await gap_service.get_signals(_effective(slug, product_slug))


@router.get("/platforms", response_model=PlatformListResponse)
async def get_gap_platforms(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> PlatformListResponse:
    """Per-platform citation breakdown with agreement matrix."""
    return await gap_service.get_platforms(_effective(slug, product_slug))


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_gap_heatmap(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> HeatmapResponse:
    """Gap score heatmap grouped by cluster."""
    return await gap_service.get_heatmap(_effective(slug, product_slug))


@router.get("/embeddings", response_model=EmbeddingProjectionResponse)
async def get_gap_embeddings(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    method: Literal["umap", "tsne"] = Query("umap", description="Projection method: umap or tsne"),
    _access=Depends(require_tenant),
) -> EmbeddingProjectionResponse:
    """2D embedding projections for scatter plot visualization."""
    return await gap_service.get_embedding_projection(
        _effective(slug, product_slug), method=method,
    )


@router.get("/trend", response_model=SPATrendResponse)
async def get_spa_trend_endpoint(
    slug: str,
    gap_service: GapDataServiceProtocol = Depends(get_gap_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> SPATrendResponse:
    """SPA score trend across completed gap analysis runs."""
    return await gap_service.get_spa_trend(_effective(slug, product_slug))
