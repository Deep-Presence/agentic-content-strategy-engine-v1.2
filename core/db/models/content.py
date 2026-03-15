"""Content domain models — generated content pieces and research artifacts."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.enums import ArtifactStatus, ArtifactType, ContentPieceStatus


# ── Content Pieces ───────────────────────────────────────────────────────


class ContentPieceModel(UUIDPKMixin, TimestampMixin, Base):
    """A generated content piece from the content engine pipeline."""

    __tablename__ = "content_pieces"
    __table_args__ = (
        Index("ix_content_pieces_run", "run_id"),
        Index("ix_content_pieces_gap_query", "gap_run_id", "query_id"),
        Index("ix_content_pieces_status", "status"),
        Index("ix_content_pieces_topic_assignment", "topic_assignment_id"),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    gap_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cluster_name: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ContentPieceStatus | None] = mapped_column(
        PgEnum(ContentPieceStatus, name="content_piece_status_enum", create_type=True),
        nullable=True,
    )
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    citability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_assignment_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_assignments.id", ondelete="SET NULL"),
        nullable=True,
    )


# ── Research Artifacts ───────────────────────────────────────────────────


class ResearchArtifactModel(UUIDPKMixin, TimestampMixin, Base):
    """Versioned research artifact (company context, persona, style guide)."""

    __tablename__ = "research_artifacts"
    __table_args__ = (
        Index(
            "ix_research_artifacts_company_type", "company_id", "artifact_type"
        ),
        Index(
            "ix_research_artifacts_slug_type", "effective_slug", "artifact_type"
        ),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)
    artifact_type: Mapped[ArtifactType] = mapped_column(
        PgEnum(ArtifactType, name="artifact_type_enum", create_type=True),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ArtifactStatus] = mapped_column(
        PgEnum(ArtifactStatus, name="artifact_status_enum", create_type=True),
        default=ArtifactStatus.draft,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
