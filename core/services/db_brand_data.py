"""DbBrandDataService — Postgres-backed implementation of BrandDataServiceProtocol.

Reads run history from pipeline_runs table via PipelineRepository.
Research artifacts remain filesystem-backed (markdown files are the source of truth).
"""
from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from api.schemas.brand_data import (
    ResearchArtifactsResponse,
    RunHistoryItem,
    RunHistoryResponse,
)
from core.db.enums import PipelineStatus, PipelineType
from core.db.repositories.pipeline_repo import PipelineRepository

# Map DB PipelineType → total steps (for progress bar)
_PIPELINE_TOTAL_STEPS: Dict[str, int] = {
    "gap_analysis": 8,
    "research": 3,
    "content": 4,
}

# Map DB statuses → frontend-compatible set
_STATUS_MAP: Dict[str, str] = {
    "pending": "running",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "failed",
}


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


def _format_duration(seconds: Optional[int]) -> str:
    """Convert duration_seconds to human-readable string."""
    if seconds is None or seconds <= 0:
        return ""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    return "<1m"


def _slug_to_company_name(slug: str) -> str:
    """Convert slug to display name: 'webflow' -> 'Webflow'."""
    base = slug.split("__")[0]
    return base.replace("-", " ").title()


class DbBrandDataService:
    """Postgres-backed brand data service.

    - ``get_research_artifacts`` delegates to filesystem (markdown source of truth)
    - ``get_run_history`` reads from pipeline_runs table
    """

    def __init__(
        self,
        pipeline_repo: PipelineRepository,
        artifacts_root: Path,
    ) -> None:
        self._pipeline_repo = pipeline_repo
        self._artifacts_root = artifacts_root

    # ── Research Artifacts (filesystem-backed) ───────────────────────

    async def get_research_artifacts(
        self, slug: str,
    ) -> ResearchArtifactsResponse:
        """Delegate to filesystem — markdown files are the source of truth."""
        from api.services.brand_data_service import get_research_artifacts

        return await asyncio.to_thread(
            get_research_artifacts, self._artifacts_root, slug,
        )

    # ── Run History (DB-backed) ──────────────────────────────────────

    async def get_run_history(
        self,
        slug: str,
        *,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> RunHistoryResponse:
        """Build run history from pipeline_runs table."""
        # Map pipeline filter string to PipelineType enum
        pipeline_type: PipelineType | None = None
        if pipeline:
            try:
                pipeline_type = PipelineType(pipeline)
            except ValueError:
                pass  # unknown pipeline type → skip filter

        # Map frontend status to DB status(es)
        db_status: PipelineStatus | None = None
        if status:
            # Reverse map: "running" → PipelineStatus.running
            # Note: "running" catches both 'running' and 'pending'
            status_mapping: Dict[str, PipelineStatus] = {
                "running": PipelineStatus.running,
                "completed": PipelineStatus.completed,
                "failed": PipelineStatus.failed,
            }
            db_status = status_mapping.get(status)

        runs = await self._pipeline_repo.list_runs_by_slug(
            slug,
            pipeline_type=pipeline_type,
            status=db_status,
            limit=limit,
        )

        company_name = _slug_to_company_name(slug)
        items: List[RunHistoryItem] = []

        for run in runs:
            # Duration
            duration = _format_duration(run.duration_seconds)

            # Pipeline type string
            pt_str = run.pipeline_type.value if run.pipeline_type else ""

            # Status mapping
            display_status = _STATUS_MAP.get(
                run.status.value if run.status else "running",
                "running",
            )

            # If frontend filter is "running", also include "pending" runs
            if status == "running" and run.status == PipelineStatus.pending:
                display_status = "running"

            # Extract metrics from summary JSONB
            summary: Dict[str, Any] = run.summary or {}
            spa_score = _safe_float(summary.get("spa_score"))
            total_queries = int(_safe_float(summary.get("total_queries")))
            total_citations = int(_safe_float(summary.get("total_citations")))

            # Steps completed from stages_executed array
            stages_executed = run.stages_executed or []
            steps_completed = len(stages_executed)
            total_steps = _PIPELINE_TOTAL_STEPS.get(pt_str, 0)

            # If completed, mark all steps done
            if run.status == PipelineStatus.completed:
                steps_completed = total_steps

            items.append(
                RunHistoryItem(
                    id=str(run.id),
                    pipeline=pt_str,
                    company=company_name,
                    company_slug=slug,
                    status=display_status,
                    started=run.created_at.isoformat() if run.created_at else "",
                    duration=duration,
                    queries=total_queries,
                    citations=total_citations,
                    spa_score=spa_score,
                    steps_completed=steps_completed,
                    total_steps=total_steps,
                )
            )

        return RunHistoryResponse(runs=items, total=len(items))
