"""Tests for core.audit.logger — audit logging public API."""
from __future__ import annotations

from typing import Any, List
from unittest.mock import AsyncMock

import pytest

from core.audit.logger import (
    _build_event,
    get_sink,
    log_auth_event,
    log_hitl_decision,
    log_pipeline_launch,
    set_sink,
)
from core.audit.models import AuditEvent, AuditEventType
from core.audit.sink import NoOpAuditSink


class _CaptureSink:
    """Test sink that captures persisted events."""

    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    async def persist(self, event: AuditEvent) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _reset_sink():
    """Reset sink to NoOp after each test."""
    original = get_sink()
    yield
    set_sink(original if not isinstance(original, _CaptureSink) else NoOpAuditSink())


class TestSetGetSink:
    def test_default_sink_is_noop(self) -> None:
        set_sink(NoOpAuditSink())
        assert isinstance(get_sink(), NoOpAuditSink)

    def test_set_and_get(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        assert get_sink() is sink


class TestBuildEvent:
    def test_builds_event_with_fields(self) -> None:
        event = _build_event(
            AuditEventType.LOGIN_SUCCESS,
            user_id="u-1",
            company_slug="ramp",
            detail={"extra": "data"},
        )
        assert event.event_type == AuditEventType.LOGIN_SUCCESS
        assert event.user_id == "u-1"
        assert event.company_slug == "ramp"
        assert event.detail == {"extra": "data"}
        assert event.timestamp is not None

    def test_builds_event_with_defaults(self) -> None:
        event = _build_event(AuditEventType.LOGIN_FAILED)
        assert event.user_id is None
        assert event.company_slug is None
        assert event.detail == {}


class TestLogAuthEvent:
    @pytest.mark.asyncio
    async def test_login_success_persists_event(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_auth_event(
            AuditEventType.LOGIN_SUCCESS,
            user_id="u-1",
            email="alice@example.com",
            company_slug="ramp",
        )
        assert len(sink.events) == 1
        evt = sink.events[0]
        assert evt.event_type == AuditEventType.LOGIN_SUCCESS
        assert evt.user_id == "u-1"
        assert evt.detail["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_login_failed_with_detail(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_auth_event(
            AuditEventType.LOGIN_FAILED,
            email="bob@example.com",
            detail={"reason": "invalid_credentials"},
        )
        assert len(sink.events) == 1
        evt = sink.events[0]
        assert evt.event_type == AuditEventType.LOGIN_FAILED
        assert evt.detail["reason"] == "invalid_credentials"
        assert evt.detail["email"] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_register_event(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_auth_event(
            AuditEventType.REGISTER,
            user_id="u-new",
            email="new@co.com",
            company_slug="new-co",
            detail={"role": "superuser", "company_name": "New Co"},
        )
        evt = sink.events[0]
        assert evt.event_type == AuditEventType.REGISTER
        assert evt.detail["role"] == "superuser"

    @pytest.mark.asyncio
    async def test_sink_error_does_not_raise(self) -> None:
        """Sink failures are caught — never crash the caller."""
        failing_sink = AsyncMock(spec=["persist"])
        failing_sink.persist.side_effect = RuntimeError("DB down")
        set_sink(failing_sink)
        # Should not raise
        await log_auth_event(AuditEventType.LOGIN_SUCCESS, user_id="u-1")


class TestLogHitlDecision:
    @pytest.mark.asyncio
    async def test_emits_hitl_decision(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_hitl_decision(
            user_id="u-1",
            run_id="run-abc",
            pipeline="knowledge_base",
            stage="kb_checkpoint_1",
            decision="approve",
            company_slug="ramp",
            detail={"revision_note_provided": False},
        )
        evt = sink.events[0]
        assert evt.event_type == AuditEventType.HITL_DECISION
        assert evt.detail["pipeline"] == "knowledge_base"
        assert evt.detail["decision"] == "approve"
        assert evt.detail["run_id"] == "run-abc"

    @pytest.mark.asyncio
    async def test_rejected_decision_uses_rejected_event_type(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_hitl_decision(
            user_id="u-1",
            run_id="run-abc",
            pipeline="content_v13",
            stage="topic_approval",
            decision="rejected",
            company_slug="ramp",
            detail={"reason": "Stale nonce"},
        )
        evt = sink.events[0]
        assert evt.event_type == AuditEventType.HITL_DECISION_REJECTED
        assert evt.detail["reason"] == "Stale nonce"


class TestLogPipelineLaunch:
    @pytest.mark.asyncio
    async def test_emits_pipeline_started(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_pipeline_launch(
            user_id="u-1",
            pipeline="gap_analysis",
            company_slug="ramp",
            task_id="task-123",
            detail={"product_slug": "cards", "force_rerun": True},
        )
        evt = sink.events[0]
        assert evt.event_type == AuditEventType.PIPELINE_STARTED
        assert evt.detail["pipeline"] == "gap_analysis"
        assert evt.detail["task_id"] == "task-123"
        assert evt.detail["product_slug"] == "cards"

    @pytest.mark.asyncio
    async def test_minimal_pipeline_launch(self) -> None:
        sink = _CaptureSink()
        set_sink(sink)
        await log_pipeline_launch(
            user_id="u-1",
            pipeline="site_audit",
            company_slug="ramp",
            task_id="task-456",
        )
        evt = sink.events[0]
        assert evt.detail["pipeline"] == "site_audit"
        assert "product_slug" not in evt.detail
