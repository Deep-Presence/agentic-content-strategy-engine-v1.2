"""DB repositories for Voice Style Guide ORM operations.

Follows the project's SQLAlchemyRepository pattern:
- Repos call session.add() + session.flush() only
- session.commit() is NEVER called here — commit happens in the DI layer

Three table-specific repositories:
- VSGRunRepository    — vsg_runs
- VSGAuthorRepository — vsg_authors
- VSGGuideRepository  — vsg_guides
"""
from __future__ import annotations

import uuid as _uuid
from typing import Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ResearchRunStatus
from core.db.models.voice_style_guide import (
    VSGAuthorModel,
    VSGGuideModel,
    VSGRunModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class VSGRunRepository(SQLAlchemyRepository[VSGRunModel]):
    """Repository for vsg_runs table."""

    model_class = VSGRunModel

    async def get_by_effective_slug(
        self, effective_slug: str
    ) -> Optional[VSGRunModel]:
        """Find the latest VSG run by effective_slug."""
        stmt = (
            select(VSGRunModel)
            .where(VSGRunModel.effective_slug == effective_slug)
            .order_by(VSGRunModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_company(
        self, company_id: _uuid.UUID | str
    ) -> Sequence[VSGRunModel]:
        """List VSG runs for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(VSGRunModel)
            .where(VSGRunModel.company_id == cid)
            .order_by(VSGRunModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self, run_id: _uuid.UUID | str, status: ResearchRunStatus
    ) -> Optional[VSGRunModel]:
        """Update the status of a VSG run."""
        return await self.update(run_id, status=status)

    async def upsert_run(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        *,
        pipeline_run_id: _uuid.UUID | None = None,
        product_id: _uuid.UUID | None = None,
        ap_manifest_version: str | None = None,
        status: ResearchRunStatus = ResearchRunStatus.draft,
    ) -> VSGRunModel:
        """Find-or-create by (company_id, effective_slug). Updates if exists."""
        stmt = (
            select(VSGRunModel)
            .where(
                VSGRunModel.company_id == company_id,
                VSGRunModel.effective_slug == effective_slug,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.status = status
            if pipeline_run_id is not None:
                existing.pipeline_run_id = pipeline_run_id
            if product_id is not None:
                existing.product_id = product_id
            if ap_manifest_version is not None:
                existing.ap_manifest_version = ap_manifest_version
            await self._session.flush()
            return existing

        run = VSGRunModel(
            company_id=company_id,
            effective_slug=effective_slug,
            pipeline_run_id=pipeline_run_id,
            product_id=product_id,
            ap_manifest_version=ap_manifest_version,
            status=status,
        )
        self._session.add(run)
        await self._session.flush()
        return run


class VSGAuthorRepository(SQLAlchemyRepository[VSGAuthorModel]):
    """Repository for vsg_authors table."""

    model_class = VSGAuthorModel

    async def get_by_run_and_author_id(
        self,
        vsg_run_id: _uuid.UUID | str,
        author_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[VSGAuthorModel]:
        """Get an author by run + author_id, optionally by version."""
        rid = _uuid.UUID(str(vsg_run_id)) if isinstance(vsg_run_id, str) else vsg_run_id
        stmt = select(VSGAuthorModel).where(
            VSGAuthorModel.vsg_run_id == rid,
            VSGAuthorModel.author_id == author_id,
        )
        if version is not None:
            stmt = stmt.where(VSGAuthorModel.version == version)
        else:
            stmt = stmt.order_by(VSGAuthorModel.version.desc())
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_run(
        self, vsg_run_id: _uuid.UUID | str
    ) -> Sequence[VSGAuthorModel]:
        """List all authors for a VSG run."""
        rid = _uuid.UUID(str(vsg_run_id)) if isinstance(vsg_run_id, str) else vsg_run_id
        stmt = (
            select(VSGAuthorModel)
            .where(VSGAuthorModel.vsg_run_id == rid)
            .order_by(VSGAuthorModel.author_id, VSGAuthorModel.version.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_author(
        self,
        vsg_run_id: _uuid.UUID,
        author_id: str,
        name: str,
        version: int,
        storage_key: str,
        *,
        status: str | None = None,
        content_hash: str | None = None,
        word_count: int = 0,
        metadata_json: dict | None = None,
    ) -> VSGAuthorModel:
        """Find-or-create by (vsg_run_id, author_id, version). Updates if exists."""
        stmt = (
            select(VSGAuthorModel)
            .where(
                VSGAuthorModel.vsg_run_id == vsg_run_id,
                VSGAuthorModel.author_id == author_id,
                VSGAuthorModel.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.name = name
            existing.storage_key = storage_key
            if status is not None:
                existing.status = status
            if content_hash is not None:
                existing.content_hash = content_hash
            existing.word_count = word_count
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            await self._session.flush()
            return existing

        author = VSGAuthorModel(
            vsg_run_id=vsg_run_id,
            author_id=author_id,
            name=name,
            version=version,
            storage_key=storage_key,
            status=status,
            content_hash=content_hash,
            word_count=word_count,
            metadata_json=metadata_json,
        )
        self._session.add(author)
        await self._session.flush()
        return author


class VSGGuideRepository(SQLAlchemyRepository[VSGGuideModel]):
    """Repository for vsg_guides table."""

    model_class = VSGGuideModel

    async def get_by_run(
        self,
        vsg_run_id: _uuid.UUID | str,
        *,
        version: Optional[int] = None,
    ) -> Optional[VSGGuideModel]:
        """Get guide by run, optionally by version (latest if omitted)."""
        rid = _uuid.UUID(str(vsg_run_id)) if isinstance(vsg_run_id, str) else vsg_run_id
        stmt = select(VSGGuideModel).where(
            VSGGuideModel.vsg_run_id == rid,
        )
        if version is not None:
            stmt = stmt.where(VSGGuideModel.version == version)
        else:
            stmt = stmt.order_by(VSGGuideModel.version.desc())
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert_guide(
        self,
        vsg_run_id: _uuid.UUID,
        version: int,
        storage_key: str,
        *,
        content_hash: str | None = None,
        word_count: int = 0,
        source_authors: list | None = None,
        promoted: bool = False,
        metadata_json: dict | None = None,
    ) -> VSGGuideModel:
        """Find-or-create by (vsg_run_id, version). Updates if exists."""
        stmt = (
            select(VSGGuideModel)
            .where(
                VSGGuideModel.vsg_run_id == vsg_run_id,
                VSGGuideModel.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.storage_key = storage_key
            if content_hash is not None:
                existing.content_hash = content_hash
            existing.word_count = word_count
            if source_authors is not None:
                existing.source_authors = source_authors
            existing.promoted = promoted
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            await self._session.flush()
            return existing

        guide = VSGGuideModel(
            vsg_run_id=vsg_run_id,
            version=version,
            storage_key=storage_key,
            content_hash=content_hash,
            word_count=word_count,
            source_authors=source_authors,
            promoted=promoted,
            metadata_json=metadata_json,
        )
        self._session.add(guide)
        await self._session.flush()
        return guide
