"""pgvector migration: persona_embeddings table, nullable FKs, company_slug columns.

Adds the persona_embeddings table for audience persona vector storage,
relaxes the paragraph_embeddings FK constraint, and adds denormalized
company_slug columns for direct slug-based queries (replaces ChromaDB
collection-name addressing).

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "0016"
down_revision: str = "0015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. Create persona_embeddings table ────────────────────────────────
    op.create_table(
        "persona_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_slug", sa.String, nullable=False),
        sa.Column("effective_slug", sa.String, nullable=False),
        sa.Column("persona_id", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_persona_embeddings_slug_persona",
        "persona_embeddings",
        ["effective_slug", "persona_id"],
    )
    op.create_index(
        "ix_persona_embeddings_slug",
        "persona_embeddings",
        ["effective_slug"],
    )
    # HNSW index for vector similarity search
    op.execute("""
        CREATE INDEX ix_persona_embeddings_hnsw
        ON persona_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ── 2. Add company_slug to semantic_units ─────────────────────────────
    op.add_column("semantic_units", sa.Column("company_slug", sa.String, nullable=True))
    op.create_index(
        "ix_semantic_units_company_slug",
        "semantic_units",
        ["company_slug"],
    )
    op.create_index(
        "ix_semantic_units_slug_unit",
        "semantic_units",
        ["company_slug", "unit_id"],
    )
    # Make run_id nullable (for script-based inserts without pipeline context)
    op.alter_column("semantic_units", "run_id", nullable=True)
    # Backfill company_slug from companies table for existing rows
    op.execute("""
        UPDATE semantic_units su
        SET company_slug = c.slug
        FROM companies c
        WHERE su.company_id = c.id AND su.company_slug IS NULL
    """)

    # ── 3. Alter paragraph_embeddings ─────────────────────────────────────
    # Make url_enrichment_id nullable (removes hard FK requirement)
    op.alter_column("paragraph_embeddings", "url_enrichment_id", nullable=True)
    # Add company_slug for direct slug-based queries
    op.add_column("paragraph_embeddings", sa.Column("company_slug", sa.String, nullable=True))
    op.create_index(
        "ix_paragraph_embeddings_company_slug",
        "paragraph_embeddings",
        ["company_slug"],
    )


def downgrade() -> None:
    # ── 3. Revert paragraph_embeddings ────────────────────────────────────
    op.drop_index("ix_paragraph_embeddings_company_slug", table_name="paragraph_embeddings")
    op.drop_column("paragraph_embeddings", "company_slug")
    # Clean null rows before re-constraining to avoid IntegrityError
    op.execute("DELETE FROM paragraph_embeddings WHERE url_enrichment_id IS NULL")
    op.alter_column("paragraph_embeddings", "url_enrichment_id", nullable=False)

    # ── 2. Revert semantic_units ──────────────────────────────────────────
    # Clean null rows before re-constraining to avoid IntegrityError
    op.execute("DELETE FROM semantic_units WHERE run_id IS NULL")
    op.alter_column("semantic_units", "run_id", nullable=False)
    op.drop_index("ix_semantic_units_slug_unit", table_name="semantic_units")
    op.drop_index("ix_semantic_units_company_slug", table_name="semantic_units")
    op.drop_column("semantic_units", "company_slug")

    # ── 1. Drop persona_embeddings ────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_persona_embeddings_hnsw")
    op.drop_index("ix_persona_embeddings_slug", table_name="persona_embeddings")
    op.drop_constraint("uq_persona_embeddings_slug_persona", "persona_embeddings")
    op.drop_table("persona_embeddings")
