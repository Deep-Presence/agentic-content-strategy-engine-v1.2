"""Site audit & finding ORM models."""
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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, UUIDPKMixin
from core.db.enums import FindingSeverity, PipelineStatus


# ── Site Audits ─────────────────────────────────────────────────────────


class SiteAuditModel(UUIDPKMixin, Base):
    __tablename__ = "site_audits"
    __table_args__ = (
        Index("ix_site_audits_company_created", "company_id", "created_at"),
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


# ── Audit Findings ──────────────────────────────────────────────────────


class AuditFindingModel(UUIDPKMixin, Base):
    __tablename__ = "audit_findings"
    __table_args__ = (
        Index("ix_audit_findings_audit_severity", "audit_id", "severity"),
        Index("ix_audit_findings_audit_type", "audit_id", "finding_type"),
        Index("ix_audit_findings_audit_resolved", "audit_id", "is_resolved"),
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
