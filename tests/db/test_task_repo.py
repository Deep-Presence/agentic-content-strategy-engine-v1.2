"""Tests for TaskRepository — CRUD, filters, active slug lookup, orphan marking.

All tests auto-skip without TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

from core.db.models.api_tasks import ApiTaskModel
from core.db.repositories.task_repo import TaskRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def task_repo(db_session):
    return TaskRepository(db_session)


class TestTaskRepoCRUD:
    """Basic create, read, update operations."""

    @pytest.mark.asyncio
    async def test_create_and_get_by_task_id(self, task_repo):
        task_id = str(uuid.uuid4())
        created = await task_repo.create_task(
            task_id=task_id,
            pipeline="gap_analysis",
            status="running",
            company_slug="test-co",
        )
        assert created.task_id == task_id
        assert created.pipeline == "gap_analysis"

        fetched = await task_repo.get_by_task_id(task_id)
        assert fetched is not None
        assert fetched.task_id == task_id

    @pytest.mark.asyncio
    async def test_get_by_task_id_not_found(self, task_repo):
        result = await task_repo.get_by_task_id("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_by_task_id(self, task_repo):
        task_id = str(uuid.uuid4())
        await task_repo.create_task(
            task_id=task_id,
            pipeline="research",
            status="running",
            company_slug="test-co",
        )
        updated = await task_repo.update_by_task_id(
            task_id,
            status="completed",
            current_step="style_guide",
            progress_pct=100.0,
        )
        assert updated is not None
        assert updated.status == "completed"
        assert updated.current_step == "style_guide"
        assert updated.progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, task_repo):
        result = await task_repo.update_by_task_id("nope", status="failed")
        assert result is None


class TestTaskRepoFilters:
    """list_tasks with various filter combinations."""

    @pytest.mark.asyncio
    async def test_list_tasks_no_filter(self, task_repo):
        for i in range(3):
            await task_repo.create_task(
                task_id=str(uuid.uuid4()),
                pipeline="research",
                status="completed",
                company_slug="test-co",
            )
        all_tasks = await task_repo.list_tasks()
        assert len(all_tasks) >= 3

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_pipeline(self, task_repo):
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="content",
            status="running",
            company_slug="test-co",
        )
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="research",
            status="running",
            company_slug="test-co",
        )
        content_tasks = await task_repo.list_tasks(pipeline="content")
        assert all(t.pipeline == "content" for t in content_tasks)

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_status(self, task_repo):
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="research",
            status="failed",
            company_slug="test-co",
        )
        failed = await task_repo.list_tasks(status="failed")
        assert all(t.status == "failed" for t in failed)

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_company_slug(self, task_repo):
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="research",
            status="running",
            company_slug="acme-corp",
        )
        acme_tasks = await task_repo.list_tasks(company_slug="acme-corp")
        assert all(t.company_slug == "acme-corp" for t in acme_tasks)


class TestFindActiveBySlug:
    """find_active_by_slug returns only running/pending_approval tasks."""

    @pytest.mark.asyncio
    async def test_finds_active_tasks(self, task_repo):
        slug = "active-test"
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="gap_analysis",
            status="running",
            company_slug="test-co",
            effective_slug=slug,
        )
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="gap_analysis",
            status="completed",
            company_slug="test-co",
            effective_slug=slug,
        )
        active = await task_repo.find_active_by_slug(slug)
        assert len(active) == 1
        assert active[0].status == "running"


class TestMarkOrphansFailed:
    """mark_orphans_failed transitions running/pending_approval → failed_restart."""

    @pytest.mark.asyncio
    async def test_marks_running_as_failed_restart(self, task_repo):
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="research",
            status="running",
            company_slug="test-co",
        )
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="research",
            status="pending_approval",
            company_slug="test-co",
        )
        await task_repo.create_task(
            task_id=str(uuid.uuid4()),
            pipeline="research",
            status="completed",
            company_slug="test-co",
        )
        count = await task_repo.mark_orphans_failed()
        assert count == 2

        # Verify only the non-terminal tasks were updated
        all_tasks = await task_repo.list_tasks()
        statuses = {t.status for t in all_tasks}
        assert "running" not in statuses
        assert "pending_approval" not in statuses
        assert "failed_restart" in statuses
        assert "completed" in statuses
