"""Knowledge document upload, storage, and retrieval service.

File-backed service following the same patterns as gap_data_service.py.
Documents stored in artifacts/knowledge_docs/{effective_slug}/ with a
_metadata.json sidecar for tracking.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import UploadFile

from core.models.knowledge_docs import KnowledgeDocument
from core.shared_tools.knowledge_doc_metadata import (
    load_metadata,
    metadata_lock,
    save_metadata,
    slug_dir,
)
from core.shared_tools.text_extraction import extract_text

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


async def upload_document(
    artifacts_root: Path,
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

    # Create storage directory
    doc_dir = slug_dir(artifacts_root, effective_slug)
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Generate collision-safe stored filename
    doc_id = str(uuid4())
    stored_filename = f"{doc_id}_{safe_name}"
    stored_path = doc_dir / stored_filename

    # Path traversal check
    if not stored_path.resolve().is_relative_to(doc_dir.resolve()):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid filename")

    # Write file to disk
    stored_path.write_bytes(content)

    # Extract text for word count
    text = extract_text(stored_path)
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

    # Persist metadata (shared lock coordinates with s1 mark-as-embedded)
    with metadata_lock:
        docs = load_metadata(artifacts_root, effective_slug)
        docs.append(doc)
        save_metadata(artifacts_root, effective_slug, docs)

    return doc


def list_documents(
    artifacts_root: Path, effective_slug: str
) -> List[KnowledgeDocument]:
    """List all knowledge documents for an effective slug."""
    _validate_slug(effective_slug)
    return load_metadata(artifacts_root, effective_slug)


def get_document(
    artifacts_root: Path, effective_slug: str, doc_id: str
) -> Optional[KnowledgeDocument]:
    """Get a single knowledge document by ID."""
    docs = load_metadata(artifacts_root, effective_slug)
    for d in docs:
        if d.id == doc_id:
            return d
    return None


def get_document_path(
    artifacts_root: Path, effective_slug: str, doc_id: str
) -> Optional[Path]:
    """Get the filesystem path of a stored document."""
    doc = get_document(artifacts_root, effective_slug, doc_id)
    if not doc:
        return None
    path = slug_dir(artifacts_root, effective_slug) / doc.stored_filename
    if path.exists():
        return path
    return None


def delete_document(
    artifacts_root: Path, effective_slug: str, doc_id: str
) -> bool:
    """Delete a knowledge document (file + metadata entry). Returns True if deleted."""
    _validate_slug(effective_slug)

    with metadata_lock:
        docs = load_metadata(artifacts_root, effective_slug)
        target = None
        remaining = []
        for d in docs:
            if d.id == doc_id:
                target = d
            else:
                remaining.append(d)

        if not target:
            return False

        # Remove file from disk
        file_path = slug_dir(artifacts_root, effective_slug) / target.stored_filename
        if file_path.exists():
            file_path.unlink()

        save_metadata(artifacts_root, effective_slug, remaining)

    return True
