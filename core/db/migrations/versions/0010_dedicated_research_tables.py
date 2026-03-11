"""Create dedicated tables for KB, AP, and VSG pipelines.

Replaces the generic research_artifacts approach with pipeline-specific
tables: kb_runs/documents/syntheses, persona_runs/profiles,
vsg_runs/authors/guides.

research_artifacts table is untouched — new tables are additive.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "0010"
down_revision: str = "0009"

ENUM_NAME = "research_run_status_enum"
ENUM_VALUES = ("draft", "running", "hitl_pending", "completed", "failed")


def upgrade() -> None:
    # ── 1. Create shared enum ────────────────────────────────────────────
    research_run_status = sa.Enum(
        *ENUM_VALUES, name=ENUM_NAME, create_type=False,
    )
    op.execute(
        f"CREATE TYPE {ENUM_NAME} AS ENUM ({', '.join(repr(v) for v in ENUM_VALUES)})"
    )

    # ── 2. KB tables ─────────────────────────────────────────────────────
    op.create_table(
        "kb_runs",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id"), nullable=False,
        ),
        sa.Column(
            "product_id", PgUUID(as_uuid=True),
            sa.ForeignKey("products.id"), nullable=True,
        ),
        sa.Column(
            "pipeline_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"), nullable=True,
        ),
        sa.Column("effective_slug", sa.String(), nullable=True),
        sa.Column("status", research_run_status, nullable=False, server_default="draft"),
        sa.Column("mode", sa.String(), nullable=True),
        sa.Column("synthesis_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_full_refresh", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
        ),
    )
    op.create_index("ix_kb_runs_company", "kb_runs", ["company_id"])
    op.create_index("ix_kb_runs_effective_slug", "kb_runs", ["effective_slug"])

    op.create_table(
        "kb_documents",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kb_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("kb_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("staleness_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_kb_documents_run_doctype", "kb_documents", ["kb_run_id", "doc_type"])

    op.create_table(
        "kb_syntheses",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kb_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("kb_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promoted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_kb_syntheses_run", "kb_syntheses", ["kb_run_id"])

    # ── 3. Persona tables ────────────────────────────────────────────────
    op.create_table(
        "persona_runs",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id"), nullable=False,
        ),
        sa.Column(
            "product_id", PgUUID(as_uuid=True),
            sa.ForeignKey("products.id"), nullable=True,
        ),
        sa.Column(
            "pipeline_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"), nullable=True,
        ),
        sa.Column("effective_slug", sa.String(), nullable=True),
        sa.Column("status", research_run_status, nullable=False, server_default="draft"),
        sa.Column("kb_synthesis_version", sa.Integer(), nullable=True),
        sa.Column("briefs_suggested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("briefs_approved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("profiles_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
        ),
    )
    op.create_index("ix_persona_runs_company", "persona_runs", ["company_id"])
    op.create_index("ix_persona_runs_effective_slug", "persona_runs", ["effective_slug"])

    op.create_table(
        "persona_profiles",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "persona_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("persona_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("persona_id", sa.String(), nullable=False),
        sa.Column("persona_name", sa.String(), nullable=False),
        sa.Column("tagline", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_persona_profiles_run", "persona_profiles", ["persona_run_id"])
    op.create_index(
        "ix_persona_profiles_persona_id", "persona_profiles",
        ["persona_run_id", "persona_id"],
    )

    # ── 4. VSG tables ────────────────────────────────────────────────────
    op.create_table(
        "vsg_runs",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id"), nullable=False,
        ),
        sa.Column(
            "product_id", PgUUID(as_uuid=True),
            sa.ForeignKey("products.id"), nullable=True,
        ),
        sa.Column(
            "pipeline_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"), nullable=True,
        ),
        sa.Column("effective_slug", sa.String(), nullable=True),
        sa.Column("status", research_run_status, nullable=False, server_default="draft"),
        sa.Column("ap_manifest_version", sa.String(), nullable=True),
        sa.Column("authors_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("authors_approved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guide_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
        ),
    )
    op.create_index("ix_vsg_runs_company", "vsg_runs", ["company_id"])
    op.create_index("ix_vsg_runs_effective_slug", "vsg_runs", ["effective_slug"])

    op.create_table(
        "vsg_authors",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vsg_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("vsg_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("author_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_vsg_authors_run", "vsg_authors", ["vsg_run_id"])
    op.create_index("ix_vsg_authors_author_id", "vsg_authors", ["vsg_run_id", "author_id"])

    op.create_table(
        "vsg_guides",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vsg_run_id", PgUUID(as_uuid=True),
            sa.ForeignKey("vsg_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_authors", JSONB, nullable=True),
        sa.Column("promoted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_vsg_guides_run", "vsg_guides", ["vsg_run_id"])


def downgrade() -> None:
    # ── Drop in reverse FK order ─────────────────────────────────────────
    op.drop_table("vsg_guides")
    op.drop_table("vsg_authors")
    op.drop_table("vsg_runs")
    op.drop_table("persona_profiles")
    op.drop_table("persona_runs")
    op.drop_table("kb_syntheses")
    op.drop_table("kb_documents")
    op.drop_table("kb_runs")
    op.execute(f"DROP TYPE IF EXISTS {ENUM_NAME}")
