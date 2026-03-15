"""Request/response schemas for the Onboarding Pipeline Orchestrator API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class OnboardingStartRequest(BaseModel):
    """Request body for POST /api/v1/onboarding/start.

    company_name and domain are NOT in the request — resolved from auth token.
    The user provides industry, seed_personas, and pipeline-level config.
    """

    # Onboarding-specific
    industry: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Company industry (e.g. 'Fintech', 'SaaS', 'Healthcare')",
    )
    seed_personas: List[str] = Field(
        default_factory=list,
        max_length=7,
        description="User-provided persona descriptions (e.g. 'VP of Engineering at B2B SaaS')",
    )

    # Site Audit config
    seed_urls: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="Seed URLs for KB and GA pipelines",
    )
    max_pages: int = Field(default=200, ge=10, le=500)
    max_depth: int = Field(default=4, ge=1, le=10)

    # AP config
    max_personas: int = Field(default=5, ge=3, le=7)

    # VSG config
    max_authors: int = Field(default=3, ge=2, le=3)

    # GA config
    max_queries: int = Field(default=75, ge=10, le=500)
    platforms: List[str] = Field(
        default_factory=lambda: ["perplexity", "openai", "gemini", "claude"],
    )

    # Shared
    language: str = "en"
    region: Optional[str] = None

    # Re-run control
    force_rerun: bool = False
