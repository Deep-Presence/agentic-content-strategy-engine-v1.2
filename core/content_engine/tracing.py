"""Langfuse tracing for the Content Generation Engine.

Provides a lazy-initialised Langfuse singleton and helper functions
for structured observability across all 4 pipeline stages.

Uses Langfuse v3 SDK API:
  - lf.start_span() creates a root span (acts as a "trace")
  - span.update_trace(session_id=..., name=...) sets trace-level attributes
  - span.start_span() creates child spans
  - span.start_observation(as_type='generation') creates LLM call records
  - span.score() attaches numeric/categorical scores

Hierarchy:
  Session: content-gen-{slug}-{timestamp}
    Pipeline Trace: content-pipeline/{slug}
      Stage Spans: stage/1-planner | stage/2-workers | stage/3-evaluator | stage/4-review
    Stage Traces: planner | Worker #1: {title} | evaluator/{brief_id} | review/{brief_id}
      Observation Spans: outliner | drafter | fact_enricher | formatter | structural_check | ...
        Generations: the actual LLM calls
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

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
            init_span.update_trace(
                session_id=session_id,
                name=f"session/{company_slug}",
            )
            init_span.end()
        except Exception as exc:
            logger.warning("Langfuse session creation failed: %s", exc)
    return session_id


def create_pipeline_trace(
    session_id: str,
    company_slug: str,
    company_name: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Create a pipeline-level root trace under a session.

    This is the top-level trace that encompasses the entire 4-stage pipeline.
    Stage spans are created under this trace.

    Returns the root span object or None.
    """
    lf = _get_langfuse()
    if not lf:
        return None
    try:
        span = lf.start_span(
            name=f"content-pipeline/{company_slug}",
            input={"company_name": company_name, "company_slug": company_slug},
            metadata=metadata or {},
        )
        span.update_trace(
            session_id=session_id,
            name=f"content-pipeline/{company_slug}",
            tags=["pipeline", f"company:{company_slug}"],
            user_id=company_slug,
            input={"company_name": company_name, "company_slug": company_slug},
        )
        return span
    except Exception as exc:
        logger.warning("Langfuse pipeline trace creation failed: %s", exc)
        return None


def create_trace(
    session_id: str,
    name: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    input: Optional[Any] = None,
    tags: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> Optional[Any]:
    """Create a root span (trace) under a session.

    In Langfuse v3, a root span with update_trace(session_id=..., name=...)
    serves as a trace grouped under a session. Sets trace-level name, input,
    tags, and user_id for proper dashboard display.

    Returns the span object or None.
    """
    lf = _get_langfuse()
    if not lf:
        return None
    try:
        span = lf.start_span(
            name=name,
            input=input,
            metadata=metadata or {},
        )
        update_kwargs: Dict[str, Any] = {
            "session_id": session_id,
            "name": name,
        }
        if input is not None:
            update_kwargs["input"] = input
        if tags:
            update_kwargs["tags"] = tags
        if user_id:
            update_kwargs["user_id"] = user_id
        span.update_trace(**update_kwargs)
        return span
    except Exception as exc:
        logger.warning("Langfuse trace creation failed: %s", exc)
        return None


def update_trace_output(
    trace: Optional[Any],
    *,
    output: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
) -> None:
    """Update trace-level output after work completes.

    Call this to set the trace output, additional metadata, or tags
    on a trace that was created earlier with create_trace().
    """
    if not trace:
        return
    try:
        update_kwargs: Dict[str, Any] = {}
        if output is not None:
            update_kwargs["output"] = output
        if metadata:
            update_kwargs["metadata"] = metadata
        if tags:
            update_kwargs["tags"] = tags
        if update_kwargs:
            trace.update_trace(**update_kwargs)
    except Exception as exc:
        logger.warning("Langfuse trace output update failed: %s", exc)


def log_generation(
    trace: Optional[Any],
    name: str,
    model: str,
    input_text: Any,
    output_text: Any,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, int]] = None,
    model_parameters: Optional[Dict[str, Any]] = None,
    parent_span: Optional[Any] = None,
) -> Optional[Any]:
    """Log an LLM generation to Langfuse.

    Pass the FULL input/output — do not truncate. Langfuse handles
    arbitrary payload sizes via async batching.

    Returns the generation object or None.
    """
    target = parent_span or trace
    if not target:
        return None
    try:
        gen_kwargs: Dict[str, Any] = {
            "name": name,
            "model": model,
            "input": input_text,
            "output": output_text,
            "metadata": metadata or {},
            "usage_details": usage,
        }
        if model_parameters:
            gen_kwargs["model_parameters"] = model_parameters
        gen = target.start_observation(as_type="generation", **gen_kwargs)
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
    input: Optional[Any] = None,
    parent_span: Optional[Any] = None,
) -> Optional[Any]:
    """Create a Langfuse span under a trace or parent span.

    Returns span or None.
    """
    target = parent_span or trace
    if not target:
        return None
    try:
        span_kwargs: Dict[str, Any] = {
            "name": name,
            "metadata": metadata or {},
        }
        if input is not None:
            span_kwargs["input"] = input
        return target.start_span(**span_kwargs)
    except Exception as exc:
        logger.warning("Langfuse span creation failed: %s", exc)
        return None


def end_span(
    span: Optional[Any],
    *,
    output: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    level: Optional[str] = None,
    status_message: Optional[str] = None,
) -> None:
    """End a Langfuse span with optional output, level, and status_message."""
    if not span:
        return
    try:
        update_kwargs: Dict[str, Any] = {}
        if output is not None:
            update_kwargs["output"] = output
        if metadata:
            update_kwargs["metadata"] = metadata
        if level:
            update_kwargs["level"] = level
        if status_message:
            update_kwargs["status_message"] = status_message
        if update_kwargs:
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
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a score to a Langfuse trace/span."""
    if not trace:
        return
    try:
        score_kwargs: Dict[str, Any] = {"name": name, "value": value}
        if comment:
            score_kwargs["comment"] = comment
        if metadata:
            score_kwargs["metadata"] = metadata
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
