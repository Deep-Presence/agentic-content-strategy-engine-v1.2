"""Pipeline run & stage log ORM models."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.enums import PipelineStatus, PipelineType, StageStatus


# ── Pipeline Runs ────────────────────────────────────────────────────────


class PipelineRunModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_company_type", "company_id", "pipeline_type"),
        Index("ix_pipeline_runs_slug_type", "effective_slug", "pipeline_type"),
        Index(
            "ix_pipeline_runs_active",
            "status",
            postgresql_where="status IN ('pending', 'running')",
        ),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)
    pipeline_type: Mapped[PipelineType] = mapped_column(
        PgEnum(PipelineType, name="pipeline_type_enum", create_type=True),
        nullable=False,
    )
    parent_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )
    status: Mapped[PipelineStatus] = mapped_column(
        PgEnum(PipelineStatus, name="pipeline_status_enum", create_type=True),
        nullable=False,
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stages_executed: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    parent_run: Mapped[PipelineRunModel | None] = relationship(
        "PipelineRunModel", remote_side="PipelineRunModel.id", lazy="selectin"
    )
    stage_logs: Mapped[list[PipelineStageLogModel]] = relationship(
        "PipelineStageLogModel",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ── Pipeline Stage Logs ──────────────────────────────────────────────────


class PipelineStageLogModel(UUIDPKMixin, Base):
    """Individual stage execution record within a pipeline run.

    Uses UUIDPKMixin only — no timestamp mixin needed since ordering is
    derived from the parent run and ``started_at`` / ``completed_at``.
    """

    __tablename__ = "pipeline_stage_logs"
    __table_args__ = (Index("ix_pipeline_stage_logs_run_id", "run_id"),)

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[StageStatus | None] = mapped_column(
        PgEnum(StageStatus, name="stage_status_enum", create_type=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_from_cache: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # relationships
    run: Mapped[PipelineRunModel] = relationship(
        "PipelineRunModel", back_populates="stage_logs"
    )
