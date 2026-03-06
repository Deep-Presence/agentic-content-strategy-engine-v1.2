"""Tests for core.content_engine.context_router — pure data transformations.

Tests Phase 1 (scorecard extraction) and Phase 2 (full context extraction)
plus markdown formatting functions. No mocks needed — all pure functions.
"""
from __future__ import annotations

import pytest

from core.content_engine.context_router import (
    extract_scorecard,
    extract_worker_context,
    format_scorecard_as_markdown,
    format_worker_context_as_markdown,
)
from core.models.content_generation_v13 import (
    PlannerScorecard,
    WorkerQueryContext,
)


# ═══════════════════════════════════════════════════════════════════════
# extract_scorecard
# ═══════════════════════════════════════════════════════════════════════


class TestExtractScorecard:
    """Tests for extract_scorecard()."""

    def test_empty_analysis_returns_empty_scorecard(self):
        sc = extract_scorecard({})
        assert isinstance(sc, PlannerScorecard)
        assert sc.queries == []
        assert sc.clusters == []
        assert sc.total_queries == 0
        assert sc.total_clusters == 0

    def test_extracts_query_scorecards(self, sample_analysis_json):
        sc = extract_scorecard(sample_analysis_json)
        assert len(sc.queries) == 3
        q1 = sc.queries[0]
        assert q1.query_id == "q-001"
        assert q1.query_text == "what is a 409A valuation"
        assert q1.cluster_name == "equity"
        assert q1.gap == pytest.approx(0.35)
        assert q1.best_company_similarity == pytest.approx(0.55)
        assert q1.avg_citation_similarity == pytest.approx(0.90)
        assert q1.interpretation == "significant_gap"

    def test_exemplar_count_and_has_brief(self, sample_analysis_json):
        sc = extract_scorecard(sample_analysis_json)
        # q-001 has 1 exemplar + content_brief
        assert sc.queries[0].exemplar_count == 1
        assert sc.queries[0].has_brief is True
        # q-002 has 0 exemplars, no brief
        assert sc.queries[1].exemplar_count == 0
        assert sc.queries[1].has_brief is False
        # q-003 has 2 exemplars + brief
        assert sc.queries[2].exemplar_count == 2
        assert sc.queries[2].has_brief is True

    def test_cluster_aggregation(self, sample_analysis_json):
        sc = extract_scorecard(sample_analysis_json)
        assert len(sc.clusters) == 2
        # Clusters sorted alphabetically
        eq = next(c for c in sc.clusters if c.cluster_name == "equity")
        fr = next(c for c in sc.clusters if c.cluster_name == "fundraising")
        assert eq.query_count == 2
        assert eq.significant_gap_count == 1
        # avg of 0.35 and 0.10
        assert eq.avg_gap == pytest.approx(0.225)
        assert eq.max_gap == pytest.approx(0.35)
        assert fr.query_count == 1
        assert fr.avg_gap == pytest.approx(0.42)

    def test_cluster_dominant_types_from_specs(self, sample_analysis_json):
        sc = extract_scorecard(sample_analysis_json)
        eq = next(c for c in sc.clusters if c.cluster_name == "equity")
        assert eq.dominant_content_type == "long_blog"
        assert eq.dominant_authority_type == "industry_report"

    def test_company_summary_truncated_at_600(self):
        long_text = "A" * 800
        sc = extract_scorecard({}, company_context_md=long_text)
        assert len(sc.company_summary) == 600

    def test_company_summary_empty_when_none(self):
        sc = extract_scorecard({}, company_context_md="")
        assert sc.company_summary == ""

    def test_product_focus_passed_through(self):
        sc = extract_scorecard({}, product_focus="Cap table product")
        assert sc.product_focus == "Cap table product"

    def test_product_focus_default_none(self):
        sc = extract_scorecard({})
        assert sc.product_focus is None

    def test_missing_fields_handled_gracefully(self):
        """Gaps without cluster_name or top_cited_exemplars should not crash."""
        analysis = {
            "gaps": [
                {"query_id": "x"},  # Minimal gap — many fields missing
            ],
        }
        sc = extract_scorecard(analysis)
        assert len(sc.queries) == 1
        assert sc.queries[0].query_id == "x"
        assert sc.queries[0].cluster_name == ""
        assert sc.queries[0].exemplar_count == 0
        assert sc.queries[0].has_brief is False

    def test_total_counts_match(self, sample_analysis_json):
        sc = extract_scorecard(sample_analysis_json)
        assert sc.total_queries == 3
        assert sc.total_clusters == 2

    def test_gap_with_none_values(self):
        """Fields that are None should fall back to defaults."""
        analysis = {
            "gaps": [
                {
                    "query_id": "n-1",
                    "query_text": "test",
                    "gap": None,
                    "interpretation": None,
                    "cluster_name": None,
                },
            ],
        }
        sc = extract_scorecard(analysis)
        assert sc.queries[0].gap == 0.0
        assert sc.queries[0].interpretation == ""
        assert sc.queries[0].cluster_name == ""


# ═══════════════════════════════════════════════════════════════════════
# extract_worker_context
# ═══════════════════════════════════════════════════════════════════════


class TestExtractWorkerContext:
    """Tests for extract_worker_context()."""

    def test_empty_ids_returns_empty_dict(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, [])
        assert result == {}

    def test_no_matching_ids_returns_empty(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["nonexistent"])
        assert result == {}

    def test_filters_to_approved_only(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-001", "q-003"])
        assert set(result.keys()) == {"q-001", "q-003"}
        assert "q-002" not in result

    def test_populates_query_gap(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-001"])
        ctx = result["q-001"]
        assert isinstance(ctx, WorkerQueryContext)
        assert ctx.query_gap["query_id"] == "q-001"
        assert ctx.query_gap["gap"] == 0.35

    def test_populates_exemplars(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-001"])
        ctx = result["q-001"]
        assert len(ctx.exemplars) == 1
        assert ctx.exemplars[0]["url"] == "https://example.com/409a"

    def test_populates_cluster_spec(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-001"])
        ctx = result["q-001"]
        assert ctx.cluster_spec["cluster_name"] == "equity"
        assert ctx.cluster_spec["dominant_content_type"] == "long_blog"

    def test_populates_content_brief(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-001"])
        ctx = result["q-001"]
        assert ctx.gap_content_brief is not None
        assert ctx.gap_content_brief["target_format"] == "long_blog"

    def test_null_brief_stays_none(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-002"])
        ctx = result["q-002"]
        assert ctx.gap_content_brief is None

    def test_company_best_text(self, sample_analysis_json):
        result = extract_worker_context(sample_analysis_json, ["q-001"])
        assert result["q-001"].company_best_text == "We offer cap table management."

    def test_missing_query_logs_warning(self, sample_analysis_json, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            result = extract_worker_context(sample_analysis_json, ["q-001", "q-999"])
        assert "q-999" in caplog.text
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════
# format_scorecard_as_markdown
# ═══════════════════════════════════════════════════════════════════════


class TestFormatScorecardAsMarkdown:
    """Tests for format_scorecard_as_markdown()."""

    def test_contains_cluster_overview_header(self, sample_scorecard):
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "## Cluster Overview" in md

    def test_contains_query_scorecards_header(self, sample_scorecard):
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "## Query Scorecards" in md

    def test_contains_company_summary_section(self, sample_scorecard):
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "## Company Summary" in md
        assert "TestCo provides equity management" in md

    def test_omits_company_summary_when_empty(self, sample_scorecard):
        sample_scorecard.company_summary = ""
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "## Company Summary" not in md

    def test_contains_product_focus_section(self, sample_scorecard):
        sample_scorecard.product_focus = "Cap table product"
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "## Product Focus" in md
        assert "Cap table product" in md

    def test_omits_product_focus_when_none(self, sample_scorecard):
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "## Product Focus" not in md

    def test_truncates_long_query_text(self):
        from core.models.content_generation_v13 import PlannerScorecard, QueryScorecard

        sc = PlannerScorecard(
            queries=[
                QueryScorecard(query_id="long", query_text="x" * 100),
            ],
            total_queries=1,
        )
        md = format_scorecard_as_markdown(sc)
        assert ("x" * 80 + "...") in md

    def test_total_counts_in_output(self, sample_scorecard):
        md = format_scorecard_as_markdown(sample_scorecard)
        assert "**Total queries:** 3" in md
        assert "**Total clusters:** 2" in md


# ═══════════════════════════════════════════════════════════════════════
# format_worker_context_as_markdown
# ═══════════════════════════════════════════════════════════════════════


class TestFormatWorkerContextAsMarkdown:
    """Tests for format_worker_context_as_markdown()."""

    def test_contains_query_gap_section(self, sample_worker_context):
        md = format_worker_context_as_markdown(sample_worker_context)
        assert "## Query Gap Analysis" in md
        assert "q-001" in md

    def test_contains_company_best_content(self, sample_worker_context):
        md = format_worker_context_as_markdown(sample_worker_context)
        assert "## Company's Current Best Content" in md
        assert "cap table management" in md

    def test_omits_company_content_when_empty(self):
        ctx = WorkerQueryContext(query_gap={"query_id": "x"})
        md = format_worker_context_as_markdown(ctx)
        assert "## Company's Current Best Content" not in md

    def test_contains_content_brief_section(self, sample_worker_context):
        md = format_worker_context_as_markdown(sample_worker_context)
        assert "## Pre-Computed Content Brief Targets" in md

    def test_omits_brief_when_none(self):
        ctx = WorkerQueryContext(query_gap={"query_id": "x"})
        md = format_worker_context_as_markdown(ctx)
        assert "## Pre-Computed Content Brief Targets" not in md

    def test_contains_exemplars_section(self, sample_worker_context):
        md = format_worker_context_as_markdown(sample_worker_context)
        assert "## Top-Cited Exemplars" in md
        assert "### Exemplar 1" in md
        assert "https://example.com/409a" in md

    def test_contains_structural_signals(self, sample_worker_context):
        md = format_worker_context_as_markdown(sample_worker_context)
        assert "Structural Signals" in md
        assert "word_count" in md

    def test_contains_cluster_spec_section(self, sample_worker_context):
        md = format_worker_context_as_markdown(sample_worker_context)
        assert "## Cluster Content Specification" in md

    def test_omits_cluster_spec_when_empty(self):
        ctx = WorkerQueryContext(query_gap={"query_id": "x"})
        md = format_worker_context_as_markdown(ctx)
        assert "## Cluster Content Specification" not in md
