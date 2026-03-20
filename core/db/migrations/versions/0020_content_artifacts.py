"""Add content_artifacts table + extend content_pieces for DB-ready pipeline.

New table:
  content_artifacts — one row per stage file per content piece (outline,
  draft, linked, enriched, eval_history, final). Storage key points to
  blob storage or local filesystem.

Alterations to content_pieces:
  - run_id made nullable (allows pre-pipeline brief creation via add_brief)
  - effective_slug added (tenant scoping for run_id=NULL rows)
  - brief_id added (immutable external identity, e.g. "brief-001")
  - company_id added (FK to companies, tenant scoping)
  - unique constraint on (effective_slug, brief_id) for upsert key

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgENUM
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0020"
down_revision: str = "0019"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. Create content_artifact_stage_enum (idempotent) ─────────────
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE content_artifact_stage_enum AS ENUM "
        "('outline', 'draft', 'linked', 'enriched', 'eval_history', 'final'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    # ── 2. Create content_artifacts table ──────────────────────────────
    op.create_table(
        "content_artifacts",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "piece_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("content_pieces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage",
            PgENUM(
                "outline", "draft", "linked", "enriched", "eval_history", "final",
                name="content_artifact_stage_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String, nullable=False),
        sa.Column("content_type", sa.String, nullable=False, server_default="text/markdown"),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_content_artifacts_piece_stage",
        "content_artifacts",
        ["piece_id", "stage"],
        unique=True,
    )

    # ── 3. ALTER content_pieces — make run_id nullable ─────────────────
    op.alter_column("content_pieces", "run_id", nullable=True)

    # ── 4. ALTER content_pieces — add new columns ──────────────────────
    op.add_column(
        "content_pieces",
        sa.Column("effective_slug", sa.String, nullable=True),
    )
    op.add_column(
        "content_pieces",
        sa.Column("brief_id", sa.String, nullable=True),
    )
    op.add_column(
        "content_pieces",
        sa.Column(
            "company_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ── 5. Indexes on new columns ──────────────────────────────────────
    op.create_index(
        "uq_content_pieces_slug_brief",
        "content_pieces",
        ["effective_slug", "brief_id"],
        unique=True,
        postgresql_where=sa.text("effective_slug IS NOT NULL AND brief_id IS NOT NULL"),
    )
    op.create_index(
        "ix_content_pieces_company",
        "content_pieces",
        ["company_id"],
    )
    op.create_index(
        "ix_content_pieces_slug",
        "content_pieces",
        ["effective_slug"],
    )


def downgrade() -> None:
    # ── Drop indexes ───────────────────────────────────────────────────
    op.drop_index("ix_content_pieces_slug")
    op.drop_index("ix_content_pieces_company")
    op.drop_index("uq_content_pieces_slug_brief")

    # ── Drop new columns ──────────────────────────────────────────────
    op.drop_column("content_pieces", "company_id")
    op.drop_column("content_pieces", "brief_id")
    op.drop_column("content_pieces", "effective_slug")

    # ── Restore run_id NOT NULL (only safe if no NULL rows exist) ──────
    op.alter_column("content_pieces", "run_id", nullable=False)

    # ── Drop content_artifacts table ───────────────────────────────────
    op.drop_index("uq_content_artifacts_piece_stage", table_name="content_artifacts")
    op.drop_table("content_artifacts")

    # ── Drop enum type ─────────────────────────────────────────────────
    op.execute("DROP TYPE IF EXISTS content_artifact_stage_enum")
