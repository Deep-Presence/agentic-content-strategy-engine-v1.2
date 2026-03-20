"""Content data retrieval endpoints.

Serves content pipeline artifacts for the Content Pipeline workspace.
All endpoints require authentication and company membership.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.auth.dependencies import require_tenant
from api.dependencies import get_content_data_service
from api.schemas.content_data import (
    AddBriefRequest,
    ContentBriefDetailResponse,
    ContentBriefListItem,
    ContentBriefListResponse,
    StageContentResponse,
)
from core.services.content_data import ContentDataServiceProtocol

router = APIRouter(
    prefix="/api/v1/companies/{slug}/content",
    tags=["content-data"],
)


def _effective(slug: str, product_slug: Optional[str]) -> str:
    """Compute effective artifact directory slug."""
    return f"{slug}__{product_slug}" if product_slug else slug


@router.get("/briefs", response_model=ContentBriefListResponse)
async def list_briefs(
    slug: str,
    content_service: ContentDataServiceProtocol = Depends(get_content_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> ContentBriefListResponse:
    """List all content briefs with inferred statuses and eval scores."""
    return await content_service.get_briefs(_effective(slug, product_slug))


@router.post("/briefs", response_model=ContentBriefListItem, status_code=201)
async def add_brief(
    slug: str,
    body: AddBriefRequest,
    content_service: ContentDataServiceProtocol = Depends(get_content_data_service),
    product_slug: Optional[str] = Query(None, description="Product slug"),
    _access=Depends(require_tenant),
) -> ContentBriefListItem:
    """Immediately add a topic to the content cycle.

    Creates a brief entry in blueprints.json so it appears in Content Studio
    right away. The content pipeline can later enrich/generate content for it.
    """
    return await content_service.add_brief(
        effective_slug=_effective(slug, product_slug),
        title=body.title,
        cluster=body.cluster,
        description=body.description,
        source=body.source,
        gap_query_id=body.gap_query_id,
    )


@router.get("/briefs/{brief_id}", response_model=ContentBriefDetailResponse)
async def get_brief(
    slug: str,
    brief_id: str,
    content_service: ContentDataServiceProtocol = Depends(get_content_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> ContentBriefDetailResponse:
    """Get full detail for a single content brief."""
    return await content_service.get_brief_detail(
        _effective(slug, product_slug), brief_id,
    )


@router.get("/briefs/{brief_id}/{stage}", response_model=StageContentResponse)
async def get_stage_content(
    slug: str,
    brief_id: str,
    stage: str,
    content_service: ContentDataServiceProtocol = Depends(get_content_data_service),
    product_slug: Optional[str] = Query(None, description="Filter by product slug"),
    _access=Depends(require_tenant),
) -> StageContentResponse:
    """Get stage-specific file content for a brief.

    Valid stages: outline, draft, enriched, formatted, eval_history, final
    """
    return await content_service.get_brief_stage_content(
        _effective(slug, product_slug), brief_id, stage,
    )
