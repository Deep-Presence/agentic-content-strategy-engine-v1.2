"""Tests for DbBrandDataService — Postgres-backed brand data service.

Auto-skips without TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from core.db.enums import PipelineStatus, PipelineType
from core.db.models.pipelines import PipelineRunModel
from core.db.repositories.pipeline_repo import PipelineRepository
from core.services.db_brand_data import DbBrandDataService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture
async def brand_service(svc_db_session, tmp_path):
    """Build a DbBrandDataService with repo backed by the test session."""
    return DbBrandDataService(
        pipeline_repo=PipelineRepository(svc_db_session),
        artifacts_root=tmp_path,
    )


@pytest_asyncio.fixture
async def seed_multiple_runs(svc_db_session, seed_company):
    """Create multiple pipeline runs for run history testing."""
    now = datetime.now(tz=timezone.utc)
    runs = []
    for i, (pt, status) in enumerate([
        (PipelineType.gap_analysis, PipelineStatus.completed),
        (PipelineType.research, PipelineStatus.completed),
        (PipelineType.content, PipelineStatus.running),
        (PipelineType.gap_analysis, PipelineStatus.failed),
    ]):
        run = PipelineRunModel(
            company_id=seed_company.id,
            effective_slug="test-co",
            pipeline_type=pt,
            status=status,
            summary={"spa_score": 5.0 + i, "total_queries": 10 + i, "total_citations": 50 + i},
            stages_executed=["s1", "s2"] if i < 2 else [],
            started_at=now,
            completed_at=now if status == PipelineStatus.completed else None,
            duration_seconds=300 if status == PipelineStatus.completed else None,
        )
        svc_db_session.add(run)
        runs.append(run)

    await svc_db_session.flush()
    return runs


class TestGetRunHistory:
    """Test get_run_history() method."""

    @pytest.mark.asyncio
    async def test_returns_all_runs(
        self, brand_service, seed_multiple_runs,
    ):
        resp = await brand_service.get_run_history("test-co")
        assert resp.total == 4
        assert len(resp.runs) == 4

    @pytest.mark.asyncio
    async def test_filter_by_pipeline(
        self, brand_service, seed_multiple_runs,
    ):
        resp = await brand_service.get_run_history(
            "test-co", pipeline="gap_analysis",
        )
        assert resp.total == 2
        for run in resp.runs:
            assert run.pipeline == "gap_analysis"

    @pytest.mark.asyncio
    async def test_status_mapping(
        self, brand_service, seed_multiple_runs,
    ):
        """Verify DB statuses are mapped to frontend-compatible values."""
        resp = await brand_service.get_run_history("test-co")
        statuses = {r.status for r in resp.runs}
        # Should not contain raw DB statuses like 'pending'
        assert statuses <= {"running", "completed", "failed"}

    @pytest.mark.asyncio
    async def test_completed_run_has_duration(
        self, brand_service, seed_multiple_runs,
    ):
        resp = await brand_service.get_run_history(
            "test-co", status="completed",
        )
        for run in resp.runs:
            assert run.duration != ""

    @pytest.mark.asyncio
    async def test_empty_slug(self, brand_service):
        resp = await brand_service.get_run_history("nonexistent-slug")
        assert resp.total == 0
        assert resp.runs == []

    @pytest.mark.asyncio
    async def test_limit(self, brand_service, seed_multiple_runs):
        resp = await brand_service.get_run_history("test-co", limit=2)
        assert resp.total == 2

    @pytest.mark.asyncio
    async def test_company_name_from_slug(
        self, brand_service, seed_multiple_runs,
    ):
        resp = await brand_service.get_run_history("test-co")
        assert resp.runs[0].company == "Test Co"

    @pytest.mark.asyncio
    async def test_steps_completed_for_completed_run(
        self, brand_service, seed_gap_run,
    ):
        """Completed gap run should show 8/8 steps."""
        resp = await brand_service.get_run_history("test-co")
        gap_runs = [r for r in resp.runs if r.pipeline == "gap_analysis"]
        assert len(gap_runs) >= 1
        assert gap_runs[0].steps_completed == 8
        assert gap_runs[0].total_steps == 8
