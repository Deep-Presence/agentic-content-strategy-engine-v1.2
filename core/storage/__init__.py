from pathlib import Path
from typing import Optional

from core.storage.backends.base import StorageBackend
from core.storage.backends.local import LocalStorageBackend

__all__ = ["LocalStorageBackend", "StorageBackend", "get_storage_backend"]


def get_storage_backend(artifacts_root: Optional[Path] = None) -> StorageBackend:
    """Return the configured storage backend.

    Currently returns LocalStorageBackend. When blob storage (S3/GCS) is
    added, this function switches based on config — single DI point.
    """
    root = artifacts_root or Path(__file__).resolve().parents[2] / "artifacts"
    return LocalStorageBackend(root)
