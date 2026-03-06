"""Create api_tasks table for persistent task storage.

Mirrors PipelineTask with DB-backed persistence. Status is a plain
VARCHAR (not PG enum) because TaskStatus includes ``pending_approval``
and ``failed_restart`` which don't exist in ``pipeline_status_enum``.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_tasks",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", sa.String, unique=True, nullable=False),
        sa.Column("pipeline", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="running"),
        sa.Column("company_slug", sa.String, nullable=False, server_default=""),
        sa.Column("product_slug", sa.String, nullable=True),
        sa.Column("effective_slug", sa.String, nullable=True),
        sa.Column("current_step", sa.String, nullable=True),
        sa.Column("progress_pct", sa.Float, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("approval_payload", JSONB, nullable=True),
        sa.Column("approval_history", JSONB, nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "pipeline_run_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
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
    )

    # Indexes
    op.create_index("ix_api_tasks_task_id", "api_tasks", ["task_id"], unique=True)
    op.create_index("ix_api_tasks_effective_slug", "api_tasks", ["effective_slug"])
    op.create_index("ix_api_tasks_status", "api_tasks", ["status"])
    op.create_index(
        "ix_api_tasks_company_pipeline", "api_tasks", ["company_slug", "pipeline"]
    )


def downgrade() -> None:
    op.drop_index("ix_api_tasks_company_pipeline", table_name="api_tasks")
    op.drop_index("ix_api_tasks_status", table_name="api_tasks")
    op.drop_index("ix_api_tasks_effective_slug", table_name="api_tasks")
    op.drop_index("ix_api_tasks_task_id", table_name="api_tasks")
    op.drop_table("api_tasks")
