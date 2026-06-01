"""CMS integration ORM models — connections, publish records, synced posts."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin, _utcnow
from core.db.enums import CMSPostStatus, CMSProvider, CMSPublishAction


# ── CMS Connections ───────────────────────────────────────────────────


class CMSConnectionModel(UUIDPKMixin, TimestampMixin, Base):
    """Company CMS connection with encrypted credentials and sync metadata.

    One company can have exactly one active CMS connection (for now).
    """

    __tablename__ = "cms_connections"
    __table_args__ = (
        Index(
            "uq_cms_conn_company_tenant",
            "company_id",
            "tenant_id",
            unique=True,
        ),
        Index("ix_cms_conn_company_slug", "company_slug"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    company_slug: Mapped[str] = mapped_column(String, nullable=False)

    provider: Mapped[CMSProvider] = mapped_column(
        PgEnum(CMSProvider, name="cms_provider_enum", create_type=False),
        nullable=False,
    )
    site_url: Mapped[str] = mapped_column(String(512), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)

    site_name: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    cms_version: Mapped[str] = mapped_column(
        String(50), default="", server_default=""
    )
    user_display_name: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_post_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )


# ── CMS Publish Records ──────────────────────────────────────────────


class CMSPublishRecordModel(UUIDPKMixin, TimestampMixin, Base):
    """Audit trail of each publish/update action from Deep Presence to CMS.

    Links a Content Engine brief to its CMS post.
    """

    __tablename__ = "cms_publish_records"
    __table_args__ = (
        Index("ix_cms_pub_company_brief", "company_slug", "brief_id"),
        Index("ix_cms_pub_connection", "connection_id"),
    )

    connection_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("cms_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_slug: Mapped[str] = mapped_column(String, nullable=False)

    # Deep Presence side
    brief_id: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_slug: Mapped[str] = mapped_column(
        String, nullable=False, default=""
    )
    content_engine_run_id: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )

    # CMS side
    cms_post_id: Mapped[str] = mapped_column(String(50), nullable=False)
    cms_post_url: Mapped[str] = mapped_column(
        String(1024), default="", server_default=""
    )
    cms_post_slug: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )

    # Publish metadata
    action: Mapped[CMSPublishAction] = mapped_column(
        PgEnum(
            CMSPublishAction,
            name="cms_publish_action_enum",
            create_type=False,
        ),
        nullable=False,
    )
    status_at_publish: Mapped[CMSPostStatus] = mapped_column(
        PgEnum(
            CMSPostStatus,
            name="cms_post_status_enum",
            create_type=False,
        ),
        default=CMSPostStatus.draft,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
    )

    # Snapshot of what was sent
    title_published: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )
    word_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )


# ── CMS Synced Posts ──────────────────────────────────────────────────


class CMSSyncedPostModel(UUIDPKMixin, TimestampMixin, Base):
    """Local index of existing posts on the client's CMS.

    Populated by the initial sync flow and refreshed periodically.

    Enables:
    - Cannibalization check (does a post on this topic already exist?)
    - Staleness detection (was this post modified more than N days ago?)
    - Content refresh targeting (which existing posts should we update?)
    """

    __tablename__ = "cms_synced_posts"
    __table_args__ = (
        Index(
            "uq_cms_synced_conn_post",
            "connection_id",
            "cms_post_id",
            unique=True,
        ),
        Index("ix_cms_synced_company_stale", "company_slug", "is_stale"),
        Index("ix_cms_synced_company", "company_slug"),
    )

    connection_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("cms_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_slug: Mapped[str] = mapped_column(String, nullable=False)

    cms_post_id: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(
        String(1024), default="", server_default=""
    )
    excerpt: Mapped[str] = mapped_column(Text, default="", server_default="")
    content_preview: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    word_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    categories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    seo_title: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )
    seo_description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )

    # Analysis fields
    is_stale: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    staleness_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    detected_primary_keyword: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    cannibalization_risk: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Refresh tracking
    queued_for_refresh: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    refresh_brief_id: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    refresh_queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
    )

    # ── Content Inventory link ────────────────────────────────────
    content_inventory_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_inventory.id", ondelete="SET NULL"),
        nullable=True,
        comment="Link to the canonical content inventory record for this CMS post.",
    )
