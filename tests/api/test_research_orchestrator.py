"""Tests for Research Orchestrator API endpoints.

Covers: start, status, auth, tenant isolation.
HITL approvals reuse existing per-pipeline endpoints (KB, AP, VSG).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from tests._support.model_config_service import FailingModelConfigService


# ── Constants ─────────────────────────────────────────────────────────

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}

PREFIX = "/api/v1/research"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_orchestrator_runner():
    """Mock the orchestrator runner to complete instantly."""
    with patch(
        # F12 lesson: patch at point-of-use
        "api.routers.research_orchestrator.run_research_orchestrator_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {
                "pipeline": "research_orchestrator",
            })
            task_store.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "orchestrator_status": "completed",
                    "pipelines_run": ["kb", "ap", "vsg"],
                },
            )
            event_bus.publish(task_id, "completed", {
                "pipeline": "research_orchestrator",
            })

        mock_fn.side_effect = _complete_task
        yield mock_fn


# ═══════════════════════════════════════════════════════════════════════
# POST /start
# ═══════════════════════════════════════════════════════════════════════


class TestStartResearchOrchestrator:
    """Tests for POST /api/v1/research/start."""

    def test_start_success(self, client, mock_orchestrator_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert data["pipeline"] == "research_orchestrator"
        assert data["status"] in ("started", "running")
        assert "run_id" in data

    def test_start_returns_run_id(self, client, mock_orchestrator_runner):
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.json()["run_id"]

    def test_start_requires_auth(self, public_client):
        resp = public_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code in (401, 403)

    def test_start_tenant_isolation(self, client):
        """Cannot start pipeline for a different company."""
        resp = client.post(
            f"{PREFIX}/start",
            json={"company_name": "Other Corp", "domain": "other.com"},
        )
        assert resp.status_code == 403

    def test_start_with_auto_approve(self, client, mock_orchestrator_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={
                **MINIMAL_PAYLOAD,
                "auto_approve": {"kb": [1, 2, 3], "ap": [1, 2], "vsg": [1]},
            },
        )
        assert resp.status_code == 202

    def test_start_with_selective_pipelines(self, client, mock_orchestrator_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "pipelines": ["kb", "ap"]},
        )
        assert resp.status_code == 202

    def test_start_with_force_rerun(self, client, mock_orchestrator_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202

    def test_start_invalid_pipelines_value(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "pipelines": ["invalid"]},
        )
        assert resp.status_code == 422

    def test_start_invalid_max_personas(self, client):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_personas": 1},
        )
        assert resp.status_code == 422

    def test_start_invalid_product_slug_path_traversal(self, client):
        """product_slug with path traversal must be rejected (Codex Fix #2)."""
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "../evil"},
        )
        assert resp.status_code == 422

    def test_start_invalid_product_slug_uppercase(self, client):
        """product_slug with uppercase must be rejected (Codex Fix #2)."""
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "BadSlug"},
        )
        assert resp.status_code == 422

    def test_start_max_authors_above_vsg_limit(self, client):
        """max_authors > VSG_MAX_AUTHORS_LIMIT (3) must be rejected (Codex Fix #4)."""
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "max_authors": 5},
        )
        assert resp.status_code == 422

    def test_start_with_product_slug(self, client, mock_orchestrator_runner):
        resp = client.post(
            f"{PREFIX}/start",
            json={**MINIMAL_PAYLOAD, "product_slug": "expense"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["effective_slug"] == "test-co__expense"

    def test_missing_byok_config_blocks_start_before_task_creation(self, client):
        service = FailingModelConfigService()
        client.app.state.model_config_service = service

        with patch(
            "api.routers.research_orchestrator.create_task_durable",
            new_callable=AsyncMock,
        ) as create_task:
            resp = client.post(
                f"{PREFIX}/start",
                json={**MINIMAL_PAYLOAD, "pipelines": ["kb", "vsg"]},
            )

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == "byok_model_config_required"
        assert detail["missing_credential"] is True
        assert detail["reason"] == "model_config_required"
        assert "research.kb.company_overview" in detail["required_agent_keys"]
        assert "research.vsg.author_discovery" in detail["required_agent_keys"]
        assert "research.ap.suggester" not in detail["required_agent_keys"]
        assert "research.vsg.author_discovery" in service.preflight_calls[0][1]
        create_task.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════
# GET /{run_id}/status
# ═══════════════════════════════════════════════════════════════════════


class TestResearchOrchestratorStatus:
    """Tests for GET /api/v1/research/{run_id}/status."""

    def test_status_after_completion(self, client, mock_orchestrator_runner):
        # Start the orchestrator
        start_resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        run_id = start_resp.json()["run_id"]

        # Check status
        resp = client.get(f"{PREFIX}/{run_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["pipeline"] == "research_orchestrator"
        assert data["status"] == "completed"

    def test_status_cross_tenant_denied(self, client, task_store):
        """Status for a task owned by another company must return 403 (Codex Fix #1)."""
        task = task_store.create_task(
            pipeline="research_orchestrator",
            company_slug="other-co",
        )
        resp = client.get(f"{PREFIX}/{task.task_id}/status")
        assert resp.status_code == 403

    def test_status_not_found(self, client):
        resp = client.get(f"{PREFIX}/nonexistent-id/status")
        assert resp.status_code == 404

    def test_status_requires_auth(self, public_client):
        resp = public_client.get(f"{PREFIX}/some-id/status")
        assert resp.status_code in (401, 403)
