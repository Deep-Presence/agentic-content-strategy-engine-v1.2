"""Request/response schemas for company settings endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── Phase 1A: User / Team Management ──────────────────────


class TeamMemberResponse(BaseModel):
    """Single team member in the list response."""

    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    created_at: datetime


class TeamListResponse(BaseModel):
    """Response for GET /settings/team."""

    members: List[TeamMemberResponse]
    total: int


class UpdateUserRequest(BaseModel):
    """Request body for PUT /settings/team/{user_id}."""

    role: Optional[Literal["superuser", "member", "viewer"]] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None


# ── Phase 1B: Company Profile ─────────────────────────────


class CompanyProfileSettingsResponse(BaseModel):
    """Response for GET /settings/profile."""

    slug: str
    name: str
    domain: str
    additional_domains: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class UpdateCompanyProfileRequest(BaseModel):
    """Request body for PUT /settings/profile."""

    name: Optional[str] = None
    domain: Optional[str] = None
    additional_domains: Optional[List[str]] = None


# ── Phase 1C: Pipeline Defaults ───────────────────────────


class PipelineDefaultsResponse(BaseModel):
    """Response for GET /settings/pipeline-defaults."""

    # Gap analysis
    max_crawl_pages: Optional[int] = None
    max_crawl_depth: Optional[int] = None
    max_queries: Optional[int] = None
    platforms: Optional[List[str]] = None

    # Research
    max_personas: Optional[int] = None
    auto_approve_research: bool = False

    # Content
    max_briefs: Optional[int] = None
    max_revision_cycles: Optional[int] = None
    auto_approve_content: bool = False

    updated_at: Optional[datetime] = None


class UpdatePipelineDefaultsRequest(BaseModel):
    """Request body for PUT /settings/pipeline-defaults.

    Only non-None fields are applied (partial update).
    """

    # Gap analysis
    max_crawl_pages: Optional[int] = Field(default=None, ge=1, le=5000)
    max_crawl_depth: Optional[int] = Field(default=None, ge=1, le=10)
    max_queries: Optional[int] = Field(default=None, ge=1, le=500)
    platforms: Optional[List[str]] = None

    # Research
    max_personas: Optional[int] = Field(default=None, ge=1, le=10)
    auto_approve_research: Optional[bool] = None

    # Content
    max_briefs: Optional[int] = Field(default=None, ge=1, le=50)
    max_revision_cycles: Optional[int] = Field(default=None, ge=0, le=5)
    auto_approve_content: Optional[bool] = None
