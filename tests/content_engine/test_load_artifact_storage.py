"""Tests for _load_artifact_text / _load_artifact_json with StorageBackend support (CX-1 fix)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Import helpers under test
# ---------------------------------------------------------------------------

from core.content_engine.pipeline_v13 import _load_artifact_text, _load_artifact_json


# ---------------------------------------------------------------------------
# _load_artifact_text
# ---------------------------------------------------------------------------


class TestLoadArtifactText:
    """Tests for _load_artifact_text with optional storage parameter."""

    def test_empty_path_returns_empty(self):
        assert _load_artifact_text(None) == ""
        assert _load_artifact_text("") == ""

    def test_with_storage_reads_from_backend(self):
        """When storage is provided and has the key, read from storage."""
        storage = MagicMock()
        storage.read.return_value = "# Company Context\nAcme Corp does widgets."

        result = _load_artifact_text("company_context/acme.md", storage=storage)

        storage.read.assert_called_once_with("company_context/acme.md")
        assert result == "# Company Context\nAcme Corp does widgets."

    def test_storage_returns_none_falls_back_to_filesystem(self, tmp_path: Path, monkeypatch):
        """When storage.read() returns None for a relative key, fall back to filesystem."""
        storage = MagicMock()
        storage.read.return_value = None

        # Create a real file at _PROJECT_ROOT / relative key for filesystem fallback
        import core.content_engine.pipeline_v13 as mod
        monkeypatch.setattr(mod, "_PROJECT_ROOT", tmp_path)

        artifact = tmp_path / "company_context.md"
        artifact.write_text("fallback content", encoding="utf-8")

        result = _load_artifact_text("company_context.md", storage=storage)

        storage.read.assert_called_once_with("company_context.md")
        assert result == "fallback content"

    def test_no_storage_reads_filesystem(self, tmp_path: Path):
        """Without storage, reads from filesystem (backward compat)."""
        artifact = tmp_path / "style_guide.md"
        artifact.write_text("guide content", encoding="utf-8")

        result = _load_artifact_text(str(artifact))

        assert result == "guide content"

    def test_no_storage_nonexistent_file_returns_empty(self):
        """Without storage, nonexistent file returns empty string."""
        result = _load_artifact_text("/nonexistent/path/to/file.md")
        assert result == ""

    def test_storage_none_path_returns_empty(self):
        """None path with storage still returns empty."""
        storage = MagicMock()
        result = _load_artifact_text(None, storage=storage)
        assert result == ""
        storage.read.assert_not_called()

    def test_absolute_path_skips_storage(self, tmp_path: Path):
        """Absolute paths bypass storage and read directly from filesystem."""
        storage = MagicMock()
        artifact = tmp_path / "context.md"
        artifact.write_text("absolute content", encoding="utf-8")

        result = _load_artifact_text(str(artifact), storage=storage)

        storage.read.assert_not_called()
        assert result == "absolute content"


# ---------------------------------------------------------------------------
# _load_artifact_json
# ---------------------------------------------------------------------------


class TestLoadArtifactJson:
    """Tests for _load_artifact_json with optional storage parameter."""

    def test_empty_path_returns_empty_dict(self):
        assert _load_artifact_json(None) == {}
        assert _load_artifact_json("") == {}

    def test_with_storage_reads_json_from_backend(self):
        """When storage has the key, parse JSON from storage content."""
        data = {"topics": [{"name": "AI"}], "company": "Acme"}
        storage = MagicMock()
        storage.read.return_value = json.dumps(data)

        result = _load_artifact_json("gap_analysis/acme/analysis.json", storage=storage)

        storage.read.assert_called_once_with("gap_analysis/acme/analysis.json")
        assert result == data

    def test_storage_returns_none_falls_back_to_filesystem(self, tmp_path: Path, monkeypatch):
        """When storage.read() returns None for a relative key, fall back to filesystem."""
        data = {"key": "value"}
        storage = MagicMock()
        storage.read.return_value = None

        import core.content_engine.pipeline_v13 as mod
        monkeypatch.setattr(mod, "_PROJECT_ROOT", tmp_path)

        artifact = tmp_path / "analysis.json"
        artifact.write_text(json.dumps(data), encoding="utf-8")

        result = _load_artifact_json("analysis.json", storage=storage)
        assert result == data

    def test_no_storage_reads_filesystem(self, tmp_path: Path):
        """Without storage, reads JSON from filesystem."""
        data = {"count": 42}
        artifact = tmp_path / "queries.json"
        artifact.write_text(json.dumps(data), encoding="utf-8")

        result = _load_artifact_json(str(artifact))
        assert result == data

    def test_no_storage_nonexistent_returns_empty_dict(self):
        result = _load_artifact_json("/nonexistent/analysis.json")
        assert result == {}

    def test_storage_invalid_json_returns_empty_dict(self):
        """If storage returns invalid JSON, return empty dict."""
        storage = MagicMock()
        storage.read.return_value = "not valid json {{"

        result = _load_artifact_json("gap_analysis/acme/analysis.json", storage=storage)
        assert result == {}
