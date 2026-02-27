"""Content data retrieval endpoints (Phase 3).

Serves content pipeline artifacts for the Content Pipeline workspace.
All data is read from ``artifacts/content/{slug}/`` JSON and stage files.

All endpoints require authentication and company membership.
"""
from __future__ import annotations

from pathlib import Path

from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.auth.dependencies import require_tenant
from api.dependencies import get_artifacts_root
from api.schemas.content_data import (
    ContentBriefDetailResponse,
    ContentBriefListResponse,
    StageContentResponse,
)
from api.services.content_data_service import (
    get_brief_detail,
    get_brief_stage_content,
    get_briefs,
)

router = APIRouter(
    prefix="/api/v1/companies/{slug}/content",
    tags=["content-data"],
)


def _effective(slug: str, product_slug: Optional[str]) -> str:
    """Compute effective artifact directory slug."""
    return f"{slug}__{product_slug}" if product_slug else slug


@router.get("/briefs", response_model=ContentBriefListResponse)
def list_briefs(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> ContentBriefListResponse:
    """List all content briefs with inferred statuses and eval scores."""
    return get_briefs(artifacts_root, _effective(slug, product_slug))


@router.get("/briefs/{brief_id}", response_model=ContentBriefDetailResponse)
def get_brief(
    slug: str,
    brief_id: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> ContentBriefDetailResponse:
    """Get full detail for a single content brief."""
    return get_brief_detail(artifacts_root, _effective(slug, product_slug), brief_id)


@router.get("/briefs/{brief_id}/{stage}", response_model=StageContentResponse)
def get_stage_content(
    slug: str,
    brief_id: str,
    stage: str,
    artifacts_root: Path = Depends(get_artifacts_root),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> StageContentResponse:
    """Get stage-specific file content for a brief.

    Valid stages: outline, draft, enriched, formatted, eval_history, final
    """
    return get_brief_stage_content(
        artifacts_root, _effective(slug, product_slug), brief_id, stage
    )
