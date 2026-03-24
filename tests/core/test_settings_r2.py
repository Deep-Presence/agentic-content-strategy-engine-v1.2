"""Tests for R2 storage backend settings fields."""
from __future__ import annotations

import pytest


class TestR2SettingsDefaults:
    """Verify R2 fields default to safe values (no R2 unless explicitly configured)."""

    def test_storage_backend_defaults_to_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        from core.config.settings import Settings
        s = Settings()
        assert s.storage_backend == "local"

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
