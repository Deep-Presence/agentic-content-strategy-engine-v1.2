"""Shared checkpointer factory for LangGraph HITL sub-graphs.

Returns RedisSaver when Redis is configured. Raises RuntimeError otherwise.
Replaces duplicated _resolve_checkpointer() functions across graph modules.

Config: REDIS_CHECKPOINTER=true + REDIS_URL -> RedisSaver singleton.
Override: passing an explicit BaseCheckpointSaver bypasses the factory.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver

from core.config.settings import settings

logger = logging.getLogger(__name__)

_redis_saver: Optional[BaseCheckpointSaver] = None
_init_attempted: bool = False
_init_lock = threading.Lock()


def _import_redis_saver() -> BaseCheckpointSaver:
    """Import and construct a RedisSaver. Separated for testability."""
    from langgraph.checkpoint.redis import RedisSaver

    saver = RedisSaver(
        redis_url=settings.redis_url,
        connection_args={
            "socket_timeout": settings.redis_socket_timeout,
            "socket_connect_timeout": settings.redis_socket_connect_timeout,
        },
    )
    saver.setup()
    return saver


def _init_redis_saver() -> Optional[BaseCheckpointSaver]:
    """Lazily create a RedisSaver singleton. Thread-safe via _init_lock.

    Transient failures do NOT set _init_attempted — the next call retries.
    Only permanent decisions (no redis_url configured, successful init) set
    the flag to prevent repeated attempts.
    """
    global _redis_saver, _init_attempted
    if _init_attempted:
        return _redis_saver
    with _init_lock:
        # Double-checked locking — re-test after acquiring lock
        if _init_attempted:
            return _redis_saver
        try:
            if not settings.redis_url:
                _init_attempted = True  # Permanent: no URL is config, not transient
                return None
            _redis_saver = _import_redis_saver()
            _init_attempted = True  # Set AFTER success only
            logger.info("LangGraph RedisSaver initialized")
            return _redis_saver
        except Exception:
            # Do NOT set _init_attempted — allow retry on next call
            logger.warning(
                "Failed to initialize RedisSaver — will retry on next call",
                exc_info=True,
            )
            return None


def get_checkpointer(override: Any = None) -> BaseCheckpointSaver:
    """Return a LangGraph checkpointer.

    Args:
        override: If a valid BaseCheckpointSaver, return it directly.

    Returns:
        BaseCheckpointSaver -- RedisSaver (required).

    Priority:
    1. Explicit override (if it's a valid BaseCheckpointSaver)
    2. RedisSaver (REDIS_URL + REDIS_CHECKPOINTER=true required)

    Raises RuntimeError if Redis is not configured.
    """
    if isinstance(override, BaseCheckpointSaver):
        return override

    if settings.redis_checkpointer and settings.redis_url:
        redis_saver = _init_redis_saver()
        if redis_saver is not None:
            return redis_saver

    raise RuntimeError(
        "REDIS_URL and REDIS_CHECKPOINTER=true are required for LangGraph checkpointing. "
        "Set them in your environment or .env file."
    )


def reset_checkpointer() -> None:
    """Reset cached RedisSaver. For testing."""
    global _redis_saver, _init_attempted
    _redis_saver = None
    _init_attempted = False
