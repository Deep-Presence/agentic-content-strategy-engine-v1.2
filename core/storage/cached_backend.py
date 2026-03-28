"""CachedStorageBackend — transparent Redis cache wrapper for any StorageBackend.

Checks Redis before hitting the underlying backend on ``read()`` and
``list_dir()`` calls.  Writes and deletes delegate to the backend and
invalidate the corresponding cache entries.

All cache operations use the shared sync Redis client
(``get_sync_redis_or_none()``) and degrade gracefully when Redis is
unavailable — callers always get correct results, just without caching.
"""
from __future__ import annotations

import logging
from typing import Optional

from core.cache import cache_delete, cache_get, cache_set
from core.redis import get_sync_redis_or_none
from core.storage.backends.base import StorageBackend

_logger = logging.getLogger(__name__)

# Size guard: skip caching reads larger than 512 KB to avoid Redis bloat
_MAX_CACHEABLE_SIZE = 512 * 1024

_READ_TTL = 300   # 5 min — matches existing service TTLs
_LIST_TTL = 120   # 2 min — R2 ListObjectsV2 is expensive


def _parent_prefix(path: str) -> str:
    """Extract the parent directory prefix from a storage path."""
    if "/" in path:
        return path.rsplit("/", 1)[0]
    return ""


class CachedStorageBackend(StorageBackend):
    """Wraps any StorageBackend with Redis TTL cache for reads.

    Cache key schema:
    - ``artifact:{path}`` — cached ``read()`` results (text)
    - ``artifact_ls:{prefix}`` — cached ``list_dir()`` results

    Mutation methods (``write``, ``write_bytes``, ``delete``) delegate to
    the inner backend and invalidate both the path's read cache and the
    parent directory's listing cache.
    """

    def __init__(
        self,
        backend: StorageBackend,
        *,
        default_ttl: int = _READ_TTL,
    ) -> None:
        self._backend = backend
        self._read_ttl = default_ttl

    @property
    def inner(self) -> StorageBackend:
        """Access the wrapped backend directly (e.g. for ``.root``)."""
        return self._backend

    # ── Cached reads ─────────────────────────────────────────────────

    def read(self, path: str) -> Optional[str]:
        redis = get_sync_redis_or_none()
        cache_key = f"artifact:{path}"

        if redis is not None:
            cached = cache_get(redis, cache_key)
            if cached is not None:
                return cached

        content = self._backend.read(path)

        if content is not None and redis is not None:
            if len(content) <= _MAX_CACHEABLE_SIZE:
                cache_set(redis, cache_key, content, ttl=self._read_ttl)

        return content

    def list_dir(self, prefix: str) -> list[str]:
        redis = get_sync_redis_or_none()
        cache_key = f"artifact_ls:{prefix}"

        if redis is not None:
            cached = cache_get(redis, cache_key)
            if cached is not None:
                return cached

        result = self._backend.list_dir(prefix)

        if redis is not None:
            cache_set(redis, cache_key, result, ttl=_LIST_TTL)

        return result

    # ── Mutation (delegate + invalidate) ─────────────────────────────

    def _invalidate(self, path: str) -> None:
        """Delete cached read + parent listing for a mutated path."""
        redis = get_sync_redis_or_none()
        if redis is None:
            return
        keys = [f"artifact:{path}"]
        parent = _parent_prefix(path)
        if parent:
            keys.append(f"artifact_ls:{parent}")
        cache_delete(redis, *keys)

    def write(self, path: str, content: str) -> str:
        result = self._backend.write(path, content)
        self._invalidate(path)
        return result

    def write_bytes(self, path: str, content: bytes) -> str:
        result = self._backend.write_bytes(path, content)
        self._invalidate(path)
        return result

    def delete(self, path: str) -> bool:
        result = self._backend.delete(path)
        self._invalidate(path)
        return result

    # ── Pure delegation (no caching benefit) ─────────────────────────

    def read_bytes(self, path: str) -> Optional[bytes]:
        return self._backend.read_bytes(path)

    def exists(self, path: str) -> bool:
        return self._backend.exists(path)

    def mkdir(self, path: str) -> None:
        self._backend.mkdir(path)
