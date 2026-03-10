"""Database layer — SQLAlchemy 2.0 + asyncpg + Alembic.

All exports are lazy — no DB connection is created at import time.
"""
from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.engine import get_engine, get_session_factory, reset_engine

__all__ = [
    "Base",
    "UUIDPKMixin",
    "TimestampMixin",
    "get_engine",
    "get_session_factory",
    "reset_engine",
]
