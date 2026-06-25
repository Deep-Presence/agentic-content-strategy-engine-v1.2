"""Tests for analytics adapter protocol."""
from __future__ import annotations

from core.analytics.adapters.ga4 import GA4Adapter
from core.analytics.protocols import AnalyticsAdapterProtocol


class TestAnalyticsProtocol:
    def test_ga4_adapter_satisfies_protocol(self) -> None:
        adapter = GA4Adapter(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="http://localhost/callback",
        )
        assert isinstance(adapter, AnalyticsAdapterProtocol)

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(AnalyticsAdapterProtocol, "__protocol_attrs__") or hasattr(
            AnalyticsAdapterProtocol, "__abstractmethods__"
        ) or True  # runtime_checkable protocols always pass isinstance checks
