"""Background task wrappers for pipeline execution."""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore
from core.gap_analysis.pipeline import run_gap_analysis
from core.models.artifacts import CompanyResearchInput
from core.models.gap_analysis import GapAnalysisInput
from core.models.personas import PersonaResearchInput
from core.models.style_guide import StyleGuideResearchInput

logger = logging.getLogger(__name__)


def _derive_slug(company_name: str, company_slug: Optional[str] = None) -> str:
    if company_slug:
        return company_slug
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-") or company_name.lower()


def resolve_artifacts(slug: str, artifacts_root: Path) -> Dict[str, Any]:
    """Auto-discover approved research artifacts for a company slug.

    Only resolves final (approved) artifacts — ignores .draft.md files.
    Returns a dict with resolved paths and a summary for the API response.
    """
    resolved: Dict[str, Any] = {
        "company_context_path": None,
        "persona_paths": [],
        "style_guide_path": None,
    }

    # Company context: artifacts/company_context/{slug}.md
    company_ctx = artifacts_root / "company_context" / f"{slug}.md"
    if company_ctx.exists():
        resolved["company_context_path"] = str(company_ctx)

    # Personas: artifacts/personas/{slug}__persona-*.md (exclude .draft.md)
    personas_dir = artifacts_root / "personas"
    if personas_dir.exists():
        persona_files = sorted(
            p for p in personas_dir.glob(f"{slug}__persona-*.md")
            if not p.name.endswith(".draft.md")
        )
        resolved["persona_paths"] = [str(p) for p in persona_files]

    # Style guide: artifacts/style_guides/{slug}.md
    style_guide = artifacts_root / "style_guides" / f"{slug}.md"
    if style_guide.exists():
        resolved["style_guide_path"] = str(style_guide)

    return resolved


async def run_gap_pipeline_task(
    task_id: str,
    request: Any,
    artifacts_root: Path,
    task_store: TaskStore,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for gap analysis pipeline.

    Accepts the simplified GapAnalysisStartRequest, auto-resolves research
    artifact paths from disk, and constructs GapAnalysisInput internally.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", request.company_name.lower()).strip("-")

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "gap_analysis"})

            # Auto-resolve research artifacts from filesystem
            resolved = resolve_artifacts(slug, artifacts_root)

            input_data = GapAnalysisInput(
                company_name=request.company_name,
                domain=request.domain,
                company_slug=slug,
                seed_urls=request.seed_urls or [f"https://{request.domain}/"],
                company_context_path=resolved["company_context_path"],
                persona_paths=resolved["persona_paths"],
                style_guide_path=resolved["style_guide_path"],
                max_queries=request.max_queries,
                platforms=request.platforms,
                language=request.language,
                region=request.region,
                additional_constraints=request.additional_constraints,
                max_crawl_pages=request.max_crawl_pages,
                max_crawl_depth=request.max_crawl_depth,
            )

            report = await run_gap_analysis(
                input_data=input_data, skip_steps=request.skip_steps
            )
            result = {
                "report_md": report.report_md[:500] if report.report_md else None,
                "report_json": report.report_json,
                "visualization_paths": report.visualization_paths,
                "resolved_artifacts": resolved,
                "produced_artifacts": [
                    {"type": "gap_analysis", "slug": slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result
            )
            event_bus.publish(task_id, "completed", {"pipeline": "gap_analysis"})
    except Exception as exc:
        logger.exception("Gap analysis pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc)
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(slug)


# ── Research pipeline runner ─────────────────────────────────────────


async def _run_research_stage(
    stage_name: str,
    build_graph_fn: Callable[..., Any],
    initial_state: Dict[str, Any],
    task_id: str,
    task_store: TaskStore,
    event_bus: EventBus,
) -> Dict[str, Any]:
    """Run a single research stage with HITL interrupt/resume support.

    Uses MemorySaver for checkpointing so interrupt() + Command(resume=...) works.
    Research graphs are synchronous, so we wrap in asyncio.to_thread().
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Command

    checkpointer = MemorySaver()
    graph = build_graph_fn(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": f"{task_id}-{stage_name}"}}

    event_bus.publish(task_id, "stage_start", {"stage": stage_name})
    task_store.update_task(task_id, current_step=stage_name)

    # First invocation
    try:
        result = await asyncio.to_thread(graph.invoke, initial_state, config)
    except GraphInterrupt:
        # Graph paused at approval gate — get the interrupt payload
        snapshot = graph.get_state(config)
        interrupt_values = snapshot.tasks[0].interrupts[0].value if snapshot.tasks else {}

        task_store.update_task(
            task_id,
            status=TaskStatus.PENDING_APPROVAL,
            approval_payload={"stage": stage_name, **interrupt_values},
        )
        event_bus.publish(task_id, "pending_approval", {"stage": stage_name, **interrupt_values})

        # Wait for human decision
        while True:
            approval = await task_store.wait_for_approval(task_id)
            decision = approval["decision"]
            revision_note = approval.get("revision_note")

            task_store.update_task(task_id, status=TaskStatus.RUNNING, current_step=stage_name)
            event_bus.publish(task_id, "approval_received", {"stage": stage_name, "decision": decision})

            # Resume the graph with the approval decision
            resume_value = {"approval_decision": decision}
            if revision_note:
                resume_value["revision_note"] = revision_note

            try:
                result = await asyncio.to_thread(
                    graph.invoke, Command(resume=resume_value), config
                )
                break  # Completed without another interrupt
            except GraphInterrupt:
                # Another interrupt (e.g., revise → agent → approval_gate again)
                snapshot = graph.get_state(config)
                interrupt_values = snapshot.tasks[0].interrupts[0].value if snapshot.tasks else {}
                task_store.update_task(
                    task_id,
                    status=TaskStatus.PENDING_APPROVAL,
                    approval_payload={"stage": stage_name, **interrupt_values},
                )
                event_bus.publish(task_id, "pending_approval", {"stage": stage_name, **interrupt_values})
                continue

    event_bus.publish(task_id, "stage_complete", {"stage": stage_name})
    return result


async def run_research_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStore,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for research pipeline (company → persona → style).

    Accepts the simplified ResearchStartRequest and constructs per-stage
    core model inputs internally. The frontend never needs to know about
    artifact paths — the runner chains them automatically.
    """
    from core.research.graphs.company_research import build_graph as build_company_graph
    from core.research.graphs.persona_research import build_graph as build_persona_graph
    from core.research.graphs.style_guide import build_graph as build_style_graph

    slug = re.sub(r"[^a-z0-9]+", "-", request.company_name.lower()).strip("-")
    stages = request.stages
    auto_approve = request.auto_approve

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "research"})

            company_output_path: Optional[str] = None
            persona_paths: List[str] = []

            # Stage 1: Company research (always runs)
            if "company" in stages:
                company_input = CompanyResearchInput(
                    company_name=request.company_name,
                    domain=request.domain,
                    seed_urls=request.seed_urls or [f"https://{request.domain}/"],
                    internal_sources=request.internal_sources,
                    language=request.language,
                    region=request.region,
                    additional_constraints=request.additional_constraints,
                )
                company_state = {"input": company_input, "auto_approve": auto_approve}
                company_result = await _run_research_stage(
                    "company", build_company_graph, company_state,
                    task_id, task_store, event_bus,
                )
                company_output_path = company_result.get("output_path")

            # Stage 2: Persona research
            if "persona" in stages:
                persona_input = PersonaResearchInput(
                    company_name=request.company_name,
                    domain=request.domain,
                    company_slug=slug,
                    company_context_path=company_output_path,
                    internal_sources=request.internal_sources,
                    max_personas=request.max_personas,
                    language=request.language,
                    region=request.region,
                    additional_constraints=request.additional_constraints,
                )
                persona_state = {"input": persona_input, "auto_approve": auto_approve}
                persona_result = await _run_research_stage(
                    "persona", build_persona_graph, persona_state,
                    task_id, task_store, event_bus,
                )
                persona_paths = persona_result.get("written_paths") or []

            # Stage 3: Style guide research
            if "style_guide" in stages:
                style_input = StyleGuideResearchInput(
                    company_name=request.company_name,
                    domain=request.domain,
                    company_slug=slug,
                    company_context_path=company_output_path,
                    persona_paths=persona_paths,
                    internal_sources=request.internal_sources,
                    language=request.language,
                    region=request.region,
                    additional_constraints=request.additional_constraints,
                )
                style_state = {"input": style_input, "auto_approve": auto_approve}
                await _run_research_stage(
                    "style", build_style_graph, style_state,
                    task_id, task_store, event_bus,
                )

            # Map stages to artifact types
            _stage_to_artifact_type = {
                "company": "company_context",
                "persona": "personas",
                "style_guide": "style_guides",
            }
            produced = [
                {"type": _stage_to_artifact_type[s], "slug": slug}
                for s in stages
                if s in _stage_to_artifact_type
            ]

            task_store.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result={
                    "stage": "complete",
                    "company_output_path": company_output_path,
                    "produced_artifacts": produced,
                },
            )
            event_bus.publish(task_id, "completed", {"pipeline": "research"})

    except Exception as exc:
        logger.exception("Research pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(slug)


# ── Content generation pipeline runner ───────────────────────────────


async def run_content_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStore,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for content generation pipeline."""
    from core.content_engine.pipeline import run_content_generation
    from core.models.content_generation import ContentGenerationInput

    slug = re.sub(r"[^a-z0-9]+", "-", input_data.company_name.lower()).strip("-")

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content"})

            output = await run_content_generation(input_data=input_data)

            result = {
                "company_slug": output.company_slug,
                "total_briefs": output.total_briefs,
                "total_approved": output.total_approved,
                "total_rejected": output.total_rejected,
                "pieces": [
                    {
                        "brief_id": p.brief_id,
                        "title": p.title,
                        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                    }
                    for p in output.pieces
                ],
                "produced_artifacts": [
                    {"type": "content", "slug": slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result
            )
            event_bus.publish(task_id, "completed", {"pipeline": "content"})

    except Exception as exc:
        logger.exception("Content generation pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(slug)
