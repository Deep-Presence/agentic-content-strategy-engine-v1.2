"""JsonGapDataService — StorageBackend-backed implementation of GapDataServiceProtocol.

Wraps the existing module-level functions in ``api.services.gap_data_service``
and ``api.services.brand_data_service`` (for SPA trend) via ``asyncio.to_thread()``.
"""
from __future__ import annotations

import asyncio
from typing import Literal, Optional

from core.storage.backends.base import StorageBackend

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
from api.services import gap_data_service as _gap_svc
from api.services import brand_data_service as _brand_svc
from core.services.task_store import TaskStoreProtocol


class JsonGapDataService:
    """StorageBackend-backed gap data service.

    All methods delegate to the existing synchronous service functions
    via ``asyncio.to_thread()`` so routers can be ``async def``.
    """

    def __init__(self, storage: StorageBackend, task_store: TaskStoreProtocol) -> None:
        self._storage = storage
        self._task_store = task_store

    async def get_summary(self, effective_slug: str, *, ga_run_id: Optional[str] = None) -> GapSummaryResponse:
        return await asyncio.to_thread(
            _gap_svc.get_summary, self._storage, effective_slug, ga_run_id=ga_run_id,
        )

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
        return await asyncio.to_thread(
            _gap_svc.get_queries,
            self._storage,
            effective_slug,
            cluster=cluster,
            classification=classification,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )

    async def get_clusters(self, effective_slug: str) -> ClusterListResponse:
        return await asyncio.to_thread(
            _gap_svc.get_clusters, self._storage, effective_slug,
        )

    async def get_signals(self, effective_slug: str) -> SignalAveragesResponse:
        return await asyncio.to_thread(
            _gap_svc.get_signals, self._storage, effective_slug,
        )

    async def get_platforms(self, effective_slug: str) -> PlatformListResponse:
        return await asyncio.to_thread(
            _gap_svc.get_platforms, self._storage, effective_slug,
        )

    async def get_heatmap(self, effective_slug: str) -> HeatmapResponse:
        return await asyncio.to_thread(
            _gap_svc.get_heatmap, self._storage, effective_slug,
        )

    async def get_embedding_projection(
        self,
        effective_slug: str,
        method: Literal["umap", "tsne"] = "umap",
    ) -> EmbeddingProjectionResponse:
        return await asyncio.to_thread(
            _gap_svc.get_embedding_projection,
            self._storage,
            effective_slug,
            method=method,
        )

    async def get_spa_trend(self, effective_slug: str) -> SPATrendResponse:
        return await asyncio.to_thread(
            _brand_svc.get_spa_trend, self._task_store, effective_slug,
        )

    async def get_cluster_profiles(
        self, effective_slug: str,
    ) -> ClusterProfileListResponse:
        return await asyncio.to_thread(
            _gap_svc.get_cluster_profiles, self._storage, effective_slug,
        )

    async def get_territory_gaps(
        self, effective_slug: str,
    ) -> TerritoryGapsResponse:
        return await asyncio.to_thread(
            _gap_svc.get_territory_gaps, self._storage, effective_slug,
        )
