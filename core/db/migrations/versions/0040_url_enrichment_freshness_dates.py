"""Add freshness date columns to url_enrichment_cache.

Revision ID: 0040
Revises: 0039
Create Date: 2026-04-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str = "0039"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "url_enrichment_cache",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "url_enrichment_cache",
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("url_enrichment_cache", "modified_at")
    op.drop_column("url_enrichment_cache", "published_at")
