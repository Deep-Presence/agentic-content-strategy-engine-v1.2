"""Repository for per-platform citation summaries.

Used by ``DbGapDataService`` to compute platform breakdowns and
per-platform URL sets (for Jaccard agreement computed in Python).
"""
from __future__ import annotations

import uuid as _uuid
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.gap_analysis import RunCitationModel


class PlatformRepository:
    """Platform-level aggregation queries on run_citations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_platform_summaries(
        self, run_id: _uuid.UUID,
    ) -> Sequence[dict[str, Any]]:
        """Per-engine citation counts and unique URL counts.

        Returns list of dicts: {engine, citation_count, unique_urls}.
        """
        rc = RunCitationModel
        stmt = (
            select(
                rc.engine,
                func.count().label("citation_count"),
                func.count(func.distinct(rc.url)).label("unique_urls"),
            )
            .where(rc.run_id == run_id)
            .group_by(rc.engine)
            .order_by(rc.engine)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "engine": str(row.engine.value) if hasattr(row.engine, "value") else str(row.engine),
                "citation_count": int(row.citation_count),
                "unique_urls": int(row.unique_urls),
            }
            for row in result.all()
        ]

    async def get_platform_url_sets(
        self, run_id: _uuid.UUID,
    ) -> dict[str, set[str]]:
        """Per-engine sets of cited URLs for Jaccard agreement computation.

        The Jaccard matrix is computed in Python, not SQL (per plan W4).
        Returns {engine_name: {url1, url2, ...}}.
        """
        rc = RunCitationModel
        stmt = (
            select(rc.engine, rc.url)
            .where(rc.run_id == run_id)
            .distinct()
        )
        result = await self._session.execute(stmt)

        url_sets: dict[str, set[str]] = {}
        for row in result.all():
            engine_name = str(row.engine.value) if hasattr(row.engine, "value") else str(row.engine)
            url_sets.setdefault(engine_name, set()).add(row.url)
        return url_sets

    async def get_citation_exclusivity(
        self, run_id: _uuid.UUID,
    ) -> dict[str, int]:
        """Count URLs cited by only one platform (exclusive citations).

        Returns {engine_name: exclusive_count}.
        """
        rc = RunCitationModel

        # Subquery: count how many engines cite each URL
        engine_count_sq = (
            select(
                rc.url,
                func.count(func.distinct(rc.engine)).label("engine_count"),
            )
            .where(rc.run_id == run_id)
            .group_by(rc.url)
            .subquery()
        )

        # URLs exclusive to one engine
        exclusive_urls = (
            select(engine_count_sq.c.url)
            .where(engine_count_sq.c.engine_count == 1)
            .subquery()
        )

        stmt = (
            select(
                rc.engine,
                func.count(func.distinct(rc.url)).label("exclusive_count"),
            )
            .where(rc.run_id == run_id, rc.url.in_(select(exclusive_urls.c.url)))
            .group_by(rc.engine)
        )
        result = await self._session.execute(stmt)
        return {
            str(row.engine.value) if hasattr(row.engine, "value") else str(row.engine): int(row.exclusive_count)
            for row in result.all()
        }
