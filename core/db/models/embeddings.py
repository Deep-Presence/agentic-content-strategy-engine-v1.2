"""Embedding domain models — semantic units, query & paragraph embeddings, scores."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from pgvector.sqlalchemy import Vector

from core.db.base import Base, UUIDPKMixin


# ── Semantic Units ───────────────────────────────────────────────────────


class SemanticUnitModel(UUIDPKMixin, Base):
    """Embedded content chunk from a company's website or knowledge docs."""

    __tablename__ = "semantic_units"
    __table_args__ = (
        Index("ix_semantic_units_company_run", "company_id", "run_id"),
        Index("ix_semantic_units_slug_unit", "company_slug", "unit_id"),
        # HNSW index on the embedding column — actually created in migration 0002
        # to control index parameters (m, ef_construction) and avoid blocking
        # table creation during initial Alembic run.
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    unit_id: Mapped[str] = mapped_column(String, nullable=False)
    company_slug: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    discovery_source: Mapped[str] = mapped_column(String, default="website")
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Query Embeddings ─────────────────────────────────────────────────────


class QueryEmbeddingModel(UUIDPKMixin, Base):
    """Embedded search query generated during gap analysis."""

    __tablename__ = "query_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "query_id", name="uq_query_embeddings_run_query"
        ),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_id: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Paragraph Embeddings ─────────────────────────────────────────────────


class ParagraphEmbeddingModel(UUIDPKMixin, Base):
    """Embedded paragraph extracted from an enriched citation URL."""

    __tablename__ = "paragraph_embeddings"
    __table_args__ = (Index("ix_paragraph_embeddings_url_enrichment", "url_enrichment_id"),)

    url_enrichment_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("url_enrichment_cache.id", ondelete="CASCADE"),
        nullable=True,
    )
    embedding_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    company_slug: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    paragraph_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    original_paragraph_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Run Paragraph Scores ─────────────────────────────────────────────────


class RunParagraphScoreModel(UUIDPKMixin, Base):
    """Top-k paragraph similarity score for a citation within a run."""

    __tablename__ = "run_paragraph_scores"
    __table_args__ = (
        Index("ix_run_paragraph_scores_citation", "run_citation_id"),
    )

    run_citation_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("run_citations.id", ondelete="CASCADE"),
        nullable=False,
    )
    paragraph_embedding_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("paragraph_embeddings.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)


# ── Persona Embeddings ──────────────────────────────────────────────────


class PersonaEmbeddingModel(UUIDPKMixin, Base):
    """Embedded audience persona profile for vector similarity search."""

    __tablename__ = "persona_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "effective_slug", "persona_id", name="uq_persona_embeddings_slug_persona"
        ),
        Index("ix_persona_embeddings_slug", "effective_slug"),
    )

    company_slug: Mapped[str] = mapped_column(String, nullable=False)
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)
    persona_id: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
