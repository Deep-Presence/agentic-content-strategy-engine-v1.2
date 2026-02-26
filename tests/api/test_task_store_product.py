"""Tests for product-aware task store: effective-slug locking and product_slug filter."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.tasks.models import TaskStatus
from api.tasks.store import TaskConflictError, TaskStore
from api.tasks.event_bus import EventBus


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    eb = EventBus()
    return TaskStore(base_dir=tmp_path / "_jobs", event_bus=eb)


class TestProductTaskCreation:
    """Task creation with product_slug."""

    def test_task_carries_product_slug(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp", product_slug="corporate-card")
        assert task.product_slug == "corporate-card"
        assert task.company_slug == "ramp"

    def test_task_effective_slug_product(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp", product_slug="corporate-card")
        assert task.effective_slug == "ramp__corporate-card"

    def test_task_effective_slug_company_level(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp")
        assert task.effective_slug == "ramp"
        assert task.product_slug is None

    def test_company_and_product_locks_are_independent(self, store: TaskStore) -> None:
        """Company-level run and product-level run can coexist."""
        t1 = store.create_task("gap_analysis", "ramp")
        t2 = store.create_task("gap_analysis", "ramp", product_slug="corporate-card")
        assert t1.effective_slug == "ramp"
        assert t2.effective_slug == "ramp__corporate-card"

    def test_two_product_runs_conflict(self, store: TaskStore) -> None:
        """Two runs for the same product slug must be blocked."""
        store.create_task("gap_analysis", "ramp", product_slug="corporate-card")
        with pytest.raises(TaskConflictError):
            store.create_task("gap_analysis", "ramp", product_slug="corporate-card")

    def test_different_products_coexist(self, store: TaskStore) -> None:
        """Different products under same company can run concurrently."""
        t1 = store.create_task("gap_analysis", "ramp", product_slug="corporate-card")
        t2 = store.create_task("gap_analysis", "ramp", product_slug="travel")
        assert t1.effective_slug != t2.effective_slug

    def test_task_persists_product_slug(self, tmp_path: Path) -> None:
        """product_slug and effective_slug survive JSON round-trip."""
        eb = EventBus()
        store1 = TaskStore(base_dir=tmp_path / "_jobs", event_bus=eb)
        task = store1.create_task("gap_analysis", "ramp", product_slug="card")

        # Reload from disk
        store2 = TaskStore(base_dir=tmp_path / "_jobs", event_bus=eb)
        recovered = store2.get_task(task.task_id)
        assert recovered.product_slug == "card"
        assert recovered.effective_slug == "ramp__card"


class TestProductSlugLockRelease:
    """Effective slug must be used for lock release."""

    def test_release_product_lock_allows_rerun(self, store: TaskStore) -> None:
        task = store.create_task("gap_analysis", "ramp", product_slug="card")
        store.update_task(task.task_id, status=TaskStatus.COMPLETED)
        store.release_slug_lock(task.effective_slug)

        # Should be able to create another task now
        t2 = store.create_task("gap_analysis", "ramp", product_slug="card")
        assert t2.effective_slug == "ramp__card"

    def test_company_lock_unaffected_by_product_lock_release(self, store: TaskStore) -> None:
        t_company = store.create_task("gap_analysis", "ramp")
        t_product = store.create_task("gap_analysis", "ramp", product_slug="card")

        # Release product lock
        store.release_slug_lock(t_product.effective_slug)

        # Company lock still held — new company run should conflict
        with pytest.raises(TaskConflictError):
            store.create_task("gap_analysis", "ramp")


class TestListTasksProductFilter:
    """list_tasks() product_slug filter."""

    def test_filter_by_product_slug(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp")
        store.create_task("gap_analysis", "ramp", product_slug="card")
        store.create_task("gap_analysis", "ramp", product_slug="travel")

        card_tasks = store.list_tasks(product_slug="card")
        assert len(card_tasks) == 1
        assert card_tasks[0].product_slug == "card"

    def test_filter_no_product_slug_includes_all(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp")
        store.create_task("gap_analysis", "ramp", product_slug="card")
        all_tasks = store.list_tasks()
        assert len(all_tasks) == 2

    def test_filter_by_product_and_company(self, store: TaskStore) -> None:
        store.create_task("gap_analysis", "ramp", product_slug="card")
        store.create_task("gap_analysis", "carta", product_slug="card")

        ramp_card = store.list_tasks(company_slug="ramp", product_slug="card")
        assert len(ramp_card) == 1
        assert ramp_card[0].company_slug == "ramp"


class TestCancelEndpointEffectiveSlug:
    """Cancel endpoint uses effective_slug for lock release."""

    def test_cancel_releases_effective_slug_lock(
        self, client, task_store: TaskStore
    ) -> None:
        """After cancel, the effective_slug lock is released."""
        from fastapi.testclient import TestClient
        task = task_store.create_task("gap_analysis", "ramp", product_slug="card")

        # Confirm lock held
        from api.tasks.store import TaskConflictError
        with pytest.raises(TaskConflictError):
            task_store.create_task("gap_analysis", "ramp", product_slug="card")

        # Cancel via HTTP
        resp = client.post(f"/api/v1/tasks/{task.task_id}/cancel")
        assert resp.status_code == 200

        # Lock should be released — new run succeeds
        t2 = task_store.create_task("gap_analysis", "ramp", product_slug="card")
        assert t2.effective_slug == "ramp__card"

    def test_cancel_response_includes_product_slug(
        self, client, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("gap_analysis", "ramp", product_slug="card")
        resp = client.post(f"/api/v1/tasks/{task.task_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


class TestTaskListFilterViaAPI:
    """API-level product_slug filter on GET /api/v1/tasks."""

    def test_filter_by_product_slug_via_api(
        self, client, task_store: TaskStore
    ) -> None:
        task_store.create_task("gap_analysis", "ramp")
        task_store.create_task("gap_analysis", "ramp", product_slug="card")

        resp = client.get("/api/v1/tasks?product_slug=card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["tasks"][0]["product_slug"] == "card"

    def test_task_summary_includes_effective_slug(
        self, client, task_store: TaskStore
    ) -> None:
        task_store.create_task("gap_analysis", "ramp", product_slug="card")
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        t = resp.json()["tasks"][0]
        assert t["effective_slug"] == "ramp__card"
        assert t["product_slug"] == "card"
