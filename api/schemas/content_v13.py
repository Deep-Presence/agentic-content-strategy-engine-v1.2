"""Request/response schemas for the v1.3 content engine API.

Three HITL approval endpoints + start + status.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Start Request
# ---------------------------------------------------------------------------


class ContentStartRequestV13(BaseModel):
    """Launch the v1.3 content pipeline."""

    company_name: str = ""
    domain: str = ""
    workspace_slug: str = ""
    entry_mode: Literal["autonomous", "manual"] = "autonomous"

    # Autonomous mode
    max_topics: int = Field(default=6, ge=1, le=15)
    gap_slug: Optional[str] = None  # Resolve gap artifacts from this slug

    # Manual mode
    manual_prompt: Optional[str] = Field(default=None, max_length=2000)
    manual_description: Optional[str] = Field(default=None, max_length=2000)
    manual_cluster: Optional[str] = Field(default=None, max_length=200)
    gap_query_id: Optional[str] = None  # Direct gap lookup key from Analytics
    brief_id_hint: Optional[str] = Field(
        default=None, max_length=20, pattern=r"^[A-Za-z][A-Za-z0-9]{0,9}-\d{1,4}$",
    )  # Pre-created brief_id — accepts brief-001 and display_id (WE-003)

    # Product scope
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None

    # Shared options
    auto_approve: bool = False
    max_concurrent_workers: int = Field(default=3, ge=1, le=10)
    max_revision_cycles: int = Field(default=2, ge=0, le=5)
    skip_stages: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_manual_fields(self) -> "ContentStartRequestV13":
        """Ensure manual mode has a non-empty prompt and valid skip_stages."""
        if not self.company_name.strip():
            raise ValueError("company_name is required")
        if not self.domain.strip():
            raise ValueError("domain is required")
        if self.entry_mode == "manual":
            if not self.manual_prompt or not self.manual_prompt.strip():
                raise ValueError(
                    "manual_prompt is required and must be non-empty "
                    "when entry_mode is 'manual'"
                )
            # M1-fix: normalize manual_cluster whitespace at input boundary
            if self.manual_cluster:
                self.manual_cluster = self.manual_cluster.strip()
            # H6-fix: stages 0-1 are skipped by design, stage 2 is required
            invalid_skips = set(self.skip_stages) & {0, 1, 2}
            if invalid_skips:
                raise ValueError(
                    f"Manual mode cannot skip stages {sorted(invalid_skips)}. "
                    "Stages 0-1 are already skipped by design, and stage 2 "
                    "(Brief Builder) is required. Only stages 3, 4, 5 may be skipped."
                )
        return self


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
    content_markdown: Optional[str] = Field(default=None)
    rethink: bool = Field(
        default=False,
        description="If true on reject, trigger major direction change (re-brief).",
    )


class ContentDraftRequestV13(BaseModel):
    """Save a user-edited review draft for a final content piece."""

    brief_id: str
    content_markdown: str = Field(default="")


class ContentDraftResponseV13(BaseModel):
    """Review draft payload returned by draft save/load endpoints."""

    brief_id: str = ""
    content_markdown: str = ""


class ContentDraftSaveResponseV13(BaseModel):
    """Review draft save acknowledgement."""

    status: str = "saved"
    brief_id: str = ""
    storage_key: Optional[str] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class TopicRunSummaryV13(BaseModel):
    """Durable topic-run summary for TD-entry Content Engine flows."""

    topic_run_id: str = ""
    batch_run_id: str = ""
    topic_assignment_id: str = ""
    display_id: str = ""
    topic_text: str = ""
    brief_id: str = ""
    ga_run_id: Optional[str] = None
    pipeline_task_id: Optional[str] = None
    status: str = ""
    stage: str = ""
    seq: int = 0
    content_piece_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class PipelineRunResponseV13(BaseModel):
    """Response after starting the v1.3 pipeline."""

    run_id: str = ""
    workspace_id: Optional[str] = None
    status: str = "started"
    entry_mode: str = "autonomous"
    message: Optional[str] = None
    batch_run_id: Optional[str] = None
    topic_runs: List[TopicRunSummaryV13] = Field(default_factory=list)


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

    company_name: str = ""
    domain: str = ""
    workspace_slug: str = ""
    effective_slug: str = ""
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


class TopicContentProductionRequest(BaseModel):
    """Start content production from pre-computed topic-scoped GA results.

    Phase 2 of the two-phase TD → GA → CE pipeline. The user has reviewed
    the GA results and clicked "Start Production" in the Content Studio.
    """

    company_name: str = ""
    domain: str = ""
    workspace_slug: str = ""
    effective_slug: str = ""
    topic_assignment_ids: List[str] = Field(min_length=1, max_length=20)
    ga_run_id: str  # UUID of the completed topic-scoped GA run

    @field_validator("topic_assignment_ids")
    @classmethod
    def _validate_topic_ids_prod(cls, v: List[str]) -> List[str]:
        import uuid as _uuid

        for tid in v:
            try:
                _uuid.UUID(tid)
            except ValueError:
                raise ValueError(
                    f"Each topic_assignment_id must be a valid UUID, got: {tid!r}"
                )
        return v

    @field_validator("ga_run_id")
    @classmethod
    def _validate_ga_run_id(cls, v: str) -> str:
        import uuid as _uuid

        try:
            _uuid.UUID(v)
        except ValueError:
            raise ValueError(f"ga_run_id must be a valid UUID, got: {v!r}")
        return v

    # Product scope
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None

    # Options
    auto_approve: bool = False


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


class TopicRunListResponseV13(BaseModel):
    """List response for TD-entry durable topic runs."""

    effective_slug: str = ""
    total: int = 0
    items: List[TopicRunSummaryV13] = Field(default_factory=list)


class TopicRunEventV13(BaseModel):
    """Durable append-only event for one TD-entry topic run."""

    topic_event_id: str = ""
    topic_run_id: str = ""
    topic_assignment_id: str = ""
    display_id: str = ""
    brief_id: str = ""
    event_type: str = ""
    stage: str = ""
    status: str = ""
    seq: int = 0
    content_piece_id: Optional[str] = None
    pipeline_task_id: Optional[str] = None
    payload_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class TopicRunEventListResponseV13(BaseModel):
    """List response for one durable TD-entry topic-run event stream."""

    effective_slug: str = ""
    topic_run_id: str = ""
    topic_assignment_id: str = ""
    display_id: str = ""
    topic_text: str = ""
    brief_id: str = ""
    total: int = 0
    items: List[TopicRunEventV13] = Field(default_factory=list)
