# Skill: Daily Tracker — Orchestrator & API (Integration)

**Target teammate**: `integration`


## Your Mission

Build two components:
1. **Daily Tracker Orchestrator** — Coordinates the full daily run workflow (prompt selection → platform execution → mention detection → analytics storage)
2. **FastAPI Router** — REST API endpoints for the daily tracker feature

You are the integration layer. You wire together the work of Agents 1-3 into a working product.

---

## CRITICAL: Study the Codebase First

```bash
# 1. Your interfaces (Agent 0)
cat core/daily_tracker/protocols.py

# 2. Your domain models (Agent 0)
cat core/models/daily_tracker.py

# 3. Prompt Library Service (Agent 1)
cat core/daily_tracker/prompt_library.py

# 4. Platform Runner Service (Agent 2)
cat core/daily_tracker/platform_runner.py

# 5. Mention Detector (Agent 2)
cat core/daily_tracker/mention_detector.py

# 6. Analytics Service (Agent 3)
cat core/daily_tracker/analytics_engine.py

# 7. Repositories (Agent 1)
cat core/db/repositories/daily_tracker_repo.py

# 8. Existing API router patterns (match these EXACTLY)
cat api/routers/gap_analysis.py | head -80
cat api/routers/research.py | head -80
cat api/routers/content.py | head -80

# 9. Existing DI patterns
cat api/dependencies.py

# 10. Existing app registration
cat api/app.py | head -50

# 11. Existing task store pattern
cat api/services/task_store.py | head -50

# 12. Existing SSE event pattern
cat api/services/event_bus.py | head -50

# 13. Project conventions
cat CLAUDE.md
```

---

## Files You Create

### 1. `core/daily_tracker/orchestrator.py`

```python
"""Daily Tracker Orchestrator — coordinates the full daily run pipeline.

Pipeline flow:
1. Select prompts (from PromptLibraryService)
2. Execute across platforms (PlatformRunnerService)
3. Detect mentions (MentionDetector)
4. Store raw results (DailyRunResponseRepository)
5. Update run metadata (DailyRunRepository)
6. Optionally trigger analytics recomputation

The orchestrator does NOT compute analytics inline — that's a separate
read-path concern handled by AnalyticsService.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from core.daily_tracker.protocols import (
    DailyTrackerOrchestratorProtocol,
    PromptLibraryServiceProtocol,
    PlatformRunnerServiceProtocol,
    MentionDetectorProtocol,
)
from core.models.daily_tracker import DailyRunConfig, DailyRunResult, TrackedPrompt
from core.db.repositories.daily_tracker_repo import (
    DailyRunRepository, DailyRunResponseRepository, TrackedPromptRepository,
)

logger = logging.getLogger(__name__)


class DailyTrackerOrchestrator:
    """Coordinates the daily tracking run.

    Follows the Mediator pattern: no module talks to another directly.
    The orchestrator calls each module in sequence and passes data between them.
    """

    def __init__(
        self,
        prompt_service: PromptLibraryServiceProtocol,
        runner_service: PlatformRunnerServiceProtocol,
        mention_detector: MentionDetectorProtocol,
        run_repo: DailyRunRepository,
        response_repo: DailyRunResponseRepository,
    ) -> None:
        self._prompts = prompt_service
        self._runner = runner_service
        self._detector = mention_detector
        self._run_repo = run_repo
        self._response_repo = response_repo

    async def execute_daily_run(
        self, company_id: UUID, config: DailyRunConfig,
    ) -> UUID:
        """Execute a complete daily tracking run.

        Steps:
        1. Create a DailyRun record (status=pending)
        2. Fetch active prompts (or specific prompt_ids from config)
        3. Run prompts across platforms
        4. Detect mentions in each response
        5. Store all responses
        6. Update run status to completed

        Returns:
            The run_id of the created daily run.
        """
        run_id = uuid4()

        # Step 1: Create run record
        run = await self._run_repo.create(
            id=run_id,
            company_id=company_id,
            config=config.model_dump(mode="json"),
            status="running",
            engines_used=config.engines,
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Step 2: Get prompts
            if config.prompt_ids:
                prompts = [
                    await self._prompts.get_prompt(pid)
                    for pid in config.prompt_ids
                ]
                prompts = [p for p in prompts if p is not None]
            else:
                prompts = list(await self._prompts.list_prompts(
                    company_id, filters=None  # All active prompts
                ))

            if not prompts:
                await self._run_repo.update(
                    run_id, status="completed",
                    completed_at=datetime.now(timezone.utc),
                    prompts_count=0, responses_count=0, mentions_found=0,
                )
                return run_id

            # Step 3: Run prompts across platforms
            results: list[DailyRunResult] = await self._runner.run_prompts(
                prompts, config.engines, concurrency=config.concurrency,
            )

            # Step 4: Detect mentions + Step 5: Store responses
            mentions_found = 0
            response_records = []

            for result in results:
                analysis = self._detector.detect_mentions(
                    result.response_text,
                    brand_names=config.brand_names,
                    brand_domains=config.brand_domains,
                    competitor_names=config.competitor_names or None,
                    competitor_domains=config.competitor_domains or None,
                )

                response_records.append({
                    "run_id": run_id,
                    "prompt_id": result.prompt_id,
                    "engine": result.engine,
                    "response_text": result.response_text,
                    "citations_json": result.citations,
                    "brand_mentioned": analysis.brand_mentioned,
                    "brand_citation_rank": analysis.brand_citation_rank,
                    "brand_urls_cited": analysis.brand_citation_urls,
                    "competitor_mentions": analysis.competitor_mentions,
                    "competitor_urls_cited": analysis.competitor_citation_urls,
                    "sentiment": analysis.sentiment,
                    "checked_at": result.queried_at,
                })

                if analysis.brand_mentioned:
                    mentions_found += 1

            # Bulk store responses
            await self._response_repo.bulk_create(response_records)

            # Step 6: Update run status
            await self._run_repo.update(
                run_id,
                status="completed",
                completed_at=datetime.now(timezone.utc),
                prompts_count=len(prompts),
                responses_count=len(results),
                mentions_found=mentions_found,
            )

            logger.info(
                "Daily run %s completed: %d prompts × %d engines = %d responses, %d mentions",
                run_id, len(prompts), len(config.engines), len(results), mentions_found,
            )
            return run_id

        except Exception as exc:
            logger.error("Daily run %s failed: %s", run_id, exc)
            await self._run_repo.update(
                run_id,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
            raise

    async def get_run_status(self, run_id: UUID) -> dict:
        """Get the current status of a daily run."""
        run = await self._run_repo.get_by_id(run_id)
        if not run:
            return {"error": "Run not found"}
        return {
            "run_id": str(run.id),
            "status": run.status,
            "prompts_count": run.prompts_count,
            "responses_count": run.responses_count,
            "mentions_found": run.mentions_found,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error_message": run.error_message,
        }
```

### 2. `api/routers/daily_tracker.py`

Follow the EXACT patterns from existing routers:

```python
"""Daily Tracker API — prompt library management, run triggers, analytics queries.

Endpoints:
  POST   /api/v1/daily-tracker/prompts              Create a tracked prompt
  GET    /api/v1/daily-tracker/prompts               List tracked prompts
  GET    /api/v1/daily-tracker/prompts/{prompt_id}   Get a specific prompt
  PUT    /api/v1/daily-tracker/prompts/{prompt_id}   Update a prompt
  DELETE /api/v1/daily-tracker/prompts/{prompt_id}   Delete a prompt
  PATCH  /api/v1/daily-tracker/prompts/{prompt_id}/toggle  Toggle active status
  POST   /api/v1/daily-tracker/prompts/import        Import from gap analysis
  POST   /api/v1/daily-tracker/prompts/bulk          Bulk create prompts

  POST   /api/v1/daily-tracker/runs                  Trigger a daily run
  GET    /api/v1/daily-tracker/runs/{run_id}         Get run status
  GET    /api/v1/daily-tracker/runs                  List runs for company

  GET    /api/v1/daily-tracker/analytics/visibility   Get visibility metrics
  GET    /api/v1/daily-tracker/analytics/mention-trend Get mention rate trend
  GET    /api/v1/daily-tracker/analytics/sov          Get share of voice
  GET    /api/v1/daily-tracker/analytics/citations    Get citation rates
  GET    /api/v1/daily-tracker/analytics/competitors  Get competitor metrics
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from core.models.daily_tracker import (
    TrackedPrompt, PromptLibraryFilter, DailyRunConfig,
    VisibilityMetrics, TrendDataPoint, CompetitorMetrics,
    PromptImportRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daily-tracker", tags=["daily-tracker"])


# ── Request/Response Schemas ─────────────────────────────────────

class CreatePromptRequest(BaseModel):
    text: str
    tags: list[str] = Field(default_factory=list)
    cluster_name: str | None = None

class UpdatePromptRequest(BaseModel):
    text: str | None = None
    tags: list[str] | None = None
    cluster_name: str | None = None
    is_active: bool | None = None

class ToggleActiveRequest(BaseModel):
    active: bool

class ImportPromptsRequest(BaseModel):
    gap_run_id: UUID
    max_prompts: int = 50

class BulkCreatePromptsRequest(BaseModel):
    prompts: list[PromptImportRequest]

class TriggerRunRequest(BaseModel):
    config: DailyRunConfig

class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    prompts_count: int
    responses_count: int
    mentions_found: int
    started_at: str | None
    completed_at: str | None
    error_message: str | None = None

class VisibilityMetricsRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    engines: list[str] | None = None

class TrendRequest(BaseModel):
    days: int = 30
    engines: list[str] | None = None

class SOVRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    competitor_names: list[str] | None = None

class CitationRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    by_domain: bool = False

class CompetitorRequest(BaseModel):
    competitor_names: list[str]
    date_from: date | None = None
    date_to: date | None = None


# ── Dependency injection ─────────────────────────────────────────
# Follow the pattern from api/dependencies.py
# You'll need to add get_prompt_library_service(), get_analytics_service(),
# get_daily_tracker_orchestrator() to api/dependencies.py

# ── Prompt Library Endpoints ─────────────────────────────────────

@router.post("/prompts", status_code=201)
async def create_prompt(
    request: CreatePromptRequest,
    company_id: UUID = Query(...),  # In production, from auth context
):
    """Create a new tracked prompt."""
    ...

@router.get("/prompts")
async def list_prompts(
    company_id: UUID = Query(...),
    tags: list[str] | None = Query(None),
    source: str | None = Query(None),
    is_active: bool | None = Query(None),
    search_text: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List tracked prompts with optional filters."""
    ...

@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: UUID):
    ...

@router.put("/prompts/{prompt_id}")
async def update_prompt(prompt_id: UUID, request: UpdatePromptRequest):
    ...

@router.delete("/prompts/{prompt_id}", status_code=204)
async def delete_prompt(prompt_id: UUID):
    ...

@router.patch("/prompts/{prompt_id}/toggle")
async def toggle_prompt(prompt_id: UUID, request: ToggleActiveRequest):
    ...

@router.post("/prompts/import")
async def import_prompts(
    request: ImportPromptsRequest,
    company_id: UUID = Query(...),
):
    """Import prompts from a gap analysis run."""
    ...

@router.post("/prompts/bulk", status_code=201)
async def bulk_create_prompts(
    request: BulkCreatePromptsRequest,
    company_id: UUID = Query(...),
):
    ...


# ── Run Management Endpoints ────────────────────────────────────

@router.post("/runs", status_code=202)
async def trigger_daily_run(
    request: TriggerRunRequest,
    company_id: UUID = Query(...),
    background_tasks: BackgroundTasks = None,
):
    """Trigger a daily tracking run. Runs async in the background."""
    # Use asyncio.create_task() following existing pattern from gap_analysis router
    ...

@router.get("/runs/{run_id}")
async def get_run_status(run_id: UUID):
    ...

@router.get("/runs")
async def list_runs(
    company_id: UUID = Query(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    ...


# ── Analytics Endpoints ──────────────────────────────────────────

@router.get("/analytics/visibility")
async def get_visibility_metrics(
    company_id: UUID = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    engines: list[str] | None = Query(None),
):
    """Get comprehensive visibility metrics."""
    ...

@router.get("/analytics/mention-trend")
async def get_mention_trend(
    company_id: UUID = Query(...),
    days: int = Query(30, ge=1, le=365),
    engines: list[str] | None = Query(None),
):
    """Get mention rate trend over time."""
    ...

@router.get("/analytics/sov")
async def get_share_of_voice(
    company_id: UUID = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    competitor_names: list[str] | None = Query(None),
):
    ...

@router.get("/analytics/citations")
async def get_citation_rates(
    company_id: UUID = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    by_domain: bool = Query(False),
):
    ...

@router.get("/analytics/competitors")
async def get_competitor_metrics(
    company_id: UUID = Query(...),
    competitor_names: list[str] = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    ...
```

### 3. `api/dependencies.py` additions

Add DI functions for the daily tracker services. **Append to the existing file, do NOT replace it:**

```python
# In api/dependencies.py — ADD these functions (don't replace existing ones)

async def get_prompt_library_service(session=Depends(get_db_session)):
    from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
    from core.daily_tracker.prompt_library import PromptLibraryService
    repo = TrackedPromptRepository(session)
    return PromptLibraryService(prompt_repo=repo)

async def get_analytics_service(session=Depends(get_db_session)):
    from core.db.repositories.daily_tracker_repo import DailyRunResponseRepository, DailyRunRepository
    from core.daily_tracker.analytics_engine import AnalyticsService
    response_repo = DailyRunResponseRepository(session)
    run_repo = DailyRunRepository(session)
    return AnalyticsService(response_repo=response_repo, run_repo=run_repo)

async def get_daily_tracker_orchestrator(session=Depends(get_db_session)):
    from core.db.repositories.daily_tracker_repo import (
        TrackedPromptRepository, DailyRunRepository, DailyRunResponseRepository,
    )
    from core.daily_tracker.prompt_library import PromptLibraryService
    from core.daily_tracker.platform_runner import PlatformRunnerService
    from core.daily_tracker.mention_detector import MentionDetector
    from core.daily_tracker.orchestrator import DailyTrackerOrchestrator

    prompt_repo = TrackedPromptRepository(session)
    run_repo = DailyRunRepository(session)
    response_repo = DailyRunResponseRepository(session)

    return DailyTrackerOrchestrator(
        prompt_service=PromptLibraryService(prompt_repo=prompt_repo),
        runner_service=PlatformRunnerService(),
        mention_detector=MentionDetector(),
        run_repo=run_repo,
        response_repo=response_repo,
    )
```

### 4. `api/app.py` registration

**Add the router registration (don't replace existing registrations):**

```python
from api.routers.daily_tracker import router as daily_tracker_router
app.include_router(daily_tracker_router, prefix="/api/v1")
```

### 5. Tests

**`tests/daily_tracker/test_orchestrator.py`:**

```python
"""Tests for DailyTrackerOrchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from core.daily_tracker.orchestrator import DailyTrackerOrchestrator
from core.models.daily_tracker import DailyRunConfig, TrackedPrompt, DailyRunResult, MentionAnalysis


class TestDailyTrackerOrchestrator:
    @pytest.fixture
    def mock_services(self):
        return {
            "prompt_service": AsyncMock(),
            "runner_service": AsyncMock(),
            "mention_detector": MagicMock(),
            "run_repo": AsyncMock(),
            "response_repo": AsyncMock(),
        }

    @pytest.fixture
    def orchestrator(self, mock_services):
        return DailyTrackerOrchestrator(**mock_services)

    @pytest.mark.asyncio
    async def test_full_run_success(self, orchestrator, mock_services): ...
    @pytest.mark.asyncio
    async def test_run_no_prompts(self, orchestrator, mock_services): ...
    @pytest.mark.asyncio
    async def test_run_with_specific_prompt_ids(self, orchestrator, mock_services): ...
    @pytest.mark.asyncio
    async def test_run_failure_sets_error_status(self, orchestrator, mock_services): ...
    @pytest.mark.asyncio
    async def test_run_counts_mentions_correctly(self, orchestrator, mock_services): ...
    @pytest.mark.asyncio
    async def test_run_stores_all_responses(self, orchestrator, mock_services): ...
```

**`tests/daily_tracker/test_api_endpoints.py`:**

```python
"""Tests for Daily Tracker API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from api.app import app


class TestPromptEndpoints:
    @pytest.mark.asyncio
    async def test_create_prompt(self): ...
    @pytest.mark.asyncio
    async def test_list_prompts(self): ...
    @pytest.mark.asyncio
    async def test_get_prompt(self): ...
    @pytest.mark.asyncio
    async def test_update_prompt(self): ...
    @pytest.mark.asyncio
    async def test_delete_prompt(self): ...
    @pytest.mark.asyncio
    async def test_toggle_prompt(self): ...
    @pytest.mark.asyncio
    async def test_import_prompts(self): ...
    @pytest.mark.asyncio
    async def test_bulk_create_prompts(self): ...


class TestRunEndpoints:
    @pytest.mark.asyncio
    async def test_trigger_run(self): ...
    @pytest.mark.asyncio
    async def test_get_run_status(self): ...
    @pytest.mark.asyncio
    async def test_list_runs(self): ...


class TestAnalyticsEndpoints:
    @pytest.mark.asyncio
    async def test_get_visibility_metrics(self): ...
    @pytest.mark.asyncio
    async def test_get_mention_trend(self): ...
    @pytest.mark.asyncio
    async def test_get_sov(self): ...
    @pytest.mark.asyncio
    async def test_get_citations(self): ...
    @pytest.mark.asyncio
    async def test_get_competitor_metrics(self): ...
```

---

## Files You Must NOT Touch

- `core/daily_tracker/protocols.py` — Agent 0 owns
- `core/daily_tracker/prompt_library.py` — Agent 1 owns
- `core/daily_tracker/platform_runner.py` — Agent 2 owns
- `core/daily_tracker/mention_detector.py` — Agent 2 owns
- `core/daily_tracker/analytics_engine.py` — Agent 3 owns
- `core/daily_tracker/metrics/` — Agent 3 owns

**Files you APPEND to (do not replace):**
- `api/dependencies.py` — add new DI functions only
- `api/app.py` — add router registration only

---

## Acceptance Criteria

- [ ] Orchestrator follows Mediator pattern — no direct module-to-module calls
- [ ] All endpoints follow existing API patterns (auth, error handling, response schemas)
- [ ] Run trigger is async (returns immediately with run_id, processes in background)
- [ ] DI wiring matches existing FastAPI dependency injection patterns
- [ ] Router registered in app.py
- [ ] All tests pass: `python -m pytest tests/daily_tracker/ -v`
- [ ] Full integration test: create prompts → trigger run → check analytics
- [ ] Codex gpt-5.3-codex review completed (high reasoning) — all CRITICALs fixed, no regressions

## Completion Protocol

1. Run full test suite: `python -m pytest tests/daily_tracker/ -v`
2. Check for regressions: `python -m pytest tests/ -v --tb=short -q`
3. Run Codex review (see kickoff prompt for exact command)
4. Fix all CRITICALs, re-run both test suites
5. Commit with review summary
6. Message the lead: "integration complete. Codex review incorporated. Full module ready."
