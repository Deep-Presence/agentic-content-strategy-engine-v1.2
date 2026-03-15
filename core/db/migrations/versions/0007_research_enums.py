"""Add research pipeline enum values for DB Foundation Sprint.

Extends pipeline_type_enum, artifact_type_enum, and artifact_status_enum
so that KB, AP, and VSG pipelines can track runs and artifact status in Postgres.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-10
"""
from __future__ import annotations

from alembic import op

revision: str = "0007"
down_revision: str = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Pipeline types for research sub-pipelines
    op.execute("ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'knowledge_base'")
    op.execute("ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'audience_persona'")
    op.execute("ALTER TYPE pipeline_type_enum ADD VALUE IF NOT EXISTS 'voice_style_guide'")

    # Artifact type for KB L2 documents (company_overview, customer_reviews, etc.)
    # L3 synthesis already covered by 'company_context'.
    op.execute("ALTER TYPE artifact_type_enum ADD VALUE IF NOT EXISTS 'knowledge_base'")

    # Artifact status values matching research pipeline vocabulary
    op.execute("ALTER TYPE artifact_status_enum ADD VALUE IF NOT EXISTS 'fresh'")
    op.execute("ALTER TYPE artifact_status_enum ADD VALUE IF NOT EXISTS 'stale'")
    op.execute("ALTER TYPE artifact_status_enum ADD VALUE IF NOT EXISTS 'pending_review'")


def downgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot be reversed in PostgreSQL.
    # Enum values can only be removed by recreating the type, which risks
    # data loss if rows reference these values. Manual intervention required.
    pass
