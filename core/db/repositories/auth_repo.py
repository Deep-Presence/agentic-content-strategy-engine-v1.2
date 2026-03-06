"""Repository for user / auth operations."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import UserRole
from core.db.models.organization import UserModel
from core.db.repositories.base import SQLAlchemyRepository


class AuthRepository(SQLAlchemyRepository[UserModel]):
    model_class = UserModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_email(self, email: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_company(
        self,
        company_id: _uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[UserModel]:
        stmt = (
            select(UserModel)
            .where(UserModel.company_id == company_id)
            .order_by(UserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_superusers(self, company_id: _uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(
                UserModel.company_id == company_id,
                UserModel.role == UserRole.superuser,
                UserModel.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def deactivate(self, user_id: _uuid.UUID | str) -> UserModel | None:
        pk = _uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
        stmt = (
            update(UserModel)
            .where(UserModel.id == pk)
            .values(is_active=False)
            .returning(UserModel)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalars().first()
