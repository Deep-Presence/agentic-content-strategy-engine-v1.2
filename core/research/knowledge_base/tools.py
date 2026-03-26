"""Tool definitions for Knowledge Base agents.

Only `read_file` is needed — for the synthesis agent (Claude Opus via create_react_agent).
Agent 5 (Brand Perception) uses Anthropic's native web_search_20250305 server-side tool.
"""
from __future__ import annotations

import logging
from pathlib import PurePosixPath

from langchain_core.tools import tool

from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


def make_read_file_tool(backend: StorageBackend, prefix: str):
    """Create a read_file tool that reads via a StorageBackend.

    Works identically whether the backend is local filesystem or R2 (cloud).

    Security: Path traversal is prevented by normalising the requested path
    and checking it doesn't escape the prefix.

    Args:
        backend: StorageBackend instance (local or R2).
        prefix: Key prefix for the knowledge base slug
            (e.g. ``knowledge_base/{slug}/``).

    Returns:
        A LangChain @tool function.
    """

    @tool
    def read_file(file_path: str) -> str:
        """Read a file from the company's knowledge base directory.

        Args:
            file_path: Path to read, relative to the knowledge base root.
                Example: "company_overview/v1.md"
        """
        # Security: block absolute paths
        if file_path.startswith("/"):
            return f"Access denied: path '{file_path}' is outside the knowledge base directory."

        # Security: normalise and block traversal (.. escaping prefix)
        normalised = PurePosixPath(file_path)
        try:
            # Resolve ".." components — if it escapes, parts will start
            # with ".."
            resolved_parts = []
            for part in normalised.parts:
                if part == "..":
                    if not resolved_parts:
                        return f"Access denied: path '{file_path}' is outside the knowledge base directory."
                    resolved_parts.pop()
                else:
                    resolved_parts.append(part)
            clean_path = "/".join(resolved_parts)
        except Exception:
            return f"Access denied: path '{file_path}' is outside the knowledge base directory."

        key = f"{prefix}{clean_path}"
        try:
            content = backend.read(key)
            if content is None:
                return f"File not found: {file_path}"
            return content
        except Exception as exc:
            logger.warning("read_file failed for %s: %s", file_path, exc)
            return f"Error reading file: {exc}"

    return read_file
