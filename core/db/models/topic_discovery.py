"""Topic Discovery ORM models.

Extended from the initial scaffolds to support the full Topic Discovery
Module architecture: taxonomy trees, subdomain nodes, topic assignments,
source results, and persona affinity.

Tables:
- topic_discoveries — top-level discovery run per company/product
- taxonomy_trees — versioned taxonomy snapshots
- subdomain_nodes — individual nodes in the taxonomy hierarchy (self-referencing)
- topic_assignments — content opportunities in the dimensionality matrix
- td_source_results — per-source S1 generation statistics
- td_persona_affinity — persona-subdomain affinity scores
"""
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
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin
from core.db.enums import (
    AudienceSegmentType,
    BuyerStage,
    IntentType,
    RelevanceCell,
    TDStatus,
    TopicAssignmentStatus,
)


# ── Topic Discoveries ───────────────────────────────────────────────────


class TopicDiscoveryModel(UUIDPKMixin, Base):
    """Top-level discovery run for a company (optionally scoped to product)."""

    __tablename__ = "topic_discoveries"
    __table_args__ = (
        Index("ix_topic_discoveries_company", "company_id"),
        Index("ix_topic_discoveries_effective_slug", "effective_slug"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )
    pipeline_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )
    domain_name: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[TDStatus] = mapped_column(
        PgEnum(TDStatus, name="td_status_enum", create_type=True),
        default=TDStatus.draft,
    )
    taxonomy_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    matrix_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    scoring_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    persona_affinity_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    manifest_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scoring_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    persona_affinity_index_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )


# ── Taxonomy Trees ──────────────────────────────────────────────────────


class TaxonomyTreeModel(UUIDPKMixin, Base):
    """A versioned snapshot of the taxonomy tree for a discovery run."""

    __tablename__ = "taxonomy_trees"
    __table_args__ = (
        Index("ix_taxonomy_trees_discovery", "discovery_id"),
        UniqueConstraint(
            "discovery_id", "version",
            name="uq_taxonomy_trees_discovery_version",
        ),
    )

    discovery_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_subdomains: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    max_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    chao1_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    capture_recapture_est: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    tree_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[TDStatus] = mapped_column(
        PgEnum(TDStatus, name="td_status_enum", create_type=True),
        default=TDStatus.draft,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Subdomain Nodes ─────────────────────────────────────────────────────


class SubdomainNodeModel(UUIDPKMixin, Base):
    """A single node in the taxonomy hierarchy (self-referencing tree)."""

    __tablename__ = "subdomain_nodes"
    __table_args__ = (
        Index("ix_subdomain_nodes_taxonomy", "taxonomy_id"),
        Index("ix_subdomain_nodes_parent", "parent_id"),
        # Partial unique indexes created in migration 0031 via raw SQL
        # (not representable as declarative constraints due to WHERE clauses).
    )

    taxonomy_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("taxonomy_trees.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subdomain_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    source_provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_manually_added: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority_factors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    persona_affinity_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    expansion_status: Mapped[str | None] = mapped_column(
        String, nullable=True, server_default="not_expanded",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now(),
    )


# ── Topic Assignments ───────────────────────────────────────────────────


class TopicAssignmentModel(UUIDPKMixin, Base):
    """A single content opportunity in the dimensionality matrix."""

    __tablename__ = "topic_assignments"
    __table_args__ = (
        Index("ix_topic_assignments_discovery", "discovery_id"),
        Index("ix_topic_assignments_subdomain", "subdomain_node_id"),
        Index("ix_topic_assignments_persona", "persona_id"),
        Index(
            "ix_topic_assignments_subdomain_version",
            "discovery_id", "subdomain_node_id", "matrix_version",
        ),
        Index("ix_topic_assignments_batch", "expansion_batch_id"),
    )

    discovery_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    matrix_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
    )
    subdomain_node_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subdomain_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    topic_text: Mapped[str] = mapped_column(Text, nullable=False)
    buyer_stage: Mapped[BuyerStage] = mapped_column(
        PgEnum(BuyerStage, name="buyer_stage_enum", create_type=True),
        default=BuyerStage.tofu,
    )
    intent_type: Mapped[IntentType] = mapped_column(
        PgEnum(IntentType, name="intent_type_enum", create_type=True),
        default=IntentType.informational,
    )
    audience_segment: Mapped[str | None] = mapped_column(String, nullable=True)
    audience_segment_type: Mapped[AudienceSegmentType] = mapped_column(
        PgEnum(
            AudienceSegmentType,
            name="audience_segment_type_enum",
            create_type=True,
        ),
        default=AudienceSegmentType.individual_persona,
    )
    relevance: Mapped[RelevanceCell] = mapped_column(
        PgEnum(RelevanceCell, name="relevance_cell_enum", create_type=True),
        default=RelevanceCell.relevant,
    )
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority_factors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[TopicAssignmentStatus] = mapped_column(
        PgEnum(
            TopicAssignmentStatus,
            name="topic_assignment_status_enum",
            create_type=True,
        ),
        default=TopicAssignmentStatus.not_started,
    )
    is_manually_added: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    persona_id: Mapped[str | None] = mapped_column(String, nullable=True)
    persona_name: Mapped[str | None] = mapped_column(String, nullable=True)
    subdomain_id_text: Mapped[str | None] = mapped_column(String, nullable=True)
    subdomain_name: Mapped[str | None] = mapped_column(String, nullable=True)
    persona_affinity_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )
    expansion_batch_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Source Results ──────────────────────────────────────────────────────


class SourceResultModel(UUIDPKMixin, Base):
    """Per-source S1 generation statistics and raw candidates."""

    __tablename__ = "td_source_results"
    __table_args__ = (
        Index("ix_td_source_results_discovery", "discovery_id"),
    )

    discovery_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
    )
    total_candidates: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    total_rounds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    singletons: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    doubletons: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    chao1_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_sample_coverage: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    execution_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidates_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Persona Affinity ───────────────────────────────────────────────────


class PersonaAffinityModel(UUIDPKMixin, Base):
    """Persona-subdomain affinity score (many-to-many join table)."""

    __tablename__ = "td_persona_affinity"
    __table_args__ = (
        Index("ix_td_persona_affinity_discovery", "discovery_id"),
        Index("ix_td_persona_affinity_persona", "persona_id"),
    )

    discovery_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    subdomain_node_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subdomain_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    persona_id: Mapped[str] = mapped_column(String, nullable=False)
    persona_name: Mapped[str | None] = mapped_column(String, nullable=True)
    career_role: Mapped[str | None] = mapped_column(String, nullable=True)
    subdomain_id_str: Mapped[str | None] = mapped_column(String, nullable=True)
    subdomain_name: Mapped[str | None] = mapped_column(String, nullable=True)
    affinity_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    provenance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pain_points: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
