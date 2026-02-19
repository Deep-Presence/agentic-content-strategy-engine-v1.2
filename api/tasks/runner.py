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

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


def _enrich_interrupt_with_draft_content(
    interrupt_values: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize interrupt payload — read draft files and inject artifact_md if missing.

    Company graph sends artifact_md directly; persona/style_guide graphs only send
    draft_paths. This ensures the frontend always receives artifact_md in the SSE event.
    """
    if interrupt_values.get("artifact_md"):
        return interrupt_values  # Already present (company graph)

    draft_paths: List[str] = interrupt_values.get("draft_paths", [])
    draft_path: Optional[str] = interrupt_values.get("draft_path")
    if draft_path and not draft_paths:
        draft_paths = [draft_path]

    if not draft_paths:
        return interrupt_values

    combined: List[str] = []
    for p in draft_paths:
        full = _PROJECT_ROOT / p.lstrip("/")
        if full.exists():
            try:
                content = full.read_text(encoding="utf-8")
                if content.strip():
                    combined.append(content)
            except Exception as exc:
                logger.warning("Failed to read draft %s: %s", p, exc)

    interrupt_values["artifact_md"] = "\n\n---\n\n".join(combined) if combined else ""
    if not combined:
        logger.warning("No draft content found for paths: %s", draft_paths)

    return interrupt_values


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
    slug = _derive_slug(request.company_name)

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
                "report_md": report.report_md or None,
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
    except asyncio.CancelledError:
        logger.info("Gap analysis pipeline cancelled: task_id=%s", task_id)
        # Status already set by cancel endpoint; just ensure slug lock released
    except Exception as exc:
        logger.exception("Gap analysis pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc)
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(slug)
        task_store.remove_task_handle(task_id)


# ── Research pipeline runner ─────────────────────────────────────────


def _has_interrupt(result: Dict[str, Any]) -> bool:
    """Check if a LangGraph invoke result contains an interrupt.

    LangGraph >=1.0: graph.invoke() does NOT raise GraphInterrupt — it returns
    normally with ``__interrupt__`` in the result dict when a node calls interrupt().
    See: https://docs.langchain.com/oss/python/langgraph/interrupts
    """
    return bool(result.get("__interrupt__"))


def _get_interrupt_value(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the first interrupt payload from a LangGraph invoke result."""
    interrupts = result.get("__interrupt__", [])
    if interrupts and hasattr(interrupts[0], "value"):
        return interrupts[0].value
    return {}


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

    LangGraph >=1.0: graph.invoke() returns normally with ``__interrupt__`` in the
    result dict when a node calls interrupt() — it does NOT raise GraphInterrupt.
    See: https://github.com/langchain-ai/langgraph/issues/3675
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    checkpointer = MemorySaver()
    graph = build_graph_fn(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": f"{task_id}-{stage_name}"}}

    event_bus.publish(task_id, "stage_start", {"stage": stage_name})
    task_store.update_task(task_id, current_step=stage_name)

    # First invocation
    result = await asyncio.to_thread(graph.invoke, initial_state, config)

    # If graph paused at approval gate, handle HITL loop
    if _has_interrupt(result):
        interrupt_values = _get_interrupt_value(result)
        interrupt_values = _enrich_interrupt_with_draft_content(interrupt_values)

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

            result = await asyncio.to_thread(
                graph.invoke, Command(resume=resume_value), config
            )

            if not _has_interrupt(result):
                break  # Completed without another interrupt

            # Another interrupt (e.g., revise → agent → approval_gate again)
            interrupt_values = _get_interrupt_value(result)
            interrupt_values = _enrich_interrupt_with_draft_content(interrupt_values)
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

    slug = _derive_slug(request.company_name)
    stages = request.stages
    auto_approve = request.auto_approve

    # Map stages to artifact types
    _stage_to_artifact_type = {
        "company": "company_context",
        "persona": "personas",
        "style_guide": "style_guides",
    }

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "research"})

            company_output_path: Optional[str] = None
            persona_paths: List[str] = []
            completed_stages: List[str] = []

            # Stage 1: Company research
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
                company_state = {"input": company_input.model_dump(mode="json"), "auto_approve": auto_approve}
                company_result = await _run_research_stage(
                    "company", build_company_graph, company_state,
                    task_id, task_store, event_bus,
                )
                # Check if stage was rejected — early exit
                decision = (company_result.get("approval_decision") or "").lower()
                if decision == "reject":
                    logger.info("Company stage rejected — stopping pipeline")
                else:
                    company_output_path = company_result.get("output_path")
                    completed_stages.append("company")

            # Stage 2: Persona research
            if "persona" in stages and "company" not in stages or "company" in completed_stages:
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
                persona_state = {"input": persona_input.model_dump(mode="json"), "auto_approve": auto_approve}
                persona_result = await _run_research_stage(
                    "persona", build_persona_graph, persona_state,
                    task_id, task_store, event_bus,
                )
                decision = (persona_result.get("approval_decision") or "").lower()
                if decision == "reject":
                    logger.info("Persona stage rejected — stopping pipeline")
                else:
                    persona_paths = persona_result.get("written_paths") or []
                    completed_stages.append("persona")

            # Stage 3: Style guide research (W1: use "style_guide" not "style")
            if "style_guide" in stages and (
                "persona" not in stages or "persona" in completed_stages
            ):
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
                style_state = {"input": style_input.model_dump(mode="json"), "auto_approve": auto_approve}
                style_result = await _run_research_stage(
                    "style_guide", build_style_graph, style_state,
                    task_id, task_store, event_bus,
                )
                decision = (style_result.get("approval_decision") or "").lower()
                if decision != "reject":
                    completed_stages.append("style_guide")

            # W3: Only report actually completed stages as produced artifacts
            produced = [
                {"type": _stage_to_artifact_type[s], "slug": slug}
                for s in completed_stages
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

    except asyncio.CancelledError:
        logger.info("Research pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Research pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(slug)
        task_store.remove_task_handle(task_id)


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

    slug = _derive_slug(input_data.company_name)

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

    except asyncio.CancelledError:
        logger.info("Content generation pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Content generation pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(slug)
        task_store.remove_task_handle(task_id)
