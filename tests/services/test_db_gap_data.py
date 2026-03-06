"""Tests for DbGapDataService — Postgres-backed gap data service.

Auto-skips without TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

from core.db.repositories.gap_analysis_repo import GapAnalysisRepository
from core.db.repositories.pipeline_repo import PipelineRepository
from core.db.repositories.platform_repo import PlatformRepository
from core.db.repositories.signal_repo import SignalRepository
from core.services.db_gap_data import DbGapDataService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture
async def gap_service(svc_db_session, tmp_path):
    """Build a DbGapDataService with repos backed by the test session."""
    return DbGapDataService(
        gap_repo=GapAnalysisRepository(svc_db_session),
        pipeline_repo=PipelineRepository(svc_db_session),
        signal_repo=SignalRepository(svc_db_session),
        platform_repo=PlatformRepository(svc_db_session),
        artifacts_root=tmp_path,
    )


class TestGetSummary:
    """Test get_summary() method."""

    @pytest.mark.asyncio
    async def test_returns_summary_with_spa_and_gaps(
        self, gap_service, seed_gap_run, seed_query_gaps,
        seed_cluster_specs, seed_spa_results, seed_centroid_results,
    ):
        resp = await gap_service.get_summary("test-co")
        assert resp.total_queries == 5
        assert resp.spa is not None
        assert resp.spa.t_stat == pytest.approx(5.25)
        assert resp.classification_counts is not None

    @pytest.mark.asyncio
    async def test_empty_slug_returns_empty(self, gap_service):
        """Slug with no completed runs returns empty summary."""
        resp = await gap_service.get_summary("nonexistent-slug")
        assert resp.total_queries == 0


class TestGetQueries:
    """Test get_queries() method."""

    @pytest.mark.asyncio
    async def test_paginated_queries(
        self, gap_service, seed_gap_run, seed_query_gaps,
    ):
        resp = await gap_service.get_queries("test-co", page=1, page_size=3)
        assert resp.total == 5
        assert len(resp.queries) == 3
        assert resp.page == 1
        assert resp.total_pages == 2

    @pytest.mark.asyncio
    async def test_filter_by_cluster(
        self, gap_service, seed_gap_run, seed_query_gaps,
    ):
        resp = await gap_service.get_queries(
            "test-co", cluster="Mechanism",
        )
        assert resp.total == 3
        for q in resp.queries:
            assert q.cluster == "Mechanism"

    @pytest.mark.asyncio
    async def test_filter_by_classification(
        self, gap_service, seed_gap_run, seed_query_gaps,
    ):
        resp = await gap_service.get_queries(
            "test-co", classification="significant_gap",
        )
        assert resp.total == 2

    @pytest.mark.asyncio
    async def test_empty_slug(self, gap_service):
        resp = await gap_service.get_queries("nonexistent-slug")
        assert resp.total == 0
        assert resp.queries == []


class TestGetClusters:
    """Test get_clusters() method."""

    @pytest.mark.asyncio
    async def test_returns_cluster_specs(
        self, gap_service, seed_gap_run, seed_cluster_specs,
        seed_query_gaps, seed_centroid_results,
    ):
        resp = await gap_service.get_clusters("test-co")
        assert len(resp.clusters) == 2
        names = {c.cluster_name for c in resp.clusters}
        assert "Mechanism" in names
        assert "Definition" in names


class TestGetHeatmap:
    """Test get_heatmap() method."""

    @pytest.mark.asyncio
    async def test_returns_heatmap_data(
        self, gap_service, seed_gap_run, seed_query_gaps,
    ):
        resp = await gap_service.get_heatmap("test-co")
        assert len(resp.clusters) == 2  # Mechanism + Definition

    @pytest.mark.asyncio
    async def test_empty_slug(self, gap_service):
        resp = await gap_service.get_heatmap("nonexistent-slug")
        assert resp.clusters == []


class TestGetSpaTrend:
    """Test get_spa_trend() method."""

    @pytest.mark.asyncio
    async def test_returns_trend_data(
        self, gap_service, seed_gap_run,
    ):
        resp = await gap_service.get_spa_trend("test-co")
        assert len(resp.trend) == 1
        assert resp.trend[0].spa_score == pytest.approx(5.25)

    @pytest.mark.asyncio
    async def test_empty_slug(self, gap_service):
        resp = await gap_service.get_spa_trend("nonexistent-slug")
        assert resp.trend == []
