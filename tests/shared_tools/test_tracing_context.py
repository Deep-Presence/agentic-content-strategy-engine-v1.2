"""Tests for LangSmith trace linkage — Layer 2.

Verifies that create_pipeline_trace / create_trace / create_research_trace
automatically bind ``langsmith_trace_id`` to the structured logging context.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_context():
    from core.shared_tools.structured_logging import clear_context

    clear_context()
    yield
    clear_context()


class TestLangSmithTraceIdBinding:
    """Binding langsmith_trace_id to structured logging context."""

    def test_bound_after_create_pipeline_trace(self):
        from core.shared_tools.structured_logging import get_context

        mock_id = uuid.uuid4()
        mock_tree = MagicMock()
        mock_tree.id = mock_id
        mock_tree.post = MagicMock()

        with (
            patch("core.shared_tools.tracing._is_enabled", return_value=True),
            patch("core.shared_tools.tracing.RunTree", return_value=mock_tree),
            patch("core.shared_tools.tracing._get_client", return_value=None),
        ):
            from core.shared_tools.tracing import create_pipeline_trace

            result = create_pipeline_trace("session-1", "test-co", "Test Co")

        assert result is not None
        ctx = get_context()
        assert "langsmith_trace_id" in ctx
        assert ctx["langsmith_trace_id"] == str(mock_id)

    def test_not_bound_when_tracing_disabled(self):
        from core.shared_tools.structured_logging import get_context

        with patch("core.shared_tools.tracing._is_enabled", return_value=False):
            from core.shared_tools.tracing import create_pipeline_trace

            result = create_pipeline_trace("session-1", "test-co")

        assert result is None
        assert "langsmith_trace_id" not in get_context()

    def test_bound_after_create_trace(self):
        from core.shared_tools.structured_logging import get_context

        mock_id = uuid.uuid4()
        mock_tree = MagicMock()
        mock_tree.id = mock_id
        mock_tree.post = MagicMock()

        with (
            patch("core.shared_tools.tracing._is_enabled", return_value=True),
            patch("core.shared_tools.tracing.RunTree", return_value=mock_tree),
            patch("core.shared_tools.tracing._get_client", return_value=None),
        ):
            from core.shared_tools.tracing import create_trace

            result = create_trace("session-1", "my-trace")

        assert result is not None
        ctx = get_context()
        assert ctx["langsmith_trace_id"] == str(mock_id)

    def test_bound_after_create_research_trace(self):
        from core.shared_tools.structured_logging import get_context

        mock_id = uuid.uuid4()
        mock_tree = MagicMock()
        mock_tree.id = mock_id
        mock_tree.post = MagicMock()

        with (
            patch("core.shared_tools.tracing._is_enabled", return_value=True),
            patch("core.shared_tools.tracing.RunTree", return_value=mock_tree),
            patch("core.shared_tools.tracing._get_client", return_value=None),
        ):
            from core.shared_tools.tracing import create_research_trace

            result = create_research_trace("test-co", "Test Co")

        assert result is not None
        ctx = get_context()
        assert ctx["langsmith_trace_id"] == str(mock_id)

    def test_trace_id_is_string_not_uuid(self):
        from core.shared_tools.structured_logging import get_context

        mock_tree = MagicMock()
        mock_tree.id = uuid.uuid4()
        mock_tree.post = MagicMock()

        with (
            patch("core.shared_tools.tracing._is_enabled", return_value=True),
            patch("core.shared_tools.tracing.RunTree", return_value=mock_tree),
            patch("core.shared_tools.tracing._get_client", return_value=None),
        ):
            from core.shared_tools.tracing import create_pipeline_trace

            create_pipeline_trace("session-1", "test-co")

        ctx = get_context()
        assert isinstance(ctx["langsmith_trace_id"], str)
