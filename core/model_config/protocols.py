"""Protocols for BYOK model configuration collaborators."""
from __future__ import annotations

from typing import Protocol

from core.model_config.schemas import CredentialTestResult


class OpenRouterCredentialValidator(Protocol):
    async def validate_key(self, api_key: str) -> CredentialTestResult:
        """Validate an OpenRouter key without storing it."""
