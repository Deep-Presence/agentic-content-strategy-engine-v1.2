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

from sqlalchemy import and_, func, select
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
