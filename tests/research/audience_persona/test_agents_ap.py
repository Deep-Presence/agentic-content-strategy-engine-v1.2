"""Tests for Audience Persona agents — Suggester (OpenRouter) + Profile Generator (Perplexity).

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
_OR_CLIENT_PATCH = f"{_AGENTS_MOD}.get_async_client"


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


def _make_or_response(text: str = _VALID_BRIEFS_JSON) -> MagicMock:
    """Build a mock OpenRouter chat.completions.create response."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def _mock_or_client(monkeypatch: pytest.MonkeyPatch, response: MagicMock) -> MagicMock:
    """Patch get_async_client to return a mock with given response."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=response)
    monkeypatch.setattr(_OR_CLIENT_PATCH, lambda: mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# TestGetGeminiApiKey
# ---------------------------------------------------------------------------


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
    """Knowledge document loading helper — reads via StorageBackend."""

    @pytest.fixture()
    def storage(self, tmp_path: Path):
        from core.storage.backends.local import LocalStorageBackend
        return LocalStorageBackend(tmp_path)

    def _write_doc(self, storage, slug: str, filename: str, content: str) -> None:
        storage.write(f"knowledge_docs/{slug}/{filename}", content)

    def _write_meta(self, storage, slug: str, entries: list) -> None:
        storage.write(
            f"knowledge_docs/{slug}/_metadata.json",
            json.dumps([e.model_dump(mode="json") if hasattr(e, "model_dump") else e for e in entries]),
        )

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_docs(self, storage) -> None:
        from core.research.audience_persona.agents import _load_knowledge_docs

        result = await _load_knowledge_docs(storage, "test-co", "test-co")
        assert result == ""

    @pytest.mark.asyncio
    async def test_loads_docs_from_effective_slug(self, storage) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        self._write_doc(storage, "test-co", "guide.md", "# Product Guide\nOur product helps companies.")
        meta = [KnowledgeDocument(filename="guide.md", stored_filename="guide.md")]
        self._write_meta(storage, "test-co", meta)

        result = await _load_knowledge_docs(storage, "test-co", "test-co")
        assert "### guide.md" in result
        assert "Our product helps companies" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_company_slug(self, storage) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        # No docs under effective_slug, but company_slug has docs
        self._write_doc(storage, "test-co", "info.txt", "Company info text.")
        meta = [KnowledgeDocument(filename="info.txt", stored_filename="info.txt")]
        self._write_meta(storage, "test-co", meta)

        result = await _load_knowledge_docs(storage, "test-co__product", "test-co")
        assert "### info.txt" in result
        assert "Company info text" in result

    @pytest.mark.asyncio
    async def test_formats_doc_headers(self, storage) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        self._write_doc(storage, "test-co", "a.md", "Content A")
        self._write_doc(storage, "test-co", "b.md", "Content B")
        meta = [
            KnowledgeDocument(filename="a.md", stored_filename="a.md"),
            KnowledgeDocument(filename="b.md", stored_filename="b.md"),
        ]
        self._write_meta(storage, "test-co", meta)

        result = await _load_knowledge_docs(storage, "test-co", "test-co")
        assert "### a.md" in result
        assert "### b.md" in result

    @pytest.mark.asyncio
    async def test_truncates_at_max_chars(self, storage) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        big_content = "x" * 10_000
        self._write_doc(storage, "test-co", "big.md", big_content)
        meta = [KnowledgeDocument(filename="big.md", stored_filename="big.md")]
        self._write_meta(storage, "test-co", meta)

        result = await _load_knowledge_docs(storage, "test-co", "test-co", max_chars=100)
        assert len(result) <= 100

    @pytest.mark.asyncio
    async def test_handles_extraction_failure(self, storage) -> None:
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        self._write_doc(storage, "test-co", "good.md", "Good content")
        self._write_doc(storage, "test-co", "bad.bin", "binary junk")
        meta = [
            KnowledgeDocument(filename="good.md", stored_filename="good.md"),
            KnowledgeDocument(filename="bad.bin", stored_filename="bad.bin"),
        ]
        self._write_meta(storage, "test-co", meta)

        # bad.bin returns empty string from extract_text_from_bytes (unsupported type)
        result = await _load_knowledge_docs(storage, "test-co", "test-co")
        assert "Good content" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_both_slugs_empty(self, storage) -> None:
        from core.research.audience_persona.agents import _load_knowledge_docs

        result = await _load_knowledge_docs(storage, "no-such", "also-no-such")
        assert result == ""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, storage) -> None:
        """stored_filename with ../ should be blocked by StorageBackend validation."""
        from core.models.knowledge_docs import KnowledgeDocument
        from core.research.audience_persona.agents import _load_knowledge_docs

        self._write_doc(storage, "test-co", "legit.md", "Legit content")
        meta = [
            KnowledgeDocument(filename="legit.md", stored_filename="legit.md"),
            KnowledgeDocument(filename="secret.txt", stored_filename="../../secret.txt"),
        ]
        self._write_meta(storage, "test-co", meta)

        result = await _load_knowledge_docs(storage, "test-co", "test-co")
        assert "Legit content" in result
        # Path traversal filename should fail StorageBackend validation or not be found
        assert "TOP SECRET" not in result


# ---------------------------------------------------------------------------
# TestRunPersonaSuggester
# ---------------------------------------------------------------------------


class TestRunPersonaSuggester:
    """Agent 1 — Persona brief generation via OpenRouter."""

    @pytest.mark.asyncio
    async def test_success_returns_briefs(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
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

        _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
        briefs, _ = await run_persona_suggester(
            ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert len(briefs) == len(_VALID_BRIEFS_RAW)

    @pytest.mark.asyncio
    async def test_system_prompt_in_messages(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages")
        assert messages is not None
        assert messages[0]["role"] == "system"
        assert len(messages[0]["content"]) > 0

    @pytest.mark.asyncio
    async def test_json_mode_enabled(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.chat.completions.create.call_args
        rf = call_kwargs.kwargs.get("response_format")
        assert rf == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_uses_correct_model(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        mock_client = _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.chat.completions.create.call_args
        model_arg = call_kwargs.kwargs.get("model")
        assert "gemini" in model_arg.lower()

    @pytest.mark.asyncio
    async def test_timeout_returns_empty_list(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
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

        mock_client = _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
        mock_client.chat.completions.create = AsyncMock(
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

        bad_resp = _make_or_response("not valid json at all")
        good_resp = _make_or_response(_VALID_BRIEFS_JSON)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[bad_resp, good_resp])
        monkeypatch.setattr(_OR_CLIENT_PATCH, lambda: mock_client)

        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) >= 3
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_too_few_briefs_triggers_retry(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        two_briefs = json.dumps(_VALID_BRIEFS_RAW[:2])
        three_briefs = _VALID_BRIEFS_JSON

        bad_resp = _make_or_response(two_briefs)
        good_resp = _make_or_response(three_briefs)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[bad_resp, good_resp])
        monkeypatch.setattr(_OR_CLIENT_PATCH, lambda: mock_client)

        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) >= 3

    @pytest.mark.asyncio
    async def test_retry_also_fails_returns_partial(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        two_briefs = json.dumps(_VALID_BRIEFS_RAW[:2])
        bad1 = _make_or_response(two_briefs)
        bad2 = _make_or_response(two_briefs)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[bad1, bad2])
        monkeypatch.setattr(_OR_CLIENT_PATCH, lambda: mock_client)

        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) == 2  # Partial results returned

    @pytest.mark.asyncio
    async def test_missing_openrouter_key_returns_empty(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        monkeypatch.setattr(
            _OR_CLIENT_PATCH,
            MagicMock(side_effect=RuntimeError("OPENROUTER_API_KEY is not set")),
        )
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

        mock_client = _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
        await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages")
        # System prompt should have max_personas resolved (no {max_personas} placeholder)
        assert "{max_personas}" not in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_strips_code_fences_from_response(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        fenced = f"```json\n{_VALID_BRIEFS_JSON}\n```"
        _mock_or_client(monkeypatch, _make_or_response(fenced))
        briefs, _ = await run_persona_suggester(ap_input, "ctx", "reviews", timeout_s=10)
        assert len(briefs) == 3

    @pytest.mark.asyncio
    async def test_execution_time_always_positive(
        self, ap_input: AudiencePersonaInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        _mock_or_client(monkeypatch, _make_or_response(_VALID_BRIEFS_JSON))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=("", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
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
        mock_client.research = MagicMock(return_value=(_PROFILE_MD, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_persona_profile_generator(
            sample_brief, ap_input, "ctx", "reviews", timeout_s=10,
        )
        assert result.execution_time_s > 0


# ---------------------------------------------------------------------------
# Cost tracking tests
# ---------------------------------------------------------------------------


class TestPersonaSuggesterCostTracking:
    """Verify track_llm_cost() is called inside run_persona_suggester()."""

    @pytest.mark.asyncio
    async def test_cost_tracked_on_initial_call(
        self,
        ap_input: AudiencePersonaInput,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.audience_persona.agents import run_persona_suggester

        resp = _make_or_response(_VALID_BRIEFS_JSON)
        resp.usage = MagicMock(prompt_tokens=50, completion_tokens=100)
        _mock_or_client(monkeypatch, resp)

        with patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            await run_persona_suggester(ap_input, "company ctx", "reviews", timeout_s=10)

        # At least the initial call should be tracked
        assert mock_track.call_count >= 1
        kw = mock_track.call_args_list[0][1]
        assert kw["pipeline"] == "audience_persona"
        assert kw["pipeline_step"] == "persona_suggester"
        assert kw["provider"] == "openrouter"
        assert kw["source"] == "openrouter"
        assert kw["prompt_tokens"] == 50
        assert kw["completion_tokens"] == 100
