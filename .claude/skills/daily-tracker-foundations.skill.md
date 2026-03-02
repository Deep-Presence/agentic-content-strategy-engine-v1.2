# Skill: Daily Tracker — Foundations (Protocols, Models, ORM, Migration)

**Target teammate**: `foundations`

## Mission

Create the foundational layer that ALL other teammates depend on: Protocol interfaces, Pydantic models, ORM tables, Alembic migration, and the MetricCalculator ABC. Zero business logic — only contracts and schemas.

## CRITICAL: Study the Codebase First

Before writing ANY code, read these files to understand existing patterns:

```bash
cat CLAUDE.md
cat core/db/models/tracking.py          # Existing ORM pattern to follow
cat core/db/models/base.py              # Base model class
cat core/db/repositories/base_repo.py   # Repository base pattern
cat core/db/enums.py                    # Existing enum patterns
cat core/settings.py                    # Settings & config
cat core/models/research.py             # Existing Pydantic model patterns
cat api/services/protocols.py           # Existing Protocol pattern
cat core/db/migrations/versions/        # List existing migrations for naming
```

## Files You Create

### 1. `core/daily_tracker/__init__.py`
Empty `__init__.py` to create the package.

### 2. `core/daily_tracker/protocols.py`

Five `@runtime_checkable` Protocol interfaces:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class PromptLibraryServiceProtocol(Protocol):
    async def create_prompt(self, company_id: str, text: str, category: str | None = None, tags: list[str] | None = None) -> TrackedPrompt: ...
    async def list_prompts(self, company_id: str, filters: PromptLibraryFilter | None = None) -> list[TrackedPrompt]: ...
    async def get_prompt(self, prompt_id: str) -> TrackedPrompt | None: ...
    async def update_prompt(self, prompt_id: str, **kwargs) -> TrackedPrompt: ...
    async def delete_prompt(self, prompt_id: str) -> bool: ...
    async def toggle_prompt(self, prompt_id: str, active: bool) -> TrackedPrompt: ...
    async def import_from_gap_analysis(self, company_id: str, slug: str) -> list[TrackedPrompt]: ...
    async def bulk_create(self, company_id: str, prompts: list[dict]) -> list[TrackedPrompt]: ...

@runtime_checkable
class PlatformRunnerServiceProtocol(Protocol):
    async def run_prompts(self, prompts: list[TrackedPrompt], engines: list[str] | None = None, concurrency: int = 6) -> DailyRunResult: ...
    async def get_available_engines(self) -> list[str]: ...

@runtime_checkable
class MentionDetectorProtocol(Protocol):
    def detect_mentions(self, response_text: str, brand: str, competitors: list[str] | None = None) -> MentionAnalysis: ...
    def extract_citations(self, response_text: str) -> list[str]: ...

@runtime_checkable
class AnalyticsServiceProtocol(Protocol):
    async def compute_visibility_metrics(self, company_id: str, run_id: str | None = None) -> VisibilityMetrics: ...
    async def compute_mention_rate_trend(self, company_id: str, days: int = 30) -> list[TrendDataPoint]: ...
    async def compute_share_of_voice(self, company_id: str, run_id: str | None = None) -> dict[str, float]: ...
    async def compute_citation_rate(self, company_id: str, run_id: str | None = None) -> dict: ...
    async def get_competitor_metrics(self, company_id: str, run_id: str | None = None) -> list[CompetitorMetrics]: ...

@runtime_checkable
class DailyTrackerOrchestratorProtocol(Protocol):
    async def execute_daily_run(self, company_id: str, prompt_ids: list[str] | None = None, engines: list[str] | None = None) -> str: ...
    async def get_run_status(self, run_id: str) -> dict: ...
```

### 3. `core/models/daily_tracker.py`

Pydantic models — follow patterns from `core/models/research.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class PromptSource(str, Enum):
    MANUAL = "manual"
    GAP_ANALYSIS = "gap_analysis"
    IMPORTED = "imported"

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TrackedPrompt(BaseModel):
    id: str
    company_id: str
    text: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: PromptSource = PromptSource.MANUAL
    source_metadata: dict | None = None  # e.g., {"cluster_name": "...", "slug": "..."}
    active: bool = True
    created_at: datetime
    updated_at: datetime

class PromptLibraryFilter(BaseModel):
    category: str | None = None
    tags: list[str] | None = None
    active: bool | None = None
    source: PromptSource | None = None
    search: str | None = None

class DailyRunConfig(BaseModel):
    company_id: str
    prompt_ids: list[str] | None = None  # None = all active prompts
    engines: list[str] | None = None     # None = all available
    concurrency: int = 6
    brand: str | None = None
    competitors: list[str] | None = None

class PlatformResponse(BaseModel):
    prompt_id: str
    engine: str
    response_text: str
    latency_ms: float
    error: str | None = None
    timestamp: datetime

class MentionAnalysis(BaseModel):
    brand_mentioned: bool
    brand_mention_count: int
    competitor_mentions: dict[str, int] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    citation_rank: int | None = None  # 1-indexed position of first brand citation

class DailyRunResult(BaseModel):
    run_id: str
    company_id: str
    status: RunStatus
    responses: list[PlatformResponse] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    prompt_count: int = 0
    engine_count: int = 0

class VisibilityMetrics(BaseModel):
    overall_mention_rate: float          # 0.0 - 1.0
    by_engine: dict[str, float]          # engine_name -> mention_rate
    total_prompts: int
    total_responses: int
    brand_mention_count: int

class TrendDataPoint(BaseModel):
    date: datetime
    mention_rate: float
    response_count: int
    run_id: str

class CompetitorMetrics(BaseModel):
    name: str
    mention_rate: float
    mention_count: int
    share_of_voice: float
```

### 4. `core/db/models/daily_tracker.py`

ORM models — follow exact patterns from `core/db/models/tracking.py`:

```python
# 3 ORM tables:
# TrackedPromptModel — prompt library
#   - id: UUID PK
#   - company_id: String, indexed
#   - text: Text, not null
#   - category: String, nullable
#   - tags: JSONB, server_default='[]'
#   - source: String (enum value), default 'manual'
#   - source_metadata: JSONB, nullable
#   - active: Boolean, default True
#   - created_at, updated_at: DateTime with timezone

# DailyRunModel — run metadata
#   - id: UUID PK
#   - company_id: String, indexed
#   - status: String (enum value), default 'pending'
#   - config: JSONB (serialized DailyRunConfig)
#   - started_at, completed_at: DateTime nullable
#   - error: Text, nullable
#   - prompt_count, engine_count: Integer
#   - created_at, updated_at: DateTime with timezone

# DailyRunResponseModel — raw LLM responses
#   - id: UUID PK
#   - run_id: UUID FK -> DailyRunModel.id
#   - prompt_id: UUID FK -> TrackedPromptModel.id
#   - engine: String
#   - response_text: Text
#   - latency_ms: Float
#   - error: Text, nullable
#   - brand_mentioned: Boolean
#   - brand_mention_count: Integer, default 0
#   - competitor_mentions: JSONB, server_default='{}'
#   - citations: JSONB, server_default='[]'
#   - citation_rank: Integer, nullable
#   - created_at: DateTime with timezone
```

Use `PgUUID(as_uuid=True)` for PKs. Follow flush-only repository contract.

### 5. `core/db/migrations/versions/0005_daily_tracker.py`

Hand-written Alembic migration (NOT autogenerated). Create all 3 tables + indexes.

### 6. `core/daily_tracker/metrics/__init__.py` and `core/daily_tracker/metrics/base.py`

```python
# base.py
from abc import ABC, abstractmethod
from typing import Any

class MetricCalculator(ABC):
    """Strategy pattern base for all daily tracker metrics."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique metric identifier."""
        ...

    @abstractmethod
    async def compute(self, responses: list, **kwargs) -> Any:
        """Compute metric from platform responses."""
        ...
```

### 7. `tests/daily_tracker/__init__.py`, `conftest.py`, `test_models.py`

- `conftest.py`: Shared fixtures (factory functions for TrackedPrompt, PlatformResponse, etc.)
- `test_models.py`: Validation tests for all Pydantic models (required fields, defaults, serialization)

## Files You Must NOT Touch

Everything outside `core/daily_tracker/`, `core/models/daily_tracker.py`, `core/db/models/daily_tracker.py`, `core/db/migrations/versions/0005_*.py`, and `tests/daily_tracker/`.

## Acceptance Criteria

- [ ] All 5 Protocols are `@runtime_checkable`
- [ ] All Pydantic models validate correctly
- [ ] ORM models follow existing patterns from `tracking.py`
- [ ] Migration is hand-written and creates all 3 tables + indexes
- [ ] `MetricCalculator` ABC has `name` property + `compute()` method
- [ ] Tests pass: `python -m pytest tests/daily_tracker/test_models.py -v`
- [ ] No circular imports
- [ ] Message the lead when done with list of created files
