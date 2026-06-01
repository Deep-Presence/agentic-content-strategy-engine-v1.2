"""Add provider_config JSONB to cms_connections for CMS-specific settings.

Stores non-secret provider configuration (Webflow site/collection/field mapping,
future OAuth metadata pointers, etc.). Secrets remain in encrypted_credentials.

Revision ID: 0045
Revises: 0044
Create Date: 2026-06-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0045"
down_revision: str = "0044"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "cms_connections",
        sa.Column(
            "provider_config",
            JSONB,
            nullable=True,
            comment="Provider-specific non-secret config (Webflow collections, field maps, etc.)",
        ),
    )


def downgrade() -> None:
    op.drop_column("cms_connections", "provider_config")
