"""Tests for Webflow field mapping heuristics (WF-2)."""
from __future__ import annotations

from core.cms.adapters.webflow.field_mapper import suggest_field_mapping


def _fields(*specs: tuple[str, str, str]) -> list[dict]:
    return [
        {"slug": slug, "displayName": display, "type": ftype}
        for slug, display, ftype in specs
    ]


class TestSuggestFieldMapping:
    def test_detects_common_blog_fields(self) -> None:
        mapping = suggest_field_mapping(
            _fields(
                ("name", "Name", "PlainText"),
                ("slug", "Slug", "PlainText"),
                ("post-body", "Post Body", "RichText"),
                ("post-summary", "Summary", "PlainText"),
                ("seo-title", "SEO Title", "PlainText"),
                ("seo-description", "SEO Description", "PlainText"),
                ("category", "Category", "Option"),
                ("tags", "Tags", "PlainText"),
                ("main-image", "Main Image", "Image"),
            )
        )
        assert mapping.title_field == "name"
        assert mapping.slug_field == "slug"
        assert mapping.body_field == "post-body"
        assert mapping.excerpt_field == "post-summary"
        assert mapping.seo_title_field == "seo-title"
        assert mapping.seo_description_field == "seo-description"
        assert mapping.category_field == "category"
        assert mapping.tags_field == "tags"
        assert mapping.featured_image_field == "main-image"

    def test_defaults_when_schema_sparse(self) -> None:
        mapping = suggest_field_mapping(_fields(("custom-title", "Title", "PlainText"),))
        assert mapping.title_field == "custom-title"
        assert mapping.slug_field == "slug"
