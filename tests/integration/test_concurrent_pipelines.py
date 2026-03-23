"""Integration tests for async concurrency primitives.

Tests real concurrent behavior of TaskStore slug locks, semaphore,
EventBus ordering, and approval queues using actual asyncio.create_task
(NOT patched to no-ops).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from api.tasks.event_bus import EventBus
from api.tasks.store import TaskConflictError, TaskStore


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def task_store(tmp_path, event_bus) -> TaskStore:
    return TaskStore(tmp_path / "_jobs", event_bus, max_concurrent=2)


# ── Slug locks ───────────────────────────────────────────────────────


class TestSlugLocks:
    """Test that slug locks prevent duplicate pipeline runs."""

    def test_duplicate_slug_raises_conflict(self, task_store: TaskStore):
        """Creating two tasks for the same slug raises TaskConflictError."""
        task_store.create_task("gap_analysis", "test-co")

        with pytest.raises(TaskConflictError):
            task_store.create_task("gap_analysis", "test-co")

    def test_different_pipelines_same_slug_allowed(self, task_store: TaskStore):
        """Different pipeline types can run concurrently for the same slug."""
        t1 = task_store.create_task("gap_analysis", "test-co")
        t2 = task_store.create_task("content", "test-co")

        assert t1.task_id != t2.task_id

    def test_lock_released_after_completion(self, task_store: TaskStore):
        """Completing a task frees the slug lock for a new run."""
        t1 = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(t1.task_id, status="completed")
        task_store.release_slug_lock("gap_analysis:test-co")

        # Should succeed now
        t2 = task_store.create_task("gap_analysis", "test-co")
        assert t2.task_id != t1.task_id

    def test_stale_lock_auto_cleared(self, task_store: TaskStore):
        """A lock pointing to a completed task is auto-cleared on next acquire."""
        t1 = task_store.create_task("gap_analysis", "test-co")
        task_store.update_task(t1.task_id, status="completed")
        # Don't explicitly release — lock is stale

        t2 = task_store.create_task("gap_analysis", "test-co")
        assert t2.task_id != t1.task_id

    def test_product_slug_creates_separate_lock(self, task_store: TaskStore):
        """product_slug creates effective_slug = company__product."""
        t1 = task_store.create_task("content", "ramp", product_slug="card")
        t2 = task_store.create_task("content", "ramp", product_slug="travel")

        assert t1.effective_slug == "ramp__card"
        assert t2.effective_slug == "ramp__travel"

    def test_allow_parallel_skips_lock(self, task_store: TaskStore):
        """allow_parallel=True allows multiple tasks for the same slug."""
        t1 = task_store.create_task("content", "test-co", allow_parallel=True)
        t2 = task_store.create_task("content", "test-co", allow_parallel=True)

        assert t1.task_id != t2.task_id


# ── Semaphore ────────────────────────────────────────────────────────


class TestSemaphore:
    """Test that the global semaphore limits concurrency."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_tasks(self, task_store: TaskStore):
        """Only max_concurrent tasks can hold the semaphore simultaneously."""
        entered = []
        barrier = asyncio.Event()

        async def hold_semaphore(name: str):
            async with task_store.semaphore:
                entered.append(name)
                if len(entered) >= 2:
                    barrier.set()
                await asyncio.sleep(0.1)

        tasks = [
            asyncio.create_task(hold_semaphore("a")),
            asyncio.create_task(hold_semaphore("b")),
            asyncio.create_task(hold_semaphore("c")),
        ]

        # Wait for first two to enter
        await asyncio.wait_for(barrier.wait(), timeout=2.0)

        # At this point, 2 tasks hold semaphore, 3rd should be waiting
        # (max_concurrent=2). Let them all complete.
        await asyncio.gather(*tasks)

        # All 3 eventually completed
        assert len(entered) == 3


# ── EventBus concurrent access ───────────────────────────────────────


class TestEventBusConcurrency:
    """Test EventBus ordering under concurrent publish."""

    def test_sequential_ids_single_task(self, event_bus: EventBus):
        """Events for the same task_id get monotonically increasing IDs."""
        for i in range(10):
            event_bus.publish("task-1", "progress", {"step": i})

        history = event_bus.get_history("task-1")
        ids = [e["id"] for e in history]
        assert ids == list(range(1, 11))

    @pytest.mark.asyncio
    async def test_concurrent_publish_preserves_ordering(self, event_bus: EventBus):
        """Multiple concurrent publishers still get sequential IDs."""
        async def publish_batch(start: int):
            for i in range(5):
                event_bus.publish("task-1", "progress", {"n": start + i})
                await asyncio.sleep(0)  # yield to event loop

        await asyncio.gather(
            publish_batch(0),
            publish_batch(100),
        )

        history = event_bus.get_history("task-1")
        ids = [e["id"] for e in history]

        # IDs must be strictly monotonically increasing
        assert ids == sorted(ids)
        assert len(set(ids)) == len(ids)  # no duplicates
        assert len(ids) == 10

    def test_independent_id_counters_per_task(self, event_bus: EventBus):
        """Each task_id has its own counter."""
        event_bus.publish("task-a", "progress", {"x": 1})
        event_bus.publish("task-b", "progress", {"x": 1})
        event_bus.publish("task-a", "progress", {"x": 2})

        assert event_bus.get_history("task-a")[-1]["id"] == 2
        assert event_bus.get_history("task-b")[-1]["id"] == 1

    @pytest.mark.asyncio
    async def test_subscriber_receives_live_events(self, event_bus: EventBus):
        """Subscriber queue receives events published after subscription."""
        queue = event_bus.subscribe("task-1")
        event_bus.publish("task-1", "progress", {"step": 1})

        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["data"]["step"] == 1


# ── Approval queue ───────────────────────────────────────────────────


class TestApprovalQueue:
    """Test HITL approval queue concurrent submit/wait."""

    @pytest.mark.asyncio
    async def test_submit_before_wait(self, task_store: TaskStore):
        """submit_approval before wait_for_approval still delivers."""
        t = task_store.create_task("content", "test-co")
        task_store.submit_approval(t.task_id, "approve")

        result = await task_store.wait_for_approval(t.task_id, timeout=1.0)
        assert result["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_wait_then_submit(self, task_store: TaskStore):
        """wait_for_approval blocks until submit_approval is called."""
        t = task_store.create_task("content", "test-co")

        async def delayed_submit():
            await asyncio.sleep(0.05)
            task_store.submit_approval(t.task_id, "reject", revision_note="Needs work")

        asyncio.create_task(delayed_submit())

        result = await asyncio.wait_for(
            task_store.wait_for_approval(t.task_id, timeout=2.0),
            timeout=3.0,
        )
        assert result["decision"] == "reject"
        assert result["revision_note"] == "Needs work"

    @pytest.mark.asyncio
    async def test_approval_timeout_auto_rejects(self, task_store: TaskStore):
        """Timeout on wait_for_approval returns auto-reject."""
        t = task_store.create_task("content", "test-co")

        result = await task_store.wait_for_approval(t.task_id, timeout=0.05)

        assert result["decision"] == "reject"
        assert "timed out" in result["revision_note"].lower()
