"""JsonBrandDataService — filesystem + TaskStore implementation of BrandDataServiceProtocol.

Wraps the existing module-level functions in ``api.services.brand_data_service``
via ``asyncio.to_thread()``.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from api.schemas.brand_data import (
    ResearchArtifactsResponse,
    RunHistoryResponse,
)
from api.services import brand_data_service as _brand_svc
from api.tasks.store import TaskStore


class JsonBrandDataService:
    """Filesystem + TaskStore backed brand data service.

    All methods delegate to the existing synchronous service functions
    via ``asyncio.to_thread()`` so routers can be ``async def``.
    """

    def __init__(self, artifacts_root: Path, task_store: TaskStore) -> None:
        self._artifacts_root = artifacts_root
        self._task_store = task_store

    async def get_research_artifacts(
        self, slug: str,
    ) -> ResearchArtifactsResponse:
        return await asyncio.to_thread(
            _brand_svc.get_research_artifacts, self._artifacts_root, slug,
        )

    async def get_run_history(
        self,
        slug: str,
        *,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> RunHistoryResponse:
        return await asyncio.to_thread(
            _brand_svc.get_run_history,
            self._task_store,
            slug,
            pipeline=pipeline,
            status=status,
            limit=limit,
        )
