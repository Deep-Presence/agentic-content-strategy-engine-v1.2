"""API schemas for workspace BYOK model configuration."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CredentialStatusResponse(BaseModel):
    provider: str = "openrouter"
    configured: bool = False
    status: str = ""
    masked_key: str = ""
    last_validated_at: str | None = None
    last_validation_error: str = ""


class AgentCatalogItemResponse(BaseModel):
    agent_key: str = ""
    display_name: str = ""
    group: str = ""
    pipeline: str = ""
    pipeline_step: str = ""
    default_model: str = ""
    capabilities: list[str] = Field(default_factory=list)
    required: bool = True
    description: str = ""


class AgentModelConfigResponse(BaseModel):
    agent_key: str = ""
    model: str = ""
    provider: str = "openrouter"
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    enabled: bool = True
    uses_default: bool = True
    updated_at: str | None = None


class WorkspaceModelConfigResponse(BaseModel):
    workspace_slug: str = ""
    credential: CredentialStatusResponse = Field(default_factory=CredentialStatusResponse)
    catalog: list[AgentCatalogItemResponse] = Field(default_factory=list)
    configs: list[AgentModelConfigResponse] = Field(default_factory=list)
    missing_required_agent_keys: list[str] = Field(default_factory=list)


class OpenRouterKeyUpsertRequest(BaseModel):
    api_key: str = ""


class OpenRouterKeyTestRequest(BaseModel):
    api_key: str | None = None


class AgentModelConfigUpdateRequest(BaseModel):
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    enabled: bool | None = None
    extra_body: dict[str, Any] | None = None


class ModelConfigPreflightRequest(BaseModel):
    agent_keys: list[str] = Field(default_factory=list)


class CredentialTestResponse(BaseModel):
    ok: bool = False
    provider: str = "openrouter"
    model: str = ""
    error: str = ""


class AgentConfigTestResponse(BaseModel):
    ok: bool = False
    agent_key: str = ""
    model: str = ""
    error: str = ""


class ModelConfigPreflightResponse(BaseModel):
    ok: bool = False
    missing_credential: bool = False
    invalid_credential: bool = False
    missing_agent_keys: list[str] = Field(default_factory=list)
    disabled_agent_keys: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DeleteOpenRouterKeyResponse(BaseModel):
    deleted: bool = False
