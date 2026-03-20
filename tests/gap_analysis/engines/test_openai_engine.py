"""Tests for OpenAI engine — Fix 6: fallback logging."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.gap_analysis import PlatformResult


class TestOpenAIEngineFallback:
    """Verify web_search fallback logs a warning."""

    @pytest.mark.asyncio
    async def test_web_search_fallback_logs_warning(self, caplog):
        """When web_search request fails, should log warning and still return result."""
        mock_client = MagicMock()

        # First call (web_search) raises; second call (plain) succeeds
        call_count = 0

        async def _selective_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("web_search tool not available")
            return MagicMock(output_text="fallback response")

        mock_client.responses = MagicMock()
        mock_client.responses.create = AsyncMock(side_effect=_selective_create)

        with patch(
            "core.gap_analysis.engines.openai_engine.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.gap_analysis_openai_engine_model = "gpt-test"

            from core.gap_analysis.engines.openai_engine import OpenAIEngine

            engine = OpenAIEngine(model="gpt-test")
            with caplog.at_level(logging.WARNING, logger="core.gap_analysis.engines.openai_engine"):
                result = await engine.search("test query", "q1", client=mock_client)

        assert isinstance(result, PlatformResult)
        assert result.response_text == "fallback response"
        assert result.citations == []
        # Verify warning was logged
        assert any("web_search failed" in record.message for record in caplog.records), (
            f"Expected 'web_search failed' warning, got: {[r.message for r in caplog.records]}"
        )

    @pytest.mark.asyncio
    async def test_web_search_success_no_warning(self, caplog):
        """When web_search succeeds, no warning should be logged."""
        mock_client = MagicMock()

        async def _success_create(**kwargs):
            return MagicMock(output=[], output_text="success")

        mock_client.responses = MagicMock()
        mock_client.responses.create = AsyncMock(side_effect=_success_create)

        with patch(
            "core.gap_analysis.engines.openai_engine.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.gap_analysis_openai_engine_model = "gpt-test"

            from core.gap_analysis.engines.openai_engine import OpenAIEngine

            engine = OpenAIEngine(model="gpt-test")
            with caplog.at_level(logging.WARNING, logger="core.gap_analysis.engines.openai_engine"):
                result = await engine.search("test query", "q1", client=mock_client)

        assert isinstance(result, PlatformResult)
        assert not any("web_search failed" in record.message for record in caplog.records)
