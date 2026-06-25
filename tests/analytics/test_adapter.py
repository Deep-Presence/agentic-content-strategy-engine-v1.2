"""Tests for GA4 adapter — OAuth, Admin API, Data API.

All Google API calls are mocked. Tests verify correct URL construction,
request payloads, response parsing, and error handling.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.analytics.adapters.ga4 import GA4Adapter
from core.analytics.exceptions import GA4APIError, GA4AuthError, GA4QuotaError
from core.analytics.models import ConversionRow, GA4Property, GA4TokenSet, TrafficRow


def _adapter() -> GA4Adapter:
    return GA4Adapter(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost/callback",
    )


class TestBuildAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_returns_google_url_with_params(self) -> None:
        adapter = _adapter()
        url = await adapter.build_authorization_url(state="test-state-123")

        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=test-client-id" in url
        assert "redirect_uri=http" in url
        assert "response_type=code" in url
        assert "scope=https" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "state=test-state-123" in url

    @pytest.mark.asyncio
    async def test_state_is_url_encoded(self) -> None:
        adapter = _adapter()
        url = await adapter.build_authorization_url(state="a=b&c=d")
        # State should be URL-encoded
        assert "state=a%3Db%26c%3Dd" in url


class TestExchangeCodeForTokens:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        adapter = _adapter()
        mock_response = httpx.Response(
            200,
            json={
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/analytics.readonly",
            },
        )
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.exchange_code_for_tokens("auth-code-123")

        assert isinstance(result, GA4TokenSet)
        assert result.access_token == "ya29.access"
        assert result.refresh_token == "1//refresh"
        assert result.token_expiry is not None
        assert len(result.scopes) > 0

    @pytest.mark.asyncio
    async def test_failure_raises_auth_error(self) -> None:
        adapter = _adapter()
        mock_response = httpx.Response(400, json={"error": "invalid_grant"})
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(GA4AuthError, match="Token exchange failed"):
                await adapter.exchange_code_for_tokens("bad-code")

    @pytest.mark.asyncio
    async def test_missing_refresh_token_raises(self) -> None:
        """First exchange must return a refresh_token — fail fast otherwise."""
        adapter = _adapter()
        mock_response = httpx.Response(
            200,
            json={
                "access_token": "ya29.access",
                # No refresh_token in response
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/analytics.readonly",
            },
        )
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(GA4AuthError, match="refresh token"):
                await adapter.exchange_code_for_tokens("auth-code-123")


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_success_preserves_refresh_token(self) -> None:
        adapter = _adapter()
        mock_response = httpx.Response(
            200,
            json={
                "access_token": "ya29.new-access",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/analytics.readonly",
            },
        )
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.refresh_access_token("1//original-refresh")

        assert result.access_token == "ya29.new-access"
        assert result.refresh_token == "1//original-refresh"  # Preserved

    @pytest.mark.asyncio
    async def test_failure_raises_auth_error(self) -> None:
        adapter = _adapter()
        mock_response = httpx.Response(401, json={"error": "invalid_grant"})
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(GA4AuthError):
                await adapter.refresh_access_token("1//revoked-token")


class TestRevokeToken:
    @pytest.mark.asyncio
    async def test_success_returns_true(self) -> None:
        adapter = _adapter()
        mock_response = httpx.Response(200)
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.revoke_token("ya29.token")
        assert result is True

    @pytest.mark.asyncio
    async def test_failure_returns_false(self) -> None:
        adapter = _adapter()
        mock_response = httpx.Response(400)
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.revoke_token("ya29.bad")
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self) -> None:
        adapter = _adapter()
        with patch("core.analytics.adapters.ga4.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.revoke_token("ya29.token")
        assert result is False


class TestParseDateHelper:
    def test_yyyymmdd_to_iso(self) -> None:
        assert GA4Adapter._parse_date("20260315") == "2026-03-15"

    def test_already_iso_passthrough(self) -> None:
        assert GA4Adapter._parse_date("2026-03-15") == "2026-03-15"

    def test_short_string_passthrough(self) -> None:
        assert GA4Adapter._parse_date("abc") == "abc"


class TestParseTrafficRow:
    def test_parses_dimensions_and_metrics(self) -> None:
        adapter = _adapter()

        # Mock a GA4 report row
        row = MagicMock()
        row.dimension_values = [
            MagicMock(value="20260315"),
            MagicMock(value="/blog/test"),
            MagicMock(value="google"),
            MagicMock(value="organic"),
            MagicMock(value="campaign1"),
        ]
        row.metric_values = [
            MagicMock(value="100"),   # sessions
            MagicMock(value="80"),    # engaged_sessions
            MagicMock(value="0.8"),   # engagement_rate
            MagicMock(value="0.2"),   # bounce_rate
            MagicMock(value="120.5"), # avg_session_duration
            MagicMock(value="250"),   # screen_page_views
            MagicMock(value="10"),    # conversions
            MagicMock(value="60"),    # new_users
            MagicMock(value="100"),   # total_users
        ]

        result = adapter._parse_traffic_row(row)

        assert isinstance(result, TrafficRow)
        assert result.date == "2026-03-15"
        assert result.landing_page_url == "/blog/test"
        assert result.source == "google"
        assert result.medium == "organic"
        assert result.campaign == "campaign1"
        assert result.sessions == 100
        assert result.engaged_sessions == 80
        assert result.engagement_rate == 0.8
        assert result.bounce_rate == 0.2
        assert result.avg_session_duration_secs == 120.5
        assert result.screen_page_views == 250
        assert result.conversions == 10
        assert result.new_users == 60
        assert result.returning_users == 40  # total_users - new_users


class TestParseConversionRow:
    def test_parses_dimensions_and_metrics(self) -> None:
        adapter = _adapter()

        row = MagicMock()
        row.dimension_values = [
            MagicMock(value="20260315"),
            MagicMock(value="generate_lead"),
            MagicMock(value="/contact"),
            MagicMock(value="chatgpt.com"),
            MagicMock(value="referral"),
        ]
        row.metric_values = [
            MagicMock(value="5"),
            MagicMock(value="250.00"),
        ]

        result = adapter._parse_conversion_row(row)

        assert isinstance(result, ConversionRow)
        assert result.date == "2026-03-15"
        assert result.event_name == "generate_lead"
        assert result.landing_page_url == "/contact"
        assert result.source == "chatgpt.com"
        assert result.medium == "referral"
        assert result.event_count == 5
        assert result.event_value == 250.00


class TestListProperties:
    @pytest.mark.asyncio
    async def test_parses_account_summaries(self) -> None:
        adapter = _adapter()

        # Mock property summary
        mock_prop = MagicMock()
        mock_prop.property = "properties/123456"
        mock_prop.display_name = "Test Property"

        mock_summary = MagicMock()
        mock_summary.account = "accounts/789"
        mock_summary.display_name = "Test Account"
        mock_summary.property_summaries = [mock_prop]

        with patch(
            "google.analytics.admin_v1alpha.AnalyticsAdminServiceClient"
        ) as mock_cls:
            mock_client = MagicMock()
            mock_client.list_account_summaries.return_value = [mock_summary]
            mock_cls.return_value = mock_client

            props = await adapter.list_properties("ya29.token")

        assert len(props) == 1
        assert props[0].property_id == "123456"
        assert props[0].display_name == "Test Property"
        assert props[0].account_id == "789"
        assert props[0].account_display_name == "Test Account"


class TestRunTrafficReport:
    @pytest.mark.asyncio
    async def test_requests_page_path_dimension(self) -> None:
        adapter = _adapter()

        fake_response = MagicMock()
        fake_response.rows = []
        fake_response.row_count = 0

        with patch.object(adapter, "_run_report_with_retry", new=AsyncMock(return_value=fake_response)) as mock_run:
            result = await adapter.run_traffic_report(
                access_token="ya29.token",
                property_id="123456",
                start_date="2026-03-01",
                end_date="2026-03-31",
            )

        assert result == []
        request = mock_run.await_args.args[1]
        assert [dim.name for dim in request.dimensions] == [
            "date",
            "pagePath",
            "sessionSource",
            "sessionMedium",
            "sessionCampaignName",
        ]


class TestTranslateGoogleError:
    def test_permission_denied(self) -> None:
        from google.api_core.exceptions import PermissionDenied

        result = GA4Adapter._translate_google_error(PermissionDenied("denied"))
        assert isinstance(result, GA4AuthError)

    def test_resource_exhausted(self) -> None:
        from google.api_core.exceptions import ResourceExhausted

        result = GA4Adapter._translate_google_error(
            ResourceExhausted("quota exceeded")
        )
        assert isinstance(result, GA4QuotaError)

    def test_generic_google_error(self) -> None:
        from google.api_core.exceptions import GoogleAPIError

        result = GA4Adapter._translate_google_error(GoogleAPIError("oops"))
        assert isinstance(result, GA4APIError)

    def test_non_google_error(self) -> None:
        result = GA4Adapter._translate_google_error(RuntimeError("something"))
        assert isinstance(result, GA4APIError)
