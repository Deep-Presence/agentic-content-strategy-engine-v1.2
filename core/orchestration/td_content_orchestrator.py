"""End-to-end orchestrator: Topic Discovery → Gap Analysis → Content Engine.

Chains approved TopicAssignments from TD Pipeline B through a topic-scoped
GA run and into the Content Engine in TOPIC_DISCOVERY mode.

Usage:
    output = await run_td_to_content_pipeline(
        effective_slug="ramp",
        topic_assignment_ids=["ta-1", "ta-2", "ta-3"],
        company_name="Ramp",
        domain="ramp.com",
    )
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from core.gap_analysis.pipeline import run_topic_scoped_gap_analysis
from core.gap_analysis.topic_cluster_map import is_excluded_combo
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

    # Step 2: Load assignments, filter excluded combos
    requested_ids = set(topic_assignment_ids)
    all_assignments = [a for a in matrix.assignments if a.id in requested_ids]

    valid_assignments: List[TopicAssignment] = []
    for a in all_assignments:
        if is_excluded_combo(a.buyer_stage.value, a.intent_type.value):
            logger.warning(
                "Skipping excluded combo %s × %s for topic '%s' (id=%s)",
                a.buyer_stage.value, a.intent_type.value,
                a.topic_text[:50], a.id,
            )
            continue
        valid_assignments.append(a)

    if not valid_assignments:
        logger.warning("No valid assignments after filtering. Returning empty output.")
        return ContentGenerationOutput(
            company_slug=effective_slug,
            run_metadata={"error": "No valid topic assignments after filtering excluded combos"},
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
    )

    # Step 5: Update assignment status → content_produced (DB)
    await _update_assignment_statuses_db(
        session_factory, valid_ids, TopicAssignmentStatus.content_produced,
    )

    total_elapsed = time.monotonic() - pipeline_start
    logger.info(
        "TD→Content orchestrator completed: %d pieces, %.1fs total",
        len(output.pieces), total_elapsed,
    )

    return output
