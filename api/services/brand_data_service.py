"""Service layer for Brand Brain + Run History endpoints (Phase 4).

Follows the same patterns as gap_data_service.py and content_data_service.py:
- Module-level TTL-based cache with FIFO eviction
- Slug validation via regex
- Path traversal protection via is_relative_to
- Service functions return data; routers handle HTTP concerns
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.storage.backends.base import StorageBackend

from fastapi import HTTPException

from api.schemas.brand_data import (
    ArtifactContent,
    PersonaArtifact,
    ResearchArtifactsResponse,
    RunHistoryItem,
    RunHistoryResponse,
    SPATrendPoint,
    SPATrendResponse,
)
from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.store import TaskStore

logger = logging.getLogger(__name__)

# ── Caching (Redis-backed, Session 6) ────────────────────────────────

from core.cache import cache_get, cache_set
from core.redis import get_sync_redis_or_none

# ── Validation ───────────────────────────────────────────────────────

# Accepts bare company slugs ("ramp") and effective product slugs ("ramp__card")
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")


def _validate_slug(slug: str) -> None:
    """Validate slug format. Raises HTTPException(400) for invalid slugs."""
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")


# ── Numeric safety ───────────────────────────────────────────────────


def _safe_float(val: Any) -> float:
    """Convert to float, returning 0.0 for NaN/Inf/None/non-numeric."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


# ── File utilities ───────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 1: Research Artifacts
# ══════════════════════════════════════════════════════════════════════


def _detect_artifact(
    artifacts_root: Path, type_name: str, slug: str,
    *, backend: Optional[StorageBackend] = None,
) -> ArtifactContent:
    """Detect artifact status and read content.

    Checks {slug}.md (approved) first, then {slug}.draft.md (draft).
    Returns ArtifactContent with content, status, updated_at.
    """
    from core.storage.backends.local import LocalStorageBackend
    _backend = backend or LocalStorageBackend(artifacts_root)
    content = _backend.read(f"{type_name}/{slug}.md")
    if content is not None:
        return ArtifactContent(content=content, status="approved", updated_at=None)
    content = _backend.read(f"{type_name}/{slug}.draft.md")
    if content is not None:
        return ArtifactContent(content=content, status="draft", updated_at=None)
    return ArtifactContent()


def _detect_personas(
    artifacts_root: Path, slug: str,
    *, backend: Optional[StorageBackend] = None,
) -> List[PersonaArtifact]:
    """Find all persona profiles for a slug, read content, detect status."""
    from core.storage.backends.local import LocalStorageBackend
    _backend = backend or LocalStorageBackend(artifacts_root)
    try:
        from core.research.audience_persona.storage import PersonaStorage
        ap_storage = PersonaStorage(artifacts_root, slug, backend=_backend)
        manifest = ap_storage.read_manifest()
        if not manifest.personas:
            return []
        personas: List[PersonaArtifact] = []
        for pid, entry in manifest.personas.items():
            if entry.status not in ("fresh", "stale") or entry.current_version == 0:
                continue
            key = f"audience_personas/{slug}/{pid}/v{entry.current_version}.md"
            content = _backend.read(key)
            if content is None:
                continue
            personas.append(PersonaArtifact(
                id=pid,
                name=entry.persona_name or pid.replace("-", " ").title(),
                type=entry.kind,
                content=content,
                status="approved",
                updated_at=entry.last_updated.isoformat() if entry.last_updated else None,
            ))
        return personas
    except Exception:
        logger.debug("audience_personas/ lookup failed for %s", slug)
        return []


def get_research_artifacts(
    artifacts_root: Path, slug: str,
    *, backend: Optional[StorageBackend] = None,
) -> ResearchArtifactsResponse:
    """Build research artifacts response — Redis cache first, compute fallback."""
    _validate_slug(slug)

    redis = get_sync_redis_or_none()
    if redis is not None:
        cached = cache_get(redis, f"cache:brand:{slug}:artifacts")
        if cached is not None:
            try:
                return ResearchArtifactsResponse.model_validate(cached)
            except Exception:
                logger.debug("Corrupted brand cache for %s — recomputing", slug)

    company_context = _detect_artifact(artifacts_root, "company_context", slug, backend=backend)
    style_guide = _detect_artifact(artifacts_root, "style_guides", slug, backend=backend)
    personas = _detect_personas(artifacts_root, slug, backend=backend)

    result = ResearchArtifactsResponse(
        company_context=company_context,
        personas=personas,
        style_guide=style_guide,
    )

    if redis is not None:
        cache_set(redis, f"cache:brand:{slug}:artifacts", result.model_dump(mode="json"), ttl=300)

    return result


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 2: Run History
# ══════════════════════════════════════════════════════════════════════

_PIPELINE_TOTAL_STEPS: Dict[str, int] = {
    "gap_analysis": 8,
    "content": 4,
}

_GAP_STEP_MAP: Dict[str, int] = {
    "s1_embed_assets": 1,
    "s2_generate_queries": 2,
    "s3_search_platforms": 3,
    "s4_enrich_citations": 4,
    "s5_embed_content": 5,
    "s6_analyze": 6,
    "s7_visualize": 7,
    "s8_generate_report": 8,
}

# Map backend statuses to frontend-compatible set (Codex finding #4)
_STATUS_MAP: Dict[str, str] = {
    "running": "running",
    "pending_approval": "running",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "failed",
    "failed_restart": "failed",
}


def _format_duration(created_at: datetime, updated_at: datetime) -> str:
    """Compute human-readable duration string.

    Returns '' if times are equal or updated_at <= created_at.
    Returns '3h 46m' for multi-hour, '23m' for under 1 hour, '<1m' for very short.
    """
    delta = updated_at - created_at
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return ""

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "<1m"


def _infer_steps_completed(task: PipelineTask) -> int:
    """Infer steps completed from current_step string or task status."""
    pipeline = task.pipeline
    total = _PIPELINE_TOTAL_STEPS.get(pipeline, 0)

    # If completed, all steps done
    if task.status == TaskStatus.COMPLETED:
        return total

    step = task.current_step
    if not step:
        return 0

    if pipeline == "gap_analysis":
        return _GAP_STEP_MAP.get(step, 0)
    elif pipeline == "content":
        # Content steps are "stage 1" .. "stage 4"
        try:
            return int(step.split()[-1])
        except (ValueError, IndexError):
            return 0

    return 0


def _extract_gap_metrics(
    result: Optional[Dict[str, Any]],
) -> Tuple[float, int, int]:
    """Extract (spa_score, total_queries, total_citations) from task.result.

    Returns (0.0, 0, 0) if any extraction fails.
    """
    if not result:
        return 0.0, 0, 0

    report_json = result.get("report_json")
    if not isinstance(report_json, dict):
        return 0.0, 0, 0

    # SPA score from spa_results[0].t_stat
    spa_score = 0.0
    spa_results = report_json.get("spa_results")
    if isinstance(spa_results, list) and len(spa_results) > 0:
        first = spa_results[0]
        if isinstance(first, dict):
            spa_score = _safe_float(first.get("t_stat"))

    # Queries and citations from decision_metrics
    dm = report_json.get("decision_metrics")
    total_queries = 0
    total_citations = 0
    if isinstance(dm, dict):
        total_queries = int(_safe_float(dm.get("total_queries")))
        total_citations = int(_safe_float(dm.get("total_citations")))

    return spa_score, total_queries, total_citations


def _slug_to_company_name(slug: str) -> str:
    """Convert slug to display name: 'webflow' -> 'Webflow'."""
    return slug.replace("-", " ").title()


def get_run_history(
    task_store: TaskStore,
    slug: str,
    *,
    pipeline: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> RunHistoryResponse:
    """Build run history response from TaskStore.

    Filters by company_slug, optional pipeline and status.
    Results sorted by started descending (most recent first).
    """
    _validate_slug(slug)

    tasks = task_store.list_tasks(company_slug=slug)

    # Apply optional filters
    if pipeline:
        tasks = [t for t in tasks if t.pipeline == pipeline]
    if status:
        # Filter on mapped status so ?status=running catches pending_approval too
        tasks = [
            t for t in tasks
            if _STATUS_MAP.get(t.status.value, t.status.value) == status
        ]

    # Sort by created_at descending (most recent first)
    tasks.sort(key=lambda t: t.created_at, reverse=True)

    # Apply limit
    if limit > 0:
        tasks = tasks[:limit]

    company_name = _slug_to_company_name(slug)
    runs: List[RunHistoryItem] = []

    for task in tasks:
        # Determine if the task is terminal (has a final duration)
        is_terminal = task.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED_RESTART,
        )

        duration = _format_duration(task.created_at, task.updated_at) if is_terminal else ""

        # Extract gap-specific metrics
        spa_score, queries, citations = (
            _extract_gap_metrics(task.result)
            if task.pipeline == "gap_analysis"
            else (0.0, 0, 0)
        )

        steps_completed = _infer_steps_completed(task)
        total_steps = _PIPELINE_TOTAL_STEPS.get(task.pipeline, 0)

        # Map status to frontend-compatible set (Codex finding #4)
        display_status = _STATUS_MAP.get(task.status.value, task.status.value)

        runs.append(
            RunHistoryItem(
                id=task.task_id,
                pipeline=task.pipeline,
                company=company_name,
                company_slug=slug,
                status=display_status,
                started=task.created_at.isoformat(),
                duration=duration,
                queries=queries,
                citations=citations,
                spa_score=spa_score,
                steps_completed=steps_completed,
                total_steps=total_steps,
            )
        )

    return RunHistoryResponse(runs=runs, total=len(runs))


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 3: SPA Score Trend
# ══════════════════════════════════════════════════════════════════════


def get_spa_trend(
    task_store: TaskStore,
    slug: str,
) -> SPATrendResponse:
    """Build SPA score trend from completed gap analysis runs.

    Sorted by created_at ascending (oldest first for chart x-axis).
    Skips runs without extractable SPA metrics.
    """
    _validate_slug(slug)

    # Handle product-level effective slugs (e.g. "ramp__card").
    # list_tasks() supports filtering by both company_slug and product_slug,
    # so we split and use both filters to return only the correct scope.
    if "__" in slug:
        parts = slug.split("__", 1)
        tasks = task_store.list_tasks(
            pipeline="gap_analysis",
            status="completed",
            company_slug=parts[0],
            product_slug=parts[1],
        )
    else:
        # Company-level: explicitly exclude product-scoped runs so product
        # runs don't pollute the company-level trend chart.
        all_tasks = task_store.list_tasks(
            pipeline="gap_analysis",
            status="completed",
            company_slug=slug,
        )
        tasks = [t for t in all_tasks if t.product_slug is None]

    # Sort ascending (oldest first for chart)
    tasks.sort(key=lambda t: t.created_at)

    points: List[SPATrendPoint] = []

    for task in tasks:
        if not task.result:
            continue

        report_json = task.result.get("report_json")
        if not isinstance(report_json, dict):
            continue

        spa_results = report_json.get("spa_results")
        if not isinstance(spa_results, list) or len(spa_results) == 0:
            continue

        first_spa = spa_results[0]
        if not isinstance(first_spa, dict):
            continue

        spa_score = _safe_float(first_spa.get("t_stat"))
        mean_citation = _safe_float(first_spa.get("mean_citation_similarity"))
        mean_company = _safe_float(first_spa.get("mean_company_similarity"))

        dm = report_json.get("decision_metrics", {})
        total_queries = int(_safe_float(dm.get("total_queries")))
        total_citations = int(_safe_float(dm.get("total_citations")))

        # Short date label for chart x-axis
        run_label = task.created_at.strftime("%b %d")
        # Remove leading zero: "Feb 06" -> "Feb 6"
        parts = run_label.split()
        if len(parts) == 2 and parts[1].startswith("0"):
            run_label = f"{parts[0]} {parts[1].lstrip('0')}"

        points.append(
            SPATrendPoint(
                run_id=task.task_id,
                run=run_label,
                timestamp=task.created_at.isoformat(),
                spa_score=spa_score,
                citation_advantage=round(mean_citation - mean_company, 6),
                company_advantage=round(mean_company - mean_citation, 6),
                total_queries=total_queries,
                total_citations=total_citations,
            )
        )

    return SPATrendResponse(trend=points)
