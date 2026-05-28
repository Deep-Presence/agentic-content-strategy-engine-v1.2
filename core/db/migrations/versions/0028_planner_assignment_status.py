"""Add approved/rejected values to topic_assignment_status_enum.

Supports the Content Planner approve/reject workflow on individual
topic assignments.

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-04
"""
from __future__ import annotations

from alembic import op

revision: str = "0028"
down_revision: str = "0027"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE topic_assignment_status_enum "
        "ADD VALUE IF NOT EXISTS 'approved' AFTER 'not_started'"
    )
    op.execute(
        "ALTER TYPE topic_assignment_status_enum "
        "ADD VALUE IF NOT EXISTS 'rejected' AFTER 'approved'"
    )


def downgrade() -> None:
    # Cannot remove enum values from PostgreSQL — no-op.
    pass
