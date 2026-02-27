"""Brand Brain + Run History endpoints (Phase 4).

- GET /api/v1/companies/{slug}/research/artifacts
- GET /api/v1/companies/{slug}/runs

All endpoints require authentication and company membership.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.auth.dependencies import require_tenant
from api.dependencies import get_artifacts_root, get_task_store
from api.schemas.brand_data import (
    ResearchArtifactsResponse,
    RunHistoryResponse,
)
from api.services.brand_data_service import (
    get_research_artifacts,
    get_run_history,
)
from api.tasks.store import TaskStore

router = APIRouter(
    prefix="/api/v1/companies/{slug}",
    tags=["brand-data"],
)


@router.get("/research/artifacts", response_model=ResearchArtifactsResponse)
def get_brand_research_artifacts(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    _access=Depends(require_tenant),
) -> ResearchArtifactsResponse:
    """Research artifacts (company context, personas, style guide) with content."""
    return get_research_artifacts(artifacts_root, slug)


@router.get("/runs", response_model=RunHistoryResponse)
def get_company_runs(
    slug: str,
    task_store: TaskStore = Depends(get_task_store),
    pipeline: Optional[str] = Query(None, description="Filter by pipeline type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    _access=Depends(require_tenant),
) -> RunHistoryResponse:
    """Run history across all pipelines for a company."""
    return get_run_history(
        task_store, slug, pipeline=pipeline, status=status, limit=limit
    )
