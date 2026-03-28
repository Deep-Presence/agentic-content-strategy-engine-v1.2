"""Lazy Redis clients -- async and sync singletons.

Clients are created on first call (not at import time) to avoid
breaking CLI scripts and tests that don't set REDIS_URL.

Async client: ``get_redis()`` — for EventBus, stream reads, pipeline state.
Sync client: ``get_sync_redis()`` — for distributed locks, sync readers
(sub-millisecond blocking operations where async bridging is unnecessary).

Follows the same pattern as core/db/engine.py for PostgreSQL.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional
from urllib.parse import urlparse, urlunparse

import redis as _sync_redis
import redis.asyncio as aioredis

from core.config.settings import settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_pool: Optional[aioredis.ConnectionPool] = None
_client: Optional[aioredis.Redis] = None

# Sync client (for locks, sync state reads)
_sync_lock = threading.RLock()
_sync_client: Optional[_sync_redis.Redis] = None


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

    Catches all exceptions from client creation (RuntimeError, ValueError,
    ConnectionError, TimeoutError, etc.) so callers always get None rather
    than an unexpected crash when Redis is misconfigured or unreachable.
    """
    if not settings.redis_url:
        return None
    try:
        return get_redis()
    except Exception as exc:
        logger.debug("Redis async client unavailable: %s", exc)
        return None


def get_sync_redis() -> _sync_redis.Redis:
    """Return the shared sync Redis client (created lazily, thread-safe).

    Used for sub-millisecond blocking operations (distributed locks,
    sync pipeline state reads). Raises RuntimeError if REDIS_URL not set.
    """
    global _sync_client
    if _sync_client is not None:
        return _sync_client
    with _sync_lock:
        if _sync_client is not None:
            return _sync_client
        if not settings.redis_url:
            raise RuntimeError(
                "REDIS_URL is not set. "
                "Set it in .env.local or as an environment variable."
            )
        _sync_client = _sync_redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
        )
        logger.info("Sync Redis client initialized: %s", _redact_url(settings.redis_url))
    return _sync_client


def get_sync_redis_or_none() -> Optional[_sync_redis.Redis]:
    """Return the sync Redis client if REDIS_URL is configured, else None.

    Catches all exceptions from client creation so callers always get None
    rather than an unexpected crash when Redis is misconfigured or unreachable.
    """
    if not settings.redis_url:
        return None
    try:
        return get_sync_redis()
    except Exception as exc:
        logger.debug("Redis sync client unavailable: %s", exc)
        return None


async def close_redis() -> None:
    """Close all Redis clients. Call during app shutdown.

    Each close is isolated so one failure does not leak the others' sockets.
    Sync client is closed via asyncio.to_thread() to avoid blocking the loop.
    """
    import asyncio as _asyncio

    global _pool, _client, _sync_client

    # Snapshot and clear globals first (prevents new callers)
    with _lock:
        client = _client
        pool = _pool
        _client = None
        _pool = None
    with _sync_lock:
        sync = _sync_client
        _sync_client = None

    errors: list[Exception] = []

    if client is not None:
        try:
            await client.aclose()
        except Exception as exc:
            errors.append(exc)

    if pool is not None:
        try:
            await pool.aclose()
        except Exception as exc:
            errors.append(exc)

    if sync is not None:
        try:
            await _asyncio.to_thread(sync.close)
        except Exception as exc:
            errors.append(exc)

    if errors:
        logger.warning(
            "Errors during Redis shutdown (%d): %s",
            len(errors),
            "; ".join(str(e) for e in errors),
        )
    logger.info("Redis connection pool closed")


async def redis_ping() -> bool:
    """Health check -- returns True if Redis responds to PING."""
    try:
        client = get_redis()
        return await client.ping()
    except Exception:
        return False
