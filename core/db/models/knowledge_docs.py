"""Knowledge document ORM models."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin


# ── Knowledge Documents ─────────────────────────────────────────────────


class KnowledgeDocumentModel(UUIDPKMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_documents_company_slug", "company_id", "effective_slug"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    last_embedded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
