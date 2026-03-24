"""Cloudflare R2 (S3-compatible) storage backend.

Uses boto3 synchronous client for S3-compatible operations against R2.
All methods are synchronous — call sites wrap in asyncio.to_thread() as needed.

Lazy-imported: this module is only loaded when STORAGE_BACKEND=r2.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


class R2StorageBackend(StorageBackend):
    """Cloudflare R2 artifact storage (S3-compatible API)."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "auto",
        *,
        _client: Any = None,
    ) -> None:
        self._bucket_name = bucket_name
        self._client = _client or boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_path(path: str) -> None:
        """Reject paths that attempt directory traversal or use absolute paths."""
        if path.startswith("/"):
            raise ValueError(f"Path must be relative: {path!r}")
        if ".." in path.split("/"):
            raise ValueError(f"Path escapes storage scope: {path!r}")

    @staticmethod
    def _is_not_found(exc: ClientError) -> bool:
        """Check if a ClientError indicates the key was not found."""
        code = exc.response.get("Error", {}).get("Code", "")
        return code in _NOT_FOUND_CODES

    # ------------------------------------------------------------------
    # Text read / write
    # ------------------------------------------------------------------

    def read(self, path: str) -> Optional[str]:
        """Read artifact as UTF-8 text. Returns None if key does not exist."""
        self._validate_path(path)
        data = self.read_bytes(path)
        if data is None:
            return None
        return data.decode("utf-8")

    def write(self, path: str, content: str) -> str:
        """Write UTF-8 text artifact to R2."""
        self._validate_path(path)
        self._client.put_object(
            Bucket=self._bucket_name,
            Key=path,
            Body=content.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
        return path

    # ------------------------------------------------------------------
    # Binary read / write
    # ------------------------------------------------------------------

    def read_bytes(self, path: str) -> Optional[bytes]:
        """Read raw bytes from R2. Returns None if key does not exist."""
        self._validate_path(path)
        try:
            response = self._client.get_object(
                Bucket=self._bucket_name, Key=path
            )
            return response["Body"].read()
        except ClientError as exc:
            if self._is_not_found(exc):
                return None
            raise

    def write_bytes(self, path: str, content: bytes) -> str:
        """Write raw bytes to R2."""
        self._validate_path(path)
        self._client.put_object(
            Bucket=self._bucket_name,
            Key=path,
            Body=content,
            ContentType="application/octet-stream",
        )
        return path

    # ------------------------------------------------------------------
    # exists / delete / list_dir / mkdir
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Check whether a key or prefix exists in R2.

        First checks for an exact object key via HEAD. If not found, checks
        whether any objects exist under ``path/`` (directory-like prefix) to
        match LocalStorageBackend behavior where ``exists()`` returns True
        for both files and directories.
        """
        self._validate_path(path)
        try:
            self._client.head_object(Bucket=self._bucket_name, Key=path)
            return True
        except ClientError as exc:
            if not self._is_not_found(exc):
                raise
        # Fallback: check if it's a prefix with children (directory equivalent)
        prefix = path.rstrip("/") + "/"
        response = self._client.list_objects_v2(
            Bucket=self._bucket_name,
            Prefix=prefix,
            MaxKeys=1,
        )
        return response.get("KeyCount", 0) > 0

    def delete(self, path: str) -> bool:
        """Delete a key from R2. Returns True if it existed, False otherwise.

        Uses head_object to check existence first, then delete_object.
        S3 delete_object is idempotent and doesn't report whether the key existed.
        """
        self._validate_path(path)
        try:
            self._client.head_object(Bucket=self._bucket_name, Key=path)
        except ClientError as exc:
            if self._is_not_found(exc):
                return False
            raise
        self._client.delete_object(Bucket=self._bucket_name, Key=path)
        return True

    def list_dir(self, prefix: str) -> list[str]:
        """List immediate children under *prefix* (files + sub-prefixes).

        Normalizes prefix to ensure trailing ``/``. Uses the S3 paginator to
        handle buckets with >1000 keys. Combines ``Contents`` keys and
        ``CommonPrefixes`` entries, strips trailing ``/`` from prefixes,
        and returns a sorted list matching LocalStorageBackend behavior.
        """
        self._validate_path(prefix)
        # Normalize prefix: ensure trailing /
        if not prefix.endswith("/"):
            prefix = prefix + "/"

        entries: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=self._bucket_name,
            Prefix=prefix,
            Delimiter="/",
        )

        for page in page_iterator:
            # Files at this level
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip directory markers (key == prefix itself)
                if key == prefix:
                    continue
                entries.append(key)

            # Sub-prefixes (subdirectories)
            for cp in page.get("CommonPrefixes", []):
                # Strip trailing / to match LocalStorageBackend behavior
                entries.append(cp["Prefix"].rstrip("/"))

        return sorted(entries)

    def mkdir(self, path: str) -> None:
        """No-op — R2 is a flat key-value store; directories are implicit."""
