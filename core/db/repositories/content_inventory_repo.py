"""Repository for the content_inventory table."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.content_inventory.url_utils import normalize_url
from core.db.enums import ContentIngestionSource
from core.db.models.content_inventory import ContentInventoryModel
from core.db.repositories.base import SQLAlchemyRepository


class ContentInventoryRepository(SQLAlchemyRepository[ContentInventoryModel]):
    """Repository for content_inventory table.

    Transaction ownership: only ``session.flush()``, never ``session.commit()``.
    """

    model_class = ContentInventoryModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Upsert ────────────────────────────────────────────────────

    async def upsert_page(
        self,
        *,
        company_id: _uuid.UUID,
        effective_slug: str,
        url: str,
        title: str,
        ingestion_source: ContentIngestionSource,
        ingestion_run_id: _uuid.UUID | None = None,
        h1_text: str = "",
        meta_description: str = "",
        content_preview: str = "",
        word_count: int = 0,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        seo_title: str = "",
        seo_description: str = "",
        published_at: datetime | None = None,
        content_modified_at: datetime | None = None,
        has_faq_section: bool = False,
        has_schema_markup: bool = False,
        heading_count: int = 0,
        content_type_detected: str = "",
    ) -> ContentInventoryModel:
        """Insert or update a content inventory record.

        Dedup key: (company_id, url_normalized).
        On conflict: updates all mutable fields, preserves embedding if present.
        """
        url_norm = normalize_url(url)
        new_id = _uuid.uuid4()
        now = datetime.now(timezone.utc)

        values = {
            "id": new_id,
            "company_id": company_id,
            "effective_slug": effective_slug,
            "url": url,
            "url_normalized": url_norm,
            "title": title,
            "h1_text": h1_text,
            "meta_description": meta_description,
            "content_preview": content_preview,
            "word_count": word_count,
            "categories": categories,
            "tags": tags,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "published_at": published_at,
            "content_modified_at": content_modified_at,
            "last_crawled_at": now,
            "ingestion_source": ingestion_source.value,
            "ingestion_run_id": ingestion_run_id,
            "has_faq_section": has_faq_section,
            "has_schema_markup": has_schema_markup,
            "heading_count": heading_count,
            "content_type_detected": content_type_detected,
            "created_at": now,
            "updated_at": now,
        }

        stmt = pg_insert(ContentInventoryModel).values(values)

        # On conflict: update mutable fields, preserve embedding
        update_set = {
            "title": stmt.excluded.title,
            "h1_text": stmt.excluded.h1_text,
            "meta_description": stmt.excluded.meta_description,
            "content_preview": stmt.excluded.content_preview,
            "word_count": stmt.excluded.word_count,
            "categories": stmt.excluded.categories,
            "tags": stmt.excluded.tags,
            "seo_title": stmt.excluded.seo_title,
            "seo_description": stmt.excluded.seo_description,
            "published_at": stmt.excluded.published_at,
            "content_modified_at": stmt.excluded.content_modified_at,
            "last_crawled_at": stmt.excluded.last_crawled_at,
            "ingestion_source": stmt.excluded.ingestion_source,
            "ingestion_run_id": stmt.excluded.ingestion_run_id,
            "has_faq_section": stmt.excluded.has_faq_section,
            "has_schema_markup": stmt.excluded.has_schema_markup,
            "heading_count": stmt.excluded.heading_count,
            "content_type_detected": stmt.excluded.content_type_detected,
            "effective_slug": stmt.excluded.effective_slug,
            "updated_at": stmt.excluded.updated_at,
        }

        stmt = stmt.on_conflict_do_update(
            constraint="uq_content_inventory_company_url",
            set_=update_set,
        ).returning(ContentInventoryModel)

        result = await self._session.execute(stmt)
        row = result.scalars().first()
        if row is not None:
            await self._session.flush()
            return row

        # Fallback: re-query (should not happen with RETURNING)
        q = select(ContentInventoryModel).where(
            ContentInventoryModel.company_id == company_id,
            ContentInventoryModel.url_normalized == url_norm,
        )
        result = await self._session.execute(q)
        row = result.scalars().first()
        await self._session.flush()
        return row  # type: ignore[return-value]

    async def bulk_upsert_from_crawl(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        ingestion_run_id: _uuid.UUID,
        pages: list[Any],
    ) -> int:
        """Batch upsert from site audit crawl. Returns upsert count.

        *pages* should be ``CrawledPageData`` instances (or any object with
        matching attributes).
        """
        if not pages:
            return 0

        now = datetime.now(timezone.utc)
        rows: list[dict[str, Any]] = []

        for page in pages:
            url_norm = normalize_url(page.url)
            if not url_norm:
                continue

            # Parse sitemap_lastmod if present
            content_modified_at = None
            if hasattr(page, "sitemap_lastmod") and page.sitemap_lastmod:
                try:
                    content_modified_at = datetime.fromisoformat(
                        page.sitemap_lastmod.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            rows.append(
                {
                    "id": _uuid.uuid4(),
                    "company_id": company_id,
                    "effective_slug": effective_slug,
                    "url": page.url,
                    "url_normalized": url_norm,
                    "title": getattr(page, "title", "") or "",
                    "h1_text": getattr(page, "h1_text", "") or "",
                    "meta_description": getattr(page, "meta_description", "") or "",
                    "content_preview": getattr(page, "content_preview", "") or "",
                    "word_count": getattr(page, "word_count", 0) or 0,
                    "has_faq_section": getattr(page, "has_faq_section", False),
                    "has_schema_markup": getattr(page, "has_schema_markup", False),
                    "heading_count": getattr(page, "heading_count", 0) or 0,
                    "content_type_detected": getattr(page, "content_type_detected", "") or "",
                    "ingestion_source": ContentIngestionSource.site_audit_crawl.value,
                    "ingestion_run_id": ingestion_run_id,
                    "last_crawled_at": now,
                    "content_modified_at": content_modified_at,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        if not rows:
            return 0

        stmt = pg_insert(ContentInventoryModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_content_inventory_company_url",
            set_={
                "title": stmt.excluded.title,
                "h1_text": stmt.excluded.h1_text,
                "meta_description": stmt.excluded.meta_description,
                "content_preview": stmt.excluded.content_preview,
                "word_count": stmt.excluded.word_count,
                "has_faq_section": stmt.excluded.has_faq_section,
                "has_schema_markup": stmt.excluded.has_schema_markup,
                "heading_count": stmt.excluded.heading_count,
                "content_type_detected": stmt.excluded.content_type_detected,
                "ingestion_source": stmt.excluded.ingestion_source,
                "ingestion_run_id": stmt.excluded.ingestion_run_id,
                "last_crawled_at": stmt.excluded.last_crawled_at,
                "content_modified_at": stmt.excluded.content_modified_at,
                "effective_slug": stmt.excluded.effective_slug,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]

    # ── Embedding ─────────────────────────────────────────────────

    async def update_embeddings_batch(
        self,
        updates: list[tuple[_uuid.UUID, list[float]]],
    ) -> int:
        """Batch update embedding column. Returns count updated."""
        if not updates:
            return 0
        count = 0
        for record_id, embedding in updates:
            stmt = (
                update(ContentInventoryModel)
                .where(ContentInventoryModel.id == record_id)
                .values(embedding=embedding)
            )
            result = await self._session.execute(stmt)
            count += result.rowcount
        await self._session.flush()
        return count

    async def get_pages_missing_embeddings(
        self,
        company_id: _uuid.UUID,
        *,
        limit: int = 500,
    ) -> Sequence[ContentInventoryModel]:
        """Return pages for a company that don't have embeddings yet."""
        stmt = (
            select(ContentInventoryModel)
            .where(
                ContentInventoryModel.company_id == company_id,
                ContentInventoryModel.embedding.is_(None),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Similarity ────────────────────────────────────────────────

    async def find_similar(
        self,
        company_id: _uuid.UUID,
        query_embedding: list[float],
        *,
        threshold: float = 0.80,
        limit: int = 5,
    ) -> list[tuple[ContentInventoryModel, float]]:
        """Find inventory pages similar to a query embedding.

        Returns (model, cosine_similarity) pairs ordered by similarity desc.
        Cosine similarity = 1 - cosine_distance.
        """
        distance_expr = ContentInventoryModel.embedding.cosine_distance(  # type: ignore[attr-defined]
            query_embedding
        )
        similarity_expr = (1 - distance_expr).label("similarity")

        stmt = (
            select(ContentInventoryModel, similarity_expr)
            .where(
                ContentInventoryModel.company_id == company_id,
                ContentInventoryModel.embedding.isnot(None),
                (1 - distance_expr) >= threshold,
            )
            .order_by(distance_expr.asc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    # ── Query ─────────────────────────────────────────────────────

    async def get_by_company(
        self,
        company_id: _uuid.UUID,
        *,
        ingestion_source: ContentIngestionSource | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[Sequence[ContentInventoryModel], int]:
        """Paginated listing with optional source filter. Returns (items, total)."""
        base_filter = [ContentInventoryModel.company_id == company_id]
        if ingestion_source is not None:
            base_filter.append(
                ContentInventoryModel.ingestion_source == ingestion_source
            )

        # Count
        count_stmt = (
            select(func.count())
            .select_from(ContentInventoryModel)
            .where(*base_filter)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        # Items
        items_stmt = (
            select(ContentInventoryModel)
            .where(*base_filter)
            .order_by(ContentInventoryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = (await self._session.execute(items_stmt)).scalars().all()

        return items, total

    async def get_stats(
        self,
        company_id: _uuid.UUID,
    ) -> dict[str, Any]:
        """Aggregate stats: total pages, by source, avg word count, coverage metrics."""
        base = ContentInventoryModel.company_id == company_id

        # Total
        total = (
            await self._session.execute(
                select(func.count()).select_from(ContentInventoryModel).where(base)
            )
        ).scalar_one()

        # By source
        source_rows = (
            await self._session.execute(
                select(
                    ContentInventoryModel.ingestion_source,
                    func.count(),
                )
                .where(base)
                .group_by(ContentInventoryModel.ingestion_source)
            )
        ).all()
        by_source = {
            (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
            for row in source_rows
        }

        # Avg word count
        avg_wc = (
            await self._session.execute(
                select(func.avg(ContentInventoryModel.word_count)).where(base)
            )
        ).scalar_one()

        # Pages with embeddings
        with_embeddings = (
            await self._session.execute(
                select(func.count())
                .select_from(ContentInventoryModel)
                .where(base, ContentInventoryModel.embedding.isnot(None))
            )
        ).scalar_one()

        # Oldest and newest content
        oldest = (
            await self._session.execute(
                select(func.min(ContentInventoryModel.published_at)).where(base)
            )
        ).scalar_one()

        newest = (
            await self._session.execute(
                select(func.max(ContentInventoryModel.published_at)).where(base)
            )
        ).scalar_one()

        return {
            "total_pages": total,
            "by_source": by_source,
            "avg_word_count": round(float(avg_wc), 1) if avg_wc else 0.0,
            "pages_with_embeddings": with_embeddings,
            "oldest_content": oldest.isoformat() if oldest else None,
            "newest_content": newest.isoformat() if newest else None,
        }

    # ── Delete ────────────────────────────────────────────────────

    async def delete_by_company(
        self,
        company_id: _uuid.UUID,
    ) -> int:
        """Delete all inventory records for a company. Returns count."""
        stmt = (
            delete(ContentInventoryModel)
            .where(ContentInventoryModel.company_id == company_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
