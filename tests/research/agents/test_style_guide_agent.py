"""Tests for the style guide research agent: build, get, run_style_guide_agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.models.style_guide import StyleGuideResearchInput
from core.research.agents import style_guide_agent as sga


# ---------------------------------------------------------------------------
# build_agent / get_style_guide_agent
# ---------------------------------------------------------------------------

class TestBuildStyleGuideAgent:
    def test_with_correct_model(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        agent = sga.build_agent()
        assert agent is not None

    def test_uses_system_prompt_kwarg(self, mock_research_settings, mock_google_chat_model):
        """Regression: was system_message=, now system_prompt=."""
        with patch.object(sga, "create_deep_agent", return_value=MagicMock()) as mock_create:
            sga.build_agent()
            call_kwargs = mock_create.call_args
            # Must use system_prompt, not system_message
            assert "system_prompt" in (call_kwargs.kwargs or {})
            assert "system_message" not in (call_kwargs.kwargs or {})

    def test_raises_without_api_key(self):
        with patch.object(sga, "settings") as mock_s:
            mock_s.google_api_key_style_guide_research_deepagent = None
            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY_STYLE_GUIDE_RESEARCH_DEEPAGENT"):
                sga.build_agent()


class TestGetStyleGuideAgent:
    def test_caches_singleton(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        a1 = sga.get_style_guide_agent()
        a2 = sga.get_style_guide_agent()
        assert a1 is a2


# ---------------------------------------------------------------------------
# run_style_guide_agent
# ---------------------------------------------------------------------------

class TestRunStyleGuideAgent:
    def _make_json_agent(self, written_paths: list, notes: str = "done"):
        response = json.dumps({"written_paths": written_paths, "notes": notes})
        agent = MagicMock()
        agent.invoke.return_value = {
            "messages": [
                {"role": "user", "content": "prompt"},
                {"role": "assistant", "content": response},
            ]
        }
        return agent

    def test_returns_parsed_json(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, style_input
    ):
        paths = ["/artifacts/style_guides/acme-corp.draft.md"]
        agent = self._make_json_agent(paths)
        with patch.object(sga, "get_style_guide_agent", return_value=agent):
            result = sga.run_style_guide_agent(style_input, use_draft_paths=True)
        assert result["written_paths"] == paths

    def test_handles_non_json_output(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, style_input
    ):
        agent = MagicMock()
        agent.invoke.return_value = {
            "messages": [
                {"role": "user", "content": "prompt"},
                {"role": "assistant", "content": "Here is the style guide..."},
            ]
        }
        with patch.object(sga, "get_style_guide_agent", return_value=agent):
            result = sga.run_style_guide_agent(style_input, use_draft_paths=True)
        assert result["notes"] == "Non-JSON agent output"
        assert "raw" in result

    def test_disk_fallback(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, style_input
    ):
        draft = isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md"
        draft.write_text("# Style Guide\n\nContent.", encoding="utf-8")

        agent = self._make_json_agent(written_paths=[])
        with patch.object(sga, "get_style_guide_agent", return_value=agent):
            result = sga.run_style_guide_agent(style_input, use_draft_paths=True)
        assert "/artifacts/style_guides/acme-corp.draft.md" in result["written_paths"]

    def test_default_persona_paths_when_none_given(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts
    ):
        input_data = StyleGuideResearchInput(
            company_name="Acme Corp",
            company_slug="acme-corp",
            persona_paths=[],  # empty
        )
        paths = ["/artifacts/style_guides/acme-corp.md"]
        agent = self._make_json_agent(paths)
        with patch.object(sga, "get_style_guide_agent", return_value=agent):
            sga.run_style_guide_agent(input_data, use_draft_paths=False)
        prompt = agent.invoke.call_args[0][0]["messages"][0]["content"]
        # Should use default persona paths when none provided
        assert "persona-icp.md" in prompt

    def test_revision_note_in_prompt(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, style_input
    ):
        agent = self._make_json_agent(["/artifacts/style_guides/acme-corp.draft.md"])
        with patch.object(sga, "get_style_guide_agent", return_value=agent):
            sga.run_style_guide_agent(style_input, revision_note="More examples", use_draft_paths=True)
        prompt = agent.invoke.call_args[0][0]["messages"][0]["content"]
        assert "More examples" in prompt

    def test_single_file_output(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, style_input
    ):
        """Style guide produces one file, not multiple like persona."""
        paths = ["/artifacts/style_guides/acme-corp.draft.md"]
        agent = self._make_json_agent(paths)
        with patch.object(sga, "get_style_guide_agent", return_value=agent):
            result = sga.run_style_guide_agent(style_input, use_draft_paths=True)
        assert len(result["written_paths"]) == 1
