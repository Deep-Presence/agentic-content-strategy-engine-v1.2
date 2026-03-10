"""Tests for daily tracker repositories.

Unit tests using mocked AsyncSession — no real database required.
Tests verify that repositories build correct SQLAlchemy queries and
follow the flush-only contract.

Why mocked session: DB integration tests live in tests/db/ and require
TEST_DATABASE_URL.  These tests run in CI without a database, verifying
method signatures, query construction, and contract compliance.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from core.db.repositories.daily_tracker_repo import (
    DailyRunRepository,
    DailyRunResponseRepository,
    TrackedPromptRepository,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common execute patterns."""
    session = AsyncMock()
    # Default: execute returns a result with empty scalars
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalar_one.return_value = 0
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _make_orm_prompt(**overrides: object) -> SimpleNamespace:
    """Create a fake TrackedPromptModel-like object."""
    defaults = {
        "id": uuid.uuid4(),
        "company_id": "company-abc",
        "text": "Test prompt",
        "category": None,
        "tags": [],
        "source": "manual",
        "source_metadata": None,
        "active": True,
        "platforms": [],
        "created_at": datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_orm_run(**overrides: object) -> SimpleNamespace:
    """Create a fake DailyRunModel-like object."""
    defaults = {
        "id": uuid.uuid4(),
        "company_id": "company-abc",
        "status": "completed",
        "config": None,
        "started_at": datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 2, 28, 12, 30, 0, tzinfo=timezone.utc),
        "error": None,
        "prompt_count": 10,
        "engine_count": 4,
        "created_at": datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_orm_response(**overrides: object) -> SimpleNamespace:
    """Create a fake DailyRunResponseModel-like object."""
    defaults = {
        "id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "prompt_id": uuid.uuid4(),
        "engine": "openai",
        "response_text": "Some AI response",
        "latency_ms": 500.0,
        "error": None,
        "brand_mentioned": True,
        "brand_mention_count": 2,
        "competitor_mentions": {"Brex": 1},
        "citations": ["https://example.com"],
        "citation_rank": 1,
        "created_at": datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── TrackedPromptRepository ───────────────────────────────────────────


class TestTrackedPromptRepository:
    """Tests for TrackedPromptRepository."""

    @pytest.fixture()
    def session(self) -> AsyncMock:
        return _make_mock_session()

    @pytest.fixture()
    def repo(self, session: AsyncMock) -> TrackedPromptRepository:
        return TrackedPromptRepository(session)

    @pytest.mark.asyncio
    async def test_list_by_company_basic(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company executes query and returns results."""
        prompts = [_make_orm_prompt(text="p1"), _make_orm_prompt(text="p2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = prompts
        session.execute.return_value = mock_result

        result = await repo.list_by_company("company-abc")
        assert len(result) == 2
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_company_empty(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company returns empty when no prompts exist."""
        result = await repo.list_by_company("company-abc")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_by_company_with_active_filter(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company adds active filter to query."""
        await repo.list_by_company("company-abc", is_active=True)
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_company_with_source_filter(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company adds source filter to query."""
        await repo.list_by_company("company-abc", source="gap_analysis")
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_company_with_category_filter(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company adds category filter to query."""
        await repo.list_by_company("company-abc", category="general")
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_company_with_search_text(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company adds ILIKE filter for search text."""
        await repo.list_by_company("company-abc", search_text="expense")
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_company_with_tags(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company filters by tags using JSONB containment."""
        await repo.list_by_company("company-abc", tags=["t1", "t2"])
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_company_pagination(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """list_by_company respects limit and offset."""
        await repo.list_by_company("company-abc", limit=10, offset=20)
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_active_prompts(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """get_active_prompts returns only active prompts."""
        active = [_make_orm_prompt(active=True)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = active
        session.execute.return_value = mock_result

        result = await repo.get_active_prompts("company-abc")
        assert len(result) == 1
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_count_by_company(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """count_by_company returns count from DB."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        session.execute.return_value = mock_result

        result = await repo.count_by_company("company-abc")
        assert result == 5

    @pytest.mark.asyncio
    async def test_count_by_company_with_active_filter(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """count_by_company applies active filter."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        session.execute.return_value = mock_result

        result = await repo.count_by_company("company-abc", is_active=True)
        assert result == 3

    @pytest.mark.asyncio
    async def test_bulk_create(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """bulk_create adds all instances and flushes once."""
        prompts_data = [
            {"company_id": "co", "text": "P1", "tags": [], "source": "manual"},
            {"company_id": "co", "text": "P2", "tags": [], "source": "manual"},
        ]
        # Patch the model class to avoid actual DB model instantiation
        with patch(
            "core.db.repositories.daily_tracker_repo.TrackedPromptModel"
        ) as MockModel:
            MockModel.side_effect = lambda **kw: SimpleNamespace(**kw)
            result = await repo.bulk_create(prompts_data)

        assert len(result) == 2
        assert session.add.call_count == 2
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bulk_create_empty(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """bulk_create with empty list flushes but creates nothing."""
        result = await repo.bulk_create([])
        assert result == []
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_find_by_text(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """find_by_text returns a matching prompt."""
        orm = _make_orm_prompt(text="exact match")
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = orm
        session.execute.return_value = mock_result

        result = await repo.find_by_text("company-abc", "exact match")
        assert result is not None
        assert result.text == "exact match"

    @pytest.mark.asyncio
    async def test_find_by_text_not_found(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """find_by_text returns None when no match."""
        result = await repo.find_by_text("company-abc", "no match")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists_by_text_true(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """exists_by_text returns True when prompt exists."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        session.execute.return_value = mock_result

        result = await repo.exists_by_text("company-abc", "some text")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_by_text_false(
        self, repo: TrackedPromptRepository, session: AsyncMock
    ) -> None:
        """exists_by_text returns False when prompt does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        session.execute.return_value = mock_result

        result = await repo.exists_by_text("company-abc", "no match")
        assert result is False


# ── DailyRunRepository ────────────────────────────────────────────────


class TestDailyRunRepository:
    """Tests for DailyRunRepository."""

    @pytest.fixture()
    def session(self) -> AsyncMock:
        return _make_mock_session()

    @pytest.fixture()
    def repo(self, session: AsyncMock) -> DailyRunRepository:
        return DailyRunRepository(session)

    @pytest.mark.asyncio
    async def test_get_latest_run_found(
        self, repo: DailyRunRepository, session: AsyncMock
    ) -> None:
        """get_latest_run returns the most recent run."""
        run = _make_orm_run()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = run
        session.execute.return_value = mock_result

        result = await repo.get_latest_run("company-abc")
        assert result is not None
        assert result.company_id == "company-abc"

    @pytest.mark.asyncio
    async def test_get_latest_run_none(
        self, repo: DailyRunRepository, session: AsyncMock
    ) -> None:
        """get_latest_run returns None when no runs exist."""
        result = await repo.get_latest_run("company-abc")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_runs(
        self, repo: DailyRunRepository, session: AsyncMock
    ) -> None:
        """list_runs returns runs ordered by date."""
        runs = [_make_orm_run(), _make_orm_run()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = runs
        session.execute.return_value = mock_result

        result = await repo.list_runs("company-abc")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_runs_empty(
        self, repo: DailyRunRepository, session: AsyncMock
    ) -> None:
        """list_runs returns empty list when no runs exist."""
        result = await repo.list_runs("company-abc")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_runs_pagination(
        self, repo: DailyRunRepository, session: AsyncMock
    ) -> None:
        """list_runs respects limit and offset."""
        await repo.list_runs("company-abc", limit=5, offset=10)
        session.execute.assert_awaited_once()


# ── DailyRunResponseRepository ────────────────────────────────────────


class TestDailyRunResponseRepository:
    """Tests for DailyRunResponseRepository."""

    @pytest.fixture()
    def session(self) -> AsyncMock:
        return _make_mock_session()

    @pytest.fixture()
    def repo(self, session: AsyncMock) -> DailyRunResponseRepository:
        return DailyRunResponseRepository(session)

    @pytest.mark.asyncio
    async def test_get_responses_by_run(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """get_responses_by_run returns all responses for a run."""
        run_id = uuid.uuid4()
        responses = [
            _make_orm_response(run_id=run_id, engine="openai"),
            _make_orm_response(run_id=run_id, engine="claude"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = responses
        session.execute.return_value = mock_result

        result = await repo.get_responses_by_run(run_id)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_responses_by_run_empty(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """get_responses_by_run returns empty when no responses exist."""
        result = await repo.get_responses_by_run(uuid.uuid4())
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_responses_by_run_and_engine(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """get_responses_by_run_and_engine filters by engine."""
        run_id = uuid.uuid4()
        responses = [_make_orm_response(run_id=run_id, engine="openai")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = responses
        session.execute.return_value = mock_result

        result = await repo.get_responses_by_run_and_engine(run_id, "openai")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_count_mentions_by_run(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """count_mentions_by_run returns count of brand-mentioned responses."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 7
        session.execute.return_value = mock_result

        result = await repo.count_mentions_by_run(uuid.uuid4())
        assert result == 7

    @pytest.mark.asyncio
    async def test_count_mentions_by_run_zero(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """count_mentions_by_run returns 0 when no mentions."""
        result = await repo.count_mentions_by_run(uuid.uuid4())
        assert result == 0

    @pytest.mark.asyncio
    async def test_bulk_create(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """bulk_create adds all instances and flushes once."""
        run_id = uuid.uuid4()
        prompt_id = uuid.uuid4()
        responses_data = [
            {
                "run_id": run_id,
                "prompt_id": prompt_id,
                "engine": "openai",
                "response_text": "Response 1",
            },
            {
                "run_id": run_id,
                "prompt_id": prompt_id,
                "engine": "claude",
                "response_text": "Response 2",
            },
        ]
        with patch(
            "core.db.repositories.daily_tracker_repo.DailyRunResponseModel"
        ) as MockModel:
            MockModel.side_effect = lambda **kw: SimpleNamespace(**kw)
            result = await repo.bulk_create(responses_data)

        assert len(result) == 2
        assert session.add.call_count == 2
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bulk_create_empty(
        self, repo: DailyRunResponseRepository, session: AsyncMock
    ) -> None:
        """bulk_create with empty list flushes but creates nothing."""
        result = await repo.bulk_create([])
        assert result == []
        session.flush.assert_awaited_once()
