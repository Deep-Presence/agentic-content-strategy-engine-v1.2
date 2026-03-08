"""Tests for Voice Style Guide agents — mocked LLM calls.

Covers:
- Author Discovery (LiteLLM → Gemini Flash)
  - Happy path with valid JSON
  - Retry on malformed output
  - Timeout handling
  - Deduplication
- Author Research (Perplexity)
  - Happy path
  - Timeout / API error
- Voice Synthesis (LiteLLM → Claude Sonnet)
  - Happy path
  - Empty output on error
- Validation helpers
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

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
    )


@pytest.fixture()
def company_context_md() -> str:
    return "# Ramp\n\nRamp is a corporate card platform."


@pytest.fixture()
def persona_mds() -> list[str]:
    return ["# Sarah\nVP Finance", "# Marcus\nCFO"]


@pytest.fixture()
def author_brief() -> AuthorBrief:
    return AuthorBrief(
        author_id="morgan-housel",
        name="Morgan Housel",
        description="Financial writer.",
        famous_works=["The Psychology of Money"],
        resonance_rationale="Great fit for finance audience.",
        work_persona_mapping=[
            WorkPersonaMapping(
                work_title="The Psychology of Money",
                persona_id="sarah",
                persona_name="Sarah",
                relevance="Finance leaders relate.",
            ),
        ],
    )


def _mock_litellm_response(content: str) -> Any:
    """Create a mock LiteLLM response object."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=200, total_tokens=300)
    return SimpleNamespace(choices=[choice], usage=usage, model="test-model")


VALID_AUTHORS_JSON = json.dumps([
    {
        "name": "Morgan Housel",
        "description": "Financial writer known for accessible storytelling.",
        "famous_works": ["The Psychology of Money", "Same as Ever"],
        "resonance_rationale": "His clear, story-driven style resonates with finance personas.",
        "work_persona_mapping": [
            {
                "work_title": "The Psychology of Money",
                "persona_id": "sarah",
                "persona_name": "Sarah",
                "relevance": "Finance leaders relate to behavioral insights.",
            }
        ],
    },
    {
        "name": "Ann Handley",
        "description": "Marketing author focused on content creation.",
        "famous_works": ["Everybody Writes"],
        "resonance_rationale": "Her practical writing advice suits B2B content teams.",
    },
    {
        "name": "Seth Godin",
        "description": "Marketing guru known for concise, punchy writing.",
        "famous_works": ["Purple Cow", "This is Marketing"],
        "resonance_rationale": "His brevity and clarity fit fast-paced fintech audiences.",
    },
])


# ── Validation Helpers ────────────────────────────────────────────────


class TestValidationHelpers:
    """Tests for _validate_author_briefs and helpers."""

    def test_validate_valid_briefs(self) -> None:
        from core.research.voice_style_guide.agents import _validate_author_briefs

        raw = json.loads(VALID_AUTHORS_JSON)
        valid, errors = _validate_author_briefs(raw, max_authors=3)
        assert len(valid) == 3
        assert len(errors) == 0
        assert valid[0].name == "Morgan Housel"
        assert valid[0].author_id == "morgan-housel"
        assert valid[0].source == "agent"

    def test_validate_deduplicates_by_name(self) -> None:
        from core.research.voice_style_guide.agents import _validate_author_briefs

        raw = [
            {"name": "Morgan Housel", "description": "v1"},
            {"name": "Morgan Housel", "description": "v2"},  # duplicate
            {"name": "Ann Handley", "description": "v3"},
        ]
        valid, errors = _validate_author_briefs(raw, max_authors=3)
        assert len(valid) == 2
        assert any("duplicate" in e for e in errors)

    def test_validate_missing_name(self) -> None:
        from core.research.voice_style_guide.agents import _validate_author_briefs

        raw = [{"description": "no name"}, {"name": "Valid", "description": "ok"}]
        valid, errors = _validate_author_briefs(raw, max_authors=3)
        assert len(valid) == 1
        assert any("missing" in e for e in errors)

    def test_validate_non_dict(self) -> None:
        from core.research.voice_style_guide.agents import _validate_author_briefs

        raw = ["not a dict", {"name": "Valid", "description": "ok"}]
        valid, errors = _validate_author_briefs(raw, max_authors=3)
        assert len(valid) == 1
        assert any("not a dict" in e for e in errors)

    def test_validate_truncates_to_max(self) -> None:
        from core.research.voice_style_guide.agents import _validate_author_briefs

        raw = [
            {"name": f"Author {i}", "description": f"desc {i}"}
            for i in range(5)
        ]
        valid, errors = _validate_author_briefs(raw, max_authors=2)
        assert len(valid) == 2

    def test_slugify_name(self) -> None:
        from core.research.voice_style_guide.agents import _slugify_name

        assert _slugify_name("Morgan Housel") == "morgan-housel"
        assert _slugify_name("Ann Handley") == "ann-handley"
        assert _slugify_name("  J.K. Rowling  ") == "j-k-rowling"
        assert _slugify_name("") == "unknown"

    def test_strip_code_fences(self) -> None:
        from core.research.voice_style_guide.agents import _strip_code_fences

        fenced = '```json\n[{"name": "test"}]\n```'
        assert _strip_code_fences(fenced) == '[{"name": "test"}]'

    def test_parse_json_array_tolerant(self) -> None:
        from core.research.voice_style_guide.agents import _parse_json_array

        # Normal JSON
        assert len(_parse_json_array('[{"a": 1}]')) == 1
        # Wrapped in text
        assert len(_parse_json_array('Here is: [{"a": 1}] done')) == 1
        # Invalid
        assert _parse_json_array("not json") == []


# ── Author Discovery Agent ───────────────────────────────────────────


class TestAuthorDiscovery:
    """Tests for run_author_discovery()."""

    @pytest.mark.asyncio
    async def test_happy_path(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        mock_response = _mock_litellm_response(VALID_AUTHORS_JSON)

        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            briefs, elapsed = await asyncio.wait_for(
                _import_and_run_discovery(vsg_input, company_context_md, persona_mds),
                timeout=10,
            )

        assert len(briefs) == 3
        assert briefs[0].name == "Morgan Housel"
        assert briefs[0].author_id == "morgan-housel"
        assert elapsed > 0
        mock_litellm.acompletion.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_malformed_json(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        """First call returns invalid JSON, retry returns valid."""
        bad_response = _mock_litellm_response("not valid json")
        good_response = _mock_litellm_response(VALID_AUTHORS_JSON)

        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=[bad_response, good_response])
            briefs, elapsed = await asyncio.wait_for(
                _import_and_run_discovery(vsg_input, company_context_md, persona_mds),
                timeout=10,
            )

        assert len(briefs) == 3
        assert mock_litellm.acompletion.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=asyncio.TimeoutError())
            briefs, elapsed = await asyncio.wait_for(
                _import_and_run_discovery(vsg_input, company_context_md, persona_mds),
                timeout=10,
            )

        assert briefs == []
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=RuntimeError("API key invalid"))
            briefs, elapsed = await asyncio.wait_for(
                _import_and_run_discovery(vsg_input, company_context_md, persona_mds),
                timeout=10,
            )

        assert briefs == []


# ── Author Research Agent ─────────────────────────────────────────────


class TestAuthorResearch:
    """Tests for run_author_research()."""

    @pytest.mark.asyncio
    async def test_happy_path(
        self, author_brief: AuthorBrief, vsg_input: VoiceStyleGuideInput, company_context_md: str,
    ) -> None:
        mock_md = "# Morgan Housel Style Analysis\n\n## Voice & Tone\nClear, story-driven..."

        with patch(
            "core.research.voice_style_guide.agents.perplexity_client.research",
            return_value=mock_md,
        ):
            result = await asyncio.wait_for(
                _import_and_run_research(author_brief, vsg_input, company_context_md, "Persona summaries"),
                timeout=10,
            )

        assert result.author_id == "morgan-housel"
        assert result.name == "Morgan Housel"
        assert result.content_md == mock_md
        assert result.word_count > 0
        assert result.error is None
        assert result.execution_time_s > 0

    @pytest.mark.asyncio
    async def test_timeout_returns_error(
        self, author_brief: AuthorBrief, vsg_input: VoiceStyleGuideInput, company_context_md: str,
    ) -> None:
        with patch(
            "core.research.voice_style_guide.agents.perplexity_client.research",
            side_effect=RuntimeError("Timeout"),
        ), patch(
            "core.research.voice_style_guide.agents.asyncio.to_thread",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await asyncio.wait_for(
                _import_and_run_research(author_brief, vsg_input, company_context_md, "Summaries"),
                timeout=10,
            )

        assert result.error is not None
        assert "Timeout" in result.error
        assert result.content_md == ""

    @pytest.mark.asyncio
    async def test_api_error_returns_error(
        self, author_brief: AuthorBrief, vsg_input: VoiceStyleGuideInput, company_context_md: str,
    ) -> None:
        with patch(
            "core.research.voice_style_guide.agents.perplexity_client.research",
            side_effect=RuntimeError("API rate limit"),
        ), patch(
            "core.research.voice_style_guide.agents.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=RuntimeError("API rate limit"),
        ):
            result = await asyncio.wait_for(
                _import_and_run_research(author_brief, vsg_input, company_context_md, "Summaries"),
                timeout=10,
            )

        assert result.error is not None
        assert "rate limit" in result.error


# ── Voice Synthesis Agent ─────────────────────────────────────────────


class TestVoiceSynthesis:
    """Tests for run_voice_synthesis()."""

    @pytest.mark.asyncio
    async def test_happy_path(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        guide_content = "# Voice Style Guide for Ramp\n\n## Voice & Tone\nConfident, clear..."
        mock_response = _mock_litellm_response(guide_content)

        author_mds = {
            "morgan-housel": "# Morgan Housel analysis...",
            "ann-handley": "# Ann Handley analysis...",
        }

        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)
            guide_md, elapsed = await asyncio.wait_for(
                _import_and_run_synthesis(author_mds, company_context_md, persona_mds, vsg_input),
                timeout=10,
            )

        assert "Voice Style Guide" in guide_md
        assert elapsed > 0
        mock_litellm.acompletion.assert_called_once()

        # Verify max_tokens=8192 was passed
        call_kwargs = mock_litellm.acompletion.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 8192

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=asyncio.TimeoutError())
            guide_md, elapsed = await asyncio.wait_for(
                _import_and_run_synthesis({}, company_context_md, persona_mds, vsg_input),
                timeout=10,
            )

        assert guide_md == ""
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        with patch("core.research.voice_style_guide.agents.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(side_effect=RuntimeError("Model not found"))
            guide_md, elapsed = await asyncio.wait_for(
                _import_and_run_synthesis({}, company_context_md, persona_mds, vsg_input),
                timeout=10,
            )

        assert guide_md == ""


# ── Import helpers (to avoid import-time LiteLLM issues) ─────────────


async def _import_and_run_discovery(
    input_data: VoiceStyleGuideInput,
    company_context_md: str,
    persona_mds: list[str],
) -> Any:
    from core.research.voice_style_guide.agents import run_author_discovery

    return await run_author_discovery(input_data, company_context_md, persona_mds)


async def _import_and_run_research(
    brief: AuthorBrief,
    input_data: VoiceStyleGuideInput,
    company_context_md: str,
    persona_summaries: str,
) -> Any:
    from core.research.voice_style_guide.agents import run_author_research

    return await run_author_research(brief, input_data, company_context_md, persona_summaries)


async def _import_and_run_synthesis(
    author_mds: Dict[str, str],
    company_context_md: str,
    persona_mds: list[str],
    input_data: VoiceStyleGuideInput,
) -> Any:
    from core.research.voice_style_guide.agents import run_voice_synthesis

    return await run_voice_synthesis(author_mds, company_context_md, persona_mds, input_data)
