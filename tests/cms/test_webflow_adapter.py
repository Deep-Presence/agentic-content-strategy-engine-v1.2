"""Tests for Webflow adapter using httpx.MockTransport."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from core.cms.adapters.webflow.adapter import WebflowAdapter
from core.cms.exceptions import CMSRateLimitError
from core.cms.models import CMSConnectionConfig, CMSPostCreate, CMSPostStatus, CMSPostUpdate
from core.cms.protocols import CMSAdapterProtocol
from core.cms.webflow_models import WebflowCollectionConfig, WebflowFieldMapping, WebflowProviderConfig
from core.db.enums import CMSProvider

_SITE_URL = "https://marketing.example.com"
_SITE_ID = "580e63e98c9a982ac9b8b741"
_COLL_ID = "634a5a9b5f4e7a0012345678"


def _provider_config() -> dict[str, Any]:
    return WebflowProviderConfig(
        site_id=_SITE_ID,
        collections=[
            WebflowCollectionConfig(
                collection_id=_COLL_ID,
                collection_slug="blog-posts",
                display_name="Blog Posts",
                enabled=True,
                is_default_publish_target=True,
                field_mapping=WebflowFieldMapping(
                    title_field="name",
                    slug_field="slug",
                    body_field="post-body",
                    category_field="category",
                ),
            ),
            WebflowCollectionConfig(
                collection_id="coll-guides",
                collection_slug="guides",
                display_name="Guides",
                enabled=True,
                field_mapping=WebflowFieldMapping(
                    title_field="name",
                    slug_field="slug",
                    body_field="post-body",
                ),
            ),
        ],
    ).to_provider_config()


def _make_transport(
    responses: dict[tuple[str, str], tuple[int, Any, dict[str, str] | None]],
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        for (m, suffix), (status, body, headers) in responses.items():
            if method == m and path.endswith(suffix):
                resp_headers = headers or {}
                if isinstance(body, (dict, list)):
                    return httpx.Response(status, json=body, headers=resp_headers)
                return httpx.Response(status, text=str(body), headers=resp_headers)
        return httpx.Response(404, json={"message": "not found", "code": "resource_not_found"})

    return httpx.MockTransport(handler)


def _make_adapter(
    responses: dict[tuple[str, str], tuple[int, Any, dict[str, str] | None]],
    *,
    provider_config: dict[str, Any] | None = None,
) -> WebflowAdapter:
    config = CMSConnectionConfig(
        provider=CMSProvider.webflow,
        site_url=_SITE_URL,
        api_key="wf-test-token",
        extra={"auth_type": "site_token", "access_token": "wf-test-token"},
        provider_config=provider_config or _provider_config(),
    )
    return WebflowAdapter(config, _transport=_make_transport(responses))


def _sample_item(item_id: str = "item-abc", **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": item_id,
        "isDraft": False,
        "lastPublished": "2026-01-15T10:00:00.000Z",
        "lastUpdated": "2026-02-20T14:30:00.000Z",
        "fieldData": {
            "name": "Sample Post",
            "slug": "sample-post",
            "post-body": "<p>Sample body</p>",
            "category": "News",
        },
    }
    item.update(overrides)
    return item


class TestValidateConnection:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        adapter = _make_adapter({
            ("GET", "/authorized_by"): (
                200,
                {"email": "dev@example.com"},
                None,
            ),
            ("GET", f"/sites/{_SITE_ID}"): (
                200,
                {
                    "id": _SITE_ID,
                    "displayName": "Marketing Site",
                    "previewUrl": "https://marketing.example.com",
                },
                None,
            ),
        })
        status = await adapter.validate_connection()
        assert status.connected is True
        assert status.site_name == "Marketing Site"
        assert status.cms_version == "webflow-v2"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_error_status(self) -> None:
        adapter = _make_adapter({
            ("GET", "/authorized_by"): (401, {"message": "unauthorized"}, None),
        })
        status = await adapter.validate_connection()
        assert status.connected is False
        assert status.error


class TestListAllPosts:
    @pytest.mark.asyncio
    async def test_multi_collection_sync(self) -> None:
        adapter = _make_adapter({
            ("GET", f"/collections/{_COLL_ID}/items/live"): (
                200,
                {
                    "items": [_sample_item("blog-1")],
                    "pagination": {"offset": 0, "limit": 100, "total": 1},
                },
                None,
            ),
            ("GET", "/collections/coll-guides/items/live"): (
                200,
                {
                    "items": [_sample_item("guide-1", fieldData={"name": "Guide", "slug": "guide", "post-body": "<p>G</p>"})],
                    "pagination": {"offset": 0, "limit": 100, "total": 1},
                },
                None,
            ),
        })
        posts, truncated = await adapter.list_all_posts()
        assert truncated is False
        assert len(posts) == 2
        ids = {p.cms_id for p in posts}
        assert ids == {"blog-1", "guide-1"}


class TestPublishAndUpdate:
    @pytest.mark.asyncio
    async def test_publish_live_item(self) -> None:
        adapter = _make_adapter({
            ("POST", f"/collections/{_COLL_ID}/items/live"): (
                200,
                _sample_item("new-1"),
                None,
            ),
        })
        created = await adapter.publish_post(
            CMSPostCreate(
                title="Sample Post",
                slug="sample-post",
                content_html="<p>Sample body</p>",
                status=CMSPostStatus.publish,
            )
        )
        assert created.cms_id == "new-1"
        assert created.title == "Sample Post"

    @pytest.mark.asyncio
    async def test_update_live_item(self) -> None:
        adapter = _make_adapter({
            ("GET", f"/collections/{_COLL_ID}/items/item-abc/live"): (
                200,
                _sample_item("item-abc"),
                None,
            ),
            ("PATCH", f"/collections/{_COLL_ID}/items/item-abc/live"): (
                200,
                _sample_item("item-abc", fieldData={"name": "Updated", "slug": "sample-post", "post-body": "<p>New</p>"}),
                None,
            ),
        })
        updated = await adapter.update_post(
            "item-abc",
            CMSPostUpdate(title="Updated", content_html="<p>New</p>"),
        )
        assert updated.title == "Updated"

    @pytest.mark.asyncio
    async def test_update_non_default_collection_probes_collections(self) -> None:
        """Multi-collection refresh resolves the owning collection by probing."""
        adapter = _make_adapter({
            ("GET", f"/collections/{_COLL_ID}/items/guide-1/live"): (
                404,
                {"message": "not found", "code": "resource_not_found"},
                None,
            ),
            ("GET", "/collections/coll-guides/items/guide-1/live"): (
                200,
                _sample_item(
                    "guide-1",
                    fieldData={"name": "Guide", "slug": "guide", "post-body": "<p>Old</p>"},
                ),
                None,
            ),
            ("PATCH", "/collections/coll-guides/items/guide-1/live"): (
                200,
                _sample_item(
                    "guide-1",
                    fieldData={"name": "Guide Updated", "slug": "guide", "post-body": "<p>New</p>"},
                ),
                None,
            ),
        })
        updated = await adapter.update_post(
            "guide-1",
            CMSPostUpdate(title="Guide Updated", content_html="<p>New</p>"),
        )
        assert updated.title == "Guide Updated"


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_429_maps_to_rate_limit_error(self) -> None:
        adapter = _make_adapter({
            ("GET", f"/collections/{_COLL_ID}/items/live"): (
                429,
                {"message": "Too Many Requests"},
                {"Retry-After": "60"},
            ),
        })
        with pytest.raises(CMSRateLimitError):
            await adapter.list_posts()


class TestProtocol:
    def test_satisfies_protocol(self) -> None:
        adapter = _make_adapter({})
        assert isinstance(adapter, CMSAdapterProtocol)


class TestUploadMedia:
    @pytest.mark.asyncio
    async def test_upload_media_returns_asset(self) -> None:
        responses = {
            ("POST", "/assets"): (
                200,
                {
                    "id": "asset-1",
                    "uploadUrl": "https://uploads.example/s3",
                    "hostedUrl": "https://cdn.example/image.png",
                    "uploadDetails": {
                        "acl": "public-read",
                        "bucket": "wf-assets",
                        "key": "asset-key",
                    },
                },
                None,
            ),
        }
        adapter = _make_adapter(responses)

        async def s3_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, json={"ok": True})

        adapter._client._transport = httpx.MockTransport(s3_handler)
        # Patch upload URL client separately — upload_asset_bytes uses its own client
        original_upload = adapter._client.upload_asset_bytes

        async def fake_upload(
            site_id: str,
            *,
            file_name: str,
            content_bytes: bytes,
            mime_type: str = "image/png",
        ) -> dict[str, Any]:
            return {
                "id": "asset-1",
                "url": "https://cdn.example/image.png",
                "fileName": file_name,
            }

        adapter._client.upload_asset_bytes = fake_upload  # type: ignore[method-assign]

        from core.cms.models import CMSMediaUpload

        result = await adapter.upload_media(
            CMSMediaUpload(
                filename="hero.png",
                content_bytes=b"fake-image-bytes",
                mime_type="image/png",
            )
        )
        assert result.cms_id == "asset-1"
        assert result.url == "https://cdn.example/image.png"
        adapter._client.upload_asset_bytes = original_upload  # type: ignore[method-assign]
