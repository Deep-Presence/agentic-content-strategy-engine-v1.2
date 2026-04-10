"""Unit tests for durable topic-run activity snapshot shaping."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from core.services.content_engine_topic_runs import ContentEngineTopicRunService


def test_to_event_snapshot_merges_run_context_into_payload() -> None:
    run = SimpleNamespace(
        id="run-1",
        batch_run_id="batch-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        topic_text="Equity dilution guide",
        brief_id="WE-003",
        effective_slug="test-co",
        entry_mode="topic_discovery",
        metadata_json={
            "buyer_stage": "tofu",
            "intent_type": "informational",
        },
    )
    event = SimpleNamespace(
        id="evt-1",
        topic_run_id="run-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        event_type="topic_run_changed",
        stage="drafting",
        status="drafting",
        seq=4,
        content_piece_id=None,
        pipeline_task_id="task-1",
        payload_json={"note": "Worker drafting started"},
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )

    snapshot = ContentEngineTopicRunService._to_event_snapshot(run, event)

    assert snapshot.payload_json == {
        "note": "Worker drafting started",
        "brief_id": "WE-003",
        "display_id": "WE-003",
        "topic_text": "Equity dilution guide",
        "entry_mode": "topic_discovery",
        "buyer_stage": "tofu",
        "intent_type": "informational",
        "effective_slug": "test-co",
        "batch_run_id": "batch-1",
    }


def test_to_event_snapshot_preserves_explicit_payload_values() -> None:
    run = SimpleNamespace(
        id="run-1",
        batch_run_id="batch-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        topic_text="Equity dilution guide",
        brief_id="WE-003",
        effective_slug="test-co",
        entry_mode="topic_discovery",
        metadata_json={"buyer_stage": "tofu"},
    )
    event = SimpleNamespace(
        id="evt-1",
        topic_run_id="run-1",
        topic_assignment_id="ta-1",
        display_id="WE-003",
        event_type="topic_run_created",
        stage="gap_analysis_pending",
        status="gap_analysis_pending",
        seq=1,
        content_piece_id=None,
        pipeline_task_id="task-1",
        payload_json={
            "brief_id": "CUSTOM-1",
            "display_id": "CUSTOM-1",
            "topic_text": "Custom topic",
            "entry_mode": "manual",
            "buyer_stage": "bofu",
            "batch_run_id": "batch-custom",
        },
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )

    snapshot = ContentEngineTopicRunService._to_event_snapshot(run, event)

    assert snapshot.payload_json["brief_id"] == "CUSTOM-1"
    assert snapshot.payload_json["display_id"] == "CUSTOM-1"
    assert snapshot.payload_json["topic_text"] == "Custom topic"
    assert snapshot.payload_json["entry_mode"] == "manual"
    assert snapshot.payload_json["buyer_stage"] == "bofu"
    assert snapshot.payload_json["batch_run_id"] == "batch-custom"
