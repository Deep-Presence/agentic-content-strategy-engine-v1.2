"""GA4 analytics integration exceptions."""
from __future__ import annotations


class GA4Error(Exception):
    """Base exception for all GA4 analytics operations."""

    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GA4AuthError(GA4Error):
    """Authentication/authorization failure (401/403, revoked tokens)."""


class GA4QuotaError(GA4Error):
    """Google API quota exceeded (429 rate limit)."""


class GA4APIError(GA4Error):
    """General Google Analytics API error (500s, network, malformed responses)."""
