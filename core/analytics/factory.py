"""Analytics adapter factory — returns the correct adapter for a given provider."""
from __future__ import annotations

from core.analytics.adapters.ga4 import GA4Adapter
from core.analytics.protocols import AnalyticsAdapterProtocol
from core.db.enums import AnalyticsProvider

_ADAPTER_REGISTRY: dict[AnalyticsProvider, type] = {
    AnalyticsProvider.ga4: GA4Adapter,
}


def create_analytics_adapter(
    provider: AnalyticsProvider,
    *,
    client_id: str = "",
    client_secret: str = "",
    redirect_uri: str = "",
) -> AnalyticsAdapterProtocol:
    """Instantiate the adapter for *provider*.

    Raises ``ValueError`` if *provider* is not registered.
    """
    adapter_cls = _ADAPTER_REGISTRY.get(provider)
    if adapter_cls is None:
        raise ValueError(f"No adapter registered for analytics provider: {provider}")
    return adapter_cls(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
