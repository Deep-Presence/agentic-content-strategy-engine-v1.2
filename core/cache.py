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


def cache_delete_pattern(redis_sync, pattern: str, *, _batch_size: int = 500) -> int:
    """Delete all keys matching a pattern. Returns count deleted.

    Uses SCAN instead of KEYS to avoid blocking the Redis server.
    """
    try:
        deleted = 0
        batch: list[str] = []
        for key in redis_sync.scan_iter(match=pattern, count=_batch_size):
            batch.append(key)
            if len(batch) >= _batch_size:
                deleted += redis_sync.delete(*batch)
                batch = []
        if batch:
            deleted += redis_sync.delete(*batch)
        return deleted
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
