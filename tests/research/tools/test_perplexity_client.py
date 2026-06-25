"""Tests for the Perplexity Deep Research client (via OpenRouter)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import openai
import pytest

from core.research.tools import perplexity_client


# ---------------------------------------------------------------------------
# _client() tests
# ---------------------------------------------------------------------------

class TestClient:
    def test_raises_when_no_api_key(self):
        with patch.object(perplexity_client, "settings") as mock_settings:
            mock_settings.openrouter_api_key = None
            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
                perplexity_client._client()

    def test_creates_openai_client_with_openrouter_config(self):
        with patch.object(perplexity_client, "settings") as mock_settings, \
             patch.object(perplexity_client.openai, "OpenAI") as mock_cls:
            mock_settings.openrouter_api_key = "sk-or-test"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"
            perplexity_client._client(timeout_s=120.0)
            mock_cls.assert_called_once_with(
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-or-test",
                timeout=120.0,
                max_retries=0,
            )

    def test_creates_openai_client_with_explicit_workspace_key(self):
        with patch.object(perplexity_client, "settings") as mock_settings, \
             patch.object(perplexity_client.openai, "OpenAI") as mock_cls:
            mock_settings.openrouter_api_key = None
            mock_settings.openrouter_base_url = "https://platform.invalid"
            perplexity_client._client(
                timeout_s=120.0,
                api_key="sk-workspace",
                base_url="https://openrouter.workspace/api/v1",
            )
            mock_cls.assert_called_once_with(
                base_url="https://openrouter.workspace/api/v1",
                api_key="sk-workspace",
                timeout=120.0,
                max_retries=0,
            )


# ---------------------------------------------------------------------------
# research() tests
# ---------------------------------------------------------------------------

class TestResearch:
    def _make_completion(self, content: str = "Answer text", citations=None):
        """Build a mock completion response matching OpenAI SDK shape."""
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = citations
        # model_extra fallback
        completion.model_extra = {"citations": citations} if citations else {}
        return completion

    def test_returns_content_with_citations(self):
        completion = self._make_completion(
            content="Answer text",
            citations=["https://url1.com", "https://url2.com"],
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result, usage = perplexity_client.research("test query")

        assert "Answer text" in result
        assert "Sources:" in result
        assert "[1] https://url1.com" in result
        assert "[2] https://url2.com" in result
        assert isinstance(usage, dict)
        assert "prompt_tokens" in usage

    def test_returns_content_without_citations(self):
        completion = self._make_completion(content="Just an answer", citations=None)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result = perplexity_client.research("q")

        assert "Just an answer" in result
        assert "Sources:" not in result

    def test_empty_choices_returns_empty_string(self):
        completion = MagicMock()
        completion.choices = []
        completion.citations = None
        completion.model_extra = {}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result, usage = perplexity_client.research("q")

        assert result == ""

    def test_raises_on_auth_error(self):
        mock_client = MagicMock()
        # OpenAI SDK raises typed AuthenticationError
        mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            with pytest.raises(RuntimeError, match="API key invalid or expired"):
                perplexity_client.research("q")

    def test_raises_on_rate_limit(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = openai.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None,
        )

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            with pytest.raises(RuntimeError, match="rate limit or quota exceeded"):
                perplexity_client.research("q")

    def test_reraises_generic_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ValueError("500 server error")

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            with pytest.raises(ValueError, match="500 server error"):
                perplexity_client.research("q")

    def test_handles_content_none(self):
        msg = MagicMock()
        msg.content = None
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = None
        completion.model_extra = {}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result, usage = perplexity_client.research("q")

        assert result == ""

    def test_citations_via_model_extra_fallback(self):
        """When citations attr is None but model_extra has them."""
        msg = MagicMock()
        msg.content = "Answer"
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = None  # Direct attr is None
        completion.model_extra = {"citations": ["https://source.com"]}  # But model_extra has them
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result, usage = perplexity_client.research("q")

        assert "[1] https://source.com" in result

    def test_model_prefix_auto_added(self):
        """Bare 'sonar-deep-research' gets prefixed to 'perplexity/sonar-deep-research'."""
        completion = self._make_completion(content="ok")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-deep-research"
            perplexity_client.research("q")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "perplexity/sonar-deep-research"


# ---------------------------------------------------------------------------
# search() alias tests
# ---------------------------------------------------------------------------

class TestSearch:
    def test_delegates_to_research(self):
        _rv = ("result", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        with patch.object(perplexity_client, "research", return_value=_rv) as mock_research:
            result, usage = perplexity_client.search("test query")
            mock_research.assert_called_once_with(
                query="test query",
                max_results=8,
                search_depth="advanced",
                include_raw_content=False,
                include_answer=True,
                timeout_s=300.0,
                model=None,
                pipeline="",
                pipeline_step="",
                company_slug="",
            )
            assert result == "result"

    def test_passes_kwargs_through(self):
        _rv = ("r", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        with patch.object(perplexity_client, "research", return_value=_rv) as mock_research:
            perplexity_client.search("q", max_results=5, search_depth="basic")
            mock_research.assert_called_once_with(
                query="q",
                max_results=5,
                search_depth="basic",
                include_raw_content=False,
                include_answer=True,
                timeout_s=300.0,
                model=None,
                pipeline="",
                pipeline_step="",
                company_slug="",
            )


# ---------------------------------------------------------------------------
# Cost tracking tests
# ---------------------------------------------------------------------------

class TestResearchCostTracking:
    """Verify track_llm_cost() is called inside research()."""

    def _make_completion(self, content="Answer", prompt_tokens=100, completion_tokens=200):
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = None
        completion.model_extra = {}
        completion.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        return completion

    def test_cost_tracked_on_success(self):
        completion = self._make_completion(prompt_tokens=100, completion_tokens=200)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms, \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            ms.perplexity_deep_research_model = "sonar-deep-research"
            perplexity_client.research("test query")

        mock_track.assert_called_once()
        kw = mock_track.call_args[1]
        assert kw["model"] == "perplexity/sonar-deep-research"
        assert kw["provider"] == "openrouter"
        assert kw["prompt_tokens"] == 100
        assert kw["completion_tokens"] == 200
        assert kw["source"] == "openrouter"
        assert kw["call_site"] == "core.research.tools.perplexity_client"

    def test_cost_tracked_with_pipeline_params(self):
        completion = self._make_completion()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms, \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            ms.perplexity_deep_research_model = "sonar-deep-research"
            perplexity_client.research(
                "test query",
                pipeline="knowledge_base",
                pipeline_step="kb1_overview",
                company_slug="test-co",
            )

        kw = mock_track.call_args[1]
        assert kw["pipeline"] == "knowledge_base"
        assert kw["pipeline_step"] == "kb1_overview"
        assert kw["company_slug"] == "test-co"

    def test_cost_tracked_with_byok_metadata(self):
        completion = self._make_completion()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms, \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            ms.perplexity_deep_research_model = "sonar-deep-research"
            perplexity_client.research(
                "test query",
                api_key="sk-workspace",
                base_url="https://openrouter.workspace/api/v1",
                workspace_id="ws-123",
                agent_key="topic_discovery.source_c_deep_research",
                credential_id="cred-123",
                model_config_id="cfg-123",
                workspace_billed=True,
            )

        kw = mock_track.call_args[1]
        assert kw["workspace_id"] == "ws-123"
        assert kw["agent_key"] == "topic_discovery.source_c_deep_research"
        assert kw["credential_id"] == "cred-123"
        assert kw["model_config_id"] == "cfg-123"
        assert kw["actual_provider"] == "perplexity"
        assert kw["workspace_billed"] is True

    def test_cost_tracked_with_missing_usage(self):
        completion = self._make_completion()
        completion.usage = None
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms, \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            ms.perplexity_deep_research_model = "sonar-test"
            perplexity_client.research("q")

        kw = mock_track.call_args[1]
        assert kw["prompt_tokens"] == 0
        assert kw["completion_tokens"] == 0

    def test_cost_not_tracked_on_api_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms, \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            ms.perplexity_deep_research_model = "sonar-test"
            with pytest.raises(RuntimeError):
                perplexity_client.research("q")

        mock_track.assert_not_called()
