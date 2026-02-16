"""Content Generation Pipeline — top-level async orchestrator.

4-stage pipeline:
  [1/4] Strategic Planner  — produces content briefs from gap analysis
  [2/4] Content Workers    — parallel outline → draft → enrich → format
  [3/4] Evaluator Loop     — 4-dimension quality gate with revision cycles
  [4/4] Human Review       — LangGraph HITL (approve / edit / reject)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from core.config.settings import settings
from core.content_engine.tracing import (
    create_pipeline_trace,
    create_session,
    create_span,
    end_span,
    flush,
    update_trace_output,
)
from core.models.content_generation import (
    ContentGenerationInput,
    ContentGenerationOutput,
    ContentPiece,
    ContentStatus,
    FormattedContent,
    PlannerOutput,
    RevisionHistory,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/

_STAGE_NAMES: Dict[int, str] = {
    1: "Strategic Planner",
    2: "Content Workers",
    3: "Evaluator Loop",
    4: "Human Review",
}


# ── CLI progress helpers ────────────────────────────────────────────


def _fmt_duration(seconds: float) -> str:
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {s:.1f}s"
    return f"{seconds:.1f}s"


def _cli_header(slug: str, skip_stages: List[int]) -> None:
    w = sys.stdout.write
    w("\n")
    w("─" * 52 + "\n")
    w(f"  Content Generation Pipeline — {slug}\n")
    if skip_stages:
        w(f"  Skipping stages: {', '.join(str(s) for s in sorted(skip_stages))}\n")
    w("─" * 52 + "\n\n")
    sys.stdout.flush()


def _cli_stage(stage: int, elapsed: float, *, skipped: bool = False, detail: str = "") -> None:
    name = _STAGE_NAMES.get(stage, f"Stage {stage}")
    tag = " (skipped)" if skipped else ""
    if detail:
        tag += f" ({detail})"
    dots = "." * (36 - len(name))
    sys.stdout.write(f"  [{stage}/4] {name} {dots} {_fmt_duration(elapsed):>8s}{tag}\n")
    sys.stdout.flush()


def _cli_worker_progress(message: str) -> None:
    """Print a worker-level progress update."""
    sys.stdout.write(f"         {message}\n")
    sys.stdout.flush()


def _cli_footer(total: float, approved: int, rejected: int) -> None:
    w = sys.stdout.write
    w("\n" + "─" * 52 + "\n")
    w(f"  Done — {_fmt_duration(total)} total | {approved} approved, {rejected} rejected\n")
    w("─" * 52 + "\n\n")
    sys.stdout.flush()


# ── Slug + artifact helpers ─────────────────────────────────────────


def _company_slug(input_data: ContentGenerationInput) -> str:
    return re.sub(r"[^a-z0-9]+", "-", input_data.company_name.lower()).strip("-")


def _artifact_dir(company_slug: str) -> Path:
    path = _PROJECT_ROOT / "artifacts" / "content" / company_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _brief_dir(artifact_dir: Path, brief_id: str) -> Path:
    path = artifact_dir / "content" / brief_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_artifact_md(path: Optional[str]) -> str:
    """Load a markdown artifact file, returning empty string if not found."""
    if not path:
        return ""
    p = Path(path) if Path(path).is_absolute() else _PROJECT_ROOT / path.lstrip("/")
    if p.exists():
        return p.read_text(encoding="utf-8")
    logger.warning("Artifact not found: %s", p)
    return ""


def _load_artifact_json(path: Optional[str]) -> dict:
    """Load a JSON artifact file, returning empty dict if not found."""
    if not path:
        return {}
    p = Path(path) if Path(path).is_absolute() else _PROJECT_ROOT / path.lstrip("/")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    logger.warning("Artifact not found: %s", p)
    return {}


# ── Main pipeline orchestrator ──────────────────────────────────────


async def run_content_generation(
    input_data: ContentGenerationInput,
) -> ContentGenerationOutput:
    """Run the full 4-stage content generation pipeline.

    Args:
        input_data: Pipeline configuration and artifact paths.

    Returns:
        ContentGenerationOutput with all content pieces and metadata.
    """
    slug = _company_slug(input_data)
    artifact_dir = _artifact_dir(slug)
    skip_stages = input_data.skip_stages
    pipeline_start = time.monotonic()

    # Langfuse session + pipeline trace
    session_id = create_session(slug)
    pipeline_trace = create_pipeline_trace(
        session_id,
        slug,
        input_data.company_name,
        metadata={
            "max_briefs": input_data.max_briefs,
            "max_revision_cycles": input_data.max_revision_cycles,
            "skip_stages": skip_stages,
            "auto_approve": input_data.auto_approve,
        },
    )

    _cli_header(slug, skip_stages)

    # Load shared input artifacts
    company_context_md = _load_artifact_md(input_data.company_context_path)
    style_guide_md = _load_artifact_md(input_data.style_guide_path)
    persona_mds = [_load_artifact_md(p) for p in input_data.persona_paths]
    gap_report_json = _load_artifact_json(input_data.gap_report_json_path)
    generation_spec_json = _load_artifact_json(input_data.generation_spec_json_path)
    analysis_json = _load_artifact_json(input_data.analysis_json_path)

    # ── Stage 1: Strategic Planner ──────────────────────────────
    stage_start = time.monotonic()
    stage1_span = create_span(
        pipeline_trace, "stage/1-planner",
        input={"max_briefs": input_data.max_briefs},
        metadata={"stage": 1, "stage_name": "Strategic Planner"},
    )
    if 1 in skip_stages:
        briefs_path = artifact_dir / "briefs.json"
        if briefs_path.exists():
            planner_output = PlannerOutput(**json.loads(briefs_path.read_text(encoding="utf-8")))
        else:
            raise RuntimeError("Stage 1 skipped but briefs.json not found.")
        end_span(stage1_span, output={"skipped": True, "briefs_loaded": len(planner_output.briefs)})
        _cli_stage(1, time.monotonic() - stage_start, skipped=True)
    else:
        from core.content_engine.planner import plan_content

        planner_output = await plan_content(
            input_data=input_data,
            company_context_md=company_context_md,
            style_guide_md=style_guide_md,
            persona_mds=persona_mds,
            gap_report_json=gap_report_json,
            generation_spec_json=generation_spec_json,
            analysis_json=analysis_json,
            session_id=session_id,
        )
        # Persist briefs
        (artifact_dir / "briefs.json").write_text(
            json.dumps(planner_output.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        end_span(stage1_span, output={
            "briefs_count": len(planner_output.briefs),
            "brief_titles": [b.title for b in planner_output.briefs],
        })
        _cli_stage(1, time.monotonic() - stage_start, detail=f"{len(planner_output.briefs)} briefs")

    briefs = planner_output.briefs[: input_data.max_briefs]

    # ── Stage 2: Content Workers ────────────────────────────────
    stage_start = time.monotonic()
    stage2_span = create_span(
        pipeline_trace, "stage/2-workers",
        input={"brief_count": len(briefs)},
        metadata={"stage": 2, "stage_name": "Content Workers"},
    )
    if 2 in skip_stages:
        # Load pre-existing formatted content
        formatted_contents: List[FormattedContent] = []
        for brief in briefs:
            bdir = artifact_dir / "content" / brief.brief_id
            fmt_path = bdir / "formatted.md"
            if fmt_path.exists():
                formatted_contents.append(
                    FormattedContent(
                        brief_id=brief.brief_id,
                        title=brief.title,
                        markdown=fmt_path.read_text(encoding="utf-8"),
                    )
                )
        end_span(stage2_span, output={"skipped": True, "loaded": len(formatted_contents)})
        _cli_stage(2, time.monotonic() - stage_start, skipped=True)
    else:
        from core.content_engine.workers.dispatcher import dispatch_workers

        formatted_contents = await dispatch_workers(
            briefs=briefs,
            input_data=input_data,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            max_concurrent=input_data.max_concurrent_workers,
            session_id=session_id,
            artifact_dir=artifact_dir,
        )
        end_span(stage2_span, output={
            "completed": len(formatted_contents),
            "total": len(briefs),
        })
        _cli_stage(
            2,
            time.monotonic() - stage_start,
            detail=f"{len(formatted_contents)}/{len(briefs)} briefs",
        )

    # ── Stage 3: Evaluator Loop ─────────────────────────────────
    stage_start = time.monotonic()
    stage3_span = create_span(
        pipeline_trace, "stage/3-evaluator",
        input={
            "briefs_to_evaluate": len(formatted_contents),
            "max_cycles": input_data.max_revision_cycles,
        },
        metadata={"stage": 3, "stage_name": "Evaluator Loop"},
    )
    revision_histories: List[RevisionHistory] = []
    if 3 in skip_stages or input_data.max_revision_cycles == 0:
        # Pass through without evaluation
        for fc in formatted_contents:
            revision_histories.append(
                RevisionHistory(brief_id=fc.brief_id, final_passed=True)
            )
        end_span(stage3_span, output={"skipped": True})
        _cli_stage(3, time.monotonic() - stage_start, skipped=True)
    else:
        from core.content_engine.evaluator.loop import evaluate_and_optimize

        eval_results = []
        passed_count = 0
        for i, fc in enumerate(formatted_contents):
            brief = next((b for b in briefs if b.brief_id == fc.brief_id), None)
            if not brief:
                continue
            _cli_worker_progress(
                f"Evaluating brief-{i + 1}/{len(formatted_contents)}: \"{fc.title[:50]}...\""
            )
            optimized, history = await evaluate_and_optimize(
                content=fc,
                brief=brief,
                company_context_md=company_context_md,
                style_guide_md=style_guide_md,
                input_data=input_data,
                max_cycles=input_data.max_revision_cycles,
                session_id=session_id,
                artifact_dir=artifact_dir,
            )
            formatted_contents[i] = optimized
            revision_histories.append(history)
            if history.final_passed:
                passed_count += 1
            # Save eval history
            bdir = _brief_dir(artifact_dir, fc.brief_id)
            (bdir / "eval_history.json").write_text(
                json.dumps(history.model_dump(mode="json"), indent=2, default=str),
                encoding="utf-8",
            )
        end_span(stage3_span, output={
            "passed": passed_count,
            "total": len(formatted_contents),
        })
        _cli_stage(
            3,
            time.monotonic() - stage_start,
            detail=f"{passed_count}/{len(formatted_contents)} passed",
        )

    # ── Stage 4: Human Review ───────────────────────────────────
    stage_start = time.monotonic()
    stage4_span = create_span(
        pipeline_trace, "stage/4-review",
        input={"pieces_to_review": len(formatted_contents)},
        metadata={"stage": 4, "stage_name": "Human Review"},
    )
    pieces: List[ContentPiece] = []
    if 4 in skip_stages:
        # Auto-approve all
        for fc in formatted_contents:
            bdir = _brief_dir(artifact_dir, fc.brief_id)
            final_path = bdir / "final.md"
            final_path.write_text(fc.markdown, encoding="utf-8")
            pieces.append(
                ContentPiece(
                    brief_id=fc.brief_id,
                    title=fc.title,
                    status=ContentStatus.APPROVED,
                    final_markdown=fc.markdown,
                    artifact_path=str(final_path),
                )
            )
        end_span(stage4_span, output={"skipped": True, "auto_approved": len(pieces)})
        _cli_stage(4, time.monotonic() - stage_start, skipped=True)
    elif input_data.auto_approve:
        for fc in formatted_contents:
            bdir = _brief_dir(artifact_dir, fc.brief_id)
            final_path = bdir / "final.md"
            final_path.write_text(fc.markdown, encoding="utf-8")
            pieces.append(
                ContentPiece(
                    brief_id=fc.brief_id,
                    title=fc.title,
                    status=ContentStatus.APPROVED,
                    final_markdown=fc.markdown,
                    artifact_path=str(final_path),
                )
            )
        end_span(stage4_span, output={"auto_approved": len(pieces)})
        _cli_stage(4, time.monotonic() - stage_start, detail="auto-approved")
    else:
        from core.content_engine.graph import run_content_review

        pieces = await run_content_review(
            formatted_contents=formatted_contents,
            briefs=briefs,
            revision_histories=revision_histories,
            session_id=session_id,
            artifact_dir=artifact_dir,
        )
        end_span(stage4_span, output={
            "approved": sum(1 for p in pieces if p.status == ContentStatus.APPROVED),
            "rejected": sum(1 for p in pieces if p.status == ContentStatus.REJECTED),
        })
        _cli_stage(4, time.monotonic() - stage_start)

    # ── Finalize ────────────────────────────────────────────────
    total_approved = sum(1 for p in pieces if p.status == ContentStatus.APPROVED)
    total_rejected = sum(1 for p in pieces if p.status == ContentStatus.REJECTED)

    output = ContentGenerationOutput(
        company_slug=slug,
        total_briefs=len(briefs),
        total_approved=total_approved,
        total_rejected=total_rejected,
        pieces=pieces,
        run_metadata={
            "session_id": session_id,
            "total_time_s": round(time.monotonic() - pipeline_start, 1),
            "skip_stages": skip_stages,
            "auto_approve": input_data.auto_approve,
        },
    )

    # Save run metadata
    (artifact_dir / "run_metadata.json").write_text(
        json.dumps(output.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    _cli_footer(
        time.monotonic() - pipeline_start,
        total_approved,
        total_rejected,
    )

    # Finalize pipeline trace
    update_trace_output(pipeline_trace, output={
        "total_briefs": len(briefs),
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "total_time_s": round(time.monotonic() - pipeline_start, 1),
    })
    end_span(pipeline_trace)

    flush()  # Flush Langfuse events
    return output
