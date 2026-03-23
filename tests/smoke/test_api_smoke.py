"""Smoke tests for deployed API instances.

Run against a live deployment to catch issues that unit tests miss:
environment config, network connectivity, auth flow, SSE streaming.

Usage:
    SMOKE_TEST_URL=https://api.example.com pytest tests/smoke/ -v
    SMOKE_TEST_URL=http://localhost:8000 pytest tests/smoke/ -v

All tests are skipped if SMOKE_TEST_URL is not set.
"""
from __future__ import annotations

import os

import httpx
import pytest

SMOKE_URL = os.environ.get("SMOKE_TEST_URL", "")

pytestmark = pytest.mark.skipif(
    not SMOKE_URL,
    reason="SMOKE_TEST_URL not set — skipping smoke tests",
)

# Optional auth credentials for authenticated endpoints
SMOKE_EMAIL = os.environ.get("SMOKE_TEST_EMAIL", "")
SMOKE_PASSWORD = os.environ.get("SMOKE_TEST_PASSWORD", "")


# ── Helpers ──────────────────────────────────────────────────────────


def _url(path: str) -> str:
    return f"{SMOKE_URL.rstrip('/')}{path}"


def _get_auth_token() -> str | None:
    """Attempt to login and return a Bearer token, or None."""
    if not SMOKE_EMAIL or not SMOKE_PASSWORD:
        return None
    try:
        resp = httpx.post(
            _url("/api/v1/auth/login"),
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except httpx.HTTPError:
        pass
    return None


# ── Health endpoints ─────────────────────────────────────────────────


class TestHealthSmoke:
    def test_health_endpoint(self):
        """GET /health returns 200 with status field."""
        resp = httpx.get(_url("/health"), timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_readiness_endpoint(self):
        """GET /readiness returns 200 with ready field."""
        resp = httpx.get(_url("/readiness"), timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data
        assert isinstance(data["ready"], bool)

    def test_health_response_shape(self):
        """Health response has expected keys."""
        resp = httpx.get(_url("/health"), timeout=10)
        data = resp.json()
        assert "database" in data
        assert data["database"] in ("connected", "unavailable")


# ── Auth flow ────────────────────────────────────────────────────────


class TestAuthSmoke:
    def test_unauthenticated_tasks_returns_401(self):
        """Accessing protected endpoints without auth returns 401."""
        resp = httpx.get(_url("/api/v1/tasks"), timeout=10)
        assert resp.status_code == 401

    @pytest.mark.skipif(
        not SMOKE_EMAIL or not SMOKE_PASSWORD,
        reason="SMOKE_TEST_EMAIL/PASSWORD not set",
    )
    def test_login_returns_token(self):
        """POST /api/v1/auth/login returns access_token."""
        resp = httpx.post(
            _url("/api/v1/auth/login"),
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    @pytest.mark.skipif(
        not SMOKE_EMAIL or not SMOKE_PASSWORD,
        reason="SMOKE_TEST_EMAIL/PASSWORD not set",
    )
    def test_authenticated_tasks_list(self):
        """GET /api/v1/tasks with auth returns 200."""
        token = _get_auth_token()
        assert token is not None, "Failed to obtain auth token"

        resp = httpx.get(
            _url("/api/v1/tasks"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data or isinstance(data, list)


# ── SSE endpoint ─────────────────────────────────────────────────────


class TestSSESmoke:
    def test_sse_unknown_task_returns_404(self):
        """SSE for nonexistent task returns 404."""
        resp = httpx.get(
            _url("/api/v1/tasks/nonexistent-id/events"),
            timeout=10,
        )
        # Should be 401 (no auth) or 404 (not found)
        assert resp.status_code in (401, 404)
