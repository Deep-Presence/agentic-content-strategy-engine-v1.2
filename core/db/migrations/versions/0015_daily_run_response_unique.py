"""Add unique constraint on daily_run_responses(run_id, prompt_id, engine).

Prevents duplicate response rows when persist_daily_run_result is retried
for the same run.  Existing duplicates (if any) are pruned first.

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op

revision: str = "0015"
down_revision: str = "0014"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Prune any pre-existing duplicates — keep the newest row per group.
    op.execute("""
        DELETE FROM daily_run_responses
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY run_id, prompt_id, engine
                           ORDER BY created_at DESC, id DESC
                       ) AS rn
                FROM daily_run_responses
            ) ranked
            WHERE rn > 1
        )
    """)

    op.create_unique_constraint(
        "uq_daily_run_responses_run_prompt_engine",
        "daily_run_responses",
        ["run_id", "prompt_id", "engine"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_daily_run_responses_run_prompt_engine",
        "daily_run_responses",
    )
