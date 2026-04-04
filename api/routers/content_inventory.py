"""Content Inventory API endpoints.

Auth: All endpoints require authentication + tenant isolation.
Write operations require ``member`` or ``superuser`` role.

7 endpoints:
  GET    /                    List inventory (paginated, filterable)
  GET    /stats               Aggregate stats for company
  GET    /{inventory_id}      Get single record
  POST   /import              CSV upload import
  POST   /import-url          Single URL manual registration
  POST   /generate-embeddings Trigger embedding generation
  DELETE /                    Clear all inventory for company
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from api.auth.dependencies import require_auth, require_role
from api.dependencies import get_auth_service, get_content_inventory_service
from api.schemas.content_inventory import (
    ContentInventoryItem,
    ContentInventoryListResponse,
    ContentInventoryStats,
    CSVImportResponse,
    GenerateEmbeddingsResponse,
    SingleURLImportRequest,
)
from core.auth.service import AuthServiceProtocol
from core.db.enums import ContentIngestionSource
from core.models.organization import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/content-inventory", tags=["content-inventory"])

_MAX_PAGE_SIZE = 200
_MAX_CSV_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Helpers ───────────────────────────────────────────────────────────


def _get_company_slug(request: Request) -> str:
    """Extract company_slug from authenticated request state."""
    slug: Optional[str] = getattr(request.state, "company_slug", None)
    if not slug:
        raise HTTPException(status_code=403, detail="Access denied")
    return slug


def _model_to_item(model: Any) -> ContentInventoryItem:
    """Convert an ORM model to a response schema."""
    return ContentInventoryItem(
        id=str(model.id),
        url=model.url or "",
        url_normalized=model.url_normalized or "",
        title=model.title or "",
        h1_text=model.h1_text or "",
        meta_description=model.meta_description or "",
        content_preview=model.content_preview or "",
        word_count=model.word_count or 0,
        ingestion_source=(
            model.ingestion_source.value
            if hasattr(model.ingestion_source, "value")
            else str(model.ingestion_source or "")
        ),
        categories=model.categories or [],
        tags=model.tags or [],
        content_type_detected=model.content_type_detected or "",
        has_faq_section=model.has_faq_section or False,
        has_schema_markup=model.has_schema_markup or False,
        heading_count=model.heading_count or 0,
        has_embedding=model.embedding is not None,
        published_at=model.published_at,
        content_modified_at=model.content_modified_at,
        last_crawled_at=model.last_crawled_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _parse_source_filter(source: Optional[str]) -> ContentIngestionSource | None:
    """Validate and parse source filter query param."""
    if not source:
        return None
    try:
        return ContentIngestionSource(source)
    except ValueError:
        valid = [e.value for e in ContentIngestionSource]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source filter '{source}'. Valid values: {valid}",
        )


# ── 1. List Inventory ─────────────────────────────────────────────────


@router.get("/", response_model=ContentInventoryListResponse)
async def list_inventory(
    http_request: Request,
    page: int = 1,
    page_size: int = 50,
    source: Optional[str] = None,
    _user: UserProfile = Depends(require_auth),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentInventoryListResponse:
    """List content inventory records (paginated, filterable by source)."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Validate pagination
    page = max(1, page)
    page_size = max(1, min(page_size, _MAX_PAGE_SIZE))
    offset = (page - 1) * page_size

    ingestion_source = _parse_source_filter(source)

    items, total = await inventory_service._repo.get_by_company(
        company.id,
        ingestion_source=ingestion_source,
        limit=page_size,
        offset=offset,
    )

    return ContentInventoryListResponse(
        items=[_model_to_item(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── 2. Stats ──────────────────────────────────────────────────────────


@router.get("/stats", response_model=ContentInventoryStats)
async def get_stats(
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentInventoryStats:
    """Aggregate stats for the company's content inventory."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    stats = await inventory_service._repo.get_stats(company.id)
    return ContentInventoryStats(**stats)


# ── 3. Single Record ─────────────────────────────────────────────────


@router.get("/{inventory_id}", response_model=ContentInventoryItem)
async def get_inventory_item(
    inventory_id: str,
    http_request: Request,
    _user: UserProfile = Depends(require_auth),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentInventoryItem:
    """Get a single content inventory record."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        model = await inventory_service._repo.get_by_id(inventory_id)
    except (ValueError, Exception):
        raise HTTPException(status_code=400, detail="Invalid inventory ID format")
    if model is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    # Tenant isolation
    if model.company_id != company.id:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    return _model_to_item(model)


# ── 4. CSV Import ────────────────────────────────────────────────────


@router.post("/import", response_model=CSVImportResponse)
async def import_csv(
    http_request: Request,
    file: UploadFile,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> CSVImportResponse:
    """Import content inventory from a CSV file."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Read and parse CSV (bounded)
    content = await file.read(_MAX_CSV_SIZE_BYTES + 1)
    if len(content) > _MAX_CSV_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="CSV file exceeds 10 MB limit")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV")

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return CSVImportResponse(imported=0, skipped=0, errors=["Empty CSV file"])

    result = await inventory_service.ingest_from_csv(
        company_id=company.id,
        effective_slug=company_slug,
        csv_rows=rows,
    )

    return CSVImportResponse(**result)


# ── 5. Single URL Import ────────────────────────────────────────────


@router.post("/import-url", response_model=ContentInventoryItem)
async def import_url(
    body: SingleURLImportRequest,
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> ContentInventoryItem:
    """Register a single URL into the content inventory.

    Phase 2: Registers URL + title only (no URL fetching/scraping).
    """
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if not body.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    model = await inventory_service._repo.upsert_page(
        company_id=company.id,
        effective_slug=company_slug,
        url=body.url.strip(),
        title=body.title.strip() or body.url.strip(),
        ingestion_source=ContentIngestionSource.manual,
    )

    return _model_to_item(model)


# ── 6. Generate Embeddings ───────────────────────────────────────────


@router.post("/generate-embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(
    http_request: Request,
    _user: UserProfile = Depends(require_role("member", "superuser")),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> GenerateEmbeddingsResponse:
    """Trigger embedding generation for inventory records missing embeddings."""
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    count = await inventory_service.generate_embeddings_for_company(company.id)

    return GenerateEmbeddingsResponse(
        generated=count,
        message=f"Generated {count} embeddings" if count else "All records already have embeddings",
    )


# ── 7. Delete All ───────────────────────────────────────────────────


@router.delete("/")
async def delete_inventory(
    http_request: Request,
    _user: UserProfile = Depends(require_role("superuser")),
    inventory_service: Any = Depends(get_content_inventory_service),
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> dict[str, int]:
    """Delete all content inventory records for the company.

    Restricted to superuser role.
    """
    company_slug = _get_company_slug(http_request)
    company = await auth_service.get_company_by_slug(company_slug)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    count = await inventory_service._repo.delete_by_company(company.id)
    return {"deleted": count}
