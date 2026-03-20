"""Integration tests — auth endpoints emit correct audit events."""
from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.audit.logger import get_sink, set_sink
from core.audit.models import AuditEvent, AuditEventType
from core.audit.sink import NoOpAuditSink


# ── Capture sink ──────────────────────────────────────────


class _CaptureSink:
    """Test sink that records persisted audit events."""

    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    async def persist(self, event: AuditEvent) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _audit_sink():
    """Install a capture sink for the duration of each test."""
    sink = _CaptureSink()
    original = get_sink()
    set_sink(sink)
    yield sink
    set_sink(original if not isinstance(original, _CaptureSink) else NoOpAuditSink())


# ── Helpers ───────────────────────────────────────────────

_REG_PAYLOAD = {
    "first_name": "Alice",
    "last_name": "Audit",
    "email": "alice@auditco.com",
    "password": "securepass123",
    "company_name": "Audit Co",
    "company_domain": "auditco.com",
}


def _events_of_type(sink: _CaptureSink, event_type: AuditEventType) -> List[AuditEvent]:
    return [e for e in sink.events if e.event_type == event_type]


# ── Register ──────────────────────────────────────────────


class TestAuditRegister:
    def test_register_emits_audit_event(self, client: TestClient, _audit_sink: _CaptureSink) -> None:
        resp = client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        assert resp.status_code == 201

        events = _events_of_type(_audit_sink, AuditEventType.REGISTER)
        assert len(events) == 1
        evt = events[0]
        assert evt.user_id is not None
        assert evt.company_slug == "audit-co"
        assert evt.detail["role"] == "superuser"
        assert evt.detail["company_name"] == "Audit Co"

    def test_register_conflict_no_audit(self, client: TestClient, _audit_sink: _CaptureSink) -> None:
        """Domain conflict (409) should not emit a REGISTER event."""
        client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        _audit_sink.events.clear()

        resp = client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        assert resp.status_code == 409

        register_events = _events_of_type(_audit_sink, AuditEventType.REGISTER)
        assert len(register_events) == 0


# ── Login Success ─────────────────────────────────────────


class TestAuditLoginSuccess:
    def test_login_success_emits_audit_event(self, client: TestClient, _audit_sink: _CaptureSink) -> None:
        client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        _audit_sink.events.clear()

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@auditco.com", "password": "securepass123"},
        )
        assert resp.status_code == 200

        events = _events_of_type(_audit_sink, AuditEventType.LOGIN_SUCCESS)
        assert len(events) == 1
        evt = events[0]
        assert evt.user_id is not None
        assert evt.company_slug == "audit-co"
        assert evt.detail.get("email") == "alice@auditco.com"


# ── Login Failed ──────────────────────────────────────────


class TestAuditLoginFailed:
    def test_wrong_password_emits_failed(self, client: TestClient, _audit_sink: _CaptureSink) -> None:
        client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        _audit_sink.events.clear()

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@auditco.com", "password": "wrongpass123"},
        )
        assert resp.status_code == 401

        events = _events_of_type(_audit_sink, AuditEventType.LOGIN_FAILED)
        assert len(events) == 1
        assert events[0].detail["reason"] == "invalid_credentials"

    def test_nonexistent_user_emits_failed(self, client: TestClient, _audit_sink: _CaptureSink) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.com", "password": "securepass123"},
        )
        assert resp.status_code == 401

        events = _events_of_type(_audit_sink, AuditEventType.LOGIN_FAILED)
        assert len(events) == 1
        assert events[0].detail["reason"] == "invalid_credentials"
        # No user_id for nonexistent user
        assert events[0].user_id is None

    def test_failed_login_uses_same_reason_for_both_cases(
        self, client: TestClient, _audit_sink: _CaptureSink
    ) -> None:
        """Both 'not found' and 'wrong pw' use 'invalid_credentials' to prevent enumeration."""
        client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        _audit_sink.events.clear()

        # Wrong password
        client.post(
            "/api/v1/auth/login",
            json={"email": "alice@auditco.com", "password": "wrongpass123"},
        )
        # Nonexistent
        client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@auditco.com", "password": "whatever1234"},
        )

        events = _events_of_type(_audit_sink, AuditEventType.LOGIN_FAILED)
        assert len(events) == 2
        reasons = {e.detail["reason"] for e in events}
        assert reasons == {"invalid_credentials"}


# ── Invite Created ────────────────────────────────────────


class TestAuditInviteCreated:
    def test_invite_created_emits_audit(self, superuser_client: TestClient, _audit_sink: _CaptureSink) -> None:
        _audit_sink.events.clear()
        resp = superuser_client.post("/api/v1/auth/invite", json={"role": "member"})
        assert resp.status_code == 201

        events = _events_of_type(_audit_sink, AuditEventType.INVITE_CREATED)
        assert len(events) == 1
        evt = events[0]
        assert evt.user_id is not None
        assert evt.company_slug == "test-co"
        assert evt.detail["role"] == "member"


# ── Invite Redeemed (Join) ────────────────────────────────


class TestAuditInviteRedeemed:
    def test_join_emits_invite_redeemed(
        self, superuser_client: TestClient, public_client: TestClient, _audit_sink: _CaptureSink
    ) -> None:
        inv_resp = superuser_client.post("/api/v1/auth/invite", json={"role": "member"})
        code = inv_resp.json()["invite_code"]
        _audit_sink.events.clear()

        resp = public_client.post(
            "/api/v1/auth/join",
            json={
                "invite_code": code,
                "first_name": "Bob",
                "last_name": "Joiner",
                "email": "bob@testco.com",
                "password": "joinerpass123",
            },
        )
        assert resp.status_code == 201

        events = _events_of_type(_audit_sink, AuditEventType.INVITE_REDEEMED)
        assert len(events) == 1
        evt = events[0]
        assert evt.user_id is not None
        assert evt.company_slug == "test-co"
        assert evt.detail["role"] == "member"
