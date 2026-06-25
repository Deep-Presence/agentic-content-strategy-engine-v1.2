"""Regression tests: pipeline runners use persisted task slug/workspace scope."""
from __future__ import annotations

import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.runner import (
    _create_pipeline_run,
    _task_runner_slugs,
    run_audience_persona_pipeline_task,
    run_daily_tracker_task,
    run_onboarding_task,
    run_research_orchestrator_task,
    run_topic_discovery_pipeline_task,
    run_topic_expansion_pipeline_task,
    run_voice_style_guide_pipeline_task,
)


def _task(
    *,
    company_slug: str = "second-brand",
    product_slug: str | None = None,
    workspace_id: str | None = None,
) -> PipelineTask:
    return PipelineTask(
        task_id=str(uuid.uuid4()),
        pipeline="audience_persona",
        company_slug=company_slug,
        product_slug=product_slug,
        status=TaskStatus.RUNNING,
        workspace_id=workspace_id,
    )


class TestTaskRunnerSlugs:
    def test_prefers_task_slugs_over_stale_request_company_name(self) -> None:
        task = _task(company_slug="second-brand", workspace_id="ws-uuid")
        request = MagicMock(company_name="Stale Co", product_slug=None)

        company_slug, product_slug, workspace_id = _task_runner_slugs(task, request)

        assert company_slug == "second-brand"
        assert product_slug is None
        assert workspace_id == "ws-uuid"


class TestRunnerSourceUsesTaskScope:
    def test_ap_runner_passes_workspace_id_to_create_pipeline_run(self) -> None:
        source = inspect.getsource(run_audience_persona_pipeline_task)
        assert "_task_runner_slugs" in source
        assert "workspace_id=workspace_id" in source

    def test_vsg_runner_passes_workspace_id_to_create_pipeline_run(self) -> None:
        source = inspect.getsource(run_voice_style_guide_pipeline_task)
        assert "_task_runner_slugs" in source
        assert "workspace_id=workspace_id" in source

    def test_research_orchestrator_runner_passes_workspace_id(self) -> None:
        source = inspect.getsource(run_research_orchestrator_task)
        assert "_task_runner_slugs" in source
        assert "workspace_id=workspace_id" in source

    def test_onboarding_runner_passes_workspace_id(self) -> None:
        source = inspect.getsource(run_onboarding_task)
        assert "_task_runner_slugs" in source
        assert "workspace_id=workspace_id" in source

    def test_daily_tracker_runner_passes_workspace_id(self) -> None:
        source = inspect.getsource(run_daily_tracker_task)
        assert "_task_runner_slugs" in source
        assert "workspace_id=workspace_id" in source

    def test_topic_discovery_runner_passes_workspace_id_to_input(self) -> None:
        source = inspect.getsource(run_topic_discovery_pipeline_task)
        assert "workspace_id=workspace_id" in source
        assert "workspace_id=workspace_id or \"\"" in source

    def test_topic_expansion_runner_passes_workspace_id_to_input(self) -> None:
        source = inspect.getsource(run_topic_expansion_pipeline_task)
        assert "workspace_id=workspace_id" in source
        assert "workspace_id=workspace_id or \"\"" in source


@pytest.mark.asyncio
async def test_ap_runner_create_pipeline_run_uses_task_workspace_id() -> None:
    """Runner must not derive scope from request.company_name when task has workspace slug."""
    task_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    task = _task(company_slug="second-brand", workspace_id=ws_id)
    request = MagicMock(
        company_name="Wrong Co",
        product_slug=None,
        domain=None,
        max_personas=5,
        language="en",
        region=None,
        additional_constraints=None,
        auto_approve_checkpoints=[],
    )

    task_store = MagicMock()
    task_store.get_task.return_value = task
    task_store.pipeline_semaphore.return_value = MagicMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=None),
    )
    task_store.update_task = MagicMock()
    task_store.flush_terminal = AsyncMock()
    task_store.release_slug_lock = MagicMock()
    task_store.remove_task_handle = MagicMock()

    event_bus = MagicMock()
    event_bus.publish = MagicMock()

    scope = MagicMock(
        company_slug="second-brand",
        effective_slug="second-brand",
        product_slug=None,
        product_name=None,
    )

    with (
        patch("api.tasks.runner._resolve_scope_async", new_callable=AsyncMock, return_value=scope),
        patch(
            "api.tasks.runner._resolve_db_context",
            new_callable=AsyncMock,
            return_value=(MagicMock(), uuid.uuid4(), uuid.uuid4()),
        ),
        patch("api.tasks.runner._create_pipeline_run", new_callable=AsyncMock) as mock_create,
        patch(
            "core.research.audience_persona.pipeline.run_audience_persona_pipeline",
            new_callable=AsyncMock,
            return_value=MagicMock(
                slug="second-brand",
                company_name="Second Brand",
                briefs_suggested=0,
                briefs_approved=0,
                profiles_generated=0,
                persona_dir="",
            ),
        ),
        patch("api.tasks.runner.get_sync_redis_or_none", return_value=None),
    ):
        await run_audience_persona_pipeline_task(
            task_id=task_id,
            request=request,
            task_store=task_store,
            event_bus=event_bus,
            auth_service=None,
            artifacts_root=None,
        )

    mock_create.assert_awaited_once()
    assert mock_create.await_args.kwargs.get("workspace_id") == ws_id
    assert mock_create.await_args.args[3] == "second-brand"
