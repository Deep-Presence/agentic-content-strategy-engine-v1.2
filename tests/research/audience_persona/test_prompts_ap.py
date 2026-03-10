"""Tests for audience persona prompt builders — system prompts and user prompts."""
from __future__ import annotations

from unittest.mock import patch

from core.models.audience_persona import AudiencePersonaInput, PersonaBrief
from core.research.prompts.persona_suggester import (
    PERSONA_SUGGESTER_SYSTEM_PROMPT,
    _HUB_NAME as SUGGESTER_HUB_NAME,
    build_persona_suggester_user_prompt,
    get_persona_suggester_system_prompt,
)
from core.research.prompts.persona_generator import (
    PERSONA_GENERATOR_SYSTEM_PROMPT,
    _HUB_NAME as GENERATOR_HUB_NAME,
    build_persona_generator_user_prompt,
    get_persona_generator_system_prompt,
)


# ---------------------------------------------------------------------------
# Suggester System Prompt
# ---------------------------------------------------------------------------


class TestSuggesterSystemPrompt:
    def test_non_empty(self) -> None:
        assert len(PERSONA_SUGGESTER_SYSTEM_PROMPT) > 100

    def test_contains_key_instructions(self) -> None:
        assert "JSON array" in PERSONA_SUGGESTER_SYSTEM_PROMPT
        assert "persona_name" in PERSONA_SUGGESTER_SYSTEM_PROMPT
        assert "tagline" in PERSONA_SUGGESTER_SYSTEM_PROMPT
        assert "rationale" in PERSONA_SUGGESTER_SYSTEM_PROMPT
        assert "Strategic Audience Analyst" in PERSONA_SUGGESTER_SYSTEM_PROMPT

    def test_contains_max_personas_placeholder(self) -> None:
        assert "{max_personas}" in PERSONA_SUGGESTER_SYSTEM_PROMPT

    def test_hub_name_set(self) -> None:
        assert SUGGESTER_HUB_NAME == "research-persona-suggester-system"

    def test_get_system_prompt_uses_hub_fallback(self) -> None:
        with patch("core.content_engine.prompt_registry.get_prompt") as mock_get:
            mock_get.return_value = PERSONA_SUGGESTER_SYSTEM_PROMPT
            result = get_persona_suggester_system_prompt()
            mock_get.assert_called_once_with(SUGGESTER_HUB_NAME, PERSONA_SUGGESTER_SYSTEM_PROMPT)
            assert result == PERSONA_SUGGESTER_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Suggester User Prompt
# ---------------------------------------------------------------------------


class TestSuggesterUserPrompt:
    def _make_input(self, **overrides: object) -> AudiencePersonaInput:
        defaults = {"company_name": "Test Co", "max_personas": 5}
        defaults.update(overrides)
        return AudiencePersonaInput(**defaults)

    def test_includes_company_context(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), "Company overview text", "Review text"
        )
        assert "Company overview text" in prompt
        assert "### Company Overview" in prompt

    def test_includes_customer_reviews(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), "ctx", "Customer review data here"
        )
        assert "Customer review data here" in prompt
        assert "### Customer Reviews" in prompt

    def test_includes_knowledge_docs(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), "ctx", "rev", "Internal doc content"
        )
        assert "Internal doc content" in prompt

    def test_empty_knowledge_docs_fallback(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), "ctx", "rev", ""
        )
        # When no knowledge docs provided, "Internal Documents" section is omitted
        assert "Internal Documents" not in prompt

    def test_includes_company_name(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(company_name="Ramp"), "ctx", "rev"
        )
        assert "Ramp" in prompt

    def test_includes_domain(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(domain="ramp.com"), "ctx", "rev"
        )
        assert "ramp.com" in prompt

    def test_includes_region(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(region="US"), "ctx", "rev"
        )
        assert "US" in prompt

    def test_default_region_global(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), "ctx", "rev"
        )
        assert "Global" in prompt

    def test_includes_max_personas(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(max_personas=4), "ctx", "rev"
        )
        assert "4" in prompt

    def test_includes_additional_constraints(self) -> None:
        prompt = build_persona_suggester_user_prompt(
            self._make_input(additional_constraints="Focus on mid-market"), "ctx", "rev"
        )
        assert "Focus on mid-market" in prompt

    def test_truncates_company_context(self) -> None:
        long_ctx = "x " * 80_000  # 160k chars, exceeds ~15k token limit (60k chars)
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), long_ctx, "rev"
        )
        assert len(prompt) < len(long_ctx)

    def test_truncates_customer_reviews(self) -> None:
        long_rev = "y " * 80_000  # 160k chars, exceeds ~10k token limit (40k chars)
        prompt = build_persona_suggester_user_prompt(
            self._make_input(), "ctx", long_rev
        )
        assert len(prompt) < len(long_rev)


# ---------------------------------------------------------------------------
# Generator System Prompt
# ---------------------------------------------------------------------------


class TestGeneratorSystemPrompt:
    def test_non_empty(self) -> None:
        assert len(PERSONA_GENERATOR_SYSTEM_PROMPT) > 200

    def test_contains_stable_section_headers(self) -> None:
        for header in [
            "## Output Format",
            "Persona Title & Snapshot",
            "Daily Reality",
            "Core Fears",
            "Deep Motivations",
            "Trust Builders",
            "Trust Killers",
            "Critical Pain Points",
            "## Company Fit Section",
            "## General Rules",
        ]:
            assert header in PERSONA_GENERATOR_SYSTEM_PROMPT, f"Missing header: {header}"

    def test_contains_word_count_guidance(self) -> None:
        assert "300" in PERSONA_GENERATOR_SYSTEM_PROMPT
        assert "400" in PERSONA_GENERATOR_SYSTEM_PROMPT

    def test_contains_tone_instruction(self) -> None:
        assert "Professional but empathetic" in PERSONA_GENERATOR_SYSTEM_PROMPT

    def test_hub_name_set(self) -> None:
        assert GENERATOR_HUB_NAME == "research-persona-generator-system"

    def test_get_system_prompt_uses_hub_fallback(self) -> None:
        with patch("core.content_engine.prompt_registry.get_prompt") as mock_get:
            mock_get.return_value = PERSONA_GENERATOR_SYSTEM_PROMPT
            result = get_persona_generator_system_prompt()
            mock_get.assert_called_once_with(GENERATOR_HUB_NAME, PERSONA_GENERATOR_SYSTEM_PROMPT)
            assert result == PERSONA_GENERATOR_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Generator User Prompt
# ---------------------------------------------------------------------------


class TestGeneratorUserPrompt:
    def _make_input(self, **overrides: object) -> AudiencePersonaInput:
        defaults = {"company_name": "Test Co", "max_personas": 5}
        defaults.update(overrides)
        return AudiencePersonaInput(**defaults)

    def _make_brief(self, **overrides: object) -> PersonaBrief:
        defaults = {
            "brief_id": "pb-001",
            "persona_name": "Sarah",
            "tagline": "VP of Finance at mid-market SaaS",
            "description": "Manages financial ops.",
            "rationale": ["Evidence from G2", "Common title"],
        }
        defaults.update(overrides)
        return PersonaBrief(**defaults)

    def test_includes_brief_fields(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "ctx", "rev"
        )
        assert "Sarah" in prompt
        assert "VP of Finance" in prompt
        assert "Evidence from G2" in prompt

    def test_includes_company_context(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "Company overview", "rev"
        )
        assert "Company overview" in prompt

    def test_includes_customer_reviews(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "ctx", "Review data"
        )
        assert "Review data" in prompt

    def test_includes_knowledge_docs(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "ctx", "rev", "Internal docs"
        )
        assert "Internal docs" in prompt

    def test_empty_knowledge_docs_fallback(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "ctx", "rev", ""
        )
        assert "No internal documents provided" in prompt

    def test_no_revision_note(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "ctx", "rev"
        )
        assert "## Reviewer Feedback" not in prompt

    def test_revision_note_appended(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), "ctx", "rev",
            revision_note="Add more about procurement triggers",
        )
        assert "## Reviewer Feedback" in prompt
        assert "Add more about procurement triggers" in prompt

    def test_includes_company_name(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(company_name="Ramp"), "ctx", "rev"
        )
        assert "Ramp" in prompt

    def test_includes_domain(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(domain="ramp.com"), "ctx", "rev"
        )
        assert "ramp.com" in prompt

    def test_includes_additional_constraints(self) -> None:
        prompt = build_persona_generator_user_prompt(
            self._make_brief(),
            self._make_input(additional_constraints="Focus on enterprise"),
            "ctx", "rev",
        )
        assert "Focus on enterprise" in prompt

    def test_truncates_contexts(self) -> None:
        long_ctx = "x " * 80_000  # 160k chars, exceeds ~15k token limit (60k chars)
        long_rev = "y " * 80_000  # 160k chars, exceeds ~10k token limit (40k chars)
        prompt = build_persona_generator_user_prompt(
            self._make_brief(), self._make_input(), long_ctx, long_rev
        )
        assert len(prompt) < len(long_ctx) + len(long_rev)

    def test_brief_rationale_listed(self) -> None:
        brief = self._make_brief(rationale=["R1", "R2", "R3"])
        prompt = build_persona_generator_user_prompt(
            brief, self._make_input(), "ctx", "rev"
        )
        assert "R1" in prompt
        assert "R2" in prompt
        assert "R3" in prompt
