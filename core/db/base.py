"""Declarative base + shared mixins for all ORM models."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class UUIDPKMixin:
    """Mixin providing a native Postgres UUID primary key."""

    id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=_uuid.uuid4,
    )


class TimestampMixin:
    """Mixin providing created_at / updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
