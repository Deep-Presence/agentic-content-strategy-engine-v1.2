"""Tests for GA4AnalyticsService — OAuth state, token encryption, sync orchestration."""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from core.analytics.exceptions import GA4AuthError, GA4Error
from core.analytics.models import (
    AnalyticsConnectionInfo,
    GA4Property,
    GA4TokenSet,
    SyncResult,
    TrafficRow,
    ConversionRow,
)
from core.analytics.service import GA4AnalyticsService
from core.db.enums import AnalyticsProvider, AnalyticsSyncStatus


@pytest.fixture()
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture()
def secret_key() -> str:
    return secrets.token_hex(32)


def _mock_repos():
    """Create mock repositories."""
    conn_repo = AsyncMock()
    traffic_repo = AsyncMock()
    conv_repo = AsyncMock()
    return conn_repo, traffic_repo, conv_repo


def _service(
    fernet_key: str,
    conn_repo=None,
    traffic_repo=None,
    conv_repo=None,
) -> GA4AnalyticsService:
    cr, tr, cvr = _mock_repos()
    return GA4AnalyticsService(
        connection_repo=conn_repo or cr,
        traffic_repo=traffic_repo or tr,
        conversion_repo=conv_repo or cvr,
        fernet_key=fernet_key,
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost/callback",
        ai_referral_sources="chatgpt.com:openai,claude.ai:anthropic",
        lookback_days=7,
    )


class TestOAuthState:
    def test_create_and_verify_roundtrip(self, fernet_key: str, secret_key: str) -> None:
        svc = _service(fernet_key)
        state = svc._create_oauth_state(
            secret_key=secret_key,
            company_slug="test-co",
            return_url="http://frontend/settings",
        )

        payload = GA4AnalyticsService.verify_oauth_state(secret_key, state)

        assert payload is not None
        assert payload["company_slug"] == "test-co"
        assert payload["return_url"] == "http://frontend/settings"
        assert payload["purpose"] == "ga4_oauth"
        assert "user_id" not in payload

    def test_invalid_signature_returns_none(self, fernet_key: str, secret_key: str) -> None:
        svc = _service(fernet_key)
        state = svc._create_oauth_state(
            secret_key=secret_key,
            company_slug="c",
        )
        # Tamper with signature
        payload = GA4AnalyticsService.verify_oauth_state("wrong-key", state)
        assert payload is None

    def test_expired_state_returns_none(self, fernet_key: str, secret_key: str) -> None:
        svc = _service(fernet_key)
        # Manually create expired state
        import base64, hashlib, hmac, json
        from datetime import datetime, timedelta, timezone

        payload_dict = {
            "company_slug": "c",
            "return_url": "",
            "purpose": "ga4_oauth",
            "exp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        payload_bytes = json.dumps(payload_dict).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
        sig = hmac.new(secret_key.encode(), payload_bytes, hashlib.sha256).hexdigest()
        expired_state = f"{payload_b64}.{sig}"

        result = GA4AnalyticsService.verify_oauth_state(secret_key, expired_state)
        assert result is None

    def test_wrong_purpose_returns_none(self, fernet_key: str, secret_key: str) -> None:
        import base64, hashlib, hmac, json
        from datetime import datetime, timedelta, timezone

        payload_dict = {
            "company_slug": "c",
            "purpose": "not_ga4",
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        }
        payload_bytes = json.dumps(payload_dict).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
        sig = hmac.new(secret_key.encode(), payload_bytes, hashlib.sha256).hexdigest()
        state = f"{payload_b64}.{sig}"

        result = GA4AnalyticsService.verify_oauth_state(secret_key, state)
        assert result is None

    def test_garbage_state_returns_none(self) -> None:
        result = GA4AnalyticsService.verify_oauth_state("key", "garbage")
        assert result is None


class TestGenerateAuthorizeUrl:
    def test_returns_google_url(self, fernet_key: str, secret_key: str) -> None:
        svc = _service(fernet_key)
        url = svc.generate_authorize_url(
            secret_key=secret_key,
            company_slug="test-co",
            return_url="http://frontend",
        )
        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=test-client-id" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self, fernet_key: str) -> None:
        svc = _service(fernet_key)
        encrypted = svc._encrypt_token("my-secret-token")
        assert encrypted != "my-secret-token"
        decrypted = svc._decrypt_token(encrypted)
        assert decrypted == "my-secret-token"


class TestGetConnectionInfo:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_connection(self, fernet_key: str) -> None:
        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=None)
        svc = _service(fernet_key, conn_repo=conn_repo)

        result = await svc.get_connection_info("test-co", tenant_id="test-co")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_info_when_connected(self, fernet_key: str) -> None:
        conn = MagicMock()
        conn.provider = AnalyticsProvider.ga4
        conn.ga4_property_id = "123456"
        conn.ga4_property_name = "Test Property"
        conn.ga4_account_id = "789"
        conn.is_active = True
        conn.connected_at = datetime.now(timezone.utc)
        conn.last_sync_at = None
        conn.last_sync_status = AnalyticsSyncStatus.success
        conn.last_sync_error = ""

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        svc = _service(fernet_key, conn_repo=conn_repo)

        result = await svc.get_connection_info("test-co", tenant_id="test-co")
        assert result is not None
        assert isinstance(result, AnalyticsConnectionInfo)
        assert result.ga4_property_id == "123456"
        assert result.is_active is True


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_no_connection_returns_false(self, fernet_key: str) -> None:
        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=None)
        svc = _service(fernet_key, conn_repo=conn_repo)

        result = await svc.disconnect("test-co", tenant_id="test-co")
        assert result is False

    @pytest.mark.asyncio
    async def test_revokes_token_and_deactivates(self, fernet_key: str) -> None:
        svc = _service(fernet_key)
        conn = MagicMock()
        conn.id = "conn-id"
        conn.refresh_token_encrypted = svc._encrypt_token("refresh-token")

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.deactivate = AsyncMock(return_value=True)
        svc._conn_repo = conn_repo

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.revoke_token = AsyncMock(return_value=True)
            mock_build.return_value = mock_adapter

            result = await svc.disconnect("test-co", tenant_id="test-co")

        assert result is True
        conn_repo.deactivate.assert_awaited_once_with("conn-id")

    @pytest.mark.asyncio
    async def test_disconnect_with_purge_deletes_data(self, fernet_key: str) -> None:
        svc = _service(fernet_key)
        conn = MagicMock()
        conn.id = "conn-id"
        conn.refresh_token_encrypted = svc._encrypt_token("refresh-token")

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.deactivate = AsyncMock(return_value=True)
        svc._conn_repo = conn_repo

        traffic_repo = AsyncMock()
        traffic_repo.delete_by_connection = AsyncMock(return_value=10)
        svc._traffic_repo = traffic_repo

        conv_repo = AsyncMock()
        conv_repo.delete_by_connection = AsyncMock(return_value=5)
        svc._conv_repo = conv_repo

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.revoke_token = AsyncMock(return_value=True)
            mock_build.return_value = mock_adapter

            result = await svc.disconnect(
                "test-co", tenant_id="test-co", purge_data=True
            )

        assert result is True
        traffic_repo.delete_by_connection.assert_awaited_once_with("conn-id")
        conv_repo.delete_by_connection.assert_awaited_once_with("conn-id")

    @pytest.mark.asyncio
    async def test_disconnect_without_purge_skips_delete(self, fernet_key: str) -> None:
        svc = _service(fernet_key)
        conn = MagicMock()
        conn.id = "conn-id"
        conn.refresh_token_encrypted = svc._encrypt_token("refresh-token")

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.deactivate = AsyncMock(return_value=True)
        svc._conn_repo = conn_repo

        traffic_repo = AsyncMock()
        traffic_repo.delete_by_connection = AsyncMock()
        svc._traffic_repo = traffic_repo

        conv_repo = AsyncMock()
        conv_repo.delete_by_connection = AsyncMock()
        svc._conv_repo = conv_repo

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.revoke_token = AsyncMock(return_value=True)
            mock_build.return_value = mock_adapter

            result = await svc.disconnect(
                "test-co", tenant_id="test-co", purge_data=False
            )

        assert result is True
        traffic_repo.delete_by_connection.assert_not_awaited()
        conv_repo.delete_by_connection.assert_not_awaited()


class TestSelectProperty:
    @pytest.mark.asyncio
    async def test_updates_property(self, fernet_key: str) -> None:
        conn = MagicMock()
        conn.id = "conn-id"

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.update_property = AsyncMock()
        svc = _service(fernet_key, conn_repo=conn_repo)

        await svc.select_property(
            company_slug="test-co",
            tenant_id="test-co",
            property_id="123456",
            property_name="My Site",
            account_id="789",
        )

        conn_repo.update_property.assert_awaited_once_with(
            "conn-id",
            ga4_property_id="123456",
            ga4_property_name="My Site",
            ga4_account_id="789",
        )

    @pytest.mark.asyncio
    async def test_no_connection_raises(self, fernet_key: str) -> None:
        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=None)
        svc = _service(fernet_key, conn_repo=conn_repo)

        with pytest.raises(GA4AuthError, match="No active analytics connection"):
            await svc.select_property(
                company_slug="test-co",
                tenant_id="test-co",
                property_id="123",
                property_name="x",
                account_id="y",
            )


class TestListProperties:
    @pytest.mark.asyncio
    async def test_no_connection_raises(self, fernet_key: str) -> None:
        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=None)
        svc = _service(fernet_key, conn_repo=conn_repo)

        with pytest.raises(GA4AuthError, match="No active analytics connection"):
            await svc.list_properties("test-co", tenant_id="test-co")

    @pytest.mark.asyncio
    async def test_returns_properties(self, fernet_key: str) -> None:
        svc = _service(fernet_key)
        conn = MagicMock()
        conn.id = "conn-id"
        conn.is_active = True
        conn.access_token_encrypted = svc._encrypt_token("ya29.access")
        conn.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        svc._conn_repo = conn_repo

        expected_props = [
            GA4Property(property_id="123", display_name="Test", account_id="a1")
        ]

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.list_properties = AsyncMock(return_value=expected_props)
            mock_build.return_value = mock_adapter

            result = await svc.list_properties("test-co", tenant_id="test-co")

        assert result == expected_props


class TestParseAiReferralSources:
    def test_parses_valid_string(self) -> None:
        result = GA4AnalyticsService._parse_ai_referral_sources(
            "chatgpt.com:openai,claude.ai:anthropic"
        )
        assert result == {"chatgpt.com": "openai", "claude.ai": "anthropic"}

    def test_empty_string(self) -> None:
        assert GA4AnalyticsService._parse_ai_referral_sources("") == {}

    def test_handles_whitespace(self) -> None:
        result = GA4AnalyticsService._parse_ai_referral_sources(
            " chatgpt.com : openai , claude.ai : anthropic "
        )
        assert result == {"chatgpt.com": "openai", "claude.ai": "anthropic"}

    def test_skips_invalid_entries(self) -> None:
        result = GA4AnalyticsService._parse_ai_referral_sources(
            "chatgpt.com:openai,invalid_no_colon,claude.ai:anthropic"
        )
        assert "chatgpt.com" in result
        assert "claude.ai" in result
        # "invalid_no_colon" has no colon so it's not in result


class TestSyncData:
    @pytest.mark.asyncio
    async def test_no_connection_raises(self, fernet_key: str) -> None:
        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=None)
        svc = _service(fernet_key, conn_repo=conn_repo)

        with pytest.raises(GA4AuthError):
            await svc.sync_data(company_slug="test-co", tenant_id="test-co")

    @pytest.mark.asyncio
    async def test_no_property_raises(self, fernet_key: str) -> None:
        conn = MagicMock()
        conn.is_active = True
        conn.ga4_property_id = ""

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        svc = _service(fernet_key, conn_repo=conn_repo)

        with pytest.raises(GA4Error, match="No GA4 property selected"):
            await svc.sync_data(company_slug="test-co", tenant_id="test-co")

    @pytest.mark.asyncio
    async def test_successful_sync(self, fernet_key: str) -> None:
        svc = _service(fernet_key)

        conn = MagicMock()
        conn.id = "conn-id"
        conn.company_id = "company-id"
        conn.is_active = True
        conn.ga4_property_id = "123456"
        conn.access_token_encrypted = svc._encrypt_token("ya29.access")
        conn.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.update_sync_status = AsyncMock()
        svc._conn_repo = conn_repo

        traffic_repo = AsyncMock()
        traffic_repo.bulk_upsert = AsyncMock(return_value=5)
        traffic_repo.mark_ai_referrals = AsyncMock(return_value=2)
        svc._traffic_repo = traffic_repo

        conv_repo = AsyncMock()
        conv_repo.bulk_upsert = AsyncMock(return_value=3)
        conv_repo.mark_ai_referrals = AsyncMock(return_value=1)
        svc._conv_repo = conv_repo

        mock_traffic = [TrafficRow(date="2026-03-15", landing_page_url="/test", source="google", medium="organic")]
        mock_conversions = [ConversionRow(date="2026-03-15", event_name="sign_up", landing_page_url="/test", source="google", medium="organic")]

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.run_traffic_report = AsyncMock(return_value=mock_traffic)
            mock_adapter.run_conversion_report = AsyncMock(return_value=mock_conversions)
            mock_build.return_value = mock_adapter

            result = await svc.sync_data(company_slug="test-co", tenant_id="test-co")

        assert isinstance(result, SyncResult)
        assert result.traffic_rows_synced == 5
        assert result.conversion_rows_synced == 3
        assert result.ai_referrals_tagged == 3  # 2 + 1

        # Verify sync status updates
        calls = conn_repo.update_sync_status.call_args_list
        assert calls[0].kwargs["status"] == AnalyticsSyncStatus.in_progress
        assert calls[1].kwargs["status"] == AnalyticsSyncStatus.success
        assert result.errors == []
        traffic_payload = traffic_repo.bulk_upsert.call_args.args[0]
        conv_payload = conv_repo.bulk_upsert.call_args.args[0]
        assert traffic_payload[0]["date"] == date(2026, 3, 15)
        assert conv_payload[0]["date"] == date(2026, 3, 15)

    @pytest.mark.asyncio
    async def test_partial_failure_traffic_fails_conversions_succeed(self, fernet_key: str) -> None:
        """If traffic report fails, conversions should still be processed."""
        svc = _service(fernet_key)

        conn = MagicMock()
        conn.id = "conn-id"
        conn.company_id = "company-id"
        conn.is_active = True
        conn.ga4_property_id = "123456"
        conn.access_token_encrypted = svc._encrypt_token("ya29.access")
        conn.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.update_sync_status = AsyncMock()
        svc._conn_repo = conn_repo

        traffic_repo = AsyncMock()
        traffic_repo.bulk_upsert = AsyncMock(return_value=0)
        traffic_repo.mark_ai_referrals = AsyncMock(return_value=0)
        svc._traffic_repo = traffic_repo

        conv_repo = AsyncMock()
        conv_repo.bulk_upsert = AsyncMock(return_value=3)
        conv_repo.mark_ai_referrals = AsyncMock(return_value=1)
        svc._conv_repo = conv_repo

        mock_conversions = [ConversionRow(date="2026-03-15", event_name="sign_up", landing_page_url="/test", source="google", medium="organic")]

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            # Traffic report raises, conversion succeeds
            mock_adapter.run_traffic_report = AsyncMock(
                side_effect=GA4Error("traffic API error")
            )
            mock_adapter.run_conversion_report = AsyncMock(return_value=mock_conversions)
            mock_build.return_value = mock_adapter

            result = await svc.sync_data(company_slug="test-co", tenant_id="test-co")

        assert result.traffic_rows_synced == 0
        assert result.conversion_rows_synced == 3
        assert len(result.errors) == 1
        assert "traffic_report" in result.errors[0]

        # Conversion data was still upserted
        conv_repo.bulk_upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_failure_auth_error_still_raises(self, fernet_key: str) -> None:
        """Auth errors should still propagate even in partial failure mode."""
        svc = _service(fernet_key)

        conn = MagicMock()
        conn.id = "conn-id"
        conn.company_id = "company-id"
        conn.is_active = True
        conn.ga4_property_id = "123456"
        conn.access_token_encrypted = svc._encrypt_token("ya29.access")
        conn.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.update_sync_status = AsyncMock()
        svc._conn_repo = conn_repo

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.run_traffic_report = AsyncMock(
                side_effect=GA4AuthError("token revoked")
            )
            mock_adapter.run_conversion_report = AsyncMock(return_value=[])
            mock_build.return_value = mock_adapter

            with pytest.raises(GA4AuthError, match="token revoked"):
                await svc.sync_data(company_slug="test-co", tenant_id="test-co")

    @pytest.mark.asyncio
    async def test_generic_failure_rolls_back_before_marking_failed(self, fernet_key: str) -> None:
        svc = _service(fernet_key)

        conn = MagicMock()
        conn.id = "conn-id"
        conn.company_id = "company-id"
        conn.is_active = True
        conn.ga4_property_id = "123456"
        conn.access_token_encrypted = svc._encrypt_token("ya29.access")
        conn.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.update_sync_status = AsyncMock()
        conn_repo._session = AsyncMock()
        svc._conn_repo = conn_repo

        traffic_repo = AsyncMock()
        traffic_repo.bulk_upsert = AsyncMock(side_effect=RuntimeError("insert failed"))
        svc._traffic_repo = traffic_repo

        conv_repo = AsyncMock()
        conv_repo.bulk_upsert = AsyncMock(return_value=0)
        svc._conv_repo = conv_repo

        mock_traffic = [
            TrafficRow(
                date="2026-03-15",
                landing_page_url="/test",
                source="google",
                medium="organic",
            )
        ]

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.run_traffic_report = AsyncMock(return_value=mock_traffic)
            mock_adapter.run_conversion_report = AsyncMock(return_value=[])
            mock_build.return_value = mock_adapter

            with pytest.raises(RuntimeError, match="insert failed"):
                await svc.sync_data(company_slug="test-co", tenant_id="test-co")

        conn_repo._session.rollback.assert_awaited_once()
        calls = conn_repo.update_sync_status.call_args_list
        assert calls[0].kwargs["status"] == AnalyticsSyncStatus.in_progress
        assert calls[1].kwargs["status"] == AnalyticsSyncStatus.failed

    @pytest.mark.asyncio
    async def test_failure_uses_captured_connection_id_after_rollback(self, fernet_key: str) -> None:
        svc = _service(fernet_key)

        class _Conn:
            def __init__(self) -> None:
                self._expired = False
                self.company_id = "company-id"
                self.is_active = True
                self.ga4_property_id = "123456"
                self.access_token_encrypted = svc._encrypt_token("ya29.access")
                self.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

            @property
            def id(self):
                if self._expired:
                    raise AssertionError("conn.id accessed after rollback")
                return "conn-id"

        conn = _Conn()
        conn_repo = AsyncMock()
        conn_repo.get_by_company_slug = AsyncMock(return_value=conn)
        conn_repo.update_sync_status = AsyncMock()
        conn_repo._session = AsyncMock()

        async def _rollback():
            conn._expired = True

        conn_repo._session.rollback.side_effect = _rollback
        svc._conn_repo = conn_repo

        traffic_repo = AsyncMock()
        traffic_repo.bulk_upsert = AsyncMock(side_effect=RuntimeError("insert failed"))
        svc._traffic_repo = traffic_repo

        with patch.object(svc, "_build_adapter") as mock_build:
            mock_adapter = AsyncMock()
            mock_adapter.run_traffic_report = AsyncMock(
                return_value=[
                    TrafficRow(
                        date="2026-03-15",
                        landing_page_url="/test",
                        source="google",
                        medium="organic",
                    )
                ]
            )
            mock_adapter.run_conversion_report = AsyncMock(return_value=[])
            mock_build.return_value = mock_adapter

            with pytest.raises(RuntimeError, match="insert failed"):
                await svc.sync_data(company_slug="test-co", tenant_id="test-co")

        failed_call = conn_repo.update_sync_status.call_args_list[1]
        assert failed_call.args[0] == "conn-id"
