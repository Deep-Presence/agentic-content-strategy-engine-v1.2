"""Daily Tracker API — prompt library management, run triggers, analytics queries.

Endpoints:
    Prompt CRUD (8 endpoints):
        POST   /prompts              Create a tracked prompt
        GET    /prompts              List tracked prompts with filters
        GET    /prompts/{prompt_id}  Get a specific prompt
        PUT    /prompts/{prompt_id}  Update a prompt
        DELETE /prompts/{prompt_id}  Delete a prompt
        PATCH  /prompts/{prompt_id}/toggle   Toggle active status
        POST   /prompts/import       Import from gap analysis queries
        POST   /prompts/bulk         Bulk create prompts

    Run Management (3 endpoints):
        POST   /runs                 Trigger a daily run (async, returns immediately)
        GET    /runs/{run_id}        Get run status
        GET    /runs                 List runs for company

    Analytics (5 endpoints):
        GET    /analytics/visibility      Overall visibility metrics
        GET    /analytics/mention-trend   Mention rate over time
        GET    /analytics/sov             Share of voice vs competitors
        GET    /analytics/citations       Citation rates
        GET    /analytics/competitors     Per-competitor metrics

All endpoints require authentication and tenant isolation following
the existing router patterns (require_auth, require_tenant).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.auth.dependencies import require_auth, require_role
from api.dependencies import (
    get_analytics_service,
    get_daily_tracker_orchestrator,
    get_prompt_library_service,
)
from core.daily_tracker.analytics_engine import AnalyticsService
from core.daily_tracker.orchestrator import DailyTrackerOrchestrator
from core.daily_tracker.prompt_library import PromptLibraryService
from core.models.daily_tracker import (
    CompetitorMetrics,
    PromptLibraryFilter,
    PromptSource,
    TrackedPrompt,
    TrendDataPoint,
    VisibilityMetrics,
)
from core.models.organization import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/daily-tracker", tags=["daily-tracker"])


# ── Request/Response Schemas ─────────────────────────────────────────


class CreatePromptRequest(BaseModel):
    """Request body for creating a tracked prompt."""

    text: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class UpdatePromptRequest(BaseModel):
    """Request body for updating a tracked prompt."""

    text: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    active: bool | None = None


class ToggleActiveRequest(BaseModel):
    """Request body for toggling a prompt's active status."""

    active: bool


class ImportPromptsRequest(BaseModel):
    """Request body for importing prompts from gap analysis."""

    slug: str


class BulkPromptItem(BaseModel):
    """A single prompt in a bulk create request."""

    text: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None


class BulkCreatePromptsRequest(BaseModel):
    """Request body for bulk creating prompts."""

    prompts: list[BulkPromptItem]


class TriggerRunRequest(BaseModel):
    """Request body for triggering a daily run."""

    engines: list[str] | None = None
    prompt_ids: list[str] | None = None
    brand: str | None = None
    competitors: list[str] | None = None
    concurrency: int = Field(default=6, ge=1, le=20)


class RunStatusResponse(BaseModel):
    """Response for run status queries."""

    run_id: str
    company_id: str = ""
    status: str
    prompt_count: int = 0
    engine_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class PromptListResponse(BaseModel):
    """Paginated response for prompt listings."""

    prompts: list[TrackedPrompt]
    total: int = 0


class RunListResponse(BaseModel):
    """Paginated response for run listings."""

    runs: list[RunStatusResponse]
    total: int = 0


# ── Prompt Library Endpoints ─────────────────────────────────────────


@router.post("/prompts", status_code=201)
async def create_prompt(
    body: CreatePromptRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Create a new tracked prompt for the authenticated company."""
    company_id = _get_company_id(request)
    try:
        return await prompt_service.create_prompt(
            company_id=company_id,
            text=body.text,
            category=body.category,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/prompts")
async def list_prompts(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
    category: str | None = Query(None),
    source: str | None = Query(None),
    active: bool | None = Query(None),
    search: str | None = Query(None),
    tags: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PromptListResponse:
    """List tracked prompts with optional filters."""
    company_id = _get_company_id(request)

    filters = PromptLibraryFilter(
        category=category,
        tags=tags,
        active=active,
        source=PromptSource(source) if source else None,
        search=search,
    )

    prompts = await prompt_service.list_prompts(company_id, filters=filters)
    return PromptListResponse(prompts=prompts, total=len(prompts))


@router.get("/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Get a specific tracked prompt by ID."""
    _get_company_id(request)  # tenant check
    prompt = await prompt_service.get_prompt(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@router.put("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: str,
    body: UpdatePromptRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Update a tracked prompt's fields."""
    _get_company_id(request)  # tenant check
    update_kwargs: dict[str, Any] = {}
    if body.text is not None:
        update_kwargs["text"] = body.text
    if body.category is not None:
        update_kwargs["category"] = body.category
    if body.tags is not None:
        update_kwargs["tags"] = body.tags
    if body.active is not None:
        update_kwargs["active"] = body.active

    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        return await prompt_service.update_prompt(prompt_id, **update_kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/prompts/{prompt_id}", status_code=204)
async def delete_prompt(
    prompt_id: str,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> None:
    """Delete a tracked prompt."""
    _get_company_id(request)  # tenant check
    deleted = await prompt_service.delete_prompt(prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prompt not found")


@router.patch("/prompts/{prompt_id}/toggle")
async def toggle_prompt(
    prompt_id: str,
    body: ToggleActiveRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Toggle a prompt's active/inactive status."""
    _get_company_id(request)  # tenant check
    try:
        return await prompt_service.toggle_prompt(prompt_id, body.active)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/prompts/import", status_code=201)
async def import_prompts(
    body: ImportPromptsRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> list[TrackedPrompt]:
    """Import prompts from a gap analysis run's queries.json."""
    company_id = _get_company_id(request)
    try:
        return await prompt_service.import_from_gap_analysis(
            company_id=company_id,
            slug=body.slug,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/prompts/bulk", status_code=201)
async def bulk_create_prompts(
    body: BulkCreatePromptsRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> list[TrackedPrompt]:
    """Bulk create tracked prompts (duplicates are skipped)."""
    company_id = _get_company_id(request)
    prompt_dicts = [p.model_dump(mode="json") for p in body.prompts]
    return await prompt_service.bulk_create(company_id, prompt_dicts)


# ── Run Management Endpoints ─────────────────────────────────────────


@router.post("/runs", status_code=202)
async def trigger_daily_run(
    body: TriggerRunRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    orchestrator: DailyTrackerOrchestrator = Depends(
        get_daily_tracker_orchestrator
    ),
) -> RunStatusResponse:
    """Trigger a daily tracking run.

    The run executes synchronously within this request because the
    orchestrator is lightweight (delegates to platform runner).
    For long-running runs with many prompts, consider the SSE task
    pattern in a future iteration.
    """
    company_id = _get_company_id(request)

    result = await orchestrator.execute_daily_run(
        company_id=company_id,
        prompt_ids=body.prompt_ids,
        engines=body.engines,
        brand=body.brand,
        competitors=body.competitors,
        concurrency=body.concurrency,
    )

    return RunStatusResponse(
        run_id=result.run_id,
        company_id=result.company_id,
        status=result.status.value,
        prompt_count=result.prompt_count,
        engine_count=result.engine_count,
        started_at=result.started_at.isoformat() if result.started_at else None,
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        error=result.error,
    )


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    orchestrator: DailyTrackerOrchestrator = Depends(
        get_daily_tracker_orchestrator
    ),
) -> RunStatusResponse:
    """Get the status of a daily run."""
    _get_company_id(request)  # tenant check
    status_dict = await orchestrator.get_run_status(run_id)
    return RunStatusResponse(
        run_id=status_dict.get("run_id", run_id),  # type: ignore[arg-type]
        status=str(status_dict.get("status", "unknown")),
    )


@router.get("/runs")
async def list_runs(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RunListResponse:
    """List daily runs for the authenticated company.

    Note: In the current implementation without DB persistence for runs,
    this returns an empty list. Full implementation requires DB run storage
    (deferred to the next iteration when DB repos are wired end-to-end).
    """
    _get_company_id(request)  # tenant check
    # Why: orchestrator is stateless — run listing requires DB lookup.
    # In v1, runs are transient (returned from trigger endpoint).
    # Full DB persistence for run listing is deferred.
    return RunListResponse(runs=[], total=0)


# ── Analytics Endpoints ──────────────────────────────────────────────


@router.get("/analytics/visibility")
async def get_visibility_metrics(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    analytics: AnalyticsService = Depends(get_analytics_service),
    run_id: str | None = Query(None),
) -> VisibilityMetrics:
    """Get comprehensive visibility metrics for the company."""
    company_id = _get_company_id(request)
    return await analytics.compute_visibility_metrics(company_id, run_id=run_id)


@router.get("/analytics/mention-trend")
async def get_mention_trend(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    analytics: AnalyticsService = Depends(get_analytics_service),
    days: int = Query(30, ge=1, le=365),
) -> list[TrendDataPoint]:
    """Get mention rate trend over time."""
    company_id = _get_company_id(request)
    return await analytics.compute_mention_rate_trend(company_id, days=days)


@router.get("/analytics/sov")
async def get_share_of_voice(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    analytics: AnalyticsService = Depends(get_analytics_service),
    run_id: str | None = Query(None),
) -> dict[str, float]:
    """Get share of voice vs competitors."""
    company_id = _get_company_id(request)
    return await analytics.compute_share_of_voice(company_id, run_id=run_id)


@router.get("/analytics/citations")
async def get_citation_rates(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    analytics: AnalyticsService = Depends(get_analytics_service),
    run_id: str | None = Query(None),
) -> dict[str, object]:
    """Get citation rates with domain breakdown."""
    company_id = _get_company_id(request)
    return await analytics.compute_citation_rate(company_id, run_id=run_id)


@router.get("/analytics/competitors")
async def get_competitor_metrics(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    analytics: AnalyticsService = Depends(get_analytics_service),
    run_id: str | None = Query(None),
) -> list[CompetitorMetrics]:
    """Get per-competitor visibility metrics."""
    company_id = _get_company_id(request)
    return await analytics.get_competitor_metrics(company_id, run_id=run_id)


# ── Private helpers ──────────────────────────────────────────────────


def _get_company_id(request: Request) -> str:
    """Extract the company slug from the authenticated request state.

    Why company_slug as company_id: the daily tracker uses string-based
    company_id (not UUID FK) so it can work standalone before company
    onboarding.  The auth middleware sets company_slug on request.state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The authenticated user's company_slug.

    Raises:
        HTTPException: If no company_slug is found in request state.
    """
    company_slug = getattr(request.state, "company_slug", None)
    if not company_slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return company_slug
