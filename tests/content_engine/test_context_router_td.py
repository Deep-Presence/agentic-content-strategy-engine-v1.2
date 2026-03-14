"""Tests for Topic Discovery context routing functions.

Phase 5 of TD → GA → CE integration.
Tests extract_topic_contexts() and topic_assignment_to_selection().
"""
from __future__ import annotations

import pytest

from core.content_engine.context_router import (
    extract_topic_contexts,
    topic_assignment_to_selection,
)
from core.models.content_generation_v13 import TopicSelection, WorkerQueryContext
from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
)


def _make_assignment(
    assignment_id: str = "ta-1",
    buyer_stage: BuyerStage = BuyerStage.MOFU,
    intent_type: IntentType = IntentType.commercial,
) -> TopicAssignment:
    return TopicAssignment(
        id=assignment_id,
        subdomain_id="sd-1",
        subdomain_name="AP Automation",
        topic_text="How AP Automation Reduces Invoice Processing Time",
        buyer_stage=buyer_stage,
        intent_type=intent_type,
        audience_segment="AP Manager",
        priority_score=0.85,
    )


# ---------------------------------------------------------------------------
# extract_topic_contexts
# ---------------------------------------------------------------------------


class TestExtractTopicContexts:
    def test_basic_extraction(self):
        analysis_json = {
            "gaps": [
                {
                    "query_id": "tq_1",
                    "query_text": "What is AP automation?",
                    "cluster_name": "Definition",
                    "gap": 0.25,
                    "best_company_similarity": 0.3,
                    "avg_citation_similarity": 0.55,
                    "interpretation": "significant_gap",
                    "top_cited_exemplars": [
                        {"url": "https://a.com", "similarity": 0.8, "snippet": "AP explained"},
                    ],
                    "content_brief": {"target_word_count": [1200, 2000]},
                    "best_company_unit_text": "Our AP page",
                    "best_company_url": "https://test.co/ap",
                },
                {
                    "query_id": "tq_2",
                    "query_text": "How to reduce AP time?",
                    "cluster_name": "Problem/Awareness",
                    "gap": 0.15,
                    "top_cited_exemplars": [
                        {"url": "https://b.com", "similarity": 0.7},
                    ],
                },
            ],
            "cluster_specs": [
                {"cluster_name": "Definition", "avg_word_count": 1500},
                {"cluster_name": "Problem/Awareness", "avg_word_count": 1200},
            ],
        }
        topic_query_map = {"ta-1": ["tq_1", "tq_2"]}

        result = extract_topic_contexts(analysis_json, topic_query_map)

        # Keyed by first query_id
        assert "tq_1" in result
        ctx = result["tq_1"]
        assert isinstance(ctx, WorkerQueryContext)
        # Should use highest-gap query as primary
        assert ctx.query_gap["query_id"] == "tq_1"
        assert ctx.query_gap["gap"] == 0.25
        # Exemplars aggregated from both queries (deduped by URL)
        assert len(ctx.exemplars) == 2
        assert ctx.company_best_text == "Our AP page"
        assert ctx.company_best_url == "https://test.co/ap"

    def test_multi_topic_extraction(self):
        analysis_json = {
            "gaps": [
                {"query_id": "tq_1", "query_text": "Q1", "cluster_name": "C5",
                 "gap": 0.2, "top_cited_exemplars": []},
                {"query_id": "tq_2", "query_text": "Q2", "cluster_name": "C7",
                 "gap": 0.3, "top_cited_exemplars": []},
            ],
            "cluster_specs": [],
        }
        topic_query_map = {
            "ta-1": ["tq_1"],
            "ta-2": ["tq_2"],
        }

        result = extract_topic_contexts(analysis_json, topic_query_map)

        assert len(result) == 2
        assert "tq_1" in result
        assert "tq_2" in result

    def test_empty_topic_query_map(self):
        result = extract_topic_contexts({"gaps": [], "cluster_specs": []}, {})
        assert result == {}

    def test_deduplicates_exemplars_by_url(self):
        analysis_json = {
            "gaps": [
                {"query_id": "tq_1", "cluster_name": "C5", "gap": 0.3,
                 "top_cited_exemplars": [
                     {"url": "https://same.com", "similarity": 0.8},
                 ]},
                {"query_id": "tq_2", "cluster_name": "C6", "gap": 0.1,
                 "top_cited_exemplars": [
                     {"url": "https://same.com", "similarity": 0.7},
                     {"url": "https://other.com", "similarity": 0.6},
                 ]},
            ],
            "cluster_specs": [],
        }
        topic_query_map = {"ta-1": ["tq_1", "tq_2"]}

        result = extract_topic_contexts(analysis_json, topic_query_map)
        ctx = result["tq_1"]
        # https://same.com appears in both queries but only once in exemplars
        urls = [ex.get("url") for ex in ctx.exemplars]
        assert urls.count("https://same.com") == 1
        assert "https://other.com" in urls

    def test_caps_exemplars_at_5(self):
        exemplars = [{"url": f"https://ex{i}.com", "similarity": 0.5}
                     for i in range(10)]
        analysis_json = {
            "gaps": [
                {"query_id": "tq_1", "cluster_name": "C5", "gap": 0.2,
                 "top_cited_exemplars": exemplars},
            ],
            "cluster_specs": [],
        }
        topic_query_map = {"ta-1": ["tq_1"]}

        result = extract_topic_contexts(analysis_json, topic_query_map)
        assert len(result["tq_1"].exemplars) <= 5


# ---------------------------------------------------------------------------
# topic_assignment_to_selection
# ---------------------------------------------------------------------------


class TestTopicAssignmentToSelection:
    def test_basic_conversion(self):
        assignment = _make_assignment(
            buyer_stage=BuyerStage.BOFU,
            intent_type=IntentType.commercial,
        )
        query_ids = ["tq_1", "tq_2"]
        query_texts = ["Q1 text", "Q2 text"]

        sel = topic_assignment_to_selection(assignment, query_ids, query_texts, rank=0)

        assert isinstance(sel, TopicSelection)
        assert sel.rank == 0
        assert sel.query_ids == ["tq_1", "tq_2"]
        assert sel.query_texts == ["Q1 text", "Q2 text"]
        assert sel.estimated_impact == "high"  # BOFU → high
        assert "AP Automation" in sel.rationale
        assert assignment.topic_text in sel.consolidation_note

    def test_tofu_impact(self):
        assignment = _make_assignment(buyer_stage=BuyerStage.TOFU)
        sel = topic_assignment_to_selection(assignment, ["q1"], ["t1"])
        assert sel.estimated_impact == "medium"

    def test_mofu_impact(self):
        assignment = _make_assignment(buyer_stage=BuyerStage.MOFU)
        sel = topic_assignment_to_selection(assignment, ["q1"], ["t1"])
        assert sel.estimated_impact == "medium"

    def test_empty_queries(self):
        assignment = _make_assignment()
        sel = topic_assignment_to_selection(assignment, [], [])
        assert sel.query_ids == []
        assert sel.query_texts == []

    def test_priority_in_rationale(self):
        assignment = _make_assignment()
        assignment.priority_score = 0.92
        sel = topic_assignment_to_selection(assignment, ["q1"], ["t1"])
        assert "0.92" in sel.rationale

    def test_cluster_name_derived_from_mapping(self):
        """L2 fix: cluster_name should be derived, not hardcoded empty."""
        assignment = _make_assignment(
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.informational,
        )
        sel = topic_assignment_to_selection(assignment, ["q1"], ["t1"])
        # TOFU × informational → primary C5 → "Definition"
        assert sel.cluster_name == "Definition"

    def test_cluster_name_bofu_commercial(self):
        """L2 fix: BOFU × commercial → primary C8 → 'Branded Evaluation'."""
        assignment = _make_assignment(
            buyer_stage=BuyerStage.BOFU,
            intent_type=IntentType.commercial,
        )
        sel = topic_assignment_to_selection(assignment, ["q1"], ["t1"])
        assert sel.cluster_name == "Branded Evaluation"

    def test_cluster_name_empty_for_excluded_combo(self):
        """L2 fix: excluded combos should still return empty cluster_name."""
        assignment = _make_assignment(
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.transactional,
        )
        sel = topic_assignment_to_selection(assignment, [], [])
        assert sel.cluster_name == ""
