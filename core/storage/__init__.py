from pathlib import Path
from typing import Optional

from core.storage.backends.base import StorageBackend
from core.storage.backends.local import LocalStorageBackend

__all__ = ["LocalStorageBackend", "R2StorageBackend", "StorageBackend", "get_storage_backend"]


# Lazy import — avoid requiring boto3 at module level
def __getattr__(name: str):
    if name == "R2StorageBackend":
        from core.storage.backends.r2 import R2StorageBackend

        return R2StorageBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_storage_backend(artifacts_root: Optional[Path] = None) -> StorageBackend:
    """Return the configured storage backend.

    Reads ``STORAGE_BACKEND`` from settings:
    - ``"local"`` (default): filesystem-backed via LocalStorageBackend
    - ``"r2"``: Cloudflare R2 via R2StorageBackend (S3-compatible)
    """
    from core.config.settings import settings

    if settings.storage_backend == "r2":
        from core.storage.backends.r2 import R2StorageBackend

        endpoint = settings.effective_r2_endpoint_url
        if not settings.r2_bucket_name:
            raise ValueError("STORAGE_BACKEND=r2 requires R2_BUCKET_NAME")
        if not endpoint:
            raise ValueError(
                "STORAGE_BACKEND=r2 requires R2_ACCOUNT_ID (or R2_ENDPOINT_URL)"
            )
        if not settings.r2_access_key_id:
            raise ValueError("STORAGE_BACKEND=r2 requires R2_ACCESS_KEY_ID")
        if not settings.r2_secret_access_key:
            raise ValueError("STORAGE_BACKEND=r2 requires R2_SECRET_ACCESS_KEY")
        return R2StorageBackend(
            bucket_name=settings.r2_bucket_name,
            endpoint_url=endpoint,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
        )

    root = artifacts_root or Path(__file__).resolve().parents[2] / "artifacts"
    return LocalStorageBackend(root)
