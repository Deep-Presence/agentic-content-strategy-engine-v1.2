"""Analytics (GA4) integration — connections, traffic data, conversion events.

New tables:
  analytics_connections    — OAuth credentials, GA4 property metadata, sync status
  ga4_traffic_data         — traffic by landing page + source/medium
  ga4_conversion_events    — conversion events by landing page + source/medium

New enum types:
  analytics_provider_enum, analytics_sync_status_enum

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, ENUM as PgENUM, JSONB, UUID as PgUUID

revision: str = "0023"
down_revision: str = "0022"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. Create enum types (idempotent) ─────────────────────────

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE analytics_provider_enum AS ENUM ('ga4'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE analytics_sync_status_enum AS ENUM "
        "('pending', 'in_progress', 'success', 'failed', 'auth_revoked'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    # ── 2. analytics_connections ──────────────────────────────────

    op.create_table(
        "analytics_connections",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_slug", sa.String, nullable=False),
        sa.Column("tenant_id", sa.String, nullable=False),
        sa.Column(
            "provider",
            PgENUM(name="analytics_provider_enum", create_type=False),
            nullable=False,
        ),
        # OAuth tokens (Fernet-encrypted)
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=False),
        sa.Column(
            "token_expiry", sa.DateTime(timezone=True), nullable=True
        ),
        # GA4 property metadata
        sa.Column("ga4_property_id", sa.String(50), server_default=""),
        sa.Column("ga4_property_name", sa.String(255), server_default=""),
        sa.Column("ga4_account_id", sa.String(50), server_default=""),
        # Scopes & status
        sa.Column("scopes_granted", ARRAY(sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        # Sync tracking
        sa.Column(
            "last_sync_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "last_sync_status",
            PgENUM(
                name="analytics_sync_status_enum", create_type=False
            ),
            nullable=True,
        ),
        sa.Column("last_sync_error", sa.Text, server_default=""),
        sa.Column("sync_config", JSONB, nullable=True, server_default="{}"),
        # Timestamps
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
        "uq_analytics_conn_slug_tenant_provider",
        "analytics_connections",
        ["company_slug", "tenant_id", "provider"],
        unique=True,
    )
    op.create_index(
        "ix_analytics_conn_company_slug",
        "analytics_connections",
        ["company_slug"],
    )
    op.create_index(
        "ix_analytics_conn_company_id",
        "analytics_connections",
        ["company_id"],
    )

    # ── 3. ga4_traffic_data ──────────────────────────────────────

    op.create_table(
        "ga4_traffic_data",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey(
                "analytics_connections.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Dimensions
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("landing_page_url", sa.String(2048), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("medium", sa.String(255), nullable=False),
        sa.Column("campaign", sa.String(255), server_default=""),
        # Metrics
        sa.Column("sessions", sa.Integer, server_default="0"),
        sa.Column("engaged_sessions", sa.Integer, server_default="0"),
        sa.Column("engagement_rate", sa.Float, server_default="0"),
        sa.Column("bounce_rate", sa.Float, server_default="0"),
        sa.Column(
            "avg_session_duration_secs", sa.Float, server_default="0"
        ),
        sa.Column("screen_page_views", sa.Integer, server_default="0"),
        sa.Column("conversions", sa.Integer, server_default="0"),
        sa.Column("new_users", sa.Integer, server_default="0"),
        sa.Column("returning_users", sa.Integer, server_default="0"),
        # AI referral classification
        sa.Column("is_ai_referral", sa.Boolean, server_default="false"),
        sa.Column("ai_platform", sa.String(100), server_default=""),
        # Sync metadata
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        # Timestamps
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
        "uq_ga4_traffic_conn_date_page_src_med",
        "ga4_traffic_data",
        ["connection_id", "date", "landing_page_url", "source", "medium"],
        unique=True,
    )
    op.create_index(
        "ix_ga4_traffic_company_date",
        "ga4_traffic_data",
        ["company_id", "date"],
    )
    op.create_index(
        "ix_ga4_traffic_ai_referral",
        "ga4_traffic_data",
        ["company_id", "is_ai_referral"],
    )

    # ── 4. ga4_conversion_events ─────────────────────────────────

    op.create_table(
        "ga4_conversion_events",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey(
                "analytics_connections.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Dimensions
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("event_name", sa.String(255), nullable=False),
        sa.Column("landing_page_url", sa.String(2048), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("medium", sa.String(255), nullable=False),
        # Metrics
        sa.Column("event_count", sa.Integer, server_default="0"),
        sa.Column("event_value", sa.Float, server_default="0"),
        # AI referral classification
        sa.Column("is_ai_referral", sa.Boolean, server_default="false"),
        sa.Column("ai_platform", sa.String(100), server_default=""),
        # Sync metadata
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        # Timestamps
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
        "uq_ga4_conv_conn_date_evt_page_src_med",
        "ga4_conversion_events",
        [
            "connection_id",
            "date",
            "event_name",
            "landing_page_url",
            "source",
            "medium",
        ],
        unique=True,
    )
    op.create_index(
        "ix_ga4_conv_company_date",
        "ga4_conversion_events",
        ["company_id", "date"],
    )
    op.create_index(
        "ix_ga4_conv_ai_referral",
        "ga4_conversion_events",
        ["company_id", "is_ai_referral"],
    )


def downgrade() -> None:
    op.drop_table("ga4_conversion_events")
    op.drop_table("ga4_traffic_data")
    op.drop_table("analytics_connections")
    op.execute("DROP TYPE IF EXISTS analytics_sync_status_enum")
    op.execute("DROP TYPE IF EXISTS analytics_provider_enum")
