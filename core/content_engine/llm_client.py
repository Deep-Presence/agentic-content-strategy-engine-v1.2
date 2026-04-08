"""Unified LLM client via OpenRouter for the v1.3 content pipeline.

All LLM calls in the v1.3 pipeline route through this module, providing:
  - Model abstraction (Anthropic, OpenAI, Perplexity, Google via one interface)
  - Retry logic with jittered exponential backoff
  - Token budget enforcement
  - Tracing via per-caller log_generation() calls (LangSmith)

The module uses the ``openai`` SDK pointed at OpenRouter's base URL.
Model strings use provider-prefixed format:
  - "anthropic/claude-sonnet-4-6"
  - "anthropic/claude-haiku-4-5"
  - "perplexity/sonar-pro"
  - "openai/gpt-5.2-2025-12-11"
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional

from core.models.content_generation_v13 import LLMResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model prefix helper (canonical implementation in openrouter_client)
# ---------------------------------------------------------------------------

from core.shared_tools.openrouter_client import _ensure_model_prefix  # noqa: E402
from core.shared_tools.cost_tracker import track_llm_cost  # noqa: E402

# Backward-compatible alias
_ensure_litellm_model = _ensure_model_prefix


# ---------------------------------------------------------------------------
# OpenRouter configuration
# ---------------------------------------------------------------------------


def configure_openrouter() -> None:
    """Validate OpenRouter API key and pre-warm the client.

    Should be called once at pipeline startup.
    """
    from core.shared_tools.openrouter_client import get_async_client

    try:
        get_async_client()
        logger.info("OpenRouter client configured")
    except RuntimeError as exc:
        logger.warning("OpenRouter not configured: %s", exc)


# Backward-compatible alias for existing call sites
configure_litellm_callbacks = configure_openrouter


# ---------------------------------------------------------------------------
# Main LLM call function
# ---------------------------------------------------------------------------


async def llm_call(
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    response_format: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> LLMResponse:
    """Make a unified LLM call through OpenRouter with retry and tracing.

    Args:
        model: Provider-prefixed model string (e.g. "anthropic/claude-sonnet-4-6").
        system: System prompt.
        user: User prompt.
        max_tokens: Maximum output tokens.
        temperature: Sampling temperature.
        response_format: Optional dict (e.g. {"type": "json_object"}) passed
            through as-is. None → no structured output constraint.
        metadata: Optional metadata dict (passed via extra_body for tracing).
        max_retries: Maximum retry attempts on transient failures.
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        LLMResponse with content, model, token counts, and finish reason.

    Raises:
        RuntimeError: If OpenRouter API key is not configured.
        Exception: If all retries exhausted.
    """
    from core.shared_tools.openrouter_client import get_async_client

    model = _ensure_model_prefix(model)
    client = get_async_client()

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

    extra_body: Dict[str, Any] = {}
    if metadata:
        extra_body["metadata"] = metadata
    if extra_body:
        kwargs["extra_body"] = extra_body

    if response_format is not None:
        kwargs["response_format"] = response_format

    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(**kwargs)

            # Extract response fields
            choice = response.choices[0]
            usage = response.usage

            # Cost tracking (never raises)
            _meta = metadata or {}
            track_llm_cost(
                model=response.model or model,
                provider="openrouter",
                pipeline=_meta.get("pipeline", ""),
                pipeline_step=_meta.get("pipeline_step", ""),
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                company_slug=_meta.get("company_slug", ""),
                call_site="core.content_engine.llm_client",
                source="openrouter",
            )

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model or model,
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
