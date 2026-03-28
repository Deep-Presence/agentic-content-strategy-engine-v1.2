"""Add worker_id column to api_tasks for multi-worker scoped recovery.

Each worker process stamps its hostname:pid on tasks it creates.
On startup, recovery only marks THIS worker's orphans as failed — leaving
other workers' in-flight tasks untouched.

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str = "0021"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "api_tasks",
        sa.Column("worker_id", sa.String(), nullable=True),
    )
    op.create_index("ix_api_tasks_worker_id", "api_tasks", ["worker_id"])


def downgrade() -> None:
    op.drop_index("ix_api_tasks_worker_id", table_name="api_tasks")
    op.drop_column("api_tasks", "worker_id")
