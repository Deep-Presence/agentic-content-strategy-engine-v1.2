"""Tests for Audience Persona agents — Suggester (Gemini) + Profile Generator (Perplexity).

TDD: tests written FIRST, implementation follows.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.audience_persona import (
    AudiencePersonaInput,
    PersonaAgentResult,
    PersonaBrief,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENTS_MOD = "core.research.audience_persona.agents"
_PERPLEXITY_PATCH = f"{_AGENTS_MOD}.perplexity_client"
_GENAI_PATCH = f"{_AGENTS_MOD}.genai"


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_VALID_BRIEFS_RAW: List[Dict[str, Any]] = [
    {
        "persona_name": "Sarah",
        "tagline": "VP of Finance at mid-market SaaS",
        "description": "Manages financial ops and budget.",
        "rationale": ["Evidence from G2 reviews", "Common in SaaS"],
    },
    {
        "persona_name": "Marcus",
        "tagline": "Head of Product at B2B startup",
        "description": "Drives product roadmap.",
        "rationale": ["Mentioned in customer reviews"],
    },
    {
        "persona_name": "Priya",
        "tagline": "Director of Marketing at mid-market",
        "description": "Owns demand gen and brand.",
        "rationale": ["Key buyer segment", "High LTV"],
    },
]

_VALID_BRIEFS_JSON = json.dumps(_VALID_BRIEFS_RAW)

_PROFILE_MD = """\
# Persona: Sarah (ICP)

**Company:** Test Co
**Role/Title:** VP of Finance
**Industry context:** SaaS

## Persona Summary
Sarah manages financial operations at mid-market SaaS companies.

## Role & Context
Typical VP of Finance in a 200-500 person SaaS company.

## Pain Points & Blockers
Manual reconciliation, slow month-end close.

## Sources
[1] https://example.com/source1
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ap_input() -> AudiencePersonaInput:
    return AudiencePersonaInput(
        company_name="Test Co",
        domain="test.co",
        company_slug="test-co",
        max_personas=5,
    )


@pytest.fixture()
def sample_brief() -> PersonaBrief:
    return PersonaBrief(
        brief_id="pb-001",
        persona_name="Sarah",
        tagline="VP of Finance at mid-market SaaS",
        description="Manages financial ops.",
        rationale=["Evidence from G2", "Common title"],
    )


@pytest.fixture(autouse=True)
def _mock_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable tracing for all agent tests."""
    monkeypatch.setattr(f"{_AGENTS_MOD}.create_span", lambda *a, **kw: None)
    monkeypatch.setattr(f"{_AGENTS_MOD}.end_span", lambda *a, **kw: None)
    monkeypatch.setattr(f"{_AGENTS_MOD}.log_generation", lambda *a, **kw: None)


def _make_gemini_response(text: str = _VALID_BRIEFS_JSON) -> MagicMock:
    """Build a mock google.genai GenerateContentResponse."""
    response = MagicMock()
    response.text = text
    return response


def _mock_gemini_client(monkeypatch: pytest.MonkeyPatch, response: MagicMock) -> MagicMock:
    """Patch genai.Client to return a mock with given response."""
    mock_aio_models = AsyncMock()
    mock_aio_models.generate_content = AsyncMock(return_value=response)
    mock_aio = MagicMock()
    mock_aio.models = mock_aio_models
    mock_client = MagicMock()
    mock_client.aio = mock_aio
    monkeypatch.setattr(f"{_GENAI_PATCH}.Client", MagicMock(return_value=mock_client))
    return mock_client


# ---------------------------------------------------------------------------
# TestGetGeminiApiKey
# ---------------------------------------------------------------------------


class TestGetGeminiApiKey:
    """API key resolution with fallback chain."""

    def test_uses_primary_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.audience_persona.agents import _get_gemini_api_key

        monkeypatch.setattr("core.config.settings.settings.google_api_key_audience_persona", "primary-key")
        monkeypatch.setattr("core.config.settings.settings.google_api_key_persona_research_deepagent", "fallback-key")
        assert _get_gemini_api_key() == "primary-key"

    def test_falls_back_to_deepagent_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.audience_persona.agents import _get_gemini_api_key

        monkeypatch.setattr("core.config.settings.settings.google_api_key_audience_persona", None)
        monkeypatch.setattr("core.config.settings.settings.google_api_key_persona_research_deepagent", "fallback-key")
        assert _get_gemini_api_key() == "fallback-key"

    def test_raises_when_no_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.audience_persona.agents import _get_gemini_api_key

        monkeypatch.setattr("core.config.settings.settings.google_api_key_audience_persona", None)
        monkeypatch.setattr("core.config.settings.settings.google_api_key_persona_research_deepagent", None)
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
            _get_gemini_api_key()

    def test_primary_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.audience_persona.agents import _get_gemini_api_key

        monkeypatch.setattr("core.config.settings.settings.google_api_key_audience_persona", "primary")
        monkeypatch.setattr("core.config.settings.settings.google_api_key_persona_research_deepagent", "fallback")
        assert _get_gemini_api_key() == "primary"


# ---------------------------------------------------------------------------
# TestStripCodeFences
# ---------------------------------------------------------------------------


class TestStripCodeFences:
    """Code fence stripping for LLM JSON responses."""

    def test_strips_json_code_fence(self) -> None:
        from core.research.audience_persona.agents import _strip_code_fences

        text = '```json\n[{"persona_name": "Sarah"}]\n```'
        assert _strip_code_fences(text) == '[{"persona_name": "Sarah"}]'

    def test_strips_bare_code_fence(self) -> None:
        from core.research.audience_persona.agents import _strip_code_fences

        text = '```\n[{"persona_name": "Sarah"}]\n```'
        assert _strip_code_fences(text) == '[{"persona_name": "Sarah"}]'

    def test_passes_clean_json_unchanged(self) -> None:
        from core.research.audience_persona.agents import _strip_code_fences

        text = '[{"persona_name": "Sarah"}]'
        assert _strip_code_fences(text) == text


# ---------------------------------------------------------------------------
# TestValidateBriefs
# ---------------------------------------------------------------------------


class TestValidateBriefs:
    """Brief validation and normalization."""

    def test_valid_briefs_pass(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        briefs, errors = _validate_briefs(_VALID_BRIEFS_RAW, max_personas=5)
        assert len(briefs) == 3
        assert not errors

    def test_assigns_brief_id_when_missing(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        briefs, _ = _validate_briefs(_VALID_BRIEFS_RAW, max_personas=5)
        for b in briefs:
            assert b.brief_id.startswith("pb-")
            assert len(b.brief_id) > 3

    def test_detects_duplicate_names(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        raw = [
            {"persona_name": "Sarah", "tagline": "VP Finance", "description": "A", "rationale": ["x"]},
            {"persona_name": "sarah", "tagline": "CFO", "description": "B", "rationale": ["y"]},
            {"persona_name": "Marcus", "tagline": "Head Product", "description": "C", "rationale": ["z"]},
        ]
        briefs, errors = _validate_briefs(raw, max_personas=5)
        assert len(briefs) == 2  # Duplicate removed
        assert any("duplicate" in e.lower() for e in errors)

    def test_missing_required_fields(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        raw = [
            {"tagline": "VP Finance", "description": "A", "rationale": ["x"]},  # no persona_name
        ]
        briefs, errors = _validate_briefs(raw, max_personas=5)
        assert len(briefs) == 0
        assert any("persona_name" in e.lower() or "required" in e.lower() for e in errors)

    def test_sets_source_to_agent(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        briefs, _ = _validate_briefs(_VALID_BRIEFS_RAW, max_personas=5)
        for b in briefs:
            assert b.source == "agent"

    def test_non_string_persona_name_skipped(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        raw = [
            {"persona_name": 42, "tagline": "T", "description": "D", "rationale": ["x"]},
            {"persona_name": "Valid", "tagline": "T", "description": "D", "rationale": ["x"]},
        ]
        briefs, errors = _validate_briefs(raw, max_personas=5)
        assert len(briefs) == 1
        assert briefs[0].persona_name == "Valid"
        assert any("not a string" in e for e in errors)

    def test_max_personas_enforced(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        raw = [
            {"persona_name": f"Persona{i}", "tagline": "T", "description": "D", "rationale": ["x"]}
            for i in range(10)
        ]
        briefs, _ = _validate_briefs(raw, max_personas=3)
        assert len(briefs) == 3

    def test_none_persona_name_skipped(self) -> None:
        from core.research.audience_persona.agents import _validate_briefs

        raw = [
            {"persona_name": None, "tagline": "T", "description": "D", "rationale": ["x"]},
            {"persona_name": "Valid", "tagline": "T", "description": "D", "rationale": ["x"]},
        ]
        briefs, errors = _validate_briefs(raw, max_personas=5)
        assert len(briefs) == 1
        assert any("not a string" in e for e in errors)


# ---------------------------------------------------------------------------
# TestLoadKnowledgeDocs
# ---------------------------------------------------------------------------


class TestLoadKnowledgeDocs:
    """Knowledge document loading helper."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_docs(self, tmp_path: Path) -> None:
        from core.research.audience_persona.agents import _load_knowledge_docs

        result = await _load_knowledge_docs(tmp_path, "test-co", "test-co")
        assert result == ""

    @pytest.mark.asyncio
    async def test_loads_docs_from_effective_slug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        # Setup: create doc dir and metadata
        doc_dir = tmp_path / "knowledge_docs" / "test-co"
        doc_dir.mkdir(parents=True)
        doc_file = doc_dir / "guide.md"
        doc_file.write_text("# Product Guide\nOur product helps companies.")
        meta = [KnowledgeDocument(filename="guide.md", stored_filename="guide.md")]
        (doc_dir / "_metadata.json").write_text(
            json.dumps([m.model_dump(mode="json") for m in meta])
        )

        result = await _load_knowledge_docs(tmp_path, "test-co", "test-co")
        assert "### guide.md" in result
        assert "Our product helps companies" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_company_slug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        # No docs under effective_slug, but company_slug has docs
        company_dir = tmp_path / "knowledge_docs" / "test-co"
        company_dir.mkdir(parents=True)
        doc_file = company_dir / "info.txt"
        doc_file.write_text("Company info text.")
        meta = [KnowledgeDocument(filename="info.txt", stored_filename="info.txt")]
        (company_dir / "_metadata.json").write_text(
            json.dumps([m.model_dump(mode="json") for m in meta])
        )

        result = await _load_knowledge_docs(tmp_path, "test-co__product", "test-co")
        assert "### info.txt" in result
        assert "Company info text" in result

    @pytest.mark.asyncio
    async def test_formats_doc_headers(self, tmp_path: Path) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        doc_dir = tmp_path / "knowledge_docs" / "test-co"
        doc_dir.mkdir(parents=True)
        (doc_dir / "a.md").write_text("Content A")
        (doc_dir / "b.md").write_text("Content B")
        meta = [
            KnowledgeDocument(filename="a.md", stored_filename="a.md"),
            KnowledgeDocument(filename="b.md", stored_filename="b.md"),
        ]
        (doc_dir / "_metadata.json").write_text(
            json.dumps([m.model_dump(mode="json") for m in meta])
        )

        result = await _load_knowledge_docs(tmp_path, "test-co", "test-co")
        assert "### a.md" in result
        assert "### b.md" in result

    @pytest.mark.asyncio
    async def test_truncates_at_max_chars(self, tmp_path: Path) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        doc_dir = tmp_path / "knowledge_docs" / "test-co"
        doc_dir.mkdir(parents=True)
        big_content = "x" * 10_000
        (doc_dir / "big.md").write_text(big_content)
        meta = [KnowledgeDocument(filename="big.md", stored_filename="big.md")]
        (doc_dir / "_metadata.json").write_text(
            json.dumps([m.model_dump(mode="json") for m in meta])
        )

        result = await _load_knowledge_docs(tmp_path, "test-co", "test-co", max_chars=100)
        assert len(result) <= 100

    @pytest.mark.asyncio
    async def test_handles_extraction_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        doc_dir = tmp_path / "knowledge_docs" / "test-co"
        doc_dir.mkdir(parents=True)
        (doc_dir / "good.md").write_text("Good content")
        (doc_dir / "bad.bin").write_text("binary junk")
        meta = [
            KnowledgeDocument(filename="good.md", stored_filename="good.md"),
            KnowledgeDocument(filename="bad.bin", stored_filename="bad.bin"),
        ]
        (doc_dir / "_metadata.json").write_text(
            json.dumps([m.model_dump(mode="json") for m in meta])
        )

        # bad.bin returns empty string from extract_text (unsupported type)
        result = await _load_knowledge_docs(tmp_path, "test-co", "test-co")
        assert "Good content" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_both_slugs_empty(self, tmp_path: Path) -> None:
        from core.research.audience_persona.agents import _load_knowledge_docs

        result = await _load_knowledge_docs(tmp_path, "no-such", "also-no-such")
        assert result == ""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """stored_filename with ../ should be skipped (defense-in-depth)."""
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        doc_dir = tmp_path / "knowledge_docs" / "test-co"
        doc_dir.mkdir(parents=True)
        # Legitimate file
        (doc_dir / "legit.md").write_text("Legit content")
        # Sensitive file outside doc_dir
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP SECRET")

        meta = [
            KnowledgeDocument(filename="legit.md", stored_filename="legit.md"),
            KnowledgeDocument(filename="secret.txt", stored_filename="../../secret.txt"),
        ]
        (doc_dir / "_metadata.json").write_text(
            json.dumps([m.model_dump(mode="json") for m in meta])
        )

        result = await _load_knowledge_docs(tmp_path, "test-co", "test-co")
        assert "Legit content" in result
        assert "TOP SECRET" not in result


# ---------------------------------------------------------------------------
# TestRunPersonaSuggester
# ---------------------------------------------------------------------------


class TestRunPersonaSuggester:
    """Agent 1 — Gemini Flash persona brief generation."""

    @pytest.fixture(autouse=True)
    def _mock_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "core.config.settings.settings.google_api_key_audience_persona", "test-key"
        )

    @pytest.mark.asyncio
    async def test_success_returns_briefs(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        briefs, elapsed = await run_persona_suggester(
            ap_input, "company context", "customer reviews", timeout_s=10,
        )
        assert len(briefs) == 3
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_correct_brief_count(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        briefs, _ = await run_persona_suggester(
            ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert len(briefs) == len(_VALID_BRIEFS_RAW)

    @pytest.mark.asyncio
    async def test_system_prompt_passed_as_config(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config is not None
        assert config.system_instruction is not None

    @pytest.mark.asyncio
    async def test_json_mode_enabled(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config.response_mime_type == "application/json"

    @pytest.mark.asyncio
    async def test_uses_correct_model(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.aio.models.generate_content.call_args
        model_arg = call_kwargs.kwargs.get("model") or call_kwargs[0][0]
        assert "gemini" in model_arg.lower()

    @pytest.mark.asyncio
    async def test_timeout_returns_empty_list(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        with patch(f"{_AGENTS_MOD}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            briefs, elapsed = await run_persona_suggester(
                ap_input, "ctx", "reviews", timeout_s=0.01,
            )
        assert briefs == []
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_api_error_returns_empty_list(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_response = _make_gemini_response(_VALID_BRIEFS_JSON)
        mock_client = _mock_gemini_client(monkeypatch, mock_response)
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API quota exceeded"),
        )
        briefs, elapsed = await run_persona_suggester(
            ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert briefs == []
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_malformed_json_triggers_retry(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        bad_resp = _make_gemini_response("not valid json at all")
        good_resp = _make_gemini_response(_VALID_BRIEFS_JSON)

        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content = AsyncMock(side_effect=[bad_resp, good_resp])
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        monkeypatch.setattr(f"{_GENAI_PATCH}.Client", MagicMock(return_value=mock_client))

        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) >= 3
        assert mock_aio_models.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_too_few_briefs_triggers_retry(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        # First response: only 2 briefs (below _MIN_BRIEFS=3)
        two_briefs = json.dumps(_VALID_BRIEFS_RAW[:2])
        three_briefs = _VALID_BRIEFS_JSON

        bad_resp = _make_gemini_response(two_briefs)
        good_resp = _make_gemini_response(three_briefs)

        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content = AsyncMock(side_effect=[bad_resp, good_resp])
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        monkeypatch.setattr(f"{_GENAI_PATCH}.Client", MagicMock(return_value=mock_client))

        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) >= 3

    @pytest.mark.asyncio
    async def test_retry_also_fails_returns_partial(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        two_briefs = json.dumps(_VALID_BRIEFS_RAW[:2])
        bad1 = _make_gemini_response(two_briefs)
        bad2 = _make_gemini_response(two_briefs)

        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content = AsyncMock(side_effect=[bad1, bad2])
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        monkeypatch.setattr(f"{_GENAI_PATCH}.Client", MagicMock(return_value=mock_client))

        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) == 2  # Partial results returned

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_empty(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        monkeypatch.setattr("core.config.settings.settings.google_api_key_audience_persona", None)
        monkeypatch.setattr("core.config.settings.settings.google_api_key_persona_research_deepagent", None)
        briefs, elapsed = await run_persona_suggester(
            ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert briefs == []
        assert elapsed > 0

    @pytest.mark.asyncio
    async def test_formats_max_personas_into_system_prompt(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        # System prompt should have max_personas resolved (no {max_personas} placeholder)
        assert "{max_personas}" not in config.system_instruction

    @pytest.mark.asyncio
    async def test_strips_code_fences_from_response(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        fenced = f"```json\n{_VALID_BRIEFS_JSON}\n```"
        _mock_gemini_client(monkeypatch, _make_gemini_response(fenced))
        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) == 3

    @pytest.mark.asyncio
    async def test_execution_time_always_positive(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_gemini_client(monkeypatch, _make_gemini_response(_VALID_BRIEFS_JSON))
        _, elapsed = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert elapsed > 0


# ---------------------------------------------------------------------------
# TestRunPersonaProfileGenerator
# ---------------------------------------------------------------------------


class TestRunPersonaProfileGenerator:
    """Agent 2 — Perplexity persona profile generation."""

    @pytest.mark.asyncio
    async def test_success_returns_result(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_persona_profile_generator(
            sample_brief, ap_input, "company ctx", "reviews", timeout_s=10,
        )
        assert result.error is None
        assert "Sarah" in result.content_md
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_populates_brief_id_and_name(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert result.brief_id == "pb-001"
        assert result.persona_name == "Sarah"

    @pytest.mark.asyncio
    async def test_timeout_returns_error(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        with patch(f"{_AGENTS_MOD}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await run_persona_profile_generator(
                sample_brief, ap_input, "ctx", "reviews", timeout_s=0.01,
            )
        assert result.error is not None
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_api_error_returns_error(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=RuntimeError("API key invalid"))
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert result.error is not None
        assert "API key invalid" in result.error

    @pytest.mark.asyncio
    async def test_empty_response(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value="")
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert result.error is None
        assert result.word_count == 0

    @pytest.mark.asyncio
    async def test_revision_note_in_prompt(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews",
            timeout_s=10, revision_note="Add more KPIs",
        )
        call_kwargs = mock_client.research.call_args
        query = call_kwargs.kwargs.get("query", call_kwargs[0][0] if call_kwargs[0] else "")
        assert "Reviewer Feedback" in query
        assert "Add more KPIs" in query

    @pytest.mark.asyncio
    async def test_no_revision_note_omits_feedback(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=10,
        )
        call_kwargs = mock_client.research.call_args
        query = call_kwargs.kwargs.get("query", call_kwargs[0][0] if call_kwargs[0] else "")
        assert "Reviewer Feedback" not in query

    @pytest.mark.asyncio
    async def test_includes_all_context_in_prompt(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_persona_profile_generator(
            sample_brief, ap_input, "COMPANY_CTX_MARKER", "REVIEWS_MARKER",
            knowledge_docs_text="KDOCS_MARKER", timeout_s=10,
        )
        call_kwargs = mock_client.research.call_args
        query = call_kwargs.kwargs.get("query", call_kwargs[0][0] if call_kwargs[0] else "")
        assert "COMPANY_CTX_MARKER" in query
        assert "REVIEWS_MARKER" in query
        assert "KDOCS_MARKER" in query

    @pytest.mark.asyncio
    async def test_timeout_forwarded_to_client(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=42.0,
        )
        call_kwargs = mock_client.research.call_args
        assert call_kwargs.kwargs.get("timeout_s") == 42.0

    @pytest.mark.asyncio
    async def test_execution_time_always_positive(
        self,
        ap_input: AudiencePersonaInput,
        sample_brief: PersonaBrief,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_profile_generator

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value=_PROFILE_MD)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert result.execution_time_s > 0
