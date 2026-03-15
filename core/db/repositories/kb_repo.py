"""DB repositories for Knowledge Base ORM operations.

Follows the project's SQLAlchemyRepository pattern:
- Repos call session.add() + session.flush() only
- session.commit() is NEVER called here — commit happens in the DI layer

Three table-specific repositories:
- KBRunRepository       — kb_runs
- KBDocumentRepository  — kb_documents
- KBSynthesisRepository — kb_syntheses
"""
from __future__ import annotations

import uuid as _uuid
from typing import Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ResearchRunStatus
from core.db.models.knowledge_base import (
    KBDocumentModel,
    KBRunModel,
    KBSynthesisModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class KBRunRepository(SQLAlchemyRepository[KBRunModel]):
    """Repository for kb_runs table."""

    model_class = KBRunModel

    async def get_by_effective_slug(
        self, effective_slug: str
    ) -> Optional[KBRunModel]:
        """Find the latest KB run by effective_slug."""
        stmt = (
            select(KBRunModel)
            .where(KBRunModel.effective_slug == effective_slug)
            .order_by(KBRunModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_company(
        self, company_id: _uuid.UUID | str
    ) -> Sequence[KBRunModel]:
        """List KB runs for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(KBRunModel)
            .where(KBRunModel.company_id == cid)
            .order_by(KBRunModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self, run_id: _uuid.UUID | str, status: ResearchRunStatus
    ) -> Optional[KBRunModel]:
        """Update the status of a KB run."""
        return await self.update(run_id, status=status)

    async def update_synthesis_version(
        self, run_id: _uuid.UUID | str, version: int
    ) -> Optional[KBRunModel]:
        """Update the synthesis_version counter."""
        return await self.update(run_id, synthesis_version=version)

    async def upsert_run(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        *,
        pipeline_run_id: _uuid.UUID | None = None,
        product_id: _uuid.UUID | None = None,
        mode: str | None = None,
        status: ResearchRunStatus = ResearchRunStatus.draft,
    ) -> KBRunModel:
        """Find-or-create by (company_id, effective_slug). Updates if exists."""
        stmt = (
            select(KBRunModel)
            .where(
                KBRunModel.company_id == company_id,
                KBRunModel.effective_slug == effective_slug,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.status = status
            if pipeline_run_id is not None:
                existing.pipeline_run_id = pipeline_run_id
            if mode is not None:
                existing.mode = mode
            if product_id is not None:
                existing.product_id = product_id
            await self._session.flush()
            return existing

        run = KBRunModel(
            company_id=company_id,
            effective_slug=effective_slug,
            pipeline_run_id=pipeline_run_id,
            product_id=product_id,
            mode=mode,
            status=status,
        )
        self._session.add(run)
        await self._session.flush()
        return run


class KBDocumentRepository(SQLAlchemyRepository[KBDocumentModel]):
    """Repository for kb_documents table."""

    model_class = KBDocumentModel

    async def get_by_run_and_type(
        self,
        kb_run_id: _uuid.UUID | str,
        doc_type: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[KBDocumentModel]:
        """Get a KB document by run, type, and optionally version."""
        rid = _uuid.UUID(str(kb_run_id)) if isinstance(kb_run_id, str) else kb_run_id
        stmt = select(KBDocumentModel).where(
            KBDocumentModel.kb_run_id == rid,
            KBDocumentModel.doc_type == doc_type,
        )
        if version is not None:
            stmt = stmt.where(KBDocumentModel.version == version)
        else:
            stmt = stmt.order_by(KBDocumentModel.version.desc())
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_run(
        self, kb_run_id: _uuid.UUID | str
    ) -> Sequence[KBDocumentModel]:
        """List all documents for a KB run."""
        rid = _uuid.UUID(str(kb_run_id)) if isinstance(kb_run_id, str) else kb_run_id
        stmt = (
            select(KBDocumentModel)
            .where(KBDocumentModel.kb_run_id == rid)
            .order_by(KBDocumentModel.doc_type, KBDocumentModel.version.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_document(
        self,
        kb_run_id: _uuid.UUID,
        doc_type: str,
        version: int,
        storage_key: str,
        *,
        status: str | None = None,
        content_hash: str | None = None,
        word_count: int = 0,
        staleness_days: int = 90,
        metadata_json: dict | None = None,
    ) -> KBDocumentModel:
        """Find-or-create by (kb_run_id, doc_type, version). Updates if exists."""
        stmt = (
            select(KBDocumentModel)
            .where(
                KBDocumentModel.kb_run_id == kb_run_id,
                KBDocumentModel.doc_type == doc_type,
                KBDocumentModel.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
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

        doc = KBDocumentModel(
            kb_run_id=kb_run_id,
            doc_type=doc_type,
            version=version,
            storage_key=storage_key,
            status=status,
            content_hash=content_hash,
            word_count=word_count,
            staleness_days=staleness_days,
            metadata_json=metadata_json,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def delete_by_run(self, kb_run_id: _uuid.UUID) -> int:
        """Delete all documents for a KB run. Returns deleted count."""
        stmt = delete(KBDocumentModel).where(
            KBDocumentModel.kb_run_id == kb_run_id
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount


class KBSynthesisRepository(SQLAlchemyRepository[KBSynthesisModel]):
    """Repository for kb_syntheses table."""

    model_class = KBSynthesisModel

    async def get_by_run(
        self,
        kb_run_id: _uuid.UUID | str,
        *,
        version: Optional[int] = None,
    ) -> Optional[KBSynthesisModel]:
        """Get synthesis by run, optionally by version (latest if omitted)."""
        rid = _uuid.UUID(str(kb_run_id)) if isinstance(kb_run_id, str) else kb_run_id
        stmt = select(KBSynthesisModel).where(
            KBSynthesisModel.kb_run_id == rid,
        )
        if version is not None:
            stmt = stmt.where(KBSynthesisModel.version == version)
        else:
            stmt = stmt.order_by(KBSynthesisModel.version.desc())
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert_synthesis(
        self,
        kb_run_id: _uuid.UUID,
        version: int,
        storage_key: str,
        *,
        content_hash: str | None = None,
        word_count: int = 0,
        promoted: bool = False,
        metadata_json: dict | None = None,
    ) -> KBSynthesisModel:
        """Find-or-create by (kb_run_id, version). Updates if exists."""
        stmt = (
            select(KBSynthesisModel)
            .where(
                KBSynthesisModel.kb_run_id == kb_run_id,
                KBSynthesisModel.version == version,
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
            existing.promoted = promoted
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            await self._session.flush()
            return existing

        synth = KBSynthesisModel(
            kb_run_id=kb_run_id,
            version=version,
            storage_key=storage_key,
            content_hash=content_hash,
            word_count=word_count,
            promoted=promoted,
            metadata_json=metadata_json,
        )
        self._session.add(synth)
        await self._session.flush()
        return synth
