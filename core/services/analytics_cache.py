"""Redis cache helpers for GA4 analytics integration.

Provides get/set/invalidate functions for analytics-specific caches:
  - Connection info (display fields only, no credentials)
  - GA4 properties list (from Admin API)

All operations are synchronous (sub-ms Redis calls) because callers run
them via ``asyncio.to_thread()``.  Every function calls
``get_sync_redis_or_none()`` internally — no Redis injection needed.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.cache import cache_delete, cache_delete_pattern, cache_get, cache_set
from core.redis import get_sync_redis_or_none

logger = logging.getLogger(__name__)

# ── TTLs ─────────────────────────────────────────────────────────────

GA4_CONNECTION_TTL = 1800   # 30 min  — connection metadata is stable
GA4_PROPERTIES_TTL = 3600   # 1 hour  — properties rarely change


# ── Key builders ─────────────────────────────────────────────────────


def ga4_connection_key(company_slug: str, tenant_id: str) -> str:
    return f"cache:ga4:{company_slug}:connection:{tenant_id}"


def ga4_properties_key(company_slug: str, tenant_id: str) -> str:
    return f"cache:ga4:{company_slug}:properties:{tenant_id}"


# ── Connection info cache ────────────────────────────────────────────


def get_cached_ga4_connection(
    company_slug: str, tenant_id: str
) -> Optional[dict[str, Any]]:
    """Return cached connection display info or None on miss."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return None
    return cache_get(redis, ga4_connection_key(company_slug, tenant_id))


def set_cached_ga4_connection(
    company_slug: str, tenant_id: str, data: dict[str, Any]
) -> None:
    """Cache serialized connection info (display fields only)."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_set(
        redis, ga4_connection_key(company_slug, tenant_id),
        data, ttl=GA4_CONNECTION_TTL,
    )


def invalidate_ga4_connection(
    company_slug: str, tenant_id: str
) -> None:
    """Delete cached connection info."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_delete(redis, ga4_connection_key(company_slug, tenant_id))


# ── Properties cache ────────────────────────────────────────────────


def get_cached_ga4_properties(
    company_slug: str, tenant_id: str
) -> Optional[list[dict[str, Any]]]:
    """Return cached properties list or None on miss."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return None
    return cache_get(redis, ga4_properties_key(company_slug, tenant_id))


def set_cached_ga4_properties(
    company_slug: str, tenant_id: str, data: list[dict[str, Any]]
) -> None:
    """Cache serialized GA4 properties list."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_set(
        redis, ga4_properties_key(company_slug, tenant_id),
        data, ttl=GA4_PROPERTIES_TTL,
    )


def invalidate_ga4_properties(
    company_slug: str, tenant_id: str
) -> None:
    """Delete cached properties list."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_delete(redis, ga4_properties_key(company_slug, tenant_id))


# ── Bulk invalidation ────────────────────────────────────────────────


def invalidate_all_ga4_caches(company_slug: str) -> None:
    """Delete all GA4 cache keys for a company.

    Called after sync completes, disconnect, property selection, etc.
    """
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_delete_pattern(redis, f"cache:ga4:{company_slug}:*")
