"""Unit tests for CachedStorageBackend (core/storage/cached_backend.py).

Uses a real LocalStorageBackend(tmp_path) as the inner backend and a mock
Redis client to verify cache hit/miss/invalidation behaviour.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.storage.backends.local import LocalStorageBackend
from core.storage.cached_backend import CachedStorageBackend, _MAX_CACHEABLE_SIZE


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def inner(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(tmp_path)


@pytest.fixture()
def mock_redis() -> MagicMock:
    r = MagicMock()
    r.get.return_value = None  # Default: cache miss
    return r


# ── read() ───────────────────────────────────────────────────────────


class TestRead:
    def test_cache_miss_reads_from_backend_and_populates(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        inner.write("data/file.txt", "hello world")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.read("data/file.txt")

        assert result == "hello world"
        # Should populate cache
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == "artifact:data/file.txt"
        assert call_args[1] == 300  # default TTL

    def test_cache_hit_returns_cached_value(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        mock_redis.get.return_value = json.dumps("cached content")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.read("data/file.txt")

        assert result == "cached content"

    def test_none_not_cached(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        """read() returning None (file does not exist) should NOT be cached."""
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.read("nonexistent.txt")

        assert result is None
        mock_redis.setex.assert_not_called()

    def test_large_file_not_cached(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        """Files larger than _MAX_CACHEABLE_SIZE should not be cached in Redis."""
        large_content = "x" * (_MAX_CACHEABLE_SIZE + 1)
        inner.write("big.json", large_content)
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.read("big.json")

        assert result == large_content
        mock_redis.setex.assert_not_called()

    def test_graceful_degradation_without_redis(
        self, inner: LocalStorageBackend,
    ) -> None:
        """When Redis is unavailable, read() still works via backend."""
        inner.write("data/file.txt", "direct read")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=None,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.read("data/file.txt")

        assert result == "direct read"


# ── list_dir() ───────────────────────────────────────────────────────


class TestListDir:
    def test_cache_miss_reads_from_backend_and_populates(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        inner.write("mydir/a.txt", "a")
        inner.write("mydir/b.txt", "b")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.list_dir("mydir")

        assert sorted(result) == ["mydir/a.txt", "mydir/b.txt"]
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == "artifact_ls:mydir"
        assert call_args[1] == 120  # list TTL

    def test_cache_hit_returns_cached_list(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        mock_redis.get.return_value = json.dumps(["mydir/cached.txt"])
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.list_dir("mydir")

        assert result == ["mydir/cached.txt"]

    def test_empty_list_cached(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        """Empty list_dir results should be cached (prevents repeated R2 calls)."""
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.list_dir("nonexistent")

        assert result == []
        mock_redis.setex.assert_called_once()


# ── write() invalidation ─────────────────────────────────────────────


class TestWriteInvalidation:
    def test_write_invalidates_read_and_parent_list(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            cb.write("gap_analysis/ramp/analysis.json", '{"data": true}')

        # Should delegate to backend
        assert inner.read("gap_analysis/ramp/analysis.json") == '{"data": true}'
        # Should invalidate both keys
        mock_redis.delete.assert_called_once_with(
            "artifact:gap_analysis/ramp/analysis.json",
            "artifact_ls:gap_analysis/ramp",
        )

    def test_write_bytes_invalidates(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            cb.write_bytes("docs/file.bin", b"\x00\x01\x02")

        assert inner.read_bytes("docs/file.bin") == b"\x00\x01\x02"
        mock_redis.delete.assert_called_once_with(
            "artifact:docs/file.bin",
            "artifact_ls:docs",
        )

    def test_write_top_level_file_no_parent_list_key(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        """Writing a file at the root has no parent prefix to invalidate."""
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            cb.write("top.txt", "content")

        mock_redis.delete.assert_called_once_with("artifact:top.txt")


# ── delete() invalidation ────────────────────────────────────────────


class TestDeleteInvalidation:
    def test_delete_invalidates_cache(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        inner.write("content/ramp/blueprints.json", "[]")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            result = cb.delete("content/ramp/blueprints.json")

        assert result is True
        mock_redis.delete.assert_called_once_with(
            "artifact:content/ramp/blueprints.json",
            "artifact_ls:content/ramp",
        )


# ── Pure delegation ──────────────────────────────────────────────────


class TestPureDelegation:
    def test_read_bytes_delegates(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        inner.write_bytes("data.bin", b"binary")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            assert cb.read_bytes("data.bin") == b"binary"
        # No cache operations for read_bytes
        mock_redis.get.assert_not_called()

    def test_exists_delegates(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        inner.write("file.txt", "exists")
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            assert cb.exists("file.txt") is True
            assert cb.exists("nope.txt") is False

    def test_mkdir_delegates(
        self, inner: LocalStorageBackend, mock_redis: MagicMock,
    ) -> None:
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            cb = CachedStorageBackend(inner)
            cb.mkdir("new_dir")
        assert (inner.root / "new_dir").is_dir()


# ── inner property ───────────────────────────────────────────────────


class TestInnerProperty:
    def test_inner_returns_wrapped_backend(
        self, inner: LocalStorageBackend,
    ) -> None:
        with patch(
            "core.storage.cached_backend.get_sync_redis_or_none",
            return_value=None,
        ):
            cb = CachedStorageBackend(inner)
            assert cb.inner is inner
