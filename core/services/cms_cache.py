"""Redis cache helpers for CMS integration.

Provides get/set/invalidate functions for CMS-specific caches:
  - Categories (from WordPress API)
  - Connection info (display fields only, no credentials)
  - Stale action cards (Home dashboard)
  - Synced posts (paginated lists)

All operations are synchronous (sub-ms Redis calls) because callers run
them via ``asyncio.to_thread()``.  Every function calls
``get_sync_redis_or_none()`` internally — no Redis injection needed.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Optional

from core.cache import cache_delete, cache_delete_pattern, cache_get, cache_set
from core.redis import get_sync_redis_or_none

logger = logging.getLogger(__name__)

# ── TTLs ─────────────────────────────────────────────────────────────

CMS_CATEGORIES_TTL = 3600   # 1 hour  — categories rarely change
CMS_CONNECTION_TTL = 1800   # 30 min  — connection metadata is stable
CMS_STALE_TTL = 1800        # 30 min  — stale list changes only on sync/queue
CMS_POSTS_TTL = 600         # 10 min  — synced posts, paginated


# ── Key builders ─────────────────────────────────────────────────────

def _normalize_site_url(site_url: str) -> str:
    """Normalize site_url for use in cache keys."""
    return site_url.rstrip("/").lower()


def cms_categories_key(site_url: str) -> str:
    return f"cache:cms:categories:{_normalize_site_url(site_url)}"


def cms_connection_key(company_slug: str, tenant_id: str) -> str:
    return f"cache:cms:{company_slug}:connection:{tenant_id}"


def cms_stale_key(company_slug: str) -> str:
    return f"cache:cms:{company_slug}:stale"


def cms_posts_key(
    company_slug: str,
    stale_only: bool,
    limit: int,
    offset: int,
) -> str:
    return (
        f"cache:cms:{company_slug}:posts:"
        f"stale={stale_only}:limit={limit}:offset={offset}"
    )


# ── Serialization helpers ────────────────────────────────────────────

def serialize_synced_post(post: Any) -> dict[str, Any]:
    """Serialize a CMSSyncedPostModel (or compatible) to a cache-safe dict."""
    return {
        "id": str(getattr(post, "id", "")),
        "cms_post_id": getattr(post, "cms_post_id", ""),
        "title": getattr(post, "title", ""),
        "slug": getattr(post, "slug", ""),
        "url": getattr(post, "url", ""),
        "word_count": getattr(post, "word_count", 0),
        "published_at": (
            post.published_at.isoformat()
            if getattr(post, "published_at", None)
            else None
        ),
        "modified_at": (
            post.modified_at.isoformat()
            if getattr(post, "modified_at", None)
            else None
        ),
        "is_stale": getattr(post, "is_stale", False),
        "staleness_days": getattr(post, "staleness_days", 0),
        "categories": getattr(post, "categories", []),
        "queued_for_refresh": getattr(post, "queued_for_refresh", False),
    }


def deserialize_synced_post(data: dict[str, Any]) -> SimpleNamespace:
    """Reconstruct a SimpleNamespace from a cached synced post dict.

    The router accesses attributes like ``p.id``, ``p.title``,
    ``p.categories`` — SimpleNamespace supports all of these.
    """
    return SimpleNamespace(**data)


# ── Categories cache ─────────────────────────────────────────────────

def get_cached_categories(site_url: str) -> Optional[list[dict[str, Any]]]:
    """Return cached categories list or None on miss."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return None
    return cache_get(redis, cms_categories_key(site_url))


def set_cached_categories(
    site_url: str, data: list[dict[str, Any]]
) -> None:
    """Cache serialized categories list."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_set(redis, cms_categories_key(site_url), data, ttl=CMS_CATEGORIES_TTL)


def invalidate_categories(site_url: str) -> None:
    """Delete cached categories for a site."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_delete(redis, cms_categories_key(site_url))


# ── Connection info cache ────────────────────────────────────────────

def get_cached_connection_info(
    company_slug: str, tenant_id: str
) -> Optional[dict[str, Any]]:
    """Return cached connection display info or None on miss."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return None
    return cache_get(redis, cms_connection_key(company_slug, tenant_id))


def set_cached_connection_info(
    company_slug: str, tenant_id: str, data: dict[str, Any]
) -> None:
    """Cache serialized connection info (display fields only)."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_set(
        redis, cms_connection_key(company_slug, tenant_id),
        data, ttl=CMS_CONNECTION_TTL,
    )


def invalidate_connection_info(
    company_slug: str, tenant_id: str
) -> None:
    """Delete cached connection info."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_delete(redis, cms_connection_key(company_slug, tenant_id))


# ── Stale actions cache ──────────────────────────────────────────────

def get_cached_stale_actions(
    company_slug: str,
) -> Optional[list[dict[str, Any]]]:
    """Return cached stale action cards or None on miss."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return None
    return cache_get(redis, cms_stale_key(company_slug))


def set_cached_stale_actions(
    company_slug: str, data: list[dict[str, Any]]
) -> None:
    """Cache stale action cards."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_set(redis, cms_stale_key(company_slug), data, ttl=CMS_STALE_TTL)


# ── Synced posts cache ───────────────────────────────────────────────

def get_cached_synced_posts(
    company_slug: str,
    stale_only: bool,
    limit: int,
    offset: int,
) -> Optional[list[dict[str, Any]]]:
    """Return cached synced posts list or None on miss."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return None
    return cache_get(
        redis, cms_posts_key(company_slug, stale_only, limit, offset)
    )


def set_cached_synced_posts(
    company_slug: str,
    stale_only: bool,
    limit: int,
    offset: int,
    data: list[dict[str, Any]],
) -> None:
    """Cache serialized synced posts list."""
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_set(
        redis,
        cms_posts_key(company_slug, stale_only, limit, offset),
        data,
        ttl=CMS_POSTS_TTL,
    )


# ── Bulk invalidation ────────────────────────────────────────────────

def invalidate_all_cms_caches(company_slug: str) -> None:
    """Delete all CMS cache keys for a company.

    Called after sync completes, queue_stale_for_refresh, etc.
    """
    redis = get_sync_redis_or_none()
    if redis is None:
        return
    cache_delete_pattern(redis, f"cache:cms:{company_slug}:*")
