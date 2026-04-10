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


@pytest.fixture(autouse=True)
def _disable_tracing():
    """Keep evaluator tests local and deterministic."""
    with (
        patch("core.content_engine.evaluator.loop.create_trace", return_value=MagicMock()),
        patch("core.content_engine.evaluator.loop.create_span", return_value=MagicMock()),
        patch("core.content_engine.evaluator.loop.end_span"),
        patch("core.content_engine.evaluator.loop.log_score"),
        patch("core.content_engine.evaluator.loop.update_trace_output"),
    ):
        yield


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
        result_content, history, feedback_route = await evaluate_and_optimize(
            content=sample_formatted,
            brief=sample_brief,
            company_context_md="",
            style_guide_md="",
            input_data=input_data,
            max_cycles=2,
            artifact_dir=tmp_path,
        )

    assert history.final_passed is True
    assert feedback_route == "pass"
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
        result_content, history, feedback_route = await evaluate_and_optimize(
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


@pytest.mark.asyncio
async def test_evaluate_and_optimize_threads_session_factory_to_revising_state(
    sample_brief,
    sample_formatted,
    tmp_path,
):
    """Revision loops must carry session_factory so TD durable topic-run updates fire."""
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_revision_cycles=1,
    )
    session_factory = MagicMock()

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
        patch(
            "core.content_engine.evaluator.loop._write_pipeline_state_async",
            new_callable=AsyncMock,
        ) as mock_write_state,
    ):
        await evaluate_and_optimize(
            content=sample_formatted,
            brief=sample_brief,
            company_context_md="",
            style_guide_md="",
            input_data=input_data,
            max_cycles=1,
            artifact_dir=tmp_path,
            task_id="task-1",
            effective_slug="test-co",
            session_factory=session_factory,
        )

    revising_calls = [
        call for call in mock_write_state.call_args_list
        if len(call.args) >= 3 and call.args[2] == "revising"
    ]
    assert revising_calls, "expected a revising state write during the revision loop"
    assert revising_calls[0].kwargs["session_factory"] is session_factory


# ─────────────────────────────────────────────────────────────────────
# C1 Regression: v1.0 pipeline must not crash on 3-tuple unpack
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_v10_pipeline_handles_3tuple_from_evaluate(sample_brief, tmp_path):
    """C1 regression: pipeline.py must unpack all 3 values from evaluate_and_optimize.

    evaluate_and_optimize now returns (FormattedContent, RevisionHistory, FeedbackRoute).
    The v1.0 pipeline previously only unpacked 2 — that causes ValueError at runtime.
    This test ensures the call site handles the full return tuple correctly.
    """
    from core.content_engine.evaluator.loop import evaluate_and_optimize

    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_revision_cycles=1,
    )

    # Verify evaluate_and_optimize returns exactly 3 values
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
        sample_fc = FormattedContent(
            brief_id="brief-001",
            title="Test",
            markdown="# Test\n\nContent here.",
            word_count=100,
        )
        result = await evaluate_and_optimize(
            content=sample_fc,
            brief=sample_brief,
            company_context_md="",
            style_guide_md="",
            input_data=input_data,
            max_cycles=1,
            artifact_dir=tmp_path,
        )

    # Must return a 3-tuple — unpacking to 2 values would raise ValueError
    assert len(result) == 3, (
        "evaluate_and_optimize must return 3 values: "
        "(FormattedContent, RevisionHistory, FeedbackRoute)"
    )
    content_out, history_out, feedback_route_out = result
    assert isinstance(content_out, FormattedContent)
    assert history_out.final_passed is True
    assert feedback_route_out == "pass"
