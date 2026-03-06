"""Request/response schemas for knowledge doc upload endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class KnowledgeDocResponse(BaseModel):
    """Single knowledge document metadata."""

    id: str
    filename: str
    content_type: str
    file_size_bytes: int
    word_count: int
    uploaded_at: datetime
    is_embedded: bool
    last_embedded_at: Optional[datetime] = None


class KnowledgeDocListResponse(BaseModel):
    """Response for GET /knowledge-docs."""

    documents: List[KnowledgeDocResponse]
    total: int
