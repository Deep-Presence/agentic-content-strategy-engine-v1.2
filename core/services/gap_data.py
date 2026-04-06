"""GapDataServiceProtocol — async interface for gap analysis data retrieval."""
from __future__ import annotations

from typing import Literal, Optional, Protocol, runtime_checkable

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


@runtime_checkable
class GapDataServiceProtocol(Protocol):
    """Async interface for gap analysis data endpoints.

    Two implementations:
    - ``JsonGapDataService``: wraps filesystem-backed functions via ``asyncio.to_thread()``
    - ``DbGapDataService``: SQL queries against Postgres (Phase 3, Step 3)
    """

    async def get_summary(self, effective_slug: str) -> GapSummaryResponse: ...

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
    ) -> QueryListResponse: ...

    async def get_clusters(self, effective_slug: str) -> ClusterListResponse: ...

    async def get_signals(self, effective_slug: str) -> SignalAveragesResponse: ...

    async def get_platforms(self, effective_slug: str) -> PlatformListResponse: ...

    async def get_heatmap(self, effective_slug: str) -> HeatmapResponse: ...

    async def get_embedding_projection(
        self,
        effective_slug: str,
        method: Literal["umap", "tsne"] = "umap",
    ) -> EmbeddingProjectionResponse: ...

    async def get_spa_trend(self, effective_slug: str) -> SPATrendResponse: ...

    async def get_cluster_profiles(
        self, effective_slug: str,
    ) -> ClusterProfileListResponse: ...

    async def get_territory_gaps(
        self, effective_slug: str,
    ) -> TerritoryGapsResponse: ...
