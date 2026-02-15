"""Langfuse tracing for the Content Generation Engine.

Provides a lazy-initialised Langfuse singleton and helper functions
for structured observability across all 4 pipeline stages.

Uses Langfuse v3 SDK API:
  - lf.start_span() creates a root span (acts as a "trace")
  - span.update_trace(session_id=...) associates with a session
  - span.start_span() creates child spans
  - span.start_generation() creates LLM call records
  - span.score() attaches numeric/categorical scores

Hierarchy:
  Session: content-gen-{slug}-{timestamp}
    Root Span (trace): planner | worker/{brief_id} | evaluator/{brief_id} | review/{brief_id}
      Span: outliner | drafter | fact_enricher | formatter | structural_check | ...
        Generation: the actual LLM call
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from core.config.settings import settings

logger = logging.getLogger(__name__)

_langfuse_client = None
_init_attempted = False


def _get_langfuse():
    """Lazy singleton — returns Langfuse client or None if not configured."""
    global _langfuse_client, _init_attempted

    if _init_attempted:
        return _langfuse_client

    _init_attempted = True

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.debug("Langfuse keys not configured — tracing disabled.")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized (host=%s)", settings.langfuse_host)
    except Exception as exc:
        logger.warning("Failed to initialize Langfuse: %s", exc)
        _langfuse_client = None

    return _langfuse_client


def create_session(company_slug: str) -> str:
    """Create a Langfuse session and return its ID.

    In Langfuse v3, sessions are implicit — they're created when a trace
    references a session_id. We create an init span to register the session.
    """
    session_id = f"content-gen-{company_slug}-{int(time.time())}"
    lf = _get_langfuse()
    if lf:
        try:
            init_span = lf.start_span(
                name="session_init",
                metadata={"company_slug": company_slug},
            )
            init_span.update_trace(session_id=session_id)
            init_span.end()
        except Exception as exc:
            logger.warning("Langfuse session creation failed: %s", exc)
    return session_id


def create_trace(
    session_id: str,
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Create a root span (trace) under a session.

    In Langfuse v3, a root span with update_trace(session_id=...) serves
    as a trace grouped under a session. Returns the span object or None.
    """
    lf = _get_langfuse()
    if not lf:
        return None
    try:
        span = lf.start_span(
            name=name,
            metadata=metadata or {},
        )
        span.update_trace(session_id=session_id)
        return span
    except Exception as exc:
        logger.warning("Langfuse trace creation failed: %s", exc)
        return None


def log_generation(
    trace: Optional[Any],
    name: str,
    model: str,
    input_text: str,
    output_text: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, int]] = None,
    parent_span: Optional[Any] = None,
) -> Optional[Any]:
    """Log an LLM generation to Langfuse. Returns the generation object or None."""
    target = parent_span or trace
    if not target:
        return None
    try:
        gen = target.start_generation(
            name=name,
            model=model,
            input=input_text,
            output=output_text,
            metadata=metadata or {},
            usage_details=usage,
        )
        gen.end()
        return gen
    except Exception as exc:
        logger.warning("Langfuse generation log failed: %s", exc)
        return None


def create_span(
    trace: Optional[Any],
    name: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    parent_span: Optional[Any] = None,
) -> Optional[Any]:
    """Create a Langfuse span under a trace or parent span. Returns span or None."""
    target = parent_span or trace
    if not target:
        return None
    try:
        return target.start_span(name=name, metadata=metadata or {})
    except Exception as exc:
        logger.warning("Langfuse span creation failed: %s", exc)
        return None


def end_span(
    span: Optional[Any],
    *,
    output: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """End a Langfuse span with optional output update before ending."""
    if not span:
        return
    try:
        if output is not None or metadata:
            update_kwargs: Dict[str, Any] = {}
            if output is not None:
                update_kwargs["output"] = output
            if metadata:
                update_kwargs["metadata"] = metadata
            span.update(**update_kwargs)
        span.end()
    except Exception as exc:
        logger.warning("Langfuse span end failed: %s", exc)


def log_score(
    trace: Optional[Any],
    name: str,
    value: float | str | bool,
    *,
    comment: Optional[str] = None,
) -> None:
    """Log a score to a Langfuse trace/span."""
    if not trace:
        return
    try:
        score_kwargs: Dict[str, Any] = {"name": name, "value": value}
        if comment:
            score_kwargs["comment"] = comment
        trace.score(**score_kwargs)
    except Exception as exc:
        logger.warning("Langfuse score log failed: %s", exc)


def flush() -> None:
    """Flush any pending Langfuse events."""
    lf = _get_langfuse()
    if lf:
        try:
            lf.flush()
        except Exception as exc:
            logger.warning("Langfuse flush failed: %s", exc)
