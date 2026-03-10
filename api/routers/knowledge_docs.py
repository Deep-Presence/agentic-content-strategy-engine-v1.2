"""Knowledge document upload and management endpoints.

Upload internal docs (product one-pagers, competitive analyses, etc.) that
get embedded alongside public site content in the s1 pipeline step.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Tuple, TypeVar

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from api.auth.dependencies import require_company_member, require_tenant
from api.dependencies import get_artifacts_root
from api.schemas.knowledge_docs import (
    KnowledgeDocListResponse,
    KnowledgeDocResponse,
)
from api.services import knowledge_doc_service as svc
from core.models.knowledge_docs import KnowledgeDocument
from core.models.organization import Company, UserProfile

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
    artifacts_root: Path,
    slug: str,
    lookup_fn: Callable[[Path, str], Optional[T]],
) -> Optional[T]:
    """Search for a resource across company-level and all product-level slugs.

    Tries the bare company slug first, then scans all ``{slug}__*`` product
    directories.  ``lookup_fn(artifacts_root, effective_slug)`` should return
    a truthy result on success or None on miss.
    """
    # 1. Try bare company slug
    result = lookup_fn(artifacts_root, slug)
    if result:
        return result

    # 2. Scan product-level dirs
    kdocs_root = artifacts_root / "knowledge_docs"
    if kdocs_root.is_dir():
        for subdir in sorted(kdocs_root.iterdir()):
            if subdir.is_dir() and (
                subdir.name == slug or subdir.name.startswith(f"{slug}__")
            ):
                result = lookup_fn(artifacts_root, subdir.name)
                if result:
                    return result

    return None


@router.post("", response_model=KnowledgeDocResponse, status_code=201)
async def upload_knowledge_doc(
    slug: str,
    file: UploadFile = File(...),
    product_slug: Optional[str] = Query(default=None),
    user_company: Tuple[UserProfile, Company] = Depends(require_company_member),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> KnowledgeDocResponse:
    """Upload a knowledge document (PDF, Markdown, TXT, DOCX)."""
    user, _ = user_company
    eff_slug = _effective_slug(slug, product_slug)
    doc = await svc.upload_document(
        artifacts_root=artifacts_root,
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
    artifacts_root: Path = Depends(get_artifacts_root),
) -> KnowledgeDocListResponse:
    """List all knowledge documents for this company/product."""
    eff_slug = _effective_slug(slug, product_slug)
    docs = svc.list_documents(artifacts_root, eff_slug)
    return KnowledgeDocListResponse(
        documents=[_doc_to_response(d) for d in docs],
        total=len(docs),
    )


@router.get("/{doc_id}", response_model=KnowledgeDocResponse)
def get_knowledge_doc(
    slug: str,
    doc_id: str,
    _user: UserProfile = Depends(require_tenant),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> KnowledgeDocResponse:
    """Get metadata for a single knowledge document."""
    doc = _find_across_product_slugs(
        artifacts_root,
        slug,
        lambda root, es: svc.get_document(root, es, doc_id),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_knowledge_doc(
    slug: str,
    doc_id: str,
    user_company: Tuple[UserProfile, Company] = Depends(require_company_member),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> None:
    """Delete a knowledge document."""
    deleted = _find_across_product_slugs(
        artifacts_root,
        slug,
        lambda root, es: svc.delete_document(root, es, doc_id) or None,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/{doc_id}/download")
def download_knowledge_doc(
    slug: str,
    doc_id: str,
    _user: UserProfile = Depends(require_tenant),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> FileResponse:
    """Download a knowledge document file."""
    file_path = _find_across_product_slugs(
        artifacts_root,
        slug,
        lambda root, es: svc.get_document_path(root, es, doc_id),
    )
    if not file_path:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get doc metadata for the original filename
    doc = _find_across_product_slugs(
        artifacts_root,
        slug,
        lambda root, es: svc.get_document(root, es, doc_id),
    )
    filename = doc.filename if doc else file_path.name
    return FileResponse(path=str(file_path), filename=filename)
