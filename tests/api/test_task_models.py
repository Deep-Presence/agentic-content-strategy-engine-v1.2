"""Tests for api.tasks.models — task status, pipeline task, approval record, response schemas."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.tasks.models import (
    ApprovalRecord,
    PipelineTask,
    TaskStatus,
)
from api.schemas.common import PipelineRunResponse, TaskResponse


class TestTaskStatus:
    def test_enum_values(self) -> None:
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.PENDING_APPROVAL == "pending_approval"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.FAILED_RESTART == "failed_restart"

    def test_enum_count(self) -> None:
        assert len(TaskStatus) == 6


class TestPipelineTask:
    def test_creation_with_defaults(self) -> None:
        task = PipelineTask(
            task_id="test-123",
            pipeline="gap_analysis",
            company_slug="ramp",
        )
        assert task.task_id == "test-123"
        assert task.pipeline == "gap_analysis"
        assert task.status == TaskStatus.RUNNING
        assert task.company_slug == "ramp"
        assert task.current_step is None
        assert task.progress_pct is None
        assert task.result is None
        assert task.error is None
        assert task.approval_payload is None
        assert task.approval_history == []
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)

    def test_creation_with_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        task = PipelineTask(
            task_id="test-456",
            pipeline="research",
            status=TaskStatus.COMPLETED,
            company_slug="carta",
            current_step="company",
            progress_pct=100.0,
            created_at=now,
            updated_at=now,
            result={"output_path": "/artifacts/company_context/carta.md"},
            error=None,
            approval_payload=None,
            approval_history=[],
        )
        assert task.status == TaskStatus.COMPLETED
        assert task.progress_pct == 100.0
        assert task.result == {"output_path": "/artifacts/company_context/carta.md"}

    def test_serialization_roundtrip(self) -> None:
        task = PipelineTask(
            task_id="test-789",
            pipeline="content",
            company_slug="ramp",
        )
        data = task.model_dump(mode="json")
        restored = PipelineTask(**data)
        assert restored.task_id == task.task_id
        assert restored.pipeline == task.pipeline
        assert restored.status == task.status
        assert restored.company_slug == task.company_slug

    def test_pipeline_literal_validation(self) -> None:
        for valid in (
            "research", "gap_analysis", "content", "content_v13",
            "site_audit", "knowledge_base", "audience_persona",
            "voice_style_guide", "topic_discovery",
        ):
            task = PipelineTask(task_id="t", pipeline=valid, company_slug="x")
            assert task.pipeline == valid


class TestApprovalRecord:
    def test_creation(self) -> None:
        record = ApprovalRecord(
            task_id="test-123",
            stage="company",
            decision="approve",
        )
        assert record.task_id == "test-123"
        assert record.stage == "company"
        assert record.decision == "approve"
        assert record.revision_note is None
        assert isinstance(record.decided_at, datetime)

    def test_with_revision_note(self) -> None:
        record = ApprovalRecord(
            task_id="test-123",
            stage="persona",
            decision="revise",
            revision_note="Add more detail about enterprise personas",
        )
        assert record.decision == "revise"
        assert record.revision_note == "Add more detail about enterprise personas"

    def test_serialization_roundtrip(self) -> None:
        record = ApprovalRecord(
            task_id="test-123",
            stage="company",
            decision="approve",
        )
        data = record.model_dump(mode="json")
        restored = ApprovalRecord(**data)
        assert restored.task_id == record.task_id
        assert restored.decision == record.decision


class TestPipelineRunResponse:
    def test_schema(self) -> None:
        now = datetime.now(timezone.utc)
        resp = PipelineRunResponse(
            run_id="run-abc",
            pipeline="gap_analysis",
            company_slug="ramp",
            status="running",
            created_at=now,
        )
        assert resp.run_id == "run-abc"
        assert resp.pipeline == "gap_analysis"
        assert resp.company_slug == "ramp"
        assert resp.status == "running"
        assert resp.created_at == now


class TestTaskResponse:
    def test_schema_minimal(self) -> None:
        now = datetime.now(timezone.utc)
        resp = TaskResponse(
            run_id="run-abc",
            pipeline="research",
            company_slug="ramp",
            status="running",
            created_at=now,
            updated_at=now,
        )
        assert resp.run_id == "run-abc"
        assert resp.company_slug == "ramp"
        assert resp.current_step is None
        assert resp.progress_pct is None
        assert resp.result is None
        assert resp.error is None
        assert resp.approval_payload is None

    def test_schema_full(self) -> None:
        now = datetime.now(timezone.utc)
        resp = TaskResponse(
            run_id="run-abc",
            pipeline="gap_analysis",
            company_slug="ramp",
            status="completed",
            current_step="Step 8",
            progress_pct=100.0,
            created_at=now,
            updated_at=now,
            result={"report_md": "# Report"},
            error=None,
            approval_payload=None,
        )
        assert resp.status == "completed"
        assert resp.result == {"report_md": "# Report"}
