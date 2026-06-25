"""Async OpenAI embedding client via OpenRouter.

Async counterpart of embedding_client.py for the async-first pipeline.
Uses AsyncOpenAI (via OpenRouter singleton) with semaphore-controlled
batching and retry with jittered backoff.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
from typing import Callable, List, TypeVar

from openai import APIError, RateLimitError

from core.config.settings import settings
from core.shared_tools.openrouter_client import (
    build_async_client_for_key,
    get_async_client,
    _ensure_model_prefix,
)

logger = logging.getLogger(__name__)

# text-embedding-3-small / text-embedding-3-large accept max 8191 tokens per input.
# Conservative chars-per-token ratio (3.2) avoids depending on tiktoken (Rust ext
# that adds ~8 min to Docker builds). Actual average is ~4 chars/token for English;
# 3.2 gives headroom so we never exceed the token limit.
_MAX_CHARS_PER_CHUNK = int(8191 * 3.2)  # ~26,211 chars


def _chunk_text(text: str, max_chars: int = _MAX_CHARS_PER_CHUNK) -> List[str]:
    """Split text into chunks that each fit within the embedding token limit.

    Uses a conservative character-based estimate (3.2 chars/token) to avoid
    depending on tiktoken.
    """
    if len(text) <= max_chars:
        return [text]
    num_chunks = math.ceil(len(text) / max_chars)
    logger.info(
        "Splitting embedding input (%d chars, ~%d tokens) into %d chunks",
        len(text), len(text) // 4, num_chunks,
    )
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def _average_embeddings(embeddings: List[List[float]]) -> List[float]:
    """Mean-pool multiple chunk embeddings into a single normalized vector."""
    dim = len(embeddings[0])
    avg = [sum(e[d] for e in embeddings) / len(embeddings) for d in range(dim)]
    # L2-normalize so downstream cosine similarity works correctly
    norm = math.sqrt(sum(x * x for x in avg)) or 1.0
    return [x / norm for x in avg]

T = TypeVar("T")


async def _retry_async(
    fn: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    *,
    retryable_exceptions: tuple = (RateLimitError, APIError),
) -> T:
    """Retry an async callable with jittered exponential backoff.

    Args:
        fn: Async callable to retry.
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
            return await fn()
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
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def async_embed_texts(
    texts: List[str],
    batch_size: int | None = None,
    max_concurrent_batches: int | None = None,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_s: float | None = None,
    pipeline: str = "embeddings",
    pipeline_step: str = "async_embed_texts",
    company_slug: str = "",
    run_id: str | None = None,
    workspace_id: str | None = None,
    agent_key: str = "",
    credential_id: str | None = None,
    model_config_id: str | None = None,
    actual_provider: str = "",
    workspace_billed: bool = False,
) -> List[List[float]]:
    """Embed texts using AsyncOpenAI (via OpenRouter) with concurrent batching and retry.

    Long texts that exceed the model's 8191-token limit are automatically
    split into chunks, embedded separately, and mean-pooled back into a
    single normalized vector per original text.

    Args:
        texts: Texts to embed.
        batch_size: Number of texts per API call (default: settings).
        max_concurrent_batches: Max batches in flight (default: settings).

    Returns:
        List of embedding vectors, one per input text, in the same order as input.
    """
    if not texts:
        return []

    model = model or settings.embedding_model
    if not model:
        raise RuntimeError("EMBEDDING_MODEL is not set. Add it to .env.local.")
    model = _ensure_model_prefix(model)

    effective_batch_size = batch_size if batch_size is not None else settings.gap_analysis_s5_embed_batch_size
    effective_concurrency = (
        max_concurrent_batches
        if max_concurrent_batches is not None
        else settings.gap_analysis_s5_embed_concurrent_batches
    )

    # --- Pre-process: chunk any texts that exceed the token limit -----------
    # flat_chunks[i] = (original_text_index, chunk_text)
    flat_chunks: List[tuple[int, str]] = []
    chunks_per_text: List[int] = []
    for idx, text in enumerate(texts):
        chunks = _chunk_text(text)
        chunks_per_text.append(len(chunks))
        for chunk in chunks:
            flat_chunks.append((idx, chunk))

    all_chunk_texts = [c[1] for c in flat_chunks]

    # --- Embed all chunks ---------------------------------------------------
    client = (
        build_async_client_for_key(api_key, base_url=base_url, timeout_s=timeout_s)
        if api_key
        else get_async_client()
    )
    batches = [
        all_chunk_texts[i : i + effective_batch_size]
        for i in range(0, len(all_chunk_texts), effective_batch_size)
    ]
    sem = asyncio.Semaphore(effective_concurrency)

    async def _embed_batch(
        batch: List[str], batch_idx: int
    ) -> tuple[int, List[List[float]]]:
        async def _call():
            return await client.embeddings.create(model=model, input=batch)

        async with sem:
            response = await _retry_async(_call, max_retries=3, base_delay=1.0)

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
                call_site="core.shared_tools.async_embedding_client",
                source="openrouter",
                run_id=run_id,
                workspace_id=workspace_id,
                agent_key=agent_key,
                credential_id=credential_id,
                model_config_id=model_config_id,
                actual_provider=actual_provider or (model.split("/", 1)[0] if "/" in model else ""),
                workspace_billed=workspace_billed,
            )

            sorted_data = sorted(response.data, key=lambda d: d.index)
            return batch_idx, [item.embedding for item in sorted_data]

    results = await asyncio.gather(
        *[_embed_batch(b, i) for i, b in enumerate(batches)]
    )

    # Flatten batch results in original order
    results_sorted = sorted(results, key=lambda x: x[0])
    all_chunk_embeddings = [emb for _, batch_embs in results_sorted for emb in batch_embs]

    # --- Post-process: mean-pool chunk embeddings per original text ---------
    final_embeddings: List[List[float]] = []
    offset = 0
    for n_chunks in chunks_per_text:
        chunk_embs = all_chunk_embeddings[offset : offset + n_chunks]
        offset += n_chunks
        if n_chunks == 1:
            final_embeddings.append(chunk_embs[0])
        else:
            final_embeddings.append(_average_embeddings(chunk_embs))

    return final_embeddings
