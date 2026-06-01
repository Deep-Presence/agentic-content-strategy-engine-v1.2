"""Backfill workspace_id for runtime rows created before app write support.

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: str = "0043"
branch_labels: str | None = None
depends_on: str | None = None

_TABLES_WITH_COMPANY_ID = (
    "pipeline_runs",
    "content_inventory",
    "cms_connections",
    "analytics_connections",
    "content_engine_topic_runs",
)


def upgrade() -> None:
    for table in _TABLES_WITH_COMPANY_ID:
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET workspace_id = company_id
                WHERE workspace_id IS NULL
                """
            )
        )

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
    pass
