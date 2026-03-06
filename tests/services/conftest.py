"""Shared fixtures for service tests.

DB tests auto-skip without TEST_DATABASE_URL.
Protocol conformance tests run without any DB.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.db.base import Base

# Import all models to register metadata
import core.db.models  # noqa: F401

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


# ── DB fixtures (session-scoped engine) ──────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def svc_db_engine():
    """Create test engine and schema (once per session)."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def svc_db_session(svc_db_engine):
    """Savepoint-based session — each test rolls back completely."""
    async with svc_db_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await conn.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(session_sync, transaction):
            if transaction.nested and not transaction._parent.nested:
                session_sync.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


# ── Seed data helpers ────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_company(svc_db_session):
    """Create a test company."""
    from core.db.models.organization import CompanyModel

    company = CompanyModel(slug="test-co", name="Test Co", domain="test.com")
    svc_db_session.add(company)
    await svc_db_session.flush()
    return company


@pytest_asyncio.fixture
async def seed_gap_run(svc_db_session, seed_company):
    """Create a completed gap analysis pipeline run with summary data."""
    from core.db.models.pipelines import PipelineRunModel
    from core.db.enums import PipelineType, PipelineStatus

    now = datetime.now(tz=timezone.utc)
    run = PipelineRunModel(
        company_id=seed_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.completed,
        summary={
            "spa_score": 5.25,
            "total_queries": 10,
            "total_citations": 50,
            "avg_gap": 0.08,
        },
        stages_executed=[
            "s1_embed_assets", "s2_generate_queries", "s3_search_platforms",
            "s4_enrich_citations", "s5_embed_content", "s6_analyze",
            "s7_visualize", "s8_generate_report",
        ],
        started_at=now,
        completed_at=now,
        duration_seconds=300,
    )
    svc_db_session.add(run)
    await svc_db_session.flush()
    return run


@pytest_asyncio.fixture
async def seed_content_run(svc_db_session, seed_company):
    """Create a completed content pipeline run."""
    from core.db.models.pipelines import PipelineRunModel
    from core.db.enums import PipelineType, PipelineStatus

    now = datetime.now(tz=timezone.utc)
    run = PipelineRunModel(
        company_id=seed_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.content,
        status=PipelineStatus.completed,
        summary={},
        stages_executed=["stage_1", "stage_2", "stage_3", "stage_4"],
        started_at=now,
        completed_at=now,
        duration_seconds=120,
    )
    svc_db_session.add(run)
    await svc_db_session.flush()
    return run


@pytest_asyncio.fixture
async def seed_query_gaps(svc_db_session, seed_gap_run):
    """Insert test query gaps."""
    from core.db.models.gap_analysis import QueryGapModel
    from core.db.enums import GapClassification

    gaps = []
    for i in range(5):
        gap = QueryGapModel(
            run_id=seed_gap_run.id,
            query_id=f"q_{i+1}",
            query_text=f"Test query {i+1}",
            cluster_name="Mechanism" if i < 3 else "Definition",
            cluster_id=f"C{1 if i < 3 else 2}",
            avg_citation_similarity=0.65 + i * 0.02,
            best_company_similarity=0.55 + i * 0.01,
            gap=0.10 - i * 0.03,
            classification=(
                GapClassification.significant_gap if i < 2
                else GapClassification.roughly_equal
            ),
            content_brief={"exemplars": []},
        )
        svc_db_session.add(gap)
        gaps.append(gap)

    await svc_db_session.flush()
    return gaps


@pytest_asyncio.fixture
async def seed_cluster_specs(svc_db_session, seed_gap_run):
    """Insert test cluster specs."""
    from core.db.models.gap_analysis import ClusterSpecModel

    specs = []
    for name, cid, qc in [("Mechanism", "C1", 3), ("Definition", "C2", 2)]:
        spec = ClusterSpecModel(
            run_id=seed_gap_run.id,
            cluster_id=cid,
            cluster_name=name,
            query_count=qc,
            total_citations_analyzed=qc * 10,
            word_count_min=200,
            word_count_max=5000,
            avg_word_count=1500.0,
            faq_rate=0.3,
            table_rate=0.1,
            list_rate=0.8,
            header_rate=0.9,
            stat_rate=0.5,
            citation_rate=0.7,
            structural_rates={"headers": 0.9, "lists": 0.8, "faq": 0.3},
        )
        svc_db_session.add(spec)
        specs.append(spec)

    await svc_db_session.flush()
    return specs


@pytest_asyncio.fixture
async def seed_spa_results(svc_db_session, seed_gap_run):
    """Insert test SPA results."""
    from core.db.models.gap_analysis import SpaResultModel

    spa = SpaResultModel(
        run_id=seed_gap_run.id,
        cluster_name="all",
        t_stat=5.25,
        p_value=0.00001,
        effect="citation_advantage",
        mean_citation_similarity=0.67,
        mean_company_similarity=0.57,
    )
    svc_db_session.add(spa)
    await svc_db_session.flush()
    return [spa]


@pytest_asyncio.fixture
async def seed_centroid_results(svc_db_session, seed_gap_run):
    """Insert test centroid results."""
    from core.db.models.gap_analysis import CentroidResultModel

    centroids = []
    for name, dist in [("Mechanism", 0.15), ("Definition", 0.22)]:
        c = CentroidResultModel(
            run_id=seed_gap_run.id,
            cluster_name=name,
            distance=dist,
        )
        svc_db_session.add(c)
        centroids.append(c)

    await svc_db_session.flush()
    return centroids


@pytest_asyncio.fixture
async def seed_content_pieces(svc_db_session, seed_content_run):
    """Insert test content pieces."""
    from core.db.models.content import ContentPieceModel
    from core.db.enums import ContentPieceStatus

    pieces = []
    for i, (title, status) in enumerate([
        ("Guide to Spend Management", ContentPieceStatus.approved),
        ("FAQ: Corporate Cards", ContentPieceStatus.review),
        ("3-Way Matching Explained", ContentPieceStatus.drafting),
    ]):
        piece = ContentPieceModel(
            run_id=seed_content_run.id,
            title=title,
            content_type="long_blog" if i % 2 == 0 else "short_faq",
            status=status,
            cluster_name="Mechanism" if i < 2 else "Definition",
            word_count=1500 + i * 200,
            citability_score=0.78 + i * 0.05,
        )
        svc_db_session.add(piece)
        pieces.append(piece)

    await svc_db_session.flush()
    return pieces
