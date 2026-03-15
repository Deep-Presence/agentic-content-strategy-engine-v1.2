"""Daily Tracker Orchestrator — coordinates the full daily run pipeline.

Implements the Mediator pattern: no module talks to another directly.
The orchestrator calls each module in sequence and passes data between them.

Pipeline flow:
    1. Create run record (status=running)
    2. Fetch prompts (from PromptLibraryService)
    3. Execute across platforms (PlatformRunnerService)
    4. Detect mentions (MentionDetector) per response
    5. Store raw results (DailyRunRepository + DailyRunResponseRepository)
    6. Update run status (completed/failed)

Why Mediator: modules (prompt library, platform runner, mention detector,
analytics engine) are decoupled from each other.  Adding a new module
(e.g. a notification service) requires changes only here, not in every
module.  This also makes testing trivial — mock any module independently.

Does NOT compute analytics inline — that is a separate read-path concern
handled by AnalyticsService on demand from the API layer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from core.daily_tracker.protocols import (
    DailyTrackerOrchestratorProtocol,
    MentionDetectorProtocol,
    PlatformRunnerServiceProtocol,
    PromptLibraryServiceProtocol,
)
from core.models.daily_tracker import (
    DailyRunResult,
    MentionAnalysis,
    PlatformResponse,
    RunStatus,
    TrackedPrompt,
)

logger = logging.getLogger(__name__)


class DailyTrackerOrchestrator:
    """Coordinates the daily tracking run.

    Follows the Mediator pattern: no module talks to another directly.
    The orchestrator calls each module in sequence and passes data between them.

    Implements ``DailyTrackerOrchestratorProtocol``.
    """

    def __init__(
        self,
        prompt_service: PromptLibraryServiceProtocol,
        runner_service: PlatformRunnerServiceProtocol,
        mention_detector: MentionDetectorProtocol,
    ) -> None:
        self._prompts = prompt_service
        self._runner = runner_service
        self._detector = mention_detector

    async def execute_daily_run(
        self,
        company_id: str,
        prompt_ids: list[str] | None = None,
        engines: list[str] | None = None,
        brand: str | None = None,
        competitors: list[str] | None = None,
        concurrency: int = 6,
        run_id: str | None = None,
    ) -> DailyRunResult:
        """Execute a complete daily tracking run.

        Steps:
            1. Fetch prompts (specific IDs or all active for company)
            2. Run prompts across platforms via PlatformRunnerService
            3. Detect mentions in each response via MentionDetector
            4. Assemble DailyRunResult with mention analysis per response

        The caller (API layer) is responsible for persisting the result
        to the database.  This keeps the orchestrator free of DB dependencies,
        making it easy to test with pure mocks.

        Args:
            company_id: Company identifier.
            prompt_ids: Optional specific prompt IDs to run. If None, all
                active prompts for the company are used.
            engines: Optional list of engine names. If None, all available.
            brand: Brand name for mention detection.
            competitors: Competitor names for mention detection.
            concurrency: Max concurrent API calls (default 6).
            run_id: Optional pre-generated run UUID string. If None, a new
                UUID is generated. Caller can pre-generate to create a
                DB record before orchestration starts (in-flight visibility).

        Returns:
            DailyRunResult with all responses and mention analyses.

        Raises:
            Exception: Re-raised from platform runner on catastrophic failure.
        """
        run_id = run_id or str(uuid4())
        started_at = datetime.now(timezone.utc)

        logger.info(
            "Starting daily run %s for company %s (prompts=%s, engines=%s)",
            run_id,
            company_id,
            prompt_ids or "all-active",
            engines or "all",
        )

        try:
            # Step 1: Fetch prompts
            prompts = await self._fetch_prompts(company_id, prompt_ids)

            if not prompts:
                logger.info("Daily run %s: no prompts to run", run_id)
                return DailyRunResult(
                    run_id=run_id,
                    company_id=company_id,
                    status=RunStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    prompt_count=0,
                    engine_count=0,
                )

            # Step 2: Run prompts across platforms
            # Why: PlatformRunnerService returns a DailyRunResult with
            # PlatformResponse objects, but WITHOUT mention analysis.
            # The orchestrator enriches each response with mention data.
            run_result = await self._runner.run_prompts(
                prompts, engines=engines, concurrency=concurrency,
            )

            # Step 3: Detect mentions in each response
            enriched_responses: list[PlatformResponse] = []
            mention_analyses: list[MentionAnalysis] = []

            for response in run_result.responses:
                analysis = self._detector.detect_mentions(
                    response.response_text,
                    brand=brand or "",
                    competitors=competitors,
                )
                mention_analyses.append(analysis)
                enriched_responses.append(response)

            # Step 4: Assemble final result
            mentions_found = sum(
                1 for a in mention_analyses if a.brand_mentioned
            )

            completed_at = datetime.now(timezone.utc)

            result = DailyRunResult(
                run_id=run_id,
                company_id=company_id,
                status=RunStatus.COMPLETED,
                responses=enriched_responses,
                started_at=started_at,
                completed_at=completed_at,
                prompt_count=len(prompts),
                engine_count=run_result.engine_count,
            )

            logger.info(
                "Daily run %s completed: %d prompts x %d engines = %d responses, %d mentions",
                run_id,
                len(prompts),
                run_result.engine_count,
                len(enriched_responses),
                mentions_found,
            )

            # Why: attach mention analyses as a separate attribute so the
            # API layer can persist them alongside responses.  Using a list
            # index-aligned with responses avoids modifying the PlatformResponse
            # model (which is owned by foundations teammate).
            result._mention_analyses = mention_analyses  # type: ignore[attr-defined]

            return result

        except Exception as exc:
            logger.error("Daily run %s failed: %s", run_id, exc)
            return DailyRunResult(
                run_id=run_id,
                company_id=company_id,
                status=RunStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error=str(exc),
            )

    async def get_run_status(self, run_id: str) -> dict[str, object]:
        """Get the current status of a daily run.

        Note: This is a pass-through that the API layer can implement
        directly via DB lookup.  Provided for protocol compliance.

        Args:
            run_id: The run UUID string.

        Returns:
            Dict with run status information.
        """
        # Why: the orchestrator is stateless — it does not cache run results.
        # The API layer fetches run status directly from the DB via repos.
        # This method exists for protocol compliance only.
        return {"run_id": run_id, "status": "unknown", "message": "Use DB lookup"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_prompts(
        self,
        company_id: str,
        prompt_ids: list[str] | None,
    ) -> list[TrackedPrompt]:
        """Fetch prompts for the run.

        If specific prompt_ids are given, fetch each individually.
        Otherwise fetch all active prompts for the company.

        Args:
            company_id: Company identifier.
            prompt_ids: Optional list of specific prompt IDs.

        Returns:
            List of TrackedPrompt objects to run.
        """
        if prompt_ids:
            prompts: list[TrackedPrompt] = []
            for pid in prompt_ids:
                prompt = await self._prompts.get_prompt(pid)
                if prompt is None:
                    logger.warning("Prompt %s not found, skipping", pid)
                elif prompt.company_id != company_id:
                    logger.warning(
                        "Prompt %s belongs to %s, not %s — skipping (tenant isolation)",
                        pid, prompt.company_id, company_id,
                    )
                else:
                    prompts.append(prompt)
            return prompts

        # Fetch all active prompts for the company
        return await self._prompts.list_prompts(company_id, filters=None)
