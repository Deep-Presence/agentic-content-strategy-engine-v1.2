"""Add gap_analysis_complete to topic_assignment_status_enum and td_gap_analysis to pipeline_type_enum.

Supports the two-phase TD → GA → CE pipeline split: gap analysis runs
as a separate task with its own SSE stream, then content engine starts
on user action.

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-06
"""
from __future__ import annotations

from alembic import op

revision: str = "0032"
down_revision: str = "0031"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE topic_assignment_status_enum "
        "ADD VALUE IF NOT EXISTS 'gap_analysis_complete' AFTER 'in_gap_analysis'"
    )
    op.execute(
        "ALTER TYPE pipeline_type_enum "
        "ADD VALUE IF NOT EXISTS 'td_gap_analysis' AFTER 'daily_tracker'"
    )


def downgrade() -> None:
    # Cannot remove enum values from PostgreSQL — no-op.
    pass
