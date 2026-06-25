"""Tests for the GA Perplexity search engine (OpenRouter-routed)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.gap_analysis.engines.perplexity import PerplexityEngine


class TestPerplexityEngineCostTracking:
    """Verify track_llm_cost() is called inside PerplexityEngine.search()."""

    @pytest.mark.asyncio
    async def test_cost_tracked_on_search(self):
        msg = MagicMock()
        msg.content = "search result"
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = ["https://example.com"]
        completion.model_extra = {}
        completion.usage = MagicMock(prompt_tokens=80, completion_tokens=150)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=completion)

        engine = PerplexityEngine(model="perplexity/sonar-pro")

        with patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            result = await engine.search("test query", client=mock_client)

        mock_track.assert_called_once()
        kw = mock_track.call_args[1]
        assert kw["pipeline"] == "gap_analysis"
        assert kw["pipeline_step"] == "s3_perplexity_engine"
        assert kw["model"] == "perplexity/sonar-pro"
        assert kw["prompt_tokens"] == 80
        assert kw["completion_tokens"] == 150
        assert kw["source"] == "openrouter"

    @pytest.mark.asyncio
    async def test_cost_tracked_with_missing_usage(self):
        msg = MagicMock()
        msg.content = "result"
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        completion.citations = None
        completion.model_extra = {}
        completion.usage = None

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=completion)

        engine = PerplexityEngine(model="perplexity/sonar-pro")

        with patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            await engine.search("test query", client=mock_client)

        kw = mock_track.call_args[1]
        assert kw["prompt_tokens"] == 0
        assert kw["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_workspace_search_requires_resolved_byok_client(self):
        engine = PerplexityEngine(model="perplexity/sonar-pro")

        with (
            patch("core.shared_tools.openrouter_client.get_async_client") as mock_singleton,
            pytest.raises(RuntimeError, match="requires a workspace OpenRouter client"),
        ):
            await engine.search(
                "test query",
                workspace_id="ws-123",
                workspace_slug="ramp",
            )

        mock_singleton.assert_not_called()
