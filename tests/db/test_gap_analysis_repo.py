"""Tests for GapAnalysisRepository."""
from __future__ import annotations

import os

import pytest

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
            "brand_awareness", 0.8, GapClassification.large_gap,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q2", "Ramp alternatives",
            "competitor_comparison", 0.3, GapClassification.small_gap,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q3", "Expense management tools",
            "category_generic", 0.5, GapClassification.moderate_gap,
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
            "q10", "Test query", "cluster_a", 0.7, GapClassification.large_gap,
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
            "cluster_b", 0.9, GapClassification.large_gap,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q21", "No gap query",
            "cluster_b", 0.0, GapClassification.no_gap,
        ),
    ])

    large_gaps = await repo.get_gaps_by_run(
        sample_pipeline_run.id, classification=GapClassification.large_gap
    )
    assert all(g.classification == GapClassification.large_gap for g in large_gaps)
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
            "cluster_x", 0.6, GapClassification.moderate_gap,
        ),
        _make_gap_data(
            sample_pipeline_run.id,
            "q31", "Cluster Y query",
            "cluster_y", 0.4, GapClassification.small_gap,
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
            "cluster_z", 0.5, GapClassification.moderate_gap,
        ),
    ])
    gap = results[0]

    updated = await repo.update_gap(
        gap.id,
        gap=0.1,
        classification=GapClassification.no_gap,
        content_brief={"title": "New brief"},
    )
    assert updated is not None
    assert updated.gap == pytest.approx(0.1)
    assert updated.classification == GapClassification.no_gap
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
