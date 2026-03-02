# Skill: Daily Tracker — Platform Runner & Mention Detector

**Target teammate**: `platform-runner`


## Your Mission

Build two independent modules:
1. **Platform Runner** — Adapts the existing gap analysis search engines for daily tracking use
2. **Mention Detector** — Analyzes LLM responses for brand/competitor mentions and citation extraction

---

## CRITICAL: Study the Codebase First

```bash
# 1. Your interfaces (Agent 0 created)
cat core/daily_tracker/protocols.py

# 2. Your domain models (Agent 0 created)
cat core/models/daily_tracker.py

# 3. Existing search engine ABC (you WRAP this, never modify)
cat core/gap_analysis/engines/base.py

# 4. Existing engine implementations (understand how they work)
cat core/gap_analysis/engines/claude.py
cat core/gap_analysis/engines/openai_engine.py
cat core/gap_analysis/engines/gemini.py
cat core/gap_analysis/engines/perplexity.py

# 5. Existing s3_search_platforms.py (you adapt this pattern)
cat core/gap_analysis/steps/s3_search_platforms.py

# 6. PlatformResult model (this is what engines return)
cat core/models/gap_analysis.py | grep -A 20 "class PlatformResult"
cat core/models/gap_analysis.py | grep -A 10 "class CitationRef"

# 7. Project conventions
cat CLAUDE.md
```

### KEY DESIGN CONSTRAINT: DO NOT DUPLICATE ENGINE CODE

The gap analysis engines (`core/gap_analysis/engines/`) are the single source of truth for LLM platform interaction. Your Platform Runner is an **adapter** that:
1. Accepts `TrackedPrompt` objects (not `GeneratedQuery`)
2. Delegates to the existing `SearchEngine` implementations
3. Converts `PlatformResult` → `DailyRunResult`

You import and reuse, you do NOT copy or rewrite.

---

## Files You Create

### 1. `core/daily_tracker/platform_runner.py`

```python
"""Platform Runner — executes tracked prompts across LLM search engines.

This module is an ADAPTER over the existing gap analysis engines.
It follows the Single Responsibility Principle: run prompts, return results.
It does NOT analyze results (that's AnalyticsService).
It does NOT detect mentions (that's MentionDetector).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from core.daily_tracker.protocols import PlatformRunnerServiceProtocol
from core.models.daily_tracker import TrackedPrompt, DailyRunResult

# Reuse existing engines — DO NOT duplicate
from core.gap_analysis.engines import (
    SearchEngine as SearchEngineABC,
    ClaudeEngine, GeminiEngine, OpenAIEngine, PerplexityEngine,
)
from core.models.gap_analysis import PlatformResult

logger = logging.getLogger(__name__)


def _build_engine_registry() -> dict[str, SearchEngineABC]:
    """Build the engine registry. Matches s3_search_platforms._engine_registry()."""
    return {
        "perplexity": PerplexityEngine(),
        "openai": OpenAIEngine(),
        "gemini": GeminiEngine(),
        "claude": ClaudeEngine(),
    }


def _select_engines(names: list[str]) -> list[SearchEngineABC]:
    """Select engines by name. Unknown names are silently skipped."""
    registry = _build_engine_registry()
    return [registry[n.strip().lower()] for n in names if n.strip().lower() in registry]


def _platform_result_to_daily_result(
    prompt: TrackedPrompt, result: PlatformResult
) -> DailyRunResult:
    """Convert a gap analysis PlatformResult to a DailyRunResult."""
    return DailyRunResult(
        prompt_id=prompt.id,
        prompt_text=prompt.text,
        engine=result.engine,
        response_text=result.response_text or "",
        citations=[c.model_dump(mode="json") for c in (result.citations or [])],
        queried_at=datetime.now(timezone.utc),
    )


class PlatformRunnerService:
    """Runs tracked prompts across LLM platforms using existing engine adapters.

    Follows the Adapter pattern: converts TrackedPrompt → engine query → DailyRunResult.
    Uses asyncio.Semaphore for concurrency control (same pattern as s3_search_platforms).
    """

    def __init__(self, engine_registry: dict[str, SearchEngineABC] | None = None) -> None:
        self._registry = engine_registry or _build_engine_registry()

    async def run_prompts(
        self, prompts: Sequence[TrackedPrompt], engines: list[str],
        *, concurrency: int = 6,
    ) -> list[DailyRunResult]:
        """Execute all prompts across all specified engines concurrently.

        Args:
            prompts: List of tracked prompts to run.
            engines: List of engine names (e.g., ["openai", "claude", "gemini", "perplexity"]).
            concurrency: Max concurrent API calls.

        Returns:
            List of DailyRunResult for every (prompt, engine) pair.
        """
        selected_engines = [self._registry[e] for e in engines if e in self._registry]
        if not selected_engines:
            logger.warning("No valid engines selected from: %s", engines)
            return []

        semaphore = asyncio.Semaphore(concurrency)
        tasks: list[asyncio.Task[DailyRunResult]] = []

        for prompt in prompts:
            for engine in selected_engines:
                tasks.append(
                    asyncio.create_task(
                        self._run_one(prompt, engine, semaphore)
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log them
        valid_results: list[DailyRunResult] = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("Platform runner task failed: %s", r)
            else:
                valid_results.append(r)

        return valid_results

    async def _run_one(
        self, prompt: TrackedPrompt, engine: SearchEngineABC,
        semaphore: asyncio.Semaphore,
    ) -> DailyRunResult:
        """Run a single prompt on a single engine with semaphore."""
        async with semaphore:
            try:
                result: PlatformResult = await engine.search(
                    query_text=prompt.text,
                    query_id=str(prompt.id),
                )
                return _platform_result_to_daily_result(prompt, result)
            except Exception as exc:
                logger.error(
                    "Engine %s failed for prompt %s: %s",
                    engine.engine_name, prompt.id, exc,
                )
                return DailyRunResult(
                    prompt_id=prompt.id,
                    prompt_text=prompt.text,
                    engine=engine.engine_name,
                    response_text=f"ERROR: {exc}",
                    citations=[],
                    queried_at=datetime.now(timezone.utc),
                )
```

### 2. `core/daily_tracker/mention_detector.py`

```python
"""Mention Detector — analyzes LLM responses for brand and competitor presence.

Pure computation module with NO I/O dependencies.
Takes text + configuration → returns MentionAnalysis.
"""
from __future__ import annotations

import re
import logging
from typing import Sequence

from core.daily_tracker.protocols import MentionDetectorProtocol
from core.models.daily_tracker import MentionAnalysis

logger = logging.getLogger(__name__)


class MentionDetector:
    """Detects brand and competitor mentions in LLM response text.

    Uses case-insensitive text matching for brand/competitor names
    and domain matching for citation URLs.

    This is a pure function module — no database, no API calls.
    Easy to test, easy to extend.
    """

    def detect_mentions(
        self,
        response_text: str,
        *,
        brand_names: list[str],
        brand_domains: list[str],
        competitor_names: list[str] | None = None,
        competitor_domains: list[str] | None = None,
    ) -> MentionAnalysis:
        """Detect brand and competitor mentions in a response.

        Args:
            response_text: Full LLM response text.
            brand_names: List of brand name variants (e.g., ["Ramp", "Ramp Financial"]).
            brand_domains: List of brand domains (e.g., ["ramp.com"]).
            competitor_names: Optional list of competitor names.
            competitor_domains: Optional list of competitor domains.

        Returns:
            MentionAnalysis with mention flags, citation URLs, and ranks.
        """
        text_lower = response_text.lower()

        # ── Brand mentions ───────────────────────────────────────
        brand_mentioned = self._check_name_mentions(text_lower, brand_names)
        brand_mention_count = self._count_name_mentions(text_lower, brand_names)

        # ── Brand citations ──────────────────────────────────────
        brand_citation_urls = self._extract_domain_urls(response_text, brand_domains)
        brand_citation_rank = self._find_first_citation_rank(response_text, brand_domains)

        # ── Competitor mentions ──────────────────────────────────
        competitor_mention_map: dict[str, bool] = {}
        competitor_citation_map: dict[str, list[str]] = {}

        if competitor_names:
            for name in competitor_names:
                competitor_mention_map[name] = self._check_name_mentions(text_lower, [name])

        if competitor_domains:
            for domain in competitor_domains:
                urls = self._extract_domain_urls(response_text, [domain])
                if urls:
                    competitor_citation_map[domain] = urls

        return MentionAnalysis(
            brand_mentioned=brand_mentioned,
            brand_mention_count=brand_mention_count,
            brand_citation_urls=brand_citation_urls,
            brand_citation_rank=brand_citation_rank,
            competitor_mentions=competitor_mention_map,
            competitor_citation_urls=competitor_citation_map,
        )

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _check_name_mentions(text_lower: str, names: list[str]) -> bool:
        """Check if any name variant appears in the text."""
        for name in names:
            # Word-boundary match to avoid partial matches
            pattern = r'\b' + re.escape(name.lower()) + r'\b'
            if re.search(pattern, text_lower):
                return True
        return False

    @staticmethod
    def _count_name_mentions(text_lower: str, names: list[str]) -> int:
        """Count total mentions across all name variants."""
        count = 0
        for name in names:
            pattern = r'\b' + re.escape(name.lower()) + r'\b'
            count += len(re.findall(pattern, text_lower))
        return count

    @staticmethod
    def _extract_domain_urls(text: str, domains: list[str]) -> list[str]:
        """Extract URLs that match any of the given domains."""
        # Find all URLs in text
        url_pattern = r'https?://[^\s<>"\')\]]*'
        all_urls = re.findall(url_pattern, text)

        matching: list[str] = []
        for url in all_urls:
            for domain in domains:
                if domain.lower() in url.lower():
                    matching.append(url)
                    break
        return matching

    @staticmethod
    def _find_first_citation_rank(text: str, domains: list[str]) -> int | None:
        """Find the rank (1-indexed) of the first citation matching the domains."""
        url_pattern = r'https?://[^\s<>"\')\]]*'
        all_urls = re.findall(url_pattern, text)

        for rank, url in enumerate(all_urls, start=1):
            for domain in domains:
                if domain.lower() in url.lower():
                    return rank
        return None
```

### 3. Tests

**`tests/daily_tracker/test_platform_runner.py`:**

```python
"""Tests for PlatformRunnerService — always with mocked engines."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from core.daily_tracker.platform_runner import PlatformRunnerService, _platform_result_to_daily_result
from core.models.daily_tracker import TrackedPrompt, DailyRunResult
from core.models.gap_analysis import PlatformResult, CitationRef


@pytest.fixture
def mock_engine():
    engine = AsyncMock()
    engine.engine_name = "mock_engine"
    engine.search = AsyncMock(return_value=PlatformResult(
        engine="mock_engine", model="test-model",
        query_id="q1", query_text="test query",
        response_text="Ramp is a great corporate card solution. Visit ramp.com for more.",
        citations=[CitationRef(url="https://ramp.com/blog", domain="ramp.com", rank=1)],
    ))
    return engine


@pytest.fixture
def sample_prompt():
    return TrackedPrompt(
        id=uuid4(), company_id=uuid4(),
        text="What is the best corporate card?",
        tags=["finance", "corporate-card"],
        source="manual", is_active=True,
    )


class TestPlatformRunnerService:
    @pytest.mark.asyncio
    async def test_run_prompts_single_engine(self, mock_engine, sample_prompt): ...

    @pytest.mark.asyncio
    async def test_run_prompts_multiple_engines(self, sample_prompt): ...

    @pytest.mark.asyncio
    async def test_run_prompts_empty_list(self): ...

    @pytest.mark.asyncio
    async def test_run_prompts_invalid_engine_name_skipped(self, sample_prompt): ...

    @pytest.mark.asyncio
    async def test_run_prompts_engine_error_returns_error_result(self, sample_prompt): ...

    @pytest.mark.asyncio
    async def test_concurrency_semaphore_respected(self, mock_engine, sample_prompt): ...

    @pytest.mark.asyncio
    async def test_result_conversion_preserves_citations(self, mock_engine, sample_prompt): ...


class TestPlatformResultConversion:
    def test_converts_platform_result_to_daily_result(self): ...
    def test_handles_empty_citations(self): ...
    def test_handles_none_response_text(self): ...
```

**`tests/daily_tracker/test_mention_detector.py`:**

```python
"""Tests for MentionDetector — pure unit tests, no mocking needed."""
import pytest
from core.daily_tracker.mention_detector import MentionDetector


@pytest.fixture
def detector():
    return MentionDetector()


@pytest.fixture
def ramp_response():
    return (
        "When looking for corporate card solutions, Ramp stands out as a top choice. "
        "Ramp offers automated expense management and real-time spending controls. "
        "You can learn more at https://ramp.com/corporate-card. "
        "Alternatives include Brex (https://brex.com) and Divvy. "
        "For a comparison, see https://ramp.com/vs-brex."
    )


class TestBrandMentionDetection:
    def test_detects_brand_mentioned(self, detector, ramp_response): ...
    def test_detects_brand_not_mentioned(self, detector): ...
    def test_counts_multiple_mentions(self, detector, ramp_response): ...
    def test_case_insensitive_match(self, detector): ...
    def test_word_boundary_avoids_partial_match(self, detector): ...
    def test_multiple_brand_variants(self, detector): ...


class TestCitationExtraction:
    def test_extracts_brand_citation_urls(self, detector, ramp_response): ...
    def test_finds_brand_citation_rank(self, detector, ramp_response): ...
    def test_no_citation_returns_none_rank(self, detector): ...
    def test_extracts_competitor_citations(self, detector, ramp_response): ...


class TestCompetitorDetection:
    def test_detects_competitor_mentioned(self, detector, ramp_response): ...
    def test_competitor_not_mentioned(self, detector, ramp_response): ...
    def test_multiple_competitors(self, detector, ramp_response): ...


class TestEdgeCases:
    def test_empty_response(self, detector): ...
    def test_no_urls_in_response(self, detector): ...
    def test_empty_brand_names(self, detector): ...
    def test_special_characters_in_brand_name(self, detector): ...
```

---

## Files You Must NOT Touch

- `core/gap_analysis/engines/` — read only, import only
- `core/gap_analysis/steps/s3_search_platforms.py` — read only, learn from it
- `core/daily_tracker/protocols.py` — Agent 0 owns
- `core/daily_tracker/prompt_library.py` — Agent 1 owns
- `core/daily_tracker/analytics_engine.py` — Agent 3 owns

---

## Acceptance Criteria

- [ ] `PlatformRunnerService` implements `PlatformRunnerServiceProtocol`
- [ ] `MentionDetector` implements `MentionDetectorProtocol`
- [ ] **Zero code duplication** with gap analysis engines — only adapter/wrapper code
- [ ] All async operations use proper semaphore concurrency control
- [ ] Engine errors are caught and returned as error results (never crash the run)
- [ ] All tests pass with mocked engines (no real API calls)
- [ ] `python -m pytest tests/daily_tracker/test_platform_runner.py tests/daily_tracker/test_mention_detector.py -v`
- [ ] Codex gpt-5.3-codex review completed (high reasoning) — all CRITICALs fixed

## Completion Protocol

1. Run tests: `python -m pytest tests/daily_tracker/test_platform_runner.py tests/daily_tracker/test_mention_detector.py -v`
2. Run Codex review (see kickoff prompt for exact command)
3. Fix all CRITICALs, re-run tests
4. Commit with review summary
5. Message the lead: "platform-runner complete. Codex review incorporated."
