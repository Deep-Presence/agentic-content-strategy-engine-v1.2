"""Repository for the content_inventory_prompts join table.

Provides link CRUD, bidirectional lookups, and per-page metric
aggregation for the Content-to-Prompt pipeline.

Transaction ownership: only ``session.flush()``, never ``session.commit()``.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.content_inventory_prompt import ContentInventoryPromptModel
from core.db.models.daily_tracker import DailyRunResponseModel, TrackedPromptModel
from core.db.repositories.base import SQLAlchemyRepository


class ContentInventoryPromptRepository(
    SQLAlchemyRepository[ContentInventoryPromptModel],
):
    """Repository for content_inventory_prompts join table."""

    model_class = ContentInventoryPromptModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Bulk creation ─────────────────────────────────────────────

    async def bulk_create_links(
        self,
        links: list[dict[str, Any]],
    ) -> list[ContentInventoryPromptModel]:
        """Create multiple link rows in a single flush.

        Each dict must contain at least ``content_inventory_id`` and
        ``tracked_prompt_id``.  Optional: ``generation_run_id``,
        ``buyer_stage``, ``intent_type``, ``is_branded``, ``approved``.

        Returns created ORM instances.
        """
        instances: list[ContentInventoryPromptModel] = []
        for link in links:
            obj = ContentInventoryPromptModel(**link)
            self._session.add(obj)
            instances.append(obj)
        if instances:
            await self._session.flush()
        return instances

    # ── Lookups ───────────────────────────────────────────────────

    async def get_prompts_for_page(
        self,
        inventory_id: _uuid.UUID,
        *,
        approved_only: bool = False,
    ) -> Sequence[ContentInventoryPromptModel]:
        """Get all link rows for a content inventory page."""
        stmt = select(ContentInventoryPromptModel).where(
            ContentInventoryPromptModel.content_inventory_id == inventory_id,
        )
        if approved_only:
            stmt = stmt.where(ContentInventoryPromptModel.approved.is_(True))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_pages_for_prompt(
        self,
        prompt_id: _uuid.UUID,
    ) -> Sequence[ContentInventoryPromptModel]:
        """Get all link rows for a tracked prompt (reverse lookup)."""
        stmt = select(ContentInventoryPromptModel).where(
            ContentInventoryPromptModel.tracked_prompt_id == prompt_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def link_exists(
        self,
        inventory_id: _uuid.UUID,
        prompt_id: _uuid.UUID,
    ) -> bool:
        """Check if a link already exists between page and prompt."""
        stmt = select(func.count()).where(
            and_(
                ContentInventoryPromptModel.content_inventory_id == inventory_id,
                ContentInventoryPromptModel.tracked_prompt_id == prompt_id,
            ),
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def count_links_for_prompt(
        self,
        prompt_id: _uuid.UUID,
    ) -> int:
        """Count how many pages are linked to a prompt (for orphan detection)."""
        stmt = select(func.count()).where(
            ContentInventoryPromptModel.tracked_prompt_id == prompt_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    # ── Deletion ──────────────────────────────────────────────────

    async def delete_links_for_page(
        self,
        inventory_id: _uuid.UUID,
        *,
        preserve_user_edited: bool = True,
    ) -> int:
        """Delete link rows for a page (used during re-generation).

        If ``preserve_user_edited`` is True, links marked as user-edited
        are kept.  Returns the number of rows deleted.
        """
        conditions = [
            ContentInventoryPromptModel.content_inventory_id == inventory_id,
        ]
        if preserve_user_edited:
            conditions.append(
                ContentInventoryPromptModel.is_user_edited.is_(False),
            )
        stmt = delete(ContentInventoryPromptModel).where(and_(*conditions))
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def delete_links_by_run(
        self,
        generation_run_id: _uuid.UUID,
    ) -> int:
        """Delete all links from a specific generation run."""
        stmt = delete(ContentInventoryPromptModel).where(
            ContentInventoryPromptModel.generation_run_id == generation_run_id,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    # ── Approval ──────────────────────────────────────────────────

    async def approve_links(
        self,
        link_ids: list[_uuid.UUID],
    ) -> int:
        """Bulk approve pending links.  Returns count of updated rows."""
        if not link_ids:
            return 0
        count = 0
        for link_id in link_ids:
            obj = await self.get_by_id(link_id)
            if obj and not obj.approved:
                obj.approved = True
                count += 1
        if count:
            await self._session.flush()
        return count

    # ── Pending review ────────────────────────────────────────────

    async def get_pending_for_company(
        self,
        company_id: _uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ContentInventoryPromptModel]:
        """Get unapproved links for a company.

        Joins through content_inventory to filter by company_id.
        """
        from core.db.models.content_inventory import ContentInventoryModel

        stmt = (
            select(ContentInventoryPromptModel)
            .join(
                ContentInventoryModel,
                ContentInventoryPromptModel.content_inventory_id == ContentInventoryModel.id,
            )
            .where(
                and_(
                    ContentInventoryModel.company_id == company_id,
                    ContentInventoryPromptModel.approved.is_(False),
                ),
            )
            .order_by(ContentInventoryPromptModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_pending_by_slug(
        self,
        effective_slug: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ContentInventoryPromptModel]:
        """Get unapproved links filtered by company effective_slug."""
        from core.db.models.content_inventory import ContentInventoryModel

        stmt = (
            select(ContentInventoryPromptModel)
            .join(
                ContentInventoryModel,
                ContentInventoryPromptModel.content_inventory_id == ContentInventoryModel.id,
            )
            .where(
                and_(
                    ContentInventoryModel.effective_slug == effective_slug,
                    ContentInventoryPromptModel.approved.is_(False),
                ),
            )
            .order_by(ContentInventoryPromptModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Per-page metric aggregation ───────────────────────────────

    async def get_page_prompt_ids(
        self,
        inventory_id: _uuid.UUID,
    ) -> list[_uuid.UUID]:
        """Get all tracked_prompt_ids linked to a page."""
        stmt = select(ContentInventoryPromptModel.tracked_prompt_id).where(
            and_(
                ContentInventoryPromptModel.content_inventory_id == inventory_id,
                ContentInventoryPromptModel.approved.is_(True),
            ),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_page_metrics(
        self,
        inventory_id: _uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Aggregate mention/citation metrics for all prompts linked to a page.

        Joins: content_inventory_prompts → tracked_prompts → daily_run_responses
        Returns: {total_prompts, active_prompts, mention_rate, citation_rate,
                  total_responses, by_buyer_stage: [...]}
        """
        # Prompt counts
        prompt_ids = await self.get_page_prompt_ids(inventory_id)
        if not prompt_ids:
            return {
                "total_prompts": 0,
                "active_prompts": 0,
                "mention_rate": 0.0,
                "citation_rate": 0.0,
                "total_responses": 0,
                "by_buyer_stage": [],
            }

        # Active count
        active_stmt = select(func.count()).where(
            and_(
                TrackedPromptModel.id.in_(prompt_ids),
                TrackedPromptModel.active.is_(True),
            ),
        )
        active_result = await self._session.execute(active_stmt)
        active_count = active_result.scalar() or 0

        # Response aggregates (mention_rate, citation_rate)
        resp_stmt = select(
            func.count().label("total"),
            func.sum(
                func.cast(DailyRunResponseModel.brand_mentioned, func.integer())  # type: ignore[call-arg]
            ).label("mentioned"),
            func.sum(
                case(
                    (func.jsonb_array_length(DailyRunResponseModel.citations) > 0, 1),
                    else_=0,
                )
            ).label("cited"),
        ).where(
            and_(
                DailyRunResponseModel.prompt_id.in_(prompt_ids),
                DailyRunResponseModel.created_at >= start,
                DailyRunResponseModel.created_at <= end,
            ),
        )
        resp_result = await self._session.execute(resp_stmt)
        row = resp_result.one_or_none()

        total = int(row.total) if row and row.total else 0
        mentioned = int(row.mentioned) if row and row.mentioned else 0
        cited = int(row.cited) if row and row.cited else 0

        mention_rate = mentioned / total if total > 0 else 0.0
        citation_rate = cited / total if total > 0 else 0.0

        # Per-buyer-stage breakdown
        stage_stmt = (
            select(
                ContentInventoryPromptModel.buyer_stage,
                func.count(func.distinct(ContentInventoryPromptModel.tracked_prompt_id)).label("prompt_count"),
            )
            .where(
                and_(
                    ContentInventoryPromptModel.content_inventory_id == inventory_id,
                    ContentInventoryPromptModel.approved.is_(True),
                    ContentInventoryPromptModel.buyer_stage.isnot(None),
                ),
            )
            .group_by(ContentInventoryPromptModel.buyer_stage)
        )
        stage_result = await self._session.execute(stage_stmt)
        by_stage = [
            {"stage": row.buyer_stage, "prompt_count": row.prompt_count}
            for row in stage_result.all()
        ]

        return {
            "total_prompts": len(prompt_ids),
            "active_prompts": active_count,
            "mention_rate": round(mention_rate, 4),
            "citation_rate": round(citation_rate, 4),
            "total_responses": total,
            "by_buyer_stage": by_stage,
        }

    # ── Batch citation metrics (for content performance table) ────

    async def get_citation_metrics_batch(
        self,
        company_id: _uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Batch-aggregate citation counts + per-engine presence for all pages.

        Single query, grouped by content_inventory_id.  Pages without
        linked prompts or responses simply won't appear — the caller
        defaults missing pages to zero.

        Returns: [{inventory_id, total_cited, cited_openai, cited_claude,
                   cited_gemini, cited_perplexity}]
        """
        from core.db.models.content_inventory import ContentInventoryModel

        has_citations = func.jsonb_array_length(DailyRunResponseModel.citations) > 0

        stmt = (
            select(
                ContentInventoryPromptModel.content_inventory_id.label("inventory_id"),
                func.sum(
                    case((has_citations, 1), else_=0)
                ).label("total_cited"),
                func.bool_or(
                    and_(DailyRunResponseModel.engine == "openai", has_citations)
                ).label("cited_openai"),
                func.bool_or(
                    and_(DailyRunResponseModel.engine == "claude", has_citations)
                ).label("cited_claude"),
                func.bool_or(
                    and_(DailyRunResponseModel.engine == "gemini", has_citations)
                ).label("cited_gemini"),
                func.bool_or(
                    and_(DailyRunResponseModel.engine == "perplexity", has_citations)
                ).label("cited_perplexity"),
            )
            .join(
                ContentInventoryModel,
                ContentInventoryPromptModel.content_inventory_id == ContentInventoryModel.id,
            )
            .join(
                TrackedPromptModel,
                ContentInventoryPromptModel.tracked_prompt_id == TrackedPromptModel.id,
            )
            .join(
                DailyRunResponseModel,
                DailyRunResponseModel.prompt_id == TrackedPromptModel.id,
            )
            .where(
                and_(
                    ContentInventoryModel.company_id == company_id,
                    ContentInventoryPromptModel.approved.is_(True),
                    DailyRunResponseModel.created_at >= start,
                    DailyRunResponseModel.created_at <= end,
                ),
            )
            .group_by(ContentInventoryPromptModel.content_inventory_id)
        )

        result = await self._session.execute(stmt)
        return [
            {
                "inventory_id": row.inventory_id,
                "total_cited": int(row.total_cited or 0),
                "cited_openai": bool(row.cited_openai),
                "cited_claude": bool(row.cited_claude),
                "cited_gemini": bool(row.cited_gemini),
                "cited_perplexity": bool(row.cited_perplexity),
            }
            for row in result.all()
        ]

    async def get_citation_timeline(
        self,
        inventory_id: _uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Daily citation timeseries for a single page.

        Groups by day, returns [{day, cited, total_responses}] ordered by date.
        Used in the content-performance detail/drawer endpoint.
        """
        has_citations = func.jsonb_array_length(DailyRunResponseModel.citations) > 0
        day_col = func.date_trunc("day", DailyRunResponseModel.created_at)

        prompt_ids = await self.get_page_prompt_ids(inventory_id)
        if not prompt_ids:
            return []

        stmt = (
            select(
                day_col.label("day"),
                func.sum(
                    case((has_citations, 1), else_=0)
                ).label("cited"),
                func.count().label("total_responses"),
            )
            .where(
                and_(
                    DailyRunResponseModel.prompt_id.in_(prompt_ids),
                    DailyRunResponseModel.created_at >= start,
                    DailyRunResponseModel.created_at <= end,
                ),
            )
            .group_by(day_col)
            .order_by(day_col)
        )

        result = await self._session.execute(stmt)
        return [
            {
                "day": row.day,
                "cited": int(row.cited or 0),
                "total_responses": int(row.total_responses or 0),
            }
            for row in result.all()
        ]

    async def get_pages_without_prompts(
        self,
        company_id: _uuid.UUID,
        *,
        limit: int = 500,
    ) -> list[_uuid.UUID]:
        """Get content inventory page IDs that have NO linked prompts.

        Uses a LEFT JOIN + NULL check (anti-join) to find pages in
        content_inventory that are not present in content_inventory_prompts.
        """
        from core.db.models.content_inventory import ContentInventoryModel

        subq = (
            select(ContentInventoryPromptModel.content_inventory_id)
            .distinct()
            .subquery()
        )

        stmt = (
            select(ContentInventoryModel.id)
            .outerjoin(subq, ContentInventoryModel.id == subq.c.content_inventory_id)
            .where(
                and_(
                    ContentInventoryModel.company_id == company_id,
                    subq.c.content_inventory_id.is_(None),
                ),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Pages with prompt counts (for listing) ────────────────────

    async def get_pages_with_counts(
        self,
        company_id: _uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get content inventory pages that have linked prompts, with counts.

        Returns: [{inventory_id, prompt_count, approved_count}]
        """
        from core.db.models.content_inventory import ContentInventoryModel

        stmt = (
            select(
                ContentInventoryPromptModel.content_inventory_id,
                func.count().label("prompt_count"),
                func.sum(
                    func.cast(ContentInventoryPromptModel.approved, func.integer())  # type: ignore[call-arg]
                ).label("approved_count"),
            )
            .join(
                ContentInventoryModel,
                ContentInventoryPromptModel.content_inventory_id == ContentInventoryModel.id,
            )
            .where(ContentInventoryModel.company_id == company_id)
            .group_by(ContentInventoryPromptModel.content_inventory_id)
            .order_by(func.count().desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "inventory_id": row.content_inventory_id,
                "prompt_count": row.prompt_count,
                "approved_count": int(row.approved_count or 0),
            }
            for row in result.all()
        ]
