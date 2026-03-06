"""Tests for the Linker worker — link placeholder resolution."""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import pytest

from core.content_engine.prompts.linker_prompts import (
    LINKER_SYSTEM_PROMPT,
    build_linker_user_prompt,
)
from core.content_engine.workers.linker import (
    _count_external_links,
    _count_internal_links,
    _count_stats_resolved,
    link_content,
)
from core.models.content_generation import ContentBrief, ContentDraft, LinkedDraft


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_brief():
    return ContentBrief(
        brief_id="brief-001",
        title="Spend Management Guide",
        key_topics=["spend management", "expense tracking"],
    )


@pytest.fixture
def sample_draft():
    return ContentDraft(
        brief_id="brief-001",
        title="Spend Management Guide",
        markdown=(
            "# Spend Management Guide\n\n"
            "Effective spend management is critical for modern businesses. "
            "[INTERNAL-LINK: expense tracking software] can help reduce costs.\n\n"
            "According to [EXTERNAL-LINK: Gartner spend management report], "
            "organizations that implement spend management see [STAT: percentage savings].\n\n"
            "Learn more about [INTERNAL-LINK: corporate card management]."
        ),
        word_count=50,
    )


@pytest.fixture
def linked_response_text():
    return (
        "# Spend Management Guide\n\n"
        "Effective spend management is critical for modern businesses. "
        "[expense tracking software](https://ramp.com/expense-tracking) can help reduce costs.\n\n"
        "According to [Gartner spend management report](https://gartner.com/spend-2024), "
        "organizations that implement spend management see 15-25% savings [Gartner, 2024].\n\n"
        "Learn more about [corporate card management](https://ramp.com/cards)."
    )


# ---------------------------------------------------------------------------
# Prompt Tests
# ---------------------------------------------------------------------------

class TestLinkerPrompts:
    def test_system_prompt_contains_key_instructions(self):
        assert "INTERNAL-LINK" in LINKER_SYSTEM_PROMPT
        assert "EXTERNAL-LINK" in LINKER_SYSTEM_PROMPT
        assert "STAT" in LINKER_SYSTEM_PROMPT
        assert "Must NOT Do" in LINKER_SYSTEM_PROMPT

    def test_build_user_prompt_with_site_pages(self):
        prompt = build_linker_user_prompt(
            draft_markdown="# Test\n\nContent here.",
            title="Test Article",
            key_topics=["topic1"],
            company_name="Acme",
            domain="acme.com",
            site_pages=["https://acme.com/page1", "https://acme.com/page2"],
        )
        assert "https://acme.com/page1" in prompt
        assert "https://acme.com/page2" in prompt
        assert "ONLY use these URLs" in prompt

    def test_build_user_prompt_without_site_pages(self):
        prompt = build_linker_user_prompt(
            draft_markdown="# Test\n\nContent here.",
            title="Test Article",
            key_topics=["topic1"],
            company_name="Acme",
            domain="acme.com",
            site_pages=None,
        )
        assert "No site pages provided" in prompt
        assert "convert" in prompt.lower()

    def test_build_user_prompt_contains_draft(self):
        prompt = build_linker_user_prompt(
            draft_markdown="# My Draft\n\nThe content body.",
            title="My Article",
            key_topics=[],
            company_name="Test",
            domain="test.com",
        )
        assert "# My Draft" in prompt
        assert "The content body." in prompt


# ---------------------------------------------------------------------------
# Counter Tests
# ---------------------------------------------------------------------------

class TestLinkCounters:
    def test_count_internal_links(self):
        md = (
            "[page1](https://ramp.com/page1) and "
            "[page2](https://ramp.com/page2) and "
            "[external](https://example.com/page)"
        )
        assert _count_internal_links(md, "ramp.com") == 2

    def test_count_external_links(self):
        md = (
            "[page1](https://ramp.com/page1) and "
            "[ext1](https://gartner.com/report) and "
            "[ext2](https://example.com/page)"
        )
        assert _count_external_links(md, "ramp.com") == 2

    def test_count_stats_resolved(self):
        original = "We see [STAT: savings percent] and [STAT: ROI increase]."
        linked = "We see 25% savings and [STAT: ROI increase]."
        assert _count_stats_resolved(original, linked) == 1

    def test_count_stats_resolved_all(self):
        original = "[STAT: data1] and [STAT: data2]."
        linked = "50% and 75%."
        assert _count_stats_resolved(original, linked) == 2

    def test_count_stats_resolved_none(self):
        original = "[STAT: data1]."
        linked = "[STAT: data1]."
        assert _count_stats_resolved(original, linked) == 0

    def test_count_internal_links_no_links(self):
        assert _count_internal_links("No links here.", "ramp.com") == 0

    def test_count_external_links_no_links(self):
        assert _count_external_links("No links here.", "ramp.com") == 0


# ---------------------------------------------------------------------------
# Worker Tests
# ---------------------------------------------------------------------------

class TestLinkContent:
    @pytest.mark.asyncio
    async def test_graceful_no_api_key(self, sample_draft, sample_brief):
        """When PERPLEXITY_API_KEY is missing, return draft as-is."""
        with patch("core.content_engine.workers.linker.settings") as mock_settings:
            mock_settings.perplexity_api_key = None
            mock_settings.content_engine_v13_linker_model = "perplexity/sonar-pro"
            result = await link_content(
                draft=sample_draft,
                brief=sample_brief,
                company_name="Ramp",
                domain="ramp.com",
            )
        assert isinstance(result, LinkedDraft)
        assert result.markdown == sample_draft.markdown
        assert result.internal_links_added == 0
        assert result.external_links_added == 0

    @pytest.mark.asyncio
    async def test_link_content_success(
        self, sample_draft, sample_brief, linked_response_text
    ):
        """Full link resolution with mocked LLM response."""
        mock_response = AsyncMock()
        mock_response.content = linked_response_text
        mock_response.input_tokens = 500
        mock_response.output_tokens = 300
        mock_response.total_tokens = 800

        with (
            patch("core.content_engine.workers.linker.settings") as mock_settings,
            patch("core.content_engine.workers.linker.llm_call", return_value=mock_response) as mock_llm,
        ):
            mock_settings.perplexity_api_key = "test-key"
            mock_settings.content_engine_v13_linker_model = "perplexity/sonar-pro"
            result = await link_content(
                draft=sample_draft,
                brief=sample_brief,
                company_name="Ramp",
                domain="ramp.com",
                site_pages=["https://ramp.com/expense-tracking", "https://ramp.com/cards"],
            )

        assert isinstance(result, LinkedDraft)
        assert result.internal_links_added == 2
        assert result.external_links_added == 1
        assert result.stats_resolved == 1
        assert "[INTERNAL-LINK" not in result.markdown
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_content_no_site_pages(
        self, sample_draft, sample_brief, linked_response_text
    ):
        """Link resolution works when site_pages is None."""
        mock_response = AsyncMock()
        mock_response.content = linked_response_text
        mock_response.input_tokens = 500
        mock_response.output_tokens = 300
        mock_response.total_tokens = 800

        with (
            patch("core.content_engine.workers.linker.settings") as mock_settings,
            patch("core.content_engine.workers.linker.llm_call", return_value=mock_response),
        ):
            mock_settings.perplexity_api_key = "test-key"
            mock_settings.content_engine_v13_linker_model = "perplexity/sonar-pro"
            result = await link_content(
                draft=sample_draft,
                brief=sample_brief,
                company_name="Ramp",
                domain="ramp.com",
                site_pages=None,
            )

        assert isinstance(result, LinkedDraft)
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_link_content_strips_code_fences(self, sample_draft, sample_brief):
        """Code fences in response are stripped."""
        fenced = "```markdown\n# Title\n\nContent.\n```"
        mock_response = AsyncMock()
        mock_response.content = fenced
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_response.total_tokens = 150

        with (
            patch("core.content_engine.workers.linker.settings") as mock_settings,
            patch("core.content_engine.workers.linker.llm_call", return_value=mock_response),
        ):
            mock_settings.perplexity_api_key = "test-key"
            mock_settings.content_engine_v13_linker_model = "perplexity/sonar-pro"
            result = await link_content(
                draft=sample_draft,
                brief=sample_brief,
                company_name="Ramp",
                domain="ramp.com",
            )

        assert not result.markdown.startswith("```")
        assert not result.markdown.endswith("```")


# ---------------------------------------------------------------------------
# Truncation Tests
# ---------------------------------------------------------------------------


class TestLinkerTruncation:
    """Regression tests for user-prompt truncation before LLM call.

    Ensures draft markdown is truncated when it would exceed the model context
    window, preventing excessive token cost and potential API errors.
    """

    @pytest.mark.asyncio
    async def test_prompt_is_truncated_when_draft_is_very_long(self, sample_brief):
        """A very long draft must be truncated before passing to llm_call."""
        # ~700k chars = ~175k tokens — well above the 120k limit
        huge_markdown = "A " * 350_000
        huge_draft = ContentDraft(
            brief_id="brief-001",
            title="Long Draft",
            markdown=huge_markdown,
            word_count=350_000,
        )

        mock_response = AsyncMock()
        mock_response.content = "# Resolved\n\nContent."
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_response.total_tokens = 150

        with (
            patch("core.content_engine.workers.linker.settings") as mock_settings,
            patch("core.content_engine.workers.linker.llm_call", return_value=mock_response) as mock_llm,
        ):
            mock_settings.perplexity_api_key = "test-key"
            mock_settings.content_engine_v13_linker_model = "perplexity/sonar-pro"
            await link_content(
                draft=huge_draft,
                brief=sample_brief,
                company_name="Ramp",
                domain="ramp.com",
            )

        mock_llm.assert_called_once()
        called_user_prompt = mock_llm.call_args[1]["user"]
        # Truncation marker must be present
        assert "[... truncated" in called_user_prompt
        # Prompt must be within the truncation budget (120k tokens * 4 chars + small overhead)
        assert len(called_user_prompt) < 120_000 * 4 + 500

    @pytest.mark.asyncio
    async def test_prompt_not_truncated_when_draft_is_short(self, sample_draft, sample_brief):
        """A normal-length draft must pass through untruncated."""
        mock_response = AsyncMock()
        mock_response.content = "# Title\n\nResolved."
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_response.total_tokens = 150

        with (
            patch("core.content_engine.workers.linker.settings") as mock_settings,
            patch("core.content_engine.workers.linker.llm_call", return_value=mock_response) as mock_llm,
        ):
            mock_settings.perplexity_api_key = "test-key"
            mock_settings.content_engine_v13_linker_model = "perplexity/sonar-pro"
            await link_content(
                draft=sample_draft,
                brief=sample_brief,
                company_name="Ramp",
                domain="ramp.com",
            )

        mock_llm.assert_called_once()
        called_user_prompt = mock_llm.call_args[1]["user"]
        # No truncation marker for a short draft
        assert "[... truncated" not in called_user_prompt
        # The original draft text must be fully present
        assert sample_draft.markdown in called_user_prompt
