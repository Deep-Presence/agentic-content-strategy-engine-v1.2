"""Analytics (GA4) integration request/response schemas.

All fields have defaults for backward compatibility (Pydantic v2 strict).
UUIDs are serialized as ``str`` (D2: UUIDPKMixin).
No encrypted data is exposed in any response schema.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────


class SelectPropertyRequest(BaseModel):
    """Select which GA4 property to sync."""

    property_id: str
    property_name: str = ""
    account_id: str = ""


class SyncRequest(BaseModel):
    """Trigger a manual GA4 data sync."""

    start_date: str | None = None  # ISO date, defaults to lookback_days
    end_date: str | None = None  # ISO date, defaults to yesterday


# ── Response Schemas ─────────────────────────────────────────────────


class AuthorizeResponse(BaseModel):
    """OAuth authorization URL for Google consent screen."""

    authorization_url: str = ""


class ConnectionResponse(BaseModel):
    """Current GA4 connection status for a company."""

    provider: str = ""
    ga4_property_id: str = ""
    ga4_property_name: str = ""
    ga4_account_id: str = ""
    is_active: bool = False
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    last_sync_status: str = ""


class GA4PropertyItem(BaseModel):
    """A single GA4 property for the property selection UI."""

    property_id: str = ""
    display_name: str = ""
    account_id: str = ""
    account_display_name: str = ""


class PropertiesResponse(BaseModel):
    """List of GA4 properties the user has access to."""

    properties: list[GA4PropertyItem] = Field(default_factory=list)


class SyncResponse(BaseModel):
    """Result of a manual GA4 sync trigger."""

    status: str = ""  # "started", "completed", "failed"
    traffic_rows_synced: int = 0
    conversion_rows_synced: int = 0
    ai_referrals_tagged: int = 0
    date_range_start: str = ""
    date_range_end: str = ""
    errors: list[str] = Field(default_factory=list)


class TrafficDataResponse(BaseModel):
    """Single row of synced GA4 traffic data."""

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
    is_ai_referral: bool = False
    ai_platform: str = ""


class ConversionDataResponse(BaseModel):
    """Single row of synced GA4 conversion event data."""

    date: str = ""
    event_name: str = ""
    landing_page_url: str = ""
    source: str = ""
    medium: str = ""
    event_count: int = 0
    event_value: float = 0.0
    is_ai_referral: bool = False
    ai_platform: str = ""


class DisconnectResponse(BaseModel):
    """Result of disconnecting GA4."""

    disconnected: bool = False
    data_purged: bool = False
    error: str | None = None
