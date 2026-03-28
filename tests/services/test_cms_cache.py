"""Tests for core/services/cms_cache.py — CMS Redis cache helpers."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# All tests patch get_sync_redis_or_none to control Redis availability.
_REDIS_PATCH = "core.services.cms_cache.get_sync_redis_or_none"


# ── Key builder tests ────────────────────────────────────────────────


class TestKeyBuilders:
    def test_categories_key_normalizes_url(self):
        from core.services.cms_cache import cms_categories_key

        assert (
            cms_categories_key("https://Blog.Example.COM/")
            == "cache:cms:categories:https://blog.example.com"
        )

    def test_categories_key_strips_trailing_slash(self):
        from core.services.cms_cache import cms_categories_key

        k1 = cms_categories_key("https://site.com/")
        k2 = cms_categories_key("https://site.com")
        assert k1 == k2

    def test_connection_key(self):
        from core.services.cms_cache import cms_connection_key

        assert (
            cms_connection_key("test-co", "tenant-1")
            == "cache:cms:test-co:connection:tenant-1"
        )

    def test_stale_key(self):
        from core.services.cms_cache import cms_stale_key

        assert cms_stale_key("test-co") == "cache:cms:test-co:stale"

    def test_posts_key(self):
        from core.services.cms_cache import cms_posts_key

        assert (
            cms_posts_key("test-co", True, 50, 10)
            == "cache:cms:test-co:posts:stale=True:limit=50:offset=10"
        )


# ── Serialization tests ─────────────────────────────────────────────


class TestSerialization:
    def test_serialize_synced_post_extracts_fields(self):
        from core.services.cms_cache import serialize_synced_post

        post = SimpleNamespace(
            id="abc-123",
            cms_post_id="42",
            title="Test Post",
            slug="test-post",
            url="https://blog.example.com/test-post/",
            word_count=500,
            published_at=None,
            modified_at=None,
            is_stale=True,
            staleness_days=45,
            categories=["AI", "Tech"],
            queued_for_refresh=False,
        )
        result = serialize_synced_post(post)
        assert result["id"] == "abc-123"
        assert result["cms_post_id"] == "42"
        assert result["title"] == "Test Post"
        assert result["is_stale"] is True
        assert result["categories"] == ["AI", "Tech"]
        assert result["published_at"] is None

    def test_serialize_synced_post_handles_datetimes(self):
        from datetime import datetime, timezone

        from core.services.cms_cache import serialize_synced_post

        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        post = SimpleNamespace(
            id="x",
            cms_post_id="1",
            title="T",
            slug="t",
            url="",
            word_count=0,
            published_at=dt,
            modified_at=dt,
            is_stale=False,
            staleness_days=0,
            categories=[],
            queued_for_refresh=False,
        )
        result = serialize_synced_post(post)
        assert result["published_at"] == "2026-01-15T12:00:00+00:00"
        assert result["modified_at"] == "2026-01-15T12:00:00+00:00"

    def test_deserialize_synced_post_roundtrip(self):
        from core.services.cms_cache import (
            deserialize_synced_post,
            serialize_synced_post,
        )

        post = SimpleNamespace(
            id="abc",
            cms_post_id="42",
            title="Hello",
            slug="hello",
            url="https://example.com/hello/",
            word_count=100,
            published_at=None,
            modified_at=None,
            is_stale=False,
            staleness_days=0,
            categories=["AI"],
            queued_for_refresh=True,
        )
        serialized = serialize_synced_post(post)
        restored = deserialize_synced_post(serialized)

        assert restored.id == "abc"
        assert restored.cms_post_id == "42"
        assert restored.title == "Hello"
        assert restored.categories == ["AI"]
        assert restored.queued_for_refresh is True


# ── Categories cache tests ───────────────────────────────────────────


class TestCategoriesCache:
    def test_get_hit(self):
        from core.services.cms_cache import get_cached_categories

        r = MagicMock()
        r.get.return_value = json.dumps([{"cms_id": "1", "name": "AI"}])
        with patch(_REDIS_PATCH, return_value=r):
            result = get_cached_categories("https://blog.example.com")
        assert result == [{"cms_id": "1", "name": "AI"}]
        r.get.assert_called_once()

    def test_get_miss(self):
        from core.services.cms_cache import get_cached_categories

        r = MagicMock()
        r.get.return_value = None
        with patch(_REDIS_PATCH, return_value=r):
            assert get_cached_categories("https://blog.example.com") is None

    def test_get_no_redis(self):
        from core.services.cms_cache import get_cached_categories

        with patch(_REDIS_PATCH, return_value=None):
            assert get_cached_categories("https://blog.example.com") is None

    def test_set_writes_with_ttl(self):
        from core.services.cms_cache import CMS_CATEGORIES_TTL, set_cached_categories

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            set_cached_categories(
                "https://blog.example.com", [{"cms_id": "1"}]
            )
        r.setex.assert_called_once()
        args = r.setex.call_args[0]
        assert args[1] == CMS_CATEGORIES_TTL

    def test_set_no_redis(self):
        from core.services.cms_cache import set_cached_categories

        with patch(_REDIS_PATCH, return_value=None):
            set_cached_categories("https://x.com", [])  # should not raise

    def test_invalidate(self):
        from core.services.cms_cache import cms_categories_key, invalidate_categories

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            invalidate_categories("https://blog.example.com")
        r.delete.assert_called_once_with(
            cms_categories_key("https://blog.example.com")
        )


# ── Connection info cache tests ──────────────────────────────────────


class TestConnectionInfoCache:
    def test_get_hit(self):
        from core.services.cms_cache import get_cached_connection_info

        r = MagicMock()
        r.get.return_value = json.dumps({"provider": "wordpress", "site_url": "x"})
        with patch(_REDIS_PATCH, return_value=r):
            result = get_cached_connection_info("test-co", "tenant-1")
        assert result["provider"] == "wordpress"

    def test_get_no_redis(self):
        from core.services.cms_cache import get_cached_connection_info

        with patch(_REDIS_PATCH, return_value=None):
            assert get_cached_connection_info("test-co", "t") is None

    def test_set_and_invalidate(self):
        from core.services.cms_cache import (
            cms_connection_key,
            invalidate_connection_info,
            set_cached_connection_info,
        )

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            set_cached_connection_info("test-co", "t", {"provider": "wordpress"})
        r.setex.assert_called_once()

        r.reset_mock()
        with patch(_REDIS_PATCH, return_value=r):
            invalidate_connection_info("test-co", "t")
        r.delete.assert_called_once_with(cms_connection_key("test-co", "t"))


# ── Stale actions cache tests ────────────────────────────────────────


class TestStaleActionsCache:
    def test_get_hit(self):
        from core.services.cms_cache import get_cached_stale_actions

        r = MagicMock()
        r.get.return_value = json.dumps([{"title": "Old Post"}])
        with patch(_REDIS_PATCH, return_value=r):
            result = get_cached_stale_actions("test-co")
        assert result == [{"title": "Old Post"}]

    def test_set_with_ttl(self):
        from core.services.cms_cache import CMS_STALE_TTL, set_cached_stale_actions

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            set_cached_stale_actions("test-co", [{"title": "Old"}])
        args = r.setex.call_args[0]
        assert args[1] == CMS_STALE_TTL

    def test_get_no_redis(self):
        from core.services.cms_cache import get_cached_stale_actions

        with patch(_REDIS_PATCH, return_value=None):
            assert get_cached_stale_actions("test-co") is None


# ── Synced posts cache tests ─────────────────────────────────────────


class TestSyncedPostsCache:
    def test_get_hit(self):
        from core.services.cms_cache import get_cached_synced_posts

        r = MagicMock()
        r.get.return_value = json.dumps([{"id": "1", "title": "Post"}])
        with patch(_REDIS_PATCH, return_value=r):
            result = get_cached_synced_posts("test-co", False, 100, 0)
        assert result == [{"id": "1", "title": "Post"}]

    def test_set_with_ttl(self):
        from core.services.cms_cache import CMS_POSTS_TTL, set_cached_synced_posts

        r = MagicMock()
        with patch(_REDIS_PATCH, return_value=r):
            set_cached_synced_posts("test-co", False, 100, 0, [{"id": "1"}])
        args = r.setex.call_args[0]
        assert args[1] == CMS_POSTS_TTL

    def test_key_varies_by_params(self):
        from core.services.cms_cache import cms_posts_key

        k1 = cms_posts_key("test-co", False, 100, 0)
        k2 = cms_posts_key("test-co", True, 100, 0)
        k3 = cms_posts_key("test-co", False, 50, 10)
        assert k1 != k2
        assert k1 != k3
        assert k2 != k3


# ── Bulk invalidation tests ─────────────────────────────────────────


class TestBulkInvalidation:
    def test_invalidate_all_uses_pattern(self):
        from core.services.cms_cache import invalidate_all_cms_caches

        r = MagicMock()
        r.scan_iter.return_value = iter([
            "cache:cms:test-co:stale",
            "cache:cms:test-co:connection:t",
        ])
        r.delete.return_value = 2
        with patch(_REDIS_PATCH, return_value=r):
            invalidate_all_cms_caches("test-co")
        r.scan_iter.assert_called_once_with(
            match="cache:cms:test-co:*", count=500
        )

    def test_invalidate_all_no_redis(self):
        from core.services.cms_cache import invalidate_all_cms_caches

        with patch(_REDIS_PATCH, return_value=None):
            invalidate_all_cms_caches("test-co")  # should not raise
