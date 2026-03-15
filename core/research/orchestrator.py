"""Research Orchestrator — KB → AP → VSG sequential DAG.

Thin coordinator that runs three research pipelines in order:
  1. Knowledge Base (KB) — company context + agent docs
  2. Audience Persona (AP) — persona profiles (depends on KB)
  3. Voice Style Guide (VSG) — style guide (depends on KB + AP)

Each sub-pipeline is called directly (not via runner wrappers) so
the orchestrator owns the single semaphore/slug-lock scope.
HITL checkpoints work transparently through shared task_id.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.models.research_orchestrator import (
    OrchestratorStatus,
    ResearchOrchestratorInput,
    ResearchOrchestratorOutput,
    SubPipelineResult,
    SubPipelineStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Null-safe helpers (same pattern as KB/AP/VSG pipelines)
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


def _resolve_slugs(
    input_data: ResearchOrchestratorInput,
) -> Tuple[str, str]:
    """Return (company_slug, effective_slug) from orchestrator input."""
    from core.auth.utils.domain import derive_slug

    company_slug = input_data.company_slug or derive_slug(input_data.company_name)
    if input_data.product_slug:
        effective_slug = f"{company_slug}__{input_data.product_slug}"
    else:
        effective_slug = company_slug
    return company_slug, effective_slug


# ---------------------------------------------------------------------------
# Skip-logic helpers
# ---------------------------------------------------------------------------


def _should_skip_kb(
    root: Path,
    effective_slug: str,
    force_rerun: bool,
    skip_if_fresh: bool,
) -> Tuple[bool, Optional[str]]:
    """Check if KB can be skipped (synthesis exists and all docs fresh)."""
    if force_rerun or not skip_if_fresh:
        return False, None
    try:
        from core.research.knowledge_base.storage import KBStorage

        storage = KBStorage(root, effective_slug)
        manifest = storage.read_manifest()
        if manifest.synthesis_version > 0:
            report = storage.get_staleness_report()
            if not report.stale_docs and not report.missing_docs:
                return True, (
                    f"KB is fresh (synthesis v{manifest.synthesis_version}, "
                    f"0 stale docs)"
                )
    except Exception:
        logger.debug("KB skip check failed — will run KB", exc_info=True)
    return False, None


def _should_skip_ap(
    root: Path,
    effective_slug: str,
    company_slug: str,
    force_rerun: bool,
    skip_if_fresh: bool,
) -> Tuple[bool, Optional[str]]:
    """Check if AP can be skipped (personas exist and KB unchanged)."""
    if force_rerun or not skip_if_fresh:
        return False, None
    try:
        from core.research.audience_persona.storage import PersonaStorage
        from core.research.knowledge_base.storage import KBStorage

        persona_storage = PersonaStorage(root, effective_slug)
        manifest = persona_storage.read_manifest()
        approved = sum(
            1
            for e in manifest.personas.values()
            if e.status in ("fresh", "stale")
        )
        if approved == 0:
            return False, None

        # Check if KB has been updated since last AP run
        kb_storage = KBStorage(root, effective_slug)
        kb_manifest = kb_storage.read_manifest()
        ap_kb_version = manifest.kb_synthesis_version or 0
        if kb_manifest.synthesis_version > ap_kb_version:
            return False, None  # KB updated → must re-run AP

        return True, (
            f"AP has {approved} approved personas, "
            f"KB unchanged (v{kb_manifest.synthesis_version})"
        )
    except Exception:
        logger.debug("AP skip check failed — will run AP", exc_info=True)
    return False, None


def _should_skip_vsg(
    root: Path,
    effective_slug: str,
    company_slug: str,
    force_rerun: bool,
    skip_if_fresh: bool,
) -> Tuple[bool, Optional[str]]:
    """Check if VSG can be skipped (guide fresh and AP unchanged)."""
    if force_rerun or not skip_if_fresh:
        return False, None
    try:
        from core.research.voice_style_guide.storage import VoiceStyleGuideStorage

        vsg_storage = VoiceStyleGuideStorage(root, effective_slug)
        manifest = vsg_storage.read_manifest()
        if manifest.guide.current_version <= 0 or manifest.guide.status != "fresh":
            return False, None

        # Check if AP has been updated since last VSG run
        from core.research.audience_persona.storage import PersonaStorage

        persona_storage = PersonaStorage(root, effective_slug)
        ap_manifest = persona_storage.read_manifest()
        if ap_manifest.personas:
            # Compare AP manifest fingerprint (last_full_run timestamp)
            ap_run_ts = (
                ap_manifest.last_full_run.isoformat()
                if ap_manifest.last_full_run
                else ""
            )
            vsg_ap_version = manifest.ap_manifest_version or ""
            if ap_run_ts and ap_run_ts != vsg_ap_version:
                return False, None  # AP updated → must re-run VSG

        return True, (
            f"VSG guide is fresh (v{manifest.guide.current_version})"
        )
    except Exception:
        logger.debug("VSG skip check failed — will run VSG", exc_info=True)
    return False, None


# ---------------------------------------------------------------------------
# Input construction helpers
# ---------------------------------------------------------------------------


def _build_kb_input(
    input_data: ResearchOrchestratorInput,
    effective_slug: str,
) -> Any:
    """Build KnowledgeBaseInput from orchestrator input."""
    from core.models.knowledge_base import KnowledgeBaseInput

    return KnowledgeBaseInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=effective_slug,
        product_slug=input_data.product_slug,
        product_name=input_data.product_name,
        seed_urls=input_data.seed_urls,
        internal_sources=input_data.internal_sources,
        staleness_threshold_days=input_data.staleness_threshold_days,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=input_data.additional_constraints,
        auto_approve_checkpoints=input_data.auto_approve.kb,
    )


def _build_ap_input(
    input_data: ResearchOrchestratorInput,
    company_slug: str,
) -> Any:
    """Build AudiencePersonaInput from orchestrator input."""
    from core.models.audience_persona import AudiencePersonaInput

    return AudiencePersonaInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=company_slug,
        product_slug=input_data.product_slug,
        product_name=input_data.product_name,
        max_personas=input_data.max_personas,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=input_data.additional_constraints,
        auto_approve_checkpoints=input_data.auto_approve.ap,
    )


def _build_vsg_input(
    input_data: ResearchOrchestratorInput,
    company_slug: str,
) -> Any:
    """Build VoiceStyleGuideInput from orchestrator input."""
    from core.models.voice_style_guide import VoiceStyleGuideInput

    return VoiceStyleGuideInput(
        company_name=input_data.company_name,
        domain=input_data.domain or None,
        company_slug=company_slug,
        product_slug=input_data.product_slug,
        product_name=input_data.product_name,
        max_authors=input_data.max_authors,
        language=input_data.language,
        region=input_data.region,
        additional_constraints=input_data.additional_constraints,
        auto_approve_checkpoints=input_data.auto_approve.vsg,
    )


# ---------------------------------------------------------------------------
# Sub-pipeline output summarizers
# ---------------------------------------------------------------------------


def _summarize_kb_output(output: Any) -> Dict[str, Any]:
    return {
        "synthesis_word_count": (
            len(output.synthesis_md.split()) if output.synthesis_md else 0
        ),
        "agent_count": len(output.agent_results),
        "company_profile_path": output.company_profile_path,
    }


def _summarize_ap_output(output: Any) -> Dict[str, Any]:
    return {
        "briefs_suggested": output.briefs_suggested,
        "briefs_approved": output.briefs_approved,
        "profiles_generated": output.profiles_generated,
        "persona_dir": output.persona_dir,
    }


def _summarize_vsg_output(output: Any) -> Dict[str, Any]:
    return {
        "authors_discovered": output.authors_discovered,
        "authors_approved": output.authors_approved,
        "authors_researched": output.authors_researched,
        "guide_generated": output.guide_generated,
        "style_guide_path": output.style_guide_path,
    }


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_research_orchestrator(
    input_data: ResearchOrchestratorInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
) -> ResearchOrchestratorOutput:
    """Run the KB → AP → VSG orchestrator.

    Calls each sub-pipeline directly (not via runner wrappers).
    Semaphore and slug-lock are owned by the caller (runner).
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    company_slug, effective_slug = _resolve_slugs(input_data)

    # Proxy rewrites sub-pipeline terminal events so they don't close SSE stream
    proxy_bus = _SubPipelineEventProxy(event_bus) if event_bus else None

    sub_results: Dict[str, SubPipelineResult] = {}
    pipelines_run: List[str] = []
    pipelines_skipped: List[str] = []

    # Artifact paths (populated as pipelines complete)
    company_context_path: Optional[str] = None
    persona_dir: Optional[str] = None
    style_guide_path: Optional[str] = None

    _emit(event_bus, task_id, "pipeline_start", {
        "pipeline": "research_orchestrator",
        "pipelines_requested": input_data.pipelines,
    })
    _update_task(task_store, task_id, current_step="initializing")

    # Ordered pipeline definitions
    pipeline_defs = [
        ("kb", _should_skip_kb, _run_kb_stage),
        ("ap", _should_skip_ap, _run_ap_stage),
        ("vsg", _should_skip_vsg, _run_vsg_stage),
    ]

    failed = False
    position = 0

    for name, skip_fn, run_fn in pipeline_defs:
        if name not in input_data.pipelines:
            continue

        position += 1

        # --- Skip check ---
        if name == "kb":
            should_skip, skip_reason = skip_fn(
                root, effective_slug,
                input_data.force_rerun,
                input_data.skip_config.skip_kb_if_fresh,
            )
        elif name == "ap":
            should_skip, skip_reason = skip_fn(
                root, effective_slug, company_slug,
                input_data.force_rerun,
                input_data.skip_config.skip_ap_if_fresh,
            )
        else:  # vsg
            should_skip, skip_reason = skip_fn(
                root, effective_slug, company_slug,
                input_data.force_rerun,
                input_data.skip_config.skip_vsg_if_fresh,
            )

        if should_skip:
            _emit(event_bus, task_id, "orchestrator_stage_skipped", {
                "stage": name, "reason": skip_reason, "position": position,
            })
            sub_results[name] = SubPipelineResult(
                pipeline=name,
                status=SubPipelineStatus.skipped,
                skip_reason=skip_reason,
            )
            pipelines_skipped.append(name)
            logger.info("Orchestrator: skipping %s — %s", name, skip_reason)
            continue

        # --- Run ---
        _emit(event_bus, task_id, "orchestrator_stage_start", {
            "stage": name, "position": position,
        })
        _update_task(task_store, task_id, current_step=name)
        stage_start = time.time()

        try:
            output, summary = await run_fn(
                input_data=input_data,
                company_slug=company_slug,
                effective_slug=effective_slug,
                root=root,
                task_id=task_id,
                task_store=task_store,
                event_bus=proxy_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )
            stage_time = time.time() - stage_start

            sub_results[name] = SubPipelineResult(
                pipeline=name,
                status=SubPipelineStatus.completed,
                execution_time_s=stage_time,
                output_summary=summary,
            )
            pipelines_run.append(name)

            # Capture artifact paths
            if name == "kb" and output:
                company_context_path = getattr(output, "company_profile_path", None)
            elif name == "ap" and output:
                persona_dir = getattr(output, "persona_dir", None)
            elif name == "vsg" and output:
                style_guide_path = getattr(output, "style_guide_path", None)

            _emit(event_bus, task_id, "orchestrator_stage_complete", {
                "stage": name, "execution_time_s": stage_time,
            })

        except Exception as exc:
            stage_time = time.time() - stage_start
            logger.exception("Orchestrator: %s failed", name)
            sub_results[name] = SubPipelineResult(
                pipeline=name,
                status=SubPipelineStatus.failed,
                execution_time_s=stage_time,
                error=str(exc),
            )
            _emit(event_bus, task_id, "orchestrator_stage_failed", {
                "stage": name, "error": str(exc),
            })
            failed = True
            break  # Stop — downstream pipelines depend on this

    # Determine terminal status
    if failed:
        orchestrator_status = OrchestratorStatus.failed
    elif pipelines_skipped:
        orchestrator_status = OrchestratorStatus.completed_partial
    else:
        orchestrator_status = OrchestratorStatus.completed

    total_time = time.time() - start_time

    output = ResearchOrchestratorOutput(
        slug=company_slug,
        company_name=input_data.company_name,
        effective_slug=effective_slug,
        orchestrator_status=orchestrator_status,
        pipelines_run=pipelines_run,
        pipelines_skipped=pipelines_skipped,
        sub_results=sub_results,
        total_execution_time_s=total_time,
        company_context_path=company_context_path,
        persona_dir=persona_dir,
        style_guide_path=style_guide_path,
    )

    # Emit correct terminal event — "failed" for soft-failures, "completed" otherwise
    terminal_event = "failed" if failed else "completed"
    _emit(event_bus, task_id, terminal_event, {
        "pipeline": "research_orchestrator",
        "orchestrator_status": orchestrator_status.value,
        "pipelines_run": pipelines_run,
        "pipelines_skipped": pipelines_skipped,
    })

    return output


# ---------------------------------------------------------------------------
# Stage runners (thin wrappers around sub-pipeline calls)
# ---------------------------------------------------------------------------


async def _run_kb_stage(
    *,
    input_data: ResearchOrchestratorInput,
    company_slug: str,
    effective_slug: str,
    root: Path,
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    session_factory: Optional[Any],
    run_id: Optional[Any],
    company_id: Optional[Any],
) -> Tuple[Any, Dict[str, Any]]:
    from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

    kb_input = _build_kb_input(input_data, effective_slug)
    output = await run_knowledge_base_pipeline(
        kb_input,
        task_id=task_id,
        task_store=task_store,
        event_bus=event_bus,
        artifacts_root=root,
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
    )
    return output, _summarize_kb_output(output)


async def _run_ap_stage(
    *,
    input_data: ResearchOrchestratorInput,
    company_slug: str,
    effective_slug: str,
    root: Path,
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    session_factory: Optional[Any],
    run_id: Optional[Any],
    company_id: Optional[Any],
) -> Tuple[Any, Dict[str, Any]]:
    from core.research.audience_persona.pipeline import run_audience_persona_pipeline

    ap_input = _build_ap_input(input_data, company_slug)
    output = await run_audience_persona_pipeline(
        ap_input,
        task_id=task_id,
        task_store=task_store,
        event_bus=event_bus,
        artifacts_root=root,
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
    )
    return output, _summarize_ap_output(output)


async def _run_vsg_stage(
    *,
    input_data: ResearchOrchestratorInput,
    company_slug: str,
    effective_slug: str,
    root: Path,
    task_id: Optional[str],
    task_store: Optional[Any],
    event_bus: Optional[Any],
    session_factory: Optional[Any],
    run_id: Optional[Any],
    company_id: Optional[Any],
) -> Tuple[Any, Dict[str, Any]]:
    from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

    vsg_input = _build_vsg_input(input_data, company_slug)
    output = await run_voice_style_guide_pipeline(
        vsg_input,
        task_id=task_id,
        task_store=task_store,
        event_bus=event_bus,
        artifacts_root=root,
        session_factory=session_factory,
        run_id=run_id,
        company_id=company_id,
    )
    return output, _summarize_vsg_output(output)
