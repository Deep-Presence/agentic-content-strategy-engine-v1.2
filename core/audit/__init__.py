"""Audit logging module — structured audit events for auth, HITL, and pipeline actions.

Public API::

    from core.audit import (
        AuditEventType,
        AuditEvent,
        log_auth_event,
        log_hitl_decision,
        log_pipeline_launch,
        set_sink,
        get_sink,
    )
"""
from core.audit.logger import (
    get_sink,
    log_auth_event,
    log_hitl_decision,
    log_pipeline_launch,
    set_sink,
)
from core.audit.models import AuditEvent, AuditEventType

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "get_sink",
    "log_auth_event",
    "log_hitl_decision",
    "log_pipeline_launch",
    "set_sink",
]
