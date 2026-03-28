"""Unit tests for core/cache.py and Redis cache integration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── core/cache.py unit tests ────────────────────────────────────────


class TestCacheGet:
    def test_returns_none_on_miss(self):
        """cache_get returns None when Redis returns None (cache miss)."""
        from core.cache import cache_get

        r = MagicMock()
        r.get.return_value = None
        assert cache_get(r, "cache:gap:ramp:analysis.json") is None
        r.get.assert_called_once_with("cache:gap:ramp:analysis.json")

    def test_returns_parsed_json_on_hit(self):
        """cache_get returns parsed JSON dict on cache hit."""
        from core.cache import cache_get

        r = MagicMock()
        r.get.return_value = '{"a": 1, "b": [2, 3]}'
        result = cache_get(r, "cache:gap:ramp:analysis.json")
        assert result == {"a": 1, "b": [2, 3]}

    def test_returns_none_on_redis_error(self):
        """cache_get returns None on Redis connection error (graceful degradation)."""
        from core.cache import cache_get

        r = MagicMock()
        r.get.side_effect = ConnectionError("Redis unavailable")
        assert cache_get(r, "cache:gap:ramp:analysis.json") is None


class TestCacheSet:
    def test_writes_json_with_ttl(self):
        """cache_set writes JSON-serialized value with TTL via setex."""
        from core.cache import cache_set

        r = MagicMock()
        cache_set(r, "cache:gap:ramp:analysis.json", {"a": 1}, ttl=300)
        r.setex.assert_called_once_with(
            "cache:gap:ramp:analysis.json", 300, json.dumps({"a": 1}, default=str)
        )

    def test_swallows_errors(self):
        """cache_set does not propagate Redis errors."""
        from core.cache import cache_set

        r = MagicMock()
        r.setex.side_effect = Exception("write failed")
        # Should not raise
        cache_set(r, "key", {"data": True})


class TestCacheDeletePattern:
    def test_deletes_matching_keys(self):
        """cache_delete_pattern finds and deletes all matching keys via SCAN."""
        from core.cache import cache_delete_pattern

        r = MagicMock()
        r.scan_iter.return_value = iter([
            "cache:gap:ramp:analysis.json",
            "cache:gap:ramp:gap_report.json",
            "cache:gap:ramp:enriched_citations.json",
        ])
        r.delete.return_value = 3
        count = cache_delete_pattern(r, "cache:gap:ramp:*")
        assert count == 3
        r.scan_iter.assert_called_once_with(match="cache:gap:ramp:*", count=500)
        r.delete.assert_called_once_with(
            "cache:gap:ramp:analysis.json",
            "cache:gap:ramp:gap_report.json",
            "cache:gap:ramp:enriched_citations.json",
        )

    def test_returns_zero_on_no_matches(self):
        """cache_delete_pattern returns 0 when no keys match."""
        from core.cache import cache_delete_pattern

        r = MagicMock()
        r.scan_iter.return_value = iter([])
        assert cache_delete_pattern(r, "cache:gap:nonexistent:*") == 0
        r.delete.assert_not_called()

    def test_batches_large_key_sets(self):
        """cache_delete_pattern batches DELETE calls for large key sets."""
        from core.cache import cache_delete_pattern

        r = MagicMock()
        # 3 keys with batch_size=2 → two DELETE calls
        r.scan_iter.return_value = iter(["k1", "k2", "k3"])
        r.delete.side_effect = [2, 1]

        count = cache_delete_pattern(r, "prefix:*", _batch_size=2)
        assert count == 3
        assert r.delete.call_count == 2


# ── Service integration tests ───────────────────────────────────────


class TestGapDataServiceCache:
    @staticmethod
    def _make_storage(tmp_path: Path):
        from core.storage.backends.local import LocalStorageBackend
        return LocalStorageBackend(tmp_path)

    def test_returns_from_redis_on_hit(self, tmp_path: Path):
        """When Redis has cached data, file should NOT be read."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = '{"queries": [{"text": "test"}]}'

        with patch(
            "api.services.gap_data_service.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            from api.services.gap_data_service import _load_json_cached

            result = _load_json_cached(self._make_storage(tmp_path), "test-co", "analysis.json")

        assert result == {"queries": [{"text": "test"}]}

    def test_reads_file_and_populates_on_miss(self, tmp_path: Path):
        """On cache miss, file is read and cache is populated."""
        gap_dir = tmp_path / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        (gap_dir / "analysis.json").write_text('{"queries": []}', encoding="utf-8")

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Cache miss

        with patch(
            "api.services.gap_data_service.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            from api.services.gap_data_service import _load_json_cached

            result = _load_json_cached(self._make_storage(tmp_path), "test-co", "analysis.json")

        assert result == {"queries": []}
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "cache:gap:test-co:analysis.json"
        assert call_args[0][1] == 300  # 5 min TTL

    def test_works_without_redis(self, tmp_path: Path):
        """When Redis is unavailable, file is read directly without errors."""
        gap_dir = tmp_path / "gap_analysis" / "test-co"
        gap_dir.mkdir(parents=True)
        (gap_dir / "analysis.json").write_text('{"data": true}', encoding="utf-8")

        with patch(
            "api.services.gap_data_service.get_sync_redis_or_none",
            return_value=None,
        ):
            from api.services.gap_data_service import _load_json_cached

            result = _load_json_cached(self._make_storage(tmp_path), "test-co", "analysis.json")

        assert result == {"data": True}


class TestContentDataServiceCache:
    def test_uses_correct_ttl_and_key_format(self, tmp_path: Path):
        """Content data service uses 60s TTL for blueprints.json and aligned key format."""
        from core.storage.backends.local import LocalStorageBackend

        # Create file at path StorageBackend will resolve
        content_dir = tmp_path / "content" / "test-co"
        content_dir.mkdir(parents=True)
        (content_dir / "blueprints.json").write_text("[]", encoding="utf-8")

        storage = LocalStorageBackend(tmp_path)
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Cache miss

        with patch(
            "api.services.content_data_service.get_sync_redis_or_none",
            return_value=mock_redis,
        ):
            from api.services.content_data_service import _load_json_cached

            _load_json_cached(storage, "content/test-co/blueprints.json")

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        # Key format must match invalidation pattern cache:content:{slug}:*
        assert call_args[0][0] == "cache:content:test-co:blueprints.json"
        assert call_args[0][1] == 60  # blueprints.json has 60s TTL in _TTL_BY_FILE


class TestPipelineFinalizationCache:
    def test_finalization_invalidates_cache(self):
        """cache_delete_pattern correctly invalidates content cache keys via SCAN."""
        from core.cache import cache_delete_pattern

        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter([
            "cache:content:test-co:blueprints.json",
            "cache:content:test-co:run_metadata_v13.json",
        ])
        mock_redis.delete.return_value = 2

        count = cache_delete_pattern(mock_redis, "cache:content:test-co:*")

        assert count == 2
        mock_redis.scan_iter.assert_called_once_with(match="cache:content:test-co:*", count=500)
        mock_redis.delete.assert_called_once_with(
            "cache:content:test-co:blueprints.json",
            "cache:content:test-co:run_metadata_v13.json",
        )


class TestLargeFileCaching:
    def test_large_file_roundtrip(self):
        """20MB JSON dict survives cache_set/cache_get round-trip."""
        from core.cache import cache_get, cache_set

        # Build a ~20MB dict
        large_data = {f"key_{i}": f"value_{'x' * 1000}" for i in range(20000)}
        serialized = json.dumps(large_data, default=str)

        r = MagicMock()
        # Simulate setex storing the value, then get returning it
        stored = {}

        def fake_setex(key, ttl, value):
            stored[key] = value

        def fake_get(key):
            return stored.get(key)

        r.setex.side_effect = fake_setex
        r.get.side_effect = fake_get

        cache_set(r, "cache:gap:ramp:enriched_citations.json", large_data)
        result = cache_get(r, "cache:gap:ramp:enriched_citations.json")

        assert result == large_data
        assert len(serialized) > 10_000_000  # Confirm it's actually large
