"""Add BYOK workspace model configuration tables.

Revision ID: 0046
Revises: 0045
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0046"
down_revision: str = "0045"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_llm_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=False, server_default="openrouter"),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("api_key_fingerprint", sa.String(), nullable=False),
        sa.Column("api_key_masked", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validation_error", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_workspace_llm_credentials_active_provider",
        "workspace_llm_credentials",
        ["workspace_id", "provider"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_workspace_llm_credentials_workspace_id",
        "workspace_llm_credentials",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_llm_credentials_provider",
        "workspace_llm_credentials",
        ["provider"],
    )
    op.create_index(
        "ix_workspace_llm_credentials_status",
        "workspace_llm_credentials",
        ["status"],
    )

    op.create_table(
        "workspace_agent_model_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_key", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="openrouter"),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("timeout_s", sa.Float(), nullable=True),
        sa.Column("extra_body", JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "agent_key",
            name="uq_workspace_agent_model_configs_workspace_agent",
        ),
    )
    op.create_index(
        "ix_workspace_agent_model_configs_workspace_id",
        "workspace_agent_model_configs",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_agent_model_configs_agent_key",
        "workspace_agent_model_configs",
        ["agent_key"],
    )
    op.create_index(
        "ix_workspace_agent_model_configs_provider",
        "workspace_agent_model_configs",
        ["provider"],
    )

    op.add_column("llm_cost_events", sa.Column("agent_key", sa.String(), nullable=True))
    op.add_column(
        "llm_cost_events",
        sa.Column(
            "credential_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace_llm_credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "llm_cost_events",
        sa.Column(
            "model_config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace_agent_model_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "llm_cost_events", sa.Column("actual_provider", sa.String(), nullable=True)
    )
    op.add_column(
        "llm_cost_events",
        sa.Column(
            "workspace_billed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index("ix_llm_cost_events_agent_key", "llm_cost_events", ["agent_key"])
    op.create_index(
        "ix_llm_cost_events_credential_id", "llm_cost_events", ["credential_id"]
    )
    op.create_index(
        "ix_llm_cost_events_model_config_id", "llm_cost_events", ["model_config_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_cost_events_model_config_id", table_name="llm_cost_events")
    op.drop_index("ix_llm_cost_events_credential_id", table_name="llm_cost_events")
    op.drop_index("ix_llm_cost_events_agent_key", table_name="llm_cost_events")
    op.drop_column("llm_cost_events", "workspace_billed")
    op.drop_column("llm_cost_events", "actual_provider")
    op.drop_column("llm_cost_events", "model_config_id")
    op.drop_column("llm_cost_events", "credential_id")
    op.drop_column("llm_cost_events", "agent_key")

    op.drop_index(
        "ix_workspace_agent_model_configs_provider",
        table_name="workspace_agent_model_configs",
    )
    op.drop_index(
        "ix_workspace_agent_model_configs_agent_key",
        table_name="workspace_agent_model_configs",
    )
    op.drop_index(
        "ix_workspace_agent_model_configs_workspace_id",
        table_name="workspace_agent_model_configs",
    )
    op.drop_table("workspace_agent_model_configs")

    op.drop_index(
        "ix_workspace_llm_credentials_status",
        table_name="workspace_llm_credentials",
    )
    op.drop_index(
        "ix_workspace_llm_credentials_provider",
        table_name="workspace_llm_credentials",
    )
    op.drop_index(
        "ix_workspace_llm_credentials_workspace_id",
        table_name="workspace_llm_credentials",
    )
    op.drop_index(
        "uq_workspace_llm_credentials_active_provider",
        table_name="workspace_llm_credentials",
    )
    op.drop_table("workspace_llm_credentials")
