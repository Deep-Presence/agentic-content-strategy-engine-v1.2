"""Topic discovery & discovered topic ORM models."""
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin
from core.db.enums import PipelineStatus


# ── Topic Discoveries ───────────────────────────────────────────────────


class TopicDiscoveryModel(UUIDPKMixin, Base):
    __tablename__ = "topic_discoveries"
    __table_args__ = (
        Index("ix_topic_discoveries_company", "company_id"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    pipeline_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )
    status: Mapped[PipelineStatus] = mapped_column(
        PgEnum(PipelineStatus, name="pipeline_status_enum", create_type=True),
        default=PipelineStatus.pending,
    )
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Discovered Topics ──────────────────────────────────────────────────


class DiscoveredTopicModel(UUIDPKMixin, Base):
    __tablename__ = "discovered_topics"
    __table_args__ = (
        Index("ix_discovered_topics_discovery", "discovery_id"),
    )

    discovery_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_text: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
