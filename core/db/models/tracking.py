"""Tracking domain models — periodic snapshots, mention tracking, content performance."""
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, UUIDPKMixin
from core.db.enums import SearchEngine, TrackingStatus


# ── Tracking Snapshots ───────────────────────────────────────────────────


class TrackingSnapshotModel(UUIDPKMixin, Base):
    """Periodic tracking snapshot for a company (optionally per-product)."""

    __tablename__ = "tracking_snapshots"
    __table_args__ = (
        # Codex C9 — NULL != NULL in Postgres, so we need two partial unique
        # indexes: one for rows WITH a product_id, one for rows WITHOUT.
        Index(
            "ix_tracking_snapshots_with_product",
            "company_id",
            "product_id",
            "snapshot_date",
            unique=True,
            postgresql_where=text("product_id IS NOT NULL"),
        ),
        Index(
            "ix_tracking_snapshots_no_product",
            "company_id",
            "snapshot_date",
            unique=True,
            postgresql_where=text("product_id IS NULL"),
        ),
        Index("ix_tracking_snapshots_company_date", "company_id", "snapshot_date"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    gap_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )
    status: Mapped[TrackingStatus] = mapped_column(
        PgEnum(TrackingStatus, name="tracking_status_enum", create_type=True),
        default=TrackingStatus.pending,
    )
    queries_checked: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    mention_tracks: Mapped[list[ContentMentionTrackingModel]] = relationship(
        "ContentMentionTrackingModel",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    piece_tracks: Mapped[list[ContentPieceTrackingModel]] = relationship(
        "ContentPieceTrackingModel",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ── Content Mention Tracking ─────────────────────────────────────────────


class ContentMentionTrackingModel(UUIDPKMixin, Base):
    """Per-query, per-engine mention check within a tracking snapshot."""

    __tablename__ = "content_mention_tracking"
    __table_args__ = (
        Index("ix_content_mention_tracking_snap_engine", "snapshot_id", "engine"),
        Index(
            "ix_content_mention_tracking_snap_cluster",
            "snapshot_id",
            "cluster_name",
        ),
    )

    snapshot_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tracking_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cluster_name: Mapped[str | None] = mapped_column(String, nullable=True)
    engine: Mapped[SearchEngine] = mapped_column(
        PgEnum(SearchEngine, name="search_engine_enum", create_type=True),
        nullable=False,
    )
    company_mentioned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    company_citation_rank: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    company_url_cited: Mapped[str | None] = mapped_column(Text, nullable=True)
    competitor_urls_cited: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    snapshot: Mapped[TrackingSnapshotModel] = relationship(
        "TrackingSnapshotModel", back_populates="mention_tracks"
    )


# ── Content Piece Tracking ───────────────────────────────────────────────


class ContentPieceTrackingModel(UUIDPKMixin, Base):
    """Per-URL performance tracking within a tracking snapshot."""

    __tablename__ = "content_piece_tracking"
    __table_args__ = (
        Index("ix_content_piece_tracking_snap_url", "snapshot_id", "url"),
        Index(
            "ix_content_piece_tracking_piece_snap",
            "content_piece_id",
            "snapshot_id",
        ),
    )

    snapshot_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tracking_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_piece_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_pieces.id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_count_by_platform: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    avg_citation_rank: Mapped[float | None] = mapped_column(Float, nullable=True)
    traffic_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    snapshot: Mapped[TrackingSnapshotModel] = relationship(
        "TrackingSnapshotModel", back_populates="piece_tracks"
    )
