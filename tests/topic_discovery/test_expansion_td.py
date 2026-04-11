"""Tests for on-demand subdomain expansion (Phase 4).

Covers:
- run_subdomain_expansion() agent function (mocked LLM)
- Prompt builder functions
- Topic priority scoring integration
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
)
from core.topic_discovery.agents import run_subdomain_expansion
from core.topic_discovery.prompts.subdomain_expansion import (
    build_subdomain_expansion_user_prompt,
    get_subdomain_expansion_system_prompt,
)
from core.topic_discovery.scoring import compute_topic_priority


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------


class TestSubdomainExpansionPrompt:
    """Tests for subdomain_expansion.py prompt builder."""

    def test_system_prompt_returns_string(self):
        prompt = get_subdomain_expansion_system_prompt()
        assert isinstance(prompt, str)
        assert "Subdomain Expansion Agent" in prompt

    def test_user_prompt_includes_subdomain(self):
        prompt = build_subdomain_expansion_user_prompt(
            subdomain_name="Expense Management",
            subdomain_description="Managing company expenses",
            buyer_stages=["tofu", "mofu"],
            intent_types=["informational"],
            audience_segments=[("david", "David Chen")],
            company_context="Ramp is a fintech company.",
        )
        assert "Expense Management" in prompt
        assert "Managing company expenses" in prompt
        assert "Ramp is a fintech company" in prompt
        assert "David Chen" in prompt
        assert "david" in prompt

    def test_user_prompt_combo_count(self):
        prompt = build_subdomain_expansion_user_prompt(
            subdomain_name="AP Automation",
            subdomain_description="",
            buyer_stages=["tofu", "mofu", "bofu"],
            intent_types=["informational", "commercial_investigation"],
            audience_segments=[("p1", "CFO"), ("p2", "AP Manager")],
            company_context="",
        )
        # 3 stages × 2 intents × 2 personas = 12 combos
        assert "**Total combinations:** 12" in prompt

    def test_user_prompt_persona_context(self):
        prompt = build_subdomain_expansion_user_prompt(
            subdomain_name="Billing",
            subdomain_description="",
            buyer_stages=["tofu"],
            intent_types=["informational"],
            audience_segments=[("p1", "CFO")],
            company_context="",
            persona_context="David is a VP of Finance with 10 years experience.",
        )
        assert "Persona Focus" in prompt
        assert "David is a VP of Finance" in prompt

    def test_user_prompt_no_persona_context(self):
        prompt = build_subdomain_expansion_user_prompt(
            subdomain_name="Billing",
            subdomain_description="",
            buyer_stages=["tofu"],
            intent_types=["informational"],
            audience_segments=[("p1", "CFO")],
            company_context="",
            persona_context=None,
        )
        assert "Persona Focus" not in prompt


# ---------------------------------------------------------------------------
# Agent function tests (mocked LLM)
# ---------------------------------------------------------------------------

_MOCK_EXPANSION_RESPONSE = json.dumps({
    "subdomain": "Expense Management",
    "topics": [
        {
            "buyer_stage": "tofu",
            "intent_type": "informational",
            "persona_id": "david",
            "persona_name": "David Chen",
            "title": "How to Build an Enterprise Expense Policy",
            "slug": "enterprise-expense-policy",
            "angle": "how_to",
            "description": "A guide to expense policies.",
            "target_keywords": {"primary": "expense policy", "secondary": ["corporate cards"]},
            "ai_citation_potential": "HIGH",
            "content_format": "guide",
            "estimated_word_count": 2500,
        },
        {
            "buyer_stage": "mofu",
            "intent_type": "commercial_investigation",
            "persona_id": "david",
            "persona_name": "David Chen",
            "title": "Ramp vs Brex: Expense Management Comparison",
            "slug": "ramp-vs-brex",
            "angle": "comparison",
            "description": "Head-to-head comparison.",
            "target_keywords": {"primary": "ramp vs brex", "secondary": []},
            "ai_citation_potential": "MEDIUM",
            "content_format": "comparison",
            "estimated_word_count": 3000,
        },
    ],
    "skipped_combos": 4,
    "total_combos_evaluated": 12,
})


class TestRunSubdomainExpansion:
    """Tests for run_subdomain_expansion() agent."""

    @pytest.mark.asyncio
    async def test_expansion_produces_assignments(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, _MOCK_EXPANSION_RESPONSE),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Expense Management",
                subdomain_description="Managing expenses",
                buyer_stages=["tofu", "mofu", "bofu"],
                intent_types=["informational", "commercial_investigation"],
                audience_segments=[("david", "David Chen")],
                company_context="Ramp is a fintech.",
            )

        assert len(result) == 2
        assert all(isinstance(a, TopicAssignment) for a in result)

    @pytest.mark.asyncio
    async def test_expansion_includes_persona_id_and_name(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, _MOCK_EXPANSION_RESPONSE),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Expense Management",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("david", "David Chen")],
                company_context="",
            )

        assert result[0].persona_id == "david"
        assert result[0].persona_name == "David Chen"

    @pytest.mark.asyncio
    async def test_expansion_maps_buyer_stage_enum(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, _MOCK_EXPANSION_RESPONSE),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Expense Management",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("david", "David Chen")],
                company_context="",
            )

        assert result[0].buyer_stage == BuyerStage.TOFU
        assert result[1].buyer_stage == BuyerStage.MOFU

    @pytest.mark.asyncio
    async def test_expansion_maps_intent_type_enum(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, _MOCK_EXPANSION_RESPONSE),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Expense Management",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("david", "David Chen")],
                company_context="",
            )

        assert result[0].intent_type == IntentType.informational
        assert result[1].intent_type == IntentType.commercial

    @pytest.mark.asyncio
    async def test_expansion_stores_metadata(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, _MOCK_EXPANSION_RESPONSE),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Expense Management",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("david", "David Chen")],
                company_context="",
            )

        assert result[0].metadata.get("angle") == "how_to"
        assert result[0].metadata.get("content_format") == "guide"
        assert result[0].metadata.get("slug") == "enterprise-expense-policy"

    @pytest.mark.asyncio
    async def test_expansion_empty_on_parse_failure(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, "not json"),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Billing",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("p1", "CFO")],
                company_context="",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_expansion_empty_on_exception(self):
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, "{}"),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Billing",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("p1", "CFO")],
                company_context="",
            )

        # No "topics" key → empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_expansion_skips_non_dict_topics(self):
        resp = json.dumps({"topics": ["not a dict", {"title": "Valid", "buyer_stage": "tofu", "intent_type": "informational", "persona_id": "p1", "persona_name": "CFO"}]})
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, resp),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Billing",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("p1", "CFO")],
                company_context="",
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_expansion_invalid_enum_defaults(self):
        """Invalid buyer_stage/intent_type strings default gracefully."""
        resp = json.dumps({
            "topics": [{
                "buyer_stage": "invalid_stage",
                "intent_type": "invalid_intent",
                "persona_id": "p1",
                "persona_name": "CFO",
                "title": "Test Topic",
            }],
        })
        with patch(
            "core.topic_discovery.agents._run_completion",
            new_callable=AsyncMock,
            return_value=(None, resp),
        ):
            result = await run_subdomain_expansion(
                subdomain_name="Billing",
                subdomain_description="",
                buyer_stages=["tofu"],
                intent_types=["informational"],
                audience_segments=[("p1", "CFO")],
                company_context="",
            )

        assert len(result) == 1
        assert result[0].buyer_stage == BuyerStage.TOFU  # default
        assert result[0].intent_type == IntentType.informational  # default


# ---------------------------------------------------------------------------
# Topic priority integration tests
# ---------------------------------------------------------------------------


class TestTopicPriorityIntegration:
    """Tests for compute_topic_priority with expansion output."""

    def test_bofu_transactional_highest(self):
        priority, factors = compute_topic_priority("bofu", "transactional", 1.0)
        assert priority == pytest.approx(1.0, abs=0.01)

    def test_tofu_navigational_lowest(self):
        priority, factors = compute_topic_priority("tofu", "navigational", 1.0)
        # (0.6 + 0.2) / 2 * 1.0 = 0.4
        assert priority < 0.5

    def test_priority_factors_populated(self):
        _, factors = compute_topic_priority("mofu", "commercial", 0.7)
        assert "buyer_weight" in factors
        assert "intent_weight" in factors
        assert "subdomain_score" in factors

    def test_subdomain_multiplier_effect(self):
        p_high, _ = compute_topic_priority("bofu", "transactional", 1.0)
        p_low, _ = compute_topic_priority("bofu", "transactional", 0.5)
        assert p_high > p_low


# ---------------------------------------------------------------------------
# Cannibalization detection helpers
# ---------------------------------------------------------------------------


from core.topic_discovery.pipeline import _build_cannibal_query, _apply_cannibalization_results


class TestBuildCannibalQuery:
    """Tests for _build_cannibal_query()."""

    def test_basic_topic_text(self):
        a = TopicAssignment(topic_text="How to Build an Expense Policy")
        result = _build_cannibal_query(a)
        assert result == "How to Build an Expense Policy"

    def test_includes_description(self):
        a = TopicAssignment(
            topic_text="Expense Policy Guide",
            metadata={"description": "A comprehensive guide to expense policies."},
        )
        result = _build_cannibal_query(a)
        assert "Expense Policy Guide" in result
        assert "A comprehensive guide" in result
        assert " | " in result

    def test_includes_target_keywords(self):
        a = TopicAssignment(
            topic_text="Ramp vs Brex",
            metadata={
                "description": "Head-to-head comparison.",
                "target_keywords": ["expense management", "corporate cards", "AP automation"],
            },
        )
        result = _build_cannibal_query(a)
        assert "Ramp vs Brex" in result
        assert "expense management" in result
        assert "corporate cards" in result

    def test_truncates_keywords_at_10(self):
        a = TopicAssignment(
            topic_text="Topic",
            metadata={"target_keywords": [f"kw{i}" for i in range(20)]},
        )
        result = _build_cannibal_query(a)
        assert "kw9" in result
        assert "kw10" not in result

    def test_handles_empty_metadata(self):
        a = TopicAssignment(topic_text="Some Topic", metadata={})
        result = _build_cannibal_query(a)
        assert result == "Some Topic"

    def test_handles_non_list_keywords(self):
        a = TopicAssignment(
            topic_text="Topic",
            metadata={"target_keywords": {"primary": "expense"}},
        )
        result = _build_cannibal_query(a)
        # Non-list keywords are ignored
        assert result == "Topic"


class TestApplyCannibalizationResults:
    """Tests for _apply_cannibalization_results()."""

    def _make_match(self, similarity: float = 0.85):
        """Create a mock CannibalizationMatch."""

        class _Match:
            def __init__(self, sim):
                self.inventory_id = "inv-123"
                self.url = "https://example.com/blog/guide"
                self.title = "Existing Guide"
                self.similarity = sim
                self.word_count = 1500
                self.content_type_detected = "blog_post"

        return _Match(similarity)

    def test_no_matches_sets_zero_risk(self):
        a = TopicAssignment(topic_text="New Topic", priority_score=0.8, metadata={})
        _apply_cannibalization_results([a], ["New Topic"], {})
        assert a.metadata["cannibalization_risk"] == 0.0
        assert a.metadata["cannibalization_risk_level"] == "none"
        assert a.metadata["cannibalization_recommended_action"] == "safe_to_create_new"
        assert a.metadata["cannibalization_matches"] == []
        assert a.priority_score == 0.8  # Unchanged

    def test_match_enriches_metadata(self):
        a = TopicAssignment(topic_text="Topic A", priority_score=0.8, metadata={})
        match = self._make_match(0.87)
        _apply_cannibalization_results([a], ["Topic A"], {"Topic A": [match]})
        assert a.metadata["cannibalization_risk"] == 0.87
        assert a.metadata["cannibalization_risk_level"] in {"medium", "high"}
        assert a.metadata["cannibalization_recommended_action"] in {
            "differentiate_angle",
            "merge_or_refresh_existing",
        }
        assert len(a.metadata["cannibalization_matches"]) == 1
        assert a.metadata["cannibalization_matches"][0]["url"] == "https://example.com/blog/guide"
        assert a.metadata["cannibalization_matches"][0]["similarity"] == 0.87
        assert "risk_score" in a.metadata["cannibalization_matches"][0]
        assert "signals" in a.metadata["cannibalization_matches"][0]

    def test_penalty_zero_at_threshold(self):
        """Similarity at exactly the threshold (0.80) should produce no penalty."""
        a = TopicAssignment(
            topic_text="T", priority_score=1.0,
            priority_factors={}, metadata={},
        )
        _apply_cannibalization_results(
            [a], ["T"], {"T": [self._make_match(0.80)]},
        )
        # At 0.80, penalty should be 0 (or negligible)
        assert a.priority_score == pytest.approx(1.0, abs=0.01)

    def test_penalty_moderate_at_085(self):
        """Similarity 0.85 → ~10% penalty."""
        a = TopicAssignment(
            topic_text="T", priority_score=1.0,
            priority_factors={}, metadata={},
        )
        _apply_cannibalization_results(
            [a], ["T"], {"T": [self._make_match(0.85)]},
        )
        assert a.priority_score == pytest.approx(0.90, abs=0.02)
        assert "cannibalization_penalty" in a.priority_factors

    def test_penalty_strong_at_090(self):
        """Similarity 0.90 → 20% penalty."""
        a = TopicAssignment(
            topic_text="T", priority_score=1.0,
            priority_factors={}, metadata={},
        )
        _apply_cannibalization_results(
            [a], ["T"], {"T": [self._make_match(0.90)]},
        )
        assert a.priority_score == pytest.approx(0.80, abs=0.02)

    def test_penalty_very_strong_at_095(self):
        """Similarity 0.95 → ~27.5% penalty."""
        a = TopicAssignment(
            topic_text="T", priority_score=1.0,
            priority_factors={}, metadata={},
        )
        _apply_cannibalization_results(
            [a], ["T"], {"T": [self._make_match(0.95)]},
        )
        assert a.priority_score == pytest.approx(0.725, abs=0.02)

    def test_penalty_capped_at_035(self):
        """Penalty never exceeds 35% even at similarity=1.0."""
        a = TopicAssignment(
            topic_text="T", priority_score=1.0,
            priority_factors={}, metadata={},
        )
        _apply_cannibalization_results(
            [a], ["T"], {"T": [self._make_match(1.0)]},
        )
        assert a.priority_score >= 0.65

    def test_caps_matches_at_max(self):
        """Only top N matches stored (default 5 from settings)."""
        a = TopicAssignment(topic_text="T", priority_score=1.0, metadata={})
        matches = [self._make_match(0.80 + 0.02 * i) for i in range(10)]
        _apply_cannibalization_results([a], ["T"], {"T": matches})
        assert len(a.metadata["cannibalization_matches"]) <= 5

    def test_multiple_assignments(self):
        """Batch mode: each assignment gets its own result."""
        a1 = TopicAssignment(topic_text="T1", priority_score=1.0, metadata={})
        a2 = TopicAssignment(topic_text="T2", priority_score=0.8, metadata={})
        results = {
            "Q1": [self._make_match(0.90)],
            "Q2": [],
        }
        _apply_cannibalization_results([a1, a2], ["Q1", "Q2"], results)
        assert a1.metadata["cannibalization_risk"] == 0.90
        assert a2.metadata["cannibalization_risk"] == 0.0
        assert a1.priority_score < 1.0
        assert a2.priority_score == 0.8  # Unchanged

    def test_zero_priority_not_modified(self):
        """Assignments with priority_score=0 are not penalized."""
        a = TopicAssignment(topic_text="T", priority_score=0.0, metadata={})
        _apply_cannibalization_results(
            [a], ["T"], {"T": [self._make_match(0.95)]},
        )
        assert a.priority_score == 0.0

    def test_signal_overrides_flow_into_match_metadata(self):
        a = TopicAssignment(topic_text="T", priority_score=1.0, metadata={})
        match = self._make_match(0.82)

        _apply_cannibalization_results(
            [a],
            ["T"],
            {"T": [match]},
            signal_overrides_by_query={
                "T": {
                    "inv-123": {
                        "query_overlap_score": 0.9,
                        "citation_overlap_score": 0.8,
                        "citation_count": 5,
                        "matched_queries": ["expense management software"],
                    },
                },
            },
        )

        top_match = a.metadata["cannibalization_matches"][0]
        assert top_match["signals"]["query_overlap"] == pytest.approx(0.9)
        assert top_match["signals"]["citation_overlap"] == pytest.approx(0.8)
