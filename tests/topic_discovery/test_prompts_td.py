"""Tests for Topic Discovery prompt templates.

Covers: system prompts non-empty, builder functions produce strings with
expected fragments, round-number injection, specialist_lens injection.
"""
from __future__ import annotations

import pytest

from core.topic_discovery.prompts.source_a_company import (
    SOURCE_A_SYSTEM_PROMPT,
    get_source_a_system_prompt,
    build_source_a_user_prompt,
)
from core.topic_discovery.prompts.source_b_persona import (
    SOURCE_B_SYSTEM_PROMPT,
    get_source_b_system_prompt,
    build_source_b_user_prompt,
)
from core.topic_discovery.prompts.source_c_deep_research import (
    SOURCE_C_SYSTEM_PROMPT,
    get_source_c_system_prompt,
    build_source_c_user_prompt,
)
from core.topic_discovery.prompts.source_d_adversarial import (
    SOURCE_D_SYSTEM_PROMPT,
    get_source_d_system_prompt,
    build_source_d_user_prompt,
)
from core.topic_discovery.prompts.hierarchy_construction import (
    HIERARCHY_SYSTEM_PROMPT,
    get_hierarchy_system_prompt,
    build_hierarchy_user_prompt,
)
from core.topic_discovery.prompts.relevance_filtering import (
    RELEVANCE_SYSTEM_PROMPT,
    get_relevance_system_prompt,
    build_relevance_user_prompt,
)
from core.topic_discovery.prompts.topic_generation import (
    TOPIC_GENERATION_SYSTEM_PROMPT,
    get_topic_generation_system_prompt,
    build_topic_generation_user_prompt,
)


# ── System Prompts ───────────────────────────────────────────────────────


class TestSystemPrompts:
    """All system prompts must be non-empty and substantial."""

    @pytest.mark.parametrize("prompt,name", [
        (SOURCE_A_SYSTEM_PROMPT, "source_a"),
        (SOURCE_B_SYSTEM_PROMPT, "source_b"),
        (SOURCE_C_SYSTEM_PROMPT, "source_c"),
        (SOURCE_D_SYSTEM_PROMPT, "source_d"),
        (HIERARCHY_SYSTEM_PROMPT, "hierarchy"),
        (RELEVANCE_SYSTEM_PROMPT, "relevance"),
        (TOPIC_GENERATION_SYSTEM_PROMPT, "topic_generation"),
    ])
    def test_system_prompt_is_non_empty(self, prompt, name):
        assert isinstance(prompt, str)
        assert len(prompt) > 100, f"{name} system prompt too short"

    @pytest.mark.parametrize("getter", [
        get_source_a_system_prompt,
        get_source_b_system_prompt,
        get_source_c_system_prompt,
        get_source_d_system_prompt,
        get_hierarchy_system_prompt,
        get_relevance_system_prompt,
        get_topic_generation_system_prompt,
    ])
    def test_getter_returns_string(self, getter):
        result = getter()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_all_system_prompts_mention_json(self):
        """All prompts should require JSON output."""
        for prompt in [
            SOURCE_A_SYSTEM_PROMPT,
            SOURCE_B_SYSTEM_PROMPT,
            SOURCE_C_SYSTEM_PROMPT,
            SOURCE_D_SYSTEM_PROMPT,
            HIERARCHY_SYSTEM_PROMPT,
            RELEVANCE_SYSTEM_PROMPT,
            TOPIC_GENERATION_SYSTEM_PROMPT,
        ]:
            assert "json" in prompt.lower() or "JSON" in prompt, \
                "System prompt must mention JSON output"


# ── Source A Builder ─────────────────────────────────────────────────────


class TestSourceABuilder:
    def test_basic_prompt(self):
        result = build_source_a_user_prompt("Ramp is a fintech company")
        assert isinstance(result, str)
        assert "Ramp is a fintech company" in result

    def test_round_number_injection(self):
        result = build_source_a_user_prompt("context", round_number=3)
        assert "3" in result

    def test_previous_subdomains_injection(self):
        result = build_source_a_user_prompt(
            "context",
            round_number=2,
            previous_subdomains=["expense management", "corporate cards"],
        )
        assert "expense management" in result
        assert "corporate cards" in result

    def test_first_round_no_previous(self):
        result = build_source_a_user_prompt("context", round_number=1)
        assert isinstance(result, str)


# ── Source B Builder ─────────────────────────────────────────────────────


class TestSourceBBuilder:
    def test_basic_prompt(self):
        result = build_source_b_user_prompt(
            persona_profiles="CFO persona profile...",
            company_context="Ramp is a fintech company",
        )
        assert "CFO persona profile" in result
        assert "Ramp is a fintech company" in result

    def test_round_number_injection(self):
        result = build_source_b_user_prompt(
            "personas", "context", round_number=4
        )
        assert "4" in result

    def test_previous_subdomains_injection(self):
        result = build_source_b_user_prompt(
            "personas", "context",
            round_number=2,
            previous_subdomains=["budgeting"],
        )
        assert "budgeting" in result


# ── Source C Builder ─────────────────────────────────────────────────────


class TestSourceCBuilder:
    def test_basic_prompt(self):
        result = build_source_c_user_prompt(
            company_context="Ramp is a fintech company providing corporate cards",
            competitor_landscape="Brex and Divvy are key competitors",
            domain="corporate spend management",
        )
        assert "Ramp is a fintech" in result
        assert "corporate spend management" in result
        assert "Brex and Divvy" in result

    def test_empty_competitor_landscape(self):
        result = build_source_c_user_prompt(
            company_context="Ramp context",
            competitor_landscape="",
            domain="fintech",
        )
        assert "No competitor data provided" in result

    def test_revision_note(self):
        result = build_source_c_user_prompt(
            company_context="Context",
            competitor_landscape="Competitors",
            domain="fintech",
            revision_note="Add more emerging topics",
        )
        assert "Reviewer Feedback" in result
        assert "Add more emerging topics" in result


# ── Source D Builder ─────────────────────────────────────────────────────


class TestSourceDBuilder:
    def test_basic_prompt(self):
        result = build_source_d_user_prompt(
            company_context="Ramp is a fintech company",
            specialist_lens="regulatory compliance expert",
        )
        assert "regulatory compliance expert" in result
        assert "Ramp is a fintech company" in result

    def test_round_number_injection(self):
        result = build_source_d_user_prompt(
            "context", "security expert", round_number=3
        )
        assert "3" in result

    def test_previous_subdomains_injection(self):
        result = build_source_d_user_prompt(
            "context", "infra specialist",
            round_number=2,
            previous_subdomains=["SOC2 compliance"],
        )
        assert "SOC2 compliance" in result


# ── Hierarchy Builder ────────────────────────────────────────────────────


class TestHierarchyBuilder:
    def test_basic_prompt(self):
        result = build_hierarchy_user_prompt(
            subdomains=["expense management", "corporate cards", "compliance"],
            company_domain="fintech",
        )
        assert "expense management" in result
        assert "fintech" in result

    def test_many_subdomains(self):
        subs = [f"subdomain-{i}" for i in range(50)]
        result = build_hierarchy_user_prompt(subs, "tech")
        assert "subdomain-49" in result


# ── Relevance Builder ───────────────────────────────────────────────────


class TestRelevanceBuilder:
    def test_basic_prompt(self):
        dims = [
            {"buyer_stage": "tofu", "intent_type": "informational", "audience_segment": "CFO"},
            {"buyer_stage": "mofu", "intent_type": "commercial", "audience_segment": "CFO"},
        ]
        result = build_relevance_user_prompt(
            subdomain="expense management",
            dimensions=dims,
            company_context="Ramp fintech",
        )
        assert "expense management" in result
        assert "tofu" in result or "TOFU" in result


# ── Topic Generation Builder ────────────────────────────────────────────


class TestTopicGenerationBuilder:
    def test_basic_prompt(self):
        result = build_topic_generation_user_prompt(
            subdomain="expense management",
            buyer_stage="tofu",
            intent_type="informational",
            audience_segment="CFO",
            company_context="Ramp fintech company",
        )
        assert "expense management" in result
        assert "Ramp fintech company" in result
