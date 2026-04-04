"""Tests for LLM cost tracking utilities.

Covers ``core.shared_tools.cost_tracker``:
  - Pricing table prefix matching
  - Cost estimation arithmetic
  - track_llm_cost() structlog event emission + never-raises guarantee
  - Provider-specific usage extractors (Anthropic HTTP, Gemini HTTP,
    OpenAI responses.create, Anthropic SDK, LiteLLM)
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.shared_tools.cost_tracker import (
    PRICING,
    estimate_cost,
    extract_usage_anthropic_http,
    extract_usage_anthropic_sdk,
    extract_usage_gemini_http,
    extract_usage_langchain_openai,
    extract_usage_litellm,
    extract_usage_openai_responses,
    track_llm_cost,
)


# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------


class TestPricingTable:
    """Verify pricing entries exist for native-API models."""

    def test_known_models_present(self) -> None:
        assert "claude-sonnet-4-6" in PRICING
        assert "claude-opus-4-6" in PRICING
        assert "gpt-5.2" in PRICING
        assert "gemini-3-flash-preview" in PRICING

    def test_embedding_models_present(self) -> None:
        assert "text-embedding-3-small" in PRICING
        assert "text-embedding-3-large" in PRICING
        # Embeddings have no output cost
        assert PRICING["text-embedding-3-small"][1] == 0.0
        assert PRICING["text-embedding-3-large"][1] == 0.0

    def test_entries_are_positive(self) -> None:
        for model, (inp, out) in PRICING.items():
            assert inp >= 0, f"{model} input price negative"
            assert out >= 0, f"{model} output price negative"


# ---------------------------------------------------------------------------
# estimate_cost
# ---------------------------------------------------------------------------


class TestEstimateCost:
    """Arithmetic for USD cost estimation."""

    def test_known_model_basic_math(self) -> None:
        # claude-sonnet-4-6: $3.00 input / $15.00 output per 1M tokens
        cost = estimate_cost(
            model="claude-sonnet-4-6",
            provider="anthropic",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        assert cost == pytest.approx(18.00, abs=0.01)

    def test_prefix_matching(self) -> None:
        # gpt-5.2-2025-12-11 should match "gpt-5.2" entry
        cost = estimate_cost(
            model="gpt-5.2-2025-12-11",
            provider="openai",
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        assert cost > 0

    def test_zero_tokens_returns_zero(self) -> None:
        cost = estimate_cost(
            model="claude-sonnet-4-6",
            provider="anthropic",
            prompt_tokens=0,
            completion_tokens=0,
        )
        assert cost == 0.0

    def test_unknown_model_returns_zero(self) -> None:
        cost = estimate_cost(
            model="totally-unknown-model-xyz",
            provider="unknown",
            prompt_tokens=10000,
            completion_tokens=5000,
        )
        assert cost == 0.0

    def test_provider_prefixed_model(self) -> None:
        # "anthropic/claude-sonnet-4-6" should strip prefix and match
        cost = estimate_cost(
            model="anthropic/claude-sonnet-4-6",
            provider="anthropic",
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        assert cost == pytest.approx(3.00, abs=0.01)

    def test_embedding_model_input_only(self) -> None:
        # text-embedding-3-small: $0.02 per 1M input, $0.00 output
        cost = estimate_cost(
            model="text-embedding-3-small",
            provider="openai",
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        assert cost == pytest.approx(0.02, abs=0.001)

    def test_embedding_model_large(self) -> None:
        cost = estimate_cost(
            model="openai/text-embedding-3-large",
            provider="openai",
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        assert cost == pytest.approx(0.13, abs=0.001)


# ---------------------------------------------------------------------------
# track_llm_cost
# ---------------------------------------------------------------------------


class TestTrackLlmCost:
    """Verify structured log event emission."""

    def test_emits_log_event(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="claude-sonnet-4-6",
                provider="anthropic",
                pipeline="gap_analysis",
                pipeline_step="s3_claude_engine",
                prompt_tokens=100,
                completion_tokens=50,
                company_slug="ramp",
                call_site="core.gap_analysis.engines.claude",
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "llm_cost_tracked" in record.message
        assert record.model == "claude-sonnet-4-6"  # type: ignore[attr-defined]
        assert record.provider == "anthropic"  # type: ignore[attr-defined]
        assert record.prompt_tokens == 100  # type: ignore[attr-defined]
        assert record.completion_tokens == 50  # type: ignore[attr-defined]
        assert record.source == "native"  # type: ignore[attr-defined]

    def test_never_raises_on_error(self) -> None:
        """Even if logging itself blows up, track_llm_cost must not raise."""
        with patch("core.shared_tools.cost_tracker.logger") as mock_logger:
            mock_logger.info.side_effect = RuntimeError("boom")
            # Should NOT raise
            track_llm_cost(
                model="x",
                provider="x",
                pipeline="x",
                pipeline_step="x",
                prompt_tokens=0,
                completion_tokens=0,
            )

    def test_includes_source_native(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="gpt-5.2",
                provider="openai",
                pipeline="gap_analysis",
                pipeline_step="s2_query_gen",
                prompt_tokens=10,
                completion_tokens=5,
            )
        assert caplog.records[0].source == "native"  # type: ignore[attr-defined]

    def test_includes_estimated_cost(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="claude-sonnet-4-6",
                provider="anthropic",
                pipeline="test",
                pipeline_step="test",
                prompt_tokens=1_000_000,
                completion_tokens=1_000_000,
            )
        assert caplog.records[0].estimated_cost_usd == pytest.approx(18.00, abs=0.01)  # type: ignore[attr-defined]

    def test_extra_fields_forwarded(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="gemini-3-flash-preview",
                provider="google",
                pipeline="knowledge_base",
                pipeline_step="synthesis",
                prompt_tokens=100,
                completion_tokens=50,
                extra={"estimation_method": "char_count"},
            )
        assert caplog.records[0].estimation_method == "char_count"  # type: ignore[attr-defined]

    def test_zero_usage_still_emits(self, caplog: pytest.LogCaptureFixture) -> None:
        """Missing usage → emit with 0 tokens and 0 cost, never skip."""
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="unknown",
                provider="unknown",
                pipeline="test",
                pipeline_step="test",
                prompt_tokens=0,
                completion_tokens=0,
            )
        assert len(caplog.records) == 1
        assert caplog.records[0].estimated_cost_usd == 0.0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Usage extractors
# ---------------------------------------------------------------------------


class TestExtractUsageAnthropicHttp:
    """Extract from raw Anthropic JSON response dict."""

    def test_normal_response(self) -> None:
        data = {"usage": {"input_tokens": 123, "output_tokens": 456}}
        assert extract_usage_anthropic_http(data) == (123, 456)

    def test_missing_usage_key(self) -> None:
        assert extract_usage_anthropic_http({}) == (0, 0)

    def test_none_values(self) -> None:
        data = {"usage": {"input_tokens": None, "output_tokens": None}}
        assert extract_usage_anthropic_http(data) == (0, 0)

    def test_partial_usage(self) -> None:
        data = {"usage": {"input_tokens": 100}}
        assert extract_usage_anthropic_http(data) == (100, 0)


class TestExtractUsageGeminiHttp:
    """Extract from raw Gemini JSON response dict."""

    def test_normal_response(self) -> None:
        data = {"usageMetadata": {"promptTokenCount": 200, "candidatesTokenCount": 300}}
        assert extract_usage_gemini_http(data) == (200, 300)

    def test_missing_metadata(self) -> None:
        assert extract_usage_gemini_http({}) == (0, 0)

    def test_none_values(self) -> None:
        data = {"usageMetadata": {"promptTokenCount": None, "candidatesTokenCount": None}}
        assert extract_usage_gemini_http(data) == (0, 0)

    def test_partial_metadata(self) -> None:
        data = {"usageMetadata": {"promptTokenCount": 150}}
        assert extract_usage_gemini_http(data) == (150, 0)


class TestExtractUsageOpenaiResponses:
    """Extract from OpenAI responses.create() SDK response object."""

    def test_normal_response(self) -> None:
        resp = SimpleNamespace(usage=SimpleNamespace(input_tokens=500, output_tokens=250))
        assert extract_usage_openai_responses(resp) == (500, 250)

    def test_no_usage_attribute(self) -> None:
        resp = SimpleNamespace()
        assert extract_usage_openai_responses(resp) == (0, 0)

    def test_usage_is_none(self) -> None:
        resp = SimpleNamespace(usage=None)
        assert extract_usage_openai_responses(resp) == (0, 0)

    def test_none_token_values(self) -> None:
        resp = SimpleNamespace(usage=SimpleNamespace(input_tokens=None, output_tokens=None))
        assert extract_usage_openai_responses(resp) == (0, 0)


class TestExtractUsageAnthropicSdk:
    """Extract from Anthropic SDK Message response object."""

    def test_normal_response(self) -> None:
        resp = SimpleNamespace(usage=SimpleNamespace(input_tokens=800, output_tokens=400))
        assert extract_usage_anthropic_sdk(resp) == (800, 400)

    def test_no_usage(self) -> None:
        resp = SimpleNamespace()
        assert extract_usage_anthropic_sdk(resp) == (0, 0)

    def test_usage_none(self) -> None:
        resp = SimpleNamespace(usage=None)
        assert extract_usage_anthropic_sdk(resp) == (0, 0)


class TestExtractUsageLitellm:
    """Extract from LiteLLM response object."""

    def test_normal_response(self) -> None:
        resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=600, completion_tokens=300))
        assert extract_usage_litellm(resp) == (600, 300)

    def test_no_usage(self) -> None:
        resp = SimpleNamespace()
        assert extract_usage_litellm(resp) == (0, 0)

    def test_usage_none(self) -> None:
        resp = SimpleNamespace(usage=None)
        assert extract_usage_litellm(resp) == (0, 0)

    def test_none_token_values(self) -> None:
        resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=None, completion_tokens=None))
        assert extract_usage_litellm(resp) == (0, 0)


class TestExtractUsageLangchainOpenai:
    """Extract from LangChain ChatOpenAI AIMessage.response_metadata."""

    def test_normal_response(self) -> None:
        resp = SimpleNamespace(
            response_metadata={"token_usage": {"prompt_tokens": 700, "completion_tokens": 350}},
        )
        assert extract_usage_langchain_openai(resp) == (700, 350)

    def test_missing_response_metadata(self) -> None:
        resp = SimpleNamespace()
        assert extract_usage_langchain_openai(resp) == (0, 0)

    def test_missing_token_usage(self) -> None:
        resp = SimpleNamespace(response_metadata={"some_other_key": 42})
        assert extract_usage_langchain_openai(resp) == (0, 0)

    def test_none_values(self) -> None:
        resp = SimpleNamespace(
            response_metadata={"token_usage": {"prompt_tokens": None, "completion_tokens": None}},
        )
        assert extract_usage_langchain_openai(resp) == (0, 0)


class TestTrackLlmCostSourceParam:
    """Verify the optional source parameter on track_llm_cost()."""

    def test_source_defaults_to_native(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="gpt-5.2", provider="openai",
                pipeline="test", pipeline_step="test",
                prompt_tokens=10, completion_tokens=5,
            )
        assert caplog.records[0].source == "native"  # type: ignore[attr-defined]

    def test_source_openrouter(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="llm_cost"):
            track_llm_cost(
                model="anthropic/claude-opus-4-6", provider="openrouter",
                pipeline="knowledge_base", pipeline_step="synthesis",
                prompt_tokens=1000, completion_tokens=500,
                source="openrouter",
            )
        assert caplog.records[0].source == "openrouter"  # type: ignore[attr-defined]
