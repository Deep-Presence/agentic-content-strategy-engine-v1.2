"""Repository for gap analysis domain models (query gaps, cluster specs)."""
from __future__ import annotations

import uuid as _uuid
from typing import Any, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import GapClassification

# Severity rank: higher = worse gap
_CLASSIFICATION_RANK = {
    GapClassification.significant_gap: 4,
    GapClassification.gap_to_close: 3,
    GapClassification.roughly_equal: 2,
    GapClassification.company_wins: 1,
    GapClassification.no_data: 0,
}
from core.db.models.gap_analysis import (
    ClusterSpecModel,
    QueryGapModel,
    SpaResultModel,
    CentroidResultModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class GapAnalysisRepository(SQLAlchemyRepository[QueryGapModel]):
    model_class = QueryGapModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def bulk_insert_query_gaps(
        self, gaps: list[dict[str, object]]
    ) -> Sequence[QueryGapModel]:
        """Insert multiple query gaps in a single flush.

        Each dict in *gaps* is unpacked as keyword arguments to
        ``QueryGapModel()``.
        """
        instances: list[QueryGapModel] = []
        for gap_data in gaps:
            instance = QueryGapModel(**gap_data)
            self._session.add(instance)
            instances.append(instance)
        await self._session.flush()
        return instances

    async def get_gaps_by_run(
        self,
        run_id: _uuid.UUID | str,
        *,
        classification: GapClassification | None = None,
        cluster_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[QueryGapModel]:
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = select(QueryGapModel).where(QueryGapModel.run_id == pk)

        if classification is not None:
            stmt = stmt.where(QueryGapModel.classification == classification)
        if cluster_name is not None:
            stmt = stmt.where(QueryGapModel.cluster_name == cluster_name)

        stmt = (
            stmt.order_by(QueryGapModel.gap.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_gap(
        self, gap_id: _uuid.UUID | str, **kwargs: object
    ) -> QueryGapModel | None:
        return await self.update(gap_id, **kwargs)

    async def get_cluster_specs(
        self, run_id: _uuid.UUID | str
    ) -> Sequence[ClusterSpecModel]:
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(ClusterSpecModel)
            .where(ClusterSpecModel.run_id == pk)
            .order_by(ClusterSpecModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Phase 3 additions ─────────────────────────────────────────────

    async def count_gaps_by_run(
        self, run_id: _uuid.UUID | str,
    ) -> int:
        """Total gap count for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = select(func.count()).select_from(QueryGapModel).where(
            QueryGapModel.run_id == pk,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_classification_counts(
        self, run_id: _uuid.UUID | str,
    ) -> dict[str, int]:
        """Count gaps per classification for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(
                QueryGapModel.classification,
                func.count().label("cnt"),
            )
            .where(QueryGapModel.run_id == pk)
            .group_by(QueryGapModel.classification)
        )
        result = await self._session.execute(stmt)
        return {
            str(row.classification.value): int(row.cnt)
            for row in result.all()
        }

    async def get_spa_results(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[SpaResultModel]:
        """Get SPA results for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(SpaResultModel)
            .where(SpaResultModel.run_id == pk)
            .order_by(SpaResultModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_centroid_results(
        self, run_id: _uuid.UUID | str,
    ) -> Sequence[CentroidResultModel]:
        """Get centroid distances for a run."""
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = (
            select(CentroidResultModel)
            .where(CentroidResultModel.run_id == pk)
            .order_by(CentroidResultModel.cluster_name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_gaps_paginated(
        self,
        run_id: _uuid.UUID | str,
        *,
        cluster: str | None = None,
        classification: str | None = None,
        search: str | None = None,
        sort_by: str = "gap",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 15,
    ) -> dict[str, Any]:
        """Enhanced paginated query with search, filter, sort.

        Returns {items: [...], total: int, page: int, page_size: int, total_pages: int}.
        """
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        base = select(QueryGapModel).where(QueryGapModel.run_id == pk)

        if cluster:
            base = base.where(
                (QueryGapModel.cluster_name == cluster)
                | (QueryGapModel.cluster_id == cluster)
            )
        if classification:
            try:
                cls = GapClassification(classification)
                base = base.where(QueryGapModel.classification == cls)
            except ValueError:
                pass  # invalid classification — skip filter
        if search:
            base = base.where(QueryGapModel.query_text.ilike(f"%{search}%"))

        # Count total (before pagination)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))  # Clamp to valid range

        # Sort — severity-ranked for classification, column-based otherwise
        if sort_by == "classification":
            severity_expr = case(
                *[
                    (QueryGapModel.classification == cls, rank)
                    for cls, rank in _CLASSIFICATION_RANK.items()
                ],
                else_=0,
            )
            order = severity_expr.desc() if sort_dir == "desc" else severity_expr.asc()
        else:
            sort_col = getattr(QueryGapModel, sort_by, QueryGapModel.gap)
            order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
        base = base.order_by(order)

        # Paginate
        offset = (page - 1) * page_size
        base = base.offset(offset).limit(page_size)

        result = await self._session.execute(base)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
