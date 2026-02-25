"""Content data retrieval endpoints (Phase 3).

Serves content pipeline artifacts for the Content Pipeline workspace.
All data is read from ``artifacts/content/{slug}/`` JSON and stage files.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

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


@router.get("/briefs", response_model=ContentBriefListResponse)
def list_briefs(
    slug: str,
    artifacts_root: Path = Depends(get_artifacts_root),
) -> ContentBriefListResponse:
    """List all content briefs with inferred statuses and eval scores."""
    return get_briefs(artifacts_root, slug)


@router.get("/briefs/{brief_id}", response_model=ContentBriefDetailResponse)
def get_brief(
    slug: str,
    brief_id: str,
    artifacts_root: Path = Depends(get_artifacts_root),
) -> ContentBriefDetailResponse:
    """Get full detail for a single content brief."""
    return get_brief_detail(artifacts_root, slug, brief_id)


@router.get("/briefs/{brief_id}/{stage}", response_model=StageContentResponse)
def get_stage_content(
    slug: str,
    brief_id: str,
    stage: str,
    artifacts_root: Path = Depends(get_artifacts_root),
) -> StageContentResponse:
    """Get stage-specific file content for a brief.

    Valid stages: outline, draft, enriched, formatted, eval_history, final
    """
    return get_brief_stage_content(artifacts_root, slug, brief_id, stage)
