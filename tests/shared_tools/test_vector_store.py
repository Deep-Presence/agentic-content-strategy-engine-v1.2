"""Tests for pgvector-backed VectorStoreClient — drop-in replacement for ChromaDB.

All tests mock the SQLAlchemy session layer so they run without a real database.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.shared_tools.vector_store import (
    VectorStoreClient,
    _reset_client,
    async_collection_exists,
    async_delete_company_collection,
    async_get_all_embeddings,
    async_get_embeddings_by_ids,
    async_get_persona_embeddings,
    async_upsert_citation_embeddings,
    async_upsert_embeddings,
    async_upsert_persona_embeddings,
)

# ── Helpers ──────────────────────────────────────────────────────────────

_VEC = [0.1] * 1536  # Dummy 1536-dim vector
_COMPANY_ID = uuid.uuid4()
_MODULE = "core.shared_tools.vector_store"


class FakeRow:
    """Mimics a SQLAlchemy Row with named attributes."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeResult:
    """Mimics SQLAlchemy execute result."""
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar_value = scalar_value
        self.rowcount = len(self._rows)

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value

    def scalars(self):
        return self


class FakeSession:
    """Minimal async session mock with context manager support."""
    def __init__(self, execute_returns=None):
        self._execute_returns = execute_returns or []
        self._execute_call_count = 0
        self.committed = False
        self.added = []

    async def execute(self, stmt):
        if self._execute_call_count < len(self._execute_returns):
            result = self._execute_returns[self._execute_call_count]
        else:
            result = FakeResult()
        self._execute_call_count += 1
        return result

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def make_session_factory(session):
    """Create a callable that returns the session as a context manager."""
    def factory():
        return session
    return factory


@pytest.fixture(autouse=True)
def reset_client():
    """Reset module-level client between tests."""
    _reset_client()
    yield
    _reset_client()


# ── VectorStoreClient Tests ─────────────────────────────────────────────


class TestUpsertEmbeddings:
    """Tests for upsert_embeddings (semantic units, S1)."""

    @pytest.mark.asyncio
    async def test_upserts_semantic_units(self):
        """Should insert semantic unit rows via session."""
        # company_id lookup returns our fake ID, then delete, then flush
        session = FakeSession(execute_returns=[
            FakeResult(scalar_value=_COMPANY_ID),  # resolve company_id
            FakeResult(),  # delete existing
        ])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_embeddings(
            company_slug="test-co",
            unit_ids=["u1", "u2"],
            texts=["text one", "text two"],
            embeddings=[_VEC, _VEC],
        )

        assert session.committed
        assert len(session.added) == 2

    @pytest.mark.asyncio
    async def test_skips_when_company_not_found(self):
        """Should log warning and skip when company slug not in DB."""
        session = FakeSession(execute_returns=[
            FakeResult(scalar_value=None),  # company not found
        ])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_embeddings(
            company_slug="unknown",
            unit_ids=["u1"],
            texts=["t"],
            embeddings=[_VEC],
        )

        assert not session.committed

    @pytest.mark.asyncio
    async def test_uses_provided_company_id(self):
        """Should skip company_id lookup when explicitly provided."""
        session = FakeSession(execute_returns=[
            FakeResult(),  # delete existing (no company lookup needed)
        ])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_embeddings(
            company_slug="test-co",
            unit_ids=["u1"],
            texts=["t"],
            embeddings=[_VEC],
            company_id=_COMPANY_ID,
        )

        assert session.committed
        assert len(session.added) == 1

    @pytest.mark.asyncio
    async def test_empty_unit_ids_is_noop(self):
        """Should return immediately for empty input."""
        session = FakeSession()
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_embeddings(
            company_slug="test-co",
            unit_ids=[],
            texts=[],
            embeddings=[],
        )

        assert not session.committed


class TestGetAllEmbeddings:
    """Tests for get_all_embeddings."""

    @pytest.mark.asyncio
    async def test_returns_mapping(self):
        """Should return dict mapping unit_id -> embedding."""
        rows = [
            FakeRow(unit_id="u1", embedding=[1.0, 2.0]),
            FakeRow(unit_id="u2", embedding=[3.0, 4.0]),
        ]
        session = FakeSession(execute_returns=[FakeResult(rows=rows)])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        result = await client.get_all_embeddings("test-co")

        assert result == {"u1": [1.0, 2.0], "u2": [3.0, 4.0]}

    @pytest.mark.asyncio
    async def test_empty_returns_empty_dict(self):
        """Should return empty dict when no rows found."""
        session = FakeSession(execute_returns=[FakeResult(rows=[])])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        result = await client.get_all_embeddings("test-co")

        assert result == {}


class TestGetEmbeddingsByIds:
    """Tests for get_embeddings_by_ids."""

    @pytest.mark.asyncio
    async def test_returns_only_requested(self):
        """Should return only the requested unit IDs."""
        rows = [
            FakeRow(unit_id="u1", embedding=[1.0]),
            FakeRow(unit_id="u3", embedding=[3.0]),
        ]
        session = FakeSession(execute_returns=[FakeResult(rows=rows)])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        result = await client.get_embeddings_by_ids("test-co", ["u1", "u3"])

        assert "u1" in result
        assert "u3" in result
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(self):
        """Should return empty dict for empty ID list."""
        client = VectorStoreClient(session_factory=make_session_factory(FakeSession()))

        result = await client.get_embeddings_by_ids("test-co", [])

        assert result == {}


class TestCollectionExists:
    """Tests for collection_exists."""

    @pytest.mark.asyncio
    async def test_returns_true_when_count_positive(self):
        """Should return True when embeddings exist for slug."""
        session = FakeSession(execute_returns=[FakeResult(scalar_value=5)])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        assert await client.collection_exists("test-co") is True

    @pytest.mark.asyncio
    async def test_returns_false_when_count_zero(self):
        """Should return False when no embeddings exist."""
        session = FakeSession(execute_returns=[FakeResult(scalar_value=0)])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        assert await client.collection_exists("test-co") is False


class TestDeleteCompanyEmbeddings:
    """Tests for delete_company_embeddings."""

    @pytest.mark.asyncio
    async def test_deletes_and_commits(self):
        """Should execute delete and commit."""
        session = FakeSession(execute_returns=[FakeResult(rows=[1, 2])])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.delete_company_embeddings("test-co")

        assert session.committed


class TestUpsertCitationEmbeddings:
    """Tests for upsert_citation_embeddings."""

    @pytest.mark.asyncio
    async def test_upserts_citations(self):
        """Should execute upsert statement and commit."""
        session = FakeSession(execute_returns=[FakeResult()])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_citation_embeddings(
            company_slug="test-co",
            embedding_ids=["e1", "e2"],
            documents=["para 1", "para 2"],
            embeddings=[_VEC, _VEC],
        )

        assert session.committed

    @pytest.mark.asyncio
    async def test_empty_ids_is_noop(self):
        """Should return immediately for empty input."""
        session = FakeSession()
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_citation_embeddings(
            company_slug="test-co",
            embedding_ids=[],
            documents=[],
            embeddings=[],
        )

        assert not session.committed


class TestPersonaEmbeddings:
    """Tests for persona embedding upsert and retrieval."""

    @pytest.mark.asyncio
    async def test_upsert_persona_embeddings(self):
        """Should execute upsert and commit."""
        session = FakeSession(execute_returns=[FakeResult()])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_persona_embeddings(
            effective_slug="ramp__fintech",
            persona_ids=["vp-eng", "cto"],
            texts=["VP of Engineering profile", "CTO profile"],
            embeddings=[_VEC, _VEC],
        )

        assert session.committed

    @pytest.mark.asyncio
    async def test_get_persona_embeddings(self):
        """Should return dict mapping persona_id -> embedding."""
        rows = [
            FakeRow(persona_id="vp-eng", embedding=[1.0, 2.0]),
            FakeRow(persona_id="cto", embedding=[3.0, 4.0]),
        ]
        session = FakeSession(execute_returns=[FakeResult(rows=rows)])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        result = await client.get_persona_embeddings("ramp__fintech")

        assert result == {"vp-eng": [1.0, 2.0], "cto": [3.0, 4.0]}

    @pytest.mark.asyncio
    async def test_get_persona_embeddings_with_filter(self):
        """Should pass persona_ids filter to query."""
        rows = [FakeRow(persona_id="vp-eng", embedding=[1.0])]
        session = FakeSession(execute_returns=[FakeResult(rows=rows)])
        client = VectorStoreClient(session_factory=make_session_factory(session))

        result = await client.get_persona_embeddings("ramp", persona_ids=["vp-eng"])

        assert "vp-eng" in result
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_persona_ids_is_noop(self):
        """Should return immediately for empty persona_ids."""
        session = FakeSession()
        client = VectorStoreClient(session_factory=make_session_factory(session))

        await client.upsert_persona_embeddings(
            effective_slug="ramp",
            persona_ids=[],
            texts=[],
            embeddings=[],
        )

        assert not session.committed


# ── Module-Level Convenience Function Tests ─────────────────────────────


class TestModuleLevelFunctions:
    """Tests for module-level drop-in replacement functions."""

    @pytest.mark.asyncio
    async def test_async_upsert_embeddings_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client

            await async_upsert_embeddings("co", ["u1"], ["t"], [[1.0]])

            mock_client.upsert_embeddings.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_get_all_embeddings_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get_all_embeddings.return_value = {"u1": [1.0]}
            mock_get.return_value = mock_client

            result = await async_get_all_embeddings("co")

            assert result == {"u1": [1.0]}

    @pytest.mark.asyncio
    async def test_async_collection_exists_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.collection_exists.return_value = True
            mock_get.return_value = mock_client

            result = await async_collection_exists("co")

            assert result is True

    @pytest.mark.asyncio
    async def test_async_delete_company_collection_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client

            await async_delete_company_collection("co")

            mock_client.delete_company_embeddings.assert_awaited_once_with("co")

    @pytest.mark.asyncio
    async def test_async_upsert_citation_embeddings_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client

            await async_upsert_citation_embeddings("co", ["e1"], ["d"], [[1.0]])

            mock_client.upsert_citation_embeddings.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_upsert_persona_embeddings_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client

            await async_upsert_persona_embeddings("slug", ["p1"], ["t"], [[1.0]])

            mock_client.upsert_persona_embeddings.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_get_persona_embeddings_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get_persona_embeddings.return_value = {"p1": [1.0]}
            mock_get.return_value = mock_client

            result = await async_get_persona_embeddings("slug")

            assert result == {"p1": [1.0]}

    @pytest.mark.asyncio
    async def test_async_get_embeddings_by_ids_delegates(self):
        """Module-level function should delegate to client."""
        with patch(f"{_MODULE}._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get_embeddings_by_ids.return_value = {"u1": [1.0]}
            mock_get.return_value = mock_client

            result = await async_get_embeddings_by_ids("co", ["u1"])

            assert result == {"u1": [1.0]}


class TestErrorHandling:
    """Tests for graceful error handling (never crash pipeline)."""

    @pytest.mark.asyncio
    async def test_upsert_swallows_exception(self):
        """Should catch and log, not raise."""
        client = VectorStoreClient(session_factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        # Should not raise
        await client.upsert_embeddings("co", ["u1"], ["t"], [_VEC])

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_on_error(self):
        """Should return empty dict on error."""
        client = VectorStoreClient(session_factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = await client.get_all_embeddings("co")
        assert result == {}

    @pytest.mark.asyncio
    async def test_collection_exists_returns_false_on_error(self):
        """Should return False on error."""
        client = VectorStoreClient(session_factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = await client.collection_exists("co")
        assert result is False
