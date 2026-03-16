"""Audit logs table: append-only event store for auth, HITL, and pipeline events.

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: str = "0017"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("company_slug", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_company_slug", "audit_logs", ["company_slug"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index(
        "ix_audit_logs_company_type_created",
        "audit_logs",
        ["company_slug", "event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_company_type_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_slug", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_table("audit_logs")
