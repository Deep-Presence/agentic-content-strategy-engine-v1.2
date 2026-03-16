"""pgvector-backed vector store — drop-in replacement for async_chroma_client.

All module-level convenience functions mirror the async_chroma_client API
exactly so that consumers only need to change their import path.

Session management: each method opens its own session (per-function
isolation, matching the persistence.py pattern).
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


class VectorStoreClient:
    """pgvector-backed vector store. Replaces ChromaDB.

    Each method opens its own session for per-operation transaction isolation.
    Errors are caught and logged — vector store failures never crash pipelines.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._slug_cache: dict[str, _uuid.UUID] = {}

    def _get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is not None:
            return self._session_factory
        from core.db.engine import get_session_factory
        self._session_factory = get_session_factory()
        return self._session_factory

    async def _resolve_company_id(
        self, slug: str, session: AsyncSession,
    ) -> _uuid.UUID | None:
        """Resolve company slug to company_id (cached for pipeline duration)."""
        if slug in self._slug_cache:
            return self._slug_cache[slug]
        from core.db.models.organization import CompanyModel
        stmt = select(CompanyModel.id).where(CompanyModel.slug == slug)
        result = await session.execute(stmt)
        company_id = result.scalar_one_or_none()
        if company_id:
            self._slug_cache[slug] = company_id
        return company_id

    # ── Company Asset Embeddings (S1) ────────────────────────────────────

    async def upsert_embeddings(
        self,
        company_slug: str,
        unit_ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, str]]] = None,
        *,
        company_id: _uuid.UUID | None = None,
        run_id: _uuid.UUID | None = None,
    ) -> None:
        """Upsert semantic unit embeddings into pgvector."""
        if not unit_ids:
            return
        try:
            from core.db.models.embeddings import SemanticUnitModel

            sf = self._get_session_factory()
            async with sf() as session:
                if company_id is None:
                    company_id = await self._resolve_company_id(company_slug, session)
                if company_id is None:
                    logger.warning(
                        "vector_store: company '%s' not found, skipping upsert", company_slug
                    )
                    return

                # Delete existing embeddings for this slug (idempotent re-runs)
                await session.execute(
                    delete(SemanticUnitModel)
                    .where(SemanticUnitModel.company_slug == company_slug)
                )

                for i in range(0, len(unit_ids), _BATCH_SIZE):
                    end = i + _BATCH_SIZE
                    batch_items = []
                    for j in range(i, min(end, len(unit_ids))):
                        meta = metadatas[j] if metadatas else {}
                        batch_items.append({
                            "id": _uuid.uuid4(),
                            "company_id": company_id,
                            "run_id": run_id,
                            "unit_id": unit_ids[j],
                            "company_slug": company_slug,
                            "text": texts[j],
                            "embedding": embeddings[j],
                            "url": meta.get("url") if meta else None,
                            "title": meta.get("title") if meta else None,
                            "discovery_source": meta.get("discovery_source", "website") if meta else "website",
                            "char_count": len(texts[j]),
                            "word_count": len(texts[j].split()),
                        })
                    session.add_all([SemanticUnitModel(**item) for item in batch_items])
                    await session.flush()

                await session.commit()
            logger.info(
                "vector_store: upserted %d semantic units for '%s'",
                len(unit_ids), company_slug,
            )
        except Exception:
            logger.warning(
                "vector_store: upsert_embeddings failed for '%s', continuing",
                company_slug, exc_info=True,
            )

    async def get_embeddings_by_ids(
        self,
        company_slug: str,
        unit_ids: List[str],
    ) -> Dict[str, List[float]]:
        """Retrieve embeddings for specific unit IDs."""
        if not unit_ids:
            return {}
        try:
            from core.db.models.embeddings import SemanticUnitModel

            sf = self._get_session_factory()
            async with sf() as session:
                stmt = (
                    select(SemanticUnitModel.unit_id, SemanticUnitModel.embedding)
                    .where(
                        SemanticUnitModel.company_slug == company_slug,
                        SemanticUnitModel.unit_id.in_(unit_ids),
                    )
                )
                result = await session.execute(stmt)
                return {
                    row.unit_id: [float(x) for x in row.embedding]
                    for row in result.all()
                }
        except Exception:
            logger.warning(
                "vector_store: get_embeddings_by_ids failed for '%s', returning empty",
                company_slug, exc_info=True,
            )
            return {}

    async def get_all_embeddings(
        self,
        company_slug: str,
    ) -> Dict[str, List[float]]:
        """Retrieve all embeddings for a company slug."""
        try:
            from core.db.models.embeddings import SemanticUnitModel

            sf = self._get_session_factory()
            async with sf() as session:
                stmt = (
                    select(SemanticUnitModel.unit_id, SemanticUnitModel.embedding)
                    .where(SemanticUnitModel.company_slug == company_slug)
                )
                result = await session.execute(stmt)
                return {
                    row.unit_id: [float(x) for x in row.embedding]
                    for row in result.all()
                }
        except Exception:
            logger.warning(
                "vector_store: get_all_embeddings failed for '%s', returning empty",
                company_slug, exc_info=True,
            )
            return {}

    async def collection_exists(
        self,
        company_slug: str,
    ) -> bool:
        """Check if any embeddings exist for a company slug."""
        try:
            from core.db.models.embeddings import SemanticUnitModel

            sf = self._get_session_factory()
            async with sf() as session:
                stmt = (
                    select(func.count())
                    .select_from(SemanticUnitModel)
                    .where(SemanticUnitModel.company_slug == company_slug)
                )
                result = await session.execute(stmt)
                return result.scalar_one() > 0
        except Exception:
            logger.warning(
                "vector_store: collection_exists failed for '%s', returning False",
                company_slug, exc_info=True,
            )
            return False

    async def delete_company_embeddings(
        self,
        company_slug: str,
    ) -> None:
        """Delete all semantic unit embeddings for a company slug."""
        try:
            from core.db.models.embeddings import SemanticUnitModel

            sf = self._get_session_factory()
            async with sf() as session:
                stmt = (
                    delete(SemanticUnitModel)
                    .where(SemanticUnitModel.company_slug == company_slug)
                )
                result = await session.execute(stmt)
                await session.commit()
            logger.info(
                "vector_store: deleted %d semantic units for '%s'",
                result.rowcount, company_slug,
            )
        except Exception:
            logger.warning(
                "vector_store: delete_company_embeddings failed for '%s'",
                company_slug, exc_info=True,
            )

    # ── Citation Embeddings (S5) ─────────────────────────────────────────

    async def upsert_citation_embeddings(
        self,
        company_slug: str,
        embedding_ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Upsert citation paragraph embeddings into pgvector."""
        if not embedding_ids:
            return
        try:
            from core.db.models.embeddings import ParagraphEmbeddingModel

            sf = self._get_session_factory()
            async with sf() as session:
                for i in range(0, len(embedding_ids), _BATCH_SIZE):
                    end = i + _BATCH_SIZE
                    batch_items = []
                    for j in range(i, min(end, len(embedding_ids))):
                        batch_items.append({
                            "id": _uuid.uuid4(),
                            "embedding_id": embedding_ids[j],
                            "company_slug": company_slug,
                            "paragraph_text": documents[j],
                            "embedding": embeddings[j],
                        })
                    stmt = pg_insert(ParagraphEmbeddingModel).values(batch_items)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["embedding_id"],
                        set_={
                            "paragraph_text": stmt.excluded.paragraph_text,
                            "embedding": stmt.excluded.embedding,
                            "company_slug": stmt.excluded.company_slug,
                        },
                    )
                    await session.execute(stmt)

                await session.commit()
            logger.info(
                "vector_store: upserted %d citation embeddings for '%s'",
                len(embedding_ids), company_slug,
            )
        except Exception:
            logger.warning(
                "vector_store: upsert_citation_embeddings failed for '%s', continuing",
                company_slug, exc_info=True,
            )

    # ── Persona Embeddings ───────────────────────────────────────────────

    async def upsert_persona_embeddings(
        self,
        effective_slug: str,
        persona_ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
    ) -> None:
        """Upsert persona profile embeddings into pgvector."""
        if not persona_ids:
            return
        try:
            from core.db.models.embeddings import PersonaEmbeddingModel

            # Extract company_slug from effective_slug (company__product or just company)
            company_slug = effective_slug.split("__")[0]

            sf = self._get_session_factory()
            async with sf() as session:
                items = []
                for i in range(len(persona_ids)):
                    items.append({
                        "id": _uuid.uuid4(),
                        "company_slug": company_slug,
                        "effective_slug": effective_slug,
                        "persona_id": persona_ids[i],
                        "text": texts[i],
                        "embedding": embeddings[i],
                    })
                stmt = pg_insert(PersonaEmbeddingModel).values(items)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_persona_embeddings_slug_persona",
                    set_={
                        "text": stmt.excluded.text,
                        "embedding": stmt.excluded.embedding,
                        "company_slug": stmt.excluded.company_slug,
                    },
                )
                await session.execute(stmt)
                await session.commit()
            logger.info(
                "vector_store: upserted %d persona embeddings for '%s'",
                len(persona_ids), effective_slug,
            )
        except Exception:
            logger.warning(
                "vector_store: upsert_persona_embeddings failed for '%s', continuing",
                effective_slug, exc_info=True,
            )

    async def get_persona_embeddings(
        self,
        effective_slug: str,
        persona_ids: Optional[List[str]] = None,
    ) -> Dict[str, List[float]]:
        """Retrieve persona embeddings by effective slug."""
        try:
            from core.db.models.embeddings import PersonaEmbeddingModel

            sf = self._get_session_factory()
            async with sf() as session:
                stmt = (
                    select(PersonaEmbeddingModel.persona_id, PersonaEmbeddingModel.embedding)
                    .where(PersonaEmbeddingModel.effective_slug == effective_slug)
                )
                if persona_ids:
                    stmt = stmt.where(PersonaEmbeddingModel.persona_id.in_(persona_ids))
                result = await session.execute(stmt)
                return {
                    row.persona_id: [float(x) for x in row.embedding]
                    for row in result.all()
                }
        except Exception:
            logger.warning(
                "vector_store: get_persona_embeddings failed for '%s', returning empty",
                effective_slug, exc_info=True,
            )
            return {}


# ── Module-Level Convenience Functions ───────────────────────────────────
# Drop-in replacements for async_chroma_client functions.
# Consumers only need to change their import path.

_client: VectorStoreClient | None = None


def _get_client() -> VectorStoreClient:
    """Lazy-initialize the module-level VectorStoreClient singleton."""
    global _client
    if _client is None:
        _client = VectorStoreClient()
    return _client


def _reset_client() -> None:
    """Reset the module-level client (for testing)."""
    global _client
    _client = None


# ── Company asset embeddings (S1) ────────────────────────────────────────


async def async_upsert_embeddings(
    company_slug: str,
    unit_ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, str]]] = None,
    *,
    company_id: _uuid.UUID | None = None,
    run_id: _uuid.UUID | None = None,
) -> None:
    """Upsert semantic unit embeddings (drop-in for async_chroma_client)."""
    await _get_client().upsert_embeddings(
        company_slug, unit_ids, texts, embeddings, metadatas,
        company_id=company_id, run_id=run_id,
    )


async def async_get_all_embeddings(
    company_slug: str,
) -> Dict[str, List[float]]:
    """Retrieve all embeddings for a company (drop-in for async_chroma_client)."""
    return await _get_client().get_all_embeddings(company_slug)


async def async_get_embeddings_by_ids(
    company_slug: str,
    unit_ids: List[str],
) -> Dict[str, List[float]]:
    """Retrieve embeddings by IDs (drop-in for async_chroma_client)."""
    return await _get_client().get_embeddings_by_ids(company_slug, unit_ids)


async def async_delete_company_collection(company_slug: str) -> None:
    """Delete company embeddings (drop-in for async_chroma_client)."""
    await _get_client().delete_company_embeddings(company_slug)


async def async_collection_exists(company_slug: str) -> bool:
    """Check if embeddings exist (drop-in for async_chroma_client)."""
    return await _get_client().collection_exists(company_slug)


# ── Citation embeddings (S5) ─────────────────────────────────────────────


async def async_upsert_citation_embeddings(
    company_slug: str,
    embedding_ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Upsert citation embeddings (drop-in for async_chroma_client)."""
    await _get_client().upsert_citation_embeddings(
        company_slug, embedding_ids, documents, embeddings, metadatas,
    )


# ── Persona embeddings ──────────────────────────────────────────────────


async def async_upsert_persona_embeddings(
    effective_slug: str,
    persona_ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
) -> None:
    """Upsert persona embeddings (drop-in for async_chroma_client)."""
    await _get_client().upsert_persona_embeddings(
        effective_slug, persona_ids, texts, embeddings,
    )


async def async_get_persona_embeddings(
    effective_slug: str,
    persona_ids: Optional[List[str]] = None,
) -> Dict[str, List[float]]:
    """Retrieve persona embeddings (drop-in for async_chroma_client)."""
    return await _get_client().get_persona_embeddings(effective_slug, persona_ids)
