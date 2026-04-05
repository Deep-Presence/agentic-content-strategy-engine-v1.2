"""GA4 analytics service — orchestrates OAuth, property management, and data sync.

Standalone orchestrator (like ``CMSService``), injected with repos and config.
Does NOT follow the Protocol/JsonService/DbService pattern.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.analytics.exceptions import GA4AuthError, GA4Error
from core.analytics.factory import create_analytics_adapter
from core.analytics.models import (
    AnalyticsConnectionInfo,
    ConversionRow,
    GA4Property,
    GA4TokenSet,
    SyncResult,
    TrafficRow,
)
from core.db.enums import AnalyticsProvider, AnalyticsSyncStatus
from core.db.repositories.analytics_repo import (
    AnalyticsConnectionRepository,
    GA4ConversionEventRepository,
    GA4TrafficDataRepository,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_TOKEN_REFRESH_BUFFER_SECONDS = 300  # 5 minutes before expiry
_OAUTH_STATE_EXPIRY_MINUTES = 10


class GA4AnalyticsService:
    """Orchestrates GA4 OAuth, property management, and data sync."""

    def __init__(
        self,
        *,
        connection_repo: AnalyticsConnectionRepository,
        traffic_repo: GA4TrafficDataRepository,
        conversion_repo: GA4ConversionEventRepository,
        fernet_key: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        ai_referral_sources: str = "",
        lookback_days: int = 7,
    ) -> None:
        self._conn_repo = connection_repo
        self._traffic_repo = traffic_repo
        self._conv_repo = conversion_repo
        self._fernet_key = fernet_key
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._lookback_days = lookback_days
        self._ai_referral_map = self._parse_ai_referral_sources(ai_referral_sources)

    # ── OAuth flow ───────────────────────────────────────────────────

    def generate_authorize_url(
        self,
        *,
        secret_key: str,
        company_slug: str,
        return_url: str = "",
    ) -> str:
        """Generate the Google OAuth consent URL with a signed state token.

        Uses the same HMAC-SHA256 signed token format as
        ``core/auth/utils/tokens.py``.
        """
        adapter = self._build_adapter()
        state = self._create_oauth_state(
            secret_key=secret_key,
            company_slug=company_slug,
            return_url=return_url,
        )
        # build_authorization_url is a coroutine but only does string ops,
        # so we can run it eagerly in a sync context via a small event-loop trick.
        # However, since the router is async, we return a coroutine-compatible value.
        # The router will ``await`` the adapter call separately.
        # We pre-build the URL synchronously here since it's pure string work.
        from urllib.parse import urlencode

        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/analytics.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @staticmethod
    def verify_oauth_state(secret_key: str, state: str) -> dict | None:
        """Verify and decode an OAuth state token.

        Returns the payload dict if valid and not expired, else ``None``.
        """
        try:
            parts = state.split(".", 1)
            if len(parts) != 2:
                return None
            payload_b64, sig = parts
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            expected_sig = hmac.new(
                secret_key.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            payload = json.loads(payload_bytes)
            exp = datetime.fromisoformat(payload.get("exp", ""))
            if datetime.now(timezone.utc) > exp:
                return None
            if payload.get("purpose") != "ga4_oauth":
                return None
            return payload
        except Exception:
            return None

    async def exchange_code_and_store(
        self,
        *,
        code: str,
        company_id: str,
        company_slug: str,
        tenant_id: str,
    ) -> None:
        """Exchange authorization code for tokens and store the connection."""
        adapter = self._build_adapter()
        token_set = await adapter.exchange_code_for_tokens(code)

        access_enc = self._encrypt_token(token_set.access_token)
        refresh_enc = self._encrypt_token(token_set.refresh_token)

        # Check for existing connection (re-auth or reconnect scenario)
        existing = await self._conn_repo.get_by_company_slug(
            company_slug, tenant_id, active_only=False,
        )

        if existing:
            await self._conn_repo.update_tokens(
                existing.id,
                access_token_encrypted=access_enc,
                refresh_token_encrypted=refresh_enc,
                token_expiry=token_set.token_expiry,
            )
            # Re-activate if previously deactivated
            if not existing.is_active:
                from sqlalchemy import update

                from core.db.models.analytics import AnalyticsConnectionModel

                stmt = (
                    update(AnalyticsConnectionModel)
                    .where(AnalyticsConnectionModel.id == existing.id)
                    .values(
                        is_active=True,
                        scopes_granted=token_set.scopes or None,
                        last_sync_status=None,
                        last_sync_error="",
                    )
                )
                await self._conn_repo._session.execute(stmt)
                await self._conn_repo._session.flush()
        else:
            cid = (
                _uuid.UUID(company_id)
                if isinstance(company_id, str)
                else company_id
            )
            await self._conn_repo.create(
                company_id=cid,
                company_slug=company_slug,
                tenant_id=tenant_id,
                provider=AnalyticsProvider.ga4,
                access_token_encrypted=access_enc,
                refresh_token_encrypted=refresh_enc,
                token_expiry=token_set.token_expiry,
                scopes_granted=token_set.scopes or None,
                is_active=True,
            )

    # ── Connection info ──────────────────────────────────────────────

    async def get_connection_info(
        self,
        company_slug: str,
        *,
        tenant_id: str,
    ) -> Optional[AnalyticsConnectionInfo]:
        """Return public-facing connection status (no secrets)."""
        conn = await self._conn_repo.get_by_company_slug(company_slug, tenant_id)
        if conn is None:
            return None
        return AnalyticsConnectionInfo(
            provider=conn.provider.value if conn.provider else "ga4",
            ga4_property_id=conn.ga4_property_id or "",
            ga4_property_name=conn.ga4_property_name or "",
            ga4_account_id=conn.ga4_account_id or "",
            is_active=conn.is_active,
            connected_at=conn.connected_at,
            last_sync_at=conn.last_sync_at,
            last_sync_status=conn.last_sync_status.value if conn.last_sync_status else "",
            last_sync_error=conn.last_sync_error or "",
        )

    async def disconnect(
        self,
        company_slug: str,
        *,
        tenant_id: str,
        purge_data: bool = False,
    ) -> bool:
        """Revoke OAuth tokens and deactivate the connection.

        If *purge_data* is ``True``, also delete all synced GA4 traffic and
        conversion data for the connection (GDPR compliance).
        """
        conn = await self._conn_repo.get_by_company_slug(company_slug, tenant_id)
        if conn is None:
            return False

        # Best-effort token revocation with Google
        try:
            refresh_token = self._decrypt_token(conn.refresh_token_encrypted)
            adapter = self._build_adapter()
            await adapter.revoke_token(refresh_token)
        except Exception:
            logger.warning("Token revocation failed (best-effort)", exc_info=True)

        await self._conn_repo.deactivate(conn.id)

        if purge_data:
            await self._traffic_repo.delete_by_connection(conn.id)
            await self._conv_repo.delete_by_connection(conn.id)

        return True

    # ── Property management ──────────────────────────────────────────

    async def list_properties(
        self,
        company_slug: str,
        *,
        tenant_id: str,
    ) -> list[GA4Property]:
        """List GA4 properties the connected account has access to."""
        conn = await self._conn_repo.get_by_company_slug(company_slug, tenant_id)
        if conn is None or not conn.is_active:
            raise GA4AuthError("No active analytics connection")

        access_token = await self._ensure_fresh_token(conn)
        adapter = self._build_adapter()
        return await adapter.list_properties(access_token)

    async def select_property(
        self,
        *,
        company_slug: str,
        tenant_id: str,
        property_id: str,
        property_name: str,
        account_id: str,
    ) -> None:
        """Store the selected GA4 property for syncing."""
        conn = await self._conn_repo.get_by_company_slug(company_slug, tenant_id)
        if conn is None:
            raise GA4AuthError("No active analytics connection")
        await self._conn_repo.update_property(
            conn.id,
            ga4_property_id=property_id,
            ga4_property_name=property_name,
            ga4_account_id=account_id,
        )

    # ── Data sync ────────────────────────────────────────────────────

    async def sync_data(
        self,
        *,
        company_slug: str,
        tenant_id: str,
        start_date_override: str | None = None,
        end_date_override: str | None = None,
    ) -> SyncResult:
        """Run the GA4 data sync — fetch reports, upsert, classify AI referrals."""
        conn = await self._conn_repo.get_by_company_slug(company_slug, tenant_id)
        if conn is None or not conn.is_active:
            raise GA4AuthError("No active analytics connection")
        if not conn.ga4_property_id:
            raise GA4Error("No GA4 property selected")

        # Mark in-progress
        await self._conn_repo.update_sync_status(
            conn.id, status=AnalyticsSyncStatus.in_progress
        )

        try:
            access_token = await self._ensure_fresh_token(conn)
            adapter = self._build_adapter()

            start_date = start_date_override or f"{self._lookback_days}daysAgo"
            end_date = end_date_override or "yesterday"

            # Run both reports in parallel — partial failure: if one report
            # fails, still process the other (spec Section 8).
            results = await asyncio.gather(
                adapter.run_traffic_report(
                    access_token, conn.ga4_property_id, start_date, end_date
                ),
                adapter.run_conversion_report(
                    access_token, conn.ga4_property_id, start_date, end_date
                ),
                return_exceptions=True,
            )

            errors: list[str] = []
            traffic_rows: list[TrafficRow] = []
            conversion_rows: list[ConversionRow] = []

            if isinstance(results[0], BaseException):
                logger.warning(
                    "GA4 traffic report failed for %s: %s",
                    company_slug, results[0],
                )
                errors.append(f"traffic_report: {results[0]}")
                # Re-raise auth errors even in partial-failure mode
                if isinstance(results[0], GA4AuthError):
                    raise results[0]
            else:
                traffic_rows = results[0]

            if isinstance(results[1], BaseException):
                logger.warning(
                    "GA4 conversion report failed for %s: %s",
                    company_slug, results[1],
                )
                errors.append(f"conversion_report: {results[1]}")
                if isinstance(results[1], GA4AuthError):
                    raise results[1]
            else:
                conversion_rows = results[1]

            # Bulk upsert traffic data
            traffic_count = 0
            if traffic_rows:
                traffic_dicts = [
                    {
                        "connection_id": conn.id,
                        "company_id": conn.company_id,
                        "date": row.date,
                        "landing_page_url": row.landing_page_url,
                        "source": row.source,
                        "medium": row.medium,
                        "campaign": row.campaign,
                        "sessions": row.sessions,
                        "engaged_sessions": row.engaged_sessions,
                        "engagement_rate": row.engagement_rate,
                        "bounce_rate": row.bounce_rate,
                        "avg_session_duration_secs": row.avg_session_duration_secs,
                        "screen_page_views": row.screen_page_views,
                        "conversions": row.conversions,
                        "new_users": row.new_users,
                        "returning_users": row.returning_users,
                        "synced_at": datetime.now(timezone.utc),
                    }
                    for row in traffic_rows
                ]
                traffic_count = await self._traffic_repo.bulk_upsert(traffic_dicts)

            # Bulk upsert conversion data
            conv_count = 0
            if conversion_rows:
                conv_dicts = [
                    {
                        "connection_id": conn.id,
                        "company_id": conn.company_id,
                        "date": row.date,
                        "event_name": row.event_name,
                        "landing_page_url": row.landing_page_url,
                        "source": row.source,
                        "medium": row.medium,
                        "event_count": row.event_count,
                        "event_value": row.event_value,
                        "synced_at": datetime.now(timezone.utc),
                    }
                    for row in conversion_rows
                ]
                conv_count = await self._conv_repo.bulk_upsert(conv_dicts)

            # Classify AI referrals
            ai_tagged = 0
            if self._ai_referral_map:
                t_tagged = await self._traffic_repo.mark_ai_referrals(
                    conn.id, self._ai_referral_map
                )
                c_tagged = await self._conv_repo.mark_ai_referrals(
                    conn.id, self._ai_referral_map
                )
                ai_tagged = t_tagged + c_tagged

            # Mark success
            now = datetime.now(timezone.utc)
            await self._conn_repo.update_sync_status(
                conn.id,
                status=AnalyticsSyncStatus.success,
                last_sync_at=now,
            )

            result = SyncResult(
                traffic_rows_synced=traffic_count,
                conversion_rows_synced=conv_count,
                date_range_start=start_date,
                date_range_end=end_date,
                ai_referrals_tagged=ai_tagged,
                errors=errors,
            )
            logger.info(
                "GA4 sync completed for %s: %d traffic, %d conversions, %d AI referrals, %d errors",
                company_slug,
                traffic_count,
                conv_count,
                ai_tagged,
                len(errors),
            )
            return result

        except GA4AuthError:
            await self._conn_repo.update_sync_status(
                conn.id,
                status=AnalyticsSyncStatus.auth_revoked,
                error="Token revoked or expired",
            )
            await self._conn_repo.deactivate(conn.id)
            raise
        except Exception as exc:
            await self._conn_repo.update_sync_status(
                conn.id,
                status=AnalyticsSyncStatus.failed,
                error=str(exc)[:1000],
            )
            raise

    # ── Private helpers ──────────────────────────────────────────────

    def _build_adapter(self):
        """Create a GA4 adapter with current OAuth credentials."""
        return create_analytics_adapter(
            AnalyticsProvider.ga4,
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=self._redirect_uri,
        )

    async def _ensure_fresh_token(self, connection) -> str:
        """Decrypt the access token, refreshing first if near expiry.

        Returns the plaintext access token ready for API calls.
        """
        needs_refresh = (
            connection.token_expiry is None
            or connection.token_expiry
            <= datetime.now(timezone.utc) + timedelta(seconds=_TOKEN_REFRESH_BUFFER_SECONDS)
        )

        if needs_refresh:
            refresh_token = self._decrypt_token(connection.refresh_token_encrypted)
            adapter = self._build_adapter()
            try:
                new_tokens = await adapter.refresh_access_token(refresh_token)
            except GA4AuthError:
                # Refresh failed — mark connection as auth_revoked
                await self._conn_repo.update_sync_status(
                    connection.id,
                    status=AnalyticsSyncStatus.auth_revoked,
                    error="Token refresh failed — access revoked",
                )
                await self._conn_repo.deactivate(connection.id)
                raise

            new_access_enc = self._encrypt_token(new_tokens.access_token)
            await self._conn_repo.update_tokens(
                connection.id,
                access_token_encrypted=new_access_enc,
                token_expiry=new_tokens.token_expiry,
            )
            return new_tokens.access_token

        return self._decrypt_token(connection.access_token_encrypted)

    def _encrypt_token(self, plaintext: str) -> str:
        """Encrypt a token using Fernet symmetric encryption."""
        from cryptography.fernet import Fernet

        return Fernet(self._fernet_key.encode()).encrypt(
            plaintext.encode()
        ).decode()

    def _decrypt_token(self, ciphertext: str) -> str:
        """Decrypt a Fernet-encrypted token."""
        from cryptography.fernet import Fernet

        return Fernet(self._fernet_key.encode()).decrypt(
            ciphertext.encode()
        ).decode()

    @staticmethod
    def _create_oauth_state(
        *,
        secret_key: str,
        company_slug: str,
        return_url: str = "",
    ) -> str:
        """Create a signed state token for the GA4 OAuth flow.

        Contains ``company_slug``, ``return_url``, ``purpose``, and ``exp``.
        Signed with HMAC-SHA256 — forgery-proof and time-limited (10 min).
        """
        payload = {
            "company_slug": company_slug,
            "return_url": return_url,
            "purpose": "ga4_oauth",
            "exp": (
                datetime.now(timezone.utc)
                + timedelta(minutes=_OAUTH_STATE_EXPIRY_MINUTES)
            ).isoformat(),
        }
        payload_bytes = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()
        sig = hmac.new(
            secret_key.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return f"{payload_b64}.{sig}"

    @staticmethod
    def _parse_ai_referral_sources(raw: str) -> dict[str, str]:
        """Parse ``domain:platform,domain:platform,...`` into a dict."""
        if not raw:
            return {}
        result: dict[str, str] = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                domain, platform = pair.split(":", 1)
                result[domain.strip()] = platform.strip()
        return result
