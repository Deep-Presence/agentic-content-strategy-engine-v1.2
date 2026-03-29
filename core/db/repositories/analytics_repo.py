"""Repositories for analytics integration domain models.

Three table-specific repositories:
- AnalyticsConnectionRepository  — analytics_connections
- GA4TrafficDataRepository       — ga4_traffic_data
- GA4ConversionEventRepository   — ga4_conversion_events

Transaction ownership: repos call ``session.add()`` + ``session.flush()`` only.
``session.commit()`` is NEVER called here — commit happens in the DI layer.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import AnalyticsSyncStatus
from core.db.models.analytics import (
    AnalyticsConnectionModel,
    GA4ConversionEventModel,
    GA4TrafficDataModel,
)
from core.db.repositories.base import SQLAlchemyRepository


# ── AnalyticsConnectionRepository ────────────────────────────────────


class AnalyticsConnectionRepository(
    SQLAlchemyRepository[AnalyticsConnectionModel]
):
    """Repository for analytics OAuth connections."""

    model_class = AnalyticsConnectionModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_active_connection(
        self,
        company_id: _uuid.UUID | str,
        tenant_id: str,
    ) -> Optional[AnalyticsConnectionModel]:
        """Return the single active analytics connection for a company+tenant."""
        cid = (
            _uuid.UUID(str(company_id))
            if isinstance(company_id, str)
            else company_id
        )
        stmt = (
            select(AnalyticsConnectionModel)
            .where(
                AnalyticsConnectionModel.company_id == cid,
                AnalyticsConnectionModel.tenant_id == tenant_id,
                AnalyticsConnectionModel.is_active.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_company_slug(
        self,
        company_slug: str,
        tenant_id: str,
    ) -> Optional[AnalyticsConnectionModel]:
        """Return active connection by company_slug + tenant_id."""
        stmt = (
            select(AnalyticsConnectionModel)
            .where(
                AnalyticsConnectionModel.company_slug == company_slug,
                AnalyticsConnectionModel.tenant_id == tenant_id,
                AnalyticsConnectionModel.is_active.is_(True),
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
            update(AnalyticsConnectionModel)
            .where(AnalyticsConnectionModel.id == cid)
            .values(is_active=False)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def update_tokens(
        self,
        connection_id: _uuid.UUID | str,
        *,
        access_token_encrypted: str,
        refresh_token_encrypted: str | None = None,
        token_expiry: datetime | None = None,
    ) -> None:
        """Update OAuth tokens after a token refresh."""
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        values: dict[str, object] = {
            "access_token_encrypted": access_token_encrypted,
        }
        if refresh_token_encrypted is not None:
            values["refresh_token_encrypted"] = refresh_token_encrypted
        if token_expiry is not None:
            values["token_expiry"] = token_expiry
        stmt = (
            update(AnalyticsConnectionModel)
            .where(AnalyticsConnectionModel.id == cid)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def update_sync_status(
        self,
        connection_id: _uuid.UUID | str,
        *,
        status: AnalyticsSyncStatus,
        error: str = "",
        last_sync_at: datetime | None = None,
    ) -> None:
        """Update sync status after a sync run."""
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        values: dict[str, object] = {
            "last_sync_status": status,
            "last_sync_error": error,
        }
        if last_sync_at is not None:
            values["last_sync_at"] = last_sync_at
        stmt = (
            update(AnalyticsConnectionModel)
            .where(AnalyticsConnectionModel.id == cid)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def update_property(
        self,
        connection_id: _uuid.UUID | str,
        *,
        ga4_property_id: str,
        ga4_property_name: str,
        ga4_account_id: str,
    ) -> None:
        """Store the selected GA4 property for syncing."""
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        stmt = (
            update(AnalyticsConnectionModel)
            .where(AnalyticsConnectionModel.id == cid)
            .values(
                ga4_property_id=ga4_property_id,
                ga4_property_name=ga4_property_name,
                ga4_account_id=ga4_account_id,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_all_active(self) -> Sequence[AnalyticsConnectionModel]:
        """Return all active connections (for scheduled sync job)."""
        stmt = select(AnalyticsConnectionModel).where(
            AnalyticsConnectionModel.is_active.is_(True)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


# ── GA4TrafficDataRepository ─────────────────────────────────────────


class GA4TrafficDataRepository(
    SQLAlchemyRepository[GA4TrafficDataModel]
):
    """Repository for GA4 traffic data (bulk upsert + query)."""

    model_class = GA4TrafficDataModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def bulk_upsert(self, items: list[dict[str, object]]) -> int:
        """Upsert traffic rows via ON CONFLICT DO UPDATE.

        Returns the number of rows affected.
        """
        if not items:
            return 0
        stmt = pg_insert(GA4TrafficDataModel).values(items)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_traffic_conn_date_page_src_med",
            set_={
                "campaign": stmt.excluded.campaign,
                "sessions": stmt.excluded.sessions,
                "engaged_sessions": stmt.excluded.engaged_sessions,
                "engagement_rate": stmt.excluded.engagement_rate,
                "bounce_rate": stmt.excluded.bounce_rate,
                "avg_session_duration_secs": stmt.excluded.avg_session_duration_secs,
                "screen_page_views": stmt.excluded.screen_page_views,
                "conversions": stmt.excluded.conversions,
                "new_users": stmt.excluded.new_users,
                "returning_users": stmt.excluded.returning_users,
                "synced_at": stmt.excluded.synced_at,
            },
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def get_by_date_range(
        self,
        company_id: _uuid.UUID | str,
        start_date: date,
        end_date: date,
        *,
        landing_page_url: str | None = None,
    ) -> Sequence[GA4TrafficDataModel]:
        """Return traffic rows for a company within a date range."""
        cid = (
            _uuid.UUID(str(company_id))
            if isinstance(company_id, str)
            else company_id
        )
        stmt = select(GA4TrafficDataModel).where(
            GA4TrafficDataModel.company_id == cid,
            GA4TrafficDataModel.date >= start_date,
            GA4TrafficDataModel.date <= end_date,
        )
        if landing_page_url is not None:
            stmt = stmt.where(
                GA4TrafficDataModel.landing_page_url == landing_page_url
            )
        stmt = stmt.order_by(GA4TrafficDataModel.date.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_ai_referrals(
        self,
        company_id: _uuid.UUID | str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Sequence[GA4TrafficDataModel]:
        """Return traffic rows flagged as AI referrals."""
        cid = (
            _uuid.UUID(str(company_id))
            if isinstance(company_id, str)
            else company_id
        )
        stmt = select(GA4TrafficDataModel).where(
            GA4TrafficDataModel.company_id == cid,
            GA4TrafficDataModel.is_ai_referral.is_(True),
        )
        if start_date is not None:
            stmt = stmt.where(GA4TrafficDataModel.date >= start_date)
        if end_date is not None:
            stmt = stmt.where(GA4TrafficDataModel.date <= end_date)
        stmt = stmt.order_by(GA4TrafficDataModel.date.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def delete_by_connection(
        self,
        connection_id: _uuid.UUID | str,
    ) -> int:
        """Delete all traffic data for a connection (GDPR purge).

        Returns the number of rows deleted.
        """
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        stmt = delete(GA4TrafficDataModel).where(
            GA4TrafficDataModel.connection_id == cid
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def mark_ai_referrals(
        self,
        connection_id: _uuid.UUID | str,
        source_platform_map: dict[str, str],
    ) -> int:
        """Tag rows whose source matches known AI referral domains.

        Args:
            connection_id: Scope to a specific connection.
            source_platform_map: Mapping of source domain → platform name,
                e.g. ``{"chatgpt.com": "openai", "claude.ai": "anthropic"}``.

        Returns:
            Number of rows updated.
        """
        if not source_platform_map:
            return 0
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        # Build CASE expression for ai_platform based on source patterns
        whens = [
            (
                GA4TrafficDataModel.source.ilike(f"%{domain}%"),
                platform,
            )
            for domain, platform in source_platform_map.items()
        ]
        platform_case = case(*whens, else_="")

        # Build OR condition for any matching source
        source_conditions = [
            GA4TrafficDataModel.source.ilike(f"%{domain}%")
            for domain in source_platform_map
        ]
        from sqlalchemy import or_

        stmt = (
            update(GA4TrafficDataModel)
            .where(
                GA4TrafficDataModel.connection_id == cid,
                GA4TrafficDataModel.is_ai_referral.is_(False),
                or_(*source_conditions),
            )
            .values(
                is_ai_referral=True,
                ai_platform=platform_case,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount


# ── GA4ConversionEventRepository ─────────────────────────────────────


class GA4ConversionEventRepository(
    SQLAlchemyRepository[GA4ConversionEventModel]
):
    """Repository for GA4 conversion events (bulk upsert + query)."""

    model_class = GA4ConversionEventModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def bulk_upsert(self, items: list[dict[str, object]]) -> int:
        """Upsert conversion rows via ON CONFLICT DO UPDATE.

        Returns the number of rows affected.
        """
        if not items:
            return 0
        stmt = pg_insert(GA4ConversionEventModel).values(items)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ga4_conv_conn_date_evt_page_src_med",
            set_={
                "event_count": stmt.excluded.event_count,
                "event_value": stmt.excluded.event_value,
                "synced_at": stmt.excluded.synced_at,
            },
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def get_by_date_range(
        self,
        company_id: _uuid.UUID | str,
        start_date: date,
        end_date: date,
        *,
        event_name: str | None = None,
    ) -> Sequence[GA4ConversionEventModel]:
        """Return conversion rows for a company within a date range."""
        cid = (
            _uuid.UUID(str(company_id))
            if isinstance(company_id, str)
            else company_id
        )
        stmt = select(GA4ConversionEventModel).where(
            GA4ConversionEventModel.company_id == cid,
            GA4ConversionEventModel.date >= start_date,
            GA4ConversionEventModel.date <= end_date,
        )
        if event_name is not None:
            stmt = stmt.where(
                GA4ConversionEventModel.event_name == event_name
            )
        stmt = stmt.order_by(GA4ConversionEventModel.date.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_ai_referrals(
        self,
        company_id: _uuid.UUID | str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Sequence[GA4ConversionEventModel]:
        """Return conversion rows flagged as AI referrals."""
        cid = (
            _uuid.UUID(str(company_id))
            if isinstance(company_id, str)
            else company_id
        )
        stmt = select(GA4ConversionEventModel).where(
            GA4ConversionEventModel.company_id == cid,
            GA4ConversionEventModel.is_ai_referral.is_(True),
        )
        if start_date is not None:
            stmt = stmt.where(GA4ConversionEventModel.date >= start_date)
        if end_date is not None:
            stmt = stmt.where(GA4ConversionEventModel.date <= end_date)
        stmt = stmt.order_by(GA4ConversionEventModel.date.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def delete_by_connection(
        self,
        connection_id: _uuid.UUID | str,
    ) -> int:
        """Delete all conversion events for a connection (GDPR purge).

        Returns the number of rows deleted.
        """
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        stmt = delete(GA4ConversionEventModel).where(
            GA4ConversionEventModel.connection_id == cid
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def mark_ai_referrals(
        self,
        connection_id: _uuid.UUID | str,
        source_platform_map: dict[str, str],
    ) -> int:
        """Tag rows whose source matches known AI referral domains.

        Args:
            connection_id: Scope to a specific connection.
            source_platform_map: Mapping of source domain → platform name.

        Returns:
            Number of rows updated.
        """
        if not source_platform_map:
            return 0
        cid = (
            _uuid.UUID(str(connection_id))
            if isinstance(connection_id, str)
            else connection_id
        )
        whens = [
            (
                GA4ConversionEventModel.source.ilike(f"%{domain}%"),
                platform,
            )
            for domain, platform in source_platform_map.items()
        ]
        platform_case = case(*whens, else_="")

        source_conditions = [
            GA4ConversionEventModel.source.ilike(f"%{domain}%")
            for domain in source_platform_map
        ]
        from sqlalchemy import or_

        stmt = (
            update(GA4ConversionEventModel)
            .where(
                GA4ConversionEventModel.connection_id == cid,
                GA4ConversionEventModel.is_ai_referral.is_(False),
                or_(*source_conditions),
            )
            .values(
                is_ai_referral=True,
                ai_platform=platform_case,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
