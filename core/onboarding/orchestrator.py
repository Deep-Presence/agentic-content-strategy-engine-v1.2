"""Onboarding Pipeline Orchestrator — 3-phase meta-orchestrator.

Chains existing pipelines with auto-approved HITL gates:
  Phase A: Site Audit + KB (parallel)
  Phase B: AP (sequential, seeded with user personas)
  Phase C: VSG + GA + TD (parallel)

Calls sub-pipelines directly (not via runner wrappers).
Semaphore and slug-lock are owned by the caller (runner).
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config.settings import settings
from core.models.onboarding import (
    OnboardingInput,
    OnboardingOutput,
    OnboardingPhase,
    OnboardingPhaseResult,
    OnboardingStatus,
    OnboardingSubResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Child pipeline_run record helpers
# ---------------------------------------------------------------------------


async def _create_child_pipeline_run(
    session_factory: Optional[Any],
    parent_run_id: Optional[Any],
    company_id: Optional[Any],
    effective_slug: str,
    pipeline_type_str: str,
    workspace_id: str = "",
) -> Optional[_uuid.UUID]:
    """Create a pipeline_runs record for a sub-pipeline within onboarding.

    Returns a fresh run_id for the child, or None if DB not available.
    Uses parent_run_id to link the child back to the onboarding parent.
    """
    if not session_factory or not company_id:
        return None
    try:
        from core.db.models.pipelines import PipelineRunModel, PipelineStatus
        from core.db.enums import PipelineType

        child_run_id = _uuid.uuid4()
        async with session_factory() as session:
            run = PipelineRunModel(
                id=child_run_id,
                company_id=company_id,
                workspace_id=_uuid.UUID(workspace_id) if workspace_id else None,
                effective_slug=effective_slug,
                pipeline_type=PipelineType(pipeline_type_str),
                parent_run_id=parent_run_id,
                status=PipelineStatus.running,
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            await session.commit()
        return child_run_id
    except Exception:
        logger.warning(
            "Failed to create child pipeline_run for %s", pipeline_type_str,
            exc_info=True,
        )
        return None


async def _complete_child_pipeline_run(
    session_factory: Optional[Any],
    child_run_id: Optional[_uuid.UUID],
    *,
    error: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark a child pipeline_run as completed or failed."""
    if not session_factory or not child_run_id:
        return
    try:
        from core.db.models.pipelines import PipelineRunModel, PipelineStatus

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, child_run_id)
            if run:
                run.status = PipelineStatus.failed if error else PipelineStatus.completed
                run.completed_at = datetime.now(timezone.utc)
                if run.started_at:
                    run.duration_seconds = int(
                        (run.completed_at - run.started_at).total_seconds()
                    )
                if error:
                    run.error_message = str(error)[:1000]
                if summary:
                    run.summary = summary
                await session.commit()
    except Exception:
        logger.warning(
            "Failed to complete child pipeline_run %s", child_run_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Null-safe helpers (same pattern as research orchestrator)
# ---------------------------------------------------------------------------


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


class _SubPipelineEventProxy:
    """Wraps EventBus to rewrite terminal events from sub-pipelines.

    Prevents sub-pipeline "completed"/"failed"/"cancelled" events from
    terminating the parent orchestrator's SSE stream early.
    """

    _REWRITES = {
        "completed": "sub_completed",
        "failed": "sub_failed",
        "cancelled": "sub_cancelled",
    }

    def __init__(self, real_bus: Any) -> None:
        self._real_bus = real_bus

    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        event_type = self._REWRITES.get(event_type, event_type)
        self._real_bus.publish(task_id, event_type, data)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real_bus, name)


# ---------------------------------------------------------------------------
# Slug resolution
# ---------------------------------------------------------------------------


def _resolve_slugs(input_data: OnboardingInput) -> str:
    """Return company_slug from onboarding input (company-level only)."""
    from core.auth.utils.domain import derive_slug

    return input_data.company_slug or derive_slug(input_data.company_name)


# ---------------------------------------------------------------------------
# Industry → additional_constraints helper
# ---------------------------------------------------------------------------


def _build_constraints(input_data: OnboardingInput) -> Optional[str]:
    """Build additional_constraints string with industry context."""
    parts: list[str] = []
    if input_data.industry:
        parts.append(f"Industry: {input_data.industry}")
    return "; ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Input builders
# ---------------------------------------------------------------------------


def _build_sa_input(input_data: OnboardingInput, slug: str) -> Any:
    """Build SiteAuditInput from onboarding input."""
    from core.models.site_audit import SiteAuditInput

    return SiteAuditInput(
        company_name=input_data.company_name,
        domain=input_data.domain,
        company_slug=slug,
        max_pages=input_data.max_pages,
        max_depth=input_data.max_depth,
    )


def _build_kb_input(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
) -> Any:
    """Build KnowledgeBaseInput from onboarding input."""
    from core.models.knowledge_base import KnowledgeBaseInput

    return KnowledgeBaseInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=slug,
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        seed_urls=input_data.seed_urls,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=constraints,
        auto_approve_checkpoints=[1, 2, 3],
    )


def _build_ap_input(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
) -> Any:
    """Build AudiencePersonaInput from onboarding input."""
    from core.models.audience_persona import AudiencePersonaInput

    return AudiencePersonaInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=slug,
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        max_personas=input_data.max_personas,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=constraints,
        auto_approve_checkpoints=[1, 2],
        seed_personas=input_data.seed_personas,
    )


def _build_vsg_input(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
) -> Any:
    """Build VoiceStyleGuideInput from onboarding input."""
    from core.models.voice_style_guide import VoiceStyleGuideInput

    return VoiceStyleGuideInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=slug,
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        max_authors=input_data.max_authors,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=constraints,
        auto_approve_checkpoints=[1],
    )


def _build_ga_input(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
) -> Any:
    """Build GapAnalysisInput from onboarding input."""
    from core.models.gap_analysis import GapAnalysisInput

    return GapAnalysisInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=slug,
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        seed_urls=[str(u) for u in input_data.seed_urls],
        max_queries=input_data.max_queries,
        platforms=input_data.platforms,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=constraints,
    )


def _build_td_input(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
) -> Any:
    """Build TopicDiscoveryInput from onboarding input."""
    from core.models.topic_discovery import TopicDiscoveryInput

    return TopicDiscoveryInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=slug,
        workspace_id=input_data.workspace_id,
        seed_urls=input_data.seed_urls,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=constraints,
        auto_approve_checkpoints=[1],
    )


# ---------------------------------------------------------------------------
# SA progress bridge
# ---------------------------------------------------------------------------


def _make_sa_progress_bridge(
    event_bus: Optional[Any],
    task_id: Optional[str],
) -> Any:
    """Create an on_progress callback that bridges to SSE events."""
    def bridge(msg: str) -> None:
        _emit(event_bus, task_id, "onboarding_sa_progress", {"message": msg})
    return bridge


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------


async def _run_site_audit_stage(
    input_data: OnboardingInput,
    slug: str,
    event_bus: Optional[Any],
    task_id: Optional[str],
    root: Path,
    session_factory: Optional[Any] = None,
    parent_run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
) -> OnboardingSubResult:
    """Run site audit. Returns result (never raises)."""
    from core.site_audit.pipeline import run_site_audit

    child_run_id = await _create_child_pipeline_run(
        session_factory, parent_run_id, company_id, slug, "site_audit",
        workspace_id=input_data.workspace_id,
    )

    start = time.time()
    try:
        sa_input = _build_sa_input(input_data, slug)
        progress_fn = _make_sa_progress_bridge(event_bus, task_id)
        result = await run_site_audit(
            sa_input,
            on_progress=progress_fn,
        )
        elapsed = time.time() - start

        # Site audit returns status="failed" instead of raising
        if getattr(result, "status", None) == "failed":
            err = getattr(result, "error_message", "Site audit failed")
            await _complete_child_pipeline_run(session_factory, child_run_id, error=err)
            return OnboardingSubResult(
                pipeline="site_audit",
                phase="phase_a",
                status="failed",
                execution_time_s=elapsed,
                error=err,
            )

        await _complete_child_pipeline_run(session_factory, child_run_id, summary={
            "audit_id": getattr(result, "audit_id", ""),
            "pages_crawled": getattr(result, "pages_crawled", 0),
        })
        return OnboardingSubResult(
            pipeline="site_audit",
            phase="phase_a",
            status="completed",
            execution_time_s=elapsed,
            output_summary={
                "audit_id": getattr(result, "audit_id", ""),
                "pages_crawled": getattr(result, "pages_crawled", 0),
            },
        )
    except Exception as exc:
        elapsed = time.time() - start
        logger.exception("Onboarding: site_audit failed")
        await _complete_child_pipeline_run(session_factory, child_run_id, error=str(exc))
        return OnboardingSubResult(
            pipeline="site_audit",
            phase="phase_a",
            status="failed",
            execution_time_s=elapsed,
            error=str(exc),
        )


async def _run_kb_stage(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    root: Path,
    session_factory: Optional[Any],
    parent_run_id: Optional[Any],
    company_id: Optional[Any],
    langsmith_project: Optional[str] = None,
) -> Tuple[OnboardingSubResult, Any]:
    """Run KB pipeline. Returns (result, raw_output)."""
    from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

    child_run_id = await _create_child_pipeline_run(
        session_factory, parent_run_id, company_id, slug, "knowledge_base",
        workspace_id=input_data.workspace_id,
    )

    start = time.time()
    try:
        kb_input = _build_kb_input(input_data, slug, constraints)
        output = await run_knowledge_base_pipeline(
            kb_input,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            artifacts_root=root,
            session_factory=session_factory,
            run_id=child_run_id or parent_run_id,
            company_id=company_id,
            langsmith_project=langsmith_project,
        )
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, summary={
            "company_profile_path": getattr(output, "company_profile_path", ""),
        })
        result = OnboardingSubResult(
            pipeline="kb",
            phase="phase_a",
            status="completed",
            execution_time_s=elapsed,
            output_summary={
                "company_profile_path": getattr(output, "company_profile_path", ""),
            },
        )
        return result, output
    except Exception as exc:
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, error=str(exc))
        raise


async def _run_ap_stage(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    root: Path,
    session_factory: Optional[Any],
    parent_run_id: Optional[Any],
    company_id: Optional[Any],
    langsmith_project: Optional[str] = None,
) -> Tuple[OnboardingSubResult, Any]:
    """Run AP pipeline with seed_personas. Returns (result, raw_output)."""
    from core.research.audience_persona.pipeline import run_audience_persona_pipeline

    child_run_id = await _create_child_pipeline_run(
        session_factory, parent_run_id, company_id, slug, "audience_persona",
        workspace_id=input_data.workspace_id,
    )

    start = time.time()
    try:
        ap_input = _build_ap_input(input_data, slug, constraints)
        output = await run_audience_persona_pipeline(
            ap_input,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            artifacts_root=root,
            session_factory=session_factory,
            run_id=child_run_id or parent_run_id,
            company_id=company_id,
            langsmith_project=langsmith_project,
        )
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, summary={
            "persona_dir": getattr(output, "persona_dir", ""),
            "profiles_generated": getattr(output, "profiles_generated", 0),
        })
        result = OnboardingSubResult(
            pipeline="ap",
            phase="phase_b",
            status="completed",
            execution_time_s=elapsed,
            output_summary={
                "persona_dir": getattr(output, "persona_dir", ""),
                "profiles_generated": getattr(output, "profiles_generated", 0),
            },
        )
        return result, output
    except Exception as exc:
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, error=str(exc))
        raise


async def _run_vsg_stage(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    root: Path,
    session_factory: Optional[Any],
    parent_run_id: Optional[Any],
    company_id: Optional[Any],
    langsmith_project: Optional[str] = None,
) -> OnboardingSubResult:
    """Run VSG pipeline. Returns result."""
    from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

    child_run_id = await _create_child_pipeline_run(
        session_factory, parent_run_id, company_id, slug, "voice_style_guide",
        workspace_id=input_data.workspace_id,
    )

    start = time.time()
    try:
        vsg_input = _build_vsg_input(input_data, slug, constraints)
        output = await run_voice_style_guide_pipeline(
            vsg_input,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            artifacts_root=root,
            session_factory=session_factory,
            run_id=child_run_id or parent_run_id,
            company_id=company_id,
            langsmith_project=langsmith_project,
        )
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, summary={
            "style_guide_path": getattr(output, "style_guide_path", ""),
        })
    except Exception as exc:
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, error=str(exc))
        raise
    return OnboardingSubResult(
        pipeline="vsg",
        phase="phase_c",
        status="completed",
        execution_time_s=elapsed,
        output_summary={
            "style_guide_path": getattr(output, "style_guide_path", ""),
        },
    )


async def _run_ga_stage(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
    root: Path,
    session_factory: Optional[Any],
    parent_run_id: Optional[Any],
    company_id: Optional[Any],
    langsmith_project: Optional[str] = None,
) -> OnboardingSubResult:
    """Run Gap Analysis pipeline. Returns result."""
    from core.gap_analysis.pipeline import run_gap_analysis

    child_run_id = await _create_child_pipeline_run(
        session_factory, parent_run_id, company_id, slug, "gap_analysis",
        workspace_id=input_data.workspace_id,
    )

    start = time.time()
    try:
        ga_input = _build_ga_input(input_data, slug, constraints)
        output = await run_gap_analysis(
            ga_input,
            session_factory=session_factory,
            run_id=child_run_id or parent_run_id,
            company_id=company_id,
            langsmith_project=langsmith_project,
        )
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, summary={
            "gap_slug": getattr(output, "slug", ""),
        })
    except Exception as exc:
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, error=str(exc))
        raise
    return OnboardingSubResult(
        pipeline="ga",
        phase="phase_c",
        status="completed",
        execution_time_s=elapsed,
        output_summary={
            "gap_slug": getattr(output, "slug", ""),
        },
    )


async def _run_td_stage(
    input_data: OnboardingInput,
    slug: str,
    constraints: Optional[str],
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    root: Path,
    session_factory: Optional[Any],
    parent_run_id: Optional[Any],
    company_id: Optional[Any],
    langsmith_project: Optional[str] = None,
) -> OnboardingSubResult:
    """Run Topic Discovery pipeline. Returns result."""
    from core.topic_discovery.pipeline import run_topic_discovery_pipeline

    child_run_id = await _create_child_pipeline_run(
        session_factory, parent_run_id, company_id, slug, "topic_discovery",
        workspace_id=input_data.workspace_id,
    )

    start = time.time()
    try:
        td_input = _build_td_input(input_data, slug, constraints)
        output = await run_topic_discovery_pipeline(
            td_input,
            task_id=task_id,
            task_store=task_store,
            event_bus=event_bus,
            artifacts_root=root,
            session_factory=session_factory,
            run_id=child_run_id or parent_run_id,
            company_id=company_id,
            langsmith_project=langsmith_project,
        )
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, summary={
            "topic_count": getattr(output, "total_subdomains_discovered", 0),
        })
    except Exception as exc:
        elapsed = time.time() - start
        await _complete_child_pipeline_run(session_factory, child_run_id, error=str(exc))
        raise
    return OnboardingSubResult(
        pipeline="td",
        phase="phase_c",
        status="completed",
        execution_time_s=elapsed,
        output_summary={
            "topic_count": getattr(output, "total_subdomains_discovered", 0),
        },
    )


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_onboarding_pipeline(
    input_data: OnboardingInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
) -> OnboardingOutput:
    """Run the 3-phase onboarding orchestrator.

    Phase A: Site Audit + KB (parallel)
    Phase B: AP (sequential, after KB)
    Phase C: VSG + GA + TD (parallel, after AP)

    Calls sub-pipelines directly. Semaphore/slug-lock owned by caller.
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    slug = _resolve_slugs(input_data)
    constraints = _build_constraints(input_data)
    _ls_project = settings.onboarding_langsmith_project

    # Proxy rewrites sub-pipeline terminal events so they don't close SSE stream
    proxy_bus = _SubPipelineEventProxy(event_bus) if event_bus else None

    sub_results: Dict[str, OnboardingSubResult] = {}
    phases: Dict[str, OnboardingPhaseResult] = {}

    # Progress tracking — 6 sub-pipelines total
    _sub_done_count = 0
    _total_subs = 6  # SA, KB, AP, VSG, GA, TD

    def _emit_progress() -> None:
        nonlocal _sub_done_count
        _sub_done_count += 1
        pct = int((_sub_done_count / _total_subs) * 100)
        _emit(event_bus, task_id, "progress", {
            "progress_pct": pct,
            "message": f"{_sub_done_count}/{_total_subs} pipelines complete",
        })

    # Artifact paths
    audit_run_id: Optional[str] = None
    company_context_path: Optional[str] = None
    persona_dir: Optional[str] = None
    style_guide_path: Optional[str] = None
    gap_analysis_dir: Optional[str] = None
    topic_discovery_id: Optional[str] = None

    _emit(event_bus, task_id, "onboarding_start", {
        "pipeline": "onboarding",
        "phases": [p.value for p in input_data.phases],
    })
    _update_task(task_store, task_id, current_step="initializing")

    kb_succeeded = False
    ap_succeeded = False

    # =================================================================
    # PHASE A: Site Audit + KB (parallel)
    # =================================================================
    if OnboardingPhase.phase_a in input_data.phases:
        phase_a_start = time.time()
        _emit(event_bus, task_id, "onboarding_phase_start", {
            "phase": "phase_a", "pipelines": ["site_audit", "kb"],
        })
        _update_task(task_store, task_id, current_step="phase_a")

        # Launch SA as fire-and-forget task
        _emit(event_bus, task_id, "onboarding_sub_start", {
            "phase": "phase_a", "pipeline": "site_audit",
        })
        sa_task = asyncio.create_task(
            _run_site_audit_stage(
                input_data, slug, proxy_bus, task_id, root,
                session_factory=session_factory,
                parent_run_id=run_id,
                company_id=company_id,
            )
        )

        # Run KB (blocking)
        _emit(event_bus, task_id, "onboarding_sub_start", {
            "phase": "phase_a", "pipeline": "kb",
        })
        try:
            kb_result, kb_output = await _run_kb_stage(
                input_data, slug, constraints,
                task_id, task_store, proxy_bus,
                root, session_factory, run_id, company_id,
                langsmith_project=_ls_project,
            )
            sub_results["kb"] = kb_result
            kb_succeeded = True
            company_context_path = kb_result.output_summary.get(
                "company_profile_path"
            )
            _emit(event_bus, task_id, "onboarding_sub_complete", {
                "phase": "phase_a", "pipeline": "kb",
                "time_s": kb_result.execution_time_s,
            })
            _emit_progress()
        except Exception as exc:
            logger.exception("Onboarding: KB failed")
            sub_results["kb"] = OnboardingSubResult(
                pipeline="kb", phase="phase_a", status="failed",
                error=str(exc),
            )
            _emit(event_bus, task_id, "onboarding_sub_failed", {
                "phase": "phase_a", "pipeline": "kb", "error": str(exc),
            })
            _emit_progress()

        # Harvest SA result
        sa_result = await sa_task
        sub_results["site_audit"] = sa_result
        if sa_result.status == "completed":
            audit_run_id = sa_result.output_summary.get("audit_id")
            _emit(event_bus, task_id, "onboarding_sub_complete", {
                "phase": "phase_a", "pipeline": "site_audit",
                "time_s": sa_result.execution_time_s,
            })
        else:
            _emit(event_bus, task_id, "onboarding_sub_failed", {
                "phase": "phase_a", "pipeline": "site_audit",
                "error": sa_result.error or "",
            })
        _emit_progress()

        phase_a_time = time.time() - phase_a_start
        phase_a_status = "completed" if kb_succeeded else "failed"
        phases["phase_a"] = OnboardingPhaseResult(
            phase="phase_a",
            status=phase_a_status,
            pipelines={k: v for k, v in sub_results.items()
                       if v.phase == "phase_a"},
            execution_time_s=phase_a_time,
        )
        _emit(event_bus, task_id, "onboarding_phase_complete", {
            "phase": "phase_a", "status": phase_a_status,
            "time_s": phase_a_time,
        })

    # =================================================================
    # PHASE B: Audience Persona (sequential, after KB)
    # =================================================================
    if OnboardingPhase.phase_b in input_data.phases:
        if not kb_succeeded:
            phases["phase_b"] = OnboardingPhaseResult(
                phase="phase_b", status="skipped",
                error="KB failed — AP requires KB synthesis",
            )
            _emit(event_bus, task_id, "onboarding_phase_skipped", {
                "phase": "phase_b", "reason": "KB failed",
            })
        else:
            phase_b_start = time.time()
            _emit(event_bus, task_id, "onboarding_phase_start", {
                "phase": "phase_b", "pipelines": ["ap"],
            })
            _update_task(task_store, task_id, current_step="phase_b")
            _emit(event_bus, task_id, "onboarding_sub_start", {
                "phase": "phase_b", "pipeline": "ap",
            })

            try:
                ap_result, ap_output = await _run_ap_stage(
                    input_data, slug, constraints,
                    task_id, task_store, proxy_bus,
                    root, session_factory, run_id, company_id,
                    langsmith_project=_ls_project,
                )
                sub_results["ap"] = ap_result
                ap_succeeded = True
                persona_dir = ap_result.output_summary.get("persona_dir")
                _emit(event_bus, task_id, "onboarding_sub_complete", {
                    "phase": "phase_b", "pipeline": "ap",
                    "time_s": ap_result.execution_time_s,
                })
                _emit_progress()
            except Exception as exc:
                logger.exception("Onboarding: AP failed")
                sub_results["ap"] = OnboardingSubResult(
                    pipeline="ap", phase="phase_b", status="failed",
                    error=str(exc),
                )
                _emit(event_bus, task_id, "onboarding_sub_failed", {
                    "phase": "phase_b", "pipeline": "ap", "error": str(exc),
                })
                _emit_progress()

            phase_b_time = time.time() - phase_b_start
            phase_b_status = "completed" if ap_succeeded else "failed"
            phases["phase_b"] = OnboardingPhaseResult(
                phase="phase_b",
                status=phase_b_status,
                pipelines={k: v for k, v in sub_results.items()
                           if v.phase == "phase_b"},
                execution_time_s=phase_b_time,
            )
            _emit(event_bus, task_id, "onboarding_phase_complete", {
                "phase": "phase_b", "status": phase_b_status,
                "time_s": phase_b_time,
            })

    # =================================================================
    # PHASE C: VSG + GA + TD (parallel, after AP)
    # =================================================================
    if OnboardingPhase.phase_c in input_data.phases:
        if not kb_succeeded:
            phases["phase_c"] = OnboardingPhaseResult(
                phase="phase_c", status="skipped",
                error="KB failed — Phase C requires KB synthesis",
            )
            _emit(event_bus, task_id, "onboarding_phase_skipped", {
                "phase": "phase_c", "reason": "KB failed",
            })
        else:
            phase_c_start = time.time()
            phase_c_pipelines = ["vsg", "ga"]
            if ap_succeeded:
                phase_c_pipelines.append("td")

            _emit(event_bus, task_id, "onboarding_phase_start", {
                "phase": "phase_c", "pipelines": phase_c_pipelines,
            })
            _update_task(task_store, task_id, current_step="phase_c")

            # Launch parallel tasks
            common_kw = dict(
                input_data=input_data, slug=slug, constraints=constraints,
            )
            infra_kw = dict(
                task_id=task_id, task_store=task_store, event_bus=proxy_bus,
                root=root, session_factory=session_factory,
                parent_run_id=run_id, company_id=company_id,
                langsmith_project=_ls_project,
            )

            tasks: List[asyncio.Task] = []
            task_names: List[str] = []

            _emit(event_bus, task_id, "onboarding_sub_start", {
                "phase": "phase_c", "pipeline": "vsg",
            })
            tasks.append(asyncio.create_task(
                _run_vsg_stage(**common_kw, **infra_kw)
            ))
            task_names.append("vsg")

            _emit(event_bus, task_id, "onboarding_sub_start", {
                "phase": "phase_c", "pipeline": "ga",
            })
            tasks.append(asyncio.create_task(
                _run_ga_stage(
                    input_data=input_data, slug=slug, constraints=constraints,
                    root=root, session_factory=session_factory,
                    parent_run_id=run_id, company_id=company_id,
                    langsmith_project=_ls_project,
                )
            ))
            task_names.append("ga")

            if ap_succeeded:
                _emit(event_bus, task_id, "onboarding_sub_start", {
                    "phase": "phase_c", "pipeline": "td",
                })
                tasks.append(asyncio.create_task(
                    _run_td_stage(**common_kw, **infra_kw)
                ))
                task_names.append("td")

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, res in zip(task_names, results):
                if isinstance(res, BaseException):
                    tb_str = "".join(traceback.format_exception(type(res), res, res.__traceback__))
                    logger.error("Onboarding: %s failed\n%s", name, tb_str)
                    sub_results[name] = OnboardingSubResult(
                        pipeline=name, phase="phase_c", status="failed",
                        error=str(res),
                    )
                    _emit(event_bus, task_id, "onboarding_sub_failed", {
                        "phase": "phase_c", "pipeline": name,
                        "error": str(res),
                    })
                    _emit_progress()
                else:
                    sub_results[name] = res
                    if res.status == "completed":
                        _emit(event_bus, task_id, "onboarding_sub_complete", {
                            "phase": "phase_c", "pipeline": name,
                            "time_s": res.execution_time_s,
                        })
                        # Capture artifact paths
                        if name == "vsg":
                            style_guide_path = res.output_summary.get(
                                "style_guide_path"
                            )
                        elif name == "ga":
                            gap_analysis_dir = res.output_summary.get(
                                "gap_slug"
                            )
                        elif name == "td":
                            tc = res.output_summary.get("topic_count")
                            topic_discovery_id = str(tc) if tc is not None else None
                    else:
                        _emit(event_bus, task_id, "onboarding_sub_failed", {
                            "phase": "phase_c", "pipeline": name,
                            "error": res.error or "",
                        })
                    _emit_progress()

            phase_c_time = time.time() - phase_c_start
            phase_c_failed = any(
                sub_results.get(n, OnboardingSubResult()).status == "failed"
                for n in task_names
            )
            phase_c_status = "failed" if all(
                sub_results.get(n, OnboardingSubResult()).status == "failed"
                for n in task_names
            ) else ("completed" if not phase_c_failed else "completed")
            phases["phase_c"] = OnboardingPhaseResult(
                phase="phase_c",
                status=phase_c_status,
                pipelines={k: v for k, v in sub_results.items()
                           if v.phase == "phase_c"},
                execution_time_s=phase_c_time,
            )
            _emit(event_bus, task_id, "onboarding_phase_complete", {
                "phase": "phase_c", "status": phase_c_status,
                "time_s": phase_c_time,
            })

    # =================================================================
    # Terminal status
    # =================================================================
    total_time = time.time() - start_time

    # Determine overall status
    any_non_sa_failed = any(
        r.status == "failed" and r.pipeline != "site_audit"
        for r in sub_results.values()
    )
    if not kb_succeeded:
        onboarding_status = OnboardingStatus.failed
    elif any_non_sa_failed:
        onboarding_status = OnboardingStatus.completed_partial
    else:
        onboarding_status = OnboardingStatus.completed

    output = OnboardingOutput(
        slug=slug,
        company_name=input_data.company_name,
        onboarding_status=onboarding_status,
        phases=phases,
        sub_results=sub_results,
        total_execution_time_s=total_time,
        audit_run_id=audit_run_id,
        company_context_path=company_context_path,
        persona_dir=persona_dir,
        style_guide_path=style_guide_path,
        gap_analysis_dir=gap_analysis_dir,
        topic_discovery_id=topic_discovery_id,
    )

    terminal_event = "failed" if onboarding_status == OnboardingStatus.failed else "completed"
    _emit(event_bus, task_id, terminal_event, {
        "pipeline": "onboarding",
        "onboarding_status": onboarding_status.value,
    })

    return output
