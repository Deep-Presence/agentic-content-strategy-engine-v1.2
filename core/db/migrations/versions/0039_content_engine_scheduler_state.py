"""Add dedicated scheduler state columns for content_engine_topic_runs.

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039"
down_revision: str = "0038"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "content_engine_topic_runs",
        sa.Column(
            "scheduler_state",
            sa.String(length=64),
            nullable=False,
            server_default="idle",
        ),
    )
    op.add_column(
        "content_engine_topic_runs",
        sa.Column("claim_token", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "content_engine_topic_runs",
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_engine_topic_runs",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_engine_topic_runs",
        sa.Column("waiting_for_human_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_engine_topic_runs",
        sa.Column(
            "continuation_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_ce_topic_runs_company_scheduler",
        "content_engine_topic_runs",
        ["company_id", "scheduler_state", "updated_at"],
    )

    op.execute(
        """
        UPDATE content_engine_topic_runs
        SET
          scheduler_state = CASE
            WHEN status = 'content_queued' AND current_stage = 'content_queued' THEN 'queued'
            ELSE 'idle'
          END,
          claim_token = metadata_json ->> 'dispatch_claim_token',
          queued_at = CASE
            WHEN status = 'content_queued' AND current_stage = 'content_queued' THEN updated_at
            ELSE NULL
          END,
          claimed_at = CASE
            WHEN metadata_json ->> 'dispatch_state' = 'claimed'
              THEN COALESCE((metadata_json ->> 'dispatch_claimed_at')::timestamptz, updated_at)
            WHEN metadata_json ->> 'dispatch_state' = 'dispatched'
              THEN COALESCE((metadata_json ->> 'dispatch_task_created_at')::timestamptz, updated_at)
            ELSE NULL
          END
        """
    )

    op.alter_column(
        "content_engine_topic_runs",
        "scheduler_state",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index("ix_ce_topic_runs_company_scheduler", table_name="content_engine_topic_runs")
    op.drop_column("content_engine_topic_runs", "continuation_payload_json")
    op.drop_column("content_engine_topic_runs", "waiting_for_human_at")
    op.drop_column("content_engine_topic_runs", "claimed_at")
    op.drop_column("content_engine_topic_runs", "queued_at")
    op.drop_column("content_engine_topic_runs", "claim_token")
    op.drop_column("content_engine_topic_runs", "scheduler_state")
