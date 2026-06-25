"""Workspace-scoped BYOK LLM credential and agent model config models."""
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPKMixin


class WorkspaceLLMCredentialModel(UUIDPKMixin, TimestampMixin, Base):
    """Encrypted OpenRouter credential owned by a workspace."""

    __tablename__ = "workspace_llm_credentials"
    __table_args__ = (
        Index("ix_workspace_llm_credentials_workspace_id", "workspace_id"),
        Index("ix_workspace_llm_credentials_provider", "provider"),
        Index("ix_workspace_llm_credentials_status", "status"),
        Index(
            "uq_workspace_llm_credentials_active_provider",
            "workspace_id",
            "provider",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    workspace_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    api_key_masked: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkspaceAgentModelConfigModel(UUIDPKMixin, TimestampMixin, Base):
    """Workspace override for a single cataloged agent model."""

    __tablename__ = "workspace_agent_model_configs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "agent_key",
            name="uq_workspace_agent_model_configs_workspace_agent",
        ),
        Index("ix_workspace_agent_model_configs_workspace_id", "workspace_id"),
        Index("ix_workspace_agent_model_configs_agent_key", "agent_key"),
        Index("ix_workspace_agent_model_configs_provider", "provider"),
    )

    workspace_id: Mapped[_uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_key: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    model: Mapped[str] = mapped_column(String, nullable=False)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_s: Mapped[float | None] = mapped_column(nullable=True)
    extra_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_by: Mapped[_uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
