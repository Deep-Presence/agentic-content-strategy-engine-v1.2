"""Repository for embedding operations (semantic units, query & paragraph embeddings)."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence, Type, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.base import Base
from core.db.models.embeddings import (
    ParagraphEmbeddingModel,
    PersonaEmbeddingModel,
    QueryEmbeddingModel,
    SemanticUnitModel,
)
from core.db.repositories.base import SQLAlchemyRepository

EmbeddingModelT = TypeVar(
    "EmbeddingModelT",
    SemanticUnitModel,
    QueryEmbeddingModel,
    ParagraphEmbeddingModel,
    PersonaEmbeddingModel,
)


class EmbeddingRepository(SQLAlchemyRepository[SemanticUnitModel]):
    """Repository for all embedding-related models.

    Provides a generic ``store_embedding`` / ``similarity_search`` interface
    that works with any of the embedding models.
    """

    model_class = SemanticUnitModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def store_embedding(
        self,
        model_class: Type[EmbeddingModelT],
        **kwargs: object,
    ) -> EmbeddingModelT:
        """Insert a single embedding row for any embedding model type."""
        instance = model_class(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    # ── Phase 4 bulk insert methods ──────────────────────────────────────

    async def bulk_store_embeddings(
        self,
        model_class: Type[EmbeddingModelT],
        items: list[dict[str, object]],
    ) -> None:
        """Insert multiple embedding rows for any embedding model type."""
        instances = [model_class(**item) for item in items]
        self._session.add_all(instances)
        await self._session.flush()

    async def similarity_search(
        self,
        model_class: Type[EmbeddingModelT],
        query_vector: list[float],
        *,
        limit: int = 10,
    ) -> Sequence[EmbeddingModelT]:
        """Return nearest neighbours by cosine distance (ascending).

        Uses pgvector's ``<=>`` cosine distance operator via the
        ``model_class.embedding.cosine_distance(query_vector)`` expression.
        """
        distance_expr = model_class.embedding.cosine_distance(query_vector)  # type: ignore[attr-defined]
        stmt = (
            select(model_class)
            .order_by(distance_expr.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Semantic units — slug-based queries (pgvector migration) ─────────

    async def get_semantic_units_by_slug(
        self, company_slug: str,
    ) -> Sequence[SemanticUnitModel]:
        """Return all semantic units for a company slug."""
        stmt = (
            select(SemanticUnitModel)
            .where(SemanticUnitModel.company_slug == company_slug)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_semantic_units_by_ids(
        self, company_slug: str, unit_ids: list[str],
    ) -> Sequence[SemanticUnitModel]:
        """Return specific semantic units by slug + unit_ids."""
        stmt = (
            select(SemanticUnitModel)
            .where(
                SemanticUnitModel.company_slug == company_slug,
                SemanticUnitModel.unit_id.in_(unit_ids),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_slug(self, company_slug: str) -> int:
        """Return count of semantic units for a company slug."""
        stmt = (
            select(func.count())
            .select_from(SemanticUnitModel)
            .where(SemanticUnitModel.company_slug == company_slug)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_by_slug(self, company_slug: str) -> int:
        """Delete all semantic units for a company slug. Returns deleted count."""
        stmt = (
            delete(SemanticUnitModel)
            .where(SemanticUnitModel.company_slug == company_slug)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    # ── Paragraph embeddings — upsert by embedding_id ────────────────────

    async def upsert_paragraph_embeddings(
        self, items: list[dict[str, object]],
    ) -> None:
        """Upsert citation paragraph embeddings (ON CONFLICT embedding_id DO UPDATE)."""
        if not items:
            return
        stmt = pg_insert(ParagraphEmbeddingModel).values(items)
        stmt = stmt.on_conflict_do_update(
            index_elements=["embedding_id"],
            set_={
                "paragraph_text": stmt.excluded.paragraph_text,
                "embedding": stmt.excluded.embedding,
                "company_slug": stmt.excluded.company_slug,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    # ── Persona embeddings — upsert + query ──────────────────────────────

    async def upsert_persona_embeddings(
        self, items: list[dict[str, object]],
    ) -> None:
        """Upsert persona embeddings (ON CONFLICT effective_slug+persona_id DO UPDATE)."""
        if not items:
            return
        stmt = pg_insert(PersonaEmbeddingModel).values(items)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_persona_embeddings_slug_persona",
            set_={
                "text": stmt.excluded.text,
                "embedding": stmt.excluded.embedding,
                "company_slug": stmt.excluded.company_slug,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_persona_embeddings_by_slug(
        self,
        effective_slug: str,
        persona_ids: list[str] | None = None,
    ) -> Sequence[PersonaEmbeddingModel]:
        """Return persona embeddings for an effective slug, optionally filtered by IDs."""
        stmt = (
            select(PersonaEmbeddingModel)
            .where(PersonaEmbeddingModel.effective_slug == effective_slug)
        )
        if persona_ids:
            stmt = stmt.where(PersonaEmbeddingModel.persona_id.in_(persona_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()
