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
    return svc


@pytest.fixture
def app(app, mock_perf_service, monkeypatch):
    """Extend the base app fixture with content performance service mock.

    Also patch Redis cache to prevent real Redis calls.
    """
    app.state.content_performance_service = mock_perf_service

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
        }
        resp = client.get(f"/api/v1/content-performance/{inv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["traffic"] == 200
        assert len(data["daily_traffic"]) == 2
        assert len(data["source_breakdown"]) == 3
        assert len(data["ai_platform_breakdown"]) == 2

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
