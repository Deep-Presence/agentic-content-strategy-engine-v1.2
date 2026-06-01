"""Request/response schemas for the Research Orchestrator API."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from api.schemas.common import _check_product_slug
from core.models.voice_style_guide import VSG_MAX_AUTHORS_LIMIT, VSG_MIN_AUTHORS


class AutoApproveRequest(BaseModel):
    """Per-pipeline auto-approve checkpoint configuration."""

    kb: List[int] = Field(default_factory=list, description="KB checkpoints to auto-approve (1, 2, 3)")
    ap: List[int] = Field(default_factory=list, description="AP checkpoints to auto-approve (1, 2)")
    vsg: List[int] = Field(default_factory=list, description="VSG checkpoints to auto-approve (1)")


class ResearchOrchestratorStartRequest(BaseModel):
    """Request body for POST /api/v1/research/start."""

    company_name: str
    domain: str
    workspace_slug: str = ""
    product_slug: Optional[str] = None

    @field_validator("product_slug")
    @classmethod
    def _validate_product_slug(cls, v: Optional[str]) -> Optional[str]:
        return _check_product_slug(v)

    # KB-specific
    seed_urls: List[HttpUrl] = Field(default_factory=list)

    # AP-specific
    max_personas: int = Field(default=5, ge=3, le=7)

    # VSG-specific
    max_authors: int = Field(default=VSG_MAX_AUTHORS_LIMIT, ge=VSG_MIN_AUTHORS, le=VSG_MAX_AUTHORS_LIMIT)

    # Orchestrator config
    force_rerun: bool = False
    auto_approve: AutoApproveRequest = Field(default_factory=AutoApproveRequest)
    skip_fresh: bool = Field(default=True, description="Skip pipelines with fresh artifacts")
    pipelines: List[Literal["kb", "ap", "vsg"]] = Field(
        default=["kb", "ap", "vsg"],
        description="Which pipelines to run. Defaults to all 3.",
    )

    # Shared
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
