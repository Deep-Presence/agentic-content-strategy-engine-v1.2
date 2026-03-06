"""Analytics Engine — orchestrates metric computation for the daily tracker.

This service implements ``AnalyticsServiceProtocol`` and uses the Strategy
pattern: each metric is computed by a dedicated ``MetricCalculator``.  New
metrics can be added by creating a new calculator subclass and registering
it in ``metrics/__init__.py`` — no modification to this file needed
(Open/Closed Principle).

Architecture:
    AnalyticsService (this file)
        -> MentionRateCalculator   (mention_rate.py)
        -> ShareOfVoiceCalculator  (share_of_voice.py)
        -> CitationRateCalculator  (citation_rate.py)
        -> TrendCalculator         (trend.py)

Data flow:
    Orchestrator provides response data (list of dicts) -> AnalyticsService
    feeds it to the appropriate calculators -> returns Pydantic models.

Responsibilities:
    - Receive platform response data (already fetched by orchestrator or repo)
    - Route to the appropriate MetricCalculator
    - Assemble results into protocol-specified return types

Does NOT:
    - Fetch data from DB or filesystem (caller's responsibility)
    - Run prompts against platforms (PlatformRunnerService)
    - Manage prompts (PromptLibraryService)
    - Call any LLM or AI API
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from core.daily_tracker.metrics.base import MetricCalculator
from core.daily_tracker.metrics.citation_rate import CitationRateCalculator
from core.daily_tracker.metrics.mention_rate import MentionRateCalculator
from core.daily_tracker.metrics.share_of_voice import ShareOfVoiceCalculator
from core.daily_tracker.metrics.trend import TrendCalculator
from core.models.daily_tracker import (
    CompetitorMetrics,
    TrendDataPoint,
    VisibilityMetrics,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-access protocol — allows testability without concrete repo dependency
# ---------------------------------------------------------------------------


@runtime_checkable
class ResponseDataProvider(Protocol):
    """Minimal interface for fetching platform responses.

    Why a separate protocol instead of importing the repo directly:
        The ``DailyRunResponseRepository`` is created by the prompt-library
        teammate and may not exist at build time.  This protocol decouples
        the analytics engine from the storage layer, enabling pure-unit
        testing with mock providers.  The integration teammate wires the
        real repo at DI time.
    """

    async def get_responses_for_run(
        self, run_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all platform responses for a given run ID."""
        ...

    async def get_responses_for_company(
        self, company_id: str,
        *,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch platform responses for a company, optionally limited to N days."""
        ...


# ---------------------------------------------------------------------------
# Calculator registry
# ---------------------------------------------------------------------------

# Why: a dict registry lets new calculators be registered without editing
# this file.  The AnalyticsService iterates the registry for batch compute.
_CALCULATOR_REGISTRY: dict[str, MetricCalculator] = {}


def register_calculator(calculator: MetricCalculator) -> None:
    """Register a ``MetricCalculator`` instance in the global registry.

    Args:
        calculator: A concrete calculator to register.
    """
    _CALCULATOR_REGISTRY[calculator.name] = calculator


def get_calculator(name: str) -> MetricCalculator | None:
    """Look up a calculator by metric name.

    Args:
        name: Metric name (e.g. ``"mention_rate"``).

    Returns:
        The registered calculator instance, or ``None``.
    """
    return _CALCULATOR_REGISTRY.get(name)


def list_calculators() -> list[str]:
    """Return names of all registered calculators."""
    return list(_CALCULATOR_REGISTRY.keys())


# Auto-register the four built-in calculators on module load.
# Why: importing this module automatically makes all calculators available.
# Additional calculators can be registered by calling register_calculator()
# at application startup.
_BUILTIN_CALCULATORS: list[MetricCalculator] = [
    MentionRateCalculator(),
    ShareOfVoiceCalculator(),
    CitationRateCalculator(),
    TrendCalculator(),
]
for _calc in _BUILTIN_CALCULATORS:
    register_calculator(_calc)


# ---------------------------------------------------------------------------
# AnalyticsService
# ---------------------------------------------------------------------------


class AnalyticsService:
    """Computes visibility metrics from daily run data.

    Implements ``AnalyticsServiceProtocol`` from ``core.daily_tracker.protocols``.

    Constructor args:
        data_provider: An object implementing ``ResponseDataProvider`` to
            fetch platform responses.  In production this wraps the DB
            repository; in tests it's an ``AsyncMock``.
        brand: The tracked brand name (e.g. "Ramp").
        competitors: Optional list of competitor names.
        brand_domains: Optional list of brand-owned domains.

    Does NOT:
        - Run prompts (PlatformRunnerService)
        - Manage prompts (PromptLibraryService)
        - Orchestrate runs (DailyTrackerOrchestrator)
        - Call any LLM or external API
    """

    def __init__(
        self,
        data_provider: ResponseDataProvider,
        brand: str = "",
        competitors: list[str] | None = None,
        brand_domains: list[str] | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._brand = brand
        self._competitors = competitors or []
        self._brand_domains = brand_domains or []
        # Calculator instances from registry
        self._mention_rate = _CALCULATOR_REGISTRY.get(
            "mention_rate", MentionRateCalculator()
        )
        self._sov = _CALCULATOR_REGISTRY.get(
            "share_of_voice", ShareOfVoiceCalculator()
        )
        self._citation_rate = _CALCULATOR_REGISTRY.get(
            "citation_rate", CitationRateCalculator()
        )
        self._trend = _CALCULATOR_REGISTRY.get("trend", TrendCalculator())

    async def compute_visibility_metrics(
        self, company_id: str, run_id: str | None = None,
    ) -> VisibilityMetrics:
        """Compute aggregated visibility metrics for a company or run.

        If ``run_id`` is provided, metrics are scoped to that single run.
        Otherwise, all recent responses for the company are used.

        Args:
            company_id: Company identifier.
            run_id: Optional run ID to scope metrics to a single run.

        Returns:
            ``VisibilityMetrics`` with overall mention rate, per-engine
            breakdown, and response counts.
        """
        responses = await self._fetch_responses(company_id, run_id)

        result = await self._mention_rate.compute(responses)

        # Count total brand mentions across all responses
        brand_mention_count = sum(
            r.get("mention_analysis", {}).get("brand_mention_count", 0)
            for r in responses
        )

        # Count unique prompts
        prompt_ids = {r.get("prompt_id", "") for r in responses}
        prompt_ids.discard("")

        return VisibilityMetrics(
            overall_mention_rate=result["overall"],
            by_engine=result["by_engine"],
            total_prompts=len(prompt_ids),
            total_responses=len(responses),
            brand_mention_count=brand_mention_count,
        )

    async def compute_mention_rate_trend(
        self, company_id: str, days: int = 30,
    ) -> list[TrendDataPoint]:
        """Compute mention rate over time for a company.

        Args:
            company_id: Company identifier.
            days: Number of days to look back (default 30).

        Returns:
            List of ``TrendDataPoint`` sorted chronologically.
        """
        responses = await self._data_provider.get_responses_for_company(
            company_id, days=days
        )

        result = await self._trend.compute(responses)
        return result.get("data_points", [])

    async def compute_share_of_voice(
        self, company_id: str, run_id: str | None = None,
    ) -> dict[str, float]:
        """Compute share of voice vs competitors.

        Args:
            company_id: Company identifier.
            run_id: Optional run ID to scope.

        Returns:
            Dict mapping entity name to SOV float (brand + competitors).
        """
        responses = await self._fetch_responses(company_id, run_id)

        result = await self._sov.compute(
            responses,
            brand=self._brand,
            competitors=self._competitors,
        )

        # Flatten to {name: sov} format for protocol compliance
        flat: dict[str, float] = {self._brand or "brand": result["brand_sov"]}
        for comp_name, sov in result.get("competitor_sov", {}).items():
            flat[comp_name] = sov

        return flat

    async def compute_citation_rate(
        self, company_id: str, run_id: str | None = None,
    ) -> dict[str, object]:
        """Compute citation rates, optionally broken down by domain.

        Args:
            company_id: Company identifier.
            run_id: Optional run ID to scope.

        Returns:
            Dict with ``overall_citation_rate``, ``avg_citation_rank``,
            ``by_domain``, and ``top_cited_urls``.
        """
        responses = await self._fetch_responses(company_id, run_id)

        result = await self._citation_rate.compute(
            responses,
            brand_domains=self._brand_domains,
        )

        return result

    async def get_competitor_metrics(
        self, company_id: str, run_id: str | None = None,
    ) -> list[CompetitorMetrics]:
        """Compute per-competitor visibility metrics.

        Args:
            company_id: Company identifier.
            run_id: Optional run ID to scope.

        Returns:
            List of ``CompetitorMetrics``, one per tracked competitor.
        """
        responses = await self._fetch_responses(company_id, run_id)

        if not self._competitors:
            return []

        # Compute SOV to get competitor mention counts
        sov_result = await self._sov.compute(
            responses,
            brand=self._brand,
            competitors=self._competitors,
        )
        total_mentions = sov_result.get("total_mentions", 0)
        competitor_sov = sov_result.get("competitor_sov", {})

        # Compute per-competitor mention rate
        total_responses = len(responses) if responses else 1

        competitor_metrics: list[CompetitorMetrics] = []
        for comp_name in self._competitors:
            # Count responses where this competitor was mentioned
            comp_mentioned_count = 0
            for r in responses:
                analysis = r.get("mention_analysis", {})
                comp_mentions = analysis.get("competitor_mentions", {})
                count = comp_mentions.get(comp_name, 0)
                if isinstance(count, bool):
                    count = 1 if count else 0
                if count > 0:
                    comp_mentioned_count += 1

            # Mention rate = fraction of responses where competitor appears
            mention_rate = (
                comp_mentioned_count / total_responses
                if total_responses > 0
                else 0.0
            )

            # Total mention count (sum across all responses)
            total_comp_mentions = 0
            for r in responses:
                analysis = r.get("mention_analysis", {})
                comp_mentions = analysis.get("competitor_mentions", {})
                c = comp_mentions.get(comp_name, 0)
                if isinstance(c, bool):
                    c = 1 if c else 0
                total_comp_mentions += c

            competitor_metrics.append(
                CompetitorMetrics(
                    name=comp_name,
                    mention_rate=mention_rate,
                    mention_count=total_comp_mentions,
                    share_of_voice=competitor_sov.get(comp_name, 0.0),
                )
            )

        return competitor_metrics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_responses(
        self, company_id: str, run_id: str | None,
    ) -> list[dict[str, Any]]:
        """Fetch responses scoped by run or company.

        Args:
            company_id: Company identifier.
            run_id: If provided, fetch only this run's responses.

        Returns:
            List of response dicts.
        """
        if run_id:
            return await self._data_provider.get_responses_for_run(run_id)
        return await self._data_provider.get_responses_for_company(company_id)
