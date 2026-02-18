"""Evaluator-Optimizer loop — orchestrates 4 evaluation dimensions.

Runs structural, semantic, style, and factual checks in parallel.
If any dimension fails, compiles feedback and triggers a revision cycle
(re-draft → re-enrich → re-format → re-evaluate).

v2.0: Format-aware revision cycles, early-stop on score plateau.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from core.config.settings import settings
from core.content_engine.evaluator.factual_judge import evaluate_factual
from core.content_engine.evaluator.semantic import evaluate_semantic
from core.content_engine.evaluator.structural import evaluate_structural
from core.content_engine.evaluator.style_judge import evaluate_style
from core.content_engine.pipeline import _cli_worker_progress
from core.content_engine.tracing import (
    create_span,
    create_trace,
    end_span,
    log_score,
    update_trace_output,
)
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

    # Structural is sync (no LLM calls)
    structural_result = evaluate_structural(content, brief, trace=trace)

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


def _get_max_cycles(brief: ContentBrief, default: int = 2) -> int:
    """Look up format-aware max revision cycles from settings.

    Falls back to the explicit default if the content format isn't in the
    config or the JSON is malformed.
    """
    try:
        cycles_map = json.loads(settings.content_engine_revision_cycles_by_format)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid revision_cycles_by_format config, using default=%d", default)
        return default

    content_format = getattr(brief, "content_format", None) or ""
    return cycles_map.get(content_format, default)


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
    parent_span: Optional[object] = None,
) -> Tuple[FormattedContent, RevisionHistory]:
    """Run the evaluation-optimization loop for a single content piece.

    Evaluates across 4 dimensions. If any fails, revises and re-evaluates
    up to max_cycles times. Uses format-aware cycle limits and early-stops
    when score improvement plateaus (<0.02 between cycles).

    Args:
        content: Formatted content to evaluate.
        brief: Content brief with targets.
        company_context_md: Company context markdown.
        style_guide_md: Style guide markdown.
        input_data: Pipeline input for company details.
        max_cycles: Maximum revision cycles (overridden by format-aware config).
        session_id: Langfuse session ID.
        artifact_dir: Root artifact directory.

    Returns:
        Tuple of (final FormattedContent, RevisionHistory).
    """
    # Format-aware revision cycles override the default max_cycles
    max_cycles = _get_max_cycles(brief, default=max_cycles)

    trace_name = f"evaluator/{brief.brief_id}"
    trace_metadata = {
        "brief_id": brief.brief_id,
        "max_cycles": max_cycles,
        "content_format": getattr(brief, "content_format", ""),
        "brief_title": brief.title,
    }
    trace_input = {
        "brief_id": brief.brief_id,
        "title": brief.title,
        "initial_word_count": content.word_count,
        "max_cycles": max_cycles,
    }
    if parent_span is not None:
        trace = create_span(
            parent_span, trace_name,
            metadata=trace_metadata,
            input=trace_input,
        )
    else:
        trace = create_trace(
            session_id,
            trace_name,
            metadata=trace_metadata,
            input=trace_input,
            tags=["evaluator", f"brief:{brief.brief_id}"],
            user_id=input_data.domain,
        )

    history = RevisionHistory(brief_id=brief.brief_id)
    current_content = content
    prev_score: Optional[float] = None  # Track for early-stop

    for cycle in range(max_cycles + 1):  # +1 because first is initial eval
        cycle_span = create_span(
            trace, f"eval_cycle_{cycle}",
            metadata={"cycle": cycle},
            input={
                "word_count": current_content.word_count,
                "cycle_number": cycle,
            },
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

        # Log per-dimension scores
        for dim in dimensions:
            log_score(
                cycle_span, f"{dim.dimension}_score", dim.score,
                comment=f"cycle_{cycle}",
                metadata={"passed": dim.passed},
            )
        log_score(cycle_span, "overall_score", round(overall_score, 4), comment=f"cycle_{cycle}")
        end_span(cycle_span, output={
            "overall_score": round(overall_score, 4),
            "overall_passed": overall_passed,
            "dimension_scores": {d.dimension: d.score for d in dimensions},
            "dimension_passed": {d.dimension: d.passed for d in dimensions},
        })

        if overall_passed:
            _cli_worker_progress(f"{brief.brief_id}: ALL PASSED (overall: {overall_score:.2f})")
            history.final_passed = True
            break

        # Early-stop: if score improvement < 0.02 between revision cycles, stop
        if prev_score is not None and cycle > 0:
            improvement = overall_score - prev_score
            if improvement < 0.02:
                _cli_worker_progress(
                    f"{brief.brief_id}: Early-stop — score plateau "
                    f"({prev_score:.4f} → {overall_score:.4f}, Δ={improvement:.4f})"
                )
                history.final_passed = False
                break
        prev_score = overall_score

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

        failed_dims = [d.dimension for d in dimensions if not d.passed]
        revision_span = create_span(
            trace, f"revision_cycle_{cycle + 1}",
            metadata={"cycle": cycle + 1},
            input={
                "failed_dimensions": failed_dims,
                "feedback_length": len(feedback),
                "current_word_count": current_content.word_count,
            },
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

        # Re-format (pass brief for structural targets)
        current_content = await format_content(
            enriched=enriched,
            style_guide_md=style_guide_md,
            brief=brief,
            trace=trace,
        )

        end_span(revision_span, output={
            "revised_word_count": current_content.word_count,
            "revised": True,
        })

    log_score(
        trace,
        "revision_count",
        len(history.cycles) - 1,
        comment=f"final_passed={history.final_passed}",
    )

    # Trace-level output summary
    final_cycle = history.cycles[-1] if history.cycles else None
    trace_output = {
        "final_passed": history.final_passed,
        "total_cycles": len(history.cycles),
        "final_score": final_cycle.overall_score if final_cycle else 0.0,
        "final_dimensions": {
            d.dimension: {"score": d.score, "passed": d.passed}
            for d in (final_cycle.dimensions if final_cycle else [])
        },
    }
    if parent_span is not None:
        end_span(trace, output=trace_output)
    else:
        update_trace_output(trace, output=trace_output)
        end_span(trace)

    return current_content, history
