"""Tests for content generation Pydantic models.

Validates construction, defaults, serialization round-trips,
and edge-case validation for all Stage 1-4 models.
"""
from __future__ import annotations

import json

import pytest

from core.models.content_generation import (
    ContentBrief,
    ContentDraft,
    ContentGenerationInput,
    ContentGenerationOutput,
    ContentOutline,
    ContentPiece,
    ContentStatus,
    DimensionResult,
    EnrichedDraft,
    EvalResult,
    ExemplarSummary,
    FormattedContent,
    OutlineSection,
    PlannerOutput,
    RevisionHistory,
    StructuralTargets,
    TargetQuery,
)


# ---------------------------------------------------------------------------
# ContentGenerationInput
# ---------------------------------------------------------------------------


class TestContentGenerationInput:
    def test_minimal_construction(self):
        inp = ContentGenerationInput(company_name="Acme", domain="acme.com")
        assert inp.company_name == "Acme"
        assert inp.domain == "acme.com"
        assert inp.max_briefs == 10
        assert inp.max_concurrent_workers == 3
        assert inp.max_revision_cycles == 2
        assert inp.auto_approve is False
        assert inp.skip_stages == []

    def test_full_construction(self):
        inp = ContentGenerationInput(
            company_name="Carta",
            domain="carta.com",
            company_context_path="artifacts/company_context/carta.md",
            persona_paths=["p1.md", "p2.md"],
            style_guide_path="style.md",
            gap_report_json_path="report.json",
            generation_spec_json_path="spec.json",
            analysis_json_path="analysis.json",
            max_briefs=5,
            max_concurrent_workers=2,
            max_revision_cycles=1,
            auto_approve=True,
            skip_stages=[1, 3],
        )
        assert inp.persona_paths == ["p1.md", "p2.md"]
        assert inp.skip_stages == [1, 3]
        assert inp.auto_approve is True

    def test_json_round_trip(self):
        inp = ContentGenerationInput(company_name="Ramp", domain="ramp.com")
        data = json.loads(inp.model_dump_json())
        restored = ContentGenerationInput(**data)
        assert restored == inp


# ---------------------------------------------------------------------------
# Stage 1 — Planner models
# ---------------------------------------------------------------------------


class TestTargetQuery:
    def test_construction(self):
        tq = TargetQuery(query_text="What is 409A?", cluster_name="equity")
        assert tq.query_text == "What is 409A?"
        assert tq.embedding is None

    def test_with_embedding(self):
        tq = TargetQuery(
            query_text="test", cluster_name="c1", embedding=[0.1, 0.2, 0.3]
        )
        assert len(tq.embedding) == 3


class TestStructuralTargets:
    def test_defaults(self):
        st = StructuralTargets()
        # v1.0 fields
        assert st.header_rate == 0.0
        assert st.list_rate == 0.0
        assert st.stat_rate == 0.0
        assert st.citation_rate == 0.0
        assert st.min_headers == 3
        assert st.min_lists == 1
        assert st.min_citations == 2
        # v2.0 paragraph/sentence targets
        assert st.min_paragraphs == 8
        assert st.avg_paragraph_word_count == 80
        assert st.max_paragraph_word_count == 150
        assert st.avg_sentence_count_per_paragraph == 3.5
        # v2.0 granular structural rates
        assert st.table_rate == 0.0
        assert st.definition_rate == 0.0
        assert st.faq_rate == 0.0
        assert st.code_block_rate == 0.0
        # v2.0 count targets
        assert st.min_stats == 2
        assert st.min_self_contained_claims == 5
        assert st.min_bullets_per_list == 3
        # v2.0 authority/content intelligence
        assert st.dominant_authority_type is None
        assert st.dominant_content_type is None
        assert st.avg_word_count == 0

    def test_custom_values(self):
        st = StructuralTargets(header_rate=0.05, min_headers=5, min_citations=10)
        assert st.header_rate == 0.05
        assert st.min_citations == 10

    def test_v2_custom_values(self):
        st = StructuralTargets(
            min_paragraphs=12,
            avg_paragraph_word_count=100,
            faq_rate=0.45,
            table_rate=0.3,
            min_stats=5,
            min_self_contained_claims=8,
            min_bullets_per_list=5,
            dominant_authority_type="industry_report",
            dominant_content_type="how_to_guide",
            avg_word_count=2500,
        )
        assert st.min_paragraphs == 12
        assert st.avg_paragraph_word_count == 100
        assert st.faq_rate == 0.45
        assert st.table_rate == 0.3
        assert st.min_stats == 5
        assert st.min_self_contained_claims == 8
        assert st.min_bullets_per_list == 5
        assert st.dominant_authority_type == "industry_report"
        assert st.dominant_content_type == "how_to_guide"
        assert st.avg_word_count == 2500

    def test_backward_compat_v1_only(self):
        """v1 JSON (missing v2 fields) deserializes with defaults."""
        v1_data = {"header_rate": 0.03, "min_headers": 4, "min_lists": 2, "min_citations": 3}
        st = StructuralTargets(**v1_data)
        assert st.min_headers == 4
        assert st.min_paragraphs == 8  # v2 default
        assert st.faq_rate == 0.0  # v2 default


class TestExemplarSummary:
    def test_defaults(self):
        es = ExemplarSummary()
        assert es.url == ""
        assert es.word_count == 0
        assert es.header_count == 0
        assert es.list_item_count == 0
        assert es.stat_count == 0
        assert es.citation_count == 0
        assert es.authority_type == ""
        assert es.content_type == ""
        assert es.snippet == ""

    def test_full_construction(self):
        es = ExemplarSummary(
            url="https://example.com/409a-guide",
            word_count=2500,
            header_count=8,
            list_item_count=15,
            stat_count=4,
            citation_count=6,
            authority_type="industry_report",
            content_type="pillar_page",
            snippet="A 409A valuation is an independent appraisal...",
        )
        assert es.url == "https://example.com/409a-guide"
        assert es.word_count == 2500
        assert es.authority_type == "industry_report"

    def test_json_round_trip(self):
        es = ExemplarSummary(
            url="https://example.com/test",
            word_count=1200,
            header_count=5,
        )
        data = json.loads(es.model_dump_json())
        restored = ExemplarSummary(**data)
        assert restored == es


class TestContentBrief:
    def test_defaults(self):
        brief = ContentBrief(brief_id="brief-001", title="Test Article")
        assert brief.content_format == "long_blog"
        assert brief.funnel_stage == "awareness"
        assert brief.channel == "blog"
        assert brief.word_count_range == (1200, 2000)
        assert brief.semantic_threshold == 0.65
        assert isinstance(brief.structural_targets, StructuralTargets)
        # v2.0 exemplar fields default to empty lists
        assert brief.exemplar_summaries == []
        assert brief.exemplar_themes == []

    def test_word_count_range_tuple(self):
        brief = ContentBrief(
            brief_id="b-1",
            title="T",
            word_count_range=(800, 1200),
        )
        assert brief.word_count_range[0] == 800
        assert brief.word_count_range[1] == 1200

    def test_all_formats(self):
        for fmt in ("long_blog", "short_faq", "pillar_page", "comparison", "how_to"):
            brief = ContentBrief(
                brief_id="b-1", title="T", content_format=fmt
            )
            assert brief.content_format == fmt

    def test_json_round_trip(self):
        brief = ContentBrief(
            brief_id="brief-001",
            title="409A Valuations",
            target_queries=[
                TargetQuery(query_text="what is 409A", cluster_name="equity")
            ],
            target_cluster="equity",
            content_format="how_to",
            funnel_stage="consideration",
            word_count_range=(1000, 1500),
            structural_targets=StructuralTargets(min_headers=5),
            key_topics=["409A", "startup equity"],
            competitor_exemplars=["https://example.com/409a"],
            exemplar_summaries=[
                ExemplarSummary(
                    url="https://example.com/409a-guide",
                    word_count=2500,
                    header_count=8,
                    authority_type="industry_report",
                )
            ],
            exemplar_themes=["compliance-focused", "step-by-step"],
        )
        data = json.loads(brief.model_dump_json())
        restored = ContentBrief(**data)
        assert restored.brief_id == "brief-001"
        assert restored.word_count_range == (1000, 1500)
        assert restored.structural_targets.min_headers == 5
        assert len(restored.target_queries) == 1
        assert len(restored.exemplar_summaries) == 1
        assert restored.exemplar_summaries[0].word_count == 2500
        assert restored.exemplar_themes == ["compliance-focused", "step-by-step"]

    def test_backward_compat_v1_json(self):
        """v1 brief JSON (no exemplar fields) deserializes cleanly."""
        v1_data = {
            "brief_id": "b-old",
            "title": "Old Brief",
            "content_format": "long_blog",
        }
        brief = ContentBrief(**v1_data)
        assert brief.exemplar_summaries == []
        assert brief.exemplar_themes == []


class TestPlannerOutput:
    def test_empty(self):
        out = PlannerOutput()
        assert out.briefs == []
        assert out.planning_metadata == {}

    def test_with_briefs(self):
        out = PlannerOutput(
            briefs=[ContentBrief(brief_id="b-1", title="T")],
            planning_metadata={"model": "sonnet"},
        )
        assert len(out.briefs) == 1


# ---------------------------------------------------------------------------
# Stage 2 — Worker models
# ---------------------------------------------------------------------------


class TestOutlineSection:
    def test_defaults(self):
        s = OutlineSection(heading="Introduction")
        assert s.level == 2
        assert s.target_word_count == 300
        assert s.key_points == []
        # v2.0 fields
        assert s.structural_elements == []
        assert s.self_contained_claims == 0

    def test_with_structural_elements(self):
        s = OutlineSection(
            heading="Process Overview",
            structural_elements=["bullet_list", "table", "statistics"],
            self_contained_claims=3,
        )
        assert len(s.structural_elements) == 3
        assert s.self_contained_claims == 3


class TestContentOutline:
    def test_construction(self):
        outline = ContentOutline(
            brief_id="b-1",
            title="Test",
            sections=[
                OutlineSection(heading="Intro"),
                OutlineSection(heading="Body", level=3),
            ],
        )
        assert len(outline.sections) == 2
        assert outline.total_target_words == 1500
        # v2.0 defaults
        assert outline.has_faq_section is False
        assert outline.has_table_section is False
        assert outline.has_key_takeaways is False

    def test_with_structural_flags(self):
        outline = ContentOutline(
            brief_id="b-1",
            title="Comprehensive Guide",
            sections=[OutlineSection(heading="Intro")],
            has_faq_section=True,
            has_table_section=True,
            has_key_takeaways=True,
        )
        assert outline.has_faq_section is True
        assert outline.has_table_section is True
        assert outline.has_key_takeaways is True

    def test_voice_tone_description_default(self):
        outline = ContentOutline(brief_id="b-1", title="Test")
        assert outline.voice_tone_description == ""

    def test_voice_tone_description_roundtrip(self):
        outline = ContentOutline(
            brief_id="b-1",
            title="Test",
            voice_tone_description="Professional, data-driven, approachable",
        )
        data = json.loads(outline.model_dump_json())
        restored = ContentOutline(**data)
        assert restored.voice_tone_description == "Professional, data-driven, approachable"

    def test_backward_compat_without_voice_tone(self):
        """Old JSON without voice_tone_description loads with default."""
        old_data = {"brief_id": "b-1", "title": "Old", "sections": []}
        outline = ContentOutline(**old_data)
        assert outline.voice_tone_description == ""


class TestContentDraft:
    def test_defaults(self):
        d = ContentDraft(brief_id="b-1", title="T")
        assert d.markdown == ""
        assert d.word_count == 0


class TestEnrichedDraft:
    def test_with_facts(self):
        e = EnrichedDraft(
            brief_id="b-1",
            title="T",
            markdown="# Hello",
            word_count=1,
            facts_added=[{"claim": "X is Y", "source": "https://example.com"}],
        )
        assert len(e.facts_added) == 1


class TestLinkedDraft:
    def test_defaults(self):
        from core.models.content_generation import LinkedDraft
        ld = LinkedDraft()
        assert ld.brief_id == ""
        assert ld.markdown == ""
        assert ld.internal_links_added == 0
        assert ld.external_links_added == 0
        assert ld.stats_resolved == 0

    def test_full_construction(self):
        from core.models.content_generation import LinkedDraft
        ld = LinkedDraft(
            brief_id="b-1",
            title="Test",
            markdown="# Hello [link](https://example.com)",
            word_count=5,
            internal_links_added=3,
            external_links_added=5,
            stats_resolved=2,
        )
        assert ld.internal_links_added == 3
        assert ld.external_links_added == 5
        assert ld.stats_resolved == 2

    def test_json_roundtrip(self):
        from core.models.content_generation import LinkedDraft
        ld = LinkedDraft(
            brief_id="b-1", title="T",
            markdown="content", word_count=1,
            internal_links_added=2, external_links_added=4,
        )
        data = json.loads(ld.model_dump_json())
        restored = LinkedDraft(**data)
        assert restored.internal_links_added == 2
        assert restored.external_links_added == 4


class TestFormattedContent:
    def test_counts(self):
        fc = FormattedContent(
            brief_id="b-1",
            title="T",
            markdown="# H\n- item\n42% stat",
            word_count=5,
            header_count=1,
            list_count=1,
            stat_count=1,
            citation_count=0,
        )
        assert fc.header_count == 1
        assert fc.stat_count == 1


# ---------------------------------------------------------------------------
# Stage 3 — Evaluator models
# ---------------------------------------------------------------------------


class TestDimensionResult:
    def test_construction(self):
        dr = DimensionResult(
            dimension="structural", passed=True, score=0.88, feedback="Looks good"
        )
        assert dr.passed is True
        assert dr.details == {}

    def test_with_details(self):
        dr = DimensionResult(
            dimension="semantic",
            score=0.72,
            details={"similarity": 0.72, "threshold": 0.65},
        )
        assert dr.details["similarity"] == 0.72


class TestEvalResult:
    def test_construction(self):
        er = EvalResult(
            brief_id="b-1",
            cycle=0,
            dimensions=[
                DimensionResult(dimension="structural", passed=True, score=0.9),
                DimensionResult(dimension="semantic", passed=True, score=0.7),
            ],
            overall_passed=True,
            overall_score=0.8,
        )
        assert len(er.dimensions) == 2
        assert er.overall_passed is True


class TestRevisionHistory:
    def test_empty(self):
        rh = RevisionHistory(brief_id="b-1")
        assert rh.cycles == []
        assert rh.final_passed is False

    def test_with_cycles(self):
        rh = RevisionHistory(
            brief_id="b-1",
            cycles=[
                EvalResult(brief_id="b-1", cycle=0, overall_passed=False),
                EvalResult(brief_id="b-1", cycle=1, overall_passed=True),
            ],
            final_passed=True,
        )
        assert len(rh.cycles) == 2
        assert rh.final_passed is True


# ---------------------------------------------------------------------------
# Stage 4 — HITL models
# ---------------------------------------------------------------------------


class TestContentStatus:
    def test_values(self):
        assert ContentStatus.PENDING == "pending"
        assert ContentStatus.APPROVED == "approved"
        assert ContentStatus.EDITED == "edited"
        assert ContentStatus.REJECTED == "rejected"


class TestContentPiece:
    def test_defaults(self):
        cp = ContentPiece(brief_id="b-1", title="T")
        assert cp.status == ContentStatus.PENDING
        assert cp.final_markdown == ""
        assert cp.human_notes is None

    def test_approved(self):
        cp = ContentPiece(
            brief_id="b-1",
            title="T",
            status=ContentStatus.APPROVED,
            final_markdown="# Content",
            artifact_path="artifacts/content/carta/content/brief-001/final.md",
        )
        assert cp.status == ContentStatus.APPROVED
        assert cp.artifact_path is not None


class TestContentGenerationOutput:
    def test_construction(self):
        out = ContentGenerationOutput(
            company_slug="carta",
            total_briefs=10,
            total_approved=8,
            total_rejected=2,
            pieces=[
                ContentPiece(brief_id="b-1", title="T1", status=ContentStatus.APPROVED),
                ContentPiece(brief_id="b-2", title="T2", status=ContentStatus.REJECTED),
            ],
        )
        assert out.total_briefs == 10
        assert len(out.pieces) == 2

    def test_json_round_trip(self):
        out = ContentGenerationOutput(
            company_slug="ramp",
            total_briefs=1,
            pieces=[
                ContentPiece(
                    brief_id="b-1",
                    title="T",
                    status=ContentStatus.APPROVED,
                    final_markdown="# Hello",
                    eval_summary={"structural": 0.9},
                )
            ],
        )
        data = json.loads(out.model_dump_json())
        restored = ContentGenerationOutput(**data)
        assert restored.company_slug == "ramp"
        assert restored.pieces[0].status == ContentStatus.APPROVED
