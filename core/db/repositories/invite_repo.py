"""Repository for invite operations."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.organization import InviteModel
from core.db.repositories.base import SQLAlchemyRepository


class InviteRepository(SQLAlchemyRepository[InviteModel]):
    model_class = InviteModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_code(self, code: str) -> InviteModel | None:
        """Find a non-redeemed, non-expired invite by code."""
        now = datetime.now(timezone.utc)
        stmt = select(InviteModel).where(
            and_(
                InviteModel.code == code,
                InviteModel.redeemed_by.is_(None),
                # Either no expiration or not yet expired
                (InviteModel.expires_at.is_(None)) | (InviteModel.expires_at > now),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def mark_redeemed(
        self, invite_id: _uuid.UUID | str, user_id: _uuid.UUID | str
    ) -> InviteModel | None:
        """Mark an invite as redeemed by a user."""
        pk = _uuid.UUID(str(invite_id)) if isinstance(invite_id, str) else invite_id
        uid = _uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
        invite = await self.get_by_id(pk)
        if invite is None:
            return None
        invite.redeemed_by = uid
        invite.redeemed_at = datetime.now(timezone.utc)
        await self._session.flush()
        return invite

    async def list_by_company(
        self, company_id: _uuid.UUID | str
    ) -> Sequence[InviteModel]:
        """List all invites for a company (including redeemed)."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(InviteModel)
            .where(InviteModel.company_id == cid)
            .order_by(InviteModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
