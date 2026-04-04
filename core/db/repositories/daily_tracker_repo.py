"""Repositories for the Daily LLM Visibility Tracker module.

Three repositories following the flush-only contract (no ``session.commit()``):

    ``TrackedPromptRepository``     — CRUD + filtering for tracked prompts
    ``DailyRunRepository``          — Run metadata lookups
    ``DailyRunResponseRepository``  — Per-prompt, per-engine response storage

Why flush-only: the DI/service layer owns transaction boundaries.  Repos
only ``add()`` + ``flush()`` so the caller can compose multiple repo
operations into a single atomic commit.
"""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy import Row, and_, case, cast, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.daily_tracker import (
    DailyRunModel,
    DailyRunResponseModel,
    TrackedPromptModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class TrackedPromptRepository(SQLAlchemyRepository[TrackedPromptModel]):
    """Repository for tracked prompt CRUD and filtered listing."""

    model_class = TrackedPromptModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_company(
        self,
        company_id: str,
        *,
        is_active: bool | None = None,
        source: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        search_text: str | None = None,
        parent_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[TrackedPromptModel]:
        """List prompts for a company with optional filters.

        Args:
            company_id: Company identifier.
            is_active: Filter by active/inactive status.
            source: Filter by prompt source (manual, gap_analysis, imported).
            category: Filter by prompt category.
            tags: Filter by tags — prompt must contain ALL specified tags.
            search_text: Case-insensitive substring search on prompt text.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            Sequence of matching TrackedPromptModel rows.
        """
        stmt = select(TrackedPromptModel).where(
            TrackedPromptModel.company_id == company_id
        )

        if is_active is not None:
            stmt = stmt.where(TrackedPromptModel.active == is_active)
        if source is not None:
            stmt = stmt.where(TrackedPromptModel.source == source)
        if category is not None:
            stmt = stmt.where(TrackedPromptModel.category == category)
        if tags:
            # Why: JSONB @> operator checks that the stored array contains
            # all of the specified tags.  Works with GIN indexes.
            for tag in tags:
                stmt = stmt.where(
                    TrackedPromptModel.tags.op("@>")(f'["{tag}"]')
                )
        if parent_only:
            stmt = stmt.where(TrackedPromptModel.parent_prompt_id.is_(None))
        if search_text:
            stmt = stmt.where(
                TrackedPromptModel.text.ilike(f"%{search_text}%")
            )

        stmt = (
            stmt.order_by(TrackedPromptModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_active_prompts(
        self, company_id: str
    ) -> Sequence[TrackedPromptModel]:
        """Get all active prompts for a company (used by daily runs).

        Args:
            company_id: Company identifier.

        Returns:
            All active prompts ordered by creation date.
        """
        stmt = (
            select(TrackedPromptModel)
            .where(
                and_(
                    TrackedPromptModel.company_id == company_id,
                    TrackedPromptModel.active.is_(True),
                )
            )
            .order_by(TrackedPromptModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_company(
        self, company_id: str, *, is_active: bool | None = None
    ) -> int:
        """Count prompts for a company.

        Args:
            company_id: Company identifier.
            is_active: Optional active status filter.

        Returns:
            Count of matching prompts.
        """
        stmt = select(func.count()).select_from(TrackedPromptModel).where(
            TrackedPromptModel.company_id == company_id
        )
        if is_active is not None:
            stmt = stmt.where(TrackedPromptModel.active == is_active)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def bulk_create(
        self, prompts: list[dict[str, object]]
    ) -> list[TrackedPromptModel]:
        """Create multiple prompts in a single flush.

        Args:
            prompts: List of column dicts to pass to TrackedPromptModel().

        Returns:
            List of created ORM instances with IDs assigned.
        """
        instances: list[TrackedPromptModel] = []
        for prompt_data in prompts:
            instance = TrackedPromptModel(**prompt_data)
            self._session.add(instance)
            instances.append(instance)
        await self._session.flush()
        return instances

    async def find_by_text(
        self, company_id: str, text: str
    ) -> TrackedPromptModel | None:
        """Find a prompt with exact text match (for deduplication).

        Args:
            company_id: Company identifier.
            text: Exact prompt text to search for.

        Returns:
            Matching prompt or None.
        """
        stmt = select(TrackedPromptModel).where(
            and_(
                TrackedPromptModel.company_id == company_id,
                TrackedPromptModel.text == text,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def exists_by_text(self, company_id: str, text: str) -> bool:
        """Check if a prompt with this exact text already exists.

        Args:
            company_id: Company identifier.
            text: Prompt text to check.

        Returns:
            True if a prompt with this text exists for the company.
        """
        stmt = (
            select(func.count())
            .select_from(TrackedPromptModel)
            .where(
                and_(
                    TrackedPromptModel.company_id == company_id,
                    TrackedPromptModel.text == text,
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    # -- Fanout query methods --

    async def list_by_parent(
        self,
        parent_prompt_id: _uuid.UUID,
        *,
        active_only: bool = True,
    ) -> Sequence[TrackedPromptModel]:
        """Fetch fanout children of a parent prompt.

        Args:
            parent_prompt_id: The parent prompt UUID.
            active_only: If True, only return active fanouts.

        Returns:
            Sequence of fanout TrackedPromptModel rows.
        """
        stmt = select(TrackedPromptModel).where(
            TrackedPromptModel.parent_prompt_id == parent_prompt_id
        )
        if active_only:
            stmt = stmt.where(TrackedPromptModel.active.is_(True))
        stmt = stmt.order_by(TrackedPromptModel.created_at.asc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_fanouts(
        self, parent_prompt_id: _uuid.UUID
    ) -> int:
        """Count active fanouts for a parent prompt.

        Args:
            parent_prompt_id: The parent prompt UUID.

        Returns:
            Number of active fanout children.
        """
        stmt = (
            select(func.count())
            .select_from(TrackedPromptModel)
            .where(
                and_(
                    TrackedPromptModel.parent_prompt_id == parent_prompt_id,
                    TrackedPromptModel.active.is_(True),
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_unpinned_fanouts(
        self, parent_prompt_id: _uuid.UUID
    ) -> int:
        """Delete non-pinned fanouts for a parent (used by regeneration).

        Args:
            parent_prompt_id: The parent prompt UUID.

        Returns:
            Number of deleted rows.
        """
        from sqlalchemy import delete as sa_delete

        stmt = (
            sa_delete(TrackedPromptModel)
            .where(
                and_(
                    TrackedPromptModel.parent_prompt_id == parent_prompt_id,
                    TrackedPromptModel.pinned.is_(False),
                )
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]


class DailyRunRepository(SQLAlchemyRepository[DailyRunModel]):
    """Repository for daily run metadata."""

    model_class = DailyRunModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_latest_run(
        self, company_id: str
    ) -> DailyRunModel | None:
        """Get the most recent run for a company.

        Args:
            company_id: Company identifier.

        Returns:
            Most recent DailyRunModel or None.
        """
        stmt = (
            select(DailyRunModel)
            .where(DailyRunModel.company_id == company_id)
            .order_by(DailyRunModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_runs(
        self, company_id: str, *, limit: int = 20, offset: int = 0
    ) -> Sequence[DailyRunModel]:
        """List runs ordered by date descending.

        Args:
            company_id: Company identifier.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            Sequence of runs ordered most-recent first.
        """
        stmt = (
            select(DailyRunModel)
            .where(DailyRunModel.company_id == company_id)
            .order_by(DailyRunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class DailyRunResponseRepository(SQLAlchemyRepository[DailyRunResponseModel]):
    """Repository for per-prompt, per-engine daily run responses."""

    model_class = DailyRunResponseModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_responses_by_run(
        self, run_id: _uuid.UUID
    ) -> Sequence[DailyRunResponseModel]:
        """Get all responses for a run.

        Args:
            run_id: The daily run UUID.

        Returns:
            All responses associated with the run.
        """
        stmt = (
            select(DailyRunResponseModel)
            .where(DailyRunResponseModel.run_id == run_id)
            .order_by(DailyRunResponseModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_responses_by_run_and_engine(
        self, run_id: _uuid.UUID, engine: str
    ) -> Sequence[DailyRunResponseModel]:
        """Get responses for a specific engine within a run.

        Args:
            run_id: The daily run UUID.
            engine: Engine name (e.g. "openai", "claude").

        Returns:
            Responses filtered by run and engine.
        """
        stmt = (
            select(DailyRunResponseModel)
            .where(
                and_(
                    DailyRunResponseModel.run_id == run_id,
                    DailyRunResponseModel.engine == engine,
                )
            )
            .order_by(DailyRunResponseModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_mentions_by_run(self, run_id: _uuid.UUID) -> int:
        """Count how many responses have brand_mentioned=True.

        Args:
            run_id: The daily run UUID.

        Returns:
            Number of responses where the brand was mentioned.
        """
        stmt = (
            select(func.count())
            .select_from(DailyRunResponseModel)
            .where(
                and_(
                    DailyRunResponseModel.run_id == run_id,
                    DailyRunResponseModel.brand_mentioned.is_(True),
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def bulk_create(
        self, responses: list[dict[str, object]]
    ) -> list[DailyRunResponseModel]:
        """Store multiple responses in a single flush.

        Args:
            responses: List of column dicts for DailyRunResponseModel.

        Returns:
            List of created ORM instances.
        """
        instances: list[DailyRunResponseModel] = []
        for resp_data in responses:
            instance = DailyRunResponseModel(**resp_data)
            self._session.add(instance)
            instances.append(instance)
        await self._session.flush()
        return instances

    # -- Fanout analytics helpers --

    async def get_observation_counts(
        self, parent_prompt_id: _uuid.UUID
    ) -> dict[_uuid.UUID, int]:
        """Count responses per fanout prompt for a parent.

        Used by the QUERY FANOUTS section to show observation counts.

        Args:
            parent_prompt_id: The parent prompt UUID.

        Returns:
            Dict mapping fanout prompt_id to response count.
        """
        stmt = (
            select(
                DailyRunResponseModel.prompt_id,
                func.count().label("cnt"),
            )
            .where(
                DailyRunResponseModel.parent_prompt_id == parent_prompt_id
            )
            .group_by(DailyRunResponseModel.prompt_id)
        )
        result = await self._session.execute(stmt)
        return {row.prompt_id: row.cnt for row in result}

    async def get_responses_by_company(
        self,
        company_id: str,
        *,
        days: int | None = None,
    ) -> Sequence[DailyRunResponseModel]:
        """Fetch all responses for a company via a single JOIN through daily_runs.

        Replaces the N+1 pattern of listing runs then querying each.

        Args:
            company_id: Company identifier (matches daily_runs.company_id).
            days: Optional time window — only include responses created within
                the last *days* days.  ``None`` returns all.

        Returns:
            Responses ordered by created_at descending.
        """
        stmt = (
            select(DailyRunResponseModel)
            .join(
                DailyRunModel,
                DailyRunResponseModel.run_id == DailyRunModel.id,
            )
            .where(DailyRunModel.company_id == company_id)
        )
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = stmt.where(DailyRunResponseModel.created_at >= cutoff)
        stmt = stmt.order_by(DailyRunResponseModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_responses_for_prompt(
        self,
        prompt_id: _uuid.UUID,
        *,
        days: int = 30,
    ) -> Sequence[DailyRunResponseModel]:
        """Fetch responses scoped to a single prompt **plus** its fanout children.

        Uses the OR condition on ``prompt_id`` / ``parent_prompt_id`` to
        aggregate the full topic scope.  Leverages composite indexes
        ``ix_responses_prompt_created`` and ``ix_responses_parent_created``.

        Args:
            prompt_id: The parent prompt UUID.
            days: Time window (default 30 days).

        Returns:
            Responses ordered by created_at descending.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(DailyRunResponseModel)
            .where(
                and_(
                    or_(
                        DailyRunResponseModel.prompt_id == prompt_id,
                        DailyRunResponseModel.parent_prompt_id == prompt_id,
                    ),
                    DailyRunResponseModel.created_at >= cutoff,
                )
            )
            .order_by(DailyRunResponseModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # -- Enriched prompt list helpers (Phase 1) --

    async def get_prompt_metrics_batch(
        self,
        company_id: str,
        current_start: datetime,
        current_end: datetime,
        prev_start: datetime,
        prev_end: datetime,
    ) -> list[Row]:
        """Return per-parent-prompt aggregated metrics across two time windows.

        Uses ``COALESCE(parent_prompt_id, prompt_id)`` to roll up fanout
        responses into their parent prompt.  Two CTE windows provide
        current-period rates and previous-period rates (for delta computation).

        Args:
            company_id: Company identifier.
            current_start: Start of current period (inclusive).
            current_end: End of current period (exclusive).
            prev_start: Start of comparison period (inclusive).
            prev_end: End of comparison period (exclusive).

        Returns:
            List of Row objects with columns: id, text, category, tags,
            source, active, created_at, mention_rate, citation_rate,
            mention_delta, citation_delta, fanout_count, total_responses.
        """
        # Expression that maps both parent + fanout responses to the root prompt
        root_id = func.coalesce(
            DailyRunResponseModel.parent_prompt_id,
            DailyRunResponseModel.prompt_id,
        ).label("root_id")

        # -- CTE: current period metrics --
        current_base = (
            select(
                root_id,
                func.count().label("total"),
                func.count()
                .filter(DailyRunResponseModel.brand_mentioned.is_(True))
                .label("mentioned"),
                func.count()
                .filter(
                    func.jsonb_array_length(
                        cast(DailyRunResponseModel.citations, JSONB)
                    )
                    > 0
                )
                .label("cited"),
            )
            .join(DailyRunModel, DailyRunResponseModel.run_id == DailyRunModel.id)
            .where(
                and_(
                    DailyRunModel.company_id == company_id,
                    DailyRunResponseModel.created_at >= current_start,
                    DailyRunResponseModel.created_at < current_end,
                )
            )
            .group_by(
                func.coalesce(
                    DailyRunResponseModel.parent_prompt_id,
                    DailyRunResponseModel.prompt_id,
                )
            )
        ).cte("current_metrics")

        # -- CTE: previous period metrics --
        prev_root_id = func.coalesce(
            DailyRunResponseModel.parent_prompt_id,
            DailyRunResponseModel.prompt_id,
        ).label("root_id")

        prev_base = (
            select(
                prev_root_id,
                func.count().label("total"),
                func.count()
                .filter(DailyRunResponseModel.brand_mentioned.is_(True))
                .label("mentioned"),
                func.count()
                .filter(
                    func.jsonb_array_length(
                        cast(DailyRunResponseModel.citations, JSONB)
                    )
                    > 0
                )
                .label("cited"),
            )
            .join(DailyRunModel, DailyRunResponseModel.run_id == DailyRunModel.id)
            .where(
                and_(
                    DailyRunModel.company_id == company_id,
                    DailyRunResponseModel.created_at >= prev_start,
                    DailyRunResponseModel.created_at < prev_end,
                )
            )
            .group_by(
                func.coalesce(
                    DailyRunResponseModel.parent_prompt_id,
                    DailyRunResponseModel.prompt_id,
                )
            )
        ).cte("prev_metrics")

        # -- Subquery: fanout counts --
        fc = (
            select(
                TrackedPromptModel.parent_prompt_id.label("parent_id"),
                func.count().label("cnt"),
            )
            .where(
                and_(
                    TrackedPromptModel.company_id == company_id,
                    TrackedPromptModel.parent_prompt_id.isnot(None),
                    TrackedPromptModel.active.is_(True),
                )
            )
            .group_by(TrackedPromptModel.parent_prompt_id)
        ).subquery("fc")

        # -- Computed rate expressions --
        cm = current_base
        pm = prev_base

        def _safe_rate(mentioned_col, total_col):
            """mentioned / total, defaulting to 0 when total is 0."""
            return case(
                (total_col > 0, cast(mentioned_col, sa.Float) / cast(total_col, sa.Float)),
                else_=literal_column("0.0"),
            )

        cur_mention_rate = _safe_rate(cm.c.mentioned, cm.c.total)
        cur_citation_rate = _safe_rate(cm.c.cited, cm.c.total)
        prev_mention_rate = _safe_rate(pm.c.mentioned, pm.c.total)
        prev_citation_rate = _safe_rate(pm.c.cited, pm.c.total)

        stmt = (
            select(
                TrackedPromptModel.id,
                TrackedPromptModel.text,
                TrackedPromptModel.category,
                TrackedPromptModel.tags,
                TrackedPromptModel.source,
                TrackedPromptModel.active,
                TrackedPromptModel.created_at,
                func.coalesce(cur_mention_rate, 0).label("mention_rate"),
                func.coalesce(cur_citation_rate, 0).label("citation_rate"),
                (func.coalesce(cur_mention_rate, 0) - func.coalesce(prev_mention_rate, 0)).label(
                    "mention_delta"
                ),
                (func.coalesce(cur_citation_rate, 0) - func.coalesce(prev_citation_rate, 0)).label(
                    "citation_delta"
                ),
                func.coalesce(fc.c.cnt, 0).label("fanout_count"),
                func.coalesce(cm.c.total, 0).label("total_responses"),
            )
            .outerjoin(cm, cm.c.root_id == TrackedPromptModel.id)
            .outerjoin(pm, pm.c.root_id == TrackedPromptModel.id)
            .outerjoin(fc, fc.c.parent_id == TrackedPromptModel.id)
            .where(
                and_(
                    TrackedPromptModel.company_id == company_id,
                    TrackedPromptModel.parent_prompt_id.is_(None),
                    TrackedPromptModel.active.is_(True),
                )
            )
            .order_by(TrackedPromptModel.created_at.desc())
        )

        result = await self._session.execute(stmt)
        return list(result.all())

    async def get_daily_volume_batch(
        self,
        company_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[_uuid.UUID, dict[str, int]]:
        """Return daily response counts per parent prompt for sparkline data.

        Args:
            company_id: Company identifier.
            start: Start of period (inclusive).
            end: End of period (exclusive).

        Returns:
            Nested dict: ``{prompt_uuid: {"2026-04-01": 5, "2026-04-02": 3, ...}}``.
            Callers are responsible for zero-filling missing dates.
        """
        root_id = func.coalesce(
            DailyRunResponseModel.parent_prompt_id,
            DailyRunResponseModel.prompt_id,
        ).label("root_id")

        day_col = cast(
            func.date_trunc("day", DailyRunResponseModel.created_at),
            sa.Date,
        ).label("day")

        stmt = (
            select(
                root_id,
                day_col,
                func.count().label("cnt"),
            )
            .join(DailyRunModel, DailyRunResponseModel.run_id == DailyRunModel.id)
            .where(
                and_(
                    DailyRunModel.company_id == company_id,
                    DailyRunResponseModel.created_at >= start,
                    DailyRunResponseModel.created_at < end,
                )
            )
            .group_by(
                func.coalesce(
                    DailyRunResponseModel.parent_prompt_id,
                    DailyRunResponseModel.prompt_id,
                ),
                day_col,
            )
            .order_by(
                func.coalesce(
                    DailyRunResponseModel.parent_prompt_id,
                    DailyRunResponseModel.prompt_id,
                ),
                day_col,
            )
        )

        result = await self._session.execute(stmt)
        volume: dict[_uuid.UUID, dict[str, int]] = {}
        for row in result:
            pid = row.root_id
            day_str = str(row.day)
            volume.setdefault(pid, {})[day_str] = row.cnt
        return volume

    async def cleanup_old_response_text(
        self, retention_days: int = 30
    ) -> int:
        """Clear response_text for responses older than retention_days.

        Sets response_text to empty string (column is NOT NULL).
        Preserves all metric columns for trend analytics.

        Args:
            retention_days: Days to retain response text (default 30).

        Returns:
            Number of rows updated.
        """
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import update as sa_update

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = (
            sa_update(DailyRunResponseModel)
            .where(
                and_(
                    DailyRunResponseModel.created_at < cutoff,
                    DailyRunResponseModel.response_text != "",
                )
            )
            .values(response_text="")
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]
