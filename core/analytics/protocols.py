"""Analytics adapter protocol — runtime-checkable interface for analytics providers."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.analytics.models import ConversionRow, GA4Property, GA4TokenSet, TrafficRow


@runtime_checkable
class AnalyticsAdapterProtocol(Protocol):
    """Defines the contract every analytics adapter must satisfy."""

    async def build_authorization_url(self, state: str) -> str:
        """Return the full OAuth consent URL with *state* baked in."""
        ...

    async def exchange_code_for_tokens(self, code: str) -> GA4TokenSet:
        """Exchange an authorization code for access + refresh tokens."""
        ...

    async def refresh_access_token(self, refresh_token: str) -> GA4TokenSet:
        """Refresh an expired access token using the refresh token."""
        ...

    async def list_properties(self, access_token: str) -> list[GA4Property]:
        """List analytics properties the user has access to."""
        ...

    async def run_traffic_report(
        self,
        access_token: str,
        property_id: str,
        start_date: str,
        end_date: str,
    ) -> list[TrafficRow]:
        """Run the traffic-by-landing-page report."""
        ...

    async def run_conversion_report(
        self,
        access_token: str,
        property_id: str,
        start_date: str,
        end_date: str,
    ) -> list[ConversionRow]:
        """Run the conversion-events report."""
        ...

    async def revoke_token(self, token: str) -> bool:
        """Revoke an OAuth token with the provider.  Best-effort; returns True on success."""
        ...
