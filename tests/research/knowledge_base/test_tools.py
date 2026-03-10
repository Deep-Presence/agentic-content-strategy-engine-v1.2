"""Tests for Knowledge Base tools — read_file factory with path security."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.research.knowledge_base.tools import make_read_file_tool


class TestMakeReadFileTool:
    """Tests for the read_file tool factory."""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "test.md").write_text("Hello world", encoding="utf-8")

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("test.md")
        assert result == "Hello world"

    def test_file_not_found(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("nonexistent.md")
        assert "File not found" in result

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        # Create a file outside the KB dir
        (tmp_path / "secret.txt").write_text("secret data", encoding="utf-8")

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("../secret.txt")
        assert "Access denied" in result

    def test_absolute_path_traversal_blocked(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("/etc/passwd")
        assert "Access denied" in result

    def test_directory_not_readable(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "subdir").mkdir()

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("subdir")
        assert "Not a file" in result

    def test_returns_utf8_content(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "unicode.md").write_text("Héllo wörld 日本語", encoding="utf-8")

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("unicode.md")
        assert "Héllo" in result
        assert "日本語" in result

    def test_tool_has_langchain_metadata(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        tool = make_read_file_tool(kb_dir)
        assert tool.name == "read_file"
        assert tool.description
        assert len(tool.description) > 10

    def test_relative_subdirectory_path(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        sub = kb_dir / "company_overview"
        sub.mkdir(parents=True)
        (sub / "v1.md").write_text("# Overview v1", encoding="utf-8")

        tool = make_read_file_tool(kb_dir)
        result = tool.invoke("company_overview/v1.md")
        assert result == "# Overview v1"
