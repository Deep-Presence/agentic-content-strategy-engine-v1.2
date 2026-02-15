"""Tests for the evaluator loop."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.evaluator.loop import evaluate_and_optimize
from core.models.content_generation import (
    ContentGenerationInput,
    DimensionResult,
    FormattedContent,
)


@pytest.mark.asyncio
async def test_evaluate_and_optimize_all_pass(sample_brief, sample_formatted, tmp_path):
    """When all dimensions pass on first eval, no revisions should occur."""
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_revision_cycles=2,
    )

    # Mock all evaluators to pass
    with (
        patch(
            "core.content_engine.evaluator.loop.evaluate_structural",
            return_value=DimensionResult(dimension="structural", passed=True, score=0.9),
        ),
        patch(
            "core.content_engine.evaluator.loop.evaluate_semantic",
            new_callable=AsyncMock,
            return_value=DimensionResult(dimension="semantic", passed=True, score=0.8),
        ),
        patch(
            "core.content_engine.evaluator.loop.evaluate_style",
            new_callable=AsyncMock,
            return_value=DimensionResult(dimension="style", passed=True, score=0.85),
        ),
        patch(
            "core.content_engine.evaluator.loop.evaluate_factual",
            new_callable=AsyncMock,
            return_value=DimensionResult(dimension="factual", passed=True, score=0.75),
        ),
    ):
        result_content, history = await evaluate_and_optimize(
            content=sample_formatted,
            brief=sample_brief,
            company_context_md="",
            style_guide_md="",
            input_data=input_data,
            max_cycles=2,
            artifact_dir=tmp_path,
        )

    assert history.final_passed is True
    assert len(history.cycles) == 1  # Only initial eval, no revisions
    assert history.cycles[0].overall_passed is True


@pytest.mark.asyncio
async def test_evaluate_and_optimize_revision_triggered(sample_brief, sample_formatted, tmp_path):
    """When a dimension fails, revision should be triggered."""
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_revision_cycles=1,
    )

    call_count = 0

    def _structural_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return DimensionResult(dimension="structural", passed=False, score=0.6, feedback="Too short")
        return DimensionResult(dimension="structural", passed=True, score=0.9)

    with (
        patch(
            "core.content_engine.evaluator.loop.evaluate_structural",
            side_effect=_structural_side_effect,
        ),
        patch(
            "core.content_engine.evaluator.loop.evaluate_semantic",
            new_callable=AsyncMock,
            return_value=DimensionResult(dimension="semantic", passed=True, score=0.8),
        ),
        patch(
            "core.content_engine.evaluator.loop.evaluate_style",
            new_callable=AsyncMock,
            return_value=DimensionResult(dimension="style", passed=True, score=0.85),
        ),
        patch(
            "core.content_engine.evaluator.loop.evaluate_factual",
            new_callable=AsyncMock,
            return_value=DimensionResult(dimension="factual", passed=True, score=0.75),
        ),
        patch(
            "core.content_engine.evaluator.loop.revise_draft",
            new_callable=AsyncMock,
            return_value=MagicMock(
                brief_id="brief-001", title="T", markdown="# Revised", word_count=1500
            ),
        ),
        patch(
            "core.content_engine.evaluator.loop.enrich_with_facts",
            new_callable=AsyncMock,
            return_value=MagicMock(
                brief_id="brief-001", title="T", markdown="# Enriched", word_count=1500
            ),
        ),
        patch(
            "core.content_engine.evaluator.loop.format_content",
            new_callable=AsyncMock,
            return_value=FormattedContent(
                brief_id="brief-001",
                title="T",
                markdown="# Formatted",
                word_count=1500,
                header_count=4,
                list_count=3,
                stat_count=2,
                citation_count=3,
            ),
        ),
    ):
        result_content, history = await evaluate_and_optimize(
            content=sample_formatted,
            brief=sample_brief,
            company_context_md="",
            style_guide_md="",
            input_data=input_data,
            max_cycles=1,
            artifact_dir=tmp_path,
        )

    # Should have 2 cycles: initial fail + revision pass
    assert len(history.cycles) == 2
    assert history.cycles[0].overall_passed is False
    assert history.cycles[1].overall_passed is True
    assert history.final_passed is True
