"""Tests for core.audit.sink — audit persistence sinks."""
from __future__ import annotations

import pytest

from core.audit.models import AuditEvent, AuditEventType
from core.audit.sink import AuditSinkProtocol, DbAuditSink, NoOpAuditSink


def _make_event() -> AuditEvent:
    return AuditEvent(
        event_type=AuditEventType.LOGIN_SUCCESS,
        user_id="u-1",
        company_slug="ramp",
        detail={"test": True},
    )


class TestNoOpAuditSink:
    @pytest.mark.asyncio
    async def test_persist_does_nothing(self) -> None:
        sink = NoOpAuditSink()
        await sink.persist(_make_event())  # Should not raise

    def test_satisfies_protocol(self) -> None:
        assert isinstance(NoOpAuditSink(), AuditSinkProtocol)


class TestDbAuditSink:
    def test_satisfies_protocol(self) -> None:
        # DbAuditSink needs a session_factory — use a dummy for protocol check
        from unittest.mock import MagicMock

        sink = DbAuditSink(session_factory=MagicMock())
        assert isinstance(sink, AuditSinkProtocol)

    @pytest.mark.asyncio
    async def test_handles_import_error_gracefully(self) -> None:
        """If DB models aren't available, persist catches and logs."""
        from unittest.mock import AsyncMock, MagicMock

        # Create a mock session factory that raises on use
        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(side_effect=ImportError("no DB models"))
        mock_session.__aexit__ = AsyncMock()
        mock_factory.return_value = mock_session

        sink = DbAuditSink(session_factory=mock_factory)
        # Should not raise
        await sink.persist(_make_event())
