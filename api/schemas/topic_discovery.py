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
    total_personas: int = 0
    total_subdomains: int = 0
