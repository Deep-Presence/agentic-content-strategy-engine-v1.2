"""Tests for GA4 analytics exceptions."""
from __future__ import annotations

from core.analytics.exceptions import GA4APIError, GA4AuthError, GA4Error, GA4QuotaError


class TestGA4Exceptions:
    def test_hierarchy(self) -> None:
        assert issubclass(GA4AuthError, GA4Error)
        assert issubclass(GA4QuotaError, GA4Error)
        assert issubclass(GA4APIError, GA4Error)

    def test_message_propagation(self) -> None:
        err = GA4AuthError("token expired", status_code=401)
        assert str(err) == "token expired"
        assert err.status_code == 401

    def test_default_status_code_is_none(self) -> None:
        err = GA4Error("oops")
        assert err.status_code is None

    def test_catch_base_catches_subclasses(self) -> None:
        try:
            raise GA4QuotaError("rate limited", status_code=429)
        except GA4Error as exc:
            assert exc.status_code == 429
