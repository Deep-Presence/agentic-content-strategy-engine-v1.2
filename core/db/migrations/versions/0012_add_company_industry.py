"""Add industry column to companies table.

Stores the company's industry vertical (e.g. 'Fintech', 'Developer Tools').
Collected during onboarding, used in pipeline prompts.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("industry", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "industry")
