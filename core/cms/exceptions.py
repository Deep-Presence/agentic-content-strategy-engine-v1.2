"""CMS exception hierarchy.

All CMS-related exceptions inherit from CMSError so callers can
catch broadly (``except CMSError``) or narrowly (``except CMSAuthError``).
"""
from __future__ import annotations


class CMSError(Exception):
    """Base exception for all CMS operations."""


class CMSAuthError(CMSError):
    """Invalid or expired credentials."""


class CMSAPIError(CMSError):
    """CMS API returned an unexpected error."""


class CMSNotFoundError(CMSError):
    """Resource (post, category, media) not found."""


class CMSRateLimitError(CMSError):
    """CMS API rate limit hit."""


class CMSConnectionError(CMSError):
    """Cannot reach the CMS (DNS, timeout, etc.)."""
