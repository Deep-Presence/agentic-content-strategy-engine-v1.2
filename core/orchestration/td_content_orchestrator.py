"""End-to-end orchestrator: Topic Discovery → Gap Analysis → Content Engine.

Chains approved TopicAssignments from TD Pipeline B through a topic-scoped
GA run and into the Content Engine in TOPIC_DISCOVERY mode.

Supports three entry patterns:
  1. Combined (original): ``run_td_to_content_pipeline()`` — GA + CE as one task.
  2. GA-only: ``run_td_gap_analysis_only()`` — Phase 1 of the two-phase split.
  3. CE-only: ``run_td_content_production_only()`` — Phase 2, after user reviews GA.

Usage:
    # Combined (backward compat)
    output = await run_td_to_content_pipeline(...)

    # Two-phase split
    ga_result = await run_td_gap_analysis_only(...)
    output = await run_td_content_production_only(ga_run_id=ga_result.ga_run_id, ...)
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis
from core.models.content_generation import ContentGenerationOutput
from core.models.content_generation_v13 import (
    ContentGenerationInputV13,
    EntryMode,
)
from core.models.gap_analysis import GapAnalysisInput
from core.models.topic_discovery import (
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicAssignmentStatus,
)
from core.research.audience_persona.storage import PersonaStorage
from core.topic_discovery.db_ops import db_read_latest_matrix, db_read_manifest

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


@dataclass
class GapAnalysisOnlyResult:
    """Result of the GA-only phase of the two-phase pipeline."""

    ga_run_id: str
    valid_assignment_ids: List[str]
    analysis_path: str
    topic_query_map: Dict[str, List[str]] = field(default_factory=dict)


class TDContentPipelineError(RuntimeError):
    """Error raised during TD → GA → CE orchestration."""


def _derive_slug(company_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")


async def _update_assignment_statuses_db(
    session_factory: async_sessionmaker,
    assignment_ids: List[str],
    new_status: TopicAssignmentStatus,
) -> None:
    """Update assignment statuses in the database."""
    from core.topic_discovery.persistence import persist_td_assignment_status_batch
    await persist_td_assignment_status_batch(session_factory, assignment_ids, new_status.value)
    logger.info("Updated %d assignments → %s (DB)", len(assignment_ids), new_status.value)


async def _validate_preflight_db(
    session_factory: async_sessionmaker,
    effective_slug: str,
    topic_assignment_ids: List[str],
) -> TopicAssignmentMatrix:
    """Validate prerequisites using DB reads.

    Checks:
      1. Company context file exists and is non-empty
      2. At least 1 persona artifact exists
      3. TD matrix exists in DB and contains the requested assignment IDs

    Returns the matrix on success.
    """
    # 1. Company context
    ctx_path = _PROJECT_ROOT / "artifacts" / "company_context" / f"{effective_slug}.md"
    if not ctx_path.exists() or ctx_path.stat().st_size == 0:
        raise TDContentPipelineError(
            f"Company context not found or empty: {ctx_path}. "
            "Run the Knowledge Base pipeline first."
        )

    # 2. Personas
    persona_storage = PersonaStorage(
        artifacts_root=_PROJECT_ROOT / "artifacts", slug=effective_slug
    )
    persona_paths = persona_storage.list_persona_paths()
    if not persona_paths:
        raise TDContentPipelineError(
            f"No persona artifacts found for slug '{effective_slug}'. "
            "Run the Audience Persona pipeline first."
        )

    # 3. TD matrix from DB with requested IDs
    manifest = await db_read_manifest(session_factory, effective_slug)
    if manifest.matrix_version == 0:
        raise TDContentPipelineError(f"No matrix found for '{effective_slug}'")
    matrix = await db_read_latest_matrix(session_factory, effective_slug)
    if matrix is None:
        raise TDContentPipelineError(f"Matrix read returned None for '{effective_slug}'")
    existing_ids = {a.id for a in matrix.assignments}
    missing = set(topic_assignment_ids) - existing_ids
    if missing:
        raise TDContentPipelineError(f"Assignment IDs not found in matrix: {missing}")
    return matrix


async def run_td_to_content_pipeline(
    effective_slug: str,
    topic_assignment_ids: List[str],
    company_name: str,
    domain: str,
    *,
    existing_ga_slug: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    auto_approve: bool = False,
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    session_factory: async_sessionmaker = None,  # type: ignore[assignment]
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
) -> ContentGenerationOutput:
    """Orchestrate TD → scoped GA → CE as a single pipeline.

    Steps:
      1. Preflight validation (company context, personas, matrix)
      2. Load TopicAssignments, filter excluded combos
      3. Run topic-scoped gap analysis
      4. Launch Content Engine in TOPIC_DISCOVERY mode
      5. Return ContentGenerationOutput

    Args:
        effective_slug: Artifact scope slug (company or company__product).
        topic_assignment_ids: IDs of approved TopicAssignments to process.
        company_name: Company display name.
        domain: Company domain.
        existing_ga_slug: If set, reuse S1 embeddings from this GA run.
        platforms: Search platforms (default: all 4).
        auto_approve: Auto-approve HITL checkpoints.
        product_slug: Optional product slug for product-level runs.
        product_name: Optional product display name.
        product_description: Optional product description.
        task_id: Optional task ID for progress tracking.
        task_store: Optional TaskStore for progress updates.
        event_bus: Optional EventBus for SSE events.
        session_factory: Optional DB session factory.
        run_id: Optional pipeline run UUID.
        company_id: Optional company UUID.

    Returns:
        ContentGenerationOutput with pieces tagged by topic_assignment_id.

    Raises:
        TDContentPipelineError: On preflight validation failure.
    """
    pipeline_start = time.monotonic()
    ga_run_id = run_id or uuid.uuid4()
    platforms = platforms or ["perplexity", "openai", "gemini", "claude"]

    if session_factory is None:
        raise TDContentPipelineError("session_factory is required for TD→Content orchestration")

    logger.info(
        "TD→Content orchestrator: slug=%s, %d topics, run_id=%s",
        effective_slug, len(topic_assignment_ids), ga_run_id,
    )

    # Step 1: Preflight (DB-backed) — also returns the matrix
    matrix = await _validate_preflight_db(session_factory, effective_slug, topic_assignment_ids)

    # Step 2: Load requested assignments
    requested_ids = set(topic_assignment_ids)
    valid_assignments = [a for a in matrix.assignments if a.id in requested_ids]

    if not valid_assignments:
        logger.warning("No matching assignments found for requested IDs.")
        return ContentGenerationOutput(
            company_slug=effective_slug,
            run_metadata={"error": "No matching topic assignments found"},
        )

    logger.info(
        "Step 2: %d valid assignments (from %d requested)",
        len(valid_assignments), len(topic_assignment_ids),
    )

    # Step 2b: Update assignment status → in_gap_analysis (DB)
    valid_ids = [a.id for a in valid_assignments]
    await _update_assignment_statuses_db(
        session_factory, valid_ids, TopicAssignmentStatus.in_gap_analysis,
    )

    # Step 3: Build GapAnalysisInput and run scoped GA
    company_context_path = f"artifacts/company_context/{effective_slug}.md"
    persona_storage = PersonaStorage(
        artifacts_root=_PROJECT_ROOT / "artifacts", slug=effective_slug
    )
    persona_paths = persona_storage.list_persona_paths()

    base_input = GapAnalysisInput(
        company_name=company_name,
        domain=domain,
        company_slug=effective_slug,
        company_context_path=company_context_path,
        persona_paths=persona_paths,
        platforms=platforms,
        product_slug=product_slug,
        product_name=product_name,
        product_description=product_description,
    )

    _report, topic_query_map = await run_topic_scoped_gap_analysis(
        topics=valid_assignments,
        base_input=base_input,
        existing_ga_slug=existing_ga_slug,
        run_id=ga_run_id,
        session_factory=session_factory,
        company_id=company_id,
    )

    ga_elapsed = time.monotonic() - pipeline_start
    logger.info("Step 3: Scoped GA completed in %.1fs", ga_elapsed)

    # H3 guard: fail fast if GA produced no usable queries
    if not topic_query_map:
        raise TDContentPipelineError(
            "Topic-scoped Gap Analysis produced no queries. "
            "All topic × cluster combinations may have been filtered or empty."
        )

    # Step 4: Launch Content Engine in TOPIC_DISCOVERY mode
    from core.content_engine.pipeline_v13 import run_content_generation_v13
    from core.redis import get_redis_or_none as _get_async_redis

    # Acquire async Redis client for CE pipeline state writes.
    # Without this, CE writes to file only and get_briefs() falls back to
    # stale pipeline_state.json — root cause of 4-min kanban sync lag.
    _redis_async = _get_async_redis()

    ce_input = ContentGenerationInputV13(
        company_name=company_name,
        domain=domain,
        company_slug=effective_slug,
        company_context_path=company_context_path,
        persona_paths=persona_paths,
        entry_mode=EntryMode.TOPIC_DISCOVERY,
        topic_assignment_ids=[a.id for a in valid_assignments],
        td_effective_slug=effective_slug,
        td_ga_run_id=str(ga_run_id),
        auto_approve=auto_approve,
        product_slug=product_slug,
        product_name=product_name,
        product_description=product_description,
        # Use scoped analysis for CE
        analysis_json_path=str(
            _PROJECT_ROOT / "artifacts" / "gap_analysis" / effective_slug
            / "topic_scoped" / str(ga_run_id) / "analysis.json"
        ),
    )

    output = await run_content_generation_v13(
        ce_input,
        task_id=task_id,
        task_store=task_store,
        event_bus=event_bus,
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
        redis_client=_redis_async,
    )

    # Step 5: Update assignment status based on outcome
    if len(output.pieces) > 0:
        await _update_assignment_statuses_db(
            session_factory, valid_ids, TopicAssignmentStatus.content_produced,
        )
    else:
        logger.warning(
            "Combined orchestrator produced zero pieces — reverting %d assignments to gap_analysis_complete",
            len(valid_ids),
        )
        await _update_assignment_statuses_db(
            session_factory, valid_ids, TopicAssignmentStatus.gap_analysis_complete,
        )

    total_elapsed = time.monotonic() - pipeline_start
    logger.info(
        "TD→Content orchestrator completed: %d pieces, %.1fs total",
        len(output.pieces), total_elapsed,
    )

    return output


# ---------------------------------------------------------------------------
# Phase 1: Gap Analysis Only
# ---------------------------------------------------------------------------


async def run_td_gap_analysis_only(
    effective_slug: str,
    topic_assignment_ids: List[str],
    company_name: str,
    domain: str,
    *,
    existing_ga_slug: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    session_factory: async_sessionmaker = None,  # type: ignore[assignment]
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
) -> GapAnalysisOnlyResult:
    """Phase 1: Run topic-scoped GA only (no Content Engine).

    Performs preflight, loads/filters assignments, runs GA with SSE
    instrumentation, and updates assignment status to gap_analysis_complete.

    The frontend shows real-time GA progress. On completion the user
    decides whether to click "Start Production" (Phase 2).

    Returns GapAnalysisOnlyResult with ga_run_id and analysis_path.
    """
    pipeline_start = time.monotonic()
    ga_run_id = run_id or uuid.uuid4()
    platforms = platforms or ["perplexity", "openai", "gemini", "claude"]

    if session_factory is None:
        raise TDContentPipelineError("session_factory is required for TD→GA orchestration")

    logger.info(
        "TD→GA orchestrator (Phase 1): slug=%s, %d topics, run_id=%s",
        effective_slug, len(topic_assignment_ids), ga_run_id,
    )

    # Step 1: Preflight (DB-backed)
    matrix = await _validate_preflight_db(session_factory, effective_slug, topic_assignment_ids)

    # Step 2: Load requested assignments
    requested_ids = set(topic_assignment_ids)
    valid_assignments = [a for a in matrix.assignments if a.id in requested_ids]

    if not valid_assignments:
        logger.warning("No matching assignments found for requested IDs.")
        return GapAnalysisOnlyResult(
            ga_run_id=str(ga_run_id),
            valid_assignment_ids=[],
            analysis_path="",
        )

    valid_ids = [a.id for a in valid_assignments]
    logger.info(
        "Step 2: %d valid assignments (from %d requested)",
        len(valid_assignments), len(topic_assignment_ids),
    )

    # Step 2b: Update assignment status → in_gap_analysis
    await _update_assignment_statuses_db(
        session_factory, valid_ids, TopicAssignmentStatus.in_gap_analysis,
    )

    # Step 2c: Write GA-phase state to Redis for Content Studio cards
    _write_ga_phase_redis(
        effective_slug, valid_assignments, "gap_analysis_pending",
        task_id=task_id, ga_run_id=str(ga_run_id),
    )

    # Step 3: Build GapAnalysisInput and run scoped GA
    company_context_path = f"artifacts/company_context/{effective_slug}.md"
    persona_storage = PersonaStorage(
        artifacts_root=_PROJECT_ROOT / "artifacts", slug=effective_slug
    )
    persona_paths = persona_storage.list_persona_paths()

    base_input = GapAnalysisInput(
        company_name=company_name,
        domain=domain,
        company_slug=effective_slug,
        company_context_path=company_context_path,
        persona_paths=persona_paths,
        platforms=platforms,
        product_slug=product_slug,
        product_name=product_name,
        product_description=product_description,
    )

    # Update GA-phase state → gap_analysis (running)
    _write_ga_phase_redis(
        effective_slug, valid_assignments, "gap_analysis",
        task_id=task_id, ga_run_id=str(ga_run_id),
    )
    _emit_company_event(effective_slug, "state_changed", {
        "changed": [a.id for a in valid_assignments], "hint": "gap_analysis",
    })

    _report, topic_query_map = await run_topic_scoped_gap_analysis(
        topics=valid_assignments,
        base_input=base_input,
        existing_ga_slug=existing_ga_slug,
        run_id=ga_run_id,
        session_factory=session_factory,
        company_id=company_id,
        event_bus=event_bus,
        task_id=task_id,
    )

    ga_elapsed = time.monotonic() - pipeline_start
    logger.info("Step 3: Scoped GA completed in %.1fs", ga_elapsed)

    if not topic_query_map:
        raise TDContentPipelineError(
            "Topic-scoped Gap Analysis produced no queries. "
            "All topic × cluster combinations may have been filtered or empty."
        )

    # Step 4: Update status → gap_analysis_complete
    await _update_assignment_statuses_db(
        session_factory, valid_ids, TopicAssignmentStatus.gap_analysis_complete,
    )

    # Update GA-phase state → gap_analysis_complete
    analysis_path = str(
        _PROJECT_ROOT / "artifacts" / "gap_analysis" / effective_slug
        / "topic_scoped" / str(ga_run_id) / "analysis.json"
    )
    _write_ga_phase_redis(
        effective_slug, valid_assignments, "gap_analysis_complete",
        task_id=task_id, ga_run_id=str(ga_run_id),
    )
    _emit_company_event(effective_slug, "state_changed", {
        "changed": [a.id for a in valid_assignments], "hint": "gap_analysis_complete",
    })

    logger.info(
        "TD���GA orchestrator (Phase 1) completed: %d topics, %.1fs",
        len(valid_ids), time.monotonic() - pipeline_start,
    )

    return GapAnalysisOnlyResult(
        ga_run_id=str(ga_run_id),
        valid_assignment_ids=valid_ids,
        analysis_path=analysis_path,
        topic_query_map=topic_query_map,
    )


# ---------------------------------------------------------------------------
# Phase 2: Content Engine Production Only
# ---------------------------------------------------------------------------


async def run_td_content_production_only(
    effective_slug: str,
    topic_assignment_ids: List[str],
    company_name: str,
    domain: str,
    ga_run_id: str,
    *,
    auto_approve: bool = False,
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    session_factory: async_sessionmaker = None,  # type: ignore[assignment]
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
) -> ContentGenerationOutput:
    """Phase 2: Run Content Engine from pre-computed GA results.

    Validates the GA analysis.json exists, cleans up GA-phase state
    (cards graduate to real CE briefs), runs CE in TOPIC_DISCOVERY mode,
    and updates assignment status to content_produced.
    """
    from core.content_engine.pipeline_v13 import run_content_generation_v13
    from core.redis import get_redis_or_none as _get_async_redis

    pipeline_start = time.monotonic()

    # Acquire async Redis client for CE pipeline state writes.
    # Without this, CE writes to file only and get_briefs() falls back to
    # stale pipeline_state.json — root cause of 4-min kanban sync lag.
    _redis_async = _get_async_redis()

    if session_factory is None:
        raise TDContentPipelineError("session_factory is required for TD→Content production")

    logger.info(
        "TD→Content production (Phase 2): slug=%s, %d topics, ga_run_id=%s",
        effective_slug, len(topic_assignment_ids), ga_run_id,
    )

    # Step 1: Validate analysis.json exists
    from core.storage import get_storage_backend
    storage = get_storage_backend()
    analysis_key = f"gap_analysis/{effective_slug}/topic_scoped/{ga_run_id}/analysis.json"
    if not storage.exists(analysis_key):
        raise TDContentPipelineError(
            f"analysis.json not found at {analysis_key}. "
            f"GA run {ga_run_id} may not have completed successfully."
        )

    # Step 2a: Transition GA-phase cards → briefing (prevents snap-back on next poll)
    _update_ga_phase_status(effective_slug, topic_assignment_ids, "briefing", task_id=task_id)
    await _update_assignment_statuses_db(
        session_factory, topic_assignment_ids, TopicAssignmentStatus.in_content_production,
    )
    _emit_company_event(effective_slug, "state_changed", {
        "changed": topic_assignment_ids, "hint": "briefing",
    })

    # Step 2b: Build CE input and run (GA cards stay visible until CE succeeds)
    company_context_path = f"artifacts/company_context/{effective_slug}.md"
    persona_storage = PersonaStorage(
        artifacts_root=_PROJECT_ROOT / "artifacts", slug=effective_slug
    )
    persona_paths = persona_storage.list_persona_paths()

    ce_input = ContentGenerationInputV13(
        company_name=company_name,
        domain=domain,
        company_slug=effective_slug,
        company_context_path=company_context_path,
        persona_paths=persona_paths,
        entry_mode=EntryMode.TOPIC_DISCOVERY,
        topic_assignment_ids=topic_assignment_ids,
        td_effective_slug=effective_slug,
        td_ga_run_id=ga_run_id,
        auto_approve=auto_approve,
        product_slug=product_slug,
        product_name=product_name,
        product_description=product_description,
        analysis_json_path=str(
            _PROJECT_ROOT / "artifacts" / "gap_analysis" / effective_slug
            / "topic_scoped" / ga_run_id / "analysis.json"
        ),
    )

    try:
        output = await run_content_generation_v13(
            ce_input,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            session_factory=session_factory,
            run_id=run_id,
            company_id=company_id,
            redis_client=_redis_async,
        )
    except Exception:
        # CE failed — rollback: revert Redis GA-phase cards and DB status
        # so the card returns to gap_analysis_complete (retryable).
        logger.exception(
            "Phase 2 CE failed — reverting %d assignments to gap_analysis_complete",
            len(topic_assignment_ids),
        )
        _update_ga_phase_status(
            effective_slug, topic_assignment_ids, "gap_analysis_complete", task_id=task_id,
        )
        await _update_assignment_statuses_db(
            session_factory, topic_assignment_ids, TopicAssignmentStatus.gap_analysis_complete,
        )
        _emit_company_event(effective_slug, "state_changed", {
            "changed": topic_assignment_ids, "hint": "gap_analysis_complete",
        })
        raise

    if len(output.pieces) > 0:
        # Step 3: CE succeeded — clean up GA-phase cards (graduate to real briefs)
        _cleanup_ga_phase_redis(effective_slug, topic_assignment_ids)

        # Step 4: Update assignment status → content_produced
        await _update_assignment_statuses_db(
            session_factory, topic_assignment_ids, TopicAssignmentStatus.content_produced,
        )
    else:
        # Pipeline ran but produced nothing — revert to gap_analysis_complete
        # so the card remains visible and the user can retry.
        logger.warning(
            "Phase 2 produced zero pieces — reverting %d assignments to gap_analysis_complete",
            len(topic_assignment_ids),
        )
        _update_ga_phase_status(
            effective_slug, topic_assignment_ids, "gap_analysis_complete", task_id=task_id,
        )
        await _update_assignment_statuses_db(
            session_factory, topic_assignment_ids, TopicAssignmentStatus.gap_analysis_complete,
        )

    total_elapsed = time.monotonic() - pipeline_start
    logger.info(
        "TD→Content production (Phase 2) completed: %d pieces, %.1fs",
        len(output.pieces), total_elapsed,
    )

    return output


# ---------------------------------------------------------------------------
# Redis GA-phase state helpers (orchestrator-internal)
# ---------------------------------------------------------------------------


def _write_ga_phase_redis(
    slug: str,
    assignments: List[TopicAssignment],
    phase: str,
    *,
    task_id: Optional[str] = None,
    ga_run_id: Optional[str] = None,
) -> None:
    """Write GA-phase state for topic assignment cards to Redis.

    Best-effort — Redis errors are logged but don't fail the pipeline.
    """
    try:
        from core.redis import get_sync_redis_or_none
        from core.content_engine.state_redis import write_ga_phase_state

        rc = get_sync_redis_or_none()
        if rc is None:
            return

        topic_data = {}
        for a in assignments:
            meta = a.metadata or {}
            factors = a.priority_factors or {}
            topic_data[a.id] = {
                "title": a.topic_text[:200] if a.topic_text else "",
                "cluster": getattr(a, "subdomain_name", "") or "",
                "priority_score": getattr(a, "priority_score", 0.0),
                "buyer_stage": a.buyer_stage.value if a.buyer_stage else None,
                "ga_run_id": ga_run_id,
                # Enriched fields for Content Studio sidebar
                "intent_type": a.intent_type.value if a.intent_type else None,
                "persona_name": getattr(a, "persona_name", "") or "",
                "persona_id": getattr(a, "persona_id", "") or "",
                "persona_affinity": getattr(a, "persona_affinity", {}),
                "priority_factors": factors,
                "content_format": meta.get("content_format"),
                "estimated_word_count": meta.get("estimated_word_count"),
                "citation_opportunity": factors.get("citation_opportunity", a.priority_score),
                "description": meta.get("description", ""),
                "target_keywords": meta.get("target_keywords"),
                "content_angle": meta.get("angle"),
            }

        write_ga_phase_state(
            rc, slug,
            [a.id for a in assignments],
            phase,
            task_id=task_id,
            topic_data=topic_data,
        )
    except Exception:
        logger.warning(
            "Failed to write GA-phase state for %s (phase=%s)", slug, phase,
            exc_info=True,
        )


def _emit_company_event(
    effective_slug: str,
    event_type: str,
    data: dict,
) -> None:
    """Broadcast a company-wide SSE event. Best-effort."""
    try:
        from core.events.company_event_bus import company_event_bus, CompanyEvent
        company_slug = effective_slug.split("__")[0]
        company_event_bus.emit(company_slug, CompanyEvent(event_type=event_type, data=data))
    except Exception:
        logger.debug("Company event emit failed for %s", effective_slug, exc_info=True)


def _update_ga_phase_status(
    slug: str,
    assignment_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
) -> None:
    """Update GA-phase card status in Redis without full TopicAssignment objects.

    Lightweight variant of ``_write_ga_phase_redis`` — only updates the status
    field (and optionally task_id) for existing entries.  Best-effort.
    """
    try:
        from core.redis import get_sync_redis_or_none
        from core.content_engine.state_redis import write_ga_phase_state

        rc = get_sync_redis_or_none()
        if rc is None:
            return
        write_ga_phase_state(rc, slug, assignment_ids, phase, task_id=task_id)
    except Exception:
        logger.warning(
            "Failed to update GA-phase status for %s (phase=%s)", slug, phase,
            exc_info=True,
        )


def _cleanup_ga_phase_redis(slug: str, assignment_ids: List[str]) -> None:
    """Remove GA-phase state entries (graduation to CE). Best-effort."""
    try:
        from core.redis import get_sync_redis_or_none
        from core.content_engine.state_redis import cleanup_ga_phase_state

        rc = get_sync_redis_or_none()
        if rc is None:
            return
        cleanup_ga_phase_state(rc, slug, assignment_ids)
    except Exception:
        logger.warning(
            "Failed to cleanup GA-phase state for %s", slug, exc_info=True,
        )
