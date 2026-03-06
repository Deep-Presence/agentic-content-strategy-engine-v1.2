"""Tests for PipelineRepository."""
from __future__ import annotations

import os

import pytest

from core.db.enums import PipelineStatus, PipelineType, StageStatus
from core.db.repositories.pipeline_repo import PipelineRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


async def test_create_run_and_get_by_id(db_session, sample_company):
    """create_run() then get_by_id() roundtrip."""
    repo = PipelineRepository(db_session)
    run = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.pending,
    )

    fetched = await repo.get_by_id(run.id)
    assert fetched is not None
    assert fetched.id == run.id
    assert fetched.effective_slug == "test-co"
    assert fetched.pipeline_type == PipelineType.gap_analysis
    assert fetched.status == PipelineStatus.pending


async def test_update_status(db_session, sample_company):
    """update_status() changes status and optionally sets error_message."""
    repo = PipelineRepository(db_session)
    run = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.research,
        status=PipelineStatus.running,
    )

    updated = await repo.update_status(run.id, PipelineStatus.failed, "timeout")
    assert updated is not None
    assert updated.status == PipelineStatus.failed
    assert updated.error_message == "timeout"


async def test_list_by_company(db_session, sample_company):
    """list_by_company() returns runs for the given company."""
    from core.db.models.organization import CompanyModel

    repo = PipelineRepository(db_session)

    other = CompanyModel(slug="other-pipe", name="Other", domain="other-pipe.com")
    db_session.add(other)
    await db_session.flush()

    run_mine = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.completed,
    )
    run_other = await repo.create_run(
        company_id=other.id,
        effective_slug="other-pipe",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.completed,
    )

    results = await repo.list_by_company(sample_company.id)
    result_ids = [r.id for r in results]
    assert run_mine.id in result_ids
    assert run_other.id not in result_ids


async def test_list_by_company_with_type_filter(db_session, sample_company):
    """list_by_company() with pipeline_type filter narrows results."""
    repo = PipelineRepository(db_session)

    run_gap = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.completed,
    )
    run_research = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.research,
        status=PipelineStatus.completed,
    )

    gap_results = await repo.list_by_company(
        sample_company.id, pipeline_type=PipelineType.gap_analysis
    )
    gap_ids = [r.id for r in gap_results]
    assert run_gap.id in gap_ids
    assert run_research.id not in gap_ids


async def test_add_stage_log(db_session, sample_pipeline_run):
    """add_stage_log() creates a stage log entry linked to the run."""
    repo = PipelineRepository(db_session)

    log = await repo.add_stage_log(
        sample_pipeline_run.id,
        stage_name="s3_search_platforms",
        status=StageStatus.running,
        items_processed=42,
    )

    assert log.id is not None
    assert log.run_id == sample_pipeline_run.id
    assert log.stage_name == "s3_search_platforms"
    assert log.status == StageStatus.running
    assert log.items_processed == 42


async def test_get_active_runs(db_session, sample_company):
    """get_active_runs() returns only pending/running runs."""
    repo = PipelineRepository(db_session)

    active_run = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.running,
    )
    completed_run = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.research,
        status=PipelineStatus.completed,
    )
    pending_run = await repo.create_run(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.content,
        status=PipelineStatus.pending,
    )

    active = await repo.get_active_runs(sample_company.id)
    active_ids = [r.id for r in active]
    assert active_run.id in active_ids
    assert pending_run.id in active_ids
    assert completed_run.id not in active_ids
