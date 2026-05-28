"""Add career_role column to persona_profiles and td_persona_affinity.

Stores the persona's job title / career role (e.g. "VP of Marketing")
as a denormalized column for efficient display in the Content Planner.
Also fixes persona_name being NULL in td_persona_affinity by making the
field properly populated during TD pipeline persistence.

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str = "0029"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "persona_profiles",
        sa.Column("career_role", sa.String, nullable=True),
    )
    op.add_column(
        "td_persona_affinity",
        sa.Column("career_role", sa.String, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("td_persona_affinity", "career_role")
    op.drop_column("persona_profiles", "career_role")
