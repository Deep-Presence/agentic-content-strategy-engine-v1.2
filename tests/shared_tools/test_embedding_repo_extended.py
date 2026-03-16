"""Unit tests for EmbeddingRepository extended methods (pgvector migration).

Tests use mocked AsyncSession — no real database required.
Covers 7 new methods added in Phase 3 of the pgvector migration.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.db.repositories.embedding_repo import EmbeddingRepository


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession with standard execute/flush behavior."""
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session):
    """Create an EmbeddingRepository with mocked session."""
    return EmbeddingRepository(mock_session)


# ── get_semantic_units_by_slug ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_semantic_units_by_slug(repo, mock_session):
    """Returns all semantic units matching the company slug."""
    fake_unit = MagicMock()
    fake_unit.company_slug = "ramp"
    fake_unit.unit_id = "u-001"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [fake_unit]
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_semantic_units_by_slug("ramp")

    assert len(results) == 1
    assert results[0].unit_id == "u-001"
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_semantic_units_by_slug_empty(repo, mock_session):
    """Returns empty list when no units match the slug."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_semantic_units_by_slug("nonexistent")

    assert results == []


# ── get_semantic_units_by_ids ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_semantic_units_by_ids(repo, mock_session):
    """Returns specific units matching slug + unit_ids."""
    fake_units = [MagicMock(unit_id="u-1"), MagicMock(unit_id="u-2")]

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = fake_units
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_semantic_units_by_ids("ramp", ["u-1", "u-2"])

    assert len(results) == 2
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_semantic_units_by_ids_partial_match(repo, mock_session):
    """Returns only the units that exist (partial match)."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [MagicMock(unit_id="u-1")]
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_semantic_units_by_ids("ramp", ["u-1", "u-missing"])

    assert len(results) == 1


# ── count_by_slug ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_count_by_slug(repo, mock_session):
    """Returns count of semantic units for a slug."""
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 42
    mock_session.execute = AsyncMock(return_value=result_mock)

    count = await repo.count_by_slug("ramp")

    assert count == 42


@pytest.mark.asyncio
async def test_count_by_slug_zero(repo, mock_session):
    """Returns 0 for a slug with no units."""
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 0
    mock_session.execute = AsyncMock(return_value=result_mock)

    count = await repo.count_by_slug("empty-co")

    assert count == 0


# ── delete_by_slug ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_by_slug(repo, mock_session):
    """Deletes all semantic units for a slug and returns count."""
    result_mock = MagicMock()
    result_mock.rowcount = 5
    mock_session.execute = AsyncMock(return_value=result_mock)

    deleted = await repo.delete_by_slug("ramp")

    assert deleted == 5
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_slug_no_match(repo, mock_session):
    """Returns 0 when no units match the slug."""
    result_mock = MagicMock()
    result_mock.rowcount = 0
    mock_session.execute = AsyncMock(return_value=result_mock)

    deleted = await repo.delete_by_slug("nonexistent")

    assert deleted == 0


# ── upsert_paragraph_embeddings ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_paragraph_embeddings(repo, mock_session):
    """Executes upsert statement for paragraph embeddings."""
    items = [
        {
            "id": uuid.uuid4(),
            "embedding_id": "cite_abc",
            "company_slug": "ramp",
            "paragraph_text": "Some text",
            "embedding": [0.1] * 1536,
        },
    ]

    await repo.upsert_paragraph_embeddings(items)

    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_paragraph_embeddings_empty(repo, mock_session):
    """No-op for empty items list."""
    await repo.upsert_paragraph_embeddings([])

    mock_session.execute.assert_not_awaited()
    mock_session.flush.assert_not_awaited()


# ── upsert_persona_embeddings ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_persona_embeddings(repo, mock_session):
    """Executes upsert statement for persona embeddings."""
    items = [
        {
            "id": uuid.uuid4(),
            "company_slug": "ramp",
            "effective_slug": "ramp",
            "persona_id": "p-001",
            "text": "CFO persona",
            "embedding": [0.2] * 1536,
        },
    ]

    await repo.upsert_persona_embeddings(items)

    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_persona_embeddings_empty(repo, mock_session):
    """No-op for empty items list."""
    await repo.upsert_persona_embeddings([])

    mock_session.execute.assert_not_awaited()


# ── get_persona_embeddings_by_slug ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_persona_embeddings_by_slug(repo, mock_session):
    """Returns persona embeddings for an effective slug."""
    fake_persona = MagicMock()
    fake_persona.persona_id = "p-001"
    fake_persona.effective_slug = "ramp"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [fake_persona]
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_persona_embeddings_by_slug("ramp")

    assert len(results) == 1
    assert results[0].persona_id == "p-001"


@pytest.mark.asyncio
async def test_get_persona_embeddings_by_slug_with_ids(repo, mock_session):
    """Filters by persona_ids when provided."""
    fake_persona = MagicMock(persona_id="p-001")

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [fake_persona]
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_persona_embeddings_by_slug("ramp", persona_ids=["p-001"])

    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_persona_embeddings_by_slug_empty(repo, mock_session):
    """Returns empty list when no personas match."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    results = await repo.get_persona_embeddings_by_slug("nonexistent")

    assert results == []
