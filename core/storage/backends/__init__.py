from core.storage.backends.base import StorageBackend
from core.storage.backends.local import LocalStorageBackend

__all__ = ["LocalStorageBackend", "R2StorageBackend", "StorageBackend"]


# Lazy import — avoid requiring boto3 at module level
def __getattr__(name: str):
    if name == "R2StorageBackend":
        from core.storage.backends.r2 import R2StorageBackend

        return R2StorageBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
