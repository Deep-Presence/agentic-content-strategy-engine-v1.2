"""Repository for gap analysis domain models (query gaps, cluster specs)."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import GapClassification
from core.db.models.gap_analysis import ClusterSpecModel, QueryGapModel
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
