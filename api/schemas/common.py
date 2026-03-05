"""Common API response and request schemas."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

# Shared validator for product_slug fields across all pipeline start requests.
# Rejects path-traversal attempts ("../evil"), uppercase, spaces, etc.
_PRODUCT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _check_product_slug(v: Optional[str]) -> Optional[str]:
    if v is not None and not _PRODUCT_SLUG_RE.match(v):
        raise ValueError(
            "product_slug must match ^[a-z0-9][a-z0-9-]*$ "
            "(lowercase alphanumeric and hyphens, no leading hyphen)"
        )
    return v


class PipelineRunResponse(BaseModel):
    """Returned when a pipeline is launched."""

    run_id: str
    pipeline: str
    company_slug: str
    product_slug: Optional[str] = None
    effective_slug: Optional[str] = None
    status: str
    created_at: datetime
    already_exists: bool = False
    message: Optional[str] = None


class TaskResponse(BaseModel):
    """Detailed task status response."""

    run_id: str
    pipeline: str
    company_slug: str
    product_slug: Optional[str] = None
    effective_slug: Optional[str] = None
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
    product_slug: Optional[str] = None
    seed_urls: List[HttpUrl] = Field(default_factory=list)

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)
    force_rerun: bool = False
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
    product_slug: Optional[str] = None
    seed_urls: List[HttpUrl] = Field(default_factory=list)

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)
    force_rerun: bool = False
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


_KB_DOC_TYPE_LITERAL = Literal[
    "company_overview", "customer_reviews", "competitor_registry",
    "weakness_analysis", "brand_perception",
]


class KnowledgeBaseStartRequest(BaseModel):
    """Request body for starting a Knowledge Base pipeline."""

    company_name: str
    domain: str
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    seed_urls: List[HttpUrl] = Field(default_factory=list)
    force_rerun: bool = False
    mode: Literal["full", "refresh", "single"] = "full"
    refresh_docs: Optional[List[_KB_DOC_TYPE_LITERAL]] = Field(
        default=None,
        description="Doc types to refresh (mode=refresh). Ignored if mode=full.",
    )
    single_doc: Optional[_KB_DOC_TYPE_LITERAL] = Field(
        default=None,
        description="Single doc type to run (mode=single). Ignored if mode!=single.",
    )
    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description="Checkpoint numbers to auto-approve (1, 2, 3)",
    )

    @field_validator("auto_approve_checkpoints")
    @classmethod
    def _validate_auto_approve_checkpoints(cls, v: List[int]) -> List[int]:
        invalid = [x for x in v if x not in {1, 2, 3}]
        if invalid:
            raise ValueError(
                f"auto_approve_checkpoints values must be 1, 2, or 3; got invalid: {invalid}"
            )
        return v

    language: str = "en"
    region: Optional[str] = None
    internal_sources: List[str] = Field(default_factory=list)
    additional_constraints: Optional[str] = None
    staleness_threshold_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def _normalize_refresh_docs(self) -> KnowledgeBaseStartRequest:
        """Normalize mode/single_doc into refresh_docs for the pipeline."""
        if self.mode == "single":
            if not self.single_doc:
                raise ValueError("single_doc is required when mode='single'")
            self.refresh_docs = [self.single_doc]
        elif self.mode == "refresh":
            if not self.refresh_docs:
                raise ValueError(
                    "refresh_docs is required (non-empty list) when mode='refresh'"
                )
        elif self.mode == "full":
            self.refresh_docs = None
            self.single_doc = None
        return self


class ApprovalRequest(BaseModel):
    """Request body for approving/revising/rejecting a HITL decision."""

    decision: Literal["approve", "revise", "reject"]
    revision_note: Optional[str] = None


class ContentStartRequest(BaseModel):
    """Request body for starting a content generation pipeline."""

    company_name: str
    domain: str
    product_slug: Optional[str] = None
    max_briefs: int = Field(default=5, ge=1, le=20)

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)
    auto_approve: bool = False
    gap_slug: Optional[str] = None
    max_concurrent_workers: int = Field(default=3, ge=1, le=10)
    max_revision_cycles: int = Field(default=2, ge=0, le=5)
    skip_stages: List[int] = Field(default_factory=list)


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
    product_slug: Optional[str] = None
    effective_slug: Optional[str] = None
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Response wrapper for task listing."""

    tasks: List[TaskSummary]
    total: int = 0


class CancelResponse(BaseModel):
    """Returned after cancelling a task."""

    run_id: str
    status: str


# ---------------------------------------------------------------------------
# Knowledge Base — Health & Refresh Stale
# ---------------------------------------------------------------------------


class KBDocHealthResponse(BaseModel):
    """Per-document health status."""

    doc_type: str = ""
    status: str = "missing"
    current_version: int = 0
    last_updated: Optional[datetime] = None
    age_days: int = 0
    staleness_threshold_days: int = 90
    stale_reason: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)


class KBHealthResponse(BaseModel):
    """Overall knowledge base health report."""

    slug: str = ""
    overall_score: float = 0.0
    doc_health: Dict[str, KBDocHealthResponse] = Field(default_factory=dict)
    synthesis_version: int = 0
    synthesis_last_updated: Optional[datetime] = None
    synthesis_needs_refresh: bool = False
    stale_docs: List[str] = Field(default_factory=list)
    missing_docs: List[str] = Field(default_factory=list)
    last_full_refresh: Optional[datetime] = None


class KBRefreshStaleRequest(BaseModel):
    """Request body for the refresh-stale endpoint."""

    domain: str
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    staleness_threshold_override: Optional[int] = Field(
        default=None, ge=1, le=365,
        description="Override per-doc staleness thresholds (days).",
    )
    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description="Checkpoint IDs to auto-approve (1, 2, 3).",
    )
    include_synthesis: bool = Field(
        default=True,
        description="Whether to include synthesis in the refresh run.",
    )
