"""Add durable topic assignment cannibalization table.

Revision ID: 0041
Revises: 0040
Create Date: 2026-04-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041"
down_revision: str = "0040"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "topic_assignment_cannibalization",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discovery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("top_match_inventory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("max_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("risk_level", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column(
            "recommended_action",
            sa.String(length=64),
            nullable=False,
            server_default="safe_to_create_new",
        ),
        sa.Column("reasons_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("matches_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("signals_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["assignment_id"], ["topic_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["discovery_id"], ["topic_discoveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["top_match_inventory_id"], ["content_inventory.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            name="uq_topic_assignment_cannibalization_assignment",
        ),
    )
    op.create_index(
        "ix_td_assignment_cannibalization_discovery",
        "topic_assignment_cannibalization",
        ["discovery_id"],
    )
    op.create_index(
        "ix_td_assignment_cannibalization_company_level",
        "topic_assignment_cannibalization",
        ["company_id", "risk_level"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_td_assignment_cannibalization_company_level",
        table_name="topic_assignment_cannibalization",
    )
    op.drop_index(
        "ix_td_assignment_cannibalization_discovery",
        table_name="topic_assignment_cannibalization",
    )
    op.drop_table("topic_assignment_cannibalization")
