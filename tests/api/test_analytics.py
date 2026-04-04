"""Tests for GA4 analytics integration API endpoints.

GA4 service is mocked via ``app.state.ga4_analytics_service`` pre-built override
(bypasses DI), following the same pattern as ``test_cms.py``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.analytics.exceptions import GA4AuthError, GA4Error
from core.analytics.models import AnalyticsConnectionInfo, GA4Property, SyncResult


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_ga4_service():
    """Pre-built GA4AnalyticsService mock, set on app.state to bypass DI."""
    svc = MagicMock()

    svc.generate_authorize_url = MagicMock(
        return_value="https://accounts.google.com/o/oauth2/v2/auth?test=1"
    )
    svc.verify_oauth_state = MagicMock(return_value={
        "company_slug": "test-co",
        "return_url": "http://frontend/settings",
        "purpose": "ga4_oauth",
    })
    svc.exchange_code_and_store = AsyncMock()
    svc.get_connection_info = AsyncMock(return_value=None)
    svc.disconnect = AsyncMock(return_value=True)
    svc.list_properties = AsyncMock(return_value=[])
    svc.select_property = AsyncMock()
    svc.sync_data = AsyncMock(return_value=SyncResult())

    return svc


@pytest.fixture
def app(app, mock_ga4_service):
    """Extend the base app fixture with GA4 service mock."""
    app.state.ga4_analytics_service = mock_ga4_service
    return app


# ── GET /authorize ────────────────────────────────────────────────────


class TestAuthorize:
    def test_returns_authorization_url(self, client: TestClient, mock_ga4_service) -> None:
        resp = client.get("/api/v1/analytics/google/authorize")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]

    def test_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/analytics/google/authorize")
        assert resp.status_code == 401


# ── GET /callback ─────────────────────────────────────────────────────


class TestOAuthCallback:
    @patch("core.analytics.service.GA4AnalyticsService.verify_oauth_state")
    def test_redirects_on_success(
        self, mock_verify, public_client: TestClient, mock_ga4_service, test_company
    ) -> None:
        mock_verify.return_value = {

            "company_slug": "test-co",
            "return_url": "http://frontend/settings",
            "purpose": "ga4_oauth",
        }
        resp = public_client.get(
            "/api/v1/analytics/google/callback",
            params={"code": "auth-code-123", "state": "valid-state"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "analytics_connected=true" in resp.headers["location"]

    @patch("core.analytics.service.GA4AnalyticsService.verify_oauth_state")
    def test_invalid_state_redirects_with_error(
        self, mock_verify, public_client: TestClient, mock_ga4_service
    ) -> None:
        mock_verify.return_value = None

        resp = public_client.get(
            "/api/v1/analytics/google/callback",
            params={"code": "code", "state": "bad-state"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "error=invalid_state" in resp.headers["location"]

    @patch("core.analytics.service.GA4AnalyticsService.verify_oauth_state")
    def test_company_not_found_redirects_with_error(
        self, mock_verify, public_client: TestClient, mock_ga4_service
    ) -> None:
        mock_verify.return_value = {

            "company_slug": "nonexistent-co",
            "return_url": "http://frontend/settings",
            "purpose": "ga4_oauth",
        }
        resp = public_client.get(
            "/api/v1/analytics/google/callback",
            params={"code": "code", "state": "valid"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "error=company_not_found" in resp.headers["location"]

    @patch("core.analytics.service.GA4AnalyticsService.verify_oauth_state")
    def test_exchange_failure_redirects_with_error(
        self, mock_verify, public_client: TestClient, mock_ga4_service, test_company
    ) -> None:
        mock_verify.return_value = {

            "company_slug": "test-co",
            "return_url": "http://frontend/settings",
            "purpose": "ga4_oauth",
        }
        mock_ga4_service.exchange_code_and_store = AsyncMock(
            side_effect=GA4AuthError("exchange failed")
        )

        resp = public_client.get(
            "/api/v1/analytics/google/callback",
            params={"code": "code", "state": "valid"},
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert "error=oauth_failed" in resp.headers["location"]


# ── GET /connection ───────────────────────────────────────────────────


class TestGetConnection:
    def test_returns_null_when_not_connected(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.get_connection_info = AsyncMock(return_value=None)
        resp = client.get("/api/v1/analytics/google/connection")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_returns_connection_info(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.get_connection_info = AsyncMock(
            return_value=AnalyticsConnectionInfo(
                provider="ga4",
                ga4_property_id="123456",
                ga4_property_name="Test Property",
                is_active=True,
            )
        )
        resp = client.get("/api/v1/analytics/google/connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ga4_property_id"] == "123456"
        assert data["is_active"] is True

    def test_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/analytics/google/connection")
        assert resp.status_code == 401


# ── DELETE /connection ────────────────────────────────────────────────


class TestDisconnect:
    def test_disconnects_successfully(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        resp = client.delete("/api/v1/analytics/google/connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["disconnected"] is True
        assert data["data_purged"] is False

    def test_disconnect_with_purge_data(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        resp = client.delete(
            "/api/v1/analytics/google/connection",
            params={"purge_data": "true"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["disconnected"] is True
        assert data["data_purged"] is True
        mock_ga4_service.disconnect.assert_awaited_once()
        call_kwargs = mock_ga4_service.disconnect.call_args
        assert call_kwargs.kwargs.get("purge_data") is True

    def test_disconnect_default_no_purge(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        resp = client.delete("/api/v1/analytics/google/connection")
        assert resp.status_code == 200
        call_kwargs = mock_ga4_service.disconnect.call_args
        assert call_kwargs.kwargs.get("purge_data") is False

    def test_requires_member_role(self, viewer_client: TestClient) -> None:
        resp = viewer_client.delete("/api/v1/analytics/google/connection")
        assert resp.status_code == 403


# ── GET /properties ───────────────────────────────────────────────────


class TestListProperties:
    def test_returns_empty_list(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.list_properties = AsyncMock(return_value=[])
        resp = client.get("/api/v1/analytics/google/properties")
        assert resp.status_code == 200
        assert resp.json()["properties"] == []

    def test_returns_properties(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.list_properties = AsyncMock(
            return_value=[
                GA4Property(
                    property_id="123",
                    display_name="My Site",
                    account_id="a1",
                    account_display_name="My Account",
                )
            ]
        )
        resp = client.get("/api/v1/analytics/google/properties")
        assert resp.status_code == 200
        props = resp.json()["properties"]
        assert len(props) == 1
        assert props[0]["property_id"] == "123"
        assert props[0]["display_name"] == "My Site"

    def test_auth_error_returns_401(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.list_properties = AsyncMock(
            side_effect=GA4AuthError("no connection")
        )
        resp = client.get("/api/v1/analytics/google/properties")
        assert resp.status_code == 401

    def test_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/analytics/google/properties")
        assert resp.status_code == 401


# ── POST /select-property ────────────────────────────────────────────


class TestSelectProperty:
    def test_selects_property(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        resp = client.post(
            "/api/v1/analytics/google/select-property",
            json={"property_id": "123456", "property_name": "My Site", "account_id": "789"},
        )
        assert resp.status_code == 200
        assert resp.json()["selected"] is True

    def test_auth_error_returns_401(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.select_property = AsyncMock(
            side_effect=GA4AuthError("no connection")
        )
        resp = client.post(
            "/api/v1/analytics/google/select-property",
            json={"property_id": "123"},
        )
        assert resp.status_code == 401

    def test_requires_member_role(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/analytics/google/select-property",
            json={"property_id": "123"},
        )
        assert resp.status_code == 403


# ── POST /sync ────────────────────────────────────────────────────────


class TestSync:
    def test_no_connection_returns_404(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.get_connection_info = AsyncMock(return_value=None)
        resp = client.post("/api/v1/analytics/google/sync")
        assert resp.status_code == 404

    def test_no_property_returns_400(
        self, client: TestClient, mock_ga4_service
    ) -> None:
        mock_ga4_service.get_connection_info = AsyncMock(
            return_value=AnalyticsConnectionInfo(
                is_active=True,
                ga4_property_id="",  # No property selected
            )
        )
        resp = client.post("/api/v1/analytics/google/sync")
        assert resp.status_code == 400

    @patch("api.routers.analytics.asyncio.create_task")
    def test_starts_sync_task(
        self, mock_create_task, client: TestClient, mock_ga4_service
    ) -> None:
        mock_create_task.return_value = MagicMock()
        mock_ga4_service.get_connection_info = AsyncMock(
            return_value=AnalyticsConnectionInfo(
                is_active=True,
                ga4_property_id="123456",
            )
        )
        resp = client.post("/api/v1/analytics/google/sync")
        assert resp.status_code == 202
        data = resp.json()
        assert data["pipeline"] == "ga4_sync"
        assert "run_id" in data

    def test_requires_member_role(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post("/api/v1/analytics/google/sync")
        assert resp.status_code == 403


# ── POST /sync-all ───────────────────────────────────────────────────


class TestSyncAll:
    def test_missing_api_key_returns_422(
        self, public_client: TestClient
    ) -> None:
        resp = public_client.post("/api/v1/analytics/google/sync-all")
        assert resp.status_code == 422

    @patch("core.config.settings.settings")
    def test_wrong_api_key_returns_403(
        self, mock_settings, public_client: TestClient
    ) -> None:
        mock_settings.ga4_sync_api_key = "correct-key"
        resp = public_client.post(
            "/api/v1/analytics/google/sync-all",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    @patch("core.config.settings.settings")
    def test_empty_api_key_setting_returns_503(
        self, mock_settings, public_client: TestClient
    ) -> None:
        mock_settings.ga4_sync_api_key = ""
        resp = public_client.post(
            "/api/v1/analytics/google/sync-all",
            headers={"X-API-Key": "any-key"},
        )
        assert resp.status_code == 503

    @patch("api.routers.analytics.asyncio.create_task")
    @patch("core.db.repositories.analytics_repo.AnalyticsConnectionRepository.get_all_active")
    @patch("core.config.settings.settings")
    def test_valid_api_key_triggers_syncs(
        self,
        mock_settings,
        mock_get_all_active,
        mock_create_task,
        public_client: TestClient,
        app,
    ) -> None:
        mock_settings.ga4_sync_api_key = "test-cron-key"
        mock_settings.cms_fernet_key = "test-fernet"
        mock_settings.ga4_sync_lookback_days = 7
        mock_create_task.return_value = MagicMock()

        # Provide a mock session factory so the endpoint doesn't 503
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        app.state.db_session_factory = MagicMock(return_value=mock_session)

        conn1 = MagicMock()
        conn1.company_slug = "company-a"
        conn1.tenant_id = "company-a"
        conn1.ga4_property_id = "123456"

        conn2 = MagicMock()
        conn2.company_slug = "company-b"
        conn2.tenant_id = "company-b"
        conn2.ga4_property_id = "789012"

        mock_get_all_active.return_value = [conn1, conn2]

        resp = public_client.post(
            "/api/v1/analytics/google/sync-all",
            headers={"X-API-Key": "test-cron-key"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["triggered"] == 2
        assert data["skipped"] == 0
        assert data["total"] == 2

    @patch("api.routers.analytics.asyncio.create_task")
    @patch("core.db.repositories.analytics_repo.AnalyticsConnectionRepository.get_all_active")
    @patch("core.config.settings.settings")
    def test_skips_connections_without_property(
        self,
        mock_settings,
        mock_get_all_active,
        mock_create_task,
        public_client: TestClient,
        app,
    ) -> None:
        mock_settings.ga4_sync_api_key = "test-cron-key"
        mock_settings.cms_fernet_key = "test-fernet"
        mock_settings.ga4_sync_lookback_days = 7
        mock_create_task.return_value = MagicMock()

        # Provide a mock session factory so the endpoint doesn't 503
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        app.state.db_session_factory = MagicMock(return_value=mock_session)

        conn_with_property = MagicMock()
        conn_with_property.company_slug = "company-a"
        conn_with_property.tenant_id = "company-a"
        conn_with_property.ga4_property_id = "123456"

        conn_without_property = MagicMock()
        conn_without_property.company_slug = "company-b"
        conn_without_property.tenant_id = "company-b"
        conn_without_property.ga4_property_id = ""

        mock_get_all_active.return_value = [conn_with_property, conn_without_property]

        resp = public_client.post(
            "/api/v1/analytics/google/sync-all",
            headers={"X-API-Key": "test-cron-key"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["triggered"] == 1
        assert data["skipped"] == 1
