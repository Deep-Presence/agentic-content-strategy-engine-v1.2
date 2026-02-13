"""Shared OpenAI embedding client.

Consolidates the _embed_texts function duplicated across s1, s2, s5.
"""
from __future__ import annotations

from typing import List

from core.config.settings import settings


def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """Embed a list of texts using OpenAI embeddings API.

    Args:
        texts: Texts to embed.
        batch_size: Number of texts per API call.

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable embeddings."
        )
    model = settings.embedding_model
    if not model:
        raise RuntimeError("EMBEDDING_MODEL is not set. Add it to .env.local.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        embeddings.extend([row.embedding for row in response.data])
    return embeddings
