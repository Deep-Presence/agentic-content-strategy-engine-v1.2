"""Repository for company pipeline defaults."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.organization import PipelineDefaultsModel
from core.db.repositories.base import SQLAlchemyRepository


class PipelineDefaultsRepository(SQLAlchemyRepository[PipelineDefaultsModel]):
    model_class = PipelineDefaultsModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_company(
        self, company_id: _uuid.UUID | str
    ) -> PipelineDefaultsModel | None:
        """Get pipeline defaults for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = select(PipelineDefaultsModel).where(
            PipelineDefaultsModel.company_id == cid
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert(
        self, company_id: _uuid.UUID | str, defaults_json: dict
    ) -> PipelineDefaultsModel:
        """Create or update pipeline defaults for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        existing = await self.get_by_company(cid)
        if existing:
            existing.defaults_json = defaults_json
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.flush()
            return existing
        return await self.create(
            company_id=cid,
            defaults_json=defaults_json,
            updated_at=datetime.now(timezone.utc),
        )
