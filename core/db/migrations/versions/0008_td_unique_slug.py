"""Add unique constraint on topic_discoveries(company_id, effective_slug).

Prevents duplicate discovery rows for the same company + slug combination,
enabling safe upsert pattern in TopicDiscoveryRepository.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-10
"""
from __future__ import annotations

from alembic import op

revision: str = "0008"
down_revision: str = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_topic_discoveries_company_slug",
        "topic_discoveries",
        ["company_id", "effective_slug"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_topic_discoveries_company_slug",
        "topic_discoveries",
        type_="unique",
    )
