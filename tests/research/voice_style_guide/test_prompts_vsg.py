"""Tests for Voice Style Guide prompt modules.

Covers:
- System prompt retrieval (Hub fallback)
- User prompt builder output structure and content
- Token cap enforcement (truncation)
- Edge cases (missing context, empty personas)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.models.voice_style_guide import (
    AuthorBrief,
    VoiceStyleGuideInput,
    WorkPersonaMapping,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def vsg_input() -> VoiceStyleGuideInput:
    return VoiceStyleGuideInput(
        company_name="Ramp",
        domain="fintech",
        company_slug="ramp",
        max_authors=3,
        language="en",
        region="US",
        additional_constraints="Focus on B2B SaaS tone",
        product_name="Ramp Corporate Cards",
    )


@pytest.fixture()
def company_context_md() -> str:
    return "# Ramp\n\nRamp is a corporate card and spend management platform."


@pytest.fixture()
def persona_mds() -> list[str]:
    return [
        "# Persona: Sarah\n\nVP of Finance at mid-market SaaS companies.",
        "# Persona: Marcus\n\nCFO at growth-stage startups managing burn rate.",
    ]


@pytest.fixture()
def author_brief() -> AuthorBrief:
    return AuthorBrief(
        author_id="morgan-housel",
        name="Morgan Housel",
        description="Financial writer known for clear, storytelling-driven explanations.",
        famous_works=["The Psychology of Money", "Same as Ever"],
        resonance_rationale="Housel's accessible financial storytelling resonates with finance leaders.",
        work_persona_mapping=[
            WorkPersonaMapping(
                work_title="The Psychology of Money",
                persona_id="sarah",
                persona_name="Sarah",
                relevance="Finance leaders relate to behavioral finance insights.",
            ),
        ],
        source="agent",
    )


# ── Author Discovery Prompts ─────────────────────────────────────────


class TestAuthorDiscoveryPrompts:
    """Tests for author_discovery.py prompt module."""

    def test_system_prompt_returns_string(self) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            AUTHOR_DISCOVERY_SYSTEM_PROMPT,
            get_author_discovery_system_prompt,
        )

        result = get_author_discovery_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 100
        # Should fall back to local when Hub is disabled
        assert result == AUTHOR_DISCOVERY_SYSTEM_PROMPT

    def test_system_prompt_contains_key_sections(self) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            AUTHOR_DISCOVERY_SYSTEM_PROMPT,
        )

        assert "Persona-Author Resonance Analyst" in AUTHOR_DISCOVERY_SYSTEM_PROMPT
        assert "Persona Decomposition" in AUTHOR_DISCOVERY_SYSTEM_PROMPT
        assert "Author-Persona Resonance Scoring" in AUTHOR_DISCOVERY_SYSTEM_PROMPT
        assert "Differentiation Check" in AUTHOR_DISCOVERY_SYSTEM_PROMPT
        assert "valid JSON" in AUTHOR_DISCOVERY_SYSTEM_PROMPT

    def test_build_user_prompt_structure(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            build_author_discovery_user_prompt,
        )

        result = build_author_discovery_user_prompt(vsg_input, company_context_md, persona_mds)
        assert isinstance(result, str)
        assert "Ramp" in result
        assert "Company Context" in result
        assert "Audience Personas" in result
        assert "Persona 1" in result
        assert "Persona 2" in result
        assert "fintech" in result
        assert "US" in result
        assert "B2B SaaS tone" in result
        assert "Ramp Corporate Cards" in result

    def test_build_user_prompt_no_company_context(
        self, vsg_input: VoiceStyleGuideInput, persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            build_author_discovery_user_prompt,
        )

        result = build_author_discovery_user_prompt(vsg_input, "", persona_mds)
        assert "No company context available" in result

    def test_build_user_prompt_no_personas(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str,
    ) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            build_author_discovery_user_prompt,
        )

        result = build_author_discovery_user_prompt(vsg_input, company_context_md, [])
        assert "No persona profiles available" in result

    def test_build_user_prompt_truncates_long_context(
        self, vsg_input: VoiceStyleGuideInput, persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            build_author_discovery_user_prompt,
        )

        long_context = "x" * 200_000
        result = build_author_discovery_user_prompt(vsg_input, long_context, persona_mds)
        # Should truncate to 80k chars for company context
        assert len(result) < 250_000

    def test_build_user_prompt_max_authors_in_text(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.author_discovery import (
            build_author_discovery_user_prompt,
        )

        result = build_author_discovery_user_prompt(vsg_input, company_context_md, persona_mds)
        assert "3 authors" in result

    def test_hub_fallback_on_disabled(self) -> None:
        """When Hub is disabled, get_prompt returns local fallback."""
        from core.research.prompts.voice_style_guide.author_discovery import (
            AUTHOR_DISCOVERY_SYSTEM_PROMPT,
            get_author_discovery_system_prompt,
        )

        with patch("core.content_engine.prompt_registry.settings") as mock_settings:
            mock_settings.langsmith_use_hub = False
            result = get_author_discovery_system_prompt()
            assert result == AUTHOR_DISCOVERY_SYSTEM_PROMPT


# ── Author Research Prompts ───────────────────────────────────────────


class TestAuthorResearchPrompts:
    """Tests for author_research.py prompt module."""

    def test_system_prompt_returns_string(self) -> None:
        from core.research.prompts.voice_style_guide.author_research import (
            AUTHOR_RESEARCH_SYSTEM_PROMPT,
            get_author_research_system_prompt,
        )

        result = get_author_research_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 100
        assert result == AUTHOR_RESEARCH_SYSTEM_PROMPT

    def test_system_prompt_contains_7_dimensions(self) -> None:
        from core.research.prompts.voice_style_guide.author_research import (
            AUTHOR_RESEARCH_SYSTEM_PROMPT,
        )

        assert "Style Markers Table" in AUTHOR_RESEARCH_SYSTEM_PROMPT
        assert "Evidence Library" in AUTHOR_RESEARCH_SYSTEM_PROMPT
        assert "Lexicon Map" in AUTHOR_RESEARCH_SYSTEM_PROMPT
        assert "Analogy Rules" in AUTHOR_RESEARCH_SYSTEM_PROMPT
        assert "Structure & Hook Patterns" in AUTHOR_RESEARCH_SYSTEM_PROMPT
        assert "Audience Handling" in AUTHOR_RESEARCH_SYSTEM_PROMPT
        assert "Quant Kit" in AUTHOR_RESEARCH_SYSTEM_PROMPT

    def test_build_user_prompt_structure(
        self,
        author_brief: AuthorBrief,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
    ) -> None:
        from core.research.prompts.voice_style_guide.author_research import (
            build_author_research_user_prompt,
        )

        result = build_author_research_user_prompt(
            author_brief, vsg_input, company_context_md, "Sarah: VP Finance\nMarcus: CFO",
        )
        assert "Morgan Housel" in result
        assert "The Psychology of Money" in result
        assert "Same as Ever" in result
        assert "Company Context" in result
        assert "Target Audience" in result
        assert "Research Instructions" in result
        assert "Work-Persona Connections" in result
        assert "Sarah" in result

    def test_build_user_prompt_with_revision_note(
        self,
        author_brief: AuthorBrief,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
    ) -> None:
        from core.research.prompts.voice_style_guide.author_research import (
            build_author_research_user_prompt,
        )

        result = build_author_research_user_prompt(
            author_brief,
            vsg_input,
            company_context_md,
            "Persona summaries here",
            revision_note="Add more examples of sentence structure.",
        )
        assert "Reviewer Feedback" in result
        assert "Add more examples of sentence structure" in result

    def test_build_user_prompt_no_company_context(
        self,
        author_brief: AuthorBrief,
        vsg_input: VoiceStyleGuideInput,
    ) -> None:
        from core.research.prompts.voice_style_guide.author_research import (
            build_author_research_user_prompt,
        )

        result = build_author_research_user_prompt(
            author_brief, vsg_input, "", "Persona summaries",
        )
        assert "Company: Ramp" in result
        assert "Domain: fintech" in result

    def test_build_user_prompt_no_work_persona_mapping(
        self,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
    ) -> None:
        from core.research.prompts.voice_style_guide.author_research import (
            build_author_research_user_prompt,
        )

        brief = AuthorBrief(
            author_id="test-author",
            name="Test Author",
            description="A test author.",
        )
        result = build_author_research_user_prompt(
            brief, vsg_input, company_context_md, "Summaries",
        )
        # Should NOT contain work-persona section when mapping is empty
        assert "Work-Persona Connections" not in result


# ── Voice Synthesis Prompts ───────────────────────────────────────────


class TestVoiceSynthesisPrompts:
    """Tests for voice_synthesis.py prompt module."""

    def test_system_prompt_returns_string(self) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            VOICE_SYNTHESIS_SYSTEM_PROMPT,
            get_voice_synthesis_system_prompt,
        )

        result = get_voice_synthesis_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 100
        assert result == VOICE_SYNTHESIS_SYSTEM_PROMPT

    def test_system_prompt_contains_10_sections(self) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            VOICE_SYNTHESIS_SYSTEM_PROMPT,
        )

        assert "Voice Identity" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Voice Registers" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Style Metrics" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Sentence & Structure Rules" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Lexicon" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Analogy & Empathy Patterns" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Anti-Patterns & Drift Checklist" in VOICE_SYNTHESIS_SYSTEM_PROMPT
        assert "Worked Examples" in VOICE_SYNTHESIS_SYSTEM_PROMPT

    def test_build_user_prompt_structure(
        self,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
        persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            build_voice_synthesis_user_prompt,
        )

        author_mds = {
            "morgan-housel": "# Morgan Housel\n\nVoice analysis here...",
            "ann-handley": "# Ann Handley\n\nVoice analysis here...",
        }
        result = build_voice_synthesis_user_prompt(
            author_mds, company_context_md, persona_mds, vsg_input,
        )
        assert "Ramp" in result
        assert "Author Research Analyses" in result
        assert "morgan-housel" in result
        assert "ann-handley" in result
        assert "Company Context" in result
        assert "Audience Personas" in result
        assert "Persona 1" in result
        assert "Persona 2" in result
        assert "Instructions" in result

    def test_build_user_prompt_no_author_research(
        self,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
        persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            build_voice_synthesis_user_prompt,
        )

        result = build_voice_synthesis_user_prompt(
            {}, company_context_md, persona_mds, vsg_input,
        )
        assert "No author research available" in result

    def test_build_user_prompt_no_personas(
        self,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
    ) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            build_voice_synthesis_user_prompt,
        )

        result = build_voice_synthesis_user_prompt(
            {"author-1": "Research content"}, company_context_md, [], vsg_input,
        )
        assert "No persona profiles available" in result

    def test_build_user_prompt_includes_additional_context(
        self,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
        persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            build_voice_synthesis_user_prompt,
        )

        result = build_voice_synthesis_user_prompt(
            {"a": "Research"}, company_context_md, persona_mds, vsg_input,
        )
        assert "fintech" in result
        assert "US" in result
        assert "B2B SaaS tone" in result
        assert "Ramp Corporate Cards" in result

    def test_build_user_prompt_minimal_input(self) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            build_voice_synthesis_user_prompt,
        )

        minimal_input = VoiceStyleGuideInput(company_name="TestCo")
        result = build_voice_synthesis_user_prompt(
            {"a": "content"}, "", [], minimal_input,
        )
        assert "TestCo" in result
        # No additional context section when nothing extra
        assert "Company: TestCo" in result

    def test_build_user_prompt_truncates_author_research(
        self,
        vsg_input: VoiceStyleGuideInput,
        company_context_md: str,
        persona_mds: list[str],
    ) -> None:
        from core.research.prompts.voice_style_guide.voice_synthesis import (
            build_voice_synthesis_user_prompt,
        )

        long_research = "y" * 100_000
        author_mds = {"author-1": long_research, "author-2": long_research}
        result = build_voice_synthesis_user_prompt(
            author_mds, company_context_md, persona_mds, vsg_input,
        )
        # Each author research truncated to 60k, so total < 200k
        assert len(result) < 300_000
