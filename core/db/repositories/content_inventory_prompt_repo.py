"""Repository for the content_inventory_prompts join table.

Provides link CRUD, bidirectional lookups, and per-page metric
aggregation for the Content-to-Prompt pipeline.

Transaction ownership: only ``session.flush()``, never ``session.commit()``.
"""
from __future__ import annotations

import re
import uuid as _uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.content_inventory_prompt import ContentInventoryPromptModel
from core.db.models.daily_tracker import DailyRunResponseModel, TrackedPromptModel
from core.db.repositories.base import SQLAlchemyRepository

_QUERY_TOKEN_RE = re.compile(r"[a-z0-9]+")
_QUERY_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with",
}


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

    async def get_page_root_prompt_ids(
        self,
        inventory_id: _uuid.UUID,
    ) -> list[_uuid.UUID]:
        """Return distinct root prompt IDs for a page, collapsing fanout children.

        A directly linked fanout child maps back to its parent prompt so page-level
        analytics can roll up the full prompt family.
        """
        root_prompt_id = func.coalesce(
            TrackedPromptModel.parent_prompt_id,
            TrackedPromptModel.id,
        ).label("root_prompt_id")

        stmt = (
            select(root_prompt_id)
            .join(
                TrackedPromptModel,
                ContentInventoryPromptModel.tracked_prompt_id == TrackedPromptModel.id,
            )
            .where(
                and_(
                    ContentInventoryPromptModel.content_inventory_id == inventory_id,
                    ContentInventoryPromptModel.approved.is_(True),
                ),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_inventory_ids_for_root_prompt_ids(
        self,
        root_prompt_ids: Sequence[_uuid.UUID],
    ) -> list[_uuid.UUID]:
        """Return page IDs linked to any prompt family rooted at these prompts."""
        root_ids = list(dict.fromkeys(root_prompt_ids))
        if not root_ids:
            return []

        linked_root_id = func.coalesce(
            TrackedPromptModel.parent_prompt_id,
            TrackedPromptModel.id,
        )
        stmt = (
            select(ContentInventoryPromptModel.content_inventory_id)
            .join(
                TrackedPromptModel,
                ContentInventoryPromptModel.tracked_prompt_id == TrackedPromptModel.id,
            )
            .where(
                and_(
                    ContentInventoryPromptModel.approved.is_(True),
                    linked_root_id.in_(root_ids),
                )
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_page_prompt_scope(
        self,
        inventory_id: _uuid.UUID,
    ) -> dict[str, Any]:
        """Return page prompt scope including parent prompts and fanout children."""
        scopes = await self.get_page_prompt_scopes_batch([inventory_id])
        return scopes.get(inventory_id, _empty_page_scope())

    async def get_page_prompt_scopes_batch(
        self,
        inventory_ids: Sequence[_uuid.UUID],
    ) -> dict[_uuid.UUID, dict[str, Any]]:
        """Return prompt scopes for many pages in two DB round-trips."""
        page_ids = list(dict.fromkeys(inventory_ids))
        if not page_ids:
            return {}

        root_prompt_id = func.coalesce(
            TrackedPromptModel.parent_prompt_id,
            TrackedPromptModel.id,
        ).label("root_prompt_id")

        linked_roots_stmt = (
            select(
                ContentInventoryPromptModel.content_inventory_id.label("inventory_id"),
                root_prompt_id,
            )
            .join(
                TrackedPromptModel,
                ContentInventoryPromptModel.tracked_prompt_id == TrackedPromptModel.id,
            )
            .where(
                and_(
                    ContentInventoryPromptModel.content_inventory_id.in_(page_ids),
                    ContentInventoryPromptModel.approved.is_(True),
                ),
            )
            .distinct()
        )
        linked_roots_result = await self._session.execute(linked_roots_stmt)
        linked_root_rows = linked_roots_result.all()

        root_ids_by_inventory: dict[_uuid.UUID, list[_uuid.UUID]] = {
            inventory_id: []
            for inventory_id in page_ids
        }
        all_root_ids: list[_uuid.UUID] = []
        for row in linked_root_rows:
            inventory_id = row.inventory_id
            root_id = row.root_prompt_id
            if root_id not in root_ids_by_inventory[inventory_id]:
                root_ids_by_inventory[inventory_id].append(root_id)
            if root_id not in all_root_ids:
                all_root_ids.append(root_id)

        if not all_root_ids:
            return {
                inventory_id: _empty_page_scope()
                for inventory_id in page_ids
            }

        scope_root_id = func.coalesce(
            TrackedPromptModel.parent_prompt_id,
            TrackedPromptModel.id,
        ).label("root_prompt_id")
        scope_stmt = (
            select(
                TrackedPromptModel.id.label("prompt_id"),
                scope_root_id,
                TrackedPromptModel.text.label("text"),
                TrackedPromptModel.parent_prompt_id.label("parent_prompt_id"),
                TrackedPromptModel.active.label("active"),
            )
            .where(scope_root_id.in_(all_root_ids))
            .order_by(scope_root_id, TrackedPromptModel.parent_prompt_id, TrackedPromptModel.created_at)
        )
        scope_result = await self._session.execute(scope_stmt)
        scope_rows = scope_result.all()

        prompt_rows_by_root: dict[_uuid.UUID, list[Any]] = {}
        for row in scope_rows:
            prompt_rows_by_root.setdefault(row.root_prompt_id, []).append(row)

        scopes: dict[_uuid.UUID, dict[str, Any]] = {}
        for inventory_id in page_ids:
            root_ids = root_ids_by_inventory.get(inventory_id, [])
            rows: list[Any] = []
            for root_id in root_ids:
                rows.extend(prompt_rows_by_root.get(root_id, []))
            scopes[inventory_id] = _build_page_scope(root_ids, rows)
        return scopes

    async def get_page_query_overlap_signals(
        self,
        inventory_id: _uuid.UUID,
        candidate_queries: Sequence[str],
    ) -> dict[str, Any]:
        """Compute deterministic query overlap between an assignment and page scope.

        Uses parent prompts plus fanout children as the query coverage scope.
        """
        scope = await self.get_page_prompt_scope(inventory_id)
        return _compute_query_overlap_signals(scope, candidate_queries)

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
        scope = await self.get_page_prompt_scope(inventory_id)
        root_prompt_ids = scope["root_prompt_ids"]
        if not root_prompt_ids:
            return {
                "total_prompts": 0,
                "active_prompts": 0,
                "mention_rate": 0.0,
                "citation_rate": 0.0,
                "total_responses": 0,
                "by_buyer_stage": [],
            }

        # Active count
        prompt_root_id = func.coalesce(
            TrackedPromptModel.parent_prompt_id,
            TrackedPromptModel.id,
        )
        active_stmt = select(func.count()).where(
            and_(
                prompt_root_id.in_(root_prompt_ids),
                TrackedPromptModel.active.is_(True),
            ),
        )
        active_result = await self._session.execute(active_stmt)
        active_count = active_result.scalar() or 0

        # Response aggregates (mention_rate, citation_rate)
        response_root_id = func.coalesce(
            DailyRunResponseModel.parent_prompt_id,
            DailyRunResponseModel.prompt_id,
        )
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
                response_root_id.in_(root_prompt_ids),
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
            "total_prompts": len(scope["prompt_ids"]),
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
        *,
        inventory_ids: Sequence[_uuid.UUID] | None = None,
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
        response_root_id = func.coalesce(
            DailyRunResponseModel.parent_prompt_id,
            DailyRunResponseModel.prompt_id,
        )
        linked_root_id = func.coalesce(
            TrackedPromptModel.parent_prompt_id,
            TrackedPromptModel.id,
        )

        linked_roots = (
            select(
                ContentInventoryPromptModel.content_inventory_id.label("inventory_id"),
                linked_root_id.label("root_prompt_id"),
            )
            .join(
                ContentInventoryModel,
                ContentInventoryPromptModel.content_inventory_id == ContentInventoryModel.id,
            )
            .join(
                TrackedPromptModel,
                ContentInventoryPromptModel.tracked_prompt_id == TrackedPromptModel.id,
            )
            .where(
                and_(
                    ContentInventoryModel.company_id == company_id,
                    ContentInventoryPromptModel.approved.is_(True),
                ),
            )
        )
        if inventory_ids:
            linked_roots = linked_roots.where(
                ContentInventoryPromptModel.content_inventory_id.in_(list(inventory_ids)),
            )
        linked_roots = linked_roots.distinct().subquery("linked_roots")

        stmt = (
            select(
                linked_roots.c.inventory_id.label("inventory_id"),
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
                DailyRunResponseModel,
                response_root_id == linked_roots.c.root_prompt_id,
            )
            .where(
                and_(
                    DailyRunResponseModel.created_at >= start,
                    DailyRunResponseModel.created_at <= end,
                ),
            )
            .group_by(linked_roots.c.inventory_id)
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
        response_root_id = func.coalesce(
            DailyRunResponseModel.parent_prompt_id,
            DailyRunResponseModel.prompt_id,
        )

        root_prompt_ids = await self.get_page_root_prompt_ids(inventory_id)
        if not root_prompt_ids:
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
                    response_root_id.in_(root_prompt_ids),
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


def _tokenize_query_text(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _QUERY_TOKEN_RE.findall((text or "").lower()):
        if len(token) < 3 or token in _QUERY_STOP_WORDS:
            continue
        tokens.add(token)
    return tokens


def _empty_page_scope() -> dict[str, Any]:
    return {
        "root_prompt_ids": [],
        "prompt_ids": [],
        "fanout_prompt_ids": [],
        "prompt_texts": [],
    }


def _build_page_scope(
    root_prompt_ids: Sequence[_uuid.UUID],
    rows: Sequence[Any],
) -> dict[str, Any]:
    prompt_ids: list[_uuid.UUID] = []
    fanout_prompt_ids: list[_uuid.UUID] = []
    prompt_texts: list[str] = []

    for row in rows:
        prompt_ids.append(row.prompt_id)
        if row.parent_prompt_id is not None:
            fanout_prompt_ids.append(row.prompt_id)
        text = (row.text or "").strip()
        if text:
            prompt_texts.append(text)

    return {
        "root_prompt_ids": list(root_prompt_ids),
        "prompt_ids": prompt_ids,
        "fanout_prompt_ids": fanout_prompt_ids,
        "prompt_texts": prompt_texts,
    }


def _compute_query_overlap_signals(
    scope: dict[str, Any],
    candidate_queries: Sequence[str],
) -> dict[str, Any]:
    queries = [query.strip() for query in candidate_queries if query and query.strip()]
    if not queries or not scope["prompt_texts"]:
        return {
            "query_overlap_score": 0.0,
            "overlapping_query_count": 0,
            "matched_queries": [],
            "matched_prompt_texts": [],
            "root_prompt_count": len(scope["root_prompt_ids"]),
            "prompt_scope_count": len(scope["prompt_ids"]),
        }

    prompt_token_map = {
        prompt_text: _tokenize_query_text(prompt_text)
        for prompt_text in scope["prompt_texts"]
    }
    matched_queries: list[str] = []
    matched_prompt_texts: list[str] = []
    per_query_scores: list[float] = []

    for query in queries:
        query_tokens = _tokenize_query_text(query)
        if not query_tokens:
            per_query_scores.append(0.0)
            continue

        best_score = 0.0
        best_prompt = ""
        for prompt_text, prompt_tokens in prompt_token_map.items():
            score = _query_overlap_ratio(query_tokens, prompt_tokens)
            if score > best_score:
                best_score = score
                best_prompt = prompt_text
        per_query_scores.append(best_score)
        if best_score >= 0.5:
            matched_queries.append(query)
            if best_prompt and best_prompt not in matched_prompt_texts:
                matched_prompt_texts.append(best_prompt)

    overlap_score = sum(per_query_scores) / len(per_query_scores) if per_query_scores else 0.0
    return {
        "query_overlap_score": round(overlap_score, 4),
        "overlapping_query_count": len(matched_queries),
        "matched_queries": matched_queries,
        "matched_prompt_texts": matched_prompt_texts,
        "root_prompt_count": len(scope["root_prompt_ids"]),
        "prompt_scope_count": len(scope["prompt_ids"]),
    }


def _query_overlap_ratio(
    query_tokens: set[str],
    prompt_tokens: set[str],
) -> float:
    if not query_tokens or not prompt_tokens:
        return 0.0
    return len(query_tokens & prompt_tokens) / len(query_tokens)
