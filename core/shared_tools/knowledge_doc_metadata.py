"""Shared metadata I/O for knowledge documents.

Provides a single process-wide lock + read/write helpers for
``_metadata.json`` files under ``knowledge_docs/{slug}/`` in StorageBackend.

Both ``api/services/knowledge_doc_service.py`` (upload, delete) and
``core/gap_analysis/steps/s1_embed_assets.py`` (mark-as-embedded) import
from here so they coordinate through the **same** threading lock.

Phase 6 (R2 migration): all I/O goes through StorageBackend instead of
direct ``Path`` operations.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import List

from core.models.knowledge_docs import KnowledgeDocument
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

# Single process-wide lock for all metadata writes
metadata_lock = threading.Lock()


def _metadata_key(effective_slug: str) -> str:
    """Build the storage key for a knowledge doc metadata file."""
    return f"knowledge_docs/{effective_slug}/_metadata.json"


def doc_storage_key(effective_slug: str, stored_filename: str) -> str:
    """Build the storage key for a knowledge document binary file."""
    return f"knowledge_docs/{effective_slug}/{stored_filename}"


def load_metadata(
    effective_slug: str, *, storage: StorageBackend
) -> List[KnowledgeDocument]:
    """Load metadata from StorageBackend. Returns empty list if not found."""
    content = storage.read(_metadata_key(effective_slug))
    if content is None:
        return []
    try:
        data = json.loads(content)
        return [KnowledgeDocument.model_validate(d) for d in data]
    except Exception:
        logger.warning("Failed to parse knowledge doc metadata for %s", effective_slug)
        return []


def save_metadata(
    effective_slug: str,
    docs: List[KnowledgeDocument],
    *,
    storage: StorageBackend,
) -> None:
    """Write metadata to StorageBackend (atomic for both Local and R2)."""
    storage.write(
        _metadata_key(effective_slug),
        json.dumps([d.model_dump(mode="json") for d in docs], indent=2, default=str),
    )


def mark_documents_embedded(
    effective_slug: str, *, storage: StorageBackend
) -> int:
    """Mark all knowledge docs for *effective_slug* as embedded.

    Uses the shared ``metadata_lock`` to coordinate with concurrent uploads.
    Updates ``_metadata.json`` setting ``is_embedded=True`` and
    ``last_embedded_at`` on every document.  Returns count of docs updated.
    """
    now = datetime.now(timezone.utc)

    with metadata_lock:
        docs = load_metadata(effective_slug, storage=storage)
        if not docs:
            return 0

        for doc in docs:
            doc.is_embedded = True
            doc.last_embedded_at = now

        save_metadata(effective_slug, docs, storage=storage)

    logger.info(
        "[knowledge_docs] Marked %d docs as embedded for slug=%s",
        len(docs),
        effective_slug,
    )
    return len(docs)
