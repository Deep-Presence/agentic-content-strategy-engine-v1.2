"""Tests for s8_generate_report async conversion — TDD: written BEFORE implementation.

Focused on async behavior of _call_openai and generate_gap_report.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncCallOpenAI:
    """Tests for async _call_openai in s8."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """_call_openai should be an async function."""
        from core.gap_analysis.steps.s8_generate_report import _call_openai
        assert inspect.iscoroutinefunction(_call_openai)

    @pytest.mark.asyncio
    async def test_returns_text_response(self):
        """Should return the content from the async OpenRouter response."""
        msg = MagicMock()
        msg.content = "test report output"
        choice = MagicMock()
        choice.message = msg
        mock_response = MagicMock()
        mock_response.choices = [choice]

        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.shared_tools.openrouter_client.get_async_client",
            return_value=mock_client_instance,
        ):
            from core.gap_analysis.steps.s8_generate_report import _call_openai
            result, usage = await _call_openai("test prompt", "gpt-4o")

        assert result == "test report output"
        assert isinstance(usage, dict)


class TestAsyncGenerateGapReport:
    """Tests for async generate_gap_report."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """generate_gap_report should be an async function."""
        from core.gap_analysis.steps.s8_generate_report import generate_gap_report
        assert inspect.iscoroutinefunction(generate_gap_report)

    @pytest.mark.asyncio
    async def test_produces_report_with_mock_llm(self):
        """Should produce a GapReport with programmatic and LLM sections."""
        from core.models.gap_analysis import (
            AnalysisResult, GeneratedQuery, EnrichedCitation,
            QueryGap, SpaResult, StructuralSignals,
        )

        analysis = AnalysisResult(
            proximity_stats={
                "citation_similarity_mean": 0.5,
                "company_similarity_mean": 0.3,
                "citation_similarity_median": 0.45,
                "company_similarity_median": 0.28,
            },
            spa_results=[
                SpaResult(
                    test_name="cspa",
                    t_stat=2.5,
                    p_value=0.01,
                    effect="moderate",
                ),
            ],
            gaps=[
                QueryGap(
                    query_id="q_1",
                    query_text="How does expense management work?",
                    cluster_name="Mechanism",
                    gap=0.25,
                    interpretation="gap_to_close",
                ),
            ],
            centroids=[],
            cluster_specs=[],
            citation_patterns={},
            decision_metrics={"total_queries": 1, "total_citations": 5, "avg_gap": 0.25},
        )

        queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does expense management work?",
            ),
        ]
        citations = []

        llm_json = json.dumps({
            "executive_summary": "Test summary.",
            "recommendations": [
                {
                    "title_idea": "Test Content Piece",
                    "target_cluster": "Mechanism",
                    "structural_signals": "headers, lists",
                    "expected_impact": "Improve citation rate.",
                }
            ],
        })

        _usage_stub = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        with patch(
            "core.gap_analysis.steps.s8_generate_report._call_openai",
            new_callable=AsyncMock,
            return_value=(llm_json, _usage_stub),
        ), patch(
            "core.gap_analysis.steps.s8_generate_report.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_report_model = "gpt-4o"
            from core.gap_analysis.steps.s8_generate_report import generate_gap_report
            report = await generate_gap_report(analysis, queries, citations)

        assert report.report_md is not None
        assert "Gap Analysis Report" in report.report_md
        assert "Executive Summary" in report.report_md
        assert report.report_json["executive_summary"] == "Test summary."

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(self):
        """Should produce report even when LLM call fails."""
        from core.models.gap_analysis import AnalysisResult, GeneratedQuery, QueryGap

        analysis = AnalysisResult(
            proximity_stats={},
            spa_results=[],
            gaps=[
                QueryGap(
                    query_id="q_1",
                    query_text="Test query",
                    gap=0.1,
                    interpretation="roughly_equal",
                ),
            ],
            centroids=[],
            cluster_specs=[],
            citation_patterns={},
            decision_metrics={},
        )

        queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="Test query",
            ),
        ]

        with patch(
            "core.gap_analysis.steps.s8_generate_report._call_openai",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM failed"),
        ), patch(
            "core.gap_analysis.steps.s8_generate_report.settings"
        ) as mock_settings:
            mock_settings.gap_analysis_report_model = "gpt-4o"
            from core.gap_analysis.steps.s8_generate_report import generate_gap_report
            report = await generate_gap_report(analysis, queries, [])

        # Should still produce a report (just without LLM sections)
        assert report.report_md is not None
        assert "Gap Analysis Report" in report.report_md
        assert report.report_json["executive_summary"] == ""


# ---------------------------------------------------------------------------
# Phase 3 Tests: Enhanced report builders + save_report
# ---------------------------------------------------------------------------

from core.models.gap_analysis import (
    AnalysisResult,
    CitationExemplar,
    ClusterContentSpec,
    GapContentBrief,
    GapReport,
    QueryGap,
    SpaResult,
    StructuralSignals,
)


def _make_gap_with_brief(
    qid: str,
    cluster: str = "awareness",
    gap_val: float = 0.2,
) -> QueryGap:
    brief = GapContentBrief(
        target_word_count=(800, 1500),
        target_reading_level=(9.0, 12.0),
        avg_paragraph_length=(30, 50),
        recommended_header_count=(4, 8),
        header_hierarchy={"h2": 4, "h3": 3},
        has_faq_section=0.67,
        has_key_takeaways=0.33,
        has_step_by_step=0.0,
        has_tables=0.67,
        dominant_authority_type="commercial_or_media",
        dominant_content_type="blog_or_article",
        exemplar_count=3,
    )
    return QueryGap(
        query_id=qid,
        cluster_name=cluster,
        query_text=f"test query for {qid}",
        best_company_similarity=0.3,
        avg_citation_similarity=0.5,
        gap=gap_val,
        interpretation="significant_gap" if gap_val >= 0.15 else "gap_to_close",
        top_cited_exemplars=[
            CitationExemplar(
                similarity=0.85,
                domain="example.com",
                url="https://example.com/page",
                structural_signals=StructuralSignals(word_count=1000, header_count=5),
                authority_type="commercial_or_media",
            )
        ],
        content_brief=brief,
    )


def _make_test_analysis(num_gaps: int = 30) -> AnalysisResult:
    gaps = [_make_gap_with_brief(f"q{i}", gap_val=0.3 - (i * 0.01)) for i in range(num_gaps)]
    return AnalysisResult(
        proximity_stats={
            "citation_similarity_mean": 0.5,
            "citation_similarity_median": 0.48,
            "company_similarity_mean": 0.3,
            "company_similarity_median": 0.28,
        },
        spa_results=[
            SpaResult(
                cluster_name="all",
                t_stat=3.5,
                p_value=0.001,
                effect="citation_advantage",
            )
        ],
        gaps=gaps,
        decision_metrics={"total_queries": num_gaps, "total_citations": 100, "avg_gap": 0.15},
        cluster_specs=[
            ClusterContentSpec(
                cluster_name="awareness",
                query_count=15,
                word_count_range=[500, 2000],
                structural_rates={"headers": 0.9, "lists": 0.8},
                total_citations_analyzed=50,
                faq_rate=0.6,
                table_rate=0.4,
                avg_word_count=1200.0,
                avg_paragraph_word_count=45.0,
                dominant_content_type="blog_or_article",
                dominant_authority_type="commercial_or_media",
                exemplar_themes=["expense", "management", "automation"],
            )
        ],
    )


class TestGapReportMdPhase3:
    """Tests for _build_gap_report_md with top-25 rendering and inline ContentBrief."""

    def test_renders_top_25_gaps(self):
        from core.gap_analysis.steps.s8_generate_report import _build_gap_report_md
        analysis = _make_test_analysis(30)
        md = _build_gap_report_md(analysis, [])
        assert "Gap Briefs (Top 25)" in md
        assert "q0" in md
        assert "q24" in md
        assert "Remaining Query Gaps" in md

    def test_inline_content_brief_rendered(self):
        from core.gap_analysis.steps.s8_generate_report import _build_gap_report_md
        analysis = _make_test_analysis(5)
        md = _build_gap_report_md(analysis, [])
        assert "Content Brief:" in md
        assert "800" in md
        assert "FAQ" in md

    def test_no_appendix_when_under_25(self):
        from core.gap_analysis.steps.s8_generate_report import _build_gap_report_md
        analysis = _make_test_analysis(10)
        md = _build_gap_report_md(analysis, [])
        assert "Remaining Query Gaps" not in md


class TestGenerationSpecMdPhase3:
    def test_expanded_fields_rendered(self):
        from core.gap_analysis.steps.s8_generate_report import _build_generation_spec_md
        analysis = _make_test_analysis()
        md = _build_generation_spec_md(analysis)
        assert "FAQ Rate:" in md
        assert "Table Rate:" in md
        assert "Avg Word Count:" in md
        assert "Dominant Content Type:" in md
        assert "Exemplar Themes:" in md


class TestSaveReportPhase3:
    def test_writes_standard_files(self, tmp_path):
        from core.gap_analysis.steps.s8_generate_report import save_report
        from core.storage.backends.local import LocalStorageBackend
        storage = LocalStorageBackend(tmp_path)
        report = GapReport(
            report_md="# Test",
            report_json={"executive_summary": "Test"},
            generation_spec_md="# Spec",
            generation_spec_json={"cluster_specs": []},
        )
        save_report(report, storage, "out")
        assert (tmp_path / "out" / "gap_report.md").exists()
        assert (tmp_path / "out" / "gap_report.json").exists()
        assert (tmp_path / "out" / "generation_spec.md").exists()
        assert (tmp_path / "out" / "generation_spec.json").exists()

    def test_writes_complete_json_when_analysis_provided(self, tmp_path):
        from core.gap_analysis.steps.s8_generate_report import save_report
        from core.storage.backends.local import LocalStorageBackend
        storage = LocalStorageBackend(tmp_path)
        analysis = _make_test_analysis(5)
        report = GapReport(
            report_md="# Test",
            report_json={"executive_summary": "Summary", "recommendations": [{"title": "T"}]},
            generation_spec_md="# Spec",
            generation_spec_json={"cluster_specs": []},
        )
        save_report(report, storage, "out", analysis=analysis)
        complete_path = tmp_path / "out" / "gap_analysis_complete.json"
        assert complete_path.exists()
        data = json.loads(complete_path.read_text())
        assert "generated_at" in data
        assert "analysis" in data
        assert "cluster_specs" in data
        assert len(data["analysis"]["gaps"]) == 5
        assert data["analysis"]["gaps"][0]["content_brief"] is not None

    def test_no_complete_json_without_analysis(self, tmp_path):
        from core.gap_analysis.steps.s8_generate_report import save_report
        from core.storage.backends.local import LocalStorageBackend
        storage = LocalStorageBackend(tmp_path)
        report = GapReport(report_md="# Test", report_json={}, generation_spec_md="# S", generation_spec_json={})
        save_report(report, storage, "out")
        assert not (tmp_path / "out" / "gap_analysis_complete.json").exists()

    def test_existing_3_files_not_broken(self, tmp_path):
        from core.gap_analysis.steps.s8_generate_report import save_report
        from core.storage.backends.local import LocalStorageBackend
        storage = LocalStorageBackend(tmp_path)
        analysis = _make_test_analysis(3)
        report = GapReport(
            report_md="# Gap Report",
            report_json={"executive_summary": "Test", "recommendations": []},
            generation_spec_md="# Spec",
            generation_spec_json={"cluster_specs": [{"cluster_name": "test"}]},
        )
        save_report(report, storage, "out", analysis=analysis)
        assert (tmp_path / "out" / "gap_report.md").read_text() == "# Gap Report"
        gap_json = json.loads((tmp_path / "out" / "gap_report.json").read_text())
        assert gap_json["executive_summary"] == "Test"


class TestCallOpenAICostTracking:
    """Verify track_llm_cost() is called inside _call_openai()."""

    @pytest.mark.asyncio
    async def test_cost_tracked(self):
        msg = MagicMock()
        msg.content = "report output"
        choice = MagicMock()
        choice.message = msg
        mock_response = MagicMock()
        mock_response.choices = [choice]
        mock_response.usage = MagicMock(prompt_tokens=200, completion_tokens=500)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.shared_tools.openrouter_client.get_async_client",
            return_value=mock_client,
        ), patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            from core.gap_analysis.steps.s8_generate_report import _call_openai
            await _call_openai("prompt", "gpt-5.2")

        mock_track.assert_called_once()
        kw = mock_track.call_args[1]
        assert kw["pipeline"] == "gap_analysis"
        assert kw["pipeline_step"] == "s8_report"
        assert kw["prompt_tokens"] == 200
        assert kw["completion_tokens"] == 500
        assert kw["source"] == "openrouter"
