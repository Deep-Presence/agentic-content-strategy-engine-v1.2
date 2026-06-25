"""Tests for Webflow provider config models."""
from __future__ import annotations

import pytest

from core.cms.webflow_models import (
    WebflowCollectionConfig,
    WebflowFieldMapping,
    WebflowProviderConfig,
)


class TestWebflowProviderConfig:
    def test_enabled_collections_filters_disabled(self) -> None:
        cfg = WebflowProviderConfig(
            collections=[
                WebflowCollectionConfig(
                    collection_id="a",
                    enabled=True,
                    field_mapping=WebflowFieldMapping(body_field="body"),
                ),
                WebflowCollectionConfig(collection_id="b", enabled=False),
            ]
        )
        enabled = cfg.enabled_collections()
        assert len(enabled) == 1
        assert enabled[0].collection_id == "a"

    def test_resolve_publish_collection_explicit(self) -> None:
        cfg = WebflowProviderConfig(default_collection_id="default")
        assert cfg.resolve_publish_collection_id("explicit") == "explicit"

    def test_resolve_publish_collection_default_flag(self) -> None:
        cfg = WebflowProviderConfig(
            collections=[
                WebflowCollectionConfig(collection_id="x", enabled=True),
                WebflowCollectionConfig(
                    collection_id="y",
                    enabled=True,
                    is_default_publish_target=True,
                ),
            ]
        )
        assert cfg.resolve_publish_collection_id() == "y"

    def test_rejects_multiple_default_publish_targets(self) -> None:
        with pytest.raises(ValueError, match="default publish target"):
            WebflowProviderConfig(
                collections=[
                    WebflowCollectionConfig(
                        collection_id="a",
                        enabled=True,
                        is_default_publish_target=True,
                    ),
                    WebflowCollectionConfig(
                        collection_id="b",
                        enabled=True,
                        is_default_publish_target=True,
                    ),
                ]
            )

    def test_roundtrip_provider_config(self) -> None:
        cfg = WebflowProviderConfig(
            site_id="site-123",
            collections=[
                WebflowCollectionConfig(
                    collection_id="coll-1",
                    collection_slug="blog-posts",
                    display_name="Blog Posts",
                    field_mapping=WebflowFieldMapping(
                        title_field="name",
                        body_field="post-body",
                    ),
                )
            ],
        )
        restored = WebflowProviderConfig.from_provider_config(cfg.to_provider_config())
        assert restored.site_id == "site-123"
        assert restored.collections[0].collection_slug == "blog-posts"
