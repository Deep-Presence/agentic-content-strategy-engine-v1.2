"""Platform result & URL enrichment cache ORM models."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, UUIDPKMixin
from core.db.enums import SearchEngine


# ── Platform Result Cache ────────────────────────────────────────────────


class PlatformResultCacheModel(UUIDPKMixin, Base):
    __tablename__ = "platform_result_cache"
    __table_args__ = (
        UniqueConstraint(
            "query_text_hash", "engine", name="uq_platform_cache_hash_engine"
        ),
        Index(
            "ix_platform_cache_hash_engine_fetched",
            "query_text_hash",
            "engine",
            "fetched_at",
        ),
    )

    query_text_hash: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[SearchEngine] = mapped_column(
        PgEnum(SearchEngine, name="search_engine_enum", create_type=True),
        nullable=False,
    )
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── URL Enrichment Cache ─────────────────────────────────────────────────


class UrlEnrichmentCacheModel(UUIDPKMixin, Base):
    __tablename__ = "url_enrichment_cache"
    __table_args__ = (
        Index("ix_url_enrichment_hash_scraped", "url_hash", "scraped_at"),
        Index("ix_url_enrichment_domain", "domain"),
    )

    url_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority_type: Mapped[str | None] = mapped_column(String, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    paragraph_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw_paragraphs_storage_key: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    structural_signals: Mapped[UrlStructuralSignalsModel | None] = relationship(
        "UrlStructuralSignalsModel",
        back_populates="url_enrichment",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ── URL Structural Signals (1:1 extension of UrlEnrichmentCache) ─────────


class UrlStructuralSignalsModel(Base):
    """45 structural signal columns — 1:1 with url_enrichment_cache.

    PK is ``url_enrichment_id`` itself (no UUIDPKMixin).
    """

    __tablename__ = "url_structural_signals"

    url_enrichment_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("url_enrichment_cache.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # ── Original signals (11) ────────────────────────────────────────────
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    paragraph_count: Mapped[int] = mapped_column(Integer, default=0)
    header_count: Mapped[int] = mapped_column(Integer, default=0)
    list_item_count: Mapped[int] = mapped_column(Integer, default=0)
    stat_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    has_headers: Mapped[bool] = mapped_column(Boolean, default=False)
    has_lists: Mapped[bool] = mapped_column(Boolean, default=False)
    has_numbers: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Category A: Content depth (9) ────────────────────────────────────
    main_content_word_count: Mapped[int] = mapped_column(Integer, default=0)
    sentence_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_paragraph_length: Mapped[float] = mapped_column(Float, default=0.0)
    median_paragraph_length: Mapped[float] = mapped_column(Float, default=0.0)
    max_paragraph_word_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentence_length: Mapped[float] = mapped_column(Float, default=0.0)
    avg_sentence_count_per_paragraph: Mapped[float] = mapped_column(
        Float, default=0.0
    )
    reading_level: Mapped[float] = mapped_column(Float, default=0.0)
    self_contained_ratio: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Category B: Structural elements (13) ─────────────────────────────
    h1_count: Mapped[int] = mapped_column(Integer, default=0)
    h2_count: Mapped[int] = mapped_column(Integer, default=0)
    h3_count: Mapped[int] = mapped_column(Integer, default=0)
    h4_count: Mapped[int] = mapped_column(Integer, default=0)
    ordered_list_count: Mapped[int] = mapped_column(Integer, default=0)
    unordered_list_count: Mapped[int] = mapped_column(Integer, default=0)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    definition_list_count: Mapped[int] = mapped_column(Integer, default=0)
    blockquote_count: Mapped[int] = mapped_column(Integer, default=0)
    code_block_count: Mapped[int] = mapped_column(Integer, default=0)
    list_block_count: Mapped[int] = mapped_column(Integer, default=0)
    bullets_per_list_block: Mapped[float] = mapped_column(Float, default=0.0)
    min_bullets_per_list: Mapped[int] = mapped_column(Integer, default=0)

    # ── Category C: AI-friendly patterns (8) ─────────────────────────────
    has_faq_section: Mapped[bool] = mapped_column(Boolean, default=False)
    has_definition_opening: Mapped[bool] = mapped_column(Boolean, default=False)
    has_key_takeaways: Mapped[bool] = mapped_column(Boolean, default=False)
    has_toc: Mapped[bool] = mapped_column(Boolean, default=False)
    has_comparison_table: Mapped[bool] = mapped_column(Boolean, default=False)
    has_step_by_step: Mapped[bool] = mapped_column(Boolean, default=False)
    has_research_refs: Mapped[bool] = mapped_column(Boolean, default=False)
    has_expert_quotes: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Category D: Data density (3) ─────────────────────────────────────
    data_point_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_density: Mapped[float] = mapped_column(Float, default=0.0)
    named_entity_density: Mapped[float] = mapped_column(Float, default=0.0)

    # relationships
    url_enrichment: Mapped[UrlEnrichmentCacheModel] = relationship(
        "UrlEnrichmentCacheModel", back_populates="structural_signals"
    )
