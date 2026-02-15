"""Tests for s5_embed_content async conversion — TDD: written BEFORE implementation.

Focused on async behavior of embed_queries, embed_enriched_citations, and embed_all.
"""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncEmbedQueries:
    """Tests for async embed_queries."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """embed_queries should be an async function."""
        from core.gap_analysis.steps.s5_embed_content import embed_queries
        assert inspect.iscoroutinefunction(embed_queries)

    @pytest.mark.asyncio
    async def test_uses_async_embed_texts(self):
        """Should use async_embed_texts for embedding."""
        from core.models.gap_analysis import GeneratedQuery

        queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does expense management work?",
            ),
        ]

        with patch(
            "core.gap_analysis.steps.s5_embed_content.async_embed_texts",
            new_callable=AsyncMock,
            return_value=[[0.1, 0.2, 0.3]],
        ) as mock_embed:
            from core.gap_analysis.steps.s5_embed_content import embed_queries
            result = await embed_queries(queries)

        mock_embed.assert_awaited_once()
        assert result[0].embedding == [0.1, 0.2, 0.3]


class TestAsyncEmbedEnrichedCitations:
    """Tests for async embed_enriched_citations."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """embed_enriched_citations should be an async function."""
        from core.gap_analysis.steps.s5_embed_content import embed_enriched_citations
        assert inspect.iscoroutinefunction(embed_enriched_citations)

    @pytest.mark.asyncio
    async def test_uses_async_embed_and_upsert(self):
        """Should use async_embed_texts and async_upsert_citation_embeddings."""
        from core.models.gap_analysis import EnrichedCitation, StructuralSignals

        citations = [
            EnrichedCitation(
                url="https://example.com/page1",
                domain="example.com",
                title="Test Page",
                query_id="q_1",
                engine="openai",
                anchor_text="test anchor text that is long enough",
                paragraphs=["A" * 60],
                best_paragraphs=[],
                structural_signals=StructuralSignals(),
            ),
        ]

        # Two texts: paragraph + anchor
        mock_embeddings = [[0.1, 0.2], [0.3, 0.4]]

        with patch(
            "core.gap_analysis.steps.s5_embed_content.async_embed_texts",
            new_callable=AsyncMock,
            return_value=mock_embeddings,
        ) as mock_embed, patch(
            "core.gap_analysis.steps.s5_embed_content.async_upsert_citation_embeddings",
            new_callable=AsyncMock,
        ) as mock_upsert:
            from core.gap_analysis.steps.s5_embed_content import embed_enriched_citations
            result = await embed_enriched_citations(
                citations, company_slug="test-co",
            )

        mock_embed.assert_awaited_once()
        # Upsert should be called if there are embeddings
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_citations(self):
        """Should handle empty citation list."""
        from core.gap_analysis.steps.s5_embed_content import embed_enriched_citations
        result = await embed_enriched_citations([])
        assert result == []


class TestAsyncEmbedAll:
    """Tests for async embed_all."""

    @pytest.mark.asyncio
    async def test_is_async_coroutine(self):
        """embed_all should be an async function."""
        from core.gap_analysis.steps.s5_embed_content import embed_all
        assert inspect.iscoroutinefunction(embed_all)

    @pytest.mark.asyncio
    async def test_calls_both_embed_functions(self):
        """Should call embed_queries and embed_enriched_citations."""
        from core.models.gap_analysis import GeneratedQuery, EnrichedCitation, StructuralSignals

        queries = [
            GeneratedQuery(
                query_id="q_1", cluster_id="C1", cluster_name="Mechanism",
                query_text="How does it work?",
            ),
        ]
        citations = [
            EnrichedCitation(
                url="https://example.com",
                domain="example.com",
                title="Test",
                query_id="q_1",
                engine="openai",
                anchor_text="anchor text",
                paragraphs=[],
                best_paragraphs=[],
                structural_signals=StructuralSignals(),
            ),
        ]

        with patch(
            "core.gap_analysis.steps.s5_embed_content.embed_queries",
            new_callable=AsyncMock,
            return_value=queries,
        ) as mock_eq, patch(
            "core.gap_analysis.steps.s5_embed_content.embed_enriched_citations",
            new_callable=AsyncMock,
            return_value=citations,
        ) as mock_ec:
            from core.gap_analysis.steps.s5_embed_content import embed_all
            q_result, c_result = await embed_all(queries, citations, company_slug="test")

        mock_eq.assert_awaited_once()
        mock_ec.assert_awaited_once()
        assert q_result == queries
        assert c_result == citations
