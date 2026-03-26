"""Tests for S2 _read_text() StorageBackend support (C2 fix + H3 fix)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from core.gap_analysis.steps.s2_generate_queries import _read_text
from core.storage.backends.local import LocalStorageBackend


class TestReadTextWithStorage:
    """C2: _read_text() should read from StorageBackend when provided."""

    def test_reads_from_storage_backend(self) -> None:
        storage = MagicMock()
        storage.read.return_value = "# Company context content"
        result = _read_text("company_context/ramp.md", storage=storage)
        assert result == "# Company context content"
        storage.read.assert_called_once_with("company_context/ramp.md")

    def test_truncates_to_max_chars(self) -> None:
        storage = MagicMock()
        storage.read.return_value = "A" * 500
        result = _read_text("key.md", max_chars=100, storage=storage)
        assert len(result) == 100

    def test_storage_none_returns_none_falls_back_to_filesystem(self, tmp_path: Path) -> None:
        """When storage.read() returns None, fall back to filesystem."""
        storage = MagicMock()
        storage.read.return_value = None
        # No file on disk either — should return empty string
        result = _read_text("nonexistent/key.md", storage=storage)
        assert result == ""

    def test_no_storage_uses_filesystem(self, tmp_path: Path) -> None:
        """When storage is None, use filesystem (backward compat)."""
        # _read_text resolves relative to _CONTENT_ENGINE_ROOT
        # A non-existent path should return empty string
        result = _read_text("nonexistent_file_for_test.md")
        assert result == ""

    def test_empty_path_returns_empty(self) -> None:
        storage = MagicMock()
        assert _read_text(None, storage=storage) == ""
        assert _read_text("", storage=storage) == ""
        storage.read.assert_not_called()

    def test_none_storage_none_path(self) -> None:
        assert _read_text(None) == ""
        assert _read_text("") == ""


class TestReadTextH3NoFilesystemFallback:
    """H3: Non-local backends must NOT fall back to local filesystem."""

    def test_non_local_storage_no_filesystem_fallback(self, monkeypatch: "pytest.MonkeyPatch") -> None:
        """When storage is non-local and read() returns None, return '' — don't touch disk."""
        import core.gap_analysis.steps.s2_generate_queries as s2_mod

        storage = MagicMock()  # Not a LocalStorageBackend
        storage.read.return_value = None

        # Patch _resolve_virtual_path to detect if filesystem fallback is attempted
        resolve_called = False
        original_resolve = s2_mod._resolve_virtual_path

        def _tracking_resolve(vpath: str) -> Path:
            nonlocal resolve_called
            resolve_called = True
            return original_resolve(vpath)

        monkeypatch.setattr(s2_mod, "_resolve_virtual_path", _tracking_resolve)

        result = _read_text("company_context/acme.md", storage=storage)
        assert result == ""
        assert not resolve_called, "Filesystem fallback should NOT be called for non-local storage"

    def test_local_storage_does_filesystem_fallback(self, monkeypatch: "pytest.MonkeyPatch") -> None:
        """LocalStorageBackend should still allow filesystem fallback."""
        import core.gap_analysis.steps.s2_generate_queries as s2_mod

        local_storage = MagicMock(spec=LocalStorageBackend)
        local_storage.read.return_value = None

        resolve_called = False
        original_resolve = s2_mod._resolve_virtual_path

        def _tracking_resolve(vpath: str) -> Path:
            nonlocal resolve_called
            resolve_called = True
            return original_resolve(vpath)

        monkeypatch.setattr(s2_mod, "_resolve_virtual_path", _tracking_resolve)

        result = _read_text("nonexistent.md", storage=local_storage)
        assert result == ""
        assert resolve_called, "Filesystem fallback SHOULD be called for LocalStorageBackend"
