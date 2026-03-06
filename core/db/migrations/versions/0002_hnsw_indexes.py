"""Create HNSW indexes on pgvector embedding columns.

Separated from the schema migration (0001) because HNSW index creation
can be slow on large tables and may need to be run with CONCURRENTLY
in production.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-27
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # HNSW indexes for pgvector similarity search
    # Using cosine distance (vector_cosine_ops) with m=16, ef_construction=64
    op.execute(
        "CREATE INDEX ix_semantic_units_embedding_hnsw ON semantic_units "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX ix_query_embeddings_embedding_hnsw ON query_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX ix_paragraph_embeddings_embedding_hnsw ON paragraph_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_index("ix_paragraph_embeddings_embedding_hnsw")
    op.drop_index("ix_query_embeddings_embedding_hnsw")
    op.drop_index("ix_semantic_units_embedding_hnsw")
