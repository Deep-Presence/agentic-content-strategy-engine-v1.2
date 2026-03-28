"""Tests for task store initialization in app lifespan.

Verifies:
- DATABASE_URL required — RuntimeError without it
- DbTaskStore created when DATABASE_URL is set
- RuntimeError on DB init failure (no fallback)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.app import _init_task_store


@pytest.fixture
def app_stub() -> MagicMock:
    """Minimal app stub with state attributes."""
    app = MagicMock()
    app.state.redis_healthy = False
    return app


class TestInitTaskStore:
    """Tests for _init_task_store helper."""

    @pytest.mark.asyncio
    async def test_raises_without_database_url(self, app_stub: MagicMock):
        """No DATABASE_URL → raises RuntimeError."""
        with patch("core.config.settings.settings") as mock_settings:
            mock_settings.database_url = None

            with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
                await _init_task_store(app_stub)

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
            mock_settings.redis_pipeline_state = False
            store = await _init_task_store(app_stub)

        from core.services.db_task_store import DbTaskStore

        assert isinstance(store, DbTaskStore)
        mock_recover.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_on_session_factory_failure(self, app_stub: MagicMock):
        """DATABASE_URL set but get_session_factory fails → RuntimeError (no fallback)."""
        with (
            patch("core.config.settings.settings") as mock_settings,
            patch(
                "core.db.engine.get_session_factory",
                side_effect=RuntimeError("Connection refused"),
            ),
        ):
            mock_settings.database_url = "postgresql+asyncpg://localhost/testdb"

            with pytest.raises(RuntimeError):
                await _init_task_store(app_stub)

    @pytest.mark.asyncio
    async def test_raises_on_recover_failure(self, app_stub: MagicMock):
        """DATABASE_URL set, session OK, but recover_from_db fails → RuntimeError."""
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
            mock_settings.redis_pipeline_state = False

            with pytest.raises(Exception):
                await _init_task_store(app_stub)
