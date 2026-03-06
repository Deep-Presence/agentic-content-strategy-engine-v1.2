"""Repository for product operations."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.organization import ProductModel
from core.db.repositories.base import SQLAlchemyRepository


class ProductRepository(SQLAlchemyRepository[ProductModel]):
    model_class = ProductModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_slugs(
        self, company_id: _uuid.UUID | str, product_slug: str
    ) -> ProductModel | None:
        """Get a product by company ID and product slug."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = select(ProductModel).where(
            and_(
                ProductModel.company_id == cid,
                ProductModel.slug == product_slug,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_company(
        self, company_id: _uuid.UUID | str
    ) -> Sequence[ProductModel]:
        """List all products for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(ProductModel)
            .where(ProductModel.company_id == cid)
            .order_by(ProductModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
