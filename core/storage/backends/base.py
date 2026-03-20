"""Abstract StorageBackend interface.

All artifact read/write operations should go through a StorageBackend so the
underlying persistence layer (local filesystem, S3, GCS, Supabase Storage) can
be swapped via configuration without touching business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class StorageBackend(ABC):
    """Base class for artifact storage backends."""

    @abstractmethod
    def read(self, path: str) -> Optional[str]:
        """Read artifact content by logical path. Returns None if not found."""
        ...

    @abstractmethod
    def write(self, path: str, content: str) -> str:
        """Write artifact content. Returns the resolved path."""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check whether an artifact exists at the given path."""
        ...

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete an artifact. Returns True if it existed."""
        ...

    @abstractmethod
    def list_dir(self, prefix: str) -> list[str]:
        """List artifact paths under a prefix."""
        ...

    @abstractmethod
    def mkdir(self, path: str) -> None:
        """Ensure a directory (prefix) exists. No-op for object stores."""
        ...
