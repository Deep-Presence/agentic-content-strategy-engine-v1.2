"""Voice Style Guide pipeline orchestrator — 3-stage author-inspired voice guide generation.

Execution flow:
  Phase 0: Preflight (load company context + persona profiles, validate prereqs)
  Phase 1: Author Discovery (LiteLLM → Gemini Flash → 2-3 AuthorBriefs)
  ── HITL-1: per-author approval (approve/modify/reject) ──
  Phase 2: Author Research (Perplexity sonar-deep-research, parallel)
  Phase 3: Voice Synthesis (LiteLLM → Claude Sonnet → final guide markdown)
  Phase 4: Finalize (update manifest, promote guide, emit completed)
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
from core.content_engine.llm_client import configure_litellm_callbacks
from core.models.voice_style_guide import (
    AuthorBrief,
    AuthorResearchResult,
    VoiceStyleGuideInput,
    VoiceStyleGuideOutput,
)
from core.research.audience_persona.storage import PersonaStorage
from core.research.voice_style_guide.agents import (
    run_author_discovery,
    run_author_research,
    run_voice_synthesis,
)
from core.research.voice_style_guide.graph import (
    build_vsg_author_review_graph,
    run_vsg_hitl_checkpoint,
)
from core.research.utils import load_persona_profiles, read_company_context
from core.research.voice_style_guide.storage import VoiceStyleGuideStorage
from core.shared_tools.structured_logging import scoped_bind
from core.shared_tools.tracing import (
    create_session,
    create_span,
    create_trace,
    end_span,
    flush,
)

logger = logging.getLogger(__name__)

_MAX_AUTHOR_RESEARCH_CHARS = 60_000  # ~15k tokens per author
_MAX_COMPANY_CONTEXT_CHARS = 60_000


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_slug(input_data: VoiceStyleGuideInput) -> str:
    """Derive company slug from input."""
    if input_data.company_slug:
        return input_data.company_slug
    slug = input_data.company_name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug


def _resolve_effective_slug(input_data: VoiceStyleGuideInput) -> str:
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


def _slugify_author_name(name: str) -> str:
    """Convert author name to a URL-safe slug for directory naming.

    NOTE: Keep in sync with ``_slugify_name`` in ``agents.py``.
    Both are intentionally kept local to avoid a cross-module import
    cycle (agents ← pipeline would be circular via graph imports).
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-") or "unknown"


def _build_author_id_map(approved_authors: List[AuthorBrief]) -> Dict[str, str]:
    """Build frozen name → author_id mapping with collision suffixing.

    Returns {original_author_id: final_author_id} dict.
    """
    id_map: Dict[str, str] = {}
    slug_counts: Dict[str, int] = {}

    for author in approved_authors:
        base_slug = _slugify_author_name(author.name)
        count = slug_counts.get(base_slug, 0) + 1
        slug_counts[base_slug] = count

        if count == 1:
            final_id = base_slug
        else:
            final_id = f"{base_slug}-{count}"

        id_map[author.author_id] = final_id

    return id_map


def _build_persona_summaries(persona_mds: List[str], max_chars: int = 30_000) -> str:
    """Build a concatenated summary of all persona profiles for research prompts."""
    if not persona_mds:
        return ""
    parts = []
    for i, md in enumerate(persona_mds, 1):
        parts.append(f"### Persona {i}\n\n{md[:10_000]}")
    result = "\n\n---\n\n".join(parts)
    return result[:max_chars]


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_voice_style_guide_pipeline(
    input_data: VoiceStyleGuideInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
) -> VoiceStyleGuideOutput:
    """Run the Voice Style Guide pipeline.

    Coordinates a 3-stage pipeline (Discovery → Research → Synthesis)
    through 1 HITL checkpoint (author approval after discovery).
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    slug = _resolve_slug(input_data)
    company_slug = slug
    effective_slug = _resolve_effective_slug(input_data)
    storage = VoiceStyleGuideStorage(root, effective_slug)
    auto_approve_cps = set(input_data.auto_approve_checkpoints)

    # Configure LiteLLM callbacks for LangSmith tracing
    configure_litellm_callbacks()

    # Tracing
    session_id = create_session(slug)
    trace_span = create_trace(session_id, f"vsg-pipeline/{slug}", input_data={
        "company": input_data.company_name, "max_authors": input_data.max_authors,
    })

    # SSE: pipeline start
    _emit(event_bus, task_id, "pipeline_start", {"pipeline": "voice_style_guide"})
    _update_task(task_store, task_id, current_step="preflight")

    try:
        # =============================================================
        # Phase 0: Preflight — Load Context + Personas
        # =============================================================
        _emit(event_bus, task_id, "vsg_phase_start", {"phase": 0, "agents": ["preflight"]})

        # Load company context
        from core.storage.backends import LocalStorageBackend

        _backend = LocalStorageBackend(root)
        company_md = read_company_context(_backend, effective_slug, company_slug) or ""

        if not company_md.strip():
            raise RuntimeError(
                f"Company context not found or empty at company_context/{effective_slug}.md "
                f"(also checked {company_slug}.md). Run the Knowledge Base pipeline first."
            )

        company_md = company_md[:_MAX_COMPANY_CONTEXT_CHARS]

        # Load persona profiles
        persona_mds = load_persona_profiles(_backend, effective_slug, company_slug)
        if not persona_mds:
            raise RuntimeError(
                f"No active persona profiles found for slug={effective_slug}. "
                f"Run the Audience Persona pipeline first."
            )

        persona_summaries = _build_persona_summaries(persona_mds)

        _emit(event_bus, task_id, "vsg_phase_complete", {"phase": 0})

        # =============================================================
        # Phase 1: Author Discovery
        # =============================================================
        _emit(event_bus, task_id, "vsg_phase_start", {"phase": 1, "agents": ["author_discovery"]})
        _update_task(task_store, task_id, current_step="phase_1_author_discovery")

        with scoped_bind(agent_name="author_discovery"):
            briefs, discovery_time = await run_author_discovery(
                input_data=input_data,
                company_context_md=company_md,
                persona_mds=persona_mds,
                parent_span=trace_span,
            )

        if not briefs:
            raise RuntimeError(
                "Author discovery returned 0 valid authors after retry. "
                "Check company context quality or LLM availability."
            )

        # Write discovery artifact
        await asyncio.to_thread(storage.write_discovery, briefs)

        _emit(event_bus, task_id, "vsg_agent_complete", {
            "agent": "author_discovery",
            "author_count": len(briefs),
            "execution_time_s": discovery_time,
        })
        _emit(event_bus, task_id, "vsg_phase_complete", {"phase": 1})

        # =============================================================
        # HITL-1: Author Approval
        # =============================================================
        author_review_graph = build_vsg_author_review_graph()
        hitl1_state = {
            "authors": [b.model_dump(mode="json") for b in briefs],
            "checkpoint": 1,
            "auto_approve": 1 in auto_approve_cps,
        }

        hitl1_result = await run_vsg_hitl_checkpoint(
            author_review_graph, hitl1_state,
            thread_id=f"vsg-hitl-1-{slug}-{uuid.uuid4().hex[:8]}",
            task_store=task_store, event_bus=event_bus, task_id=task_id,
            stage_name="vsg_author_review",
        )

        # Deserialize approved authors
        approved_authors_raw = hitl1_result.get("approved_authors", [])
        approved_authors: List[AuthorBrief] = []
        for raw in approved_authors_raw:
            try:
                author_obj = AuthorBrief.model_validate(raw)
                if not author_obj.name.strip():
                    logger.warning("Skipping approved author with empty name")
                    continue
                approved_authors.append(author_obj)
            except Exception:
                logger.warning("Failed to validate approved author: %s", raw)

        # All authors rejected → end gracefully
        if not approved_authors:
            output = VoiceStyleGuideOutput(
                slug=slug,
                company_name=input_data.company_name,
                manifest=storage.read_manifest(),
                authors_discovered=len(briefs),
                authors_approved=0,
                guide_dir=str(storage.base_dir),
                total_execution_time_s=time.time() - start_time,
            )
            _emit(event_bus, task_id, "completed", {
                "pipeline": "voice_style_guide", "reason": "all_authors_rejected",
            })
            end_span(trace_span, output={"result": "all_authors_rejected"})
            flush()
            return output

        # Build frozen ID map
        id_map = _build_author_id_map(approved_authors)

        # =============================================================
        # Phase 2: Parallel Author Research
        # =============================================================
        _emit(event_bus, task_id, "vsg_phase_start", {
            "phase": 2, "agents": [a.author_id for a in approved_authors],
        })
        _update_task(task_store, task_id, current_step="phase_2_author_research")

        semaphore = asyncio.Semaphore(
            min(len(approved_authors), settings.voice_style_guide_max_concurrent_researchers),
        )
        storage_lock = asyncio.Lock()
        research_results: Dict[str, AuthorResearchResult] = {}

        async def _run_single_researcher(author: AuthorBrief) -> Tuple[str, AuthorResearchResult]:
            with scoped_bind(agent_name="author_research"):
                author_id = id_map[author.author_id]
                async with semaphore:
                    result = await run_author_research(
                        brief=author,
                        input_data=input_data,
                        company_context_md=company_md,
                        persona_summaries=persona_summaries,
                        parent_span=trace_span,
                    )

                    if not result.error:
                        async with storage_lock:
                            await asyncio.to_thread(
                                storage.write_author_brief, author_id, author,
                            )
                            await asyncio.to_thread(
                                storage.write_author_research,
                                author_id, author.name, result.content_md,
                            )

                    _emit(event_bus, task_id, "vsg_agent_complete", {
                        "agent": "author_research",
                        "author_name": author.name,
                        "author_id": author_id,
                        "word_count": result.word_count,
                        "has_error": result.error is not None,
                    })

                    return author_id, result

        tasks = [_run_single_researcher(author) for author in approved_authors]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, res in enumerate(raw_results):
            author = approved_authors[i]
            author_id = id_map[author.author_id]
            if isinstance(res, Exception):
                research_results[author_id] = AuthorResearchResult(
                    author_id=author_id,
                    name=author.name,
                    error=str(res)[:500],
                )
            else:
                aid, result = res
                research_results[aid] = result

        _emit(event_bus, task_id, "vsg_phase_complete", {"phase": 2})

        # =============================================================
        # Phase 3: Voice Synthesis
        # =============================================================
        # Collect successful research (skip errored)
        author_research_mds: Dict[str, str] = {}
        for aid, result in research_results.items():
            if not result.error and result.content_md:
                # Apply per-author token cap
                author_research_mds[aid] = result.content_md[:_MAX_AUTHOR_RESEARCH_CHARS]

        if not author_research_mds:
            logger.error("All author research failed — cannot synthesize guide")
            output = VoiceStyleGuideOutput(
                slug=slug,
                company_name=input_data.company_name,
                manifest=storage.read_manifest(),
                authors_discovered=len(briefs),
                authors_approved=len(approved_authors),
                authors_researched=0,
                guide_dir=str(storage.base_dir),
                total_execution_time_s=time.time() - start_time,
            )
            _emit(event_bus, task_id, "completed", {
                "pipeline": "voice_style_guide", "reason": "all_research_failed",
            })
            end_span(trace_span, output={"result": "all_research_failed"})
            flush()
            return output

        _emit(event_bus, task_id, "vsg_phase_start", {"phase": 3, "agents": ["voice_synthesis"]})
        _update_task(task_store, task_id, current_step="phase_3_voice_synthesis")

        with scoped_bind(agent_name="voice_synthesis"):
            guide_md, synthesis_time = await run_voice_synthesis(
                author_research_mds=author_research_mds,
                company_context_md=company_md,
                persona_mds=persona_mds,
                input_data=input_data,
                parent_span=trace_span,
            )

        if not guide_md.strip():
            logger.error("Voice synthesis returned empty guide")
            output = VoiceStyleGuideOutput(
                slug=slug,
                company_name=input_data.company_name,
                manifest=storage.read_manifest(),
                authors_discovered=len(briefs),
                authors_approved=len(approved_authors),
                authors_researched=len(author_research_mds),
                guide_dir=str(storage.base_dir),
                total_execution_time_s=time.time() - start_time,
            )
            _emit(event_bus, task_id, "completed", {
                "pipeline": "voice_style_guide", "reason": "synthesis_empty",
            })
            end_span(trace_span, output={"result": "synthesis_empty"})
            flush()
            return output

        # Write guide + promote
        source_authors = list(author_research_mds.keys())
        await asyncio.to_thread(
            storage.write_guide, guide_md, source_authors=source_authors,
        )

        _emit(event_bus, task_id, "vsg_agent_complete", {
            "agent": "voice_synthesis",
            "word_count": len(guide_md.split()),
            "execution_time_s": synthesis_time,
        })
        _emit(event_bus, task_id, "vsg_phase_complete", {"phase": 3})

        # =============================================================
        # Phase 4: Finalize
        # =============================================================
        _emit(event_bus, task_id, "vsg_phase_start", {"phase": 4, "agents": ["finalize"]})
        _update_task(task_store, task_id, current_step="phase_4_finalize")

        # Promote to style_guides/
        style_guide_path = await asyncio.to_thread(
            storage.promote_to_style_guides, root,
        ) or ""

        # Update manifest
        manifest = storage.read_manifest()
        manifest.company_name = input_data.company_name
        manifest.last_full_run = datetime.now(timezone.utc)
        storage.write_manifest(manifest)

        # ── DB persistence (fire-and-forget) ──
        try:
            from core.research.persistence import (
                persist_author_research,
                persist_pipeline_run_complete,
                persist_voice_style_guide,
            )

            for aid, result in research_results.items():
                if result.error or not result.content_md:
                    continue
                author_meta = (manifest.authors or {}).get(aid)
                aver = author_meta.current_version if author_meta and author_meta.current_version > 0 else 1
                await persist_author_research(
                    session_factory, run_id, company_id, effective_slug,
                    aid, result.name, aver, result.content_md,
                    f"voice_style_guide/{effective_slug}/{aid}/v{aver}.md",
                )
            guide_ver = manifest.guide.current_version if manifest.guide and manifest.guide.current_version > 0 else 1
            await persist_voice_style_guide(
                session_factory, run_id, company_id, effective_slug,
                guide_ver, guide_md,
                f"voice_style_guide/{effective_slug}/guide/v{guide_ver}.md",
                source_authors=source_authors,
            )
            await persist_pipeline_run_complete(
                session_factory, run_id,
                {"authors_researched": len(author_research_mds),
                 "guide_generated": True},
            )
        except Exception:
            logger.warning("VSG DB persistence failed, continuing", exc_info=True)

        output = VoiceStyleGuideOutput(
            slug=slug,
            company_name=input_data.company_name,
            manifest=storage.read_manifest(),
            authors_discovered=len(briefs),
            authors_approved=len(approved_authors),
            authors_researched=len(author_research_mds),
            guide_generated=True,
            guide_dir=str(storage.base_dir),
            style_guide_path=style_guide_path,
            total_execution_time_s=time.time() - start_time,
        )

        _emit(event_bus, task_id, "completed", {"pipeline": "voice_style_guide"})
        _emit(event_bus, task_id, "vsg_phase_complete", {"phase": 4})
        end_span(trace_span, output={
            "authors_discovered": len(briefs),
            "authors_approved": len(approved_authors),
            "authors_researched": len(author_research_mds),
            "guide_generated": True,
        })
        flush()
        return output

    except Exception as exc:
        logger.exception("VSG pipeline failed for %s: %s", slug, exc)
        _emit(event_bus, task_id, "failed", {"error": str(exc)})
        end_span(trace_span, error=str(exc))
        flush()
        raise
