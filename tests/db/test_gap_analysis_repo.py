"""Tests for GapAnalysisRepository."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
import uuid

import pytest

from core.db.enums import ContentPieceStatus
from core.db.enums import GapClassification
from core.db.repositories.gap_analysis_repo import GapAnalysisRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


def _make_gap_data(
    run_id,
    query_id: str,
    query_text: str,
    cluster_name: str,
    gap: float,
    classification: GapClassification,
) -> dict:
    """Helper to build a gap data dict."""
    return {
        "run_id": run_id,
        "query_id": query_id,
        "query_text": query_text,
        "cluster_name": cluster_name,
        "gap": gap,
        "classification": classification,
    }


async def test_bulk_insert_query_gaps(db_session, sample_pipeline_run):
    """bulk_insert_query_gaps() inserts multiple gaps and returns them."""
    repo = GapAnalysisRepository(db_session)

    gaps_data = [
        _make_gap_data(
            sample_pipeline_run.id,
            "q1", "What is Ramp?",
            "brand_awareness", 0.8, GapClassification.significant_gap,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q2", "Ramp alternatives",
            "competitor_comparison", 0.3, GapClassification.roughly_equal,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q3", "Expense management tools",
            "category_generic", 0.5, GapClassification.gap_to_close,
        ),
    ]

    results = await repo.bulk_insert_query_gaps(gaps_data)
    assert len(results) == 3
    assert all(r.id is not None for r in results)


async def test_get_gaps_by_run(db_session, sample_pipeline_run):
    """get_gaps_by_run() returns gaps for the given run."""
    repo = GapAnalysisRepository(db_session)

    await repo.bulk_insert_query_gaps([
        _make_gap_data(
            sample_pipeline_run.id,
            "q10", "Test query", "cluster_a", 0.7, GapClassification.significant_gap,
        ),
    ])

    gaps = await repo.get_gaps_by_run(sample_pipeline_run.id)
    assert len(gaps) >= 1
    assert any(g.query_id == "q10" for g in gaps)


async def test_get_gaps_by_run_filters_by_classification(
    db_session, sample_pipeline_run
):
    """get_gaps_by_run() with classification filter narrows results."""
    repo = GapAnalysisRepository(db_session)

    await repo.bulk_insert_query_gaps([
        _make_gap_data(
            sample_pipeline_run.id,
            "q20", "Large gap query",
            "cluster_b", 0.9, GapClassification.significant_gap,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q21", "No gap query",
            "cluster_b", 0.0, GapClassification.company_wins,
        ),
    ])

    large_gaps = await repo.get_gaps_by_run(
        sample_pipeline_run.id, classification=GapClassification.significant_gap
    )
    assert all(g.classification == GapClassification.significant_gap for g in large_gaps)
    assert any(g.query_id == "q20" for g in large_gaps)
    # q21 should NOT appear
    assert not any(g.query_id == "q21" for g in large_gaps)


async def test_get_gaps_by_run_filters_by_cluster_name(
    db_session, sample_pipeline_run
):
    """get_gaps_by_run() with cluster_name filter narrows results."""
    repo = GapAnalysisRepository(db_session)

    await repo.bulk_insert_query_gaps([
        _make_gap_data(
            sample_pipeline_run.id,
            "q30", "Cluster X query",
            "cluster_x", 0.6, GapClassification.gap_to_close,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q31", "Cluster Y query",
            "cluster_y", 0.4, GapClassification.roughly_equal,
        ),
    ])

    x_gaps = await repo.get_gaps_by_run(
        sample_pipeline_run.id, cluster_name="cluster_x"
    )
    assert all(g.cluster_name == "cluster_x" for g in x_gaps)
    assert any(g.query_id == "q30" for g in x_gaps)
    assert not any(g.query_id == "q31" for g in x_gaps)


async def test_update_gap(db_session, sample_pipeline_run):
    """update_gap() modifies an existing gap."""
    repo = GapAnalysisRepository(db_session)

    results = await repo.bulk_insert_query_gaps([
        _make_gap_data(
            sample_pipeline_run.id,
            "q40", "Update me",
            "cluster_z", 0.5, GapClassification.gap_to_close,
        ),
    ])
    gap = results[0]

    updated = await repo.update_gap(
        gap.id,
        gap=0.1,
        classification=GapClassification.company_wins,
        content_brief={"title": "New brief"},
    )
    assert updated is not None
    assert updated.gap == pytest.approx(0.1)
    assert updated.classification == GapClassification.company_wins
    assert updated.content_brief == {"title": "New brief"}


async def test_get_cluster_specs(db_session, sample_pipeline_run):
    """get_cluster_specs() returns specs for the given run."""
    from core.db.models.gap_analysis import ClusterSpecModel

    spec = ClusterSpecModel(
        run_id=sample_pipeline_run.id,
        cluster_name="brand_awareness",
        query_count=15,
        total_citations_analyzed=120,
        avg_word_count=1200.0,
    )
    db_session.add(spec)
    await db_session.flush()

    repo = GapAnalysisRepository(db_session)
    specs = await repo.get_cluster_specs(sample_pipeline_run.id)

    assert len(specs) >= 1
    found = [s for s in specs if s.cluster_name == "brand_awareness"]
    assert len(found) == 1
    assert found[0].query_count == 15
    assert found[0].total_citations_analyzed == 120


async def test_get_cited_exemplar_dates_for_inventory_url(
    db_session, sample_company, sample_pipeline_run
):
    """Returns modified/published benchmark dates for a targeted page URL."""
    from core.db.models.cache import UrlEnrichmentCacheModel
    from core.db.models.content import ContentPieceModel
    from core.db.models.gap_analysis import QueryExemplarModel, QueryGapModel

    piece = ContentPieceModel(
        company_id=sample_company.id,
        title="Published Page",
        status=ContentPieceStatus.published,
        published_url="https://example.com/blog/post/",
        published_at=datetime.now(timezone.utc) - timedelta(days=120),
    )
    db_session.add(piece)
    await db_session.flush()

    gap = QueryGapModel(
        run_id=sample_pipeline_run.id,
        query_id="q-freshness",
        query_text="freshness query",
        cluster_name="cluster",
        gap=0.4,
        classification=GapClassification.gap_to_close,
        targeted_by_content_id=piece.id,
    )
    db_session.add(gap)
    await db_session.flush()

    published_at = datetime.now(timezone.utc) - timedelta(days=50)
    modified_at = datetime.now(timezone.utc) - timedelta(days=20)
    enrichment = UrlEnrichmentCacheModel(
        id=uuid.uuid4(),
        url_hash="hash-freshness",
        url="https://competitor.example.com/article",
        final_url="https://competitor.example.com/article",
        domain="competitor.example.com",
        published_at=published_at,
        modified_at=modified_at,
        scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(enrichment)
    await db_session.flush()

    exemplar = QueryExemplarModel(
        query_gap_id=gap.id,
        url_enrichment_id=enrichment.id,
        url="https://competitor.example.com/article",
        domain="competitor.example.com",
        similarity=0.9,
        rank=1,
    )
    db_session.add(exemplar)
    await db_session.flush()

    repo = GapAnalysisRepository(db_session)
    result = await repo.get_cited_exemplar_dates_for_inventory_url(
        sample_company.id,
        "https://example.com/blog/post",
        normalized_url="https://example.com/blog/post",
    )

    assert result == [modified_at]
