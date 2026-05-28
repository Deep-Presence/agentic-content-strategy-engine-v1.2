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
from typing import Any, Optional

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


# ---------------------------------------------------------------------------
# Model prefix helper
# ---------------------------------------------------------------------------


def _ensure_model_prefix(model: str) -> str:
    """Ensure a model string has a provider prefix for OpenRouter routing.

    OpenRouter requires provider-prefixed model strings for routing.
    Auto-detects and prefixes known model families so callers can pass
    either ``"claude-sonnet-4-6"`` or ``"anthropic/claude-sonnet-4-6"``.

    Args:
        model: Raw model string (may or may not have a provider prefix).

    Returns:
        Provider-prefixed model string suitable for OpenRouter.
    """
    if "/" in model:
        return model  # Already prefixed — e.g. "anthropic/claude-opus-4-6"
    if model.startswith("claude-"):
        return f"anthropic/{model}"
    if model.startswith("sonar"):
        return f"perplexity/{model}"
    if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3") or model.startswith("text-embedding-"):
        return f"openai/{model}"
    if model.startswith("gemini-"):
        return f"google/{model}"
    return model  # Unknown — let OpenRouter route it


def build_chat_openai_via_openrouter(model: str, **kwargs: Any) -> Any:
    """Build a LangChain ``ChatOpenAI`` instance pointed at OpenRouter.

    Handles three model string formats:
    - ``"anthropic/claude-opus-4-6"`` — already prefixed (pass-through)
    - ``"claude-opus-4-6"`` — bare name (auto-prefixed)
    - ``"anthropic:claude-opus-4-6"`` — colon format (legacy KB synthesis)

    Args:
        model: Provider-prefixed, bare, or colon-separated model string.
        **kwargs: Extra kwargs forwarded to ``ChatOpenAI`` (e.g. ``temperature``).

    Returns:
        ``ChatOpenAI`` instance configured for OpenRouter routing.

    Raises:
        RuntimeError: If ``OPENROUTER_API_KEY`` is not set.
    """
    from langchain_openai import ChatOpenAI

    settings = _get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Get your key at https://openrouter.ai/settings/keys"
        )
    # Handle legacy "provider:model" format (KB synthesis)
    bare = model.split(":", 1)[-1] if ":" in model else model
    prefixed = _ensure_model_prefix(bare)
    return ChatOpenAI(
        model=prefixed,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        **kwargs,
    )
