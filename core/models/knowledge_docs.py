"""Knowledge document metadata model.

Tracks uploaded internal documents that get embedded alongside
public site content in the s1 pipeline step.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class KnowledgeDocument(BaseModel):
    """Metadata for an uploaded knowledge document."""

    id: str = Field(default_factory=_uuid)
    filename: str  # original filename from user
    stored_filename: str  # uuid_filename on disk (collision-safe)
    content_type: str = ""  # MIME type (e.g., "text/markdown")
    file_size_bytes: int = 0
    word_count: int = 0
    uploaded_at: datetime = Field(default_factory=_utcnow)
    uploaded_by: Optional[str] = None  # user_id
    company_slug: str = ""
    product_slug: Optional[str] = None
    effective_slug: str = ""
    is_embedded: bool = False
    last_embedded_at: Optional[datetime] = None
