"""Model config service fakes for API tests."""
from __future__ import annotations

from core.model_config.schemas import ModelConfigPreflightResult


class PassingModelConfigService:
    """Minimal BYOK config service fake for API route tests."""

    def __init__(self) -> None:
        self.preflight_calls: list[tuple[str, list[str]]] = []

    async def preflight(
        self,
        workspace_id: str,
        agent_keys: list[str],
    ) -> ModelConfigPreflightResult:
        self.preflight_calls.append((workspace_id, list(agent_keys)))
        return ModelConfigPreflightResult(ok=True)


class FailingModelConfigService:
    """Config service fake that simulates a workspace with no BYOK key."""

    def __init__(self) -> None:
        self.preflight_calls: list[tuple[str, list[str]]] = []

    async def preflight(
        self,
        workspace_id: str,
        agent_keys: list[str],
    ) -> ModelConfigPreflightResult:
        self.preflight_calls.append((workspace_id, list(agent_keys)))
        return ModelConfigPreflightResult(
            ok=False,
            missing_credential=True,
            errors=["missing_credential"],
        )
