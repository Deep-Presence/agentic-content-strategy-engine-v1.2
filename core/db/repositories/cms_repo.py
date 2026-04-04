"""Repositories for CMS integration domain models.

Three table-specific repositories:
- CMSConnectionRepository   — cms_connections
- CMSPublishRecordRepository — cms_publish_records
- CMSSyncedPostRepository    — cms_synced_posts

Transaction ownership: repos call ``session.add()`` + ``session.flush()`` only.
``session.commit()`` is NEVER called here — commit happens in the DI layer.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.cms import (
    CMSConnectionModel,
    CMSPublishRecordModel,
    CMSSyncedPostModel,
)
from core.db.repositories.base import SQLAlchemyRepository


# ── CMSConnectionRepository ───────────────────────────────────────────


class CMSConnectionRepository(SQLAlchemyRepository[CMSConnectionModel]):
    """Repository for CMS connections (credentials, sync metadata)."""

    model_class = CMSConnectionModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_active_connection(
        self,
        company_id: _uuid.UUID | str,
        tenant_id: str,
    ) -> Optional[CMSConnectionModel]:
        """Return the single active CMS connection for a company+tenant."""
        cid = (
            _uuid.UUID(str(company_id))
            if isinstance(company_id, str)
            else company_id
        )
        stmt = (
            select(CMSConnectionModel)
            .where(
                CMSConnectionModel.company_id == cid,
                CMSConnectionModel.tenant_id == tenant_id,
                CMSConnectionModel.is_active.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_company_slug(
        self,
        company_slug: str,
        tenant_id: str,
    ) -> Optional[CMSConnectionModel]:
        """Return active connection by company_slug + tenant_id."""
        stmt = (
            select(CMSConnectionModel)
            .where(
                CMSConnectionModel.company_slug == company_slug,
                CMSConnectionModel.tenant_id == tenant_id,
                CMSConnectionModel.is_active.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate(
        self,
        connection_id: _uuid.UUID | str,
    ) -> bool:
        """Soft-deactivate a connection (set is_active=False)."""
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        stmt = (
            update(CMSConnectionModel)
            .where(CMSConnectionModel.id == cid)
            .values(is_active=False)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def update_sync_metadata(
        self,
        connection_id: _uuid.UUID | str,
        *,
        last_sync_at: datetime,
        sync_post_count: int,
    ) -> None:
        """Update sync timestamp and count after a sync run."""
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        stmt = (
            update(CMSConnectionModel)
            .where(CMSConnectionModel.id == cid)
            .values(
                last_sync_at=last_sync_at,
                sync_post_count=sync_post_count,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()


# ── CMSPublishRecordRepository ────────────────────────────────────────


class CMSPublishRecordRepository(
    SQLAlchemyRepository[CMSPublishRecordModel]
):
    """Repository for CMS publish/refresh audit records."""

    model_class = CMSPublishRecordModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_brief(
        self,
        company_slug: str,
        brief_id: str,
    ) -> Optional[CMSPublishRecordModel]:
        """Return the most recent publish record for a brief."""
        stmt = (
            select(CMSPublishRecordModel)
            .where(
                CMSPublishRecordModel.company_slug == company_slug,
                CMSPublishRecordModel.brief_id == brief_id,
            )
            .order_by(CMSPublishRecordModel.published_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_company(
        self,
        company_slug: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CMSPublishRecordModel]:
        """Return all publish records for a company, most recent first."""
        stmt = (
            select(CMSPublishRecordModel)
            .where(CMSPublishRecordModel.company_slug == company_slug)
            .order_by(CMSPublishRecordModel.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


# ── CMSSyncedPostRepository ───────────────────────────────────────────


class CMSSyncedPostRepository(SQLAlchemyRepository[CMSSyncedPostModel]):
    """Repository for locally indexed CMS posts."""

    model_class = CMSSyncedPostModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def upsert_from_cms(
        self,
        connection_id: _uuid.UUID,
        company_slug: str,
        cms_post_id: str,
        **kwargs: object,
    ) -> CMSSyncedPostModel:
        """Insert or update a synced post by (connection_id, cms_post_id)."""
        stmt = select(CMSSyncedPostModel).where(
            CMSSyncedPostModel.connection_id == connection_id,
            CMSSyncedPostModel.cms_post_id == cms_post_id,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            existing.synced_at = datetime.now(timezone.utc)
            await self._session.flush()
            return existing
        return await self.create(
            connection_id=connection_id,
            company_slug=company_slug,
            cms_post_id=cms_post_id,
            **kwargs,
        )

    async def get_stale(
        self,
        company_slug: str,
        *,
        limit: int = 50,
    ) -> Sequence[CMSSyncedPostModel]:
        """Return stale posts not yet queued for refresh."""
        stmt = (
            select(CMSSyncedPostModel)
            .where(
                CMSSyncedPostModel.company_slug == company_slug,
                CMSSyncedPostModel.is_stale.is_(True),
                CMSSyncedPostModel.queued_for_refresh.is_(False),
            )
            .order_by(CMSSyncedPostModel.staleness_days.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_queued_for_refresh(
        self,
        synced_post_id: _uuid.UUID | str,
        refresh_brief_id: str,
    ) -> bool:
        """Mark a synced post as queued for content refresh."""
        pid = (
            _uuid.UUID(str(synced_post_id))
            if isinstance(synced_post_id, str)
            else synced_post_id
        )
        stmt = (
            update(CMSSyncedPostModel)
            .where(CMSSyncedPostModel.id == pid)
            .values(
                queued_for_refresh=True,
                refresh_brief_id=refresh_brief_id,
                refresh_queued_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def list_by_company(
        self,
        company_slug: str,
        *,
        stale_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CMSSyncedPostModel]:
        """Return all synced posts for a company."""
        stmt = select(CMSSyncedPostModel).where(
            CMSSyncedPostModel.company_slug == company_slug
        )
        if stale_only:
            stmt = stmt.where(CMSSyncedPostModel.is_stale.is_(True))
        stmt = (
            stmt.order_by(CMSSyncedPostModel.modified_at.desc().nullslast())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def batch_link_inventory_ids(
        self,
        connection_id: _uuid.UUID,
        pairs: list[tuple[_uuid.UUID, Any]],
    ) -> int:
        """Batch update content_inventory_id FK on synced posts.

        Args:
            connection_id: The CMS connection these posts belong to.
            pairs: List of ``(content_inventory_id, cms_post_id_str)`` tuples.

        Returns:
            Number of rows updated.
        """
        if not pairs:
            return 0

        count = 0
        for inventory_id, cms_post_id in pairs:
            if cms_post_id is None:
                continue
            stmt = (
                update(CMSSyncedPostModel)
                .where(
                    CMSSyncedPostModel.connection_id == connection_id,
                    CMSSyncedPostModel.cms_post_id == str(cms_post_id),
                )
                .values(content_inventory_id=inventory_id)
            )
            result = await self._session.execute(stmt)
            count += result.rowcount
        await self._session.flush()
        return count
