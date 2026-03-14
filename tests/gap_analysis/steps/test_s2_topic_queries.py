"""Tests for topic-scoped query generation (TD → GA bridge).

Covers:
  - _build_topic_prompt: prompt structure, cluster instructions, brand rules
  - _build_cluster_instructions: primary/secondary formatting
  - _build_brand_rules: conditional C8/C2 rules
  - _deduplicate_queries_cross_topic: global dedup with source_topic_ids merge
  - generate_queries_from_topics: end-to-end with mocked LLM + embeddings
  - Excluded combo handling
"""
from __future__ import annotations

import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.gap_analysis import GeneratedQuery
from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
)


def _make_topic(
    topic_id: str = "ta-1",
    subdomain_name: str = "AP Automation",
    topic_text: str = "How AP Automation Reduces Invoice Processing Time",
    buyer_stage: BuyerStage = BuyerStage.TOFU,
    intent_type: IntentType = IntentType.informational,
    audience_segment: str = "AP Manager",
    persona_id: str = "p-1",
    persona_name: str = "AP Manager Persona",
) -> TopicAssignment:
    return TopicAssignment(
        id=topic_id,
        subdomain_id="sd-1",
        subdomain_name=subdomain_name,
        topic_text=topic_text,
        buyer_stage=buyer_stage,
        intent_type=intent_type,
        audience_segment=audience_segment,
        persona_id=persona_id,
        persona_name=persona_name,
    )


# ---------------------------------------------------------------------------
# Prompt Building
# ---------------------------------------------------------------------------


class TestBuildClusterInstructions:
    def test_primary_and_secondary(self):
        from core.gap_analysis.steps.s2_generate_queries import (
            _build_cluster_instructions,
        )

        result = _build_cluster_instructions(
            primary=("C5", "C6"), secondary=("C1",)
        )
        assert "PRIMARY: C5" in result
        assert "PRIMARY: C6" in result
        assert "SECONDARY: C1" in result
        assert "Definition" in result
        assert "Problem/Awareness" in result
        assert "Mechanism" in result

    def test_no_secondary(self):
        from core.gap_analysis.steps.s2_generate_queries import (
            _build_cluster_instructions,
        )

        result = _build_cluster_instructions(primary=("C9", "C8"), secondary=())
        assert "PRIMARY: C9" in result
        assert "PRIMARY: C8" in result
        assert "SECONDARY" not in result


class TestBuildBrandRules:
    def test_no_c8_no_c2(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_brand_rules

        result = _build_brand_rules(primary=("C5", "C6"), secondary=("C1",))
        assert "Brand" in result
        assert "C8" not in result
        assert "C2" not in result

    def test_with_c8(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_brand_rules

        result = _build_brand_rules(primary=("C8", "C4"), secondary=("C3",))
        assert "C8" in result
        assert "REQUIRED" in result

    def test_with_c2(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_brand_rules

        result = _build_brand_rules(primary=("C1", "C2"), secondary=("C4",))
        assert "C2" in result
        assert "limitation" in result.lower()

    def test_with_c8_and_c2(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_brand_rules

        result = _build_brand_rules(primary=("C8",), secondary=("C2",))
        assert "C8" in result
        assert "C2" in result


class TestBuildTopicPrompt:
    def test_prompt_contains_topic_fields(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_topic_prompt

        topic = _make_topic()
        prompt = _build_topic_prompt(
            topic=topic,
            primary=("C5", "C6"),
            secondary=("C1",),
            queries_range=(5, 8),
            company_context="Test company context",
            persona_context="Test persona context",
            company_name="Test Co",
            company_domain="test.co",
        )
        assert "AP Automation" in prompt
        assert "AP Manager" in prompt
        assert "tofu" in prompt
        assert "informational" in prompt
        assert "Test Co" in prompt
        assert "5" in prompt  # min_queries
        assert "8" in prompt  # max_queries

    def test_prompt_contains_cluster_instructions(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_topic_prompt

        topic = _make_topic()
        prompt = _build_topic_prompt(
            topic=topic,
            primary=("C5", "C6"),
            secondary=("C1",),
            queries_range=(5, 8),
            company_context="",
            persona_context="",
            company_name="Test Co",
            company_domain=None,
        )
        assert "PRIMARY: C5" in prompt
        assert "SECONDARY: C1" in prompt

    def test_prompt_with_product_context(self):
        from core.gap_analysis.steps.s2_generate_queries import _build_topic_prompt

        topic = _make_topic()
        product_block = "PRODUCT: Ramp Corporate Card"
        prompt = _build_topic_prompt(
            topic=topic,
            primary=("C5",),
            secondary=(),
            queries_range=(3, 5),
            company_context="",
            persona_context="",
            company_name="Ramp",
            company_domain="ramp.com",
            product_context=product_block,
        )
        assert "Ramp Corporate Card" in prompt


# ---------------------------------------------------------------------------
# Cross-Topic Dedup
# ---------------------------------------------------------------------------


class TestDeduplicateQueriesCrossTopic:
    @pytest.mark.asyncio
    async def test_is_async(self):
        from core.gap_analysis.steps.s2_generate_queries import (
            _deduplicate_queries_cross_topic,
        )

        assert inspect.iscoroutinefunction(_deduplicate_queries_cross_topic)

    @pytest.mark.asyncio
    async def test_keeps_dissimilar_queries(self):
        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP automation?",
                source_topic_ids=["t1"],
            ),
            GeneratedQuery(
                query_id="tq_2", cluster_id="C7", cluster_name="Best-of",
                query_text="Best corporate card for startups?",
                source_topic_ids=["t2"],
            ),
        ]
        # Orthogonal embeddings → dissimilar
        mock_embs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embs,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                _deduplicate_queries_cross_topic,
            )

            result = await _deduplicate_queries_cross_topic(queries, threshold=0.85)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_merges_source_topic_ids_on_dedup(self):
        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP automation?",
                source_topic_ids=["t1"],
            ),
            GeneratedQuery(
                query_id="tq_2", cluster_id="C5", cluster_name="Definition",
                query_text="What is accounts payable automation?",
                source_topic_ids=["t2"],
            ),
        ]
        # Near-identical embeddings → dedup
        mock_embs = [[1.0, 0.0, 0.0], [0.99, 0.01, 0.0]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embs,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                _deduplicate_queries_cross_topic,
            )

            result = await _deduplicate_queries_cross_topic(queries, threshold=0.85)

        assert len(result) == 1
        # Surviving query should have both topic IDs
        assert "t1" in result[0].source_topic_ids
        assert "t2" in result[0].source_topic_ids

    @pytest.mark.asyncio
    async def test_empty_input(self):
        with patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                _deduplicate_queries_cross_topic,
            )

            result = await _deduplicate_queries_cross_topic([], threshold=0.85)

        assert result == []

    @pytest.mark.asyncio
    async def test_no_duplicate_topic_ids_after_merge(self):
        """If same topic_id already exists, don't add it again."""
        queries = [
            GeneratedQuery(
                query_id="tq_1", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?",
                source_topic_ids=["t1", "t2"],
            ),
            GeneratedQuery(
                query_id="tq_2", cluster_id="C5", cluster_name="Definition",
                query_text="What is AP?",  # exact same
                source_topic_ids=["t2", "t3"],
            ),
        ]
        mock_embs = [[1.0, 0.0], [1.0, 0.0]]  # identical

        with patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embs,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                _deduplicate_queries_cross_topic,
            )

            result = await _deduplicate_queries_cross_topic(queries, threshold=0.85)

        assert len(result) == 1
        # t2 appears in both but should only be in the list once
        assert sorted(result[0].source_topic_ids) == ["t1", "t2", "t3"]


# ---------------------------------------------------------------------------
# generate_queries_from_topics (end-to-end with mocks)
# ---------------------------------------------------------------------------


class TestGenerateQueriesFromTopics:
    @pytest.mark.asyncio
    async def test_is_async(self):
        from core.gap_analysis.steps.s2_generate_queries import (
            generate_queries_from_topics,
        )

        assert inspect.iscoroutinefunction(generate_queries_from_topics)

    @pytest.mark.asyncio
    async def test_empty_topics_returns_empty(self):
        from core.gap_analysis.steps.s2_generate_queries import (
            generate_queries_from_topics,
        )

        result = await generate_queries_from_topics(
            topics=[], company_name="Test Co",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_excluded_combo_skipped(self):
        """TOFU × transactional should produce no queries."""
        topic = _make_topic(
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.transactional,
        )

        from core.gap_analysis.steps.s2_generate_queries import (
            generate_queries_from_topics,
        )

        # No LLM call should happen — function returns empty
        result = await generate_queries_from_topics(
            topics=[topic], company_name="Test Co",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_single_topic_generates_queries(self):
        topic = _make_topic(
            topic_id="ta-1",
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.informational,
        )

        llm_response = json.dumps({
            "queries": [
                {
                    "cluster_id": "C5",
                    "cluster_name": "Definition",
                    "query_text": "What is AP automation?",
                    "buyer_stage": "tofu",
                    "persona_tag": "AP Manager",
                },
                {
                    "cluster_id": "C6",
                    "cluster_name": "Problem/Awareness",
                    "query_text": "How can I reduce invoice processing time?",
                    "buyer_stage": "tofu",
                    "persona_tag": "AP Manager",
                },
            ]
        })

        mock_embs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            new_callable=AsyncMock,
            return_value=llm_response,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embs,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                generate_queries_from_topics,
            )

            result = await generate_queries_from_topics(
                topics=[topic],
                company_name="Test Co",
                company_domain="test.co",
            )

        assert len(result) == 2
        # All queries should have source_topic_ids
        for q in result:
            assert "ta-1" in q.source_topic_ids
        # Query IDs should be sequential with tq_ prefix
        assert result[0].query_id == "tq_1"
        assert result[1].query_id == "tq_2"

    @pytest.mark.asyncio
    async def test_multiple_topics_with_dedup(self):
        topic1 = _make_topic(
            topic_id="ta-1",
            subdomain_name="AP Automation",
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.informational,
        )
        topic2 = _make_topic(
            topic_id="ta-2",
            subdomain_name="AP Workflow",
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.informational,
        )

        # Both topics generate similar queries
        call_count = 0

        async def mock_llm(prompt, model):
            nonlocal call_count
            call_count += 1
            return json.dumps({
                "queries": [
                    {
                        "cluster_id": "C5",
                        "cluster_name": "Definition",
                        "query_text": f"What is AP automation? variant {call_count}",
                    },
                ]
            })

        # Make embeddings similar enough for dedup
        mock_embs = [[1.0, 0.0], [0.99, 0.01]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            side_effect=mock_llm,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embs,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                generate_queries_from_topics,
            )

            result = await generate_queries_from_topics(
                topics=[topic1, topic2],
                company_name="Test Co",
            )

        # Dedup should merge the two similar queries
        assert len(result) == 1
        assert "ta-1" in result[0].source_topic_ids
        assert "ta-2" in result[0].source_topic_ids

    @pytest.mark.asyncio
    async def test_llm_failure_continues_with_other_topics(self):
        topic1 = _make_topic(
            topic_id="ta-1",
            buyer_stage=BuyerStage.TOFU,
            intent_type=IntentType.informational,
        )
        topic2 = _make_topic(
            topic_id="ta-2",
            buyer_stage=BuyerStage.MOFU,
            intent_type=IntentType.commercial,
        )

        call_count = 0

        async def mock_llm(prompt, model):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("LLM down")
            return json.dumps({
                "queries": [
                    {
                        "cluster_id": "C3",
                        "cluster_name": "Category Comparison",
                        "query_text": "AP automation vs manual processing",
                    },
                ]
            })

        mock_embs = [[1.0, 0.0]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            side_effect=mock_llm,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embs,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                generate_queries_from_topics,
            )

            result = await generate_queries_from_topics(
                topics=[topic1, topic2],
                company_name="Test Co",
            )

        # First topic failed, second succeeded
        assert len(result) == 1
        assert "ta-2" in result[0].source_topic_ids

    @pytest.mark.asyncio
    async def test_product_context_passed_through(self):
        topic = _make_topic(
            buyer_stage=BuyerStage.BOFU,
            intent_type=IntentType.commercial,
        )

        captured_prompts = []

        async def capture_llm(prompt, model):
            captured_prompts.append(prompt)
            return json.dumps({"queries": []})

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            side_effect=capture_llm,
        ):
            from core.gap_analysis.steps.s2_generate_queries import (
                generate_queries_from_topics,
            )

            await generate_queries_from_topics(
                topics=[topic],
                company_name="Ramp",
                company_domain="ramp.com",
                product_name="Ramp Corporate Card",
                product_slug="ramp-corporate-card",
                product_description="Corporate cards for startups",
            )

        assert len(captured_prompts) == 1
        assert "Ramp Corporate Card" in captured_prompts[0]
