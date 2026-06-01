"""Workspace tenant models — workspaces and memberships."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.enums import MembershipStatus, WorkspaceRole


class WorkspaceModel(UUIDPKMixin, TimestampMixin, Base):
    """Top-level tenant. Linked 1:1 to legacy companies during migration."""

    __tablename__ = "workspaces"
    __table_args__ = (
        Index("ix_workspaces_company_id", "company_id"),
        Index("ix_workspaces_slug", "slug"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    primary_domain: Mapped[str] = mapped_column(String, nullable=False)
    additional_domains: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str] = mapped_column(String(32), default="#5BA4C4", server_default="#5BA4C4")
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_key: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    memberships: Mapped[list[WorkspaceMembershipModel]] = relationship(
        "WorkspaceMembershipModel",
        back_populates="workspace",
        lazy="selectin",
    )


class WorkspaceMembershipModel(UUIDPKMixin, TimestampMixin, Base):
    """Many-to-many link between users and workspaces with role + status."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_memberships_workspace_user"),
        Index("ix_workspace_memberships_user_id", "user_id"),
        Index("ix_workspace_memberships_workspace_id", "workspace_id"),
    )

    workspace_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        PgEnum(WorkspaceRole, name="workspace_role_enum", create_type=True),
        default=WorkspaceRole.member,
        nullable=False,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        PgEnum(MembershipStatus, name="membership_status_enum", create_type=True),
        default=MembershipStatus.active,
        nullable=False,
    )
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workspace: Mapped[WorkspaceModel] = relationship(
        "WorkspaceModel", back_populates="memberships"
    )
