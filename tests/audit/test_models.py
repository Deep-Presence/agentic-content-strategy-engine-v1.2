"""Tests for core.audit.models — AuditEvent and AuditEventType."""
from __future__ import annotations

from datetime import datetime, timezone

from core.audit.models import AuditCategory, AuditEvent, AuditEventType


class TestAuditEventType:
    """AuditEventType enum tests."""

    def test_all_values_are_strings(self) -> None:
        for member in AuditEventType:
            assert isinstance(member.value, str)

    def test_prefix_convention(self) -> None:
        """Every event type value is prefixed by its category."""
        for member in AuditEventType:
            prefix = member.value.split(".")[0]
            assert prefix in {c.value for c in AuditCategory}

    def test_auth_events_exist(self) -> None:
        assert AuditEventType.LOGIN_SUCCESS.value == "auth.login_success"
        assert AuditEventType.LOGIN_FAILED.value == "auth.login_failed"
        assert AuditEventType.REGISTER.value == "auth.register"
        assert AuditEventType.INVITE_CREATED.value == "auth.invite_created"
        assert AuditEventType.INVITE_REDEEMED.value == "auth.invite_redeemed"

    def test_hitl_events_exist(self) -> None:
        assert AuditEventType.HITL_DECISION.value == "hitl.decision"
        assert AuditEventType.HITL_DECISION_REJECTED.value == "hitl.decision_rejected"

    def test_pipeline_events_exist(self) -> None:
        assert AuditEventType.PIPELINE_STARTED.value == "pipeline.started"


class TestAuditEvent:
    """AuditEvent Pydantic model tests."""

    def test_default_timestamp(self) -> None:
        event = AuditEvent(event_type=AuditEventType.LOGIN_SUCCESS)
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_all_fields_have_defaults(self) -> None:
        """All fields except event_type must have defaults (backward compat rule)."""
        event = AuditEvent(event_type=AuditEventType.LOGIN_FAILED)
        assert event.user_id is None
        assert event.company_slug is None
        assert event.request_id is None
        assert event.correlation_id is None
        assert event.detail == {}

    def test_full_construction(self) -> None:
        ts = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        event = AuditEvent(
            event_type=AuditEventType.REGISTER,
            timestamp=ts,
            user_id="u-123",
            company_slug="ramp",
            request_id="req-abc",
            correlation_id="corr-xyz",
            detail={"role": "superuser", "company_name": "Ramp"},
        )
        assert event.event_type == AuditEventType.REGISTER
        assert event.timestamp == ts
        assert event.user_id == "u-123"
        assert event.company_slug == "ramp"
        assert event.detail["role"] == "superuser"

    def test_serialization_round_trip(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.HITL_DECISION,
            user_id="u-1",
            detail={"pipeline": "knowledge_base", "decision": "approve"},
        )
        data = event.model_dump(mode="json")
        restored = AuditEvent.model_validate(data)
        assert restored.event_type == event.event_type
        assert restored.user_id == event.user_id
        assert restored.detail == event.detail

    def test_detail_accepts_nested_dicts(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.PIPELINE_STARTED,
            detail={"params": {"product_slug": "cards", "force_rerun": True}},
        )
        assert event.detail["params"]["product_slug"] == "cards"
