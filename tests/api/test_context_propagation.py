"""Integration tests for async context propagation (Phase 8).

Verifies that structlog contextvars propagate correctly through
``asyncio.create_task()`` boundaries — Python 3.12 copies the
``contextvars.Context`` snapshot into new tasks automatically.
"""
from __future__ import annotations

import asyncio

import pytest

from core.shared_tools.structured_logging import (
    bind_context,
    clear_context,
    get_context,
)


@pytest.fixture(autouse=True)
def _clear_context():
    clear_context()
    yield
    clear_context()


class TestAsyncContextPropagation:
    """Prove context vars propagate through asyncio task boundaries."""

    @pytest.mark.asyncio
    async def test_context_propagated_to_background_task(self) -> None:
        """bind_context in parent → create_task child inherits it."""
        bind_context(correlation_id="corr-123", pipeline_name="gap_analysis")
        result = {}

        async def _child():
            result.update(get_context())

        task = asyncio.create_task(_child())
        await task

        assert result["correlation_id"] == "corr-123"
        assert result["pipeline_name"] == "gap_analysis"

    @pytest.mark.asyncio
    async def test_background_task_context_independent_of_parent_clear(self) -> None:
        """Clearing context in parent does NOT affect child's snapshot."""
        bind_context(task_id="task-abc")
        result = {}

        async def _child():
            await asyncio.sleep(0.01)  # Small delay so parent clears first
            result.update(get_context())

        task = asyncio.create_task(_child())
        clear_context()  # Clear in parent immediately
        await task

        # Child still sees the snapshot
        assert result.get("task_id") == "task-abc"

    @pytest.mark.asyncio
    async def test_runner_augments_inherited_context(self) -> None:
        """Child can add to inherited context without affecting parent."""
        bind_context(correlation_id="corr-xyz")
        child_ctx = {}
        parent_ctx_after = {}

        async def _child():
            bind_context(task_id="task-in-child")
            child_ctx.update(get_context())

        task = asyncio.create_task(_child())
        await task
        parent_ctx_after.update(get_context())

        # Child has both parent context + its own
        assert child_ctx["correlation_id"] == "corr-xyz"
        assert child_ctx["task_id"] == "task-in-child"

        # Parent does NOT have child's addition
        assert "task_id" not in parent_ctx_after

    @pytest.mark.asyncio
    async def test_multiple_background_tasks_isolated(self) -> None:
        """Two tasks from same parent get independent copies."""
        bind_context(correlation_id="shared-corr")
        results = {}

        async def _task_a():
            bind_context(task_id="task-A")
            await asyncio.sleep(0.01)
            results["a"] = get_context().copy()

        async def _task_b():
            bind_context(task_id="task-B")
            await asyncio.sleep(0.01)
            results["b"] = get_context().copy()

        await asyncio.gather(
            asyncio.create_task(_task_a()),
            asyncio.create_task(_task_b()),
        )

        assert results["a"]["task_id"] == "task-A"
        assert results["b"]["task_id"] == "task-B"
        assert results["a"]["correlation_id"] == "shared-corr"
        assert results["b"]["correlation_id"] == "shared-corr"

    @pytest.mark.asyncio
    async def test_gather_coroutines_get_independent_snapshots(self) -> None:
        """asyncio.gather() wraps coroutines in tasks — each gets own context copy."""
        bind_context(correlation_id="gather-corr")
        results: dict[str, dict] = {}

        async def _coro_x():
            bind_context(step_name="x")
            results["x"] = get_context().copy()

        async def _coro_y():
            bind_context(step_name="y")
            results["y"] = get_context().copy()

        await asyncio.gather(_coro_x(), _coro_y())

        # Each got its own copy with parent's correlation_id
        assert results["x"]["step_name"] == "x"
        assert results["y"]["step_name"] == "y"
        assert results["x"]["correlation_id"] == "gather-corr"
        assert results["y"]["correlation_id"] == "gather-corr"

        # Parent context is unaffected — no step_name leakage
        parent_ctx = get_context()
        assert "step_name" not in parent_ctx
        assert parent_ctx["correlation_id"] == "gather-corr"
