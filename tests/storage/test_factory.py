"""Tests for get_storage_backend() factory — backend switching logic."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.storage.backends.local import LocalStorageBackend


class TestStorageFactory:
    def test_default_returns_local_backend(self, tmp_path: Path) -> None:
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "local"
            from core.storage import get_storage_backend

            backend = get_storage_backend(tmp_path)
            assert isinstance(backend, LocalStorageBackend)
            assert backend.root == tmp_path.resolve()

    def test_local_with_custom_root(self, tmp_path: Path) -> None:
        custom_root = tmp_path / "custom_artifacts"
        custom_root.mkdir()
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "local"
            from core.storage import get_storage_backend

            backend = get_storage_backend(custom_root)
            assert isinstance(backend, LocalStorageBackend)
            assert backend.root == custom_root.resolve()

    def test_r2_returns_r2_backend(self) -> None:
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "r2"
            mock_settings.r2_bucket_name = "test-bucket"
            mock_settings.effective_r2_endpoint_url = "https://acct.r2.cloudflarestorage.com"
            mock_settings.r2_access_key_id = "key"
            mock_settings.r2_secret_access_key = "secret"

            with patch("core.storage.backends.r2.boto3"):
                from core.storage import get_storage_backend
                from core.storage.backends.r2 import R2StorageBackend

                backend = get_storage_backend()
                assert isinstance(backend, R2StorageBackend)

    def test_r2_missing_bucket_raises(self) -> None:
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "r2"
            mock_settings.r2_bucket_name = None
            mock_settings.effective_r2_endpoint_url = "https://acct.r2.cloudflarestorage.com"
            mock_settings.r2_access_key_id = "key"
            mock_settings.r2_secret_access_key = "secret"

            from core.storage import get_storage_backend

            with pytest.raises(ValueError, match="R2_BUCKET_NAME"):
                get_storage_backend()

    def test_r2_missing_endpoint_raises(self) -> None:
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "r2"
            mock_settings.r2_bucket_name = "bucket"
            mock_settings.effective_r2_endpoint_url = None
            mock_settings.r2_access_key_id = "key"
            mock_settings.r2_secret_access_key = "secret"

            from core.storage import get_storage_backend

            with pytest.raises(ValueError, match="R2_ACCOUNT_ID"):
                get_storage_backend()

    def test_r2_missing_access_key_raises(self) -> None:
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "r2"
            mock_settings.r2_bucket_name = "bucket"
            mock_settings.effective_r2_endpoint_url = "https://x"
            mock_settings.r2_access_key_id = None
            mock_settings.r2_secret_access_key = "secret"

            from core.storage import get_storage_backend

            with pytest.raises(ValueError, match="R2_ACCESS_KEY_ID"):
                get_storage_backend()

    def test_r2_missing_secret_key_raises(self) -> None:
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.storage_backend = "r2"
            mock_settings.r2_bucket_name = "bucket"
            mock_settings.effective_r2_endpoint_url = "https://x"
            mock_settings.r2_access_key_id = "key"
            mock_settings.r2_secret_access_key = None

            from core.storage import get_storage_backend

            with pytest.raises(ValueError, match="R2_SECRET_ACCESS_KEY"):
                get_storage_backend()
