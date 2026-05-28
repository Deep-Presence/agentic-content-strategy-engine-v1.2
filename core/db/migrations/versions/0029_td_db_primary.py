"""Add scoring_json and persona_affinity_index_json to topic_discoveries.

Stores the full ScoredSubdomainList and PersonaAffinityIndex as JSONB,
enabling the pipeline to read/write these artifacts from DB instead of
JSON filesystem. Part of the JSON→DB migration for Topic Discovery.

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0029"
down_revision: str = "0028"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "topic_discoveries",
        sa.Column("scoring_json", JSONB, nullable=True),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column("persona_affinity_index_json", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topic_discoveries", "persona_affinity_index_json")
    op.drop_column("topic_discoveries", "scoring_json")
