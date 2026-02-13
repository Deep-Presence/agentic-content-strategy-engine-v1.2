"""ChromaDB wrapper for persistent local vector storage.

Used by the gap analysis pipeline to store and retrieve embeddings,
replacing raw-embedding JSON files with lightweight embedding_id references.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from core.config.settings import settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


def _get_persist_dir() -> str:
    """Resolve ChromaDB persist directory to absolute path."""
    p = Path(settings.chroma_persist_dir)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def get_chroma_client() -> chromadb.ClientAPI:
    """Get a persistent ChromaDB client."""
    return chromadb.PersistentClient(
        path=_get_persist_dir(),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


_CITATIONS_COLLECTION_PREFIX = "gap_citations"


def get_company_collection(
    company_slug: str,
    client: Optional[chromadb.ClientAPI] = None,
) -> chromadb.Collection:
    """Get or create the ChromaDB collection for a company's embeddings."""
    client = client or get_chroma_client()
    collection_name = f"{settings.chroma_collection_prefix}_{company_slug}"
    # Truncate to ChromaDB's 63-char limit if needed
    if len(collection_name) > 63:
        collection_name = collection_name[:63]
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_embeddings(
    company_slug: str,
    unit_ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Upsert embedding vectors into ChromaDB for a company."""
    collection = get_company_collection(company_slug)
    doc_ids = [f"{company_slug}__{uid}" for uid in unit_ids]
    batch_size = 500
    for i in range(0, len(doc_ids), batch_size):
        end = i + batch_size
        collection.upsert(
            ids=doc_ids[i:end],
            documents=texts[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end] if metadatas else None,
        )
    logger.info(
        "Upserted %d embeddings into ChromaDB collection '%s_%s'.",
        len(doc_ids),
        settings.chroma_collection_prefix,
        company_slug,
    )


def get_embeddings_by_ids(
    company_slug: str,
    unit_ids: List[str],
) -> Dict[str, List[float]]:
    """Retrieve embeddings for specific unit IDs from ChromaDB.

    Returns a dict mapping unit_id -> embedding vector.
    """
    collection = get_company_collection(company_slug)
    doc_ids = [f"{company_slug}__{uid}" for uid in unit_ids]
    result = collection.get(ids=doc_ids, include=["embeddings"])
    mapping: Dict[str, List[float]] = {}
    if result and result["ids"] and result["embeddings"] is not None:
        for doc_id, emb in zip(result["ids"], result["embeddings"]):
            original_id = doc_id.split("__", 1)[1] if "__" in doc_id else doc_id
            mapping[original_id] = [float(x) for x in emb]
    return mapping


def get_all_embeddings(company_slug: str) -> Dict[str, List[float]]:
    """Retrieve all embeddings for a company from ChromaDB.

    Returns a dict mapping unit_id -> embedding vector.
    """
    collection = get_company_collection(company_slug)
    result = collection.get(include=["embeddings"])
    mapping: Dict[str, List[float]] = {}
    if result and result["ids"] and result["embeddings"] is not None:
        for doc_id, emb in zip(result["ids"], result["embeddings"]):
            original_id = doc_id.split("__", 1)[1] if "__" in doc_id else doc_id
            mapping[original_id] = [float(x) for x in emb]
    return mapping


def collection_exists(company_slug: str) -> bool:
    """Check if a company's ChromaDB collection exists and has data."""
    try:
        client = get_chroma_client()
        collection_name = f"{settings.chroma_collection_prefix}_{company_slug}"
        if len(collection_name) > 63:
            collection_name = collection_name[:63]
        collection = client.get_collection(collection_name)
        return collection.count() > 0
    except Exception:
        return False


def delete_company_collection(company_slug: str) -> None:
    """Delete a company's ChromaDB collection (for re-runs)."""
    try:
        client = get_chroma_client()
        collection_name = f"{settings.chroma_collection_prefix}_{company_slug}"
        if len(collection_name) > 63:
            collection_name = collection_name[:63]
        client.delete_collection(collection_name)
        logger.info("Deleted ChromaDB collection: %s", collection_name)
    except Exception:
        pass


def get_citations_collection(
    company_slug: str,
    client: Optional[chromadb.ClientAPI] = None,
) -> chromadb.Collection:
    """Get or create the ChromaDB collection for citation paragraph embeddings."""
    client = client or get_chroma_client()
    collection_name = f"{_CITATIONS_COLLECTION_PREFIX}_{company_slug}"
    if len(collection_name) > 63:
        collection_name = collection_name[:63]
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_citation_embeddings(
    company_slug: str,
    embedding_ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Upsert citation paragraph embeddings into ChromaDB."""
    collection = get_citations_collection(company_slug)
    batch_size = 500
    for i in range(0, len(embedding_ids), batch_size):
        end = i + batch_size
        collection.upsert(
            ids=embedding_ids[i:end],
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end] if metadatas else None,
        )
    logger.info(
        "Upserted %d citation embeddings into ChromaDB collection '%s_%s'.",
        len(embedding_ids),
        _CITATIONS_COLLECTION_PREFIX,
        company_slug,
    )
