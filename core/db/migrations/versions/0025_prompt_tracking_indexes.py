"""Add composite indexes for per-prompt time-bounded analytics.

Supports the enriched prompt list (Phase 1) and per-prompt drawer
analytics (Phase 2) by enabling efficient aggregation queries on
daily_run_responses scoped by prompt + time window.

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-04
"""
from __future__ import annotations

from alembic import op

revision: str = "0025"
down_revision: str = "0024"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Per-prompt time-bounded queries (enriched list + drawer analytics)
    op.execute(
        "CREATE INDEX ix_responses_prompt_created "
        "ON daily_run_responses (prompt_id, created_at DESC)"
    )

    # Fanout aggregation with time filter (partial index — only fanout rows)
    op.execute(
        "CREATE INDEX ix_responses_parent_created "
        "ON daily_run_responses (parent_prompt_id, created_at DESC) "
        "WHERE parent_prompt_id IS NOT NULL"
    )

    # Company-wide time range scans (trend, enriched list CTEs)
    op.execute(
        "CREATE INDEX ix_responses_created_at "
        "ON daily_run_responses (created_at DESC)"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_responses_created_at",
        table_name="daily_run_responses",
    )
    op.execute("DROP INDEX IF EXISTS ix_responses_parent_created")
    op.drop_index(
        "ix_responses_prompt_created",
        table_name="daily_run_responses",
    )
