"""Tests for R2 storage backend settings fields."""
from __future__ import annotations

import pytest


class TestR2SettingsDefaults:
    """Verify R2 storage backend is the default, with R2 credential fields defaulting to None."""

    def test_storage_backend_defaults_to_r2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The hardcoded default in Settings is 'r2' (env files or env vars may override)."""
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        from core.config.settings import Settings
        # Build Settings without env files to test the pure class default
        s = Settings(_env_file=None)
        assert s.storage_backend == "r2"

    def test_r2_fields_default_to_none(self) -> None:
        from core.config.settings import Settings
        s = Settings()
        assert s.r2_account_id is None
        assert s.r2_access_key_id is None
        assert s.r2_secret_access_key is None
        assert s.r2_bucket_name is None
        assert s.r2_endpoint_url is None


class TestEffectiveR2EndpointUrl:
    """Verify the derived endpoint URL property."""

    def test_explicit_endpoint_takes_precedence(self) -> None:
        from core.config.settings import Settings
        s = Settings(
            r2_account_id="abc123",
            r2_endpoint_url="https://custom.endpoint.dev",
        )
        assert s.effective_r2_endpoint_url == "https://custom.endpoint.dev"

    def test_derived_from_account_id(self) -> None:
        from core.config.settings import Settings
        s = Settings(r2_account_id="abc123")
        assert s.effective_r2_endpoint_url == "https://abc123.r2.cloudflarestorage.com"

    def test_none_when_both_missing(self) -> None:
        from core.config.settings import Settings
        s = Settings()
        assert s.effective_r2_endpoint_url is None

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("R2_ACCOUNT_ID", "from-env")
        monkeypatch.setenv("STORAGE_BACKEND", "r2")
        from core.config.settings import Settings
        s = Settings()
        assert s.storage_backend == "r2"
        assert s.r2_account_id == "from-env"
        assert s.effective_r2_endpoint_url == "https://from-env.r2.cloudflarestorage.com"
