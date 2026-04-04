"""ORM model for the content inventory — universal content registry.

CMS-agnostic registry of all known published content pages for a company.
Populated by multiple ingestion sources (crawl, CMS, CSV, content engine).
Deduplicated on normalized URL per company.

Used by:
- Topic Discovery: cannibalization detection on topic assignments
- Gap Analysis: "optimize existing" vs "create new" classification
- Content Engine: existing content context in briefs
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.enums import ContentIngestionSource


class ContentInventoryModel(UUIDPKMixin, TimestampMixin, Base):
    """CMS-agnostic registry of all known published content pages for a company.

    The canonical source for "what has this company already published?"
    Deduplicated on (company_id, url_normalized).
    """

    __tablename__ = "content_inventory"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "url_normalized",
            name="uq_content_inventory_company_url",
        ),
        Index("ix_content_inv_company", "company_id"),
        Index("ix_content_inv_company_source", "company_id", "ingestion_source"),
        Index("ix_content_inv_effective_slug", "effective_slug"),
    )

    # ── Company scope ─────────────────────────────────────────────
    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    effective_slug: Mapped[str] = mapped_column(String, nullable=False)

    # ── Page identity ─────────────────────────────────────────────
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_normalized: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Lowercase, no trailing slash, no fragment, no query params. Dedup key.",
    )
    slug: Mapped[str] = mapped_column(
        String(512), default="", server_default="",
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    h1_text: Mapped[str] = mapped_column(
        String(512), default="", server_default="",
    )
    meta_description: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )

    # ── Content summary ───────────────────────────────────────────
    content_preview: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
        comment="First ~500 chars of plaintext content, HTML stripped.",
    )
    word_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )

    # ── Taxonomy / classification ─────────────────────────────────
    categories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    detected_primary_topic: Mapped[str] = mapped_column(
        String(255),
        default="",
        server_default="",
        comment="LLM-detected or keyword-extracted primary topic. Populated async.",
    )

    # ── SEO metadata ──────────────────────────────────────────────
    seo_title: Mapped[str] = mapped_column(
        String(512), default="", server_default="",
    )
    seo_description: Mapped[str] = mapped_column(
        Text, default="", server_default="",
    )

    # ── Timestamps ────────────────────────────────────────────────
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    content_modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last modified date from CMS or sitemap lastmod.",
    )
    last_crawled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When we last fetched/verified this page.",
    )

    # ── Embedding ─────────────────────────────────────────────────
    embedding: Mapped[Any] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="Page-level embedding of title + content_preview. For cannibalization similarity.",
    )

    # ── Ingestion provenance ──────────────────────────────────────
    ingestion_source: Mapped[ContentIngestionSource] = mapped_column(
        PgEnum(
            ContentIngestionSource,
            name="content_ingestion_source_enum",
            create_type=False,
        ),
        nullable=False,
    )
    ingestion_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=True,
        comment="pipeline_runs.id that discovered this page (site_audit or gap_analysis run).",
    )

    # ── Structural signals (from Site Audit S2) ───────────────────
    has_faq_section: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    has_schema_markup: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )
    heading_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
    )
    content_type_detected: Mapped[str] = mapped_column(
        String(50),
        default="",
        server_default="",
        comment="blog_post, landing_page, docs, glossary, etc.",
    )

    # ── Cannibalization analysis ──────────────────────────────────
    cannibalization_cluster_id: Mapped[str] = mapped_column(
        String(255),
        default="",
        server_default="",
        comment="Cluster label if this page was grouped with similar inventory pages.",
    )
