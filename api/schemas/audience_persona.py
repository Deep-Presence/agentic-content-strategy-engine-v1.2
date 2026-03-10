"""Request/response schemas for the Audience Persona pipeline API.

Two HITL approval endpoints (briefs, profiles) + start + status +
standalone (add-persona, approve-persona, list).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from api.schemas.common import _check_product_slug

# Reusable persona_id / slug path-safety regex
_PERSONA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# ---------------------------------------------------------------------------
# Start Request
# ---------------------------------------------------------------------------


class AudiencePersonaStartRequest(BaseModel):
    """Launch the audience persona pipeline."""

    company_name: str
    domain: str
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    max_personas: int = Field(default=5, ge=3, le=7)
    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description="Checkpoint numbers to auto-approve (1=briefs, 2=profiles)",
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
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


# ---------------------------------------------------------------------------
# HITL-1: Brief Approval
# ---------------------------------------------------------------------------


class ManualBriefItem(BaseModel):
    """A manually entered persona brief (used in approval and standalone add)."""

    persona_name: str
    tagline: str = ""
    description: str = ""
    rationale: List[str] = Field(default_factory=list)


class BriefReviewItem(BaseModel):
    """Per-brief HITL-1 decision."""

    brief_id: str
    decision: Literal["approve", "modify", "reject"]
    modified_brief: Optional[ManualBriefItem] = None


class PersonaBriefApprovalRequest(BaseModel):
    """Request body for HITL-1 brief approval."""

    batch_decision: Literal["approve_all", "partial", "reject_all"]
    brief_reviews: List[BriefReviewItem] = Field(default_factory=list)
    added_briefs: List[ManualBriefItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_partial(self) -> PersonaBriefApprovalRequest:
        if self.batch_decision == "partial":
            if not self.brief_reviews and not self.added_briefs:
                raise ValueError(
                    "batch_decision='partial' requires at least one "
                    "brief_review or added_brief"
                )
        return self


# ---------------------------------------------------------------------------
# HITL-2: Profile Approval
# ---------------------------------------------------------------------------


class ProfileReviewItem(BaseModel):
    """Per-profile HITL-2 decision."""

    persona_id: str
    decision: Literal["approve", "revise", "reject"]
    revision_note: Optional[str] = None

    @field_validator("persona_id")
    @classmethod
    def _validate_persona_id(cls, v: str) -> str:
        if not _PERSONA_ID_RE.match(v):
            raise ValueError(
                "persona_id must match ^[a-z0-9][a-z0-9-]*$ "
                "(lowercase alphanumeric and hyphens)"
            )
        return v


class PersonaProfileApprovalRequest(BaseModel):
    """Request body for HITL-2 profile approval."""

    profile_reviews: List[ProfileReviewItem] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Standalone Endpoints
# ---------------------------------------------------------------------------


class ManualPersonaBriefRequest(BaseModel):
    """Request body for standalone /add-persona."""

    persona_name: str
    tagline: str = ""
    description: str = ""
    rationale: List[str] = Field(default_factory=list)

    @field_validator("persona_name")
    @classmethod
    def _validate_persona_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("persona_name must not be empty")
        return v


class StandaloneApproveRequest(BaseModel):
    """Request body for standalone persona approve/reject."""

    decision: Literal["approve", "reject"]


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ApprovalResponseAP(BaseModel):
    """Returned after submitting an AP approval decision."""

    status: str = "accepted"
    stage: str = ""
    message: Optional[str] = None


class PersonaListItem(BaseModel):
    """Single persona entry in the list response."""

    persona_id: str = ""
    persona_name: str = ""
    tagline: str = ""
    kind: str = "secondary"
    status: str = "missing"
    current_version: int = 0
    last_updated: Optional[datetime] = None
    created_by: str = "agent"
    word_count: int = 0


class PersonaListResponse(BaseModel):
    """Response for GET /personas list."""

    slug: str = ""
    personas: List[PersonaListItem] = Field(default_factory=list)
    total: int = 0
