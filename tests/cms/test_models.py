"""Tests for CMS Pydantic domain models."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from core.cms.models import (
    CMSCategory,
    CMSConnectionConfig,
    CMSConnectionStatus,
    CMSMediaResult,
    CMSMediaUpload,
    CMSPost,
    CMSPostCreate,
    CMSPostStatus,
    CMSPostUpdate,
    CMSProvider,
)


class TestEnumValues:
    """Enum values use lowercase (codebase convention)."""

    def test_cms_provider_wordpress(self) -> None:
        assert CMSProvider.wordpress.value == "wordpress"

    def test_cms_provider_all_values(self) -> None:
        expected = {"wordpress", "webflow", "strapi", "ghost", "hubspot"}
        assert {p.value for p in CMSProvider} == expected

    def test_post_status_values(self) -> None:
        expected = {"draft", "publish", "pending", "private"}
        assert {s.value for s in CMSPostStatus} == expected

    def test_enum_serialization_to_string(self) -> None:
        """Enums serialize to plain strings in JSON mode."""
        config = CMSConnectionConfig(provider=CMSProvider.wordpress)
        data = config.model_dump(mode="json")
        assert data["provider"] == "wordpress"


class TestCMSConnectionConfig:
    def test_defaults(self) -> None:
        config = CMSConnectionConfig()
        assert config.provider == CMSProvider.wordpress
        assert config.site_url == ""
        assert config.api_key == ""
        assert config.username == ""
        assert config.extra == {}

    def test_populated(self) -> None:
        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url="https://blog.ramp.com",
            api_key="app-password-123",
            username="admin",
            extra={"custom": True},
        )
        assert config.site_url == "https://blog.ramp.com"
        assert config.extra == {"custom": True}

    def test_roundtrip(self) -> None:
        config = CMSConnectionConfig(
            provider=CMSProvider.wordpress,
            site_url="https://example.com",
            api_key="secret",
        )
        data = json.loads(config.model_dump_json())
        restored = CMSConnectionConfig(**data)
        assert restored == config


class TestCMSConnectionStatus:
    def test_defaults(self) -> None:
        status = CMSConnectionStatus()
        assert status.connected is False
        assert status.error is None
        assert status.capabilities == []

    def test_connected(self) -> None:
        status = CMSConnectionStatus(
            connected=True,
            site_name="Ramp Blog",
            capabilities=["publish_posts", "upload_files"],
        )
        assert status.connected is True
        assert len(status.capabilities) == 2

    def test_error_state(self) -> None:
        status = CMSConnectionStatus(connected=False, error="Invalid credentials")
        assert status.error == "Invalid credentials"


class TestCMSPost:
    def test_defaults(self) -> None:
        post = CMSPost()
        assert post.cms_id == ""
        assert post.status == CMSPostStatus.publish
        assert post.categories == []
        assert post.raw_metadata == {}
        assert post.published_at is None

    def test_with_datetime(self) -> None:
        now = datetime.now(timezone.utc)
        post = CMSPost(
            cms_id="42",
            title="Test Post",
            published_at=now,
            modified_at=now,
        )
        data = json.loads(post.model_dump_json())
        restored = CMSPost(**data)
        assert restored.published_at is not None
        assert restored.cms_id == "42"

    def test_roundtrip(self) -> None:
        post = CMSPost(
            cms_id="1",
            title="Hello",
            slug="hello",
            content_html="<p>Hi</p>",
            status=CMSPostStatus.draft,
            categories=["AI", "B2B"],
            word_count=100,
        )
        data = json.loads(post.model_dump_json())
        restored = CMSPost(**data)
        assert restored == post


class TestCMSPostCreate:
    def test_defaults_to_draft(self) -> None:
        create = CMSPostCreate()
        assert create.status == CMSPostStatus.draft

    def test_with_fields(self) -> None:
        create = CMSPostCreate(
            title="New Article",
            slug="new-article",
            content_html="<h1>New</h1>",
            categories=["SEO"],
            seo_title="New Article | Ramp",
        )
        assert create.title == "New Article"
        assert create.seo_title == "New Article | Ramp"


class TestCMSPostUpdate:
    def test_all_none_by_default(self) -> None:
        update = CMSPostUpdate()
        assert update.title is None
        assert update.content_html is None
        assert update.slug is None

    def test_partial_update(self) -> None:
        update = CMSPostUpdate(title="Updated Title", content_html="<p>New</p>")
        assert update.title == "Updated Title"
        assert update.slug is None  # not changed


class TestCMSCategory:
    def test_defaults(self) -> None:
        cat = CMSCategory()
        assert cat.cms_id == ""
        assert cat.parent_id is None
        assert cat.post_count == 0

    def test_roundtrip(self) -> None:
        cat = CMSCategory(cms_id="5", name="AI Research", slug="ai-research", post_count=12)
        data = json.loads(cat.model_dump_json())
        restored = CMSCategory(**data)
        assert restored == cat


class TestCMSMedia:
    def test_upload_defaults(self) -> None:
        upload = CMSMediaUpload()
        assert upload.content_bytes == b""
        assert upload.mime_type == "image/png"

    def test_result_defaults(self) -> None:
        result = CMSMediaResult()
        assert result.cms_id == ""
        assert result.url == ""
