"""Repository for tracking snapshots and content mention tracking."""
from __future__ import annotations

import uuid as _uuid
from datetime import date, timedelta, timezone, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models.tracking import ContentMentionTrackingModel, TrackingSnapshotModel
from core.db.repositories.base import SQLAlchemyRepository


class TrackingRepository(SQLAlchemyRepository[TrackingSnapshotModel]):
    model_class = TrackingSnapshotModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_snapshot(
        self, **kwargs: object
    ) -> TrackingSnapshotModel:
        return await self.create(**kwargs)

    async def get_snapshot(
        self,
        company_id: _uuid.UUID,
        snapshot_date: date,
        product_id: _uuid.UUID | None = None,
    ) -> TrackingSnapshotModel | None:
        stmt = select(TrackingSnapshotModel).where(
            TrackingSnapshotModel.company_id == company_id,
            TrackingSnapshotModel.snapshot_date == snapshot_date,
        )
        if product_id is not None:
            stmt = stmt.where(TrackingSnapshotModel.product_id == product_id)
        else:
            stmt = stmt.where(TrackingSnapshotModel.product_id.is_(None))

        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def add_mention(
        self,
        snapshot_id: _uuid.UUID | str,
        **kwargs: object,
    ) -> ContentMentionTrackingModel:
        pk = (
            _uuid.UUID(str(snapshot_id))
            if isinstance(snapshot_id, str)
            else snapshot_id
        )
        mention = ContentMentionTrackingModel(snapshot_id=pk, **kwargs)
        self._session.add(mention)
        await self._session.flush()
        return mention

    async def get_trend(
        self,
        company_id: _uuid.UUID,
        *,
        days: int = 30,
        product_id: _uuid.UUID | None = None,
    ) -> Sequence[TrackingSnapshotModel]:
        """Return snapshots for the last *days* days, ordered by date ascending."""
        cutoff_date = date.today() - timedelta(days=days)
        stmt = select(TrackingSnapshotModel).where(
            TrackingSnapshotModel.company_id == company_id,
            TrackingSnapshotModel.snapshot_date >= cutoff_date,
        )
        if product_id is not None:
            stmt = stmt.where(TrackingSnapshotModel.product_id == product_id)
        else:
            stmt = stmt.where(TrackingSnapshotModel.product_id.is_(None))

        stmt = stmt.order_by(TrackingSnapshotModel.snapshot_date.asc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
