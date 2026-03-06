"""Tests for the persona research agent: build, get, run_persona_agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.models.personas import PersonaResearchInput
from core.research.agents import persona_agent as pa


# ---------------------------------------------------------------------------
# build_agent / get_persona_agent
# ---------------------------------------------------------------------------

class TestBuildPersonaAgent:
    def test_with_correct_model(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        agent = pa.build_agent()
        assert agent is not None

    def test_has_internet_search_tool(self, mock_research_settings, mock_google_chat_model):
        with patch.object(pa, "create_deep_agent", return_value=MagicMock()) as mock_create:
            pa.build_agent()
            call_kwargs = mock_create.call_args
            tools = call_kwargs.kwargs.get("tools") or call_kwargs[1].get("tools") or call_kwargs[0][1]
            tool_names = [t.__name__ for t in tools]
            assert "internet_search" in tool_names

    def test_raises_without_api_key(self):
        with patch.object(pa, "settings") as mock_s:
            mock_s.google_api_key_persona_research_deepagent = None
            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT"):
                pa.build_agent()


class TestGetPersonaAgent:
    def test_caches_singleton(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        a1 = pa.get_persona_agent()
        a2 = pa.get_persona_agent()
        assert a1 is a2


# ---------------------------------------------------------------------------
# run_persona_agent
# ---------------------------------------------------------------------------

class TestRunPersonaAgent:
    def _make_json_agent(self, written_paths: list, notes: str = "done"):
        """Create a MockDeepAgent that returns valid JSON."""
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
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, persona_input
    ):
        paths = ["/artifacts/personas/acme-corp__persona-icp.draft.md"]
        agent = self._make_json_agent(paths)
        with patch.object(pa, "get_persona_agent", return_value=agent):
            result = pa.run_persona_agent(persona_input, use_draft_paths=True)
        assert result["written_paths"] == paths
        assert result["notes"] == "done"

    def test_handles_non_json_output(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, persona_input
    ):
        agent = MagicMock()
        agent.invoke.return_value = {
            "messages": [
                {"role": "user", "content": "prompt"},
                {"role": "assistant", "content": "Here is the persona in markdown..."},
            ]
        }
        with patch.object(pa, "get_persona_agent", return_value=agent):
            result = pa.run_persona_agent(persona_input, use_draft_paths=True)
        assert result["notes"] == "Non-JSON agent output"
        assert "raw" in result

    def test_disk_fallback_when_no_paths(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, persona_input
    ):
        # Pre-create the expected draft on disk
        draft = isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md"
        draft.write_text("# ICP Persona\n\nContent here.", encoding="utf-8")

        agent = self._make_json_agent(written_paths=[])
        with patch.object(pa, "get_persona_agent", return_value=agent):
            result = pa.run_persona_agent(persona_input, use_draft_paths=True)
        assert "/artifacts/personas/acme-corp__persona-icp.draft.md" in result["written_paths"]

    def test_slug_derivation_from_company_name(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts
    ):
        input_data = PersonaResearchInput(company_name="Acme Corp", max_personas=1)
        paths = ["/artifacts/personas/acme-corp__persona-icp.md"]
        agent = self._make_json_agent(paths)
        with patch.object(pa, "get_persona_agent", return_value=agent):
            result = pa.run_persona_agent(input_data, use_draft_paths=False)
        # Check the prompt sent to agent contains the derived slug
        prompt = agent.invoke.call_args[0][0]["messages"][0]["content"]
        assert "acme-corp" in prompt

    def test_revision_note_in_prompt(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, persona_input
    ):
        agent = self._make_json_agent(["/artifacts/personas/acme-corp__persona-icp.draft.md"])
        with patch.object(pa, "get_persona_agent", return_value=agent):
            pa.run_persona_agent(persona_input, revision_note="Add more KPIs", use_draft_paths=True)
        prompt = agent.invoke.call_args[0][0]["messages"][0]["content"]
        assert "Add more KPIs" in prompt

    def test_draft_paths_when_use_draft_true(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, persona_input
    ):
        paths = ["/artifacts/personas/acme-corp__persona-icp.draft.md"]
        agent = self._make_json_agent(paths)
        with patch.object(pa, "get_persona_agent", return_value=agent):
            pa.run_persona_agent(persona_input, use_draft_paths=True)
        prompt = agent.invoke.call_args[0][0]["messages"][0]["content"]
        assert ".draft.md" in prompt

    def test_final_paths_when_use_draft_false(
        self, mock_research_settings, mock_google_chat_model, isolated_artifacts, persona_input
    ):
        paths = ["/artifacts/personas/acme-corp__persona-icp.md"]
        agent = self._make_json_agent(paths)
        with patch.object(pa, "get_persona_agent", return_value=agent):
            pa.run_persona_agent(persona_input, use_draft_paths=False)
        prompt = agent.invoke.call_args[0][0]["messages"][0]["content"]
        assert ".draft.md" not in prompt
        assert "__persona-icp.md" in prompt
