"""CMSAdapterProtocol — contract every CMS adapter must satisfy.

Lifecycle:
    1. ``__init__(config: CMSConnectionConfig)``
    2. ``validate_connection()`` — test credentials, return site metadata
    3. Read ops: ``list_posts()``, ``get_post()``, ``list_categories()``
    4. Write ops: ``publish_post()``, ``update_post()``
    5. Media ops: ``upload_media()`` (for featured images)
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from core.cms.models import (
    CMSCategory,
    CMSConnectionStatus,
    CMSMediaResult,
    CMSMediaUpload,
    CMSPost,
    CMSPostCreate,
    CMSPostUpdate,
)


@runtime_checkable
class CMSAdapterProtocol(Protocol):
    """Contract every CMS adapter must satisfy."""

    # ── Connection ────────────────────────────────────────────────

    async def validate_connection(self) -> CMSConnectionStatus:
        """Test credentials against the CMS API.

        Returns site metadata on success.
        Raises ``CMSAuthError`` on failure.
        """
        ...

    # ── Read Operations ───────────────────────────────────────────

    async def list_posts(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        status: str = "publish",
        after: datetime | None = None,
        modified_after: datetime | None = None,
    ) -> tuple[list[CMSPost], int]:
        """Paginated listing of existing posts.

        Returns ``(posts, total_count)``.
        """
        ...

    async def get_post(self, post_id: int | str) -> CMSPost:
        """Fetch a single post by CMS-native ID."""
        ...

    async def list_categories(self) -> list[CMSCategory]:
        """Return all categories/taxonomies from the CMS."""
        ...

    # ── Write Operations ──────────────────────────────────────────

    async def publish_post(self, post: CMSPostCreate) -> CMSPost:
        """Create and publish a new post on the CMS.

        Returns the created post with its CMS-native ID and permalink.
        """
        ...

    async def update_post(
        self, post_id: int | str, updates: CMSPostUpdate
    ) -> CMSPost:
        """Update an existing post (for content refresh flows).

        Only sends changed fields.
        """
        ...

    # ── Media Operations ──────────────────────────────────────────

    async def upload_media(self, media: CMSMediaUpload) -> CMSMediaResult:
        """Upload an image to the CMS media library.

        Returns the media ID and URL for use as ``featured_image`` in posts.
        """
        ...
