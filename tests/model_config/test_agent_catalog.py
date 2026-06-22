"""Tests for BYOK agent catalog."""
from __future__ import annotations

from core.model_config.agent_catalog import (
    all_agent_definitions,
    get_agent_definition,
    required_agents_for_pipeline,
)


def test_catalog_agent_keys_are_unique() -> None:
    definitions = all_agent_definitions()
    keys = [definition.agent_key for definition in definitions]
    assert len(keys) == len(set(keys))


def test_catalog_contains_spec_required_agents() -> None:
    keys = {definition.agent_key for definition in all_agent_definitions()}
    assert "shared.embeddings.default" in keys
    assert "content.brief_builder" in keys
    assert "topic_discovery.source_c_deep_research" in keys
    assert "research.kb.brand_perception" in keys
    assert "daily_tracker.content_to_prompt" in keys
    assert "reddit_hil.ranking_drafting" in keys


def test_required_agents_for_pipeline_excludes_disabled_search_parity_agents() -> None:
    gap_required = {item.agent_key for item in required_agents_for_pipeline("gap")}
    assert "gap.query_generation" in gap_required
    assert "gap.search.perplexity" in gap_required
    assert "gap.search.openai" not in gap_required
    assert "gap.search.claude" not in gap_required
    assert "gap.search.gemini" not in gap_required


def test_get_agent_definition_returns_none_for_unknown_key() -> None:
    assert get_agent_definition("missing.agent") is None
