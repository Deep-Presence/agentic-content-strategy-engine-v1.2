"""FastAPI dependency injection for database sessions and repositories.

These dependencies coexist with the existing ``api/dependencies.py`` which
provides ``get_task_store()``, ``get_event_bus()``, etc.  In Phase 1, these
are importable but NOT wired into any existing router.  Phase 2 will
integrate them when migrating auth and services to the DB.
"""
from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.engine import get_session_factory
from core.db.repositories.auth_repo import AuthRepository
from core.db.repositories.cache_repo import CacheRepository
from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.content_repo import ContentRepository
from core.db.repositories.embedding_repo import EmbeddingRepository
from core.db.repositories.gap_analysis_repo import GapAnalysisRepository
from core.db.repositories.pipeline_repo import PipelineRepository
from core.db.repositories.tracking_repo import TrackingRepository


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session with commit-on-success, rollback-on-error.

    This is the unit-of-work boundary: all repository flushes within a
    single request are committed atomically when the request completes
    successfully.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Repository factories ──────────────────────────────────────────────
# Each takes a session (from Depends(get_db_session)) and returns a repo.
# Usage in routers (Phase 2+):
#   async def endpoint(repo: CompanyRepository = Depends(get_company_repo)):

async def get_company_repo(
    session: AsyncSession = Depends(get_db_session),
) -> CompanyRepository:
    return CompanyRepository(session)


async def get_auth_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AuthRepository:
    return AuthRepository(session)


async def get_pipeline_repo(
    session: AsyncSession = Depends(get_db_session),
) -> PipelineRepository:
    return PipelineRepository(session)


async def get_cache_repo(
    session: AsyncSession = Depends(get_db_session),
) -> CacheRepository:
    return CacheRepository(session)


async def get_gap_analysis_repo(
    session: AsyncSession = Depends(get_db_session),
) -> GapAnalysisRepository:
    return GapAnalysisRepository(session)


async def get_embedding_repo(
    session: AsyncSession = Depends(get_db_session),
) -> EmbeddingRepository:
    return EmbeddingRepository(session)


async def get_tracking_repo(
    session: AsyncSession = Depends(get_db_session),
) -> TrackingRepository:
    return TrackingRepository(session)


async def get_content_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ContentRepository:
    return ContentRepository(session)
