"""Audit log repository — append-only persistence for audit events."""
from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlalchemy import select

from core.db.models.audit_log import AuditLogModel
from core.db.repositories.base import SQLAlchemyRepository


class AuditLogRepository(SQLAlchemyRepository[AuditLogModel]):
    """Repository for audit log entries.

    Provides ``create_event()`` plus query helpers for company/user filtering.
    """

    model_class = AuditLogModel

    async def create_event(self, **kwargs: Any) -> AuditLogModel:
        """Create a new audit log entry."""
        instance = AuditLogModel(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def list_by_company(
        self,
        company_slug: str,
        *,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[AuditLogModel]:
        """List audit events for a company, optionally filtered by event type."""
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.company_slug == company_slug)
        )
        if event_type:
            stmt = stmt.where(AuditLogModel.event_type == event_type)
        stmt = stmt.order_by(AuditLogModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_user(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[AuditLogModel]:
        """List audit events for a specific user."""
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.user_id == user_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
