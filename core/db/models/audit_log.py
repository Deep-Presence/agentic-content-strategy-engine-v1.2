"""Audit log ORM model — append-only event store for security-critical actions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin


class AuditLogModel(UUIDPKMixin, Base):
    """Append-only audit log table.

    No TimestampMixin — audit logs are immutable (no ``updated_at``).
    ``user_id`` and ``company_slug`` are strings (not FKs) to allow
    logging events for unknown users and companies not yet in the DB.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_company_slug", "company_slug"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index(
            "ix_audit_logs_company_type_created",
            "company_slug",
            "event_type",
            "created_at",
        ),
    )

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    company_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        server_default=func.now(),
    )
