"""Tests for Daily Tracker query fanout generation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.daily_tracker.query_fanout import QueryFanoutService


def _response_payload() -> str:
    return json.dumps(
        {
            "queries": [
                {
                    "axis": "comparative",
                    "query_text": "best AP automation platforms",
                    "reasoning": "Category-level comparison query",
                }
            ]
        }
    )


class TestQueryFanoutByok:
    @pytest.mark.asyncio
    async def test_workspace_context_uses_byok_llm_wrapper(self) -> None:
        service = QueryFanoutService(
            model="anthropic/claude-sonnet-4-6",
            max_retries=1,
            base_delay=0.01,
        )
        response = MagicMock(
            content=_response_payload(),
            model="anthropic/claude-sonnet-4-6",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
        )

        with (
            patch(
                "core.content_engine.llm_client.llm_call_for_agent",
                new_callable=AsyncMock,
                return_value=response,
            ) as mock_call,
            patch("core.shared_tools.openrouter_client.get_async_client") as mock_platform,
        ):
            result = await service.generate_fanout(
                parent_text="best AP automation software",
                brand_name="Ramp",
                brand_category="Finance",
                competitors=["Brex"],
                target_count=12,
                workspace_id="ws-123",
                workspace_slug="ramp",
                company_slug="ramp",
            )

        assert len(result.queries) == 1
        assert result.model_used == "anthropic/claude-sonnet-4-6"
        assert result.token_usage["total_tokens"] == 30
        mock_platform.assert_not_called()
        mock_call.assert_awaited_once()
        kwargs = mock_call.call_args.kwargs
        assert kwargs["workspace_id"] == "ws-123"
        assert kwargs["workspace_slug"] == "ramp"
        assert kwargs["agent_key"] == "daily_tracker.fanout"
        assert kwargs["metadata"]["pipeline_step"] == "fanout_generation"
        assert kwargs["metadata"]["company_slug"] == "ramp"
