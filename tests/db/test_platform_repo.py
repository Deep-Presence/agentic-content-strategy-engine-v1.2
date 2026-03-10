"""Tests for PlatformRepository — platform-level citation aggregation.

Auto-skips without TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

from core.db.enums import SearchEngine
from core.db.models.gap_analysis import RunCitationModel, RunQueryModel
from core.db.repositories.platform_repo import PlatformRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture
async def platform_repo(db_session):
    return PlatformRepository(db_session)


@pytest_asyncio.fixture
async def seed_citations(db_session, sample_pipeline_run):
    """Create citations from multiple engines with overlapping URLs."""
    run_id = sample_pipeline_run.id

    # Create run_query first (FK requirement)
    rq = RunQueryModel(
        run_id=run_id, query_id="q_1", cluster_name="Test",
        query_text="test query",
    )
    db_session.add(rq)
    await db_session.flush()

    citations_data = [
        # OpenAI cites URLs A, B, C
        (SearchEngine.openai, "https://a.com", "a.com"),
        (SearchEngine.openai, "https://b.com", "b.com"),
        (SearchEngine.openai, "https://c.com", "c.com"),
        # Claude cites URLs A, B, D
        (SearchEngine.claude, "https://a.com", "a.com"),
        (SearchEngine.claude, "https://b.com", "b.com"),
        (SearchEngine.claude, "https://d.com", "d.com"),
        # Gemini cites URLs A, E
        (SearchEngine.gemini, "https://a.com", "a.com"),
        (SearchEngine.gemini, "https://e.com", "e.com"),
    ]

    for engine, url, domain in citations_data:
        cit = RunCitationModel(
            run_id=run_id, query_id="q_1", cluster_name="Test",
            engine=engine, url=url, domain=domain,
        )
        db_session.add(cit)

    await db_session.flush()


class TestGetPlatformSummaries:
    @pytest.mark.asyncio
    async def test_returns_per_engine_counts(
        self, platform_repo, sample_pipeline_run, seed_citations,
    ):
        summaries = await platform_repo.get_platform_summaries(sample_pipeline_run.id)
        assert len(summaries) == 3  # openai, claude, gemini

        by_engine = {s["engine"]: s for s in summaries}
        assert by_engine["openai"]["citation_count"] == 3
        assert by_engine["claude"]["citation_count"] == 3
        assert by_engine["gemini"]["citation_count"] == 2

    @pytest.mark.asyncio
    async def test_unique_url_counts(
        self, platform_repo, sample_pipeline_run, seed_citations,
    ):
        summaries = await platform_repo.get_platform_summaries(sample_pipeline_run.id)
        by_engine = {s["engine"]: s for s in summaries}
        assert by_engine["openai"]["unique_urls"] == 3
        assert by_engine["gemini"]["unique_urls"] == 2

    @pytest.mark.asyncio
    async def test_empty_run(self, platform_repo, sample_pipeline_run):
        summaries = await platform_repo.get_platform_summaries(sample_pipeline_run.id)
        assert summaries == []


class TestGetPlatformUrlSets:
    @pytest.mark.asyncio
    async def test_returns_url_sets(
        self, platform_repo, sample_pipeline_run, seed_citations,
    ):
        url_sets = await platform_repo.get_platform_url_sets(sample_pipeline_run.id)
        assert len(url_sets) == 3
        assert "https://a.com" in url_sets["openai"]
        assert "https://d.com" in url_sets["claude"]
        assert "https://d.com" not in url_sets["openai"]

    @pytest.mark.asyncio
    async def test_empty_run(self, platform_repo, sample_pipeline_run):
        url_sets = await platform_repo.get_platform_url_sets(sample_pipeline_run.id)
        assert url_sets == {}


class TestGetCitationExclusivity:
    @pytest.mark.asyncio
    async def test_exclusive_citations(
        self, platform_repo, sample_pipeline_run, seed_citations,
    ):
        exclusivity = await platform_repo.get_citation_exclusivity(sample_pipeline_run.id)
        # URL C is exclusive to openai
        # URL D is exclusive to claude
        # URL E is exclusive to gemini
        # URLs A and B are shared
        assert exclusivity.get("openai", 0) == 1  # c.com only
        assert exclusivity.get("claude", 0) == 1  # d.com only
        assert exclusivity.get("gemini", 0) == 1  # e.com only

    @pytest.mark.asyncio
    async def test_empty_run(self, platform_repo, sample_pipeline_run):
        exclusivity = await platform_repo.get_citation_exclusivity(sample_pipeline_run.id)
        assert exclusivity == {}
