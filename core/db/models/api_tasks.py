"""API task ORM model — mirrors PipelineTask for DB persistence."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin


class ApiTaskModel(UUIDPKMixin, TimestampMixin, Base):
    """Persistent representation of a PipelineTask.

    Status is a plain String (not PG enum) because TaskStatus includes
    ``pending_approval`` and ``failed_restart`` which don't exist in
    ``pipeline_status_enum``.
    """

    __tablename__ = "api_tasks"
    __table_args__ = (
        Index("ix_api_tasks_task_id", "task_id", unique=True),
        Index("ix_api_tasks_effective_slug", "effective_slug"),
        Index("ix_api_tasks_status", "status"),
        Index("ix_api_tasks_company_pipeline", "company_slug", "pipeline"),
        Index("ix_api_tasks_worker_id", "worker_id"),
    )

    task_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    pipeline: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    company_slug: Mapped[str] = mapped_column(String, nullable=False, default="")
    product_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    current_step: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_history: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pipeline_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    workspace_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
