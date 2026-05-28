"""Content Performance API endpoints.

Aggregates GA4 traffic data per content inventory page for the
Content Performance dashboard.

Auth: All endpoints require authentication + tenant isolation.

4 endpoints:
  GET  /                           Content performance table (all pieces)
  GET  /insights/velocity          Velocity + lifecycle insights
  GET  /{inventory_id}/similar     Similar pages (cannibalization detection)
  GET  /{inventory_id}             Detail view for a single content piece
"""
from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth.dependencies import require_auth
from api.dependencies import (
    get_auth_service,
    get_content_inventory_service,
    get_content_performance_service,
)
from api.schemas.content_performance import (
    ContentDetailResponse,
    ContentPerformanceRow,
    ContentPerformanceReadinessResponse,
    ContentPerformanceTableResponse,
    SimilarContentItem,
    SimilarContentResponse,
    VelocityInsight,
    VelocityInsightsResponse,
)
from core.auth.service import AuthServiceProtocol
from core.models.organization import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/content-performance",
    tags=["content-performance"],
)


# ── Helpers ──────────────────────────────────────────────────────────


def _get_company_slug(request: Request) -> str:
    """Extract company_slug from authenticated request state."""
    slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return slug


def _get_tenant_id(request: Request) -> str:
    """Resolve tenant_id for cache + connection lookups.

    Auth middleware currently guarantees ``company_slug`` but does not set a
    separate ``tenant_id`` field on request state. Content Performance should
    therefore key off the authenticated company slug, matching Analytics/CMS.
    """
    tenant_id: Optional[str] = getattr(request.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    return _get_company_slug(request)


def _compute_dates(days: int) -> tuple[date, date]:
    """Compute (start_date, end_date) from a lookback period in days.

    end_date = yesterday (GA4 data lags by ~1 day).
    start_date = end_date - days + 1.
    """
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start, end


# ── 1. Content Performance Table ────────────────────────────────────


@router.get("/readiness", response_model=ContentPerformanceReadinessResponse)
async def get_content_performance_readiness(
    http_request: Request,
    days: int = Query(default=28, ge=7, le=90, description="Lookback days"),
    _user: UserProfile = Depends(require_auth),
    perf_service: Any = Depends(get_content_performance_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentPerformanceReadinessResponse:
    """Return GA4 readiness metadata for the Content Performance page."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    start_date, end_date = _compute_dates(days)
    tenant_id = _get_tenant_id(http_request)
    readiness = await perf_service.get_readiness(
        company.id,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ContentPerformanceReadinessResponse(**readiness)


@router.get("/", response_model=ContentPerformanceTableResponse)
async def get_content_performance_table(
    http_request: Request,
    days: int = Query(default=28, ge=7, le=90, description="Lookback days"),
    _user: UserProfile = Depends(require_auth),
    perf_service: Any = Depends(get_content_performance_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentPerformanceTableResponse:
    """Return per-content-piece traffic summary for the content table.

    Joins content inventory with GA4 traffic data.  Includes traffic,
    AI referrals, velocity, velocity trend, freshness, and lifecycle.
    """
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check cache
    from core.services.analytics_cache import (
        get_cached_perf_table,
        set_cached_perf_table,
    )

    tenant_id = _get_tenant_id(http_request)
    cached = await asyncio.to_thread(
        get_cached_perf_table, company_slug, tenant_id, days,
    )
    if cached is not None:
        return ContentPerformanceTableResponse(**cached)

    start_date, end_date = _compute_dates(days)
    rows = await perf_service.get_content_table(
        company.id, start_date, end_date,
    )

    response = ContentPerformanceTableResponse(
        items=[ContentPerformanceRow(**r) for r in rows],
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
        total_items=len(rows),
    )

    # Populate cache
    await asyncio.to_thread(
        set_cached_perf_table,
        company_slug, tenant_id, days,
        response.model_dump(mode="json"),
    )

    return response


# ── 2. Velocity & Lifecycle Insights ────────────────────────────────


@router.get("/insights/velocity", response_model=VelocityInsightsResponse)
async def get_velocity_insights(
    http_request: Request,
    days: int = Query(default=28, ge=7, le=90, description="Lookback days"),
    _user: UserProfile = Depends(require_auth),
    perf_service: Any = Depends(get_content_performance_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> VelocityInsightsResponse:
    """Return velocity and lifecycle classification for all content pieces."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check cache
    from core.services.analytics_cache import (
        get_cached_velocity,
        set_cached_velocity,
    )

    tenant_id = _get_tenant_id(http_request)
    cached = await asyncio.to_thread(
        get_cached_velocity, company_slug, tenant_id, days,
    )
    if cached is not None:
        return VelocityInsightsResponse(**cached)

    start_date, end_date = _compute_dates(days)
    rows = await perf_service.get_velocity_insights(
        company.id, start_date, end_date,
    )

    response = VelocityInsightsResponse(
        items=[VelocityInsight(**r) for r in rows],
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
    )

    await asyncio.to_thread(
        set_cached_velocity,
        company_slug, tenant_id, days,
        response.model_dump(mode="json"),
    )

    return response


# ── 3. Similar Content (Cannibalization) ───────────────────────────


@router.get("/{inventory_id}/similar", response_model=SimilarContentResponse)
async def get_similar_content(
    inventory_id: str,
    http_request: Request,
    threshold: float = Query(default=0.78, ge=0.5, le=1.0),
    limit: int = Query(default=5, ge=1, le=20),
    _user: UserProfile = Depends(require_auth),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> SimilarContentResponse:
    """Find other inventory pages similar to this one (intra-inventory cannibalization)."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        inv_uuid = _uuid.UUID(inventory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid inventory_id format")

    matches = await inventory_service.find_similar_pages(
        company.id, inv_uuid, threshold=threshold, limit=limit,
    )

    # Check if embeddings are generated (needed for similarity to work)
    embeddings_count = await inventory_service.count_with_embeddings(company.id)

    return SimilarContentResponse(
        page_id=inventory_id,
        similar_pages=[
            SimilarContentItem(
                inventory_id=m.inventory_id,
                url=m.url,
                title=m.title,
                similarity=m.similarity,
                word_count=m.word_count,
                content_type=m.content_type_detected,
                content_preview=m.content_preview,
            )
            for m in matches
        ],
        threshold=threshold,
        embeddings_ready=embeddings_count >= 2,
    )


# ── 4. Content Detail ───────────────────────────────────────────────


@router.get("/{inventory_id}", response_model=ContentDetailResponse)
async def get_content_detail(
    inventory_id: str,
    http_request: Request,
    days: int = Query(default=28, ge=7, le=90, description="Lookback days"),
    _user: UserProfile = Depends(require_auth),
    perf_service: Any = Depends(get_content_performance_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentDetailResponse:
    """Return detailed analytics for a single content piece.

    Includes daily traffic timeseries, source breakdown, and
    AI platform breakdown.
    """
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Validate UUID
    try:
        inv_uuid = _uuid.UUID(inventory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid inventory_id format")

    # Check cache
    from core.services.analytics_cache import (
        get_cached_perf_detail,
        set_cached_perf_detail,
    )

    tenant_id = _get_tenant_id(http_request)
    cached = await asyncio.to_thread(
        get_cached_perf_detail, company_slug, tenant_id, inventory_id, days,
    )
    if cached is not None:
        return ContentDetailResponse(**cached)

    start_date, end_date = _compute_dates(days)
    detail = await perf_service.get_content_detail(
        company.id, inv_uuid, start_date, end_date,
    )

    if detail is None:
        raise HTTPException(
            status_code=404, detail="Content piece not found",
        )

    response = ContentDetailResponse(**detail)

    await asyncio.to_thread(
        set_cached_perf_detail,
        company_slug, tenant_id, inventory_id, days,
        response.model_dump(mode="json"),
    )

    return response
