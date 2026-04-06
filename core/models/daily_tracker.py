"""Pydantic v2 models for the Daily LLM Visibility Tracker.

These models define the data contracts between daily tracker modules.
All fields have defaults for backward compatibility with persisted JSON
artifacts (per project convention).

Enums:
    Platform, PromptCategory, PromptSource, PromptStatus, RunStatus

Core models:
    TrackedPrompt, PromptLibraryFilter, DailyRunConfig, DailyRunResult,
    PlatformResponse, MentionAnalysis, VisibilityMetrics, TrendDataPoint,
    CompetitorMetrics
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    """AI platforms supported for visibility tracking."""

    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    PERPLEXITY = "perplexity"


class PromptCategory(str, Enum):
    """Categories for organizing tracked prompts."""

    BRAND_AWARENESS = "brand_awareness"
    PRODUCT_COMPARISON = "product_comparison"
    FEATURE_QUERY = "feature_query"
    INDUSTRY_KNOWLEDGE = "industry_knowledge"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    USE_CASE = "use_case"
    GENERAL = "general"


class PromptSource(str, Enum):
    """How a tracked prompt was created."""

    MANUAL = "manual"
    GAP_ANALYSIS = "gap_analysis"
    IMPORTED = "imported"
    FANOUT = "fanout"
    CONTENT_INVENTORY = "content_inventory"


class PromptStatus(str, Enum):
    """Lifecycle status of a tracked prompt."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    """Execution status of a daily visibility run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------


class TrackedPrompt(BaseModel):
    """A prompt tracked for daily visibility monitoring.

    Prompts can be created manually, imported from gap analysis queries,
    or bulk-imported from external sources.
    """

    id: str = ""
    company_id: str = ""
    text: str = ""
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: PromptSource = PromptSource.MANUAL
    source_metadata: dict[str, Any] | None = None
    active: bool = True
    platforms: list[str] = Field(default_factory=list)
    parent_prompt_id: str | None = None
    fanout_axis: str | None = None
    pinned: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PromptLibraryFilter(BaseModel):
    """Filter criteria for listing tracked prompts."""

    category: str | None = None
    tags: list[str] | None = None
    active: bool | None = None
    source: PromptSource | None = None
    search: str | None = None


class DailyRunConfig(BaseModel):
    """Configuration for a daily visibility run."""

    company_id: str = ""
    prompt_ids: list[str] | None = None
    engines: list[str] | None = None
    concurrency: int = 6
    brand: str | None = None
    competitors: list[str] | None = None


class PlatformResponse(BaseModel):
    """Raw response from a single prompt execution on one platform."""

    prompt_id: str = ""
    engine: str = ""
    response_text: str = ""
    latency_ms: float = 0.0
    error: str | None = None
    timestamp: datetime | None = None


class MentionAnalysis(BaseModel):
    """Deterministic mention/citation analysis of a platform response.

    All detection is regex/string-based — no LLM calls.
    """

    brand_mentioned: bool = False
    brand_mention_count: int = 0
    competitor_mentions: dict[str, int] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    citation_rank: int | None = None


class DailyRunResult(BaseModel):
    """Aggregate result of a daily visibility run."""

    run_id: str = ""
    company_id: str = ""
    status: RunStatus = RunStatus.PENDING
    responses: list[PlatformResponse] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    prompt_count: int = 0
    engine_count: int = 0


class VisibilityMetrics(BaseModel):
    """Aggregated visibility metrics for a company across platforms."""

    overall_mention_rate: float = 0.0
    by_engine: dict[str, float] = Field(default_factory=dict)
    total_prompts: int = 0
    total_responses: int = 0
    brand_mention_count: int = 0


class TrendDataPoint(BaseModel):
    """Single data point in a visibility trend time series."""

    date: datetime | None = None
    mention_rate: float = 0.0
    response_count: int = 0
    run_id: str = ""


class CompetitorMetrics(BaseModel):
    """Visibility metrics for a single competitor."""

    name: str = ""
    mention_rate: float = 0.0
    mention_count: int = 0
    share_of_voice: float = 0.0
    rank: int = 0
    mention_delta: float = 0.0


# ---------------------------------------------------------------------------
# Enriched Prompt Models (Phase 1 — prompt tracking table)
# ---------------------------------------------------------------------------


class EnrichedPrompt(BaseModel):
    """TrackedPrompt + computed per-prompt metrics for the main table."""

    id: str = ""
    text: str = ""
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: PromptSource = PromptSource.MANUAL
    active: bool = True
    created_at: datetime | None = None
    mention_rate: float = 0.0
    mention_delta: float = 0.0
    citation_rate: float = 0.0
    citation_delta: float = 0.0
    daily_volume: list[int] = Field(default_factory=list)
    fanout_count: int = 0
    total_responses: int = 0


class EnrichedPromptListResponse(BaseModel):
    """Response for GET /prompts/enriched."""

    prompts: list[EnrichedPrompt] = Field(default_factory=list)
    total: int = 0
    period_days: int = 7
    period_start: str = ""
    period_end: str = ""


# ---------------------------------------------------------------------------
# Per-Prompt Analytics Models (Phase 2 — drawer)
# ---------------------------------------------------------------------------


class PerPromptPlatformMetrics(BaseModel):
    """Per-engine breakdown for a single prompt's analytics drawer."""

    engine: str = ""
    response_count: int = 0
    mention_count: int = 0
    mention_rate: float = 0.0


class PromptAnalyticsResponse(BaseModel):
    """Response for GET /prompts/{id}/analytics."""

    prompt_id: str = ""
    period_days: int = 30
    mention_rate: float = 0.0
    citation_rate: float = 0.0
    competitors: list[CompetitorMetrics] = Field(default_factory=list)
    platforms: list[PerPromptPlatformMetrics] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Query Fanout Models
# ---------------------------------------------------------------------------


class FanoutQuery(BaseModel):
    """A single query variant generated by the fanout LLM call."""

    axis: str = ""
    query_text: str = ""
    reasoning: str = ""


class FanoutGenerationResult(BaseModel):
    """Result of LLM-based query fanout generation for a parent prompt."""

    parent_prompt_id: str = ""
    queries: list[FanoutQuery] = Field(default_factory=list)
    model_used: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Content-to-Prompt Generation Models
# ---------------------------------------------------------------------------


class PageContext(BaseModel):
    """Input context for content-to-prompt generation.

    Constructed from a ContentInventoryModel row — provides the page
    metadata the LLM needs to generate relevant visibility prompts.
    """

    inventory_id: str = ""
    url: str = ""
    title: str = ""
    meta_description: str = ""
    content_preview: str = ""
    categories: list[str] = Field(default_factory=list)
    detected_primary_topic: str = ""
    content_type_detected: str = ""
    word_count: int = 0


class GeneratedPagePrompt(BaseModel):
    """A single prompt generated for a content inventory page."""

    query_text: str = ""
    buyer_stage: str = ""
    intent_type: str = ""
    is_branded: bool = False
    reasoning: str = ""


class PagePromptGenerationResult(BaseModel):
    """Result of generating prompts for one content inventory page."""

    inventory_id: str = ""
    prompts: list[GeneratedPagePrompt] = Field(default_factory=list)
    model_used: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)


class ContentToPromptRunResult(BaseModel):
    """Summary of a content-to-prompt generation run (one or more pages)."""

    generation_run_id: str = ""
    pages_processed: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    prompts_created: int = 0
    prompts_deduplicated: int = 0
    errors: list[dict[str, str]] = Field(default_factory=list)
