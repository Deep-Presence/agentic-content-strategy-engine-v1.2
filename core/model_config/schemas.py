"""Pydantic contracts for BYOK model configuration services."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CredentialStatus(BaseModel):
    provider: str = "openrouter"
    configured: bool = False
    status: str = ""
    masked_key: str = ""
    last_validated_at: datetime | None = None
    last_validation_error: str = ""


class AgentModelConfigUpdate(BaseModel):
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    enabled: bool | None = None
    extra_body: dict[str, Any] | None = None


class AgentCatalogItem(BaseModel):
    agent_key: str = ""
    display_name: str = ""
    group: str = ""
    pipeline: str = ""
    pipeline_step: str = ""
    default_model: str = ""
    capabilities: list[str] = Field(default_factory=list)
    required: bool = True
    description: str = ""


class AgentModelConfigView(BaseModel):
    agent_key: str = ""
    model: str = ""
    provider: str = "openrouter"
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    enabled: bool = True
    uses_default: bool = True
    model_config_id: str | None = None
    updated_at: datetime | None = None


class WorkspaceModelConfigView(BaseModel):
    workspace_slug: str = ""
    credential: CredentialStatus = Field(default_factory=CredentialStatus)
    catalog: list[AgentCatalogItem] = Field(default_factory=list)
    configs: list[AgentModelConfigView] = Field(default_factory=list)
    missing_required_agent_keys: list[str] = Field(default_factory=list)


class CredentialTestResult(BaseModel):
    ok: bool = False
    provider: str = "openrouter"
    model: str = ""
    error: str = ""


class AgentConfigTestResult(BaseModel):
    ok: bool = False
    agent_key: str = ""
    model: str = ""
    error: str = ""


class ModelConfigPreflightResult(BaseModel):
    ok: bool = False
    missing_credential: bool = False
    invalid_credential: bool = False
    missing_agent_keys: list[str] = Field(default_factory=list)
    disabled_agent_keys: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ResolvedModelConfig(BaseModel):
    workspace_id: str = ""
    workspace_slug: str = ""
    agent_key: str = ""
    model: str = ""
    provider: str = "openrouter"
    base_url: str = ""
    api_key: str = ""
    credential_id: str = ""
    model_config_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    extra_body: dict[str, Any] | None = None
