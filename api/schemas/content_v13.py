"""Request/response schemas for the v1.3 content engine API.

Three HITL approval endpoints + start + status.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Start Request
# ---------------------------------------------------------------------------


class ContentStartRequestV13(BaseModel):
    """Launch the v1.3 content pipeline."""

    company_name: str
    domain: str
    entry_mode: Literal["autonomous", "manual"] = "autonomous"

    # Autonomous mode
    max_topics: int = Field(default=6, ge=1, le=15)
    gap_slug: Optional[str] = None  # Resolve gap artifacts from this slug

    # Manual mode
    manual_prompt: Optional[str] = Field(default=None, max_length=2000)
    manual_description: Optional[str] = Field(default=None, max_length=2000)
    manual_cluster: Optional[str] = None

    # Product scope
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None

    # Shared options
    auto_approve: bool = False
    max_concurrent_workers: int = Field(default=3, ge=1, le=10)
    max_revision_cycles: int = Field(default=2, ge=0, le=5)
    skip_stages: List[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# HITL-1: Topic Approval
# ---------------------------------------------------------------------------


class TopicApprovalRequest(BaseModel):
    """Approve, modify, reject, or retry the Strategic Planner's selections."""

    decision: Literal["approve", "modify", "reject", "retry"]
    approved_topic_ranks: List[int] = Field(
        default_factory=list,
        description="Ranks of approved selections (for approve/modify). Must be non-negative.",
    )

    @field_validator("approved_topic_ranks")
    @classmethod
    def validate_non_negative_ranks(cls, v: List[int]) -> List[int]:
        """M1 fix: Prevent negative index injection."""
        if any(r < 0 for r in v):
            raise ValueError("All approved_topic_ranks must be non-negative")
        return v
    added_query_ids: List[str] = Field(
        default_factory=list,
        description="Additional query IDs to include (for modify).",
    )
    removed_query_ids: List[str] = Field(
        default_factory=list,
        description="Query IDs to exclude (for modify).",
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Guidance for retry (e.g., 'focus on expense-tracking').",
    )


# ---------------------------------------------------------------------------
# HITL-2: Brief Approval
# ---------------------------------------------------------------------------


class BriefApprovalRequest(BaseModel):
    """Approve, provide feedback, or reject a content blueprint."""

    brief_id: str
    decision: Literal["approve", "feedback", "reject"]
    feedback: Optional[str] = Field(
        default=None,
        description="Feedback for Agent 2 (e.g., 'emphasize ROI more').",
    )


# ---------------------------------------------------------------------------
# HITL-3: Final Content Review
# ---------------------------------------------------------------------------


class ContentApprovalRequestV13(BaseModel):
    """Approve, edit, or reject a final content piece."""

    brief_id: str
    decision: Literal["approve", "edit", "reject"]
    editor_notes: Optional[str] = Field(default=None, max_length=5000)
    rethink: bool = Field(
        default=False,
        description="If true on reject, trigger major direction change (re-brief).",
    )


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class PipelineRunResponseV13(BaseModel):
    """Response after starting the v1.3 pipeline."""

    run_id: str
    status: str = "started"
    entry_mode: str = "autonomous"
    message: Optional[str] = None


class ApprovalResponseV13(BaseModel):
    """Generic approval response."""

    status: str = "accepted"
    stage: str = ""
    brief_id: Optional[str] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Topic Discovery → Content Pipeline
# ---------------------------------------------------------------------------


SUPPORTED_SEARCH_PLATFORMS: set[str] = {"perplexity", "openai", "gemini", "claude"}


class TopicContentStartRequest(BaseModel):
    """Launch the TD → GA → CE pipeline for approved topic assignments."""

    company_name: str
    domain: str
    effective_slug: str
    topic_assignment_ids: List[str] = Field(min_length=1, max_length=20)

    @field_validator("topic_assignment_ids")
    @classmethod
    def _validate_topic_ids(cls, v: List[str]) -> List[str]:
        import uuid as _uuid

        for tid in v:
            try:
                _uuid.UUID(tid)
            except ValueError:
                raise ValueError(
                    f"Each topic_assignment_id must be a valid UUID, got: {tid!r}"
                )
        return v

    # Product scope
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None

    # Options
    auto_approve: bool = False
    platforms: List[str] = Field(
        default_factory=lambda: ["perplexity", "openai", "gemini", "claude"]
    )

    @field_validator("platforms")
    @classmethod
    def _validate_platforms(cls, v: List[str]) -> List[str]:
        invalid = [p for p in v if p not in SUPPORTED_SEARCH_PLATFORMS]
        if invalid:
            raise ValueError(
                f"Unsupported platform(s): {invalid}. "
                f"Allowed: {sorted(SUPPORTED_SEARCH_PLATFORMS)}"
            )
        return v


class TopicContentStatusItem(BaseModel):
    """Per-assignment status in a topic content run."""

    topic_assignment_id: str
    topic_text: str
    status: str
    content_piece_id: Optional[str] = None
    content_title: Optional[str] = None


class TopicContentStatusResponse(BaseModel):
    """Response for topic content status query."""

    effective_slug: str
    total_assignments: int = 0
    items: List[TopicContentStatusItem] = Field(default_factory=list)
