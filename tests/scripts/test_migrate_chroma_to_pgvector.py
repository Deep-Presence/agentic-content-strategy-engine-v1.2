"""Tests for scripts/migrate_chroma_to_pgvector.py.

Uses mock ChromaDB client + mock vector_store functions to verify migration
logic: collection enumeration, batch processing, dry-run, empty collections,
and summary reporting.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure scripts/ is importable
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_collection(name: str, ids: list, docs: list, embeddings: list):
    """Create a mock ChromaDB collection."""
    col = MagicMock()
    col.name = name
    col.get.return_value = {
        "ids": ids,
        "documents": docs,
        "embeddings": embeddings,
        "metadatas": [{}] * len(ids),
    }
    return col


def _make_chroma_client(collections: dict[str, MagicMock]):
    """Create a mock ChromaDB PersistentClient with named collections."""
    client = MagicMock()
    col_metas = [SimpleNamespace(name=n) for n in collections]
    client.list_collections.return_value = col_metas
    client.get_collection.side_effect = lambda name: collections[name]
    return client


# ── _extract_slug ────────────────────────────────────────────────────────


def test_extract_slug_company():
    """Extracts slug from 'gap_company_ramp' → 'ramp'."""
    from scripts.migrate_chroma_to_pgvector import _extract_slug

    assert _extract_slug("gap_company_ramp", "gap_company_") == "ramp"
    assert _extract_slug("gap_company_carta", "gap_company_") == "carta"


def test_extract_slug_citation():
    """Extracts slug from 'gap_citations_mynd' → 'mynd'."""
    from scripts.migrate_chroma_to_pgvector import _extract_slug

    assert _extract_slug("gap_citations_mynd", "gap_citations_") == "mynd"


def test_extract_slug_persona():
    """Extracts slug from 'persona_ramp' → 'ramp'."""
    from scripts.migrate_chroma_to_pgvector import _extract_slug

    assert _extract_slug("persona_ramp", "persona_") == "ramp"


def test_extract_slug_no_match():
    """Returns None when prefix doesn't match."""
    from scripts.migrate_chroma_to_pgvector import _extract_slug

    assert _extract_slug("other_collection", "gap_company_") is None
    assert _extract_slug("gap_company", "gap_company_") is None


# ── _migrate_company_collections ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_migrate_company_collections():
    """Migrates gap_company_* collections to vector store."""
    from scripts.migrate_chroma_to_pgvector import _migrate_company_collections

    embedding = [[0.1] * 1536, [0.2] * 1536]
    col = _make_collection(
        "gap_company_ramp",
        ids=["u1", "u2"],
        docs=["Text 1", "Text 2"],
        embeddings=embedding,
    )
    other = _make_collection("unrelated", ids=[], docs=[], embeddings=[])
    client = _make_chroma_client({"gap_company_ramp": col, "unrelated": other})

    mock_upsert = AsyncMock()
    with patch(
        "scripts.migrate_chroma_to_pgvector.async_upsert_embeddings",
        mock_upsert,
        create=True,
    ), patch(
        "core.shared_tools.vector_store.async_upsert_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_company_collections(client, dry_run=False)

    assert stats == {"gap_company_ramp": 2}
    mock_upsert.assert_awaited_once_with(
        company_slug="ramp",
        unit_ids=["u1", "u2"],
        texts=["Text 1", "Text 2"],
        embeddings=embedding,
    )


@pytest.mark.asyncio
async def test_migrate_company_collections_dry_run():
    """Dry run reports stats but does not write."""
    from scripts.migrate_chroma_to_pgvector import _migrate_company_collections

    col = _make_collection(
        "gap_company_ramp",
        ids=["u1"],
        docs=["Text"],
        embeddings=[[0.1] * 1536],
    )
    client = _make_chroma_client({"gap_company_ramp": col})

    mock_upsert = AsyncMock()
    with patch(
        "core.shared_tools.vector_store.async_upsert_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_company_collections(client, dry_run=True)

    assert stats == {"gap_company_ramp": 1}
    mock_upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_migrate_company_collections_empty():
    """Skips empty collections."""
    from scripts.migrate_chroma_to_pgvector import _migrate_company_collections

    col = _make_collection("gap_company_empty", ids=[], docs=[], embeddings=[])
    client = _make_chroma_client({"gap_company_empty": col})

    stats = await _migrate_company_collections(client, dry_run=False)

    assert stats == {}


# ── _migrate_citation_collections ────────────────────────────────────────


@pytest.mark.asyncio
async def test_migrate_citation_collections():
    """Migrates gap_citations_* collections to vector store."""
    from scripts.migrate_chroma_to_pgvector import _migrate_citation_collections

    embedding = [[0.3] * 1536]
    col = _make_collection(
        "gap_citations_carta",
        ids=["c1"],
        docs=["Citation text"],
        embeddings=embedding,
    )
    client = _make_chroma_client({"gap_citations_carta": col})

    mock_upsert = AsyncMock()
    with patch(
        "scripts.migrate_chroma_to_pgvector.async_upsert_citation_embeddings",
        mock_upsert,
        create=True,
    ), patch(
        "core.shared_tools.vector_store.async_upsert_citation_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_citation_collections(client, dry_run=False)

    assert stats == {"gap_citations_carta": 1}
    mock_upsert.assert_awaited_once_with(
        company_slug="carta",
        embedding_ids=["c1"],
        documents=["Citation text"],
        embeddings=embedding,
    )


@pytest.mark.asyncio
async def test_migrate_citation_dry_run():
    """Dry run for citations: no writes."""
    from scripts.migrate_chroma_to_pgvector import _migrate_citation_collections

    col = _make_collection(
        "gap_citations_mynd",
        ids=["c1", "c2"],
        docs=["A", "B"],
        embeddings=[[0.1] * 1536, [0.2] * 1536],
    )
    client = _make_chroma_client({"gap_citations_mynd": col})

    mock_upsert = AsyncMock()
    with patch(
        "core.shared_tools.vector_store.async_upsert_citation_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_citation_collections(client, dry_run=True)

    assert stats == {"gap_citations_mynd": 2}
    mock_upsert.assert_not_awaited()


# ── _migrate_persona_collections ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_migrate_persona_collections():
    """Migrates persona_* collections to vector store."""
    from scripts.migrate_chroma_to_pgvector import _migrate_persona_collections

    embedding = [[0.5] * 1536, [0.6] * 1536]
    col = _make_collection(
        "persona_ramp",
        ids=["p1", "p2"],
        docs=["Persona 1", "Persona 2"],
        embeddings=embedding,
    )
    client = _make_chroma_client({"persona_ramp": col})

    mock_upsert = AsyncMock()
    with patch(
        "scripts.migrate_chroma_to_pgvector.async_upsert_persona_embeddings",
        mock_upsert,
        create=True,
    ), patch(
        "core.shared_tools.vector_store.async_upsert_persona_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_persona_collections(client, dry_run=False)

    assert stats == {"persona_ramp": 2}
    mock_upsert.assert_awaited_once_with(
        effective_slug="ramp",
        persona_ids=["p1", "p2"],
        texts=["Persona 1", "Persona 2"],
        embeddings=embedding,
    )


@pytest.mark.asyncio
async def test_migrate_persona_dry_run():
    """Dry run for personas: no writes."""
    from scripts.migrate_chroma_to_pgvector import _migrate_persona_collections

    col = _make_collection(
        "persona_carta",
        ids=["p1"],
        docs=["Persona"],
        embeddings=[[0.1] * 1536],
    )
    client = _make_chroma_client({"persona_carta": col})

    mock_upsert = AsyncMock()
    with patch(
        "core.shared_tools.vector_store.async_upsert_persona_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_persona_collections(client, dry_run=True)

    assert stats == {"persona_carta": 1}
    mock_upsert.assert_not_awaited()


# ── main() ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_main_missing_chroma_dir(tmp_path):
    """Returns 0 when ChromaDB directory doesn't exist."""
    from scripts.migrate_chroma_to_pgvector import main

    nonexistent = tmp_path / "no_chroma_here"
    with patch("sys.argv", ["migrate", "--chroma-dir", str(nonexistent)]):
        result = await main()

    assert result == 0


@pytest.mark.asyncio
async def test_main_chromadb_not_installed(tmp_path):
    """Returns 1 when chromadb package is not importable."""
    from scripts.migrate_chroma_to_pgvector import main

    chroma_dir = tmp_path / "chroma_db"
    chroma_dir.mkdir()

    with patch("sys.argv", ["migrate", "--chroma-dir", str(chroma_dir)]), \
         patch.dict("sys.modules", {"chromadb": None}), \
         patch("builtins.__import__", side_effect=_chromadb_import_error):
        result = await main()

    assert result == 1


def _chromadb_import_error(name, *args, **kwargs):
    """Raise ImportError only for chromadb."""
    if name == "chromadb":
        raise ImportError("No module named 'chromadb'")
    return original_import(name, *args, **kwargs)


original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__


@pytest.mark.asyncio
async def test_main_dry_run_full_flow(tmp_path):
    """Full dry-run flow: enumerates collections, reports stats, no writes."""
    from scripts.migrate_chroma_to_pgvector import main

    chroma_dir = tmp_path / "chroma_db"
    chroma_dir.mkdir()

    company_col = _make_collection(
        "gap_company_ramp",
        ids=["u1", "u2"],
        docs=["A", "B"],
        embeddings=[[0.1] * 1536, [0.2] * 1536],
    )
    citation_col = _make_collection(
        "gap_citations_ramp",
        ids=["c1"],
        docs=["C"],
        embeddings=[[0.3] * 1536],
    )
    persona_col = _make_collection(
        "persona_ramp",
        ids=["p1"],
        docs=["P"],
        embeddings=[[0.4] * 1536],
    )

    mock_client = _make_chroma_client({
        "gap_company_ramp": company_col,
        "gap_citations_ramp": citation_col,
        "persona_ramp": persona_col,
    })

    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client

    with patch("sys.argv", ["migrate", "--chroma-dir", str(chroma_dir), "--dry-run"]), \
         patch.dict("sys.modules", {"chromadb": mock_chromadb}):
        result = await main()

    assert result == 0


@pytest.mark.asyncio
async def test_main_no_database_url(tmp_path):
    """Returns 1 when DATABASE_URL not set and not dry-run."""
    from scripts.migrate_chroma_to_pgvector import main

    chroma_dir = tmp_path / "chroma_db"
    chroma_dir.mkdir()

    mock_client = _make_chroma_client({})
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client

    with patch("sys.argv", ["migrate", "--chroma-dir", str(chroma_dir)]), \
         patch.dict("sys.modules", {"chromadb": mock_chromadb}), \
         patch.dict("os.environ", {"DATABASE_URL": ""}, clear=False):
        import os
        original = os.environ.get("DATABASE_URL")
        try:
            os.environ.pop("DATABASE_URL", None)
            result = await main()
        finally:
            if original is not None:
                os.environ["DATABASE_URL"] = original

    assert result == 1


# ── Edge cases ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_migrate_collections_with_missing_documents():
    """Handles collections where documents list is empty/None."""
    from scripts.migrate_chroma_to_pgvector import _migrate_company_collections

    col = MagicMock()
    col.name = "gap_company_ramp"
    col.get.return_value = {
        "ids": ["u1", "u2"],
        "documents": None,
        "embeddings": [[0.1] * 1536, [0.2] * 1536],
        "metadatas": None,
    }
    client = MagicMock()
    client.list_collections.return_value = [SimpleNamespace(name="gap_company_ramp")]
    client.get_collection.return_value = col

    mock_upsert = AsyncMock()
    with patch(
        "scripts.migrate_chroma_to_pgvector.async_upsert_embeddings",
        mock_upsert,
        create=True,
    ), patch(
        "core.shared_tools.vector_store.async_upsert_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_company_collections(client, dry_run=False)

    assert stats == {"gap_company_ramp": 2}
    # Should have been called with empty strings for missing docs
    call_kwargs = mock_upsert.call_args
    assert call_kwargs.kwargs.get("texts") == ["", ""] or call_kwargs[1].get("texts") == ["", ""]


@pytest.mark.asyncio
async def test_migrate_multiple_companies():
    """Handles multiple gap_company_* collections in one run."""
    from scripts.migrate_chroma_to_pgvector import _migrate_company_collections

    ramp_col = _make_collection(
        "gap_company_ramp",
        ids=["r1"],
        docs=["Ramp"],
        embeddings=[[0.1] * 1536],
    )
    carta_col = _make_collection(
        "gap_company_carta",
        ids=["c1", "c2"],
        docs=["Carta 1", "Carta 2"],
        embeddings=[[0.2] * 1536, [0.3] * 1536],
    )
    client = _make_chroma_client({
        "gap_company_ramp": ramp_col,
        "gap_company_carta": carta_col,
    })

    mock_upsert = AsyncMock()
    with patch(
        "scripts.migrate_chroma_to_pgvector.async_upsert_embeddings",
        mock_upsert,
        create=True,
    ), patch(
        "core.shared_tools.vector_store.async_upsert_embeddings",
        mock_upsert,
    ):
        stats = await _migrate_company_collections(client, dry_run=False)

    assert stats == {"gap_company_ramp": 1, "gap_company_carta": 2}
    assert mock_upsert.await_count == 2
