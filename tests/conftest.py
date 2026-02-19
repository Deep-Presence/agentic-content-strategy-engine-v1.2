"""pytest configuration & shared fixtures for async pipeline tests."""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock OpenAI embedding response
# ---------------------------------------------------------------------------
class FakeEmbeddingData:
    """Mimics openai.types.Embedding with .embedding and .index fields."""

    def __init__(self, embedding: List[float], index: int) -> None:
        self.embedding = embedding
        self.index = index


class FakeEmbeddingResponse:
    """Mimics openai.types.CreateEmbeddingResponse."""

    def __init__(self, data: List[FakeEmbeddingData]) -> None:
        self.data = data


def make_embedding_response(
    texts: List[str], dim: int = 8
) -> FakeEmbeddingResponse:
    """Build a fake OpenAI embedding response for a batch of texts.

    Each embedding is a simple deterministic vector based on text length
    so tests can assert on values without randomness.
    """
    data = []
    for idx, text in enumerate(texts):
        vec = [float(len(text) + i) for i in range(dim)]
        data.append(FakeEmbeddingData(embedding=vec, index=idx))
    return data


@pytest.fixture
def mock_openai_embeddings():
    """Fixture that patches AsyncOpenAI to return deterministic embeddings."""
    dim = 8

    async def fake_create(*, model: str, input: List[str], **kwargs):
        data = make_embedding_response(input, dim=dim)
        return FakeEmbeddingResponse(data=data)

    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(side_effect=fake_create)

    with patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# Mock ChromaDB collection
# ---------------------------------------------------------------------------
class FakeChromaCollection:
    """In-memory ChromaDB collection for tests."""

    def __init__(self, name: str = "test_collection") -> None:
        self.name = name
        self._store: Dict[str, dict] = {}

    def upsert(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        for i, doc_id in enumerate(ids):
            self._store[doc_id] = {
                "document": documents[i] if documents else None,
                "embedding": embeddings[i] if embeddings else None,
                "metadata": metadatas[i] if metadatas else None,
            }

    def get(
        self,
        ids: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
    ) -> dict:
        if ids is None:
            target_ids = list(self._store.keys())
        else:
            target_ids = [i for i in ids if i in self._store]

        result_ids = target_ids
        result_embeddings = None
        if include and "embeddings" in include:
            result_embeddings = [self._store[i]["embedding"] for i in target_ids]

        return {"ids": result_ids, "embeddings": result_embeddings}

    def count(self) -> int:
        return len(self._store)


@pytest.fixture
def fake_chroma_collection():
    """Provide a FakeChromaCollection for tests."""
    return FakeChromaCollection()


# ---------------------------------------------------------------------------
# Mock settings (no real API keys needed)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_settings():
    """Fixture that patches settings with test values."""
    with patch("core.config.settings.settings") as mock_s:
        mock_s.openai_api_key = "test-api-key"
        mock_s.embedding_model = "text-embedding-3-small"
        mock_s.chroma_persist_dir = "/tmp/test_chroma"
        mock_s.chroma_collection_prefix = "test_gap"
        yield mock_s
