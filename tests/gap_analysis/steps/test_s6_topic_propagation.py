"""Tests for S6 source_topic_ids propagation and S8 aggregate_per_topic.

Phase 3 of TD → GA → CE integration.
"""
from __future__ import annotations

import pytest

from core.models.gap_analysis import (
    AnalysisResult,
    CitationExemplar,
    EnrichedCitation,
    GeneratedQuery,
    ParagraphMatch,
    QueryGap,
    SemanticUnit,
)


# ---------------------------------------------------------------------------
# S6: source_topic_ids propagation
# ---------------------------------------------------------------------------


class TestS6TopicIdPropagation:
    """Verify source_topic_ids flows from GeneratedQuery → QueryGap."""

    def test_source_topic_ids_propagated_to_gap(self):
        """compute_gap_analysis should copy source_topic_ids from query to gap."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        emb = [1.0, 0.0, 0.0]
        queries = [
            GeneratedQuery(
                query_id="tq_1",
                cluster_id="C5",
                cluster_name="Definition",
                query_text="What is AP automation?",
                embedding=emb,
                source_topic_ids=["ta-1", "ta-2"],
            ),
        ]
        units = [
            SemanticUnit(
                unit_id="u1",
                text="Company AP page",
                embedding=[0.5, 0.5, 0.0],
            ),
        ]
        enriched = [
            EnrichedCitation(
                url="https://example.com/ap",
                query_id="tq_1",
                cluster_name="Definition",
                best_paragraphs=[
                    ParagraphMatch(
                        paragraph="AP automation explained",
                        embedding=[0.9, 0.1, 0.0],
                    ),
                ],
            ),
        ]

        result = compute_gap_analysis(queries, units, enriched)

        assert len(result.gaps) == 1
        assert result.gaps[0].source_topic_ids == ["ta-1", "ta-2"]

    def test_empty_source_topic_ids_propagated(self):
        """Standard queries (no topic context) should have empty source_topic_ids."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        emb = [1.0, 0.0, 0.0]
        queries = [
            GeneratedQuery(
                query_id="q_1",
                cluster_id="C1",
                cluster_name="Mechanism",
                query_text="How does AP work?",
                embedding=emb,
                # No source_topic_ids → defaults to []
            ),
        ]
        units = [
            SemanticUnit(
                unit_id="u1",
                text="Company page",
                embedding=[0.5, 0.5, 0.0],
            ),
        ]
        enriched = [
            EnrichedCitation(
                url="https://example.com",
                query_id="q_1",
                cluster_name="Mechanism",
                best_paragraphs=[
                    ParagraphMatch(
                        paragraph="How it works",
                        embedding=[0.8, 0.2, 0.0],
                    ),
                ],
            ),
        ]

        result = compute_gap_analysis(queries, units, enriched)

        assert len(result.gaps) == 1
        assert result.gaps[0].source_topic_ids == []


# ---------------------------------------------------------------------------
# S8: aggregate_per_topic
# ---------------------------------------------------------------------------


class TestAggregatePerTopic:
    def test_basic_aggregation(self):
        from core.gap_analysis.steps.s8_generate_report import aggregate_per_topic

        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?", source_topic_ids=["ta-1"],
            ),
            GeneratedQuery(
                query_id="tq_2", cluster_id="C6", cluster_name="Problem/Awareness",
                query_text="How to reduce AP time?", source_topic_ids=["ta-1"],
            ),
            GeneratedQuery(
                query_id="tq_3", cluster_id="C7", cluster_name="Best-of",
                query_text="Best AP tools?", source_topic_ids=["ta-2"],
            ),
        ]

        analysis = AnalysisResult(
            gaps=[
                QueryGap(query_id="tq_1", query_text="What is AP?",
                         cluster_name="Definition", gap=0.2,
                         interpretation="significant_gap",
                         top_cited_exemplars=[
                             CitationExemplar(similarity=0.8, url="https://a.com"),
                             CitationExemplar(similarity=0.7, url="https://b.com"),
                         ]),
                QueryGap(query_id="tq_2", query_text="How to reduce AP time?",
                         cluster_name="Problem/Awareness", gap=0.1,
                         interpretation="gap_to_close",
                         top_cited_exemplars=[
                             CitationExemplar(similarity=0.6, url="https://c.com"),
                         ]),
                QueryGap(query_id="tq_3", query_text="Best AP tools?",
                         cluster_name="Best-of", gap=0.3,
                         interpretation="significant_gap",
                         top_cited_exemplars=[]),
            ],
        )

        result = aggregate_per_topic(analysis, queries)

        assert "ta-1" in result
        assert "ta-2" in result

        ta1 = result["ta-1"]
        assert ta1["query_count"] == 2
        assert ta1["avg_gap"] == pytest.approx(0.15, abs=0.01)
        assert ta1["max_gap"] == pytest.approx(0.2, abs=0.01)
        assert ta1["significant_gap_count"] == 1
        assert ta1["exemplar_count"] == 3
        assert set(ta1["query_ids"]) == {"tq_1", "tq_2"}
        assert "Definition" in ta1["cluster_names"]
        assert "Problem/Awareness" in ta1["cluster_names"]

        ta2 = result["ta-2"]
        assert ta2["query_count"] == 1
        assert ta2["avg_gap"] == pytest.approx(0.3, abs=0.01)
        assert ta2["significant_gap_count"] == 1
        assert ta2["exemplar_count"] == 0

    def test_shared_query_across_topics(self):
        """A query with 2 source_topic_ids should appear in both topics."""
        from core.gap_analysis.steps.s8_generate_report import aggregate_per_topic

        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?", source_topic_ids=["ta-1", "ta-2"],
            ),
        ]
        analysis = AnalysisResult(
            gaps=[
                QueryGap(query_id="tq_1", query_text="What is AP?",
                         cluster_name="Definition", gap=0.2,
                         interpretation="significant_gap"),
            ],
        )

        result = aggregate_per_topic(analysis, queries)

        assert "ta-1" in result
        assert "ta-2" in result
        assert result["ta-1"]["query_ids"] == ["tq_1"]
        assert result["ta-2"]["query_ids"] == ["tq_1"]

    def test_empty_inputs(self):
        from core.gap_analysis.steps.s8_generate_report import aggregate_per_topic

        result = aggregate_per_topic(AnalysisResult(), [])
        assert result == {}

    def test_sets_topic_query_map_on_analysis(self):
        from core.gap_analysis.steps.s8_generate_report import aggregate_per_topic

        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?", source_topic_ids=["ta-1"],
            ),
        ]
        analysis = AnalysisResult(
            gaps=[
                QueryGap(query_id="tq_1", query_text="What is AP?",
                         cluster_name="Definition", gap=0.1),
            ],
        )

        aggregate_per_topic(analysis, queries)

        assert analysis.topic_query_map == {"ta-1": ["tq_1"]}

    def test_topic_with_no_matching_gaps(self):
        """If a query exists in topic_queries but not in gaps, handle gracefully."""
        from core.gap_analysis.steps.s8_generate_report import aggregate_per_topic

        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?", source_topic_ids=["ta-1"],
            ),
        ]
        # No gaps at all
        analysis = AnalysisResult(gaps=[])

        result = aggregate_per_topic(analysis, queries)

        assert result["ta-1"]["avg_gap"] == 0.0
        assert result["ta-1"]["query_count"] == 1
        assert result["ta-1"]["exemplar_count"] == 0
