"""Tests for s2_generate_queries async conversion — TDD: written BEFORE implementation.

Focused on async behavior of _call_openai, _deduplicate_queries, and generate_queries.
"""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncCallOpenAI:
    """Tests for async _call_openai."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """_call_openai should be an async function."""
        from core.gap_analysis.steps.s2_generate_queries import _call_openai
        assert inspect.iscoroutinefunction(_call_openai)

    @pytest.mark.asyncio
    async def test_returns_text_and_usage_tuple(self):
        """Should return (text, (prompt_tokens, completion_tokens)) tuple."""
        mock_response = MagicMock()
        mock_response.output_text = "test response text"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client_instance = AsyncMock()
        mock_client_instance.responses.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.gap_analysis.steps.s2_generate_queries.AsyncOpenAI",
            return_value=mock_client_instance,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            from core.gap_analysis.steps.s2_generate_queries import _call_openai
            text, usage = await _call_openai("test prompt", "gpt-4o")

        assert text == "test response text"
        assert usage == (100, 50)

    @pytest.mark.asyncio
    async def test_workspace_context_uses_byok_agent_wrapper(self):
        """Workspace-backed query generation uses the BYOK agent wrapper."""
        from core.models.content_generation_v13 import LLMResponse
        from core.gap_analysis.steps.s2_generate_queries import _call_openai

        response = LLMResponse(
            content='{"queries": []}',
            model="openai/gpt-5.2",
            input_tokens=12,
            output_tokens=7,
            total_tokens=19,
        )

        with (
            patch(
                "core.content_engine.llm_client.llm_call_for_agent",
                new_callable=AsyncMock,
                return_value=response,
            ) as mock_call,
            patch("core.gap_analysis.steps.s2_generate_queries.AsyncOpenAI") as mock_native,
        ):
            text, usage = await _call_openai(
                "prompt",
                "gpt-5.2",
                workspace_id="ws-123",
                workspace_slug="ramp",
                company_slug="ramp",
                pipeline_step="s2_query_gen_seed",
            )

        assert text == '{"queries": []}'
        assert usage == (12, 7)
        mock_native.assert_not_called()
        mock_call.assert_awaited_once()
        kwargs = mock_call.call_args.kwargs
        assert kwargs["workspace_id"] == "ws-123"
        assert kwargs["workspace_slug"] == "ramp"
        assert kwargs["agent_key"] == "gap.query_generation"
        assert kwargs["metadata"]["pipeline_step"] == "s2_query_gen_seed"
        assert kwargs["metadata"]["company_slug"] == "ramp"


class TestAsyncDeduplicateQueries:
    """Tests for async _deduplicate_queries."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """_deduplicate_queries should be an async function."""
        from core.gap_analysis.steps.s2_generate_queries import _deduplicate_queries
        assert inspect.iscoroutinefunction(_deduplicate_queries)

    @pytest.mark.asyncio
    async def test_uses_async_embed_texts(self):
        """Should use async_embed_texts for dedup embedding."""
        from core.models.gap_analysis import GeneratedQuery

        queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does expense management work?",
            ),
            GeneratedQuery(
                query_id="q_2", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does spend tracking work?",
            ),
        ]

        # Return dissimilar embeddings so both survive dedup
        mock_embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embeddings,
        ) as mock_embed:
            from core.gap_analysis.steps.s2_generate_queries import _deduplicate_queries
            result = await _deduplicate_queries(queries)

        mock_embed.assert_awaited_once()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_removes_duplicate_queries(self):
        """Should remove queries with cosine similarity >= threshold."""
        from core.models.gap_analysis import GeneratedQuery

        queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="Query A",
            ),
            GeneratedQuery(
                query_id="q_2", cluster_id="C1", cluster_name="Mechanism",
                query_text="Query B (nearly identical)",
            ),
        ]

        # Return nearly identical embeddings so second gets deduped
        mock_embeddings = [[1.0, 0.0, 0.0], [0.999, 0.01, 0.0]]

        with patch(
            "core.gap_analysis.steps.s2_generate_queries.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embeddings,
        ):
            from core.gap_analysis.steps.s2_generate_queries import _deduplicate_queries
            result = await _deduplicate_queries(queries, threshold=0.85)

        assert len(result) == 1
        assert result[0].query_id == "q_1"

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Should return empty list for empty input."""
        from core.gap_analysis.steps.s2_generate_queries import _deduplicate_queries
        result = await _deduplicate_queries([])
        assert result == []


class TestAsyncValidateCoverage:
    """Tests for async _validate_coverage."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """_validate_coverage should be an async function."""
        from core.gap_analysis.steps.s2_generate_queries import _validate_coverage
        assert inspect.iscoroutinefunction(_validate_coverage)


class TestAsyncGenerateQueries:
    """Tests for async generate_queries."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """generate_queries should be an async function."""
        from core.gap_analysis.steps.s2_generate_queries import generate_queries
        assert inspect.iscoroutinefunction(generate_queries)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(self):
        """Should run through seed gen, dedup, and coverage validation."""
        from core.models.gap_analysis import GapAnalysisInput, QueryCluster

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            seed_urls=["https://test.com"],
            platforms=["perplexity"],
            max_queries=10,
        )

        mock_clusters = [
            QueryCluster(
                cluster_id="C1", cluster_name="Mechanism",
                intent="How does X work?", buyer_stage="Consideration",
            ),
        ]

        mock_llm_response = '{"queries": [{"cluster_id": "C1", "cluster_name": "Mechanism", "query_text": "How does expense management work?", "buyer_stage": "Consideration", "persona_tag": "icp"}]}'

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._load_taxonomy",
            return_value=mock_clusters,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            new_callable=AsyncMock,
            return_value=(mock_llm_response, (100, 50)),
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._deduplicate_queries",
            new_callable=AsyncMock,
            side_effect=lambda q, **kw: q,  # pass through
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._validate_coverage",
            new_callable=AsyncMock,
            side_effect=lambda queries, **kw: queries,  # pass through
        ):
            from core.gap_analysis.steps.s2_generate_queries import generate_queries
            result = await generate_queries(input_data)

        assert len(result) >= 1
        assert result[0].query_text == "How does expense management work?"
        assert result[0].query_id == "q_1"

    @pytest.mark.asyncio
    async def test_generate_queries_passes_workspace_context_to_llm(self):
        """generate_queries should forward workspace context into the S2 LLM helper."""
        from core.models.gap_analysis import GapAnalysisInput, QueryCluster

        input_data = GapAnalysisInput(
            company_name="Test Co",
            domain="test.com",
            company_slug="test-co",
            workspace_id="ws-123",
            workspace_slug="test-co",
            seed_urls=["https://test.com"],
            platforms=["perplexity"],
            max_queries=10,
        )
        mock_clusters = [
            QueryCluster(
                cluster_id="C1", cluster_name="Mechanism",
                intent="How does X work?", buyer_stage="Consideration",
            ),
        ]
        mock_llm_response = '{"queries": [{"cluster_id": "C1", "cluster_name": "Mechanism", "query_text": "How does expense management work?", "buyer_stage": "Consideration", "persona_tag": "icp"}]}'

        with patch(
            "core.gap_analysis.steps.s2_generate_queries._load_taxonomy",
            return_value=mock_clusters,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._call_openai",
            new_callable=AsyncMock,
            return_value=(mock_llm_response, (100, 50)),
        ) as mock_call, patch(
            "core.gap_analysis.steps.s2_generate_queries._deduplicate_queries",
            new_callable=AsyncMock,
            side_effect=lambda q, **kw: q,
        ), patch(
            "core.gap_analysis.steps.s2_generate_queries._validate_coverage",
            new_callable=AsyncMock,
            side_effect=lambda queries, **kw: queries,
        ):
            from core.gap_analysis.steps.s2_generate_queries import generate_queries
            result = await generate_queries(input_data)

        assert len(result) == 1
        kwargs = mock_call.await_args.kwargs
        assert kwargs["workspace_id"] == "ws-123"
        assert kwargs["workspace_slug"] == "test-co"
        assert kwargs["company_slug"] == "test-co"
        assert kwargs["pipeline_step"] == "s2_query_gen_seed"
