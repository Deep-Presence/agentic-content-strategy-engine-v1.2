"""Shared OpenRouter client factory (AsyncOpenAI + OpenAI pointed at OpenRouter).

Provides singleton async and sync clients for all OpenRouter-routed LLM calls.
Uses the existing ``openai`` SDK — no new dependency.

Usage::

    from core.shared_tools.openrouter_client import get_async_client, get_sync_client

    client = get_async_client()
    response = await client.chat.completions.create(model="anthropic/claude-sonnet-4-6", ...)

    sync_client = get_sync_client()
    response = sync_client.chat.completions.create(model="perplexity/sonar-deep-research", ...)
"""
from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger(__name__)

_async_client: Optional[AsyncOpenAI] = None
_sync_client: Optional[OpenAI] = None


def _get_settings():
    """Lazy import to avoid circular dependency at module load."""
    from core.config.settings import settings
    return settings


def get_async_client() -> AsyncOpenAI:
    """Return a cached async OpenAI client pointed at OpenRouter.

    Raises:
        RuntimeError: If ``OPENROUTER_API_KEY`` is not set.
    """
    global _async_client
    if _async_client is None:
        settings = _get_settings()
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Get your key at https://openrouter.ai/settings/keys"
            )
        _async_client = AsyncOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            max_retries=0,  # Wrappers manage their own retry logic
        )
    return _async_client


def get_sync_client(timeout_s: float = 300.0) -> OpenAI:
    """Return a cached sync OpenAI client pointed at OpenRouter.

    Args:
        timeout_s: HTTP-level timeout in seconds (default 300s for deep research).

    Raises:
        RuntimeError: If ``OPENROUTER_API_KEY`` is not set.
    """
    global _sync_client
    if _sync_client is None:
        settings = _get_settings()
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Get your key at https://openrouter.ai/settings/keys"
            )
        _sync_client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=timeout_s,
            max_retries=0,  # Wrappers manage their own retry logic
        )
    return _sync_client


def reset_clients() -> None:
    """Reset cached clients. For test teardown only."""
    global _async_client, _sync_client
    _async_client = None
    _sync_client = None
