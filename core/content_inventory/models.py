"""Pydantic DTOs for the content inventory module.

These lightweight models serve as the data transfer layer between ingestion
sources (site audit, CMS sync, CSV import) and the content inventory
repository / service.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CrawledPageData(BaseModel):
    """Lightweight DTO for site audit -> inventory ingestion."""

    url: str
    title: str = ""
    h1_text: str = ""
    meta_description: str = ""
    content_preview: str = ""
    word_count: int = 0
    has_faq_section: bool = False
    has_schema_markup: bool = False
    heading_count: int = 0
    content_type_detected: str = ""
    sitemap_lastmod: str | None = None


class CannibalizationMatch(BaseModel):
    """Result of a cannibalization check against existing inventory."""

    inventory_id: str
    url: str
    title: str
    similarity: float
    word_count: int = 0
    content_preview: str = ""
    content_type_detected: str = ""


class ExistingCoverageResult(BaseModel):
    """Existing content that covers a query/topic."""

    inventory_id: str
    url: str
    title: str
    similarity: float
    word_count: int = 0
    content_preview: str = ""
    categories: list[str] = Field(default_factory=list)
    content_modified_at: str | None = None
