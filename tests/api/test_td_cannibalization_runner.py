from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.models import TaskStatus
from api.tasks.runner import (
    run_fanout_generation_task,
    run_td_cannibalization_recompute_task,
)


def _make_event_bus() -> MagicMock:
    event_bus = MagicMock()
    event_bus.publish = MagicMock()
    return event_bus


def _make_task_store() -> MagicMock:
    task_store = MagicMock()
    task_store.update_task = MagicMock()
    task_store.release_slug_lock = MagicMock()
    task_store.remove_task_handle = MagicMock()
    task_store.register_task_handle = MagicMock()
    task_store.flush_terminal = AsyncMock()
    return task_store


def _make_session_factory() -> tuple[MagicMock, AsyncMock]:
    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session_factory = MagicMock(return_value=ctx)
    return session_factory, session


@pytest.mark.asyncio
async def test_run_td_cannibalization_recompute_task_resolves_delta_scope():
    company_id = uuid.uuid4()
    discovery_id = uuid.uuid4()
    assignment_ids = [uuid.uuid4(), uuid.uuid4()]
    inventory_ids = [uuid.uuid4()]
    session_factory, _session = _make_session_factory()
    task_store = _make_task_store()
    event_bus = _make_event_bus()

    with patch(
        "api.tasks.runner._resolve_db_context",
        new_callable=AsyncMock,
        return_value=(session_factory, uuid.uuid4(), company_id),
    ), patch(
        "core.topic_discovery.cannibalization_service.resolve_impacted_assignment_scope_for_inventory_changes",
        new_callable=AsyncMock,
        return_value=(discovery_id, assignment_ids),
    ) as mock_resolve, patch(
        "core.topic_discovery.cannibalization_service.recalculate_assignment_cannibalization_records",
        new_callable=AsyncMock,
        return_value=2,
    ) as mock_recalc:
        await run_td_cannibalization_recompute_task(
            task_id="task-1",
            company_slug="test-co",
            task_store=task_store,
            event_bus=event_bus,
            source="cms_sync_auto_prompt",
            inventory_ids=inventory_ids,
        )

    mock_resolve.assert_awaited_once()
    assert mock_resolve.await_args.kwargs["inventory_ids"] == inventory_ids
    mock_recalc.assert_awaited_once()
    assert mock_recalc.await_args.kwargs["assignment_ids"] == assignment_ids
    final_update = task_store.update_task.call_args_list[-1]
    assert final_update.kwargs["status"] == TaskStatus.COMPLETED
    assert final_update.kwargs["result"]["persisted_records"] == 2


@pytest.mark.asyncio
async def test_run_fanout_generation_task_enqueues_cannibalization_recompute():
    parent_prompt_id = str(uuid.uuid4())
    impacted_inventory_ids = [uuid.uuid4()]
    session_factory, session = _make_session_factory()
    task_store = _make_task_store()
    event_bus = _make_event_bus()

    tracked_prompt_repo = MagicMock()
    tracked_prompt_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(text="best AI content strategy software"),
    )
    fanout_result = SimpleNamespace(
        queries=["ai content strategy platform", "content strategy software"],
        model_used="anthropic/claude-sonnet-4-6",
    )
    fanout_service = MagicMock()
    fanout_service.generate_fanout = AsyncMock(return_value=fanout_result)
    prompt_library_service = MagicMock()
    prompt_library_service.create_fanout_queries = AsyncMock(return_value=[object(), object()])
    ci_prompt_repo = MagicMock()
    ci_prompt_repo.get_inventory_ids_for_root_prompt_ids = AsyncMock(
        return_value=impacted_inventory_ids,
    )

    with patch(
        "api.tasks.runner._resolve_db_context",
        new_callable=AsyncMock,
        return_value=(session_factory, uuid.uuid4(), uuid.uuid4()),
    ), patch(
        "core.db.repositories.daily_tracker_repo.TrackedPromptRepository",
        return_value=tracked_prompt_repo,
    ), patch(
        "core.daily_tracker.query_fanout.QueryFanoutService",
        return_value=fanout_service,
    ), patch(
        "core.daily_tracker.prompt_library.PromptLibraryService",
        return_value=prompt_library_service,
    ), patch(
        "core.db.repositories.content_inventory_prompt_repo.ContentInventoryPromptRepository",
        return_value=ci_prompt_repo,
    ), patch(
        "api.tasks.runner._spawn_td_cannibalization_recompute_task",
        new_callable=AsyncMock,
    ) as mock_spawn:
        await run_fanout_generation_task(
            task_id="fanout-1",
            parent_prompt_id=parent_prompt_id,
            company_slug="test-co",
            brand_name="Test Co",
            brand_category="Software",
            competitors=["Competitor A"],
            task_store=task_store,
            event_bus=event_bus,
        )

    session.commit.assert_awaited_once()
    mock_spawn.assert_awaited_once()
    assert mock_spawn.await_args.kwargs["source"] == "daily_tracker_fanout_generation"
    assert mock_spawn.await_args.kwargs["inventory_ids"] == impacted_inventory_ids
