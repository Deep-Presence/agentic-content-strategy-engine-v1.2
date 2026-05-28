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

    def test_parse_json_array_empty_text(self) -> None:
        from core.research.voice_style_guide.agents import _parse_json_array

        assert _parse_json_array("") == []
        assert _parse_json_array("   ") == []
        assert _parse_json_array(None) == []  # type: ignore[arg-type]

    def test_parse_json_array_error_object(self) -> None:
        from core.research.voice_style_guide.agents import _parse_json_array

        error_json = json.dumps({"error": True, "error_type": "insufficient_input", "message": "too thin"})
        assert _parse_json_array(error_json) == []

    # ── Per-persona schema (new prompt format) ──

    def test_parse_json_array_per_persona_schema(self) -> None:
        """New per-persona schema: {"personas": [{"recommended_authors": [...]}]}."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({
            "personas": [
                {
                    "persona_title": "VP Finance",
                    "recommended_authors": [
                        {
                            "author_name": "Morgan Housel",
                            "bio": "Financial writer.",
                            "resonance_rationale": "Story-driven style.",
                            "key_works": [{"title": "Psychology of Money", "type": "book", "relevance": "relevant"}],
                        },
                        {
                            "author_name": "Ann Handley",
                            "bio": "Content marketing expert.",
                            "resonance_rationale": "Practical writing advice.",
                            "key_works": [{"title": "Everybody Writes", "type": "book", "relevance": "relevant"}],
                        },
                    ],
                },
                {
                    "persona_title": "CFO Startup",
                    "recommended_authors": [
                        {
                            "author_name": "Morgan Housel",
                            "bio": "Financial writer.",
                            "resonance_rationale": "Clear finance voice.",
                            "key_works": [{"title": "Same as Ever", "type": "book", "relevance": "relevant"}],
                        },
                        {
                            "author_name": "Seth Godin",
                            "bio": "Marketing guru.",
                            "resonance_rationale": "Punchy, concise writing.",
                            "key_works": [{"title": "Purple Cow", "type": "book", "relevance": "relevant"}],
                        },
                    ],
                },
            ],
            "cross_persona_synthesis": {"shared_authors": []},
            "metadata": {
                "total_personas_processed": 2,
                "total_unique_authors_recommended": 3,
                "authors_requiring_research": [
                    {"author_name": "Morgan Housel", "priority": "HIGH", "research_focus": "financial writing"},
                ],
            },
        })
        result = _parse_json_array(payload)
        # Should extract 3 unique authors (Morgan Housel deduplicated)
        names = [r.get("name") for r in result]
        assert len(result) == 3
        assert "Morgan Housel" in names
        assert "Ann Handley" in names
        assert "Seth Godin" in names

    def test_parse_json_array_per_persona_deduplicates(self) -> None:
        """Same author across multiple personas should appear once."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({
            "personas": [
                {
                    "persona_title": "Persona A",
                    "recommended_authors": [
                        {"author_name": "Gene Kim", "bio": "DevOps author."},
                    ],
                },
                {
                    "persona_title": "Persona B",
                    "recommended_authors": [
                        {"author_name": "Gene Kim", "bio": "DevOps author."},
                        {"author_name": "Sahil Lavingia", "bio": "Founder."},
                    ],
                },
            ],
        })
        result = _parse_json_array(payload)
        names = [r.get("name") for r in result]
        assert names.count("Gene Kim") == 1
        assert "Sahil Lavingia" in names
        assert len(result) == 2

    def test_parse_json_array_per_persona_empty_authors(self) -> None:
        """Personas with empty recommended_authors should not break parsing."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({
            "personas": [
                {"persona_title": "Empty", "recommended_authors": []},
                {
                    "persona_title": "Has Author",
                    "recommended_authors": [
                        {"author_name": "Test Author", "bio": "desc"},
                    ],
                },
            ],
        })
        result = _parse_json_array(payload)
        assert len(result) == 1
        assert result[0].get("name") == "Test Author"

    def test_parse_json_array_per_persona_missing_recommended_authors_key(self) -> None:
        """Persona entry without recommended_authors key should be skipped."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({
            "personas": [
                {"persona_title": "No authors key"},
                {
                    "persona_title": "Has Author",
                    "recommended_authors": [
                        {"author_name": "Valid Author", "bio": "desc"},
                    ],
                },
            ],
        })
        result = _parse_json_array(payload)
        assert len(result) == 1

    def test_parse_json_array_per_persona_non_list_personas(self) -> None:
        """If personas is not a list, fall back gracefully."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({"personas": "not a list"})
        result = _parse_json_array(payload)
        # Falls through to dict-fallback (no recommended_authors key)
        assert result == [{"personas": "not a list"}]

    def test_parse_json_array_per_persona_with_metadata_fallback(self) -> None:
        """If personas all have empty authors, metadata.authors_requiring_research used as fallback."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({
            "personas": [
                {"persona_title": "Empty", "recommended_authors": []},
            ],
            "metadata": {
                "authors_requiring_research": [
                    {"author_name": "Fallback Author", "priority": "HIGH", "research_focus": "focus"},
                ],
            },
        })
        result = _parse_json_array(payload)
        assert len(result) == 1
        assert result[0].get("name") == "Fallback Author"

    # ── Old set-level schema (backward compat) ──

    def test_parse_json_array_set_level_recommended_authors(self) -> None:
        """Old schema: {"recommended_authors": [...]} still works."""
        from core.research.voice_style_guide.agents import _parse_json_array

        payload = json.dumps({
            "recommended_authors": [
                {"author_name": "Gene Kim", "bio": "DevOps pioneer."},
                {"author_name": "Sahil Lavingia", "bio": "Founder."},
            ],
        })
        result = _parse_json_array(payload)
        assert len(result) == 2
        assert result[0].get("name") == "Gene Kim"

    # ── _map_discovery_author per-persona fields ──

    def test_map_discovery_author_per_persona_fields(self) -> None:
        """New per-persona fields should be mapped correctly."""
        from core.research.voice_style_guide.agents import _map_discovery_author

        raw = {
            "author_name": "Robert M. Lee",
            "bio": "ICS/OT security expert, founded Dragos.",
            "resonance_rationale": "Speaks directly to SCADA security fears.",
            "key_works": [
                {"title": "SANS ICS515", "type": "course", "relevance": "ICS defense framework"},
            ],
            "voice_style_implications": {
                "tonal_quality": "practitioner bluntness",
                "rhetorical_pattern": "war stories before frameworks",
                "content_format_signal": "long-form case studies",
            },
            "persona_facet_addressed": "operational fear of catastrophic breach",
            "high_score_count": 5,
        }
        mapped = _map_discovery_author(raw)
        assert mapped["name"] == "Robert M. Lee"
        assert mapped["description"] == "ICS/OT security expert, founded Dragos."
        assert mapped["resonance_rationale"] == "Speaks directly to SCADA security fears."
        assert mapped["famous_works"] == ["SANS ICS515"]

    def test_map_discovery_author_backward_compat(self) -> None:
        """Old schema fields (selection_rationale) still map correctly."""
        from core.research.voice_style_guide.agents import _map_discovery_author

        raw = {
            "author_name": "Gene Kim",
            "bio": "DevOps pioneer.",
            "selection_rationale": "Phoenix Project resonates with IT ops.",
            "key_works": [{"title": "Phoenix Project", "type": "book", "relevance": "manufacturing IT"}],
        }
        mapped = _map_discovery_author(raw)
        assert mapped["name"] == "Gene Kim"
        assert mapped["resonance_rationale"] == "Phoenix Project resonates with IT ops."

    def test_parse_json_array_code_fences_with_per_persona(self) -> None:
        """Per-persona JSON wrapped in markdown code fences."""
        from core.research.voice_style_guide.agents import _parse_json_array, _strip_code_fences

        inner = json.dumps({
            "personas": [
                {
                    "persona_title": "Test",
                    "recommended_authors": [
                        {"author_name": "Test Author", "bio": "desc"},
                    ],
                },
            ],
        })
        fenced = f"```json\n{inner}\n```"
        cleaned = _strip_code_fences(fenced)
        result = _parse_json_array(cleaned)
        assert len(result) == 1
        assert result[0].get("name") == "Test Author"


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
            return_value=(mock_md, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
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

        mock_or_client = MagicMock()
        mock_or_client.chat.completions.create = AsyncMock(return_value=mock_response)
        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_or_client):
            guide_md, elapsed = await asyncio.wait_for(
                _import_and_run_synthesis(author_mds, company_context_md, persona_mds, vsg_input),
                timeout=10,
            )

        assert "Voice Style Guide" in guide_md
        assert elapsed > 0
        mock_or_client.chat.completions.create.assert_called_once()

        # Verify max_tokens=8192 was passed
        call_kwargs = mock_or_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 8192

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(
        self, vsg_input: VoiceStyleGuideInput, company_context_md: str, persona_mds: list[str],
    ) -> None:
        mock_or_client = MagicMock()
        mock_or_client.chat.completions.create = AsyncMock(side_effect=asyncio.TimeoutError())
        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_or_client):
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
        mock_or_client = MagicMock()
        mock_or_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("Model not found"))
        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_or_client):
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
