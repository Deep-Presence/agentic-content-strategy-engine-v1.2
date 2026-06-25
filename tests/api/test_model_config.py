"""API tests for workspace BYOK model configuration routes."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.model_config.schemas import (
    AgentCatalogItem,
    AgentConfigTestResult,
    AgentModelConfigView,
    AgentUsageSummary,
    CredentialStatus,
    CredentialTestResult,
    ModelConfigPreflightResult,
    WorkspaceModelConfigView,
)


class FakeModelConfigService:
    def __init__(self) -> None:
        self.upsert_key_calls = []
        self.patch_calls = []

    async def get_workspace_model_config(
        self,
        workspace_id: str,
        *,
        workspace_slug: str = "",
    ) -> WorkspaceModelConfigView:
        return WorkspaceModelConfigView(
            workspace_slug=workspace_slug,
            credential=CredentialStatus(
                configured=True,
                status="active",
                masked_key="sk-or...1234",
                last_validated_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
            ),
            catalog=[
                AgentCatalogItem(
                    agent_key="content.brief_builder",
                    display_name="Brief Builder",
                    group="Content Engine",
                    pipeline="content",
                    pipeline_step="brief_builder",
                    default_model="anthropic/claude-sonnet-4-6",
                    capabilities=["chat", "structured_output"],
                )
            ],
            configs=[
                AgentModelConfigView(
                    agent_key="content.brief_builder",
                    model="anthropic/claude-sonnet-4-6",
                    uses_default=True,
                )
            ],
            usage_summary=[
                AgentUsageSummary(
                    agent_key="content.brief_builder",
                    call_count=3,
                    prompt_tokens=1200,
                    completion_tokens=600,
                    estimated_cost_usd=0.42,
                    last_used_at=datetime(2026, 6, 22, 1, 30, tzinfo=timezone.utc),
                )
            ],
        )

    async def upsert_openrouter_key(
        self,
        workspace_id: str,
        user_id: str,
        api_key: str,
    ) -> CredentialStatus:
        self.upsert_key_calls.append((workspace_id, user_id, api_key))
        return CredentialStatus(
            configured=True,
            status="active",
            masked_key="sk-or...1234",
        )

    async def delete_openrouter_key(self, workspace_id: str, user_id: str) -> None:
        return None

    async def test_openrouter_key(
        self,
        workspace_id: str,
        api_key: str | None = None,
    ) -> CredentialTestResult:
        return CredentialTestResult(ok=True, model="models.list")

    async def upsert_agent_config(self, workspace_id, user_id, agent_key, update):
        self.patch_calls.append((workspace_id, user_id, agent_key, update))
        return AgentModelConfigView(
            agent_key=agent_key,
            model=update.model,
            uses_default=False,
            updated_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
        )

    async def test_agent_config(self, workspace_id: str, agent_key: str):
        return AgentConfigTestResult(
            ok=True,
            agent_key=agent_key,
            model="anthropic/claude-sonnet-4-6",
        )

    async def preflight(
        self,
        workspace_id: str,
        agent_keys: list[str],
    ) -> ModelConfigPreflightResult:
        return ModelConfigPreflightResult(
            ok=False,
            missing_credential=True,
            errors=["missing_credential"],
        )


@pytest.fixture
def fake_model_config_service(app: FastAPI) -> FakeModelConfigService:
    service = FakeModelConfigService()
    app.state.model_config_service = service
    return service


def test_get_model_config_returns_catalog_without_raw_key(
    client: TestClient,
    fake_model_config_service: FakeModelConfigService,
) -> None:
    resp = client.get("/api/v1/workspaces/test-co/model-config")

    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace_slug"] == "test-co"
    assert body["credential"]["masked_key"] == "sk-or...1234"
    assert "api_key" not in str(body)
    assert body["catalog"][0]["agent_key"] == "content.brief_builder"
    assert body["configs"][0]["uses_default"] is True
    assert body["usage_summary"][0]["agent_key"] == "content.brief_builder"
    assert body["usage_summary"][0]["call_count"] == 3
    assert body["usage_summary"][0]["estimated_cost_usd"] == 0.42


def test_member_can_preflight_but_cannot_mutate_key(
    client: TestClient,
    fake_model_config_service: FakeModelConfigService,
) -> None:
    preflight = client.post(
        "/api/v1/workspaces/test-co/model-config/preflight",
        json={"agent_keys": ["content.brief_builder"]},
    )
    assert preflight.status_code == 200
    assert preflight.json()["missing_credential"] is True

    denied = client.put(
        "/api/v1/workspaces/test-co/model-config/openrouter-key",
        json={"api_key": "sk-or-secret"},
    )
    assert denied.status_code == 403
    assert fake_model_config_service.upsert_key_calls == []


def test_owner_can_store_key_and_response_masks_secret(
    superuser_client: TestClient,
    fake_model_config_service: FakeModelConfigService,
) -> None:
    resp = superuser_client.put(
        "/api/v1/workspaces/test-co/model-config/openrouter-key",
        json={"api_key": "sk-or-secret-1234"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["masked_key"] == "sk-or...1234"
    assert "sk-or-secret-1234" not in str(body)
    assert fake_model_config_service.upsert_key_calls[0][2] == "sk-or-secret-1234"


def test_owner_can_patch_agent_config(
    superuser_client: TestClient,
    fake_model_config_service: FakeModelConfigService,
) -> None:
    resp = superuser_client.patch(
        "/api/v1/workspaces/test-co/model-config/agents/content.brief_builder",
        json={"model": "anthropic/claude-opus-4-6", "temperature": 0.1},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_key"] == "content.brief_builder"
    assert body["model"] == "anthropic/claude-opus-4-6"
    assert body["uses_default"] is False
