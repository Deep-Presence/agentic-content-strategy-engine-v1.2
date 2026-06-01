"""Webflow CMS end-to-end flow using mock HTTP transport.

Covers: connect → configure → sync → publish → refresh for multi-collection sites.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet

from core.cms.adapters.webflow.adapter import WebflowAdapter
from core.cms.models import CMSConnectionConfig, CMSPostStatus, CMSPublishMetadata
from core.cms.webflow_models import (
    WebflowCollectionConfig,
    WebflowFieldMapping,
    WebflowProviderConfig,
)
from core.db.enums import CMSProvider
from core.services.cms_service import CMSService

_SITE_URL = "https://marketing.example.com"
_SITE_ID = "580e63e98c9a982ac9b8b741"
_BLOG_COLL = "634a5a9b5f4e7a0012345678"
_GUIDES_COLL = "coll-guides"
_FERNET_KEY = Fernet.generate_key().decode()


def _provider_config() -> dict[str, Any]:
    return WebflowProviderConfig(
        site_id=_SITE_ID,
        default_collection_id=_BLOG_COLL,
        collections=[
            WebflowCollectionConfig(
                collection_id=_BLOG_COLL,
                collection_slug="blog-posts",
                display_name="Blog Posts",
                enabled=True,
                is_default_publish_target=True,
                field_mapping=WebflowFieldMapping(
                    title_field="name",
                    slug_field="slug",
                    body_field="post-body",
                ),
            ),
            WebflowCollectionConfig(
                collection_id=_GUIDES_COLL,
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


def _sample_item(
    item_id: str,
    *,
    collection_slug: str = "blog-posts",
) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "id": item_id,
        "isDraft": False,
        "lastPublished": now_iso,
        "lastUpdated": now_iso,
        "fieldData": {
            "name": f"Post {item_id}",
            "slug": item_id,
            "post-body": "<p>Body</p>",
        },
        "collectionSlug": collection_slug,
    }


def _make_transport(
    responses: dict[tuple[str, str], tuple[int, Any]],
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        for (m, suffix), (status, body) in responses.items():
            if method == m and path.endswith(suffix):
                if isinstance(body, (dict, list)):
                    return httpx.Response(status, json=body)
                return httpx.Response(status, text=str(body))
        return httpx.Response(
            404,
            json={"message": "not found", "code": "resource_not_found"},
        )

    return httpx.MockTransport(handler)


def _webflow_adapter(responses: dict[tuple[str, str], tuple[int, Any]]) -> WebflowAdapter:
    config = CMSConnectionConfig(
        provider=CMSProvider.webflow,
        site_url=_SITE_URL,
        api_key="wf-test-token",
        extra={"auth_type": "site_token", "access_token": "wf-test-token"},
        provider_config=_provider_config(),
    )
    return WebflowAdapter(config, _transport=_make_transport(responses))


def _webflow_connection(*, provider_config: dict[str, Any] | None = None) -> MagicMock:
    payload = json.dumps(
        {
            "username": "",
            "api_key": "wf-test-token",
            "auth_type": "site_token",
        }
    )
    encrypted = Fernet(_FERNET_KEY.encode()).encrypt(payload.encode()).decode()
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.provider = CMSProvider.webflow
    conn.site_url = _SITE_URL
    conn.encrypted_credentials = encrypted
    conn.provider_config = provider_config or _provider_config()
    conn.company_slug = "test-co"
    conn.company_id = uuid.uuid4()
    return conn


def _make_service(**kwargs: Any) -> CMSService:
    conn_repo = AsyncMock()
    pub_repo = AsyncMock()
    synced_repo = AsyncMock()
    synced_repo.upsert_from_cms.return_value = MagicMock()
    conn_repo.update_sync_metadata.return_value = None
    pub_repo.create.return_value = MagicMock()
    storage = MagicMock()
    storage.read.return_value = "# Published Title\n\nFinal body content."
    return CMSService(
        connection_repo=conn_repo,
        publish_repo=pub_repo,
        synced_post_repo=synced_repo,
        storage=storage,
        fernet_key=_FERNET_KEY,
        **kwargs,
    )


class TestWebflowCMSE2E:
    """Provider-level flow with mock Webflow API."""

    @pytest.mark.asyncio
    async def test_connect_validate_and_export_site_id(self) -> None:
        adapter = _webflow_adapter(
            {
                ("GET", "/authorized_by"): (200, {"email": "dev@example.com"}),
                ("GET", f"/sites/{_SITE_ID}"): (
                    200,
                    {
                        "id": _SITE_ID,
                        "displayName": "Marketing Site",
                        "previewUrl": _SITE_URL,
                    },
                ),
            }
        )
        status = await adapter.validate_connection()
        assert status.connected is True
        exported = adapter.export_provider_config()
        assert exported.get("site_id") == _SITE_ID

    @pytest.mark.asyncio
    async def test_sync_multi_collection(self) -> None:
        adapter = _webflow_adapter(
            {
                ("GET", f"/collections/{_BLOG_COLL}/items/live"): (
                    200,
                    {
                        "items": [_sample_item("blog-1")],
                        "pagination": {"offset": 0, "limit": 100, "total": 1},
                    },
                ),
                ("GET", f"/collections/{_GUIDES_COLL}/items/live"): (
                    200,
                    {
                        "items": [_sample_item("guide-1", collection_slug="guides")],
                        "pagination": {"offset": 0, "limit": 100, "total": 1},
                    },
                ),
            }
        )
        posts, truncated = await adapter.list_all_posts()
        assert truncated is False
        assert len(posts) == 2
        collection_ids = {p.raw_metadata.get("collection_id") for p in posts}
        assert collection_ids == {_BLOG_COLL, _GUIDES_COLL}

    @pytest.mark.asyncio
    async def test_publish_to_explicit_collection(self) -> None:
        adapter = _webflow_adapter(
            {
                ("POST", f"/collections/{_GUIDES_COLL}/items/live"): (
                    200,
                    _sample_item("new-guide", collection_slug="guides"),
                ),
            }
        )
        from core.cms.models import CMSPostCreate

        created = await adapter.publish_post(
            CMSPostCreate(
                title="New Guide",
                slug="new-guide",
                content_html="<p>Guide body</p>",
                status=CMSPostStatus.publish,
                collection_id=_GUIDES_COLL,
            )
        )
        assert created.cms_id == "new-guide"

    @pytest.mark.asyncio
    async def test_refresh_resolves_non_default_collection(self) -> None:
        adapter = _webflow_adapter(
            {
                ("GET", f"/collections/{_BLOG_COLL}/items/guide-1/live"): (
                    404,
                    {"message": "not found", "code": "resource_not_found"},
                ),
                ("GET", f"/collections/{_GUIDES_COLL}/items/guide-1/live"): (
                    200,
                    _sample_item("guide-1", collection_slug="guides"),
                ),
                ("PATCH", f"/collections/{_GUIDES_COLL}/items/guide-1/live"): (
                    200,
                    _sample_item(
                        "guide-1",
                        collection_slug="guides",
                    ),
                ),
            }
        )
        from core.cms.models import CMSPostUpdate

        updated = await adapter.update_post(
            "guide-1",
            CMSPostUpdate(title="Refreshed Guide", content_html="<p>Updated</p>"),
        )
        assert updated.cms_id == "guide-1"


class TestWebflowCMSServiceE2E:
    """CMSService orchestration over Webflow adapter."""

    @pytest.mark.asyncio
    async def test_sync_publish_refresh_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = _make_service()
        conn = _webflow_connection()

        blog_item = _sample_item("blog-sync-1")
        guide_item = _sample_item("guide-sync-1", collection_slug="guides")

        adapter = _webflow_adapter(
            {
                ("GET", f"/collections/{_BLOG_COLL}/items/live"): (
                    200,
                    {
                        "items": [blog_item],
                        "pagination": {"offset": 0, "limit": 100, "total": 1},
                    },
                ),
                ("GET", f"/collections/{_GUIDES_COLL}/items/live"): (
                    200,
                    {
                        "items": [guide_item],
                        "pagination": {"offset": 0, "limit": 100, "total": 1},
                    },
                ),
                ("POST", f"/collections/{_BLOG_COLL}/items/live"): (
                    200,
                    _sample_item("published-1"),
                ),
                ("GET", f"/collections/{_BLOG_COLL}/items/published-1/live"): (
                    200,
                    _sample_item("published-1"),
                ),
                ("GET", f"/collections/{_GUIDES_COLL}/items/published-1/live"): (
                    404,
                    {"message": "not found", "code": "resource_not_found"},
                ),
                ("PATCH", f"/collections/{_BLOG_COLL}/items/published-1/live"): (
                    200,
                    _sample_item("published-1"),
                ),
            }
        )

        monkeypatch.setattr(
            "core.services.cms_service.create_cms_adapter",
            lambda *_args, **_kwargs: adapter,
        )

        sync_result = await service.sync_existing_content("test-co", conn)
        assert sync_result["synced"] == 2
        assert sync_result["stale"] == 0
        assert service._synced_post_repo.upsert_from_cms.await_count == 2

        published = await service.publish_brief(
            company_slug="test-co",
            brief_id="brief-001",
            connection=conn,
            effective_slug="test-co",
            target_status="publish",
            publish_metadata=CMSPublishMetadata(
                slug="published-1",
                meta_title="Published Title",
                meta_description="Meta",
            ),
            collection_id=_BLOG_COLL,
        )
        assert published.cms_id == "published-1"

        refreshed = await service.refresh_post(
            company_slug="test-co",
            cms_post_id="published-1",
            brief_id="refresh-brief-001",
            connection=conn,
            effective_slug="test-co",
        )
        assert refreshed.cms_id == "published-1"

        from core.db.enums import CMSPublishAction

        refresh_call = service._publish_repo.create.await_args_list[-1].kwargs
        assert refresh_call["action"] == CMSPublishAction.refresh
