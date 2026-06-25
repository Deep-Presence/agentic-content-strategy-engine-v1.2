"""Add query fanout support to daily tracker.

Adds self-referential parent_prompt_id FK to tracked_prompts for fanout
query variants, plus denormalized parent_prompt_id on daily_run_responses
for efficient analytics aggregation.

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0024"
down_revision: str = "0023"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # -- tracked_prompts: fanout columns --
    op.add_column(
        "tracked_prompts",
        sa.Column(
            "parent_prompt_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("tracked_prompts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "tracked_prompts",
        sa.Column("fanout_axis", sa.String(), nullable=True),
    )
    op.add_column(
        "tracked_prompts",
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Index for fetching all fanouts of a parent
    op.create_index(
        "ix_tracked_prompts_parent_id",
        "tracked_prompts",
        ["parent_prompt_id"],
    )
    # Partial index for fast parent-only listing
    op.execute(
        "CREATE INDEX ix_tracked_prompts_company_parent_null "
        "ON tracked_prompts (company_id) "
        "WHERE parent_prompt_id IS NULL"
    )

    # -- daily_run_responses: denormalized parent_prompt_id --
    op.add_column(
        "daily_run_responses",
        sa.Column("parent_prompt_id", PgUUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_daily_run_responses_parent_prompt",
        "daily_run_responses",
        ["parent_prompt_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_run_responses_parent_prompt",
        table_name="daily_run_responses",
    )
    op.drop_column("daily_run_responses", "parent_prompt_id")

    op.execute("DROP INDEX IF EXISTS ix_tracked_prompts_company_parent_null")
    op.drop_index(
        "ix_tracked_prompts_parent_id",
        table_name="tracked_prompts",
    )
    op.drop_column("tracked_prompts", "pinned")
    op.drop_column("tracked_prompts", "fanout_axis")
    op.drop_column("tracked_prompts", "parent_prompt_id")
