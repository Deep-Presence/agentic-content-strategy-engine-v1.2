"""Add nullable workspace_id columns to pipeline/runtime tables.

Backfills workspace_id from existing company_id / company_slug. During
transition, workspace_slug equals legacy company_slug and
workspace.id equals company.id for migrated rows.

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: str = "0042"
branch_labels: str | None = None
depends_on: str | None = None

_WORKSPACE_ID = sa.Column(
    "workspace_id",
    postgresql.UUID(as_uuid=True),
    nullable=True,
)

_TABLES_WITH_COMPANY_ID = (
    "pipeline_runs",
    "content_inventory",
    "cms_connections",
    "analytics_connections",
    "content_engine_topic_runs",
)


def upgrade() -> None:
    for table in _TABLES_WITH_COMPANY_ID:
        op.add_column(
            table,
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = company_id WHERE workspace_id IS NULL"
            )
        )

    op.add_column(
        "api_tasks",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_api_tasks_workspace_id", "api_tasks", ["workspace_id"])
    op.execute(
        sa.text(
            """
            UPDATE api_tasks AS t
            SET workspace_id = w.id
            FROM workspaces AS w
            WHERE t.workspace_id IS NULL
              AND w.slug = t.company_slug
            """
        )
    )

    op.add_column(
        "tracked_prompts",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_tracked_prompts_workspace_id", "tracked_prompts", ["workspace_id"])
    op.execute(
        sa.text(
            """
            UPDATE tracked_prompts AS t
            SET workspace_id = w.id
            FROM workspaces AS w
            WHERE t.workspace_id IS NULL
              AND w.id::text = t.company_id
            """
        )
    )

    op.add_column(
        "llm_cost_events",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_llm_cost_events_workspace_id", "llm_cost_events", ["workspace_id"])
    op.execute(
        sa.text(
            """
            UPDATE llm_cost_events AS e
            SET workspace_id = w.id
            FROM workspaces AS w
            WHERE e.workspace_id IS NULL
              AND w.slug = e.company_slug
            """
        )
    )


def downgrade() -> None:
    for table in (
        "llm_cost_events",
        "tracked_prompts",
        "api_tasks",
        *_TABLES_WITH_COMPANY_ID,
    ):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        op.drop_column(table, "workspace_id")
