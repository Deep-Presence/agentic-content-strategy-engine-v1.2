"""Tests for OpenRouter settings fields."""
from __future__ import annotations

import pytest


class TestOpenRouterSettings:
    """Verify openrouter_api_key and openrouter_base_url defaults."""

    def test_openrouter_api_key_defaults_to_none(self):
        from core.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.openrouter_api_key is None

    def test_openrouter_base_url_defaults_to_openrouter(self):
        from core.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.openrouter_base_url == "https://openrouter.ai/api/v1"

    def test_openrouter_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key-123")
        from core.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.openrouter_api_key == "sk-or-test-key-123"

    def test_openrouter_base_url_override_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://custom.example.com/v1")
        from core.config.settings import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.openrouter_base_url == "https://custom.example.com/v1"
