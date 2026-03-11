"""DB repositories for Audience Persona ORM operations.

Follows the project's SQLAlchemyRepository pattern:
- Repos call session.add() + session.flush() only
- session.commit() is NEVER called here — commit happens in the DI layer

Two table-specific repositories:
- PersonaRunRepository     — persona_runs
- PersonaProfileRepository — persona_profiles
"""
from __future__ import annotations

import uuid as _uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import ResearchRunStatus
from core.db.models.audience_persona import (
    PersonaProfileModel,
    PersonaRunModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class PersonaRunRepository(SQLAlchemyRepository[PersonaRunModel]):
    """Repository for persona_runs table."""

    model_class = PersonaRunModel

    async def get_by_effective_slug(
        self, effective_slug: str
    ) -> Optional[PersonaRunModel]:
        """Find the latest persona run by effective_slug."""
        stmt = (
            select(PersonaRunModel)
            .where(PersonaRunModel.effective_slug == effective_slug)
            .order_by(PersonaRunModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_company(
        self, company_id: _uuid.UUID | str
    ) -> Sequence[PersonaRunModel]:
        """List persona runs for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(PersonaRunModel)
            .where(PersonaRunModel.company_id == cid)
            .order_by(PersonaRunModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self, run_id: _uuid.UUID | str, status: ResearchRunStatus
    ) -> Optional[PersonaRunModel]:
        """Update the status of a persona run."""
        return await self.update(run_id, status=status)

    async def upsert_run(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        *,
        pipeline_run_id: _uuid.UUID | None = None,
        product_id: _uuid.UUID | None = None,
        kb_synthesis_version: int | None = None,
        status: ResearchRunStatus = ResearchRunStatus.draft,
    ) -> PersonaRunModel:
        """Find-or-create by (company_id, effective_slug). Updates if exists."""
        stmt = (
            select(PersonaRunModel)
            .where(
                PersonaRunModel.company_id == company_id,
                PersonaRunModel.effective_slug == effective_slug,
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
            if kb_synthesis_version is not None:
                existing.kb_synthesis_version = kb_synthesis_version
            await self._session.flush()
            return existing

        run = PersonaRunModel(
            company_id=company_id,
            effective_slug=effective_slug,
            pipeline_run_id=pipeline_run_id,
            product_id=product_id,
            kb_synthesis_version=kb_synthesis_version,
            status=status,
        )
        self._session.add(run)
        await self._session.flush()
        return run


class PersonaProfileRepository(SQLAlchemyRepository[PersonaProfileModel]):
    """Repository for persona_profiles table."""

    model_class = PersonaProfileModel

    async def get_by_run_and_persona_id(
        self,
        persona_run_id: _uuid.UUID | str,
        persona_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[PersonaProfileModel]:
        """Get a profile by run + persona_id, optionally by version."""
        rid = _uuid.UUID(str(persona_run_id)) if isinstance(persona_run_id, str) else persona_run_id
        stmt = select(PersonaProfileModel).where(
            PersonaProfileModel.persona_run_id == rid,
            PersonaProfileModel.persona_id == persona_id,
        )
        if version is not None:
            stmt = stmt.where(PersonaProfileModel.version == version)
        else:
            stmt = stmt.order_by(PersonaProfileModel.version.desc())
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_run(
        self, persona_run_id: _uuid.UUID | str
    ) -> Sequence[PersonaProfileModel]:
        """List all profiles for a persona run."""
        rid = _uuid.UUID(str(persona_run_id)) if isinstance(persona_run_id, str) else persona_run_id
        stmt = (
            select(PersonaProfileModel)
            .where(PersonaProfileModel.persona_run_id == rid)
            .order_by(
                PersonaProfileModel.persona_id,
                PersonaProfileModel.version.desc(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_profile(
        self,
        persona_run_id: _uuid.UUID,
        persona_id: str,
        persona_name: str,
        version: int,
        storage_key: str,
        *,
        tagline: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        content_hash: str | None = None,
        word_count: int = 0,
        created_by: str = "agent",
        metadata_json: dict | None = None,
    ) -> PersonaProfileModel:
        """Find-or-create by (persona_run_id, persona_id, version). Updates if exists."""
        stmt = (
            select(PersonaProfileModel)
            .where(
                PersonaProfileModel.persona_run_id == persona_run_id,
                PersonaProfileModel.persona_id == persona_id,
                PersonaProfileModel.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalars().first()

        if existing is not None:
            existing.persona_name = persona_name
            existing.storage_key = storage_key
            if tagline is not None:
                existing.tagline = tagline
            if kind is not None:
                existing.kind = kind
            if status is not None:
                existing.status = status
            if content_hash is not None:
                existing.content_hash = content_hash
            existing.word_count = word_count
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            await self._session.flush()
            return existing

        profile = PersonaProfileModel(
            persona_run_id=persona_run_id,
            persona_id=persona_id,
            persona_name=persona_name,
            version=version,
            storage_key=storage_key,
            tagline=tagline,
            kind=kind,
            status=status,
            content_hash=content_hash,
            word_count=word_count,
            created_by=created_by,
            metadata_json=metadata_json,
        )
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def count_by_run(
        self, persona_run_id: _uuid.UUID | str
    ) -> int:
        """Count profiles for a persona run."""
        rid = _uuid.UUID(str(persona_run_id)) if isinstance(persona_run_id, str) else persona_run_id
        stmt = select(func.count(PersonaProfileModel.id)).where(
            PersonaProfileModel.persona_run_id == rid
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
