"""Evaluator-Optimizer loop — orchestrates evaluation dimensions.

Runs structural, semantic, style, and factual checks in parallel.
If any dimension fails, compiles feedback and triggers a revision cycle
(re-draft → re-enrich → re-format → re-evaluate).

v2.0: Format-aware revision cycles, early-stop on score plateau.
v2.1: E-E-A-T dimension (5th evaluator) + dual feedback routing for v1.3.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, List, Literal, Optional, Tuple

from core.config.settings import settings
from core.content_engine.evaluator.factual_judge import evaluate_factual
from core.content_engine.evaluator.semantic import evaluate_semantic
from core.content_engine.evaluator.structural import evaluate_structural
from core.content_engine.evaluator.style_judge import evaluate_style
from core.content_engine.pipeline import _cli_worker_progress
from core.content_engine.state_helpers import _emit, _write_pipeline_state, _write_pipeline_state_async
from core.content_engine.tracing_v13 import (
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
    EvalResult,
    FormattedContent,
    RevisionHistory,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feedback Classification (v1.3 dual feedback routing)
# ---------------------------------------------------------------------------

FeedbackRoute = Literal["pass", "section_level", "major_change"]


def classify_feedback(dimensions: List[DimensionResult]) -> FeedbackRoute:
    """Classify evaluator feedback for dual feedback routing (v1.3).

    Three possible routes:
      - "pass": All dimensions passed — no revision needed.
      - "section_level": Targeted fixes — run only the workers needed.
      - "major_change": Fundamental content direction issue — re-brief needed.
        Only triggered by semantic score < 0.5 (automated) or HITL-3 human
        rejection. Never from a single-dimension fail.

    Args:
        dimensions: List of evaluation dimension results.

    Returns:
        One of "pass", "section_level", or "major_change".
    """
    if all(d.passed for d in dimensions):
        return "pass"

    # Major direction change: only when semantic alignment is critically low
    semantic_result = next((d for d in dimensions if d.dimension == "semantic"), None)
    if semantic_result and semantic_result.score < 0.5:
        return "major_change"

    return "section_level"


def _get_targeted_revision_plan(dimensions: List[DimensionResult]) -> List[str]:
    """Determine which workers to run based on failed dimensions (v1.3).

    v1.3 routing (no formatter, no enricher cascade):
      - structural fail → drafter + fact_checker
      - style fail → drafter + fact_checker
      - semantic fail → drafter + fact_checker
      - eeat fail → drafter + fact_checker
      - factual fail → fact_checker only

    If drafter revises, always re-verify facts on the new content.

    Args:
        dimensions: List of evaluation dimension results.

    Returns:
        Ordered list of worker names to run: ["drafter", "fact_checker"].
    """
    failed = {d.dimension for d in dimensions if not d.passed}

    if not failed:
        return []

    needs_drafter = bool(failed & {"semantic", "style", "eeat", "structural"})
    needs_fact_checker = "factual" in failed

    # If drafter revises, re-verify facts on new content
    if needs_drafter:
        needs_fact_checker = True

    plan = []
    if needs_drafter:
        plan.append("drafter")
    if needs_fact_checker:
        plan.append("fact_checker")

    return plan


async def _run_all_evaluations(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str,
    style_guide_md: str,
    company_name: str,
    domain: str,
    *,
    trace: Optional[object] = None,
    use_eeat: bool = False,
    company_slug: str = "",
) -> list[DimensionResult]:
    """Run evaluation dimensions in parallel.

    Args:
        use_eeat: If True, includes E-E-A-T as 5th dimension (v1.3).
    """

    # Structural is sync (no LLM calls)
    structural_result = evaluate_structural(content, brief, trace=trace)

    # Run async evaluations in parallel
    tasks = [
        ("semantic", evaluate_semantic(content, brief, trace=trace)),
        ("style", evaluate_style(content, style_guide_md, trace=trace, company_slug=company_slug)),
        ("factual", evaluate_factual(content, brief, company_name, domain, trace=trace, company_slug=company_slug)),
    ]

    if use_eeat:
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        tasks.append(
            ("eeat", evaluate_eeat(content, brief, company_context_md, trace=trace, company_slug=company_slug))
        )

    task_results = await asyncio.gather(
        *(t[1] for t in tasks),
        return_exceptions=True,
    )

    results = [structural_result]

    for (dim_name, _), result in zip(tasks, task_results):
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


async def _run_targeted_revision(
    current_content: FormattedContent,
    brief: ContentBrief,
    dimensions: List[DimensionResult],
    style_guide_md: str,
    company_context_md: str,
    company_name: str,
    domain: str,
    *,
    trace: Optional[object] = None,
    company_slug: str = "",
) -> FormattedContent:
    """Run a targeted revision based on which dimensions failed (v1.3).

    v1.3 chain: drafter (if needed) → fact_checker (if needed)
    No formatter step — structural counts computed inline.

    Args:
        current_content: Current formatted content.
        brief: Content brief.
        dimensions: Evaluation results for feedback extraction.
        style_guide_md: Style guide markdown.
        company_context_md: Company context markdown.
        company_name: Company name.
        domain: Company domain.
        trace: Trace for instrumentation.

    Returns:
        Revised FormattedContent.
    """
    from core.content_engine.workers.formatter import _count_structural_elements

    plan = _get_targeted_revision_plan(dimensions)
    feedback = _compile_feedback(dimensions)

    if "drafter" in plan:
        from core.content_engine.workers.drafter import revise_draft

        revised_draft = await revise_draft(
            current_markdown=current_content.markdown,
            brief=brief,
            feedback=feedback,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            trace=trace,
            company_slug=company_slug,
        )
    else:
        from core.models.content_generation import ContentDraft

        revised_draft = ContentDraft(
            brief_id=current_content.brief_id,
            title=current_content.title,
            markdown=current_content.markdown,
            word_count=current_content.word_count,
        )

    if "fact_checker" in plan:
        checked = await enrich_with_facts(
            draft=revised_draft,
            brief=brief,
            company_name=company_name,
            domain=domain,
            trace=trace,
            company_slug=company_slug,
        )
        final_md = checked.markdown
    else:
        final_md = revised_draft.markdown

    # Compute structural counts inline (no formatter step)
    counts = _count_structural_elements(final_md)
    return FormattedContent(
        brief_id=revised_draft.brief_id,
        title=revised_draft.title,
        markdown=final_md,
        word_count=len(final_md.split()),
        **counts,
    )


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
    use_eeat: bool = False,
    use_targeted_revision: bool = False,
    event_bus: Any = None,
    task_id: Optional[str] = None,
    redis_client: Any = None,
    effective_slug: Optional[str] = None,
    session_factory: Any = None,
) -> Tuple[FormattedContent, RevisionHistory, FeedbackRoute]:
    """Run the evaluation-optimization loop for a single content piece.

    Evaluates across 4 (or 5 with E-E-A-T) dimensions. If any fails, revises
    and re-evaluates up to max_cycles times. Uses format-aware cycle limits and
    early-stops when score improvement plateaus (<0.02 between cycles).

    Args:
        content: Formatted content to evaluate.
        brief: Content brief with targets.
        company_context_md: Company context markdown.
        style_guide_md: Style guide markdown.
        input_data: Pipeline input for company details.
        max_cycles: Maximum revision cycles (overridden by format-aware config).
        session_id: Tracing session ID.
        artifact_dir: Root artifact directory.
        parent_span: Optional parent span for tracing.
        use_eeat: If True, includes E-E-A-T as 5th dimension (v1.3).
        use_targeted_revision: If True, uses section-level feedback routing (v1.3).

    Returns:
        Tuple of (final FormattedContent, RevisionHistory, FeedbackRoute).
        FeedbackRoute indicates if all passed, section-level fix needed, or
        major direction change required.
    """
    # Format-aware revision cycles override the default max_cycles
    max_cycles = _get_max_cycles(brief, default=max_cycles)

    trace_name = f"evaluator/{brief.brief_id}"
    trace_metadata = {
        "brief_id": brief.brief_id,
        "max_cycles": max_cycles,
        "content_format": getattr(brief, "content_format", ""),
        "brief_title": brief.title,
        "use_eeat": use_eeat,
        "use_targeted_revision": use_targeted_revision,
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

    _slug = getattr(input_data, "company_slug", "") or ""
    history = RevisionHistory(brief_id=brief.brief_id)
    current_content = content
    prev_score: Optional[float] = None  # Track for early-stop
    final_route: FeedbackRoute = "pass"  # Track feedback route for return

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
            use_eeat=use_eeat,
            company_slug=_slug,
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
                final_route = "section_level"
                break
        prev_score = overall_score

        # If this was the last allowed cycle, don't revise
        if cycle >= max_cycles:
            _cli_worker_progress(
                f"{brief.brief_id}: FAILED after {max_cycles} revision cycles — flagging for HITL"
            )
            history.final_passed = False
            final_route = "section_level"
            break

        # Classify feedback route (v1.3 dual feedback)
        feedback_route = classify_feedback(dimensions) if use_targeted_revision else "section_level"

        if feedback_route == "major_change":
            _cli_worker_progress(
                f"{brief.brief_id}: Major direction change detected (semantic < 0.5) — "
                "flagging for HITL re-brief"
            )
            history.final_passed = False
            final_route = "major_change"
            break

        # Compile feedback and trigger revision
        feedback = _compile_feedback(dimensions)
        failed_dims = [d.dimension for d in dimensions if not d.passed]

        # Mark brief as "revising" for Kanban sync
        await _write_pipeline_state_async(
            artifact_dir,
            [brief.brief_id],
            "revising",
            task_id=task_id,
            redis_client=redis_client,
            effective_slug=effective_slug,
            session_factory=session_factory,
        )
        _emit(event_bus, task_id, "worker_progress", {
            "brief_id": brief.brief_id, "step": "revising", "cycle": cycle + 1,
        })

        _cli_worker_progress(
            f"{brief.brief_id}: Revision cycle {cycle + 1} — "
            f"fixing {len(failed_dims)} dimensions"
        )

        revision_span = create_span(
            trace, f"revision_cycle_{cycle + 1}",
            metadata={"cycle": cycle + 1, "feedback_route": feedback_route},
            input={
                "failed_dimensions": failed_dims,
                "feedback_length": len(feedback),
                "current_word_count": current_content.word_count,
            },
        )

        try:
            if use_targeted_revision:
                # v1.3: Section-level targeted revision
                current_content = await _run_targeted_revision(
                    current_content=current_content,
                    brief=brief,
                    dimensions=dimensions,
                    style_guide_md=style_guide_md,
                    company_context_md=company_context_md,
                    company_name=input_data.company_name,
                    domain=input_data.domain,
                    trace=trace,
                    company_slug=_slug,
                )
            else:
                # v1.0: Full revision chain (drafter → enricher → formatter)
                revised_draft = await revise_draft(
                    current_markdown=current_content.markdown,
                    brief=brief,
                    feedback=feedback,
                    style_guide_md=style_guide_md,
                    company_context_md=company_context_md,
                    trace=trace,
                    company_slug=_slug,
                )

                enriched = await enrich_with_facts(
                    draft=revised_draft,
                    brief=brief,
                    company_name=input_data.company_name,
                    domain=input_data.domain,
                    trace=trace,
                    company_slug=_slug,
                )

                current_content = await format_content(
                    enriched=enriched,
                    style_guide_md=style_guide_md,
                    brief=brief,
                    trace=trace,
                    company_slug=_slug,
                )

            end_span(revision_span, output={
                "revised_word_count": current_content.word_count,
                "revised": True,
            })
        except Exception as exc:
            end_span(revision_span, error=str(exc)[:500])
            raise

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
        # update_trace_output ends the trace internally — no end_span needed
        update_trace_output(trace, output=trace_output)

    return current_content, history, final_route
