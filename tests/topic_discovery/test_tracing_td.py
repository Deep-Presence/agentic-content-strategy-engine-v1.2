"""Tests for LangSmith tracing integration in Topic Discovery pipeline.

Verifies that tracing functions (create_span, log_generation, log_score,
end_span) are called correctly throughout agents, pipeline, and HITL graph.

Since LANGSMITH_API_KEY is not set in tests, all tracing functions return
None (graceful degradation). These tests mock the tracing functions to
verify call patterns.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.topic_discovery import (
    SourceResult,
    SubdomainCandidate,
    TDSource,
)


# ---------------------------------------------------------------------------
# Helper: mock LiteLLM response
# ---------------------------------------------------------------------------

def _mock_litellm_response(content: str = '{"subdomains": []}') -> MagicMock:
    """Create a mock LiteLLM response with usage data."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    return response


# ═══════════════════════════════════════════════════════════════════════
# Agent-level tracing tests
# ═══════════════════════════════════════════════════════════════════════


class TestSourceATracing:
    """Verify Source A agent creates spans, logs generations and scores."""

    @pytest.mark.asyncio
    async def test_source_a_logs_per_round_generations(self):
        mock_response = _mock_litellm_response(
            '{"subdomains": [{"name": "test", "description": "d", "confidence": 0.8}]}'
        )

        with (
            patch("core.topic_discovery.agents._run_completion",
                  return_value=(mock_response, mock_response.choices[0].message.content)),
            patch("core.topic_discovery.agents.create_span") as mock_create_span,
            patch("core.topic_discovery.agents.end_span") as mock_end_span,
            patch("core.topic_discovery.agents.log_generation") as mock_log_gen,
            patch("core.topic_discovery.agents.log_score") as mock_log_score,
        ):
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span
            parent = MagicMock()

            from core.topic_discovery.agents import run_source_a_company_brainstorm

            result = await run_source_a_company_brainstorm(
                "Test company context",
                max_rounds=2,
                parent_span=parent,
            )

            # Span created under parent
            mock_create_span.assert_called_once()
            assert mock_create_span.call_args[0][0] is parent
            assert mock_create_span.call_args[0][1] == "td-source-a"

            # log_generation called per round
            assert mock_log_gen.call_count == 2
            for i, call in enumerate(mock_log_gen.call_args_list):
                assert call[0][0] is mock_span  # parent is the span
                assert call[0][1] == f"round-{i + 1}"  # name

            # log_score called for metrics
            score_names = [c[0][1] for c in mock_log_score.call_args_list]
            assert "chao1_estimate" in score_names
            assert "sample_coverage" in score_names
            assert "candidate_count" in score_names

            # Span ended with output
            mock_end_span.assert_called_once()
            assert "candidates" in mock_end_span.call_args[1].get("output", {})

    @pytest.mark.asyncio
    async def test_source_a_error_ends_span_with_error(self):
        with (
            patch("core.topic_discovery.agents._run_completion",
                  side_effect=RuntimeError("LLM failed")),
            patch("core.topic_discovery.agents.create_span") as mock_create_span,
            patch("core.topic_discovery.agents.end_span") as mock_end_span,
            patch("core.topic_discovery.agents.log_generation"),
            patch("core.topic_discovery.agents.log_score"),
        ):
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span
            parent = MagicMock()

            from core.topic_discovery.agents import run_source_a_company_brainstorm

            result = await run_source_a_company_brainstorm(
                "Test company", max_rounds=1, parent_span=parent,
            )

            assert result.error is not None
            mock_end_span.assert_called_once()
            assert mock_end_span.call_args[1].get("error") is not None


class TestSourceCTracing:
    """Source C (Perplexity) must use manual log_generation."""

    @pytest.mark.asyncio
    async def test_source_c_logs_manual_generation(self):
        mock_ppx = MagicMock()
        mock_ppx.research.return_value = ('{"subdomains": []}', {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

        with (
            patch("core.research.tools.perplexity_client", mock_ppx),
            patch("core.topic_discovery.agents.create_span") as mock_create_span,
            patch("core.topic_discovery.agents.end_span"),
            patch("core.topic_discovery.agents.log_generation") as mock_log_gen,
            patch("core.topic_discovery.agents.log_score"),
        ):
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span

            from core.topic_discovery.agents import run_source_c_deep_research

            await run_source_c_deep_research(
                "company ctx", "competitor data", "example.com",
                parent_span=MagicMock(),
            )

            # Manual log_generation called (not via LiteLLM callback)
            mock_log_gen.assert_called_once()
            assert mock_log_gen.call_args[0][1] == "deep-research"


class TestDedupTracing:
    """Verify dedup agent logs scores."""

    @pytest.mark.asyncio
    async def test_dedup_logs_ratio_and_kept(self):
        candidates = [
            SubdomainCandidate(name="Topic A", description="d", source=TDSource.source_a),
            SubdomainCandidate(name="Topic B", description="d", source=TDSource.source_b),
        ]

        with (
            patch("core.shared_tools.embedding_client.embed_texts",
                  return_value=[[1.0, 0.0], [0.0, 1.0]]),
            patch("core.topic_discovery.agents.create_span") as mock_create_span,
            patch("core.topic_discovery.agents.end_span") as mock_end_span,
            patch("core.topic_discovery.agents.log_score") as mock_log_score,
        ):
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span

            from core.topic_discovery.agents import deduplicate_subdomains_with_clusters

            result = await deduplicate_subdomains_with_clusters(
                candidates, threshold=0.85, parent_span=MagicMock(),
            )

            assert len(result.kept) == 2  # no duplicates
            score_names = [c[0][1] for c in mock_log_score.call_args_list]
            assert "dedup_ratio" in score_names
            assert "total_kept" in score_names


class TestSubdomainExpansionTracing:
    """Verify expansion agent creates span and logs generation."""

    @pytest.mark.asyncio
    async def test_expansion_logs_generation_and_score(self):
        mock_response = _mock_litellm_response(
            '{"topics": [{"title": "Test Topic", "buyer_stage": "tofu", "intent_type": "informational", "persona_id": "", "persona_name": ""}]}'
        )

        with (
            patch("core.topic_discovery.agents._run_completion",
                  return_value=(mock_response, mock_response.choices[0].message.content)),
            patch("core.topic_discovery.agents.create_span") as mock_create_span,
            patch("core.topic_discovery.agents.end_span") as mock_end_span,
            patch("core.topic_discovery.agents.log_generation") as mock_log_gen,
            patch("core.topic_discovery.agents.log_score") as mock_log_score,
        ):
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span

            from core.topic_discovery.agents import run_subdomain_expansion

            result = await run_subdomain_expansion(
                "Test Subdomain", "Description",
                ["tofu", "mofu"], ["informational"],
                [("p1", "Persona 1")],
                "company context",
                parent_span=MagicMock(),
            )

            assert len(result) == 1
            mock_log_gen.assert_called_once()
            assert mock_log_gen.call_args[0][1] == "expansion"

            score_names = [c[0][1] for c in mock_log_score.call_args_list]
            assert "assignments_count" in score_names


# ═══════════════════════════════════════════════════════════════════════
# Graceful None propagation
# ═══════════════════════════════════════════════════════════════════════


class TestGracefulNonePropagation:
    """Agents work with parent_span=None (tracing disabled)."""

    @pytest.mark.asyncio
    async def test_source_a_with_none_parent_span(self):
        mock_response = _mock_litellm_response('{"subdomains": []}')

        with patch("core.topic_discovery.agents._run_completion",
                   return_value=(mock_response, mock_response.choices[0].message.content)):
            from core.topic_discovery.agents import run_source_a_company_brainstorm

            result = await run_source_a_company_brainstorm(
                "ctx", max_rounds=1, parent_span=None,
            )
            assert isinstance(result, SourceResult)
            assert result.error is None

    @pytest.mark.asyncio
    async def test_dedup_with_none_parent_span(self):
        candidates = [
            SubdomainCandidate(name="A", description="d", source=TDSource.source_a),
        ]
        with patch("core.shared_tools.embedding_client.embed_texts",
                   return_value=[[1.0, 0.0]]):
            from core.topic_discovery.agents import deduplicate_subdomains_with_clusters

            result = await deduplicate_subdomains_with_clusters(
                candidates, parent_span=None,
            )
            assert len(result.kept) == 1


# ═══════════════════════════════════════════════════════════════════════
# HITL gate tracing
# ═══════════════════════════════════════════════════════════════════════


class TestHITLGateTracing:
    """Verify HITL graph gates create spans and log decisions."""

    def test_taxonomy_gate_auto_approve_traces(self):
        with (
            patch("core.topic_discovery.graph.get_current_span") as mock_get_span,
            patch("core.topic_discovery.graph.create_span") as mock_create_span,
            patch("core.topic_discovery.graph.end_span") as mock_end_span,
            patch("core.topic_discovery.graph.log_score") as mock_log_score,
        ):
            mock_parent = MagicMock()
            mock_get_span.return_value = mock_parent
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span

            from core.topic_discovery.graph import _taxonomy_gate

            state = {
                "taxonomy": {"root_nodes": [], "total_subdomains": 0},
                "coverage_metrics": {},
                "auto_approve": True,
            }
            result = _taxonomy_gate(state)

            assert result["batch_decision"] == "approve"
            mock_create_span.assert_called_once()
            assert mock_create_span.call_args[0][1] == "td-taxonomy-gate"
            mock_log_score.assert_called_once()
            assert mock_log_score.call_args[0][1] == "decision"
            mock_end_span.assert_called_once()

    def test_matrix_gate_auto_approve_traces(self):
        with (
            patch("core.topic_discovery.graph.get_current_span") as mock_get_span,
            patch("core.topic_discovery.graph.create_span") as mock_create_span,
            patch("core.topic_discovery.graph.end_span") as mock_end_span,
            patch("core.topic_discovery.graph.log_score") as mock_log_score,
        ):
            mock_parent = MagicMock()
            mock_get_span.return_value = mock_parent
            mock_span = MagicMock()
            mock_create_span.return_value = mock_span

            from core.topic_discovery.graph import _matrix_gate

            state = {
                "matrix": {"assignments": [], "total_assignments": 0},
                "auto_approve": True,
            }
            result = _matrix_gate(state)

            assert result["batch_decision"] == "approve"
            mock_create_span.assert_called_once()
            assert mock_create_span.call_args[0][1] == "td-matrix-gate"
            mock_log_score.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# _extract_usage helper
# ═══════════════════════════════════════════════════════════════════════


class TestExtractUsage:
    """Verify _extract_usage extracts token counts safely."""

    def test_extract_usage_from_response(self):
        from core.topic_discovery.agents import _extract_usage

        response = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50

        result = _extract_usage(response)
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50

    def test_extract_usage_from_none(self):
        from core.topic_discovery.agents import _extract_usage

        assert _extract_usage(None) == {}

    def test_extract_usage_no_usage_attr(self):
        from core.topic_discovery.agents import _extract_usage

        response = MagicMock(spec=[])
        assert _extract_usage(response) == {}
