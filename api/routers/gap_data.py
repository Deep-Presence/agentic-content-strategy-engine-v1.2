"""Gap analysis data retrieval endpoints.

Serves pre-computed pipeline artifacts for the Signal Analysis dashboard.
All data is read from ``artifacts/gap_analysis/{slug}/`` JSON files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_artifacts_root, get_task_store
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
from api.services.brand_data_service import get_spa_trend
from api.tasks.store import TaskStore
from api.services.gap_data_service import (
    get_clusters,
    get_embedding_projection,
    get_heatmap,
    get_platforms,
    get_queries,
    get_signals,
    get_summary,
)

router = APIRouter(
    prefix="/api/v1/companies/{slug}/gap-analysis",
    tags=["gap-data"],
)


def _effective(slug: str, product_slug: Optional[str]) -> str:
    """Compute effective artifact directory slug."""
    return f"{slug}__{product_slug}" if product_slug else slug


@router.get("/summary", response_model=GapSummaryResponse)
def get_gap_summary(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> GapSummaryResponse:
    """Executive overview: SPA score, proximity stats, classifications, clusters."""
    return get_summary(artifacts_root, _effective(slug, product_slug))


@router.get("/queries", response_model=QueryListResponse)
def get_gap_queries(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    cluster: Optional[str] = Query(None, description="Filter by cluster name or ID"),
    classification: Optional[str] = Query(None, description="Filter by gap classification"),
    search: Optional[str] = Query(None, description="Search query text"),
    sort_by: str = Query("gap_score", description="Sort field"),
    sort_dir: str = Query("desc", description="Sort direction: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(15, ge=1, le=100, description="Items per page"),
) -> QueryListResponse:
    """Paginated, filterable query list for the Query Intelligence tab."""
    return get_queries(
        artifacts_root,
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
def get_gap_clusters(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> ClusterListResponse:
    """Cluster specifications with centroid distances and structural rates."""
    return get_clusters(artifacts_root, _effective(slug, product_slug))


@router.get("/signals", response_model=SignalAveragesResponse)
def get_gap_signals(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> SignalAveragesResponse:
    """Structural signal averages, correlations, and cluster patterns."""
    return get_signals(artifacts_root, _effective(slug, product_slug))


@router.get("/platforms", response_model=PlatformListResponse)
def get_gap_platforms(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> PlatformListResponse:
    """Per-platform citation breakdown with agreement matrix."""
    return get_platforms(artifacts_root, _effective(slug, product_slug))


@router.get("/heatmap", response_model=HeatmapResponse)
def get_gap_heatmap(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> HeatmapResponse:
    """Gap score heatmap grouped by cluster."""
    return get_heatmap(artifacts_root, _effective(slug, product_slug))


@router.get("/embeddings", response_model=EmbeddingProjectionResponse)
def get_gap_embeddings(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    method: Literal["umap", "tsne"] = Query("umap", description="Projection method: umap or tsne"),
) -> EmbeddingProjectionResponse:
    """2D embedding projections for scatter plot visualization."""
    return get_embedding_projection(
        artifacts_root, _effective(slug, product_slug), method=method
    )


@router.get("/trend", response_model=SPATrendResponse)
def get_spa_trend_endpoint(
    slug: str,
    task_store: TaskStore = Depends(get_task_store),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
) -> SPATrendResponse:
    """SPA score trend across completed gap analysis runs."""
    return get_spa_trend(task_store, _effective(slug, product_slug))
