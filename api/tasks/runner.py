"""Background task wrappers for pipeline execution."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from core.services.task_store import TaskStoreProtocol
from core.gap_analysis.pipeline import run_gap_analysis
from core.auth.utils.domain import derive_slug
from core.models.artifacts import CompanyResearchInput
from core.models.gap_analysis import GapAnalysisInput
from core.models.personas import PersonaResearchInput
from core.models.style_guide import StyleGuideResearchInput

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


# ── Scope resolution ──────────────────────────────────────────────────


@dataclass
class RunScope:
    """Resolved scope for a single pipeline run."""

    company_slug: str
    product_slug: Optional[str]
    effective_slug: str  # artifact dirs + lock key
    product_name: Optional[str]
    product_description: Optional[str]
    product_domain: Optional[str]


def _resolve_scope(
    company_slug: str,
    product_slug: Optional[str],
    auth_store: Optional[Any] = None,
) -> RunScope:
    """Resolve a RunScope from company_slug + product_slug.

    Looks up product details from auth_store when product_slug is set.
    Sync version — kept for CLI compatibility.
    """
    effective = f"{company_slug}__{product_slug}" if product_slug else company_slug
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_domain: Optional[str] = None

    if product_slug and auth_store:
        product = auth_store.get_product(company_slug, product_slug)
        if product:
            product_name = product.name
            product_description = product.description
            product_domain = product.domain

    return RunScope(
        company_slug=company_slug,
        product_slug=product_slug,
        effective_slug=effective,
        product_name=product_name,
        product_description=product_description,
        product_domain=product_domain,
    )


async def _resolve_scope_async(
    company_slug: str,
    product_slug: Optional[str],
    auth_service: Optional[Any] = None,
) -> RunScope:
    """Async version of _resolve_scope using AuthServiceProtocol."""
    effective = f"{company_slug}__{product_slug}" if product_slug else company_slug
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_domain: Optional[str] = None

    if product_slug and auth_service:
        product = await auth_service.get_product(company_slug, product_slug)
        if product:
            product_name = product.name
            product_description = product.description
            product_domain = product.domain

    return RunScope(
        company_slug=company_slug,
        product_slug=product_slug,
        effective_slug=effective,
        product_name=product_name,
        product_description=product_description,
        product_domain=product_domain,
    )


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
        interrupt_values["enrichment_warning"] = f"Draft files not found on disk: {draft_paths}"

    return interrupt_values


def _derive_slug(company_name: str, company_slug: Optional[str] = None) -> str:
    if company_slug:
        return company_slug
    return derive_slug(company_name) or company_name.lower()


def resolve_artifacts(
    slug: str,
    artifacts_root: Path,
    effective_slug: Optional[str] = None,
) -> Dict[str, Any]:
    """Auto-discover approved research artifacts for a company slug.

    Only resolves final (approved) artifacts — ignores .draft.md files.

    When ``effective_slug`` is provided and differs from ``slug``, applies the
    product-level fallback chain for each artifact type:
      1. Artifact scoped to effective_slug (product-specific)
      2. Artifact scoped to slug (company-level)
      3. None

    Returns a dict with resolved paths and a summary for the API response.
    """
    resolved: Dict[str, Any] = {
        "company_context_path": None,
        "persona_paths": [],
        "style_guide_path": None,
    }

    # Build lookup candidates: [effective_slug, slug] if different, else [slug]
    candidates = [effective_slug, slug] if effective_slug and effective_slug != slug else [slug]

    # Company context
    for lookup in candidates:
        company_ctx = artifacts_root / "company_context" / f"{lookup}.md"
        if company_ctx.exists():
            resolved["company_context_path"] = str(company_ctx)
            break

    # Personas: try effective_slug first, then bare slug
    personas_dir = artifacts_root / "personas"
    if personas_dir.exists():
        for lookup in candidates:
            persona_files = sorted(
                p for p in personas_dir.glob(f"{lookup}__persona-*.md")
                if not p.name.endswith(".draft.md")
            )
            if persona_files:
                resolved["persona_paths"] = [str(p) for p in persona_files]
                break

    # Style guide
    for lookup in candidates:
        style_guide = artifacts_root / "style_guides" / f"{lookup}.md"
        if style_guide.exists():
            resolved["style_guide_path"] = str(style_guide)
            break

    return resolved


async def _resolve_db_context(
    company_slug: str,
    effective_slug: str,
) -> tuple[Optional[async_sessionmaker], Optional[uuid.UUID], Optional[uuid.UUID]]:
    """Resolve session_factory, run_id, and company_id for DB persistence.

    Returns (None, None, None) if DATABASE_URL is not set or company not in DB.
    Never raises — all failures are logged and result in disabled DB writes.
    """
    try:
        from core.config.settings import settings

        if not settings.database_url:
            return None, None, None

        from core.db.engine import get_session_factory
        from core.db.repositories.company_repo import CompanyRepository

        sf = get_session_factory()
        run_id = uuid.uuid4()

        async with sf() as session:
            repo = CompanyRepository(session)
            company = await repo.get_by_slug(company_slug)
            if company is None:
                logger.warning(
                    "Company '%s' not found in DB — skipping DB persistence",
                    company_slug,
                )
                return None, None, None
            company_id = company.id

        return sf, run_id, company_id
    except Exception:
        logger.warning("DB context resolution failed — continuing without DB", exc_info=True)
        return None, None, None


async def _create_pipeline_run(
    session_factory: async_sessionmaker,
    run_id: uuid.UUID,
    company_id: uuid.UUID,
    effective_slug: str,
    pipeline_type_str: str,
) -> None:
    """Create a PipelineRunModel record in the DB."""
    try:
        from core.db.enums import PipelineStatus, PipelineType
        from core.db.models.pipelines import PipelineRunModel

        pipeline_type = PipelineType(pipeline_type_str)
        async with session_factory() as session:
            run = PipelineRunModel(
                id=run_id,
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_type=pipeline_type,
                status=PipelineStatus.running,
                started_at=datetime.now(tz=timezone.utc),
            )
            session.add(run)
            await session.commit()
    except Exception:
        logger.warning("Failed to create PipelineRunModel — continuing", exc_info=True)


async def _mark_pipeline_run_failed(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[uuid.UUID],
    error: str,
) -> None:
    """Mark a PipelineRunModel as failed."""
    if session_factory is None or run_id is None:
        return
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run:
                run.status = PipelineStatus.failed
                run.error_message = error[:2000] if error else None
                run.completed_at = datetime.now(tz=timezone.utc)
                await session.commit()
    except Exception:
        logger.warning("Failed to mark PipelineRunModel as failed", exc_info=True)


async def run_gap_pipeline_task(
    task_id: str,
    request: Any,
    artifacts_root: Path,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
    """Background task wrapper for gap analysis pipeline.

    Accepts the simplified GapAnalysisStartRequest, auto-resolves research
    artifact paths from disk, and constructs GapAnalysisInput internally.
    """
    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Resolve DB context for Phase 4 persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "gap_analysis",
        )

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "gap_analysis"})

            # Research artifacts: fallback chain (product-specific → company-level)
            resolved = resolve_artifacts(
                scope.company_slug,
                artifacts_root,
                effective_slug=scope.effective_slug,
            )

            # S1 domain: use product domain when available (D4 — Replace strategy)
            domain = request.domain
            if scope.product_domain:
                domain = scope.product_domain

            # Knowledge docs: product-level → company-level fallback
            knowledge_doc_dir: Optional[str] = None
            kdocs_base = artifacts_root / "knowledge_docs"
            for candidate_slug in [scope.effective_slug, scope.company_slug]:
                candidate_dir = kdocs_base / candidate_slug
                if candidate_dir.is_dir() and (candidate_dir / "_metadata.json").exists():
                    knowledge_doc_dir = str(candidate_dir)
                    break

            # Merge company pipeline defaults for Optional fields: request
            # values take precedence, then company defaults.  Non-optional
            # request fields (max_queries, platforms) are always present so
            # they pass through directly.
            _defaults = (await auth_service.get_pipeline_defaults(scope.company_slug)) if auth_service else None

            input_data = GapAnalysisInput(
                company_name=request.company_name,
                domain=domain,
                company_slug=scope.effective_slug,  # artifact dir uses effective slug
                seed_urls=request.seed_urls or [f"https://{domain}/"],
                company_context_path=resolved["company_context_path"],
                persona_paths=resolved["persona_paths"],
                style_guide_path=resolved["style_guide_path"],
                max_queries=request.max_queries,
                platforms=request.platforms,
                language=request.language,
                region=request.region,
                additional_constraints=request.additional_constraints,
                max_crawl_pages=(
                    request.max_crawl_pages
                    or (_defaults.max_crawl_pages if _defaults else None)
                ),
                max_crawl_depth=(
                    request.max_crawl_depth
                    or (_defaults.max_crawl_depth if _defaults else None)
                ),
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                product_description=scope.product_description,
                knowledge_doc_dir=knowledge_doc_dir,
            )

            report = await run_gap_analysis(
                input_data=input_data,
                skip_steps=request.skip_steps,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )
            result = {
                "report_md": report.report_md or None,
                "report_json": report.report_json,
                "visualization_paths": report.visualization_paths,
                "resolved_artifacts": resolved,
                "produced_artifacts": [
                    {"type": "gap_analysis", "slug": scope.effective_slug},
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
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(scope.effective_slug)
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
    task_store: TaskStoreProtocol,
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

            task_store.update_task(task_id, status=TaskStatus.RUNNING, current_step=stage_name, approval_payload=None)
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
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
    """Background task wrapper for research pipeline (company → persona → style).

    Accepts the simplified ResearchStartRequest and constructs per-stage
    core model inputs internally. The frontend never needs to know about
    artifact paths — the runner chains them automatically.
    """
    from core.research.graphs.company_research import build_graph as build_company_graph
    from core.research.graphs.persona_research import build_graph as build_persona_graph
    from core.research.graphs.style_guide import build_graph as build_style_graph

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)
    slug = scope.effective_slug  # persona/style_guide graphs use this for output paths
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
        task_store.release_slug_lock(scope.effective_slug)
        task_store.remove_task_handle(task_id)


# ── Content generation pipeline runner ───────────────────────────────


async def run_site_audit_task(
    task_id: str,
    request: Any,
    artifacts_root: Path,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
    """Background task wrapper for site audit pipeline.

    Derives slugs from the request, emits SSE events, calls the site audit
    pipeline (when implemented), persists results, and updates the task store.
    All exceptions are caught so the background task never crashes silently.

    Args:
        task_id: The task UUID created by the router.
        request: SiteAuditStartRequest with company_name, domain, and options.
        artifacts_root: Filesystem root for artifact persistence.
        task_store: Task persistence store.
        event_bus: SSE event bus for real-time progress streaming.
        auth_service: Optional auth service for product lookups.
    """
    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "site_audit"})

            try:
                from core.site_audit.pipeline import run_site_audit
                from core.models.site_audit import SiteAuditInput

                input_data = SiteAuditInput(
                    company_name=request.company_name,
                    domain=request.domain,
                    company_slug=scope.effective_slug,
                    product_slug=scope.product_slug,
                    max_pages=getattr(request, "max_pages", 200),
                    max_depth=getattr(request, "max_depth", 4),
                    check_core_web_vitals=getattr(request, "check_core_web_vitals", True),
                    check_schema_validation=getattr(request, "check_schema_validation", True),
                    check_ai_bot_access=getattr(request, "check_ai_bot_access", True),
                )

                audit_result = await run_site_audit(input_data)

                # Persist audit_result.json
                import json
                out_dir = (
                    artifacts_root
                    / "site_audit"
                    / scope.effective_slug
                    / audit_result.audit_id
                )
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "audit_result.json").write_text(
                    audit_result.model_dump_json(indent=2), encoding="utf-8"
                )

                result = {
                    "audit_id": audit_result.audit_id,
                    "domain": audit_result.domain,
                    "overall_score": audit_result.overall_score,
                    "grade": audit_result.grade,
                    "pages_crawled": audit_result.pages_crawled,
                    "status": audit_result.status,
                    "produced_artifacts": [
                        {"type": "site_audit", "slug": scope.effective_slug},
                    ],
                }

                # Propagate degraded pipeline info into task result
                if audit_result.status == "degraded":
                    result["degraded"] = True
                    result["failed_steps"] = audit_result.failed_steps
                    result["degraded_dimensions"] = audit_result.degraded_dimensions
            except (ImportError, NotImplementedError):
                # Pipeline not yet wired — record a placeholder result
                logger.warning(
                    "run_site_audit not available (pipeline not yet implemented): task_id=%s",
                    task_id,
                )
                result = {
                    "audit_id": "",
                    "domain": request.domain,
                    "status": "not_implemented",
                    "produced_artifacts": [],
                }

            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result
            )
            event_bus.publish(task_id, "completed", {"pipeline": "site_audit"})

    except asyncio.CancelledError:
        logger.info("Site audit pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Site audit pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc)
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(scope.effective_slug)
        task_store.remove_task_handle(task_id)


async def run_content_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for content generation pipeline.

    Passes task_store and event_bus through to run_content_generation() so
    Stage 4 can use HITL interrupt/resume when auto_approve is False.
    """
    from core.content_engine.pipeline import run_content_generation

    # Read effective_slug from the persisted task (set by create_task at launch)
    _task = task_store.get_task(task_id)
    effective = _task.effective_slug or _task.company_slug or _derive_slug(input_data.company_name)
    company_slug = _task.company_slug or _derive_slug(input_data.company_name)

    # Resolve DB context for Phase 4 persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        company_slug, effective
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            effective, "content",
        )

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content"})

            output = await run_content_generation(
                input_data=input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

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
                    {"type": "content", "slug": effective},
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
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(effective)
        task_store.remove_task_handle(task_id)


async def run_content_v13_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for v1.3 content generation pipeline.

    Follows the same semaphore + slug-lock + handle pattern as
    run_content_pipeline_task. Enforces the global max-3-concurrent
    semaphore and registers the task handle for cancellation.
    """
    from core.content_engine.pipeline_v13 import run_content_generation_v13

    _task = task_store.get_task(task_id)
    effective = _task.effective_slug or _task.company_slug or _derive_slug(input_data.company_name)
    company_slug = _task.company_slug or _derive_slug(input_data.company_name)

    session_factory, run_id, company_id = await _resolve_db_context(company_slug, effective)
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id, effective, "content_v13"
        )

    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content_v13"})

            output = await run_content_generation_v13(
                input_data=input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

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
                "produced_artifacts": [{"type": "content_v13", "slug": effective}],
            }
            task_store.update_task(task_id, status=TaskStatus.COMPLETED, result=result)
            event_bus.publish(task_id, "completed", {"pipeline": "content_v13"})

    except asyncio.CancelledError:
        logger.info("Content v1.3 pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Content v1.3 pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(effective)
        task_store.remove_task_handle(task_id)
