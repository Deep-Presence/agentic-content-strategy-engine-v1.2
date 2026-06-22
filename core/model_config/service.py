"""Workspace BYOK model configuration service."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from core.db.models.model_config import (
    WorkspaceAgentModelConfigModel,
    WorkspaceLLMCredentialModel,
)
from core.db.repositories.model_config_repo import (
    WorkspaceAgentModelConfigRepository,
    WorkspaceLLMCredentialRepository,
)
from core.model_config.agent_catalog import (
    AgentDefinition,
    all_agent_definitions,
    get_agent_definition,
)
from core.model_config.credentials import (
    decrypt_api_key,
    encrypt_api_key,
    fingerprint_api_key,
    mask_api_key,
    normalize_api_key,
    resolve_fingerprint_pepper,
)
from core.model_config.errors import ModelConfigValidationError, UnknownAgentKeyError
from core.model_config.protocols import OpenRouterCredentialValidator
from core.model_config.schemas import (
    AgentCatalogItem,
    AgentConfigTestResult,
    AgentModelConfigUpdate,
    AgentModelConfigView,
    CredentialStatus,
    CredentialTestResult,
    ModelConfigPreflightResult,
    WorkspaceModelConfigView,
)
from core.model_config.validator import LiveOpenRouterCredentialValidator
from core.shared_tools.openrouter_client import _ensure_model_prefix

_SECRET_MARKERS = ("api_key", "apikey", "secret", "token", "password")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_value(value: str | _uuid.UUID) -> _uuid.UUID:
    return _uuid.UUID(str(value)) if isinstance(value, str) else value


class ModelConfigService:
    """CRUD, validation, and preflight for workspace-owned model config."""

    def __init__(
        self,
        *,
        credential_repo: WorkspaceLLMCredentialRepository,
        config_repo: WorkspaceAgentModelConfigRepository,
        fernet_key: str,
        validator: OpenRouterCredentialValidator | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._config_repo = config_repo
        self._fernet_key = fernet_key
        self._validator = validator or LiveOpenRouterCredentialValidator()

    async def get_workspace_model_config(
        self,
        workspace_id: str,
        *,
        workspace_slug: str = "",
    ) -> WorkspaceModelConfigView:
        credential = await self._credential_repo.get_active(workspace_id)
        overrides = {
            row.agent_key: row
            for row in await self._config_repo.list_for_workspace(workspace_id)
        }
        catalog = [_catalog_item(definition) for definition in all_agent_definitions()]
        configs = [
            _effective_config_view(definition, overrides.get(definition.agent_key))
            for definition in all_agent_definitions()
        ]
        return WorkspaceModelConfigView(
            workspace_slug=workspace_slug,
            credential=_credential_status(credential),
            catalog=catalog,
            configs=configs,
            missing_required_agent_keys=[],
        )

    async def upsert_openrouter_key(
        self,
        workspace_id: str,
        user_id: str,
        api_key: str,
    ) -> CredentialStatus:
        normalized = normalize_api_key(api_key)
        if not normalized:
            raise ModelConfigValidationError("api_key_required")

        test_result = await self._validator.validate_key(normalized)
        status = "active" if test_result.ok else "invalid"
        row = await self._credential_repo.upsert_active(
            workspace_id=workspace_id,
            user_id=user_id,
            provider="openrouter",
            encrypted_api_key=encrypt_api_key(normalized, fernet_key=self._fernet_key),
            api_key_fingerprint=fingerprint_api_key(
                normalized,
                pepper=resolve_fingerprint_pepper(),
            ),
            api_key_masked=mask_api_key(normalized),
            status=status,
            last_validated_at=_utcnow(),
            last_validation_error=test_result.error or None,
        )
        return _credential_status(row)

    async def delete_openrouter_key(self, workspace_id: str, user_id: str) -> None:
        await self._credential_repo.soft_delete_active(workspace_id, user_id=user_id)

    async def test_openrouter_key(
        self,
        workspace_id: str,
        api_key: str | None = None,
    ) -> CredentialTestResult:
        key = normalize_api_key(api_key or "")
        if not key:
            credential = await self._credential_repo.get_active(workspace_id)
            if credential is None:
                return CredentialTestResult(ok=False, error="missing_credential")
            key = decrypt_api_key(credential.encrypted_api_key, fernet_key=self._fernet_key)
        return await self._validator.validate_key(key)

    async def upsert_agent_config(
        self,
        workspace_id: str,
        user_id: str,
        agent_key: str,
        update: AgentModelConfigUpdate,
    ) -> AgentModelConfigView:
        definition = get_agent_definition(agent_key)
        if definition is None:
            raise UnknownAgentKeyError(agent_key)
        if update.extra_body is not None:
            _validate_extra_body(update.extra_body)

        model = _ensure_model_prefix(update.model or definition.default_model)
        enabled = True if update.enabled is None else update.enabled
        row = await self._config_repo.upsert(
            workspace_id=workspace_id,
            user_id=user_id,
            agent_key=agent_key,
            provider="openrouter",
            model=model,
            temperature=update.temperature,
            max_tokens=update.max_tokens,
            timeout_s=update.timeout_s,
            extra_body=update.extra_body,
            enabled=enabled,
        )
        return _effective_config_view(definition, row)

    async def test_agent_config(
        self,
        workspace_id: str,
        agent_key: str,
    ) -> AgentConfigTestResult:
        definition = get_agent_definition(agent_key)
        if definition is None:
            return AgentConfigTestResult(
                ok=False,
                agent_key=agent_key,
                error="unknown_agent_key",
            )
        credential = await self._credential_repo.get_active(workspace_id)
        if credential is None:
            return AgentConfigTestResult(
                ok=False,
                agent_key=agent_key,
                model=definition.default_model,
                error="missing_credential",
            )
        if credential.status != "active":
            return AgentConfigTestResult(
                ok=False,
                agent_key=agent_key,
                model=definition.default_model,
                error="invalid_credential",
            )
        config = await self._config_repo.get_for_agent(workspace_id, agent_key)
        model = config.model if config is not None else definition.default_model
        return AgentConfigTestResult(ok=True, agent_key=agent_key, model=model)

    async def preflight(
        self,
        workspace_id: str,
        agent_keys: list[str],
    ) -> ModelConfigPreflightResult:
        result = ModelConfigPreflightResult(ok=True)
        credential = await self._credential_repo.get_active(workspace_id)
        if credential is None:
            result.ok = False
            result.missing_credential = True
            result.errors.append("missing_credential")
        elif credential.status != "active":
            result.ok = False
            result.invalid_credential = True
            result.errors.append("invalid_credential")

        for agent_key in agent_keys:
            definition = get_agent_definition(agent_key)
            if definition is None:
                result.ok = False
                result.missing_agent_keys.append(agent_key)
                continue
            config = await self._config_repo.get_for_agent(workspace_id, agent_key)
            if config is not None and not config.enabled:
                result.ok = False
                result.disabled_agent_keys.append(agent_key)
        return result


def _catalog_item(definition: AgentDefinition) -> AgentCatalogItem:
    return AgentCatalogItem(
        agent_key=definition.agent_key,
        display_name=definition.display_name,
        group=definition.group,
        pipeline=definition.pipeline,
        pipeline_step=definition.pipeline_step,
        default_model=definition.default_model,
        capabilities=[cap.value for cap in definition.capabilities],
        required=definition.required,
        description=definition.description,
    )


def _credential_status(
    credential: WorkspaceLLMCredentialModel | None,
) -> CredentialStatus:
    if credential is None:
        return CredentialStatus()
    return CredentialStatus(
        configured=credential.deleted_at is None,
        provider=credential.provider,
        status=credential.status,
        masked_key=credential.api_key_masked,
        last_validated_at=credential.last_validated_at,
        last_validation_error=credential.last_validation_error or "",
    )


def _effective_config_view(
    definition: AgentDefinition,
    config: WorkspaceAgentModelConfigModel | None,
) -> AgentModelConfigView:
    return AgentModelConfigView(
        agent_key=definition.agent_key,
        model=config.model if config is not None else _ensure_model_prefix(definition.default_model),
        provider=config.provider if config is not None else "openrouter",
        temperature=(
            config.temperature
            if config is not None and config.temperature is not None
            else definition.default_temperature
        ),
        max_tokens=(
            config.max_tokens
            if config is not None and config.max_tokens is not None
            else definition.default_max_tokens
        ),
        timeout_s=(
            config.timeout_s
            if config is not None and config.timeout_s is not None
            else definition.default_timeout_s
        ),
        enabled=config.enabled if config is not None else True,
        uses_default=config is None,
        model_config_id=str(config.id) if config is not None else None,
        updated_at=config.updated_at if config is not None else None,
    )


def _validate_extra_body(extra_body: dict[str, Any]) -> None:
    for key, value in extra_body.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            raise ModelConfigValidationError("extra_body_contains_secret")
        if isinstance(value, dict):
            _validate_extra_body(value)
