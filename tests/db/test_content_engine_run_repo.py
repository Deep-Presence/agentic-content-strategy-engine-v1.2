"""Tests for durable Content Engine batch/topic run repositories."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.db.enums import (
    AudienceSegmentType,
    BuyerStage,
    IntentType,
    RelevanceCell,
    TDStatus,
    TopicAssignmentStatus,
)
from core.db.models.content_engine_runs import ContentEngineTopicRunModel
from core.db.models.topic_discovery import TopicAssignmentModel, TopicDiscoveryModel
from core.db.repositories.content_engine_run_repo import (
    ContentEngineBatchRunRepository,
    ContentEngineTopicEventRepository,
    ContentEngineTopicRunRepository,
)
from core.services.content_engine_topic_runs import ContentEngineTopicRunService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


async def _create_assignment(db_session, sample_company) -> TopicAssignmentModel:
    discovery = TopicDiscoveryModel(
        company_id=sample_company.id,
        effective_slug="test-co",
        status=TDStatus.approved,
        matrix_version=1,
    )
    db_session.add(discovery)
    await db_session.flush()

    assignment = TopicAssignmentModel(
        discovery_id=discovery.id,
        matrix_version=1,
        topic_text="Best expense platforms for SaaS finance teams",
        buyer_stage=BuyerStage.tofu,
        intent_type=IntentType.informational,
        audience_segment="Finance",
        audience_segment_type=AudienceSegmentType.individual_persona,
        relevance=RelevanceCell.relevant,
        status=TopicAssignmentStatus.approved,
        display_id="TC-001",
    )
    db_session.add(assignment)
    await db_session.flush()
    return assignment


async def test_create_batch_topic_run_and_list_by_assignment(db_session, sample_company):
    assignment = await _create_assignment(db_session, sample_company)

    batch_repo = ContentEngineBatchRunRepository(db_session)
    topic_repo = ContentEngineTopicRunRepository(db_session)

    batch = await batch_repo.create(
        company_id=sample_company.id,
        effective_slug="test-co",
        source="topic_discovery_pipeline_b",
        source_mode="td_entry_gap_analysis",
        status="gap_analysis_pending",
        pipeline_task_id="task-123",
        submitted_count=1,
    )
    run = ContentEngineTopicRunModel(
        batch_run_id=batch.id,
        company_id=sample_company.id,
        effective_slug="test-co",
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        topic_text=assignment.topic_text,
        brief_id="TC-001",
        pipeline_task_id="task-123",
        entry_mode="topic_discovery",
        status="gap_analysis_pending",
        current_stage="gap_analysis_pending",
        status_seq=1,
        started_at=datetime.now(timezone.utc),
    )
    await topic_repo.bulk_create([run])

    rows = await topic_repo.list_by_assignment_ids([assignment.id])
    assert len(rows) == 1
    assert rows[0].display_id == "TC-001"
    assert rows[0].topic_assignment_id == assignment.id
    assert rows[0].brief_id == "TC-001"


async def test_append_event_auto_increments_seq(db_session, sample_company):
    assignment = await _create_assignment(db_session, sample_company)

    batch_repo = ContentEngineBatchRunRepository(db_session)
    topic_repo = ContentEngineTopicRunRepository(db_session)
    event_repo = ContentEngineTopicEventRepository(db_session)

    batch = await batch_repo.create(
        company_id=sample_company.id,
        effective_slug="test-co",
        source="topic_discovery_pipeline_b",
        source_mode="td_entry_gap_analysis",
        status="gap_analysis_pending",
        submitted_count=1,
    )
    run = ContentEngineTopicRunModel(
        batch_run_id=batch.id,
        company_id=sample_company.id,
        effective_slug="test-co",
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        topic_text=assignment.topic_text,
        brief_id="TC-001",
        entry_mode="topic_discovery",
        status="gap_analysis_pending",
        current_stage="gap_analysis_pending",
        status_seq=1,
        started_at=datetime.now(timezone.utc),
    )
    await topic_repo.bulk_create([run])

    first = await event_repo.append_event(
        topic_run_id=run.id,
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        event_type="topic_run_created",
        stage="gap_analysis_pending",
        status="gap_analysis_pending",
    )
    second = await event_repo.append_event(
        topic_run_id=run.id,
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        event_type="topic_run_changed",
        stage="gap_analysis",
        status="gap_analysis",
    )

    rows = await event_repo.list_for_topic_run(run.id)
    assert first.seq == 1
    assert second.seq == 2
    assert [row.seq for row in rows] == [1, 2]


async def test_service_lists_topic_run_events_scoped_by_slug(db_session, sample_company):
    assignment = await _create_assignment(db_session, sample_company)

    batch_repo = ContentEngineBatchRunRepository(db_session)
    topic_repo = ContentEngineTopicRunRepository(db_session)
    event_repo = ContentEngineTopicEventRepository(db_session)

    batch = await batch_repo.create(
        company_id=sample_company.id,
        effective_slug="test-co",
        source="topic_discovery_pipeline_b",
        source_mode="td_entry_gap_analysis",
        status="gap_analysis_pending",
        submitted_count=1,
    )
    run = ContentEngineTopicRunModel(
        batch_run_id=batch.id,
        company_id=sample_company.id,
        effective_slug="test-co",
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        topic_text=assignment.topic_text,
        brief_id="TC-001",
        entry_mode="topic_discovery",
        status="gap_analysis_pending",
        current_stage="gap_analysis_pending",
        status_seq=2,
        started_at=datetime.now(timezone.utc),
        metadata_json={
            "buyer_stage": "tofu",
            "intent_type": "informational",
            "effective_slug": "test-co",
        },
    )
    await topic_repo.bulk_create([run])
    await event_repo.append_event(
        topic_run_id=run.id,
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        event_type="topic_run_created",
        stage="gap_analysis_pending",
        status="gap_analysis_pending",
        payload_json={"brief_id": "TC-001"},
    )
    await event_repo.append_event(
        topic_run_id=run.id,
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        event_type="topic_run_changed",
        stage="briefing",
        status="briefing",
        payload_json={"note": "Moved to briefing"},
    )
    await db_session.commit()

    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    service = ContentEngineTopicRunService(session_factory)

    topic_run, events = await service.list_topic_run_events(
        effective_slug="test-co",
        topic_run_id=str(run.id),
    )

    assert topic_run is not None
    assert topic_run.topic_run_id == str(run.id)
    assert topic_run.display_id == "TC-001"
    assert [event.seq for event in events] == [1, 2]
    assert events[0].event_type == "topic_run_created"
    assert events[0].payload_json == {
        "batch_run_id": str(batch.id),
        "brief_id": "TC-001",
        "display_id": "TC-001",
        "topic_text": assignment.topic_text,
        "entry_mode": "topic_discovery",
        "buyer_stage": "tofu",
        "intent_type": "informational",
        "effective_slug": "test-co",
    }
    assert events[1].payload_json == {
        "note": "Moved to briefing",
        "brief_id": "TC-001",
        "display_id": "TC-001",
        "topic_text": assignment.topic_text,
        "entry_mode": "topic_discovery",
        "buyer_stage": "tofu",
        "intent_type": "informational",
        "effective_slug": "test-co",
        "batch_run_id": str(batch.id),
    }

    missing_run, missing_events = await service.list_topic_run_events(
        effective_slug="test-co__other",
        topic_run_id=str(run.id),
    )
    assert missing_run is None
    assert missing_events == []


async def test_advance_topic_runs_matches_original_ga_task_run(db_session, sample_company):
    assignment = await _create_assignment(db_session, sample_company)

    batch_repo = ContentEngineBatchRunRepository(db_session)
    topic_repo = ContentEngineTopicRunRepository(db_session)

    first_batch = await batch_repo.create(
        company_id=sample_company.id,
        effective_slug="test-co",
        source="topic_discovery_pipeline_b",
        source_mode="td_entry_gap_analysis",
        status="gap_analysis_pending",
        pipeline_task_id="ga-task-1",
        submitted_count=1,
    )
    second_batch = await batch_repo.create(
        company_id=sample_company.id,
        effective_slug="test-co",
        source="topic_discovery_pipeline_b",
        source_mode="td_entry_gap_analysis",
        status="gap_analysis_pending",
        pipeline_task_id="ga-task-2",
        submitted_count=1,
    )
    first_run = ContentEngineTopicRunModel(
        batch_run_id=first_batch.id,
        company_id=sample_company.id,
        effective_slug="test-co",
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        topic_text=assignment.topic_text,
        brief_id="TC-001",
        pipeline_task_id="ga-task-1",
        entry_mode="topic_discovery",
        status="gap_analysis_pending",
        current_stage="gap_analysis_pending",
        status_seq=1,
        started_at=datetime.now(timezone.utc),
    )
    second_run = ContentEngineTopicRunModel(
        batch_run_id=second_batch.id,
        company_id=sample_company.id,
        effective_slug="test-co",
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        topic_text=assignment.topic_text,
        brief_id="TC-001",
        pipeline_task_id="ga-task-2",
        entry_mode="topic_discovery",
        status="gap_analysis_pending",
        current_stage="gap_analysis_pending",
        status_seq=1,
        started_at=datetime.now(timezone.utc),
    )
    await topic_repo.bulk_create([first_run, second_run])
    await db_session.commit()

    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    service = ContentEngineTopicRunService(session_factory)
    ga_run_id = "11111111-1111-1111-1111-111111111111"

    updated = await service.advance_topic_runs(
        effective_slug="test-co",
        topic_assignment_ids=[str(assignment.id)],
        status="gap_analysis_complete",
        stage="gap_analysis_complete",
        ga_run_id=ga_run_id,
        match_pipeline_task_id="ga-task-1",
        pipeline_task_id="ga-task-1",
    )

    assert len(updated) == 1
    assert updated[0].topic_run_id == str(first_run.id)
    assert updated[0].ga_run_id == ga_run_id

    rows = await topic_repo.list_by_assignment_ids([assignment.id])
    rows_by_task = {row.pipeline_task_id: row for row in rows}
    assert rows_by_task["ga-task-1"].status == "gap_analysis_complete"
    assert str(rows_by_task["ga-task-1"].ga_run_id) == ga_run_id
    assert rows_by_task["ga-task-2"].status == "gap_analysis_pending"
    assert rows_by_task["ga-task-2"].ga_run_id is None


async def test_advance_topic_runs_by_brief_id_uses_production_task_scope(db_session, sample_company):
    assignment = await _create_assignment(db_session, sample_company)

    batch_repo = ContentEngineBatchRunRepository(db_session)
    topic_repo = ContentEngineTopicRunRepository(db_session)

    batch = await batch_repo.create(
        company_id=sample_company.id,
        effective_slug="test-co",
        source="topic_discovery_pipeline_b",
        source_mode="td_entry_gap_analysis",
        status="briefing",
        pipeline_task_id="prod-task-1",
        submitted_count=1,
    )
    run = ContentEngineTopicRunModel(
        batch_run_id=batch.id,
        company_id=sample_company.id,
        effective_slug="test-co",
        topic_assignment_id=assignment.id,
        display_id="TC-001",
        topic_text=assignment.topic_text,
        brief_id="TC-001",
        pipeline_task_id="prod-task-1",
        entry_mode="topic_discovery",
        status="briefing",
        current_stage="briefing",
        status_seq=2,
        started_at=datetime.now(timezone.utc),
    )
    await topic_repo.bulk_create([run])
    await db_session.commit()

    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    service = ContentEngineTopicRunService(session_factory)

    updated = await service.advance_topic_runs_by_brief_ids(
        effective_slug="test-co",
        brief_ids=["TC-001"],
        status="drafting",
        stage="drafting",
        pipeline_task_id="prod-task-1",
        match_pipeline_task_id="prod-task-1",
    )

    assert len(updated) == 1
    assert updated[0].brief_id == "TC-001"
    assert updated[0].status == "drafting"
    assert updated[0].stage == "drafting"
    assert updated[0].seq == 3
