"""Task API workspace tenant isolation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
class TestTasksWorkspaceScope:
    def test_list_tasks_scoped_to_workspace_slug(self, client: TestClient, task_store) -> None:
        task_store.create_task("gap_analysis", "test-co")
        task_store.create_task("gap_analysis", "other-co")

        resp = client.get("/api/v1/tasks", params={"workspace_slug": "test-co"})
        assert resp.status_code == 200
        slugs = {t["company_slug"] for t in resp.json()["tasks"]}
        assert slugs == {"test-co"}

    def test_get_task_cross_workspace_denied(
        self, client: TestClient, auth_store, task_store
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.co")
        task = task_store.create_task("gap_analysis", "other-co")
        resp = client.get(
            f"/api/v1/tasks/{task.task_id}",
            params={"workspace_slug": "test-co"},
        )
        assert resp.status_code == 403

    def test_cancel_task_requires_write_role(
        self, app, viewer_client: TestClient, task_store
    ) -> None:
        task = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(task.task_id, status=TaskStatus.RUNNING)

        resp = viewer_client.post(
            f"/api/v1/tasks/{task.task_id}/cancel",
            params={"workspace_slug": "test-co"},
        )
        assert resp.status_code == 403
