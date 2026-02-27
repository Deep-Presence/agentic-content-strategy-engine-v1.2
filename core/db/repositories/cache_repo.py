"""Repository for platform result and URL enrichment caches."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import SearchEngine
from core.db.models.cache import (
    PlatformResultCacheModel,
    UrlEnrichmentCacheModel,
    UrlStructuralSignalsModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class CacheRepository(SQLAlchemyRepository[PlatformResultCacheModel]):
    """Manages both platform result cache and URL enrichment cache.

    "Fresh" means the ``fetched_at`` / ``scraped_at`` timestamp falls within
    ``max_age_days`` of the current UTC time.
    """

    model_class = PlatformResultCacheModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Platform Result Cache ────────────────────────────────────────────

    async def get_fresh_platform_result(
        self,
        query_hash: str,
        engine: SearchEngine,
        max_age_days: int = 7,
    ) -> PlatformResultCacheModel | None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        stmt = select(PlatformResultCacheModel).where(
            PlatformResultCacheModel.query_text_hash == query_hash,
            PlatformResultCacheModel.engine == engine,
            PlatformResultCacheModel.fetched_at >= cutoff,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert_platform_result(
        self, **kwargs: object
    ) -> PlatformResultCacheModel:
        """Insert or update a platform result cache entry.

        Uses Postgres ``ON CONFLICT (query_text_hash, engine) DO UPDATE``
        to keep the cache fresh.
        """
        stmt = pg_insert(PlatformResultCacheModel).values(**kwargs)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_platform_cache_hash_engine",
            set_={
                "response_text": stmt.excluded.response_text,
                "citations": stmt.excluded.citations,
                "model_version": stmt.excluded.model_version,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Re-fetch the row to return a mapped instance.
        return await self._get_platform_result_by_hash_engine(
            str(kwargs["query_text_hash"]),
            kwargs["engine"],  # type: ignore[arg-type]
        )

    async def _get_platform_result_by_hash_engine(
        self, query_hash: str, engine: SearchEngine
    ) -> PlatformResultCacheModel:
        stmt = select(PlatformResultCacheModel).where(
            PlatformResultCacheModel.query_text_hash == query_hash,
            PlatformResultCacheModel.engine == engine,
        )
        result = await self._session.execute(stmt)
        return result.scalars().one()

    # ── URL Enrichment Cache ─────────────────────────────────────────────

    async def get_fresh_url_enrichment(
        self,
        url_hash: str,
        max_age_days: int = 7,
    ) -> UrlEnrichmentCacheModel | None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        stmt = select(UrlEnrichmentCacheModel).where(
            UrlEnrichmentCacheModel.url_hash == url_hash,
            UrlEnrichmentCacheModel.scraped_at >= cutoff,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert_url_enrichment(
        self, **kwargs: object
    ) -> UrlEnrichmentCacheModel:
        """Insert or update a URL enrichment cache entry.

        Uses Postgres ``ON CONFLICT (url_hash) DO UPDATE`` to keep the cache
        fresh.
        """
        stmt = pg_insert(UrlEnrichmentCacheModel).values(**kwargs)
        stmt = stmt.on_conflict_do_update(
            index_elements=["url_hash"],
            set_={
                "final_url": stmt.excluded.final_url,
                "domain": stmt.excluded.domain,
                "title": stmt.excluded.title,
                "authority_type": stmt.excluded.authority_type,
                "content_type": stmt.excluded.content_type,
                "paragraph_count": stmt.excluded.paragraph_count,
                "http_status": stmt.excluded.http_status,
                "scraped_at": stmt.excluded.scraped_at,
                "raw_paragraphs_storage_key": stmt.excluded.raw_paragraphs_storage_key,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Re-fetch to return a mapped instance.
        return await self._get_url_enrichment_by_hash(str(kwargs["url_hash"]))

    async def _get_url_enrichment_by_hash(
        self, url_hash: str
    ) -> UrlEnrichmentCacheModel:
        stmt = select(UrlEnrichmentCacheModel).where(
            UrlEnrichmentCacheModel.url_hash == url_hash
        )
        result = await self._session.execute(stmt)
        return result.scalars().one()

    # ── Phase 4 bulk methods ─────────────────────────────────────────────

    async def bulk_upsert_platform_results(
        self, results: list[dict[str, object]]
    ) -> None:
        """Bulk upsert platform result cache entries via ON CONFLICT."""
        for row in results:
            stmt = pg_insert(PlatformResultCacheModel).values(**row)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_platform_cache_hash_engine",
                set_={
                    "response_text": stmt.excluded.response_text,
                    "citations": stmt.excluded.citations,
                    "model_version": stmt.excluded.model_version,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await self._session.execute(stmt)
        await self._session.flush()

    async def bulk_upsert_url_enrichments(
        self, enrichments: list[dict[str, object]]
    ) -> None:
        """Bulk upsert URL enrichment cache entries via ON CONFLICT."""
        for row in enrichments:
            stmt = pg_insert(UrlEnrichmentCacheModel).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["url_hash"],
                set_={
                    "final_url": stmt.excluded.final_url,
                    "domain": stmt.excluded.domain,
                    "title": stmt.excluded.title,
                    "authority_type": stmt.excluded.authority_type,
                    "content_type": stmt.excluded.content_type,
                    "paragraph_count": stmt.excluded.paragraph_count,
                    "http_status": stmt.excluded.http_status,
                    "scraped_at": stmt.excluded.scraped_at,
                    "raw_paragraphs_storage_key": stmt.excluded.raw_paragraphs_storage_key,
                },
            )
            await self._session.execute(stmt)
        await self._session.flush()

    async def bulk_insert_structural_signals(
        self, signals: list[dict[str, object]]
    ) -> None:
        """Insert multiple structural signal rows.

        Uses ON CONFLICT DO UPDATE on the PK (url_enrichment_id) to
        handle re-persists idempotently.
        """
        for row in signals:
            stmt = pg_insert(UrlStructuralSignalsModel).values(**row)
            # Update all signal columns on conflict
            update_cols = {
                c.name: getattr(stmt.excluded, c.name)
                for c in UrlStructuralSignalsModel.__table__.columns
                if c.name != "url_enrichment_id"
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["url_enrichment_id"],
                set_=update_cols,
            )
            await self._session.execute(stmt)
        await self._session.flush()
