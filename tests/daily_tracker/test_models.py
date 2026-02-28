"""Comprehensive tests for daily tracker Pydantic models.

Covers:
    - Default values and factory defaults
    - Enum validation
    - JSON serialization roundtrips
    - Field constraints and edge cases
    - Model construction with partial/full data
    - PromptLibraryFilter combinations
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestPlatformEnum:
    """Tests for the Platform enum."""

    def test_all_values(self) -> None:
        assert Platform.OPENAI.value == "openai"
        assert Platform.CLAUDE.value == "claude"
        assert Platform.GEMINI.value == "gemini"
        assert Platform.PERPLEXITY.value == "perplexity"

    def test_is_str_enum(self) -> None:
        assert isinstance(Platform.OPENAI, str)

    def test_member_count(self) -> None:
        assert len(Platform) == 4


class TestPromptCategoryEnum:
    """Tests for the PromptCategory enum."""

    def test_all_values(self) -> None:
        assert PromptCategory.BRAND_AWARENESS.value == "brand_awareness"
        assert PromptCategory.PRODUCT_COMPARISON.value == "product_comparison"
        assert PromptCategory.FEATURE_QUERY.value == "feature_query"
        assert PromptCategory.INDUSTRY_KNOWLEDGE.value == "industry_knowledge"
        assert PromptCategory.COMPETITOR_ANALYSIS.value == "competitor_analysis"
        assert PromptCategory.USE_CASE.value == "use_case"
        assert PromptCategory.GENERAL.value == "general"

    def test_member_count(self) -> None:
        assert len(PromptCategory) == 7


class TestPromptSourceEnum:
    """Tests for the PromptSource enum."""

    def test_all_values(self) -> None:
        assert PromptSource.MANUAL.value == "manual"
        assert PromptSource.GAP_ANALYSIS.value == "gap_analysis"
        assert PromptSource.IMPORTED.value == "imported"

    def test_member_count(self) -> None:
        assert len(PromptSource) == 3


class TestPromptStatusEnum:
    """Tests for the PromptStatus enum."""

    def test_all_values(self) -> None:
        assert PromptStatus.ACTIVE.value == "active"
        assert PromptStatus.PAUSED.value == "paused"
        assert PromptStatus.ARCHIVED.value == "archived"

    def test_member_count(self) -> None:
        assert len(PromptStatus) == 3


class TestRunStatusEnum:
    """Tests for the RunStatus enum."""

    def test_all_values(self) -> None:
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"

    def test_member_count(self) -> None:
        assert len(RunStatus) == 4


# ---------------------------------------------------------------------------
# TrackedPrompt Tests
# ---------------------------------------------------------------------------


class TestTrackedPrompt:
    """Tests for the TrackedPrompt model."""

    def test_defaults(self) -> None:
        prompt = TrackedPrompt()
        assert prompt.id == ""
        assert prompt.company_id == ""
        assert prompt.text == ""
        assert prompt.category is None
        assert prompt.tags == []
        assert prompt.source == PromptSource.MANUAL
        assert prompt.source_metadata is None
        assert prompt.active is True
        assert prompt.platforms == []
        assert prompt.created_at is None
        assert prompt.updated_at is None

    def test_full_construction(self, sample_tracked_prompt: TrackedPrompt) -> None:
        p = sample_tracked_prompt
        assert p.id == "prompt-001"
        assert p.company_id == "company-abc"
        assert p.text == "What is the best corporate expense management tool?"
        assert p.category == "product_comparison"
        assert p.tags == ["expense", "comparison"]
        assert p.source == PromptSource.MANUAL
        assert p.active is True
        assert p.platforms == ["openai", "claude"]

    def test_json_roundtrip(self, sample_tracked_prompt: TrackedPrompt) -> None:
        data = sample_tracked_prompt.model_dump(mode="json")
        restored = TrackedPrompt.model_validate(data)
        assert restored == sample_tracked_prompt

    def test_tags_default_factory_isolation(self) -> None:
        """Verify default_factory creates independent lists."""
        a = TrackedPrompt()
        b = TrackedPrompt()
        a.tags.append("test")
        assert b.tags == []

    def test_platforms_default_factory_isolation(self) -> None:
        a = TrackedPrompt()
        b = TrackedPrompt()
        a.platforms.append("openai")
        assert b.platforms == []

    def test_source_enum_validation(self) -> None:
        prompt = TrackedPrompt(source="gap_analysis")
        assert prompt.source == PromptSource.GAP_ANALYSIS

    def test_source_metadata_dict(self) -> None:
        prompt = TrackedPrompt(
            source_metadata={"cluster_name": "Brand Queries", "slug": "ramp"}
        )
        assert prompt.source_metadata["cluster_name"] == "Brand Queries"

    def test_partial_construction(self) -> None:
        prompt = TrackedPrompt(id="p1", text="test query")
        assert prompt.id == "p1"
        assert prompt.text == "test query"
        assert prompt.company_id == ""


# ---------------------------------------------------------------------------
# PromptLibraryFilter Tests
# ---------------------------------------------------------------------------


class TestPromptLibraryFilter:
    """Tests for the PromptLibraryFilter model."""

    def test_all_none_defaults(self) -> None:
        f = PromptLibraryFilter()
        assert f.category is None
        assert f.tags is None
        assert f.active is None
        assert f.source is None
        assert f.search is None

    def test_full_construction(self, sample_prompt_filter: PromptLibraryFilter) -> None:
        f = sample_prompt_filter
        assert f.category == "product_comparison"
        assert f.tags == ["expense"]
        assert f.active is True
        assert f.source == PromptSource.MANUAL
        assert f.search == "expense"

    def test_json_roundtrip(self, sample_prompt_filter: PromptLibraryFilter) -> None:
        data = sample_prompt_filter.model_dump(mode="json")
        restored = PromptLibraryFilter.model_validate(data)
        assert restored == sample_prompt_filter

    def test_partial_filter(self) -> None:
        f = PromptLibraryFilter(active=False)
        assert f.active is False
        assert f.category is None

    def test_source_filter(self) -> None:
        f = PromptLibraryFilter(source=PromptSource.GAP_ANALYSIS)
        assert f.source == PromptSource.GAP_ANALYSIS


# ---------------------------------------------------------------------------
# DailyRunConfig Tests
# ---------------------------------------------------------------------------


class TestDailyRunConfig:
    """Tests for the DailyRunConfig model."""

    def test_defaults(self) -> None:
        config = DailyRunConfig()
        assert config.company_id == ""
        assert config.prompt_ids is None
        assert config.engines is None
        assert config.concurrency == 6
        assert config.brand is None
        assert config.competitors is None

    def test_full_construction(self, sample_run_config: DailyRunConfig) -> None:
        c = sample_run_config
        assert c.company_id == "company-abc"
        assert c.prompt_ids == ["prompt-001", "prompt-002"]
        assert c.engines == ["openai", "claude"]
        assert c.concurrency == 4
        assert c.brand == "Ramp"
        assert c.competitors == ["Brex", "Divvy"]

    def test_json_roundtrip(self, sample_run_config: DailyRunConfig) -> None:
        data = sample_run_config.model_dump(mode="json")
        restored = DailyRunConfig.model_validate(data)
        assert restored == sample_run_config

    def test_none_prompt_ids_means_all(self) -> None:
        config = DailyRunConfig(company_id="co")
        assert config.prompt_ids is None

    def test_none_engines_means_all(self) -> None:
        config = DailyRunConfig(company_id="co")
        assert config.engines is None


# ---------------------------------------------------------------------------
# PlatformResponse Tests
# ---------------------------------------------------------------------------


class TestPlatformResponse:
    """Tests for the PlatformResponse model."""

    def test_defaults(self) -> None:
        r = PlatformResponse()
        assert r.prompt_id == ""
        assert r.engine == ""
        assert r.response_text == ""
        assert r.latency_ms == 0.0
        assert r.error is None
        assert r.timestamp is None

    def test_full_construction(
        self, sample_platform_response: PlatformResponse
    ) -> None:
        r = sample_platform_response
        assert r.prompt_id == "prompt-001"
        assert r.engine == "openai"
        assert "Ramp" in r.response_text
        assert r.latency_ms == 1234.5
        assert r.error is None

    def test_json_roundtrip(
        self, sample_platform_response: PlatformResponse
    ) -> None:
        data = sample_platform_response.model_dump(mode="json")
        restored = PlatformResponse.model_validate(data)
        assert restored == sample_platform_response

    def test_error_response(self) -> None:
        r = PlatformResponse(
            prompt_id="p1",
            engine="gemini",
            error="rate_limit_exceeded",
            latency_ms=500.0,
        )
        assert r.error == "rate_limit_exceeded"
        assert r.response_text == ""

    def test_zero_latency(self) -> None:
        r = PlatformResponse(latency_ms=0.0)
        assert r.latency_ms == 0.0


# ---------------------------------------------------------------------------
# MentionAnalysis Tests
# ---------------------------------------------------------------------------


class TestMentionAnalysis:
    """Tests for the MentionAnalysis model."""

    def test_defaults(self) -> None:
        m = MentionAnalysis()
        assert m.brand_mentioned is False
        assert m.brand_mention_count == 0
        assert m.competitor_mentions == {}
        assert m.citations == []
        assert m.citation_rank is None

    def test_full_construction(
        self, sample_mention_analysis: MentionAnalysis
    ) -> None:
        m = sample_mention_analysis
        assert m.brand_mentioned is True
        assert m.brand_mention_count == 2
        assert m.competitor_mentions == {"Brex": 1, "Divvy": 0}
        assert len(m.citations) == 1
        assert m.citation_rank == 1

    def test_json_roundtrip(
        self, sample_mention_analysis: MentionAnalysis
    ) -> None:
        data = sample_mention_analysis.model_dump(mode="json")
        restored = MentionAnalysis.model_validate(data)
        assert restored == sample_mention_analysis

    def test_competitor_mentions_default_factory_isolation(self) -> None:
        a = MentionAnalysis()
        b = MentionAnalysis()
        a.competitor_mentions["Brex"] = 5
        assert b.competitor_mentions == {}

    def test_citations_default_factory_isolation(self) -> None:
        a = MentionAnalysis()
        b = MentionAnalysis()
        a.citations.append("https://example.com")
        assert b.citations == []

    def test_no_mention(self) -> None:
        m = MentionAnalysis(brand_mentioned=False, brand_mention_count=0)
        assert m.brand_mentioned is False
        assert m.citation_rank is None


# ---------------------------------------------------------------------------
# DailyRunResult Tests
# ---------------------------------------------------------------------------


class TestDailyRunResult:
    """Tests for the DailyRunResult model."""

    def test_defaults(self) -> None:
        r = DailyRunResult()
        assert r.run_id == ""
        assert r.company_id == ""
        assert r.status == RunStatus.PENDING
        assert r.responses == []
        assert r.started_at is None
        assert r.completed_at is None
        assert r.error is None
        assert r.prompt_count == 0
        assert r.engine_count == 0

    def test_full_construction(
        self, sample_daily_run_result: DailyRunResult
    ) -> None:
        r = sample_daily_run_result
        assert r.run_id == "run-001"
        assert r.status == RunStatus.COMPLETED
        assert r.prompt_count == 10
        assert r.engine_count == 4

    def test_json_roundtrip(
        self, sample_daily_run_result: DailyRunResult
    ) -> None:
        data = sample_daily_run_result.model_dump(mode="json")
        restored = DailyRunResult.model_validate(data)
        assert restored == sample_daily_run_result

    def test_responses_default_factory_isolation(self) -> None:
        a = DailyRunResult()
        b = DailyRunResult()
        a.responses.append(PlatformResponse())
        assert b.responses == []

    def test_status_enum_values(self) -> None:
        for status in RunStatus:
            r = DailyRunResult(status=status)
            assert r.status == status

    def test_failed_run_with_error(self) -> None:
        r = DailyRunResult(
            run_id="run-fail",
            status=RunStatus.FAILED,
            error="Connection timeout",
        )
        assert r.status == RunStatus.FAILED
        assert r.error == "Connection timeout"

    def test_with_nested_responses(self, now: datetime) -> None:
        resp = PlatformResponse(
            prompt_id="p1", engine="openai", response_text="hello", timestamp=now
        )
        result = DailyRunResult(
            run_id="run-nested",
            responses=[resp],
            prompt_count=1,
            engine_count=1,
        )
        assert len(result.responses) == 1
        assert result.responses[0].engine == "openai"


# ---------------------------------------------------------------------------
# VisibilityMetrics Tests
# ---------------------------------------------------------------------------


class TestVisibilityMetrics:
    """Tests for the VisibilityMetrics model."""

    def test_defaults(self) -> None:
        v = VisibilityMetrics()
        assert v.overall_mention_rate == 0.0
        assert v.by_engine == {}
        assert v.total_prompts == 0
        assert v.total_responses == 0
        assert v.brand_mention_count == 0

    def test_full_construction(
        self, sample_visibility_metrics: VisibilityMetrics
    ) -> None:
        v = sample_visibility_metrics
        assert v.overall_mention_rate == 0.75
        assert v.by_engine["openai"] == 0.8
        assert v.total_prompts == 10

    def test_json_roundtrip(
        self, sample_visibility_metrics: VisibilityMetrics
    ) -> None:
        data = sample_visibility_metrics.model_dump(mode="json")
        restored = VisibilityMetrics.model_validate(data)
        assert restored == sample_visibility_metrics

    def test_by_engine_default_factory_isolation(self) -> None:
        a = VisibilityMetrics()
        b = VisibilityMetrics()
        a.by_engine["openai"] = 0.5
        assert b.by_engine == {}

    def test_zero_metrics(self) -> None:
        v = VisibilityMetrics(
            overall_mention_rate=0.0,
            total_prompts=0,
            total_responses=0,
            brand_mention_count=0,
        )
        assert v.overall_mention_rate == 0.0

    def test_perfect_metrics(self) -> None:
        v = VisibilityMetrics(
            overall_mention_rate=1.0,
            total_prompts=100,
            total_responses=400,
            brand_mention_count=400,
        )
        assert v.overall_mention_rate == 1.0


# ---------------------------------------------------------------------------
# TrendDataPoint Tests
# ---------------------------------------------------------------------------


class TestTrendDataPoint:
    """Tests for the TrendDataPoint model."""

    def test_defaults(self) -> None:
        t = TrendDataPoint()
        assert t.date is None
        assert t.mention_rate == 0.0
        assert t.response_count == 0
        assert t.run_id == ""

    def test_full_construction(
        self, sample_trend_data_point: TrendDataPoint
    ) -> None:
        t = sample_trend_data_point
        assert t.mention_rate == 0.8
        assert t.response_count == 40
        assert t.run_id == "run-001"

    def test_json_roundtrip(
        self, sample_trend_data_point: TrendDataPoint
    ) -> None:
        data = sample_trend_data_point.model_dump(mode="json")
        restored = TrendDataPoint.model_validate(data)
        assert restored == sample_trend_data_point


# ---------------------------------------------------------------------------
# CompetitorMetrics Tests
# ---------------------------------------------------------------------------


class TestCompetitorMetrics:
    """Tests for the CompetitorMetrics model."""

    def test_defaults(self) -> None:
        c = CompetitorMetrics()
        assert c.name == ""
        assert c.mention_rate == 0.0
        assert c.mention_count == 0
        assert c.share_of_voice == 0.0

    def test_full_construction(
        self, sample_competitor_metrics: CompetitorMetrics
    ) -> None:
        c = sample_competitor_metrics
        assert c.name == "Brex"
        assert c.mention_rate == 0.6
        assert c.mention_count == 12
        assert c.share_of_voice == 0.3

    def test_json_roundtrip(
        self, sample_competitor_metrics: CompetitorMetrics
    ) -> None:
        data = sample_competitor_metrics.model_dump(mode="json")
        restored = CompetitorMetrics.model_validate(data)
        assert restored == sample_competitor_metrics

    def test_zero_share_of_voice(self) -> None:
        c = CompetitorMetrics(name="Unknown", share_of_voice=0.0)
        assert c.share_of_voice == 0.0


# ---------------------------------------------------------------------------
# Protocol Import Tests
# ---------------------------------------------------------------------------


class TestProtocolImports:
    """Verify all protocols are importable and runtime_checkable."""

    def test_prompt_library_protocol_importable(self) -> None:
        from core.daily_tracker.protocols import PromptLibraryServiceProtocol

        assert hasattr(PromptLibraryServiceProtocol, "__protocol_attrs__") or hasattr(
            PromptLibraryServiceProtocol, "__abstractmethods__"
        )

    def test_platform_runner_protocol_importable(self) -> None:
        from core.daily_tracker.protocols import PlatformRunnerServiceProtocol

        assert hasattr(PlatformRunnerServiceProtocol, "__protocol_attrs__") or hasattr(
            PlatformRunnerServiceProtocol, "__abstractmethods__"
        )

    def test_mention_detector_protocol_importable(self) -> None:
        from core.daily_tracker.protocols import MentionDetectorProtocol

        assert hasattr(MentionDetectorProtocol, "__protocol_attrs__") or hasattr(
            MentionDetectorProtocol, "__abstractmethods__"
        )

    def test_analytics_protocol_importable(self) -> None:
        from core.daily_tracker.protocols import AnalyticsServiceProtocol

        assert hasattr(AnalyticsServiceProtocol, "__protocol_attrs__") or hasattr(
            AnalyticsServiceProtocol, "__abstractmethods__"
        )

    def test_orchestrator_protocol_importable(self) -> None:
        from core.daily_tracker.protocols import DailyTrackerOrchestratorProtocol

        assert hasattr(
            DailyTrackerOrchestratorProtocol, "__protocol_attrs__"
        ) or hasattr(DailyTrackerOrchestratorProtocol, "__abstractmethods__")

    def test_protocols_are_runtime_checkable(self) -> None:
        from core.daily_tracker.protocols import (
            AnalyticsServiceProtocol,
            DailyTrackerOrchestratorProtocol,
            MentionDetectorProtocol,
            PlatformRunnerServiceProtocol,
            PromptLibraryServiceProtocol,
        )

        # runtime_checkable protocols can be used with isinstance()
        # Without errors (even if the check returns False for arbitrary objects)
        for proto in [
            PromptLibraryServiceProtocol,
            PlatformRunnerServiceProtocol,
            MentionDetectorProtocol,
            AnalyticsServiceProtocol,
            DailyTrackerOrchestratorProtocol,
        ]:
            assert not isinstance("not_a_service", proto)


# ---------------------------------------------------------------------------
# MetricCalculator ABC Tests
# ---------------------------------------------------------------------------


class TestMetricCalculatorABC:
    """Tests for the MetricCalculator abstract base class."""

    def test_import(self) -> None:
        from core.daily_tracker.metrics.base import MetricCalculator

        assert MetricCalculator is not None

    def test_cannot_instantiate(self) -> None:
        from core.daily_tracker.metrics.base import MetricCalculator

        with pytest.raises(TypeError):
            MetricCalculator()  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        from core.daily_tracker.metrics.base import MetricCalculator

        class DummyMetric(MetricCalculator):
            @property
            def name(self) -> str:
                return "dummy"

            async def compute(self, responses, **kwargs):
                return 42.0

        metric = DummyMetric()
        assert metric.name == "dummy"

    @pytest.mark.asyncio
    async def test_concrete_subclass_compute(self) -> None:
        from core.daily_tracker.metrics.base import MetricCalculator

        class DummyMetric(MetricCalculator):
            @property
            def name(self) -> str:
                return "dummy"

            async def compute(self, responses, **kwargs):
                return len(responses)

        metric = DummyMetric()
        result = await metric.compute([{"a": 1}, {"b": 2}])
        assert result == 2

    def test_missing_name_raises(self) -> None:
        from core.daily_tracker.metrics.base import MetricCalculator

        class Incomplete(MetricCalculator):
            async def compute(self, responses, **kwargs):
                return 0

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_missing_compute_raises(self) -> None:
        from core.daily_tracker.metrics.base import MetricCalculator

        class Incomplete(MetricCalculator):
            @property
            def name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Metric Registry Tests
# ---------------------------------------------------------------------------


class TestMetricRegistry:
    """Tests for the METRIC_REGISTRY in metrics/__init__.py."""

    def test_registry_importable(self) -> None:
        from core.daily_tracker.metrics import METRIC_REGISTRY

        assert isinstance(METRIC_REGISTRY, dict)

    def test_registry_initially_empty(self) -> None:
        from core.daily_tracker.metrics import METRIC_REGISTRY

        # Registry starts empty — concrete calculators register later
        assert len(METRIC_REGISTRY) == 0


# ---------------------------------------------------------------------------
# Cross-Model Serialization Tests
# ---------------------------------------------------------------------------


class TestCrossModelSerialization:
    """Test that models compose and serialize correctly together."""

    def test_run_result_with_responses(self, now: datetime) -> None:
        resp = PlatformResponse(
            prompt_id="p1",
            engine="openai",
            response_text="Ramp is great",
            latency_ms=100.0,
            timestamp=now,
        )
        result = DailyRunResult(
            run_id="r1",
            company_id="co",
            status=RunStatus.COMPLETED,
            responses=[resp],
            prompt_count=1,
            engine_count=1,
            started_at=now,
            completed_at=now,
        )
        data = result.model_dump(mode="json")
        restored = DailyRunResult.model_validate(data)
        assert len(restored.responses) == 1
        assert restored.responses[0].engine == "openai"
        assert restored.responses[0].response_text == "Ramp is great"

    def test_empty_run_result_serialization(self) -> None:
        result = DailyRunResult()
        data = result.model_dump(mode="json")
        restored = DailyRunResult.model_validate(data)
        assert restored.responses == []
        assert restored.status == RunStatus.PENDING

    def test_model_dump_mode_json_produces_serializable(self) -> None:
        """Verify mode='json' produces JSON-serializable types."""
        import json

        prompt = TrackedPrompt(
            id="p1",
            text="test",
            source=PromptSource.GAP_ANALYSIS,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        data = prompt.model_dump(mode="json")
        # Should not raise
        serialized = json.dumps(data)
        assert isinstance(serialized, str)

    def test_all_models_have_defaults(self) -> None:
        """Every model must be constructable with zero arguments (backward compat)."""
        models = [
            TrackedPrompt,
            PromptLibraryFilter,
            DailyRunConfig,
            PlatformResponse,
            MentionAnalysis,
            DailyRunResult,
            VisibilityMetrics,
            TrendDataPoint,
            CompetitorMetrics,
        ]
        for model_cls in models:
            instance = model_cls()
            assert instance is not None, f"{model_cls.__name__} failed default construction"
