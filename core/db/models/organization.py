"""Organisation domain models — companies, products, users, invites, defaults."""
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPKMixin
from core.db.enums import UserRole


# ── Companies ────────────────────────────────────────────────────────────


class CompanyModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    additional_domains: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    display_id_prefix: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
    )
    display_id_counter: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )

    # relationships
    products: Mapped[list[ProductModel]] = relationship(
        "ProductModel", back_populates="company", lazy="selectin"
    )
    users: Mapped[list[UserModel]] = relationship(
        "UserModel", back_populates="company", lazy="selectin"
    )
    invites: Mapped[list[InviteModel]] = relationship(
        "InviteModel", back_populates="company", lazy="selectin"
    )
    pipeline_defaults: Mapped[PipelineDefaultsModel | None] = relationship(
        "PipelineDefaultsModel", back_populates="company", uselist=False, lazy="selectin"
    )


# ── Products ─────────────────────────────────────────────────────────────


class ProductModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("company_id", "slug", name="uq_products_company_slug"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    company: Mapped[CompanyModel] = relationship(
        "CompanyModel", back_populates="products"
    )


# ── Users ────────────────────────────────────────────────────────────────


class UserModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_company_id", "company_id"),
        Index("ix_users_email", "email"),
    )

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, default="")
    last_name: Mapped[str] = mapped_column(String, default="")
    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole, name="user_role_enum", create_type=True),
        default=UserRole.member,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    company: Mapped[CompanyModel] = relationship(
        "CompanyModel", back_populates="users"
    )


# ── Invites ──────────────────────────────────────────────────────────────


class InviteModel(UUIDPKMixin, Base):
    """Invite codes — created_at only, no updated_at needed."""

    __tablename__ = "invites"

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole, name="user_role_enum", create_type=True),
        default=UserRole.member,
    )
    created_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    redeemed_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # relationships
    company: Mapped[CompanyModel] = relationship(
        "CompanyModel", back_populates="invites"
    )
    creator: Mapped[UserModel | None] = relationship(
        "UserModel", foreign_keys=[created_by]
    )
    redeemer: Mapped[UserModel | None] = relationship(
        "UserModel", foreign_keys=[redeemed_by]
    )


# ── Pipeline Defaults ────────────────────────────────────────────────────


class PipelineDefaultsModel(UUIDPKMixin, Base):
    __tablename__ = "company_pipeline_defaults"

    company_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id"),
        unique=True,
        nullable=False,
    )
    defaults_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    company: Mapped[CompanyModel] = relationship(
        "CompanyModel", back_populates="pipeline_defaults"
    )
