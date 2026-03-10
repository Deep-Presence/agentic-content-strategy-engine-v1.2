"""JsonContentDataService — filesystem-backed implementation of ContentDataServiceProtocol.

Wraps the existing module-level functions in ``api.services.content_data_service``
via ``asyncio.to_thread()``.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from api.schemas.content_data import (
    ContentBriefDetailResponse,
    ContentBriefListResponse,
    StageContentResponse,
)
from api.services import content_data_service as _content_svc


class JsonContentDataService:
    """Filesystem-backed content data service.

    All methods delegate to the existing synchronous service functions
    via ``asyncio.to_thread()`` so routers can be ``async def``.
    """

    def __init__(self, artifacts_root: Path) -> None:
        self._artifacts_root = artifacts_root

    async def get_briefs(
        self, effective_slug: str,
    ) -> ContentBriefListResponse:
        return await asyncio.to_thread(
            _content_svc.get_briefs, self._artifacts_root, effective_slug,
        )

    async def get_brief_detail(
        self, effective_slug: str, brief_id: str,
    ) -> ContentBriefDetailResponse:
        return await asyncio.to_thread(
            _content_svc.get_brief_detail,
            self._artifacts_root,
            effective_slug,
            brief_id,
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
        )
