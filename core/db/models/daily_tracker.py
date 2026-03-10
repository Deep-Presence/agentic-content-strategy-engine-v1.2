"""ORM models for the Daily LLM Visibility Tracker.

Three tables:
    ``tracked_prompts``     — Prompt library (CRUD + gap-analysis import)
    ``daily_runs``          — Daily run execution metadata
    ``daily_run_responses`` — Per-prompt, per-platform raw LLM responses
                              with mention analysis results

Design decisions:
    - ``company_id`` is a String (not FK to companies) so the tracker can
      work standalone before the company is fully onboarded in the auth
      system.  The API layer validates company access via auth middleware.
    - Status and source are plain VARCHAR (not PG enums) to avoid migration
      friction when new values are added — same pattern as ``api_tasks``.
    - Mention analysis fields are stored inline on the response row
      (not a separate table) because they are always read together and
      the 1:1 relationship makes a join unnecessary.

Follows patterns from ``core/db/models/tracking.py`` and
``core/db/base.py`` (UUIDPKMixin, TimestampMixin).
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPKMixin


# ── Tracked Prompts ────────────────────────────────────────────────────


class TrackedPromptModel(UUIDPKMixin, TimestampMixin, Base):
    """A prompt tracked for daily visibility monitoring.

    Prompts are created manually or imported from gap analysis query
    artifacts.  Each prompt targets one or more AI platforms.
    """

    __tablename__ = "tracked_prompts"
    __table_args__ = (
        Index("ix_tracked_prompts_company_id", "company_id"),
        Index("ix_tracked_prompts_company_active", "company_id", "active"),
        Index("ix_tracked_prompts_source", "source"),
    )

    company_id: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    # Why: JSONB for tags and platforms — flexible list storage without a
    # join table, and Postgres can index with GIN if needed later.
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="manual")
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    platforms: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # relationships
    responses: Mapped[list[DailyRunResponseModel]] = relationship(
        "DailyRunResponseModel",
        back_populates="prompt",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ── Daily Runs ─────────────────────────────────────────────────────────


class DailyRunModel(UUIDPKMixin, TimestampMixin, Base):
    """Metadata for a single daily visibility run execution."""

    __tablename__ = "daily_runs"
    __table_args__ = (
        Index("ix_daily_runs_company_id", "company_id"),
        Index("ix_daily_runs_status", "status"),
        Index("ix_daily_runs_company_status", "company_id", "status"),
    )

    company_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending"
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    engine_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # relationships
    responses: Mapped[list[DailyRunResponseModel]] = relationship(
        "DailyRunResponseModel",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ── Daily Run Responses ────────────────────────────────────────────────


class DailyRunResponseModel(UUIDPKMixin, Base):
    """Per-prompt, per-platform response with inline mention analysis.

    Stores the raw LLM response text alongside deterministic mention
    detection results (brand_mentioned, competitor_mentions, citations).
    """

    __tablename__ = "daily_run_responses"
    __table_args__ = (
        Index("ix_daily_run_responses_run_id", "run_id"),
        Index("ix_daily_run_responses_prompt_id", "prompt_id"),
        Index("ix_daily_run_responses_run_engine", "run_id", "engine"),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("daily_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tracked_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    engine: Mapped[str] = mapped_column(String, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Inline mention analysis — always read together with the response.
    brand_mentioned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    brand_mention_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    competitor_mentions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    citations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    citation_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    run: Mapped[DailyRunModel] = relationship(
        "DailyRunModel", back_populates="responses"
    )
    prompt: Mapped[TrackedPromptModel] = relationship(
        "TrackedPromptModel", back_populates="responses"
    )
