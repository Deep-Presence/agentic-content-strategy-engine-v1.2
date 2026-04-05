"""Add structural_signals JSONB column and gap_analysis_crawl ingestion source.

Supports richer per-page structural analysis (45-field StructuralSignals from
compute_structural_signals) and Gap Analysis S1 as a second content inventory
ingestion source.

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0033"
down_revision: str = "0032"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Add new enum value for gap analysis crawl ingestion
    op.execute(
        "ALTER TYPE content_ingestion_source_enum "
        "ADD VALUE IF NOT EXISTS 'gap_analysis_crawl' AFTER 'site_audit_crawl'"
    )

    # 2. Add structural_signals JSONB column (nullable, no default)
    op.add_column(
        "content_inventory",
        sa.Column(
            "structural_signals",
            JSONB,
            nullable=True,
            comment="Full StructuralSignals from compute_structural_signals(). "
                    "45-field Pydantic model serialized.",
        ),
    )


def downgrade() -> None:
    op.drop_column("content_inventory", "structural_signals")
    # Enum value removal is a no-op (PostgreSQL limitation).
