"""Tests for LLM cost tracking metadata utilities.

Verifies ``extract_provider`` and ``build_llm_metadata`` in
``core.shared_tools.tracing``.
"""
from __future__ import annotations

import pytest

from core.shared_tools.tracing import build_llm_metadata, extract_provider


# ---------------------------------------------------------------------------
# extract_provider
# ---------------------------------------------------------------------------


class TestExtractProvider:
    """Extract LLM provider name from model strings."""

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("anthropic/claude-sonnet-4-6", "anthropic"),
            ("openai/gpt-5.2-2025-12-11", "openai"),
            ("perplexity/sonar-pro", "perplexity"),
            ("google/gemini-3-flash-preview", "google"),
            # Bare model names (no prefix)
            ("claude-sonnet-4-6", "anthropic"),
            ("claude-haiku-4-5", "anthropic"),
            ("sonar-deep-research", "perplexity"),
            ("sonar-pro", "perplexity"),
            ("gpt-5.2-2025-12-11", "openai"),
            ("o1-preview", "openai"),
            ("o3-mini", "openai"),
            ("gemini-3-flash-preview", "google"),
            # Unknown models
            ("some-custom-model", "unknown"),
            ("llama-3", "unknown"),
        ],
    )
    def test_known_providers(self, model: str, expected: str) -> None:
        assert extract_provider(model) == expected

    def test_prefixed_takes_priority(self) -> None:
        # Even if model name looks like claude, the prefix wins
        assert extract_provider("custom/claude-sonnet-4-6") == "custom"

    def test_litellm_format(self) -> None:
        # LiteLLM uses format "anthropic:claude-opus-4-6" sometimes
        # Our function only handles "/" separator — ":" stays as-is
        assert extract_provider("anthropic:claude-opus-4-6") == "unknown"


# ---------------------------------------------------------------------------
# build_llm_metadata
# ---------------------------------------------------------------------------


class TestBuildLlmMetadata:
    """Build standardised metadata dict for LangSmith cost tracking."""

    def test_basic_fields(self) -> None:
        meta = build_llm_metadata(
            pipeline="content_engine",
            pipeline_step="drafter",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
        )
        assert meta["pipeline"] == "content_engine"
        assert meta["pipeline_step"] == "drafter"
        assert meta["provider"] == "anthropic"
        assert meta["model"] == "anthropic/claude-sonnet-4-6"
        assert meta["company_slug"] == ""  # default

    def test_company_slug(self) -> None:
        meta = build_llm_metadata(
            pipeline="knowledge_base",
            pipeline_step="synthesis",
            provider="anthropic",
            model="claude-opus-4-6",
            company_slug="ramp",
        )
        assert meta["company_slug"] == "ramp"

    def test_extra_kwargs_merged(self) -> None:
        meta = build_llm_metadata(
            pipeline="content_engine",
            pipeline_step="outliner",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
            brief_id="brief-001",
            agent="outliner",
        )
        assert meta["brief_id"] == "brief-001"
        assert meta["agent"] == "outliner"
        # Core fields still present
        assert meta["pipeline"] == "content_engine"

    def test_extra_keys_merge(self) -> None:
        meta = build_llm_metadata(
            pipeline="content_engine",
            pipeline_step="drafter",
            provider="anthropic",
            model="model",
            custom_key="custom_value",
        )
        assert meta["custom_key"] == "custom_value"
        assert len(meta) == 6  # 5 core + 1 extra

    def test_returns_plain_dict(self) -> None:
        meta = build_llm_metadata(
            pipeline="topic_discovery",
            pipeline_step="source_a",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
        )
        assert isinstance(meta, dict)
        # Must be JSON-serialisable
        import json
        json.dumps(meta)  # should not raise


# ---------------------------------------------------------------------------
# Integration: extract_provider + build_llm_metadata
# ---------------------------------------------------------------------------


class TestCostTrackingIntegration:
    """Combined usage of extract_provider and build_llm_metadata."""

    def test_typical_content_engine_usage(self) -> None:
        model = "anthropic/claude-sonnet-4-6"
        meta = build_llm_metadata(
            pipeline="content_engine",
            pipeline_step="drafter",
            provider=extract_provider(model),
            model=model,
            agent="drafter",
            brief_id="brief-001",
        )
        assert meta["provider"] == "anthropic"
        assert meta["pipeline"] == "content_engine"

    def test_typical_td_usage(self) -> None:
        model = "anthropic/claude-sonnet-4-6"
        meta = build_llm_metadata(
            pipeline="topic_discovery",
            pipeline_step="source_a",
            provider=extract_provider(model),
            model=model,
        )
        assert meta["provider"] == "anthropic"

    def test_perplexity_raw_sdk_usage(self) -> None:
        model = "sonar-deep-research"
        meta = build_llm_metadata(
            pipeline="knowledge_base",
            pipeline_step="company_overview",
            provider="perplexity",
            model=model,
        )
        assert meta["provider"] == "perplexity"
        assert meta["model"] == "sonar-deep-research"
