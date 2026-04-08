"""Content Generation Pipeline v1.3 — 6-stage async orchestrator.

Supports two entry modes:
  AUTONOMOUS: Gap Analysis → Planner → HITL-1 → Brief Builder → HITL-2
              → Workers → Evaluator → HITL-3 → Publish
  MANUAL:     User Prompt → Brief Builder → HITL-2 → Workers → Evaluator → HITL-3 → Publish
              (Skips Stage 1 + HITL-1. Lightweight gap s3-s6 deferred: PB-45)

Key differences from v1.0 (pipeline.py):
  - Two-phase context loading (scorecard → full context)
  - New Brief Builder agent (Agent 2)
  - Three HITL checkpoints (up from 1)
  - Dual feedback loops (section-level vs major direction change)
  - All LLM calls via LiteLLM
  - LangSmith tracing (replaces Langfuse)

The v1.0 pipeline is preserved alongside this module.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from core.shared_tools.structured_logging import bind_context, scoped_bind
from core.shared_tools.task_status import TaskStatus
from core.config.settings import settings
from core.content_engine.brief_builder import build_briefs_parallel
from core.content_engine.context_router import extract_scorecard, extract_worker_context
from core.content_engine.graph_v13 import (
    build_brief_approval_graph,
    build_content_review_graph,
    build_topic_approval_graph,
    run_hitl_checkpoint,
)
from core.content_engine.llm_client import configure_openrouter
from core.content_engine.state_helpers import (
    _cleanup_pipeline_state,
    _cleanup_pipeline_state_async,
    _emit,
    _emit_company,
    _write_pipeline_state,
    _write_pipeline_state_async,
)
from core.content_engine.persistence import (
    persist_blueprints_early,
    persist_content_pieces,
    persist_content_run_summary,
    persist_v13_brief_approval,
    persist_v13_planner_output,
)
from core.content_engine.strategic_planner import select_topics
from core.content_engine.tracing_v13 import (
    create_pipeline_trace,
    create_session,
    create_span,
    end_span,
    flush,
    set_current_span,
    update_trace_output,
)
from core.models.content_generation import (
    ContentGenerationOutput,
    ContentPiece,
    ContentStatus,
    FormattedContent,
    RevisionHistory,
)
from core.models.content_generation_v13 import (
    ContentBlueprint,
    ContentGenerationInputV13,
    EntryMode,
    StrategicPlannerOutput,
    TopicSelection,
    WorkerQueryContext,
)

logger = logging.getLogger(__name__)

# Lazy guard: CPS scorer may not be importable if torch is absent
try:
    from core.cps_model.scorer import get_cps_scorer
except Exception:  # pragma: no cover
    def get_cps_scorer():  # type: ignore[misc]
        return None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_STAGE_NAMES_V13: Dict[int, str] = {
    0: "Entry Router",
    1: "Strategic Planner",
    2: "Brief Builder",
    3: "Content Workers",
    4: "Evaluator",
    5: "Final Review",
}


# ── Artifact helpers ──────────────────────────────────────────────────


def _load_artifact_text(path: Optional[str], *, storage: Optional[Any] = None) -> str:
    """Load a text artifact via StorageBackend (preferred) or filesystem fallback."""
    if not path:
        return ""
    # CX-1 fix: try StorageBackend for relative storage keys (R2 or local)
    # Absolute paths are already filesystem paths — skip storage for those.
    if storage is not None and not Path(path).is_absolute():
        content = storage.read(path)
        if content is not None:
            return content
    # Filesystem fallback (absolute paths, local dev, or storage miss)
    p = Path(path) if Path(path).is_absolute() else _PROJECT_ROOT / path.lstrip("/")
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _load_artifact_json(path: Optional[str], *, storage: Optional[Any] = None) -> Dict[str, Any]:
    """Load a JSON artifact via StorageBackend (preferred) or filesystem fallback."""
    if not path:
        return {}
    # CX-1 fix: try StorageBackend for relative storage keys (R2 or local)
    # Absolute paths are already filesystem paths — skip storage for those.
    if storage is not None and not Path(path).is_absolute():
        content = storage.read(path)
        if content is not None:
            try:
                return json.loads(content)
            except (json.JSONDecodeError, ValueError):
                return {}
    # Filesystem fallback (absolute paths, local dev, or storage miss)
    p = Path(path) if Path(path).is_absolute() else _PROJECT_ROOT / path.lstrip("/")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _merge_and_write_blueprints(
    bp_path: Path,
    pipeline_blueprints: list,
    *,
    storage: Optional[Any] = None,
    storage_key: str = "",
) -> None:
    """Write pipeline blueprints via StorageBackend, preserving externally-added entries.

    Entries with a ``_source`` field (e.g. "manual", "citation") were created
    via the ``add_brief()`` API and must survive pipeline writes. Pipeline-
    generated blueprints do not carry ``_source``.

    Strategy: load existing → partition by ``_source`` → replace pipeline
    entries with the new set → keep sourced entries intact.
    """
    existing: list[dict] = []
    # Read existing blueprints via StorageBackend (preferred) or filesystem fallback
    raw_content: Optional[str] = None
    if storage and storage_key:
        raw_content = storage.read(storage_key)
    elif bp_path.is_file():
        try:
            raw_content = bp_path.read_text(encoding="utf-8")
        except OSError:
            pass
    if raw_content is not None:
        try:
            raw = json.loads(raw_content)
            if isinstance(raw, list):
                existing = raw
        except (json.JSONDecodeError, ValueError):
            pass

    # Preserve entries that have a _source field (non-pipeline)
    preserved = [e for e in existing if e.get("_source")]

    new_entries = [bp.model_dump(mode="json") for bp in pipeline_blueprints]
    merged = new_entries + preserved
    content = json.dumps(merged, indent=2)
    if storage and storage_key:
        storage.write(storage_key, content)
    else:
        bp_path.write_text(content, encoding="utf-8")


def _resolve_slug(input_data: ContentGenerationInputV13) -> str:
    """Resolve the effective slug for artifact paths."""
    if input_data.company_slug:
        return input_data.company_slug
    return input_data.company_name.lower().replace(" ", "-").replace("_", "-")


def _ensure_artifact_dir(slug: str) -> Path:
    """Ensure artifact directory exists and return it."""
    artifact_dir = _PROJECT_ROOT / "artifacts" / "content" / slug
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _brief_dir(artifact_dir: Path, brief_id: str) -> Path:
    """Return the per-brief artifact directory.

    Raises ValueError if brief_id contains path-unsafe characters.
    """
    if not brief_id or "/" in brief_id or "\\" in brief_id or ".." in brief_id or "\x00" in brief_id:
        raise ValueError(f"unsafe brief_id for directory creation: {brief_id!r}")
    d = artifact_dir / "content" / brief_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _extract_site_pages(analysis_json: Dict[str, Any]) -> List[str]:
    """Extract discovered site page URLs from the gap analysis data.

    Pulls URLs from the s1 discovery output within analysis.json.
    These are used by the linker for internal link resolution.

    Args:
        analysis_json: Full analysis JSON from gap analysis pipeline.

    Returns:
        List of discovered site page URLs, or empty list if unavailable.
    """
    if not analysis_json:
        return []

    # Try s1_discovery.pages or semantic_units
    s1_data = analysis_json.get("s1_discovery", {})
    if isinstance(s1_data, dict):
        # Check for pages list
        pages = s1_data.get("pages", [])
        if pages:
            return [p.get("url", "") for p in pages if p.get("url")]

        # Check for semantic units with URLs
        units = s1_data.get("semantic_units", [])
        if units:
            urls = list({u.get("url", "") for u in units if u.get("url")})
            return urls

    # Try top-level discovered_urls
    discovered = analysis_json.get("discovered_urls", [])
    if discovered:
        return discovered[:200]

    return []


# ── Event helpers ─────────────────────────────────────────────────────


# _emit, _write_pipeline_state, _cleanup_pipeline_state are imported from
# core.content_engine.state_helpers (see imports above).


_TOTAL_STAGES_V13: int = 5  # stages 0-5; pct = stage / _TOTAL_STAGES_V13 * 100


def _update_task(task_store: Any, task_id: Optional[str], **kwargs: Any) -> None:
    """Update task store if available.

    Translates progress={"stage": N, "stage_name": "..."} into
    current_step and progress_pct fields recognised by PipelineTask.
    setdefault ensures explicit current_step= / progress_pct= kwargs take priority.
    """
    if task_store and task_id:
        progress = kwargs.pop("progress", None)
        if isinstance(progress, dict):
            stage = progress.get("stage")
            stage_name = progress.get("stage_name", "")
            if stage is not None:
                kwargs.setdefault(
                    "current_step",
                    stage_name.lower().replace(" ", "_"),
                )
                kwargs.setdefault(
                    "progress_pct",
                    round(stage / _TOTAL_STAGES_V13 * 100, 1),
                )
        task_store.update_task(task_id, **kwargs)






# ── CPS Scoring Helper ────────────────────────────────────────────────


async def _score_cps_batch(
    evaluated: List[tuple],
    blueprint_by_id: Dict[str, Any],
    domain: str,
    parent_span: Any,
    event_bus: Any,
    task_id: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    """Score all evaluated content pieces with the CPS model.

    Returns a dict mapping brief_id -> cps_result dict.
    Gracefully returns empty dict on any failure.
    """
    import asyncio

    scorer = get_cps_scorer()
    if scorer is None:
        logger.info("CPS scoring skipped: scorer unavailable")
        return {}

    cps_span = create_span(parent_span, "cps-scoring") if parent_span else None
    cps_results: Dict[str, Dict[str, Any]] = {}
    content_url = f"https://{domain}"

    async def _score_one(brief_id: str, content: FormattedContent) -> tuple:
        blueprint = blueprint_by_id.get(brief_id)
        query_texts: List[str] = []
        if blueprint and hasattr(blueprint, "target_queries") and blueprint.target_queries:
            query_texts = [
                tq.query_text for tq in blueprint.target_queries if tq.query_text
            ]
        if not query_texts:
            query_texts = [content.title]

        try:
            result = await scorer.score_async(
                query_texts=query_texts,
                content_markdown=content.markdown,
                content_url=content_url,
            )
            return brief_id, result
        except Exception:
            logger.warning("CPS scoring failed for %s", brief_id, exc_info=True)
            return brief_id, None

    tasks = [
        _score_one(brief_id, final_content)
        for brief_id, final_content, _history, _feedback_route in evaluated
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for item in results:
        if isinstance(item, Exception):
            continue
        brief_id, result = item
        if result is not None:
            cps_results[brief_id] = result

    if cps_span:
        end_span(cps_span, output={
            "scored_count": len(cps_results),
            "total_count": len(evaluated),
        })

    _emit(event_bus, task_id, "cps_scoring_complete", {
        "scored": len(cps_results),
        "scores": {bid: data.get("cps_score") for bid, data in cps_results.items()},
    })

    return cps_results


# ── HITL-3 Feedback Loop Helpers ──────────────────────────────────────


async def _apply_human_edits(
    final_content: FormattedContent,
    blueprint: Optional["ContentBlueprint"],
    editor_notes: str,
    style_guide_md: str,
    company_context_md: str,
    company_name: str,
    domain: str,
    company_slug: str = "",
) -> Optional[FormattedContent]:
    """Apply human edits by routing to drafter + fact checker.

    Args:
        final_content: Current content to revise.
        blueprint: Content brief/blueprint for context.
        editor_notes: Human reviewer's notes/feedback.
        style_guide_md: Style guide markdown.
        company_context_md: Company context markdown.
        company_name: Company name for fact checking.
        domain: Company domain for fact checking.

    Returns:
        Revised FormattedContent, or None if revision fails.
    """
    if not blueprint:
        return None

    try:
        from core.content_engine.workers.drafter import revise_draft
        from core.content_engine.workers.fact_enricher import enrich_with_facts
        from core.content_engine.workers.formatter import _count_structural_elements
        from core.models.content_generation import ContentDraft

        revised_draft = await revise_draft(
            current_markdown=final_content.markdown,
            brief=blueprint,
            feedback=f"[HUMAN REVIEW]\n{editor_notes}",
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            company_slug=company_slug,
        )

        # Re-run fact checker on revised content
        fact_check_input = ContentDraft(
            brief_id=revised_draft.brief_id,
            title=revised_draft.title,
            markdown=revised_draft.markdown,
            word_count=revised_draft.word_count,
        )
        checked = await enrich_with_facts(
            draft=fact_check_input,
            brief=blueprint,
            company_name=company_name,
            domain=domain,
            company_slug=company_slug,
        )

        # Compute structural counts inline
        counts = _count_structural_elements(checked.markdown)
        return FormattedContent(
            brief_id=checked.brief_id,
            title=checked.title,
            markdown=checked.markdown,
            word_count=len(checked.markdown.split()),
            **counts,
        )
    except Exception:
        logger.exception("Failed to apply human edits for %s", final_content.brief_id)
        return None


async def _rebrief_and_rerun(
    blueprint: "ContentBlueprint",
    user_comment: str,
    input_data: "ContentGenerationInputV13",
    company_context_md: str,
    persona_mds: List[str],
    style_guide_md: str,
    analysis_json: Dict[str, Any],
    artifact_dir: Path,
    session_id: str,
    parent_span: Optional[object] = None,
    event_bus: Any = None,
    task_id: Optional[str] = None,
    redis_client: Optional[Any] = None,
    slug: Optional[str] = None,
) -> Optional[tuple]:
    """Re-brief a piece via Agent 2 and re-run the full worker+evaluator chain.

    Args:
        blueprint: Original blueprint to re-brief.
        user_comment: Human feedback or rejection reason.
        input_data: Pipeline configuration.
        company_context_md: Company context markdown.
        persona_mds: Persona markdowns.
        style_guide_md: Style guide markdown.
        analysis_json: Gap analysis JSON.
        artifact_dir: Artifact directory.
        session_id: Tracing session ID.
        parent_span: Optional parent span for tracing.

    Returns:
        Tuple of (FormattedContent, RevisionHistory, FeedbackRoute), or None on failure.
    """
    try:
        _slug = getattr(input_data, "company_slug", "") or ""

        # Extract worker contexts from the blueprint's gap_context.
        # gap_context is a WorkerQueryContext Pydantic model — use attribute access,
        # NOT .get() or isinstance(dict) which is always False on a Pydantic model.
        worker_contexts: Dict[str, WorkerQueryContext] = {}
        if blueprint.gap_context:
            qid = blueprint.gap_context.query_gap.get("query_id", f"rebrief-{blueprint.brief_id}")
            worker_contexts[qid] = blueprint.gap_context
        if not worker_contexts:
            # Fallback: create minimal context from blueprint
            fallback_qid = f"rebrief-{blueprint.brief_id}"
            worker_contexts[fallback_qid] = WorkerQueryContext(
                query_gap={
                    "query_id": fallback_qid,
                    "query_text": blueprint.title,
                },
            )

        # Re-brief via Agent 2 with user feedback
        rebrief_topic = TopicSelection(
            rank=0,
            query_ids=list(worker_contexts.keys()),
            query_texts=[blueprint.title],
            cluster_name=getattr(blueprint, "cluster_name", "rebrief"),
            rationale=f"Re-brief after rejection: {user_comment[:200]}",
        )

        rebrief_id = f"rebrief-{uuid.uuid4().hex[:8]}"
        new_blueprints = await build_briefs_parallel(
            contexts=worker_contexts,
            topics=[rebrief_topic],
            company_context_md=company_context_md,
            persona_mds=persona_mds,
            style_guide_md=style_guide_md,
            max_concurrent=1,
            parent_span=parent_span,
            brief_id_overrides=[rebrief_id],
            company_slug=_slug,
        )
        new_blueprints = [bp for bp in new_blueprints if bp is not None]

        if not new_blueprints:
            logger.warning("Re-brief produced no blueprints for %s", blueprint.brief_id)
            return None

        new_blueprint = new_blueprints[0]

        # Re-run workers
        site_pages = _extract_site_pages(analysis_json)
        from core.content_engine.workers.dispatcher import dispatch_workers_v13

        formatted_list, _rebrief_failures = await dispatch_workers_v13(
            briefs=[new_blueprint],
            input_data=input_data,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            max_concurrent=1,
            artifact_dir=artifact_dir,
            site_pages=site_pages,
            parent_span=parent_span,
            event_bus=event_bus,
            task_id=task_id,
            redis_client=redis_client,
            effective_slug=slug,
        )

        if not formatted_list:
            logger.warning("Re-run workers produced no content for %s", blueprint.brief_id)
            return None

        # Re-evaluate — dispatcher now returns (brief_id, FormattedContent) tuples
        _rebrief_brief_id, fc = formatted_list[0]
        from core.content_engine.evaluator.loop import evaluate_and_optimize

        final_content, history, feedback_route = await evaluate_and_optimize(
            content=fc,
            brief=new_blueprint,
            company_context_md=company_context_md,
            style_guide_md=style_guide_md,
            input_data=input_data,
            max_cycles=input_data.max_revision_cycles,
            session_id=session_id,
            artifact_dir=artifact_dir,
            parent_span=parent_span,
            use_eeat=True,
            use_targeted_revision=True,
            event_bus=event_bus,
            task_id=task_id,
            redis_client=redis_client,
            effective_slug=slug,
        )

        return (final_content, history, feedback_route)

    except Exception:
        logger.exception("Re-brief and re-run failed for %s", blueprint.brief_id)
        return None


# ── Centralized finalization ──────────────────────────────────────────


async def _finalize_pipeline(
    *,
    output: ContentGenerationOutput,
    pipeline_trace: Any,
    slug: str,
    approved_blueprints: List[Any],
    pieces: List[ContentPiece],
    start_time: float,
    input_data: ContentGenerationInputV13,
    artifact_dir: Path,
    session_factory: Optional[Any],
    run_id: Optional[uuid.UUID],
    company_id: Optional[uuid.UUID],
    task_store: Optional[Any],
    task_id: Optional[str],
    event_bus: Optional[Any],
    redis_client: Optional[Any] = None,
    storage: Optional[Any] = None,
) -> None:
    """Single finalization path — all pipeline exits MUST call this.

    Handles:
      1. Save run_metadata_v13.json artifact
      2. Persist content pieces to DB
      3. Persist run summary to DB
      4. Update trace output + flush
      5. Mark task as completed
      6. Emit pipeline_complete SSE event
    """
    _company_slug = slug.split("__")[0]  # company slug for company-wide SSE

    # 1. Save run metadata
    # For manual mode parallel runs, namespace by first brief_id to avoid
    # overwriting metadata from concurrent pipelines.
    entry_mode = output.run_metadata.get("entry_mode", "autonomous") if output.run_metadata else "autonomous"
    if entry_mode == "manual" and pieces:
        first_brief = pieces[0].brief_id
        meta_filename = f"run_metadata_v13_{first_brief}.json"
    else:
        meta_filename = "run_metadata_v13.json"
    meta_content = output.model_dump_json(indent=2)
    meta_key = f"content/{slug}/{meta_filename}"
    if storage:
        storage.write(meta_key, meta_content)
    else:
        meta_path = artifact_dir / meta_filename
        meta_path.write_text(meta_content, encoding="utf-8")

    # 2-3. Persist to DB BEFORE pipeline_state cleanup.
    # This eliminates the window where neither pipeline_state nor DB has the
    # brief's status (which causes a Triage flash in the frontend).
    await persist_content_pieces(
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
        slug=slug,
        pieces=pieces,
    )
    await persist_content_run_summary(
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
        slug=slug,
        total_briefs=len(approved_blueprints),
        total_approved=sum(1 for p in pieces if p.status == ContentStatus.APPROVED),
        total_rejected=sum(1 for p in pieces if p.status == ContentStatus.REJECTED),
    )

    # Clean up this run's brief IDs from pipeline_state.json.
    # Per-brief removal is concurrency-safe: parallel manual runs retain their entries.
    # Runs AFTER DB persist so the DB fallback is ready before pipeline_state is removed.
    await _cleanup_pipeline_state_async(artifact_dir, [p.brief_id for p in pieces], redis_client=redis_client, effective_slug=slug)

    # Invalidate content cache so next dashboard request gets fresh data
    from core.cache import cache_delete_pattern
    from core.redis import get_sync_redis_or_none

    _cache_redis = get_sync_redis_or_none()
    if _cache_redis:
        cache_delete_pattern(_cache_redis, f"cache:content:{slug}:*")

    # 4. Update trace and flush
    # update_trace_output ends the trace internally — no end_span needed
    update_trace_output(pipeline_trace, output=output.model_dump(mode="json"))
    flush()

    # 5-6. Task store + SSE
    total_approved = sum(1 for p in pieces if p.status == ContentStatus.APPROVED)
    total_rejected = sum(1 for p in pieces if p.status == ContentStatus.REJECTED)

    _update_task(task_store, task_id, status=TaskStatus.COMPLETED.value, progress={"stage": 5, "stage_name": "Complete"})
    _emit(event_bus, task_id, "pipeline_complete", {
        "total_briefs": len(approved_blueprints),
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "duration": round(time.time() - start_time, 1),
    })
    _emit_company(_company_slug, "state_changed", {"changed": [], "hint": "pipeline_complete"})

    logger.info(
        "v1.3 pipeline complete: %d briefs, %d approved, %d rejected, %.1fs",
        len(approved_blueprints),
        total_approved,
        total_rejected,
        time.time() - start_time,
    )


# ═══════════════════════════════════════════════════════════════════════
# Main Pipeline Entry Point
# ═══════════════════════════════════════════════════════════════════════


async def run_content_generation_v13(
    input_data: ContentGenerationInputV13,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    session_factory: Optional[async_sessionmaker] = None,
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
    redis_client: Optional[Any] = None,
) -> ContentGenerationOutput:
    """Run the v1.3 content generation pipeline.

    6-stage flow:
      Stage 0: Entry routing + artifact loading
      Stage 1: Strategic Planner + HITL-1 (autonomous only)
      Stage 2: Brief Builder + HITL-2
      Stage 3: Content Workers
      Stage 4: Evaluator with dual feedback loops
      Stage 5: Final HITL Review + publish

    Args:
        input_data: Pipeline configuration.
        task_id: Task identifier for SSE events.
        task_store: Task store for HITL approval flow.
        event_bus: Event bus for SSE streaming.
        session_factory: Optional DB session factory.
        run_id: Optional pipeline run ID.
        company_id: Optional company ID.

    Returns:
        ContentGenerationOutput with approved content pieces.
    """
    start_time = time.time()

    # Configure OpenRouter client
    configure_openrouter()

    slug = _resolve_slug(input_data)
    _company_slug = slug.split("__")[0]  # company slug for company-wide SSE
    artifact_dir = _ensure_artifact_dir(slug)

    # Start tracing
    session_id = create_session(slug)
    pipeline_trace = create_pipeline_trace(
        session_id=session_id,
        company_slug=slug,
        company_name=input_data.company_name,
        metadata={"entry_mode": input_data.entry_mode.value},
    )

    logger.info(
        "Starting v1.3 pipeline: slug=%s, entry_mode=%s",
        slug,
        input_data.entry_mode.value,
    )
    _emit(event_bus, task_id, "pipeline_started", {
        "slug": slug,
        "entry_mode": input_data.entry_mode.value,
    })

    # Wrap all stages in try/except so unhandled exceptions still finalize
    # the trace and mark the task as failed (Codex finding).
    approved_blueprints: List[Any] = []
    pieces: List[ContentPiece] = []
    try:
        return await _run_pipeline_stages(
            input_data=input_data,
            slug=slug,
            artifact_dir=artifact_dir,
            session_id=session_id,
            pipeline_trace=pipeline_trace,
            start_time=start_time,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            session_factory=session_factory,
            run_id=run_id,
            company_id=company_id,
            redis_client=redis_client,
        )
    except Exception as exc:
        error_msg = str(exc)[:500]
        logger.exception("v1.3 pipeline failed with unhandled exception: %s", error_msg)
        end_span(pipeline_trace, error=error_msg)
        flush()
        _update_task(task_store, task_id, status=TaskStatus.FAILED.value, error=error_msg)
        _emit(event_bus, task_id, "pipeline_error", {"error": error_msg})
        _emit_company(_company_slug, "notification", {
            "type": "pipeline_error",
            "brief_id": "",
            "title": slug,
            "message": f"Content pipeline failed: {error_msg[:200]}",
        })
        raise


async def _run_pipeline_stages(
    input_data: ContentGenerationInputV13,
    *,
    slug: str,
    artifact_dir: Path,
    session_id: str,
    pipeline_trace: Any,
    start_time: float,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
    redis_client: Optional[Any] = None,
) -> ContentGenerationOutput:
    """Internal stage execution — called by run_content_generation_v13 inside try/except."""

    _company_slug = slug.split("__")[0]  # company slug for company-wide SSE

    # Initialize StorageBackend early — needed for Stage 0 artifact loading (CX-1 fix)
    from core.storage import get_storage_backend as _get_storage_backend
    storage = _get_storage_backend(_PROJECT_ROOT / "artifacts") if artifact_dir else None

    # ── Stage 0: Entry Routing + Artifact Loading ──────────────────
    with scoped_bind(step_name="stage_0_entry_router"):
        stage0_span = create_span(pipeline_trace, "stage/0-entry-router")
        _update_task(task_store, task_id, status=TaskStatus.RUNNING.value, progress={"stage": 0, "stage_name": "Entry Router"})

        company_context_md = _load_artifact_text(input_data.company_context_path, storage=storage)
        style_guide_md = _load_artifact_text(input_data.style_guide_path, storage=storage)
        persona_mds = [_load_artifact_text(p, storage=storage) for p in input_data.persona_paths]
        analysis_json = _load_artifact_json(input_data.analysis_json_path, storage=storage)

        end_span(stage0_span, output={"entry_mode": input_data.entry_mode.value})

    # H7-fix: track actually-executed stages (not derived from skip_stages)
    stages_actually_executed: set[int] = {0}  # Stage 0 (Entry Router) always executes

    approved_blueprints: List[ContentBlueprint] = []

    if input_data.entry_mode == EntryMode.AUTONOMOUS:
        # ── Stage 1: Strategic Planner + HITL-1 ───────────────────
        if 1 not in input_data.skip_stages:
            bind_context(step_name="stage_1_strategic_planner")
            stage1_span = create_span(pipeline_trace, "stage/1-strategic-planner")
            _update_task(task_store, task_id, progress={"stage": 1, "stage_name": "Strategic Planner"})
            _emit(event_bus, task_id, "stage_started", {"stage": 1, "name": "Strategic Planner"})
            stages_actually_executed.add(1)

            # Phase 1: Extract scorecard (~11K tokens)
            product_focus = None
            if input_data.product_name:
                product_focus = f"{input_data.product_name}: {input_data.product_description or ''}"

            scorecard = extract_scorecard(
                analysis_json=analysis_json,
                company_context_md=company_context_md,
                product_focus=product_focus,
            )

            # Run Strategic Planner
            planner_output = await select_topics(
                scorecard=scorecard,
                max_topics=input_data.max_topics,
                parent_span=stage1_span,
                company_slug=slug,
            )

            # Save planner output
            planner_key = f"content/{slug}/planner_selections.json"
            if storage:
                storage.write(planner_key, planner_output.model_dump_json(indent=2))
            else:
                planner_path = artifact_dir / "planner_selections.json"
                planner_path.write_text(
                    planner_output.model_dump_json(indent=2), encoding="utf-8"
                )

            # HITL Checkpoint 1: Topic Approval
            set_current_span(stage1_span)
            topic_graph = build_topic_approval_graph()
            topic_state = await run_hitl_checkpoint(
                graph=topic_graph,
                initial_state={
                    "planner_selections": [s.model_dump() for s in planner_output.selections],
                    "selection_metadata": planner_output.selection_metadata,
                    "auto_approve": input_data.auto_approve,
                },
                thread_id=f"{task_id or 'cli'}-topic-approval",
                task_store=task_store,
                event_bus=event_bus,
                task_id=task_id,
                stage_name="Topic Approval",
            )

            # Handle topic decision — support bounded retry loop
            topic_decision = topic_state.get("topic_decision", "approve")
            _MAX_TOPIC_RETRIES = 2
            topic_retry_count = 0

            while topic_decision == "retry" and topic_retry_count < _MAX_TOPIC_RETRIES:
                topic_retry_count += 1
                topic_feedback = topic_state.get("topic_feedback", "")
                logger.info(
                    "HITL-1 retry %d/%d: feedback=%r",
                    topic_retry_count, _MAX_TOPIC_RETRIES, topic_feedback[:100] if topic_feedback else "",
                )
                _emit(event_bus, task_id, "stage_started", {
                    "stage": 1,
                    "name": f"Strategic Planner (Retry {topic_retry_count})",
                })

                planner_output = await select_topics(
                    scorecard=scorecard,
                    max_topics=input_data.max_topics,
                    parent_span=stage1_span,
                    user_feedback=topic_feedback,
                    company_slug=slug,
                )
                if storage:
                    storage.write(planner_key, planner_output.model_dump_json(indent=2))
                else:
                    planner_path = artifact_dir / "planner_selections.json"
                    planner_path.write_text(planner_output.model_dump_json(indent=2), encoding="utf-8")

                set_current_span(stage1_span)
                topic_graph = build_topic_approval_graph()
                topic_state = await run_hitl_checkpoint(
                    graph=topic_graph,
                    initial_state={
                        "planner_selections": [s.model_dump() for s in planner_output.selections],
                        "selection_metadata": planner_output.selection_metadata,
                        "auto_approve": input_data.auto_approve,
                    },
                    thread_id=f"{task_id or 'cli'}-topic-approval-r{topic_retry_count}",
                    task_store=task_store,
                    event_bus=event_bus,
                    task_id=task_id,
                    stage_name=f"Topic Approval (Retry {topic_retry_count})",
                )
                topic_decision = topic_state.get("topic_decision", "approve")

            if topic_decision in ("reject", "rejected", "retry"):
                # C3 FIX: Topic rejection must still finalize (persist, trace, task update)
                logger.info("Topics rejected or retry exhausted (decision=%s) — finalizing", topic_decision)
                end_span(stage1_span, output={"decision": topic_decision})
                output = ContentGenerationOutput(
                    company_slug=slug,
                    run_metadata={
                        "pipeline_version": "1.3",
                        "entry_mode": input_data.entry_mode.value,
                        "exit_reason": f"topic_{topic_decision}",
                        "duration_seconds": round(time.time() - start_time, 1),
                        "stages_executed": sorted(stages_actually_executed),
                    },
                )
                await _finalize_pipeline(
                    output=output,
                    pipeline_trace=pipeline_trace,
                    slug=slug,
                    approved_blueprints=[],
                    pieces=[],
                    start_time=start_time,
                    input_data=input_data,
                    artifact_dir=artifact_dir,
                    session_factory=session_factory,
                    run_id=run_id,
                    company_id=company_id,
                    task_store=task_store,
                    task_id=task_id,
                    event_bus=event_bus,
                    redis_client=redis_client,
                    storage=storage,
                )
                return output

            # Determine approved topics
            approved_ranks = topic_state.get("approved_topic_ranks", list(range(len(planner_output.selections))))
            approved_topics = [
                planner_output.selections[r]
                for r in approved_ranks
                if 0 <= r < len(planner_output.selections)  # M1 defense-in-depth: lower bound
            ]

            end_span(stage1_span, output={"approved_topics": len(approved_topics)})
            _emit(event_bus, task_id, "stage_complete", {"stage": 1, "topics_approved": len(approved_topics)})

            # Persist planner output + HITL-1 decision
            await persist_v13_planner_output(
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
                slug=slug,
                planner_output=[s.model_dump(mode="json") for s in planner_output.selections],
                approval_decision=topic_decision,
                approved_topic_ranks=approved_ranks,
            )

            # Mark approved topics as "approved" for Kanban sync
            await _write_pipeline_state_async(
                artifact_dir,
                [f"brief-{r + 1:03d}" for r in approved_ranks],
                "approved",
                task_id=task_id,
                redis_client=redis_client,
                effective_slug=slug,
            )

        else:
            # Skip stage 1 — load from saved file
            _planner_raw: Optional[str] = None
            _planner_key = f"content/{slug}/planner_selections.json"
            if storage:
                _planner_raw = storage.read(_planner_key)
            else:
                _planner_fs = artifact_dir / "planner_selections.json"
                if _planner_fs.exists():
                    _planner_raw = _planner_fs.read_text(encoding="utf-8")
            if _planner_raw:
                planner_output = StrategicPlannerOutput.model_validate_json(_planner_raw)
                approved_topics = planner_output.selections
            else:
                logger.warning("Stage 1 skipped but no planner_selections.json found")
                approved_topics = []

        # ── Stage 2: Brief Builder + HITL-2 ───────────────────────
        if 2 not in input_data.skip_stages and approved_topics:
            bind_context(step_name="stage_2_brief_builder")
            stage2_span = create_span(pipeline_trace, "stage/2-brief-builder")
            _update_task(task_store, task_id, progress={"stage": 2, "stage_name": "Brief Builder"})
            _emit(event_bus, task_id, "stage_started", {"stage": 2, "name": "Brief Builder"})
            stages_actually_executed.add(2)

            # Phase 2: Extract full context for approved queries only
            all_query_ids = []
            for topic in approved_topics:
                all_query_ids.extend(topic.query_ids)

            worker_contexts = extract_worker_context(
                analysis_json=analysis_json,
                approved_query_ids=all_query_ids,
            )

            # Build blueprints in parallel
            blueprints = await build_briefs_parallel(
                contexts=worker_contexts,
                topics=approved_topics,
                company_context_md=company_context_md,
                persona_mds=persona_mds,
                style_guide_md=style_guide_md,
                max_concurrent=input_data.max_concurrent_workers,
                parent_span=stage2_span,
                company_slug=slug,
            )
            blueprints = [bp for bp in blueprints if bp is not None]

            # Save blueprints (C1-fix: merge to preserve manually-added entries)
            blueprints_path = artifact_dir / "blueprints.json"
            _merge_and_write_blueprints(
                blueprints_path, blueprints,
                storage=storage, storage_key=f"content/{slug}/blueprints.json",
            )

            # Mark blueprints as "brief_review" pending HITL-2
            # (Uses actual brief_ids from build_briefs_parallel, not predicted IDs)
            await _write_pipeline_state_async(
                artifact_dir,
                [bp.brief_id for bp in blueprints],
                "brief_review",
                task_id=task_id,
                redis_client=redis_client,
                effective_slug=slug,
            )

            # HITL Checkpoint 2: Brief Approval (per blueprint) with feedback loop
            _MAX_BRIEF_FEEDBACK_RETRIES = 1

            brief_decision_log: list[dict] = []  # all blueprints, all outcomes

            for bp in blueprints:
                brief_feedback_count = 0

                while True:
                    # Write pending state before HITL graph so polling sees it
                    await _write_pipeline_state_async(
                        artifact_dir, [bp.brief_id],
                        "pending_brief_approval",
                        task_id=task_id,
                        redis_client=redis_client,
                        effective_slug=slug,
                    )
                    _emit_company(_company_slug, "notification", {
                        "type": "hitl_review_needed",
                        "brief_id": bp.brief_id,
                        "title": bp.title,
                        "checkpoint": "brief_approval",
                        "message": f"'{bp.title}' needs your review",
                    })
                    _emit_company(_company_slug, "state_changed", {
                        "changed": [bp.brief_id], "hint": "pending_brief_approval",
                    })
                    set_current_span(stage2_span)
                    brief_graph = build_brief_approval_graph()
                    brief_state = await run_hitl_checkpoint(
                        graph=brief_graph,
                        initial_state={
                            "blueprint": bp.model_dump(mode="json"),
                            "auto_approve": input_data.auto_approve,
                        },
                        thread_id=f"{task_id or 'cli'}-brief-approval-{bp.brief_id}-f{brief_feedback_count}",
                        task_store=task_store,
                        event_bus=event_bus,
                        task_id=task_id,
                        stage_name=f"Brief Approval ({bp.brief_id})",
                    )

                    brief_decision = brief_state.get("brief_decision", "approve")
                    if brief_decision == "approve":
                        feedback = brief_state.get("brief_feedback", "")
                        if feedback:
                            bp.user_feedback = feedback
                        approved_blueprints.append(bp)
                        await _write_pipeline_state_async(artifact_dir, [bp.brief_id], "approved", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                        brief_decision_log.append({
                            "brief_id": bp.brief_id,
                            "decision": "approve",
                            "feedback": feedback,
                            "feedback_attempts": brief_feedback_count,
                        })
                        break
                    elif brief_decision == "feedback" and brief_feedback_count < _MAX_BRIEF_FEEDBACK_RETRIES:
                        brief_feedback_count += 1
                        feedback = brief_state.get("brief_feedback", "")
                        logger.info(
                            "HITL-2 feedback for %s (attempt %d/%d): %r",
                            bp.brief_id, brief_feedback_count, _MAX_BRIEF_FEEDBACK_RETRIES,
                            feedback[:100] if feedback else "",
                        )
                        if bp.gap_context and feedback:
                            # Re-run Agent 2 with user feedback embedded in topic rationale.
                            # bp.gap_context is WorkerQueryContext with full exemplar + cluster data.
                            primary_qid = bp.gap_context.query_gap.get("query_id", bp.brief_id)
                            feedback_topic = TopicSelection(
                                rank=0,
                                query_ids=[primary_qid],
                                query_texts=[bp.title],
                                cluster_name=getattr(bp, "cluster_name", bp.target_cluster),
                                rationale=f"[User feedback: {feedback[:300]}]",
                            )
                            revised = await build_briefs_parallel(
                                contexts={primary_qid: bp.gap_context},
                                topics=[feedback_topic],
                                company_context_md=company_context_md,
                                persona_mds=persona_mds,
                                style_guide_md=style_guide_md,
                                max_concurrent=1,
                                parent_span=stage2_span,
                                brief_id_overrides=[bp.brief_id],
                                company_slug=slug,
                            )
                            revised = [r for r in revised if r is not None]
                            if revised:
                                bp = revised[0]
                                bp.user_feedback = feedback
                        # Loop back to re-present the revised blueprint
                    else:
                        # Rejected outright or feedback retries exhausted
                        feedback = brief_state.get("brief_feedback", "")
                        logger.info("Brief %s rejected", bp.brief_id)
                        brief_decision_log.append({
                            "brief_id": bp.brief_id,
                            "decision": "reject",
                            "feedback": feedback,
                            "feedback_attempts": brief_feedback_count,
                        })
                        break

            end_span(stage2_span, output={"approved_blueprints": len(approved_blueprints)})
            _emit(event_bus, task_id, "stage_complete", {"stage": 2, "briefs_approved": len(approved_blueprints)})

            # Persist brief approvals — ALL blueprints with full decision audit trail
            await persist_v13_brief_approval(
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
                slug=slug,
                blueprints=[bp.model_dump(mode="json") for bp in blueprints],
                approval_decisions=brief_decision_log,
            )

    elif input_data.entry_mode == EntryMode.MANUAL:
        # Manual mode — skips Stage 1 (Strategic Planner + HITL-1) only.
        # HITL-2 (Brief Approval) IS included so the user can review the
        # generated blueprint before committing to the expensive worker chain.
        # D3 DEFERRED: Full lightweight gap analysis (s3-s6) on user prompt
        # adds 2-5 min latency and requires s1 output (SemanticUnit list) as
        # prerequisite. Current inline WorkerQueryContext construction is
        # sufficient for v0. See .claude/sprints/pending/backlog.md PB-45.
        logger.info("Manual mode entry — creating brief from prompt")

        # H4-fix: emit Stage 2 progress events so frontend SSE shows Brief Builder active
        _update_task(task_store, task_id, progress={"stage": 2, "stage_name": "Brief Builder"})
        _emit(event_bus, task_id, "stage_started", {"stage": 2, "name": "Brief Builder"})
        stages_actually_executed.add(2)

        # L1-fix: unique query ID per manual run (avoids hardcoded "manual-1" collision risk)
        manual_query_id = f"manual-{uuid.uuid4().hex[:8]}"

        # C3-fix: inject manual_description into rationale so Brief Builder
        # receives the gap context (classification, score) from the frontend.
        rationale_parts = ["User-specified topic"]
        if input_data.manual_description:
            rationale_parts.append(input_data.manual_description.strip())

        manual_topic = TopicSelection(
            rank=0,
            query_ids=[manual_query_id],
            query_texts=[input_data.manual_prompt or ""],
            cluster_name=input_data.manual_cluster or "manual",
            rationale=". ".join(rationale_parts),
            estimated_impact="medium",  # H9-fix: placeholder, derived after gap lookup below
        )

        # H1-fix: 3-tier gap data lookup — query_id → query_text → cluster fallback.
        # When triggered from Analytics "Add to Content Cycle", gap_query_id provides
        # a direct key into analysis_json for autonomous-quality context.
        matched_gap: dict[str, Any] | None = None
        if analysis_json:
            gaps_raw = analysis_json.get("gaps", [])

            # Tier 1: Direct query_id lookup (from Analytics)
            if input_data.gap_query_id:
                matched_gap = next(
                    (g for g in gaps_raw if g.get("query_id") == input_data.gap_query_id),
                    None,
                )

            # Tier 2: query_text match fallback (non-Analytics callers)
            if not matched_gap:
                prompt_norm = (input_data.manual_prompt or "").strip().lower()
                if prompt_norm:
                    matched_gap = next(
                        (g for g in gaps_raw
                         if (g.get("query_text", "").strip().lower()) == prompt_norm),
                        None,
                    )

        if matched_gap:
            # Full autonomous-quality context from the matched gap entry
            matched_cluster = matched_gap.get("cluster_name") or input_data.manual_cluster or "manual"
            cluster_spec = next(
                (s for s in analysis_json.get("cluster_specs", [])
                 if (s.get("cluster_name") or "").strip().lower() == matched_cluster.strip().lower()),
                {},
            )
            worker_contexts: dict[str, WorkerQueryContext] = {
                manual_query_id: WorkerQueryContext(
                    query_gap=matched_gap,
                    cluster_spec=cluster_spec,
                    exemplars=matched_gap.get("top_cited_exemplars", [])[:5],
                    gap_content_brief=matched_gap.get("content_brief"),
                    company_best_text=(matched_gap.get("best_company_unit_text") or "")[:200],
                    company_best_url=matched_gap.get("best_company_url") or "",
                )
            }
            logger.info(
                "Manual mode: matched gap data (tier=%s) — full context extracted",
                "query_id" if input_data.gap_query_id else "query_text",
            )
        else:
            # Tier 3: Cluster-level fallback (H2-fix: case-insensitive matching)
            cluster_spec: dict[str, Any] = {}
            exemplars: list[dict[str, Any]] = []
            if analysis_json:
                cluster_name_key = (input_data.manual_cluster or "manual").strip().lower()
                cluster_specs_raw = analysis_json.get("cluster_specs", [])
                cluster_spec = next(
                    (s for s in cluster_specs_raw
                     if (s.get("cluster_name") or "").strip().lower() == cluster_name_key),
                    {},
                )
                # H8-fix: collect, deduplicate by URL, rank by similarity
                gaps_raw = analysis_json.get("gaps", [])
                all_exemplars: list[dict[str, Any]] = []
                seen_urls: set[str] = set()
                for g in gaps_raw:
                    if (g.get("cluster_name") or "").strip().lower() != cluster_name_key:
                        continue
                    for ex in g.get("top_cited_exemplars", []):
                        url = ex.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_exemplars.append(ex)
                all_exemplars.sort(key=lambda e: e.get("similarity", 0.0), reverse=True)
                exemplars = all_exemplars[:5]

            if cluster_spec:
                logger.info("Manual mode: cluster '%s' matched in analysis data", input_data.manual_cluster)
            else:
                logger.info("Manual mode: no cluster match for '%s' — using empty spec", input_data.manual_cluster)

            worker_contexts = {
                manual_query_id: WorkerQueryContext(
                    query_gap={
                        "query_id": manual_query_id,
                        "query_text": input_data.manual_prompt or "",
                        "cluster_name": input_data.manual_cluster or "manual",
                    },
                    cluster_spec=cluster_spec,
                    exemplars=exemplars,
                )
            }

        # H9-fix: derive estimated_impact from gap score when available
        if matched_gap and matched_gap.get("gap") is not None:
            gap_score = float(matched_gap.get("gap", 0.0))
            if gap_score >= 0.6:
                manual_topic.estimated_impact = "high"
            elif gap_score >= 0.3:
                manual_topic.estimated_impact = "medium"
            else:
                manual_topic.estimated_impact = "low"

        # Determine brief ID: use hint from frontend if available, else auto-generate.
        if input_data.brief_id_hint:
            _manual_brief_id = input_data.brief_id_hint
        else:
            # Reads blueprints.json for existing IDs and picks the next sequential one.
            _existing_ids: set[str] = set()
            _bp_raw: Optional[str] = None
            _bp_key = f"content/{slug}/blueprints.json"
            if storage:
                _bp_raw = storage.read(_bp_key)
            else:
                _bp_path = artifact_dir / "blueprints.json"
                if _bp_path.is_file():
                    try:
                        _bp_raw = _bp_path.read_text(encoding="utf-8")
                    except OSError:
                        pass
            if _bp_raw:
                try:
                    _existing = json.loads(_bp_raw)
                    if isinstance(_existing, list):
                        _existing_ids = {b.get("brief_id", "") for b in _existing if isinstance(b, dict)}
                except (json.JSONDecodeError, ValueError):
                    pass
            _next_idx = 1
            while f"brief-{_next_idx:03d}" in _existing_ids:
                _next_idx += 1
            _manual_brief_id = f"brief-{_next_idx:03d}"

        # Mark brief as "briefing" for Kanban sync — Brief Builder is about to run
        await _write_pipeline_state_async(artifact_dir, [_manual_brief_id], "briefing", task_id=task_id, redis_client=redis_client, effective_slug=slug)

        blueprints = await build_briefs_parallel(
            contexts=worker_contexts,
            topics=[manual_topic],
            company_context_md=company_context_md,
            persona_mds=persona_mds,
            style_guide_md=style_guide_md,
            max_concurrent=1,
            parent_span=pipeline_trace,
            brief_id_overrides=[_manual_brief_id],
            company_slug=slug,
        )
        blueprints = [bp for bp in blueprints if bp is not None]

        # Save blueprints before HITL-2 (C1-fix: merge to preserve existing entries)
        blueprints_path = artifact_dir / "blueprints.json"
        _merge_and_write_blueprints(
            blueprints_path, blueprints,
            storage=storage, storage_key=f"content/{slug}/blueprints.json",
        )

        # Write "brief_review" state — brief is built, pending HITL-2 review
        await _write_pipeline_state_async(artifact_dir, [bp.brief_id for bp in blueprints], "brief_review", task_id=task_id, redis_client=redis_client, effective_slug=slug)

        # HITL Checkpoint 2: Brief Approval (per blueprint) with feedback loop
        # Same as autonomous mode — user reviews the generated blueprint before
        # committing to the expensive worker chain.
        _MAX_BRIEF_FEEDBACK_RETRIES = 1

        brief_decision_log: list[dict] = []

        for bp in blueprints:
            brief_feedback_count = 0

            while True:
                # Write pending state before HITL graph so polling sees it
                await _write_pipeline_state_async(
                    artifact_dir, [bp.brief_id],
                    "pending_brief_approval",
                    task_id=task_id,
                    redis_client=redis_client,
                    effective_slug=slug,
                )
                _emit_company(_company_slug, "notification", {
                    "type": "hitl_review_needed",
                    "brief_id": bp.brief_id,
                    "title": bp.title,
                    "checkpoint": "brief_approval",
                    "message": f"'{bp.title}' needs your review",
                })
                _emit_company(_company_slug, "state_changed", {
                    "changed": [bp.brief_id], "hint": "pending_brief_approval",
                })
                set_current_span(pipeline_trace)
                brief_graph = build_brief_approval_graph()
                brief_state = await run_hitl_checkpoint(
                    graph=brief_graph,
                    initial_state={
                        "blueprint": bp.model_dump(mode="json"),
                        "auto_approve": input_data.auto_approve,
                    },
                    thread_id=f"{task_id or 'cli'}-brief-approval-{bp.brief_id}-f{brief_feedback_count}",
                    task_store=task_store,
                    event_bus=event_bus,
                    task_id=task_id,
                    stage_name=f"Brief Approval ({bp.brief_id})",
                )

                brief_decision = brief_state.get("brief_decision", "approve")
                if brief_decision == "approve":
                    feedback = brief_state.get("brief_feedback", "")
                    if feedback:
                        bp.user_feedback = feedback
                    approved_blueprints.append(bp)
                    await _write_pipeline_state_async(artifact_dir, [bp.brief_id], "approved", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                    brief_decision_log.append({
                        "brief_id": bp.brief_id,
                        "decision": "approve",
                        "feedback": feedback,
                        "feedback_attempts": brief_feedback_count,
                    })
                    break
                elif brief_decision == "feedback" and brief_feedback_count < _MAX_BRIEF_FEEDBACK_RETRIES:
                    brief_feedback_count += 1
                    feedback = brief_state.get("brief_feedback", "")
                    logger.info(
                        "Manual HITL-2 feedback for %s (attempt %d/%d): %r",
                        bp.brief_id, brief_feedback_count, _MAX_BRIEF_FEEDBACK_RETRIES,
                        feedback[:100] if feedback else "",
                    )
                    if bp.gap_context and feedback:
                        primary_qid = bp.gap_context.query_gap.get("query_id", bp.brief_id)
                        feedback_topic = TopicSelection(
                            rank=0,
                            query_ids=[primary_qid],
                            query_texts=[bp.title],
                            cluster_name=getattr(bp, "cluster_name", bp.target_cluster),
                            rationale=f"[User feedback: {feedback[:300]}]",
                        )
                        revised = await build_briefs_parallel(
                            contexts={primary_qid: bp.gap_context},
                            topics=[feedback_topic],
                            company_context_md=company_context_md,
                            persona_mds=persona_mds,
                            style_guide_md=style_guide_md,
                            max_concurrent=1,
                            parent_span=pipeline_trace,
                            brief_id_overrides=[bp.brief_id],
                            company_slug=slug,
                        )
                        revised = [r for r in revised if r is not None]
                        if revised:
                            bp = revised[0]
                            bp.user_feedback = feedback
                    # Loop back to re-present the revised blueprint
                else:
                    # Rejected outright or feedback retries exhausted
                    feedback = brief_state.get("brief_feedback", "")
                    logger.info("Manual brief %s rejected", bp.brief_id)
                    brief_decision_log.append({
                        "brief_id": bp.brief_id,
                        "decision": "reject",
                        "feedback": feedback,
                        "feedback_attempts": brief_feedback_count,
                    })
                    break

        # Persist brief approvals with full decision audit trail
        await persist_v13_brief_approval(
            session_factory=session_factory,
            run_id=run_id,
            company_id=company_id,
            slug=slug,
            blueprints=[bp.model_dump(mode="json") for bp in blueprints],
            approval_decisions=brief_decision_log,
        )

        _emit(event_bus, task_id, "stage_complete", {"stage": 2, "briefs_approved": len(approved_blueprints)})

    elif input_data.entry_mode == EntryMode.TOPIC_DISCOVERY:
        # Topic Discovery mode — skips Stage 1. Topics come pre-approved from TD HITL-2.
        # Loads topic-scoped analysis + builds per-topic WorkerQueryContext, then feeds
        # into Brief Builder (Stage 2) + optional HITL-2.
        logger.info("Topic Discovery mode — loading scoped analysis")

        # H4-fix: emit Stage 2 progress events for TD mode
        _update_task(task_store, task_id, progress={"stage": 2, "stage_name": "Brief Builder"})
        _emit(event_bus, task_id, "stage_started", {"stage": 2, "name": "Brief Builder"})
        stages_actually_executed.add(2)

        from core.content_engine.context_router import (
            extract_topic_contexts,
            topic_assignment_to_selection,
        )
        from core.topic_discovery.db_ops import db_read_assignments_by_ids

        if session_factory is None:
            raise RuntimeError("session_factory is required for TOPIC_DISCOVERY entry mode")

        assignments = await db_read_assignments_by_ids(
            session_factory, list(input_data.topic_assignment_ids),
        )
        if not assignments:
            logger.warning("No matching TopicAssignments found for IDs: %s", input_data.topic_assignment_ids)

        # Load topic-scoped analysis
        td_analysis_json: dict[str, Any] = {}
        if input_data.td_ga_run_id:
            _scoped_key = f"gap_analysis/{slug}/topic_scoped/{input_data.td_ga_run_id}/analysis.json"
            _scoped_raw: Optional[str] = None
            if storage:
                _scoped_raw = storage.read(_scoped_key)
            else:
                scoped_path = (
                    _PROJECT_ROOT / "artifacts" / "gap_analysis" / slug
                    / "topic_scoped" / input_data.td_ga_run_id / "analysis.json"
                )
                if scoped_path.exists():
                    _scoped_raw = scoped_path.read_text(encoding="utf-8")
            if _scoped_raw:
                td_analysis_json = json.loads(_scoped_raw)
            else:
                logger.warning("Scoped analysis not found: %s", _scoped_key)

        topic_query_map = td_analysis_json.get("topic_query_map", {})
        gaps_raw = td_analysis_json.get("gaps", [])

        # Build per-topic contexts
        worker_contexts = extract_topic_contexts(td_analysis_json, topic_query_map)

        # Build TopicSelection per assignment
        approved_topics: list[TopicSelection] = []
        for rank_idx, assignment in enumerate(assignments):
            qids = topic_query_map.get(assignment.id, [])
            qtexts = [
                g.get("query_text", "")
                for g in gaps_raw
                if g.get("query_id") in set(qids)
            ]
            ts = topic_assignment_to_selection(assignment, qids, qtexts, rank=rank_idx)
            approved_topics.append(ts)

        if approved_topics and worker_contexts:
            # Use display_id as brief_id when available (TD-originated).
            # Fall back to brief-{N} for assignments without display_id.
            _td_overrides = [
                a.display_id if a.display_id else f"brief-{idx + 1:03d}"
                for idx, a in enumerate(assignments)
            ]
            blueprints = await build_briefs_parallel(
                contexts=worker_contexts,
                topics=approved_topics,
                company_context_md=company_context_md,
                persona_mds=persona_mds,
                style_guide_md=style_guide_md,
                max_concurrent=input_data.max_concurrent_workers,
                parent_span=pipeline_trace,
                company_slug=slug,
                brief_id_overrides=_td_overrides,
            )

            # TD-title-fix: Preserve original topic titles from TopicAssignment.
            # Brief Builder generates SEO-optimized titles, but users expect
            # the title they approved in Topic Discovery.
            # NOTE: blueprints list preserves positional alignment with
            # assignments (None entries for failed topics). Map by index
            # BEFORE filtering Nones to avoid mis-association (H2 fix).
            for idx, bp in enumerate(blueprints):
                if bp is not None and idx < len(assignments) and assignments[idx].topic_text:
                    bp.title = assignments[idx].topic_text
                    bp.topic_assignment_id = assignments[idx].id

            # Filter out None entries (failed topics) after index mapping
            blueprints = [bp for bp in blueprints if bp is not None]

            # TD-fix: Persist blueprint placeholders to DB BEFORE HITL-2 so
            # DbContentDataService.get_briefs() returns brief-001 during the
            # approval pause. Also graduate GA-phase ta- cards so the frontend
            # sees brief-001 (with pending_brief_approval from Redis pipeline
            # state) instead of a stale ta- card stuck at "briefing".
            if blueprints:
                await persist_blueprints_early(
                    session_factory=session_factory,
                    run_id=run_id,
                    company_id=company_id,
                    slug=slug,
                    blueprints=blueprints,
                )
                if input_data.topic_assignment_ids:
                    try:
                        from core.redis import get_sync_redis_or_none as _get_sync
                        from core.content_engine.state_redis import cleanup_ga_phase_state
                        _rc = _get_sync()
                        if _rc is not None:
                            cleanup_ga_phase_state(
                                _rc, slug, list(input_data.topic_assignment_ids),
                            )
                    except Exception:
                        logger.warning("GA-phase cleanup before HITL-2 failed", exc_info=True)

            if input_data.auto_approve:
                approved_blueprints = blueprints
            else:
                # HITL-2: Brief Approval (per blueprint) with feedback loop
                # Same pattern as AUTONOMOUS/MANUAL modes — user reviews each
                # generated blueprint before committing to the worker chain.
                await _write_pipeline_state_async(
                    artifact_dir,
                    [bp.brief_id for bp in blueprints],
                    "brief_review",
                    task_id=task_id,
                    redis_client=redis_client,
                    effective_slug=slug,
                )
                _MAX_BRIEF_FEEDBACK_RETRIES = 1
                brief_decision_log: list[dict] = []

                for bp in blueprints:
                    brief_feedback_count = 0

                    while True:
                        await _write_pipeline_state_async(
                            artifact_dir, [bp.brief_id],
                            "pending_brief_approval",
                            task_id=task_id,
                            redis_client=redis_client,
                            effective_slug=slug,
                        )
                        _emit_company(_company_slug, "notification", {
                            "type": "hitl_review_needed",
                            "brief_id": bp.brief_id,
                            "title": bp.title,
                            "checkpoint": "brief_approval",
                            "message": f"'{bp.title}' needs your review",
                        })
                        _emit_company(_company_slug, "state_changed", {
                            "changed": [bp.brief_id], "hint": "pending_brief_approval",
                        })
                        set_current_span(pipeline_trace)
                        brief_graph = build_brief_approval_graph()
                        brief_state = await run_hitl_checkpoint(
                            graph=brief_graph,
                            initial_state={
                                "blueprint": bp.model_dump(mode="json"),
                                "auto_approve": input_data.auto_approve,
                            },
                            thread_id=f"{task_id or 'cli'}-brief-approval-{bp.brief_id}-f{brief_feedback_count}",
                            task_store=task_store,
                            event_bus=event_bus,
                            task_id=task_id,
                            stage_name=f"Brief Approval ({bp.brief_id})",
                        )

                        brief_decision = brief_state.get("brief_decision", "approve")
                        if brief_decision == "approve":
                            feedback = brief_state.get("brief_feedback", "")
                            if feedback:
                                bp.user_feedback = feedback
                            approved_blueprints.append(bp)
                            await _write_pipeline_state_async(artifact_dir, [bp.brief_id], "approved", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                            brief_decision_log.append({
                                "brief_id": bp.brief_id,
                                "decision": "approve",
                                "feedback": feedback,
                                "feedback_attempts": brief_feedback_count,
                            })
                            break
                        elif brief_decision == "feedback" and brief_feedback_count < _MAX_BRIEF_FEEDBACK_RETRIES:
                            brief_feedback_count += 1
                            feedback = brief_state.get("brief_feedback", "")
                            logger.info(
                                "TD HITL-2 feedback for %s (attempt %d/%d): %r",
                                bp.brief_id, brief_feedback_count, _MAX_BRIEF_FEEDBACK_RETRIES,
                                feedback[:100] if feedback else "",
                            )
                            if bp.gap_context and feedback:
                                primary_qid = bp.gap_context.query_gap.get("query_id", bp.brief_id)
                                feedback_topic = TopicSelection(
                                    rank=0,
                                    query_ids=[primary_qid],
                                    query_texts=[bp.title],
                                    cluster_name=getattr(bp, "cluster_name", bp.target_cluster),
                                    rationale=f"[User feedback: {feedback[:300]}]",
                                )
                                revised = await build_briefs_parallel(
                                    contexts={primary_qid: bp.gap_context},
                                    topics=[feedback_topic],
                                    company_context_md=company_context_md,
                                    persona_mds=persona_mds,
                                    style_guide_md=style_guide_md,
                                    max_concurrent=1,
                                    parent_span=pipeline_trace,
                                    brief_id_overrides=[bp.brief_id],
                                    company_slug=slug,
                                )
                                revised = [r for r in revised if r is not None]
                                if revised:
                                    bp = revised[0]
                                    bp.user_feedback = feedback
                        else:
                            feedback = brief_state.get("brief_feedback", "")
                            logger.info("TD brief %s rejected", bp.brief_id)
                            brief_decision_log.append({
                                "brief_id": bp.brief_id,
                                "decision": "reject",
                                "feedback": feedback,
                                "feedback_attempts": brief_feedback_count,
                            })
                            break

                # Persist brief approvals with full decision audit trail
                await persist_v13_brief_approval(
                    session_factory=session_factory,
                    run_id=run_id,
                    company_id=company_id,
                    slug=slug,
                    blueprints=[bp.model_dump(mode="json") for bp in blueprints],
                    approval_decisions=brief_decision_log,
                )

            # Tag blueprints with topic_assignment_id for downstream traceability
            for bp in approved_blueprints:
                for topic in approved_topics:
                    if topic.query_ids and bp.target_queries:
                        tq_ids = {tq.query_text for tq in bp.target_queries}
                        if set(topic.query_texts) & tq_ids:
                            if topic.rank < len(assignments):
                                bp.topic_assignment_id = assignments[topic.rank].id
                            break

        _emit(event_bus, task_id, "stage_complete", {"stage": 2, "briefs_approved": len(approved_blueprints)})

    # Build brief_id → topic_assignment_id lookup for ContentPiece traceability
    _bp_ta_map: Dict[str, str] = {}
    for bp in approved_blueprints:
        ta_id = getattr(bp, "topic_assignment_id", None)
        if ta_id and hasattr(bp, "brief_id"):
            _bp_ta_map[bp.brief_id] = ta_id

    # Persist blueprints for all entry modes so the Content Studio can display them
    # C1-fix: merge to preserve manually-added entries (those with _source field)
    if approved_blueprints:
        bp_path = artifact_dir / "blueprints.json"
        _merge_and_write_blueprints(
            bp_path, approved_blueprints,
            storage=storage, storage_key=f"content/{slug}/blueprints.json",
        )

    # C6-fix: fail early when manual/TD modes produce zero blueprints.
    # Autonomous mode may legitimately have zero if user rejected all at HITL-2.
    if not approved_blueprints and input_data.entry_mode in (
        EntryMode.MANUAL, EntryMode.TOPIC_DISCOVERY,
    ):
        error_msg = (
            f"Brief Builder produced zero blueprints in {input_data.entry_mode.value} mode. "
            "This indicates an LLM failure or invalid input."
        )
        logger.error(error_msg)
        _update_task(task_store, task_id, status=TaskStatus.FAILED.value, error=error_msg)
        _emit(event_bus, task_id, "pipeline_failed", {"error": error_msg})
        _emit_company(_company_slug, "notification", {
            "type": "pipeline_error",
            "brief_id": "",
            "title": slug,
            "message": f"Pipeline failed: {error_msg[:200]}",
        })
        update_trace_output(pipeline_trace, output={"error": error_msg})
        flush()
        return ContentGenerationOutput(
            company_slug=slug,
            total_briefs=0,
            total_approved=0,
            total_rejected=0,
            pieces=[],
            run_metadata={
                "pipeline_version": "1.3",
                "entry_mode": input_data.entry_mode.value,
                "duration_seconds": round(time.time() - start_time, 1),
                "error": error_msg,
                "stages_executed": sorted(stages_actually_executed),
            },
        )

    # Initialize pieces before Stage 3 (worker failures append to it)
    pieces: List[ContentPiece] = []

    # DB-ready: create ContentPieceModel rows early (before Stage 3)
    # so stage artifacts can be linked via FK. Upsert by (slug, brief_id)
    # to handle briefs pre-created by add_brief().
    piece_id_map: Dict[str, Any] = {}
    if session_factory and run_id and approved_blueprints:
        try:
            from core.db.enums import ContentPieceStatus as _CPS
            from core.db.repositories.content_repo import ContentRepository as _CR

            async with session_factory() as _sess:
                _repo = _CR(_sess)
                for bp in approved_blueprints:
                    existing = await _repo.get_by_slug_and_brief_id(slug, bp.brief_id)
                    if existing:
                        existing.run_id = run_id
                        existing.status = _CPS.planned
                        await _sess.flush()
                        piece_id_map[bp.brief_id] = existing.id
                    else:
                        _piece = await _repo.create_piece(
                            run_id=run_id,
                            effective_slug=slug,
                            brief_id=bp.brief_id,
                            company_id=company_id,
                            title=bp.title,
                            cluster_name=getattr(bp, "target_cluster", ""),
                            content_type=getattr(bp, "content_format", "long_blog"),
                            status=_CPS.planned,
                            word_count=0,
                            topic_assignment_id=_bp_ta_map.get(bp.brief_id),
                        )
                        piece_id_map[bp.brief_id] = _piece.id
                await _sess.commit()
        except Exception:
            logger.warning("Failed to create early ContentPieceModel rows", exc_info=True)

    # Clear stale step_name left by bind_context() in stages 1/2
    bind_context(step_name=None)

    # ── Stage 3: Content Workers ──────────────────────────────────
    with scoped_bind(step_name="stage_3_content_workers"):
        if 3 not in input_data.skip_stages and approved_blueprints:
            stage3_span = create_span(pipeline_trace, "stage/3-content-workers")
            _update_task(task_store, task_id, progress={"stage": 3, "stage_name": "Content Workers"})
            _emit(event_bus, task_id, "stage_started", {"stage": 3, "name": "Content Workers"})
            stages_actually_executed.add(3)

            # Per-brief "outlining" state is written by the dispatcher before each worker starts.
            # No coarse "in_progress" write needed here.

            # Extract site pages for linker (from s1 discovery data in analysis.json)
            site_pages = _extract_site_pages(analysis_json)

            # v1.3 dispatcher: Outliner → Drafter → Linker → Fact Checker
            from core.content_engine.workers.dispatcher import dispatch_workers_v13

            formatted_contents, worker_failures = await dispatch_workers_v13(
                briefs=approved_blueprints,  # ContentBlueprint extends ContentBrief
                input_data=input_data,
                style_guide_md=style_guide_md,
                company_context_md=company_context_md,
                max_concurrent=input_data.max_concurrent_workers,
                artifact_dir=artifact_dir,
                site_pages=site_pages,
                parent_span=stage3_span,
                storage=storage,
                session_factory=session_factory,
                piece_id_map=piece_id_map,
                event_bus=event_bus,
                task_id=task_id,
                redis_client=redis_client,
                effective_slug=slug,
            )

            # H2 FIX: Surface worker failures as rejected pieces + SSE events
            for wf in worker_failures:
                pieces.append(ContentPiece(
                    brief_id=wf["brief_id"],
                    title=f"[Worker Failed] {wf['brief_id']}",
                    status=ContentStatus.REJECTED,
                    eval_summary={"worker_error": wf["error"]},
                    topic_assignment_id=_bp_ta_map.get(wf["brief_id"]),
                ))
                _emit(event_bus, task_id, "worker_failed", {
                    "brief_id": wf["brief_id"],
                    "error": wf["error"],
                })

            end_span(stage3_span, output={
                "formatted_count": len(formatted_contents),
                "failed_count": len(worker_failures),
            })
            _emit(event_bus, task_id, "stage_complete", {
                "stage": 3,
                "pieces": len(formatted_contents),
                "failed": len(worker_failures),
            })
        else:
            formatted_contents = []

    # ── Stage 4: Evaluator with Dual Feedback ─────────────────────
    with scoped_bind(step_name="stage_4_evaluator"):
        if 4 not in input_data.skip_stages and formatted_contents:
            stage4_span = create_span(pipeline_trace, "stage/4-evaluator")
            _update_task(task_store, task_id, progress={"stage": 4, "stage_name": "Evaluator"})
            _emit(event_bus, task_id, "stage_started", {"stage": 4, "name": "Evaluator"})
            stages_actually_executed.add(4)

            from core.content_engine.evaluator.loop import evaluate_and_optimize

            evaluated: List[tuple] = []
            blueprint_by_id = {bp.brief_id: bp for bp in approved_blueprints}
            for brief_id, content in formatted_contents:
                blueprint = blueprint_by_id.get(brief_id)
                if blueprint is None:
                    logger.warning(
                        "Stage 4: no blueprint found for brief_id=%s, skipping", brief_id
                    )
                    continue
                # Mark brief as "evaluating" for Kanban sync
                await _write_pipeline_state_async(artifact_dir, [brief_id], "evaluating", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                _emit(event_bus, task_id, "worker_progress", {
                    "brief_id": brief_id, "step": "evaluating",
                })

                final_content, history, feedback_route = await evaluate_and_optimize(
                    content=content,
                    brief=blueprint,
                    company_context_md=company_context_md,
                    style_guide_md=style_guide_md,
                    input_data=input_data,
                    max_cycles=input_data.max_revision_cycles,
                    session_id=session_id,
                    artifact_dir=artifact_dir,
                    parent_span=stage4_span,
                    use_eeat=True,
                    use_targeted_revision=True,
                    event_bus=event_bus,
                    task_id=task_id,
                    redis_client=redis_client,
                    effective_slug=slug,
                )
                evaluated.append((brief_id, final_content, history, feedback_route))

            end_span(stage4_span, output={"evaluated_count": len(evaluated)})
            _emit(event_bus, task_id, "stage_complete", {"stage": 4, "evaluated": len(evaluated)})

            # Mark evaluated briefs as "review" for Kanban sync (HITL-3 pending)
            await _write_pipeline_state_async(
                artifact_dir,
                [bid for bid, _, _, _ in evaluated],
                "review",
                task_id=task_id,
                redis_client=redis_client,
                effective_slug=slug,
            )
        else:
            evaluated = [
                (bid, fc, RevisionHistory(brief_id=fc.brief_id, final_passed=True), "pass")
                for bid, fc in formatted_contents
            ]

    # ── Stage 4.5: CPS Scoring ───────────────────────────────────
    cps_results: Dict[str, Dict[str, Any]] = {}
    if evaluated:
        try:
            _bp_map = {bp.brief_id: bp for bp in approved_blueprints}
            cps_results = await _score_cps_batch(
                evaluated=evaluated,
                blueprint_by_id=_bp_map,
                domain=input_data.domain,
                parent_span=pipeline_trace,
                event_bus=event_bus,
                task_id=task_id,
            )
        except Exception:
            logger.warning("CPS scoring batch failed, continuing without CPS", exc_info=True)

    # ── Stage 5: Final HITL Review ────────────────────────────────
    with scoped_bind(step_name="stage_5_final_review"):
        _MAX_EDIT_ATTEMPTS = 2
        _MAX_REBRIEFS = 2

        if 5 not in input_data.skip_stages and evaluated:
            stage5_span = create_span(pipeline_trace, "stage/5-final-review")
            _update_task(task_store, task_id, progress={"stage": 5, "stage_name": "Final Review"})
            _emit(event_bus, task_id, "stage_started", {"stage": 5, "name": "Final Review"})
            stages_actually_executed.add(5)

            _bp_by_id = {bp.brief_id: bp for bp in approved_blueprints}
            for brief_id, final_content, history, feedback_route in evaluated:
                blueprint = _bp_by_id.get(brief_id)
                rebrief_count = 0
                edit_count = 0

                # Handle evaluator major_change signal → immediate re-brief
                if feedback_route == "major_change" and blueprint and rebrief_count < _MAX_REBRIEFS:
                    logger.info(
                        "Evaluator major_change for %s — triggering re-brief",
                        final_content.brief_id,
                    )
                    rebrief_count += 1
                    rebriefed = await _rebrief_and_rerun(
                        blueprint=blueprint,
                        user_comment="Evaluator detected major direction misalignment (semantic < 0.5)",
                        input_data=input_data,
                        company_context_md=company_context_md,
                        persona_mds=persona_mds,
                        style_guide_md=style_guide_md,
                        analysis_json=analysis_json,
                        artifact_dir=artifact_dir,
                        session_id=session_id,
                        parent_span=stage5_span,
                        event_bus=event_bus,
                        task_id=task_id,
                        redis_client=redis_client,
                        slug=slug,
                    )
                    if rebriefed:
                        final_content, history, feedback_route = rebriefed

                # HITL-3 review loop (edit/reject with bounded retries)
                piece_resolved = False
                while not piece_resolved:
                    # Build eval summary
                    eval_summary = {}
                    if history.cycles:
                        last_eval = history.cycles[-1]
                        eval_summary = {
                            "overall_score": last_eval.overall_score,
                            "overall_passed": last_eval.overall_passed,
                            "dimensions": {
                                d.dimension: {"score": d.score, "passed": d.passed}
                                for d in last_eval.dimensions
                            },
                        }
                    # CPS scored at Stage 4.5; may be stale after edit/rebrief loops
                    # (acceptable for v1 — CPS is informational, not a gate)
                    cps_data = cps_results.get(brief_id)
                    if cps_data:
                        eval_summary["cps"] = cps_data

                    # HITL Checkpoint 3: Final Content Review
                    # Write pending state BEFORE graph starts so polling also
                    # discovers the HITL state (not just SSE events).
                    await _write_pipeline_state_async(
                        artifact_dir, [final_content.brief_id],
                        "pending_content_approval",
                        task_id=task_id,
                        redis_client=redis_client,
                        effective_slug=slug,
                    )
                    _emit_company(_company_slug, "notification", {
                        "type": "hitl_review_needed",
                        "brief_id": final_content.brief_id,
                        "title": final_content.title,
                        "checkpoint": "content_review",
                        "message": f"'{final_content.title}' needs your review",
                    })
                    _emit_company(_company_slug, "state_changed", {
                        "changed": [final_content.brief_id], "hint": "pending_content_approval",
                    })
                    set_current_span(stage5_span)
                    review_graph = build_content_review_graph()
                    review_state = await run_hitl_checkpoint(
                        graph=review_graph,
                        initial_state={
                            "content": {
                                "brief_id": final_content.brief_id,
                                "title": final_content.title,
                                "markdown": final_content.markdown,
                                "word_count": final_content.word_count,
                            },
                            "eval_summary": eval_summary,
                            "auto_approve": input_data.auto_approve,
                        },
                        thread_id=f"{task_id or 'cli'}-content-review-{final_content.brief_id}-e{edit_count}-r{rebrief_count}",
                        task_store=task_store,
                        event_bus=event_bus,
                        task_id=task_id,
                        stage_name=f"Content Review ({final_content.brief_id})",
                    )

                    content_decision = review_state.get("content_decision", "approve")

                    if content_decision == "approve" or review_state.get("finalized"):
                        # Emit brief completion event for Kanban sync
                        _emit(event_bus, task_id, "brief_completed", {
                            "brief_id": final_content.brief_id, "decision": "approve",
                        })
                        _emit_company(_company_slug, "notification", {
                            "type": "pipeline_complete",
                            "brief_id": final_content.brief_id,
                            "title": final_content.title,
                            "message": f"'{final_content.title}' is ready for review",
                        })
                        _emit_company(_company_slug, "state_changed", {
                            "changed": [final_content.brief_id], "hint": "completed",
                        })
                        # Approved — write final.md via StorageBackend
                        _brief_dir(artifact_dir, final_content.brief_id)  # ensure local dir for state_helpers
                        final_rel_path = f"content/{slug}/content/{final_content.brief_id}/final.md"
                        if storage:
                            from core.content_engine.artifact_writer import persist_stage_artifact
                            from core.db.enums import ContentArtifactStage as _CAS

                            await persist_stage_artifact(
                                storage=storage, session_factory=session_factory,
                                piece_id=piece_id_map.get(final_content.brief_id),
                                stage=_CAS.final,
                                relative_path=final_rel_path,
                                content=final_content.markdown,
                            )
                        else:
                            bd = _brief_dir(artifact_dir, final_content.brief_id)
                            (bd / "final.md").write_text(final_content.markdown, encoding="utf-8")
                        pieces.append(
                            ContentPiece(
                                brief_id=final_content.brief_id,
                                title=final_content.title,
                                status=ContentStatus.APPROVED,
                                final_markdown=final_content.markdown,
                                eval_summary=eval_summary,
                                human_notes=review_state.get("editor_notes"),
                                artifact_path=final_rel_path,
                                topic_assignment_id=_bp_ta_map.get(final_content.brief_id),
                            )
                        )
                        await _write_pipeline_state_async(artifact_dir, [final_content.brief_id], "completed", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                        piece_resolved = True

                    elif content_decision == "edit" and edit_count < _MAX_EDIT_ATTEMPTS:
                        # Edit → drafter revision with human notes → fact checker → re-present
                        edit_count += 1
                        # Mark as revising for Kanban sync (tile moves back to Generating)
                        await _write_pipeline_state_async(artifact_dir, [final_content.brief_id], "revising", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                        _emit(event_bus, task_id, "worker_progress", {
                            "brief_id": final_content.brief_id, "step": "revising",
                            "edit_attempt": edit_count,
                        })
                        editor_notes = review_state.get("editor_notes", "")
                        logger.info(
                            "HITL-3 edit for %s (attempt %d/%d)",
                            final_content.brief_id,
                            edit_count,
                            _MAX_EDIT_ATTEMPTS,
                        )
                        revised = await _apply_human_edits(
                            final_content=final_content,
                            blueprint=blueprint,
                            editor_notes=editor_notes,
                            style_guide_md=style_guide_md,
                            company_context_md=company_context_md,
                            company_name=input_data.company_name,
                            domain=input_data.domain,
                            company_slug=slug,
                        )
                        if revised:
                            final_content = revised
                            # Re-evaluate after edit
                            from core.content_engine.evaluator.loop import evaluate_and_optimize
                            final_content, history, feedback_route = await evaluate_and_optimize(
                                content=final_content,
                                brief=blueprint,
                                company_context_md=company_context_md,
                                style_guide_md=style_guide_md,
                                input_data=input_data,
                                max_cycles=1,
                                session_id=session_id,
                                artifact_dir=artifact_dir,
                                parent_span=stage5_span,
                                use_eeat=True,
                                use_targeted_revision=True,
                                event_bus=event_bus,
                                task_id=task_id,
                                redis_client=redis_client,
                                effective_slug=slug,
                            )
                        # Loop back to re-present at HITL-3

                    elif (
                        content_decision == "reject"
                        and review_state.get("rethink", False)  # H3 FIX: only re-brief when rethink=True
                        and blueprint
                        and rebrief_count < _MAX_REBRIEFS
                    ):
                        # Reject + rethink → re-brief with user comment → re-run full chain
                        rebrief_count += 1
                        # Mark as "briefing" for Kanban sync (tile moves back to Brief column)
                        await _write_pipeline_state_async(artifact_dir, [final_content.brief_id], "briefing", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                        _emit(event_bus, task_id, "worker_progress", {
                            "brief_id": final_content.brief_id, "step": "briefing",
                            "rebrief_attempt": rebrief_count,
                        })
                        user_comment = review_state.get("editor_notes", "")
                        logger.info(
                            "HITL-3 reject for %s — re-briefing (attempt %d/%d)",
                            final_content.brief_id,
                            rebrief_count,
                            _MAX_REBRIEFS,
                        )
                        rebriefed = await _rebrief_and_rerun(
                            blueprint=blueprint,
                            user_comment=user_comment,
                            input_data=input_data,
                            company_context_md=company_context_md,
                            persona_mds=persona_mds,
                            style_guide_md=style_guide_md,
                            analysis_json=analysis_json,
                            artifact_dir=artifact_dir,
                            session_id=session_id,
                            parent_span=stage5_span,
                            event_bus=event_bus,
                            task_id=task_id,
                            redis_client=redis_client,
                            slug=slug,
                        )
                        if rebriefed:
                            final_content, history, feedback_route = rebriefed
                            # Reset edit count for new content
                            edit_count = 0
                        else:
                            # Re-brief failed — reject permanently
                            pieces.append(
                                ContentPiece(
                                    brief_id=final_content.brief_id,
                                    title=final_content.title,
                                    status=ContentStatus.REJECTED,
                                    eval_summary=eval_summary,
                                    human_notes=review_state.get("editor_notes"),
                                    topic_assignment_id=_bp_ta_map.get(final_content.brief_id),
                                )
                            )
                            piece_resolved = True
                        # Loop back to re-present at HITL-3

                    else:
                        # Exhausted edit/rebrief attempts or explicit reject — permanent rejection
                        await _write_pipeline_state_async(artifact_dir, [final_content.brief_id], "rejected", task_id=task_id, redis_client=redis_client, effective_slug=slug)
                        _emit(event_bus, task_id, "brief_rejected", {
                            "brief_id": final_content.brief_id,
                        })
                        pieces.append(
                            ContentPiece(
                                brief_id=final_content.brief_id,
                                title=final_content.title,
                                status=ContentStatus.REJECTED,
                                eval_summary=eval_summary,
                                human_notes=review_state.get("editor_notes"),
                                topic_assignment_id=_bp_ta_map.get(final_content.brief_id),
                            )
                        )
                        piece_resolved = True

            end_span(stage5_span, output={"pieces": len(pieces)})
        else:
            # Auto-approve all
            for _brief_id, final_content, history, _feedback_route in evaluated:
                _brief_dir(artifact_dir, final_content.brief_id)  # ensure local dir for state_helpers
                final_rel_path = f"content/{slug}/content/{final_content.brief_id}/final.md"
                if storage:
                    from core.content_engine.artifact_writer import persist_stage_artifact
                    from core.db.enums import ContentArtifactStage as _CAS

                    await persist_stage_artifact(
                        storage=storage, session_factory=session_factory,
                        piece_id=piece_id_map.get(final_content.brief_id),
                        stage=_CAS.final,
                        relative_path=final_rel_path,
                        content=final_content.markdown,
                    )
                else:
                    bd = _brief_dir(artifact_dir, final_content.brief_id)
                    (bd / "final.md").write_text(final_content.markdown, encoding="utf-8")
                auto_eval: Dict[str, Any] = {}
                if history.cycles:
                    last_eval = history.cycles[-1]
                    auto_eval = {
                        "overall_score": last_eval.overall_score,
                        "overall_passed": last_eval.overall_passed,
                        "dimensions": {
                            d.dimension: {"score": d.score, "passed": d.passed}
                            for d in last_eval.dimensions
                        },
                    }
                cps_data = cps_results.get(_brief_id)
                if cps_data:
                    auto_eval["cps"] = cps_data
                pieces.append(
                    ContentPiece(
                        brief_id=final_content.brief_id,
                        title=final_content.title,
                        status=ContentStatus.APPROVED,
                        final_markdown=final_content.markdown,
                        eval_summary=auto_eval,
                        artifact_path=final_rel_path,
                        topic_assignment_id=_bp_ta_map.get(final_content.brief_id),
                    )
                )

    # ── Finalize ──────────────────────────────────────────────────
    total_approved = sum(1 for p in pieces if p.status == ContentStatus.APPROVED)
    total_rejected = sum(1 for p in pieces if p.status == ContentStatus.REJECTED)

    output = ContentGenerationOutput(
        company_slug=slug,
        total_briefs=len(approved_blueprints),
        total_approved=total_approved,
        total_rejected=total_rejected,
        pieces=pieces,
        run_metadata={
            "pipeline_version": "1.3",
            "entry_mode": input_data.entry_mode.value,
            "duration_seconds": round(time.time() - start_time, 1),
            "stages_executed": sorted(stages_actually_executed),
        },
    )

    await _finalize_pipeline(
        output=output,
        pipeline_trace=pipeline_trace,
        slug=slug,
        approved_blueprints=approved_blueprints,
        pieces=pieces,
        start_time=start_time,
        input_data=input_data,
        artifact_dir=artifact_dir,
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
        task_store=task_store,
        task_id=task_id,
        event_bus=event_bus,
        redis_client=redis_client,
        storage=storage,
    )

    return output
