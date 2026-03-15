"""Local filesystem storage backend.

Wraps standard filesystem operations behind the StorageBackend ABC so that
all artifact I/O can later be swapped to S3/GCS without touching business logic.

All writes are atomic (tempfile + os.replace).  Path traversal is blocked.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """Filesystem-backed artifact storage rooted at a single directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def root(self) -> Path:
        """Resolved root directory for this backend."""
        return self._root

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        """Resolve *path* relative to root and validate it stays within root."""
        p = (self._root / path).resolve()
        if not p.is_relative_to(self._root):
            raise ValueError(f"Path escapes storage root: {path!r}")
        return p

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------

    def read(self, path: str) -> Optional[str]:
        """Read artifact content. Returns ``None`` if the file does not exist."""
        p = self._resolve(path)
        if not p.is_file():
            return None
        return p.read_text(encoding="utf-8")

    def write(self, path: str, content: str) -> str:
        """Write *content* atomically (tempfile + os.replace). Creates parent dirs."""
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(p.parent), suffix=".tmp", prefix=p.stem + "_",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(p))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return path

    def exists(self, path: str) -> bool:
        """Check whether a file exists at *path*."""
        p = self._resolve(path)
        return p.exists()

    def delete(self, path: str) -> bool:
        """Delete the file at *path*. Returns ``True`` if it existed."""
        p = self._resolve(path)
        if not p.is_file():
            return False
        p.unlink()
        return True

    def list_dir(self, prefix: str) -> list[str]:
        """List immediate children under *prefix* as relative paths from root.

        Returns an empty list if the directory does not exist.
        Entries are sorted for deterministic ordering.
        """
        d = self._resolve(prefix)
        if not d.is_dir():
            return []
        entries: list[str] = []
        for child in sorted(d.iterdir()):
            # Return path relative to storage root (forward slashes).
            rel = child.relative_to(self._root)
            entries.append(str(rel))
        return entries

    def mkdir(self, path: str) -> None:
        """Create directory (and parents) at *path*."""
        p = self._resolve(path)
        p.mkdir(parents=True, exist_ok=True)
