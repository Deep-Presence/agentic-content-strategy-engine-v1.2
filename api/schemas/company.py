"""Company profile response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ProductSummary(BaseModel):
    """Lightweight product info for company profile."""

    slug: str
    name: str
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
