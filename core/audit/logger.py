"""Audit logger — public API for emitting audit events.

Each function: (1) builds an ``AuditEvent``, (2) pulls ``request_id`` /
``correlation_id`` from structlog context, (3) emits a structlog INFO event,
(4) awaits ``_sink.persist(event)`` with exception safety.

Usage::

    from core.audit import log_auth_event, AuditEventType

    await log_auth_event(
        AuditEventType.LOGIN_SUCCESS,
        user_id=user["id"],
        email=body.email,
        company_slug=company.slug,
    )
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.audit.models import AuditEvent, AuditEventType
from core.audit.sink import AuditSinkProtocol, NoOpAuditSink
from core.shared_tools.structured_logging import get_context_value

__all__ = [
    "get_sink",
    "log_auth_event",
    "log_hitl_decision",
    "log_pipeline_launch",
    "set_sink",
]

_audit_logger = logging.getLogger("audit")

# Module-level sink — default NoOp, replaced at app startup via set_sink().
_sink: AuditSinkProtocol = NoOpAuditSink()


def set_sink(sink: AuditSinkProtocol) -> None:
    """Set the audit persistence sink (called once during app startup)."""
    global _sink
    _sink = sink


def get_sink() -> AuditSinkProtocol:
    """Return the current audit sink (useful for testing)."""
    return _sink


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_event(
    event_type: AuditEventType,
    *,
    user_id: Optional[str] = None,
    company_slug: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Create an AuditEvent with context-propagated request/correlation IDs."""
    return AuditEvent(
        event_type=event_type,
        user_id=user_id,
        company_slug=company_slug,
        request_id=get_context_value("request_id"),
        correlation_id=get_context_value("correlation_id"),
        detail=detail or {},
    )


async def _emit(event: AuditEvent) -> None:
    """Emit a structlog event and persist to sink."""
    _audit_logger.info(
        event.event_type.value,
        extra={
            "audit": True,
            "user_id": event.user_id,
            "company_slug": event.company_slug,
            "detail": event.detail,
        },
    )
    try:
        await _sink.persist(event)
    except Exception:
        _audit_logger.warning(
            "audit_sink_error",
            extra={"event_type": event.event_type.value},
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def log_auth_event(
    event_type: AuditEventType,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    company_slug: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an authentication event (login, register, invite, etc.)."""
    merged_detail = dict(detail or {})
    if email:
        merged_detail["email"] = email
    event = _build_event(
        event_type,
        user_id=user_id,
        company_slug=company_slug,
        detail=merged_detail,
    )
    await _emit(event)


async def log_hitl_decision(
    *,
    user_id: str,
    run_id: str,
    pipeline: str,
    stage: str,
    decision: str,
    company_slug: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a HITL approval/rejection decision."""
    merged_detail: Dict[str, Any] = {
        "run_id": run_id,
        "pipeline": pipeline,
        "stage": stage,
        "decision": decision,
    }
    if detail:
        merged_detail.update(detail)

    event_type = (
        AuditEventType.HITL_DECISION_REJECTED
        if decision == "rejected"
        else AuditEventType.HITL_DECISION
    )
    event = _build_event(
        event_type,
        user_id=user_id,
        company_slug=company_slug,
        detail=merged_detail,
    )
    await _emit(event)


async def log_pipeline_launch(
    *,
    user_id: str,
    pipeline: str,
    company_slug: str,
    task_id: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a pipeline launch event."""
    merged_detail: Dict[str, Any] = {
        "pipeline": pipeline,
        "task_id": task_id,
    }
    if detail:
        merged_detail.update(detail)
    event = _build_event(
        AuditEventType.PIPELINE_STARTED,
        user_id=user_id,
        company_slug=company_slug,
        detail=merged_detail,
    )
    await _emit(event)
