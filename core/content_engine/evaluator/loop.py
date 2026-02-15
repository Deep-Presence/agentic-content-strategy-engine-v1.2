"""Evaluator-Optimizer loop — orchestrates 4 evaluation dimensions.

Runs structural, semantic, style, and factual checks in parallel.
If any dimension fails, compiles feedback and triggers a revision cycle
(re-draft → re-enrich → re-format → re-evaluate). Max 2 cycles.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

from core.config.settings import settings
from core.content_engine.evaluator.factual_judge import evaluate_factual
from core.content_engine.evaluator.semantic import evaluate_semantic
from core.content_engine.evaluator.structural import evaluate_structural
from core.content_engine.evaluator.style_judge import evaluate_style
from core.content_engine.pipeline import _cli_worker_progress
from core.content_engine.tracing import create_span, create_trace, end_span, log_score
from core.content_engine.workers.drafter import revise_draft
from core.content_engine.workers.fact_enricher import enrich_with_facts
from core.content_engine.workers.formatter import format_content
from core.models.content_generation import (
    ContentBrief,
    ContentGenerationInput,
    DimensionResult,
    EnrichedDraft,
    EvalResult,
    FormattedContent,
    RevisionHistory,
)

logger = logging.getLogger(__name__)


async def _run_all_evaluations(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str,
    style_guide_md: str,
    company_name: str,
    domain: str,
    *,
    trace: Optional[object] = None,
) -> list[DimensionResult]:
    """Run all 4 evaluation dimensions in parallel."""

    # Structural is sync — wrap in a lambda for gather
    structural_result = evaluate_structural(content, brief)

    # Run async evaluations in parallel
    semantic_task = evaluate_semantic(content, brief, trace=trace)
    style_task = evaluate_style(content, style_guide_md, trace=trace)
    factual_task = evaluate_factual(
        content, brief, company_name, domain, trace=trace
    )

    sem_result, style_result, factual_result = await asyncio.gather(
        semantic_task, style_task, factual_task,
        return_exceptions=True,
    )

    results = [structural_result]

    for dim_name, result in [
        ("semantic", sem_result),
        ("style", style_result),
        ("factual", factual_result),
    ]:
        if isinstance(result, Exception):
            logger.error("Evaluation dimension '%s' failed: %s", dim_name, result)
            results.append(
                DimensionResult(
                    dimension=dim_name,
                    passed=False,
                    score=0.0,
                    feedback=f"Evaluation error: {result}",
                )
            )
        else:
            results.append(result)

    return results


def _compile_feedback(dimensions: list[DimensionResult]) -> str:
    """Compile feedback from failed dimensions into a single string."""
    feedbacks = []
    for dim in dimensions:
        if not dim.passed and dim.feedback:
            feedbacks.append(f"[{dim.dimension.upper()}] {dim.feedback}")
    return "\n\n".join(feedbacks)


async def evaluate_and_optimize(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str,
    style_guide_md: str,
    input_data: ContentGenerationInput,
    max_cycles: int = 2,
    *,
    session_id: str = "",
    artifact_dir: Path = Path("."),
) -> Tuple[FormattedContent, RevisionHistory]:
    """Run the evaluation-optimization loop for a single content piece.

    Evaluates across 4 dimensions. If any fails, revises and re-evaluates
    up to max_cycles times.

    Args:
        content: Formatted content to evaluate.
        brief: Content brief with targets.
        company_context_md: Company context markdown.
        style_guide_md: Style guide markdown.
        input_data: Pipeline input for company details.
        max_cycles: Maximum revision cycles.
        session_id: Langfuse session ID.
        artifact_dir: Root artifact directory.

    Returns:
        Tuple of (final FormattedContent, RevisionHistory).
    """
    trace = create_trace(
        session_id,
        f"evaluator/{brief.brief_id}",
        metadata={"brief_id": brief.brief_id, "max_cycles": max_cycles},
    )

    history = RevisionHistory(brief_id=brief.brief_id)
    current_content = content

    for cycle in range(max_cycles + 1):  # +1 because first is initial eval
        cycle_span = create_span(
            trace, f"eval_cycle_{cycle}", metadata={"cycle": cycle}
        )

        dimensions = await _run_all_evaluations(
            content=current_content,
            brief=brief,
            company_context_md=company_context_md,
            style_guide_md=style_guide_md,
            company_name=input_data.company_name,
            domain=input_data.domain,
            trace=trace,
        )

        # Compute overall score and pass/fail
        scores = [d.score for d in dimensions]
        overall_score = sum(scores) / len(scores) if scores else 0.0
        overall_passed = all(d.passed for d in dimensions)

        eval_result = EvalResult(
            brief_id=brief.brief_id,
            cycle=cycle,
            dimensions=dimensions,
            overall_passed=overall_passed,
            overall_score=round(overall_score, 4),
        )
        history.cycles.append(eval_result)

        # CLI progress
        dim_summary = ", ".join(
            f"{d.dimension.capitalize()} {'PASSED' if d.passed else 'FAILED'} ({d.score:.2f})"
            for d in dimensions
        )
        _cli_worker_progress(f"{brief.brief_id}: {dim_summary}")

        log_score(trace, "overall_score", round(overall_score, 4), comment=f"cycle_{cycle}")
        end_span(cycle_span, output=f"overall={overall_score:.3f}, passed={overall_passed}")

        if overall_passed:
            _cli_worker_progress(f"{brief.brief_id}: ALL PASSED (overall: {overall_score:.2f})")
            history.final_passed = True
            break

        # If this was the last allowed cycle, don't revise
        if cycle >= max_cycles:
            _cli_worker_progress(
                f"{brief.brief_id}: FAILED after {max_cycles} revision cycles — flagging for HITL"
            )
            history.final_passed = False
            break

        # Compile feedback and trigger revision
        feedback = _compile_feedback(dimensions)
        _cli_worker_progress(
            f"{brief.brief_id}: Revision cycle {cycle + 1} — "
            f"fixing {sum(1 for d in dimensions if not d.passed)} dimensions"
        )

        revision_span = create_span(
            trace, f"revision_cycle_{cycle + 1}", metadata={"cycle": cycle + 1}
        )

        # Re-draft with feedback (skip outliner)
        revised_draft = await revise_draft(
            current_markdown=current_content.markdown,
            brief=brief,
            feedback=feedback,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            trace=trace,
        )

        # Re-enrich
        enriched = await enrich_with_facts(
            draft=revised_draft,
            brief=brief,
            company_name=input_data.company_name,
            domain=input_data.domain,
            trace=trace,
        )

        # Re-format
        current_content = await format_content(
            enriched=enriched,
            style_guide_md=style_guide_md,
            trace=trace,
        )

        end_span(revision_span, output=f"Revised: {current_content.word_count} words")

    log_score(
        trace,
        "revision_count",
        len(history.cycles) - 1,
        comment=f"final_passed={history.final_passed}",
    )

    return current_content, history
