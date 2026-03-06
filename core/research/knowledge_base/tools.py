"""Tool definitions for Knowledge Base agents.

Only `read_file` is needed — for the synthesis agent (Claude Opus via create_react_agent).
Agent 5 (Brand Perception) uses Anthropic's native web_search_20250305 server-side tool.
"""
from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def make_read_file_tool(kb_base_dir: Path):
    """Create a read_file tool scoped to a specific knowledge base directory.

    Security: Only files under kb_base_dir can be read. Path traversal
    is prevented via Path.resolve().is_relative_to().

    Args:
        kb_base_dir: Root directory of the knowledge base (e.g.,
            artifacts/knowledge_base/{slug}).

    Returns:
        A LangChain @tool function.
    """
    resolved_root = kb_base_dir.resolve()

    @tool
    def read_file(file_path: str) -> str:
        """Read a file from the company's knowledge base directory.

        Args:
            file_path: Path to read, relative to the knowledge base root.
                Example: "company_overview/v1.md"
        """
        target = (resolved_root / file_path).resolve()
        if not target.is_relative_to(resolved_root):
            return f"Access denied: path '{file_path}' is outside the knowledge base directory."
        if not target.exists():
            return f"File not found: {file_path}"
        if not target.is_file():
            return f"Not a file: {file_path}"
        try:
            return target.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("read_file failed for %s: %s", file_path, exc)
            return f"Error reading file: {exc}"

    return read_file
