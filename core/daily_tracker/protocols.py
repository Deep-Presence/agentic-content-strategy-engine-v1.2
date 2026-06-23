"""Protocol interfaces for the Daily LLM Visibility Tracker.

Five ``@runtime_checkable`` Protocols define the contracts between modules.
Modules communicate through the orchestrator (mediator pattern), never
directly to each other.  Concrete implementations live in sibling modules.

Why runtime_checkable: allows ``isinstance()`` checks in DI factories
(``api/dependencies.py``) so the container can verify wiring at startup.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.models.daily_tracker import (
    CompetitorMetrics,
    DailyRunResult,
    FanoutGenerationResult,
    FanoutQuery,
    MentionAnalysis,
    PromptLibraryFilter,
    TrackedPrompt,
    TrendDataPoint,
    VisibilityMetrics,
)


@runtime_checkable
class PromptLibraryServiceProtocol(Protocol):
    """CRUD + import operations for tracked prompts.

    Manages the prompt library that feeds daily visibility runs.
    Supports importing prompts from gap analysis query artifacts.
    """

    async def create_prompt(
        self,
        company_id: str,
        text: str,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> TrackedPrompt: ...

    async def list_prompts(
        self,
        company_id: str,
        filters: PromptLibraryFilter | None = None,
    ) -> list[TrackedPrompt]: ...

    async def get_prompt(self, prompt_id: str) -> TrackedPrompt | None: ...

    async def update_prompt(
        self, prompt_id: str, **kwargs: object
    ) -> TrackedPrompt: ...

    async def delete_prompt(self, prompt_id: str) -> bool: ...

    async def toggle_prompt(
        self, prompt_id: str, active: bool
    ) -> TrackedPrompt: ...

    async def import_from_gap_analysis(
        self, company_id: str, slug: str
    ) -> list[TrackedPrompt]: ...

    async def bulk_create(
        self, company_id: str, prompts: list[dict[str, object]]
    ) -> list[TrackedPrompt]: ...

    async def list_fanout_queries(
        self, parent_prompt_id: str
    ) -> list[TrackedPrompt]: ...

    async def create_fanout_queries(
        self,
        parent_prompt_id: str,
        company_id: str,
        queries: list[FanoutQuery],
    ) -> list[TrackedPrompt]: ...

    async def regenerate_fanout_queries(
        self,
        parent_prompt_id: str,
        company_id: str,
        queries: list[FanoutQuery],
    ) -> list[TrackedPrompt]: ...

    async def pin_fanout(self, fanout_id: str) -> TrackedPrompt: ...

    async def unpin_fanout(self, fanout_id: str) -> TrackedPrompt: ...


@runtime_checkable
class QueryFanoutServiceProtocol(Protocol):
    """LLM-based query fanout generator.

    Generates intent-axis query variants from a parent prompt via
    a single structured OpenRouter call.
    """

    async def generate_fanout(
        self,
        parent_text: str,
        brand_name: str,
        brand_category: str = "",
        competitors: list[str] | None = None,
        target_count: int = 15,
        workspace_id: str = "",
        workspace_slug: str = "",
        company_slug: str = "",
    ) -> FanoutGenerationResult: ...


@runtime_checkable
class PlatformRunnerServiceProtocol(Protocol):
    """Adapter wrapping existing gap analysis search engines.

    Runs tracked prompts against AI platforms (ChatGPT, Claude, Gemini,
    Perplexity) using the engines from ``core/gap_analysis/engines/``.
    This is an adapter — it NEVER duplicates engine code.
    """

    async def run_prompts(
        self,
        prompts: list[TrackedPrompt],
        engines: list[str] | None = None,
        concurrency: int = 6,
        workspace_id: str = "",
        workspace_slug: str = "",
        company_slug: str = "",
    ) -> DailyRunResult: ...

    async def get_available_engines(self) -> list[str]: ...


@runtime_checkable
class MentionDetectorProtocol(Protocol):
    """Deterministic brand/competitor mention and citation detection.

    All detection is regex/string-based — no LLM calls.  Sub-millisecond
    latency per response.
    """

    def detect_mentions(
        self,
        response_text: str,
        brand: str,
        competitors: list[str] | None = None,
    ) -> MentionAnalysis: ...

    def extract_citations(self, response_text: str) -> list[str]: ...


@runtime_checkable
class AnalyticsServiceProtocol(Protocol):
    """Deterministic analytics computed from platform responses.

    Orchestrates ``MetricCalculator`` strategy instances.  All computation
    is pure Python — no LLM/AI calls.
    """

    async def compute_visibility_metrics(
        self, company_id: str, run_id: str | None = None
    ) -> VisibilityMetrics: ...

    async def compute_mention_rate_trend(
        self, company_id: str, days: int = 30
    ) -> list[TrendDataPoint]: ...

    async def compute_share_of_voice(
        self, company_id: str, run_id: str | None = None
    ) -> dict[str, float]: ...

    async def compute_citation_rate(
        self, company_id: str, run_id: str | None = None
    ) -> dict[str, object]: ...

    async def get_competitor_metrics(
        self, company_id: str, run_id: str | None = None
    ) -> list[CompetitorMetrics]: ...


@runtime_checkable
class DailyTrackerOrchestratorProtocol(Protocol):
    """Mediator coordinating the full daily-run lifecycle.

    Orchestrates prompt selection -> platform execution -> mention
    detection -> analytics computation.  Modules communicate through
    the orchestrator, never directly to each other.
    """

    async def execute_daily_run(
        self,
        company_id: str,
        prompt_ids: list[str] | None = None,
        engines: list[str] | None = None,
        workspace_id: str = "",
        workspace_slug: str = "",
    ) -> DailyRunResult: ...

    async def get_run_status(self, run_id: str) -> dict[str, object]: ...
