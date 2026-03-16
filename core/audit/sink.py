"""Audit event persistence sinks.

``NoOpAuditSink`` — default, log-only (no DB persistence).
``DbAuditSink``   — persists to ``audit_logs`` table when DATABASE_URL is set.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from core.audit.models import AuditEvent

__all__ = ["AuditSinkProtocol", "DbAuditSink", "NoOpAuditSink"]

logger = logging.getLogger(__name__)


@runtime_checkable
class AuditSinkProtocol(Protocol):
    """Interface for audit event persistence."""

    async def persist(self, event: AuditEvent) -> None: ...


class NoOpAuditSink:
    """Default sink — does nothing (structured-log-only mode)."""

    async def persist(self, event: Any) -> None:
        pass


class DbAuditSink:
    """Persists audit events to PostgreSQL via AuditLogRepository.

    Uses its own session (not tied to the request's session lifecycle).
    Catches all exceptions — audit write failures never crash callers.
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def persist(self, event: AuditEvent) -> None:
        try:
            from core.db.models.audit_log import AuditLogModel
            from core.db.repositories.audit_log_repo import AuditLogRepository

            async with self._session_factory() as session:
                repo = AuditLogRepository(session)
                await repo.create_event(
                    event_type=event.event_type.value,
                    user_id=event.user_id,
                    company_slug=event.company_slug,
                    request_id=event.request_id,
                    correlation_id=event.correlation_id,
                    detail=event.detail,
                    created_at=event.timestamp,
                )
                await session.commit()
        except Exception:
            logger.warning(
                "audit_db_write_failed",
                extra={"event_type": event.event_type.value},
                exc_info=True,
            )
