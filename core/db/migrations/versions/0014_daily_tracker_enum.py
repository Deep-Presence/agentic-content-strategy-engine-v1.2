"""Add daily_tracker to pipeline_type_enum.

Extends the Postgres ENUM so PipelineRunModel can track daily tracker runs.

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op

revision: str = "0014"
down_revision: str = "0013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'daily_tracker'"
    )


def downgrade() -> None:
    # Postgres does not support removing values from an ENUM.
    pass
