import logging
from pathlib import Path
from typing import Optional

from core.storage.backends.base import StorageBackend
from core.storage.backends.local import LocalStorageBackend
from core.storage.cached_backend import CachedStorageBackend

__all__ = [
    "CachedStorageBackend",
    "LocalStorageBackend",
    "R2StorageBackend",
    "StorageBackend",
    "get_storage_backend",
]

_logger = logging.getLogger(__name__)

# Lazy import — avoid requiring boto3 at module level
def __getattr__(name: str):
    if name == "R2StorageBackend":
        from core.storage.backends.r2 import R2StorageBackend

        return R2StorageBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _sanitize_r2_endpoint(endpoint: str, bucket_name: str) -> tuple[str, str]:
    """Detect and fix bucket name appended to the endpoint URL.

    Common misconfiguration: setting R2_ENDPOINT_URL to
    ``https://<account>.r2.cloudflarestorage.com/<bucket>`` instead of
    ``https://<account>.r2.cloudflarestorage.com``.  boto3 prepends the
    bucket to every request path, so the doubled bucket causes all keys
    to be stored under a ``{bucket}/`` prefix.

    Returns (clean_endpoint, key_prefix) where key_prefix is non-empty
    when existing data was written with the misconfigured URL.
    """
    suffix = f"/{bucket_name}"
    if endpoint.endswith(suffix):
        fixed = endpoint[: -len(suffix)]
        _logger.warning(
            "R2_ENDPOINT_URL had bucket name appended (%s) — stripped to %s. "
            "Existing data has '%s/' key prefix (auto-compensated). "
            "Fix your env var to avoid this warning.",
            endpoint, fixed, bucket_name,
        )
        return fixed, f"{bucket_name}/"
    return endpoint, ""


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

        endpoint, key_prefix = _sanitize_r2_endpoint(endpoint, settings.r2_bucket_name)

        return R2StorageBackend(
            bucket_name=settings.r2_bucket_name,
            endpoint_url=endpoint,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            key_prefix=key_prefix,
        )

    root = artifacts_root or Path(__file__).resolve().parents[2] / "artifacts"
    return LocalStorageBackend(root)
