"""Async ChromaDB client wrappers.

ChromaDB has no native async API, so we wrap sync operations with
asyncio.to_thread() to avoid blocking the event loop.

Each function mirrors its sync counterpart in chroma_client.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from core.shared_tools.chroma_client import (
    collection_exists,
    delete_company_collection,
    get_all_embeddings,
    get_company_collection,
    get_citations_collection,
    get_embeddings_by_ids,
    upsert_embeddings,
    upsert_citation_embeddings,
)

logger = logging.getLogger(__name__)


async def async_upsert_embeddings(
    company_slug: str,
    unit_ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Async wrapper for upsert_embeddings (runs in thread pool)."""
    await asyncio.to_thread(
        upsert_embeddings,
        company_slug,
        unit_ids,
        texts,
        embeddings,
        metadatas,
    )


async def async_get_all_embeddings(
    company_slug: str,
) -> Dict[str, List[float]]:
    """Async wrapper for get_all_embeddings (runs in thread pool)."""
    return await asyncio.to_thread(get_all_embeddings, company_slug)


async def async_get_embeddings_by_ids(
    company_slug: str,
    unit_ids: List[str],
) -> Dict[str, List[float]]:
    """Async wrapper for get_embeddings_by_ids (runs in thread pool)."""
    return await asyncio.to_thread(get_embeddings_by_ids, company_slug, unit_ids)


async def async_delete_company_collection(company_slug: str) -> None:
    """Async wrapper for delete_company_collection (runs in thread pool)."""
    await asyncio.to_thread(delete_company_collection, company_slug)


async def async_collection_exists(company_slug: str) -> bool:
    """Async wrapper for collection_exists (runs in thread pool)."""
    return await asyncio.to_thread(collection_exists, company_slug)


async def async_upsert_citation_embeddings(
    company_slug: str,
    embedding_ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Async wrapper for upsert_citation_embeddings (runs in thread pool)."""
    await asyncio.to_thread(
        upsert_citation_embeddings,
        company_slug,
        embedding_ids,
        documents,
        embeddings,
        metadatas,
    )
