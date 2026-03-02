"""Tests for backward-compat kwargs and contextvars in tracing_v13.

Every old Langfuse kwarg must be accepted without TypeError.
contextvars must round-trip safely.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# contextvars round-trip
# ---------------------------------------------------------------------------


class TestContextVars:
    """set_current_span / get_current_span."""

    def test_default_is_none(self):
        from core.content_engine.tracing_v13 import get_current_span

        # Reset to default
        from core.content_engine.tracing_v13 import set_current_span
        set_current_span(None)
        assert get_current_span() is None

    def test_round_trip(self):
        from core.content_engine.tracing_v13 import get_current_span, set_current_span

        sentinel = object()
        set_current_span(sentinel)
        assert get_current_span() is sentinel
        # Cleanup
        set_current_span(None)

    def test_overwrite(self):
        from core.content_engine.tracing_v13 import get_current_span, set_current_span

        s1 = MagicMock(name="span-1")
        s2 = MagicMock(name="span-2")
        set_current_span(s1)
        assert get_current_span() is s1
        set_current_span(s2)
        assert get_current_span() is s2
        set_current_span(None)


# ---------------------------------------------------------------------------
# create_span — compat kwargs
# ---------------------------------------------------------------------------


class TestCreateSpanCompat:
    """create_span accepts old Langfuse kwargs without TypeError."""

    def test_input_kwarg_alias(self):
        """``input=`` is accepted as alias for input_data."""
        from core.content_engine.tracing_v13 import create_span

        parent = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            create_span(parent, "test", input={"key": "val"})
        parent.create_child.assert_called_once()
        call_kwargs = parent.create_child.call_args
        assert call_kwargs.kwargs["inputs"] == {"key": "val"}

    def test_input_data_takes_precedence_over_input(self):
        """When both input_data and input are given, input_data wins."""
        from core.content_engine.tracing_v13 import create_span

        parent = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            create_span(parent, "test", input_data={"a": 1}, input={"b": 2})
        call_kwargs = parent.create_child.call_args
        assert call_kwargs.kwargs["inputs"] == {"a": 1}

    def test_parent_span_kwarg_absorbed(self):
        """``parent_span=`` is silently absorbed without error."""
        from core.content_engine.tracing_v13 import create_span

        parent = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            # Should not raise TypeError
            create_span(parent, "test", parent_span=MagicMock())
        parent.create_child.assert_called_once()


# ---------------------------------------------------------------------------
# create_trace — compat kwargs
# ---------------------------------------------------------------------------


class TestCreateTraceCompat:
    """create_trace accepts old Langfuse kwargs."""

    def test_input_kwarg_alias(self):
        from core.content_engine.tracing_v13 import create_trace

        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13.RunTree") as MockRT:
            mock_rt = MagicMock()
            MockRT.return_value = mock_rt
            create_trace("sid", "name", input={"x": 1})
            MockRT.assert_called_once()
            assert MockRT.call_args.kwargs["inputs"] == {"x": 1}

    def test_user_id_kwarg_absorbed(self):
        from core.content_engine.tracing_v13 import create_trace

        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13.RunTree") as MockRT:
            MockRT.return_value = MagicMock()
            # Should not raise TypeError
            create_trace("sid", "name", user_id="test-user")
            MockRT.assert_called_once()


# ---------------------------------------------------------------------------
# end_span — compat kwargs
# ---------------------------------------------------------------------------


class TestEndSpanCompat:
    """end_span accepts level= + status_message= from Langfuse callers."""

    def test_level_error_maps_to_error(self):
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        end_span(span, level="ERROR", status_message="Something broke")
        span.end.assert_called_once_with(error="Something broke")

    def test_level_error_without_status_message(self):
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        end_span(span, level="ERROR")
        span.end.assert_called_once_with(error="Error")

    def test_level_error_does_not_override_explicit_error(self):
        """Explicit error= takes precedence over level=ERROR."""
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        end_span(span, error="explicit", level="ERROR", status_message="from level")
        span.end.assert_called_once_with(error="explicit")

    def test_metadata_kwarg_absorbed(self):
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        # Should not raise TypeError
        end_span(span, output={"ok": True}, metadata={"extra": "data"})
        span.end.assert_called_once_with(outputs={"ok": True})

    def test_level_non_error_ignored(self):
        """Non-ERROR level doesn't trigger error path."""
        from core.content_engine.tracing_v13 import end_span

        span = MagicMock()
        end_span(span, output={"ok": True}, level="WARNING", status_message="warn")
        span.end.assert_called_once_with(outputs={"ok": True})


# ---------------------------------------------------------------------------
# log_generation — compat kwargs
# ---------------------------------------------------------------------------


class TestLogGenerationCompat:
    """log_generation accepts parent_span= and model_parameters=."""

    def test_parent_span_used_when_parent_is_none(self):
        from core.content_engine.tracing_v13 import log_generation

        fallback_parent = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            log_generation(
                None, "gen", "model-x",
                input_text="hi", output_text="bye",
                parent_span=fallback_parent,
            )
        fallback_parent.create_child.assert_called_once()

    def test_parent_takes_precedence_over_parent_span(self):
        from core.content_engine.tracing_v13 import log_generation

        parent = MagicMock()
        other = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            log_generation(
                parent, "gen", "model-x",
                parent_span=other,
            )
        parent.create_child.assert_called_once()
        other.create_child.assert_not_called()

    def test_model_parameters_merged_into_metadata(self):
        from core.content_engine.tracing_v13 import log_generation

        parent = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            log_generation(
                parent, "gen", "model-x",
                model_parameters={"temperature": 0.7},
            )
        call_kwargs = parent.create_child.call_args.kwargs
        assert call_kwargs["extra"]["metadata"]["model_parameters"] == {"temperature": 0.7}

    def test_any_type_input_output_accepted(self):
        """input_text and output_text accept Any type (Langfuse passed dicts)."""
        from core.content_engine.tracing_v13 import log_generation

        parent = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True):
            # Should not raise
            log_generation(
                parent, "gen", "model-x",
                input_text={"messages": [{"role": "user", "content": "hi"}]},
                output_text={"content": "response"},
            )
        parent.create_child.assert_called_once()


# ---------------------------------------------------------------------------
# log_score — compat kwargs
# ---------------------------------------------------------------------------


class TestLogScoreCompat:
    """log_score accepts str/bool values and metadata=."""

    def test_string_value(self):
        from core.content_engine.tracing_v13 import log_score

        parent = MagicMock()
        parent.id = "run-123"
        mock_client = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13._get_client", return_value=mock_client):
            log_score(parent, "decision", "approved")
            mock_client.create_feedback.assert_called_once()
            call_kwargs = mock_client.create_feedback.call_args.kwargs
            assert call_kwargs["key"] == "decision"
            assert "approved" in call_kwargs["comment"]
            assert "score" not in call_kwargs  # no numeric score for strings

    def test_bool_value_true(self):
        from core.content_engine.tracing_v13 import log_score

        parent = MagicMock()
        parent.id = "run-123"
        mock_client = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13._get_client", return_value=mock_client):
            log_score(parent, "passed", True)
            call_kwargs = mock_client.create_feedback.call_args.kwargs
            assert call_kwargs["score"] == 1.0

    def test_bool_value_false(self):
        from core.content_engine.tracing_v13 import log_score

        parent = MagicMock()
        parent.id = "run-123"
        mock_client = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13._get_client", return_value=mock_client):
            log_score(parent, "passed", False)
            call_kwargs = mock_client.create_feedback.call_args.kwargs
            assert call_kwargs["score"] == 0.0

    def test_metadata_kwarg_absorbed(self):
        from core.content_engine.tracing_v13 import log_score

        parent = MagicMock()
        parent.id = "run-123"
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13._get_client", return_value=MagicMock()):
            # Should not raise TypeError
            log_score(parent, "score", 0.85, metadata={"extra": True})

    def test_string_value_with_comment(self):
        from core.content_engine.tracing_v13 import log_score

        parent = MagicMock()
        parent.id = "run-123"
        mock_client = MagicMock()
        with patch("core.content_engine.tracing_v13._is_enabled", return_value=True), \
             patch("core.content_engine.tracing_v13._get_client", return_value=mock_client):
            log_score(parent, "decision", "approved", comment="reviewer note")
            call_kwargs = mock_client.create_feedback.call_args.kwargs
            assert "reviewer note" in call_kwargs["comment"]
            assert "approved" in call_kwargs["comment"]


# ---------------------------------------------------------------------------
# update_trace_output — compat kwargs
# ---------------------------------------------------------------------------


class TestUpdateTraceOutputCompat:
    """update_trace_output accepts metadata= and tags=."""

    def test_metadata_kwarg_absorbed(self):
        from core.content_engine.tracing_v13 import update_trace_output

        trace = MagicMock()
        # Should not raise TypeError
        update_trace_output(trace, output={"done": True}, metadata={"k": "v"})
        trace.end.assert_called_once_with(outputs={"done": True})

    def test_tags_kwarg_absorbed(self):
        from core.content_engine.tracing_v13 import update_trace_output

        trace = MagicMock()
        update_trace_output(trace, output={"done": True}, tags=["pipeline", "v1"])
        trace.end.assert_called_once_with(outputs={"done": True})
