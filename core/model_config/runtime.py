"""Runtime helpers for resolving BYOK model configs from core code."""
from __future__ import annotations

from core.model_config.resolver import ModelConfigResolver
from core.model_config.schemas import ResolvedModelConfig


async def resolve_model_config_for_agent(
    *,
    workspace_id: str,
    workspace_slug: str,
    agent_key: str,
    resolver: ModelConfigResolver | None = None,
) -> ResolvedModelConfig:
    """Resolve a workspace-scoped agent config using the standard DB repos."""
    if resolver is not None:
        return await resolver.resolve(workspace_id, workspace_slug, agent_key)

    from core.db.engine import get_session_factory
    from core.db.repositories.model_config_repo import (
        WorkspaceAgentModelConfigRepository,
        WorkspaceLLMCredentialRepository,
    )
    from core.model_config.credentials import resolve_fernet_key

    factory = get_session_factory()
    async with factory() as session:
        db_resolver = ModelConfigResolver(
            credential_repo=WorkspaceLLMCredentialRepository(session),
            config_repo=WorkspaceAgentModelConfigRepository(session),
            fernet_key=resolve_fernet_key(),
        )
        return await db_resolver.resolve(workspace_id, workspace_slug, agent_key)


def actual_provider(model: str) -> str:
    """Return provider prefix from an OpenRouter model id."""
    return model.split("/", 1)[0] if "/" in model else ""
