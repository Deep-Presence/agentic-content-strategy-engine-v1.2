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

import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.auth.dependencies import require_auth, require_role
from api.dependencies import (
    get_analytics_service,
    get_artifacts_root,
    get_daily_tracker_orchestrator,
    get_event_bus,
    get_prompt_library_service,
    get_task_store,
)
from api.schemas.common import PipelineRunResponse
from api.tasks.event_bus import EventBusProtocol
from core.daily_tracker.analytics_engine import AnalyticsService
from core.daily_tracker.orchestrator import DailyTrackerOrchestrator
from core.daily_tracker.prompt_library import PromptLibraryService
from core.services.task_store import TaskStoreProtocol
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
    generate_fanout: bool = True
    brand_name: str | None = None
    brand_category: str | None = None
    competitors: list[str] | None = None


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


class CreatePromptResponse(BaseModel):
    """Response for prompt creation with optional fanout task."""

    prompt: TrackedPrompt
    fanout_task_id: str | None = None


@router.post("/prompts", status_code=201)
async def create_prompt(
    body: CreatePromptRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
) -> CreatePromptResponse:
    """Create a new tracked prompt for the authenticated company.

    When ``generate_fanout=True`` (default), launches a background task
    to generate query fanout variants via LLM.  Returns the parent prompt
    immediately with a ``fanout_task_id`` for tracking.
    """
    company_id = _get_company_id(request)
    try:
        prompt = await prompt_service.create_prompt(
            company_id=company_id,
            text=body.text,
            category=body.category,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    fanout_task_id: str | None = None

    if body.generate_fanout and body.brand_name:
        from api.routers._helpers import create_task_durable
        from api.tasks.runner import run_fanout_generation_task

        task = await create_task_durable(
            task_store, "fanout_generation", company_id
        )
        fanout_task_id = task.task_id

        handle = asyncio.create_task(
            run_fanout_generation_task(
                task_id=task.task_id,
                parent_prompt_id=prompt.id,
                company_slug=company_id,
                brand_name=body.brand_name,
                brand_category=body.brand_category or "",
                competitors=body.competitors or [],
                task_store=task_store,
                event_bus=event_bus,
            )
        )
        task_store.register_task_handle(task.task_id, handle)

    return CreatePromptResponse(prompt=prompt, fanout_task_id=fanout_task_id)


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
    include_fanouts: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PromptListResponse:
    """List tracked prompts with optional filters.

    By default excludes fanout children (``include_fanouts=False``).
    The main prompt tracking list should only show parent prompts.
    """
    company_id = _get_company_id(request)

    filters = PromptLibraryFilter(
        category=category,
        tags=tags,
        active=active,
        source=PromptSource(source) if source else None,
        search=search,
    )

    prompts = await prompt_service.list_prompts(company_id, filters=filters)

    # Filter out fanouts unless explicitly requested
    if not include_fanouts:
        prompts = [p for p in prompts if p.parent_prompt_id is None]

    return PromptListResponse(prompts=prompts, total=len(prompts))


# ── Enriched Prompt List (Phase 1) ─────────────────────────────────
# MUST be registered BEFORE /prompts/{prompt_id} to avoid path capture.


@router.get("/prompts/enriched")
async def get_enriched_prompts(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    days: int = Query(7, ge=1, le=90),
    start_date: str | None = Query(None, description="ISO date (YYYY-MM-DD). Overrides days when paired with end_date."),
    end_date: str | None = Query(None, description="ISO date (YYYY-MM-DD). Overrides days when paired with start_date."),
    category: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Return prompts with per-prompt aggregated metrics for the main table.

    Metrics include mention_rate, citation_rate, period-over-period deltas,
    daily volume sparkline, and fanout counts.  Fanout responses are rolled
    up into the parent prompt via ``COALESCE(parent_prompt_id, prompt_id)``.

    Query params:
        days: Period length (default 7).  Delta compares current period vs
              the previous equal-length period.
        start_date/end_date: Explicit date range (overrides days).
        category: Filter by prompt category.
        search: Text search on prompt text.
        limit/offset: Pagination.
    """
    from datetime import date, timedelta

    from core.cache import cache_get, cache_set
    from core.models.daily_tracker import EnrichedPrompt, EnrichedPromptListResponse

    company_id = _get_company_id(request)

    # Compute time windows — explicit dates take precedence over days
    today = date.today()
    if start_date and end_date:
        try:
            sd = date.fromisoformat(start_date)
            ed = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="start_date and end_date must be YYYY-MM-DD")
        if sd >= ed:
            raise HTTPException(status_code=422, detail="start_date must be before end_date")
        span = (ed - sd).days + 1
        if span > 90:
            raise HTTPException(status_code=422, detail="Date range cannot exceed 90 days")
        days = span
        current_start_dt = datetime.combine(sd, datetime.min.time(), tzinfo=timezone.utc)
        current_end_dt = datetime.combine(ed + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        period_start_str = str(sd)
        period_end_str = str(ed)
    else:
        current_end_dt = datetime.combine(
            today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc,
        )
        current_start_dt = datetime.combine(
            today - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc,
        )
        period_start_str = str(current_start_dt.date())
        period_end_str = str(today)

    prev_end_dt = current_start_dt
    prev_start_dt = prev_end_dt - timedelta(days=days)

    # Redis cache check
    cache_key = f"cache:prompt_enriched:{company_id}:{period_start_str}:{period_end_str}"
    cached = await asyncio.to_thread(cache_get, cache_key)
    if cached is not None and not category and not search:
        resp = EnrichedPromptListResponse.model_validate(cached)
        sliced = resp.prompts[offset : offset + limit]
        return resp.model_copy(update={"prompts": sliced}).model_dump(mode="json")

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return EnrichedPromptListResponse(
            period_days=days,
            period_start=period_start_str,
            period_end=period_end_str,
        ).model_dump(mode="json")

    try:
        from core.db.repositories.daily_tracker_repo import DailyRunResponseRepository

        async with sf() as session:
            repo = DailyRunResponseRepository(session)

            rows = await repo.get_prompt_metrics_batch(
                company_id=company_id,
                current_start=current_start_dt,
                current_end=current_end_dt,
                prev_start=prev_start_dt,
                prev_end=prev_end_dt,
            )

            volume_map = await repo.get_daily_volume_batch(
                company_id=company_id,
                start=current_start_dt,
                end=current_end_dt,
            )

            # Build zero-filled date range for sparkline
            date_range = [
                str(today - timedelta(days=days - 1 - i))
                for i in range(days)
            ]

            enriched: list[EnrichedPrompt] = []
            for row in rows:
                pid = row.id
                vol_data = volume_map.get(pid, {})
                volume = [vol_data.get(d, 0) for d in date_range]

                if category and row.category != category:
                    continue
                if search and search.lower() not in (row.text or "").lower():
                    continue

                enriched.append(
                    EnrichedPrompt(
                        id=str(pid),
                        text=row.text or "",
                        category=row.category,
                        tags=row.tags or [],
                        source=row.source or "manual",
                        active=row.active,
                        created_at=row.created_at,
                        mention_rate=round(float(row.mention_rate or 0), 4),
                        mention_delta=round(float(row.mention_delta or 0), 4),
                        citation_rate=round(float(row.citation_rate or 0), 4),
                        citation_delta=round(float(row.citation_delta or 0), 4),
                        daily_volume=volume,
                        fanout_count=int(row.fanout_count or 0),
                        total_responses=int(row.total_responses or 0),
                    )
                )

            total = len(enriched)
            page = enriched[offset : offset + limit]

            result = EnrichedPromptListResponse(
                prompts=page,
                total=total,
                period_days=days,
                period_start=period_start_str,
                period_end=period_end_str,
            )

            # Cache unfiltered result
            if not category and not search:
                full_result = result.model_copy(update={"prompts": enriched})
                await asyncio.to_thread(
                    cache_set,
                    cache_key,
                    full_result.model_dump(mode="json"),
                    ttl=300,
                )

            return result.model_dump(mode="json")

    except Exception:
        logger.warning("get_enriched_prompts failed for %s", company_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch enriched prompts")


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


# ── Fanout Query Endpoints ──────────────────────────────────────────


class FanoutQueryResponse(BaseModel):
    """Response for a single fanout query."""

    id: str
    parent_prompt_id: str
    axis: str
    query_text: str
    reasoning: str = ""
    pinned: bool = False
    active: bool = True
    observation_count: int = 0
    created_at: datetime | None = None


class FanoutListResponse(BaseModel):
    """Response for listing fanout queries."""

    parent_prompt_id: str
    parent_text: str
    fanouts: list[FanoutQueryResponse]
    total: int


class AddFanoutRequest(BaseModel):
    """Request body for manually adding a fanout query."""

    query_text: str
    axis: str = "manual"
    reasoning: str = ""


class RegenerateFanoutRequest(BaseModel):
    """Request body for regenerating fanout queries."""

    brand_name: str | None = None
    brand_category: str | None = None
    competitors: list[str] | None = None
    target_count: int = Field(default=15, ge=6, le=24)


class AnswerRecord(BaseModel):
    """A single response record for answer history."""

    id: str
    run_id: str
    engine: str
    response_text: str
    brand_mentioned: bool = False
    brand_mention_count: int = 0
    competitor_mentions: dict[str, int] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    citation_rank: int | None = None
    persona: str = "Default"
    created_at: datetime | None = None


class AnswerHistoryResponse(BaseModel):
    """Paginated answer history for a parent prompt."""

    prompt_id: str
    responses: list[AnswerRecord]
    total: int


@router.get("/prompts/{prompt_id}/fanouts")
async def list_fanouts(
    prompt_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> FanoutListResponse:
    """List fanout queries for a parent prompt with observation counts."""
    _get_company_id(request)

    parent = await prompt_service.get_prompt(prompt_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    fanouts = await prompt_service.list_fanout_queries(prompt_id)

    # Get observation counts from response data
    sf = getattr(request.app.state, "db_session_factory", None)
    obs_counts: dict[str, int] = {}
    if sf:
        try:
            from core.db.repositories.daily_tracker_repo import DailyRunResponseRepository

            async with sf() as session:
                repo = DailyRunResponseRepository(session)
                raw_counts = await repo.get_observation_counts(
                    _uuid.UUID(prompt_id)
                )
                obs_counts = {str(k): v for k, v in raw_counts.items()}
        except Exception:
            logger.warning("Failed to fetch observation counts", exc_info=True)

    fanout_responses = [
        FanoutQueryResponse(
            id=f.id,
            parent_prompt_id=f.parent_prompt_id or prompt_id,
            axis=f.fanout_axis or "",
            query_text=f.text,
            reasoning=(f.source_metadata or {}).get("reasoning", ""),
            pinned=f.pinned,
            active=f.active,
            observation_count=obs_counts.get(f.id, 0),
            created_at=f.created_at,
        )
        for f in fanouts
    ]

    return FanoutListResponse(
        parent_prompt_id=prompt_id,
        parent_text=parent.text,
        fanouts=fanout_responses,
        total=len(fanout_responses),
    )


@router.post("/prompts/{prompt_id}/fanouts", status_code=201)
async def add_fanout(
    prompt_id: str,
    body: AddFanoutRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Manually add a fanout query to a parent prompt."""
    company_id = _get_company_id(request)

    parent = await prompt_service.get_prompt(prompt_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    from core.models.daily_tracker import FanoutQuery

    created = await prompt_service.create_fanout_queries(
        parent_prompt_id=prompt_id,
        company_id=company_id,
        queries=[
            FanoutQuery(
                axis=body.axis,
                query_text=body.query_text,
                reasoning=body.reasoning,
            )
        ],
    )
    if not created:
        raise HTTPException(
            status_code=409, detail="Fanout query already exists"
        )
    return created[0]


@router.post("/prompts/{prompt_id}/fanouts/regenerate", status_code=202)
async def regenerate_fanouts(
    prompt_id: str,
    body: RegenerateFanoutRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> dict[str, str]:
    """Regenerate fanout queries for a parent prompt (background task).

    Deletes non-pinned fanouts, generates fresh ones via LLM.
    Pinned fanouts are preserved.
    """
    company_id = _get_company_id(request)

    parent = await prompt_service.get_prompt(prompt_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if not body.brand_name:
        raise HTTPException(
            status_code=400, detail="brand_name is required for regeneration"
        )

    from api.routers._helpers import create_task_durable
    from api.tasks.runner import run_fanout_generation_task

    task = await create_task_durable(
        task_store, "fanout_generation", company_id
    )

    handle = asyncio.create_task(
        run_fanout_generation_task(
            task_id=task.task_id,
            parent_prompt_id=prompt_id,
            company_slug=company_id,
            brand_name=body.brand_name,
            brand_category=body.brand_category or "",
            competitors=body.competitors or [],
            task_store=task_store,
            event_bus=event_bus,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return {"task_id": task.task_id, "status": "running"}


@router.delete("/prompts/{prompt_id}/fanouts/{fanout_id}", status_code=204)
async def delete_fanout(
    prompt_id: str,
    fanout_id: str,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> None:
    """Delete a specific fanout query."""
    _get_company_id(request)
    deleted = await prompt_service.delete_prompt(fanout_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fanout not found")


@router.patch("/prompts/{prompt_id}/fanouts/{fanout_id}/pin")
async def toggle_pin(
    prompt_id: str,
    fanout_id: str,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Toggle the pinned status of a fanout query."""
    _get_company_id(request)
    fanout = await prompt_service.get_prompt(fanout_id)
    if fanout is None:
        raise HTTPException(status_code=404, detail="Fanout not found")

    if fanout.pinned:
        return await prompt_service.unpin_fanout(fanout_id)
    return await prompt_service.pin_fanout(fanout_id)


@router.patch("/prompts/{prompt_id}/fanouts/{fanout_id}/toggle")
async def toggle_fanout_active(
    prompt_id: str,
    fanout_id: str,
    body: ToggleActiveRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    prompt_service: PromptLibraryService = Depends(get_prompt_library_service),
) -> TrackedPrompt:
    """Toggle the active status of a fanout query."""
    _get_company_id(request)
    try:
        return await prompt_service.toggle_prompt(fanout_id, body.active)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Answer History Endpoint ─────────────────────────────────────────


@router.get("/prompts/{prompt_id}/answers")
async def get_answer_history(
    prompt_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    engine: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    start_date: str | None = Query(None, description="ISO date (YYYY-MM-DD). Overrides days when paired with end_date."),
    end_date: str | None = Query(None, description="ISO date (YYYY-MM-DD). Overrides days when paired with start_date."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AnswerHistoryResponse:
    """Get response history for a parent prompt (NOT fanout responses).

    Returns only the parent prompt's own AI responses with mention
    analysis data, ordered by date descending.
    """
    _get_company_id(request)

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return AnswerHistoryResponse(prompt_id=prompt_id, responses=[], total=0)

    try:
        from datetime import date, timedelta
        from core.db.models.daily_tracker import DailyRunResponseModel
        from sqlalchemy import and_, func, select

        if start_date and end_date:
            try:
                sd = date.fromisoformat(start_date)
                ed = date.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(status_code=422, detail="start_date and end_date must be YYYY-MM-DD")
            cutoff = datetime.combine(sd, datetime.min.time(), tzinfo=timezone.utc)
            upper = datetime.combine(ed + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            upper = None
        prompt_uuid = _uuid.UUID(prompt_id)

        async with sf() as session:
            # Base filter: responses for this prompt_id that are NOT
            # fanout responses (parent_prompt_id IS NULL).
            conditions = [
                DailyRunResponseModel.prompt_id == prompt_uuid,
                DailyRunResponseModel.parent_prompt_id.is_(None),
                DailyRunResponseModel.created_at >= cutoff,
                DailyRunResponseModel.response_text != "",
            ]
            if upper is not None:
                conditions.append(DailyRunResponseModel.created_at < upper)
            base_filter = and_(*conditions)
            if engine:
                base_filter = and_(
                    base_filter,
                    DailyRunResponseModel.engine == engine,
                )

            # Count total
            count_q = (
                select(func.count())
                .select_from(DailyRunResponseModel)
                .where(base_filter)
            )
            total = (await session.execute(count_q)).scalar() or 0

            # Fetch page
            q = (
                select(DailyRunResponseModel)
                .where(base_filter)
                .order_by(DailyRunResponseModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(q)).scalars().all()

            responses = [
                AnswerRecord(
                    id=str(row.id),
                    run_id=str(row.run_id),
                    engine=row.engine,
                    response_text=row.response_text,
                    brand_mentioned=row.brand_mentioned,
                    brand_mention_count=row.brand_mention_count,
                    competitor_mentions=row.competitor_mentions or {},
                    citations=row.citations or [],
                    citation_rank=row.citation_rank,
                    created_at=row.created_at,
                )
                for row in rows
            ]

            return AnswerHistoryResponse(
                prompt_id=prompt_id,
                responses=responses,
                total=total,
            )
    except Exception:
        logger.warning("get_answer_history failed for %s", prompt_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch answer history")


# ── Per-Prompt Analytics (Phase 2 — Drawer) ────────────────────────


@router.get("/prompts/{prompt_id}/analytics")
async def get_prompt_analytics(
    prompt_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
    days: int = Query(30, ge=1, le=365),
    start_date: str | None = Query(None, description="ISO date (YYYY-MM-DD). Overrides days when paired with end_date."),
    end_date: str | None = Query(None, description="ISO date (YYYY-MM-DD). Overrides days when paired with start_date."),
) -> dict[str, Any]:
    """Per-prompt scoped analytics for the drawer.

    Returns competitor breakdown and platform breakdown in a single
    response, computed from one DB query.  Fanout responses are included
    via the ``parent_prompt_id`` denormalization.

    Frontend fires this in parallel with ``/fanouts`` and ``/answers``.
    """
    from core.models.daily_tracker import (
        CompetitorMetrics,
        PerPromptPlatformMetrics,
        PromptAnalyticsResponse,
    )

    company_id = _get_company_id(request)

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return PromptAnalyticsResponse(
            prompt_id=prompt_id, period_days=days
        ).model_dump(mode="json")

    try:
        from datetime import date, timedelta

        from core.db.repositories.daily_tracker_repo import DailyRunResponseRepository

        # Resolve time window
        if start_date and end_date:
            try:
                sd = date.fromisoformat(start_date)
                ed = date.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(status_code=422, detail="start_date and end_date must be YYYY-MM-DD")
            span = (ed - sd).days + 1
            days = span
            current_start = datetime.combine(sd, datetime.min.time(), tzinfo=timezone.utc)
            current_end = datetime.combine(ed + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            prev_end = current_start
            prev_start = prev_end - timedelta(days=span)
        else:
            current_end = datetime.now(timezone.utc)
            current_start = current_end - timedelta(days=days)
            prev_end = current_start
            prev_start = prev_end - timedelta(days=days)

        prompt_uuid = _uuid.UUID(prompt_id)

        async with sf() as session:
            repo = DailyRunResponseRepository(session)

            # Fetch responses covering current + previous period
            total_span = (current_end - prev_start).days
            all_rows = await repo.get_responses_for_prompt(
                prompt_id=prompt_uuid, days=total_span,
            )

            if not all_rows:
                return PromptAnalyticsResponse(
                    prompt_id=prompt_id, period_days=days,
                ).model_dump(mode="json")

            rows = [r for r in all_rows if r.created_at and r.created_at >= current_start]
            prev_only = [r for r in all_rows if r.created_at and r.created_at < current_start and r.created_at >= prev_start]

            if not rows:
                return PromptAnalyticsResponse(
                    prompt_id=prompt_id, period_days=days,
                ).model_dump(mode="json")

            # -- Overall metrics --
            total = len(rows)
            mentioned = sum(1 for r in rows if r.brand_mentioned)
            cited = sum(1 for r in rows if r.citations)
            mention_rate = mentioned / total if total else 0.0
            citation_rate = cited / total if total else 0.0

            # -- Platform breakdown --
            engine_data: dict[str, dict[str, int]] = {}
            for r in rows:
                ed = engine_data.setdefault(r.engine, {"responses": 0, "mentions": 0})
                ed["responses"] += 1
                if r.brand_mentioned:
                    ed["mentions"] += 1

            platforms = [
                PerPromptPlatformMetrics(
                    engine=eng,
                    response_count=d["responses"],
                    mention_count=d["mentions"],
                    mention_rate=(
                        round(d["mentions"] / d["responses"], 4)
                        if d["responses"] else 0.0
                    ),
                )
                for eng, d in sorted(engine_data.items())
            ]

            # -- Competitor breakdown (current period) --
            comp_mentions: dict[str, int] = {}
            comp_response_count: dict[str, int] = {}
            for r in rows:
                for name, count in (r.competitor_mentions or {}).items():
                    c = int(count) if not isinstance(count, bool) else (1 if count else 0)
                    comp_mentions[name] = comp_mentions.get(name, 0) + c
                    if c > 0:
                        comp_response_count[name] = comp_response_count.get(name, 0) + 1

            # Previous period competitor rates
            prev_comp_rate: dict[str, float] = {}
            prev_total = len(prev_only)
            if prev_total:
                prev_comp_resp: dict[str, int] = {}
                for r in prev_only:
                    for name, count in (r.competitor_mentions or {}).items():
                        c = int(count) if not isinstance(count, bool) else (1 if count else 0)
                        if c > 0:
                            prev_comp_resp[name] = prev_comp_resp.get(name, 0) + 1
                for name, cnt in prev_comp_resp.items():
                    prev_comp_rate[name] = cnt / prev_total

            competitors_list = []
            for name, mc in sorted(comp_mentions.items(), key=lambda x: -x[1]):
                cur_rate = comp_response_count.get(name, 0) / total if total else 0.0
                delta = cur_rate - prev_comp_rate.get(name, 0.0)
                competitors_list.append(
                    CompetitorMetrics(
                        name=name,
                        mention_rate=round(cur_rate, 4),
                        mention_count=mc,
                        mention_delta=round(delta, 4),
                    )
                )
            for i, comp in enumerate(competitors_list, 1):
                comp.rank = i

            return PromptAnalyticsResponse(
                prompt_id=prompt_id,
                period_days=days,
                mention_rate=round(mention_rate, 4),
                citation_rate=round(citation_rate, 4),
                competitors=competitors_list,
                platforms=platforms,
            ).model_dump(mode="json")

    except Exception:
        logger.warning("get_prompt_analytics failed for %s", prompt_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch prompt analytics")


# ── Cleanup Endpoint ────────────────────────────────────────────────


@router.post("/admin/cleanup")
async def trigger_cleanup(
    request: Request,
    _user: UserProfile = Depends(require_role("superuser")),
    retention_days: int = Query(30, ge=7, le=365),
) -> dict[str, Any]:
    """Clear old response text for data retention (superuser-only).

    Sets ``response_text = ''`` for responses older than
    ``retention_days``.  Preserves all metric columns for trend analytics.
    """
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    from core.daily_tracker.cleanup import cleanup_old_response_text

    rows_updated = await cleanup_old_response_text(sf, retention_days)
    return {
        "status": "completed",
        "rows_updated": rows_updated,
        "retention_days": retention_days,
    }


# ── Run Management Endpoints ─────────────────────────────────────────


@router.post("/runs", status_code=202)
async def trigger_daily_run(
    body: TriggerRunRequest,
    request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    task_store: TaskStoreProtocol = Depends(get_task_store),
    event_bus: EventBusProtocol = Depends(get_event_bus),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> PipelineRunResponse:
    """Trigger a daily tracking run as an async background task.

    Returns 202 with a task_id immediately.  The run executes in the
    background and emits SSE events via ``GET /tasks/{task_id}/events``.
    """
    company_slug = _get_company_id(request)

    from api.routers._helpers import create_task_durable
    from api.tasks.runner import run_daily_tracker_task

    task = await create_task_durable(task_store, "daily_tracker", company_slug)

    handle = asyncio.create_task(
        run_daily_tracker_task(
            task_id=task.task_id,
            request=body,
            company_slug=company_slug,
            artifacts_root=artifacts_root,
            task_store=task_store,
            event_bus=event_bus,
        )
    )
    task_store.register_task_handle(task.task_id, handle)

    return PipelineRunResponse(
        run_id=task.task_id,
        pipeline=task.pipeline,
        company_slug=task.company_slug,
        status="running",
        created_at=task.created_at,
    )


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: str,
    request: Request,
    _user: UserProfile = Depends(require_auth),
) -> RunStatusResponse:
    """Get the status of a daily run from the database."""
    company_slug = _get_company_id(request)

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        from core.db.models.daily_tracker import DailyRunModel

        async with sf() as session:
            run_uuid = _uuid.UUID(run_id)
            row = await session.get(DailyRunModel, run_uuid)
            if row is None or row.company_id != company_slug:
                raise HTTPException(status_code=404, detail="Run not found")

            return RunStatusResponse(
                run_id=str(row.id),
                company_id=row.company_id,
                status=row.status or "unknown",
                prompt_count=row.prompt_count or 0,
                engine_count=row.engine_count or 0,
                started_at=row.started_at.isoformat() if row.started_at else None,
                completed_at=row.completed_at.isoformat() if row.completed_at else None,
                error=row.error,
            )
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    except Exception:
        logger.warning("get_run_status failed for %s", run_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch run status")


@router.get("/runs")
async def list_runs(
    request: Request,
    _user: UserProfile = Depends(require_auth),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RunListResponse:
    """List daily runs for the authenticated company from the database."""
    company_slug = _get_company_id(request)

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is None:
        return RunListResponse(runs=[], total=0)

    try:
        from core.db.models.daily_tracker import DailyRunModel
        from sqlalchemy import func, select

        async with sf() as session:
            # Count total
            count_q = (
                select(func.count())
                .select_from(DailyRunModel)
                .where(DailyRunModel.company_id == company_slug)
            )
            total = (await session.execute(count_q)).scalar() or 0

            # Fetch page
            q = (
                select(DailyRunModel)
                .where(DailyRunModel.company_id == company_slug)
                .order_by(DailyRunModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(q)).scalars().all()

            runs = [
                RunStatusResponse(
                    run_id=str(row.id),
                    company_id=row.company_id,
                    status=row.status or "unknown",
                    prompt_count=row.prompt_count or 0,
                    engine_count=row.engine_count or 0,
                    started_at=row.started_at.isoformat() if row.started_at else None,
                    completed_at=row.completed_at.isoformat() if row.completed_at else None,
                    error=row.error,
                )
                for row in rows
            ]

            return RunListResponse(runs=runs, total=total)
    except Exception:
        logger.warning("list_runs failed for %s", company_slug, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch runs")


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
