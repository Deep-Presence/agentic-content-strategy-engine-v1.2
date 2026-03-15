"""Knowledge Base ORM models.

Tables:
- kb_runs — top-level KB run per company/product
- kb_documents — per doc_type versioned entries (company_overview, etc.)
- kb_syntheses — synthesis versions
"""
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin
from core.db.enums import ResearchRunStatus


# ── KB Runs ────────────────────────────────────────────────────────────


class KBRunModel(UUIDPKMixin, Base):
    """Top-level Knowledge Base run for a company (optionally scoped to product)."""

    __tablename__ = "kb_runs"
    __table_args__ = (
        Index("ix_kb_runs_company", "company_id"),
        Index("ix_kb_runs_effective_slug", "effective_slug"),
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
    effective_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ResearchRunStatus] = mapped_column(
        PgEnum(
            ResearchRunStatus,
            name="research_run_status_enum",
            create_type=True,
        ),
        default=ResearchRunStatus.draft,
    )
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    synthesis_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    last_full_refresh: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )


# ── KB Documents ───────────────────────────────────────────────────────


class KBDocumentModel(UUIDPKMixin, Base):
    """A versioned KB document entry (company_overview, customer_reviews, etc.)."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        Index("ix_kb_documents_run_doctype", "kb_run_id", "doc_type"),
    )

    kb_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("kb_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    staleness_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90, server_default="90",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── KB Syntheses ───────────────────────────────────────────────────────


class KBSynthesisModel(UUIDPKMixin, Base):
    """A versioned KB synthesis document."""

    __tablename__ = "kb_syntheses"
    __table_args__ = (
        Index("ix_kb_syntheses_run", "kb_run_id"),
    )

    kb_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("kb_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    promoted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
