"""Add missing pipeline_type_enum values: onboarding, topic_expansion.

The Python PipelineType enum had these values but they were never added to
the Postgres enum type, causing silent _create_pipeline_run failures and
downstream FK violations (kb_runs.pipeline_run_id → pipeline_runs.id).

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-17
"""
from __future__ import annotations

from alembic import op

revision: str = "0019"
down_revision: str = "0018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ADD VALUE is non-transactional in Postgres — each must be its own statement.
    # IF NOT EXISTS makes this idempotent (safe to re-run).
    op.execute("ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'onboarding'")
    op.execute("ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'topic_expansion'")


def downgrade() -> None:
    # Postgres does not support removing enum values.
    # A full enum rebuild would be needed, but these values are harmless to keep.
    pass
