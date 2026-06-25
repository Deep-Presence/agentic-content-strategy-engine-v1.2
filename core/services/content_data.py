"""ContentDataServiceProtocol — async interface for content pipeline data retrieval."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from api.schemas.content_data import (
    ContentPublishMetadata,
    ContentBriefDetailResponse,
    ContentBriefListItem,
    ContentBriefListResponse,
    StageContentResponse,
)


@runtime_checkable
class ContentDataServiceProtocol(Protocol):
    """Async interface for content data endpoints.

    Two implementations:
    - ``JsonContentDataService``: wraps filesystem-backed functions
    - ``DbContentDataService``: SQL queries against Postgres (Phase 3, Step 3)
    """

    async def get_briefs(
        self, effective_slug: str,
    ) -> ContentBriefListResponse: ...

    async def get_brief_detail(
        self, effective_slug: str, brief_id: str,
    ) -> ContentBriefDetailResponse: ...

    async def get_brief_stage_content(
        self, effective_slug: str, brief_id: str, stage: str,
    ) -> StageContentResponse: ...

    async def add_brief(
        self,
        effective_slug: str,
        title: str,
        cluster: str = "",
        description: str = "",
        source: str = "manual",
        gap_query_id: str = "",
    ) -> ContentBriefListItem: ...

    async def save_publish_metadata(
        self,
        effective_slug: str,
        brief_id: str,
        metadata: dict | ContentPublishMetadata,
    ) -> ContentPublishMetadata: ...
