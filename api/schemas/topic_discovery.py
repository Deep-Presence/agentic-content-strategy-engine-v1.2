"""Request/response schemas for the Topic Discovery pipeline API.

Three HITL approval endpoints (taxonomy + subdomains + matrix) + start + status + read.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.schemas.common import _check_product_slug
from core.models.topic_discovery import BuyerStage, IntentType


# ---------------------------------------------------------------------------
# Start Request
# ---------------------------------------------------------------------------


class TopicDiscoveryStartRequest(BaseModel):
    """Launch the Topic Discovery pipeline."""

    model_config = ConfigDict(extra="forbid")

    company_name: str
    domain: str
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description=(
            "Checkpoint numbers to auto-approve "
            "(1=taxonomy, 2=matrix, 3=subdomain selection)"
        ),
    )

    @field_validator("auto_approve_checkpoints")
    @classmethod
    def _validate_auto_approve(cls, v: List[int]) -> List[int]:
        invalid = [x for x in v if x not in {1, 2, 3}]
        if invalid:
            raise ValueError(
                f"auto_approve_checkpoints values must be 1, 2, or 3; "
                f"got invalid: {invalid}"
            )
        return v

    force_rerun: bool = False
    max_expansion_rounds: int = Field(default=4, ge=1, le=10)
    dedup_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    top_n_expand: int = Field(
        default=10, ge=1, le=50,
        description="How many top-scored subdomains to expand (HITL-1.5)",
    )
    persona_filter: Optional[str] = Field(
        default=None,
        description="Optional persona_id to focus subdomain scoring/expansion",
    )
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


# ---------------------------------------------------------------------------
# HITL Approval Requests
# ---------------------------------------------------------------------------


class TaxonomyEditItem(BaseModel):
    """A single edit operation on the taxonomy."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["add", "delete", "rename", "reparent"]
    node_id: Optional[str] = None
    parent_id: Optional[str] = None
    new_parent_id: Optional[str] = None
    name: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None


class TaxonomyApprovalRequest(BaseModel):
    """Request body for HITL-1 taxonomy approval."""

    model_config = ConfigDict(extra="forbid")

    batch_decision: Literal["approve", "modify", "retry"]
    user_edits: List[TaxonomyEditItem] = Field(default_factory=list)
    user_feedback: Optional[str] = None


class MatrixEditItem(BaseModel):
    """A single edit operation on the matrix."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["adjust_priority", "remove", "add"]
    assignment_id: Optional[str] = None
    new_priority: Optional[float] = None
    topic_text: Optional[str] = None
    subdomain_name: Optional[str] = None
    buyer_stage: Optional[BuyerStage] = None
    intent_type: Optional[IntentType] = None
    audience_segment: Optional[str] = None
    priority_score: Optional[float] = None


class MatrixApprovalRequest(BaseModel):
    """Request body for HITL-2 matrix approval."""

    model_config = ConfigDict(extra="forbid")

    batch_decision: Literal["approve", "modify"]
    user_edits: List[MatrixEditItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ApprovalResponseTD(BaseModel):
    """Returned after submitting a TD approval decision."""

    status: str = "accepted"
    stage: str = ""
    message: Optional[str] = None


class TaxonomyReadResponse(BaseModel):
    """Response for GET /{slug}/taxonomy."""

    slug: str = ""
    taxonomy: Dict[str, Any] = Field(default_factory=dict)
    version: int = 0
    total_subdomains: int = 0
    coverage_score: float = 0.0


class MatrixReadResponse(BaseModel):
    """Response for GET /{slug}/matrix."""

    slug: str = ""
    matrix: Dict[str, Any] = Field(default_factory=dict)
    version: int = 0
    total_assignments: int = 0


# ---------------------------------------------------------------------------
# HITL-1.5: Subdomain Selection
# ---------------------------------------------------------------------------


class SubdomainSelectionRequest(BaseModel):
    """Request body for HITL-1.5 subdomain selection approval."""

    model_config = ConfigDict(extra="forbid")

    batch_decision: Literal["select", "select_top_n"]
    selected_subdomain_ids: List[str] = Field(default_factory=list)
    top_n: Optional[int] = Field(default=None, ge=1, le=50)
    persona_filter: Optional[str] = None


# ---------------------------------------------------------------------------
# Scored Subdomains + Persona Affinity Responses
# ---------------------------------------------------------------------------


class ScoredSubdomainsResponse(BaseModel):
    """Response for GET /{slug}/scored-subdomains."""

    slug: str = ""
    scored_subdomains: Dict[str, Any] = Field(default_factory=dict)
    version: int = 0
    total_scored: int = 0
    signals_used: List[str] = Field(default_factory=list)


class PersonaAffinityResponse(BaseModel):
    """Response for GET /{slug}/personas."""

    slug: str = ""
    persona_entries: Dict[str, Any] = Field(default_factory=dict)
    persona_metadata: Dict[str, Any] = Field(default_factory=dict)
    total_personas: int = 0
    total_subdomains: int = 0


# ---------------------------------------------------------------------------
# Pipeline B: Topic Expansion
# ---------------------------------------------------------------------------


class TopicExpansionStartRequest(BaseModel):
    """Launch the Topic Expansion pipeline (Pipeline B)."""

    model_config = ConfigDict(extra="forbid")

    company_name: str
    domain: str
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    subdomain_ids: List[str] = Field(
        min_length=1,
        description="Subdomain IDs to expand into the content matrix",
    )
    persona_filter: Optional[str] = None
    taxonomy_version: Optional[int] = None
    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description="Checkpoint 2 = auto-approve matrix",
    )

    @field_validator("auto_approve_checkpoints")
    @classmethod
    def _validate_auto_approve(cls, v: List[int]) -> List[int]:
        invalid = [x for x in v if x not in {2}]
        if invalid:
            raise ValueError(
                "Pipeline B only supports checkpoint 2 (matrix); "
                f"got invalid: {invalid}"
            )
        return v


class ExpansionStatusResponse(BaseModel):
    """Response for GET /{slug}/expansion-status."""

    slug: str = ""
    effective_slug: str = ""
    total_subdomains: int = 0
    expanded: int = 0
    not_expanded: int = 0
    expanded_ids: List[str] = Field(default_factory=list)
    available_for_expansion: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Planner CRUD: Assignments list, status update, custom creation
# ---------------------------------------------------------------------------


class AssignmentListResponse(BaseModel):
    """Response for GET /{slug}/assignments — paginated assignment list."""

    slug: str = ""
    items: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class DiscoverySummaryResponse(BaseModel):
    """Response for GET /{slug}/summary — quick overview of discovery state."""

    slug: str = ""
    company_name: str = ""
    has_taxonomy: bool = False
    taxonomy_version: int = 0
    has_matrix: bool = False
    matrix_version: int = 0
    scoring_version: int = 0
    persona_affinity_version: int = 0
    status: Optional[str] = None
    last_updated: Optional[str] = None


class AssignmentStatusUpdateRequest(BaseModel):
    """Request body for PATCH /{slug}/assignments/{id} — approve/reject/restore."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected", "not_started"]


class AssignmentStatusUpdateResponse(BaseModel):
    """Response after updating an assignment status."""

    assignment_id: str = ""
    status: str = ""
    message: str = ""


class CreateCustomAssignmentRequest(BaseModel):
    """Request body for POST /{slug}/assignments — create a custom topic."""

    model_config = ConfigDict(extra="forbid")

    topic_text: str = Field(..., min_length=5)
    subdomain_id: Optional[str] = None
    subdomain_name: Optional[str] = None
    buyer_stage: BuyerStage = BuyerStage.TOFU
    intent_type: IntentType = IntentType.informational
    persona_id: Optional[str] = None
    persona_name: Optional[str] = None
    priority_score: float = Field(default=0.5, ge=0.0, le=1.0)
