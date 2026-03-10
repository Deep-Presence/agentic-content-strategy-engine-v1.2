"""DB test fixtures — auto-skip if TEST_DATABASE_URL not set."""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.db.base import Base

# Import all models to register metadata
import core.db.models  # noqa: F401

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")

# Auto-skip ALL tests in this directory if no test DB configured
pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create test engine and schema (once per session)."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Savepoint-based session — each test rolls back completely."""
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Start a nested savepoint
        await conn.begin_nested()

        # Restart savepoint after each flush/commit
        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(session_sync, transaction):
            if transaction.nested and not transaction._parent.nested:
                session_sync.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


# ── Helper fixtures ───────────────────────────────────────────────────


@pytest_asyncio.fixture
async def sample_company(db_session):
    """Create and return a test company."""
    from core.db.models.organization import CompanyModel

    company = CompanyModel(slug="test-co", name="Test Co", domain="test.com")
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def sample_user(db_session, sample_company):
    """Create and return a test user."""
    from core.db.models.organization import UserModel
    from core.db.enums import UserRole

    user = UserModel(
        company_id=sample_company.id,
        email="test@test.com",
        password_hash="hashed_password",
        role=UserRole.superuser,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def sample_pipeline_run(db_session, sample_company):
    """Create and return a test pipeline run."""
    from core.db.models.pipelines import PipelineRunModel
    from core.db.enums import PipelineType, PipelineStatus

    run = PipelineRunModel(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.running,
    )
    db_session.add(run)
    await db_session.flush()
    return run
