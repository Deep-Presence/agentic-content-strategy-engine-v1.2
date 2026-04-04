"""Tests for core/services/analytics_cache.py — GA4 Redis cache helpers."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# All tests patch get_sync_redis_or_none to control Redis availability.
_REDIS_PATCH = "core.services.analytics_cache.get_sync_redis_or_none"


# ── Key builder tests ────────────────────────────────────────────────


class TestKeyBuilders:
    def test_connection_key(self):
        from core.services.analytics_cache import ga4_connection_key

        assert (
            ga4_connection_key("test-co", "tenant-1")
            == "cache:ga4:test-co:connection:tenant-1"
        )

    def test_properties_key(self):
        from core.services.analytics_cache import ga4_properties_key

        assert (
            ga4_properties_key("test-co", "tenant-1")
            == "cache:ga4:test-co:properties:tenant-1"
        )


# ── Connection info cache tests ──────────────────────────────────────


class TestConnectionCache:
    def test_get_hit(self):
        from core.services.analytics_cache import get_cached_ga4_connection

        r = MagicMock()
        r.get.return_value = json.dumps({"provider": "ga4", "is_active": True})
        with patch(_REDIS_PATCH, return_value=r):
            result = get_cached_ga4_connection("test-co", "test-co")
        assert result["provider"] == "ga4"
        assert result["is_active"] is True
        r.get.assert_called_once()

    def test_get_miss(self):
        from core.services.analytics_cache import get_cached_ga4_connection

        r = MagicMock()
        r.get.return_value = None
        with patch(_REDIS_PATCH, return_value=r):
            assert get_cached_ga4_connection("test-co", "test-co") is None

    def test_get_no_redis(self):
        from core.services.analytics_cache import get_cached_ga4_connection

        with patch(_REDIS_PATCH, return_value=None):
            assert get_cached_ga4_connection("test-co", "test-co") is None

    def test_set_writes_with_ttl(self):
        from core.services.analytics_cache import (
            GA4_CONNECTION_TTL,
            set_cached_ga4_connection,
        )

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            set_cached_ga4_connection("test-co", "test-co", {"provider": "ga4"})
        r.setex.assert_called_once()
        args = r.setex.call_args[0]
        assert args[1] == GA4_CONNECTION_TTL

    def test_set_no_redis(self):
        from core.services.analytics_cache import set_cached_ga4_connection

        with patch(_REDIS_PATCH, return_value=None):
            set_cached_ga4_connection("test-co", "test-co", {})  # should not raise

    def test_invalidate(self):
        from core.services.analytics_cache import (
            ga4_connection_key,
            invalidate_ga4_connection,
        )

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            invalidate_ga4_connection("test-co", "test-co")
        r.delete.assert_called_once_with(
            ga4_connection_key("test-co", "test-co")
        )

    def test_invalidate_no_redis(self):
        from core.services.analytics_cache import invalidate_ga4_connection

        with patch(_REDIS_PATCH, return_value=None):
            invalidate_ga4_connection("test-co", "test-co")  # should not raise


# ── Properties cache tests ───────────────────────────────────────────


class TestPropertiesCache:
    def test_get_hit(self):
        from core.services.analytics_cache import get_cached_ga4_properties

        r = MagicMock()
        r.get.return_value = json.dumps([
            {"property_id": "123", "display_name": "My Site"}
        ])
        with patch(_REDIS_PATCH, return_value=r):
            result = get_cached_ga4_properties("test-co", "test-co")
        assert result == [{"property_id": "123", "display_name": "My Site"}]
        r.get.assert_called_once()

    def test_get_miss(self):
        from core.services.analytics_cache import get_cached_ga4_properties

        r = MagicMock()
        r.get.return_value = None
        with patch(_REDIS_PATCH, return_value=r):
            assert get_cached_ga4_properties("test-co", "test-co") is None

    def test_get_no_redis(self):
        from core.services.analytics_cache import get_cached_ga4_properties

        with patch(_REDIS_PATCH, return_value=None):
            assert get_cached_ga4_properties("test-co", "test-co") is None

    def test_set_writes_with_ttl(self):
        from core.services.analytics_cache import (
            GA4_PROPERTIES_TTL,
            set_cached_ga4_properties,
        )

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            set_cached_ga4_properties(
                "test-co", "test-co", [{"property_id": "123"}]
            )
        r.setex.assert_called_once()
        args = r.setex.call_args[0]
        assert args[1] == GA4_PROPERTIES_TTL

    def test_set_no_redis(self):
        from core.services.analytics_cache import set_cached_ga4_properties

        with patch(_REDIS_PATCH, return_value=None):
            set_cached_ga4_properties("test-co", "test-co", [])  # should not raise

    def test_invalidate(self):
        from core.services.analytics_cache import (
            ga4_properties_key,
            invalidate_ga4_properties,
        )

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            invalidate_ga4_properties("test-co", "test-co")
        r.delete.assert_called_once_with(
            ga4_properties_key("test-co", "test-co")
        )


# ── Bulk invalidation tests ─────────────────────────────────────────


class TestBulkInvalidation:
    def test_invalidate_all_uses_pattern(self):
        from core.services.analytics_cache import invalidate_all_ga4_caches

        r = MagicMock()
        r.scan_iter.return_value = iter([
            "cache:ga4:test-co:connection:test-co",
            "cache:ga4:test-co:properties:test-co",
        ])
        r.delete.return_value = 2
        with patch(_REDIS_PATCH, return_value=r):
            invalidate_all_ga4_caches("test-co")
        r.scan_iter.assert_called_once_with(
            match="cache:ga4:test-co:*", count=500
        )

    def test_invalidate_all_no_redis(self):
        from core.services.analytics_cache import invalidate_all_ga4_caches

        with patch(_REDIS_PATCH, return_value=None):
            invalidate_all_ga4_caches("test-co")  # should not raise
