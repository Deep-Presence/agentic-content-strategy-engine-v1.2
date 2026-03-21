"""Tests for the Perplexity Deep Research client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.research.tools import perplexity_client


# ---------------------------------------------------------------------------
# _client() tests
# ---------------------------------------------------------------------------

class TestClient:
    def test_raises_when_no_api_key(self):
        with patch.object(perplexity_client, "settings") as mock_settings:
            mock_settings.perplexity_api_key = None
            with pytest.raises(RuntimeError, match="PERPLEXITY_API_KEY is not set"):
                perplexity_client._client()

    def test_creates_instance_with_api_key(self):
        with patch.object(perplexity_client, "settings") as mock_settings, \
             patch("core.research.tools.perplexity_client.Perplexity", create=True) as mock_cls:
            mock_settings.perplexity_api_key = "test-key-123"
            # _client() does a lazy import, so we need to patch inside the function
            # We patch at module level after import
            with patch.dict("sys.modules", {"perplexity": MagicMock(Perplexity=mock_cls)}):
                result = perplexity_client._client()
                mock_cls.assert_called_once_with(api_key="test-key-123", timeout=300.0)


# ---------------------------------------------------------------------------
# research() tests
# ---------------------------------------------------------------------------

class TestResearch:
    def _make_completion(self, content: str = "Answer text", citations=None):
        """Build a mock completion response matching Perplexity SDK shape."""
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = citations
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
            result = perplexity_client.research("test query")

        assert "Answer text" in result
        assert "Sources:" in result
        assert "[1] https://url1.com" in result
        assert "[2] https://url2.com" in result

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
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result = perplexity_client.research("q")

        assert result == ""

    def test_raises_on_auth_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("401 Authorization invalid")

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            with pytest.raises(RuntimeError, match="API key invalid or expired"):
                perplexity_client.research("q")

    def test_raises_on_rate_limit(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("429 rate limit exceeded")

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
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion

        with patch.object(perplexity_client, "_client", return_value=mock_client), \
             patch.object(perplexity_client, "settings") as ms:
            ms.perplexity_deep_research_model = "sonar-test"
            result = perplexity_client.research("q")

        assert result == ""


# ---------------------------------------------------------------------------
# search() alias tests
# ---------------------------------------------------------------------------

class TestSearch:
    def test_delegates_to_research(self):
        with patch.object(perplexity_client, "research", return_value="result") as mock_research:
            result = perplexity_client.search("test query")
            mock_research.assert_called_once_with(
                query="test query",
                max_results=8,
                search_depth="advanced",
                include_raw_content=False,
                include_answer=True,
                timeout_s=300.0,
                model=None,
            )
            assert result == "result"

    def test_passes_kwargs_through(self):
        with patch.object(perplexity_client, "research", return_value="r") as mock_research:
            perplexity_client.search("q", max_results=5, search_depth="basic")
            mock_research.assert_called_once_with(
                query="q",
                max_results=5,
                search_depth="basic",
                include_raw_content=False,
                include_answer=True,
                timeout_s=300.0,
                model=None,
            )
