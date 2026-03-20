"""Tests for runner DB persistence — H1: ensure pipeline runs are marked complete.

Verifies that _mark_pipeline_run_complete is called after each pipeline returns
successfully, and that _mark_pipeline_run_failed is called on exceptions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.tasks.runner import _mark_pipeline_run_complete


# ── _mark_pipeline_run_complete unit tests ────────────────────────────


class _FakeSession:
    """Async context manager that yields itself."""

    def __init__(self, run=None) -> None:
        self._run = run
        self.commit = AsyncMock()

    async def get(self, model_cls, run_id):
        return self._run

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestMarkPipelineRunComplete:
    async def test_no_op_when_session_factory_none(self):
        await _mark_pipeline_run_complete(None, uuid.uuid4())

    async def test_no_op_when_run_id_none(self):
        await _mark_pipeline_run_complete(MagicMock(), None)

    async def test_marks_run_as_completed(self):
        from core.db.enums import PipelineStatus

        mock_run = MagicMock()
        mock_run.status = PipelineStatus.running
        session = _FakeSession(run=mock_run)
        factory = MagicMock(return_value=session)

        await _mark_pipeline_run_complete(factory, uuid.uuid4())

        assert mock_run.status == PipelineStatus.completed
        assert mock_run.completed_at is not None
        session.commit.assert_awaited_once()

    async def test_idempotent_when_already_completed(self):
        from core.db.enums import PipelineStatus

        mock_run = MagicMock()
        mock_run.status = PipelineStatus.completed
        original_completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_run.completed_at = original_completed_at
        session = _FakeSession(run=mock_run)
        factory = MagicMock(return_value=session)

        await _mark_pipeline_run_complete(factory, uuid.uuid4())

        assert mock_run.completed_at == original_completed_at
        session.commit.assert_not_awaited()

    async def test_handles_missing_run(self):
        session = _FakeSession(run=None)
        factory = MagicMock(return_value=session)

        await _mark_pipeline_run_complete(factory, uuid.uuid4())
        session.commit.assert_not_awaited()

    async def test_stores_summary(self):
        from core.db.enums import PipelineStatus

        mock_run = MagicMock()
        mock_run.status = PipelineStatus.running
        session = _FakeSession(run=mock_run)
        factory = MagicMock(return_value=session)

        summary = {"total_docs": 5}
        await _mark_pipeline_run_complete(factory, uuid.uuid4(), summary)

        assert mock_run.summary == summary

    async def test_exception_does_not_propagate(self):
        factory = MagicMock(side_effect=RuntimeError("DB down"))
        await _mark_pipeline_run_complete(factory, uuid.uuid4())


# ── Verify runner functions call _mark_pipeline_run_complete ──────────


class TestRunnerCallsMarkComplete:
    """Verify that _mark_pipeline_run_complete is wired into each runner
    by inspecting the source code (lightweight, avoids heavy mocking)."""

    def test_kb_runner_calls_mark_complete(self):
        import inspect
        from api.tasks.runner import run_kb_pipeline_task

        source = inspect.getsource(run_kb_pipeline_task)
        assert "_mark_pipeline_run_complete(" in source
        assert "_mark_pipeline_run_failed(" in source

    def test_ap_runner_calls_mark_complete(self):
        import inspect
        from api.tasks.runner import run_audience_persona_pipeline_task

        source = inspect.getsource(run_audience_persona_pipeline_task)
        assert "_mark_pipeline_run_complete(" in source
        assert "_mark_pipeline_run_failed(" in source

    def test_vsg_runner_calls_mark_complete(self):
        import inspect
        from api.tasks.runner import run_voice_style_guide_pipeline_task

        source = inspect.getsource(run_voice_style_guide_pipeline_task)
        assert "_mark_pipeline_run_complete(" in source
        assert "_mark_pipeline_run_failed(" in source

    def test_td_runner_calls_mark_complete(self):
        import inspect
        from api.tasks.runner import run_topic_discovery_pipeline_task

        source = inspect.getsource(run_topic_discovery_pipeline_task)
        assert "_mark_pipeline_run_complete(" in source
        assert "_mark_pipeline_run_failed(" in source

    def test_site_audit_runner_calls_mark_complete(self):
        import inspect
        from api.tasks.runner import run_site_audit_task

        source = inspect.getsource(run_site_audit_task)
        assert "_mark_pipeline_run_complete(" in source
        assert "_mark_pipeline_run_failed(" in source

    def test_site_audit_runner_calls_persist(self):
        """Site audit runner must call persist_site_audit_result."""
        import inspect
        from api.tasks.runner import run_site_audit_task

        source = inspect.getsource(run_site_audit_task)
        assert "persist_site_audit_result(" in source

    def test_site_audit_runner_resolves_db_context(self):
        """Site audit runner must call _resolve_db_context."""
        import inspect
        from api.tasks.runner import run_site_audit_task

        source = inspect.getsource(run_site_audit_task)
        assert "_resolve_db_context(" in source
        assert "_create_pipeline_run(" in source

    def test_mark_complete_before_update_task(self):
        """_mark_pipeline_run_complete must be called BEFORE task_store.update_task
        (i.e., between pipeline return and result building)."""
        import inspect
        from api.tasks.runner import run_kb_pipeline_task

        source = inspect.getsource(run_kb_pipeline_task)
        complete_pos = source.index("_mark_pipeline_run_complete(")
        update_pos = source.index("task_store.update_task(")
        assert complete_pos < update_pos, \
            "_mark_pipeline_run_complete must be called before task_store.update_task"
