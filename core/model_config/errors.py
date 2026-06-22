"""Typed BYOK model configuration errors."""
from __future__ import annotations


class ModelConfigError(RuntimeError):
    """Base class for model configuration failures."""


class MissingCredentialError(ModelConfigError):
    """Workspace has no active OpenRouter credential."""


class InvalidCredentialError(ModelConfigError):
    """Workspace credential exists but is not active/valid."""


class UnknownAgentKeyError(ModelConfigError):
    """Agent key does not exist in the catalog."""


class DisabledAgentError(ModelConfigError):
    """Agent exists but is disabled for this workspace."""


class ModelConfigValidationError(ModelConfigError):
    """Model config update failed validation."""
