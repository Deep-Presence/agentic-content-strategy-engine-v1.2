"""Gap-analysis domain models — queries, citations, gaps, exemplars, cluster specs, SPA & centroid."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.enums import GapClassification, SearchEngine


# ── Run Queries ──────────────────────────────────────────────────────────


class RunQueryModel(UUIDPKMixin, Base):
    """One generated search query belonging to a gap-analysis run."""

    __tablename__ = "run_queries"
    __table_args__ = (
        UniqueConstraint("run_id", "query_id", name="uq_run_queries_run_query"),
        Index("ix_run_queries_run_cluster", "run_id", "cluster_name"),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_id: Mapped[str] = mapped_column(String, nullable=False)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cluster_name: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    buyer_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    persona_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    source_topic_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Run Citations ────────────────────────────────────────────────────────


class RunCitationModel(UUIDPKMixin, Base):
    """A citation returned by a search engine for a specific query within a run."""

    __tablename__ = "run_citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "query_id"],
            ["run_queries.run_id", "run_queries.query_id"],
            name="fk_run_citations_run_query",
        ),
        Index("ix_run_citations_run_query", "run_id", "query_id"),
        Index("ix_run_citations_run_engine", "run_id", "engine"),
        Index("ix_run_citations_run_cluster", "run_id", "cluster_name"),
        Index("ix_run_citations_url_enrichment", "url_enrichment_id"),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_id: Mapped[str] = mapped_column(String, nullable=False)
    cluster_name: Mapped[str | None] = mapped_column(String, nullable=True)
    engine: Mapped[SearchEngine] = mapped_column(
        PgEnum(SearchEngine, name="search_engine_enum", create_type=True),
        nullable=False,
    )
    url_enrichment_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("url_enrichment_cache.id"),
        nullable=True,
    )
    citation_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    is_company_citation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Query Gaps ───────────────────────────────────────────────────────────


class QueryGapModel(UUIDPKMixin, TimestampMixin, Base):
    """Computed gap for a single query within a gap-analysis run."""

    __tablename__ = "query_gaps"
    __table_args__ = (
        UniqueConstraint("run_id", "query_id", name="uq_query_gaps_run_query"),
        Index("ix_query_gaps_run_classification", "run_id", "classification"),
        Index("ix_query_gaps_run_cluster", "run_id", "cluster_name"),
        Index(
            "ix_query_gaps_targeted",
            "targeted_by_content_id",
            postgresql_where="targeted_by_content_id IS NOT NULL",
        ),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_id: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_name: Mapped[str] = mapped_column(String, nullable=False)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    avg_citation_similarity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    best_company_similarity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    best_company_unit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    best_company_unit_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_company_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_company_structural_signals: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    company_cited: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    gap: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[GapClassification] = mapped_column(
        PgEnum(GapClassification, name="gap_classification_enum", create_type=True),
        nullable=False,
    )
    content_brief: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_topic_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    targeted_by_content_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("content_pieces.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refreshed_by_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )

    # relationships
    exemplars: Mapped[list[QueryExemplarModel]] = relationship(
        "QueryExemplarModel",
        back_populates="query_gap",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ── Query Exemplars ──────────────────────────────────────────────────────


class QueryExemplarModel(UUIDPKMixin, Base):
    """Top-cited exemplar URL for a specific query gap."""

    __tablename__ = "query_exemplars"
    __table_args__ = (Index("ix_query_exemplars_gap", "query_gap_id"),)

    query_gap_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("query_gaps.id", ondelete="CASCADE"),
        nullable=False,
    )
    url_enrichment_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("url_enrichment_cache.id"),
        nullable=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority_type: Mapped[str | None] = mapped_column(String, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    # relationships
    query_gap: Mapped[QueryGapModel] = relationship(
        "QueryGapModel", back_populates="exemplars"
    )
    url_enrichment: Mapped["UrlEnrichmentCacheModel | None"] = relationship(
        "UrlEnrichmentCacheModel", lazy="select",
    )


# ── Cluster Specs ────────────────────────────────────────────────────────


class ClusterSpecModel(UUIDPKMixin, TimestampMixin, Base):
    """Computed structural specification for a query cluster."""

    __tablename__ = "cluster_specs"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "cluster_name", name="uq_cluster_specs_run_cluster"
        ),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cluster_name: Mapped[str] = mapped_column(String, nullable=False)
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    total_citations_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    min_similarity_threshold: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    word_count_min: Mapped[int] = mapped_column(Integer, default=0)
    word_count_max: Mapped[int] = mapped_column(Integer, default=0)
    avg_word_count: Mapped[float] = mapped_column(Float, default=0.0)
    avg_paragraph_word_count: Mapped[float] = mapped_column(Float, default=0.0)
    avg_sentence_count_per_paragraph: Mapped[float] = mapped_column(
        Float, default=0.0
    )
    min_bullets_per_list: Mapped[int] = mapped_column(Integer, default=0)
    faq_rate: Mapped[float] = mapped_column(Float, default=0.0)
    table_rate: Mapped[float] = mapped_column(Float, default=0.0)
    definition_rate: Mapped[float] = mapped_column(Float, default=0.0)
    code_block_rate: Mapped[float] = mapped_column(Float, default=0.0)
    key_takeaways_rate: Mapped[float] = mapped_column(Float, default=0.0)
    dominant_content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    dominant_authority_type: Mapped[str | None] = mapped_column(String, nullable=True)
    required_elements: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    structural_rates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exemplar_themes: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )


# ── SPA Results ──────────────────────────────────────────────────────────


class SpaResultModel(UUIDPKMixin, Base):
    """Semantic Proximity Analysis result per cluster."""

    __tablename__ = "spa_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "cluster_name", name="uq_spa_results_run_cluster"
        ),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cluster_name: Mapped[str] = mapped_column(String, nullable=False)
    t_stat: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_citation_similarity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    mean_company_similarity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    effect: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Centroid Results ─────────────────────────────────────────────────────


class CentroidResultModel(UUIDPKMixin, Base):
    """Company-to-citation centroid distance per cluster."""

    __tablename__ = "centroid_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "cluster_name", name="uq_centroid_results_run_cluster"
        ),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_name: Mapped[str] = mapped_column(String, nullable=False)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Cluster Proximity Stats ────────────────────────────────────────────


class ClusterProximityStatsModel(UUIDPKMixin, Base):
    """Per-cluster (and global) citation/company proximity statistics."""

    __tablename__ = "cluster_proximity_stats"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "cluster_name", name="uq_cluster_proximity_run_cluster"
        ),
        Index("ix_cluster_proximity_stats_run", "run_id"),
    )

    run_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_name: Mapped[str] = mapped_column(String, nullable=False)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    citation_mean: Mapped[float] = mapped_column(Float, default=0.0)
    citation_std: Mapped[float] = mapped_column(Float, default=0.0)
    citation_min: Mapped[float] = mapped_column(Float, default=0.0)
    citation_max: Mapped[float] = mapped_column(Float, default=0.0)
    citation_median: Mapped[float] = mapped_column(Float, default=0.0)
    company_mean: Mapped[float] = mapped_column(Float, default=0.0)
    company_median: Mapped[float] = mapped_column(Float, default=0.0)
    count: Mapped[int] = mapped_column(Integer, default=0)
