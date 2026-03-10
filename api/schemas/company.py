"""Company profile response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ProductCreateRequest(BaseModel):
    """Request body for creating a product."""

    name: str
    slug: str
    domain: Optional[str] = None
    description: Optional[str] = None


class ProductUpdateRequest(BaseModel):
    """Request body for updating a product (all fields optional)."""

    name: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None


class ProductDetailResponse(BaseModel):
    """Full product detail including timestamps."""

    id: str
    slug: str
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    company_id: str
    created_at: datetime
    updated_at: datetime


class ProductSummary(BaseModel):
    """Lightweight product info for company profile."""

    slug: str
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    has_research: bool = False
    has_gap_analysis: bool = False
    has_content: bool = False


class ResearchArtifactSummary(BaseModel):
    """Which research artifacts exist for a company."""

    company_context: Optional[str] = None
    company_context_status: str = "none"  # "none" | "draft" | "approved"
    personas: List[str] = []
    style_guide: Optional[str] = None
    style_guide_status: str = "none"


class LatestRunSummary(BaseModel):
    """Summary of the most recent pipeline run."""

    run_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    summary: Optional[Dict[str, Any]] = None


class CompanyProfileResponse(BaseModel):
    """Full company profile including products, artifacts, and latest runs."""

    slug: str
    name: str
    domain: str
    products: List[ProductSummary] = []
    has_research: bool = False
    has_gap_analysis: bool = False
    has_content: bool = False
    research_summary: ResearchArtifactSummary = ResearchArtifactSummary()
    latest_runs: Dict[str, Optional[LatestRunSummary]] = {}
