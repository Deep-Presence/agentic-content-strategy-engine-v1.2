"""Extended tests for task management — total field and company_slug filter."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


class TestTaskListTotal:
    """Verify the total field is included in TaskListResponse."""

    def test_total_matches_task_count(self, client: TestClient, task_store: TaskStore) -> None:
        task_store.create_task("gap_analysis", "test-co")
        task_store.release_slug_lock("test-co")
        task_store.create_task("research", "test-co")

        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["tasks"]) == 2

    def test_total_zero_when_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_total_reflects_filter(self, client: TestClient, task_store: TaskStore) -> None:
        task_store.create_task("gap_analysis", "test-co")
        task_store.release_slug_lock("test-co")
        task_store.create_task("research", "test-co")

        resp = client.get("/api/v1/tasks?pipeline=gap_analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


class TestTaskListCompanySlugFilter:
    """Verify the company_slug query parameter filters tasks."""

    def test_filter_by_company_slug(self, client: TestClient, task_store: TaskStore) -> None:
        task_store.create_task("gap_analysis", "test-co")
        task_store.release_slug_lock("test-co")
        task_store.create_task("research", "test-co")

        resp = client.get("/api/v1/tasks?company_slug=test-co")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(t["company_slug"] == "test-co" for t in data["tasks"])

    def test_company_slug_query_param_ignored_uses_auth(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        """company_slug query param is ignored — endpoint auto-filters by auth user's company."""
        task_store.create_task("gap_analysis", "test-co")

        # Even though we pass company_slug=nonexistent, the endpoint uses the
        # authenticated user's company_slug (test-co) from request.state
        resp = client.get("/api/v1/tasks?company_slug=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_combined_filters(self, client: TestClient, task_store: TaskStore) -> None:
        t1 = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(t1.task_id, status=TaskStatus.COMPLETED)
        task_store.release_slug_lock("test-co")
        task_store.create_task("research", "test-co")
        # Create a task for another company (won't be visible due to auto-filter)
        task_store.create_task("gap_analysis", "other-co")

        resp = client.get("/api/v1/tasks?company_slug=test-co&pipeline=gap_analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["tasks"][0]["company_slug"] == "test-co"
        assert data["tasks"][0]["pipeline"] == "gap_analysis"


class TestContentStartRequestExpanded:
    """Verify new ContentStartRequest fields are accepted."""

    def test_content_start_with_new_fields(self, client: TestClient) -> None:
        """Backend accepts the expanded ContentStartRequest fields.

        We don't actually run the pipeline (that requires real APIs),
        but we verify the request parsing doesn't fail.
        """
        resp = client.post(
            "/api/v1/content/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "max_briefs": 3,
                "auto_approve": False,
                "gap_slug": "test-co",
                "max_concurrent_workers": 5,
                "max_revision_cycles": 1,
                "skip_stages": [3, 4],
            },
        )
        # 202 Accepted or 409 Conflict (slug lock) — either means parsing worked
        assert resp.status_code in (202, 409)

    def test_content_start_without_new_fields_defaults(self, client: TestClient) -> None:
        """Old-style request without new fields should still work."""
        resp = client.post(
            "/api/v1/content/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
            },
        )
        assert resp.status_code in (202, 409)
