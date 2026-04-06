"""FallbackGapDataService — DB-first with JSON filesystem fallback on 404.

Follows the 'filesystem-first, DB-additive' principle: if a gap analysis
run was executed before DB persistence was added, the data only exists
on disk. This wrapper tries the DB service first and falls back to JSON
when the DB returns 404 (no pipeline_runs record).
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import HTTPException

from api.schemas.brand_data import SPATrendResponse
from api.schemas.content_data import EmbeddingProjectionResponse
from api.schemas.gap_data import (
    ClusterListResponse,
    ClusterProfileListResponse,
    GapSummaryResponse,
    HeatmapResponse,
    PlatformListResponse,
    QueryListResponse,
    SignalAveragesResponse,
    TerritoryGapsResponse,
)
from core.services.gap_data import GapDataServiceProtocol


class FallbackGapDataService:
    """Tries DbGapDataService, falls back to JsonGapDataService on 404."""

    def __init__(
        self,
        db: GapDataServiceProtocol,
        json: GapDataServiceProtocol,
    ) -> None:
        self._db = db
        self._json = json

    async def _fallback(self, method_name: str, *args, **kwargs):
        try:
            return await getattr(self._db, method_name)(*args, **kwargs)
        except HTTPException as e:
            if e.status_code == 404:
                return await getattr(self._json, method_name)(*args, **kwargs)
            raise

    async def get_summary(self, effective_slug: str) -> GapSummaryResponse:
        return await self._fallback("get_summary", effective_slug)

    async def get_queries(
        self,
        effective_slug: str,
        *,
        cluster: Optional[str] = None,
        classification: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "gap_score",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 15,
    ) -> QueryListResponse:
        return await self._fallback(
            "get_queries", effective_slug,
            cluster=cluster, classification=classification, search=search,
            sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size,
        )

    async def get_clusters(self, effective_slug: str) -> ClusterListResponse:
        return await self._fallback("get_clusters", effective_slug)

    async def get_signals(self, effective_slug: str) -> SignalAveragesResponse:
        return await self._fallback("get_signals", effective_slug)

    async def get_platforms(self, effective_slug: str) -> PlatformListResponse:
        return await self._fallback("get_platforms", effective_slug)

    async def get_heatmap(self, effective_slug: str) -> HeatmapResponse:
        return await self._fallback("get_heatmap", effective_slug)

    async def get_embedding_projection(
        self, effective_slug: str, *, method: Literal["umap", "tsne"] = "umap",
    ) -> EmbeddingProjectionResponse:
        return await self._fallback("get_embedding_projection", effective_slug, method=method)

    async def get_trend(self, effective_slug: str) -> SPATrendResponse:
        return await self._fallback("get_trend", effective_slug)

    async def get_cluster_profiles(
        self, effective_slug: str,
    ) -> ClusterProfileListResponse:
        return await self._fallback("get_cluster_profiles", effective_slug)

    async def get_territory_gaps(
        self, effective_slug: str,
    ) -> TerritoryGapsResponse:
        return await self._fallback("get_territory_gaps", effective_slug)
