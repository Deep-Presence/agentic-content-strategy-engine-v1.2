# Skill: Daily Tracker — Analytics Engine

**Target teammate**: `analytics`


## Your Mission

Build the **Analytics Engine** — the computation layer that transforms raw daily run responses into actionable visibility metrics: mention rates, share of voice, citation rates, and time-series trends.

This is the most metrics-heavy module. Follow the Strategy pattern with a `MetricCalculator` registry so new metrics can be added without modifying existing code (Open/Closed Principle).

---

## CRITICAL: Study the Codebase First

```bash
# 1. Your interfaces (Agent 0 created)
cat core/daily_tracker/protocols.py

# 2. Your domain models (Agent 0 created)
cat core/models/daily_tracker.py

# 3. Metric calculator base (Agent 0 created)
cat core/daily_tracker/metrics/base.py

# 4. Existing signal repository pattern (SQL aggregations — similar to what you'll do)
cat core/db/repositories/signal_repo.py | head -100
cat core/db/repositories/platform_repo.py | head -100

# 5. Existing tracking repository (you may query this)
cat core/db/repositories/tracking_repo.py

# 6. Existing tracking ORM models
cat core/db/models/tracking.py

# 7. Daily tracker ORM models (Agent 0 created)
cat core/db/models/daily_tracker.py

# 8. Daily tracker repositories (Agent 1 creates — check if available)
cat core/db/repositories/daily_tracker_repo.py 2>/dev/null || echo "Agent 1 not done yet — use Protocol interface"

# 9. Project conventions
cat CLAUDE.md
```

---

## Files You Create

### 1. `core/daily_tracker/metrics/mention_rate.py`

```python
"""Mention Rate Calculator — computes brand mention rate from daily run responses."""
from __future__ import annotations
from datetime import date
from core.daily_tracker.metrics.base import MetricCalculator


class MentionRateCalculator(MetricCalculator):
    """Computes mention rate: % of responses where the brand was mentioned.

    Variants:
    - Overall: across all engines and prompts
    - By engine: per-engine breakdown
    - By cluster: per-topic-cluster breakdown
    """

    @property
    def metric_name(self) -> str:
        return "mention_rate"

    async def compute(
        self, responses: list, *,
        date_from: date | None = None,
        date_to: date | None = None,
        group_by: str | None = None,  # "engine", "cluster", None
        **kwargs,
    ) -> dict:
        """Compute mention rate from a list of DailyRunResponseModel or dicts.

        Args:
            responses: List of response records (ORM models or dicts).
            date_from: Optional start date filter.
            date_to: Optional end date filter.
            group_by: Optional grouping dimension.

        Returns:
            {"overall": 0.45, "by_group": {"openai": 0.5, "claude": 0.4, ...}}
        """
        ...
```

### 2. `core/daily_tracker/metrics/share_of_voice.py`

```python
"""Share of Voice Calculator — computes brand's share of mentions vs competitors."""
from __future__ import annotations
from datetime import date
from core.daily_tracker.metrics.base import MetricCalculator


class ShareOfVoiceCalculator(MetricCalculator):
    """Computes SOV: brand mentions / (brand + competitor mentions).

    Three SOV variants:
    - Mention-based SOV: brand mentions ÷ total mentions for all tracked brands
    - Citation-based SOV: brand domain citations ÷ total citations
    - Prompt-based SOV: % of prompts where brand "wins" (first mentioned)
    """

    @property
    def metric_name(self) -> str:
        return "share_of_voice"

    async def compute(
        self, responses: list, *,
        date_from: date | None = None,
        date_to: date | None = None,
        brand_names: list[str] | None = None,
        competitor_names: list[str] | None = None,
        sov_type: str = "mention",  # "mention", "citation", "prompt"
        **kwargs,
    ) -> dict:
        """Compute SOV.

        Returns:
            {"brand_sov": 0.35, "competitor_sov": {"Brex": 0.25, "Divvy": 0.15, ...}, "unattributed": 0.25}
        """
        ...
```

### 3. `core/daily_tracker/metrics/citation_rate.py`

```python
"""Citation Rate Calculator — computes citation frequency by domain and URL."""
from __future__ import annotations
from datetime import date
from core.daily_tracker.metrics.base import MetricCalculator


class CitationRateCalculator(MetricCalculator):
    """Computes citation rates: how often brand domains/URLs are cited.

    Metrics:
    - Citation rate by domain: % of responses citing a given domain
    - Domain SOV: brand domains' citations ÷ total citations
    - Top cited URLs: most-cited URLs for the brand
    """

    @property
    def metric_name(self) -> str:
        return "citation_rate"

    async def compute(
        self, responses: list, *,
        date_from: date | None = None,
        date_to: date | None = None,
        brand_domains: list[str] | None = None,
        by_domain: bool = False,
        top_n: int = 10,
        **kwargs,
    ) -> dict:
        """Compute citation metrics.

        Returns:
            {
                "overall_citation_rate": 0.30,
                "by_domain": {"ramp.com": 0.25, "brex.com": 0.15, ...},
                "top_cited_urls": [{"url": "...", "count": 5}, ...],
                "domain_sov": {"ramp.com": 0.45, "brex.com": 0.30, ...},
            }
        """
        ...
```

### 4. `core/daily_tracker/metrics/trend.py`

```python
"""Trend Calculator — computes time-series data points for any metric."""
from __future__ import annotations
from datetime import date
from collections import defaultdict
from core.daily_tracker.metrics.base import MetricCalculator
from core.models.daily_tracker import TrendDataPoint


class TrendCalculator(MetricCalculator):
    """Computes time-series trends by grouping responses by date.

    Can compute trends for mention_rate, citation_rate, or any other metric.
    Groups by date, optionally by engine.
    """

    @property
    def metric_name(self) -> str:
        return "trend"

    async def compute(
        self, responses: list, *,
        date_from: date | None = None,
        date_to: date | None = None,
        metric: str = "mention_rate",
        group_by_engine: bool = False,
        **kwargs,
    ) -> list[TrendDataPoint]:
        """Compute time-series trend data.

        Args:
            responses: List of response records.
            metric: Which metric to trend ("mention_rate", "citation_rate").
            group_by_engine: If True, produce separate trend lines per engine.

        Returns:
            List of TrendDataPoint (one per date or date-engine pair).
        """
        ...
```

### 5. `core/daily_tracker/analytics_engine.py`

The main analytics service that orchestrates the metric calculators:

```python
"""Analytics Engine — orchestrates metric computation for the daily tracker.

This service uses the Strategy pattern: each metric is computed by a dedicated
MetricCalculator. New metrics can be added by creating a new calculator class
and registering it — no modification to this file needed (Open/Closed Principle).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Sequence
from uuid import UUID

from core.daily_tracker.protocols import AnalyticsServiceProtocol
from core.models.daily_tracker import (
    VisibilityMetrics, TrendDataPoint, CompetitorMetrics,
)
from core.daily_tracker.metrics.mention_rate import MentionRateCalculator
from core.daily_tracker.metrics.share_of_voice import ShareOfVoiceCalculator
from core.daily_tracker.metrics.citation_rate import CitationRateCalculator
from core.daily_tracker.metrics.trend import TrendCalculator
from core.db.repositories.daily_tracker_repo import DailyRunResponseRepository, DailyRunRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Computes visibility metrics from daily run data.

    Depends on:
    - DailyRunResponseRepository (reads raw responses)
    - MetricCalculator instances (computes specific metrics)

    Does NOT:
    - Run prompts (PlatformRunnerService)
    - Manage prompts (PromptLibraryService)
    - Orchestrate runs (DailyTrackerOrchestrator)
    """

    def __init__(
        self,
        response_repo: DailyRunResponseRepository,
        run_repo: DailyRunRepository,
    ) -> None:
        self._response_repo = response_repo
        self._run_repo = run_repo
        # Metric calculator registry
        self._mention_rate = MentionRateCalculator()
        self._sov = ShareOfVoiceCalculator()
        self._citation_rate = CitationRateCalculator()
        self._trend = TrendCalculator()

    async def compute_visibility_metrics(
        self, company_id: UUID, *,
        date_from: date | None = None,
        date_to: date | None = None,
        engines: list[str] | None = None,
    ) -> VisibilityMetrics:
        """Compute comprehensive visibility metrics for a company.

        Aggregates mention rate, prompt coverage, and response counts
        across the specified date range and engines.
        """
        # 1. Fetch runs for company in date range
        # 2. Fetch all responses for those runs (optionally filtered by engine)
        # 3. Use MentionRateCalculator to compute overall and by-engine rates
        # 4. Compute prompt coverage (unique prompts with at least one mention / total unique prompts)
        # 5. Return VisibilityMetrics
        ...

    async def compute_mention_rate_trend(
        self, company_id: UUID, *,
        days: int = 30,
        engines: list[str] | None = None,
    ) -> list[TrendDataPoint]:
        """Compute mention rate over time."""
        # 1. Fetch responses for last N days
        # 2. Use TrendCalculator with metric="mention_rate"
        # 3. Return list of TrendDataPoint
        ...

    async def compute_share_of_voice(
        self, company_id: UUID, *,
        date_from: date | None = None,
        date_to: date | None = None,
        competitor_names: list[str] | None = None,
    ) -> dict[str, float]:
        """Compute share of voice vs competitors."""
        # 1. Fetch responses
        # 2. Use ShareOfVoiceCalculator
        # 3. Return {brand: sov, competitor1: sov, ...}
        ...

    async def compute_citation_rate(
        self, company_id: UUID, *,
        date_from: date | None = None,
        date_to: date | None = None,
        by_domain: bool = False,
    ) -> dict[str, float]:
        """Compute citation rates, optionally broken down by domain."""
        ...

    async def get_competitor_metrics(
        self, company_id: UUID,
        competitor_names: list[str], *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[CompetitorMetrics]:
        """Compute per-competitor visibility metrics."""
        ...
```

### 6. Tests

**`tests/daily_tracker/test_analytics_engine.py`:**

Comprehensive tests with in-memory response data (no real DB):

```python
"""Tests for the Analytics Engine and all MetricCalculators."""
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import date, datetime, timezone

from core.daily_tracker.analytics_engine import AnalyticsService
from core.daily_tracker.metrics.mention_rate import MentionRateCalculator
from core.daily_tracker.metrics.share_of_voice import ShareOfVoiceCalculator
from core.daily_tracker.metrics.citation_rate import CitationRateCalculator
from core.daily_tracker.metrics.trend import TrendCalculator
from core.models.daily_tracker import VisibilityMetrics, TrendDataPoint, CompetitorMetrics


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_responses():
    """Create a realistic set of daily run response dicts for testing."""
    company_id = uuid4()
    return [
        # Prompt 1, OpenAI — brand mentioned + cited
        {"run_id": uuid4(), "prompt_id": uuid4(), "engine": "openai",
         "brand_mentioned": True, "brand_citation_rank": 1,
         "brand_urls_cited": ["https://ramp.com/blog"],
         "competitor_mentions": {"Brex": True, "Divvy": False},
         "competitor_urls_cited": {"brex.com": ["https://brex.com"]},
         "checked_at": datetime(2026, 2, 25, tzinfo=timezone.utc)},
        # Prompt 1, Claude — brand mentioned, not cited
        {"run_id": uuid4(), "prompt_id": uuid4(), "engine": "claude",
         "brand_mentioned": True, "brand_citation_rank": None,
         "brand_urls_cited": [],
         "competitor_mentions": {"Brex": True, "Divvy": True},
         "competitor_urls_cited": {},
         "checked_at": datetime(2026, 2, 25, tzinfo=timezone.utc)},
        # Prompt 2, OpenAI — brand NOT mentioned
        {"run_id": uuid4(), "prompt_id": uuid4(), "engine": "openai",
         "brand_mentioned": False, "brand_citation_rank": None,
         "brand_urls_cited": [],
         "competitor_mentions": {"Brex": True, "Divvy": False},
         "competitor_urls_cited": {"brex.com": ["https://brex.com/pricing"]},
         "checked_at": datetime(2026, 2, 25, tzinfo=timezone.utc)},
        # ... add more for different dates to test trends
    ]


# ── MentionRateCalculator Tests ──────────────────────────────────

class TestMentionRateCalculator:
    @pytest.fixture
    def calculator(self):
        return MentionRateCalculator()

    @pytest.mark.asyncio
    async def test_overall_mention_rate(self, calculator, sample_responses): ...

    @pytest.mark.asyncio
    async def test_mention_rate_by_engine(self, calculator, sample_responses): ...

    @pytest.mark.asyncio
    async def test_mention_rate_empty_responses(self, calculator): ...

    @pytest.mark.asyncio
    async def test_mention_rate_all_mentioned(self, calculator): ...

    @pytest.mark.asyncio
    async def test_mention_rate_none_mentioned(self, calculator): ...


# ── ShareOfVoiceCalculator Tests ─────────────────────────────────

class TestShareOfVoiceCalculator:
    @pytest.fixture
    def calculator(self):
        return ShareOfVoiceCalculator()

    @pytest.mark.asyncio
    async def test_sov_brand_vs_competitors(self, calculator, sample_responses): ...

    @pytest.mark.asyncio
    async def test_sov_no_competitors(self, calculator, sample_responses): ...

    @pytest.mark.asyncio
    async def test_sov_brand_dominates(self, calculator): ...

    @pytest.mark.asyncio
    async def test_sov_brand_absent(self, calculator): ...


# ── CitationRateCalculator Tests ─────────────────────────────────

class TestCitationRateCalculator:
    @pytest.fixture
    def calculator(self):
        return CitationRateCalculator()

    @pytest.mark.asyncio
    async def test_overall_citation_rate(self, calculator, sample_responses): ...

    @pytest.mark.asyncio
    async def test_citation_rate_by_domain(self, calculator, sample_responses): ...

    @pytest.mark.asyncio
    async def test_top_cited_urls(self, calculator, sample_responses): ...


# ── TrendCalculator Tests ────────────────────────────────────────

class TestTrendCalculator:
    @pytest.fixture
    def calculator(self):
        return TrendCalculator()

    @pytest.mark.asyncio
    async def test_daily_mention_rate_trend(self, calculator): ...

    @pytest.mark.asyncio
    async def test_trend_by_engine(self, calculator): ...

    @pytest.mark.asyncio
    async def test_trend_empty_data(self, calculator): ...


# ── AnalyticsService Integration Tests ───────────────────────────

class TestAnalyticsService:
    @pytest.fixture
    def mock_response_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_run_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_response_repo, mock_run_repo):
        return AnalyticsService(response_repo=mock_response_repo, run_repo=mock_run_repo)

    @pytest.mark.asyncio
    async def test_compute_visibility_metrics(self, service, mock_response_repo): ...

    @pytest.mark.asyncio
    async def test_compute_mention_rate_trend(self, service, mock_response_repo): ...

    @pytest.mark.asyncio
    async def test_compute_share_of_voice(self, service, mock_response_repo): ...

    @pytest.mark.asyncio
    async def test_compute_citation_rate(self, service, mock_response_repo): ...

    @pytest.mark.asyncio
    async def test_get_competitor_metrics(self, service, mock_response_repo): ...
```

---

## Files You Must NOT Touch

- `core/daily_tracker/protocols.py` — Agent 0 owns
- `core/daily_tracker/prompt_library.py` — Agent 1 owns
- `core/daily_tracker/platform_runner.py` — Agent 2 owns
- `core/daily_tracker/mention_detector.py` — Agent 2 owns
- Any existing files outside your module

---

## Acceptance Criteria

- [ ] `AnalyticsService` implements `AnalyticsServiceProtocol`
- [ ] All 4 MetricCalculators extend the `MetricCalculator` ABC
- [ ] New calculators can be added without modifying `AnalyticsService` (OCP)
- [ ] Pure computation — no API calls, no LLM calls
- [ ] All math is correct (mention rates between 0-1, SOV sums to ~1.0)
- [ ] All tests pass: `python -m pytest tests/daily_tracker/test_analytics_engine.py -v`
- [ ] Codex gpt-5.3-codex review completed (high reasoning) — all CRITICALs fixed

## Completion Protocol

1. Run tests: `python -m pytest tests/daily_tracker/test_analytics_engine.py -v`
2. Run Codex review (see kickoff prompt for exact command)
3. Fix all CRITICALs, re-run tests
4. Commit with review summary
5. Message the lead: "analytics complete. Codex review incorporated."
