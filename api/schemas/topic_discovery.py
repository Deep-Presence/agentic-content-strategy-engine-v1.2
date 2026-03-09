"""Request/response schemas for the Topic Discovery pipeline API.

Two HITL approval endpoints (taxonomy + matrix) + start + status + read.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from api.schemas.common import _check_product_slug


# ---------------------------------------------------------------------------
# Start Request
# ---------------------------------------------------------------------------


class TopicDiscoveryStartRequest(BaseModel):
    """Launch the Topic Discovery pipeline."""

    company_name: str
    domain: str
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description="Checkpoint numbers to auto-approve (1=taxonomy, 2=matrix)",
    )

    @field_validator("auto_approve_checkpoints")
    @classmethod
    def _validate_auto_approve(cls, v: List[int]) -> List[int]:
        invalid = [x for x in v if x not in {1, 2}]
        if invalid:
            raise ValueError(
                f"auto_approve_checkpoints values must be 1 or 2; got invalid: {invalid}"
            )
        return v

    force_rerun: bool = False
    max_expansion_rounds: int = Field(default=4, ge=1, le=10)
    dedup_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


# ---------------------------------------------------------------------------
# HITL Approval Requests
# ---------------------------------------------------------------------------


class TaxonomyEditItem(BaseModel):
    """A single edit operation on the taxonomy."""

    op: Literal["add", "delete", "rename", "reparent"]
    node_id: Optional[str] = None
    parent_id: Optional[str] = None
    new_parent_id: Optional[str] = None
    name: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None


class TaxonomyApprovalRequest(BaseModel):
    """Request body for HITL-1 taxonomy approval."""

    batch_decision: Literal["approve", "modify", "retry"]
    user_edits: List[TaxonomyEditItem] = Field(default_factory=list)
    user_feedback: Optional[str] = None


class MatrixEditItem(BaseModel):
    """A single edit operation on the matrix."""

    op: Literal["adjust_priority", "remove", "add"]
    assignment_id: Optional[str] = None
    new_priority: Optional[float] = None
    topic_text: Optional[str] = None
    subdomain_name: Optional[str] = None
    buyer_stage: Optional[str] = None
    intent_type: Optional[str] = None
    audience_segment: Optional[str] = None
    priority_score: Optional[float] = None


class MatrixApprovalRequest(BaseModel):
    """Request body for HITL-2 matrix approval."""

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
