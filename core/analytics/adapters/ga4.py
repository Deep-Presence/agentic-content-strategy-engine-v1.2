"""GA4 adapter — wraps Google Analytics Data API (v1beta) and Admin API (v1alpha).

All synchronous Google SDK calls are wrapped with ``asyncio.to_thread()``
so they never block the event loop.

OAuth token exchange/refresh uses ``httpx`` directly (no SDK needed).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from core.analytics.exceptions import GA4APIError, GA4AuthError, GA4QuotaError
from core.analytics.models import ConversionRow, GA4Property, GA4TokenSet, TrafficRow

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

_DATA_API_MAX_ROWS = 100_000
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 1
_MAX_PAGINATION_ITERATIONS = 1000  # safety limit to prevent infinite loops


class GA4Adapter:
    """Concrete ``AnalyticsAdapterProtocol`` implementation for Google Analytics 4."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    # ── OAuth helpers (httpx, async-native) ──────────────────────────

    async def build_authorization_url(self, state: str) -> str:
        """Construct the Google OAuth consent URL."""
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": _SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> GA4TokenSet:
        """Exchange an authorization code for access + refresh tokens."""
        payload = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_GOOGLE_TOKEN_URL, data=payload)

        if resp.status_code != 200:
            detail = resp.text[:500]
            raise GA4AuthError(
                f"Token exchange failed ({resp.status_code}): {detail}",
                status_code=resp.status_code,
            )

        data = resp.json()
        expires_in = int(data.get("expires_in", 3600))
        scopes = data.get("scope", "").split()

        refresh_token = data.get("refresh_token", "")
        if not refresh_token:
            raise GA4AuthError(
                "Google did not return a refresh token — offline access may not "
                "have been granted. Ensure prompt=consent and access_type=offline."
            )

        return GA4TokenSet(
            access_token=data["access_token"],
            refresh_token=refresh_token,
            token_expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scopes=scopes,
        )

    async def refresh_access_token(self, refresh_token: str) -> GA4TokenSet:
        """Refresh an expired access token.

        Note: Google typically does NOT return a new refresh_token on refresh.
        """
        payload = {
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_GOOGLE_TOKEN_URL, data=payload)

        if resp.status_code != 200:
            detail = resp.text[:500]
            raise GA4AuthError(
                f"Token refresh failed ({resp.status_code}): {detail}",
                status_code=resp.status_code,
            )

        data = resp.json()
        expires_in = int(data.get("expires_in", 3600))

        return GA4TokenSet(
            access_token=data["access_token"],
            refresh_token=refresh_token,  # keep the original
            token_expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scopes=data.get("scope", "").split(),
        )

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token with Google.  Best-effort — does not raise on failure."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _GOOGLE_REVOKE_URL,
                    data={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            return resp.status_code == 200
        except Exception:
            logger.warning("Token revocation failed (best-effort)", exc_info=True)
            return False

    # ── Admin API — list GA4 properties ──────────────────────────────

    async def list_properties(self, access_token: str) -> list[GA4Property]:
        """List GA4 properties via the Admin API ``accountSummaries``."""
        from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)

        def _fetch() -> list[GA4Property]:
            client = AnalyticsAdminServiceClient(credentials=creds)
            properties: list[GA4Property] = []
            for summary in client.list_account_summaries():
                account_id = summary.account.replace("accounts/", "")
                account_name = summary.display_name
                for prop in summary.property_summaries:
                    properties.append(
                        GA4Property(
                            property_id=prop.property.replace("properties/", ""),
                            display_name=prop.display_name,
                            account_id=account_id,
                            account_display_name=account_name,
                        )
                    )
            return properties

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise self._translate_google_error(exc) from exc

    # ── Data API — reports ───────────────────────────────────────────

    async def run_traffic_report(
        self,
        access_token: str,
        property_id: str,
        start_date: str,
        end_date: str,
    ) -> list[TrafficRow]:
        """Run the traffic-by-page-path report used by Content Performance.

        We intentionally use ``pagePath`` here instead of ``landingPage``.
        Content Performance needs traffic attributed to the page itself, not
        only to sessions that started on that page.
        """
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        prop_resource = f"properties/{property_id}"

        dimensions = [
            Dimension(name="date"),
            Dimension(name="pagePath"),
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
            Dimension(name="sessionCampaignName"),
        ]
        metrics = [
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="engagementRate"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="screenPageViews"),
            Metric(name="conversions"),
            Metric(name="newUsers"),
            Metric(name="totalUsers"),
        ]
        date_range = DateRange(start_date=start_date, end_date=end_date)

        all_rows: list[TrafficRow] = []
        offset = 0
        warned_large = False

        for _iteration in range(_MAX_PAGINATION_ITERATIONS):
            request = RunReportRequest(
                property=prop_resource,
                dimensions=dimensions,
                metrics=metrics,
                date_ranges=[date_range],
                limit=_DATA_API_MAX_ROWS,
                offset=offset,
            )
            response = await self._run_report_with_retry(creds, request)
            for row in response.rows:
                all_rows.append(self._parse_traffic_row(row))

            if not warned_large and response.row_count > _DATA_API_MAX_ROWS:
                logger.warning(
                    "GA4 traffic report has %d rows (>%d) — may impact quota/performance",
                    response.row_count,
                    _DATA_API_MAX_ROWS,
                )
                warned_large = True

            offset += _DATA_API_MAX_ROWS
            if offset >= response.row_count:
                break
            logger.info(
                "GA4 traffic report pagination: fetched %d / %d rows",
                offset,
                response.row_count,
            )
        else:
            logger.error(
                "GA4 traffic report pagination exceeded %d iterations",
                _MAX_PAGINATION_ITERATIONS,
            )

        return all_rows

    async def run_conversion_report(
        self,
        access_token: str,
        property_id: str,
        start_date: str,
        end_date: str,
    ) -> list[ConversionRow]:
        """Run the conversion-events report (Report 2 from spec)."""
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        prop_resource = f"properties/{property_id}"

        dimensions = [
            Dimension(name="date"),
            Dimension(name="eventName"),
            Dimension(name="landingPage"),
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
        ]
        metrics = [
            Metric(name="eventCount"),
            Metric(name="eventValue"),
        ]
        date_range = DateRange(start_date=start_date, end_date=end_date)

        all_rows: list[ConversionRow] = []
        offset = 0
        warned_large = False

        for _iteration in range(_MAX_PAGINATION_ITERATIONS):
            request = RunReportRequest(
                property=prop_resource,
                dimensions=dimensions,
                metrics=metrics,
                date_ranges=[date_range],
                limit=_DATA_API_MAX_ROWS,
                offset=offset,
            )
            response = await self._run_report_with_retry(creds, request)
            for row in response.rows:
                all_rows.append(self._parse_conversion_row(row))

            if not warned_large and response.row_count > _DATA_API_MAX_ROWS:
                logger.warning(
                    "GA4 conversion report has %d rows (>%d) — may impact quota/performance",
                    response.row_count,
                    _DATA_API_MAX_ROWS,
                )
                warned_large = True

            offset += _DATA_API_MAX_ROWS
            if offset >= response.row_count:
                break
            logger.info(
                "GA4 conversion report pagination: fetched %d / %d rows",
                offset,
                response.row_count,
            )
        else:
            logger.error(
                "GA4 conversion report pagination exceeded %d iterations",
                _MAX_PAGINATION_ITERATIONS,
            )

        return all_rows

    # ── Private helpers ──────────────────────────────────────────────

    async def _run_report_with_retry(self, creds: object, request: object) -> object:
        """Execute a RunReportRequest with exponential backoff on 429."""
        from google.analytics.data_v1beta import BetaAnalyticsDataClient

        for attempt in range(_MAX_RETRIES):
            try:
                def _call() -> object:
                    client = BetaAnalyticsDataClient(credentials=creds)
                    return client.run_report(request)

                return await asyncio.to_thread(_call)
            except Exception as exc:
                if self._is_quota_error(exc) and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BASE_SECONDS * (2 ** attempt)
                    logger.warning(
                        "GA4 quota hit (attempt %d/%d), retrying in %ds",
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise self._translate_google_error(exc) from exc

        # Should not reach here, but just in case
        raise GA4QuotaError("GA4 API quota exceeded after retries")

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        """Check if the exception is a Google quota/rate-limit error."""
        try:
            from google.api_core.exceptions import ResourceExhausted

            return isinstance(exc, ResourceExhausted)
        except ImportError:
            return False

    @staticmethod
    def _translate_google_error(exc: Exception) -> GA4APIError:
        """Map Google API exceptions to our exception hierarchy."""
        try:
            from google.api_core.exceptions import (
                GoogleAPIError,
                PermissionDenied,
                ResourceExhausted,
                Unauthenticated,
            )

            if isinstance(exc, (PermissionDenied, Unauthenticated)):
                return GA4AuthError(str(exc), status_code=403)
            if isinstance(exc, ResourceExhausted):
                return GA4QuotaError(str(exc), status_code=429)
            if isinstance(exc, GoogleAPIError):
                code = getattr(exc, "code", None)
                return GA4APIError(str(exc), status_code=code)
        except ImportError:
            pass
        return GA4APIError(str(exc))

    @staticmethod
    def _parse_date(yyyymmdd: str) -> str:
        """Convert GA4 date format ``YYYYMMDD`` to ``YYYY-MM-DD``."""
        if len(yyyymmdd) == 8 and yyyymmdd.isdigit():
            return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
        return yyyymmdd

    def _parse_traffic_row(self, row: object) -> TrafficRow:
        """Parse a single GA4 traffic report row into a ``TrafficRow``."""
        dims = row.dimension_values
        mets = row.metric_values

        total_users = int(mets[8].value) if len(mets) > 8 else 0
        new_users = int(mets[7].value) if len(mets) > 7 else 0
        returning_users = max(total_users - new_users, 0)

        return TrafficRow(
            date=self._parse_date(dims[0].value),
            landing_page_url=dims[1].value if len(dims) > 1 else "",
            source=dims[2].value if len(dims) > 2 else "",
            medium=dims[3].value if len(dims) > 3 else "",
            campaign=dims[4].value if len(dims) > 4 else "",
            sessions=int(mets[0].value) if len(mets) > 0 else 0,
            engaged_sessions=int(mets[1].value) if len(mets) > 1 else 0,
            engagement_rate=float(mets[2].value) if len(mets) > 2 else 0.0,
            bounce_rate=float(mets[3].value) if len(mets) > 3 else 0.0,
            avg_session_duration_secs=float(mets[4].value) if len(mets) > 4 else 0.0,
            screen_page_views=int(mets[5].value) if len(mets) > 5 else 0,
            conversions=int(mets[6].value) if len(mets) > 6 else 0,
            new_users=new_users,
            returning_users=returning_users,
        )

    def _parse_conversion_row(self, row: object) -> ConversionRow:
        """Parse a single GA4 conversion report row into a ``ConversionRow``."""
        dims = row.dimension_values
        mets = row.metric_values

        return ConversionRow(
            date=self._parse_date(dims[0].value),
            event_name=dims[1].value if len(dims) > 1 else "",
            landing_page_url=dims[2].value if len(dims) > 2 else "",
            source=dims[3].value if len(dims) > 3 else "",
            medium=dims[4].value if len(dims) > 4 else "",
            event_count=int(mets[0].value) if len(mets) > 0 else 0,
            event_value=float(mets[1].value) if len(mets) > 1 else 0.0,
        )
