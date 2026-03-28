"""Integration tests — HITL endpoints emit correct audit events."""
from __future__ import annotations

from typing import List

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from core.audit.logger import get_sink, set_sink
from core.audit.models import AuditEvent, AuditEventType
from core.audit.sink import NoOpAuditSink


# ── Capture sink ──────────────────────────────────────────


class _CaptureSink:
    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    async def persist(self, event: AuditEvent) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _audit_sink():
    sink = _CaptureSink()
    original = get_sink()
    set_sink(sink)
    yield sink
    set_sink(original if not isinstance(original, _CaptureSink) else NoOpAuditSink())


def _hitl_events(sink: _CaptureSink) -> List[AuditEvent]:
    return [e for e in sink.events if e.event_type == AuditEventType.HITL_DECISION]


def _rejected_events(sink: _CaptureSink) -> List[AuditEvent]:
    return [e for e in sink.events if e.event_type == AuditEventType.HITL_DECISION_REJECTED]


# ── Helper: put task in PENDING_APPROVAL ──────────────────


def _pending_task(
    task_store,
    pipeline: str,
    stage: str,
    slug: str = "test-co",
    *,
    extra_payload: dict | None = None,
) -> str:
    """Create task and set to PENDING_APPROVAL. Returns task_id."""
    task = task_store.create_task(pipeline, slug)
    payload: dict = {"stage": stage, "status": "pending_approval"}
    if extra_payload:
        payload.update(extra_payload)
    task_store.update_task(
        task.task_id,
        status=TaskStatus.PENDING_APPROVAL,
        approval_payload=payload,
    )
    return task.task_id


# ── Knowledge Base HITL ───────────────────────────────────


class TestKBApproveAudit:
    def test_approve_emits_hitl_event(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "knowledge_base", "kb_checkpoint_1")
        resp = client.post(
            f"/api/v1/knowledge-base/{task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        evt = events[0]
        assert evt.detail["pipeline"] == "knowledge_base"
        assert evt.detail["stage"] == "kb_checkpoint_1"
        assert evt.detail["decision"] == "approve"
        assert evt.detail["run_id"] == task_id
        assert evt.user_id is not None
        assert evt.company_slug == "test-co"

    def test_revise_emits_hitl_event(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "knowledge_base", "kb_checkpoint_2")
        resp = client.post(
            f"/api/v1/knowledge-base/{task_id}/approve",
            json={"decision": "revise", "revision_note": "More detail please"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["decision"] == "revise"
        assert events[0].detail["revision_note_provided"] is True

    def test_stale_nonce_emits_rejected(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "knowledge_base", "kb_checkpoint_1")
        # First approval succeeds
        client.post(
            f"/api/v1/knowledge-base/{task_id}/approve",
            json={"decision": "approve"},
        )
        _audit_sink.events.clear()

        # Second approval → 409 (stale nonce)
        resp = client.post(
            f"/api/v1/knowledge-base/{task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 409

        rejected = _rejected_events(_audit_sink)
        assert len(rejected) == 1
        assert rejected[0].detail["decision"] == "rejected"
        assert "reason" in rejected[0].detail


# ── Content v1.3 HITL (prefix: /api/v1/content/v13) ──────


class TestContentV13ApproveAudit:
    def test_topic_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "content_v13", "topic_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task_id}/approve/topics",
            json={"decision": "approve", "approved_topic_ranks": [0, 1, 2]},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "content_v13"
        assert events[0].detail["stage"] == "topic_approval"

    def test_brief_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "content_v13", "brief_approval")
        resp = client.post(
            f"/api/v1/content/v13/{task_id}/approve/briefs",
            json={"decision": "approve", "brief_id": "brief-001"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "content_v13"
        assert events[0].detail["brief_id"] == "brief-001"

    def test_content_review_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "content_v13", "content_review")
        resp = client.post(
            f"/api/v1/content/v13/{task_id}/approve/content",
            json={"decision": "approve", "brief_id": "brief-001"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["stage"] == "content_review"


# ── Topic Discovery HITL ─────────────────────────────────


class TestTopicDiscoveryApproveAudit:
    def test_taxonomy_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(
            task_store, "topic_discovery", "td_taxonomy_review",
            extra_payload={"checkpoint_nonce": "test-nonce"},
        )
        resp = client.post(
            f"/api/v1/topic-discovery/{task_id}/approve/taxonomy",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "topic_discovery"
        assert events[0].detail["stage"] == "td_taxonomy_review"

    def test_subdomain_selection_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(
            task_store, "topic_discovery", "td_subdomain_selection",
            extra_payload={"checkpoint_nonce": "test-nonce"},
        )
        resp = client.post(
            f"/api/v1/topic-discovery/{task_id}/approve/subdomains",
            json={"batch_decision": "select", "selected_subdomain_ids": ["sd-1"]},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["stage"] == "td_subdomain_selection"

    def test_matrix_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(
            task_store, "topic_discovery", "td_matrix_review",
            extra_payload={"checkpoint_nonce": "test-nonce"},
        )
        resp = client.post(
            f"/api/v1/topic-discovery/{task_id}/approve/matrix",
            json={"batch_decision": "approve"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["stage"] == "td_matrix_review"


# ── Audience Persona HITL ─────────────────────────────────


class TestAudiencePersonaApproveAudit:
    def test_brief_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "audience_persona", "persona_brief_review")
        resp = client.post(
            f"/api/v1/audience-persona/{task_id}/approve/briefs",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "audience_persona"
        assert events[0].detail["stage"] == "persona_brief_review"

    def test_profile_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "audience_persona", "persona_profile_review")
        resp = client.post(
            f"/api/v1/audience-persona/{task_id}/approve/profiles",
            json={"profile_reviews": [{"persona_id": "test-persona", "decision": "approve"}]},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["stage"] == "persona_profile_review"


# ── Voice Style Guide HITL ────────────────────────────────


class TestVSGApproveAudit:
    def test_author_approval_emits_hitl(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_id = _pending_task(task_store, "voice_style_guide", "vsg_author_review")
        resp = client.post(
            f"/api/v1/voice-style-guide/{task_id}/approve/authors",
            json={"batch_decision": "approve_all"},
        )
        assert resp.status_code == 200

        events = _hitl_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "voice_style_guide"
        assert events[0].detail["stage"] == "vsg_author_review"
