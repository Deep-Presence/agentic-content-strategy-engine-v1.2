"""CMS adapter factory.

Usage::

    adapter = create_cms_adapter(config)
    status = await adapter.validate_connection()
"""
from __future__ import annotations

from core.cms.adapters.webflow import WebflowAdapter
from core.cms.adapters.wordpress import WordPressAdapter
from core.cms.models import CMSConnectionConfig
from core.cms.protocols import CMSAdapterProtocol
from core.db.enums import CMSProvider

_ADAPTER_REGISTRY: dict[CMSProvider, type] = {
    CMSProvider.wordpress: WordPressAdapter,
    CMSProvider.webflow: WebflowAdapter,
    # CMSProvider.strapi: StrapiAdapter,     # Future
}


def create_cms_adapter(
    config: CMSConnectionConfig,
    **kwargs: object,
) -> CMSAdapterProtocol:
    """Instantiate the correct adapter based on provider type.

    Raises ``ValueError`` if the provider is not yet supported.
    Extra ``kwargs`` are forwarded to the adapter constructor
    (e.g. ``_transport`` for test injection).
    """
    adapter_cls = _ADAPTER_REGISTRY.get(config.provider)
    if adapter_cls is None:
        supported = ", ".join(p.value for p in _ADAPTER_REGISTRY)
        raise ValueError(
            f"Unsupported CMS provider: {config.provider.value}. "
            f"Supported: {supported}"
        )
    return adapter_cls(config, **kwargs)
