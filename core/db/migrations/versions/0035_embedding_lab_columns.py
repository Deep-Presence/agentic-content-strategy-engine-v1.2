"""Add embedding lab columns and cluster_proximity_stats table.

Adds is_company_citation flag to run_citations, three company-related
columns to query_gaps, and creates the cluster_proximity_stats table
for per-cluster and global proximity statistics.

Revision ID: 0035
Revises: 0034
Create Date: 2026-04-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "0035"
down_revision: str = "0034"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── run_citations: add is_company_citation ─────────────────────────
    op.add_column(
        "run_citations",
        sa.Column("is_company_citation", sa.Boolean, server_default="false", nullable=False),
    )
    op.create_index(
        "ix_run_citations_company",
        "run_citations",
        ["run_id", "is_company_citation"],
        postgresql_where=sa.text("is_company_citation = true"),
    )
    # Composite index for GROUP BY cluster_name queries (cluster profiles)
    op.create_index(
        "ix_run_citations_run_cluster",
        "run_citations",
        ["run_id", "cluster_name"],
    )

    # ── query_gaps: add company columns ────────────────────────────────
    op.add_column(
        "query_gaps",
        sa.Column("best_company_url", sa.Text, nullable=True),
    )
    op.add_column(
        "query_gaps",
        sa.Column("best_company_structural_signals", JSONB, nullable=True),
    )
    op.add_column(
        "query_gaps",
        sa.Column("company_cited", sa.Boolean, server_default="false", nullable=False),
    )

    # ── cluster_proximity_stats: new table ─────────────────────────────
    op.create_table(
        "cluster_proximity_stats",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", PgUUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cluster_name", sa.String, nullable=False),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("citation_mean", sa.Float, server_default="0.0", nullable=False),
        sa.Column("citation_std", sa.Float, server_default="0.0", nullable=False),
        sa.Column("citation_min", sa.Float, server_default="0.0", nullable=False),
        sa.Column("citation_max", sa.Float, server_default="0.0", nullable=False),
        sa.Column("citation_median", sa.Float, server_default="0.0", nullable=False),
        sa.Column("company_mean", sa.Float, server_default="0.0", nullable=False),
        sa.Column("company_median", sa.Float, server_default="0.0", nullable=False),
        sa.Column("count", sa.Integer, server_default="0", nullable=False),
    )
    op.create_unique_constraint(
        "uq_cluster_proximity_run_cluster",
        "cluster_proximity_stats",
        ["run_id", "cluster_name"],
    )
    op.create_index(
        "ix_cluster_proximity_stats_run",
        "cluster_proximity_stats",
        ["run_id"],
    )


def downgrade() -> None:
    # ── cluster_proximity_stats ────────────────────────────────────────
    op.drop_index("ix_cluster_proximity_stats_run", table_name="cluster_proximity_stats")
    op.drop_constraint("uq_cluster_proximity_run_cluster", "cluster_proximity_stats", type_="unique")
    op.drop_table("cluster_proximity_stats")

    # ── query_gaps ─────────────────────────────────────────────────────
    op.drop_column("query_gaps", "company_cited")
    op.drop_column("query_gaps", "best_company_structural_signals")
    op.drop_column("query_gaps", "best_company_url")

    # ── run_citations ──────────────────────────────────────────────────
    op.drop_index("ix_run_citations_run_cluster", table_name="run_citations")
    op.drop_index("ix_run_citations_company", table_name="run_citations")
    op.drop_column("run_citations", "is_company_citation")
