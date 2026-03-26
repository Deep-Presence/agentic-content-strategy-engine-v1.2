"""Knowledge document upload and management endpoints.

Upload internal docs (product one-pagers, competitive analyses, etc.) that
get embedded alongside public site content in the s1 pipeline step.

Phase 6 (R2 migration): all I/O goes through StorageBackend.
``FileResponse`` replaced with ``Response`` for downloads.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple, TypeVar

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile

from api.auth.dependencies import require_company_member, require_tenant
from api.dependencies import get_storage_backend
from api.schemas.knowledge_docs import (
    KnowledgeDocListResponse,
    KnowledgeDocResponse,
)
from api.services import knowledge_doc_service as svc
from core.models.knowledge_docs import KnowledgeDocument
from core.models.organization import Company, UserProfile
from core.storage.backends.base import StorageBackend

router = APIRouter(
    prefix="/api/v1/companies/{slug}/knowledge-docs",
    tags=["knowledge-docs"],
)

T = TypeVar("T")


def _effective_slug(slug: str, product_slug: Optional[str]) -> str:
    if product_slug:
        return f"{slug}__{product_slug}"
    return slug


def _doc_to_response(doc: KnowledgeDocument) -> KnowledgeDocResponse:
    return KnowledgeDocResponse(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        file_size_bytes=doc.file_size_bytes,
        word_count=doc.word_count,
        uploaded_at=doc.uploaded_at,
        is_embedded=doc.is_embedded,
        last_embedded_at=doc.last_embedded_at,
    )


def _find_across_product_slugs(
    storage: StorageBackend,
    slug: str,
    lookup_fn: Callable[[StorageBackend, str], Optional[T]],
) -> Optional[T]:
    """Search for a resource across company-level and all product-level slugs.

    Tries the bare company slug first, then scans all ``{slug}__*`` product
    directories via ``StorageBackend.list_dir()``.
    """
    # 1. Try bare company slug
    result = lookup_fn(storage, slug)
    if result:
        return result

    # 2. Scan product-level dirs
    entries = storage.list_dir("knowledge_docs")
    for entry in sorted(entries):
        # entry is like "knowledge_docs/slug__product" — extract last component
        entry_name = entry.rstrip("/").rsplit("/", 1)[-1]
        if entry_name.startswith(f"{slug}__"):
            result = lookup_fn(storage, entry_name)
            if result:
                return result

    return None


@router.post("", response_model=KnowledgeDocResponse, status_code=201)
async def upload_knowledge_doc(
    slug: str,
    file: UploadFile = File(...),
    product_slug: Optional[str] = Query(default=None),
    user_company: Tuple[UserProfile, Company] = Depends(require_company_member),
    storage: StorageBackend = Depends(get_storage_backend),
) -> KnowledgeDocResponse:
    """Upload a knowledge document (PDF, Markdown, TXT, DOCX)."""
    user, _ = user_company
    eff_slug = _effective_slug(slug, product_slug)
    doc = await svc.upload_document(
        storage=storage,
        effective_slug=eff_slug,
        company_slug=slug,
        product_slug=product_slug,
        file=file,
        uploaded_by=user.id,
    )
    return _doc_to_response(doc)


@router.get("", response_model=KnowledgeDocListResponse)
def list_knowledge_docs(
    slug: str,
    product_slug: Optional[str] = Query(default=None),
    _user: UserProfile = Depends(require_tenant),
    storage: StorageBackend = Depends(get_storage_backend),
) -> KnowledgeDocListResponse:
    """List all knowledge documents for this company/product."""
    eff_slug = _effective_slug(slug, product_slug)
    docs = svc.list_documents(eff_slug, storage=storage)
    return KnowledgeDocListResponse(
        documents=[_doc_to_response(d) for d in docs],
        total=len(docs),
    )


@router.get("/{doc_id}", response_model=KnowledgeDocResponse)
def get_knowledge_doc(
    slug: str,
    doc_id: str,
    _user: UserProfile = Depends(require_tenant),
    storage: StorageBackend = Depends(get_storage_backend),
) -> KnowledgeDocResponse:
    """Get metadata for a single knowledge document."""
    doc = _find_across_product_slugs(
        storage,
        slug,
        lambda s, es: svc.get_document(es, doc_id, storage=s),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_knowledge_doc(
    slug: str,
    doc_id: str,
    user_company: Tuple[UserProfile, Company] = Depends(require_company_member),
    storage: StorageBackend = Depends(get_storage_backend),
) -> None:
    """Delete a knowledge document."""
    deleted = _find_across_product_slugs(
        storage,
        slug,
        lambda s, es: svc.delete_document(es, doc_id, storage=s) or None,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/{doc_id}/download")
def download_knowledge_doc(
    slug: str,
    doc_id: str,
    _user: UserProfile = Depends(require_tenant),
    storage: StorageBackend = Depends(get_storage_backend),
) -> Response:
    """Download a knowledge document file."""
    key = _find_across_product_slugs(
        storage,
        slug,
        lambda s, es: svc.get_document_key(es, doc_id, storage=s),
    )
    if not key:
        raise HTTPException(status_code=404, detail="Document not found")

    data = storage.read_bytes(key)
    if data is None:
        raise HTTPException(status_code=404, detail="Document file not found")

    # Get doc metadata for the original filename and content type
    doc = _find_across_product_slugs(
        storage,
        slug,
        lambda s, es: svc.get_document(es, doc_id, storage=s),
    )
    filename = doc.filename if doc else key.rsplit("/", 1)[-1]
    content_type = doc.content_type if doc else "application/octet-stream"

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
