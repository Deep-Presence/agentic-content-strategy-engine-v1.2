"""Domain models for analytics integration (GA4).

These are Pydantic models used internally by the analytics service layer.
They are NOT the API request/response schemas (see ``api/schemas/analytics.py``).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.db.enums import AnalyticsProvider, AnalyticsSyncStatus  # noqa: F401 (re-export)


# ── GA4 Property (Admin API) ────────────────────────────────────────


class GA4Property(BaseModel):
    """A GA4 property returned from Google Analytics Admin API."""

    property_id: str = ""
    display_name: str = ""
    account_id: str = ""
    account_display_name: str = ""
    timezone: str = ""
    currency_code: str = ""
    industry_category: str = ""
    service_level: str = ""


# ── OAuth Token Set (internal only — never serialized to API) ───────


class GA4TokenSet(BaseModel):
    """Decrypted token set for a GA4 connection."""

    access_token: str = ""
    refresh_token: str = ""
    token_expiry: datetime | None = None
    scopes: list[str] = Field(default_factory=list)


# ── Sync Pipeline Data ──────────────────────────────────────────────


class TrafficRow(BaseModel):
    """Single row of GA4 traffic data (intermediate model for sync pipeline)."""

    date: str = ""
    landing_page_url: str = ""
    source: str = ""
    medium: str = ""
    campaign: str = ""
    sessions: int = 0
    engaged_sessions: int = 0
    engagement_rate: float = 0.0
    bounce_rate: float = 0.0
    avg_session_duration_secs: float = 0.0
    screen_page_views: int = 0
    conversions: int = 0
    new_users: int = 0
    returning_users: int = 0


class ConversionRow(BaseModel):
    """Single row of GA4 conversion event data."""

    date: str = ""
    event_name: str = ""
    landing_page_url: str = ""
    source: str = ""
    medium: str = ""
    event_count: int = 0
    event_value: float = 0.0


# ── Sync Result ─────────────────────────────────────────────────────


class SyncResult(BaseModel):
    """Outcome of a GA4 data sync operation."""

    traffic_rows_synced: int = 0
    conversion_rows_synced: int = 0
    date_range_start: str = ""
    date_range_end: str = ""
    ai_referrals_tagged: int = 0
    errors: list[str] = Field(default_factory=list)


# ── Connection Info (safe to expose — no secrets) ───────────────────


class AnalyticsConnectionInfo(BaseModel):
    """Public-facing connection status (no encrypted tokens)."""

    provider: str = "ga4"
    ga4_property_id: str = ""
    ga4_property_name: str = ""
    ga4_account_id: str = ""
    is_active: bool = False
    connected_at: datetime | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str = ""
    last_sync_error: str = ""
