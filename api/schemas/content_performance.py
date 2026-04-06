"""Response schemas for content performance API endpoints.

All fields have defaults (project constraint — backward compat with
existing JSON artifacts).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContentPerformanceRow(BaseModel):
    """Single row in the content performance table."""

    inventory_id: str = ""
    url: str = ""
    title: str = ""
    traffic: int = 0
    ai_referrals: int = 0
    velocity: float = 0.0
    velocity_trend: str = "flat"
    freshness_days: int = 0
    lifecycle: str = "stable"
    content_type: str = ""
    word_count: int = 0
    published_at: Optional[datetime] = None
    structural_score: int = 0
    citations: int = 0
    platforms: dict[str, bool] = Field(
        default_factory=lambda: {
            "chatgpt": False,
            "claude": False,
            "gemini": False,
            "perplexity": False,
            "google_ai": False,
        },
    )
    queries_covered: int = 0


class ContentPerformanceTableResponse(BaseModel):
    """Response for the content performance table endpoint."""

    items: list[ContentPerformanceRow] = Field(default_factory=list)
    period_start: str = ""
    period_end: str = ""
    total_items: int = 0


class DailyTrafficPoint(BaseModel):
    """Single day in a traffic timeseries."""

    date: str = ""
    sessions: int = 0
    pageviews: int = 0
    ai_sessions: int = 0


class SourceBreakdownItem(BaseModel):
    """Traffic breakdown by source channel."""

    channel: str = ""
    sessions: int = 0
    percentage: float = 0.0


class AIPlatformBreakdownItem(BaseModel):
    """AI referral breakdown by platform."""

    platform: str = ""
    sessions: int = 0


class CitationTimelinePoint(BaseModel):
    """Single day in a citation timeline."""

    date: str = ""
    cited: int = 0
    total_responses: int = 0


class ContentDetailResponse(BaseModel):
    """Detailed analytics for a single content piece."""

    inventory_id: str = ""
    url: str = ""
    title: str = ""
    traffic: int = 0
    ai_referrals: int = 0
    velocity: float = 0.0
    velocity_trend: str = "flat"
    freshness_days: int = 0
    lifecycle: str = "stable"
    daily_traffic: list[DailyTrafficPoint] = Field(default_factory=list)
    source_breakdown: list[SourceBreakdownItem] = Field(default_factory=list)
    ai_platform_breakdown: list[AIPlatformBreakdownItem] = Field(
        default_factory=list,
    )
    structural_signals: Optional[dict[str, Any]] = None
    structural_score: int = 0
    citation_timeline: list[CitationTimelinePoint] = Field(default_factory=list)
    citations: int = 0
    platforms: dict[str, bool] = Field(
        default_factory=lambda: {
            "chatgpt": False,
            "claude": False,
            "gemini": False,
            "perplexity": False,
            "google_ai": False,
        },
    )
    queries_covered: int = 0


class VelocityInsight(BaseModel):
    """Velocity insight for a single content piece."""

    inventory_id: str = ""
    url: str = ""
    title: str = ""
    velocity: float = 0.0
    velocity_trend: str = "flat"
    lifecycle: str = "stable"
    traffic: int = 0


class VelocityInsightsResponse(BaseModel):
    """Response for the velocity/lifecycle insights endpoint."""

    items: list[VelocityInsight] = Field(default_factory=list)
    period_start: str = ""
    period_end: str = ""


# ── Similar Content (Cannibalization) ────────────────────────────


class SimilarContentItem(BaseModel):
    """A page semantically similar to the queried page."""

    inventory_id: str = ""
    url: str = ""
    title: str = ""
    similarity: float = 0.0
    word_count: int = 0
    content_type: str = ""
    content_preview: str = ""


class SimilarContentResponse(BaseModel):
    """Response for intra-inventory similarity (cannibalization) check."""

    page_id: str = ""
    similar_pages: list[SimilarContentItem] = Field(default_factory=list)
    threshold: float = 0.78
    embeddings_ready: bool = True
