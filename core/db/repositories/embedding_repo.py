"""Repository for embedding operations (semantic units, query & paragraph embeddings)."""
from __future__ import annotations

from typing import Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.base import Base
from core.db.models.embeddings import (
    ParagraphEmbeddingModel,
    QueryEmbeddingModel,
    SemanticUnitModel,
)
from core.db.repositories.base import SQLAlchemyRepository

EmbeddingModelT = TypeVar(
    "EmbeddingModelT",
    SemanticUnitModel,
    QueryEmbeddingModel,
    ParagraphEmbeddingModel,
)


class EmbeddingRepository(SQLAlchemyRepository[SemanticUnitModel]):
    """Repository for all embedding-related models.

    Provides a generic ``store_embedding`` / ``similarity_search`` interface
    that works with any of the three embedding models.
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
