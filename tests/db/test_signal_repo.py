"""Tests for SignalRepository — signal aggregation SQL queries.

Auto-skips without TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

from core.db.enums import SearchEngine
from core.db.models.gap_analysis import RunCitationModel
from core.db.models.cache import UrlEnrichmentCacheModel, UrlStructuralSignalsModel
from core.db.repositories.signal_repo import SignalRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture
async def signal_repo(db_session):
    return SignalRepository(db_session)


@pytest_asyncio.fixture
async def seed_signals(db_session, sample_pipeline_run):
    """Create citations with url enrichment + structural signals."""
    run_id = sample_pipeline_run.id

    # We need run_queries first for the FK
    from core.db.models.gap_analysis import RunQueryModel
    rq = RunQueryModel(
        run_id=run_id, query_id="q_1", cluster_name="Mechanism",
        query_text="How does spend control work?",
    )
    db_session.add(rq)
    await db_session.flush()

    enrichments = []
    for i in range(3):
        # Create url enrichment cache entry
        ue = UrlEnrichmentCacheModel(
            url=f"https://example.com/page-{i}",
            domain="example.com",
        )
        db_session.add(ue)
        await db_session.flush()

        # Create structural signals
        signals = UrlStructuralSignalsModel(
            url_enrichment_id=ue.id,
            word_count=1000 + i * 500,
            sentence_count=50 + i * 10,
            paragraph_count=10 + i * 2,
            avg_paragraph_length=100.0 + i * 10,
            reading_level=8.0 + i,
            self_contained_ratio=0.7 + i * 0.05,
            h1_count=1,
            h2_count=3 + i,
            h3_count=5,
            h4_count=0,
            list_block_count=2 + i,
            ordered_list_count=1,
            table_count=i,
            code_block_count=0,
            image_count=2,
            internal_link_count=5,
            external_link_count=3,
            avg_list_items=4.0,
            stat_count=i,
            citation_count=2 + i,
            has_faq_section=i == 0,
            has_definition_opening=i < 2,
            has_comparison_section=False,
            has_step_by_step=i == 2,
            has_table_of_contents=True,
            has_key_takeaways=False,
            has_expert_quotes=False,
            authority_type="commercial_or_media",
            content_type="blog_or_article",
        )
        db_session.add(signals)
        await db_session.flush()

        # Create citation linking enrichment to run
        cit = RunCitationModel(
            run_id=run_id,
            query_id="q_1",
            cluster_name="Mechanism",
            engine=SearchEngine.openai,
            url_enrichment_id=ue.id,
            url=f"https://example.com/page-{i}",
            domain="example.com",
        )
        db_session.add(cit)
        enrichments.append(ue)

    await db_session.flush()
    return enrichments


class TestGetSignalAverages:
    @pytest.mark.asyncio
    async def test_computes_averages(self, signal_repo, sample_pipeline_run, seed_signals):
        avgs = await signal_repo.get_signal_averages(sample_pipeline_run.id)
        assert avgs["word_count"] == pytest.approx(1500.0)  # (1000+1500+2000)/3
        assert avgs["sentence_count"] == pytest.approx(60.0)  # (50+60+70)/3
        assert avgs["h2_count"] == pytest.approx(4.0)  # (3+4+5)/3

    @pytest.mark.asyncio
    async def test_empty_run(self, signal_repo, sample_pipeline_run):
        avgs = await signal_repo.get_signal_averages(sample_pipeline_run.id)
        # All should be 0 (COALESCE default) since no enrichments
        assert avgs["word_count"] == pytest.approx(0.0)


class TestGetClusterPatterns:
    @pytest.mark.asyncio
    async def test_returns_pattern_rates(self, signal_repo, sample_pipeline_run, seed_signals):
        patterns = await signal_repo.get_cluster_patterns(sample_pipeline_run.id)
        assert "Mechanism" in patterns
        mech = patterns["Mechanism"]
        assert mech["total"] == 3
        assert 0 <= mech["has_faq_section"] <= 1  # rate between 0 and 1
        assert 0 <= mech["has_definition_opening"] <= 1

    @pytest.mark.asyncio
    async def test_empty_run(self, signal_repo, sample_pipeline_run):
        patterns = await signal_repo.get_cluster_patterns(sample_pipeline_run.id)
        assert patterns == {}
