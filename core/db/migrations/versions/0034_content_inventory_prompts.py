"""Create content_inventory_prompts join table.

Links content inventory pages to tracked prompts for per-page AI visibility
monitoring.  Supports many-to-many (one prompt can be relevant to multiple
pages; one page generates multiple prompts).

Per-link metadata: buyer_stage, intent_type, is_branded, approved,
is_user_edited.  generation_run_id groups prompts from the same
generation batch.

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0034"
down_revision: str = "0033"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "content_inventory_prompts",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_inventory_id", PgUUID(as_uuid=True), sa.ForeignKey("content_inventory.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tracked_prompt_id", PgUUID(as_uuid=True), sa.ForeignKey("tracked_prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_run_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("buyer_stage", sa.String(10), nullable=True),
        sa.Column("intent_type", sa.String(20), nullable=True),
        sa.Column("is_branded", sa.Boolean, server_default="false", nullable=False),
        sa.Column("approved", sa.Boolean, server_default="true", nullable=False),
        sa.Column("is_user_edited", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Unique: one link per (page, prompt) pair
    op.create_unique_constraint(
        "uq_ci_prompts_inventory_prompt",
        "content_inventory_prompts",
        ["content_inventory_id", "tracked_prompt_id"],
    )

    # Indexes for bidirectional lookups and generation run grouping
    op.create_index("ix_ci_prompts_inventory_id", "content_inventory_prompts", ["content_inventory_id"])
    op.create_index("ix_ci_prompts_prompt_id", "content_inventory_prompts", ["tracked_prompt_id"])
    op.create_index("ix_ci_prompts_generation_run", "content_inventory_prompts", ["generation_run_id"])


def downgrade() -> None:
    op.drop_index("ix_ci_prompts_generation_run", table_name="content_inventory_prompts")
    op.drop_index("ix_ci_prompts_prompt_id", table_name="content_inventory_prompts")
    op.drop_index("ix_ci_prompts_inventory_id", table_name="content_inventory_prompts")
    op.drop_constraint("uq_ci_prompts_inventory_prompt", "content_inventory_prompts", type_="unique")
    op.drop_table("content_inventory_prompts")
