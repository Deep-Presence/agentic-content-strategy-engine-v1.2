"""ORM model for the content_inventory_prompts join table.

Links content inventory pages to tracked prompts for per-page AI visibility
monitoring.  Supports many-to-many: one prompt can be relevant to multiple
pages (cross-page dedup creates one canonical prompt linked to both), and
one page generates multiple prompts (k per page).

Used by:
- Content-to-Prompt pipeline: generation + dedup + approval
- Daily Tracker: per-page metric aggregation (mention_rate, citation_rate)
- Prompt Tracking frontend: "pages" tab with per-page drawer
"""
from __future__ import annotations

import uuid as _uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPKMixin


class ContentInventoryPromptModel(UUIDPKMixin, TimestampMixin, Base):
    """Join table linking content inventory pages to tracked prompts.

    Each row represents one page→prompt association with per-link metadata
    about the generation context (buyer_stage, intent_type) and approval state.
    """

    __tablename__ = "content_inventory_prompts"
    __table_args__ = (
        UniqueConstraint(
            "content_inventory_id",
            "tracked_prompt_id",
            name="uq_ci_prompts_inventory_prompt",
        ),
        Index("ix_ci_prompts_inventory_id", "content_inventory_id"),
        Index("ix_ci_prompts_prompt_id", "tracked_prompt_id"),
        Index("ix_ci_prompts_generation_run", "generation_run_id"),
    )

    # ── Foreign keys ──────────────────────────────────────────────
    content_inventory_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_inventory.id", ondelete="CASCADE"),
        nullable=False,
    )
    tracked_prompt_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tracked_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Generation provenance ─────────────────────────────────────
    generation_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=True,
        comment="Groups prompts from the same generation batch. NULL for manual links.",
    )

    # ── Classification (per-link context) ─────────────────────────
    buyer_stage: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="tofu | mofu | bofu — from the generation LLM output.",
    )
    intent_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="informational | commercial | navigational | transactional.",
    )
    is_branded: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # ── Approval & edit tracking ──────────────────────────────────
    approved: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        comment="false = pending manual review. Set by auto_approve config.",
    )
    is_user_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="Protects manually edited prompts from re-generation overwrite.",
    )

    # ── Relationships ─────────────────────────────────────────────
    content_inventory = relationship(
        "ContentInventoryModel",
        foreign_keys=[content_inventory_id],
        lazy="select",
    )
    tracked_prompt = relationship(
        "TrackedPromptModel",
        foreign_keys=[tracked_prompt_id],
        lazy="select",
    )
