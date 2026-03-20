"""Tests for structured logging foundation (Layer 1).

TDD — these tests define the expected interface for
core/shared_tools/structured_logging.py.
"""
from __future__ import annotations

import io
import json
import logging
from unittest.mock import patch

import pytest
import structlog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_json_log(logger_name: str, message: str, *args, **kwargs) -> dict:
    """Emit a log line via stdlib logger and capture the JSON output."""
    from core.shared_tools.structured_logging import configure_logging

    stream = io.StringIO()
    configure_logging(level="DEBUG", log_format="json", _stream=stream)
    logging.getLogger(logger_name).info(message, *args, **kwargs)
    stream.seek(0)
    line = stream.readline().strip()
    return json.loads(line)


# ---------------------------------------------------------------------------
# Phase A — configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    """Core configuration function tests."""

    def test_configure_sets_root_level(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(level="WARNING", log_format="json", _stream=stream)
        assert logging.getLogger().level == logging.WARNING

    def test_json_output_mode(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)

        logging.getLogger("test.json").info("hello json")
        stream.seek(0)
        line = stream.readline().strip()
        record = json.loads(line)

        assert record["event"] == "hello json"
        assert record["level"] == "info"
        assert "timestamp" in record
        assert record["logger"] == "test.json"

    def test_console_output_mode(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="console", _stream=stream)

        logging.getLogger("test.console").info("hello console")
        stream.seek(0)
        output = stream.read()

        # Console output should be human-readable, not JSON
        assert "hello console" in output
        with pytest.raises(json.JSONDecodeError):
            json.loads(output.strip().split("\n")[0])

    def test_percent_format_preserved(self):
        """Existing logger.info("msg %s", arg) calls must still work."""
        record = _capture_json_log("test.pct", "found %d items in %s", 42, "cache")
        assert record["event"] == "found 42 items in cache"

    def test_exception_info_included(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)

        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("test.exc").exception("caught error")

        stream.seek(0)
        line = stream.readline().strip()
        record = json.loads(line)
        assert record["event"] == "caught error"
        # exc_info should be rendered as a string in the JSON output
        assert "ValueError" in json.dumps(record)

    def test_idempotent_configure(self):
        """Calling configure_logging twice must not duplicate handlers."""
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)
        configure_logging(level="DEBUG", log_format="json", _stream=stream)

        logging.getLogger("test.idem").info("once")
        stream.seek(0)
        lines = [l for l in stream.readlines() if l.strip()]
        assert len(lines) == 1, f"Expected 1 log line, got {len(lines)}: {lines}"

    def test_uvicorn_loggers_configured(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)

        uv_logger = logging.getLogger("uvicorn.access")
        assert uv_logger.propagate is False
        assert len(uv_logger.handlers) >= 1
        handler = uv_logger.handlers[0]
        assert isinstance(
            handler.formatter,
            structlog.stdlib.ProcessorFormatter,
        )

    def test_disable_existing_loggers_false(self):
        """Existing loggers must not be silently muted after configure."""
        from core.shared_tools.structured_logging import configure_logging

        # Create a logger BEFORE calling configure
        pre_logger = logging.getLogger("test.pre_existing")
        pre_logger.setLevel(logging.DEBUG)

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)

        pre_logger.info("still alive")
        stream.seek(0)
        output = stream.read()
        assert "still alive" in output

    def test_stdlib_logger_produces_structured_output(self):
        """A plain stdlib logger must produce structured JSON output."""
        record = _capture_json_log("test.stdlib", "plain stdlib message")
        assert record["event"] == "plain stdlib message"
        assert record["logger"] == "test.stdlib"
        assert record["level"] == "info"


# ---------------------------------------------------------------------------
# Phase A — context binding
# ---------------------------------------------------------------------------


class TestContextBinding:
    """Context propagation via structlog contextvars."""

    def test_context_binding_round_trip(self):
        from core.shared_tools.structured_logging import (
            bind_context,
            clear_context,
            configure_logging,
        )

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)
        clear_context()

        bind_context(company_slug="ramp", pipeline_name="gap_analysis")
        logging.getLogger("test.ctx").info("with context")

        stream.seek(0)
        record = json.loads(stream.readline().strip())
        assert record["company_slug"] == "ramp"
        assert record["pipeline_name"] == "gap_analysis"

        clear_context()

    def test_context_clear(self):
        from core.shared_tools.structured_logging import (
            bind_context,
            clear_context,
            configure_logging,
        )

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)
        clear_context()

        bind_context(company_slug="ramp")
        clear_context()
        logging.getLogger("test.ctx.clear").info("after clear")

        stream.seek(0)
        record = json.loads(stream.readline().strip())
        assert "company_slug" not in record

    def test_get_context(self):
        from core.shared_tools.structured_logging import (
            bind_context,
            clear_context,
            get_context,
        )

        clear_context()
        bind_context(task_id="t-123")
        ctx = get_context()
        assert ctx["task_id"] == "t-123"
        clear_context()


# ---------------------------------------------------------------------------
# Phase A — Settings validation
# ---------------------------------------------------------------------------


class TestLoggingSettings:
    """Verify Settings model validates logging fields."""

    def test_invalid_log_level_rejected(self):
        """Literal validation rejects bad LOG_LEVEL values."""
        from pydantic import ValidationError
        from core.config.settings import Settings

        with pytest.raises(ValidationError):
            Settings(log_level="TRACE")  # type: ignore[arg-type]

    def test_invalid_log_format_rejected(self):
        from pydantic import ValidationError
        from core.config.settings import Settings

        with pytest.raises(ValidationError):
            Settings(log_format="yaml")  # type: ignore[arg-type]

    def test_defaults_are_valid(self):
        """Default values must pass validation."""
        from core.config.settings import Settings

        s = Settings()
        assert s.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        assert s.log_format in ("console", "json")
        assert s.log_include_caller is False


# ---------------------------------------------------------------------------
# Phase A — database_echo interaction
# ---------------------------------------------------------------------------


class TestDatabaseEchoRespected:
    """sqlalchemy.engine level must follow database_echo setting."""

    def test_database_echo_true_enables_sql_logging(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(
            level="DEBUG", log_format="json", _stream=stream, database_echo=True,
        )
        sa_logger = logging.getLogger("sqlalchemy.engine")
        assert sa_logger.level <= logging.INFO

    def test_database_echo_false_suppresses_sql_logging(self):
        from core.shared_tools.structured_logging import configure_logging

        stream = io.StringIO()
        configure_logging(
            level="DEBUG", log_format="json", _stream=stream, database_echo=False,
        )
        sa_logger = logging.getLogger("sqlalchemy.engine")
        assert sa_logger.level >= logging.WARNING


# ---------------------------------------------------------------------------
# Layer 2 — get_context_value
# ---------------------------------------------------------------------------


class TestGetContextValue:
    """Convenience accessor for single context values."""

    def test_returns_bound_value(self):
        from core.shared_tools.structured_logging import (
            bind_context, clear_context, get_context_value,
        )

        clear_context()
        bind_context(request_id="req-abc-123")
        assert get_context_value("request_id") == "req-abc-123"
        clear_context()

    def test_returns_default_when_missing(self):
        from core.shared_tools.structured_logging import (
            clear_context, get_context_value,
        )

        clear_context()
        assert get_context_value("nonexistent") is None
        clear_context()

    def test_returns_custom_default(self):
        from core.shared_tools.structured_logging import (
            clear_context, get_context_value,
        )

        clear_context()
        assert get_context_value("missing_key", "fallback") == "fallback"
        clear_context()


# ---------------------------------------------------------------------------
# Layer 2 — scoped_bind
# ---------------------------------------------------------------------------


class TestScopedBind:
    """Context manager for scoped context binding with automatic restore."""

    def test_restores_previous_value(self):
        from core.shared_tools.structured_logging import (
            bind_context, clear_context, get_context_value, scoped_bind,
        )

        clear_context()
        bind_context(step_name="original")
        with scoped_bind(step_name="temporary"):
            assert get_context_value("step_name") == "temporary"
        assert get_context_value("step_name") == "original"
        clear_context()

    def test_removes_key_if_not_previously_set(self):
        from core.shared_tools.structured_logging import (
            clear_context, get_context_value, scoped_bind,
        )

        clear_context()
        with scoped_bind(agent_name="test_agent"):
            assert get_context_value("agent_name") == "test_agent"
        assert get_context_value("agent_name") is None
        clear_context()

    def test_restores_on_exception(self):
        from core.shared_tools.structured_logging import (
            bind_context, clear_context, get_context_value, scoped_bind,
        )

        clear_context()
        bind_context(step_name="before")
        with pytest.raises(RuntimeError):
            with scoped_bind(step_name="during"):
                assert get_context_value("step_name") == "during"
                raise RuntimeError("boom")
        assert get_context_value("step_name") == "before"
        clear_context()

    def test_multiple_keys_scoped(self):
        from core.shared_tools.structured_logging import (
            clear_context, get_context_value, scoped_bind,
        )

        clear_context()
        with scoped_bind(step_name="s1", agent_name="overview"):
            assert get_context_value("step_name") == "s1"
            assert get_context_value("agent_name") == "overview"
        assert get_context_value("step_name") is None
        assert get_context_value("agent_name") is None
        clear_context()

    def test_context_visible_in_json_log(self):
        from core.shared_tools.structured_logging import (
            clear_context, configure_logging, scoped_bind,
        )

        stream = io.StringIO()
        configure_logging(level="DEBUG", log_format="json", _stream=stream)
        clear_context()

        with scoped_bind(step_name="s3_search"):
            logging.getLogger("test.scoped").info("inside scope")

        stream.seek(0)
        record = json.loads(stream.readline().strip())
        assert record["step_name"] == "s3_search"
        clear_context()
