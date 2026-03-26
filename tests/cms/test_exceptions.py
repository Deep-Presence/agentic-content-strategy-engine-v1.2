"""Tests for CMS exception hierarchy."""
from __future__ import annotations

from core.cms.exceptions import (
    CMSAPIError,
    CMSAuthError,
    CMSConnectionError,
    CMSError,
    CMSNotFoundError,
    CMSRateLimitError,
)


class TestExceptionHierarchy:
    """Every CMS exception is a subclass of CMSError and Exception."""

    def test_cms_error_is_exception(self) -> None:
        assert issubclass(CMSError, Exception)

    def test_auth_error_inherits_cms_error(self) -> None:
        assert issubclass(CMSAuthError, CMSError)

    def test_api_error_inherits_cms_error(self) -> None:
        assert issubclass(CMSAPIError, CMSError)

    def test_not_found_error_inherits_cms_error(self) -> None:
        assert issubclass(CMSNotFoundError, CMSError)

    def test_rate_limit_error_inherits_cms_error(self) -> None:
        assert issubclass(CMSRateLimitError, CMSError)

    def test_connection_error_inherits_cms_error(self) -> None:
        assert issubclass(CMSConnectionError, CMSError)

    def test_message_propagation(self) -> None:
        err = CMSAuthError("bad credentials")
        assert str(err) == "bad credentials"

    def test_catch_broadly_via_cms_error(self) -> None:
        """All subtypes are catchable via ``except CMSError``."""
        for exc_cls in (
            CMSAuthError,
            CMSAPIError,
            CMSNotFoundError,
            CMSRateLimitError,
            CMSConnectionError,
        ):
            try:
                raise exc_cls("test")
            except CMSError:
                pass  # expected
