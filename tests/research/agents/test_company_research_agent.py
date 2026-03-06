"""Tests for the company research agent: tools, build, get, _extract_final_markdown."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.research.agents import company_research_agent as cra
from core.research.graphs.company_research import _extract_final_markdown


# ---------------------------------------------------------------------------
# internet_search tool
# ---------------------------------------------------------------------------

class TestInternetSearch:
    def test_delegates_to_perplexity_research(self, mock_perplexity_research):
        result = cra.internet_search("test query about Acme")
        assert result == mock_perplexity_research


# ---------------------------------------------------------------------------
# read_local_text tool
# ---------------------------------------------------------------------------

class TestReadLocalText:
    def test_reads_file_content(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("hello world", encoding="utf-8")
        result = cra.read_local_text(str(f))
        assert result == "hello world"

    def test_truncates_to_max_chars(self, tmp_path):
        f = tmp_path / "long.txt"
        f.write_text("x" * 10000, encoding="utf-8")
        result = cra.read_local_text(str(f), max_chars=100)
        assert len(result) == 100

    def test_returns_error_for_missing_file(self):
        result = cra.read_local_text("/nonexistent/path.txt")
        assert "ERROR: path not found" in result


# ---------------------------------------------------------------------------
# build_agent / get_agent
# ---------------------------------------------------------------------------

class TestBuildAgent:
    def test_with_correct_model(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        agent = cra.build_agent()
        assert agent is not None

    def test_includes_both_tools(self, mock_research_settings, mock_google_chat_model):
        """Verify create_deep_agent is called with internet_search and read_local_text tools."""
        with patch.object(cra, "create_deep_agent", return_value=MagicMock()) as mock_create:
            cra.build_agent()
            call_kwargs = mock_create.call_args
            tools = call_kwargs.kwargs.get("tools") or call_kwargs[1].get("tools") or call_kwargs[0][1]
            tool_names = [t.__name__ for t in tools]
            assert "internet_search" in tool_names
            assert "read_local_text" in tool_names


class TestGetAgent:
    def test_returns_instance(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        agent = cra.get_agent()
        assert agent is not None

    def test_caches_singleton(
        self, mock_research_settings, mock_google_chat_model, mock_create_deep_agent
    ):
        a1 = cra.get_agent()
        a2 = cra.get_agent()
        assert a1 is a2

    def test_raises_when_no_api_key(self):
        with patch.object(cra, "settings") as mock_settings:
            mock_settings.google_api_key_company_deepagent = None
            with pytest.raises(RuntimeError, match="GOOGLE_API_KEY_COMPANY_DEEPAGENT"):
                cra.build_agent()


# ---------------------------------------------------------------------------
# _extract_final_markdown (defined in company_research graph, tested here)
# ---------------------------------------------------------------------------

class TestExtractFinalMarkdown:
    def test_from_dict_messages(self):
        msgs = [
            {"role": "user", "content": "do research"},
            {"role": "assistant", "content": "# Acme Context\n\nGreat company."},
        ]
        result = _extract_final_markdown(msgs)
        assert "# Acme Context" in result

    def test_from_basemessage_objects(self):
        msg = MagicMock()
        msg.type = "ai"
        msg.content = "# Result\n\nContent here."
        result = _extract_final_markdown([msg])
        assert "# Result" in result

    def test_skips_empty_tool_calls(self):
        """Falls back to previous non-empty assistant message."""
        msgs = [
            {"role": "user", "content": "prompt"},
            {"role": "assistant", "content": "# Real Content\n\nSome text."},
            {"role": "assistant", "content": ""},  # tool-call with empty content
        ]
        result = _extract_final_markdown(msgs)
        assert "# Real Content" in result

    def test_empty_messages_returns_empty(self):
        assert _extract_final_markdown([]) == ""
        assert _extract_final_markdown(None) == ""
