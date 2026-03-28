# Session 0: Redis Infrastructure Foundation

## Objective

Wire Redis into the application as a first-class infrastructure service — connection pool, configuration, health check, dependency injection, and a thin client wrapper. **No feature changes.** After this session, every subsequent Redis service session can import from `core.redis` and get a working async Redis client without touching infrastructure.

---

## 1. Dependencies

### Add to `requirements.txt` (or `pyproject.toml`):

```
redis[hiredis]>=5.0.0
```

`hiredis` is the C parser that makes Redis 2-5x faster on large payloads. The `redis[hiredis]` extra installs both. The `redis` package includes `redis.asyncio` — no separate `aioredis` needed (that project was merged into `redis-py` in v4.2+).

### Future sessions will add (do NOT add now):
- `langgraph-checkpoint-redis` — Session 2 (HITL RedisSaver)

---

## 2. Configuration

### File: `core/config/settings.py`

Add a Redis settings block alongside the existing Database block:

```python
# --- Redis ---
redis_url: str | None = None  # redis://localhost:6379/0
redis_max_connections: int = 20
redis_socket_timeout: float = 5.0
redis_socket_connect_timeout: float = 2.0
redis_retry_on_timeout: bool = True
redis_health_check_interval: int = 30  # seconds
```

**Why these specific settings:**

- `redis_url`: Standard Redis URL format. Railway, Render, Upstash all provide `REDIS_URL` env var in this format. `None` means Redis is not configured (graceful degradation for local dev).
- `redis_max_connections`: Connection pool ceiling. 20 is appropriate for the current scale — each Uvicorn worker gets its own pool, and most operations are sub-millisecond. Increase if you scale to many concurrent pipelines.
- `redis_socket_timeout`: Read/write timeout. 5s is generous — Redis operations are typically <1ms. This catches network partitions without timing out legitimate `BRPOP` operations (those use their own timeout parameter).
- `redis_socket_connect_timeout`: Initial TCP connection timeout. 2s catches DNS/routing issues at startup.
- `redis_retry_on_timeout`: Auto-retry on timeout. Important for transient network issues on Railway's internal network.
- `redis_health_check_interval`: The `redis-py` pool pings idle connections at this interval to detect dead sockets before they're used. 30s is the default and appropriate.

**Placement:** Put the block directly after the `# --- Database (PostgreSQL) ---` block. The settings class picks up `REDIS_URL` from the environment automatically via pydantic-settings (the field name `redis_url` maps to env var `REDIS_URL`).

---

## 3. Redis Client Module

### New file: `core/redis.py`

This is the equivalent of `core/db/engine.py` for Redis. Lazy initialization, thread-safe, singleton connection pool.

```python
"""Lazy async Redis client — singleton connection pool.

The client is created on first call to ``get_redis()``, not at import time.
This avoids breaking CLI scripts and tests that don't set REDIS_URL.

Follows the same pattern as core/db/engine.py for PostgreSQL.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

import redis.asyncio as aioredis

from core.config.settings import settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_pool: Optional[aioredis.ConnectionPool] = None
_client: Optional[aioredis.Redis] = None


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
        logger.info("Redis client initialized: %s", settings.redis_url)
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
    """Health check — returns True if Redis responds to PING."""
    try:
        client = get_redis()
        return await client.ping()
    except Exception:
        return False
```

**Key design decisions:**

- `decode_responses=True` — all Redis values come back as Python `str`, not `bytes`. Every downstream service (EventBus, pipeline state, caching) works with strings. This avoids `.decode()` calls everywhere.
- `get_redis_or_none()` — graceful degradation path. Used by services that can fall back to in-memory behavior when Redis is absent (local dev). This mirrors how `database_url` being `None` causes a fallback to JSON services today.
- `close_redis()` — explicit shutdown. Called in the app lifespan's teardown phase.
- `redis_ping()` — simple health check, used by the `/health` endpoint.

---

## 4. App Lifespan Integration

### File: `api/app.py`

#### 4a. Add Redis initialization in the `lifespan()` function

After the existing `db_session_factory` initialization block and before the DB health checks, add:

```python
# ── Redis initialization ───────────────────────────────────────────
app.state.redis = None
app.state.redis_healthy = False
try:
    from core.redis import get_redis_or_none, redis_ping

    redis_client = get_redis_or_none()
    if redis_client is not None:
        healthy = await redis_ping()
        if healthy:
            app.state.redis = redis_client
            app.state.redis_healthy = True
            logger.info("Redis health check: connected")
        else:
            logger.warning("Redis health check: PING failed — Redis unavailable")
    else:
        logger.info("Redis health check: skipped (no REDIS_URL)")
except Exception:
    logger.exception("Redis initialization failed — continuing without Redis")
```

#### 4b. Add Redis cleanup in the lifespan teardown

Before `yield`, everything is startup. After `yield`, add cleanup:

```python
yield

# Shutdown
from core.redis import close_redis
await close_redis()
logger.info("API shutting down")
```

#### 4c. Key principle: no hard failure

If `REDIS_URL` is not set, or Redis is unreachable, the app still starts. `app.state.redis` is `None`, and downstream services check for this and degrade gracefully. This matches the current pattern where `DATABASE_URL` being absent causes a fallback to JSON services.

---

## 5. Dependency Injection

### File: `api/dependencies.py`

Add a dependency function alongside the existing `get_event_bus`, `get_task_store`, etc.:

```python
from typing import Optional
import redis.asyncio as aioredis


def get_redis(request: Request) -> Optional[aioredis.Redis]:
    """Return the Redis client from app state, or None if unavailable."""
    return getattr(request.app.state, "redis", None)
```

This is intentionally simple — no session lifecycle management like the DB dependencies. Redis connections are pooled and stateless; there's no commit/rollback to manage. Routers that need Redis just declare `redis: Optional[aioredis.Redis] = Depends(get_redis)`.

---

## 6. Health Endpoint Update

### File: `api/routers/health.py`

Add Redis status to the existing `/health` response:

```python
@router.get("/health")
async def health(request: Request) -> Dict[str, Any]:
    db_healthy = getattr(request.app.state, "db_healthy", False)
    pgvector = getattr(request.app.state, "pgvector_available", False)
    redis_healthy = getattr(request.app.state, "redis_healthy", False)
    return {
        "status": "ok",
        "database": "connected" if db_healthy else "unavailable",
        "pgvector": "available" if pgvector else "unavailable",
        "redis": "connected" if redis_healthy else "unavailable",
    }
```

---

## 7. Environment Variables

### File: `.env.local` (add template entry)

```bash
# Redis (optional — app degrades gracefully without it)
# REDIS_URL=redis://localhost:6379/0
```

### Railway environment

Set `REDIS_URL` in the Railway service variables. Railway's Redis add-on provides this automatically when you add a Redis service to the project.

---

## 8. Tests

### New file: `tests/unit/test_redis_client.py`

```python
"""Unit tests for core.redis module."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.fixture(autouse=True)
def _reset_redis_module():
    """Reset module-level singleton between tests."""
    import core.redis as redis_mod
    redis_mod._client = None
    redis_mod._pool = None
    yield
    redis_mod._client = None
    redis_mod._pool = None


def test_get_redis_raises_without_url():
    """get_redis() raises RuntimeError when REDIS_URL is not set."""
    with patch("core.redis.settings") as mock_settings:
        mock_settings.redis_url = None
        from core.redis import get_redis
        with pytest.raises(RuntimeError, match="REDIS_URL is not set"):
            get_redis()


def test_get_redis_or_none_returns_none_without_url():
    """get_redis_or_none() returns None gracefully."""
    with patch("core.redis.settings") as mock_settings:
        mock_settings.redis_url = None
        from core.redis import get_redis_or_none
        assert get_redis_or_none() is None


@pytest.mark.asyncio
async def test_redis_ping_returns_false_on_failure():
    """redis_ping() returns False when Redis is unreachable."""
    with patch("core.redis.get_redis") as mock_get:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("refused")
        mock_get.return_value = mock_client
        from core.redis import redis_ping
        assert await redis_ping() is False
```

### Update: `tests/integration/` (if you have integration tests that spin up the app)

Any existing integration tests that create a test `FastAPI` app should set `app.state.redis = None` to prevent tests from requiring a live Redis instance.

---

## 9. Documentation

### File: `CLAUDE.md` — add to the infrastructure section:

```markdown
## Redis

- Client module: `core/redis.py` (lazy singleton, same pattern as `core/db/engine.py`)
- Settings: `REDIS_URL`, `REDIS_MAX_CONNECTIONS`, etc. in `core/config/settings.py`
- App state: `app.state.redis` (async Redis client or None)
- Health: `/health` endpoint includes `"redis": "connected" | "unavailable"`
- Dependency: `get_redis(request)` returns `Optional[aioredis.Redis]`
- Graceful degradation: app starts and runs without Redis; services fall back to in-memory/DB behavior
- Connection pool: shared across all async tasks within a single worker process
- `decode_responses=True`: all values returned as `str`, not `bytes`
```

---

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | Edit | Add `redis[hiredis]>=5.0.0` |
| `core/config/settings.py` | Edit | Add Redis settings block (6 fields) |
| `core/redis.py` | **Create** | Lazy singleton client, pool, ping, close |
| `api/app.py` | Edit | Redis init in lifespan startup + close in teardown |
| `api/dependencies.py` | Edit | Add `get_redis()` dependency |
| `api/routers/health.py` | Edit | Add Redis status to `/health` response |
| `.env.local` | Edit | Add `REDIS_URL` template |
| `tests/unit/test_redis_client.py` | **Create** | Unit tests for Redis client module |
| `CLAUDE.md` | Edit | Document Redis infrastructure |

---

## What This Session Does NOT Touch

- `EventBus` — unchanged, stays in-memory (Session 1)
- `TaskStore` / `DbTaskStore` — unchanged (Session 3)
- `MemorySaver` — unchanged (Session 2)
- `pipeline_state.json` — unchanged (Session 3)
- Any `Json*DataService` — unchanged (Session 6)
- No feature flags, no A/B switching between Redis/non-Redis paths yet
- No `langgraph-checkpoint-redis` dependency yet (Session 2)

---

## Validation Checklist

After this session is complete, verify:

1. `pip install -r requirements.txt` succeeds with `redis` package
2. App starts without `REDIS_URL` set — no errors, `"redis": "unavailable"` in `/health`
3. App starts with `REDIS_URL=redis://localhost:6379/0` (local Redis running) — `"redis": "connected"` in `/health`
4. `app.state.redis` is a working `redis.asyncio.Redis` instance when connected
5. `app.state.redis` is `None` when `REDIS_URL` is not set
6. All existing tests pass (no regressions from adding the module)
7. New Redis unit tests pass
8. `python -c "from core.redis import get_redis_or_none; print(get_redis_or_none())"` returns `None` without error when `REDIS_URL` is unset
