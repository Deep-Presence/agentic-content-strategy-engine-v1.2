"""Tests for Content Performance API endpoints.

ContentPerformanceService is mocked via ``app.state.content_performance_service``
pre-built override (bypasses DI).
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_perf_service(monkeypatch):
    """Pre-built ContentPerformanceService mock."""
    svc = AsyncMock()
    svc.get_content_table = AsyncMock(return_value=[])
    svc.get_content_detail = AsyncMock(return_value=None)
    svc.get_velocity_insights = AsyncMock(return_value=[])
    svc.get_readiness = AsyncMock(return_value={
        "state": "not_connected",
        "message": "Connect GA4",
        "connection_active": False,
        "has_selected_property": False,
        "inventory_pages": 0,
        "inventory_paths_sample": [],
        "unmatched_ga4_paths_sample": [],
    })
    return svc


@pytest.fixture
def mock_inventory_service():
    """Pre-built ContentInventoryService mock."""
    svc = AsyncMock()
    svc.find_similar_pages = AsyncMock(return_value=[])
    svc.count_with_embeddings = AsyncMock(return_value=0)
    return svc


@pytest.fixture
def app(app, mock_perf_service, mock_inventory_service, monkeypatch):
    """Extend the base app fixture with content performance service mock.

    Also patch Redis cache to prevent real Redis calls.
    """
    app.state.content_performance_service = mock_perf_service
    app.state.content_inventory_service = mock_inventory_service

    # Disable Redis cache reads (return None = cache miss)
    monkeypatch.setattr(
        "core.services.analytics_cache.get_sync_redis_or_none",
        lambda: None,
    )
    return app


# ── 1. Content Performance Table ─────────────────────────────────────


class TestGetContentPerformanceTable:
    """GET /api/v1/content-performance/"""

    def test_empty_table(self, client: TestClient):
        resp = client.get("/api/v1/content-performance/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total_items"] == 0

    def test_with_items(self, client: TestClient, mock_perf_service):
        mock_perf_service.get_content_table.return_value = [
            {
                "inventory_id": str(uuid.uuid4()),
                "url": "https://example.com/post",
                "title": "Test Post",
                "traffic": 150,
                "ai_referrals": 20,
                "velocity": 37.5,
                "velocity_trend": "up",
                "freshness_days": 14,
                "lifecycle": "growing",
                "content_type": "blog_post",
                "word_count": 1500,
                "published_at": None,
            },
        ]
        resp = client.get("/api/v1/content-performance/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["traffic"] == 150
        assert data["items"][0]["velocity_trend"] == "up"
        assert data["total_items"] == 1

    def test_custom_days_param(self, client: TestClient, mock_perf_service):
        resp = client.get("/api/v1/content-performance/?days=14")
        assert resp.status_code == 200
        # Service should have been called
        mock_perf_service.get_content_table.assert_called_once()

    def test_days_too_low(self, client: TestClient):
        resp = client.get("/api/v1/content-performance/?days=3")
        assert resp.status_code == 422  # validation error

    def test_days_too_high(self, client: TestClient):
        resp = client.get("/api/v1/content-performance/?days=120")
        assert resp.status_code == 422

    def test_unauthenticated(self, public_client: TestClient):
        resp = public_client.get("/api/v1/content-performance/")
        assert resp.status_code == 401


class TestGetContentPerformanceReadiness:
    """GET /api/v1/content-performance/readiness"""

    def test_returns_readiness(self, client: TestClient, mock_perf_service):
        mock_perf_service.get_readiness.return_value = {
            "state": "ready",
            "message": "Ready",
            "connection_active": True,
            "has_selected_property": True,
            "inventory_pages": 2,
            "ga4_rows_total": 42,
            "ga4_rows_in_window": 9,
            "matched_inventory_pages": 2,
            "matched_inventory_pages_in_window": 1,
            "unmatched_ga4_paths_total": 1,
            "unmatched_ga4_paths_in_window": 1,
            "inventory_paths_sample": ["/blog/post"],
            "unmatched_ga4_paths_sample": [
                {"path": "/", "sessions": 8},
            ],
            "last_sync_status": "success",
            "last_sync_error": "",
        }
        resp = client.get("/api/v1/content-performance/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "ready"
        assert data["ga4_rows_total"] == 42
        assert data["matched_inventory_pages"] == 2
        assert data["unmatched_ga4_paths_sample"][0]["path"] == "/"

    def test_readiness_requires_auth(self, public_client: TestClient):
        resp = public_client.get("/api/v1/content-performance/readiness")
        assert resp.status_code == 401

    def test_readiness_uses_company_slug_for_tenant_lookup(
        self,
        client: TestClient,
        mock_perf_service,
    ):
        resp = client.get("/api/v1/content-performance/readiness")
        assert resp.status_code == 200
        mock_perf_service.get_readiness.assert_called_once()
        assert mock_perf_service.get_readiness.call_args.kwargs["tenant_id"] == "test-co"


# ── 2. Velocity Insights ─────────────────────────────────────────────


class TestGetVelocityInsights:
    """GET /api/v1/content-performance/insights/velocity"""

    def test_empty(self, client: TestClient):
        resp = client.get("/api/v1/content-performance/insights/velocity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []

    def test_with_items(self, client: TestClient, mock_perf_service):
        mock_perf_service.get_velocity_insights.return_value = [
            {
                "inventory_id": str(uuid.uuid4()),
                "url": "https://example.com/post",
                "title": "Test Post",
                "velocity": 37.5,
                "velocity_trend": "up",
                "lifecycle": "growing",
                "traffic": 150,
            },
        ]
        resp = client.get("/api/v1/content-performance/insights/velocity")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["lifecycle"] == "growing"

    def test_unauthenticated(self, public_client: TestClient):
        resp = public_client.get("/api/v1/content-performance/insights/velocity")
        assert resp.status_code == 401


# ── 3. Content Detail ────────────────────────────────────────────────


class TestGetContentDetail:
    """GET /api/v1/content-performance/{inventory_id}"""

    def test_not_found(self, client: TestClient, mock_perf_service):
        mock_perf_service.get_content_detail.return_value = None
        inv_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/content-performance/{inv_id}")
        assert resp.status_code == 404

    def test_invalid_uuid(self, client: TestClient):
        resp = client.get("/api/v1/content-performance/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid inventory_id" in resp.json()["detail"]

    def test_happy_path(self, client: TestClient, mock_perf_service):
        inv_id = str(uuid.uuid4())
        mock_perf_service.get_content_detail.return_value = {
            "inventory_id": inv_id,
            "url": "https://example.com/post",
            "title": "Test Post",
            "traffic": 200,
            "ai_referrals": 30,
            "velocity": 50.0,
            "velocity_trend": "up",
            "freshness_days": 10,
            "lifecycle": "growing",
            "published_at": "2026-03-05T00:00:00+00:00",
            "daily_traffic": [
                {"date": "2026-03-27", "sessions": 100, "pageviews": 150, "ai_sessions": 15},
                {"date": "2026-03-28", "sessions": 100, "pageviews": 150, "ai_sessions": 15},
            ],
            "source_breakdown": [
                {"channel": "organic", "sessions": 120, "percentage": 60.0},
                {"channel": "ai_referral", "sessions": 30, "percentage": 15.0},
                {"channel": "direct", "sessions": 50, "percentage": 25.0},
            ],
            "ai_platform_breakdown": [
                {"platform": "openai", "sessions": 20},
                {"platform": "anthropic", "sessions": 10},
            ],
            "freshness": {
                "content_age_days": 40,
                "last_updated_age_days": 7,
                "cited_exemplar_avg_age_days": None,
                "cited_exemplar_median_age_days": None,
                "benchmark_sample_size": 0,
                "freshness_delta_days": None,
                "freshness_score": None,
                "freshness_status": "insufficient_data",
                "freshness_reason": "Cited exemplar freshness benchmark is not available yet.",
            },
        }
        resp = client.get(f"/api/v1/content-performance/{inv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["traffic"] == 200
        assert len(data["daily_traffic"]) == 2
        assert len(data["source_breakdown"]) == 3
        assert len(data["ai_platform_breakdown"]) == 2
        assert data["published_at"] == "2026-03-05T00:00:00Z"
        assert data["freshness"]["last_updated_age_days"] == 7

    def test_detail_includes_structural_signals(self, client: TestClient, mock_perf_service):
        """structural_signals JSONB is returned when present."""
        inv_id = str(uuid.uuid4())
        mock_perf_service.get_content_detail.return_value = {
            "inventory_id": inv_id,
            "url": "https://example.com/post",
            "title": "Test Post",
            "traffic": 200,
            "ai_referrals": 30,
            "velocity": 50.0,
            "velocity_trend": "up",
            "freshness_days": 10,
            "lifecycle": "growing",
            "daily_traffic": [],
            "source_breakdown": [],
            "ai_platform_breakdown": [],
            "structural_signals": {
                "word_count": 2450,
                "has_faq_section": True,
                "reading_level": 11.5,
                "h2_count": 6,
            },
        }
        resp = client.get(f"/api/v1/content-performance/{inv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["structural_signals"]["word_count"] == 2450
        assert data["structural_signals"]["has_faq_section"] is True
        assert data["structural_signals"]["reading_level"] == 11.5

    def test_detail_structural_signals_null(self, client: TestClient, mock_perf_service):
        """structural_signals is null when page has no signals."""
        inv_id = str(uuid.uuid4())
        mock_perf_service.get_content_detail.return_value = {
            "inventory_id": inv_id,
            "url": "https://example.com/post",
            "title": "Test Post",
            "traffic": 100,
            "ai_referrals": 0,
            "velocity": 25.0,
            "velocity_trend": "flat",
            "freshness_days": 30,
            "lifecycle": "stable",
            "daily_traffic": [],
            "source_breakdown": [],
            "ai_platform_breakdown": [],
            "structural_signals": None,
        }
        resp = client.get(f"/api/v1/content-performance/{inv_id}")
        assert resp.status_code == 200
        assert resp.json()["structural_signals"] is None

    def test_unauthenticated(self, public_client: TestClient):
        inv_id = str(uuid.uuid4())
        resp = public_client.get(f"/api/v1/content-performance/{inv_id}")
        assert resp.status_code == 401


# ── 4. Similar Content (Cannibalization) ────────────────────────────


class TestGetSimilarContent:
    """GET /api/v1/content-performance/{inventory_id}/similar"""

    def test_empty_results_no_embeddings(self, client: TestClient):
        """Zero embeddings → embeddings_ready=False."""
        inv_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/content-performance/{inv_id}/similar")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_id"] == inv_id
        assert data["similar_pages"] == []
        assert data["threshold"] == 0.78
        assert data["embeddings_ready"] is False

    def test_embeddings_ready_when_sufficient(self, client: TestClient, mock_inventory_service):
        """2+ embeddings → embeddings_ready=True."""
        mock_inventory_service.count_with_embeddings.return_value = 5
        inv_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/content-performance/{inv_id}/similar")
        assert resp.status_code == 200
        assert resp.json()["embeddings_ready"] is True

    def test_with_matches(self, client: TestClient, mock_inventory_service):
        from core.content_inventory.models import CannibalizationMatch

        inv_id = str(uuid.uuid4())
        match_id = str(uuid.uuid4())
        mock_inventory_service.find_similar_pages.return_value = [
            CannibalizationMatch(
                inventory_id=match_id,
                url="https://example.com/blog/guide",
                title="Existing Guide",
                similarity=0.87,
                word_count=1500,
                content_preview="This is a guide about...",
                content_type_detected="blog_post",
            ),
        ]
        resp = client.get(f"/api/v1/content-performance/{inv_id}/similar")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["similar_pages"]) == 1
        assert data["similar_pages"][0]["similarity"] == 0.87
        assert data["similar_pages"][0]["title"] == "Existing Guide"
        assert data["similar_pages"][0]["content_type"] == "blog_post"

    def test_custom_threshold(self, client: TestClient, mock_inventory_service):
        inv_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/content-performance/{inv_id}/similar?threshold=0.90&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["threshold"] == 0.90
        mock_inventory_service.find_similar_pages.assert_called_once()
        call_kwargs = mock_inventory_service.find_similar_pages.call_args
        assert call_kwargs.kwargs["threshold"] == 0.90
        assert call_kwargs.kwargs["limit"] == 3

    def test_invalid_uuid(self, client: TestClient):
        resp = client.get("/api/v1/content-performance/not-a-uuid/similar")
        assert resp.status_code == 400
        assert "Invalid inventory_id" in resp.json()["detail"]

    def test_threshold_too_low(self, client: TestClient):
        inv_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/content-performance/{inv_id}/similar?threshold=0.3")
        assert resp.status_code == 422

    def test_unauthenticated(self, public_client: TestClient):
        inv_id = str(uuid.uuid4())
        resp = public_client.get(f"/api/v1/content-performance/{inv_id}/similar")
        assert resp.status_code == 401
