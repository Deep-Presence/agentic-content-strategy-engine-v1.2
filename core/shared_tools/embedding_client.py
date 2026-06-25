"""Shared OpenAI embedding client via OpenRouter.

Consolidates the _embed_texts function duplicated across s1, s2, s5.
Routes through OpenRouter for centralized cost tracking.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, List, TypeVar

from openai import APIError, RateLimitError

from core.config.settings import settings
from core.shared_tools.openrouter_client import (
    build_sync_client_for_key,
    get_sync_client,
    _ensure_model_prefix,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _retry_sync(
    fn: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    *,
    retryable_exceptions: tuple = (RateLimitError, APIError),
) -> T:
    """Retry a sync callable with jittered exponential backoff.

    Mirrors the async client's ``_retry_async()`` for consistency.

    Args:
        fn: Callable to retry.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds (doubles each retry + jitter).
        retryable_exceptions: Exception types that trigger a retry.

    Returns:
        Result of the callable.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
                logger.warning(
                    "Retry %d/%d after %s: %.1fs delay",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def embed_texts(
    texts: List[str],
    batch_size: int = 64,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_s: float | None = None,
    pipeline: str = "embeddings",
    pipeline_step: str = "embed_texts",
    company_slug: str = "",
    run_id: str | None = None,
    workspace_id: str | None = None,
    agent_key: str = "",
    credential_id: str | None = None,
    model_config_id: str | None = None,
    actual_provider: str = "",
    workspace_billed: bool = False,
) -> List[List[float]]:
    """Embed a list of texts using OpenAI embeddings API via OpenRouter.

    Args:
        texts: Texts to embed.
        batch_size: Number of texts per API call.

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []
    model = model or settings.embedding_model
    if not model:
        raise RuntimeError("EMBEDDING_MODEL is not set. Add it to .env.local.")
    model = _ensure_model_prefix(model)

    client = (
        build_sync_client_for_key(api_key, base_url=base_url, timeout_s=timeout_s)
        if api_key
        else get_sync_client()
    )
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = _retry_sync(
            lambda b=batch: client.embeddings.create(model=model, input=b),
        )

        # Cost tracking per batch (never raises)
        from core.shared_tools.cost_tracker import track_llm_cost

        _usage = getattr(response, "usage", None)
        track_llm_cost(
            model=model,
            provider="openrouter",
            pipeline=pipeline,
            pipeline_step=pipeline_step,
            prompt_tokens=getattr(_usage, "prompt_tokens", 0) or 0,
            completion_tokens=0,  # Embeddings have no completion tokens
            company_slug=company_slug,
            call_site="core.shared_tools.embedding_client",
            source="openrouter",
            run_id=run_id,
            workspace_id=workspace_id,
            agent_key=agent_key,
            credential_id=credential_id,
            model_config_id=model_config_id,
            actual_provider=actual_provider or (model.split("/", 1)[0] if "/" in model else ""),
            workspace_billed=workspace_billed,
        )

        embeddings.extend([row.embedding for row in response.data])
    return embeddings
