"""Tests for Onboarding Pipeline Orchestrator API endpoints.

Covers: POST /start, GET /{run_id}/status, auth, tenant isolation, validation.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


# ── Constants ─────────────────────────────────────────────────────────

MINIMAL_PAYLOAD: dict = {}  # No required fields — company resolved from auth

PREFIX = "/api/v1/onboarding"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_onboarding_runner():
    """Mock the onboarding runner to complete instantly."""
    with patch(
        "api.routers.onboarding.run_onboarding_task",
        new_callable=AsyncMock,
    ) as mock_fn:

        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "onboarding_start", {
                "pipeline": "onboarding",
            })
            task_store.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "onboarding_status": "completed",
                    "phases": {
                        "phase_a": {"status": "completed"},
                        "phase_b": {"status": "completed"},
                        "phase_c": {"status": "completed"},
                    },
                },
            )
            event_bus.publish(task_id, "completed", {
                "pipeline": "onboarding",
            })

        mock_fn.side_effect = _complete_task
        yield mock_fn


# ═══════════════════════════════════════════════════════════════════════
# POST /start
# ═══════════════════════════════════════════════════════════════════════


class TestStartOnboarding:
    """Tests for POST /api/v1/onboarding/start."""

    def test_start_success(self, superuser_client, mock_onboarding_runner):
        resp = superuser_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert data["pipeline"] == "onboarding"
        assert data["status"] in ("started", "running")
        assert "run_id" in data
        assert data["company_slug"] == "test-co"

    def test_start_returns_run_id(self, superuser_client, mock_onboarding_runner):
        resp = superuser_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.json()["run_id"]

    def test_start_requires_auth(self, public_client):
        resp = public_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code in (401, 403)

    def test_start_requires_superuser_role(self, client):
        """Member role cannot start onboarding — superuser required."""
        resp = client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 403

    def test_start_viewer_denied(self, viewer_client):
        """Viewer role cannot start onboarding."""
        resp = viewer_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 403

    def test_start_with_industry(self, superuser_client, mock_onboarding_runner):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={"industry": "Fintech"},
        )
        assert resp.status_code == 202

    def test_start_with_seed_personas(self, superuser_client, mock_onboarding_runner):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={"seed_personas": ["VP Engineering", "CTO", "Head of Product"]},
        )
        assert resp.status_code == 202

    def test_start_with_full_config(self, superuser_client, mock_onboarding_runner):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={
                "industry": "SaaS",
                "seed_personas": ["VP Eng", "CTO"],
                "seed_urls": ["https://example.com/blog"],
                "max_pages": 100,
                "max_depth": 3,
                "max_personas": 4,
                "max_authors": 2,
                "max_queries": 50,
                "platforms": ["perplexity", "openai"],
                "language": "en",
                "region": "US",
            },
        )
        assert resp.status_code == 202

    def test_start_invalid_max_personas(self, superuser_client):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={"max_personas": 1},
        )
        assert resp.status_code == 422

    def test_start_invalid_max_pages(self, superuser_client):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={"max_pages": 5},
        )
        assert resp.status_code == 422

    def test_start_invalid_max_queries_too_high(self, superuser_client):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={"max_queries": 1000},
        )
        assert resp.status_code == 422

    def test_start_industry_too_long(self, superuser_client):
        resp = superuser_client.post(
            f"{PREFIX}/start",
            json={"industry": "x" * 201},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /{run_id}/status
# ═══════════════════════════════════════════════════════════════════════


class TestOnboardingStatus:
    """Tests for GET /api/v1/onboarding/{run_id}/status."""

    def test_status_after_completion(self, superuser_client, mock_onboarding_runner):
        start_resp = superuser_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        run_id = start_resp.json()["run_id"]

        resp = superuser_client.get(f"{PREFIX}/{run_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["pipeline"] == "onboarding"
        assert data["status"] == "completed"

    def test_status_accessible_by_member(self, superuser_client, client, mock_onboarding_runner):
        """Member can check status (require_auth, not require_role)."""
        start_resp = superuser_client.post(f"{PREFIX}/start", json=MINIMAL_PAYLOAD)
        run_id = start_resp.json()["run_id"]

        resp = client.get(f"{PREFIX}/{run_id}/status")
        assert resp.status_code == 200

    def test_status_cross_tenant_denied(self, client, task_store):
        """Status for a task owned by another company must return 403."""
        task = task_store.create_task(
            pipeline="onboarding",
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
