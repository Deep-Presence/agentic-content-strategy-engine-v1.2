"""Add durable batch/topic run tables for TD-entry Content Engine.

Revision ID: 0038
Revises: 0037
Create Date: 2026-04-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: str = "0037"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "content_engine_batch_runs",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_slug", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_mode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("pipeline_task_id", sa.String(length=128), nullable=True),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancelled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ce_batch_runs_slug_status",
        "content_engine_batch_runs",
        ["effective_slug", "status"],
    )
    op.create_index(
        "ix_ce_batch_runs_company_created",
        "content_engine_batch_runs",
        ["company_id", "created_at"],
    )

    op.create_table(
        "content_engine_topic_runs",
        sa.Column("batch_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_piece_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_slug", sa.String(), nullable=False),
        sa.Column("topic_assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_id", sa.String(length=20), nullable=False),
        sa.Column("topic_text", sa.Text(), nullable=False),
        sa.Column("brief_id", sa.String(length=64), nullable=True),
        sa.Column("ga_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_task_id", sa.String(length=128), nullable=True),
        sa.Column("entry_mode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("status_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_run_id"], ["content_engine_batch_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_piece_id"], ["content_pieces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_assignment_id"], ["topic_assignments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_run_id", "topic_assignment_id", name="uq_ce_topic_runs_batch_assignment"),
    )
    op.create_index(
        "ix_ce_topic_runs_slug_status",
        "content_engine_topic_runs",
        ["effective_slug", "status"],
    )
    op.create_index(
        "ix_ce_topic_runs_assignment",
        "content_engine_topic_runs",
        ["topic_assignment_id"],
    )
    op.create_index(
        "ix_ce_topic_runs_display_id",
        "content_engine_topic_runs",
        ["display_id"],
    )
    op.create_index(
        "ix_ce_topic_runs_batch_created",
        "content_engine_topic_runs",
        ["batch_run_id", "created_at"],
    )
    op.create_index(
        "ix_ce_topic_runs_ga_assignment",
        "content_engine_topic_runs",
        ["ga_run_id", "topic_assignment_id"],
    )

    op.create_table(
        "content_engine_topic_events",
        sa.Column("topic_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_id", sa.String(length=20), nullable=False),
        sa.Column("content_piece_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_task_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["content_piece_id"], ["content_pieces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_assignment_id"], ["topic_assignments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["topic_run_id"], ["content_engine_topic_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_run_id", "seq", name="uq_ce_topic_events_run_seq"),
    )
    op.create_index(
        "ix_ce_topic_events_assignment_seq",
        "content_engine_topic_events",
        ["topic_assignment_id", "seq"],
    )
    op.create_index(
        "ix_ce_topic_events_display_created",
        "content_engine_topic_events",
        ["display_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ce_topic_events_display_created", table_name="content_engine_topic_events")
    op.drop_index("ix_ce_topic_events_assignment_seq", table_name="content_engine_topic_events")
    op.drop_table("content_engine_topic_events")

    op.drop_index("ix_ce_topic_runs_ga_assignment", table_name="content_engine_topic_runs")
    op.drop_index("ix_ce_topic_runs_batch_created", table_name="content_engine_topic_runs")
    op.drop_index("ix_ce_topic_runs_display_id", table_name="content_engine_topic_runs")
    op.drop_index("ix_ce_topic_runs_assignment", table_name="content_engine_topic_runs")
    op.drop_index("ix_ce_topic_runs_slug_status", table_name="content_engine_topic_runs")
    op.drop_table("content_engine_topic_runs")

    op.drop_index("ix_ce_batch_runs_company_created", table_name="content_engine_batch_runs")
    op.drop_index("ix_ce_batch_runs_slug_status", table_name="content_engine_batch_runs")
    op.drop_table("content_engine_batch_runs")
