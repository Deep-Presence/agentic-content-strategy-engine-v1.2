"""Repository for workspace tenant operations."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.enums import MembershipStatus, WorkspaceRole
from core.db.models.workspace import WorkspaceMembershipModel, WorkspaceModel
from core.db.repositories.base import SQLAlchemyRepository


class WorkspaceRepository(SQLAlchemyRepository[WorkspaceModel]):
    model_class = WorkspaceModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_slug(self, slug: str) -> WorkspaceModel | None:
        stmt = select(WorkspaceModel).where(WorkspaceModel.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_company_id(self, company_id: _uuid.UUID | str) -> WorkspaceModel | None:
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = select(WorkspaceModel).where(WorkspaceModel.company_id == cid)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(func.count()).select_from(WorkspaceModel).where(
            WorkspaceModel.slug == slug
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def list_for_user(
        self,
        user_id: _uuid.UUID | str,
        *,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkspaceModel]:
        uid = _uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
        stmt = (
            select(WorkspaceModel)
            .join(
                WorkspaceMembershipModel,
                WorkspaceMembershipModel.workspace_id == WorkspaceModel.id,
            )
            .where(
                WorkspaceMembershipModel.user_id == uid,
                WorkspaceMembershipModel.status == MembershipStatus.active,
            )
            .options(selectinload(WorkspaceModel.memberships))
            .order_by(WorkspaceModel.name.asc())
            .limit(limit)
            .offset(offset)
        )
        if not include_archived:
            stmt = stmt.where(WorkspaceModel.is_archived.is_(False))
        result = await self._session.execute(stmt)
        return result.scalars().unique().all()


class WorkspaceMembershipRepository(SQLAlchemyRepository[WorkspaceMembershipModel]):
    model_class = WorkspaceMembershipModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_membership(
        self,
        workspace_id: _uuid.UUID | str,
        user_id: _uuid.UUID | str,
    ) -> WorkspaceMembershipModel | None:
        wid = _uuid.UUID(str(workspace_id)) if isinstance(workspace_id, str) else workspace_id
        uid = _uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
        stmt = select(WorkspaceMembershipModel).where(
            WorkspaceMembershipModel.workspace_id == wid,
            WorkspaceMembershipModel.user_id == uid,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_workspace(
        self,
        workspace_id: _uuid.UUID | str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WorkspaceMembershipModel]:
        wid = _uuid.UUID(str(workspace_id)) if isinstance(workspace_id, str) else workspace_id
        stmt = (
            select(WorkspaceMembershipModel)
            .where(WorkspaceMembershipModel.workspace_id == wid)
            .order_by(WorkspaceMembershipModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create_membership(
        self,
        *,
        workspace_id: _uuid.UUID,
        user_id: _uuid.UUID,
        role: WorkspaceRole,
        status: MembershipStatus = MembershipStatus.active,
    ) -> WorkspaceMembershipModel:
        return await self.create(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status=status,
        )
