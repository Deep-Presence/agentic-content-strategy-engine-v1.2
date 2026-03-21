"""Lazy async Redis client -- singleton connection pool.

The client is created on first call to ``get_redis()``, not at import time.
This avoids breaking CLI scripts and tests that don't set REDIS_URL.

Follows the same pattern as core/db/engine.py for PostgreSQL.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional
from urllib.parse import urlparse, urlunparse

import redis.asyncio as aioredis

from core.config.settings import settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_pool: Optional[aioredis.ConnectionPool] = None
_client: Optional[aioredis.Redis] = None


def _redact_url(url: str) -> str:
    """Redact password from a Redis URL for safe logging."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            replaced = parsed._replace(
                netloc=f"{parsed.username or ''}:***@{parsed.hostname}"
                + (f":{parsed.port}" if parsed.port else "")
            )
            return urlunparse(replaced)
        return url
    except Exception:
        return "redis://***"


def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client (created lazily, thread-safe).

    Raises RuntimeError if REDIS_URL is not set.
    """
    global _pool, _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        if not settings.redis_url:
            raise RuntimeError(
                "REDIS_URL is not set. "
                "Set it in .env.local or as an environment variable."
            )
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            retry_on_timeout=settings.redis_retry_on_timeout,
            health_check_interval=settings.redis_health_check_interval,
            decode_responses=True,  # Return str instead of bytes
        )
        _client = aioredis.Redis(connection_pool=_pool)
        logger.info("Redis client initialized: %s", _redact_url(settings.redis_url))
    return _client


def get_redis_or_none() -> Optional[aioredis.Redis]:
    """Return the Redis client if REDIS_URL is configured, else None.

    Used by code that should degrade gracefully without Redis
    (e.g., local development, CLI scripts).
    """
    if not settings.redis_url:
        return None
    try:
        return get_redis()
    except RuntimeError:
        return None


async def close_redis() -> None:
    """Close the connection pool. Call during app shutdown."""
    global _pool, _client
    with _lock:
        client = _client
        pool = _pool
        _client = None
        _pool = None
    if client is not None:
        await client.aclose()
    if pool is not None:
        await pool.aclose()
    logger.info("Redis connection pool closed")


async def redis_ping() -> bool:
    """Health check -- returns True if Redis responds to PING."""
    try:
        client = get_redis()
        return await client.ping()
    except Exception:
        return False
