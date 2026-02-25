"""Service layer for Brand Brain + Run History endpoints (Phase 4).

Follows the same patterns as gap_data_service.py and content_data_service.py:
- Module-level mtime-based cache with FIFO eviction
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

# ── Caching ──────────────────────────────────────────────────────────

_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10

# ── Validation ───────────────────────────────────────────────────────

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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


def _mtime_iso(path: Path) -> Optional[str]:
    """Get file mtime as ISO8601 string, or None if file doesn't exist."""
    try:
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return dt.isoformat()
    except (OSError, ValueError):
        return None


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 1: Research Artifacts
# ══════════════════════════════════════════════════════════════════════


def _detect_artifact(
    artifacts_root: Path, type_name: str, slug: str
) -> ArtifactContent:
    """Detect artifact status and read content.

    Checks {slug}.md (approved) first, then {slug}.draft.md (draft).
    Returns ArtifactContent with content, status, updated_at.
    """
    type_dir = artifacts_root / type_name
    if not type_dir.is_dir():
        return ArtifactContent()

    approved_path = type_dir / f"{slug}.md"
    draft_path = type_dir / f"{slug}.draft.md"

    # Path traversal protection
    for p in (approved_path, draft_path):
        if not p.is_relative_to(type_dir):
            return ArtifactContent()

    if approved_path.is_file():
        try:
            content = approved_path.read_text(encoding="utf-8")
            return ArtifactContent(
                content=content,
                status="approved",
                updated_at=_mtime_iso(approved_path),
            )
        except OSError:
            logger.warning("Failed to read %s", approved_path)
            return ArtifactContent()

    if draft_path.is_file():
        try:
            content = draft_path.read_text(encoding="utf-8")
            return ArtifactContent(
                content=content,
                status="draft",
                updated_at=_mtime_iso(draft_path),
            )
        except OSError:
            logger.warning("Failed to read %s", draft_path)
            return ArtifactContent()

    return ArtifactContent()


def _detect_personas(
    artifacts_root: Path, slug: str
) -> List[PersonaArtifact]:
    """Find all persona files for a slug, read content, detect status.

    Pattern: {slug}__persona-{id}.md (approved) or
             {slug}__persona-{id}.draft.md (draft)
    """
    personas_dir = artifacts_root / "personas"
    if not personas_dir.is_dir():
        return []

    prefix = f"{slug}__"
    # Collect approved and draft files, keyed by persona_id
    approved_files: Dict[str, Path] = {}
    draft_files: Dict[str, Path] = {}

    for f in sorted(personas_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if not f.name.startswith(prefix):
            continue

        # Path traversal protection
        if not f.is_relative_to(personas_dir):
            continue

        # Extract persona ID — only accept persona-* files (Codex CX-4)
        suffix = f.name[len(prefix):]  # e.g., "persona-icp.md" or "persona-icp.draft.md"
        if not suffix.startswith("persona-"):
            continue

        if suffix.endswith(".draft.md"):
            persona_id = suffix[:-len(".draft.md")]
            draft_files[persona_id] = f
        elif suffix.endswith(".md"):
            persona_id = suffix[:-len(".md")]
            approved_files[persona_id] = f

    # Merge: approved wins over draft
    all_ids = sorted(set(approved_files.keys()) | set(draft_files.keys()))
    personas: List[PersonaArtifact] = []

    for persona_id in all_ids:
        if persona_id in approved_files:
            path = approved_files[persona_id]
            status = "approved"
        else:
            path = draft_files[persona_id]
            status = "draft"

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Failed to read persona file %s", path)
            continue

        # Type: "icp" if "icp" appears in the persona_id
        persona_type = "icp" if "icp" in persona_id else "secondary"

        # Name: title-case the id, replacing hyphens with spaces
        name = persona_id.replace("-", " ").title()

        personas.append(
            PersonaArtifact(
                id=persona_id,
                name=name,
                type=persona_type,
                content=content,
                status=status,
                updated_at=_mtime_iso(path),
            )
        )

    return personas


def get_research_artifacts(
    artifacts_root: Path, slug: str
) -> ResearchArtifactsResponse:
    """Build research artifacts response with content and status."""
    _validate_slug(slug)

    company_context = _detect_artifact(artifacts_root, "company_context", slug)
    style_guide = _detect_artifact(artifacts_root, "style_guides", slug)
    personas = _detect_personas(artifacts_root, slug)

    return ResearchArtifactsResponse(
        company_context=company_context,
        personas=personas,
        style_guide=style_guide,
    )


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 2: Run History
# ══════════════════════════════════════════════════════════════════════

_PIPELINE_TOTAL_STEPS: Dict[str, int] = {
    "gap_analysis": 8,
    "research": 3,
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

_RESEARCH_STEP_MAP: Dict[str, int] = {
    "company": 1,
    "persona": 2,
    "style_guide": 3,
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
    elif pipeline == "research":
        return _RESEARCH_STEP_MAP.get(step, 0)
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

    tasks = task_store.list_tasks(
        pipeline="gap_analysis",
        status="completed",
        company_slug=slug,
    )

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
