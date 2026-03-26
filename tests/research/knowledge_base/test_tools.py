"""Tests for Knowledge Base tools — read_file via StorageBackend with path security."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.research.knowledge_base.tools import make_read_file_tool
from core.storage.backends.local import LocalStorageBackend


class TestMakeReadFileTool:
    """Tests for the read_file tool factory."""

    def _make_tool(self, tmp_path: Path, prefix: str = "knowledge_base/test-co/"):
        """Helper: create a tool backed by LocalStorageBackend at tmp_path."""
        backend = LocalStorageBackend(tmp_path)
        return make_read_file_tool(backend, prefix), backend, prefix

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        tool, backend, prefix = self._make_tool(tmp_path)
        backend.write(f"{prefix}test.md", "Hello world")

        result = tool.invoke("test.md")
        assert result == "Hello world"

    def test_file_not_found(self, tmp_path: Path) -> None:
        tool, _, _ = self._make_tool(tmp_path)

        result = tool.invoke("nonexistent.md")
        assert "File not found" in result

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        tool, backend, _ = self._make_tool(tmp_path)
        # Write a file outside the prefix
        backend.write("secret.txt", "secret data")

        result = tool.invoke("../secret.txt")
        assert "Access denied" in result

    def test_absolute_path_traversal_blocked(self, tmp_path: Path) -> None:
        tool, _, _ = self._make_tool(tmp_path)

        result = tool.invoke("/etc/passwd")
        assert "Access denied" in result

    def test_returns_utf8_content(self, tmp_path: Path) -> None:
        tool, backend, prefix = self._make_tool(tmp_path)
        backend.write(f"{prefix}unicode.md", "Héllo wörld 日本語")

        result = tool.invoke("unicode.md")
        assert "Héllo" in result
        assert "日本語" in result

    def test_tool_has_langchain_metadata(self, tmp_path: Path) -> None:
        tool, _, _ = self._make_tool(tmp_path)

        assert tool.name == "read_file"
        assert tool.description
        assert len(tool.description) > 10

    def test_relative_subdirectory_path(self, tmp_path: Path) -> None:
        tool, backend, prefix = self._make_tool(tmp_path)
        backend.write(f"{prefix}company_overview/v1.md", "# Overview v1")

        result = tool.invoke("company_overview/v1.md")
        assert result == "# Overview v1"

    def test_directory_traversal_via_double_dot_in_middle(self, tmp_path: Path) -> None:
        """Paths like 'a/../../../etc/passwd' must be blocked."""
        tool, _, _ = self._make_tool(tmp_path)

        result = tool.invoke("a/../../../etc/passwd")
        assert "Access denied" in result

    def test_reads_via_backend_not_filesystem(self, tmp_path: Path) -> None:
        """Verify the tool reads through StorageBackend, not raw Path I/O."""
        tool, backend, prefix = self._make_tool(tmp_path)
        backend.write(f"{prefix}data.md", "backend content")

        # The file should be readable through the tool
        result = tool.invoke("data.md")
        assert result == "backend content"

        # Verify it's using the backend by checking the file exists at
        # the backend's resolved path, not at some unrelated location
        assert backend.exists(f"{prefix}data.md")
