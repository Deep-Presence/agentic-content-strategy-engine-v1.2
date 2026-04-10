"""Durable batch/topic run models for TD-entry Content Engine execution."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin, _utcnow


class ContentEngineBatchRunModel(UUIDPKMixin, TimestampMixin, Base):
    """A user-submitted batch of TD-originated topics sent to Content Engine."""

    __tablename__ = "content_engine_batch_runs"
    __table_args__ = (
        Index("ix_ce_batch_runs_slug_status", "effective_slug", "status"),
        Index("ix_ce_batch_runs_company_created", "company_id", "created_at"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    pipeline_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_count: Mapped[int] = mapped_column(nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    cancelled_count: Mapped[int] = mapped_column(nullable=False, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ContentEngineTopicRunModel(UUIDPKMixin, TimestampMixin, Base):
    """Durable execution row for one TopicAssignment through TD-entry CE."""

    __tablename__ = "content_engine_topic_runs"
    __table_args__ = (
        Index("ix_ce_topic_runs_slug_status", "effective_slug", "status"),
        Index("ix_ce_topic_runs_assignment", "topic_assignment_id"),
        Index("ix_ce_topic_runs_display_id", "display_id"),
        Index("ix_ce_topic_runs_batch_created", "batch_run_id", "created_at"),
        Index("ix_ce_topic_runs_ga_assignment", "ga_run_id", "topic_assignment_id"),
        UniqueConstraint(
            "batch_run_id",
            "topic_assignment_id",
            name="uq_ce_topic_runs_batch_assignment",
        ),
    )

    batch_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_engine_batch_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_piece_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_pieces.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)
    topic_assignment_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_id: Mapped[str] = mapped_column(String(20), nullable=False)
    topic_text: Mapped[str] = mapped_column(Text, nullable=False)
    brief_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ga_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=True,
    )
    pipeline_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entry_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ContentEngineTopicEventModel(UUIDPKMixin, Base):
    """Append-only per-topic execution events for audit and replay."""

    __tablename__ = "content_engine_topic_events"
    __table_args__ = (
        Index("ix_ce_topic_events_assignment_seq", "topic_assignment_id", "seq"),
        Index("ix_ce_topic_events_display_created", "display_id", "created_at"),
        UniqueConstraint("topic_run_id", "seq", name="uq_ce_topic_events_run_seq"),
    )

    topic_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_engine_topic_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_assignment_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_id: Mapped[str] = mapped_column(String(20), nullable=False)
    content_piece_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_pieces.id", ondelete="SET NULL"),
        nullable=True,
    )
    pipeline_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
