"""Audit event models — Pydantic schemas for structured audit logging."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AuditCategory(str, Enum):
    """Top-level category for audit events."""

    AUTH = "auth"
    HITL = "hitl"
    PIPELINE = "pipeline"


class AuditEventType(str, Enum):
    """Concrete audit event types, prefixed by category."""

    # Auth events
    LOGIN_SUCCESS = "auth.login_success"
    LOGIN_FAILED = "auth.login_failed"
    REGISTER = "auth.register"
    INVITE_CREATED = "auth.invite_created"
    INVITE_REDEEMED = "auth.invite_redeemed"

    # HITL events
    HITL_DECISION = "hitl.decision"
    HITL_DECISION_REJECTED = "hitl.decision_rejected"

    # Pipeline events
    PIPELINE_STARTED = "pipeline.started"


class AuditEvent(BaseModel):
    """Structured audit event — emitted to structured logs and optionally persisted to DB."""

    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    company_slug: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)
