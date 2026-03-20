"""Add topic-discovery ↔ content integration columns.

- content_pieces.topic_assignment_id (FK → topic_assignments.id)
- run_queries.source_topic_ids (ARRAY(TEXT))
- query_gaps.source_topic_ids (ARRAY(TEXT))

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PgUUID

revision: str = "0011"
down_revision: str = "0010"


def upgrade() -> None:
    # ── 1. content_pieces.topic_assignment_id ────────────────────────────
    op.add_column(
        "content_pieces",
        sa.Column(
            "topic_assignment_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("topic_assignments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_content_pieces_topic_assignment",
        "content_pieces",
        ["topic_assignment_id"],
    )

    # ── 2. run_queries.source_topic_ids ─────────────────────────────────
    op.add_column(
        "run_queries",
        sa.Column("source_topic_ids", ARRAY(sa.Text()), nullable=True),
    )

    # ── 3. query_gaps.source_topic_ids ──────────────────────────────────
    op.add_column(
        "query_gaps",
        sa.Column("source_topic_ids", ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("query_gaps", "source_topic_ids")
    op.drop_column("run_queries", "source_topic_ids")
    op.drop_index("ix_content_pieces_topic_assignment", table_name="content_pieces")
    op.drop_column("content_pieces", "topic_assignment_id")
