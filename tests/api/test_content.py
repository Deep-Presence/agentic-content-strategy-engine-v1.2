"""Tests for content generation API endpoints."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


@pytest.fixture
def mock_content_runner():
    """Mock the content runner to complete instantly."""
    with patch(
        "api.routers.content.run_content_pipeline_task",
        new_callable=AsyncMock,
    ) as mock_fn:
        async def _complete_task(task_id, **kwargs):
            task_store = kwargs["task_store"]
            event_bus = kwargs["event_bus"]
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content"})
            task_store.update_task(task_id, status=TaskStatus.COMPLETED, result={"pieces": []})
            event_bus.publish(task_id, "completed", {"pipeline": "content"})

        mock_fn.side_effect = _complete_task
        yield mock_fn


class TestStartContent:
    def test_returns_run_id(self, client: TestClient, mock_content_runner) -> None:
        resp = client.post(
            "/api/v1/content/start",
            json={
                "input_data": {
                    "company_name": "Ramp",
                    "domain": "ramp.com",
                },
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "content"
        assert data["company_slug"] == "ramp"
        assert data["status"] == "running"

    def test_validation_error(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/content/start",
            json={"input_data": {}},
        )
        assert resp.status_code == 422

    def test_slug_conflict(
        self, client: TestClient, task_store: TaskStore, mock_content_runner
    ) -> None:
        task_store.create_task("content", "ramp")
        resp = client.post(
            "/api/v1/content/start",
            json={
                "input_data": {
                    "company_name": "Ramp",
                    "domain": "ramp.com",
                },
            },
        )
        assert resp.status_code == 409

    def test_auto_approve_param(self, client: TestClient, mock_content_runner) -> None:
        resp = client.post(
            "/api/v1/content/start",
            json={
                "input_data": {
                    "company_name": "Ramp",
                    "domain": "ramp.com",
                    "auto_approve": True,
                },
            },
        )
        assert resp.status_code == 202


class TestContentStatus:
    def test_status_after_start(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("content", "ramp")
        resp = client.get(f"/api/v1/content/{task.task_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "ramp"

    def test_completed_status(
        self, client: TestClient, mock_content_runner
    ) -> None:
        resp = client.post(
            "/api/v1/content/start",
            json={
                "input_data": {"company_name": "Ramp", "domain": "ramp.com"},
            },
        )
        run_id = resp.json()["run_id"]
        time.sleep(0.3)

        status_resp = client.get(f"/api/v1/content/{run_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/content/nonexistent-id/status")
        assert resp.status_code == 404


class TestContentApproval:
    def test_approve_pending_task(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task = task_store.create_task("content", "ramp")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "review", "briefs": []},
        )

        resp = client.post(
            f"/api/v1/content/{task.task_id}/approve",
            json={"brief_id": "brief-1", "decision": "approve"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approve"

    def test_approve_with_editor_notes(
        self, client: TestClient, task_store: TaskStore, event_bus: EventBus
    ) -> None:
        task = task_store.create_task("content", "ramp")
        task_store.update_task(
            task.task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": "review"},
        )

        resp = client.post(
            f"/api/v1/content/{task.task_id}/approve",
            json={
                "brief_id": "brief-1",
                "decision": "edit",
                "editor_notes": "Add more examples",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "edit"

    def test_approve_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/content/nonexistent/approve",
            json={"brief_id": "brief-1", "decision": "approve"},
        )
        assert resp.status_code == 404

    def test_approve_non_pending_returns_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("content", "ramp")
        resp = client.post(
            f"/api/v1/content/{task.task_id}/approve",
            json={"brief_id": "brief-1", "decision": "approve"},
        )
        assert resp.status_code == 409
