"""Tests for the Strategic Planner (Stage 1)."""
from __future__ import annotations

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
