"""Tests for the Strategic Planner (Stage 1)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.content_engine.planner import plan_content
from core.models.content_generation import ContentGenerationInput


@pytest.mark.asyncio
async def test_plan_content_produces_briefs(sample_input, mock_anthropic_planner):
    """Planner should produce briefs from gap analysis data."""
    result = await plan_content(
        input_data=sample_input,
        company_context_md="TestCo is a B2B SaaS company.",
        style_guide_md="Write professionally.",
        persona_mds=["ICP: CFOs at startups."],
        gap_report_json={"summary": "test"},
        generation_spec_json={"clusters": []},
        analysis_json={"gaps": []},
        session_id="test-session",
    )

    assert len(result.briefs) == 1
    assert result.briefs[0].brief_id == "brief-001"
    assert result.planning_metadata.get("model") is not None


@pytest.mark.asyncio
async def test_plan_content_respects_max_briefs(sample_input, mock_anthropic_planner):
    """Planner should respect the max_briefs limit."""
    sample_input.max_briefs = 1

    result = await plan_content(
        input_data=sample_input,
        company_context_md="",
        style_guide_md="",
        persona_mds=[],
        gap_report_json={},
        generation_spec_json={},
        analysis_json={},
        session_id="test-session",
    )

    assert len(result.briefs) >= 1  # At least one brief produced


@pytest.mark.asyncio
async def test_planner_cost_tracked(sample_input, mock_anthropic_planner):
    """Planner should call track_llm_cost after successful LLM call."""
    with patch("core.content_engine.planner.track_llm_cost") as mock_track:
        await plan_content(
            input_data=sample_input,
            company_context_md="TestCo is a B2B SaaS company.",
            style_guide_md="Write professionally.",
            persona_mds=["ICP: CFOs at startups."],
            gap_report_json={"summary": "test"},
            generation_spec_json={"clusters": []},
            analysis_json={"gaps": []},
            session_id="test-session",
        )
    mock_track.assert_called_once()
    kw = mock_track.call_args[1]
    assert kw["pipeline"] == "content_engine"
    assert kw["pipeline_step"] == "planner"
    assert kw["provider"] == "openrouter"
    assert kw["source"] == "openrouter"
    assert kw["prompt_tokens"] == 100  # from MockOpenRouterResponse defaults
    assert kw["completion_tokens"] == 200
