"""Workspace BYOK model configuration routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import require_auth
from api.dependencies import get_model_config_service, get_workspace_service
from api.schemas.model_config import (
    AgentConfigTestResponse,
    AgentModelConfigResponse,
    AgentModelConfigUpdateRequest,
    CredentialStatusResponse,
    CredentialTestResponse,
    DeleteOpenRouterKeyResponse,
    ModelConfigPreflightRequest,
    ModelConfigPreflightResponse,
    OpenRouterKeyTestRequest,
    OpenRouterKeyUpsertRequest,
    WorkspaceModelConfigResponse,
)
from core.model_config.errors import (
    ModelConfigValidationError,
    UnknownAgentKeyError,
)
from core.model_config.schemas import AgentModelConfigUpdate
from core.models.organization import UserProfile
from core.models.workspace import Workspace
from core.services.workspace_protocol import WorkspaceServiceProtocol
from core.model_config.service import ModelConfigService

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_slug}/model-config",
    tags=["model-config"],
)

_ADMIN_ROLES = ("owner", "admin")


async def _workspace_access(
    *,
    workspace_slug: str,
    user: UserProfile,
    workspace_service: WorkspaceServiceProtocol,
    admin: bool = False,
) -> Workspace:
    try:
        workspace, _membership = await workspace_service.assert_workspace_access(
            workspace_slug,
            user,
            min_roles=_ADMIN_ROLES if admin else None,
        )
        return workspace
    except ValueError as exc:
        code = str(exc)
        if code == "workspace_not_found":
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        raise HTTPException(status_code=403, detail="Access denied") from exc


def _workspace_response(view: object) -> WorkspaceModelConfigResponse:
    return WorkspaceModelConfigResponse.model_validate(
        view.model_dump(mode="json")  # type: ignore[attr-defined]
    )


@router.get("", response_model=WorkspaceModelConfigResponse)
async def get_workspace_model_config(
    workspace_slug: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> WorkspaceModelConfigResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
    )
    view = await model_config_service.get_workspace_model_config(
        workspace.id,
        workspace_slug=workspace.slug,
    )
    return _workspace_response(view)


@router.put("/openrouter-key", response_model=CredentialStatusResponse)
async def upsert_openrouter_key(
    workspace_slug: str,
    body: OpenRouterKeyUpsertRequest,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> CredentialStatusResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
        admin=True,
    )
    try:
        status = await model_config_service.upsert_openrouter_key(
            workspace.id,
            user.id,
            body.api_key,
        )
    except ModelConfigValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CredentialStatusResponse.model_validate(status.model_dump(mode="json"))


@router.delete("/openrouter-key", response_model=DeleteOpenRouterKeyResponse)
async def delete_openrouter_key(
    workspace_slug: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> DeleteOpenRouterKeyResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
        admin=True,
    )
    await model_config_service.delete_openrouter_key(workspace.id, user.id)
    return DeleteOpenRouterKeyResponse(deleted=True)


@router.post("/openrouter-key/test", response_model=CredentialTestResponse)
async def test_openrouter_key(
    workspace_slug: str,
    body: OpenRouterKeyTestRequest,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> CredentialTestResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
        admin=True,
    )
    result = await model_config_service.test_openrouter_key(
        workspace.id,
        body.api_key,
    )
    return CredentialTestResponse.model_validate(result.model_dump(mode="json"))


@router.patch("/agents/{agent_key}", response_model=AgentModelConfigResponse)
async def update_agent_config(
    workspace_slug: str,
    agent_key: str,
    body: AgentModelConfigUpdateRequest,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> AgentModelConfigResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
        admin=True,
    )
    try:
        view = await model_config_service.upsert_agent_config(
            workspace.id,
            user.id,
            agent_key,
            AgentModelConfigUpdate.model_validate(body.model_dump(mode="json")),
        )
    except UnknownAgentKeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown agent key") from exc
    except ModelConfigValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentModelConfigResponse.model_validate(view.model_dump(mode="json"))


@router.post("/agents/{agent_key}/test", response_model=AgentConfigTestResponse)
async def test_agent_config(
    workspace_slug: str,
    agent_key: str,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> AgentConfigTestResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
        admin=True,
    )
    result = await model_config_service.test_agent_config(workspace.id, agent_key)
    return AgentConfigTestResponse.model_validate(result.model_dump(mode="json"))


@router.post("/preflight", response_model=ModelConfigPreflightResponse)
async def preflight_model_config(
    workspace_slug: str,
    body: ModelConfigPreflightRequest,
    user: UserProfile = Depends(require_auth),
    workspace_service: WorkspaceServiceProtocol = Depends(get_workspace_service),
    model_config_service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigPreflightResponse:
    workspace = await _workspace_access(
        workspace_slug=workspace_slug,
        user=user,
        workspace_service=workspace_service,
    )
    result = await model_config_service.preflight(workspace.id, body.agent_keys)
    return ModelConfigPreflightResponse.model_validate(result.model_dump(mode="json"))
