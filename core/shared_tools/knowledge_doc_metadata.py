"""Shared metadata I/O for knowledge documents.

Provides a single process-wide lock + atomic read/write helpers for
``_metadata.json`` files under ``artifacts/knowledge_docs/{slug}/``.

Both ``api/services/knowledge_doc_service.py`` (upload, delete) and
``core/gap_analysis/steps/s1_embed_assets.py`` (mark-as-embedded) import
from here so they coordinate through the **same** threading lock.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from core.models.knowledge_docs import KnowledgeDocument

logger = logging.getLogger(__name__)

# Single process-wide lock for all metadata writes
metadata_lock = threading.Lock()


def slug_dir(artifacts_root: Path, effective_slug: str) -> Path:
    return artifacts_root / "knowledge_docs" / effective_slug


def metadata_path(artifacts_root: Path, effective_slug: str) -> Path:
    return slug_dir(artifacts_root, effective_slug) / "_metadata.json"


def load_metadata(artifacts_root: Path, effective_slug: str) -> List[KnowledgeDocument]:
    """Load metadata from disk. Returns empty list if not found."""
    path = metadata_path(artifacts_root, effective_slug)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [KnowledgeDocument.model_validate(d) for d in data]
    except Exception:
        logger.warning("Failed to parse knowledge doc metadata for %s", effective_slug)
        return []


def save_metadata(
    artifacts_root: Path, effective_slug: str, docs: List[KnowledgeDocument]
) -> None:
    """Atomically write metadata to disk."""
    path = metadata_path(artifacts_root, effective_slug)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([d.model_dump(mode="json") for d in docs], indent=2, default=str)
    )
    tmp.replace(path)


def mark_documents_embedded(knowledge_doc_dir: str) -> int:
    """Mark all knowledge docs in the directory as embedded.

    Uses the shared ``metadata_lock`` to coordinate with concurrent uploads.
    Updates ``_metadata.json`` setting ``is_embedded=True`` and
    ``last_embedded_at`` on every document.  Returns count of docs updated.
    """
    doc_dir = Path(knowledge_doc_dir)
    meta_path = doc_dir / "_metadata.json"
    if not meta_path.exists():
        return 0

    now = datetime.now(timezone.utc)

    with metadata_lock:
        # Re-read inside lock to avoid TOCTOU
        if not meta_path.exists():
            return 0
        try:
            data = json.loads(meta_path.read_text())
            docs = [KnowledgeDocument.model_validate(d) for d in data]
        except Exception:
            logger.warning("[knowledge_docs] Failed to parse _metadata.json for embedded status")
            return 0

        for doc in docs:
            doc.is_embedded = True
            doc.last_embedded_at = now

        tmp = meta_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([d.model_dump(mode="json") for d in docs], indent=2, default=str)
        )
        tmp.replace(meta_path)

    logger.info("[knowledge_docs] Marked %d docs as embedded in %s", len(docs), doc_dir)
    return len(docs)
