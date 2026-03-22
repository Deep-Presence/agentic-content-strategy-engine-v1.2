"""Redis-backed API response cache.

Replaces the five module-level _CACHE dicts with a shared Redis cache.
Each cached item gets a namespaced key and a TTL. Pipelines invalidate
by deleting keys matching a prefix pattern.

All operations are synchronous (sub-ms Redis calls) because the callers
are sync functions running in asyncio.to_thread().
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes


def cache_get(redis_sync, key: str) -> Optional[Any]:  # type: ignore[type-arg]
    """Read a cached JSON value. Returns None on miss or error."""
    try:
        raw = redis_sync.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.debug("Cache miss (error) for %s", key, exc_info=True)
        return None


def cache_set(redis_sync, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Write a JSON value to cache with TTL. Fire-and-forget on error."""
    try:
        redis_sync.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        logger.debug("Cache write failed for %s", key, exc_info=True)


def cache_delete_pattern(redis_sync, pattern: str) -> int:
    """Delete all keys matching a pattern. Returns count deleted."""
    try:
        keys = redis_sync.keys(pattern)
        if keys:
            return redis_sync.delete(*keys)
        return 0
    except Exception:
        logger.debug("Cache pattern delete failed for %s", pattern, exc_info=True)
        return 0


def cache_delete(redis_sync, *keys: str) -> None:
    """Delete specific cache keys."""
    try:
        if keys:
            redis_sync.delete(*keys)
    except Exception:
        logger.debug("Cache delete failed", exc_info=True)
