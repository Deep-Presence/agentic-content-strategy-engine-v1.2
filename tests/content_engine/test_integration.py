"""End-to-end integration test for the content generation pipeline.

Runs the full 4-stage pipeline with all LLM calls mocked.
Tests the wiring between stages, artifact persistence, and CLI output.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.pipeline import run_content_generation
from core.models.content_generation import (
    ContentBrief,
    ContentGenerationInput,
    ContentOutline,
    ContentStatus,
    DimensionResult,
    FormattedContent,
    OutlineSection,
    PlannerOutput,
    StructuralTargets,
    TargetQuery,
)


def _make_planner_output():
    """Create a realistic PlannerOutput for testing."""
    return PlannerOutput(
        briefs=[
            ContentBrief(
                brief_id="brief-001",
                title="Test Article About 409A Valuations",
                target_queries=[
                    TargetQuery(query_text="what is 409A", cluster_name="equity"),
                ],
                target_cluster="equity",
                word_count_range=(1200, 2000),
                structural_targets=StructuralTargets(min_headers=3, min_lists=1, min_citations=1),
                key_topics=["409A", "valuations"],
            ),
        ],
        planning_metadata={"model": "test"},
    )


def _make_formatted_content():
    """Create realistic FormattedContent for testing."""
    return FormattedContent(
        brief_id="brief-001",
        title="Test Article About 409A Valuations",
        markdown="# 409A Valuations\n\n## What is 409A?\n\nA 409A valuation is...\n\n"
        "## Why it matters\n\n- Tax compliance\n- Employee protection\n\n"
        "93% of startups get them [Carta, 2024].\n\n"
        "## Process\n\n1. Hire a firm\n2. Submit docs\n3. Get report",
        word_count=1500,
        header_count=3,
        list_count=5,
        stat_count=1,
        citation_count=1,
    )


@pytest.mark.asyncio
async def test_full_pipeline_auto_approve(tmp_path):
    """Full pipeline run with auto-approve — all stages mocked."""
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_briefs=1,
        max_concurrent_workers=1,
        max_revision_cycles=0,  # Skip eval loop
        auto_approve=True,
    )

    planner_output = _make_planner_output()
    formatted = _make_formatted_content()

    with (
        # Mock Stage 1: Planner — patch the source module
        patch(
            "core.content_engine.planner.plan_content",
            new_callable=AsyncMock,
            return_value=planner_output,
        ) as mock_planner,
        # Mock Stage 2: Workers — patch the source module
        patch(
            "core.content_engine.workers.dispatcher.dispatch_workers",
            new_callable=AsyncMock,
            return_value=[formatted],
        ) as mock_workers,
        # Mock artifact dir to use tmp_path
        patch(
            "core.content_engine.pipeline._artifact_dir",
            return_value=tmp_path,
        ),
    ):
        output = await run_content_generation(input_data)

    # Verify output
    assert output.company_slug == "testco"
    assert output.total_briefs == 1
    assert output.total_approved == 1
    assert output.total_rejected == 0
    assert len(output.pieces) == 1
    assert output.pieces[0].status == ContentStatus.APPROVED
    assert output.pieces[0].brief_id == "brief-001"

    # Verify artifacts were persisted
    assert (tmp_path / "briefs.json").exists()
    assert (tmp_path / "run_metadata.json").exists()

    # Verify run_metadata content
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    assert metadata["company_slug"] == "testco"
    assert metadata["total_approved"] == 1


@pytest.mark.asyncio
async def test_pipeline_skip_stages(tmp_path):
    """Pipeline should skip stages when specified."""
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_briefs=1,
        auto_approve=True,
        skip_stages=[2, 3],  # Skip workers and eval
    )

    planner_output = _make_planner_output()
    formatted = _make_formatted_content()

    # Create pre-existing formatted content for skip
    brief_dir = tmp_path / "content" / "brief-001"
    brief_dir.mkdir(parents=True)
    (brief_dir / "formatted.md").write_text(formatted.markdown)

    with (
        patch(
            "core.content_engine.planner.plan_content",
            new_callable=AsyncMock,
            return_value=planner_output,
        ),
        patch(
            "core.content_engine.pipeline._artifact_dir",
            return_value=tmp_path,
        ),
    ):
        output = await run_content_generation(input_data)

    assert output.total_approved == 1
    assert 2 in output.run_metadata["skip_stages"]
