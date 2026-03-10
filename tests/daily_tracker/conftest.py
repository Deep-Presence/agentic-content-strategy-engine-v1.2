"""Shared fixtures for daily tracker tests.

Provides factory functions for creating test instances of all daily
tracker Pydantic models with sensible defaults.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.models.daily_tracker import (
    CompetitorMetrics,
    DailyRunConfig,
    DailyRunResult,
    MentionAnalysis,
    Platform,
    PlatformResponse,
    PromptCategory,
    PromptLibraryFilter,
    PromptSource,
    PromptStatus,
    RunStatus,
    TrackedPrompt,
    TrendDataPoint,
    VisibilityMetrics,
)


_NOW = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def now() -> datetime:
    """Fixed UTC timestamp for deterministic tests."""
    return _NOW


@pytest.fixture()
def sample_tracked_prompt(now: datetime) -> TrackedPrompt:
    """A fully populated TrackedPrompt instance."""
    return TrackedPrompt(
        id="prompt-001",
        company_id="company-abc",
        text="What is the best corporate expense management tool?",
        category=PromptCategory.PRODUCT_COMPARISON.value,
        tags=["expense", "comparison"],
        source=PromptSource.MANUAL,
        source_metadata=None,
        active=True,
        platforms=[Platform.OPENAI.value, Platform.CLAUDE.value],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def sample_platform_response(now: datetime) -> PlatformResponse:
    """A fully populated PlatformResponse instance."""
    return PlatformResponse(
        prompt_id="prompt-001",
        engine=Platform.OPENAI.value,
        response_text="Ramp is a leading corporate card and expense management platform.",
        latency_ms=1234.5,
        error=None,
        timestamp=now,
    )


@pytest.fixture()
def sample_mention_analysis() -> MentionAnalysis:
    """A fully populated MentionAnalysis instance."""
    return MentionAnalysis(
        brand_mentioned=True,
        brand_mention_count=2,
        competitor_mentions={"Brex": 1, "Divvy": 0},
        citations=["https://ramp.com/blog/expense-management"],
        citation_rank=1,
    )


@pytest.fixture()
def sample_daily_run_result(now: datetime) -> DailyRunResult:
    """A fully populated DailyRunResult instance."""
    return DailyRunResult(
        run_id="run-001",
        company_id="company-abc",
        status=RunStatus.COMPLETED,
        responses=[],
        started_at=now,
        completed_at=now,
        error=None,
        prompt_count=10,
        engine_count=4,
    )


@pytest.fixture()
def sample_visibility_metrics() -> VisibilityMetrics:
    """A fully populated VisibilityMetrics instance."""
    return VisibilityMetrics(
        overall_mention_rate=0.75,
        by_engine={"openai": 0.8, "claude": 0.7},
        total_prompts=10,
        total_responses=20,
        brand_mention_count=15,
    )


@pytest.fixture()
def sample_trend_data_point(now: datetime) -> TrendDataPoint:
    """A fully populated TrendDataPoint instance."""
    return TrendDataPoint(
        date=now,
        mention_rate=0.8,
        response_count=40,
        run_id="run-001",
    )


@pytest.fixture()
def sample_competitor_metrics() -> CompetitorMetrics:
    """A fully populated CompetitorMetrics instance."""
    return CompetitorMetrics(
        name="Brex",
        mention_rate=0.6,
        mention_count=12,
        share_of_voice=0.3,
    )


@pytest.fixture()
def sample_run_config() -> DailyRunConfig:
    """A fully populated DailyRunConfig instance."""
    return DailyRunConfig(
        company_id="company-abc",
        prompt_ids=["prompt-001", "prompt-002"],
        engines=["openai", "claude"],
        concurrency=4,
        brand="Ramp",
        competitors=["Brex", "Divvy"],
    )


@pytest.fixture()
def sample_prompt_filter() -> PromptLibraryFilter:
    """A fully populated PromptLibraryFilter instance."""
    return PromptLibraryFilter(
        category=PromptCategory.PRODUCT_COMPARISON.value,
        tags=["expense"],
        active=True,
        source=PromptSource.MANUAL,
        search="expense",
    )
