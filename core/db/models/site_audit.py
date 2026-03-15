"""Site audit, finding, and page result ORM models."""
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
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin
from core.db.enums import FindingSeverity, PipelineStatus


# ── Site Audits ─────────────────────────────────────────────────────────


class SiteAuditModel(UUIDPKMixin, Base):
    __tablename__ = "site_audits"
    __table_args__ = (
        Index("ix_site_audits_company_created", "company_id", "created_at"),
        Index("ix_site_audits_slug_created", "effective_slug", "created_at"),
        Index(
            "ix_site_audits_domain_status",
            "company_id", "site_domain", "status", "created_at",
        ),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    site_domain: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[PipelineStatus] = mapped_column(
        PgEnum(PipelineStatus, name="pipeline_status_enum", create_type=True),
        default=PipelineStatus.pending,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Enriched columns (added in migration 0009) ──────────────────────

    effective_slug: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    pipeline_run_id: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id"),
        nullable=True,
        default=None,
    )
    overall_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    grade: Mapped[str | None] = mapped_column(
        String(2), nullable=True, default=None
    )
    is_degraded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    pages_discovered: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    dimension_scores: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    ai_bot_access: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    sitemap_health: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    findings_by_severity: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    findings_by_dimension: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    top_findings: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    avg_snippet_readiness: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    pages_with_schema: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    avg_question_heading_ratio: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    failed_steps: Mapped[list | None] = mapped_column(
        ARRAY(Integer), nullable=True, default=None
    )
    degraded_dimensions: Mapped[list | None] = mapped_column(
        ARRAY(Text), nullable=True, default=None
    )


# ── Audit Findings ──────────────────────────────────────────────────────


class AuditFindingModel(UUIDPKMixin, Base):
    __tablename__ = "audit_findings"
    __table_args__ = (
        Index("ix_audit_findings_audit_severity", "audit_id", "severity"),
        Index("ix_audit_findings_audit_type", "audit_id", "finding_type"),
        Index("ix_audit_findings_audit_resolved", "audit_id", "is_resolved"),
        Index("ix_audit_findings_audit_sev_dim", "audit_id", "severity", "dimension"),
    )

    audit_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("site_audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    finding_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        PgEnum(FindingSeverity, name="finding_severity_enum", create_type=True),
        nullable=False,
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Enriched columns (added in migration 0009) ──────────────────────

    dimension: Mapped[str] = mapped_column(
        String, nullable=False, default="", server_default=""
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    recommendation: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )


# ── Audit Page Results ──────────────────────────────────────────────────


class AuditPageResultModel(UUIDPKMixin, Base):
    """Per-page audit result with queryable columns + full JSONB blob."""

    __tablename__ = "audit_page_results"
    __table_args__ = (
        Index("ix_audit_page_results_audit_idx", "audit_id", "page_index"),
    )

    audit_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("site_audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crawl_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reading_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_schema: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    snippet_readiness_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    finding_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_https: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_noindex: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
