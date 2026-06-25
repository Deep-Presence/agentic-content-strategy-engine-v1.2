"""Repositories for workspace BYOK model configuration."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.db.models.model_config import (
    WorkspaceAgentModelConfigModel,
    WorkspaceLLMCredentialModel,
)
from core.db.repositories.base import SQLAlchemyRepository


def _uuid_value(value: _uuid.UUID | str) -> _uuid.UUID:
    return _uuid.UUID(str(value)) if isinstance(value, str) else value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkspaceLLMCredentialRepository(SQLAlchemyRepository[WorkspaceLLMCredentialModel]):
    model_class = WorkspaceLLMCredentialModel

    async def get_active(
        self,
        workspace_id: _uuid.UUID | str,
        *,
        provider: str = "openrouter",
    ) -> WorkspaceLLMCredentialModel | None:
        stmt = select(WorkspaceLLMCredentialModel).where(
            WorkspaceLLMCredentialModel.workspace_id == _uuid_value(workspace_id),
            WorkspaceLLMCredentialModel.provider == provider,
            WorkspaceLLMCredentialModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert_active(
        self,
        *,
        workspace_id: _uuid.UUID | str,
        encrypted_api_key: str,
        api_key_fingerprint: str,
        api_key_masked: str,
        user_id: _uuid.UUID | str | None,
        provider: str = "openrouter",
        status: str = "active",
        last_validated_at: datetime | None = None,
        last_validation_error: str | None = None,
    ) -> WorkspaceLLMCredentialModel:
        existing = await self.get_active(workspace_id, provider=provider)
        uid = _uuid_value(user_id) if user_id else None
        if existing is None:
            return await self.create(
                workspace_id=_uuid_value(workspace_id),
                provider=provider,
                encrypted_api_key=encrypted_api_key,
                api_key_fingerprint=api_key_fingerprint,
                api_key_masked=api_key_masked,
                status=status,
                last_validated_at=last_validated_at,
                last_validation_error=last_validation_error,
                created_by=uid,
                updated_by=uid,
            )

        existing.encrypted_api_key = encrypted_api_key
        existing.api_key_fingerprint = api_key_fingerprint
        existing.api_key_masked = api_key_masked
        existing.status = status
        existing.last_validated_at = last_validated_at
        existing.last_validation_error = last_validation_error
        existing.updated_by = uid
        await self._session.flush()
        return existing

    async def soft_delete_active(
        self,
        workspace_id: _uuid.UUID | str,
        *,
        user_id: _uuid.UUID | str | None = None,
        provider: str = "openrouter",
    ) -> bool:
        existing = await self.get_active(workspace_id, provider=provider)
        if existing is None:
            return False
        existing.status = "deleted"
        existing.deleted_at = _utcnow()
        existing.updated_by = _uuid_value(user_id) if user_id else None
        await self._session.flush()
        return True


class WorkspaceAgentModelConfigRepository(
    SQLAlchemyRepository[WorkspaceAgentModelConfigModel]
):
    model_class = WorkspaceAgentModelConfigModel

    async def get_for_agent(
        self,
        workspace_id: _uuid.UUID | str,
        agent_key: str,
    ) -> WorkspaceAgentModelConfigModel | None:
        stmt = select(WorkspaceAgentModelConfigModel).where(
            WorkspaceAgentModelConfigModel.workspace_id == _uuid_value(workspace_id),
            WorkspaceAgentModelConfigModel.agent_key == agent_key,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_workspace(
        self,
        workspace_id: _uuid.UUID | str,
    ) -> Sequence[WorkspaceAgentModelConfigModel]:
        stmt = (
            select(WorkspaceAgentModelConfigModel)
            .where(WorkspaceAgentModelConfigModel.workspace_id == _uuid_value(workspace_id))
            .order_by(WorkspaceAgentModelConfigModel.agent_key.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        *,
        workspace_id: _uuid.UUID | str,
        agent_key: str,
        model: str,
        provider: str = "openrouter",
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        extra_body: dict[str, Any] | None = None,
        enabled: bool = True,
        user_id: _uuid.UUID | str | None = None,
    ) -> WorkspaceAgentModelConfigModel:
        wid = _uuid_value(workspace_id)
        uid = _uuid_value(user_id) if user_id else None
        stmt = pg_insert(WorkspaceAgentModelConfigModel).values(
            id=_uuid.uuid4(),
            workspace_id=wid,
            agent_key=agent_key,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            extra_body=extra_body,
            enabled=enabled,
            created_by=uid,
            updated_by=uid,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_workspace_agent_model_configs_workspace_agent",
            set_={
                "provider": stmt.excluded.provider,
                "model": stmt.excluded.model,
                "temperature": stmt.excluded.temperature,
                "max_tokens": stmt.excluded.max_tokens,
                "timeout_s": stmt.excluded.timeout_s,
                "extra_body": stmt.excluded.extra_body,
                "enabled": stmt.excluded.enabled,
                "updated_by": stmt.excluded.updated_by,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        config = await self.get_for_agent(wid, agent_key)
        if config is None:
            raise RuntimeError("model_config_upsert_failed")
        return config
