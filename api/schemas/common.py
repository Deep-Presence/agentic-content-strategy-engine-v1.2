"""Common API response and request schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class PipelineRunResponse(BaseModel):
    """Returned when a pipeline is launched."""

    run_id: str
    pipeline: str
    company_slug: str
    status: str
    created_at: datetime


class TaskResponse(BaseModel):
    """Detailed task status response."""

    run_id: str
    pipeline: str
    company_slug: str
    status: str
    current_step: Optional[str] = None
    progress_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    approval_payload: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: Optional[str] = None


# ── Request schemas ───────────────────────────────────────────────────


class GapAnalysisStartRequest(BaseModel):
    """Simplified request body for starting a gap analysis pipeline.

    The frontend only needs company_name + domain.  The backend auto-resolves
    research artifact paths (company_context, personas, style_guide) from the
    filesystem based on the company slug.
    """

    company_name: str
    domain: str
    seed_urls: List[HttpUrl] = Field(default_factory=list)
    skip_steps: List[int] = Field(default_factory=list)
    max_queries: int = Field(default=150, ge=10, le=500)
    platforms: List[str] = Field(
        default=["perplexity", "openai", "gemini", "claude"],
    )
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    max_crawl_pages: Optional[int] = None
    max_crawl_depth: Optional[int] = None


class ResearchStartRequest(BaseModel):
    """Simplified request body for starting a research pipeline.

    The frontend only needs to provide company_name + domain.  The backend
    constructs the per-stage inputs and chains artifact paths automatically.
    """

    company_name: str
    domain: str
    seed_urls: List[HttpUrl] = Field(default_factory=list)
    stages: List[Literal["company", "persona", "style_guide"]] = Field(
        default=["company", "persona", "style_guide"],
        description="Which research stages to run. Order is always company → persona → style_guide.",
    )
    auto_approve: bool = False
    language: str = "en"
    region: Optional[str] = None
    max_personas: int = Field(default=3, ge=1, le=3)
    internal_sources: List[str] = Field(default_factory=list)
    additional_constraints: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request body for approving/revising/rejecting a HITL decision."""

    decision: Literal["approve", "revise", "reject"]
    revision_note: Optional[str] = None


class ContentStartRequest(BaseModel):
    """Request body for starting a content generation pipeline."""

    input_data: Dict[str, Any]


class ContentApprovalRequest(BaseModel):
    """Request body for approving content generation pieces."""

    brief_id: str
    decision: Literal["approve", "edit", "reject"]
    editor_notes: Optional[str] = None


# ── Approval / action response schemas ───────────────────────────────


class ApprovalResponse(BaseModel):
    """Returned after submitting an approval decision."""

    run_id: str
    decision: str
    revision_note: Optional[str] = None


class ContentApprovalResponse(BaseModel):
    """Returned after submitting a content approval decision."""

    run_id: str
    brief_id: str
    decision: str
    editor_notes: Optional[str] = None


class TaskSummary(BaseModel):
    """Lightweight task representation for list endpoints."""

    run_id: str
    pipeline: str
    status: str
    company_slug: str
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Response wrapper for task listing."""

    tasks: List[TaskSummary]


class CancelResponse(BaseModel):
    """Returned after cancelling a task."""

    run_id: str
    status: str
