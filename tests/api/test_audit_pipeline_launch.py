"""Integration tests — pipeline start endpoints emit correct audit events."""
from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

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


def _launch_events(sink: _CaptureSink) -> List[AuditEvent]:
    return [e for e in sink.events if e.event_type == AuditEventType.PIPELINE_STARTED]


# ── Common payload ────────────────────────────────────────

_START_PAYLOAD = {"company_name": "Test Co", "domain": "testco.com"}


# ── Gap Analysis (/api/v1/gap-analysis) ───────────────────


class TestAuditGapAnalysisLaunch:
    @pytest.fixture
    def mock_gap(self):
        from core.models.gap_analysis import GapReport

        report = GapReport(
            report_md="# R",
            report_json={"executive_summary": "test"},
            generation_spec_md="# S",
            generation_spec_json={},
            visualization_paths=[],
        )
        with patch(
            "api.tasks.runner.run_gap_analysis",
            new_callable=AsyncMock,
            return_value=report,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_gap, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/gap-analysis/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        evt = events[0]
        assert evt.detail["pipeline"] == "gap_analysis"
        assert evt.user_id is not None
        assert evt.company_slug == "test-co"

    def test_already_exists_emits_pipeline_started(
        self, client: TestClient, artifacts_root: Path, _audit_sink: _CaptureSink
    ) -> None:
        d = artifacts_root / "gap_analysis" / "test-co"
        d.mkdir(parents=True)
        (d / "gap_analysis_complete.json").touch()

        resp = client.post("/api/v1/gap-analysis/start", json=_START_PAYLOAD)
        assert resp.status_code == 200

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["outcome"] == "already_exists"

    def test_conflict_409_no_audit(
        self, client: TestClient, task_store, _audit_sink: _CaptureSink
    ) -> None:
        task_store.create_task("gap_analysis", "test-co")
        _audit_sink.events.clear()

        resp = client.post("/api/v1/gap-analysis/start", json=_START_PAYLOAD)
        assert resp.status_code == 409

        events = _launch_events(_audit_sink)
        assert len(events) == 0


# ── Knowledge Base (/api/v1/knowledge-base) ───────────────


class TestAuditKBLaunch:
    @pytest.fixture
    def mock_kb(self):
        with patch(
            "api.routers.knowledge_base.run_kb_pipeline_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_kb, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/knowledge-base/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "knowledge_base"
        assert events[0].company_slug == "test-co"


# ── Audience Persona (/api/v1/audience-persona) ───────────


class TestAuditAPLaunch:
    @pytest.fixture
    def mock_ap(self):
        with patch(
            "api.routers.audience_persona.run_audience_persona_pipeline_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_ap, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/audience-persona/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "audience_persona"


# ── Voice Style Guide (/api/v1/voice-style-guide) ────────


class TestAuditVSGLaunch:
    @pytest.fixture
    def mock_vsg(self):
        with patch(
            "api.routers.voice_style_guide.run_voice_style_guide_pipeline_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_vsg, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/voice-style-guide/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "voice_style_guide"


# ── Topic Discovery (/api/v1/topic-discovery) ────────────


class TestAuditTDLaunch:
    @pytest.fixture
    def mock_td(self):
        with patch(
            "api.routers.topic_discovery.run_topic_discovery_pipeline_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_td, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/topic-discovery/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "topic_discovery"


# ── Content v1.3 (/api/v1/content/v13) ───────────────────


class TestAuditContentV13Launch:
    @pytest.fixture
    def mock_content(self):
        with patch(
            "api.routers.content_v13.run_content_v13_pipeline_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_content, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/content/v13/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "content_v13"


# ── Site Audit (/api/v1/site-audit) ──────────────────────


class TestAuditSiteAuditLaunch:
    @pytest.fixture
    def mock_sa(self):
        with patch(
            "api.routers.site_audit.run_site_audit_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_sa, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/site-audit/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "site_audit"


# ── Research Orchestrator (/api/v1/research-orchestrator) ─


class TestAuditResearchOrchestratorLaunch:
    @pytest.fixture
    def mock_ro(self):
        with patch(
            "api.routers.research_orchestrator.run_research_orchestrator_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, client: TestClient, mock_ro, _audit_sink: _CaptureSink
    ) -> None:
        resp = client.post("/api/v1/research/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "research_orchestrator"


# ── Onboarding (/api/v1/onboarding) ──────────────────────


class TestAuditOnboardingLaunch:
    @pytest.fixture
    def mock_onboard(self):
        with patch(
            "api.routers.onboarding.run_onboarding_task",
            new_callable=AsyncMock,
        ):
            yield

    def test_start_emits_pipeline_started(
        self, superuser_client: TestClient, mock_onboard, _audit_sink: _CaptureSink
    ) -> None:
        resp = superuser_client.post("/api/v1/onboarding/start", json=_START_PAYLOAD)
        assert resp.status_code == 202

        events = _launch_events(_audit_sink)
        assert len(events) == 1
        assert events[0].detail["pipeline"] == "onboarding"
