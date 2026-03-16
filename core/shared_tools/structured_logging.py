"""Structured logging foundation.

Single source of truth for logging configuration. Call ``configure_logging()``
once at app startup — every stdlib ``logging.getLogger(__name__)`` call then
produces structured output (JSON in prod, colored console in dev) with
automatic context propagation via structlog contextvars.

Lives in ``core/shared_tools/`` so both ``core/`` and ``api/`` can import it.
"""
from __future__ import annotations

import logging
import logging.config
import sys
from contextlib import contextmanager
from typing import IO, Any, Iterator, Literal, Optional

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
    merge_contextvars,
)

__all__ = [
    "configure_logging",
    "bind_context",
    "clear_context",
    "get_context",
    "get_context_value",
    "scoped_bind",
]


# ---------------------------------------------------------------------------
# Public helpers — thin wrappers for ergonomic imports
# ---------------------------------------------------------------------------


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current context (request / task scope)."""
    bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context vars (call at end of request / task)."""
    clear_contextvars()


def get_context() -> dict:
    """Return the currently bound context vars (useful for tests)."""
    return get_contextvars()


def get_context_value(key: str, default: Any = None) -> Any:
    """Return a single context value by key, or *default* if not bound."""
    return get_contextvars().get(key, default)


@contextmanager
def scoped_bind(**kwargs: Any) -> Iterator[None]:
    """Bind context values for a block, then restore previous state.

    Usage::

        with scoped_bind(step_name="s3_search"):
            # all log lines in this block include step_name="s3_search"
            ...
        # step_name reverted to its previous value (or removed)
    """
    tokens = bind_contextvars(**kwargs)
    try:
        yield
    finally:
        for token in tokens.values():
            token.var.reset(token)


# ---------------------------------------------------------------------------
# Core configuration
# ---------------------------------------------------------------------------


def configure_logging(
    *,
    level: str = "INFO",
    log_format: Literal["console", "json"] = "console",
    include_caller: bool = False,
    database_echo: bool = False,
    _stream: Optional[IO] = None,
) -> None:
    """Configure structured logging for the entire process.

    Parameters
    ----------
    level:
        Root logger level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    log_format:
        ``"console"`` for colored human-readable dev output,
        ``"json"`` for structured JSON (staging/prod).
    include_caller:
        Include module/function/lineno in every log record.
    database_echo:
        When True, set ``sqlalchemy.engine`` to INFO (respect Settings.database_echo).
        When False, suppress to WARNING.
    _stream:
        Override output stream (default: sys.stdout). Used by tests.
    """
    stream = _stream or sys.stdout

    # -- Shared processors (run on every log record) --
    shared_processors: list = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if include_caller:
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ],
            ),
        )
    shared_processors.extend([
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ])

    # Layer 7: Sensitive data masking — last processor before renderer
    from core.audit.masking import SensitiveDataMasker

    shared_processors.append(SensitiveDataMasker())

    # -- Renderer (final processor) --
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # -- Configure structlog itself (for structlog.get_logger() calls) --
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # -- Build the ProcessorFormatter for stdlib logging --
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # -- Handler --
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    # -- Idempotency: clear existing root handlers --
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # -- Uvicorn loggers: route through our formatter, no propagation --
    for uv_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(uv_name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)
        uv_logger.propagate = False

    # -- Suppress noisy third-party loggers --
    for noisy in ("httpx", "openai", "anthropic", "google", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # -- SQLAlchemy: respect database_echo --
    sa_level = logging.INFO if database_echo else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sa_level)
