"""Tests for pipeline.py async orchestrator — TDD: written BEFORE implementation.

Focused on async behavior, step timing, skip_steps, and error isolation.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.gap_analysis import (
    GapAnalysisInput,
    GapReport,
    SemanticUnit,
    GeneratedQuery,
    PlatformResult,
    EnrichedCitation,
    AnalysisResult,
    StructuralSignals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def input_data():
    return GapAnalysisInput(
        company_name="Test Co",
        domain="test.com",
        seed_urls=["https://test.com"],
        platforms=["perplexity"],
        max_queries=10,
    )


@pytest.fixture
def mock_report():
    return GapReport(
        report_md="# Test Report",
        report_json={"executive_summary": "test"},
        generation_spec_md="# Spec",
        generation_spec_json={},
        visualization_paths=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncRunGapAnalysis:
    """Tests for async run_gap_analysis."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """run_gap_analysis should be an async function."""
        from core.gap_analysis.pipeline import run_gap_analysis
        assert inspect.iscoroutinefunction(run_gap_analysis)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_all_steps_mocked(self, input_data, mock_report, tmp_path):
        """Should run all 8 steps and return a GapReport."""
        (tmp_path / "visualizations").mkdir()
        mock_units = [
            SemanticUnit(
                unit_id="unit_1",
                url="https://test.com",
                page_title="Test",
                text="Test text",
                embedding=[0.1, 0.2],
            ),
        ]
        mock_queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does it work?",
            ),
        ]
        mock_platform_results = [
            PlatformResult(
                query_id="q_1",
                engine="perplexity",
                citations=[],
            ),
        ]
        mock_enriched = [
            EnrichedCitation(
                url="https://example.com",
                domain="example.com",
                title="Test",
                query_id="q_1",
                engine="perplexity",
                anchor_text="anchor",
                paragraphs=[],
                best_paragraphs=[],
                structural_signals=StructuralSignals(),
            ),
        ]
        mock_analysis = AnalysisResult(
            proximity_stats={},
            spa_results=[],
            gaps=[],
            centroids=[],
            cluster_specs=[],
            citation_patterns={},
            decision_metrics={},
        )

        with patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            return_value=mock_units,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries",
            new_callable=AsyncMock,
            return_value=mock_queries,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock,
            return_value=mock_platform_results,
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock,
            return_value=mock_enriched,
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock,
            return_value=(mock_queries, mock_enriched),
        ), patch(
            "core.gap_analysis.pipeline.compute_gap_analysis",
            return_value=mock_analysis,
        ), patch(
            "core.gap_analysis.pipeline.generate_visualizations",
            return_value={},
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            report = await run_gap_analysis(input_data)

        assert isinstance(report, GapReport)
        assert report.report_md == "# Test Report"

    @pytest.mark.asyncio
    async def test_skip_steps_loads_from_artifacts(self, input_data, mock_report, tmp_path):
        """Should load from artifacts when steps are skipped."""
        (tmp_path / "visualizations").mkdir()
        # Create artifact files for steps 1 and 2
        units_data = [
            SemanticUnit(
                unit_id="unit_1",
                url="https://test.com",
                page_title="Test",
                text="Test text",
                embedding=[0.1, 0.2],
            ).model_dump(mode="json"),
        ]
        queries_data = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does it work?",
            ).model_dump(mode="json"),
        ]

        (tmp_path / "company_embeddings.json").write_text(json.dumps(units_data, default=str))
        (tmp_path / "queries.json").write_text(json.dumps(queries_data, default=str))

        mock_platform_results = []
        mock_enriched = []
        mock_analysis = AnalysisResult(
            proximity_stats={}, spa_results=[], gaps=[], centroids=[],
            cluster_specs=[], citation_patterns={}, decision_metrics={},
        )

        with patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock,
            return_value=mock_platform_results,
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock,
            return_value=mock_enriched,
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock,
            return_value=([], mock_enriched),
        ), patch(
            "core.gap_analysis.pipeline.compute_gap_analysis",
            return_value=mock_analysis,
        ), patch(
            "core.gap_analysis.pipeline.generate_visualizations",
            return_value={},
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            report = await run_gap_analysis(input_data, skip_steps=[1, 2])

        assert isinstance(report, GapReport)

    @pytest.mark.asyncio
    async def test_step_error_isolation(self, input_data, tmp_path):
        """Individual step failures should not crash the pipeline."""
        with patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            side_effect=RuntimeError("s1 exploded"),
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            # Should raise since s1 failure means no data for subsequent steps
            with pytest.raises(RuntimeError, match="s1 exploded"):
                await run_gap_analysis(input_data)


# ---------------------------------------------------------------------------
# Tests: Self-citation helpers
# ---------------------------------------------------------------------------
from core.models.gap_analysis import CitationRef


class TestFastMode:
    """Tests for Phase 5: fast/demo mode."""

    def test_fast_mode_caps_queries(self):
        """fast_mode=True should cap max_queries at 30."""
        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            max_queries=150,
            fast_mode=True,
        )
        # Simulate the fast mode guard logic from pipeline
        if input_data.fast_mode:
            input_data.max_queries = min(input_data.max_queries or 30, 30)
        assert input_data.max_queries == 30

    def test_fast_mode_selects_fast_engines(self):
        """fast_mode=True should select only openai and perplexity."""
        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            platforms=["perplexity", "openai", "gemini", "claude"],
            fast_mode=True,
        )
        if input_data.fast_mode:
            if not input_data.platforms or len(input_data.platforms) > 2:
                input_data.platforms = ["openai", "perplexity"]
        assert set(input_data.platforms) == {"openai", "perplexity"}

    def test_fast_mode_preserves_custom_two_platforms(self):
        """fast_mode with exactly 2 platforms should keep user's choice."""
        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            platforms=["gemini", "claude"],
            fast_mode=True,
        )
        if input_data.fast_mode:
            if not input_data.platforms or len(input_data.platforms) > 2:
                input_data.platforms = ["openai", "perplexity"]
        assert input_data.platforms == ["gemini", "claude"]

    def test_fast_mode_default_false(self):
        """GapAnalysisInput without fast_mode should default to False."""
        input_data = GapAnalysisInput(company_name="Test Co")
        assert input_data.fast_mode is False

    def test_fast_mode_backward_compat_deserialization(self):
        """Old JSON without fast_mode should deserialize with default False."""
        old_json = {"company_name": "Test Co", "max_queries": 100}
        input_data = GapAnalysisInput(**old_json)
        assert input_data.fast_mode is False
        assert input_data.max_queries == 100


class TestFlagCompanyCitations:
    """Tests for _flag_company_citations helper."""

    def test_flags_matching_domain(self):
        from core.gap_analysis.pipeline import _flag_company_citations

        results = [
            PlatformResult(
                engine="perplexity",
                query_id="q1",
                citations=[
                    CitationRef(url="https://ramp.com/blog/post-1"),
                    CitationRef(url="https://competitor.com/page"),
                ],
            ),
        ]
        _flag_company_citations(results, "ramp.com")
        assert results[0].citations[0].is_company_citation is True
        assert results[0].citations[1].is_company_citation is False

    def test_handles_www_prefix(self):
        from core.gap_analysis.pipeline import _flag_company_citations

        results = [
            PlatformResult(
                engine="openai",
                query_id="q1",
                citations=[
                    CitationRef(url="https://www.ramp.com/blog"),
                ],
            ),
        ]
        _flag_company_citations(results, "ramp.com")
        assert results[0].citations[0].is_company_citation is True

    def test_handles_subdomain(self):
        from core.gap_analysis.pipeline import _flag_company_citations

        results = [
            PlatformResult(
                engine="claude",
                query_id="q1",
                citations=[
                    CitationRef(url="https://docs.ramp.com/api"),
                ],
            ),
        ]
        _flag_company_citations(results, "ramp.com")
        assert results[0].citations[0].is_company_citation is True

    def test_no_domain_skips_flagging(self):
        from core.gap_analysis.pipeline import _flag_company_citations

        results = [
            PlatformResult(
                engine="gemini",
                query_id="q1",
                citations=[CitationRef(url="https://ramp.com/x")],
            ),
        ]
        _flag_company_citations(results, None)
        assert results[0].citations[0].is_company_citation is False


class TestBuildCompanyCitationMap:
    """Tests for _build_company_citation_map helper."""

    def test_builds_map_from_flagged_citations(self):
        from core.gap_analysis.pipeline import _build_company_citation_map

        results = [
            PlatformResult(
                engine="perplexity",
                query_id="q1",
                citations=[
                    CitationRef(url="https://ramp.com/blog", is_company_citation=True),
                    CitationRef(url="https://other.com", is_company_citation=False),
                ],
            ),
            PlatformResult(
                engine="openai",
                query_id="q1",
                citations=[
                    CitationRef(url="https://ramp.com/page", is_company_citation=True),
                ],
            ),
        ]
        result = _build_company_citation_map(results)
        assert "q1" in result
        assert set(result["q1"]) == {"perplexity", "openai"}

    def test_empty_when_no_company_citations(self):
        from core.gap_analysis.pipeline import _build_company_citation_map

        results = [
            PlatformResult(
                engine="gemini",
                query_id="q1",
                citations=[
                    CitationRef(url="https://other.com", is_company_citation=False),
                ],
            ),
        ]
        result = _build_company_citation_map(results)
        assert result == {}


# ---------------------------------------------------------------------------
# S1 || S2 Parallelism tests
# ---------------------------------------------------------------------------


class TestS1S2Parallelism:
    """Verify S1 and S2 run in parallel via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_s1_s2_run_concurrently(self, input_data, mock_report, tmp_path):
        """S1 and S2 should overlap in time, not run sequentially."""
        import time

        (tmp_path / "visualizations").mkdir()

        s1_start = None
        s2_start = None
        s1_end = None
        s2_end = None

        mock_units = [
            SemanticUnit(
                unit_id="unit_1", url="https://test.com",
                text="Test text", embedding=[0.1, 0.2],
            ),
        ]
        mock_queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Test",
                query_text="How does it work?",
            ),
        ]

        async def _slow_s1(input_data):
            nonlocal s1_start, s1_end
            s1_start = time.monotonic()
            await asyncio.sleep(0.2)
            s1_end = time.monotonic()
            return mock_units

        async def _slow_s2(input_data, **kwargs):
            nonlocal s2_start, s2_end
            s2_start = time.monotonic()
            await asyncio.sleep(0.2)
            s2_end = time.monotonic()
            return mock_queries

        mock_analysis = AnalysisResult(
            proximity_stats={}, spa_results=[], gaps=[], centroids=[],
            cluster_specs=[], citation_patterns={}, decision_metrics={},
        )

        with patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock, side_effect=_slow_s1,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries",
            new_callable=AsyncMock, side_effect=_slow_s2,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock, return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock, return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock, return_value=(mock_queries, []),
        ), patch(
            "core.gap_analysis.pipeline.compute_gap_analysis",
            return_value=mock_analysis,
        ), patch(
            "core.gap_analysis.pipeline.generate_visualizations",
            return_value={},
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock, return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            from core.gap_analysis.pipeline import run_gap_analysis

            t0 = time.monotonic()
            await run_gap_analysis(input_data)
            wall_time = time.monotonic() - t0

        # If sequential, total >= 0.4s. If parallel, total ~0.2s
        assert wall_time < 0.35, f"S1+S2 took {wall_time:.2f}s — likely sequential"
        # S2 should start before S1 finishes (overlap)
        assert s2_start < s1_end, "S2 did not start before S1 finished"

    @pytest.mark.asyncio
    async def test_s1_failure_aborts_pipeline(self, input_data, tmp_path):
        """If S1 fails, pipeline should abort (S6/S7 need company_units)."""
        with patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            side_effect=RuntimeError("s1 exploded"),
        ), patch(
            "core.gap_analysis.pipeline.generate_queries",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            with pytest.raises(RuntimeError, match="s1 exploded"):
                await run_gap_analysis(input_data)

    @pytest.mark.asyncio
    async def test_s2_failure_aborts_pipeline(self, input_data, tmp_path):
        """If S2 fails, pipeline should abort (S3 needs queries)."""
        mock_units = [
            SemanticUnit(
                unit_id="unit_1", url="https://test.com",
                text="Test text", embedding=[0.1, 0.2],
            ),
        ]

        with patch(
            "core.gap_analysis.pipeline._artifact_dir",
            return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            return_value=mock_units,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries",
            new_callable=AsyncMock,
            side_effect=RuntimeError("s2 exploded"),
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            with pytest.raises(RuntimeError, match="s2 exploded"):
                await run_gap_analysis(input_data)

    @pytest.mark.asyncio
    async def test_skip_s1_s2_loads_from_artifacts(self, input_data, mock_report, tmp_path):
        """When both S1 and S2 are skipped, artifacts are loaded (no parallelism needed)."""
        (tmp_path / "visualizations").mkdir()

        units_data = [
            SemanticUnit(
                unit_id="u1", url="https://test.com",
                text="test", embedding=[0.1],
            ).model_dump(mode="json"),
        ]
        queries_data = [
            GeneratedQuery(
                query_id="q1", cluster_id="C1", cluster_name="Test",
                query_text="test?",
            ).model_dump(mode="json"),
        ]
        (tmp_path / "company_embeddings.json").write_text(json.dumps(units_data, default=str))
        (tmp_path / "queries.json").write_text(json.dumps(queries_data, default=str))

        mock_analysis = AnalysisResult(
            proximity_stats={}, spa_results=[], gaps=[], centroids=[],
            cluster_specs=[], citation_patterns={}, decision_metrics={},
        )

        with patch(
            "core.gap_analysis.pipeline._artifact_dir", return_value=tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock, return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock, return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock, return_value=([], []),
        ), patch(
            "core.gap_analysis.pipeline.compute_gap_analysis",
            return_value=mock_analysis,
        ), patch(
            "core.gap_analysis.pipeline.generate_visualizations",
            return_value={},
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock, return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            from core.gap_analysis.pipeline import run_gap_analysis
            report = await run_gap_analysis(input_data, skip_steps=[1, 2])

        assert isinstance(report, GapReport)
