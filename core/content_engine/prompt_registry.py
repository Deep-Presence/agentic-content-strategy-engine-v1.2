"""LangSmith Hub prompt registry — pull prompts at runtime with local fallback.

Thread-safe, TTL-cached prompt fetching from LangSmith Hub.
When Hub is unavailable or disabled, local fallback prompts are used.

Usage in prompt files:
    from core.content_engine.prompt_registry import get_prompt

    _HUB_NAME = "outliner-system"

    def get_outliner_system_prompt() -> str:
        return get_prompt(_HUB_NAME, OUTLINER_SYSTEM_PROMPT)

Configuration:
    - LANGSMITH_API_KEY must be set for Hub pulls
    - settings.langsmith_use_hub = True to enable (default: False)
    - settings.langsmith_hub_tag = "production" for version pinning
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from core.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Process-global cache
# ---------------------------------------------------------------------------

_CACHE: Dict[str, tuple[str, float]] = {}  # key → (text, fetched_at)
_CACHE_TTL = 300  # 5 minutes
_LOCK = threading.Lock()


def _extract_text_from_manifest(manifest: Dict[str, Any]) -> Optional[str]:
    """Defensively extract prompt text from a LangSmith PromptCommit manifest.

    Three extraction paths:
        1. Direct content in first message kwargs
        2. Nested prompt template in first message kwargs
        3. Top-level template in first message kwargs
    """
    messages = manifest.get("messages", [])
    if not messages:
        return None

    first = messages[0]
    kwargs = first.get("kwargs", {})

    # Path 1: direct content
    if "content" in kwargs:
        return kwargs["content"]

    # Path 2: nested prompt template
    prompt = kwargs.get("prompt", {})
    if isinstance(prompt, dict):
        template = prompt.get("kwargs", {}).get("template")
        if template:
            return template

    # Path 3: top-level template
    return kwargs.get("template")


def _pull_from_hub(hub_name: str, tag: str = "") -> Optional[str]:
    """Pull a prompt from LangSmith Hub. Returns text or None on failure."""
    try:
        from langsmith import Client

        client_kwargs: Dict[str, Any] = {"api_key": settings.langsmith_api_key}
        if settings.langsmith_workspace_id:
            client_kwargs["workspace_id"] = settings.langsmith_workspace_id
        client = Client(**client_kwargs)
        # Version pinning via identifier string: "name:tag"
        identifier = f"{hub_name}:{tag}" if tag else hub_name
        commit = client.pull_prompt_commit(identifier)
        if commit and hasattr(commit, "manifest") and commit.manifest:
            return _extract_text_from_manifest(commit.manifest)

        logger.warning("Hub prompt '%s' returned no manifest", hub_name)
        return None
    except Exception as exc:
        logger.debug("Failed to pull prompt '%s' from Hub: %s", hub_name, exc)
        return None


def get_prompt(hub_name: str, local_fallback: str, tag: str = "") -> str:
    """Get a prompt from Hub with local fallback. Thread-safe, TTL-cached.

    Args:
        hub_name: LangSmith Hub prompt name (e.g., "outliner-system").
        local_fallback: Local prompt string to use when Hub is unavailable.
        tag: Optional version tag for Hub (e.g., "production").

    Returns:
        Prompt text string — always returns a valid string, never raises.
    """
    # Hub disabled — return local immediately
    if not settings.langsmith_use_hub:
        return local_fallback

    cache_key = f"{hub_name}:{tag or settings.langsmith_hub_tag}"

    # Check cache first (outside lock for fast path)
    cached = _CACHE.get(cache_key)
    if cached:
        text, fetched_at = cached
        if time.time() - fetched_at < _CACHE_TTL:
            return text

    # Cache miss or expired — pull from Hub under lock
    with _LOCK:
        # Double-check after acquiring lock (another thread may have populated)
        cached = _CACHE.get(cache_key)
        if cached:
            text, fetched_at = cached
            if time.time() - fetched_at < _CACHE_TTL:
                return text

        effective_tag = tag or settings.langsmith_hub_tag
        pulled = _pull_from_hub(hub_name, effective_tag)
        if pulled:
            _CACHE[cache_key] = (pulled, time.time())
            return pulled

        # Hub failed — use local fallback, don't cache the failure
        logger.info("Using local fallback for prompt '%s'", hub_name)
        return local_fallback


async def aget_prompt(hub_name: str, local_fallback: str, tag: str = "") -> str:
    """Async wrapper for get_prompt — runs Hub pull in thread pool."""
    import asyncio

    return await asyncio.to_thread(get_prompt, hub_name, local_fallback, tag)


def clear_cache() -> None:
    """Clear the prompt cache. Useful for testing."""
    with _LOCK:
        _CACHE.clear()
