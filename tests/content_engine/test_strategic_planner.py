"""Tests for core.content_engine.strategic_planner — Agent 1.

Tests select_topics() with mocked llm_call and tracing.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation_v13 import (
    PlannerScorecard,
    QueryScorecard,
    StrategicPlannerOutput,
    TopicSelection,
)
from tests.content_engine.conftest import _make_llm_response


def _planner_output_json(selections=None):
    """Build a valid StrategicPlannerOutput JSON string."""
    if selections is None:
        selections = [
            TopicSelection(
                rank=1, query_ids=["q-001"],
                query_texts=["what is a 409A valuation"],
                cluster_name="equity",
                rationale="High gap with strong exemplars",
                estimated_impact="high",
            ),
            TopicSelection(
                rank=2, query_ids=["q-003"],
                query_texts=["startup fundraising"],
                cluster_name="fundraising",
                rationale="Critical content gap",
                estimated_impact="medium",
            ),
        ]
    output = StrategicPlannerOutput(
        selections=selections,
        selection_metadata={},
    )
    return json.dumps(output.model_dump(mode="json"), default=str)


# Patch paths for tracing + llm_call
_TRACING_PATCHES = [
    "core.content_engine.strategic_planner.create_span",
    "core.content_engine.strategic_planner.end_span",
    "core.content_engine.strategic_planner.log_generation",
]


@pytest.fixture(autouse=True)
def _mock_tracing():
    """Disable LangSmith tracing for all planner tests."""
    with patch(_TRACING_PATCHES[0], return_value=MagicMock()) as m1, \
         patch(_TRACING_PATCHES[1]) as m2, \
         patch(_TRACING_PATCHES[2]) as m3:
        yield {"create_span": m1, "end_span": m2, "log_generation": m3}


class TestSelectTopics:
    """Tests for select_topics()."""

    @pytest.mark.asyncio
    async def test_returns_strategic_planner_output(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await select_topics(sample_scorecard)

        assert isinstance(result, StrategicPlannerOutput)
        assert len(result.selections) == 2

    @pytest.mark.asyncio
    async def test_uses_byok_agent_call_when_workspace_present(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call_for_agent",
                   new_callable=AsyncMock, return_value=resp) as mock_byok, \
             patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock) as mock_legacy:
            result = await select_topics(
                sample_scorecard,
                company_slug="test-co",
                workspace_id="workspace-123",
            )

        assert len(result.selections) == 2
        mock_legacy.assert_not_called()
        mock_byok.assert_awaited_once()
        kwargs = mock_byok.await_args.kwargs
        assert kwargs["workspace_id"] == "workspace-123"
        assert kwargs["workspace_slug"] == "test-co"
        assert kwargs["agent_key"] == "content.strategic_planner"
        assert kwargs["metadata"]["agent_key"] == "content.strategic_planner"

    @pytest.mark.asyncio
    async def test_topic_ranking(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await select_topics(sample_scorecard)

        assert result.selections[0].rank == 1
        assert result.selections[1].rank == 2
        assert result.selections[0].estimated_impact == "high"

    @pytest.mark.asyncio
    async def test_metadata_enriched(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(
            _planner_output_json(), input_tokens=500, output_tokens=200,
        )
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await select_topics(sample_scorecard)

        assert result.selection_metadata["input_tokens"] == 500
        assert result.selection_metadata["output_tokens"] == 200
        assert result.selection_metadata["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_max_topics_passed_to_prompt_builder(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp) as mock_call, \
             patch("core.content_engine.strategic_planner.build_strategic_planner_user_prompt",
                   return_value="test prompt") as mock_build:
            await select_topics(sample_scorecard, max_topics=3)

        mock_build.assert_called_once()
        assert mock_build.call_args[1]["max_topics"] == 3

    @pytest.mark.asyncio
    async def test_user_feedback_passed_to_prompt_builder(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp), \
             patch("core.content_engine.strategic_planner.build_strategic_planner_user_prompt",
                   return_value="test prompt") as mock_build:
            await select_topics(sample_scorecard, user_feedback="Focus on equity topics")

        assert mock_build.call_args[1]["user_feedback"] == "Focus on equity topics"

    @pytest.mark.asyncio
    async def test_empty_scorecard_produces_valid_output(self):
        from core.content_engine.strategic_planner import select_topics

        empty_sc = PlannerScorecard()
        resp = _make_llm_response(
            json.dumps({"selections": [], "selection_metadata": {}})
        )
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await select_topics(empty_sc)

        assert isinstance(result, StrategicPlannerOutput)
        assert result.selections == []

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response("This is not JSON")
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            with pytest.raises((ValueError, Exception)):
                await select_topics(sample_scorecard)

    @pytest.mark.asyncio
    async def test_tracing_span_created_and_ended(self, sample_scorecard, _mock_tracing):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            await select_topics(sample_scorecard, parent_span=MagicMock())

        _mock_tracing["create_span"].assert_called_once()
        _mock_tracing["end_span"].assert_called_once()

    @pytest.mark.asyncio
    async def test_query_ids_in_selections(self, sample_scorecard):
        from core.content_engine.strategic_planner import select_topics

        resp = _make_llm_response(_planner_output_json())
        with patch("core.content_engine.strategic_planner.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await select_topics(sample_scorecard)

        assert result.selections[0].query_ids == ["q-001"]
        assert result.selections[0].cluster_name == "equity"
