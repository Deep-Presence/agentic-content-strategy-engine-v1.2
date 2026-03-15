"""Repository for site audit domain models.

Provides typed query helpers on top of the generic
:class:`~core.db.repositories.base.SQLAlchemyRepository`.

Transaction contract (inherited from base):
    - Only ``session.add()`` + ``session.flush()`` are used here.
    - ``session.commit()`` is NEVER called inside a repository — commit
      happens at the DI / service layer that owns the unit of work.

Usage::

    async with session_factory() as session:
        repo = SiteAuditRepository(session)
        latest = await repo.get_latest_for_company(company_id)
        await session.commit()
"""
from __future__ import annotations

import uuid as _uuid
from typing import Sequence

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import PipelineStatus
from core.db.models.site_audit import (
    AuditFindingModel,
    AuditPageResultModel,
    SiteAuditModel,
)
from core.db.repositories.base import SQLAlchemyRepository


class SiteAuditRepository(SQLAlchemyRepository[SiteAuditModel]):
    """Repository for :class:`~core.db.models.site_audit.SiteAuditModel` rows.

    Inherits generic CRUD from :class:`~core.db.repositories.base.SQLAlchemyRepository`
    and adds site-audit–specific query methods.
    """

    model_class = SiteAuditModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Existing methods ────────────────────────────────────────────────

    async def get_latest_for_company(
        self, company_id: _uuid.UUID | str
    ) -> SiteAuditModel | None:
        """Return the most recently completed audit for a company."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(SiteAuditModel)
            .where(
                SiteAuditModel.company_id == cid,
                SiteAuditModel.status == PipelineStatus.completed,
            )
            .order_by(SiteAuditModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_company(
        self,
        company_id: _uuid.UUID | str,
        limit: int = 20,
    ) -> Sequence[SiteAuditModel]:
        """Return the most recent audits for a company (any status)."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(SiteAuditModel)
            .where(SiteAuditModel.company_id == cid)
            .order_by(SiteAuditModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_audit(
        self,
        audit_id: _uuid.UUID | str,
        *,
        severity: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[AuditFindingModel]:
        """Return all findings for a specific audit run."""
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id
        stmt = select(AuditFindingModel).where(AuditFindingModel.audit_id == aid)

        if severity is not None:
            stmt = stmt.where(AuditFindingModel.severity == severity)

        stmt = (
            stmt.order_by(AuditFindingModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create_audit(
        self,
        company_id: _uuid.UUID | str,
        site_domain: str,
        **kwargs: object,
    ) -> SiteAuditModel:
        """Create a new :class:`SiteAuditModel` row and flush."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        return await self.create(
            company_id=cid,
            site_domain=site_domain,
            **kwargs,
        )

    async def get_latest_for_domain(
        self,
        company_id: _uuid.UUID | str,
        domain: str,
    ) -> SiteAuditModel | None:
        """Return the most recently completed audit for a specific domain."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(SiteAuditModel)
            .where(
                SiteAuditModel.company_id == cid,
                SiteAuditModel.site_domain == domain,
                SiteAuditModel.status == PipelineStatus.completed,
            )
            .order_by(SiteAuditModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_for_domain(
        self,
        company_id: _uuid.UUID | str,
        domain: str,
    ) -> bool:
        """Check if at least one completed audit exists for *domain*."""
        cid = _uuid.UUID(str(company_id)) if isinstance(company_id, str) else company_id
        stmt = (
            select(sa_func.count())
            .select_from(SiteAuditModel)
            .where(
                SiteAuditModel.company_id == cid,
                SiteAuditModel.site_domain == domain,
                SiteAuditModel.status == PipelineStatus.completed,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def bulk_insert_findings(
        self,
        audit_id: _uuid.UUID | str,
        findings: list[dict[str, object]],
    ) -> Sequence[AuditFindingModel]:
        """Insert multiple findings for a single audit in one flush."""
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id
        instances: list[AuditFindingModel] = []
        for finding_data in findings:
            instance = AuditFindingModel(audit_id=aid, **finding_data)
            self._session.add(instance)
            instances.append(instance)
        await self._session.flush()
        return instances

    # ── New methods (migration 0009) ────────────────────────────────────

    async def list_for_slug(
        self,
        effective_slug: str,
        limit: int = 20,
    ) -> Sequence[SiteAuditModel]:
        """Return the most recent audits for an effective_slug (any status)."""
        stmt = (
            select(SiteAuditModel)
            .where(SiteAuditModel.effective_slug == effective_slug)
            .order_by(SiteAuditModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_slug_and_audit_id(
        self,
        effective_slug: str,
        audit_id: _uuid.UUID | str,
    ) -> SiteAuditModel | None:
        """Return audit matching both effective_slug and audit_id (tenant-safe)."""
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id
        stmt = (
            select(SiteAuditModel)
            .where(
                SiteAuditModel.effective_slug == effective_slug,
                SiteAuditModel.id == aid,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_enriched_data(
        self, audit_id: _uuid.UUID | str
    ) -> bool:
        """Check if audit has been fully persisted (overall_score IS NOT NULL)."""
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id
        stmt = (
            select(sa_func.count())
            .select_from(SiteAuditModel)
            .where(
                SiteAuditModel.id == aid,
                SiteAuditModel.overall_score.isnot(None),
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def get_findings_for_audit(
        self,
        audit_id: _uuid.UUID | str,
        *,
        severity: str | None = None,
        dimension: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[AuditFindingModel], int]:
        """Return paginated findings with optional filters.

        Returns:
            Tuple of (findings, total_count).
        """
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id

        # Base filter
        base_where = [AuditFindingModel.audit_id == aid]
        if severity is not None:
            base_where.append(AuditFindingModel.severity == severity)
        if dimension is not None:
            base_where.append(AuditFindingModel.dimension == dimension)

        # Count query
        count_stmt = (
            select(sa_func.count())
            .select_from(AuditFindingModel)
            .where(*base_where)
        )
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data query
        data_stmt = (
            select(AuditFindingModel)
            .where(*base_where)
            .order_by(AuditFindingModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        data_result = await self._session.execute(data_stmt)
        findings = data_result.scalars().all()

        return findings, total

    async def get_page_results_for_audit(
        self,
        audit_id: _uuid.UUID | str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[AuditPageResultModel], int]:
        """Return paginated page results ordered by page_index.

        Returns:
            Tuple of (page_results, total_count).
        """
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id

        # Count
        count_stmt = (
            select(sa_func.count())
            .select_from(AuditPageResultModel)
            .where(AuditPageResultModel.audit_id == aid)
        )
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data
        data_stmt = (
            select(AuditPageResultModel)
            .where(AuditPageResultModel.audit_id == aid)
            .order_by(AuditPageResultModel.page_index.asc())
            .limit(limit)
            .offset(offset)
        )
        data_result = await self._session.execute(data_stmt)
        pages = data_result.scalars().all()

        return pages, total

    async def bulk_insert_page_results(
        self,
        audit_id: _uuid.UUID | str,
        page_results: list[dict[str, object]],
    ) -> None:
        """Bulk insert page result rows for an audit."""
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id
        for pr_data in page_results:
            instance = AuditPageResultModel(audit_id=aid, **pr_data)
            self._session.add(instance)
        await self._session.flush()
