"""Shared checkpointer factory for LangGraph HITL sub-graphs.

Replaces duplicated _resolve_checkpointer() across graph modules.

Config: REDIS_CHECKPOINTER=true + REDIS_URL → RedisSaver singleton.
Fallback: MemorySaver (in-process only).
Override: passing an explicit BaseCheckpointSaver bypasses the factory.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_singleton: Optional[BaseCheckpointSaver] = None


def get_checkpointer(override: Optional[Any] = None) -> BaseCheckpointSaver:
    """Return a checkpointer instance.

    Args:
        override: If a valid BaseCheckpointSaver, return it directly.

    Returns:
        BaseCheckpointSaver — RedisSaver if configured, else MemorySaver.
    """
    if isinstance(override, BaseCheckpointSaver):
        return override

    global _singleton
    if _singleton is not None:
        return _singleton

    from core.config.settings import settings

    if getattr(settings, "redis_checkpointer", False) and settings.redis_url:
        try:
            from langgraph.checkpoint.redis import RedisSaver

            _singleton = RedisSaver(url=str(settings.redis_url))
            logger.info("Using RedisSaver checkpointer")
            return _singleton
        except Exception as exc:
            logger.warning(
                "RedisSaver init failed, falling back to MemorySaver: %s", exc
            )

    _singleton = MemorySaver()
    return _singleton
