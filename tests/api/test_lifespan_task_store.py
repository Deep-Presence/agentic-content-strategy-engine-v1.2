"""Tests for task store initialization in app lifespan.

Verifies:
- Default: JSON TaskStore when no DATABASE_URL
- DbTaskStore when DATABASE_URL set
- Fallback to JSON TaskStore on DB init failure
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.app import _init_task_store
from api.tasks.store import TaskStore


@pytest.fixture
def app_stub() -> MagicMock:
    """Minimal app stub with event_bus on state."""
    from api.tasks.event_bus import EventBus

    app = MagicMock()
    app.state.event_bus = EventBus()
    return app


class TestInitTaskStore:
    """Tests for _init_task_store helper."""

    @pytest.mark.asyncio
    async def test_default_json_task_store(self, app_stub: MagicMock):
        """No DATABASE_URL → returns JSON TaskStore."""
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.database_url = None
            store = await _init_task_store(app_stub)

        assert isinstance(store, TaskStore)

    @pytest.mark.asyncio
    async def test_db_task_store_when_database_url_set(self, app_stub: MagicMock):
        """DATABASE_URL set → creates DbTaskStore and recovers from DB."""
        mock_recover = AsyncMock(return_value=0)

        with (
            patch("core.config.settings.settings") as mock_settings,
            patch(
                "core.db.engine.get_session_factory",
                return_value=MagicMock(),
            ),
            patch(
                "core.services.db_task_store.DbTaskStore.recover_from_db",
                mock_recover,
            ),
        ):
            mock_settings.database_url = "postgresql+asyncpg://localhost/testdb"
            store = await _init_task_store(app_stub)

        from core.services.db_task_store import DbTaskStore

        assert isinstance(store, DbTaskStore)
        mock_recover.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_on_session_factory_failure(self, app_stub: MagicMock):
        """DATABASE_URL set but get_session_factory fails → falls back to JSON."""
        with (
            patch("core.config.settings.settings") as mock_settings,
            patch(
                "core.db.engine.get_session_factory",
                side_effect=RuntimeError("Connection refused"),
            ),
        ):
            mock_settings.database_url = "postgresql+asyncpg://localhost/testdb"
            store = await _init_task_store(app_stub)

        assert isinstance(store, TaskStore)

    @pytest.mark.asyncio
    async def test_fallback_on_recover_failure(self, app_stub: MagicMock):
        """DATABASE_URL set, session OK, but recover_from_db fails → fallback."""
        with (
            patch("core.config.settings.settings") as mock_settings,
            patch(
                "core.db.engine.get_session_factory",
                return_value=MagicMock(),
            ),
            patch(
                "core.services.db_task_store.DbTaskStore.recover_from_db",
                AsyncMock(side_effect=Exception("DB corrupt")),
            ),
        ):
            mock_settings.database_url = "postgresql+asyncpg://localhost/testdb"
            store = await _init_task_store(app_stub)

        assert isinstance(store, TaskStore)
