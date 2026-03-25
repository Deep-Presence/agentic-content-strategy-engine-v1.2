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
    """Base class for artifact storage backends.

    All paths must be relative (no leading ``/``, no ``..`` traversal).
    Implementations validate paths and raise ``ValueError`` on invalid input.
    """

    @abstractmethod
    def read(self, path: str) -> Optional[str]:
        """Read text artifact content by logical path.

        Returns ``None`` if the key does not exist.

        Raises:
            OSError | ClientError: On I/O or permission errors.
        """
        ...

    @abstractmethod
    def write(self, path: str, content: str) -> str:
        """Write text artifact content. Returns the storage key written.

        Implementations SHOULD use atomic writes (temp file + rename).

        Raises:
            OSError | ClientError: On I/O, permission, or quota errors.
        """
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check whether an artifact exists at the given path.

        Returns ``False`` if the key does not exist. Implementations SHOULD
        degrade gracefully to ``False`` on transient I/O errors.

        Raises:
            OSError | ClientError: May raise on permission errors.
        """
        ...

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete an artifact. Returns ``True`` if it existed (idempotent).

        Returns ``False`` if the key was already absent.

        Raises:
            OSError | ClientError: On permission errors.
        """
        ...

    @abstractmethod
    def list_dir(self, prefix: str) -> list[str]:
        """List artifact paths under a prefix.

        Returns an empty list if the prefix has no children.

        Raises:
            OSError | ClientError: On permission errors.
        """
        ...

    @abstractmethod
    def read_bytes(self, path: str) -> Optional[bytes]:
        """Read binary artifact content by logical path.

        Returns ``None`` if the key does not exist.

        Raises:
            OSError | ClientError: On I/O or permission errors.
        """
        ...

    @abstractmethod
    def write_bytes(self, path: str, content: bytes) -> str:
        """Write binary artifact content. Returns the storage key written.

        Implementations SHOULD use atomic writes (temp file + rename).

        Raises:
            OSError | ClientError: On I/O, permission, or quota errors.
        """
        ...

    @abstractmethod
    def mkdir(self, path: str) -> None:
        """Ensure a directory (prefix) exists. No-op for object stores.

        Raises:
            OSError: On permission errors (filesystem backends).
        """
        ...
