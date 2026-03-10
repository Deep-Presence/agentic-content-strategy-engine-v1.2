"""Repository for company operations."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.organization import CompanyModel
from core.db.repositories.base import SQLAlchemyRepository


class CompanyRepository(SQLAlchemyRepository[CompanyModel]):
    model_class = CompanyModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_slug(self, slug: str) -> CompanyModel | None:
        stmt = select(CompanyModel).where(CompanyModel.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_domain(self, domain: str) -> CompanyModel | None:
        stmt = select(CompanyModel).where(CompanyModel.domain == domain)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def slug_exists(self, slug: str) -> bool:
        """Fast COUNT check for slug collision avoidance."""
        stmt = select(func.count()).select_from(CompanyModel).where(
            CompanyModel.slug == slug
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def list_active(
        self, *, limit: int = 100, offset: int = 0
    ) -> Sequence[CompanyModel]:
        stmt = (
            select(CompanyModel)
            .where(CompanyModel.is_archived.is_(False))
            .order_by(CompanyModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
