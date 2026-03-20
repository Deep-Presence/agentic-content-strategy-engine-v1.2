"""Tests for task management API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


class TestListTasks:
    def test_list_all_tasks(self, client: TestClient, task_store: TaskStore) -> None:
        task_store.create_task("gap_analysis", "test-co")
        task_store.release_slug_lock("gap_analysis:test-co")
        task_store.create_task("research", "test-co")

        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 2

    def test_filter_by_pipeline(self, client: TestClient, task_store: TaskStore) -> None:
        task_store.create_task("gap_analysis", "test-co")
        task_store.release_slug_lock("gap_analysis:test-co")
        task_store.create_task("research", "test-co")

        resp = client.get("/api/v1/tasks?pipeline=gap_analysis")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["pipeline"] == "gap_analysis"

    def test_filter_by_status(self, client: TestClient, task_store: TaskStore) -> None:
        t1 = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(t1.task_id, status=TaskStatus.COMPLETED)
        task_store.release_slug_lock("gap_analysis:test-co")
        t2 = task_store.create_task("research", "test-co")

        resp = client.get("/api/v1/tasks?status=completed")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["status"] == "completed"

    def test_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []


class TestGetTask:
    def test_get_task_detail(self, client: TestClient, task_store: TaskStore) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        resp = client.get(f"/api/v1/tasks/{task.task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == task.task_id
        assert data["pipeline"] == "gap_analysis"
        assert data["company_slug"] == "test-co"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tasks/nonexistent")
        assert resp.status_code == 404


class TestCancelTask:
    def test_cancel_running_task(self, client: TestClient, task_store: TaskStore) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        resp = client.post(f"/api/v1/tasks/{task.task_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify task is actually cancelled
        updated = task_store.get_task(task.task_id)
        assert updated.status == TaskStatus.CANCELLED

    def test_cancel_pending_approval_task(self, client: TestClient, task_store: TaskStore) -> None:
        task = task_store.create_task("research", "test-co")
        task_store.update_task(task.task_id, status=TaskStatus.PENDING_APPROVAL)

        resp = client.post(f"/api/v1/tasks/{task.task_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_completed_returns_409(self, client: TestClient, task_store: TaskStore) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(task.task_id, status=TaskStatus.COMPLETED)

        resp = client.post(f"/api/v1/tasks/{task.task_id}/cancel")
        assert resp.status_code == 409

    def test_cancel_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/tasks/nonexistent/cancel")
        assert resp.status_code == 404
