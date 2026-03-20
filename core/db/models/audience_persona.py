"""Audience Persona ORM models.

Tables:
- persona_runs — top-level AP run per company/product
- persona_profiles — individual persona profile versions
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
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


# ── Persona Runs ───────────────────────────────────────────────────────


class PersonaRunModel(UUIDPKMixin, Base):
    """Top-level Audience Persona run for a company (optionally scoped to product)."""

    __tablename__ = "persona_runs"
    __table_args__ = (
        Index("ix_persona_runs_company", "company_id"),
        Index("ix_persona_runs_effective_slug", "effective_slug"),
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
    kb_synthesis_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    briefs_suggested: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    briefs_approved: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    profiles_generated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )


# ── Persona Profiles ──────────────────────────────────────────────────


class PersonaProfileModel(UUIDPKMixin, Base):
    """A versioned persona profile document."""

    __tablename__ = "persona_profiles"
    __table_args__ = (
        Index("ix_persona_profiles_run", "persona_run_id"),
        Index(
            "ix_persona_profiles_persona_id", "persona_run_id", "persona_id"
        ),
    )

    persona_run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("persona_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    persona_id: Mapped[str] = mapped_column(String, nullable=False)
    persona_name: Mapped[str] = mapped_column(String, nullable=False)
    tagline: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    created_by: Mapped[str | None] = mapped_column(
        String, nullable=True, default="agent",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
