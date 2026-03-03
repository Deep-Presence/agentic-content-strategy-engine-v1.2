"""LangSmith tracing for the content engine.

Unified tracing module — replaces both the old Langfuse tracing.py and
the original v1.3-only tracing_v13.py.  All pipeline stages (v1.0 and
v1.3) import from this single module.

Backward-compatible kwargs:
  Every public function accepts the OLD Langfuse kwargs (input=, parent_span=,
  level=, status_message=, model_parameters=, user_id=, metadata= on end_span)
  as keyword-only arguments so that callers migrated by a simple import swap
  continue to work without callsite changes.

Context-var span propagation:
  LangGraph graph nodes are sync functions whose state dicts are serialised
  by MemorySaver (msgpack).  Putting a RunTree into state crashes with
  ``TypeError: Type is not msgpack serializable``.  Instead we use
  ``contextvars`` to propagate the current span out-of-band.

LangSmith provides:
  - Full trace hierarchy (pipeline → stage → worker → LLM call)
  - Trace → Playground → Re-run capability for prompt iteration
  - Integration with LiteLLM via success/failure callbacks

Configuration:
  - Set LANGSMITH_API_KEY env var to enable tracing
  - Set LANGSMITH_PROJECT to control the project name (default: "content-engine")
  - Tracing is optional — all functions return None gracefully when disabled
"""
from __future__ import annotations

import contextvars
import logging
import time
from typing import Any, Dict, List, Optional, Union

from core.config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context-var span propagation (for LangGraph sync nodes)
# ---------------------------------------------------------------------------

_current_span: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "langsmith_current_span", default=None
)


def set_current_span(span: Optional[Any]) -> None:
    """Set the current span in contextvars (for LangGraph node access)."""
    _current_span.set(span)


def get_current_span() -> Optional[Any]:
    """Get the current span from contextvars."""
    return _current_span.get()


# ---------------------------------------------------------------------------
# Lazy import + init
# ---------------------------------------------------------------------------

_langsmith_available = False

try:
    from langsmith import Client
    from langsmith.run_trees import RunTree

    _langsmith_available = True
except ImportError:
    Client = None  # type: ignore[assignment,misc]
    RunTree = None  # type: ignore[assignment,misc]


def _is_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    if not _langsmith_available:
        return False
    if not settings.langsmith_api_key:
        return False
    return True


def _get_project_name() -> str:
    """Get the LangSmith project name from env or default."""
    return settings.langsmith_project


_client_instance: Optional[Any] = None


def _get_client() -> Any:
    """Return a cached LangSmith Client singleton."""
    global _client_instance
    if _client_instance is None:
        _kwargs: dict[str, Any] = {"api_key": settings.langsmith_api_key}
        if settings.langsmith_workspace_id:
            _kwargs["workspace_id"] = settings.langsmith_workspace_id
        _client_instance = Client(**_kwargs)
    return _client_instance


# ---------------------------------------------------------------------------
# Session + Trace Management
# ---------------------------------------------------------------------------


def create_session(company_slug: str) -> str:
    """Create a session ID for grouping traces.

    Args:
        company_slug: Company identifier for the session.

    Returns:
        Session ID string (format: "content-{slug}-{timestamp}").
    """
    return f"content-{company_slug}-{int(time.time())}"


def create_pipeline_trace(
    session_id: str,
    company_slug: str,
    company_name: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Create the top-level pipeline trace in LangSmith.

    Args:
        session_id: Session identifier for grouping.
        company_slug: Company identifier.
        company_name: Human-readable company name.
        metadata: Additional metadata to attach.

    Returns:
        RunTree instance or None if tracing is disabled.
    """
    if not _is_enabled():
        return None

    try:
        run_tree = RunTree(
            name=f"content-pipeline/{company_slug}",
            run_type="chain",
            project_name=_get_project_name(),
            inputs={
                "company_slug": company_slug,
                "company_name": company_name,
                "session_id": session_id,
            },
            extra={"metadata": metadata or {}},
        )
        run_tree.post()
        return run_tree
    except Exception as exc:
        logger.warning("Failed to create LangSmith pipeline trace: %s", exc)
        return None


def create_trace(
    session_id: str,
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
    input_data: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
    *,
    input: Optional[Any] = None,  # noqa: A002 — compat with Langfuse's input= kwarg
    user_id: Optional[str] = None,  # absorbed, not used by LangSmith
) -> Optional[Any]:
    """Create a standalone trace in LangSmith.

    Backward-compat kwargs (keyword-only, silently absorbed):
        input: Alias for input_data (Langfuse callers pass ``input=``).
        user_id: Ignored — LangSmith traces don't have user_id.

    Args:
        session_id: Session identifier.
        name: Trace name.
        metadata: Additional metadata.
        input_data: Input data to attach.
        tags: Tags for filtering.

    Returns:
        RunTree instance or None.
    """
    effective_input = input_data if input_data is not None else input
    if not _is_enabled():
        return None

    try:
        run_tree = RunTree(
            name=name,
            run_type="chain",
            project_name=_get_project_name(),
            inputs=effective_input or {},
            extra={"metadata": metadata or {}, "tags": tags or []},
        )
        run_tree.post()
        return run_tree
    except Exception as exc:
        logger.warning("Failed to create LangSmith trace '%s': %s", name, exc)
        return None


# ---------------------------------------------------------------------------
# Span Management
# ---------------------------------------------------------------------------


def create_span(
    parent: Optional[Any],
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
    input_data: Optional[Dict[str, Any]] = None,
    *,
    input: Optional[Any] = None,  # noqa: A002 — compat with Langfuse's input= kwarg
    parent_span: Optional[Any] = None,  # absorbed — callers sometimes pass this
) -> Optional[Any]:
    """Create a child span under a parent trace/span.

    Backward-compat kwargs (keyword-only, silently absorbed):
        input: Alias for input_data (Langfuse callers pass ``input=``).
        parent_span: Ignored — parent is always the first positional arg.

    Args:
        parent: Parent RunTree (or None to skip).
        name: Span name.
        metadata: Additional metadata.
        input_data: Input data to attach.

    Returns:
        Child RunTree instance or None.
    """
    effective_input = input_data if input_data is not None else input
    if parent is None or not _is_enabled():
        return None

    try:
        child = parent.create_child(
            name=name,
            run_type="chain",
            inputs=effective_input or {},
            extra={"metadata": metadata or {}},
        )
        child.post()
        return child
    except Exception as exc:
        logger.warning("Failed to create LangSmith span '%s': %s", name, exc)
        return None


def end_span(
    span: Optional[Any],
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    *,
    level: Optional[str] = None,  # compat: level="ERROR" maps to error=
    status_message: Optional[str] = None,  # compat: used with level="ERROR"
    metadata: Optional[Dict[str, Any]] = None,  # absorbed silently
) -> None:
    """End a span, recording output or error.

    Backward-compat kwargs (keyword-only):
        level: If ``"ERROR"`` and ``error`` is None, sets error from status_message.
        status_message: Error detail when level="ERROR".
        metadata: Ignored — LangSmith doesn't support metadata on end.

    Args:
        span: RunTree to end (or None to skip).
        output: Output data to attach.
        error: Error message if the span failed.
    """
    if span is None:
        return

    # Resolve Langfuse compat: level="ERROR" + status_message → error
    effective_error = error
    if effective_error is None and level and level.upper() == "ERROR":
        effective_error = status_message or "Error"

    try:
        if effective_error:
            span.end(error=effective_error)
        else:
            span.end(outputs=output or {})
        span.patch()
    except Exception as exc:
        logger.warning("Failed to end LangSmith span: %s", exc)


# ---------------------------------------------------------------------------
# LLM Generation Logging
# ---------------------------------------------------------------------------


def log_generation(
    parent: Optional[Any],
    name: str,
    model: str,
    input_text: Any = "",
    output_text: Any = "",
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, int]] = None,
    *,
    parent_span: Optional[Any] = None,  # compat: Langfuse callers pass this
    model_parameters: Optional[Dict[str, Any]] = None,  # absorbed into metadata
) -> None:
    """Log an LLM generation call as a child span.

    Backward-compat kwargs (keyword-only):
        parent_span: If provided AND parent is None, used as the parent.
        model_parameters: Merged into metadata dict.

    Note: When using LiteLLM with LangSmith callbacks, generation logging
    happens automatically. This function is for manual logging when needed
    (e.g., for Perplexity calls that bypass LiteLLM).

    Args:
        parent: Parent RunTree.
        name: Generation name (e.g., "plan_content", "build_brief").
        model: Model identifier used.
        input_text: Input prompt text.
        output_text: Generated output text.
        metadata: Additional metadata.
        usage: Token usage dict (prompt_tokens, completion_tokens, total_tokens).
    """
    # Resolve effective parent — Langfuse callers sometimes pass parent_span=
    effective_parent = parent if parent is not None else parent_span
    if effective_parent is None or not _is_enabled():
        return

    # Merge model_parameters into metadata if provided
    merged_metadata = {**(metadata or {}), "model": model, "usage": usage or {}}
    if model_parameters:
        merged_metadata["model_parameters"] = model_parameters

    try:
        input_str = str(input_text)[:5000] if input_text else ""
        output_str = str(output_text)[:5000] if output_text else ""

        child = effective_parent.create_child(
            name=name,
            run_type="llm",
            inputs={"input": input_str},
            extra={"metadata": merged_metadata},
        )
        child.end(outputs={"output": output_str})
        child.post()
        child.patch()
    except Exception as exc:
        logger.warning("Failed to log LangSmith generation '%s': %s", name, exc)


def log_score(
    parent: Optional[Any],
    name: str,
    value: Union[float, str, bool],
    comment: str = "",
    *,
    metadata: Optional[Dict[str, Any]] = None,  # absorbed silently
) -> None:
    """Log a score/metric on a trace.

    Backward-compat kwargs (keyword-only):
        metadata: Ignored — LangSmith create_feedback doesn't accept metadata.

    Accepts float, str, or bool values:
        - float: passed as score directly
        - bool: converted to 1.0/0.0
        - str: stored in comment (LangSmith feedback requires numeric score)

    Args:
        parent: Parent RunTree.
        name: Score name (e.g., "structural_score", "semantic_score").
        value: Score value.
        comment: Optional comment.
    """
    if parent is None or not _is_enabled():
        return

    try:
        client = _get_client()
        if isinstance(value, str):
            # LangSmith requires numeric score — put string value in comment
            feedback_comment = f"{comment} | value={value}" if comment else f"value={value}"
            client.create_feedback(
                run_id=parent.id,
                key=name,
                comment=feedback_comment,
            )
        elif isinstance(value, bool):
            client.create_feedback(
                run_id=parent.id,
                key=name,
                score=1.0 if value else 0.0,
                comment=comment,
            )
        else:
            client.create_feedback(
                run_id=parent.id,
                key=name,
                score=value,
                comment=comment,
            )
    except Exception as exc:
        logger.warning("Failed to log LangSmith score '%s': %s", name, exc)


# ---------------------------------------------------------------------------
# Trace Finalization
# ---------------------------------------------------------------------------


def update_trace_output(
    trace: Optional[Any],
    output: Optional[Dict[str, Any]] = None,
    *,
    metadata: Optional[Dict[str, Any]] = None,  # absorbed silently
    tags: Optional[List[str]] = None,  # absorbed silently
) -> None:
    """End the trace and set its final output.

    NOTE: This calls trace.end() + trace.patch() internally.
    Do NOT call end_span() after this — it would overwrite outputs with {}.

    Backward-compat kwargs (keyword-only):
        metadata: Ignored — LangSmith doesn't support metadata on end.
        tags: Ignored — LangSmith doesn't support tags on end.

    Args:
        trace: Root RunTree.
        output: Final pipeline output to attach.
    """
    if trace is None:
        return

    try:
        trace.end(outputs=output or {})
        trace.patch()
    except Exception as exc:
        logger.warning("Failed to update LangSmith trace output: %s", exc)


def flush() -> None:
    """Flush any pending LangSmith events.

    LangSmith RunTree uses post/patch which are synchronous HTTP calls,
    so there's typically nothing to flush. This is kept for API parity
    with the old Langfuse tracing module.
    """
    pass
