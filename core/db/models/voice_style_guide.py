"""Voice Style Guide ORM models.

Tables:
- vsg_runs — top-level VSG run per company/product
- vsg_authors — individual author research versions
- vsg_guides — final voice style guide versions
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


# ── VSG Runs ──────────────────────────────────────────────────────────


class VSGRunModel(UUIDPKMixin, Base):
    """Top-level Voice Style Guide run for a company (optionally scoped to product)."""

    __tablename__ = "vsg_runs"
    __table_args__ = (
        Index("ix_vsg_runs_company", "company_id"),
        Index("ix_vsg_runs_effective_slug", "effective_slug"),
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
    ap_manifest_version: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    authors_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    authors_approved: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    guide_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )


# ── VSG Authors ───────────────────────────────────────────────────────


class VSGAuthorModel(UUIDPKMixin, Base):
    """A versioned author research document."""

    __tablename__ = "vsg_authors"
    __table_args__ = (
        Index("ix_vsg_authors_run", "vsg_run_id"),
        Index("ix_vsg_authors_author_id", "vsg_run_id", "author_id"),
    )

    vsg_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vsg_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── VSG Guides ────────────────────────────────────────────────────────


class VSGGuideModel(UUIDPKMixin, Base):
    """A versioned voice style guide document."""

    __tablename__ = "vsg_guides"
    __table_args__ = (
        Index("ix_vsg_guides_run", "vsg_run_id"),
    )

    vsg_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vsg_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    source_authors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    promoted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
