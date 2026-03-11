"""Enrich site_audits with full audit result columns, add audit_page_results table.

Adds ~19 columns to site_audits (score, grade, dimensions, AEO metrics, etc.),
3 columns to audit_findings (dimension, message, recommendation), and creates
the audit_page_results table for per-page data with JSONB result blobs.

All new columns are nullable for safe migration on existing data.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID

revision: str = "0009"
down_revision: str = "0008"


def upgrade() -> None:
    # ── site_audits: new columns ────────────────────────────────────────
    op.add_column(
        "site_audits",
        sa.Column("effective_slug", sa.String(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column(
            "pipeline_run_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "site_audits",
        sa.Column("overall_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("grade", sa.String(2), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column(
            "is_degraded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "site_audits",
        sa.Column("pages_discovered", sa.Integer(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("duration_seconds", sa.Float(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("dimension_scores", JSONB(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("ai_bot_access", JSONB(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("sitemap_health", JSONB(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("findings_by_severity", JSONB(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("findings_by_dimension", JSONB(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("top_findings", JSONB(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("avg_snippet_readiness", sa.Float(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("pages_with_schema", sa.Integer(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("avg_question_heading_ratio", sa.Float(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("failed_steps", ARRAY(sa.Integer()), nullable=True),
    )
    op.add_column(
        "site_audits",
        sa.Column("degraded_dimensions", ARRAY(sa.Text()), nullable=True),
    )

    # New indexes on site_audits
    op.create_index(
        "ix_site_audits_slug_created",
        "site_audits",
        ["effective_slug", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_site_audits_domain_status",
        "site_audits",
        ["company_id", "site_domain", "status", sa.text("created_at DESC")],
    )

    # ── audit_findings: new columns ─────────────────────────────────────
    op.add_column(
        "audit_findings",
        sa.Column(
            "dimension",
            sa.String(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    op.add_column(
        "audit_findings",
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    op.add_column(
        "audit_findings",
        sa.Column(
            "recommendation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )

    # New composite index for filtered finding queries
    op.create_index(
        "ix_audit_findings_audit_sev_dim",
        "audit_findings",
        ["audit_id", "severity", "dimension"],
    )

    # ── audit_page_results: new table ───────────────────────────────────
    op.create_table(
        "audit_page_results",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "audit_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("site_audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("crawl_depth", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("reading_level", sa.Float(), nullable=True),
        sa.Column("has_schema", sa.Boolean(), nullable=True),
        sa.Column("snippet_readiness_score", sa.Float(), nullable=True),
        sa.Column("finding_count", sa.Integer(), nullable=True),
        sa.Column("has_https", sa.Boolean(), nullable=True),
        sa.Column("is_noindex", sa.Boolean(), nullable=True),
        sa.Column("result_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_audit_page_results_audit_idx",
        "audit_page_results",
        ["audit_id", "page_index"],
    )


def downgrade() -> None:
    # Drop new table
    op.drop_index("ix_audit_page_results_audit_idx", table_name="audit_page_results")
    op.drop_table("audit_page_results")

    # Drop audit_findings columns + index
    op.drop_index("ix_audit_findings_audit_sev_dim", table_name="audit_findings")
    op.drop_column("audit_findings", "recommendation")
    op.drop_column("audit_findings", "message")
    op.drop_column("audit_findings", "dimension")

    # Drop site_audits columns + indexes
    op.drop_index("ix_site_audits_domain_status", table_name="site_audits")
    op.drop_index("ix_site_audits_slug_created", table_name="site_audits")
    op.drop_column("site_audits", "degraded_dimensions")
    op.drop_column("site_audits", "failed_steps")
    op.drop_column("site_audits", "error_message")
    op.drop_column("site_audits", "avg_question_heading_ratio")
    op.drop_column("site_audits", "pages_with_schema")
    op.drop_column("site_audits", "avg_snippet_readiness")
    op.drop_column("site_audits", "top_findings")
    op.drop_column("site_audits", "findings_by_dimension")
    op.drop_column("site_audits", "findings_by_severity")
    op.drop_column("site_audits", "sitemap_health")
    op.drop_column("site_audits", "ai_bot_access")
    op.drop_column("site_audits", "dimension_scores")
    op.drop_column("site_audits", "duration_seconds")
    op.drop_column("site_audits", "pages_discovered")
    op.drop_column("site_audits", "is_degraded")
    op.drop_column("site_audits", "grade")
    op.drop_column("site_audits", "overall_score")
    op.drop_column("site_audits", "pipeline_run_id")
    op.drop_column("site_audits", "effective_slug")
