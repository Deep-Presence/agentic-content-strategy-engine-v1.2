"""Regression tests for analytics repository SQL construction."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.db.repositories.analytics_repo import (
    GA4ConversionEventRepository,
    GA4TrafficDataRepository,
)


class _FakeInsert:
    def __init__(self, excluded: SimpleNamespace) -> None:
        self.excluded = excluded
        self.items = None
        self.conflict_kwargs: dict[str, object] | None = None

    def values(self, items):
        self.items = items
        return self

    def on_conflict_do_update(self, **kwargs):
        self.conflict_kwargs = kwargs
        return self


class TestTrafficBulkUpsertSQL:
    @pytest.mark.asyncio
    async def test_uses_index_elements_not_constraint(self, monkeypatch) -> None:
        fake_stmt = _FakeInsert(
            SimpleNamespace(
                campaign="campaign",
                sessions="sessions",
                engaged_sessions="engaged_sessions",
                engagement_rate="engagement_rate",
                bounce_rate="bounce_rate",
                avg_session_duration_secs="avg_session_duration_secs",
                screen_page_views="screen_page_views",
                conversions="conversions",
                new_users="new_users",
                returning_users="returning_users",
                synced_at="synced_at",
            )
        )
        monkeypatch.setattr(
            "core.db.repositories.analytics_repo.pg_insert",
            lambda _: fake_stmt,
        )
        session = AsyncMock()
        session.execute.return_value = SimpleNamespace(rowcount=2)
        repo = GA4TrafficDataRepository(session)

        count = await repo.bulk_upsert([{"connection_id": "conn-id"}])

        assert count == 2
        assert fake_stmt.conflict_kwargs is not None
        assert fake_stmt.conflict_kwargs["index_elements"] == [
            "connection_id",
            "date",
            "landing_page_url",
            "source",
            "medium",
        ]
        assert "constraint" not in fake_stmt.conflict_kwargs


class TestConversionBulkUpsertSQL:
    @pytest.mark.asyncio
    async def test_uses_index_elements_not_constraint(self, monkeypatch) -> None:
        fake_stmt = _FakeInsert(
            SimpleNamespace(
                event_count="event_count",
                event_value="event_value",
                synced_at="synced_at",
            )
        )
        monkeypatch.setattr(
            "core.db.repositories.analytics_repo.pg_insert",
            lambda _: fake_stmt,
        )
        session = AsyncMock()
        session.execute.return_value = SimpleNamespace(rowcount=1)
        repo = GA4ConversionEventRepository(session)

        count = await repo.bulk_upsert([{"connection_id": "conn-id"}])

        assert count == 1
        assert fake_stmt.conflict_kwargs is not None
        assert fake_stmt.conflict_kwargs["index_elements"] == [
            "connection_id",
            "date",
            "event_name",
            "landing_page_url",
            "source",
            "medium",
        ]
        assert "constraint" not in fake_stmt.conflict_kwargs
