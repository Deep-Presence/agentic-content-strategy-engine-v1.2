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
        """Should return the output_text from the async OpenAI response."""
        mock_response = MagicMock()
        mock_response.output_text = "test report output"

        mock_client_instance = AsyncMock()
        mock_client_instance.responses.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.gap_analysis.steps.s8_generate_report.AsyncOpenAI",
            return_value=mock_client_instance,
        ), patch(
            "core.gap_analysis.steps.s8_generate_report.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            from core.gap_analysis.steps.s8_generate_report import _call_openai
            result = await _call_openai("test prompt", "gpt-4o")

        assert result == "test report output"


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
                    interpretation="moderate_gap",
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

        with patch(
            "core.gap_analysis.steps.s8_generate_report._call_openai",
            new_callable=AsyncMock,
            return_value=llm_json,
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
                    interpretation="small_gap",
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
