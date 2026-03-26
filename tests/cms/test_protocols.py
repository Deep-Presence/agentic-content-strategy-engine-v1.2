"""Tests for CMSAdapterProtocol runtime checkability."""
from __future__ import annotations

from core.cms.protocols import CMSAdapterProtocol


class _CompleteMock:
    """Mock that implements all protocol methods (signatures only)."""

    async def validate_connection(self):  # noqa: ANN201
        ...

    async def list_posts(self, *, page=1, per_page=100, status="publish", after=None, modified_after=None):  # noqa: ANN201
        ...

    async def get_post(self, post_id):  # noqa: ANN201
        ...

    async def list_categories(self):  # noqa: ANN201
        ...

    async def publish_post(self, post):  # noqa: ANN201
        ...

    async def update_post(self, post_id, updates):  # noqa: ANN201
        ...

    async def upload_media(self, media):  # noqa: ANN201
        ...


class _IncompleteMock:
    """Mock missing ``upload_media``."""

    async def validate_connection(self):  # noqa: ANN201
        ...

    async def list_posts(self, *, page=1, per_page=100, status="publish", after=None, modified_after=None):  # noqa: ANN201
        ...

    async def get_post(self, post_id):  # noqa: ANN201
        ...

    async def list_categories(self):  # noqa: ANN201
        ...

    async def publish_post(self, post):  # noqa: ANN201
        ...

    async def update_post(self, post_id, updates):  # noqa: ANN201
        ...


class TestProtocolChecks:
    def test_complete_mock_satisfies_protocol(self) -> None:
        assert isinstance(_CompleteMock(), CMSAdapterProtocol)

    def test_incomplete_mock_fails_protocol(self) -> None:
        assert not isinstance(_IncompleteMock(), CMSAdapterProtocol)

    def test_protocol_is_runtime_checkable(self) -> None:
        """The protocol decorator allows isinstance() checks."""
        assert hasattr(CMSAdapterProtocol, "__protocol_attrs__") or hasattr(
            CMSAdapterProtocol, "__abstractmethods__"
        )
