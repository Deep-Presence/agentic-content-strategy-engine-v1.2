"""Tests for WordPress adapter using httpx.MockTransport."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from core.cms.adapters.wordpress import WordPressAdapter
from core.cms.exceptions import CMSAPIError, CMSAuthError, CMSNotFoundError
from core.cms.models import (
    CMSConnectionConfig,
    CMSMediaUpload,
    CMSPostCreate,
    CMSPostStatus,
    CMSPostUpdate,
)
from core.cms.protocols import CMSAdapterProtocol
from core.db.enums import CMSProvider

_SITE_URL = "https://blog.example.com"


# ── Mock Transport Builder ────────────────────────────────────────────


def _make_wp_transport(
    responses: dict[tuple[str, str], tuple[int, Any, dict[str, str] | None]],
) -> httpx.MockTransport:
    """Build a mock transport for WP REST API tests.

    Args:
        responses: Mapping of ``(HTTP_METHOD, url_suffix)`` to
            ``(status_code, json_body_or_str, extra_headers)``.
            URL suffix is matched against the end of the request URL path.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        method = request.method
        for (m, suffix), (status, body, headers) in responses.items():
            if method == m and url_path.endswith(suffix):
                resp_headers = headers or {}
                if isinstance(body, (dict, list)):
                    return httpx.Response(
                        status, json=body, headers=resp_headers
                    )
                return httpx.Response(status, text=str(body), headers=resp_headers)
        return httpx.Response(404, json={"code": "rest_no_route"})

    return httpx.MockTransport(handler)


def _make_adapter(
    responses: dict[tuple[str, str], tuple[int, Any, dict[str, str] | None]],
) -> WordPressAdapter:
    config = CMSConnectionConfig(
        provider=CMSProvider.wordpress,
        site_url=_SITE_URL,
        username="admin",
        api_key="xxxx xxxx xxxx",
    )
    return WordPressAdapter(config, _transport=_make_wp_transport(responses))


def _sample_wp_post(post_id: int = 1, **overrides: Any) -> dict[str, Any]:
    """Minimal WP REST API post response."""
    post: dict[str, Any] = {
        "id": post_id,
        "title": {"rendered": f"Post {post_id}"},
        "slug": f"post-{post_id}",
        "content": {"rendered": f"<p>Content of post {post_id}</p>"},
        "excerpt": {"rendered": ""},
        "status": "publish",
        "link": f"{_SITE_URL}/post-{post_id}/",
        "date": "2026-01-15T10:00:00",
        "modified": "2026-02-20T14:30:00",
        "author": 1,
        "categories": [3, 7],
        "tags": [5],
        "featured_media": 0,
    }
    post.update(overrides)
    return post


# ── Connection Tests ──────────────────────────────────────────────────


class TestValidateConnection:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        adapter = _make_adapter({
            ("GET", "/wp-json"): (
                200,
                {"name": "Test Blog", "url": _SITE_URL, "description": "6.7.1"},
                None,
            ),
            ("GET", "/users/me"): (
                200,
                {"name": "Admin User", "capabilities": {"publish_posts": True}},
                None,
            ),
        })
        status = await adapter.validate_connection()
        assert status.connected is True
        assert status.site_name == "Test Blog"
        assert "publish_posts" in status.capabilities

    @pytest.mark.asyncio
    async def test_site_unreachable(self) -> None:
        adapter = _make_adapter({
            ("GET", "/wp-json"): (503, "Service Unavailable", None),
        })
        status = await adapter.validate_connection()
        assert status.connected is False
        assert "503" in (status.error or "")

    @pytest.mark.asyncio
    async def test_invalid_credentials(self) -> None:
        adapter = _make_adapter({
            ("GET", "/wp-json"): (
                200,
                {"name": "Blog", "url": _SITE_URL},
                None,
            ),
            ("GET", "/users/me"): (401, {"code": "invalid_auth"}, None),
        })
        status = await adapter.validate_connection()
        assert status.connected is False
        assert "credentials" in (status.error or "").lower()


# ── List Posts Tests ──────────────────────────────────────────────────


class TestListPosts:
    @pytest.mark.asyncio
    async def test_single_page(self) -> None:
        posts_data = [_sample_wp_post(i) for i in range(1, 4)]
        adapter = _make_adapter({
            ("GET", "/posts"): (200, posts_data, {"X-WP-Total": "3"}),
        })
        posts, total = await adapter.list_posts()
        assert total == 3
        assert len(posts) == 3
        assert posts[0].cms_id == "1"

    @pytest.mark.asyncio
    async def test_pagination_header(self) -> None:
        posts_data = [_sample_wp_post(1)]
        adapter = _make_adapter({
            ("GET", "/posts"): (200, posts_data, {"X-WP-Total": "250"}),
        })
        _, total = await adapter.list_posts()
        assert total == 250

    @pytest.mark.asyncio
    async def test_bad_request(self) -> None:
        adapter = _make_adapter({
            ("GET", "/posts"): (400, "Invalid parameter", None),
        })
        with pytest.raises(CMSAPIError, match="Bad request"):
            await adapter.list_posts()


# ── List All Posts Tests ──────────────────────────────────────────────


class TestListAllPosts:
    @pytest.mark.asyncio
    async def test_multiple_pages(self) -> None:
        """Simulate 3 total posts: page 1 returns 2, page 2 returns 1."""
        page1 = [_sample_wp_post(1), _sample_wp_post(2)]
        page2 = [_sample_wp_post(3)]

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            if request.url.path.endswith("/posts"):
                call_count += 1
                if call_count == 1:
                    return httpx.Response(
                        200,
                        json=page1,
                        headers={"X-WP-Total": "3"},
                    )
                return httpx.Response(
                    200,
                    json=page2,
                    headers={"X-WP-Total": "3"},
                )
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(
            config, _transport=httpx.MockTransport(handler)
        )
        posts, truncated = await adapter.list_all_posts()
        assert len(posts) == 3
        assert truncated is False


# ── Get Post Tests ────────────────────────────────────────────────────


class TestGetPost:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        adapter = _make_adapter({
            ("GET", "/posts/42"): (200, _sample_wp_post(42), None),
        })
        post = await adapter.get_post(42)
        assert post.cms_id == "42"
        assert post.title == "Post 42"

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        adapter = _make_adapter({
            ("GET", "/posts/999"): (404, {"code": "not_found"}, None),
        })
        with pytest.raises(CMSNotFoundError, match="999"):
            await adapter.get_post(999)


# ── List Categories Tests ─────────────────────────────────────────────


class TestListCategories:
    @pytest.mark.asyncio
    async def test_single_page(self) -> None:
        cats = [
            {"id": 1, "name": "AI", "slug": "ai", "parent": 0, "count": 5},
            {"id": 2, "name": "B2B", "slug": "b2b", "parent": 0, "count": 3},
        ]
        adapter = _make_adapter({
            ("GET", "/categories"): (200, cats, {"X-WP-TotalPages": "1"}),
        })
        result = await adapter.list_categories()
        assert len(result) == 2
        assert result[0].name == "AI"
        assert result[0].cms_id == "1"

    @pytest.mark.asyncio
    async def test_multi_page(self) -> None:
        """Two pages of categories."""
        page1 = [{"id": i, "name": f"Cat{i}", "slug": f"cat{i}", "parent": 0, "count": 0} for i in range(1, 3)]
        page2 = [{"id": 3, "name": "Cat3", "slug": "cat3", "parent": 0, "count": 0}]

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            if request.url.path.endswith("/categories"):
                call_count += 1
                if call_count == 1:
                    return httpx.Response(
                        200, json=page1, headers={"X-WP-TotalPages": "2"}
                    )
                return httpx.Response(
                    200, json=page2, headers={"X-WP-TotalPages": "2"}
                )
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(
            config, _transport=httpx.MockTransport(handler)
        )
        cats = await adapter.list_categories()
        assert len(cats) == 3


# ── Publish Post Tests ────────────────────────────────────────────────


class TestPublishPost:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        created = _sample_wp_post(99, status="draft")
        adapter = _make_adapter({
            ("GET", "/categories"): (200, [], {"X-WP-TotalPages": "1"}),
            ("POST", "/posts"): (201, created, None),
        })
        post_create = CMSPostCreate(
            title="New Article",
            slug="new-article",
            content_html="<h1>Hello</h1>",
        )
        result = await adapter.publish_post(post_create)
        assert result.cms_id == "99"

    @pytest.mark.asyncio
    async def test_forbidden(self) -> None:
        adapter = _make_adapter({
            ("GET", "/categories"): (200, [], {"X-WP-TotalPages": "1"}),
            ("POST", "/posts"): (403, {"code": "forbidden"}, None),
        })
        with pytest.raises(CMSAuthError, match="permissions"):
            await adapter.publish_post(CMSPostCreate(title="Test"))

    @pytest.mark.asyncio
    async def test_with_seo_meta(self) -> None:
        """SEO fields should be sent as Yoast meta."""
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/categories"):
                return httpx.Response(200, json=[], headers={"X-WP-TotalPages": "1"})
            if request.method == "POST" and request.url.path.endswith("/posts"):
                captured_payload.update(json.loads(request.content))
                return httpx.Response(201, json=_sample_wp_post(50))
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(
            config, _transport=httpx.MockTransport(handler)
        )
        await adapter.publish_post(
            CMSPostCreate(
                title="SEO Test",
                seo_title="SEO Title | Brand",
                seo_description="Meta description",
            )
        )
        assert captured_payload["meta"]["_yoast_wpseo_title"] == "SEO Title | Brand"
        assert captured_payload["meta"]["_yoast_wpseo_metadesc"] == "Meta description"


# ── Update Post Tests ─────────────────────────────────────────────────


class TestUpdatePost:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        updated = _sample_wp_post(42, title={"rendered": "Updated"})
        adapter = _make_adapter({
            ("POST", "/posts/42"): (200, updated, None),
        })
        result = await adapter.update_post(
            42, CMSPostUpdate(title="Updated")
        )
        assert result.cms_id == "42"

    @pytest.mark.asyncio
    async def test_empty_payload_gets_post(self) -> None:
        """All-None update should short-circuit to get_post."""
        adapter = _make_adapter({
            ("GET", "/posts/42"): (200, _sample_wp_post(42), None),
        })
        result = await adapter.update_post(42, CMSPostUpdate())
        assert result.cms_id == "42"

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        adapter = _make_adapter({
            ("POST", "/posts/999"): (404, {"code": "not_found"}, None),
        })
        with pytest.raises(CMSNotFoundError):
            await adapter.update_post(
                999, CMSPostUpdate(title="X")
            )


# ── Upload Media Tests ────────────────────────────────────────────────


class TestUploadMedia:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        adapter = _make_adapter({
            ("POST", "/media"): (
                201,
                {"id": 77, "source_url": "https://blog.example.com/wp-content/img.png"},
                None,
            ),
        })
        result = await adapter.upload_media(
            CMSMediaUpload(
                filename="hero.png",
                content_bytes=b"\x89PNG...",
                mime_type="image/png",
            )
        )
        assert result.cms_id == "77"
        assert "img.png" in result.url


# ── Parse Helpers Tests ───────────────────────────────────────────────


class TestParsePost:
    def _adapter(self) -> WordPressAdapter:
        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        return WordPressAdapter(config)

    def test_nested_rendered_fields(self) -> None:
        raw = _sample_wp_post(1)
        post = self._adapter()._parse_post(raw)
        assert post.title == "Post 1"
        assert "<p>" in post.content_html

    def test_yoast_seo(self) -> None:
        raw = _sample_wp_post(
            1,
            yoast_head_json={
                "title": "SEO Title",
                "og_description": "SEO Desc",
            },
        )
        post = self._adapter()._parse_post(raw)
        assert post.seo_title == "SEO Title"
        assert post.seo_description == "SEO Desc"

    def test_missing_yoast(self) -> None:
        raw = _sample_wp_post(1)
        # No yoast_head_json key at all
        raw.pop("yoast_head_json", None)
        post = self._adapter()._parse_post(raw)
        assert post.seo_title == ""
        assert post.seo_description == ""

    def test_categories_as_string_ids(self) -> None:
        raw = _sample_wp_post(1, categories=[3, 7, 15])
        post = self._adapter()._parse_post(raw)
        assert post.categories == ["3", "7", "15"]


class TestParseDt:
    def _adapter(self) -> WordPressAdapter:
        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        return WordPressAdapter(config)

    def test_valid(self) -> None:
        dt = self._adapter()._parse_dt("2026-01-15T10:00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_invalid(self) -> None:
        assert self._adapter()._parse_dt("not-a-date") is None

    def test_none(self) -> None:
        assert self._adapter()._parse_dt(None) is None


# ── Category Resolution Tests ─────────────────────────────────────────


class TestResolveCategoryIds:
    @pytest.mark.asyncio
    async def test_existing_categories(self) -> None:
        cats = [{"id": 10, "name": "AI", "slug": "ai", "parent": 0, "count": 5}]
        adapter = _make_adapter({
            ("GET", "/categories"): (200, cats, {"X-WP-TotalPages": "1"}),
        })
        ids = await adapter._resolve_category_ids(["AI"])
        assert ids == [10]

    @pytest.mark.asyncio
    async def test_create_missing(self) -> None:
        adapter = _make_adapter({
            ("GET", "/categories"): (200, [], {"X-WP-TotalPages": "1"}),
            ("POST", "/categories"): (201, {"id": 42}, None),
        })
        ids = await adapter._resolve_category_ids(["New Category"])
        assert ids == [42]

    @pytest.mark.asyncio
    async def test_case_insensitive(self) -> None:
        cats = [{"id": 10, "name": "AI Research", "slug": "ai-research", "parent": 0, "count": 0}]
        adapter = _make_adapter({
            ("GET", "/categories"): (200, cats, {"X-WP-TotalPages": "1"}),
        })
        ids = await adapter._resolve_category_ids(["ai research"])
        assert ids == [10]

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config)
        ids = await adapter._resolve_category_ids([])
        assert ids == []


# ── Protocol Compliance ───────────────────────────────────────────────


class TestProtocolCompliance:
    def test_wordpress_adapter_satisfies_protocol(self) -> None:
        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config)
        assert isinstance(adapter, CMSAdapterProtocol)


# ── Rate Limiting: Category Creation Cap ─────────────────────────────


class TestCategoryCreationCap:
    @pytest.mark.asyncio
    async def test_caps_at_limit(self) -> None:
        """Only _MAX_NEW_CATEGORIES_PER_CALL new categories are created."""
        from core.cms.adapters.wordpress import _MAX_NEW_CATEGORIES_PER_CALL

        post_count = 0
        next_id = 100

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal post_count, next_id
            if request.method == "GET" and request.url.path.endswith("/categories"):
                return httpx.Response(
                    200, json=[], headers={"X-WP-TotalPages": "1"}
                )
            if request.method == "POST" and request.url.path.endswith("/categories"):
                post_count += 1
                next_id += 1
                return httpx.Response(201, json={"id": next_id})
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config, _transport=httpx.MockTransport(handler))

        # 8 new categories — should only create 5
        names = [f"Cat-{i}" for i in range(8)]
        ids = await adapter._resolve_category_ids(names)

        assert post_count == _MAX_NEW_CATEGORIES_PER_CALL
        assert len(ids) == _MAX_NEW_CATEGORIES_PER_CALL

    @pytest.mark.asyncio
    async def test_existing_not_counted_against_cap(self) -> None:
        """Existing categories do not count against the creation cap."""
        from core.cms.adapters.wordpress import _MAX_NEW_CATEGORIES_PER_CALL

        existing_cats = [
            {"id": i, "name": f"Existing-{i}", "slug": f"existing-{i}", "parent": 0, "count": 0}
            for i in range(3)
        ]
        post_count = 0
        next_id = 200

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal post_count, next_id
            if request.method == "GET" and request.url.path.endswith("/categories"):
                return httpx.Response(
                    200, json=existing_cats, headers={"X-WP-TotalPages": "1"}
                )
            if request.method == "POST" and request.url.path.endswith("/categories"):
                post_count += 1
                next_id += 1
                return httpx.Response(201, json={"id": next_id})
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config, _transport=httpx.MockTransport(handler))

        # 3 existing + 3 new → all should resolve (under cap)
        names = [f"Existing-{i}" for i in range(3)] + ["New-A", "New-B", "New-C"]
        ids = await adapter._resolve_category_ids(names)

        assert post_count == 3
        assert len(ids) == 6

    @pytest.mark.asyncio
    async def test_under_cap_all_created(self) -> None:
        """When under cap, all new categories are created."""
        post_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal post_count
            if request.method == "GET" and request.url.path.endswith("/categories"):
                return httpx.Response(
                    200, json=[], headers={"X-WP-TotalPages": "1"}
                )
            if request.method == "POST" and request.url.path.endswith("/categories"):
                post_count += 1
                return httpx.Response(201, json={"id": post_count})
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config, _transport=httpx.MockTransport(handler))
        ids = await adapter._resolve_category_ids(["A", "B", "C"])
        assert post_count == 3
        assert len(ids) == 3


# ── Rate Limiting: Pagination Cap ────────────────────────────────────


class TestPaginationCap:
    @pytest.mark.asyncio
    async def test_truncates_at_page_limit(self) -> None:
        """list_all_posts stops after _MAX_PAGINATION_PAGES pages."""
        from core.cms.adapters.wordpress import _MAX_PAGINATION_PAGES

        page_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal page_count
            if request.url.path.endswith("/posts"):
                page_count += 1
                # Always return 100 posts, total=999999 (never ends naturally)
                posts = [_sample_wp_post(i) for i in range(100)]
                return httpx.Response(
                    200, json=posts, headers={"X-WP-Total": "999999"}
                )
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config, _transport=httpx.MockTransport(handler))
        posts, truncated = await adapter.list_all_posts()

        assert truncated is True
        assert page_count == _MAX_PAGINATION_PAGES
        assert len(posts) == _MAX_PAGINATION_PAGES * 100

    @pytest.mark.asyncio
    async def test_no_truncation_for_small_site(self) -> None:
        """Small site (1 page) returns all posts without truncation."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/posts"):
                posts = [_sample_wp_post(i) for i in range(5)]
                return httpx.Response(
                    200, json=posts, headers={"X-WP-Total": "5"}
                )
            return httpx.Response(404, json={})

        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url=_SITE_URL,
            username="admin",
            api_key="key",
        )
        adapter = WordPressAdapter(config, _transport=httpx.MockTransport(handler))
        posts, truncated = await adapter.list_all_posts()

        assert truncated is False
        assert len(posts) == 5
