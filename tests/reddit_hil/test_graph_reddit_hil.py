"""Tests for Reddit HIL graph — LLM integration via OpenRouter.

First-ever test file for the Reddit HIL monitor.  Covers:
  - _get_llm() returns ChatOpenAI pointed at OpenRouter
  - _llm_select_and_draft() JSON parsing, cost tracking, error handling
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation_v13 import LLMResponse
from core.models.reddit_hil import DraftNotification, RedditThread


# ---------------------------------------------------------------------------
# _get_llm
# ---------------------------------------------------------------------------

_GRAPH_MOD = "core.reddit_hil.graph"
_OR_CLIENT_MOD = "core.shared_tools.openrouter_client"
_COST_MOD = "core.shared_tools.cost_tracker"


class TestGetLlm:
    """_get_llm() returns a ChatOpenAI pointed at OpenRouter."""

    def test_returns_chat_openai_instance(self) -> None:
        from langchain_openai import ChatOpenAI

        with patch(f"{_OR_CLIENT_MOD}.build_chat_openai_via_openrouter") as mock_build:
            mock_build.return_value = MagicMock(spec=ChatOpenAI)
            from core.reddit_hil.graph import _get_llm

            llm = _get_llm()

            assert isinstance(llm, ChatOpenAI)

    def test_passes_model_from_settings(self) -> None:
        with (
            patch(f"{_OR_CLIENT_MOD}.build_chat_openai_via_openrouter") as mock_build,
            patch(f"{_GRAPH_MOD}.settings") as mock_settings,
        ):
            mock_settings.google_gemini_model_reddit_hil = "google/gemini-3-flash-preview"
            mock_build.return_value = MagicMock()
            from core.reddit_hil.graph import _get_llm

            _get_llm()

            mock_build.assert_called_once_with("google/gemini-3-flash-preview")


# ---------------------------------------------------------------------------
# _llm_select_and_draft
# ---------------------------------------------------------------------------

def _make_thread(thread_id: str = "abc123") -> RedditThread:
    return RedditThread(
        id=thread_id,
        subreddit="testsubreddit",
        title="Test Thread",
        url="https://reddit.com/r/test/abc123",
        created_utc=1700000000.0,
        score=10,
        num_comments=5,
        selftext="Test body",
    )


def _make_candidates(thread_id: str = "abc123") -> List[Tuple[RedditThread, float]]:
    return [(_make_thread(thread_id), 0.8)]


def _valid_json_response(thread_id: str = "abc123") -> str:
    return json.dumps([{
        "thread_id": thread_id,
        "fit_score": 0.9,
        "why_match": "Great match for the ICP persona.",
        "draft_markdown": "Here is a helpful reply about the topic.",
    }])


class TestLlmSelectAndDraft:
    """_llm_select_and_draft() JSON parsing, cost tracking, error cases."""

    def test_valid_json_returns_draft_notifications(self) -> None:
        from core.reddit_hil.graph import _llm_select_and_draft

        mock_response = MagicMock()
        mock_response.content = _valid_json_response()
        mock_response.response_metadata = {}

        with patch(f"{_GRAPH_MOD}._get_llm") as mock_get:
            mock_get.return_value.invoke.return_value = mock_response
            results = _llm_select_and_draft(
                company_md="# Company", persona_md="# Persona",
                style_md="# Style", candidates=_make_candidates(),
                top_k=3,
            )

        assert len(results) == 1
        assert isinstance(results[0], DraftNotification)
        assert results[0].fit_score == pytest.approx(0.9)
        assert "helpful reply" in results[0].draft_markdown

    def test_workspace_context_uses_byok_agent_wrapper(self) -> None:
        from core.reddit_hil.graph import _llm_select_and_draft

        response = LLMResponse(
            content=_valid_json_response(),
            model="google/gemini-3-flash-preview",
            input_tokens=111,
            output_tokens=44,
            total_tokens=155,
        )

        with (
            patch(
                "core.content_engine.llm_client.llm_call_for_agent",
                new_callable=AsyncMock,
                return_value=response,
            ) as mock_call,
            patch(f"{_GRAPH_MOD}._get_llm") as mock_legacy,
            patch(f"{_COST_MOD}.track_llm_cost") as mock_track,
        ):
            results = _llm_select_and_draft(
                company_md="# Company",
                persona_md="# Persona",
                style_md="# Style",
                candidates=_make_candidates(),
                top_k=3,
                workspace_id="ws-123",
                workspace_slug="ramp",
            )

        assert len(results) == 1
        mock_legacy.assert_not_called()
        mock_track.assert_not_called()
        mock_call.assert_awaited_once()
        kwargs = mock_call.call_args.kwargs
        assert kwargs["workspace_id"] == "ws-123"
        assert kwargs["workspace_slug"] == "ramp"
        assert kwargs["agent_key"] == "reddit_hil.ranking_drafting"
        assert kwargs["metadata"]["pipeline"] == "reddit_hil"
        assert kwargs["metadata"]["pipeline_step"] == "select_and_draft"
        assert kwargs["metadata"]["company_slug"] == "ramp"

    def test_empty_content_raises(self) -> None:
        from core.reddit_hil.graph import _llm_select_and_draft

        mock_response = MagicMock()
        mock_response.content = ""
        mock_response.response_metadata = {}

        with patch(f"{_GRAPH_MOD}._get_llm") as mock_get:
            mock_get.return_value.invoke.return_value = mock_response
            with pytest.raises(RuntimeError, match="empty content"):
                _llm_select_and_draft(
                    company_md="# Company", persona_md="# Persona",
                    style_md="# Style", candidates=_make_candidates(),
                    top_k=3,
                )

    def test_invalid_json_raises(self) -> None:
        from core.reddit_hil.graph import _llm_select_and_draft

        mock_response = MagicMock()
        mock_response.content = "Not valid JSON {{{"
        mock_response.response_metadata = {}

        with patch(f"{_GRAPH_MOD}._get_llm") as mock_get:
            mock_get.return_value.invoke.return_value = mock_response
            with pytest.raises(RuntimeError, match="valid JSON"):
                _llm_select_and_draft(
                    company_md="# Company", persona_md="# Persona",
                    style_md="# Style", candidates=_make_candidates(),
                    top_k=3,
                )

    def test_extracts_openai_format_usage(self) -> None:
        """After migration to ChatOpenAI, usage comes as token_usage with prompt_tokens/completion_tokens."""
        from core.reddit_hil.graph import _llm_select_and_draft

        mock_response = MagicMock()
        mock_response.content = _valid_json_response()
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 500, "completion_tokens": 200},
        }

        with (
            patch(f"{_GRAPH_MOD}._get_llm") as mock_get,
            patch(f"{_COST_MOD}.track_llm_cost") as mock_track,
        ):
            mock_get.return_value.invoke.return_value = mock_response
            _llm_select_and_draft(
                company_md="# Company", persona_md="# Persona",
                style_md="# Style", candidates=_make_candidates(),
                top_k=3,
            )

            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args.kwargs
            assert call_kwargs["prompt_tokens"] == 500
            assert call_kwargs["completion_tokens"] == 200
            assert call_kwargs["source"] == "openrouter"

    def test_char_count_fallback_when_no_usage(self) -> None:
        """When token_usage is empty, falls back to char-count estimation."""
        from core.reddit_hil.graph import _llm_select_and_draft

        mock_response = MagicMock()
        mock_response.content = _valid_json_response()
        mock_response.response_metadata = {}  # No token_usage

        with (
            patch(f"{_GRAPH_MOD}._get_llm") as mock_get,
            patch(f"{_COST_MOD}.track_llm_cost") as mock_track,
        ):
            mock_get.return_value.invoke.return_value = mock_response
            _llm_select_and_draft(
                company_md="# Company", persona_md="# Persona",
                style_md="# Style", candidates=_make_candidates(),
                top_k=3,
            )

            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args.kwargs
            # Char-count estimation: tokens > 0 (prompt is non-trivial)
            assert call_kwargs["prompt_tokens"] > 0
            extra = call_kwargs.get("extra", {})
            assert extra.get("estimation_method") == "char_count"
