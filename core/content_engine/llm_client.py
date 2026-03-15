"""Unified LLM client via LiteLLM for the v1.3 content pipeline.

All LLM calls in the v1.3 pipeline route through this module, providing:
  - Model abstraction (Anthropic, OpenAI, Perplexity, Google via one interface)
  - Retry logic with jittered exponential backoff
  - Token budget enforcement
  - Automatic tracing via LangSmith callbacks (when configured)

The module replaces direct SDK calls (anthropic.AsyncAnthropic, httpx to
Perplexity, etc.) with a single ``llm_call()`` function. The v1.0 pipeline
continues using raw SDKs — this module is for v1.3 only.

Model strings use LiteLLM's provider-prefixed format:
  - "anthropic/claude-sonnet-4-5-20250929"
  - "anthropic/claude-haiku-4-5-20251001"
  - "perplexity/sonar-pro"
  - "openai/gpt-5.2-2025-12-11"
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from core.models.content_generation_v13 import LLMResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LiteLLM import (lazy — allows tests to mock without installing)
# ---------------------------------------------------------------------------

_litellm_available = False
try:
    import litellm

    _litellm_available = True
except ImportError:
    litellm = None  # type: ignore[assignment]
    logger.debug("litellm not installed — llm_call will raise if invoked")


# ---------------------------------------------------------------------------
# LangSmith callback integration
# ---------------------------------------------------------------------------


def _get_langsmith_callback() -> Optional[Any]:
    """Return a LangSmith callback handler if configured, else None.

    LangSmith integration is automatic when LANGSMITH_API_KEY is set.
    LiteLLM picks up the callback and logs every call.
    """
    try:
        from langsmith import Client  # noqa: F401

        # LiteLLM auto-detects LangSmith when the env var is set
        # and includes it in success/failure callbacks
        return None  # LiteLLM handles this via litellm.success_callback
    except ImportError:
        return None


def configure_litellm_callbacks() -> None:
    """Configure LiteLLM: export API keys to os.environ + set LangSmith callbacks.

    LiteLLM reads API keys from os.environ, but pydantic-settings loads them
    into the Settings object without setting os.environ.  This bridge ensures
    litellm can authenticate with every provider.

    Should be called once at pipeline startup.
    """
    if not _litellm_available:
        return

    import os

    from core.config.settings import settings

    # Bridge pydantic-settings → os.environ for LiteLLM
    _KEY_MAP = {
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "OPENAI_API_KEY": settings.openai_api_key,
        "PERPLEXITY_API_KEY": settings.perplexity_api_key,
    }
    for env_var, value in _KEY_MAP.items():
        if value and not os.environ.get(env_var):
            os.environ[env_var] = value

    try:
        if os.environ.get("LANGSMITH_API_KEY"):
            litellm.success_callback = ["langsmith"]  # type: ignore[union-attr]
            litellm.failure_callback = ["langsmith"]  # type: ignore[union-attr]
            logger.info("LiteLLM LangSmith callbacks configured")
        else:
            logger.debug("LANGSMITH_API_KEY not set — LangSmith callbacks skipped")
    except Exception as exc:
        logger.warning("Failed to configure LiteLLM callbacks: %s", exc)


# ---------------------------------------------------------------------------
# Main LLM call function
# ---------------------------------------------------------------------------


def _ensure_litellm_model(model: str) -> str:
    """Ensure a model string has a LiteLLM provider prefix.

    LiteLLM requires provider-prefixed model strings for routing.
    Auto-detects and prefixes known model families so callers can pass
    either ``"claude-sonnet-4-5-20250929"`` or ``"anthropic/claude-sonnet-4-5-20250929"``.

    Args:
        model: Raw model string (may or may not have a provider prefix).

    Returns:
        Provider-prefixed model string suitable for LiteLLM.
    """
    if "/" in model:
        return model  # Already prefixed
    if model.startswith("claude-"):
        return f"anthropic/{model}"
    if model.startswith("sonar"):
        return f"perplexity/{model}"
    if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        return f"openai/{model}"
    if model.startswith("gemini-"):
        return f"google/{model}"
    return model  # Unknown — let LiteLLM route it


async def llm_call(
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    response_format: Optional[Type[BaseModel]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> LLMResponse:
    """Make a unified LLM call through LiteLLM with retry and tracing.

    Args:
        model: LiteLLM model string (e.g. "anthropic/claude-sonnet-4-5-20250929").
        system: System prompt.
        user: User prompt.
        max_tokens: Maximum output tokens.
        temperature: Sampling temperature.
        response_format: Optional Pydantic model for structured output.
        metadata: Optional metadata dict passed to LiteLLM (appears in traces).
        max_retries: Maximum retry attempts on transient failures.
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        LLMResponse with content, model, token counts, and finish reason.

    Raises:
        RuntimeError: If litellm is not installed.
        Exception: If all retries exhausted.
    """
    if not _litellm_available:
        raise RuntimeError(
            "litellm is not installed. Install it with: pip install litellm"
        )

    model = _ensure_litellm_model(model)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if metadata:
        kwargs["metadata"] = metadata

    if response_format:
        kwargs["response_format"] = response_format

    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(**kwargs)  # type: ignore[union-attr]

            # Extract response fields
            choice = response.choices[0]  # type: ignore[index]
            usage = response.usage  # type: ignore[union-attr]

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model or model,  # type: ignore[union-attr]
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                finish_reason=choice.finish_reason or "",
            )

        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, base_delay)
                logger.warning(
                    "LLM call failed (attempt %d/%d, model=%s): %s. "
                    "Retrying in %.1fs",
                    attempt + 1,
                    max_retries,
                    model,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "LLM call failed after %d attempts (model=%s): %s",
                    max_retries,
                    model,
                    exc,
                )

    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Embedding helper (pass-through to existing shared tools)
# ---------------------------------------------------------------------------


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts using the existing async embedding client.

    This is a pass-through to the existing shared_tools embedding client,
    keeping all embedding calls consistent across v1.0 and v1.3.
    """
    from core.shared_tools.async_embedding_client import async_embed_texts

    return await async_embed_texts(texts)
