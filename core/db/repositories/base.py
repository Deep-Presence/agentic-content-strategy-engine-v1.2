"""Generic base repository with common CRUD operations."""
from __future__ import annotations

import uuid as _uuid
from typing import Generic, Sequence, Type, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class SQLAlchemyRepository(Generic[ModelT]):
    """Base repository providing common CRUD operations.

    Transaction ownership contract:
    - Repos call ``session.add()`` + ``session.flush()`` only.
    - ``session.commit()`` is NEVER called here — commit happens in the DI layer.
    """

    model_class: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: _uuid.UUID | str) -> ModelT | None:
        pk = _uuid.UUID(str(id)) if isinstance(id, str) else id
        return await self._session.get(self.model_class, pk)

    async def create(self, **kwargs: object) -> ModelT:
        instance = self.model_class(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def update(self, id: _uuid.UUID | str, **kwargs: object) -> ModelT | None:
        instance = await self.get_by_id(id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._session.flush()
        return instance

    async def delete(self, id: _uuid.UUID | str) -> bool:
        pk = _uuid.UUID(str(id)) if isinstance(id, str) else id
        stmt = delete(self.model_class).where(self.model_class.id == pk)  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def list_all(
        self, *, limit: int = 100, offset: int = 0
    ) -> Sequence[ModelT]:
        stmt = select(self.model_class).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()
