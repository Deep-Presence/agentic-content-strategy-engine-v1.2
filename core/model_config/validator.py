"""OpenRouter credential validation."""
from __future__ import annotations

from core.model_config.schemas import CredentialTestResult
from core.shared_tools.openrouter_client import build_async_client_for_key


class LiveOpenRouterCredentialValidator:
    """Validate keys against OpenRouter with a minimal models-list request."""

    async def validate_key(self, api_key: str) -> CredentialTestResult:
        try:
            client = build_async_client_for_key(api_key)
            await client.models.list()
            return CredentialTestResult(ok=True, model="models.list")
        except Exception as exc:  # noqa: BLE001
            return CredentialTestResult(ok=False, error=str(exc))
