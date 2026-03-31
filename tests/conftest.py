"""pytest configuration & shared fixtures for async pipeline tests."""
from __future__ import annotations

import asyncio
import os
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

# ---------------------------------------------------------------------------
# Force local storage backend for ALL tests — must run before settings import
# ---------------------------------------------------------------------------
os.environ.setdefault("STORAGE_BACKEND", "local")


# ---------------------------------------------------------------------------
# Patch all LangGraph graph modules to use MemorySaver (no Redis required)
# ---------------------------------------------------------------------------
_GRAPH_MODULES_WITH_CHECKPOINTER = [
    "core.content_engine.graph_v13",
    "core.research.audience_persona.graph",
    "core.research.knowledge_base.graph",
    "core.research.voice_style_guide.graph",
    "core.topic_discovery.graph",
]


@pytest.fixture(autouse=True)
def _use_memory_checkpointer(monkeypatch):
    """Replace get_checkpointer in every graph module with MemorySaver.

    Without this, any test that transitively calls build_*_graph() would
    require a running Redis with RediSearch — which CI does not have.
    Patched at the *usage* module level so the ``from core.checkpointer
    import get_checkpointer`` binding is replaced.
    """
    for mod in _GRAPH_MODULES_WITH_CHECKPOINTER:
        monkeypatch.setattr(
            f"{mod}.get_checkpointer",
            lambda override=None: override
            if override is not None
            else MemorySaver(),
        )


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
    """Fixture that patches get_async_client to return deterministic embeddings."""
    dim = 8

    async def fake_create(*, model: str, input: List[str], **kwargs):
        data = make_embedding_response(input, dim=dim)
        return FakeEmbeddingResponse(data=data)

    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(side_effect=fake_create)

    with patch("core.shared_tools.async_embedding_client.get_async_client", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# Mock settings (no real API keys needed)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_settings():
    """Fixture that patches settings with test values."""
    with patch("core.config.settings.settings") as mock_s:
        mock_s.openai_api_key = "test-api-key"
        mock_s.embedding_model = "text-embedding-3-small"
        yield mock_s
