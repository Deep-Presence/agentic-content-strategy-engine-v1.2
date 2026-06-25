"""Topic Discovery additive upsert support.

Adds columns and indexes to support per-subdomain atomic writes during
Pipeline B expansion, replacing the destructive delete-all + re-insert-all
pattern.

Changes:
- ADD COLUMN topic_assignments.persona_affinity_json (JSONB)
- ADD COLUMN topic_assignments.expansion_batch_id (UUID)
- ADD COLUMN subdomain_nodes.updated_at (TIMESTAMPTZ)
- CREATE INDEX ix_topic_assignments_subdomain_version (composite)
- CREATE INDEX ix_topic_assignments_batch (expansion_batch_id)
- CREATE UNIQUE INDEX uq_subdomain_nodes_name_parent (partial, non-null parent)
- CREATE UNIQUE INDEX uq_subdomain_nodes_name_root (partial, null parent)

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "0031"
down_revision: str = "0030"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. topic_assignments: per-assignment persona affinity ──────────
    op.add_column(
        "topic_assignments",
        sa.Column("persona_affinity_json", JSONB, nullable=True),
    )

    # ── 2. topic_assignments: expansion batch grouping ────────────────
    op.add_column(
        "topic_assignments",
        sa.Column("expansion_batch_id", PgUUID(as_uuid=True), nullable=True),
    )

    # ── 3. subdomain_nodes: updated_at for staleness tracking ─────────
    op.add_column(
        "subdomain_nodes",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 4. Composite index for per-subdomain assignment queries ───────
    op.create_index(
        "ix_topic_assignments_subdomain_version",
        "topic_assignments",
        ["discovery_id", "subdomain_node_id", "matrix_version"],
    )

    # ── 5. Index on expansion_batch_id ────────────────────────────────
    op.create_index(
        "ix_topic_assignments_batch",
        "topic_assignments",
        ["expansion_batch_id"],
    )

    # ── 6. Partial unique indexes for subdomain node dedup ────────────
    # Non-root nodes: UNIQUE(taxonomy_id, name, parent_id) WHERE parent_id IS NOT NULL
    # Handles the PostgreSQL NULL-is-distinct behavior.
    op.execute(
        "CREATE UNIQUE INDEX uq_subdomain_nodes_name_parent "
        "ON subdomain_nodes (taxonomy_id, name, parent_id) "
        "WHERE parent_id IS NOT NULL"
    )
    # Root nodes: UNIQUE(taxonomy_id, name) WHERE parent_id IS NULL
    op.execute(
        "CREATE UNIQUE INDEX uq_subdomain_nodes_name_root "
        "ON subdomain_nodes (taxonomy_id, name) "
        "WHERE parent_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_subdomain_nodes_name_root")
    op.execute("DROP INDEX IF EXISTS uq_subdomain_nodes_name_parent")
    op.drop_index("ix_topic_assignments_batch", table_name="topic_assignments")
    op.drop_index(
        "ix_topic_assignments_subdomain_version",
        table_name="topic_assignments",
    )
    op.drop_column("subdomain_nodes", "updated_at")
    op.drop_column("topic_assignments", "expansion_batch_id")
    op.drop_column("topic_assignments", "persona_affinity_json")
