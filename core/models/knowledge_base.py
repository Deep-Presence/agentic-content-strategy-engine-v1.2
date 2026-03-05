"""Pydantic models for the 3-layer Knowledge Base architecture.

Layer 1 (Raw Inputs): Ephemeral — Perplexity/Claude research outputs
Layer 2 (Knowledge Base): 5 typed, versioned documents
Layer 3 (Company Profile): Synthesized artifact from L2 docs

All fields have defaults for backward compatibility with existing JSON artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KBDocType(str, Enum):
    """Knowledge base document types (5 L2 + 1 L3 synthesis)."""

    COMPANY_OVERVIEW = "company_overview"
    CUSTOMER_REVIEWS = "customer_reviews"
    COMPETITOR_REGISTRY = "competitor_registry"
    WEAKNESS_ANALYSIS = "weakness_analysis"
    BRAND_PERCEPTION = "brand_perception"
    SYNTHESIS = "synthesis"


# The five L2 doc types (excludes L3 synthesis).
# Use this instead of iterating KBDocType when only L2 docs are needed.
L2_DOC_TYPES: tuple[KBDocType, ...] = (
    KBDocType.COMPANY_OVERVIEW,
    KBDocType.CUSTOMER_REVIEWS,
    KBDocType.COMPETITOR_REGISTRY,
    KBDocType.WEAKNESS_ANALYSIS,
    KBDocType.BRAND_PERCEPTION,
)


# ---------------------------------------------------------------------------
# Storage Models
# ---------------------------------------------------------------------------


class KBDocVersion(BaseModel):
    """A single version of an L2 document."""

    version: int = 1
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    created_by: str = "agent"
    content_md: str = ""
    content_json: Optional[Dict[str, Any]] = None
    word_count: int = 0
    source_count: int = 0
    sha256: str = ""


class KBDocEntry(BaseModel):
    """Manifest entry tracking the state of one L2 document type."""

    doc_type: KBDocType = KBDocType.COMPANY_OVERVIEW
    current_version: int = 0
    last_updated: Optional[datetime] = None
    staleness_days: int = 90
    status: Literal["fresh", "stale", "missing"] = "missing"
    dependencies: List[KBDocType] = Field(default_factory=list)


class KBManifest(BaseModel):
    """Top-level manifest for a company's knowledge base."""

    slug: str = ""
    company_name: str = ""
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_full_refresh: Optional[datetime] = None
    documents: Dict[str, KBDocEntry] = Field(default_factory=dict)
    synthesis_version: int = 0
    synthesis_last_updated: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Agent I/O Models
# ---------------------------------------------------------------------------


class KBAgentResult(BaseModel):
    """Result from a single specialist agent execution."""

    doc_type: KBDocType = KBDocType.COMPANY_OVERVIEW
    version: int = 1
    content_md: str = ""
    content_json: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, str]] = Field(default_factory=list)
    word_count: int = 0
    execution_time_s: float = 0.0
    error: Optional[str] = None
    is_partial: bool = False


class KnowledgeBaseInput(BaseModel):
    """Input for the KB pipeline orchestrator."""

    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = None
    company_id: Optional[str] = None
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    seed_urls: List[str] = Field(default_factory=list)
    internal_sources: List[str] = Field(default_factory=list)
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    refresh_docs: Optional[List[KBDocType]] = None
    staleness_threshold_days: int = 30
    auto_approve_checkpoints: List[int] = Field(default_factory=list)


class KnowledgeBaseOutput(BaseModel):
    """Output from the KB pipeline orchestrator."""

    slug: str = ""
    company_name: str = ""
    manifest: Optional[KBManifest] = None
    agent_results: Dict[str, KBAgentResult] = Field(default_factory=dict)
    synthesis_md: str = ""
    company_profile_path: str = ""
    knowledge_base_dir: str = ""
    total_execution_time_s: float = 0.0


# ---------------------------------------------------------------------------
# Per-Agent Structured Output Models
# ---------------------------------------------------------------------------


class CustomerReview(BaseModel):
    """A single customer review extracted by the Customer Reviews agent."""

    quote: str = ""
    source_platform: str = ""
    source_url: Optional[str] = None
    reviewer_role: Optional[str] = None
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    themes: List[str] = Field(default_factory=list)
    date: Optional[str] = None


class CustomerReviewsStructured(BaseModel):
    """Structured output from the Customer Reviews agent."""

    total_reviews_analyzed: int = 0
    reviews: List[CustomerReview] = Field(default_factory=list)
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict)
    top_positive_themes: List[str] = Field(default_factory=list)
    top_negative_themes: List[str] = Field(default_factory=list)
    notable_quotes: List[str] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    """Profile of a single competitor."""

    name: str = ""
    domain: str = ""
    relevance: Literal["direct", "indirect", "mindshare", "niche"] = "direct"
    relevance_score: float = 0.0
    key_differentiators: List[str] = Field(default_factory=list)
    market_position: str = ""


class CompetitorRegistryStructured(BaseModel):
    """Structured output from the Competitor Scanner agent."""

    direct_competitors: List[CompetitorProfile] = Field(default_factory=list)
    mindshare_competitors: List[CompetitorProfile] = Field(default_factory=list)
    market_map: str = ""


class CompetitorWeakness(BaseModel):
    """A specific weakness identified for a competitor."""

    competitor_name: str = ""
    weakness_category: str = ""
    description: str = ""
    severity: Literal["critical", "significant", "minor"] = "minor"
    evidence: List[str] = Field(default_factory=list)
    opportunity_for_us: str = ""


class WeaknessAnalysisStructured(BaseModel):
    """Structured output from the Weakness Analyst agent."""

    per_competitor: Dict[str, List[CompetitorWeakness]] = Field(
        default_factory=dict
    )
    systemic_industry_problems: List[str] = Field(default_factory=list)
    strategic_opportunities: List[str] = Field(default_factory=list)


class BrandPerceptionStructured(BaseModel):
    """Structured output from the Brand Perception agent."""

    market_position: str = ""
    brand_positioning: str = ""
    key_differentiators: List[str] = Field(default_factory=list)
    strengths_liked_by_users: List[str] = Field(default_factory=list)
    challenges_and_pain_points: List[str] = Field(default_factory=list)
    strategic_recommendations: List[str] = Field(default_factory=list)
