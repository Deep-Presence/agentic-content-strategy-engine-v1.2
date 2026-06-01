"""Request/response schemas for the Voice Style Guide pipeline API.

One HITL approval endpoint (authors) + start + status + guide read.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from api.schemas.common import _check_product_slug
from core.models.voice_style_guide import VSG_MAX_AUTHORS_LIMIT, VSG_MIN_AUTHORS


# ---------------------------------------------------------------------------
# Start Request
# ---------------------------------------------------------------------------


class VoiceStyleGuideStartRequest(BaseModel):
    """Launch the voice style guide pipeline."""

    company_name: str
    domain: str
    workspace_slug: str = ""
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    max_authors: int = Field(default=VSG_MAX_AUTHORS_LIMIT, ge=VSG_MIN_AUTHORS, le=VSG_MAX_AUTHORS_LIMIT)
    auto_approve_checkpoints: List[int] = Field(
        default_factory=list,
        description="Checkpoint numbers to auto-approve (1=authors)",
    )

    @field_validator("auto_approve_checkpoints")
    @classmethod
    def _validate_auto_approve(cls, v: List[int]) -> List[int]:
        invalid = [x for x in v if x not in {1}]
        if invalid:
            raise ValueError(
                f"auto_approve_checkpoints values must be 1; got invalid: {invalid}"
            )
        return v

    force_rerun: bool = False
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


# ---------------------------------------------------------------------------
# HITL-1: Author Approval
# ---------------------------------------------------------------------------


class AuthorReviewItem(BaseModel):
    """Per-author HITL-1 decision."""

    author_id: str
    decision: Literal["approve", "modify", "reject"]
    modified_author: Optional[dict] = None


class AuthorApprovalRequest(BaseModel):
    """Request body for HITL-1 author approval."""

    batch_decision: Literal["approve_all", "partial", "reject_all"]
    author_reviews: List[AuthorReviewItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_partial(self) -> AuthorApprovalRequest:
        if self.batch_decision == "partial":
            if not self.author_reviews:
                raise ValueError(
                    "batch_decision='partial' requires at least one author_review"
                )
        return self


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ApprovalResponseVSG(BaseModel):
    """Returned after submitting a VSG approval decision."""

    status: str = "accepted"
    stage: str = ""
    message: Optional[str] = None
