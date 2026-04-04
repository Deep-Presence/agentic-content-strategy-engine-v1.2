"""Knowledge Base pipeline orchestrator — DAG execution with 3 HITL checkpoints.

DAG execution order:
  Phase 1 (parallel):  company_overview + customer_reviews
  Phase 2 (sequential): competitor_scanner (needs company_overview_md)
  ── HITL-1: review 3 docs ──
  Phase 3 (parallel):  weakness_analyst + brand_perception
  ── HITL-2: review 2 docs ──
  Phase 4 (sequential): synthesis (reads all L2 docs → L3 Company Profile)
  ── HITL-3: review synthesis ──
  DONE → write artifacts

Modes:
  full:    Run all agents, all HITL checkpoints, synthesis.
  refresh: Run specified agents only, HITL + synthesis for changed docs.
  single:  Run one agent only, skip HITL and synthesis.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.models.knowledge_base import (
    L2_DOC_TYPES,
    KBAgentResult,
    KBDocType,
    KnowledgeBaseInput,
    KnowledgeBaseOutput,
)
from core.config.settings import settings
from core.research.knowledge_base.agents import (
    run_brand_perception_agent,
    run_company_overview_agent,
    run_competitor_scanner_agent,
    run_customer_reviews_agent,
    run_synthesis_agent,
    run_weakness_analyst_agent,
)
from core.research.knowledge_base.graph import (
    build_kb_doc_review_graph,
    build_kb_synthesis_review_graph,
    run_kb_hitl_checkpoint,
)
from core.research.knowledge_base.storage import KBStorage
from core.shared_tools.structured_logging import scoped_bind
from core.shared_tools.tracing import create_session, create_span, create_trace, end_span, flush, log_generation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_slug(input_data: KnowledgeBaseInput) -> str:
    """Derive company slug from input."""
    if input_data.company_slug:
        return input_data.company_slug
    # Derive from company name
    slug = input_data.company_name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug


def _resolve_mode(
    input_data: KnowledgeBaseInput,
    storage: KBStorage,
) -> Tuple[str, List[KBDocType]]:
    """Determine execution mode and target doc types.

    Returns:
        (mode, target_docs) where mode is "full", "refresh", or "single".
    """
    if input_data.refresh_docs:
        if len(input_data.refresh_docs) == 1:
            return "single", list(input_data.refresh_docs)
        return "refresh", list(input_data.refresh_docs)
    return "full", list(L2_DOC_TYPES)


def _get_doc_md(
    results: Dict[KBDocType, KBAgentResult],
    doc_type: KBDocType,
    storage: KBStorage,
) -> str:
    """Get markdown for a doc type from results, falling back to storage."""
    result = results.get(doc_type)
    if result and result.content_md:
        return result.content_md
    # Fallback to storage
    version = storage.get_latest_version(doc_type)
    if version:
        return version.content_md
    return ""


def _build_upstream_docs(
    results: Dict[KBDocType, KBAgentResult],
    storage: KBStorage,
) -> Dict[str, str]:
    """Build upstream_docs dict for brand_perception agent."""
    upstream_types = [
        KBDocType.COMPANY_OVERVIEW,
        KBDocType.CUSTOMER_REVIEWS,
        KBDocType.COMPETITOR_REGISTRY,
        KBDocType.WEAKNESS_ANALYSIS,
    ]
    docs: Dict[str, str] = {}
    for dt in upstream_types:
        md = _get_doc_md(results, dt, storage)
        if md:
            docs[dt.value] = md
    return docs


def _collect_synthesis_inputs(
    storage: KBStorage,
) -> Tuple[Dict[str, str], List[str]]:
    """Gather available/missing doc file paths for synthesis agent."""
    available: Dict[str, str] = {}
    missing: List[str] = []
    manifest = storage.read_manifest()
    for dt in L2_DOC_TYPES:
        entry = manifest.documents.get(dt.value)
        if entry and entry.current_version > 0:
            file_path = f"{dt.value}/v{entry.current_version}.md"
            available[dt.value] = file_path
        else:
            missing.append(dt.value)
    return available, missing


def _build_doc_summaries(
    results: Dict[KBDocType, KBAgentResult],
    doc_types: List[KBDocType],
) -> Dict[str, Dict[str, Any]]:
    """Build doc summaries dict for HITL checkpoint."""
    summaries: Dict[str, Dict[str, Any]] = {}
    for dt in doc_types:
        result = results.get(dt)
        if result:
            summaries[dt.value] = {
                "content_preview": result.content_md[:500] if result.content_md else "",
                "word_count": result.word_count,
                "has_error": result.error is not None,
                "error": result.error,
            }
    return summaries


def _emit(
    event_bus: Optional[Any],
    task_id: Optional[str],
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Null-safe SSE event publish."""
    if event_bus and task_id:
        event_bus.publish(task_id, event_type, data)


def _update_task(
    task_store: Optional[Any],
    task_id: Optional[str],
    **kwargs: Any,
) -> None:
    """Null-safe task_store update."""
    if task_store and task_id:
        task_store.update_task(task_id, **kwargs)


async def _maybe_extract_competitor_json(
    result: KBAgentResult,
    input_data: KnowledgeBaseInput,
    parent_span: Optional[Any] = None,
) -> None:
    """Post-process competitor_registry: extract structured JSON sidecar.

    Mutates ``result.content_json`` in-place.  Never raises — logs warnings
    on failure and leaves ``content_json`` as ``None``.
    """
    if result.error or not result.content_md:
        return
    if result.doc_type != KBDocType.COMPETITOR_REGISTRY:
        return

    span = create_span(
        parent_span,
        "competitor_extraction",
        metadata={"company_name": input_data.company_name},
        input_data={"markdown_length": len(result.content_md)},
    )

    try:
        from core.research.knowledge_base.extraction import (
            extract_competitor_registry_json,
        )

        json_data = await extract_competitor_registry_json(
            content_md=result.content_md,
            company_name=input_data.company_name,
            parent_span=span,
        )
        if json_data:
            result.content_json = json_data
            logger.info(
                "Competitor JSON sidecar extracted: %d competitors",
                json_data.get("total_competitor_count", 0),
            )
            end_span(span, output={
                "total_competitors": json_data.get("total_competitor_count", 0),
                "extraction_model": json_data.get("extraction_model", ""),
            })
        else:
            end_span(span, output={"result": "no_data_extracted"})
    except Exception:
        logger.warning(
            "Competitor JSON extraction failed — continuing without sidecar",
            exc_info=True,
        )
        end_span(span, error="Competitor extraction failed")


async def _run_single_agent(
    input_data: KnowledgeBaseInput,
    doc_type: KBDocType,
    storage: KBStorage,
    results: Dict[KBDocType, KBAgentResult],
    parent_span: Optional[Any] = None,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Run a single agent by doc type with optional revision note."""
    with scoped_bind(agent_name=doc_type.value):
        if doc_type == KBDocType.COMPANY_OVERVIEW:
            return await run_company_overview_agent(
                input_data, parent_span=parent_span, revision_note=revision_note,
            )
        elif doc_type == KBDocType.CUSTOMER_REVIEWS:
            return await run_customer_reviews_agent(
                input_data, parent_span=parent_span, revision_note=revision_note,
            )
        elif doc_type == KBDocType.COMPETITOR_REGISTRY:
            overview_md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
            result = await run_competitor_scanner_agent(
                input_data, company_overview_md=overview_md,
                parent_span=parent_span, revision_note=revision_note,
            )
            await _maybe_extract_competitor_json(result, input_data, parent_span)
            return result
        elif doc_type == KBDocType.WEAKNESS_ANALYSIS:
            overview_md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
            competitor_md = _get_doc_md(results, KBDocType.COMPETITOR_REGISTRY, storage)
            return await run_weakness_analyst_agent(
                input_data, company_overview_md=overview_md,
                competitor_registry_md=competitor_md,
                parent_span=parent_span, revision_note=revision_note,
            )
        elif doc_type == KBDocType.BRAND_PERCEPTION:
            upstream_docs = _build_upstream_docs(results, storage)
            return await run_brand_perception_agent(
                input_data, upstream_docs=upstream_docs,
                parent_span=parent_span, revision_note=revision_note,
            )
        else:
            return KBAgentResult(doc_type=doc_type, error=f"Unknown doc type: {doc_type}")


# ---------------------------------------------------------------------------
# Express mode — Eager DAG with event-based coordination
# ---------------------------------------------------------------------------


async def _run_eager_dag(
    input_data: KnowledgeBaseInput,
    storage: KBStorage,
    results: Dict[KBDocType, KBAgentResult],
    changed_doc_types: List[KBDocType],
    trace_span: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
) -> None:
    """Run all 5 L2 agents with event-based dependency coordination.

    Uses asyncio.Event for DAG signals. Each agent awaits its upstream
    events before starting. Events fire in finally blocks to prevent
    deadlocks on upstream failure.

    Timeline (express mode with sonar-pro for cr/cs):
      T=0:   co (deep, ~3m) + cr (pro, ~30s) start
      T=0.5: cr done
      T=3:   co done → cs (pro, ~30s) starts
      T=3.5: cs done → wa (deep, ~3m) + bp (~1.5m) start
      T=5:   bp done
      T=6.5: wa done → all complete
    """
    overview_done = asyncio.Event()
    reviews_done = asyncio.Event()
    competitor_done = asyncio.Event()

    _emit(event_bus, task_id, "kb_phase_start", {
        "phase": "eager", "agents": [d.value for d in L2_DOC_TYPES],
    })
    _update_task(task_store, task_id, current_step="eager_dag")

    async def _agent_co() -> None:
        with scoped_bind(agent_name="company_overview"):
            try:
                result = await run_company_overview_agent(
                    input_data, parent_span=trace_span,
                )
                results[KBDocType.COMPANY_OVERVIEW] = result
                if not result.error:
                    storage.write_version(
                        KBDocType.COMPANY_OVERVIEW, result.content_md, result.content_json,
                    )
                    changed_doc_types.append(KBDocType.COMPANY_OVERVIEW)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": "company_overview",
                    "word_count": result.word_count,
                    "has_error": result.error is not None,
                })
            except Exception as exc:
                results[KBDocType.COMPANY_OVERVIEW] = KBAgentResult(
                    doc_type=KBDocType.COMPANY_OVERVIEW, error=str(exc),
                )
            finally:
                overview_done.set()

    async def _agent_cr() -> None:
        with scoped_bind(agent_name="customer_reviews"):
            try:
                result = await run_customer_reviews_agent(
                    input_data, parent_span=trace_span,
                )
                results[KBDocType.CUSTOMER_REVIEWS] = result
                if not result.error:
                    storage.write_version(
                        KBDocType.CUSTOMER_REVIEWS, result.content_md, result.content_json,
                    )
                    changed_doc_types.append(KBDocType.CUSTOMER_REVIEWS)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": "customer_reviews",
                    "word_count": result.word_count,
                    "has_error": result.error is not None,
                })
            except Exception as exc:
                results[KBDocType.CUSTOMER_REVIEWS] = KBAgentResult(
                    doc_type=KBDocType.CUSTOMER_REVIEWS, error=str(exc),
                )
            finally:
                reviews_done.set()

    async def _agent_cs() -> None:
        with scoped_bind(agent_name="competitor_scanner"):
            await overview_done.wait()
            try:
                overview_md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
                result = await run_competitor_scanner_agent(
                    input_data, company_overview_md=overview_md, parent_span=trace_span,
                )
                results[KBDocType.COMPETITOR_REGISTRY] = result
                if not result.error:
                    await _maybe_extract_competitor_json(result, input_data, trace_span)
                    storage.write_version(
                        KBDocType.COMPETITOR_REGISTRY, result.content_md, result.content_json,
                    )
                    changed_doc_types.append(KBDocType.COMPETITOR_REGISTRY)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": "competitor_registry",
                    "word_count": result.word_count,
                    "has_error": result.error is not None,
                })
            except Exception as exc:
                results[KBDocType.COMPETITOR_REGISTRY] = KBAgentResult(
                    doc_type=KBDocType.COMPETITOR_REGISTRY, error=str(exc),
                )
            finally:
                competitor_done.set()

    async def _agent_wa() -> None:
        with scoped_bind(agent_name="weakness_analyst"):
            await overview_done.wait()
            await competitor_done.wait()
            try:
                overview_md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
                competitor_md = _get_doc_md(results, KBDocType.COMPETITOR_REGISTRY, storage)
                result = await run_weakness_analyst_agent(
                    input_data, company_overview_md=overview_md,
                    competitor_registry_md=competitor_md, parent_span=trace_span,
                )
                results[KBDocType.WEAKNESS_ANALYSIS] = result
                if not result.error:
                    storage.write_version(
                        KBDocType.WEAKNESS_ANALYSIS, result.content_md, result.content_json,
                    )
                    changed_doc_types.append(KBDocType.WEAKNESS_ANALYSIS)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": "weakness_analysis",
                    "word_count": result.word_count,
                    "has_error": result.error is not None,
                })
            except Exception as exc:
                results[KBDocType.WEAKNESS_ANALYSIS] = KBAgentResult(
                    doc_type=KBDocType.WEAKNESS_ANALYSIS, error=str(exc),
                )

    async def _agent_bp() -> None:
        with scoped_bind(agent_name="brand_perception"):
            await overview_done.wait()
            await reviews_done.wait()
            await competitor_done.wait()
            try:
                upstream_docs = _build_upstream_docs(results, storage)
                result = await run_brand_perception_agent(
                    input_data, upstream_docs=upstream_docs, parent_span=trace_span,
                )
                results[KBDocType.BRAND_PERCEPTION] = result
                if not result.error:
                    storage.write_version(
                        KBDocType.BRAND_PERCEPTION, result.content_md, result.content_json,
                    )
                    changed_doc_types.append(KBDocType.BRAND_PERCEPTION)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": "brand_perception",
                    "word_count": result.word_count,
                    "has_error": result.error is not None,
                })
            except Exception as exc:
                results[KBDocType.BRAND_PERCEPTION] = KBAgentResult(
                    doc_type=KBDocType.BRAND_PERCEPTION, error=str(exc),
                )

    await asyncio.gather(
        _agent_co(), _agent_cr(), _agent_cs(), _agent_wa(), _agent_bp(),
    )

    _emit(event_bus, task_id, "kb_phase_complete", {"phase": "eager"})


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_knowledge_base_pipeline(
    input_data: KnowledgeBaseInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
    langsmith_project: Optional[str] = None,
) -> KnowledgeBaseOutput:
    """Run the full Knowledge Base pipeline.

    Coordinates 5 specialist agents + 1 synthesis agent through
    a DAG with 3 HITL checkpoints.
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    slug = _resolve_slug(input_data)
    storage = KBStorage(root, slug)
    mode, target_docs = _resolve_mode(input_data, storage)
    results: Dict[KBDocType, KBAgentResult] = {}
    changed_doc_types: List[KBDocType] = []

    # Tracing
    session_id = create_session(slug)
    _ls_project = langsmith_project or settings.research_kb_project
    trace_span = create_trace(session_id, f"kb-pipeline/{slug}", input_data={
        "mode": mode, "target_docs": [d.value for d in target_docs],
    }, project_name=_ls_project)

    # SSE: pipeline start
    _emit(event_bus, task_id, "pipeline_start", {"pipeline": "knowledge_base"})
    _update_task(task_store, task_id, current_step="initializing")

    # Auto-approve logic
    auto_approve_cps = set(input_data.auto_approve_checkpoints)

    try:
        # =================================================================
        # Single mode — run one agent only, skip HITL and synthesis
        # =================================================================
        if mode == "single":
            dt = target_docs[0]
            _emit(event_bus, task_id, "kb_phase_start", {"phase": 0, "agents": [dt.value]})
            _update_task(task_store, task_id, current_step=f"running_{dt.value}")

            result = await _run_single_agent(input_data, dt, storage, results, trace_span)
            results[dt] = result

            if not result.error:
                storage.write_version(dt, result.content_md, result.content_json)
                changed_doc_types.append(dt)

            _emit(event_bus, task_id, "kb_agent_complete", {
                "agent": dt.value,
                "word_count": result.word_count,
                "has_error": result.error is not None,
            })

            output = KnowledgeBaseOutput(
                slug=slug,
                company_name=input_data.company_name,
                manifest=storage.read_manifest(),
                agent_results={dt.value: result},
                knowledge_base_dir=str(storage.base_dir),
                total_execution_time_s=time.time() - start_time,
                changed_docs=[d.value for d in changed_doc_types],
            )
            _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
            end_span(trace_span, output={"mode": "single"})
            flush()
            return output

        # =================================================================
        # Express mode — Eager DAG (full mode only)
        # =================================================================
        if input_data.express_mode and mode == "full":
            auto_approve_cps = auto_approve_cps | {1, 2}

            await _run_eager_dag(
                input_data, storage, results, changed_doc_types,
                trace_span, event_bus, task_id, task_store,
            )

            # Single merged HITL: review all 5 docs (auto-approved)
            doc_review_graph = build_kb_doc_review_graph()
            express_doc_types = [dt for dt in L2_DOC_TYPES if dt in results]

            if express_doc_types:
                hitl_state = {
                    "doc_summaries": _build_doc_summaries(results, express_doc_types),
                    "checkpoint": 1,
                    "auto_approve": True,
                }
                hitl_express_span = create_span(trace_span, "hitl/express", input_data={
                    "checkpoint": 1, "docs": [dt.value for dt in express_doc_types],
                })
                hitl_result = await run_kb_hitl_checkpoint(
                    doc_review_graph, hitl_state,
                    thread_id=f"kb-hitl-express-{slug}-{uuid.uuid4().hex[:8]}",
                    task_store=task_store, event_bus=event_bus, task_id=task_id,
                    stage_name="kb_checkpoint_express",
                )

                cp_decision = hitl_result.get("decision", "approve")
                end_span(hitl_express_span, output={"decision": cp_decision})
                if cp_decision == "reject":
                    output = KnowledgeBaseOutput(
                        slug=slug,
                        company_name=input_data.company_name,
                        manifest=storage.read_manifest(),
                        agent_results={dt.value: r for dt, r in results.items()},
                        knowledge_base_dir=str(storage.base_dir),
                        total_execution_time_s=time.time() - start_time,
                    )
                    _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
                    end_span(trace_span, output={"decision": "rejected_express"})
                    flush()
                    return output

                if cp_decision == "revise":
                    revision_notes = hitl_result.get("revision_notes", {})
                    for doc_type_str, note in revision_notes.items():
                        try:
                            dt_rev = KBDocType(doc_type_str)
                        except ValueError:
                            continue
                        if dt_rev not in express_doc_types:
                            continue
                        revised = await _run_single_agent(
                            input_data, dt_rev, storage, results, trace_span,
                            revision_note=note,
                        )
                        results[dt_rev] = revised
                        if not revised.error:
                            storage.write_version(
                                dt_rev, revised.content_md, revised.content_json,
                            )
                            if dt_rev not in changed_doc_types:
                                changed_doc_types.append(dt_rev)

            # Staleness propagation
            if changed_doc_types:
                storage.propagate_staleness(changed_doc_types)

            # Synthesis
            _emit(event_bus, task_id, "kb_phase_start", {
                "phase": 4, "agents": ["synthesis"],
            })
            _update_task(task_store, task_id, current_step="phase_4_synthesis")

            available_docs, missing_docs = _collect_synthesis_inputs(storage)

            with scoped_bind(agent_name="synthesis"):
                synthesis_result = await run_synthesis_agent(
                    input_data,
                    available_docs=available_docs,
                    missing_docs=missing_docs,
                    parent_span=trace_span,
                    storage_backend=storage.backend,
                    storage_prefix=storage.prefix,
                )

                synthesis_md = ""
                if not synthesis_result.error:
                    synthesis_md = synthesis_result.content_md
                    storage.write_synthesis(synthesis_md)
                else:
                    logger.error(
                        "KB synthesis failed for %s: %s",
                        slug, synthesis_result.error,
                    )

                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": "synthesis", "word_count": synthesis_result.word_count,
                    "has_error": synthesis_result.error is not None,
                })
            _emit(event_bus, task_id, "kb_phase_complete", {"phase": 4})

            # HITL-3: review synthesis (NOT auto-approved unless user set it)
            if synthesis_md:
                synthesis_review_graph = build_kb_synthesis_review_graph()
                hitl3_state = {
                    "synthesis_preview": synthesis_md[:2000],
                    "synthesis_word_count": len(synthesis_md.split()),
                    "checkpoint": 3,
                    "auto_approve": 3 in auto_approve_cps,
                }
                hitl3_express_span = create_span(trace_span, "hitl/express-cp3", input_data={
                    "checkpoint": 3, "synthesis_word_count": len(synthesis_md.split()),
                })
                hitl3_result = await run_kb_hitl_checkpoint(
                    synthesis_review_graph, hitl3_state,
                    thread_id=f"kb-hitl-3-{slug}-{uuid.uuid4().hex[:8]}",
                    task_store=task_store, event_bus=event_bus, task_id=task_id,
                    stage_name="kb_checkpoint_3",
                )

                cp3_decision = hitl3_result.get("decision", "approve")
                end_span(hitl3_express_span, output={"decision": cp3_decision})
                if cp3_decision == "reject":
                    output = KnowledgeBaseOutput(
                        slug=slug,
                        company_name=input_data.company_name,
                        manifest=storage.read_manifest(),
                        agent_results={dt.value: r for dt, r in results.items()},
                        knowledge_base_dir=str(storage.base_dir),
                        total_execution_time_s=time.time() - start_time,
                        changed_docs=[d.value for d in changed_doc_types],
                    )
                    _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
                    end_span(trace_span, output={"decision": "rejected_cp3"})
                    flush()
                    return output

                if cp3_decision == "revise":
                    revision_note_3 = hitl3_result.get("revision_note", "")
                    with scoped_bind(agent_name="synthesis"):
                        synthesis_result = await run_synthesis_agent(
                            input_data,
                            available_docs=available_docs,
                            missing_docs=missing_docs,
                            parent_span=trace_span,
                            revision_note=revision_note_3,
                            storage_backend=storage.backend,
                            storage_prefix=storage.prefix,
                        )
                        if not synthesis_result.error:
                            synthesis_md = synthesis_result.content_md
                            storage.write_synthesis(synthesis_md)

                # Promote approved synthesis
                if synthesis_md:
                    storage.promote_synthesis_to_company_context(synthesis_md)
                    manifest = storage.read_manifest()
                    manifest.last_full_refresh = datetime.now(timezone.utc)
                    storage.write_manifest(manifest)

            # DB persistence (fire-and-forget)
            try:
                from core.research.persistence import (
                    persist_kb_doc,
                    persist_kb_synthesis,
                    persist_pipeline_run_complete,
                )

                manifest = storage.read_manifest()
                for dt_p in changed_doc_types:
                    r = results.get(dt_p)
                    if r and not r.error and r.content_md:
                        entry = manifest.documents.get(dt_p.value) if manifest.documents else None
                        ver = entry.current_version if entry and entry.current_version > 0 else 1
                        await persist_kb_doc(
                            session_factory, run_id, company_id, slug,
                            dt_p.value, ver, r.content_md,
                            f"knowledge_base/{slug}/{dt_p.value}/v{ver}.md",
                        )
                if synthesis_md:
                    synth_ver = manifest.synthesis_version or 1
                    await persist_kb_synthesis(
                        session_factory, run_id, company_id, slug,
                        synth_ver, synthesis_md,
                        f"knowledge_base/{slug}/synthesis/v{synth_ver}.md",
                    )
                await persist_pipeline_run_complete(
                    session_factory, run_id,
                    {"mode": "express", "docs_changed": len(changed_doc_types)},
                )
            except Exception:
                logger.warning("KB DB persistence failed, continuing", exc_info=True)

            # Build output
            output = KnowledgeBaseOutput(
                slug=slug,
                company_name=input_data.company_name,
                manifest=storage.read_manifest(),
                agent_results={dt.value: r for dt, r in results.items()},
                synthesis_md=synthesis_md,
                company_profile_path=str(root / "company_context" / f"{slug}.md"),
                knowledge_base_dir=str(storage.base_dir),
                total_execution_time_s=time.time() - start_time,
                changed_docs=[d.value for d in changed_doc_types],
            )

            _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
            end_span(trace_span, output={"mode": "express", "docs": len(results)})
            flush()
            return output

        # =================================================================
        # Full/Refresh mode — Classic DAG execution
        # =================================================================

        # Phase 1: company_overview + customer_reviews (parallel)
        phase1_agents = [
            dt for dt in [KBDocType.COMPANY_OVERVIEW, KBDocType.CUSTOMER_REVIEWS]
            if dt in target_docs
        ]
        if phase1_agents:
            _emit(event_bus, task_id, "kb_phase_start", {
                "phase": 1, "agents": [d.value for d in phase1_agents],
            })
            _update_task(task_store, task_id, current_step="phase_1")

            phase1_tasks = [
                _run_single_agent(input_data, dt, storage, results, trace_span)
                for dt in phase1_agents
            ]
            phase1_results = await asyncio.gather(*phase1_tasks, return_exceptions=True)

            for dt, res in zip(phase1_agents, phase1_results):
                if isinstance(res, Exception):
                    res = KBAgentResult(doc_type=dt, error=str(res))
                results[dt] = res
                if not res.error:
                    storage.write_version(dt, res.content_md, res.content_json)
                    changed_doc_types.append(dt)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": dt.value, "word_count": res.word_count,
                    "has_error": res.error is not None,
                })

            _emit(event_bus, task_id, "kb_phase_complete", {"phase": 1})

        extraction_task = None  # May be set below if competitor extraction runs
        # Phase 2: competitor_scanner (needs company_overview_md)
        if KBDocType.COMPETITOR_REGISTRY in target_docs:
            _emit(event_bus, task_id, "kb_phase_start", {
                "phase": 2, "agents": ["competitor_registry"],
            })
            _update_task(task_store, task_id, current_step="phase_2")

            overview_md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
            cs_result = await run_competitor_scanner_agent(
                input_data, company_overview_md=overview_md, parent_span=trace_span,
            )
            results[KBDocType.COMPETITOR_REGISTRY] = cs_result
            if not cs_result.error:
                # Fire extraction concurrently — Phase 3 agents only need the
                # markdown (via _get_doc_md), not the JSON sidecar.  We write
                # the markdown immediately so downstream agents aren't blocked,
                # and await the extraction before the final write with JSON.
                extraction_task = asyncio.create_task(
                    _maybe_extract_competitor_json(cs_result, input_data, trace_span)
                )
                # Write markdown-only version first (JSON=None at this point)
                storage.write_version(
                    KBDocType.COMPETITOR_REGISTRY, cs_result.content_md, cs_result.content_json,
                )
                changed_doc_types.append(KBDocType.COMPETITOR_REGISTRY)
            else:
                extraction_task = None
            _emit(event_bus, task_id, "kb_agent_complete", {
                "agent": "competitor_registry", "word_count": cs_result.word_count,
                "has_error": cs_result.error is not None,
            })
            _emit(event_bus, task_id, "kb_phase_complete", {"phase": 2})

        # Await concurrent competitor JSON extraction (if running).
        # The markdown was already written — now re-write with the JSON sidecar.
        if KBDocType.COMPETITOR_REGISTRY in target_docs and extraction_task is not None:
            await extraction_task
            if cs_result.content_json is not None:
                storage.write_version(
                    KBDocType.COMPETITOR_REGISTRY, cs_result.content_md, cs_result.content_json,
                )

        # ── HITL-1: review Phase 1+2 docs ──
        # Build graph once — reused for both HITL-1 and HITL-2
        doc_review_graph = build_kb_doc_review_graph()

        cp1_docs = [KBDocType.COMPANY_OVERVIEW, KBDocType.CUSTOMER_REVIEWS, KBDocType.COMPETITOR_REGISTRY]
        cp1_doc_types = [dt for dt in cp1_docs if dt in results]

        if cp1_doc_types:

            hitl1_state = {
                "doc_summaries": _build_doc_summaries(results, cp1_doc_types),
                "checkpoint": 1,
                "auto_approve": 1 in auto_approve_cps,
            }
            hitl1_span = create_span(trace_span, "hitl/checkpoint-1", input_data={
                "checkpoint": 1, "docs": [dt.value for dt in cp1_doc_types],
            })
            hitl1_result = await run_kb_hitl_checkpoint(
                doc_review_graph, hitl1_state,
                thread_id=f"kb-hitl-1-{slug}-{uuid.uuid4().hex[:8]}",
                task_store=task_store, event_bus=event_bus, task_id=task_id,
                stage_name="kb_checkpoint_1",
            )

            # Handle HITL-1 decision
            cp1_decision = hitl1_result.get("decision", "approve")
            end_span(hitl1_span, output={"decision": cp1_decision})
            if cp1_decision == "reject":
                output = KnowledgeBaseOutput(
                    slug=slug,
                    company_name=input_data.company_name,
                    manifest=storage.read_manifest(),
                    agent_results={dt.value: r for dt, r in results.items()},
                    knowledge_base_dir=str(storage.base_dir),
                    total_execution_time_s=time.time() - start_time,
                )
                _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
                end_span(trace_span, output={"decision": "rejected_cp1"})
                flush()
                return output

            if cp1_decision == "revise":
                revision_notes = hitl1_result.get("revision_notes", {})
                for doc_type_str, note in revision_notes.items():
                    try:
                        dt = KBDocType(doc_type_str)
                    except ValueError:
                        logger.warning("HITL cp1: unknown doc_type '%s', skipping", doc_type_str)
                        continue
                    if dt not in cp1_doc_types:
                        logger.warning("HITL cp1: doc_type '%s' not in checkpoint scope, skipping", doc_type_str)
                        continue
                    revised = await _run_single_agent(
                        input_data, dt, storage, results, trace_span, revision_note=note,
                    )
                    results[dt] = revised
                    if not revised.error:
                        storage.write_version(dt, revised.content_md, revised.content_json)
                        if dt not in changed_doc_types:
                            changed_doc_types.append(dt)

        # Phase 3: weakness_analyst + brand_perception (parallel)
        phase3_agents = [
            dt for dt in [KBDocType.WEAKNESS_ANALYSIS, KBDocType.BRAND_PERCEPTION]
            if dt in target_docs
        ]
        if phase3_agents:
            _emit(event_bus, task_id, "kb_phase_start", {
                "phase": 3, "agents": [d.value for d in phase3_agents],
            })
            _update_task(task_store, task_id, current_step="phase_3")

            phase3_tasks = []
            for dt in phase3_agents:
                if dt == KBDocType.WEAKNESS_ANALYSIS:
                    overview_md = _get_doc_md(results, KBDocType.COMPANY_OVERVIEW, storage)
                    competitor_md = _get_doc_md(results, KBDocType.COMPETITOR_REGISTRY, storage)
                    phase3_tasks.append(
                        run_weakness_analyst_agent(
                            input_data, company_overview_md=overview_md,
                            competitor_registry_md=competitor_md, parent_span=trace_span,
                        )
                    )
                elif dt == KBDocType.BRAND_PERCEPTION:
                    upstream_docs = _build_upstream_docs(results, storage)
                    phase3_tasks.append(
                        run_brand_perception_agent(
                            input_data, upstream_docs=upstream_docs, parent_span=trace_span,
                        )
                    )

            phase3_results = await asyncio.gather(*phase3_tasks, return_exceptions=True)

            for dt, res in zip(phase3_agents, phase3_results):
                if isinstance(res, Exception):
                    res = KBAgentResult(doc_type=dt, error=str(res))
                results[dt] = res
                if not res.error:
                    storage.write_version(dt, res.content_md, res.content_json)
                    changed_doc_types.append(dt)
                _emit(event_bus, task_id, "kb_agent_complete", {
                    "agent": dt.value, "word_count": res.word_count,
                    "has_error": res.error is not None,
                })

            _emit(event_bus, task_id, "kb_phase_complete", {"phase": 3})

        # ── HITL-2: review Phase 3 docs ──
        cp2_doc_types = [dt for dt in phase3_agents if dt in results]
        if cp2_doc_types:
            hitl2_state = {
                "doc_summaries": _build_doc_summaries(results, cp2_doc_types),
                "checkpoint": 2,
                "auto_approve": 2 in auto_approve_cps,
            }
            hitl2_span = create_span(trace_span, "hitl/checkpoint-2", input_data={
                "checkpoint": 2, "docs": [dt.value for dt in cp2_doc_types],
            })
            hitl2_result = await run_kb_hitl_checkpoint(
                doc_review_graph, hitl2_state,
                thread_id=f"kb-hitl-2-{slug}-{uuid.uuid4().hex[:8]}",
                task_store=task_store, event_bus=event_bus, task_id=task_id,
                stage_name="kb_checkpoint_2",
            )

            cp2_decision = hitl2_result.get("decision", "approve")
            end_span(hitl2_span, output={"decision": cp2_decision})
            if cp2_decision == "reject":
                output = KnowledgeBaseOutput(
                    slug=slug,
                    company_name=input_data.company_name,
                    manifest=storage.read_manifest(),
                    agent_results={dt.value: r for dt, r in results.items()},
                    knowledge_base_dir=str(storage.base_dir),
                    total_execution_time_s=time.time() - start_time,
                )
                _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
                end_span(trace_span, output={"decision": "rejected_cp2"})
                flush()
                return output

            if cp2_decision == "revise":
                revision_notes = hitl2_result.get("revision_notes", {})
                for doc_type_str, note in revision_notes.items():
                    try:
                        dt = KBDocType(doc_type_str)
                    except ValueError:
                        logger.warning("HITL cp2: unknown doc_type '%s', skipping", doc_type_str)
                        continue
                    if dt not in cp2_doc_types:
                        logger.warning("HITL cp2: doc_type '%s' not in checkpoint scope, skipping", doc_type_str)
                        continue
                    revised = await _run_single_agent(
                        input_data, dt, storage, results, trace_span, revision_note=note,
                    )
                    results[dt] = revised
                    if not revised.error:
                        storage.write_version(dt, revised.content_md, revised.content_json)
                        if dt not in changed_doc_types:
                            changed_doc_types.append(dt)

        # Propagate staleness before synthesis
        if changed_doc_types:
            storage.propagate_staleness(changed_doc_types)

        # Phase 4: Synthesis
        _emit(event_bus, task_id, "kb_phase_start", {"phase": 4, "agents": ["synthesis"]})
        _update_task(task_store, task_id, current_step="phase_4_synthesis")

        available_docs, missing_docs = _collect_synthesis_inputs(storage)

        # Delta synthesis: refresh mode + existing synthesis → incremental update
        use_delta = False
        previous_synthesis_path: Optional[str] = None
        changed_docs_for_synth: Optional[Dict[str, str]] = None

        if mode == "refresh" and storage.read_synthesis() is not None:
            manifest = storage.read_manifest()
            previous_synthesis_path = f"synthesis/v{manifest.synthesis_version}.md"
            changed_docs_for_synth = {
                dt.value: available_docs[dt.value]
                for dt in changed_doc_types
                if dt.value in available_docs
            }
            use_delta = True

        with scoped_bind(agent_name="synthesis"):
            synthesis_result = await run_synthesis_agent(
                input_data,
                available_docs=available_docs,
                missing_docs=missing_docs,
                parent_span=trace_span,
                delta_mode=use_delta,
                changed_docs=changed_docs_for_synth,
                previous_synthesis_path=previous_synthesis_path,
                storage_backend=storage.backend,
                storage_prefix=storage.prefix,
            )

            synthesis_md = ""
            if not synthesis_result.error:
                synthesis_md = synthesis_result.content_md
                # Write synthesis version to KB storage (versioned draft)
                storage.write_synthesis(synthesis_md)
            else:
                logger.error(
                    "KB synthesis failed for %s: %s",
                    slug, synthesis_result.error,
                )

            _emit(event_bus, task_id, "kb_agent_complete", {
                "agent": "synthesis", "word_count": synthesis_result.word_count,
                "has_error": synthesis_result.error is not None,
            })
        _emit(event_bus, task_id, "kb_phase_complete", {"phase": 4})

        # ── HITL-3: review synthesis ──
        if synthesis_md:
            synthesis_review_graph = build_kb_synthesis_review_graph()
            hitl3_state = {
                "synthesis_preview": synthesis_md[:2000],
                "synthesis_word_count": len(synthesis_md.split()),
                "checkpoint": 3,
                "auto_approve": 3 in auto_approve_cps,
            }
            hitl3_span = create_span(trace_span, "hitl/checkpoint-3", input_data={
                "checkpoint": 3, "synthesis_word_count": len(synthesis_md.split()),
            })
            hitl3_result = await run_kb_hitl_checkpoint(
                synthesis_review_graph, hitl3_state,
                thread_id=f"kb-hitl-3-{slug}-{uuid.uuid4().hex[:8]}",
                task_store=task_store, event_bus=event_bus, task_id=task_id,
                stage_name="kb_checkpoint_3",
            )

            cp3_decision = hitl3_result.get("decision", "approve")
            end_span(hitl3_span, output={"decision": cp3_decision})
            if cp3_decision == "reject":
                output = KnowledgeBaseOutput(
                    slug=slug,
                    company_name=input_data.company_name,
                    manifest=storage.read_manifest(),
                    agent_results={dt.value: r for dt, r in results.items()},
                    knowledge_base_dir=str(storage.base_dir),
                    total_execution_time_s=time.time() - start_time,
                    changed_docs=[d.value for d in changed_doc_types],
                )
                _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
                end_span(trace_span, output={"decision": "rejected_cp3"})
                flush()
                return output

            if cp3_decision == "revise":
                revision_note = hitl3_result.get("revision_note", "")
                with scoped_bind(agent_name="synthesis"):
                    synthesis_result = await run_synthesis_agent(
                        input_data,
                        available_docs=available_docs,
                        missing_docs=missing_docs,
                        parent_span=trace_span,
                        revision_note=revision_note,
                        delta_mode=use_delta,
                        changed_docs=changed_docs_for_synth,
                        previous_synthesis_path=previous_synthesis_path,
                        storage_backend=storage.backend,
                        storage_prefix=storage.prefix,
                    )
                    if not synthesis_result.error:
                        synthesis_md = synthesis_result.content_md
                        storage.write_synthesis(synthesis_md)

            # Promote approved synthesis to company_context
            if synthesis_md:
                storage.promote_synthesis_to_company_context(synthesis_md)

                # Update last_full_refresh for full mode
                if mode == "full":
                    manifest = storage.read_manifest()
                    manifest.last_full_refresh = datetime.now(timezone.utc)
                    storage.write_manifest(manifest)

        # ── DB persistence (fire-and-forget) ──
        try:
            from core.research.persistence import (
                persist_kb_doc,
                persist_kb_synthesis,
                persist_pipeline_run_complete,
            )

            manifest = storage.read_manifest()
            for dt in changed_doc_types:
                r = results.get(dt)
                if r and not r.error and r.content_md:
                    entry = manifest.documents.get(dt.value) if manifest.documents else None
                    ver = entry.current_version if entry and entry.current_version > 0 else 1
                    await persist_kb_doc(
                        session_factory, run_id, company_id, slug,
                        dt.value, ver, r.content_md,
                        f"knowledge_base/{slug}/{dt.value}/v{ver}.md",
                    )
            if synthesis_md:
                synth_ver = manifest.synthesis_version or 1
                await persist_kb_synthesis(
                    session_factory, run_id, company_id, slug,
                    synth_ver, synthesis_md,
                    f"knowledge_base/{slug}/synthesis/v{synth_ver}.md",
                )
            await persist_pipeline_run_complete(
                session_factory, run_id,
                {"mode": mode, "docs_changed": len(changed_doc_types)},
            )
        except Exception:
            logger.warning("KB DB persistence failed, continuing", exc_info=True)

        # Build output
        output = KnowledgeBaseOutput(
            slug=slug,
            company_name=input_data.company_name,
            manifest=storage.read_manifest(),
            agent_results={dt.value: r for dt, r in results.items()},
            synthesis_md=synthesis_md,
            company_profile_path=str(root / "company_context" / f"{slug}.md"),
            knowledge_base_dir=str(storage.base_dir),
            total_execution_time_s=time.time() - start_time,
            changed_docs=[d.value for d in changed_doc_types],
        )

        _emit(event_bus, task_id, "completed", {"pipeline": "knowledge_base"})
        end_span(trace_span, output={"mode": mode, "docs": len(results)})
        flush()
        return output

    except Exception as exc:
        logger.exception("KB pipeline failed for %s: %s", slug, exc)
        _emit(event_bus, task_id, "failed", {"error": str(exc)})
        end_span(trace_span, error=str(exc))
        flush()
        raise
