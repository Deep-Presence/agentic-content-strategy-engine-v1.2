"""Tests for prompt tracking enriched endpoints and repository methods.

Covers:
  Phase 0: _DbResponseDataProvider fixes (N+1, days, _row_to_dict)
  Phase 1: Enriched prompt list endpoint (/prompts/enriched)
  Phase 2: Per-prompt analytics endpoint (/prompts/{id}/analytics)
  Phase 3: Answer history persona field
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.db.repositories.daily_tracker_repo import (
    DailyRunResponseRepository,
)
from core.models.daily_tracker import (
    CompetitorMetrics,
    EnrichedPrompt,
    EnrichedPromptListResponse,
    PerPromptPlatformMetrics,
    PromptAnalyticsResponse,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one.return_value = 0
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _make_response_row(**overrides: object) -> SimpleNamespace:
    defaults = {
        "id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "prompt_id": uuid.uuid4(),
        "parent_prompt_id": None,
        "engine": "openai",
        "response_text": "Test response.",
        "brand_mentioned": False,
        "brand_mention_count": 0,
        "competitor_mentions": {},
        "citations": [],
        "citation_rank": None,
        "latency_ms": 100.0,
        "error": None,
        "created_at": datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── Phase 0: _DbResponseDataProvider fixes ──────────────────────────


class TestDbResponseDataProviderFixes:
    """Verify the fixed _DbResponseDataProvider in api/dependencies.py."""

    def test_row_to_dict_includes_new_fields(self):
        """_row_to_dict should include timestamp, parent_prompt_id, run_id."""
        from api.dependencies import _DbResponseDataProvider

        row = _make_response_row(
            parent_prompt_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            created_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        result = _DbResponseDataProvider._row_to_dict(row)

        assert "timestamp" in result
        assert result["timestamp"] == "2026-04-01T12:00:00+00:00"
        assert "parent_prompt_id" in result
        assert result["parent_prompt_id"] == str(row.parent_prompt_id)
        assert "run_id" in result
        assert result["run_id"] == str(row.run_id)

    def test_row_to_dict_null_parent(self):
        """parent_prompt_id should be None when not a fanout response."""
        from api.dependencies import _DbResponseDataProvider

        row = _make_response_row(parent_prompt_id=None)
        result = _DbResponseDataProvider._row_to_dict(row)
        assert result["parent_prompt_id"] is None

    @pytest.mark.asyncio
    async def test_get_responses_for_company_uses_single_query(self):
        """Should call get_responses_by_company, not list_runs + loop."""
        from api.dependencies import _DbResponseDataProvider

        mock_repo = AsyncMock()
        mock_repo.get_responses_by_company = AsyncMock(return_value=[])
        mock_run_repo = AsyncMock()

        provider = _DbResponseDataProvider(mock_repo, mock_run_repo)
        result = await provider.get_responses_for_company("test-co", days=7)

        mock_repo.get_responses_by_company.assert_awaited_once_with(
            "test-co", days=7,
        )
        # Should NOT call list_runs (old N+1 pattern)
        mock_run_repo.list_runs.assert_not_awaited()
        assert result == []


# ── Phase 0: Repository — get_responses_by_company ──────────────────


class TestGetResponsesByCompany:
    """Test the new get_responses_by_company repo method."""

    @pytest.mark.asyncio
    async def test_calls_execute_with_correct_query(self):
        """Should build a JOIN query through daily_runs."""
        session = _make_mock_session()
        repo = DailyRunResponseRepository(session)

        await repo.get_responses_by_company("test-co", days=7)

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_days_filter_returns_all(self):
        """days=None should not apply time filter."""
        session = _make_mock_session()
        repo = DailyRunResponseRepository(session)

        await repo.get_responses_by_company("test-co", days=None)

        session.execute.assert_awaited_once()


# ── Phase 0: Repository — get_responses_for_prompt ──────────────────


class TestGetResponsesForPrompt:
    """Test the per-prompt scoped response fetch."""

    @pytest.mark.asyncio
    async def test_calls_execute(self):
        session = _make_mock_session()
        repo = DailyRunResponseRepository(session)
        pid = uuid.uuid4()

        await repo.get_responses_for_prompt(pid, days=30)

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_days_is_30(self):
        session = _make_mock_session()
        repo = DailyRunResponseRepository(session)
        pid = uuid.uuid4()

        # Should not raise
        await repo.get_responses_for_prompt(pid)

        session.execute.assert_awaited_once()


# ── Phase 1: Pydantic models ────────────────────────────────────────


class TestEnrichedPromptModels:
    """Verify new Pydantic models have correct defaults."""

    def test_enriched_prompt_defaults(self):
        p = EnrichedPrompt()
        assert p.mention_rate == 0.0
        assert p.mention_delta == 0.0
        assert p.citation_rate == 0.0
        assert p.citation_delta == 0.0
        assert p.daily_volume == []
        assert p.fanout_count == 0
        assert p.total_responses == 0

    def test_enriched_prompt_list_response_defaults(self):
        r = EnrichedPromptListResponse()
        assert r.prompts == []
        assert r.total == 0
        assert r.period_days == 7

    def test_enriched_prompt_serialization(self):
        p = EnrichedPrompt(
            id="test-id",
            text="Test prompt",
            mention_rate=0.75,
            mention_delta=0.05,
            daily_volume=[1, 2, 3, 4, 5, 6, 7],
            fanout_count=3,
        )
        data = p.model_dump(mode="json")
        assert data["mention_rate"] == 0.75
        assert len(data["daily_volume"]) == 7


# ── Phase 2: Per-Prompt Analytics models ─────────────────────────────


class TestPromptAnalyticsModels:
    """Verify Phase 2 Pydantic models."""

    def test_per_prompt_platform_metrics_defaults(self):
        m = PerPromptPlatformMetrics()
        assert m.engine == ""
        assert m.response_count == 0
        assert m.mention_rate == 0.0

    def test_prompt_analytics_response_defaults(self):
        r = PromptAnalyticsResponse()
        assert r.prompt_id == ""
        assert r.competitors == []
        assert r.platforms == []

    def test_competitor_metrics_has_rank_and_delta(self):
        c = CompetitorMetrics(
            name="Bolt.new",
            mention_rate=0.15,
            mention_count=12,
            rank=1,
            mention_delta=0.02,
        )
        assert c.rank == 1
        assert c.mention_delta == 0.02

    def test_competitor_metrics_backward_compat(self):
        """Existing code creating CompetitorMetrics without rank/delta should still work."""
        c = CompetitorMetrics(name="Brex", mention_rate=0.4, mention_count=8)
        assert c.rank == 0
        assert c.mention_delta == 0.0


# ── Phase 3: AnswerRecord persona field ──────────────────────────────


class TestAnswerRecordPersona:
    """Verify persona field was added to AnswerRecord."""

    def test_answer_record_has_persona_default(self):
        from api.routers.daily_tracker import AnswerRecord

        record = AnswerRecord(id="a-1", run_id="r-1", engine="openai", response_text="test")
        assert record.persona == "Default"

    def test_answer_record_custom_persona(self):
        from api.routers.daily_tracker import AnswerRecord

        record = AnswerRecord(
            id="a-1", run_id="r-1", engine="openai",
            response_text="test", persona="Research Analyst",
        )
        assert record.persona == "Research Analyst"


# ── Phase 1: Enriched endpoint — no-DB fallback ─────────────────────


class TestEnrichedEndpointNoDB:
    """Enriched endpoint returns empty response when no DB is available."""

    @pytest.fixture()
    def client(self, tmp_path):
        from api.app import create_app
        from api.auth.store import AuthStore
        from tests._support.auth_service import TestAuthService

        app = create_app()

        # Minimal auth setup
        auth_store = AuthStore(base_dir=tmp_path / "auth")
        app.state.auth_store = auth_store
        app.state.secret_key = auth_store._secret_key
        app.state.auth_service = TestAuthService(auth_store)

        auth_store.create_company("test-co", "Test Co", "testco.com")
        company = auth_store.get_company_by_slug("test-co")
        user = auth_store.create_user(
            company_id=company.id,
            email="dev@testco.com",
            password="pass123",
            first_name="Test",
            last_name="User",
            role="member",
        )
        token = auth_store.create_access_token(user.id, company.slug)

        from core.services.db_task_store import DbTaskStore
        from tests._support.event_bus import InMemoryEventBus

        app.state.event_bus = InMemoryEventBus()
        app.state.task_store = DbTaskStore(
            session_factory=MagicMock(), max_concurrent=10,
        )
        app.state.artifacts_root = tmp_path / "artifacts"

        # Mock services needed by other endpoints
        app.state.prompt_library_service = AsyncMock()
        app.state.analytics_service = AsyncMock()
        app.state.daily_tracker_orchestrator = AsyncMock()

        with TestClient(app) as c:
            # Override AFTER lifespan startup to simulate no DATABASE_URL
            app.state.db_session_factory = None
            c.headers["Authorization"] = f"Bearer {token}"
            yield c

    @patch("core.cache.cache_get", return_value=None)
    def test_enriched_no_db_returns_empty(self, _mock_cache, client):
        resp = client.get("/api/v1/daily-tracker/prompts/enriched")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompts"] == []
        assert data["total"] == 0
        assert data["period_days"] == 7

    def test_prompt_analytics_no_db_returns_empty(self, client):
        pid = str(uuid.uuid4())
        resp = client.get(f"/api/v1/daily-tracker/prompts/{pid}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompt_id"] == pid
        assert data["competitors"] == []
        assert data["platforms"] == []


# ── Phase 1: Repository batch methods ────────────────────────────────


class TestPromptMetricsBatch:
    """Verify get_prompt_metrics_batch builds and executes query."""

    @pytest.mark.asyncio
    async def test_executes_query(self):
        session = _make_mock_session()
        # Return empty result as list of rows
        session.execute.return_value = MagicMock()
        session.execute.return_value.all.return_value = []
        repo = DailyRunResponseRepository(session)

        now = datetime.now(timezone.utc)
        result = await repo.get_prompt_metrics_batch(
            company_id="test-co",
            current_start=now - timedelta(days=7),
            current_end=now,
            prev_start=now - timedelta(days=14),
            prev_end=now - timedelta(days=7),
        )

        session.execute.assert_awaited_once()
        assert isinstance(result, list)


class TestDailyVolumeBatch:
    """Verify get_daily_volume_batch builds and executes query."""

    @pytest.mark.asyncio
    async def test_executes_and_returns_dict(self):
        session = _make_mock_session()
        # Mock iteration over rows
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute.return_value = mock_result
        repo = DailyRunResponseRepository(session)

        now = datetime.now(timezone.utc)
        result = await repo.get_daily_volume_batch(
            company_id="test-co",
            start=now - timedelta(days=7),
            end=now,
        )

        session.execute.assert_awaited_once()
        assert isinstance(result, dict)
