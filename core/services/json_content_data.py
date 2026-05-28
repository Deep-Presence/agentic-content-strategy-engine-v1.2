"""JsonContentDataService — StorageBackend-backed implementation of ContentDataServiceProtocol.

Wraps the existing module-level functions in ``api.services.content_data_service``
via ``asyncio.to_thread()``.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from api.schemas.content_data import (
    ContentPublishMetadata,
    ContentBriefDetailResponse,
    ContentBriefListItem,
    ContentBriefListResponse,
    StageContentResponse,
)
from fastapi import HTTPException
from api.services import content_data_service as _content_svc
from core.storage.backends.base import StorageBackend


class JsonContentDataService:
    """StorageBackend-backed content data service.

    All methods delegate to the existing synchronous service functions
    via ``asyncio.to_thread()`` so routers can be ``async def``.
    """

    def __init__(
        self, artifacts_root: Path, *, storage: Optional[StorageBackend] = None,
    ) -> None:
        self._artifacts_root = artifacts_root
        self._storage = storage

    async def get_briefs(
        self, effective_slug: str,
    ) -> ContentBriefListResponse:
        return await asyncio.to_thread(
            _content_svc.get_briefs, self._artifacts_root, effective_slug,
            storage=self._storage,
        )

    async def get_brief_detail(
        self, effective_slug: str, brief_id: str,
    ) -> ContentBriefDetailResponse:
        return await asyncio.to_thread(
            _content_svc.get_brief_detail,
            self._artifacts_root,
            effective_slug,
            brief_id,
            storage=self._storage,
        )

    async def get_brief_stage_content(
        self, effective_slug: str, brief_id: str, stage: str,
    ) -> StageContentResponse:
        return await asyncio.to_thread(
            _content_svc.get_brief_stage_content,
            self._artifacts_root,
            effective_slug,
            brief_id,
            stage,
            storage=self._storage,
        )

    async def add_brief(
        self,
        effective_slug: str,
        title: str,
        cluster: str = "",
        description: str = "",
        source: str = "manual",
        gap_query_id: str = "",
    ) -> ContentBriefListItem:
        return await asyncio.to_thread(
            _content_svc.add_brief,
            self._artifacts_root,
            effective_slug,
            title,
            cluster,
            description,
            source,
            gap_query_id,
            storage=self._storage,
        )

    async def save_publish_metadata(
        self,
        effective_slug: str,
        brief_id: str,
        metadata: dict | ContentPublishMetadata,
    ) -> ContentPublishMetadata:
        raise HTTPException(
            status_code=501,
            detail="Publish metadata editing requires database-backed content storage.",
        )
