"""LLM cost tracking ORM models — per-call events + editable pricing."""
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
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin


class LLMCostEventModel(UUIDPKMixin, TimestampMixin, Base):
    """One row per LLM call — written fire-and-forget by track_llm_cost()."""

    __tablename__ = "llm_cost_events"
    __table_args__ = (
        Index("ix_llm_cost_events_event_time", "event_time"),
        Index("ix_llm_cost_events_model_time", "model", "event_time"),
        Index("ix_llm_cost_events_pipeline_time", "pipeline", "event_time"),
        Index(
            "ix_llm_cost_events_run_id",
            "run_id",
            postgresql_where="run_id IS NOT NULL",
        ),
        Index("ix_llm_cost_events_slug_time", "company_slug", "event_time"),
        Index("ix_llm_cost_events_agent_key", "agent_key"),
        Index("ix_llm_cost_events_credential_id", "credential_id"),
        Index("ix_llm_cost_events_model_config_id", "model_config_id"),
    )

    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    model: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    pipeline: Mapped[str] = mapped_column(String, nullable=False)
    pipeline_step: Mapped[str] = mapped_column(String, nullable=False, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    company_slug: Mapped[str] = mapped_column(String, nullable=False, default="")
    workspace_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_key: Mapped[str | None] = mapped_column(String, nullable=True)
    credential_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspace_llm_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_config_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspace_agent_model_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    actual_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    workspace_billed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    call_site: Mapped[str] = mapped_column(String, nullable=False, default="")
    source: Mapped[str] = mapped_column(String, nullable=False, default="native")
    run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )
    extra_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ModelPricingModel(UUIDPKMixin, TimestampMixin, Base):
    """Editable pricing per model — source of truth for the cost dashboard."""

    __tablename__ = "model_pricing"
    __table_args__ = (
        Index("uq_model_pricing_model_name", "model_name", unique=True),
    )

    model_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    input_cost_per_1m: Mapped[float] = mapped_column(Float, nullable=False)
    output_cost_per_1m: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
