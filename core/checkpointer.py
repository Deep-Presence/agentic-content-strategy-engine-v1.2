"""Shared checkpointer factory for LangGraph HITL sub-graphs.

Returns RedisSaver when Redis is configured, MemorySaver otherwise.
Replaces duplicated _resolve_checkpointer() functions across graph modules.

Config: REDIS_CHECKPOINTER=true + REDIS_URL -> RedisSaver singleton.
Fallback: MemorySaver (in-process only).
Override: passing an explicit BaseCheckpointSaver bypasses the factory.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from core.config.settings import settings

logger = logging.getLogger(__name__)

_redis_saver: Optional[BaseCheckpointSaver] = None
_init_attempted: bool = False
_init_lock = threading.Lock()


def _import_redis_saver() -> BaseCheckpointSaver:
    """Import and construct a RedisSaver. Separated for testability."""
    from langgraph.checkpoint.redis import RedisSaver

    saver = RedisSaver(redis_url=settings.redis_url)
    saver.setup()
    return saver


def _init_redis_saver() -> Optional[BaseCheckpointSaver]:
    """Lazily create a RedisSaver singleton. Thread-safe via _init_lock."""
    global _redis_saver, _init_attempted
    if _init_attempted:
        return _redis_saver
    with _init_lock:
        # Double-checked locking — re-test after acquiring lock
        if _init_attempted:
            return _redis_saver
        _init_attempted = True
        try:
            if not settings.redis_url:
                return None
            _redis_saver = _import_redis_saver()
            logger.info("LangGraph RedisSaver initialized")
            return _redis_saver
        except Exception:
            logger.warning(
                "Failed to initialize RedisSaver — falling back to MemorySaver",
                exc_info=True,
            )
            return None


def get_checkpointer(override: Any = None) -> BaseCheckpointSaver:
    """Return a LangGraph checkpointer.

    Args:
        override: If a valid BaseCheckpointSaver, return it directly.

    Returns:
        BaseCheckpointSaver -- RedisSaver if configured, else MemorySaver.

    Priority:
    1. Explicit override (if it's a valid BaseCheckpointSaver)
    2. RedisSaver (if REDIS_URL is set and redis_checkpointer is True)
    3. MemorySaver (fallback)

    This replaces the six _resolve_checkpointer() functions.
    """
    if isinstance(override, BaseCheckpointSaver):
        return override

    if settings.redis_checkpointer and settings.redis_url:
        redis_saver = _init_redis_saver()
        if redis_saver is not None:
            return redis_saver

    return MemorySaver()


def reset_checkpointer() -> None:
    """Reset cached RedisSaver. For testing."""
    global _redis_saver, _init_attempted
    _redis_saver = None
    _init_attempted = False
