"""Runtime resolver for workspace BYOK model config."""
from __future__ import annotations

from core.db.repositories.model_config_repo import (
    WorkspaceAgentModelConfigRepository,
    WorkspaceLLMCredentialRepository,
)
from core.model_config.agent_catalog import get_agent_definition
from core.model_config.credentials import decrypt_api_key
from core.model_config.errors import (
    DisabledAgentError,
    InvalidCredentialError,
    MissingCredentialError,
    UnknownAgentKeyError,
)
from core.model_config.schemas import ResolvedModelConfig
from core.shared_tools.openrouter_client import _ensure_model_prefix


class ModelConfigResolver:
    """Resolve `(workspace_id, agent_key)` into a runtime-safe OpenRouter config."""

    def __init__(
        self,
        *,
        credential_repo: WorkspaceLLMCredentialRepository,
        config_repo: WorkspaceAgentModelConfigRepository,
        fernet_key: str,
        base_url: str | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._config_repo = config_repo
        self._fernet_key = fernet_key
        self._base_url = base_url

    async def resolve(
        self,
        workspace_id: str,
        workspace_slug: str,
        agent_key: str,
    ) -> ResolvedModelConfig:
        definition = get_agent_definition(agent_key)
        if definition is None:
            raise UnknownAgentKeyError(agent_key)

        credential = await self._credential_repo.get_active(workspace_id)
        if credential is None:
            raise MissingCredentialError("openrouter")
        if credential.status != "active":
            raise InvalidCredentialError(credential.status)

        override = await self._config_repo.get_for_agent(workspace_id, agent_key)
        if override is not None and not override.enabled:
            raise DisabledAgentError(agent_key)

        model = override.model if override is not None else definition.default_model
        temperature = (
            override.temperature
            if override is not None and override.temperature is not None
            else definition.default_temperature
        )
        max_tokens = (
            override.max_tokens
            if override is not None and override.max_tokens is not None
            else definition.default_max_tokens
        )
        timeout_s = (
            override.timeout_s
            if override is not None and override.timeout_s is not None
            else definition.default_timeout_s
        )
        extra_body = override.extra_body if override is not None else None

        from core.config.settings import settings

        return ResolvedModelConfig(
            workspace_id=str(workspace_id),
            workspace_slug=workspace_slug,
            agent_key=agent_key,
            model=_ensure_model_prefix(model),
            provider="openrouter",
            base_url=self._base_url or settings.openrouter_base_url,
            api_key=decrypt_api_key(
                credential.encrypted_api_key,
                fernet_key=self._fernet_key,
            ),
            credential_id=str(credential.id),
            model_config_id=str(override.id) if override is not None else None,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            extra_body=extra_body,
        )
