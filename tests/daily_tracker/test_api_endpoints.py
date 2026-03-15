"""Tests for Daily Tracker API endpoints.

All service dependencies are mocked via FastAPI dependency overrides.
Uses the authenticated TestClient from the API test conftest to match
the existing API testing pattern.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import create_app
from api.auth.store import AuthStore
from api.dependencies import (
    get_analytics_service,
    get_daily_tracker_orchestrator,
    get_prompt_library_service,
)
from api.tasks.event_bus import EventBus
from api.tasks.store import TaskStore
from core.models.daily_tracker import (
    CompetitorMetrics,
    DailyRunResult,
    MentionAnalysis,
    PlatformResponse,
    PromptSource,
    RunStatus,
    TrackedPrompt,
    TrendDataPoint,
    VisibilityMetrics,
)
from core.models.organization import Company, UserProfile


# ── Test fixtures ────────────────────────────────────────────────────


_NOW = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)


def _sample_prompt(prompt_id: str = "p-1") -> TrackedPrompt:
    return TrackedPrompt(
        id=prompt_id,
        company_id="test-co",
        text="What is the best expense tool?",
        category="product_comparison",
        tags=["expense"],
        source=PromptSource.MANUAL,
        active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _sample_run_result() -> DailyRunResult:
    return DailyRunResult(
        run_id="run-001",
        company_id="test-co",
        status=RunStatus.COMPLETED,
        responses=[
            PlatformResponse(
                prompt_id="p-1",
                engine="openai",
                response_text="Ramp is great.",
                latency_ms=100.0,
                timestamp=_NOW,
            )
        ],
        started_at=_NOW,
        completed_at=_NOW,
        prompt_count=1,
        engine_count=1,
    )


@pytest.fixture()
def mock_prompt_service() -> AsyncMock:
    service = AsyncMock()
    service.create_prompt = AsyncMock(return_value=_sample_prompt())
    service.list_prompts = AsyncMock(return_value=[_sample_prompt()])
    service.get_prompt = AsyncMock(return_value=_sample_prompt())
    service.update_prompt = AsyncMock(return_value=_sample_prompt())
    service.delete_prompt = AsyncMock(return_value=True)
    service.toggle_prompt = AsyncMock(return_value=_sample_prompt())
    service.import_from_gap_analysis = AsyncMock(return_value=[_sample_prompt()])
    service.bulk_create = AsyncMock(return_value=[_sample_prompt()])
    return service


@pytest.fixture()
def mock_analytics_service() -> AsyncMock:
    service = AsyncMock()
    service.compute_visibility_metrics = AsyncMock(
        return_value=VisibilityMetrics(
            overall_mention_rate=0.75,
            by_engine={"openai": 0.8},
            total_prompts=10,
            total_responses=20,
            brand_mention_count=15,
        )
    )
    service.compute_mention_rate_trend = AsyncMock(
        return_value=[
            TrendDataPoint(
                date=_NOW, mention_rate=0.8, response_count=40, run_id="run-001"
            )
        ]
    )
    service.compute_share_of_voice = AsyncMock(
        return_value={"Ramp": 0.6, "Brex": 0.4}
    )
    service.compute_citation_rate = AsyncMock(
        return_value={
            "overall_citation_rate": 0.3,
            "avg_citation_rank": 2.5,
        }
    )
    service.get_competitor_metrics = AsyncMock(
        return_value=[
            CompetitorMetrics(
                name="Brex",
                mention_rate=0.4,
                mention_count=8,
                share_of_voice=0.3,
            )
        ]
    )
    return service


@pytest.fixture()
def mock_orchestrator() -> AsyncMock:
    orch = AsyncMock()
    orch.execute_daily_run = AsyncMock(return_value=_sample_run_result())
    orch.get_run_status = AsyncMock(
        return_value={"run_id": "run-001", "status": "completed"}
    )
    return orch


# ── Shared app/client setup ──────────────────────────────────────────


@pytest.fixture()
def _app_with_overrides(
    tmp_path,
    mock_prompt_service,
    mock_analytics_service,
    mock_orchestrator,
) -> FastAPI:
    """Create app with daily tracker DI overrides."""
    application = create_app()

    # Infrastructure state
    event_bus = EventBus()
    application.state.event_bus = event_bus
    application.state.task_store = TaskStore(
        base_dir=tmp_path / "_jobs", event_bus=event_bus
    )
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir(exist_ok=True)
    application.state.artifacts_root = artifacts_root
    auth_store = AuthStore(base_dir=artifacts_root)
    application.state.auth_store = auth_store
    application.state.secret_key = auth_store._secret_key

    # Create test company + user
    auth_store.create_company("test-co", "Test Co", "testco.com")
    company = auth_store.get_company_by_slug("test-co")
    assert company is not None
    user = auth_store.create_user(
        company_id=company.id,
        email="dev@testco.com",
        password="testpassword123",
        first_name="Test",
        last_name="User",
        role="member",
    )
    token = auth_store.create_access_token(user.id, company.slug)

    # Inject mock services as app.state overrides
    # Why: the DI functions check app.state first, so setting these
    # bypasses the real DB-backed construction.
    application.state.prompt_library_service = mock_prompt_service
    application.state.analytics_service = mock_analytics_service
    application.state.daily_tracker_orchestrator = mock_orchestrator

    # Store token for client fixture
    application.state._test_token = token

    return application


class _AuthTestClient(TestClient):
    """TestClient that auto-injects auth headers."""

    def __init__(self, app: FastAPI, token: str, **kwargs):
        super().__init__(app, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        self._token = token

    def request(self, method: str, url: str, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        if "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self._token}"
        return super().request(method, url, headers=headers, **kwargs)


@pytest.fixture()
def client(_app_with_overrides: FastAPI) -> TestClient:
    token = _app_with_overrides.state._test_token
    return _AuthTestClient(_app_with_overrides, token=token)


@pytest.fixture()
def public_client(_app_with_overrides: FastAPI) -> TestClient:
    return TestClient(_app_with_overrides)


# ── Prompt Endpoints ─────────────────────────────────────────────────


class TestCreatePrompt:
    def test_create_prompt_success(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/daily-tracker/prompts",
            json={"text": "What is the best expense tool?"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "What is the best expense tool?"

    def test_create_prompt_with_category_and_tags(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/daily-tracker/prompts",
            json={
                "text": "Test prompt",
                "category": "product_comparison",
                "tags": ["expense", "comparison"],
            },
        )
        assert resp.status_code == 201

    def test_create_prompt_duplicate_returns_409(
        self, client: TestClient, mock_prompt_service: AsyncMock
    ) -> None:
        mock_prompt_service.create_prompt.side_effect = ValueError("duplicate")
        resp = client.post(
            "/api/v1/daily-tracker/prompts",
            json={"text": "Duplicate prompt"},
        )
        assert resp.status_code == 409

    def test_create_prompt_unauthenticated(self, public_client: TestClient) -> None:
        resp = public_client.post(
            "/api/v1/daily-tracker/prompts",
            json={"text": "No auth"},
        )
        assert resp.status_code == 401


class TestListPrompts:
    def test_list_prompts_success(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data
        assert isinstance(data["prompts"], list)

    def test_list_prompts_with_filters(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/daily-tracker/prompts",
            params={"category": "product_comparison", "active": True},
        )
        assert resp.status_code == 200


class TestGetPrompt:
    def test_get_prompt_success(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/prompts/p-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "p-1"

    def test_get_prompt_not_found(
        self, client: TestClient, mock_prompt_service: AsyncMock
    ) -> None:
        mock_prompt_service.get_prompt.return_value = None
        resp = client.get("/api/v1/daily-tracker/prompts/nonexistent")
        assert resp.status_code == 404


class TestUpdatePrompt:
    def test_update_prompt_success(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/daily-tracker/prompts/p-1",
            json={"text": "Updated prompt text"},
        )
        assert resp.status_code == 200

    def test_update_prompt_no_fields(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/daily-tracker/prompts/p-1",
            json={},
        )
        assert resp.status_code == 400

    def test_update_prompt_not_found(
        self, client: TestClient, mock_prompt_service: AsyncMock
    ) -> None:
        mock_prompt_service.update_prompt.side_effect = ValueError("not found")
        resp = client.put(
            "/api/v1/daily-tracker/prompts/p-1",
            json={"text": "Updated"},
        )
        assert resp.status_code == 404


class TestDeletePrompt:
    def test_delete_prompt_success(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/daily-tracker/prompts/p-1")
        assert resp.status_code == 204

    def test_delete_prompt_not_found(
        self, client: TestClient, mock_prompt_service: AsyncMock
    ) -> None:
        mock_prompt_service.delete_prompt.return_value = False
        resp = client.delete("/api/v1/daily-tracker/prompts/nonexistent")
        assert resp.status_code == 404


class TestTogglePrompt:
    def test_toggle_prompt_success(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/daily-tracker/prompts/p-1/toggle",
            json={"active": False},
        )
        assert resp.status_code == 200

    def test_toggle_prompt_not_found(
        self, client: TestClient, mock_prompt_service: AsyncMock
    ) -> None:
        mock_prompt_service.toggle_prompt.side_effect = ValueError("not found")
        resp = client.patch(
            "/api/v1/daily-tracker/prompts/p-1/toggle",
            json={"active": True},
        )
        assert resp.status_code == 404


class TestImportPrompts:
    def test_import_prompts_success(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/daily-tracker/prompts/import",
            json={"slug": "test-co"},
        )
        assert resp.status_code == 201
        assert isinstance(resp.json(), list)

    def test_import_prompts_not_found(
        self, client: TestClient, mock_prompt_service: AsyncMock
    ) -> None:
        mock_prompt_service.import_from_gap_analysis.side_effect = FileNotFoundError(
            "queries.json not found"
        )
        resp = client.post(
            "/api/v1/daily-tracker/prompts/import",
            json={"slug": "missing-slug"},
        )
        assert resp.status_code == 404


class TestBulkCreatePrompts:
    def test_bulk_create_success(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/daily-tracker/prompts/bulk",
            json={
                "prompts": [
                    {"text": "Prompt 1"},
                    {"text": "Prompt 2", "category": "general"},
                ]
            },
        )
        assert resp.status_code == 201
        assert isinstance(resp.json(), list)


# ── Run Endpoints ────────────────────────────────────────────────────


class TestTriggerRun:
    def test_trigger_run_returns_202_with_task_id(self, client: TestClient) -> None:
        """POST /runs now launches async task and returns 202 with task_id."""
        with patch("api.routers.daily_tracker.asyncio.create_task"):
            resp = client.post(
                "/api/v1/daily-tracker/runs",
                json={},
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "running"
        assert data["pipeline"] == "daily_tracker"
        assert "run_id" in data

    def test_trigger_run_with_options(self, client: TestClient) -> None:
        with patch("api.routers.daily_tracker.asyncio.create_task"):
            resp = client.post(
                "/api/v1/daily-tracker/runs",
                json={
                    "engines": ["openai", "claude"],
                    "prompt_ids": ["p-1"],
                    "brand": "Ramp",
                    "competitors": ["Brex"],
                    "concurrency": 2,
                },
            )
        assert resp.status_code == 202

    def test_trigger_run_unauthenticated(self, public_client: TestClient) -> None:
        resp = public_client.post(
            "/api/v1/daily-tracker/runs",
            json={},
        )
        assert resp.status_code == 401


class TestGetRunStatus:
    def test_get_run_status_no_db(self, client: TestClient) -> None:
        """Without DB, GET /runs/{run_id} returns 503."""
        resp = client.get("/api/v1/daily-tracker/runs/11111111-1111-1111-1111-111111111111")
        assert resp.status_code == 503

    def test_get_run_status_invalid_uuid(self, client: TestClient) -> None:
        """Invalid UUID format returns 503 (no DB) or 400."""
        resp = client.get("/api/v1/daily-tracker/runs/not-a-uuid")
        # Without DB: 503 (db_session_factory is None)
        assert resp.status_code in (400, 503)


class TestListRuns:
    def test_list_runs_returns_empty_without_db(self, client: TestClient) -> None:
        """Without DB session factory, list_runs gracefully returns empty."""
        resp = client.get("/api/v1/daily-tracker/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []
        assert data["total"] == 0


# ── Analytics Endpoints ──────────────────────────────────────────────


class TestVisibilityMetrics:
    def test_get_visibility_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/analytics/visibility")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_mention_rate" in data
        assert data["overall_mention_rate"] == 0.75

    def test_get_visibility_metrics_with_run_id(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/daily-tracker/analytics/visibility",
            params={"run_id": "run-001"},
        )
        assert resp.status_code == 200


class TestMentionTrend:
    def test_get_mention_trend(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/analytics/mention-trend")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_get_mention_trend_custom_days(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/daily-tracker/analytics/mention-trend",
            params={"days": 7},
        )
        assert resp.status_code == 200


class TestShareOfVoice:
    def test_get_sov(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/analytics/sov")
        assert resp.status_code == 200
        data = resp.json()
        assert "Ramp" in data
        assert data["Ramp"] == 0.6


class TestCitationRates:
    def test_get_citations(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/analytics/citations")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_citation_rate" in data


class TestCompetitorMetrics:
    def test_get_competitor_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/daily-tracker/analytics/competitors")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["name"] == "Brex"


# ── Auth enforcement ─────────────────────────────────────────────────


class TestAuthEnforcement:
    """Verify all daily tracker endpoints require authentication."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/v1/daily-tracker/prompts"),
        ("POST", "/api/v1/daily-tracker/prompts"),
        ("GET", "/api/v1/daily-tracker/prompts/p-1"),
        ("PUT", "/api/v1/daily-tracker/prompts/p-1"),
        ("DELETE", "/api/v1/daily-tracker/prompts/p-1"),
        ("PATCH", "/api/v1/daily-tracker/prompts/p-1/toggle"),
        ("POST", "/api/v1/daily-tracker/prompts/import"),
        ("POST", "/api/v1/daily-tracker/prompts/bulk"),
        ("POST", "/api/v1/daily-tracker/runs"),
        ("GET", "/api/v1/daily-tracker/runs/run-001"),
        ("GET", "/api/v1/daily-tracker/runs"),
        ("GET", "/api/v1/daily-tracker/analytics/visibility"),
        ("GET", "/api/v1/daily-tracker/analytics/mention-trend"),
        ("GET", "/api/v1/daily-tracker/analytics/sov"),
        ("GET", "/api/v1/daily-tracker/analytics/citations"),
        ("GET", "/api/v1/daily-tracker/analytics/competitors"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_endpoint_requires_auth(
        self, public_client: TestClient, method: str, path: str
    ) -> None:
        if method == "GET":
            resp = public_client.get(path)
        elif method == "POST":
            resp = public_client.post(path, json={})
        elif method == "PUT":
            resp = public_client.put(path, json={})
        elif method == "DELETE":
            resp = public_client.delete(path)
        elif method == "PATCH":
            resp = public_client.patch(path, json={})
        else:
            pytest.fail(f"Unknown method: {method}")

        assert resp.status_code == 401, (
            f"{method} {path} should return 401, got {resp.status_code}"
        )
