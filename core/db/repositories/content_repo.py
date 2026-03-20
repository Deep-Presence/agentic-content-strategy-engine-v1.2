"""Repository for content pieces."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ContentPieceStatus
from core.db.models.content import ContentPieceModel
from core.db.repositories.base import SQLAlchemyRepository


class ContentRepository(SQLAlchemyRepository[ContentPieceModel]):
    model_class = ContentPieceModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_piece(self, **kwargs: object) -> ContentPieceModel:
        return await self.create(**kwargs)

    async def update_status(
        self,
        piece_id: _uuid.UUID | str,
        status: ContentPieceStatus,
    ) -> ContentPieceModel | None:
        return await self.update(piece_id, status=status)

    async def list_by_run(
        self,
        run_id: _uuid.UUID | str,
        *,
        status: ContentPieceStatus | None = None,
    ) -> Sequence[ContentPieceModel]:
        pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        stmt = select(ContentPieceModel).where(ContentPieceModel.run_id == pk)
        if status is not None:
            stmt = stmt.where(ContentPieceModel.status == status)
        stmt = stmt.order_by(ContentPieceModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_gap_query(
        self,
        gap_run_id: _uuid.UUID | str,
        query_id: str,
    ) -> ContentPieceModel | None:
        pk = (
            _uuid.UUID(str(gap_run_id))
            if isinstance(gap_run_id, str)
            else gap_run_id
        )
        stmt = select(ContentPieceModel).where(
            ContentPieceModel.gap_run_id == pk,
            ContentPieceModel.query_id == query_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_topic_assignment(
        self,
        topic_assignment_id: _uuid.UUID | str,
    ) -> Sequence[ContentPieceModel]:
        """List all content pieces linked to a specific topic assignment."""
        try:
            pk = (
                _uuid.UUID(str(topic_assignment_id))
                if isinstance(topic_assignment_id, str)
                else topic_assignment_id
            )
        except ValueError:
            return []
        stmt = (
            select(ContentPieceModel)
            .where(ContentPieceModel.topic_assignment_id == pk)
            .order_by(ContentPieceModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Phase 4 additions (DB-ready pipeline) ───────────────────────────

    async def get_by_slug_and_brief_id(
        self,
        effective_slug: str,
        brief_id: str,
    ) -> ContentPieceModel | None:
        """Lookup by immutable external identity (effective_slug, brief_id)."""
        stmt = select(ContentPieceModel).where(
            ContentPieceModel.effective_slug == effective_slug,
            ContentPieceModel.brief_id == brief_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_slug(
        self,
        effective_slug: str,
        *,
        status: ContentPieceStatus | None = None,
    ) -> Sequence[ContentPieceModel]:
        """List all pieces for an effective_slug (including run_id=NULL briefs)."""
        stmt = select(ContentPieceModel).where(
            ContentPieceModel.effective_slug == effective_slug,
        )
        if status is not None:
            stmt = stmt.where(ContentPieceModel.status == status)
        stmt = stmt.order_by(ContentPieceModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Phase 3 additions ─────────────────────────────────────────────

    async def get_piece_detail(
        self,
        run_id: _uuid.UUID | str,
        piece_id: _uuid.UUID | str,
    ) -> ContentPieceModel | None:
        """Get a single content piece by run_id + piece_id."""
        run_pk = _uuid.UUID(str(run_id)) if isinstance(run_id, str) else run_id
        piece_pk = _uuid.UUID(str(piece_id)) if isinstance(piece_id, str) else piece_id
        stmt = select(ContentPieceModel).where(
            ContentPieceModel.run_id == run_pk,
            ContentPieceModel.id == piece_pk,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
