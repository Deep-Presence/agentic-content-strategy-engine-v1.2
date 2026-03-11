"""Audience Persona pipeline orchestrator — 2-agent architecture with 2 HITL checkpoints.

Execution flow:
  Phase 0: Preflight + Load Context (validate KB outputs, load company context / reviews / knowledge docs)
  Phase 1: Agent 1 — Persona Suggester (Gemini Flash → 3-5 PersonaBriefs)
  ── HITL-1: per-brief approval (approve/modify/reject + manual add) ──
  Phase 2: Agent 2 — Profile Generator (parallel, Perplexity deep research)
  ── HITL-2: per-profile review (approve/revise/reject) ──
  Phase 3: Finalize (update manifest, emit completed)
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

from core.config.settings import settings
from core.models.audience_persona import (
    AudiencePersonaInput,
    AudiencePersonaOutput,
    PersonaAgentResult,
    PersonaBrief,
)
from core.research.audience_persona.agents import (
    _load_knowledge_docs,
    run_persona_profile_generator,
    run_persona_suggester,
)
from core.research.audience_persona.graph import (
    build_ap_brief_review_graph,
    build_ap_profile_review_graph,
    run_ap_hitl_checkpoint,
)
from core.research.audience_persona.storage import PersonaStorage
from core.shared_tools.tracing import create_session, create_span, create_trace, end_span, flush, log_generation

logger = logging.getLogger(__name__)

_MAX_COMPANY_CONTEXT_CHARS = 60_000  # ~15k tokens
_MAX_CUSTOMER_REVIEWS_CHARS = 40_000  # ~10k tokens


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_slug(input_data: AudiencePersonaInput) -> str:
    """Derive company slug from input."""
    if input_data.company_slug:
        return input_data.company_slug
    slug = input_data.company_name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug


def _resolve_effective_slug(input_data: AudiencePersonaInput) -> str:
    """Derive effective slug (company__product if product_slug is set)."""
    slug = _resolve_slug(input_data)
    if input_data.product_slug:
        return f"{slug}__{input_data.product_slug}"
    return slug


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


def _slugify_persona_name(name: str) -> str:
    """Convert persona name to a URL-safe slug for directory naming."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug or "unnamed"


def _build_id_map(approved_briefs: List[PersonaBrief]) -> Dict[str, str]:
    """Build a frozen brief_id → persona_id mapping with collision suffixing.

    Handles duplicate persona names by appending -2, -3, etc.
    Returns {brief_id: persona_id} dict.
    """
    id_map: Dict[str, str] = {}
    slug_counts: Dict[str, int] = {}

    for brief in approved_briefs:
        base_slug = _slugify_persona_name(brief.persona_name)
        count = slug_counts.get(base_slug, 0) + 1
        slug_counts[base_slug] = count

        if count == 1:
            persona_id = base_slug
        else:
            persona_id = f"{base_slug}-{count}"

        id_map[brief.brief_id] = persona_id

    return id_map


async def _preflight_check(
    root: Path,
    effective_slug: str,
    company_slug: str,
    *,
    backend: Optional["StorageBackend"] = None,
) -> Tuple[str, str, str, Optional[int]]:
    """Validate KB outputs exist and load context.

    Returns (company_context_md, customer_reviews_md, knowledge_docs_text, kb_synthesis_version).
    Raises RuntimeError if company context is missing or empty.
    """
    from core.research.utils import read_company_context
    from core.storage.backends import LocalStorageBackend

    _backend = backend or LocalStorageBackend(root)

    # Company context — check effective_slug first, fallback to company_slug
    company_md = read_company_context(_backend, effective_slug, company_slug) or ""

    if not company_md.strip():
        raise RuntimeError(
            f"Company context not found or empty at company_context/{effective_slug}.md "
            f"(also checked {company_slug}.md). Run the Knowledge Base pipeline first."
        )

    company_md = company_md[:_MAX_COMPANY_CONTEXT_CHARS]

    # Customer reviews — read from KB storage (safe version lookup)
    reviews_md = ""
    kb_synthesis_version: Optional[int] = None
    try:
        from core.models.knowledge_base import KBDocType
        from core.research.knowledge_base.storage import KBStorage

        kb_storage = KBStorage(root, effective_slug)
        kb_manifest = kb_storage.read_manifest()
        kb_synthesis_version = kb_manifest.synthesis_version or None

        version = kb_storage.get_latest_version(KBDocType.CUSTOMER_REVIEWS)
        if version and version.content_md:
            reviews_md = version.content_md[:_MAX_CUSTOMER_REVIEWS_CHARS]
        else:
            logger.warning("AP preflight: no customer_reviews found for slug=%s", effective_slug)
    except Exception as exc:
        logger.warning("AP preflight: failed to read KB storage for %s: %s", effective_slug, exc)

    # Knowledge docs
    kdocs_text = await _load_knowledge_docs(root, effective_slug, company_slug)

    return company_md, reviews_md, kdocs_text, kb_synthesis_version


def _build_profile_summaries(
    persona_results: Dict[str, PersonaAgentResult],
    storage: PersonaStorage,
) -> Dict[str, Dict[str, Any]]:
    """Build HITL-2 profile summaries with trimmed previews."""
    summaries: Dict[str, Dict[str, Any]] = {}
    manifest = storage.read_manifest()

    for pid, result in persona_results.items():
        if result.error:
            continue
        entry = manifest.personas.get(pid)
        version = entry.current_version if entry else 0
        summaries[pid] = {
            "content_preview": result.content_md[:500] if result.content_md else "",
            "word_count": result.word_count,
            "has_error": False,
            "storage_path": f"{pid}/v{version}.md",
        }

    return summaries


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_audience_persona_pipeline(
    input_data: AudiencePersonaInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
) -> AudiencePersonaOutput:
    """Run the Audience Persona pipeline.

    Coordinates a 2-agent pipeline (Suggester → Generator) through
    2 HITL checkpoints (brief approval → profile review).
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    slug = _resolve_slug(input_data)
    company_slug = slug
    effective_slug = _resolve_effective_slug(input_data)
    storage = PersonaStorage(root, effective_slug)
    auto_approve_cps = set(input_data.auto_approve_checkpoints)

    # Tracing
    session_id = create_session(slug)
    trace_span = create_trace(session_id, f"ap-pipeline/{slug}", input_data={
        "company": input_data.company_name, "max_personas": input_data.max_personas,
    })

    # SSE: pipeline start
    _emit(event_bus, task_id, "pipeline_start", {"pipeline": "audience_persona"})
    _update_task(task_store, task_id, current_step="preflight")

    try:
        # =============================================================
        # Phase 0: Preflight + Load Context
        # =============================================================
        _emit(event_bus, task_id, "ap_phase_start", {"phase": 0, "agents": ["preflight"]})

        company_md, reviews_md, kdocs_text, kb_synth_version = await _preflight_check(
            root, effective_slug, company_slug,
        )

        _emit(event_bus, task_id, "ap_phase_complete", {"phase": 0})

        # =============================================================
        # Phase 1: Persona Suggester
        # =============================================================
        _emit(event_bus, task_id, "ap_phase_start", {"phase": 1, "agents": ["persona_suggester"]})
        _update_task(task_store, task_id, current_step="phase_1_suggester")

        briefs, suggester_time = await run_persona_suggester(
            input_data=input_data,
            company_context_md=company_md,
            customer_reviews_md=reviews_md,
            knowledge_docs_text=kdocs_text,
            parent_span=trace_span,
        )

        if not briefs:
            raise RuntimeError(
                "Persona suggester returned 0 valid briefs after retry. "
                "Check company context quality or LLM availability."
            )

        _emit(event_bus, task_id, "ap_agent_complete", {
            "agent": "persona_suggester",
            "brief_count": len(briefs),
            "execution_time_s": suggester_time,
        })
        _emit(event_bus, task_id, "ap_phase_complete", {"phase": 1})

        # =============================================================
        # HITL-1: Brief Approval
        # =============================================================
        brief_review_graph = build_ap_brief_review_graph()
        hitl1_state = {
            "briefs": [b.model_dump(mode="json") for b in briefs],
            "checkpoint": 1,
            "auto_approve": 1 in auto_approve_cps,
        }

        hitl1_result = await run_ap_hitl_checkpoint(
            brief_review_graph, hitl1_state,
            thread_id=f"ap-hitl-1-{slug}-{uuid.uuid4().hex[:8]}",
            task_store=task_store, event_bus=event_bus, task_id=task_id,
            stage_name="persona_brief_review",
        )

        # Deserialize approved briefs
        approved_briefs_raw = hitl1_result.get("approved_briefs", [])
        approved_briefs: List[PersonaBrief] = []
        for raw in approved_briefs_raw:
            try:
                brief_obj = PersonaBrief.model_validate(raw)
                if not brief_obj.persona_name.strip():
                    logger.warning("Skipping approved brief with empty persona_name")
                    continue
                approved_briefs.append(brief_obj)
            except Exception:
                logger.warning("Failed to validate approved brief: %s", raw)

        # All briefs rejected → end gracefully
        if not approved_briefs:
            output = AudiencePersonaOutput(
                slug=slug,
                company_name=input_data.company_name,
                manifest=storage.read_manifest(),
                briefs_suggested=len(briefs),
                briefs_approved=0,
                profiles_generated=0,
                persona_dir=str(storage.base_dir),
                total_execution_time_s=time.time() - start_time,
            )
            _emit(event_bus, task_id, "completed", {
                "pipeline": "audience_persona", "reason": "all_briefs_rejected",
            })
            end_span(trace_span, output={"result": "all_briefs_rejected"})
            flush()
            return output

        # Build frozen ID map
        id_map = _build_id_map(approved_briefs)
        # Reverse map for HITL-2 revisions: persona_id → brief
        pid_to_brief = {pid: b for b, pid in zip(approved_briefs, [id_map[b.brief_id] for b in approved_briefs])}

        # =============================================================
        # Phase 2: Parallel Profile Generators
        # =============================================================
        _emit(event_bus, task_id, "ap_phase_start", {
            "phase": 2, "agents": [b.brief_id for b in approved_briefs],
        })
        _update_task(task_store, task_id, current_step="phase_2_generators")

        semaphore = asyncio.Semaphore(
            min(len(approved_briefs), settings.audience_persona_max_concurrent_generators),
        )
        storage_lock = asyncio.Lock()
        persona_results: Dict[str, PersonaAgentResult] = {}

        async def _run_single_generator(brief: PersonaBrief, kind: str) -> Tuple[str, PersonaAgentResult]:
            persona_id = id_map[brief.brief_id]
            async with semaphore:
                result = await run_persona_profile_generator(
                    brief=brief,
                    input_data=input_data,
                    company_context_md=company_md,
                    customer_reviews_md=reviews_md,
                    knowledge_docs_text=kdocs_text,
                    parent_span=trace_span,
                )

                if not result.error:
                    async with storage_lock:
                        storage.write_brief(persona_id, brief)
                        storage.write_version(
                            persona_id,
                            brief.persona_name,
                            result.content_md,
                            result.content_json,
                            kind=kind,
                            created_by=brief.source,
                            tagline=brief.tagline,
                        )

                _emit(event_bus, task_id, "ap_agent_complete", {
                    "agent": "persona_generator",
                    "persona_name": brief.persona_name,
                    "persona_id": persona_id,
                    "word_count": result.word_count,
                    "has_error": result.error is not None,
                })

                return persona_id, result

        tasks = []
        for i, brief in enumerate(approved_briefs):
            kind = "icp" if i == 0 else "secondary"
            tasks.append(_run_single_generator(brief, kind))

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, res in enumerate(raw_results):
            brief = approved_briefs[i]
            persona_id = id_map[brief.brief_id]
            if isinstance(res, Exception):
                persona_results[persona_id] = PersonaAgentResult(
                    brief_id=brief.brief_id,
                    persona_name=brief.persona_name,
                    error=str(res)[:500],
                )
            else:
                pid, result = res
                persona_results[pid] = result

        _emit(event_bus, task_id, "ap_phase_complete", {"phase": 2})

        # =============================================================
        # HITL-2: Profile Review
        # =============================================================
        successful_ids = [pid for pid, r in persona_results.items() if not r.error]

        if successful_ids:
            profile_review_graph = build_ap_profile_review_graph()
            profile_summaries = _build_profile_summaries(persona_results, storage)

            hitl2_state = {
                "profile_summaries": profile_summaries,
                "checkpoint": 2,
                "auto_approve": 2 in auto_approve_cps,
            }

            hitl2_result = await run_ap_hitl_checkpoint(
                profile_review_graph, hitl2_state,
                thread_id=f"ap-hitl-2-{slug}-{uuid.uuid4().hex[:8]}",
                task_store=task_store, event_bus=event_bus, task_id=task_id,
                stage_name="persona_profile_review",
            )

            # Use graph's computed fields
            revision_requests = hitl2_result.get("revision_requests", {})
            rejected_profiles = hitl2_result.get("rejected_profiles", [])

            # Handle revisions
            for pid, revision_note in revision_requests.items():
                brief = pid_to_brief.get(pid)
                if not brief:
                    logger.warning("HITL-2 revision for unknown persona_id=%s, skipping", pid)
                    continue

                revised = await run_persona_profile_generator(
                    brief=brief,
                    input_data=input_data,
                    company_context_md=company_md,
                    customer_reviews_md=reviews_md,
                    knowledge_docs_text=kdocs_text,
                    parent_span=trace_span,
                    revision_note=revision_note,
                )
                persona_results[pid] = revised

                if not revised.error:
                    async with storage_lock:
                        kind = "icp" if pid == id_map.get(approved_briefs[0].brief_id) else "secondary"
                        storage.write_version(
                            pid,
                            brief.persona_name,
                            revised.content_md,
                            revised.content_json,
                            kind=kind,
                            created_by=brief.source,
                            tagline=brief.tagline,
                        )

            # Handle rejections
            for pid in rejected_profiles:
                async with storage_lock:
                    storage.mark_persona_status(pid, "archived")

        # =============================================================
        # Phase 3: Finalize
        # =============================================================
        _emit(event_bus, task_id, "ap_phase_start", {"phase": 3, "agents": ["finalize"]})
        _update_task(task_store, task_id, current_step="phase_3_finalize")

        manifest = storage.read_manifest()
        manifest.company_name = input_data.company_name
        manifest.last_full_run = datetime.now(timezone.utc)
        if kb_synth_version is not None:
            manifest.kb_synthesis_version = kb_synth_version
            manifest.kb_synthesis_updated_at = datetime.now(timezone.utc)
        storage.write_manifest(manifest)

        profiles_generated = sum(
            1 for r in persona_results.values() if not r.error and r.content_md
        )

        # ── DB persistence (fire-and-forget) ──
        try:
            from core.research.persistence import (
                persist_persona_profile,
                persist_pipeline_run_complete,
            )

            manifest = storage.read_manifest()
            for pid, result in persona_results.items():
                if result.error or not result.content_md:
                    continue
                brief = pid_to_brief.get(pid)
                kind = "icp" if pid == id_map.get(approved_briefs[0].brief_id) else "secondary"
                meta = (manifest.personas or {}).get(pid)
                ver = meta.current_version if meta and meta.current_version > 0 else 1
                await persist_persona_profile(
                    session_factory, run_id, company_id, effective_slug,
                    pid, result.persona_name or (brief.persona_name if brief else pid),
                    ver, result.content_md,
                    f"audience_personas/{effective_slug}/{pid}/v{ver}.md",
                    kind=kind,
                )
            await persist_pipeline_run_complete(
                session_factory, run_id,
                {"profiles_generated": profiles_generated,
                 "briefs_suggested": len(briefs),
                 "briefs_approved": len(approved_briefs)},
            )
        except Exception:
            logger.warning("AP DB persistence failed, continuing", exc_info=True)

        output = AudiencePersonaOutput(
            slug=slug,
            company_name=input_data.company_name,
            manifest=storage.read_manifest(),
            briefs_suggested=len(briefs),
            briefs_approved=len(approved_briefs),
            profiles_generated=profiles_generated,
            persona_results=persona_results,
            persona_dir=str(storage.base_dir),
            total_execution_time_s=time.time() - start_time,
        )

        _emit(event_bus, task_id, "completed", {"pipeline": "audience_persona"})
        _emit(event_bus, task_id, "ap_phase_complete", {"phase": 3})
        end_span(trace_span, output={
            "briefs": len(briefs),
            "approved": len(approved_briefs),
            "profiles": profiles_generated,
        })
        flush()
        return output

    except Exception as exc:
        logger.exception("AP pipeline failed for %s: %s", slug, exc)
        _emit(event_bus, task_id, "failed", {"error": str(exc)})
        end_span(trace_span, error=str(exc))
        flush()
        raise
