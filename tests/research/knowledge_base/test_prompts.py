"""Tests for Knowledge Base research prompts — Hub getters, user prompt builders, naming."""
from __future__ import annotations

import importlib
from typing import Dict

import pytest

from core.models.knowledge_base import KnowledgeBaseInput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def kb_input() -> KnowledgeBaseInput:
    return KnowledgeBaseInput(
        company_name="Test Co",
        domain="test.co",
        company_slug="test-co",
        language="en",
        region="US",
        additional_constraints="Focus on B2B SaaS",
    )


@pytest.fixture()
def upstream_docs() -> Dict[str, str]:
    return {
        "company_overview": "# Company Overview\n\nTest Co builds enterprise tools.",
        "customer_reviews": "# Customer Reviews\n\nUsers love the simplicity.",
        "competitor_registry": "# Competitor Registry\n\n- Rival Inc\n- Alt Corp",
        "weakness_analysis": "# Weakness Analysis\n\nRival Inc has poor docs.",
    }


# ---------------------------------------------------------------------------
# Prompt Getters — return non-empty local fallback when Hub disabled
# ---------------------------------------------------------------------------

class TestPromptGetters:
    """Each getter returns a non-empty string (local fallback, Hub disabled by default)."""

    def test_company_overview_getter(self) -> None:
        from core.research.prompts.company_overview import get_company_overview_system_prompt

        prompt = get_company_overview_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_customer_reviews_getter(self) -> None:
        from core.research.prompts.customer_reviews import get_customer_reviews_system_prompt

        prompt = get_customer_reviews_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_competitor_scanner_getter(self) -> None:
        from core.research.prompts.competitor_scanner import get_competitor_scanner_system_prompt

        prompt = get_competitor_scanner_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_weakness_analyst_getter(self) -> None:
        from core.research.prompts.weakness_analyst import get_weakness_analyst_system_prompt

        prompt = get_weakness_analyst_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_brand_perception_getter(self) -> None:
        from core.research.prompts.brand_perception import get_brand_perception_system_prompt

        prompt = get_brand_perception_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_synthesis_getter(self) -> None:
        from core.research.prompts.synthesis import get_synthesis_system_prompt

        prompt = get_synthesis_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50


# ---------------------------------------------------------------------------
# User Prompt Builders — contain key data from input
# ---------------------------------------------------------------------------

class TestUserPromptBuilders:
    """Each builder returns a string containing expected data."""

    def test_company_overview_includes_company_name(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.company_overview import build_company_overview_user_prompt

        prompt = build_company_overview_user_prompt(kb_input)
        assert "Test Co" in prompt
        assert "test.co" in prompt

    def test_customer_reviews_includes_domain(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.customer_reviews import build_customer_reviews_user_prompt

        prompt = build_customer_reviews_user_prompt(kb_input)
        assert "Test Co" in prompt
        assert "test.co" in prompt

    def test_competitor_scanner_includes_upstream_context(
        self, kb_input: KnowledgeBaseInput
    ) -> None:
        from core.research.prompts.competitor_scanner import build_competitor_scanner_user_prompt

        company_overview_md = "# Company Overview\n\nTest Co builds enterprise tools."
        prompt = build_competitor_scanner_user_prompt(kb_input, company_overview_md)
        assert "Test Co" in prompt
        assert "enterprise tools" in prompt

    def test_weakness_analyst_includes_both_upstream_docs(
        self, kb_input: KnowledgeBaseInput
    ) -> None:
        from core.research.prompts.weakness_analyst import build_weakness_analyst_user_prompt

        company_md = "# Company Overview\n\nTest Co details."
        competitor_md = "# Competitors\n\n- Rival Inc"
        prompt = build_weakness_analyst_user_prompt(kb_input, company_md, competitor_md)
        assert "Test Co" in prompt
        assert "Rival Inc" in prompt

    def test_brand_perception_includes_all_upstream_docs(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str]
    ) -> None:
        from core.research.prompts.brand_perception import build_brand_perception_user_prompt

        prompt = build_brand_perception_user_prompt(kb_input, upstream_docs)
        assert "Test Co" in prompt
        assert "Company Overview" in prompt
        assert "Customer Reviews" in prompt
        assert "Competitor Registry" in prompt
        assert "Weakness Analysis" in prompt

    def test_synthesis_includes_available_and_missing(
        self, kb_input: KnowledgeBaseInput
    ) -> None:
        from core.research.prompts.synthesis import build_synthesis_user_prompt

        available = {
            "company_overview": "# Overview\n\nContent.",
            "customer_reviews": "# Reviews\n\nContent.",
            "competitor_registry": "# Competitors\n\nContent.",
        }
        missing = ["weakness_analysis", "brand_perception"]
        prompt = build_synthesis_user_prompt(kb_input, available, missing)
        assert "Test Co" in prompt
        assert "Weakness Analysis" in prompt
        assert "Brand Perception" in prompt


# ---------------------------------------------------------------------------
# Revision Note Injection — all 6 builders append feedback section
# ---------------------------------------------------------------------------

class TestRevisionNoteInjection:
    """Each builder appends ## Reviewer Feedback when revision_note is provided."""

    def test_company_overview_revision_note(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.company_overview import build_company_overview_user_prompt

        prompt = build_company_overview_user_prompt(kb_input, revision_note="Add more funding data")
        assert "## Reviewer Feedback" in prompt
        assert "Add more funding data" in prompt

    def test_company_overview_no_revision_note(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.company_overview import build_company_overview_user_prompt

        prompt = build_company_overview_user_prompt(kb_input)
        assert "## Reviewer Feedback" not in prompt

    def test_customer_reviews_revision_note(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.customer_reviews import build_customer_reviews_user_prompt

        prompt = build_customer_reviews_user_prompt(kb_input, revision_note="Include G2 reviews")
        assert "## Reviewer Feedback" in prompt
        assert "Include G2 reviews" in prompt

    def test_competitor_scanner_revision_note(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.competitor_scanner import build_competitor_scanner_user_prompt

        prompt = build_competitor_scanner_user_prompt(
            kb_input, "# Overview", revision_note="Add pricing comparison",
        )
        assert "## Reviewer Feedback" in prompt
        assert "Add pricing comparison" in prompt

    def test_weakness_analyst_revision_note(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.weakness_analyst import build_weakness_analyst_user_prompt

        prompt = build_weakness_analyst_user_prompt(
            kb_input, "# Overview", "# Competitors", revision_note="More specific examples",
        )
        assert "## Reviewer Feedback" in prompt
        assert "More specific examples" in prompt

    def test_brand_perception_revision_note(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.prompts.brand_perception import build_brand_perception_user_prompt

        prompt = build_brand_perception_user_prompt(
            kb_input, upstream_docs, revision_note="Focus on social media sentiment",
        )
        assert "## Reviewer Feedback" in prompt
        assert "Focus on social media sentiment" in prompt

    def test_synthesis_revision_note(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.prompts.synthesis import build_synthesis_user_prompt

        available = {"company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3"}
        prompt = build_synthesis_user_prompt(
            kb_input, available, [], revision_note="Strengthen recommendations section",
        )
        assert "## Reviewer Feedback" in prompt
        assert "Strengthen recommendations section" in prompt


# ---------------------------------------------------------------------------
# Hub Names — naming convention and uniqueness
# ---------------------------------------------------------------------------

_PROMPT_MODULES = [
    "core.research.prompts.company_overview",
    "core.research.prompts.customer_reviews",
    "core.research.prompts.competitor_scanner",
    "core.research.prompts.weakness_analyst",
    "core.research.prompts.brand_perception",
    "core.research.prompts.synthesis",
]

_ALL_HUB_MODULES = _PROMPT_MODULES  # includes delta hub name via synthesis module


class TestHubNames:
    """Each prompt file has a _HUB_NAME following the naming convention."""

    def test_hub_names_unique(self) -> None:
        names = []
        for mod_path in _PROMPT_MODULES:
            mod = importlib.import_module(mod_path)
            names.append(mod._HUB_NAME)
        assert len(names) == len(set(names)), f"Duplicate hub names: {names}"

    def test_hub_names_follow_convention(self) -> None:
        for mod_path in _PROMPT_MODULES:
            mod = importlib.import_module(mod_path)
            name = mod._HUB_NAME
            assert name.startswith("research-"), f"{mod_path}: {name} doesn't start with 'research-'"
            assert name.endswith("-system"), f"{mod_path}: {name} doesn't end with '-system'"

    def test_all_files_have_hub_name(self) -> None:
        for mod_path in _PROMPT_MODULES:
            mod = importlib.import_module(mod_path)
            assert hasattr(mod, "_HUB_NAME"), f"{mod_path} missing _HUB_NAME"
            assert isinstance(mod._HUB_NAME, str)
            assert len(mod._HUB_NAME) > 0


# ---------------------------------------------------------------------------
# Delta Synthesis Prompt
# ---------------------------------------------------------------------------


class TestDeltaSynthesisPrompt:
    """Tests for the incremental/delta synthesis prompt builder."""

    def test_delta_system_prompt_returns_string(self) -> None:
        from core.research.prompts.synthesis import get_delta_synthesis_system_prompt

        prompt = get_delta_synthesis_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "UPDATING" in prompt

    def test_delta_user_prompt_includes_previous_path(
        self, kb_input: KnowledgeBaseInput
    ) -> None:
        from core.research.prompts.synthesis import build_delta_synthesis_user_prompt

        prompt = build_delta_synthesis_user_prompt(
            kb_input,
            previous_synthesis_path="synthesis/v2.md",
            changed_docs={"customer_reviews": "customer_reviews/v3.md"},
            unchanged_docs={"company_overview": "company_overview/v1.md"},
            missing_docs=[],
        )
        assert "synthesis/v2.md" in prompt

    def test_delta_user_prompt_includes_changed_and_unchanged(
        self, kb_input: KnowledgeBaseInput
    ) -> None:
        from core.research.prompts.synthesis import build_delta_synthesis_user_prompt

        prompt = build_delta_synthesis_user_prompt(
            kb_input,
            previous_synthesis_path="synthesis/v1.md",
            changed_docs={
                "customer_reviews": "customer_reviews/v3.md",
                "brand_perception": "brand_perception/v2.md",
            },
            unchanged_docs={"company_overview": "company_overview/v1.md"},
            missing_docs=["weakness_analysis"],
        )
        assert "Changed Documents" in prompt
        assert "customer_reviews/v3.md" in prompt
        assert "brand_perception/v2.md" in prompt
        assert "Unchanged Documents" in prompt
        assert "company_overview/v1.md" in prompt
        assert "Weakness Analysis" in prompt

    def test_delta_user_prompt_with_revision_note(
        self, kb_input: KnowledgeBaseInput
    ) -> None:
        from core.research.prompts.synthesis import build_delta_synthesis_user_prompt

        prompt = build_delta_synthesis_user_prompt(
            kb_input,
            previous_synthesis_path="synthesis/v1.md",
            changed_docs={"customer_reviews": "customer_reviews/v2.md"},
            unchanged_docs={},
            missing_docs=[],
            revision_note="Expand the competitive analysis section",
        )
        assert "## Reviewer Feedback" in prompt
        assert "Expand the competitive analysis section" in prompt

    def test_delta_hub_name_unique(self) -> None:
        """Delta hub name must not collide with any other prompt hub name."""
        from core.research.prompts.synthesis import _DELTA_HUB_NAME

        all_names = []
        for mod_path in _ALL_HUB_MODULES:
            mod = importlib.import_module(mod_path)
            all_names.append(mod._HUB_NAME)
        assert _DELTA_HUB_NAME not in all_names
