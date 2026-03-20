"""Repository for content artifact metadata (stage-level files)."""
from __future__ import annotations

import uuid as _uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ContentArtifactStage
from core.db.models.content import ContentArtifactModel
from core.db.repositories.base import SQLAlchemyRepository


class ContentArtifactRepository(SQLAlchemyRepository[ContentArtifactModel]):
    model_class = ContentArtifactModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_artifact(self, **kwargs: object) -> ContentArtifactModel:
        return await self.create(**kwargs)

    async def get_by_piece_and_stage(
        self,
        piece_id: _uuid.UUID,
        stage: ContentArtifactStage,
    ) -> Optional[ContentArtifactModel]:
        stmt = select(ContentArtifactModel).where(
            ContentArtifactModel.piece_id == piece_id,
            ContentArtifactModel.stage == stage,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_piece(
        self,
        piece_id: _uuid.UUID,
    ) -> Sequence[ContentArtifactModel]:
        stmt = (
            select(ContentArtifactModel)
            .where(ContentArtifactModel.piece_id == piece_id)
            .order_by(ContentArtifactModel.created_at)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_artifact(
        self,
        piece_id: _uuid.UUID,
        stage: ContentArtifactStage,
        storage_key: str,
        content_type: str = "text/markdown",
        size_bytes: int = 0,
        word_count: int | None = None,
        checksum: str | None = None,
    ) -> ContentArtifactModel:
        """Insert or update artifact by (piece_id, stage) unique key."""
        existing = await self.get_by_piece_and_stage(piece_id, stage)
        if existing:
            existing.storage_key = storage_key
            existing.content_type = content_type
            existing.size_bytes = size_bytes
            existing.word_count = word_count
            existing.checksum = checksum
            await self._session.flush()
            return existing
        return await self.create(
            piece_id=piece_id,
            stage=stage,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
            word_count=word_count,
            checksum=checksum,
        )
