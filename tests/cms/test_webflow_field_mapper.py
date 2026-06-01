"""Tests for Webflow field mapper."""
from __future__ import annotations

from core.cms.adapters.webflow.field_mapper import (
    build_field_data_for_create,
    build_field_data_for_update,
    parse_webflow_item,
)
from core.cms.models import CMSPostCreate, CMSPostStatus, CMSPostUpdate
from core.cms.webflow_models import WebflowCollectionConfig, WebflowFieldMapping


def _collection() -> WebflowCollectionConfig:
    return WebflowCollectionConfig(
        collection_id="coll-1",
        collection_slug="blog",
        field_mapping=WebflowFieldMapping(
            title_field="name",
            slug_field="slug",
            body_field="post-body",
            seo_title_field="meta-title",
            category_field="category",
        ),
    )


class TestFieldMapper:
    def test_parse_webflow_item(self) -> None:
        raw = {
            "id": "item-1",
            "isDraft": False,
            "lastPublished": "2026-01-10T12:00:00.000Z",
            "lastUpdated": "2026-02-01T08:30:00.000Z",
            "fieldData": {
                "name": "Hello Webflow",
                "slug": "hello-webflow",
                "post-body": "<p>Body</p>",
                "meta-title": "SEO Title",
                "category": "Guides",
            },
        }
        post = parse_webflow_item(raw, collection=_collection(), item_url="https://x.com/blog/hello-webflow")
        assert post.cms_id == "item-1"
        assert post.title == "Hello Webflow"
        assert post.slug == "hello-webflow"
        assert post.content_html == "<p>Body</p>"
        assert post.seo_title == "SEO Title"
        assert post.categories == ["Guides"]
        assert post.raw_metadata["collection_id"] == "coll-1"

    def test_build_field_data_for_create(self) -> None:
        create = CMSPostCreate(
            title="New Post",
            slug="new-post",
            content_html="<p>Hi</p>",
            seo_title="New",
            categories=["News"],
            status=CMSPostStatus.publish,
        )
        field_data = build_field_data_for_create(create, _collection().field_mapping)
        assert field_data["name"] == "New Post"
        assert field_data["slug"] == "new-post"
        assert field_data["post-body"] == "<p>Hi</p>"
        assert field_data["meta-title"] == "New"
        assert field_data["category"] == "News"

    def test_build_field_data_for_update_partial(self) -> None:
        updates = CMSPostUpdate(title="Updated", content_html="<p>New</p>")
        field_data = build_field_data_for_update(updates, _collection().field_mapping)
        assert field_data == {"name": "Updated", "post-body": "<p>New</p>"}
