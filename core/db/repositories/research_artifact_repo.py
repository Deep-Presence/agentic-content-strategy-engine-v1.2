"""Repository for research artifact CRUD operations."""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ArtifactStatus, ArtifactType
from core.db.models.content import ResearchArtifactModel
from core.db.repositories.base import SQLAlchemyRepository


class ResearchArtifactRepository(SQLAlchemyRepository[ResearchArtifactModel]):
    model_class = ResearchArtifactModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_slug_and_type(
        self,
        effective_slug: str,
        artifact_type: ArtifactType,
        *,
        version: int | None = None,
    ) -> ResearchArtifactModel | None:
        """Get artifact by slug, type, and optionally version."""
        stmt = select(ResearchArtifactModel).where(
            ResearchArtifactModel.effective_slug == effective_slug,
            ResearchArtifactModel.artifact_type == artifact_type,
        )
        if version is not None:
            stmt = stmt.where(ResearchArtifactModel.version == version)
        else:
            stmt = stmt.order_by(ResearchArtifactModel.version.desc())
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_latest_by_slug_and_type(
        self,
        effective_slug: str,
        artifact_type: ArtifactType,
    ) -> ResearchArtifactModel | None:
        """Get the highest-version artifact for slug + type."""
        return await self.get_by_slug_and_type(effective_slug, artifact_type)

    async def list_by_slug(
        self,
        effective_slug: str,
        *,
        artifact_type: ArtifactType | None = None,
    ) -> Sequence[ResearchArtifactModel]:
        """List all artifacts for an effective slug, optionally filtered by type."""
        stmt = select(ResearchArtifactModel).where(
            ResearchArtifactModel.effective_slug == effective_slug,
        )
        if artifact_type is not None:
            stmt = stmt.where(ResearchArtifactModel.artifact_type == artifact_type)
        stmt = stmt.order_by(
            ResearchArtifactModel.artifact_type,
            ResearchArtifactModel.version.desc(),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_company(
        self,
        company_id: _uuid.UUID,
        *,
        artifact_type: ArtifactType | None = None,
        limit: int = 100,
    ) -> Sequence[ResearchArtifactModel]:
        """List artifacts for a company, optionally filtered by type."""
        stmt = select(ResearchArtifactModel).where(
            ResearchArtifactModel.company_id == company_id,
        )
        if artifact_type is not None:
            stmt = stmt.where(ResearchArtifactModel.artifact_type == artifact_type)
        stmt = stmt.order_by(
            ResearchArtifactModel.created_at.desc(),
        ).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_artifact(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        artifact_type: ArtifactType,
        version: int,
        storage_key: str,
        *,
        product_id: _uuid.UUID | None = None,
        title: str | None = None,
        status: ArtifactStatus = ArtifactStatus.draft,
        content_hash: str | None = None,
        metadata_json: dict | None = None,
    ) -> ResearchArtifactModel:
        """Insert or update an artifact keyed by (company, slug, type, title, version).

        If a matching row exists, updates status/hash/metadata.
        Otherwise inserts a new row.
        """
        stmt = select(ResearchArtifactModel).where(
            ResearchArtifactModel.company_id == company_id,
            ResearchArtifactModel.effective_slug == effective_slug,
            ResearchArtifactModel.artifact_type == artifact_type,
            ResearchArtifactModel.version == version,
        )
        if title is not None:
            stmt = stmt.where(ResearchArtifactModel.title == title)
        else:
            stmt = stmt.where(ResearchArtifactModel.title.is_(None))

        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.status = status
            existing.storage_key = storage_key
            if content_hash is not None:
                existing.content_hash = content_hash
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            await self._session.flush()
            return existing

        artifact = ResearchArtifactModel(
            company_id=company_id,
            product_id=product_id,
            effective_slug=effective_slug,
            artifact_type=artifact_type,
            title=title,
            status=status,
            version=version,
            storage_key=storage_key,
            content_hash=content_hash,
            metadata_json=metadata_json,
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def delete_by_slug_and_type(
        self,
        effective_slug: str,
        artifact_type: ArtifactType,
    ) -> int:
        """Delete all artifacts matching slug + type. Returns deleted count."""
        stmt = (
            delete(ResearchArtifactModel)
            .where(
                ResearchArtifactModel.effective_slug == effective_slug,
                ResearchArtifactModel.artifact_type == artifact_type,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
