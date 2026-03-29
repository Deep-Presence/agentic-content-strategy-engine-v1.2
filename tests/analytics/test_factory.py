"""Tests for analytics adapter factory."""
from __future__ import annotations

import pytest

from core.analytics.adapters.ga4 import GA4Adapter
from core.analytics.factory import create_analytics_adapter
from core.analytics.protocols import AnalyticsAdapterProtocol
from core.db.enums import AnalyticsProvider


class TestFactory:
    def test_create_ga4_adapter(self) -> None:
        adapter = create_analytics_adapter(
            AnalyticsProvider.ga4,
            client_id="id",
            client_secret="secret",
            redirect_uri="http://localhost",
        )
        assert isinstance(adapter, GA4Adapter)

    def test_satisfies_protocol(self) -> None:
        adapter = create_analytics_adapter(
            AnalyticsProvider.ga4,
            client_id="id",
            client_secret="secret",
            redirect_uri="http://localhost",
        )
        assert isinstance(adapter, AnalyticsAdapterProtocol)

    def test_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="No adapter registered"):
            create_analytics_adapter("unknown_provider")  # type: ignore[arg-type]
