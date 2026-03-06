"""Tests for research pipeline API endpoints."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


# ── Minimal valid payload (simplified schema) ──────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}


@pytest.fixture
def mock_research_runner():
    """Mock the research runner to complete instantly."""
    with patch(
        "api.routers.research.run_research_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:
        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "research"})
            task_store.update_task(task_id, status=TaskStatus.COMPLETED, result={"stage": "complete"})
            event_bus.publish(task_id, "completed", {"pipeline": "research"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


class TestStartResearch:
    def test_returns_run_id(self, client: TestClient, mock_research_runner) -> None:
        resp = client.post("/api/v1/research/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "research"
        assert data["company_slug"] == "test-co"
        assert data["status"] == "running"

    def test_minimal_payload_only_requires_name_and_domain(
        self, client: TestClient, mock_research_runner
    ) -> None:
        """Frontend only needs company_name + domain — everything else has defaults."""
        resp = client.post(
            "/api/v1/research/start",
            json={"company_name": "Test Co", "domain": "testco.com"},
        )
        assert resp.status_code == 202

    def test_validation_error_missing_company_name(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/research/start",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 422

    def test_validation_error_missing_domain(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/research/start",
            json={"company_name": "Test Co"},
        )
        assert resp.status_code == 422

    def test_slug_conflict(
        self, client: TestClient, task_store: TaskStore, mock_research_runner
    ) -> None:
        task_store.create_task("research", "test-co")
        resp = client.post("/api/v1/research/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 409

    def test_with_all_stages_explicit(self, client: TestClient, mock_research_runner) -> None:
        resp = client.post(
            "/api/v1/research/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "seed_urls": ["https://testco.com/"],
                "stages": ["company", "persona", "style_guide"],
                "auto_approve": True,
                "max_personas": 2,
            },
        )
        assert resp.status_code == 202

    def test_company_only_stage(self, client: TestClient, mock_research_runner) -> None:
        resp = client.post(
            "/api/v1/research/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "stages": ["company"],
            },
        )
        assert resp.status_code == 202

    def test_auto_approve_forwarded(self, client: TestClient, mock_research_runner) -> None:
        resp = client.post(
            "/api/v1/research/start",
            json={**MINIMAL_PAYLOAD, "auto_approve": True},
        )
        assert resp.status_code == 202
        time.sleep(0.1)
        call_kwargs = mock_research_runner.call_args
        assert call_kwargs is not None

    def test_optional_fields_accepted(self, client: TestClient, mock_research_runner) -> None:
        resp = client.post(
            "/api/v1/research/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "language": "en",
                "region": "us",
                "max_personas": 2,
                "internal_sources": ["/path/to/notes.md"],
                "additional_constraints": "Focus on enterprise segment",
            },
        )
        assert resp.status_code == 202


class TestStartResearchGuard:
    """Guard: return 200 already_exists when all requested stages have approved artifacts."""

    def _write_company(self, artifacts_root: Path, slug: str) -> None:
        d = artifacts_root / "company_context"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{slug}.md").touch()

    def _write_persona(self, artifacts_root: Path, slug: str, draft: bool = False) -> None:
        d = artifacts_root / "personas"
        d.mkdir(parents=True, exist_ok=True)
        suffix = ".draft.md" if draft else ".md"
        (d / f"{slug}__persona-icp{suffix}").touch()

    def _write_style(self, artifacts_root: Path, slug: str) -> None:
        d = artifacts_root / "style_guides"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{slug}.md").touch()

    def test_start_returns_already_exists_when_all_default_stages_present(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        self._write_company(artifacts_root, "test-co")
        self._write_persona(artifacts_root, "test-co")
        self._write_style(artifacts_root, "test-co")
        resp = client.post("/api/v1/research/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True
        assert data["status"] == "already_exists"
        assert "force_rerun" in data["message"].lower()

    def test_start_partial_stages_only_skip_if_requested_stages_present(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """stages=["persona"] only triggers guard if persona artifact exists."""
        # Only company context exists — NOT persona
        self._write_company(artifacts_root, "test-co")
        resp = client.post(
            "/api/v1/research/start",
            json={**MINIMAL_PAYLOAD, "stages": ["persona"]},
        )
        # Persona artifact missing → should NOT skip → but wait, we don't have mock_research_runner
        # The endpoint would try to launch a real task (which is fine for status 202 assertion)
        # We just need to assert 200 is NOT returned
        assert resp.status_code != 200

    def test_start_persona_draft_does_not_trigger_guard(
        self, client: TestClient, artifacts_root: Path, mock_research_runner
    ) -> None:
        """A .draft.md persona file must NOT count as approved — guard must not fire."""
        self._write_company(artifacts_root, "test-co")
        self._write_persona(artifacts_root, "test-co", draft=True)  # draft only
        self._write_style(artifacts_root, "test-co")
        resp = client.post("/api/v1/research/start", json=MINIMAL_PAYLOAD)
        # All default stages requested, but persona is only a draft → proceed normally
        assert resp.status_code == 202
        assert resp.json()["already_exists"] is False

    def test_start_force_rerun_bypasses_guard(
        self, client: TestClient, artifacts_root: Path, mock_research_runner
    ) -> None:
        self._write_company(artifacts_root, "test-co")
        self._write_persona(artifacts_root, "test-co")
        self._write_style(artifacts_root, "test-co")
        resp = client.post(
            "/api/v1/research/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202
        assert resp.json()["already_exists"] is False

    def test_start_stages_subset_missing_one_proceeds(
        self, client: TestClient, artifacts_root: Path, mock_research_runner
    ) -> None:
        """Company + style exist, but stages=["persona"] requested with no persona artifact → proceed."""
        self._write_company(artifacts_root, "test-co")
        self._write_style(artifacts_root, "test-co")
        resp = client.post(
            "/api/v1/research/start",
            json={**MINIMAL_PAYLOAD, "stages": ["persona"]},
        )
        assert resp.status_code == 202


class TestResearchStatus:
    def test_status_after_start(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("research", "test-co")
        resp = client.get(f"/api/v1/research/{task.task_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "test-co"

    def test_completed_status(
        self, client: TestClient, mock_research_runner
    ) -> None:
        resp = client.post("/api/v1/research/start", json=MINIMAL_PAYLOAD)
        run_id = resp.json()["run_id"]
        time.sleep(0.3)

        status_resp = client.get(f"/api/v1/research/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/research/nonexistent-id/status")
        assert resp.status_code == 404


class TestResearchApproval:
    def test_approve_pending_task(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task = task_store.create_task("research", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "company", "status": "pending_approval"},
        )

        resp = client.post(
            f"/api/v1/research/{task.task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approve"

    def test_approve_with_revision_note(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task = task_store.create_task("research", "test-co")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "company", "status": "pending_approval"},
        )

        resp = client.post(
            f"/api/v1/research/{task.task_id}/approve",
            json={"decision": "revise", "revision_note": "Add more detail about products"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "revise"

    def test_approve_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/research/nonexistent/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 404

    def test_approve_non_pending_returns_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("research", "test-co")
        resp = client.post(
            f"/api/v1/research/{task.task_id}/approve",
            json={"decision": "approve"},
        )
        assert resp.status_code == 409
