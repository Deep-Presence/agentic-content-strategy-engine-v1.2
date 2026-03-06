"""Task management models for the API layer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


from core.shared_tools.task_status import TaskStatus  # noqa: F401  # re-export


class ApprovalRecord(BaseModel):
    """Audit trail for HITL decisions."""

    task_id: str
    stage: str
    decision: str
    revision_note: Optional[str] = None
    decided_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class PipelineTask(BaseModel):
    """Represents a single pipeline run managed by the TaskStore."""

    task_id: str
    pipeline: Literal["research", "gap_analysis", "content", "content_v13", "site_audit", "knowledge_base", "audience_persona"]
    status: TaskStatus = TaskStatus.RUNNING
    company_slug: str = ""
    product_slug: Optional[str] = None
    effective_slug: Optional[str] = None
    current_step: Optional[str] = None
    progress_pct: Optional[float] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    approval_payload: Optional[Dict[str, Any]] = None
    approval_history: List[ApprovalRecord] = Field(default_factory=list)
