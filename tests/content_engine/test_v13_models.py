"""Tests for core.models.content_generation_v13 — Pydantic model validation.

Tests JSON roundtrip, defaults, inheritance, and enum values.
"""
from __future__ import annotations

import json

import pytest

from core.models.content_generation import ContentBrief
from core.models.content_generation_v13 import (
    BlueprintSection,
    ClusterSummary,
    ContentBlueprint,
    ContentGenerationInputV13,
    EntryMode,
    FeedbackRoute,
    LLMResponse,
    ManualPromptInput,
    PlannerScorecard,
    QueryScorecard,
    StrategicPlannerOutput,
    TopicSelection,
    WorkerQueryContext,
)


class TestQueryScorecard:
    def test_defaults(self):
        qs = QueryScorecard()
        assert qs.query_id == ""
        assert qs.gap == 0.0
        assert qs.exemplar_count == 0
        assert qs.has_brief is False

    def test_json_roundtrip(self):
        qs = QueryScorecard(query_id="q-1", query_text="test", gap=0.35)
        data = json.loads(qs.model_dump_json())
        qs2 = QueryScorecard(**data)
        assert qs2.query_id == "q-1"
        assert qs2.gap == pytest.approx(0.35)


class TestClusterSummary:
    def test_defaults(self):
        cs = ClusterSummary()
        assert cs.cluster_name == ""
        assert cs.dominant_content_type is None

    def test_json_roundtrip(self):
        cs = ClusterSummary(cluster_name="equity", query_count=5, avg_gap=0.3)
        data = json.loads(cs.model_dump_json())
        cs2 = ClusterSummary(**data)
        assert cs2.cluster_name == "equity"


class TestPlannerScorecard:
    def test_defaults(self):
        ps = PlannerScorecard()
        assert ps.queries == []
        assert ps.clusters == []
        assert ps.total_queries == 0

    def test_json_roundtrip(self):
        ps = PlannerScorecard(
            queries=[QueryScorecard(query_id="q-1")],
            clusters=[ClusterSummary(cluster_name="c-1")],
            company_summary="Test company",
            total_queries=1,
            total_clusters=1,
        )
        data = json.loads(ps.model_dump_json())
        ps2 = PlannerScorecard(**data)
        assert len(ps2.queries) == 1
        assert ps2.company_summary == "Test company"


class TestTopicSelection:
    def test_defaults(self):
        ts = TopicSelection()
        assert ts.rank == 0
        assert ts.query_ids == []
        assert ts.estimated_impact == "medium"

    def test_json_roundtrip(self):
        ts = TopicSelection(
            rank=1, query_ids=["q-1", "q-2"],
            cluster_name="equity", estimated_impact="high",
        )
        data = json.loads(ts.model_dump_json())
        ts2 = TopicSelection(**data)
        assert ts2.rank == 1
        assert ts2.estimated_impact == "high"


class TestStrategicPlannerOutput:
    def test_defaults(self):
        spo = StrategicPlannerOutput()
        assert spo.selections == []
        assert spo.selection_metadata == {}

    def test_json_roundtrip(self):
        spo = StrategicPlannerOutput(
            selections=[TopicSelection(rank=1)],
            selection_metadata={"model": "test"},
        )
        data = json.loads(spo.model_dump_json())
        spo2 = StrategicPlannerOutput(**data)
        assert len(spo2.selections) == 1


class TestWorkerQueryContext:
    def test_defaults(self):
        wqc = WorkerQueryContext()
        assert wqc.query_gap == {}
        assert wqc.exemplars == []
        assert wqc.gap_content_brief is None

    def test_json_roundtrip(self):
        wqc = WorkerQueryContext(
            query_gap={"query_id": "q-1"},
            exemplars=[{"url": "https://example.com"}],
            company_best_text="test text",
        )
        data = json.loads(wqc.model_dump_json())
        wqc2 = WorkerQueryContext(**data)
        assert wqc2.query_gap["query_id"] == "q-1"


class TestBlueprintSection:
    def test_defaults(self):
        bs = BlueprintSection()
        assert bs.heading == ""
        assert bs.level == 2
        assert bs.target_word_count == 300
        assert bs.key_points == []

    def test_json_roundtrip(self):
        bs = BlueprintSection(
            heading="Intro", level=2,
            key_points=["point1"], target_word_count=500,
        )
        data = json.loads(bs.model_dump_json())
        bs2 = BlueprintSection(**data)
        assert bs2.heading == "Intro"


class TestContentBlueprint:
    def test_extends_content_brief(self):
        bp = ContentBlueprint(brief_id="b-1", title="Test")
        assert isinstance(bp, ContentBrief)

    def test_defaults(self):
        bp = ContentBlueprint(brief_id="b-1", title="Test")
        assert bp.sections == []
        assert bp.territory_queries == []
        assert bp.reading_hierarchy == {}
        assert bp.must_hit_checklist == []
        assert bp.user_feedback == ""
        assert bp.gap_context is None

    def test_new_direction_fields_defaults(self):
        bp = ContentBlueprint(brief_id="b-1", title="Test")
        assert bp.gap_reasoning == []
        assert bp.tone_voice_description == ""
        assert bp.target_persona == ""
        assert bp.buyer_stage == ""
        assert bp.intent_stage == ""

    def test_new_direction_fields_roundtrip(self):
        bp = ContentBlueprint(
            brief_id="b-1",
            title="Test",
            gap_reasoning=["Fills gap in equity content", "No existing coverage", "High search volume"],
            tone_voice_description="Professional, data-driven authority",
            target_persona="VP of Engineering at Series B startup",
            buyer_stage="solution-aware",
            intent_stage="commercial",
        )
        data = json.loads(bp.model_dump_json())
        bp2 = ContentBlueprint(**data)
        assert len(bp2.gap_reasoning) == 3
        assert bp2.gap_reasoning[0] == "Fills gap in equity content"
        assert bp2.tone_voice_description == "Professional, data-driven authority"
        assert bp2.target_persona == "VP of Engineering at Series B startup"
        assert bp2.buyer_stage == "solution-aware"
        assert bp2.intent_stage == "commercial"

    def test_backward_compat_without_new_fields(self):
        """Existing JSON without new fields should load with defaults."""
        old_json = {
            "brief_id": "b-1",
            "title": "Old Blueprint",
            "sections": [],
            "territory_queries": [],
        }
        bp = ContentBlueprint(**old_json)
        assert bp.gap_reasoning == []
        assert bp.tone_voice_description == ""
        assert bp.target_persona == ""

    def test_json_roundtrip(self):
        bp = ContentBlueprint(
            brief_id="b-1",
            title="Test Blueprint",
            sections=[BlueprintSection(heading="Intro")],
            must_hit_checklist=["Define term"],
        )
        data = json.loads(bp.model_dump_json())
        bp2 = ContentBlueprint(**data)
        assert bp2.brief_id == "b-1"
        assert len(bp2.sections) == 1

    def test_inherits_content_brief_fields(self):
        bp = ContentBlueprint(
            brief_id="b-1",
            title="Test",
            key_topics=["topic1"],
        )
        assert bp.key_topics == ["topic1"]
        assert bp.brief_id == "b-1"


class TestEntryMode:
    def test_values(self):
        assert EntryMode.AUTONOMOUS.value == "autonomous"
        assert EntryMode.MANUAL.value == "manual"


class TestFeedbackRoute:
    def test_values(self):
        assert FeedbackRoute.PASS.value == "pass"
        assert FeedbackRoute.SECTION_LEVEL.value == "section_level"
        assert FeedbackRoute.MAJOR_CHANGE.value == "major_change"


class TestContentGenerationInputV13:
    def test_defaults(self):
        cgi = ContentGenerationInputV13(company_name="Test", domain="test.com")
        assert cgi.entry_mode == EntryMode.AUTONOMOUS
        assert cgi.max_topics == 6
        assert cgi.manual_prompt is None

    def test_json_roundtrip(self):
        cgi = ContentGenerationInputV13(
            company_name="Test", domain="test.com",
            entry_mode=EntryMode.MANUAL,
            manual_prompt="Write about 409A",
        )
        data = json.loads(cgi.model_dump_json())
        cgi2 = ContentGenerationInputV13(**data)
        assert cgi2.entry_mode == EntryMode.MANUAL
        assert cgi2.manual_prompt == "Write about 409A"


class TestManualPromptInput:
    def test_defaults(self):
        mpi = ManualPromptInput()
        assert mpi.prompt == ""
        assert mpi.description == ""
        assert mpi.cluster_name == ""


class TestLLMResponse:
    def test_defaults(self):
        lr = LLMResponse()
        assert lr.content == ""
        assert lr.input_tokens == 0

    def test_json_roundtrip(self):
        lr = LLMResponse(
            content="Hello", model="test", input_tokens=10,
            output_tokens=20, total_tokens=30, finish_reason="stop",
        )
        data = json.loads(lr.model_dump_json())
        lr2 = LLMResponse(**data)
        assert lr2.content == "Hello"
        assert lr2.total_tokens == 30
