# Skill: Daily Tracker — Prompt Library

**Target teammate**: `prompt-library`

## Your Mission

Build the **Prompt Library Module** — the component that manages tracked prompts for the daily visibility tracker. Users can create, read, update, delete, tag, activate/deactivate prompts, and import them from gap analysis runs or content engine outputs.

---

## CRITICAL: Study the Codebase First

Before writing ANY code, read these files:

```bash
# 1. Your interfaces (Agent 0 created these)
cat core/daily_tracker/protocols.py

# 2. Your domain models (Agent 0 created these)
cat core/models/daily_tracker.py

# 3. Your ORM models (Agent 0 created these)
cat core/db/models/daily_tracker.py

# 4. Existing repository pattern (you follow this EXACTLY)
cat core/db/repositories/base.py
cat core/db/repositories/tracking_repo.py

# 5. Existing gap analysis queries model (you import from here)
cat core/models/gap_analysis.py | grep -A 20 "class GeneratedQuery"

# 6. How gap analysis stores queries (you read from this to import)
# Look at artifacts/gap_analysis/{slug}/queries.json format
cat core/gap_analysis/steps/s2_generate_queries.py | head -50

# 7. Existing service pattern (match this for DI)
cat api/services/protocols.py | head -50

# 8. Project conventions
cat CLAUDE.md
```

---

## Files You Create

### 1. `core/db/repositories/daily_tracker_repo.py`

Implement repositories for the daily tracker ORM models. Follow the flush-only pattern:

```python
"""Repositories for the daily tracker module."""
from __future__ import annotations
import uuid as _uuid
from typing import Sequence
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from core.db.models.daily_tracker import TrackedPromptModel, DailyRunModel, DailyRunResponseModel
from core.db.repositories.base import SQLAlchemyRepository


class TrackedPromptRepository(SQLAlchemyRepository[TrackedPromptModel]):
    model_class = TrackedPromptModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_company(
        self, company_id: _uuid.UUID, *,
        is_active: bool | None = None,
        source: str | None = None,
        cluster_name: str | None = None,
        tags: list[str] | None = None,
        search_text: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> Sequence[TrackedPromptModel]:
        """List prompts for a company with optional filters."""
        # Build query with filters
        # Use JSONB containment (@>) for tag filtering
        # Use ILIKE for text search
        ...

    async def get_active_prompts(self, company_id: _uuid.UUID) -> Sequence[TrackedPromptModel]:
        """Get all active prompts for a company (used by daily runs)."""
        ...

    async def count_by_company(self, company_id: _uuid.UUID, *, is_active: bool | None = None) -> int:
        """Count prompts for a company."""
        ...

    async def bulk_create(self, prompts: list[dict]) -> list[TrackedPromptModel]:
        """Create multiple prompts in a single flush."""
        ...

    async def exists_by_text(self, company_id: _uuid.UUID, text: str) -> bool:
        """Check if a prompt with this exact text already exists."""
        ...


class DailyRunRepository(SQLAlchemyRepository[DailyRunModel]):
    model_class = DailyRunModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_latest_run(self, company_id: _uuid.UUID) -> DailyRunModel | None:
        """Get the most recent run for a company."""
        ...

    async def list_runs(self, company_id: _uuid.UUID, *, limit: int = 20, offset: int = 0) -> Sequence[DailyRunModel]:
        """List runs ordered by date descending."""
        ...


class DailyRunResponseRepository(SQLAlchemyRepository[DailyRunResponseModel]):
    model_class = DailyRunResponseModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_responses_by_run(self, run_id: _uuid.UUID) -> Sequence[DailyRunResponseModel]:
        """Get all responses for a run."""
        ...

    async def get_responses_by_run_and_engine(self, run_id: _uuid.UUID, engine: str) -> Sequence[DailyRunResponseModel]:
        """Get responses for a specific engine within a run."""
        ...

    async def count_mentions_by_run(self, run_id: _uuid.UUID) -> int:
        """Count how many responses have brand_mentioned=True."""
        ...

    async def bulk_create(self, responses: list[dict]) -> list[DailyRunResponseModel]:
        """Store multiple responses in a single flush (used after a run completes)."""
        ...
```

### 2. `core/daily_tracker/prompt_library.py`

Implement the `PromptLibraryServiceProtocol`:

```python
"""Prompt Library Service — manages tracked prompts for daily visibility runs."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Sequence
from uuid import UUID

from core.daily_tracker.protocols import PromptLibraryServiceProtocol
from core.models.daily_tracker import (
    TrackedPrompt, PromptLibraryFilter, PromptSource, PromptImportRequest,
)
from core.db.repositories.daily_tracker_repo import TrackedPromptRepository

logger = logging.getLogger(__name__)


class PromptLibraryService:
    """Concrete implementation of the prompt library.

    Responsibilities:
    - CRUD operations for tracked prompts
    - Import from gap analysis queries.json
    - Bulk operations
    - Deduplication on import

    Does NOT:
    - Execute prompts (that's PlatformRunnerService)
    - Compute analytics (that's AnalyticsService)
    """

    def __init__(self, prompt_repo: TrackedPromptRepository) -> None:
        self._repo = prompt_repo

    async def list_prompts(
        self, company_id: UUID, *, filters: PromptLibraryFilter | None = None
    ) -> Sequence[TrackedPrompt]:
        """List prompts with optional filtering."""
        ...

    async def get_prompt(self, prompt_id: UUID) -> TrackedPrompt | None:
        ...

    async def create_prompt(
        self, company_id: UUID, *, text: str, tags: list[str] | None = None,
        cluster_name: str | None = None, source: str = "manual"
    ) -> TrackedPrompt:
        """Create a new tracked prompt. Raises ValueError if duplicate text exists."""
        ...

    async def update_prompt(self, prompt_id: UUID, **kwargs) -> TrackedPrompt | None:
        ...

    async def delete_prompt(self, prompt_id: UUID) -> bool:
        ...

    async def toggle_active(self, prompt_id: UUID, active: bool) -> TrackedPrompt | None:
        ...

    async def import_from_gap_analysis(
        self, company_id: UUID, gap_run_id: UUID, *, max_prompts: int = 50
    ) -> list[TrackedPrompt]:
        """Import prompts from a gap analysis run's queries.json.

        Reads the GeneratedQuery objects from the gap analysis artifacts,
        deduplicates against existing prompts, and creates new tracked prompts.

        Args:
            company_id: Company to import for.
            gap_run_id: Pipeline run ID for the gap analysis.
            max_prompts: Maximum number of prompts to import.

        Returns:
            List of newly created TrackedPrompt objects.
        """
        # 1. Load queries.json from artifacts/gap_analysis/{slug}/queries.json
        # 2. Parse as list of GeneratedQuery
        # 3. For each query, check if text already exists (dedup)
        # 4. Create new prompts with source=gap_analysis, source_ref_id=gap_run_id
        # 5. Preserve cluster_name from the query's cluster assignment
        ...

    async def bulk_create(
        self, company_id: UUID, prompts: list[PromptImportRequest]
    ) -> list[TrackedPrompt]:
        """Create multiple prompts, skipping duplicates."""
        ...

    # ── Private helpers ──────────────────────────────────────────
    def _orm_to_pydantic(self, model) -> TrackedPrompt:
        """Convert ORM model to Pydantic model."""
        ...
```

### 3. Tests

**`tests/daily_tracker/test_prompt_library.py`:**

Write comprehensive tests. Use mocked repositories (no real DB needed):

```python
"""Tests for the Prompt Library Service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from core.daily_tracker.prompt_library import PromptLibraryService
from core.models.daily_tracker import TrackedPrompt, PromptLibraryFilter, PromptSource, PromptImportRequest


@pytest.fixture
def mock_prompt_repo():
    repo = AsyncMock()
    repo.list_by_company = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.exists_by_text = AsyncMock(return_value=False)
    repo.bulk_create = AsyncMock(return_value=[])
    repo.get_active_prompts = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def service(mock_prompt_repo):
    return PromptLibraryService(prompt_repo=mock_prompt_repo)


class TestListPrompts:
    @pytest.mark.asyncio
    async def test_list_prompts_no_filter(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_list_prompts_with_tag_filter(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_list_prompts_with_source_filter(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_list_prompts_with_search_text(self, service, mock_prompt_repo): ...


class TestCreatePrompt:
    @pytest.mark.asyncio
    async def test_create_prompt_success(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_create_prompt_duplicate_raises(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_create_prompt_with_tags(self, service, mock_prompt_repo): ...


class TestImportFromGapAnalysis:
    @pytest.mark.asyncio
    async def test_import_deduplicates(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_import_respects_max_prompts(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_import_preserves_cluster(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_import_sets_source_gap_analysis(self, service, mock_prompt_repo): ...


class TestBulkCreate:
    @pytest.mark.asyncio
    async def test_bulk_create_skips_duplicates(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_bulk_create_empty_list(self, service, mock_prompt_repo): ...


class TestToggleActive:
    @pytest.mark.asyncio
    async def test_toggle_active_on(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_toggle_active_off(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_toggle_nonexistent_returns_none(self, service, mock_prompt_repo): ...


class TestDeletePrompt:
    @pytest.mark.asyncio
    async def test_delete_success(self, service, mock_prompt_repo): ...
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, service, mock_prompt_repo): ...
```

**`tests/daily_tracker/test_repositories.py`** (your portion):

Test TrackedPromptRepository, DailyRunRepository, DailyRunResponseRepository with in-memory mocks or proper DB fixtures.

---

## Files You Must NOT Touch

- `core/gap_analysis/` — read only, never modify
- `core/daily_tracker/protocols.py` — Agent 0 owns this
- `core/models/daily_tracker.py` — Agent 0 owns this
- `core/db/models/daily_tracker.py` — Agent 0 owns this
- Any existing files outside `core/daily_tracker/` and `core/db/repositories/daily_tracker_repo.py`

---

## Acceptance Criteria

- [ ] `PromptLibraryService` implements `PromptLibraryServiceProtocol` fully
- [ ] All repository methods work with async/await
- [ ] Import from gap analysis reads real queries.json format
- [ ] Deduplication works on prompt text
- [ ] All tests pass: `python -m pytest tests/daily_tracker/test_prompt_library.py -v`
- [ ] No circular imports
- [ ] Codex gpt-5.3-codex review completed (high reasoning) — all CRITICALs fixed

## Completion Protocol

1. Run tests: `python -m pytest tests/daily_tracker/test_prompt_library.py tests/daily_tracker/test_repositories.py -v`
2. Run Codex review (see kickoff prompt for exact command)
3. Fix all CRITICALs, re-run tests
4. Commit with review summary
5. Message the lead: "prompt-library complete. Codex review incorporated."
