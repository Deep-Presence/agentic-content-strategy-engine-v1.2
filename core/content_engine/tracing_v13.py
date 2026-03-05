"""Re-export shim — all tracing now lives in core.shared_tools.tracing.

This file is kept for backward compatibility so that all existing imports
(``from core.content_engine.tracing_v13 import create_span, ...``) continue
to work without any callsite changes.
"""
from core.shared_tools.tracing import (  # noqa: F401 — re-exports
    create_pipeline_trace,
    create_research_trace,
    create_session,
    create_span,
    create_trace,
    end_span,
    flush,
    get_current_span,
    log_generation,
    log_score,
    set_current_span,
    update_trace_output,
)

__all__ = [
    "create_pipeline_trace",
    "create_research_trace",
    "create_session",
    "create_span",
    "create_trace",
    "end_span",
    "flush",
    "get_current_span",
    "log_generation",
    "log_score",
    "set_current_span",
    "update_trace_output",
]
