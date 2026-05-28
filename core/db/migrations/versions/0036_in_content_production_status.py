"""Add in_content_production to topic_assignment_status_enum.

Supports the GA → CE transition: when "Start Production" is clicked,
assignments move to in_content_production before the Content Engine
starts creating brief records.

Revision ID: 0036
Revises: 0035
Create Date: 2026-04-07
"""
from __future__ import annotations

from alembic import op

revision: str = "0036"
down_revision: str = "0035"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE topic_assignment_status_enum "
        "ADD VALUE IF NOT EXISTS 'in_content_production' AFTER 'gap_analysis_complete'"
    )


def downgrade() -> None:
    # Cannot remove enum values from PostgreSQL — no-op.
    pass
