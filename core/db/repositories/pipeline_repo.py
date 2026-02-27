"""Repository for pipeline runs and stage logs."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import PipelineStatus, PipelineType
from core.db.models.pipelines import PipelineRunModel, PipelineStageLogModel
from core.db.repositories.base import SQLAlchemyRepository


class PipelineRepository(SQLAlchemyRepository[PipelineRunModel]):
    model_class = PipelineRunModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_run(self, **kwargs: object) -> PipelineRunModel:
        return await self.create(**kwargs)

    async def update_status(
        self,
        run_id: _uuid.UUID | str,
        status: PipelineStatus,
        error_message: str | None = None,
    ) -> PipelineRunModel | None:
        update_kwargs: dict[str, object] = {"status": status}
        if error_message is not None:
            update_kwargs["error_message"] = error_message
        return await self.update(run_id, **update_kwargs)

    async def list_by_company(
        self,
        company_id: _uuid.UUID,
        *,
        pipeline_type: PipelineType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[PipelineRunModel]:
        stmt = select(PipelineRunModel).where(
            PipelineRunModel.company_id == company_id
        )
        if pipeline_type is not None:
            stmt = stmt.where(PipelineRunModel.pipeline_type == pipeline_type)
        stmt = (
            stmt.order_by(PipelineRunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add_stage_log(
        self, run_id: _uuid.UUID | str, **kwargs: object
    ) -> PipelineStageLogModel:
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stage_log = PipelineStageLogModel(run_id=pk, **kwargs)
        self._session.add(stage_log)
        await self._session.flush()
        return stage_log

    async def get_active_runs(
        self, company_id: _uuid.UUID | None = None
    ) -> Sequence[PipelineRunModel]:
        active_statuses = (PipelineStatus.pending, PipelineStatus.running)
        stmt = select(PipelineRunModel).where(
            PipelineRunModel.status.in_(active_statuses)
        )
        if company_id is not None:
            stmt = stmt.where(PipelineRunModel.company_id == company_id)
        stmt = stmt.order_by(PipelineRunModel.created_at.asc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
