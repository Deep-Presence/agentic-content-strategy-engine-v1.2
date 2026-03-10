"""Tests for async ChromaDB client — TDD: written BEFORE implementation."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import FakeChromaCollection


# Patch target: sync chroma_client module (where the sync functions live)
_SYNC_MODULE = "core.shared_tools.chroma_client"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncUpsertEmbeddings:
    """Tests for async_upsert_embeddings()."""

    @pytest.mark.asyncio
    async def test_upserts_to_chroma_via_thread(self):
        """Should delegate to sync upsert_embeddings via asyncio.to_thread."""
        fake_collection = FakeChromaCollection()

        with patch(
            f"{_SYNC_MODULE}.get_company_collection",
            return_value=fake_collection,
        ):
            from core.shared_tools.async_chroma_client import async_upsert_embeddings

            await async_upsert_embeddings(
                company_slug="test-co",
                unit_ids=["u1", "u2"],
                texts=["text one", "text two"],
                embeddings=[[1.0, 2.0], [3.0, 4.0]],
            )

        assert fake_collection.count() == 2
        assert "test-co__u1" in fake_collection._store
        assert "test-co__u2" in fake_collection._store

    @pytest.mark.asyncio
    async def test_upsert_with_metadatas(self):
        """Should pass metadatas through correctly."""
        fake_collection = FakeChromaCollection()

        with patch(
            f"{_SYNC_MODULE}.get_company_collection",
            return_value=fake_collection,
        ):
            from core.shared_tools.async_chroma_client import async_upsert_embeddings

            await async_upsert_embeddings(
                company_slug="test-co",
                unit_ids=["u1"],
                texts=["text"],
                embeddings=[[1.0]],
                metadatas=[{"source": "test"}],
            )

        stored = fake_collection._store["test-co__u1"]
        assert stored["metadata"] == {"source": "test"}


class TestAsyncGetAllEmbeddings:
    """Tests for async_get_all_embeddings()."""

    @pytest.mark.asyncio
    async def test_returns_all_embeddings(self):
        """Should return all embeddings as a dict mapping unit_id -> vector."""
        fake_collection = FakeChromaCollection()
        fake_collection.upsert(
            ids=["co__a", "co__b"],
            documents=["doc a", "doc b"],
            embeddings=[[1.0, 2.0], [3.0, 4.0]],
        )

        with patch(
            f"{_SYNC_MODULE}.get_company_collection",
            return_value=fake_collection,
        ):
            from core.shared_tools.async_chroma_client import async_get_all_embeddings

            result = await async_get_all_embeddings("co")

        assert "a" in result
        assert "b" in result
        assert result["a"] == [1.0, 2.0]

    @pytest.mark.asyncio
    async def test_empty_collection_returns_empty_dict(self):
        """Should return empty dict for collection with no data."""
        fake_collection = FakeChromaCollection()

        with patch(
            f"{_SYNC_MODULE}.get_company_collection",
            return_value=fake_collection,
        ):
            from core.shared_tools.async_chroma_client import async_get_all_embeddings

            result = await async_get_all_embeddings("co")

        assert result == {}


class TestAsyncGetEmbeddingsByIds:
    """Tests for async_get_embeddings_by_ids()."""

    @pytest.mark.asyncio
    async def test_returns_requested_ids_only(self):
        """Should return only the requested unit IDs."""
        fake_collection = FakeChromaCollection()
        fake_collection.upsert(
            ids=["co__a", "co__b", "co__c"],
            documents=["a", "b", "c"],
            embeddings=[[1.0], [2.0], [3.0]],
        )

        with patch(
            f"{_SYNC_MODULE}.get_company_collection",
            return_value=fake_collection,
        ):
            from core.shared_tools.async_chroma_client import async_get_embeddings_by_ids

            result = await async_get_embeddings_by_ids("co", ["a", "c"])

        assert "a" in result
        assert "c" in result
        assert "b" not in result


class TestAsyncDeleteCompanyCollection:
    """Tests for async_delete_company_collection()."""

    @pytest.mark.asyncio
    async def test_delegates_to_sync_delete(self):
        """Should call sync delete_company_collection via to_thread."""
        with patch(
            "core.shared_tools.async_chroma_client.delete_company_collection"
        ) as mock_delete:
            from core.shared_tools.async_chroma_client import async_delete_company_collection

            await async_delete_company_collection("test-co")

        mock_delete.assert_called_once_with("test-co")


class TestAsyncCollectionExists:
    """Tests for async_collection_exists()."""

    @pytest.mark.asyncio
    async def test_returns_true_when_data_exists(self):
        """Should return True when collection has data."""
        with patch(
            "core.shared_tools.async_chroma_client.collection_exists",
            return_value=True,
        ):
            from core.shared_tools.async_chroma_client import async_collection_exists

            assert await async_collection_exists("test-co") is True

    @pytest.mark.asyncio
    async def test_returns_false_when_empty(self):
        """Should return False when collection is empty or missing."""
        with patch(
            "core.shared_tools.async_chroma_client.collection_exists",
            return_value=False,
        ):
            from core.shared_tools.async_chroma_client import async_collection_exists

            assert await async_collection_exists("test-co") is False


class TestAsyncUpsertCitationEmbeddings:
    """Tests for async_upsert_citation_embeddings()."""

    @pytest.mark.asyncio
    async def test_upserts_citations_to_chroma(self):
        """Should delegate citation embedding upsert to sync via to_thread."""
        fake_collection = FakeChromaCollection()

        with patch(
            f"{_SYNC_MODULE}.get_citations_collection",
            return_value=fake_collection,
        ):
            from core.shared_tools.async_chroma_client import async_upsert_citation_embeddings

            await async_upsert_citation_embeddings(
                company_slug="test-co",
                embedding_ids=["emb1", "emb2"],
                documents=["para 1", "para 2"],
                embeddings=[[0.1, 0.2], [0.3, 0.4]],
            )

        assert fake_collection.count() == 2
        assert "emb1" in fake_collection._store
