"""Platform Runner — executes tracked prompts across LLM search engines.

This module is an ADAPTER over the existing gap analysis search engines
(``core/gap_analysis/engines/``).  It follows the Single Responsibility
Principle: run prompts, return results.  It does NOT analyze results
(that is the AnalyticsService) and does NOT detect mentions (that is
the MentionDetector).

Why adapter instead of new engine code:
    - Zero code duplication — the gap engines already handle all LLM API
      calls, retries, and response parsing.
    - Single point of maintenance — engine changes automatically propagate.
    - Follows Open/Closed Principle — new platforms are added in the engine
      layer, and this adapter picks them up via the registry.

Concurrency:
    Uses ``asyncio.Semaphore`` with configurable concurrency (default 6),
    matching the pattern from ``core/gap_analysis/steps/s3_search_platforms.py``.

Error handling:
    Engine errors are caught per (prompt, engine) pair and returned as
    ``PlatformResponse`` with an ``error`` field — a single engine failure
    NEVER crashes the entire run.

Implements ``PlatformRunnerServiceProtocol`` from ``core.daily_tracker.protocols``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from core.models.daily_tracker import (
    DailyRunResult,
    PlatformResponse,
    RunStatus,
    TrackedPrompt,
)

# Why: import engines from the canonical location — NEVER duplicate engine code.
from core.gap_analysis.engines import (
    ClaudeEngine,
    GeminiEngine,
    OpenAIEngine,
    PerplexityEngine,
    SearchEngine,
)

logger = logging.getLogger(__name__)

# Why: module-level registry builder so it can be mocked in tests
# via ``mock.patch("core.daily_tracker.platform_runner._build_engine_registry")``.
_ENGINE_REGISTRY: dict[str, type[SearchEngine]] = {
    "openai": OpenAIEngine,
    "claude": ClaudeEngine,
    "gemini": GeminiEngine,
    "perplexity": PerplexityEngine,
}


def _build_engine_registry() -> dict[str, SearchEngine]:
    """Instantiate all available engines.

    Returns:
        Dict mapping engine name to engine instance.
    """
    return {name: cls() for name, cls in _ENGINE_REGISTRY.items()}


class PlatformRunnerService:
    """Runs tracked prompts across LLM platforms using existing engine adapters.

    Follows the Adapter pattern: converts TrackedPrompt -> engine.search() call
    -> PlatformResponse -> DailyRunResult aggregate.

    Uses asyncio.Semaphore for concurrency control (same pattern as
    s3_search_platforms.py in gap analysis).

    Implements ``PlatformRunnerServiceProtocol``.
    """

    def __init__(
        self,
        engine_registry: dict[str, SearchEngine] | None = None,
    ) -> None:
        self._registry = engine_registry if engine_registry is not None else _build_engine_registry()

    async def run_prompts(
        self,
        prompts: list[TrackedPrompt],
        engines: list[str] | None = None,
        concurrency: int = 6,
    ) -> DailyRunResult:
        """Execute all prompts across specified engines concurrently.

        Args:
            prompts: List of tracked prompts to execute.
            engines: List of engine names. If None, uses all available.
            concurrency: Max concurrent API calls (default 6).

        Returns:
            DailyRunResult containing all PlatformResponse objects
            and aggregate metadata.
        """
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)

        engine_names = engines or list(self._registry.keys())
        selected = {
            name: self._registry[name]
            for name in engine_names
            if name in self._registry
        }

        if not selected:
            logger.warning("No valid engines selected from: %s", engine_names)
            return DailyRunResult(
                run_id=run_id,
                status=RunStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                prompt_count=len(prompts),
                engine_count=0,
            )

        if not prompts:
            return DailyRunResult(
                run_id=run_id,
                status=RunStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                prompt_count=0,
                engine_count=len(selected),
            )

        semaphore = asyncio.Semaphore(concurrency)
        tasks: list[asyncio.Task[PlatformResponse]] = []

        for prompt in prompts:
            for engine_name, engine in selected.items():
                tasks.append(
                    asyncio.create_task(
                        self._run_one(prompt, engine, engine_name, semaphore)
                    )
                )

        responses = await asyncio.gather(*tasks)

        # Why: gather with default return_exceptions=False raises on first error.
        # _run_one catches all exceptions internally, so this is safe.
        completed_at = datetime.now(timezone.utc)

        return DailyRunResult(
            run_id=run_id,
            status=RunStatus.COMPLETED,
            responses=list(responses),
            started_at=started_at,
            completed_at=completed_at,
            prompt_count=len(prompts),
            engine_count=len(selected),
        )

    async def get_available_engines(self) -> list[str]:
        """Return names of all registered engines.

        Returns:
            Sorted list of engine name strings.
        """
        return sorted(self._registry.keys())

    async def _run_one(
        self,
        prompt: TrackedPrompt,
        engine: SearchEngine,
        engine_name: str,
        semaphore: asyncio.Semaphore,
    ) -> PlatformResponse:
        """Run a single prompt on a single engine with semaphore control.

        On success, converts the gap analysis PlatformResult to a
        daily tracker PlatformResponse.  On failure, returns a
        PlatformResponse with the error field set.

        Args:
            prompt: The tracked prompt to execute.
            engine: The SearchEngine instance.
            engine_name: The engine's registry key.
            semaphore: asyncio.Semaphore for concurrency control.

        Returns:
            PlatformResponse for this (prompt, engine) pair.
        """
        async with semaphore:
            start_ms = time.monotonic()
            try:
                result = await engine.search(
                    query_text=prompt.text,
                    query_id=prompt.id,
                )
                elapsed_ms = (time.monotonic() - start_ms) * 1000

                return PlatformResponse(
                    prompt_id=prompt.id,
                    engine=engine_name,
                    response_text=result.response_text or "",
                    latency_ms=round(elapsed_ms, 2),
                    timestamp=datetime.now(timezone.utc),
                )

            except Exception as exc:
                elapsed_ms = (time.monotonic() - start_ms) * 1000
                logger.error(
                    "Engine %s failed for prompt %s: %s",
                    engine_name,
                    prompt.id,
                    exc,
                )
                return PlatformResponse(
                    prompt_id=prompt.id,
                    engine=engine_name,
                    response_text="",
                    latency_ms=round(elapsed_ms, 2),
                    error=str(exc),
                    timestamp=datetime.now(timezone.utc),
                )
