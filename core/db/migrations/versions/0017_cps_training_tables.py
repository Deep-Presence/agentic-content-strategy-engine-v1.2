"""CPS training tables: snippet + query embeddings for pgvector-backed training pipeline.

Creates cps_training_snippets and cps_training_queries tables with HNSW indexes,
replacing ChromaDB collections used by the external CPS training pipeline.

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "0017"
down_revision: str = "0016"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── cps_training_snippets ───────────────────────────────────────────
    op.create_table(
        "cps_training_snippets",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("snippet_id", sa.String(), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("citation_count", sa.Integer(), server_default="0"),
        sa.Column("selection_rate", sa.Float(), server_default="0.0"),
        sa.Column("engine_mask", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_cps_snippets_hnsw",
        "cps_training_snippets",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # ── cps_training_queries ────────────────────────────────────────────
    op.create_table(
        "cps_training_queries",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_id", sa.String(), nullable=False, unique=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("engine", sa.String(), nullable=True),
        sa.Column("selection_rate", sa.Float(), server_default="0.0"),
        sa.Column("snippet_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_cps_queries_hnsw",
        "cps_training_queries",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_cps_queries_hnsw", table_name="cps_training_queries")
    op.drop_table("cps_training_queries")
    op.drop_index("ix_cps_snippets_hnsw", table_name="cps_training_snippets")
    op.drop_table("cps_training_snippets")
