"""Lazy async engine + session factory.

The engine is created on first call to ``get_engine()``, **not** at import
time.  This avoids breaking existing pipeline scripts and CLI tools that
don't set ``DATABASE_URL``.
"""
from __future__ import annotations

import threading

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config.settings import settings

_lock = threading.Lock()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the shared async engine (created lazily, thread-safe)."""
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        # Double-checked locking: re-check after acquiring lock.
        if _engine is not None:
            return _engine
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Set it in .env.local or as an environment variable."
            )
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle=3600,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared async session factory (created lazily)."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory
    with _lock:
        if _session_factory is not None:
            return _session_factory
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def reset_engine() -> None:
    """Dispose engine pool and reset globals (for testing).

    Made async so callers can ``await reset_engine()`` — ``engine.dispose()``
    is a coroutine on ``AsyncEngine``.
    """
    global _engine, _session_factory
    with _lock:
        engine = _engine
        _engine = None
        _session_factory = None
    if engine is not None:
        await engine.dispose()
