"""Content Inventory request/response schemas.

Response fields have defaults for backward compatibility (Pydantic v2 strict).
Request fields may require values (e.g. URL for import).
UUIDs are serialized as ``str`` (D2: UUIDPKMixin).
Embedding vector excluded from API responses (too large).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────────────────


class SingleURLImportRequest(BaseModel):
    """Register a single URL into the content inventory."""

    url: str
    title: str = ""


# ── Response Schemas ─���─────────────────────────────────────────��──────


class ContentInventoryItem(BaseModel):
    """Single content inventory record."""

    id: str = ""  # UUID string
    url: str = ""
    url_normalized: str = ""
    title: str = ""
    h1_text: str = ""
    meta_description: str = ""
    content_preview: str = ""
    word_count: int = 0
    ingestion_source: str = ""
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    content_type_detected: str = ""
    has_faq_section: bool = False
    has_schema_markup: bool = False
    heading_count: int = 0
    has_embedding: bool = False
    published_at: Optional[datetime] = None
    content_modified_at: Optional[datetime] = None
    last_crawled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ContentInventoryListResponse(BaseModel):
    """Paginated content inventory list."""

    items: list[ContentInventoryItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class ContentInventoryStats(BaseModel):
    """Aggregate stats for a company's content inventory."""

    total_pages: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    avg_word_count: float = 0.0
    pages_with_embeddings: int = 0
    oldest_content: Optional[datetime] = None
    newest_content: Optional[datetime] = None


class CSVImportResponse(BaseModel):
    """Result of a CSV import operation."""

    imported: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class GenerateEmbeddingsResponse(BaseModel):
    """Result of embedding generation trigger."""

    generated: int = 0
    message: str = ""
