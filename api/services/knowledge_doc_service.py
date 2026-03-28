"""Knowledge document upload, storage, and retrieval service.

All binary I/O goes through ``StorageBackend`` so the service works with
both local filesystem (dev) and Cloudflare R2 (production).

Phase 6 (R2 migration): replaced direct ``Path`` operations with
StorageBackend calls.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import UploadFile

from core.models.knowledge_docs import KnowledgeDocument
from core.shared_tools.knowledge_doc_metadata import (
    doc_storage_key,
    load_metadata,
    metadata_lock,
    save_metadata,
)
from core.shared_tools.text_extraction import extract_text_from_bytes
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")

# MIME type mapping for supported file extensions
_EXTENSION_CONTENT_TYPE = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_EXTENSIONS = frozenset(_EXTENSION_CONTENT_TYPE.keys())
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_slug(slug: str) -> None:
    if not _SLUG_PATTERN.match(slug):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid slug format")


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename: strip path components, reject traversal."""
    # Take only the final component (no directory paths)
    name = Path(filename).name
    # Remove any remaining suspicious characters
    name = re.sub(r"[^\w\-.]", "_", name)
    return name


def _count_words(text: str) -> int:
    return len(text.split())


def _persist_upload_sync(
    storage: StorageBackend,
    effective_slug: str,
    stored_filename: str,
    content: bytes,
    doc: KnowledgeDocument,
) -> None:
    """Write blob + update metadata under lock (sync, runs via asyncio.to_thread).

    H6-fix: keeps blocking I/O and the threading.Lock off the event loop.
    """
    storage.write_bytes(doc_storage_key(effective_slug, stored_filename), content)
    with metadata_lock:
        docs = load_metadata(effective_slug, storage=storage)
        docs.append(doc)
        save_metadata(effective_slug, docs, storage=storage)


async def upload_document(
    storage: StorageBackend,
    effective_slug: str,
    company_slug: str,
    product_slug: Optional[str],
    file: UploadFile,
    uploaded_by: Optional[str] = None,
    max_size_bytes: Optional[int] = None,
) -> KnowledgeDocument:
    """Upload a knowledge document. Returns metadata."""
    _validate_slug(effective_slug)

    # Validate filename
    if not file.filename:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Filename is required")

    safe_name = _sanitize_filename(file.filename)
    suffix = Path(safe_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read content and check size
    effective_max = max_size_bytes if max_size_bytes is not None else DEFAULT_MAX_UPLOAD_BYTES
    content = await file.read()
    if len(content) > effective_max:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"File too large ({len(content)} bytes). Max: {effective_max} bytes",
        )

    # Ensure storage prefix exists (no-op for R2)
    storage.mkdir(f"knowledge_docs/{effective_slug}")

    # Generate collision-safe stored filename
    doc_id = str(uuid4())
    stored_filename = f"{doc_id}_{safe_name}"

    # Extract text for word count (bytes already in memory — no read-back needed)
    text = extract_text_from_bytes(content, suffix)
    word_count = _count_words(text) if text else 0

    # Create metadata entry
    doc = KnowledgeDocument(
        id=doc_id,
        filename=safe_name,
        stored_filename=stored_filename,
        content_type=_EXTENSION_CONTENT_TYPE.get(suffix, "application/octet-stream"),
        file_size_bytes=len(content),
        word_count=word_count,
        uploaded_by=uploaded_by,
        company_slug=company_slug,
        product_slug=product_slug,
        effective_slug=effective_slug,
    )

    # H6-fix: run blocking I/O (write_bytes + metadata lock) off the event loop
    await asyncio.to_thread(
        _persist_upload_sync, storage, effective_slug, stored_filename, content, doc
    )

    return doc


def list_documents(
    effective_slug: str, *, storage: StorageBackend
) -> List[KnowledgeDocument]:
    """List all knowledge documents for an effective slug."""
    _validate_slug(effective_slug)
    return load_metadata(effective_slug, storage=storage)


def get_document(
    effective_slug: str, doc_id: str, *, storage: StorageBackend
) -> Optional[KnowledgeDocument]:
    """Get a single knowledge document by ID."""
    docs = load_metadata(effective_slug, storage=storage)
    for d in docs:
        if d.id == doc_id:
            return d
    return None


def get_document_key(
    effective_slug: str, doc_id: str, *, storage: StorageBackend
) -> Optional[str]:
    """Get the storage key of a stored document. Returns None if not found."""
    doc = get_document(effective_slug, doc_id, storage=storage)
    if not doc:
        return None
    key = doc_storage_key(effective_slug, doc.stored_filename)
    if storage.exists(key):
        return key
    return None


def delete_document(
    effective_slug: str, doc_id: str, *, storage: StorageBackend
) -> bool:
    """Delete a knowledge document (blob + metadata entry). Returns True if deleted."""
    _validate_slug(effective_slug)

    with metadata_lock:
        docs = load_metadata(effective_slug, storage=storage)
        target = None
        remaining = []
        for d in docs:
            if d.id == doc_id:
                target = d
            else:
                remaining.append(d)

        if not target:
            return False

        # Remove blob from StorageBackend
        storage.delete(doc_storage_key(effective_slug, target.stored_filename))

        save_metadata(effective_slug, remaining, storage=storage)

    return True
