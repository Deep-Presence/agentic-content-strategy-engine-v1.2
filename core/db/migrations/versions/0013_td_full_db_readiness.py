"""Topic Discovery full DB readiness — close all schema gaps.

Changes:
- ADD VALUE 'discovery_complete' to td_status_enum
- ADD 4 columns to subdomain_nodes (priority_score, priority_factors, etc.)
- ADD 4 columns to topic_assignments (persona_id, persona_name, etc.)
- ADD 3 columns to topic_discoveries (scoring_version, etc.)
- ADD unique constraint on taxonomy_trees (discovery_id, version)
- CREATE TABLE td_source_results
- CREATE TABLE td_persona_affinity

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Fix td_status_enum: add missing 'discovery_complete' value ──
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in PG < 12,
    # but Alembic's default autocommit_block handles this.  IF NOT EXISTS
    # makes it idempotent.
    op.execute(
        "ALTER TYPE td_status_enum ADD VALUE IF NOT EXISTS 'discovery_complete'"
        " BEFORE 'approved'"
    )

    # ── 2. subdomain_nodes: add scoring + affinity columns ─────────────
    op.add_column(
        "subdomain_nodes",
        sa.Column("priority_score", sa.Float, nullable=True),
    )
    op.add_column(
        "subdomain_nodes",
        sa.Column("priority_factors", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "subdomain_nodes",
        sa.Column("persona_affinity_json", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "subdomain_nodes",
        sa.Column(
            "expansion_status",
            sa.String,
            nullable=True,
            server_default="not_expanded",
        ),
    )

    # ── 3. topic_assignments: add persona + subdomain display columns ──
    op.add_column(
        "topic_assignments",
        sa.Column("persona_id", sa.String, nullable=True),
    )
    op.add_column(
        "topic_assignments",
        sa.Column("persona_name", sa.String, nullable=True),
    )
    op.add_column(
        "topic_assignments",
        sa.Column("subdomain_id_text", sa.String, nullable=True),
    )
    op.add_column(
        "topic_assignments",
        sa.Column("subdomain_name", sa.String, nullable=True),
    )
    op.create_index(
        "ix_topic_assignments_persona",
        "topic_assignments",
        ["persona_id"],
    )

    # ── 4. topic_discoveries: add version tracking + manifest ──────────
    op.add_column(
        "topic_discoveries",
        sa.Column(
            "scoring_version",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column(
            "persona_affinity_version",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column("manifest_json", postgresql.JSONB, nullable=True),
    )

    # ── 5. taxonomy_trees: unique constraint on (discovery_id, version) ─
    op.create_unique_constraint(
        "uq_taxonomy_trees_discovery_version",
        "taxonomy_trees",
        ["discovery_id", "version"],
    )

    # ── 6. CREATE TABLE td_source_results ──────────────────────────────
    op.create_table(
        "td_source_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "discovery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "total_candidates", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "total_rounds", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("singletons", sa.Integer, nullable=False, server_default="0"),
        sa.Column("doubletons", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chao1_estimate", sa.Float, nullable=True),
        sa.Column("source_sample_coverage", sa.Float, nullable=True),
        sa.Column("execution_time_s", sa.Float, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("candidates_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_td_source_results_discovery",
        "td_source_results",
        ["discovery_id"],
    )

    # ── 7. CREATE TABLE td_persona_affinity ────────────────────────────
    op.create_table(
        "td_persona_affinity",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "discovery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subdomain_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subdomain_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("persona_id", sa.String, nullable=False),
        sa.Column("persona_name", sa.String, nullable=True),
        sa.Column("subdomain_id_str", sa.String, nullable=True),
        sa.Column("subdomain_name", sa.String, nullable=True),
        sa.Column(
            "affinity_score", sa.Float, nullable=False, server_default="0"
        ),
        sa.Column("provenance", sa.String(20), nullable=True),
        sa.Column("pain_points", postgresql.JSONB, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_td_persona_affinity_discovery",
        "td_persona_affinity",
        ["discovery_id"],
    )
    op.create_index(
        "ix_td_persona_affinity_persona",
        "td_persona_affinity",
        ["persona_id"],
    )


def downgrade() -> None:
    # ── 7. Drop td_persona_affinity ────────────────────────────────────
    op.drop_index("ix_td_persona_affinity_persona", table_name="td_persona_affinity")
    op.drop_index("ix_td_persona_affinity_discovery", table_name="td_persona_affinity")
    op.drop_table("td_persona_affinity")

    # ── 6. Drop td_source_results ──────────────────────────────────────
    op.drop_index("ix_td_source_results_discovery", table_name="td_source_results")
    op.drop_table("td_source_results")

    # ── 5. Drop taxonomy_trees unique constraint ───────────────────────
    op.drop_constraint(
        "uq_taxonomy_trees_discovery_version",
        "taxonomy_trees",
        type_="unique",
    )

    # ── 4. Drop topic_discoveries columns ──────────────────────────────
    op.drop_column("topic_discoveries", "manifest_json")
    op.drop_column("topic_discoveries", "persona_affinity_version")
    op.drop_column("topic_discoveries", "scoring_version")

    # ── 3. Drop topic_assignments columns ──────────────────────────────
    op.drop_index("ix_topic_assignments_persona", table_name="topic_assignments")
    op.drop_column("topic_assignments", "subdomain_name")
    op.drop_column("topic_assignments", "subdomain_id_text")
    op.drop_column("topic_assignments", "persona_name")
    op.drop_column("topic_assignments", "persona_id")

    # ── 2. Drop subdomain_nodes columns ────────────────────────────────
    op.drop_column("subdomain_nodes", "expansion_status")
    op.drop_column("subdomain_nodes", "persona_affinity_json")
    op.drop_column("subdomain_nodes", "priority_factors")
    op.drop_column("subdomain_nodes", "priority_score")

    # ── 1. Cannot remove enum value from PG — skip ─────────────────────
    pass
