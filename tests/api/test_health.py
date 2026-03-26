"""Tests for health and readiness endpoints."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "database": "unavailable", "pgvector": "unavailable", "redis": "unavailable"}

    def test_readiness_with_all_keys(self, client: TestClient) -> None:
        with patch("api.routers.health.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.anthropic_api_key = "sk-ant-test"
            mock_settings.perplexity_api_key = "pplx-test"
            resp = client.get("/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["missing_keys"] == []

    def test_readiness_with_missing_keys(self, client: TestClient) -> None:
        with patch("api.routers.health.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.anthropic_api_key = None
            mock_settings.perplexity_api_key = None
            resp = client.get("/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is False
        assert "anthropic_api_key" in data["missing_keys"]
        assert "perplexity_api_key" in data["missing_keys"]

    def test_cors_headers(self, client: TestClient) -> None:
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_health_with_db_connected(self, client: TestClient) -> None:
        """When DB is healthy, response includes 'connected'."""
        client.app.state.db_healthy = True
        client.app.state.pgvector_available = True
        resp = client.get("/health")
        data = resp.json()
        assert data["database"] == "connected"
        assert data["pgvector"] == "available"
        # Reset
        client.app.state.db_healthy = False
        client.app.state.pgvector_available = False

    def test_health_without_db(self, client: TestClient) -> None:
        """When DB is not configured, response shows 'unavailable'."""
        client.app.state.db_healthy = False
        resp = client.get("/health")
        data = resp.json()
        assert data["database"] == "unavailable"
        assert data["status"] == "ok"  # App still healthy without DB
