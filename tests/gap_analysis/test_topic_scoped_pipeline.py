"""Tests for run_topic_scoped_gap_analysis pipeline entry.

Phase 4 of TD → GA → CE integration.
Tests the end-to-end pipeline with mocked S1-S8 steps.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.gap_analysis import (
    AnalysisResult,
    EnrichedCitation,
    GapAnalysisInput,
    GapReport,
    GeneratedQuery,
    ParagraphMatch,
    QueryGap,
    SemanticUnit,
)
from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
)


def _make_topic(topic_id: str = "ta-1") -> TopicAssignment:
    return TopicAssignment(
        id=topic_id,
        subdomain_id="sd-1",
        subdomain_name="AP Automation",
        topic_text="How AP Automation Reduces Invoice Processing Time",
        buyer_stage=BuyerStage.TOFU,
        intent_type=IntentType.informational,
        audience_segment="AP Manager",
    )


def _make_base_input() -> GapAnalysisInput:
    return GapAnalysisInput(
        company_name="Test Co",
        domain="test.co",
        platforms=["openai"],
    )


class TestRunTopicScopedGapAnalysis:
    def test_is_async(self):
        from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis

        assert inspect.iscoroutinefunction(run_topic_scoped_gap_analysis)

    @pytest.mark.asyncio
    async def test_empty_queries_returns_empty_report(self, tmp_path):
        """If topic-scoped S2 produces 0 queries, return empty report."""
        from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis

        topic = _make_topic()
        base_input = _make_base_input()

        with patch(
            "core.gap_analysis.pipeline._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries_from_topics",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline._resolve_persona_paths",
        ):
            report, topic_query_map = await run_topic_scoped_gap_analysis(
                topics=[topic],
                base_input=base_input,
            )

        assert topic_query_map == {}
        assert isinstance(report, GapReport)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(self, tmp_path):
        """End-to-end with all steps mocked."""
        from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis

        topic = _make_topic(topic_id="ta-1")
        base_input = _make_base_input()

        mock_queries = [
            GeneratedQuery(
                query_id="tq_1",
                cluster_id="C5",
                cluster_name="Definition",
                query_text="What is AP automation?",
                embedding=[1.0, 0.0, 0.0],
                source_topic_ids=["ta-1"],
            ),
        ]
        mock_units = [
            SemanticUnit(
                unit_id="u1",
                text="Company AP page",
                embedding=[0.5, 0.5, 0.0],
            ),
        ]
        mock_enriched = [
            EnrichedCitation(
                url="https://example.com",
                query_id="tq_1",
                cluster_name="Definition",
                best_paragraphs=[
                    ParagraphMatch(
                        paragraph="AP explained",
                        embedding=[0.9, 0.1, 0.0],
                    ),
                ],
            ),
        ]
        mock_report = GapReport(
            report_md="# Test Report",
            report_json={"gaps": []},
        )

        with patch(
            "core.gap_analysis.pipeline._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.gap_analysis.pipeline._resolve_persona_paths",
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            return_value=mock_units,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries_from_topics",
            new_callable=AsyncMock,
            return_value=mock_queries,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock,
            return_value=mock_enriched,
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock,
            return_value=(mock_queries, mock_enriched),
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            report, topic_query_map = await run_topic_scoped_gap_analysis(
                topics=[topic],
                base_input=base_input,
            )

        assert isinstance(report, GapReport)
        assert "ta-1" in topic_query_map
        assert "tq_1" in topic_query_map["ta-1"]

    @pytest.mark.asyncio
    async def test_reuses_cached_embeddings(self, tmp_path):
        """When existing_ga_slug has cached embeddings, S1 should reuse them."""
        from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis

        # Create cached embeddings
        cache_dir = tmp_path / "artifacts" / "gap_analysis" / "test-co"
        cache_dir.mkdir(parents=True)
        cached_units = [
            SemanticUnit(
                unit_id="u1", text="Cached page",
                embedding=[1.0, 0.0, 0.0],
            ).model_dump(mode="json"),
        ]
        (cache_dir / "company_embeddings.json").write_text(
            json.dumps(cached_units), encoding="utf-8",
        )

        topic = _make_topic()
        base_input = _make_base_input()

        mock_queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?", embedding=[1.0, 0.0, 0.0],
                source_topic_ids=["ta-1"],
            ),
        ]

        embed_assets_mock = AsyncMock()

        with patch(
            "core.gap_analysis.pipeline._PROJECT_ROOT", tmp_path,
        ), patch(
            "core.gap_analysis.pipeline._resolve_persona_paths",
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            embed_assets_mock,
        ), patch(
            "core.gap_analysis.pipeline.generate_queries_from_topics",
            new_callable=AsyncMock,
            return_value=mock_queries,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock,
            return_value=(mock_queries, []),
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=GapReport(),
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            await run_topic_scoped_gap_analysis(
                topics=[topic],
                base_input=base_input,
                existing_ga_slug="test-co",
            )

        # embed_company_assets should NOT have been called (cache hit)
        embed_assets_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_scoped_artifacts_written(self, tmp_path):
        """Verify artifacts go to topic_scoped/{run_id}/ subdirectory."""
        import uuid

        from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis
        from core.storage.backends.local import LocalStorageBackend

        topic = _make_topic()
        base_input = _make_base_input()
        test_run_id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        storage = LocalStorageBackend(tmp_path)

        mock_queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?", embedding=[1.0, 0.0, 0.0],
                source_topic_ids=["ta-1"],
            ),
        ]

        with patch(
            "core.gap_analysis.pipeline._resolve_persona_paths",
        ), patch(
            "core.gap_analysis.pipeline.embed_company_assets",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.generate_queries_from_topics",
            new_callable=AsyncMock,
            return_value=mock_queries,
        ), patch(
            "core.gap_analysis.pipeline.search_platforms",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.save_platform_results",
        ), patch(
            "core.gap_analysis.pipeline.enrich_citations",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "core.gap_analysis.pipeline.save_enriched_citations",
        ), patch(
            "core.gap_analysis.pipeline.embed_all",
            new_callable=AsyncMock,
            return_value=(mock_queries, []),
        ), patch(
            "core.gap_analysis.pipeline.save_embeddings",
        ), patch(
            "core.gap_analysis.pipeline.generate_gap_report",
            new_callable=AsyncMock,
            return_value=GapReport(),
        ), patch(
            "core.gap_analysis.pipeline.save_report",
        ):
            await run_topic_scoped_gap_analysis(
                topics=[topic],
                base_input=base_input,
                run_id=test_run_id,
                storage=storage,
            )

        prefix = f"gap_analysis/test-co/topic_scoped/{test_run_id}"
        assert storage.exists(f"{prefix}/queries.json")
        assert storage.exists(f"{prefix}/analysis.json")
        assert storage.exists(f"{prefix}/topic_metrics.json")

        # Verify topic_query_map is in analysis.json
        analysis_data = json.loads(
            storage.read(f"{prefix}/analysis.json")
        )
        assert "topic_query_map" in analysis_data
        assert "ta-1" in analysis_data["topic_query_map"]
