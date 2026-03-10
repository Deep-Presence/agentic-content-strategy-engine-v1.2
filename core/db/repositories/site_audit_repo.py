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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import PipelineStatus
from core.db.models.site_audit import AuditFindingModel, SiteAuditModel
from core.db.repositories.base import SQLAlchemyRepository


class SiteAuditRepository(SQLAlchemyRepository[SiteAuditModel]):
    """Repository for :class:`~core.db.models.site_audit.SiteAuditModel` rows.

    Inherits generic CRUD from :class:`~core.db.repositories.base.SQLAlchemyRepository`
    and adds site-audit–specific query methods.
    """

    model_class = SiteAuditModel

    def __init__(self, session: AsyncSession) -> None:
        """Initialise the repository with an async session.

        Args:
            session: SQLAlchemy async session owned by the caller.
        """
        super().__init__(session)

    async def get_latest_for_company(
        self, company_id: _uuid.UUID | str
    ) -> SiteAuditModel | None:
        """Return the most recently completed audit for a company.

        Args:
            company_id: UUID of the company whose audit we want.

        Returns:
            The newest :class:`SiteAuditModel` with
            ``status=PipelineStatus.completed``, or ``None`` if none exists.
        """
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
        """Return the most recent audits for a company (any status).

        Args:
            company_id: UUID of the company.
            limit: Maximum number of rows to return.  Defaults to 20.

        Returns:
            Sequence of :class:`SiteAuditModel`, newest first.
        """
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
        """Return all findings for a specific audit run.

        Args:
            audit_id: UUID of the :class:`SiteAuditModel` run.
            severity: Optional filter — only return findings with this
                severity value (e.g. ``"critical"``).
            limit: Max rows to return.
            offset: Pagination offset.

        Returns:
            Sequence of :class:`AuditFindingModel` rows, ordered by
            creation time ascending (oldest first = most stable ordering
            for pagination).
        """
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
        """Create a new :class:`SiteAuditModel` row and flush.

        Args:
            company_id: UUID of the owning company.
            site_domain: Domain being audited.
            **kwargs: Any additional column values (e.g. ``status``, ``config``).

        Returns:
            The newly created and flushed :class:`SiteAuditModel` instance.
        """
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
        """Return the most recently completed audit for a specific domain.

        Args:
            company_id: UUID of the company.
            domain: Site domain to filter on.

        Returns:
            The newest completed :class:`SiteAuditModel` for *domain*,
            or ``None`` if none exists.
        """
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
        """Check if at least one completed audit exists for *domain*.

        Args:
            company_id: UUID of the company.
            domain: Site domain to check.

        Returns:
            True if a completed audit exists for the given domain.
        """
        from sqlalchemy import func as sa_func

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
        """Insert multiple findings for a single audit in one flush.

        Args:
            audit_id: UUID of the parent :class:`SiteAuditModel`.
            findings: List of dicts.  Each dict is unpacked as kwargs into
                :class:`AuditFindingModel`.  The ``audit_id`` key is injected
                automatically — do not include it in the dicts.

        Returns:
            Sequence of the newly created :class:`AuditFindingModel` instances.
        """
        aid = _uuid.UUID(str(audit_id)) if isinstance(audit_id, str) else audit_id
        instances: list[AuditFindingModel] = []
        for finding_data in findings:
            instance = AuditFindingModel(audit_id=aid, **finding_data)
            self._session.add(instance)
            instances.append(instance)
        await self._session.flush()
        return instances
