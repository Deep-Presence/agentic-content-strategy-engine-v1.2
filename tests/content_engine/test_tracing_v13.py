"""Tests for core.content_engine.tracing_v13 — LangSmith tracing.

Tests graceful degradation, session/span creation, and flushing.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestCreateSession:
    """Tests for create_session()."""

    def test_returns_formatted_session_id(self):
        from core.content_engine.tracing_v13 import create_session

        sid = create_session("test-co")
        assert sid.startswith("content-test-co-")
        # The timestamp part should be numeric
        ts_part = sid.split("-")[-1]
        assert ts_part.isdigit()

    def test_different_slugs_produce_different_ids(self):
        from core.content_engine.tracing_v13 import create_session

        s1 = create_session("company-a")
        s2 = create_session("company-b")
        assert "company-a" in s1
        assert "company-b" in s2
        assert s1 != s2


class TestCreatePipelineTrace:
    """Tests for create_pipeline_trace()."""

    def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from core.content_engine.tracing_v13 import create_pipeline_trace

        with patch("core.content_engine.tracing_v13._langsmith_available", False):
            result = create_pipeline_trace("session-1", "test-co")

        assert result is None

    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from core.content_engine.tracing_v13 import create_pipeline_trace

        with patch("core.content_engine.tracing_v13._langsmith_available", True):
            result = create_pipeline_trace("session-1", "test-co")

        assert result is None


class TestCreateSpan:
    """Tests for create_span()."""

    def test_returns_none_when_parent_is_none(self):
        from core.content_engine.tracing_v13 import create_span

        result = create_span(None, "test-span")
        assert result is None

    def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from core.content_engine.tracing_v13 import create_span

        parent = MagicMock()
        with patch("core.content_engine.tracing_v13._langsmith_available", False):
            result = create_span(parent, "test-span")

        assert result is None


class TestEndSpan:
    """Tests for end_span()."""

    def test_noop_when_span_is_none(self):
        from core.content_engine.tracing_v13 import end_span

        # Should not raise
        end_span(None)

    def test_calls_end_and_patch(self):
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        end_span(span, output={"result": "ok"})
        span.end.assert_called_once_with(outputs={"result": "ok"})
        span.patch.assert_called_once()

    def test_error_parameter(self):
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        end_span(span, error="Something failed")
        span.end.assert_called_once_with(error="Something failed")


class TestFlush:
    """Tests for flush()."""

    def test_runs_without_error(self):
        from core.content_engine.tracing_v13 import flush

        # Should not raise
        flush()
