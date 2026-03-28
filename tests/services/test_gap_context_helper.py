"""Tests for core.services.gap_context_helper — local backend cache eviction."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import core.services.gap_context_helper as helper_mod
from core.services.gap_context_helper import _LOCAL_BACKEND_CACHE, _resolve_storage


@pytest.fixture(autouse=True)
def _clear_backend_cache():
    """Ensure cache is empty before and after each test."""
    _LOCAL_BACKEND_CACHE.clear()
    yield
    _LOCAL_BACKEND_CACHE.clear()


def test_local_backend_cache_evicts_at_max(tmp_path: Path) -> None:
    """When cache hits _LOCAL_BACKEND_CACHE_MAX, the oldest entry is evicted."""
    original_max = helper_mod._LOCAL_BACKEND_CACHE_MAX

    try:
        # Set a small cap for testing
        helper_mod._LOCAL_BACKEND_CACHE_MAX = 3

        # Create 4 distinct directories so LocalStorageBackend can instantiate
        paths = [tmp_path / f"dir_{i}" for i in range(4)]
        for p in paths:
            p.mkdir()

        # Insert first 3 — cache should hold all 3
        for p in paths[:3]:
            _resolve_storage(p)

        assert len(_LOCAL_BACKEND_CACHE) == 3
        assert str(paths[0]) in _LOCAL_BACKEND_CACHE
        assert str(paths[1]) in _LOCAL_BACKEND_CACHE
        assert str(paths[2]) in _LOCAL_BACKEND_CACHE

        # Insert 4th — should evict the oldest (paths[0])
        _resolve_storage(paths[3])

        assert len(_LOCAL_BACKEND_CACHE) == 3
        assert str(paths[0]) not in _LOCAL_BACKEND_CACHE, "oldest entry should be evicted"
        assert str(paths[1]) in _LOCAL_BACKEND_CACHE
        assert str(paths[2]) in _LOCAL_BACKEND_CACHE
        assert str(paths[3]) in _LOCAL_BACKEND_CACHE
    finally:
        helper_mod._LOCAL_BACKEND_CACHE_MAX = original_max


def test_local_backend_cache_returns_cached_instance(tmp_path: Path) -> None:
    """Calling _resolve_storage twice with the same Path returns the same backend."""
    d = tmp_path / "same"
    d.mkdir()

    b1 = _resolve_storage(d)
    b2 = _resolve_storage(d)

    assert b1 is b2
    assert len(_LOCAL_BACKEND_CACHE) == 1


def test_resolve_storage_passthrough_for_backend() -> None:
    """When given a StorageBackend instance, it is returned as-is (no caching)."""
    from unittest.mock import MagicMock
    from core.storage.backends.base import StorageBackend

    mock_backend = MagicMock(spec=StorageBackend)
    result = _resolve_storage(mock_backend)

    assert result is mock_backend
    assert len(_LOCAL_BACKEND_CACHE) == 0
