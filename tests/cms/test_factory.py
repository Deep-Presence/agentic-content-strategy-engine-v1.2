"""Tests for CMS adapter factory."""
from __future__ import annotations

import pytest

from core.cms.adapters.webflow import WebflowAdapter
from core.cms.adapters.wordpress import WordPressAdapter
from core.cms.factory import create_cms_adapter
from core.cms.models import CMSConnectionConfig
from core.cms.protocols import CMSAdapterProtocol
from core.db.enums import CMSProvider


def _wp_config() -> CMSConnectionConfig:
    return CMSConnectionConfig(
        provider=CMSProvider.wordpress,
        site_url="https://blog.example.com",
        username="admin",
        api_key="xxxx xxxx xxxx xxxx",
    )


class TestFactory:
    def test_create_wordpress_adapter(self) -> None:
        adapter = create_cms_adapter(_wp_config())
        assert isinstance(adapter, WordPressAdapter)

    def test_create_webflow_adapter(self) -> None:
        config = CMSConnectionConfig(
            provider=CMSProvider.webflow,
            site_url="https://marketing.example.com",
            api_key="wf-token",
            provider_config={"site_id": "site-1"},
        )
        adapter = create_cms_adapter(config)
        assert isinstance(adapter, WebflowAdapter)

    def test_satisfies_protocol(self) -> None:
        adapter = create_cms_adapter(_wp_config())
        assert isinstance(adapter, CMSAdapterProtocol)

    def test_unsupported_provider_raises(self) -> None:
        config = CMSConnectionConfig(provider=CMSProvider.strapi)
        with pytest.raises(ValueError, match="Unsupported CMS provider"):
            create_cms_adapter(config)

    def test_error_message_includes_supported(self) -> None:
        config = CMSConnectionConfig(provider=CMSProvider.strapi)
        with pytest.raises(ValueError, match="wordpress"):
            create_cms_adapter(config)

    def test_kwargs_forwarded_to_adapter(self) -> None:
        """Extra kwargs like _transport are passed through."""
        adapter = create_cms_adapter(_wp_config(), _transport=None)
        assert isinstance(adapter, WordPressAdapter)
