"""Tests for BYOK model config service and resolver."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from core.model_config.credentials import decrypt_api_key
from core.model_config.errors import (
    DisabledAgentError,
    MissingCredentialError,
    ModelConfigValidationError,
    UnknownAgentKeyError,
)
from core.model_config.resolver import ModelConfigResolver
from core.model_config.schemas import AgentModelConfigUpdate, CredentialTestResult
from core.model_config.service import ModelConfigService


class FakeValidator:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok

    async def validate_key(self, api_key: str) -> CredentialTestResult:
        return CredentialTestResult(
            ok=self.ok,
            model="models.list",
            error="" if self.ok else "invalid",
        )


class FakeCredentialRepo:
    def __init__(self) -> None:
        self.row = None

    async def get_active(self, workspace_id: str, *, provider: str = "openrouter"):
        return self.row

    async def upsert_active(self, **kwargs):
        self.row = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(str(kwargs["workspace_id"])),
            provider=kwargs["provider"],
            encrypted_api_key=kwargs["encrypted_api_key"],
            api_key_fingerprint=kwargs["api_key_fingerprint"],
            api_key_masked=kwargs["api_key_masked"],
            status=kwargs["status"],
            last_validated_at=kwargs["last_validated_at"],
            last_validation_error=kwargs["last_validation_error"],
            deleted_at=None,
        )
        return self.row

    async def soft_delete_active(self, workspace_id: str, *, user_id=None, provider="openrouter"):
        if self.row is None:
            return False
        self.row.status = "deleted"
        self.row.deleted_at = datetime.now(timezone.utc)
        return True


class FakeConfigRepo:
    def __init__(self) -> None:
        self.rows = {}

    async def list_for_workspace(self, workspace_id: str):
        return list(self.rows.values())

    async def get_for_agent(self, workspace_id: str, agent_key: str):
        return self.rows.get(agent_key)

    async def upsert(self, **kwargs):
        row = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(str(kwargs["workspace_id"])),
            agent_key=kwargs["agent_key"],
            provider=kwargs["provider"],
            model=kwargs["model"],
            temperature=kwargs["temperature"],
            max_tokens=kwargs["max_tokens"],
            timeout_s=kwargs["timeout_s"],
            extra_body=kwargs["extra_body"],
            enabled=kwargs["enabled"],
            updated_at=datetime.now(timezone.utc),
        )
        self.rows[row.agent_key] = row
        return row


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def workspace_id() -> str:
    return str(uuid.uuid4())


def _service(
    credential_repo: FakeCredentialRepo,
    config_repo: FakeConfigRepo,
    fernet_key: str,
    *,
    validator_ok: bool = True,
) -> ModelConfigService:
    return ModelConfigService(
        credential_repo=credential_repo,  # type: ignore[arg-type]
        config_repo=config_repo,  # type: ignore[arg-type]
        fernet_key=fernet_key,
        validator=FakeValidator(ok=validator_ok),
    )


@pytest.mark.asyncio
async def test_upsert_openrouter_key_encrypts_and_masks(
    workspace_id: str,
    fernet_key: str,
) -> None:
    credential_repo = FakeCredentialRepo()
    config_repo = FakeConfigRepo()
    service = _service(credential_repo, config_repo, fernet_key)

    status = await service.upsert_openrouter_key(
        workspace_id,
        str(uuid.uuid4()),
        " sk-or-test-secret-1234 ",
    )

    assert status.configured is True
    assert status.status == "active"
    assert status.masked_key == "sk-or...1234"
    assert "sk-or-test-secret-1234" not in credential_repo.row.encrypted_api_key
    assert (
        decrypt_api_key(credential_repo.row.encrypted_api_key, fernet_key=fernet_key)
        == "sk-or-test-secret-1234"
    )


@pytest.mark.asyncio
async def test_upsert_agent_config_validates_catalog_and_extra_body(
    workspace_id: str,
    fernet_key: str,
) -> None:
    service = _service(FakeCredentialRepo(), FakeConfigRepo(), fernet_key)

    with pytest.raises(UnknownAgentKeyError):
        await service.upsert_agent_config(
            workspace_id,
            str(uuid.uuid4()),
            "missing.agent",
            AgentModelConfigUpdate(model="anthropic/claude-sonnet-4-6"),
        )

    with pytest.raises(ModelConfigValidationError):
        await service.upsert_agent_config(
            workspace_id,
            str(uuid.uuid4()),
            "content.brief_builder",
            AgentModelConfigUpdate(
                model="anthropic/claude-sonnet-4-6",
                extra_body={"api_key": "secret"},
            ),
        )


@pytest.mark.asyncio
async def test_preflight_fails_closed_when_missing_credential(
    workspace_id: str,
    fernet_key: str,
) -> None:
    service = _service(FakeCredentialRepo(), FakeConfigRepo(), fernet_key)

    result = await service.preflight(workspace_id, ["content.brief_builder"])

    assert result.ok is False
    assert result.missing_credential is True
    assert result.errors == ["missing_credential"]


@pytest.mark.asyncio
async def test_resolver_returns_decrypted_workspace_config(
    workspace_id: str,
    fernet_key: str,
) -> None:
    credential_repo = FakeCredentialRepo()
    config_repo = FakeConfigRepo()
    service = _service(credential_repo, config_repo, fernet_key)
    await service.upsert_openrouter_key(workspace_id, str(uuid.uuid4()), "sk-or-secret")
    await service.upsert_agent_config(
        workspace_id,
        str(uuid.uuid4()),
        "content.brief_builder",
        AgentModelConfigUpdate(model="claude-sonnet-4-6", temperature=0.2),
    )
    resolver = ModelConfigResolver(
        credential_repo=credential_repo,  # type: ignore[arg-type]
        config_repo=config_repo,  # type: ignore[arg-type]
        fernet_key=fernet_key,
        base_url="https://openrouter.test/api/v1",
    )

    resolved = await resolver.resolve(
        workspace_id,
        "test-co",
        "content.brief_builder",
    )

    assert resolved.api_key == "sk-or-secret"
    assert resolved.model == "anthropic/claude-sonnet-4-6"
    assert resolved.temperature == 0.2
    assert resolved.credential_id
    assert resolved.model_config_id


@pytest.mark.asyncio
async def test_resolver_fails_closed_for_missing_or_disabled_config(
    workspace_id: str,
    fernet_key: str,
) -> None:
    credential_repo = FakeCredentialRepo()
    config_repo = FakeConfigRepo()
    resolver = ModelConfigResolver(
        credential_repo=credential_repo,  # type: ignore[arg-type]
        config_repo=config_repo,  # type: ignore[arg-type]
        fernet_key=fernet_key,
    )

    with pytest.raises(MissingCredentialError):
        await resolver.resolve(workspace_id, "test-co", "content.brief_builder")

    service = _service(credential_repo, config_repo, fernet_key)
    await service.upsert_openrouter_key(workspace_id, str(uuid.uuid4()), "sk-or-secret")
    await service.upsert_agent_config(
        workspace_id,
        str(uuid.uuid4()),
        "content.brief_builder",
        AgentModelConfigUpdate(
            model="anthropic/claude-sonnet-4-6",
            enabled=False,
        ),
    )

    with pytest.raises(DisabledAgentError):
        await resolver.resolve(workspace_id, "test-co", "content.brief_builder")
