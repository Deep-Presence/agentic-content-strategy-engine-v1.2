"""CMS integration — connections, publish records, synced posts.

New tables:
  cms_connections    — encrypted credentials, site metadata, sync status
  cms_publish_records — audit trail: brief → CMS post mapping
  cms_synced_posts   — local index of existing CMS posts (staleness, refresh tracking)

New enum types:
  cms_provider_enum, cms_post_status_enum, cms_publish_action_enum

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "0021"
down_revision: str = "0020"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. Create enum types (idempotent) ─────────────────────────

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE cms_provider_enum AS ENUM "
        "('wordpress', 'webflow', 'strapi', 'ghost', 'hubspot'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE cms_post_status_enum AS ENUM "
        "('draft', 'publish', 'pending', 'private'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE cms_publish_action_enum AS ENUM "
        "('create', 'update', 'refresh'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    # ── 2. cms_connections ────────────────────────────────────────

    op.create_table(
        "cms_connections",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String, nullable=False),
        sa.Column("company_slug", sa.String, nullable=False),
        sa.Column(
            "provider",
            PgENUM(name="cms_provider_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("site_url", sa.String(512), nullable=False),
        sa.Column("encrypted_credentials", sa.Text, nullable=False),
        sa.Column("site_name", sa.String(255), server_default=""),
        sa.Column("cms_version", sa.String(50), server_default=""),
        sa.Column("user_display_name", sa.String(255), server_default=""),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_post_count", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "uq_cms_conn_company_tenant",
        "cms_connections",
        ["company_id", "tenant_id"],
        unique=True,
    )
    op.create_index(
        "ix_cms_conn_company_slug",
        "cms_connections",
        ["company_slug"],
    )

    # ── 3. cms_publish_records ────────────────────────────────────

    op.create_table(
        "cms_publish_records",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("cms_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_slug", sa.String, nullable=False),
        sa.Column("brief_id", sa.String(255), nullable=False),
        sa.Column("effective_slug", sa.String, server_default=""),
        sa.Column("content_engine_run_id", sa.String(255), server_default=""),
        sa.Column("cms_post_id", sa.String(50), nullable=False),
        sa.Column("cms_post_url", sa.String(1024), server_default=""),
        sa.Column("cms_post_slug", sa.String(512), server_default=""),
        sa.Column(
            "action",
            PgENUM(name="cms_publish_action_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status_at_publish",
            PgENUM(name="cms_post_status_enum", create_type=False),
            server_default="draft",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("title_published", sa.String(512), server_default=""),
        sa.Column("word_count", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_cms_pub_company_brief",
        "cms_publish_records",
        ["company_slug", "brief_id"],
    )
    op.create_index(
        "ix_cms_pub_connection",
        "cms_publish_records",
        ["connection_id"],
    )

    # ── 4. cms_synced_posts ───────────────────────────────────────

    op.create_table(
        "cms_synced_posts",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("cms_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_slug", sa.String, nullable=False),
        sa.Column("cms_post_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("slug", sa.String(512), nullable=False),
        sa.Column("url", sa.String(1024), server_default=""),
        sa.Column("excerpt", sa.Text, server_default=""),
        sa.Column("content_preview", sa.Text, server_default=""),
        sa.Column("word_count", sa.Integer, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("categories", JSONB, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("seo_title", sa.String(512), server_default=""),
        sa.Column("seo_description", sa.Text, server_default=""),
        # Analysis
        sa.Column("is_stale", sa.Boolean, server_default="false"),
        sa.Column("staleness_days", sa.Integer, server_default="0"),
        sa.Column("detected_primary_keyword", sa.String(255), server_default=""),
        sa.Column("cannibalization_risk", sa.Boolean, server_default="false"),
        # Refresh tracking
        sa.Column("queued_for_refresh", sa.Boolean, server_default="false"),
        sa.Column("refresh_brief_id", sa.String(255), server_default=""),
        sa.Column("refresh_queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "uq_cms_synced_conn_post",
        "cms_synced_posts",
        ["connection_id", "cms_post_id"],
        unique=True,
    )
    op.create_index(
        "ix_cms_synced_company_stale",
        "cms_synced_posts",
        ["company_slug", "is_stale"],
    )
    op.create_index(
        "ix_cms_synced_company",
        "cms_synced_posts",
        ["company_slug"],
    )


def downgrade() -> None:
    op.drop_table("cms_synced_posts")
    op.drop_table("cms_publish_records")
    op.drop_table("cms_connections")
    op.execute("DROP TYPE IF EXISTS cms_publish_action_enum")
    op.execute("DROP TYPE IF EXISTS cms_post_status_enum")
    op.execute("DROP TYPE IF EXISTS cms_provider_enum")
