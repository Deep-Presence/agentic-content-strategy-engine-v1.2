"""Tests for the Analytics Engine and all MetricCalculators.

Comprehensive tests covering:
    - Each calculator independently (mention rate, SOV, citation rate, trend)
    - AnalyticsService integration with mocked data providers
    - Edge cases: empty data, division by zero, single data point, all zeros
    - SOV sums to ~1.0 verification
    - Mention rates in [0, 1] verification
    - Trend direction correctness
    - Calculator registry tests
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from core.daily_tracker.analytics_engine import (
    AnalyticsService,
    ResponseDataProvider,
    _CALCULATOR_REGISTRY,
    get_calculator,
    list_calculators,
    register_calculator,
)
from core.daily_tracker.metrics.base import MetricCalculator
from core.daily_tracker.metrics.citation_rate import CitationRateCalculator, _extract_domain
from core.daily_tracker.metrics.mention_rate import MentionRateCalculator
from core.daily_tracker.metrics.share_of_voice import ShareOfVoiceCalculator
from core.daily_tracker.metrics.trend import TrendCalculator, _to_date, _compute_direction
from core.models.daily_tracker import (
    CompetitorMetrics,
    TrendDataPoint,
    VisibilityMetrics,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_response(
    *,
    engine: str = "openai",
    brand_mentioned: bool = False,
    brand_mention_count: int = 0,
    competitor_mentions: dict | None = None,
    citations: list[str] | None = None,
    citation_rank: int | None = None,
    timestamp: datetime | None = None,
    prompt_id: str = "p1",
    run_id: str = "r1",
) -> dict:
    """Create a platform response dict for testing."""
    return {
        "prompt_id": prompt_id,
        "engine": engine,
        "response_text": "Test response",
        "run_id": run_id,
        "timestamp": timestamp or datetime(2026, 2, 25, tzinfo=timezone.utc),
        "mention_analysis": {
            "brand_mentioned": brand_mentioned,
            "brand_mention_count": brand_mention_count,
            "competitor_mentions": competitor_mentions or {},
            "citations": citations or [],
            "citation_rank": citation_rank,
        },
    }


@pytest.fixture
def sample_responses() -> list[dict]:
    """A realistic set of platform responses for testing multiple calculators."""
    return [
        # Prompt 1, OpenAI — brand mentioned + cited
        _make_response(
            engine="openai",
            brand_mentioned=True,
            brand_mention_count=2,
            competitor_mentions={"Brex": 1, "Divvy": 0},
            citations=["https://ramp.com/blog", "https://brex.com/pricing"],
            citation_rank=1,
            prompt_id="p1",
            timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
        ),
        # Prompt 1, Claude — brand mentioned, not cited
        _make_response(
            engine="claude",
            brand_mentioned=True,
            brand_mention_count=1,
            competitor_mentions={"Brex": 1, "Divvy": 1},
            citations=[],
            prompt_id="p1",
            timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
        ),
        # Prompt 2, OpenAI — brand NOT mentioned
        _make_response(
            engine="openai",
            brand_mentioned=False,
            brand_mention_count=0,
            competitor_mentions={"Brex": 1, "Divvy": 0},
            citations=["https://brex.com/pricing"],
            prompt_id="p2",
            timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
        ),
        # Prompt 2, Claude — brand mentioned + cited
        _make_response(
            engine="claude",
            brand_mentioned=True,
            brand_mention_count=1,
            competitor_mentions={"Brex": 0, "Divvy": 0},
            citations=["https://ramp.com/features"],
            citation_rank=2,
            prompt_id="p2",
            timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def multi_day_responses() -> list[dict]:
    """Responses spanning multiple days for trend testing."""
    return [
        # Day 1: 2 responses, 1 mentioned
        _make_response(
            engine="openai", brand_mentioned=True, brand_mention_count=1,
            timestamp=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
            prompt_id="p1", run_id="r1",
        ),
        _make_response(
            engine="claude", brand_mentioned=False,
            timestamp=datetime(2026, 2, 23, 11, 0, tzinfo=timezone.utc),
            prompt_id="p2", run_id="r1",
        ),
        # Day 2: 2 responses, 2 mentioned (100%)
        _make_response(
            engine="openai", brand_mentioned=True, brand_mention_count=1,
            timestamp=datetime(2026, 2, 24, 10, 0, tzinfo=timezone.utc),
            prompt_id="p1", run_id="r2",
        ),
        _make_response(
            engine="claude", brand_mentioned=True, brand_mention_count=1,
            timestamp=datetime(2026, 2, 24, 11, 0, tzinfo=timezone.utc),
            prompt_id="p2", run_id="r2",
        ),
        # Day 3: 2 responses, 2 mentioned (100%)
        _make_response(
            engine="openai", brand_mentioned=True, brand_mention_count=1,
            timestamp=datetime(2026, 2, 25, 10, 0, tzinfo=timezone.utc),
            prompt_id="p1", run_id="r3",
        ),
        _make_response(
            engine="claude", brand_mentioned=True, brand_mention_count=1,
            timestamp=datetime(2026, 2, 25, 11, 0, tzinfo=timezone.utc),
            prompt_id="p2", run_id="r3",
        ),
    ]


# ====================================================================
# MentionRateCalculator Tests
# ====================================================================


class TestMentionRateCalculator:
    @pytest.fixture
    def calculator(self) -> MentionRateCalculator:
        return MentionRateCalculator()

    @pytest.mark.asyncio
    async def test_name(self, calculator: MentionRateCalculator) -> None:
        assert calculator.name == "mention_rate"

    @pytest.mark.asyncio
    async def test_overall_mention_rate(
        self, calculator: MentionRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(sample_responses)
        # 3 out of 4 responses have brand_mentioned=True
        assert result["overall"] == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_mention_rate_by_engine(
        self, calculator: MentionRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(sample_responses)
        by_engine = result["by_engine"]
        # OpenAI: 1/2 mentioned
        assert by_engine["openai"] == pytest.approx(0.5)
        # Claude: 2/2 mentioned
        assert by_engine["claude"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_mention_rate_empty_responses(
        self, calculator: MentionRateCalculator
    ) -> None:
        result = await calculator.compute([])
        assert result["overall"] == 0.0
        assert result["by_engine"] == {}

    @pytest.mark.asyncio
    async def test_mention_rate_all_mentioned(
        self, calculator: MentionRateCalculator
    ) -> None:
        responses = [
            _make_response(brand_mentioned=True, engine="openai"),
            _make_response(brand_mentioned=True, engine="claude"),
            _make_response(brand_mentioned=True, engine="gemini"),
        ]
        result = await calculator.compute(responses)
        assert result["overall"] == pytest.approx(1.0)
        for rate in result["by_engine"].values():
            assert rate == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_mention_rate_none_mentioned(
        self, calculator: MentionRateCalculator
    ) -> None:
        responses = [
            _make_response(brand_mentioned=False, engine="openai"),
            _make_response(brand_mentioned=False, engine="claude"),
        ]
        result = await calculator.compute(responses)
        assert result["overall"] == pytest.approx(0.0)
        for rate in result["by_engine"].values():
            assert rate == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_mention_rate_single_response(
        self, calculator: MentionRateCalculator
    ) -> None:
        result = await calculator.compute(
            [_make_response(brand_mentioned=True)]
        )
        assert result["overall"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_mention_rate_in_bounds(
        self, calculator: MentionRateCalculator, sample_responses: list[dict]
    ) -> None:
        """Verify all rates are in [0, 1]."""
        result = await calculator.compute(sample_responses)
        assert 0.0 <= result["overall"] <= 1.0
        for rate in result["by_engine"].values():
            assert 0.0 <= rate <= 1.0

    @pytest.mark.asyncio
    async def test_missing_mention_analysis(
        self, calculator: MentionRateCalculator
    ) -> None:
        """Responses without mention_analysis should default to not mentioned."""
        responses = [{"engine": "openai"}, {"engine": "claude"}]
        result = await calculator.compute(responses)
        assert result["overall"] == 0.0

    @pytest.mark.asyncio
    async def test_unknown_engine_defaults_to_unknown(
        self, calculator: MentionRateCalculator
    ) -> None:
        responses = [{"mention_analysis": {"brand_mentioned": True}}]
        result = await calculator.compute(responses)
        assert "unknown" in result["by_engine"]
        assert result["by_engine"]["unknown"] == pytest.approx(1.0)


# ====================================================================
# ShareOfVoiceCalculator Tests
# ====================================================================


class TestShareOfVoiceCalculator:
    @pytest.fixture
    def calculator(self) -> ShareOfVoiceCalculator:
        return ShareOfVoiceCalculator()

    @pytest.mark.asyncio
    async def test_name(self, calculator: ShareOfVoiceCalculator) -> None:
        assert calculator.name == "share_of_voice"

    @pytest.mark.asyncio
    async def test_sov_brand_vs_competitors(
        self, calculator: ShareOfVoiceCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(
            sample_responses,
            brand="Ramp",
            competitors=["Brex", "Divvy"],
        )
        assert 0.0 <= result["brand_sov"] <= 1.0
        # Brand has 4 mentions, Brex has 3, Divvy has 1 → total 8
        assert result["brand_sov"] == pytest.approx(4 / 8)
        assert result["competitor_sov"]["Brex"] == pytest.approx(3 / 8)
        assert result["competitor_sov"]["Divvy"] == pytest.approx(1 / 8)
        assert result["total_mentions"] == 8

    @pytest.mark.asyncio
    async def test_sov_sums_to_approximately_one(
        self, calculator: ShareOfVoiceCalculator, sample_responses: list[dict]
    ) -> None:
        """All SOV values should sum to ~1.0."""
        result = await calculator.compute(
            sample_responses,
            brand="Ramp",
            competitors=["Brex", "Divvy"],
        )
        total_sov = result["brand_sov"] + sum(result["competitor_sov"].values())
        assert total_sov == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_sov_no_competitors_specified(
        self, calculator: ShareOfVoiceCalculator, sample_responses: list[dict]
    ) -> None:
        """When no competitors specified, all competitor mentions still counted."""
        result = await calculator.compute(
            sample_responses, brand="Ramp"
        )
        # Should still have competitor SOV from the data
        assert result["brand_sov"] > 0.0
        assert result["total_mentions"] > 0

    @pytest.mark.asyncio
    async def test_sov_brand_dominates(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        """Brand mentioned in all responses, no competitors."""
        responses = [
            _make_response(brand_mentioned=True, brand_mention_count=5),
            _make_response(brand_mentioned=True, brand_mention_count=3),
        ]
        result = await calculator.compute(responses, brand="Ramp")
        assert result["brand_sov"] == pytest.approx(1.0)
        assert result["total_mentions"] == 8

    @pytest.mark.asyncio
    async def test_sov_brand_absent(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        """Brand never mentioned, only competitors."""
        responses = [
            _make_response(
                brand_mentioned=False,
                competitor_mentions={"Brex": 2},
            ),
            _make_response(
                brand_mentioned=False,
                competitor_mentions={"Brex": 1},
            ),
        ]
        result = await calculator.compute(
            responses, brand="Ramp", competitors=["Brex"]
        )
        assert result["brand_sov"] == pytest.approx(0.0)
        assert result["competitor_sov"]["Brex"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_sov_empty_responses(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        result = await calculator.compute([], brand="Ramp")
        assert result["brand_sov"] == 0.0
        assert result["total_mentions"] == 0

    @pytest.mark.asyncio
    async def test_sov_all_zeros(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        """All mention counts are zero."""
        responses = [
            _make_response(brand_mentioned=False, brand_mention_count=0),
            _make_response(brand_mentioned=False, brand_mention_count=0),
        ]
        result = await calculator.compute(responses, brand="Ramp")
        assert result["brand_sov"] == 0.0
        assert result["total_mentions"] == 0

    @pytest.mark.asyncio
    async def test_sov_boolean_competitor_mentions(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        """Handle legacy boolean competitor mentions (True/False instead of int)."""
        responses = [
            _make_response(
                brand_mentioned=True,
                brand_mention_count=1,
                competitor_mentions={"Brex": True, "Divvy": False},
            ),
        ]
        result = await calculator.compute(
            responses, brand="Ramp", competitors=["Brex", "Divvy"]
        )
        # Brand=1, Brex=1 (True→1), Divvy=0 (False→0) → total=2
        assert result["brand_sov"] == pytest.approx(0.5)
        assert result["competitor_sov"]["Brex"] == pytest.approx(0.5)
        assert result["competitor_sov"]["Divvy"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_sov_filters_by_tracked_competitors(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        """Only tracked competitors should appear in results."""
        responses = [
            _make_response(
                brand_mentioned=True,
                brand_mention_count=1,
                competitor_mentions={"Brex": 2, "Divvy": 1, "Bill": 3},
            ),
        ]
        result = await calculator.compute(
            responses, brand="Ramp", competitors=["Brex"]
        )
        # Bill is not tracked, so should not appear
        assert "Bill" not in result["competitor_sov"]
        assert "Brex" in result["competitor_sov"]
        # total = brand(1) + Brex(2) = 3
        assert result["total_mentions"] == 3

    @pytest.mark.asyncio
    async def test_sov_brand_mentioned_true_but_count_zero(
        self, calculator: ShareOfVoiceCalculator
    ) -> None:
        """Fallback: brand_mentioned=True with count=0 should count as 1."""
        responses = [
            _make_response(brand_mentioned=True, brand_mention_count=0),
        ]
        result = await calculator.compute(responses, brand="Ramp")
        assert result["brand_sov"] == pytest.approx(1.0)
        assert result["total_mentions"] == 1


# ====================================================================
# CitationRateCalculator Tests
# ====================================================================


class TestCitationRateCalculator:
    @pytest.fixture
    def calculator(self) -> CitationRateCalculator:
        return CitationRateCalculator()

    @pytest.mark.asyncio
    async def test_name(self, calculator: CitationRateCalculator) -> None:
        assert calculator.name == "citation_rate"

    @pytest.mark.asyncio
    async def test_overall_citation_rate(
        self, calculator: CitationRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(sample_responses)
        # 3 out of 4 responses have citations
        assert result["overall_citation_rate"] == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_avg_citation_rank(
        self, calculator: CitationRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(sample_responses)
        # Ranks: 1, 2 → avg = 1.5
        assert result["avg_citation_rank"] == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_citation_rate_by_domain(
        self, calculator: CitationRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(
            sample_responses, brand_domains=["ramp.com"]
        )
        # ramp.com appears in 2 out of 4 responses
        assert result["by_domain"]["ramp.com"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_top_cited_urls(
        self, calculator: CitationRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(sample_responses, top_n=5)
        top_urls = result["top_cited_urls"]
        assert len(top_urls) > 0
        # brex.com/pricing appears twice
        brex_entry = next(
            (u for u in top_urls if "brex.com/pricing" in u["url"]), None
        )
        assert brex_entry is not None
        assert brex_entry["count"] == 2

    @pytest.mark.asyncio
    async def test_citation_rate_empty_responses(
        self, calculator: CitationRateCalculator
    ) -> None:
        result = await calculator.compute([])
        assert result["overall_citation_rate"] == 0.0
        assert result["avg_citation_rank"] is None
        assert result["by_domain"] == {}
        assert result["top_cited_urls"] == []

    @pytest.mark.asyncio
    async def test_citation_rate_no_citations(
        self, calculator: CitationRateCalculator
    ) -> None:
        responses = [
            _make_response(citations=[]),
            _make_response(citations=[]),
        ]
        result = await calculator.compute(responses)
        assert result["overall_citation_rate"] == 0.0
        assert result["avg_citation_rank"] is None

    @pytest.mark.asyncio
    async def test_citation_rate_all_cited(
        self, calculator: CitationRateCalculator
    ) -> None:
        responses = [
            _make_response(citations=["https://ramp.com"], citation_rank=1),
            _make_response(citations=["https://ramp.com/blog"], citation_rank=2),
        ]
        result = await calculator.compute(responses)
        assert result["overall_citation_rate"] == pytest.approx(1.0)
        assert result["avg_citation_rank"] == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_citation_rate_in_bounds(
        self, calculator: CitationRateCalculator, sample_responses: list[dict]
    ) -> None:
        result = await calculator.compute(sample_responses)
        assert 0.0 <= result["overall_citation_rate"] <= 1.0
        for rate in result["by_domain"].values():
            assert 0.0 <= rate <= 1.0

    @pytest.mark.asyncio
    async def test_top_n_limits_results(
        self, calculator: CitationRateCalculator
    ) -> None:
        responses = [
            _make_response(citations=[f"https://example.com/page{i}"])
            for i in range(20)
        ]
        result = await calculator.compute(responses, top_n=5)
        assert len(result["top_cited_urls"]) <= 5

    @pytest.mark.asyncio
    async def test_domain_dedup_per_response(
        self, calculator: CitationRateCalculator
    ) -> None:
        """Multiple URLs from the same domain in one response count as 1."""
        responses = [
            _make_response(citations=[
                "https://ramp.com/page1",
                "https://ramp.com/page2",
                "https://ramp.com/page3",
            ]),
        ]
        result = await calculator.compute(
            responses, brand_domains=["ramp.com"]
        )
        # Only 1 response, domain appears in 1 response → rate = 1.0
        assert result["by_domain"]["ramp.com"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_missing_mention_analysis(
        self, calculator: CitationRateCalculator
    ) -> None:
        responses = [{"engine": "openai"}, {"engine": "claude"}]
        result = await calculator.compute(responses)
        assert result["overall_citation_rate"] == 0.0
        assert result["avg_citation_rank"] is None


class TestExtractDomain:
    """Unit tests for the _extract_domain helper."""

    def test_normal_url(self) -> None:
        assert _extract_domain("https://ramp.com/blog/post") == "ramp.com"

    def test_http_url(self) -> None:
        assert _extract_domain("http://example.com/page") == "example.com"

    def test_subdomain(self) -> None:
        assert _extract_domain("https://blog.ramp.com/post") == "blog.ramp.com"

    def test_url_with_port(self) -> None:
        assert _extract_domain("https://localhost:8080/api") == "localhost:8080"

    def test_empty_string(self) -> None:
        assert _extract_domain("") == ""

    def test_invalid_url(self) -> None:
        # urlparse handles gracefully — may return empty netloc
        result = _extract_domain("not-a-url")
        assert isinstance(result, str)

    def test_none_input(self) -> None:
        # Should not crash
        result = _extract_domain(None)  # type: ignore[arg-type]
        assert result == ""


# ====================================================================
# TrendCalculator Tests
# ====================================================================


class TestTrendCalculator:
    @pytest.fixture
    def calculator(self) -> TrendCalculator:
        return TrendCalculator()

    @pytest.mark.asyncio
    async def test_name(self, calculator: TrendCalculator) -> None:
        assert calculator.name == "trend"

    @pytest.mark.asyncio
    async def test_daily_mention_rate_trend(
        self, calculator: TrendCalculator, multi_day_responses: list[dict]
    ) -> None:
        result = await calculator.compute(multi_day_responses)
        data_points = result["data_points"]
        # 3 days of data
        assert len(data_points) == 3
        # First day: 1/2 = 0.5
        assert data_points[0].mention_rate == pytest.approx(0.5)
        # Second day: 2/2 = 1.0
        assert data_points[1].mention_rate == pytest.approx(1.0)
        # Third day: 2/2 = 1.0
        assert data_points[2].mention_rate == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_trend_direction_up(
        self, calculator: TrendCalculator, multi_day_responses: list[dict]
    ) -> None:
        result = await calculator.compute(multi_day_responses)
        # 0.5 → 1.0 is an upward trend
        assert result["direction"] == "up"
        assert result["change_pct"] > 0

    @pytest.mark.asyncio
    async def test_trend_direction_down(
        self, calculator: TrendCalculator
    ) -> None:
        responses = [
            _make_response(
                brand_mentioned=True,
                timestamp=datetime(2026, 2, 23, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=True,
                timestamp=datetime(2026, 2, 23, 1, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=False,
                timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=False,
                timestamp=datetime(2026, 2, 25, 1, tzinfo=timezone.utc),
            ),
        ]
        result = await calculator.compute(responses)
        assert result["direction"] == "down"
        assert result["change_pct"] < 0

    @pytest.mark.asyncio
    async def test_trend_direction_stable(
        self, calculator: TrendCalculator
    ) -> None:
        responses = [
            _make_response(
                brand_mentioned=True,
                timestamp=datetime(2026, 2, 23, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=False,
                timestamp=datetime(2026, 2, 23, 1, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=True,
                timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=False,
                timestamp=datetime(2026, 2, 25, 1, tzinfo=timezone.utc),
            ),
        ]
        result = await calculator.compute(responses)
        # 50% → 50% = stable
        assert result["direction"] == "stable"

    @pytest.mark.asyncio
    async def test_trend_empty_data(
        self, calculator: TrendCalculator
    ) -> None:
        result = await calculator.compute([])
        assert result["data_points"] == []
        assert result["direction"] == "stable"
        assert result["change_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_trend_single_day(
        self, calculator: TrendCalculator
    ) -> None:
        responses = [
            _make_response(
                brand_mentioned=True,
                timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
            ),
        ]
        result = await calculator.compute(responses)
        assert len(result["data_points"]) == 1
        assert result["direction"] == "stable"
        assert result["change_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_trend_sorted_chronologically(
        self, calculator: TrendCalculator, multi_day_responses: list[dict]
    ) -> None:
        result = await calculator.compute(multi_day_responses)
        dates = [dp.date for dp in result["data_points"]]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_trend_response_counts(
        self, calculator: TrendCalculator, multi_day_responses: list[dict]
    ) -> None:
        result = await calculator.compute(multi_day_responses)
        for dp in result["data_points"]:
            assert dp.response_count == 2  # 2 responses per day in fixture

    @pytest.mark.asyncio
    async def test_trend_no_timestamps(
        self, calculator: TrendCalculator
    ) -> None:
        """Responses without timestamps should be skipped."""
        responses = [{"engine": "openai", "mention_analysis": {"brand_mentioned": True}}]
        result = await calculator.compute(responses)
        assert result["data_points"] == []
        assert result["direction"] == "stable"

    @pytest.mark.asyncio
    async def test_trend_from_zero_to_nonzero(
        self, calculator: TrendCalculator
    ) -> None:
        """Going from 0% to non-zero should report up with capped change."""
        responses = [
            _make_response(
                brand_mentioned=False,
                timestamp=datetime(2026, 2, 23, tzinfo=timezone.utc),
            ),
            _make_response(
                brand_mentioned=True,
                timestamp=datetime(2026, 2, 25, tzinfo=timezone.utc),
            ),
        ]
        result = await calculator.compute(responses)
        assert result["direction"] == "up"
        assert result["change_pct"] == 100.0


class TestToDate:
    """Unit tests for the _to_date helper."""

    def test_datetime_input(self) -> None:
        dt = datetime(2026, 2, 25, 10, 30, tzinfo=timezone.utc)
        from datetime import date
        assert _to_date(dt) == date(2026, 2, 25)

    def test_date_input(self) -> None:
        from datetime import date
        d = date(2026, 2, 25)
        assert _to_date(d) == d

    def test_string_input(self) -> None:
        from datetime import date
        assert _to_date("2026-02-25") == date(2026, 2, 25)

    def test_iso_string_with_time(self) -> None:
        from datetime import date
        assert _to_date("2026-02-25T10:30:00") == date(2026, 2, 25)

    def test_invalid_string(self) -> None:
        assert _to_date("not-a-date") is None

    def test_none_input(self) -> None:
        assert _to_date(None) is None

    def test_int_input(self) -> None:
        assert _to_date(12345) is None


class TestComputeDirection:
    """Unit tests for the _compute_direction helper."""

    def test_single_point_is_stable(self) -> None:
        points = [TrendDataPoint(mention_rate=0.5, response_count=10)]
        direction, change = _compute_direction(points)
        assert direction == "stable"
        assert change == 0.0

    def test_empty_list_is_stable(self) -> None:
        direction, change = _compute_direction([])
        assert direction == "stable"
        assert change == 0.0

    def test_up_direction(self) -> None:
        points = [
            TrendDataPoint(mention_rate=0.3, response_count=10),
            TrendDataPoint(mention_rate=0.6, response_count=10),
        ]
        direction, change = _compute_direction(points)
        assert direction == "up"
        assert change == pytest.approx(100.0)

    def test_down_direction(self) -> None:
        points = [
            TrendDataPoint(mention_rate=0.6, response_count=10),
            TrendDataPoint(mention_rate=0.3, response_count=10),
        ]
        direction, change = _compute_direction(points)
        assert direction == "down"
        assert change == pytest.approx(-50.0)

    def test_stable_within_threshold(self) -> None:
        points = [
            TrendDataPoint(mention_rate=0.50, response_count=10),
            TrendDataPoint(mention_rate=0.5045, response_count=10),
        ]
        direction, change = _compute_direction(points)
        assert direction == "stable"

    def test_zero_to_zero(self) -> None:
        points = [
            TrendDataPoint(mention_rate=0.0, response_count=10),
            TrendDataPoint(mention_rate=0.0, response_count=10),
        ]
        direction, change = _compute_direction(points)
        assert direction == "stable"
        assert change == 0.0

    def test_zero_to_nonzero(self) -> None:
        points = [
            TrendDataPoint(mention_rate=0.0, response_count=10),
            TrendDataPoint(mention_rate=0.5, response_count=10),
        ]
        direction, change = _compute_direction(points)
        assert direction == "up"
        assert change == 100.0


# ====================================================================
# Calculator Registry Tests
# ====================================================================


class TestCalculatorRegistry:
    def test_builtin_calculators_registered(self) -> None:
        """All 4 built-in calculators should be auto-registered."""
        assert "mention_rate" in _CALCULATOR_REGISTRY
        assert "share_of_voice" in _CALCULATOR_REGISTRY
        assert "citation_rate" in _CALCULATOR_REGISTRY
        assert "trend" in _CALCULATOR_REGISTRY

    def test_get_calculator(self) -> None:
        calc = get_calculator("mention_rate")
        assert calc is not None
        assert isinstance(calc, MentionRateCalculator)

    def test_get_calculator_unknown(self) -> None:
        assert get_calculator("nonexistent") is None

    def test_list_calculators(self) -> None:
        names = list_calculators()
        assert "mention_rate" in names
        assert "share_of_voice" in names
        assert "citation_rate" in names
        assert "trend" in names

    def test_register_custom_calculator(self) -> None:
        """New calculators can be registered without modifying existing code (OCP)."""

        class CustomCalculator(MetricCalculator):
            @property
            def name(self) -> str:
                return "custom_test_metric"

            async def compute(self, responses: list, **kwargs) -> dict:
                return {"value": 42}

        calc = CustomCalculator()
        register_calculator(calc)
        assert get_calculator("custom_test_metric") is calc
        # Cleanup
        _CALCULATOR_REGISTRY.pop("custom_test_metric", None)


# ====================================================================
# AnalyticsService Integration Tests
# ====================================================================


class TestAnalyticsService:
    @pytest.fixture
    def mock_data_provider(self) -> AsyncMock:
        """Mock ResponseDataProvider for testing."""
        provider = AsyncMock(spec=ResponseDataProvider)
        return provider

    @pytest.fixture
    def service(self, mock_data_provider: AsyncMock) -> AnalyticsService:
        return AnalyticsService(
            data_provider=mock_data_provider,
            brand="Ramp",
            competitors=["Brex", "Divvy"],
            brand_domains=["ramp.com"],
        )

    @pytest.mark.asyncio
    async def test_compute_visibility_metrics(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = (
            sample_responses
        )
        result = await service.compute_visibility_metrics("company-1")
        assert isinstance(result, VisibilityMetrics)
        assert result.overall_mention_rate == pytest.approx(0.75)
        assert result.total_responses == 4
        assert result.total_prompts == 2  # p1 and p2
        assert "openai" in result.by_engine
        assert "claude" in result.by_engine

    @pytest.mark.asyncio
    async def test_compute_visibility_metrics_with_run_id(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_run.return_value = (
            sample_responses
        )
        result = await service.compute_visibility_metrics(
            "company-1", run_id="run-1"
        )
        assert isinstance(result, VisibilityMetrics)
        mock_data_provider.get_responses_for_run.assert_awaited_once_with(
            "run-1"
        )

    @pytest.mark.asyncio
    async def test_compute_visibility_metrics_empty(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = []
        result = await service.compute_visibility_metrics("company-1")
        assert result.overall_mention_rate == 0.0
        assert result.total_responses == 0
        assert result.total_prompts == 0

    @pytest.mark.asyncio
    async def test_compute_mention_rate_trend(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        multi_day_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = (
            multi_day_responses
        )
        result = await service.compute_mention_rate_trend("company-1", days=30)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(dp, TrendDataPoint) for dp in result)
        mock_data_provider.get_responses_for_company.assert_awaited_once_with(
            "company-1", days=30
        )

    @pytest.mark.asyncio
    async def test_compute_mention_rate_trend_empty(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = []
        result = await service.compute_mention_rate_trend("company-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_compute_share_of_voice(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = (
            sample_responses
        )
        result = await service.compute_share_of_voice("company-1")
        assert isinstance(result, dict)
        assert "Ramp" in result
        assert result["Ramp"] > 0.0
        # Should also include competitor SOV
        assert "Brex" in result

    @pytest.mark.asyncio
    async def test_compute_share_of_voice_with_run_id(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_run.return_value = (
            sample_responses
        )
        result = await service.compute_share_of_voice(
            "company-1", run_id="run-1"
        )
        assert "Ramp" in result
        mock_data_provider.get_responses_for_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compute_citation_rate(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = (
            sample_responses
        )
        result = await service.compute_citation_rate("company-1")
        assert isinstance(result, dict)
        assert "overall_citation_rate" in result
        assert result["overall_citation_rate"] == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_compute_citation_rate_with_run_id(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_run.return_value = (
            sample_responses
        )
        result = await service.compute_citation_rate(
            "company-1", run_id="run-1"
        )
        assert "overall_citation_rate" in result
        mock_data_provider.get_responses_for_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_competitor_metrics(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_company.return_value = (
            sample_responses
        )
        result = await service.get_competitor_metrics("company-1")
        assert isinstance(result, list)
        assert len(result) == 2  # Brex and Divvy
        assert all(isinstance(cm, CompetitorMetrics) for cm in result)
        # Find Brex
        brex = next(cm for cm in result if cm.name == "Brex")
        assert brex.mention_count > 0
        assert brex.share_of_voice > 0.0

    @pytest.mark.asyncio
    async def test_get_competitor_metrics_no_competitors(
        self,
        mock_data_provider: AsyncMock,
    ) -> None:
        """Service with no competitors returns empty list."""
        service = AnalyticsService(
            data_provider=mock_data_provider,
            brand="Ramp",
        )
        mock_data_provider.get_responses_for_company.return_value = []
        result = await service.get_competitor_metrics("company-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_competitor_metrics_with_run_id(
        self,
        service: AnalyticsService,
        mock_data_provider: AsyncMock,
        sample_responses: list[dict],
    ) -> None:
        mock_data_provider.get_responses_for_run.return_value = (
            sample_responses
        )
        result = await service.get_competitor_metrics(
            "company-1", run_id="run-1"
        )
        assert len(result) == 2
        mock_data_provider.get_responses_for_run.assert_awaited()

    @pytest.mark.asyncio
    async def test_protocol_compliance(
        self, service: AnalyticsService
    ) -> None:
        """Verify AnalyticsService implements AnalyticsServiceProtocol."""
        from core.daily_tracker.protocols import AnalyticsServiceProtocol

        assert isinstance(service, AnalyticsServiceProtocol)
