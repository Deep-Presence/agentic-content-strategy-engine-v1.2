"""Analytics integration ORM models.

Tables:
  analytics_connections   — OAuth credentials, GA4 property metadata, sync status
  ga4_traffic_data        — GA4 traffic by landing page + source/medium
  ga4_conversion_events   — GA4 conversion events by landing page + source/medium
"""
from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    ENUM as PgEnum,
    JSONB,
    UUID as PgUUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin, _utcnow
from core.db.enums import AnalyticsProvider, AnalyticsSyncStatus


# ── analytics_connections ────────────────────────────────────────────


class AnalyticsConnectionModel(UUIDPKMixin, TimestampMixin, Base):
    """OAuth connection to an analytics provider (GA4)."""

    __tablename__ = "analytics_connections"
    __table_args__ = (
        Index(
            "uq_analytics_conn_slug_tenant_provider",
            "company_slug",
            "tenant_id",
            "provider",
            unique=True,
        ),
        Index("ix_analytics_conn_company_slug", "company_slug"),
        Index("ix_analytics_conn_company_id", "company_id"),
    )

    # ── Foreign keys ─────────────────────────────────────────────────
    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_slug: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Provider ─────────────────────────────────────────────────────
    provider: Mapped[AnalyticsProvider] = mapped_column(
        PgEnum(
            AnalyticsProvider,
            name="analytics_provider_enum",
            create_type=False,
        ),
        nullable=False,
    )

    # ── OAuth tokens (Fernet-encrypted) ──────────────────────────────
    access_token_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    refresh_token_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── GA4 property metadata ────────────────────────────────────────
    ga4_property_id: Mapped[str] = mapped_column(
        String(50), default="", server_default=""
    )
    ga4_property_name: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    ga4_account_id: Mapped[str] = mapped_column(
        String(50), default="", server_default=""
    )

    # ── Scopes & status ──────────────────────────────────────────────
    scopes_granted: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # ── Sync tracking ────────────────────────────────────────────────
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_status: Mapped[AnalyticsSyncStatus | None] = mapped_column(
        PgEnum(
            AnalyticsSyncStatus,
            name="analytics_sync_status_enum",
            create_type=False,
        ),
        nullable=True,
    )
    last_sync_error: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    sync_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default="{}"
    )


# ── ga4_traffic_data ─────────────────────────────────────────────────


class GA4TrafficDataModel(UUIDPKMixin, TimestampMixin, Base):
    """GA4 traffic data by page path + source/medium.

    ``landing_page_url`` is the historical column name and currently stores the
    GA4 path used for Content Performance joins.
    """

    __tablename__ = "ga4_traffic_data"
    __table_args__ = (
        Index(
            "uq_ga4_traffic_conn_date_page_src_med",
            "connection_id",
            "date",
            "landing_page_url",
            "source",
            "medium",
            unique=True,
        ),
        Index("ix_ga4_traffic_company_date", "company_id", "date"),
        Index("ix_ga4_traffic_ai_referral", "company_id", "is_ai_referral"),
    )

    # ── Foreign keys ─────────────────────────────────────────────────
    connection_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("analytics_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Dimensions ───────────────────────────────────────────────────
    date: Mapped[date] = mapped_column(Date, nullable=False)
    landing_page_url: Mapped[str] = mapped_column(
        String(2048), nullable=False
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    medium: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )

    # ── Metrics ──────────────────────────────────────────────────────
    sessions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    engaged_sessions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    engagement_rate: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0"
    )
    bounce_rate: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0"
    )
    avg_session_duration_secs: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0"
    )
    screen_page_views: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    conversions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    new_users: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    returning_users: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # ── AI referral classification ───────────────────────────────────
    is_ai_referral: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ai_platform: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )

    # ── Sync metadata ────────────────────────────────────────────────
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )


# ── ga4_conversion_events ────────────────────────────────────────────


class GA4ConversionEventModel(UUIDPKMixin, TimestampMixin, Base):
    """GA4 conversion events by landing page + source/medium."""

    __tablename__ = "ga4_conversion_events"
    __table_args__ = (
        Index(
            "uq_ga4_conv_conn_date_evt_page_src_med",
            "connection_id",
            "date",
            "event_name",
            "landing_page_url",
            "source",
            "medium",
            unique=True,
        ),
        Index("ix_ga4_conv_company_date", "company_id", "date"),
        Index("ix_ga4_conv_ai_referral", "company_id", "is_ai_referral"),
    )

    # ── Foreign keys ─────────────────────────────────────────────────
    connection_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("analytics_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Dimensions ───────────────────────────────────────────────────
    date: Mapped[date] = mapped_column(Date, nullable=False)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False)
    landing_page_url: Mapped[str] = mapped_column(
        String(2048), nullable=False
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    medium: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Metrics ──────────────────────────────────────────────────────
    event_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    event_value: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0"
    )

    # ── AI referral classification ───────────────────────────────────
    is_ai_referral: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ai_platform: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )

    # ── Sync metadata ────────────────────────────────────────────────
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
